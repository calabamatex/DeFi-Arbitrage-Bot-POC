"""
Transaction Manager - Handles all blockchain transaction operations.

Supports both EIP-1559 type-2 transactions (preferred) and legacy gas pricing.
"""

import asyncio
from decimal import Decimal
from typing import Tuple, Optional, Any, Set, Dict, cast
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

    Supports EIP-1559 type-2 transactions with maxFeePerGas and
    maxPriorityFeePerGas, falling back to legacy gasPrice when
    the network does not support EIP-1559.
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

    def _supports_eip1559(self) -> bool:
        """
        Check whether the connected network supports EIP-1559.

        Returns:
            True if baseFeePerGas is present in the latest block.
        """
        try:
            latest = self.web3.eth.get_block("latest")
            return "baseFeePerGas" in latest and latest["baseFeePerGas"] is not None
        except Exception:
            return False

    def _get_eip1559_fees(
        self, urgency: str = "normal"
    ) -> Dict[str, int]:
        """
        Calculate EIP-1559 fee parameters from the latest block.

        Args:
            urgency: "low", "normal", or "high"

        Returns:
            Dict with maxFeePerGas and maxPriorityFeePerGas in wei.
        """
        latest = self.web3.eth.get_block("latest")
        base_fee = latest.get("baseFeePerGas", self.web3.eth.gas_price)

        priority_map = {
            "low": self.web3.to_wei(1, "gwei"),
            "normal": self.web3.to_wei(2, "gwei"),
            "high": self.web3.to_wei(3, "gwei"),
        }
        priority_fee = priority_map.get(urgency, self.web3.to_wei(2, "gwei"))

        # Allow for one full base-fee doubling: 2 * base + priority
        max_fee = base_fee * 2 + priority_fee

        return {
            "maxFeePerGas": max_fee,
            "maxPriorityFeePerGas": priority_fee,
        }

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

        When *gas_price* is explicitly provided, a legacy (type-0) transaction
        is built for backward compatibility.  When it is ``None`` (the default),
        the manager checks whether the network supports EIP-1559 and, if so,
        builds a type-2 transaction with ``maxFeePerGas`` / ``maxPriorityFeePerGas``.
        On non-EIP-1559 networks it falls back to the legacy ``gasPrice`` field.

        Args:
            contract_function: Contract function to call
            gas_limit: Gas limit for transaction
            value: Value to send (in wei)
            gas_price: Legacy gas price override. When set, forces legacy tx.

        Returns:
            Transaction dictionary
        """
        # Get nonce
        nonce = await self.get_next_nonce()

        # Get chain ID
        chain_id = self.web3.eth.chain_id

        # Build gas parameters
        if gas_price is not None:
            # Caller explicitly requested legacy gas pricing
            gas_params: dict = {"gasPrice": gas_price}
        else:
            # Try EIP-1559; fall back to legacy
            try:
                if self._supports_eip1559():
                    gas_params = self._get_eip1559_fees()
                else:
                    gas_params = {"gasPrice": self.web3.eth.gas_price}
            except Exception:
                gas_params = {"gasPrice": self.web3.eth.gas_price}

        # Assemble base tx fields
        tx_fields: dict = {
            "from": self.account,
            "nonce": nonce,
            "gas": gas_limit,
            "value": value,
            "chainId": chain_id,
        }
        tx_fields.update(gas_params)

        # Build transaction
        try:
            transaction = contract_function.build_transaction(tx_fields)

            if "maxFeePerGas" in gas_params:
                logger.debug(
                    f"Built EIP-1559 tx: nonce={nonce}, gas={gas_limit}, "
                    f"maxFee={gas_params['maxFeePerGas']}, "
                    f"priority={gas_params['maxPriorityFeePerGas']}"
                )
            else:
                logger.debug(
                    f"Built legacy tx: nonce={nonce}, gas={gas_limit}, "
                    f"gasPrice={gas_params.get('gasPrice')}"
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

        On the first attempt, a new nonce is allocated via ``build_transaction``.
        On subsequent retries the same nonce is reused with a gas-bumped
        replacement transaction so that stuck transactions are properly
        superseded instead of creating nonce gaps.

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

                if attempt == 0 or nonce is None:
                    # First attempt: allocate a fresh nonce
                    transaction = await self.build_transaction(
                        contract_function, gas_limit, value
                    )
                    nonce = transaction["nonce"]
                else:
                    # Retry: reuse the same nonce with bumped gas
                    transaction = await self.build_replacement_transaction(
                        contract_function,
                        gas_limit,
                        original_nonce=nonce,
                        value=value,
                        gas_bump_pct=15 * attempt,  # 15%, 30%, ...
                    )

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

                # Release nonce if we have it and won't retry
                if nonce is not None and attempt >= max_retries - 1:
                    self.release_nonce(nonce)

                # Wait before retry
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)

        # All retries failed — ensure nonce is released
        if nonce is not None:
            self.release_nonce(nonce)
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

    async def build_replacement_transaction(
        self,
        contract_function: Any,
        gas_limit: int,
        original_nonce: int,
        value: int = 0,
        gas_bump_pct: int = 15,
    ) -> dict:
        """
        Build a replacement (speed-up) transaction reusing an existing nonce.

        EIP-1559 nodes require at least a 10% bump on both maxFeePerGas and
        maxPriorityFeePerGas to accept a replacement. This method applies
        *gas_bump_pct* (default 15%) on top of current network fees to ensure
        acceptance.

        Args:
            contract_function: Contract function to call
            gas_limit: Gas limit for transaction
            original_nonce: Nonce of the stuck transaction to replace
            value: Value to send (in wei)
            gas_bump_pct: Percentage to bump gas fees (default 15)

        Returns:
            Transaction dictionary with the same nonce and higher fees
        """
        chain_id = self.web3.eth.chain_id
        bump = 1 + gas_bump_pct / 100

        try:
            if self._supports_eip1559():
                fees = self._get_eip1559_fees(urgency="high")
                gas_params: dict = {
                    "maxFeePerGas": int(fees["maxFeePerGas"] * bump),
                    "maxPriorityFeePerGas": int(fees["maxPriorityFeePerGas"] * bump),
                }
            else:
                gas_params = {
                    "gasPrice": int(self.web3.eth.gas_price * bump),
                }

            tx_fields: dict = {
                "from": self.account,
                "nonce": original_nonce,
                "gas": gas_limit,
                "value": value,
                "chainId": chain_id,
            }
            tx_fields.update(gas_params)

            transaction = contract_function.build_transaction(tx_fields)

            logger.info(
                f"Built replacement tx for nonce {original_nonce} "
                f"(+{gas_bump_pct}% gas bump)"
            )
            return transaction

        except Exception as e:
            logger.error(f"Error building replacement transaction: {e}")
            raise

    def get_pending_nonce_count(self) -> int:
        """
        Get number of pending transactions being tracked.

        Returns:
            Number of pending nonces
        """
        return len(self._pending_nonces)
