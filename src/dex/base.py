"""Abstract base class for DEX implementations."""

from abc import ABC, abstractmethod
from web3 import Web3
from web3.contract import Contract
from decimal import Decimal
from typing import Tuple, Optional, Dict, List
import logging
import asyncio

logger = logging.getLogger(__name__)


class DEX(ABC):
    """Abstract base class for DEX implementations."""

    def __init__(self, router_address: str, router_abi: list, name: str):
        """
        Initialize DEX with contract details.

        Args:
            router_address: Address of the DEX router contract
            router_abi: ABI of the router contract
            name: Name of the DEX (e.g., "Uniswap V3", "SushiSwap")
        """
        self.router_address = Web3.to_checksum_address(router_address)
        self.router_abi = router_abi
        self.name = name
        self.contract: Optional[Contract] = None
        logger.info(f"Initialized {self.name} DEX with router at {self.router_address}")

    def initialize_contract(self, web3: Web3) -> None:
        """
        Initialize Web3 contract instance.

        Args:
            web3: Web3 instance to use for contract initialization

        Raises:
            ValueError: If Web3 instance is not connected
        """
        if not web3.is_connected():
            raise ValueError(f"Web3 instance not connected for {self.name}")

        self.contract = web3.eth.contract(
            address=self.router_address, abi=self.router_abi
        )
        logger.info(f"Initialized contract for {self.name}")

    @abstractmethod
    async def get_token_price(
        self, token_address: str, web3: Web3, amount: Optional[Decimal] = None
    ) -> Decimal:
        """
        Get token price on this DEX. Must be implemented by subclasses.

        Args:
            token_address: Address of the token to get price for
            web3: Web3 instance
            amount: Optional amount to get price for (for price impact calculation)

        Returns:
            Price as Decimal

        Raises:
            NotImplementedError: If not implemented by subclass
        """
        pass

    @abstractmethod
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
        Execute trade. Must be implemented by subclasses.

        Args:
            token_in: Address of input token
            token_out: Address of output token
            amount: Amount to trade
            web3: Web3 instance
            account: Account address to trade from
            private_key: Private key for signing transaction

        Returns:
            Tuple of (success: bool, transaction_hash: str)

        Raises:
            NotImplementedError: If not implemented by subclass
        """
        pass

    @abstractmethod
    async def get_liquidity_depth(
        self, token1: str, token2: str, web3: Web3, max_amount: Decimal
    ) -> Tuple[Decimal, Decimal]:
        """
        Get liquidity depth. Must be implemented by subclasses.

        Args:
            token1: Address of first token
            token2: Address of second token
            web3: Web3 instance
            max_amount: Maximum amount to check liquidity for

        Returns:
            Tuple of (available_liquidity: Decimal, price_impact: Decimal)

        Raises:
            NotImplementedError: If not implemented by subclass
        """
        pass

    @staticmethod
    async def fetch_concurrent_prices(
        dex_instances: List["DEX"], token_address: str, web3: Web3
    ) -> Dict[str, Decimal]:
        """
        Fetch prices from multiple DEXes concurrently.

        Args:
            dex_instances: List of DEX instances to fetch prices from
            token_address: Token address to get prices for
            web3: Web3 instance

        Returns:
            Dictionary mapping DEX name to price

        Example:
            >>> prices = await DEX.fetch_concurrent_prices(
            ...     [uniswap, sushiswap], token_addr, web3
            ... )
            >>> print(prices)
            {'Uniswap V3': Decimal('1850.50'), 'SushiSwap': Decimal('1849.75')}
        """
        tasks = []
        for dex in dex_instances:
            task = dex.get_token_price(token_address, web3)
            tasks.append(task)

        # Fetch all prices concurrently
        prices = await asyncio.gather(*tasks, return_exceptions=True)

        # Build result dictionary, handling any exceptions
        result: Dict[str, Decimal] = {}
        for dex, price in zip(dex_instances, prices):
            if isinstance(price, Exception):
                logger.error(f"Error fetching price from {dex.name}: {price}")
                # Don't include failed fetches in results
            elif isinstance(price, Decimal):
                result[dex.name] = price

        return result


def init_dex_instances(env_config: Dict, token_list: Dict) -> Dict[str, DEX]:
    """
    Initialize all DEX instances for the current environment.

    Args:
        env_config: Environment configuration (mainnet or testnet)
        token_list: Token list for this environment

    Returns:
        Dictionary of {dex_name: dex_instance}
    """
    from .uniswap_v3 import UniswapV3
    from .sushiswap import SushiSwap
    from .quickswap import QuickSwap

    dex_instances: Dict[str, DEX] = {}

    # Initialize Uniswap V3
    if "UNISWAP_V3_ROUTER" in env_config:
        # For testnet, factory and quoter addresses
        if "testnet" in str(env_config.get("POLYGON_RPC_URL", "")):
            factory = "0x1F98431c8aD98523631AE4a59f267346ea31F984"
            quoter = "0xb27308f9F90D607463bb33eA1BeBb41C27CE5AB6"
        else:
            factory = "0x1F98431c8aD98523631AE4a59f267346ea31F984"  # Same on mainnet
            quoter = "0xb27308f9F90D607463bb33eA1BeBb41C27CE5AB6"

        dex_instances["Uniswap V3"] = UniswapV3(
            router_address=env_config["UNISWAP_V3_ROUTER"],
            factory_address=factory,
            quoter_address=quoter,
        )
        logger.info("Initialized Uniswap V3")

    # Initialize SushiSwap
    if "SUSHISWAP_ROUTER" in env_config:
        dex_instances["SushiSwap"] = SushiSwap(
            router_address=env_config["SUSHISWAP_ROUTER"]
        )
        logger.info("Initialized SushiSwap")

    # Initialize QuickSwap
    if "QUICKSWAP_ROUTER" in env_config:
        dex_instances["QuickSwap"] = QuickSwap(
            router_address=env_config["QUICKSWAP_ROUTER"]
        )
        logger.info("Initialized QuickSwap")

    logger.info(f"Initialized {len(dex_instances)} DEX instance(s)")
    return dex_instances
