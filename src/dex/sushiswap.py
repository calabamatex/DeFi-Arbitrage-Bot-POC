"""SushiSwap (Uniswap V2 fork) DEX adapter."""

from decimal import Decimal
from typing import Tuple, Optional, List
from web3 import Web3
from web3.contract import Contract
from .base import DEX
import logging

logger = logging.getLogger(__name__)


class SushiSwap(DEX):
    """SushiSwap (Uniswap V2 fork) adapter."""

    def __init__(self, router_address: str, name: str = "SushiSwap"):
        """
        Initialize SushiSwap adapter.

        Args:
            router_address: SushiSwap router contract address
            name: DEX name
        """
        # Uniswap V2 style router ABI
        router_abi = [
            {
                "inputs": [
                    {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
                    {"internalType": "address[]", "name": "path", "type": "address[]"},
                ],
                "name": "getAmountsOut",
                "outputs": [
                    {
                        "internalType": "uint256[]",
                        "name": "amounts",
                        "type": "uint256[]",
                    }
                ],
                "stateMutability": "view",
                "type": "function",
            },
            {
                "inputs": [
                    {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
                    {
                        "internalType": "uint256",
                        "name": "amountOutMin",
                        "type": "uint256",
                    },
                    {"internalType": "address[]", "name": "path", "type": "address[]"},
                    {"internalType": "address", "name": "to", "type": "address"},
                    {"internalType": "uint256", "name": "deadline", "type": "uint256"},
                ],
                "name": "swapExactTokensForTokens",
                "outputs": [
                    {
                        "internalType": "uint256[]",
                        "name": "amounts",
                        "type": "uint256[]",
                    }
                ],
                "stateMutability": "nonpayable",
                "type": "function",
            },
        ]

        super().__init__(router_address, router_abi, name)
        logger.info(f"Initialized {name} with router at {self.router_address}")

    async def get_token_price(
        self, token_address: str, web3: Web3, amount: Optional[Decimal] = None
    ) -> Decimal:
        """
        Get token price using getAmountsOut.

        Args:
            token_address: Token contract address
            web3: Web3 instance
            amount: Amount to price (defaults to 1 token)

        Returns:
            Price in base currency (WETH)
        """
        try:
            if not self.contract:
                self.initialize_contract(web3)

            assert self.contract is not None, "Router contract not initialized"

            # Default to pricing 1 token
            if amount is None:
                amount = Decimal("1")

            amount_wei = int(amount * Decimal(10**18))

            # Get WETH address (Mumbai testnet WETH)
            weth_address = "0xA6FA4fB5f76172d178d61B04b0ecd319C5d1C0aa"

            # Get best path
            path = self._get_best_path(token_address, weth_address)

            # Get amounts out
            amounts = self.contract.functions.getAmountsOut(amount_wei, path).call()

            # Return last amount (output amount)
            price = Decimal(amounts[-1]) / Decimal(10**18)
            logger.debug(f"Got price for {token_address}: {price} WETH")
            return price

        except Exception as e:
            logger.error(f"Error getting price from {self.name}: {e}")
            return Decimal("0")

    def _get_best_path(self, token_in: str, token_out: str) -> List[str]:
        """
        Get best path for swap.

        Try direct path first, fall back to routing through WETH.

        Args:
            token_in: Input token address
            token_out: Output token address

        Returns:
            List of token addresses representing the swap path
        """
        # Checksum addresses
        token_in_checksum = Web3.to_checksum_address(token_in)
        token_out_checksum = Web3.to_checksum_address(token_out)

        # For now, always use direct path
        # In production, you'd check if pair exists first
        path: List[str] = [token_in_checksum, token_out_checksum]

        logger.debug(f"Using direct path: {' -> '.join(path)}")
        return path

    async def execute_trade(
        self,
        token_in: str,
        token_out: str,
        amount: Decimal,
        web3: Web3,
        account: str,
        private_key: str,
    ) -> Tuple[bool, str]:
        """
        Execute swap on SushiSwap.

        Args:
            token_in: Input token address
            token_out: Output token address
            amount: Amount to swap
            web3: Web3 instance
            account: Account address
            private_key: Private key for signing

        Returns:
            Tuple of (success: bool, tx_hash or error_message)
        """
        try:
            if not self.contract:
                self.initialize_contract(web3)

            assert self.contract is not None, "Router contract not initialized"

            # Convert amount to wei
            amount_wei = int(amount * Decimal(10**18))

            # Get expected output
            path = self._get_best_path(token_in, token_out)
            amounts = self.contract.functions.getAmountsOut(amount_wei, path).call()

            # Calculate min output (0.5% slippage)
            expected_out = amounts[-1]
            min_out = int(expected_out * 0.995)

            # Get deadline (5 minutes from now)
            latest_block = web3.eth.get_block("latest")
            deadline = latest_block["timestamp"] + 300

            # Build transaction
            account_checksum = Web3.to_checksum_address(account)
            txn = self.contract.functions.swapExactTokensForTokens(
                amount_wei, min_out, path, account_checksum, deadline
            ).build_transaction(
                {
                    "from": account_checksum,
                    "gas": 300000,
                    "gasPrice": web3.eth.gas_price,
                    "nonce": web3.eth.get_transaction_count(account_checksum),
                }
            )

            # Sign transaction
            signed_txn = web3.eth.account.sign_transaction(txn, private_key)

            # Send transaction
            tx_hash = web3.eth.send_raw_transaction(signed_txn.raw_transaction)

            # Wait for receipt
            receipt = web3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

            if receipt["status"] == 1:
                logger.info(f"{self.name} trade successful: {tx_hash.hex()}")
                return True, tx_hash.hex()
            else:
                logger.error(f"{self.name} trade reverted: {tx_hash.hex()}")
                return False, f"Transaction reverted: {tx_hash.hex()}"

        except Exception as e:
            logger.error(f"Error executing {self.name} trade: {e}")
            return False, str(e)

    async def get_liquidity_depth(
        self, token1: str, token2: str, web3: Web3, max_amount: Decimal
    ) -> Tuple[Decimal, Decimal]:
        """
        Get liquidity depth (simplified).

        Args:
            token1: First token address
            token2: Second token address
            web3: Web3 instance
            max_amount: Maximum amount to check

        Returns:
            Tuple of (available_liquidity, price_impact_percent)

        Note:
            This is a simplified implementation. For accurate V2 liquidity,
            you would need to query the pair contract's reserves.
        """
        try:
            # For V2, would need to query pair contract reserves
            # Simplified for now - assumes reasonable liquidity
            available_liquidity = Decimal("1000000")
            price_impact = (max_amount / available_liquidity) * Decimal("100")

            # Cap impact at 100%
            price_impact = min(price_impact, Decimal("100"))

            logger.debug(
                f"Liquidity for {token1}/{token2}: {available_liquidity}, "
                f"impact: {price_impact}%"
            )
            return available_liquidity, price_impact

        except Exception as e:
            logger.error(f"Error getting liquidity depth: {e}")
            return Decimal("0"), Decimal("100")
