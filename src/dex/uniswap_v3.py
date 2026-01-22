"""Uniswap V3 DEX adapter with fee tier optimization."""

from decimal import Decimal
from typing import Tuple, Optional
from web3 import Web3
from web3.contract import Contract
from .base import DEX
import logging

logger = logging.getLogger(__name__)


class UniswapV3(DEX):
    """Uniswap V3 DEX adapter with fee tier optimization."""

    FEE_TIERS = [100, 500, 3000, 10000]  # 0.01%, 0.05%, 0.3%, 1%

    def __init__(
        self,
        router_address: str,
        factory_address: str,
        quoter_address: str,
        name: str = "Uniswap V3",
    ):
        """
        Initialize Uniswap V3 adapter.

        Args:
            router_address: SwapRouter contract address
            factory_address: UniswapV3Factory contract address
            quoter_address: Quoter contract address
            name: DEX name
        """
        # Get Uniswap V3 Router ABI (simplified)
        router_abi = [
            {
                "inputs": [
                    {
                        "components": [
                            {
                                "internalType": "address",
                                "name": "tokenIn",
                                "type": "address",
                            },
                            {
                                "internalType": "address",
                                "name": "tokenOut",
                                "type": "address",
                            },
                            {"internalType": "uint24", "name": "fee", "type": "uint24"},
                            {
                                "internalType": "address",
                                "name": "recipient",
                                "type": "address",
                            },
                            {
                                "internalType": "uint256",
                                "name": "deadline",
                                "type": "uint256",
                            },
                            {
                                "internalType": "uint256",
                                "name": "amountIn",
                                "type": "uint256",
                            },
                            {
                                "internalType": "uint256",
                                "name": "amountOutMinimum",
                                "type": "uint256",
                            },
                            {
                                "internalType": "uint160",
                                "name": "sqrtPriceLimitX96",
                                "type": "uint160",
                            },
                        ],
                        "internalType": "struct ISwapRouter.ExactInputSingleParams",
                        "name": "params",
                        "type": "tuple",
                    }
                ],
                "name": "exactInputSingle",
                "outputs": [
                    {"internalType": "uint256", "name": "amountOut", "type": "uint256"}
                ],
                "stateMutability": "payable",
                "type": "function",
            }
        ]

        super().__init__(router_address, router_abi, name)
        self.factory_address = Web3.to_checksum_address(factory_address)
        self.quoter_address = Web3.to_checksum_address(quoter_address)
        self.factory_contract: Optional[Contract] = None
        self.quoter_contract: Optional[Contract] = None

        logger.info(
            f"Initialized {name} with factory {self.factory_address} "
            f"and quoter {self.quoter_address}"
        )

    async def get_token_price(
        self, token_address: str, web3: Web3, amount: Optional[Decimal] = None
    ) -> Decimal:
        """
        Get token price using Uniswap V3 Quoter.

        Args:
            token_address: Token contract address
            web3: Web3 instance
            amount: Amount to price (defaults to 1 token)

        Returns:
            Price in base currency (WETH)
        """
        try:
            if not self.quoter_contract:
                self._initialize_quoter(web3)

            assert self.quoter_contract is not None, "Quoter contract not initialized"

            # Default to pricing 1 token
            if amount is None:
                amount = Decimal("1")

            amount_wei = int(amount * Decimal(10**18))

            # Get WETH address (Mumbai testnet WETH)
            weth_address = "0xA6FA4fB5f76172d178d61B04b0ecd319C5d1C0aa"

            # Get optimal fee tier
            fee = self._get_optimal_fee_tier(token_address, weth_address, web3)

            # Quote the swap
            # Use quoter.quoteExactInputSingle
            amount_out = self.quoter_contract.functions.quoteExactInputSingle(
                token_address, weth_address, fee, amount_wei, 0  # sqrtPriceLimitX96
            ).call()

            price = Decimal(amount_out) / Decimal(10**18)
            logger.debug(
                f"Got price for {token_address}: {price} WETH (fee tier: {fee})"
            )
            return price

        except Exception as e:
            logger.error(f"Error getting price from Uniswap V3: {e}")
            return Decimal("0")

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
        Execute a swap on Uniswap V3.

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

            # Get optimal fee tier
            fee = self._get_optimal_fee_tier(token_in, token_out, web3)

            # Convert amount to wei
            amount_wei = int(amount * Decimal(10**18))

            # Calculate minimum output (with 0.5% slippage)
            expected_out = await self.get_token_price(token_in, web3, amount)
            min_out = int(expected_out * Decimal(0.995) * Decimal(10**18))

            # Get deadline (5 minutes from now)
            latest_block = web3.eth.get_block("latest")
            deadline = latest_block["timestamp"] + 300

            # Build swap params as tuple
            swap_params = (
                Web3.to_checksum_address(token_in),
                Web3.to_checksum_address(token_out),
                fee,
                Web3.to_checksum_address(account),
                deadline,
                amount_wei,
                min_out,
                0,  # sqrtPriceLimitX96
            )

            # Build transaction
            account_checksum = Web3.to_checksum_address(account)
            txn = self.contract.functions.exactInputSingle(
                swap_params
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
                logger.info(f"Uniswap V3 trade successful: {tx_hash.hex()}")
                return True, tx_hash.hex()
            else:
                logger.error(f"Uniswap V3 trade reverted: {tx_hash.hex()}")
                return False, f"Transaction reverted: {tx_hash.hex()}"

        except Exception as e:
            logger.error(f"Error executing Uniswap V3 trade: {e}")
            return False, str(e)

    async def get_liquidity_depth(
        self, token1: str, token2: str, web3: Web3, max_amount: Decimal
    ) -> Tuple[Decimal, Decimal]:
        """
        Get available liquidity for a token pair.

        Args:
            token1: First token address
            token2: Second token address
            web3: Web3 instance
            max_amount: Maximum amount to check

        Returns:
            Tuple of (available_liquidity, price_impact_percent)
        """
        try:
            if not self.factory_contract:
                self._initialize_factory(web3)

            assert self.factory_contract is not None, "Factory contract not initialized"

            fee = self._get_optimal_fee_tier(token1, token2, web3)

            # Get pool address
            pool_address = self.factory_contract.functions.getPool(
                token1, token2, fee
            ).call()

            if pool_address == "0x0000000000000000000000000000000000000000":
                logger.warning(f"No pool found for {token1}/{token2} with fee {fee}")
                return Decimal("0"), Decimal("100")

            # Get pool liquidity
            pool_abi = [
                {
                    "inputs": [],
                    "name": "liquidity",
                    "outputs": [
                        {"internalType": "uint128", "name": "", "type": "uint128"}
                    ],
                    "stateMutability": "view",
                    "type": "function",
                }
            ]
            pool_contract = web3.eth.contract(address=pool_address, abi=pool_abi)
            liquidity = pool_contract.functions.liquidity().call()

            available = Decimal(liquidity) / Decimal(10**18)

            # Estimate price impact (simplified)
            if available > 0:
                impact = (max_amount / available) * Decimal("100")
            else:
                impact = Decimal("100")

            logger.debug(
                f"Liquidity for {token1}/{token2}: {available}, " f"impact: {impact}%"
            )
            return available, min(impact, Decimal("100"))

        except Exception as e:
            logger.error(f"Error getting liquidity depth: {e}")
            return Decimal("0"), Decimal("100")

    def _get_optimal_fee_tier(self, token_in: str, token_out: str, web3: Web3) -> int:
        """
        Find the fee tier with highest liquidity.

        Args:
            token_in: Input token address
            token_out: Output token address
            web3: Web3 instance

        Returns:
            Fee tier (100, 500, 3000, or 10000)
        """
        if not self.factory_contract:
            self._initialize_factory(web3)

        assert self.factory_contract is not None, "Factory contract not initialized"

        best_fee = 3000  # Default to 0.3%
        highest_liquidity = 0

        token_in_checksum = Web3.to_checksum_address(token_in)
        token_out_checksum = Web3.to_checksum_address(token_out)

        for fee in self.FEE_TIERS:
            try:
                # Get pool address
                pool_address = self.factory_contract.functions.getPool(
                    token_in_checksum, token_out_checksum, fee
                ).call()

                if pool_address != "0x0000000000000000000000000000000000000000":
                    # Get pool liquidity
                    pool_abi = [
                        {
                            "inputs": [],
                            "name": "liquidity",
                            "outputs": [
                                {
                                    "internalType": "uint128",
                                    "name": "",
                                    "type": "uint128",
                                }
                            ],
                            "stateMutability": "view",
                            "type": "function",
                        }
                    ]
                    pool_contract = web3.eth.contract(
                        address=pool_address, abi=pool_abi
                    )
                    liquidity = pool_contract.functions.liquidity().call()

                    if liquidity > highest_liquidity:
                        highest_liquidity = liquidity
                        best_fee = fee
                        logger.debug(
                            f"Found better fee tier {fee} with liquidity {liquidity}"
                        )
            except Exception as e:
                logger.debug(f"No pool found for fee tier {fee}: {e}")
                continue

        logger.info(f"Selected fee tier {best_fee} with liquidity {highest_liquidity}")
        return best_fee

    def _initialize_factory(self, web3: Web3) -> None:
        """Initialize factory contract."""
        factory_abi = [
            {
                "inputs": [
                    {"internalType": "address", "name": "tokenA", "type": "address"},
                    {"internalType": "address", "name": "tokenB", "type": "address"},
                    {"internalType": "uint24", "name": "fee", "type": "uint24"},
                ],
                "name": "getPool",
                "outputs": [
                    {"internalType": "address", "name": "pool", "type": "address"}
                ],
                "stateMutability": "view",
                "type": "function",
            }
        ]
        self.factory_contract = web3.eth.contract(
            address=self.factory_address, abi=factory_abi
        )
        logger.debug(f"Initialized Uniswap V3 factory contract")

    def _initialize_quoter(self, web3: Web3) -> None:
        """Initialize quoter contract."""
        quoter_abi = [
            {
                "inputs": [
                    {"internalType": "address", "name": "tokenIn", "type": "address"},
                    {"internalType": "address", "name": "tokenOut", "type": "address"},
                    {"internalType": "uint24", "name": "fee", "type": "uint24"},
                    {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
                    {
                        "internalType": "uint160",
                        "name": "sqrtPriceLimitX96",
                        "type": "uint160",
                    },
                ],
                "name": "quoteExactInputSingle",
                "outputs": [
                    {"internalType": "uint256", "name": "amountOut", "type": "uint256"}
                ],
                "stateMutability": "nonpayable",
                "type": "function",
            }
        ]
        self.quoter_contract = web3.eth.contract(
            address=self.quoter_address, abi=quoter_abi
        )
        logger.debug(f"Initialized Uniswap V3 quoter contract")
