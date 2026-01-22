"""
Transaction Manager - Handles all blockchain transaction operations.
"""

import asyncio
from decimal import Decimal
from typing import Tuple, Optional, Any, Set, cast
from web3 import Web3
from web3.types import TxParams, TxReceipt, HexStr
from eth_account import Account
import logging
import time

logger = logging.getLogger(__name__)


class TransactionManager:
    """
    Manages blockchain transactions with proper nonce handling,
    signing, sending, and monitoring.
    """

    def __init__(self, web3: Web3, account: str, private_key: str):
        """
        Initialize transaction manager.

        Args:
            web3: Web3 instance
            account: Account address
            private_key: Private key for signing
        """
        self.web3 = web3
        self.account = Web3.to_checksum_address(account)
        self.private_key = private_key
        self._nonce_lock = asyncio.Lock()
        self._pending_nonces: Set[int] = set()

        logger.info(f"TransactionManager initialized for account {self.account}")

    async def get_next_nonce(self) -> int:
        """
        Get next available nonce with thread-safe tracking.

        Returns:
            Next nonce to use
        """
        async with self._nonce_lock:
            # Get pending transaction count
            pending_nonce = self.web3.eth.get_transaction_count(self.account, "pending")

            # If we have pending nonces we're tracking, use max + 1
            if self._pending_nonces:
                tracked_max = max(self._pending_nonces)
                nonce = max(pending_nonce, tracked_max + 1)
            else:
                nonce = pending_nonce

            # Track this nonce
            self._pending_nonces.add(nonce)

            logger.debug(f"Allocated nonce {nonce}")
            return nonce

    def release_nonce(self, nonce: int):
        """
        Release a nonce after transaction completion.

        Args:
            nonce: Nonce to release
        """
        if nonce in self._pending_nonces:
            self._pending_nonces.remove(nonce)
            logger.debug(f"Released nonce {nonce}")

    async def build_transaction(
        self,
        contract_function: Any,
        gas_limit: int,
        value: int = 0,
        gas_price: Optional[int] = None,
    ) -> dict:
        """
        Build transaction dictionary.

        Args:
            contract_function: Contract function to call
            gas_limit: Gas limit for transaction
            value: Value to send (in wei)
            gas_price: Gas price (if None, uses current network price)

        Returns:
            Transaction dictionary
        """
        # Get nonce
        nonce = await self.get_next_nonce()

        # Get gas price if not provided
        if gas_price is None:
            gas_price = self.web3.eth.gas_price

        # Get chain ID
        chain_id = self.web3.eth.chain_id

        # Build transaction
        try:
            transaction = contract_function.build_transaction(
                {
                    "from": self.account,
                    "nonce": nonce,
                    "gas": gas_limit,
                    "gasPrice": gas_price,
                    "value": value,
                    "chainId": chain_id,
                }
            )

            logger.debug(
                f"Built transaction: nonce={nonce}, gas={gas_limit}, "
                f"gasPrice={gas_price}"
            )

            return transaction

        except Exception as e:
            # Release nonce on failure
            self.release_nonce(nonce)
            logger.error(f"Error building transaction: {e}")
            raise

    async def sign_and_send(self, transaction: dict) -> str:
        """
        Sign and send transaction.

        Args:
            transaction: Transaction dictionary

        Returns:
            Transaction hash (hex string)

        Raises:
            Exception: If sending fails
        """
        try:
            # Sign transaction
            signed_txn = self.web3.eth.account.sign_transaction(
                transaction, self.private_key
            )

            logger.debug(f"Signed transaction with nonce {transaction['nonce']}")

            # Send transaction
            tx_hash = self.web3.eth.send_raw_transaction(signed_txn.rawTransaction)

            tx_hash_hex = tx_hash.hex()
            logger.info(f"Transaction sent: {tx_hash_hex}")

            return tx_hash_hex

        except Exception as e:
            logger.error(f"Error signing/sending transaction: {e}")
            raise

    async def wait_for_confirmation(
        self, tx_hash: str, timeout: int = 120, poll_interval: float = 1.0
    ) -> TxReceipt:
        """
        Wait for transaction confirmation.

        Args:
            tx_hash: Transaction hash
            timeout: Maximum time to wait (seconds)
            poll_interval: How often to check (seconds)

        Returns:
            Transaction receipt

        Raises:
            TimeoutError: If transaction not confirmed in time
        """
        logger.info(f"Waiting for confirmation of {tx_hash}")

        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                receipt = self.web3.eth.get_transaction_receipt(cast(HexStr, tx_hash))

                # Check if transaction succeeded
                if receipt["status"] == 1:
                    logger.info(
                        f"Transaction {tx_hash} confirmed successfully in block "
                        f"{receipt['blockNumber']}"
                    )
                else:
                    logger.error(f"Transaction {tx_hash} reverted")

                return receipt

            except Exception:
                # Transaction not yet mined
                await asyncio.sleep(poll_interval)

        raise TimeoutError(
            f"Transaction {tx_hash} not confirmed within {timeout} seconds"
        )

    async def execute_transaction(
        self,
        contract_function: Any,
        gas_limit: int,
        value: int = 0,
        max_retries: int = 3,
        retry_delay: float = 5.0,
    ) -> Tuple[bool, str]:
        """
        Execute transaction with retry logic.

        Args:
            contract_function: Contract function to execute
            gas_limit: Gas limit
            value: Value to send
            max_retries: Maximum retry attempts
            retry_delay: Delay between retries (seconds)

        Returns:
            Tuple of (success: bool, tx_hash or error_message: str)
        """
        last_error = None
        nonce = None

        for attempt in range(max_retries):
            try:
                logger.info(
                    f"Executing transaction (attempt {attempt + 1}/{max_retries})"
                )

                # Build transaction
                transaction = await self.build_transaction(
                    contract_function, gas_limit, value
                )

                nonce = transaction["nonce"]

                # Send transaction
                tx_hash = await self.sign_and_send(transaction)

                # Wait for confirmation
                receipt = await self.wait_for_confirmation(tx_hash)

                # Release nonce
                self.release_nonce(nonce)

                # Check status
                if receipt["status"] == 1:
                    return True, tx_hash
                else:
                    logger.error(f"Transaction reverted: {tx_hash}")
                    return False, f"Transaction reverted: {tx_hash}"

            except Exception as e:
                last_error = str(e)
                logger.error(f"Transaction attempt {attempt + 1} failed: {e}")

                # Release nonce if we have it
                if nonce is not None:
                    self.release_nonce(nonce)

                # Wait before retry
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)

        # All retries failed
        return False, f"All retries failed. Last error: {last_error}"

    async def simulate_transaction(
        self, contract_function: Any, value: int = 0
    ) -> bool:
        """
        Simulate transaction without sending (dry run).

        Args:
            contract_function: Contract function to simulate
            value: Value to send

        Returns:
            True if simulation succeeds, False otherwise
        """
        try:
            # Call the function (doesn't send transaction)
            result = contract_function.call({"from": self.account, "value": value})

            logger.info("Transaction simulation succeeded")
            return True

        except Exception as e:
            logger.error(f"Transaction simulation failed: {e}")
            return False

    async def estimate_gas(self, contract_function: Any, value: int = 0) -> int:
        """
        Estimate gas for transaction.

        Args:
            contract_function: Contract function
            value: Value to send

        Returns:
            Estimated gas amount
        """
        try:
            gas_estimate = contract_function.estimate_gas(
                {"from": self.account, "value": value}
            )

            logger.debug(f"Gas estimate: {gas_estimate}")
            return gas_estimate

        except Exception as e:
            logger.error(f"Gas estimation failed: {e}")
            # Return a conservative default
            return 300000

    def get_pending_nonce_count(self) -> int:
        """
        Get number of pending transactions being tracked.

        Returns:
            Number of pending nonces
        """
        return len(self._pending_nonces)
