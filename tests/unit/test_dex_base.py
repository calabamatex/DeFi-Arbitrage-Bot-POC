"""Comprehensive tests for DEX base class."""

import pytest
from decimal import Decimal
from unittest.mock import MagicMock, AsyncMock, patch
from web3 import Web3

from src.dex.base import DEX, init_dex_instances


class ConcreteDEX(DEX):
    """Concrete implementation of DEX for testing."""

    async def get_token_price(
        self, token_address: str, web3: Web3, amount: Decimal = None
    ) -> Decimal:
        """Test implementation."""
        return Decimal("1850.50")

    async def execute_trade(
        self,
        token_in: str,
        token_out: str,
        amount: Decimal,
        web3: Web3,
        account: str,
        private_key: str,
    ) -> tuple:
        """Test implementation."""
        return (True, "0xabcd1234")

    async def get_liquidity_depth(
        self, token1: str, token2: str, web3: Web3, max_amount: Decimal
    ) -> tuple:
        """Test implementation."""
        return (Decimal("1000000"), Decimal("0.01"))


class IncompleteDEX(DEX):
    """DEX with missing implementations to test abstract methods."""

    pass


@pytest.fixture
def mock_web3():
    """Fixture providing mock Web3 instance."""
    web3 = MagicMock()
    web3.is_connected.return_value = True
    web3.eth.contract.return_value = MagicMock()
    web3.to_checksum_address = Web3.to_checksum_address
    return web3


@pytest.fixture
def router_address():
    """Fixture providing valid router address."""
    return "0xE592427A0AEce92De3Edee1F18E0157C05861564"


@pytest.fixture
def router_abi():
    """Fixture providing minimal router ABI."""
    return [
        {
            "inputs": [],
            "name": "factory",
            "outputs": [{"internalType": "address", "name": "", "type": "address"}],
            "stateMutability": "view",
            "type": "function",
        }
    ]


@pytest.fixture
def concrete_dex(router_address, router_abi):
    """Fixture providing concrete DEX instance."""
    return ConcreteDEX(
        router_address=router_address, router_abi=router_abi, name="TestDEX"
    )


def test_abstract_methods_raise_not_implemented():
    """Test that abstract methods raise NotImplementedError when not implemented."""
    # This should raise TypeError because IncompleteDEX doesn't implement abstract methods
    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        IncompleteDEX(
            router_address="0xE592427A0AEce92De3Edee1F18E0157C05861564",
            router_abi=[],
            name="IncompleteDEX",
        )


def test_initialization(router_address, router_abi):
    """Test DEX initialization with valid parameters."""
    dex = ConcreteDEX(
        router_address=router_address, router_abi=router_abi, name="TestDEX"
    )

    assert dex.name == "TestDEX"
    assert dex.router_address == Web3.to_checksum_address(router_address)
    assert dex.router_abi == router_abi
    assert dex.contract is None  # Not initialized yet


def test_initialization_checksums_address(router_abi):
    """Test that initialization converts address to checksum format."""
    lowercase_address = "0xe592427a0aece92de3edee1f18e0157c05861564"
    dex = ConcreteDEX(
        router_address=lowercase_address, router_abi=router_abi, name="TestDEX"
    )

    # Should be checksummed
    assert dex.router_address == "0xE592427A0AEce92De3Edee1F18E0157C05861564"
    assert dex.router_address != lowercase_address


def test_initialize_contract_success(concrete_dex, mock_web3):
    """Test successful contract initialization."""
    concrete_dex.initialize_contract(mock_web3)

    assert concrete_dex.contract is not None
    mock_web3.eth.contract.assert_called_once_with(
        address=concrete_dex.router_address, abi=concrete_dex.router_abi
    )


def test_initialize_contract_not_connected(concrete_dex, mock_web3):
    """Test contract initialization fails when Web3 not connected."""
    mock_web3.is_connected.return_value = False

    with pytest.raises(ValueError, match="Web3 instance not connected"):
        concrete_dex.initialize_contract(mock_web3)


def test_initialize_contract_multiple_times(concrete_dex, mock_web3):
    """Test that contract can be reinitialized."""
    concrete_dex.initialize_contract(mock_web3)
    first_contract = concrete_dex.contract

    concrete_dex.initialize_contract(mock_web3)
    second_contract = concrete_dex.contract

    # Should create new contract instance
    assert concrete_dex.contract is not None
    assert mock_web3.eth.contract.call_count == 2


@pytest.mark.asyncio
async def test_get_token_price_implementation(concrete_dex, mock_web3):
    """Test that concrete implementation of get_token_price works."""
    token_address = "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619"

    price = await concrete_dex.get_token_price(token_address, mock_web3)

    assert isinstance(price, Decimal)
    assert price == Decimal("1850.50")


@pytest.mark.asyncio
async def test_execute_trade_implementation(concrete_dex, mock_web3):
    """Test that concrete implementation of execute_trade works."""
    token_in = "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619"
    token_out = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
    amount = Decimal("1.5")
    account = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb"
    private_key = "0x" + "a" * 64

    success, tx_hash = await concrete_dex.execute_trade(
        token_in, token_out, amount, mock_web3, account, private_key
    )

    assert success is True
    assert isinstance(tx_hash, str)
    assert tx_hash == "0xabcd1234"


@pytest.mark.asyncio
async def test_get_liquidity_depth_implementation(concrete_dex, mock_web3):
    """Test that concrete implementation of get_liquidity_depth works."""
    token1 = "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619"
    token2 = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
    max_amount = Decimal("100")

    liquidity, price_impact = await concrete_dex.get_liquidity_depth(
        token1, token2, mock_web3, max_amount
    )

    assert isinstance(liquidity, Decimal)
    assert isinstance(price_impact, Decimal)
    assert liquidity == Decimal("1000000")
    assert price_impact == Decimal("0.01")


@pytest.mark.asyncio
async def test_fetch_concurrent_prices_success(mock_web3):
    """Test fetching prices from multiple DEXes concurrently."""
    # Create multiple DEX instances with different prices
    dex1 = ConcreteDEX(
        router_address="0xE592427A0AEce92De3Edee1F18E0157C05861564",
        router_abi=[],
        name="DEX1",
    )
    dex2 = ConcreteDEX(
        router_address="0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F",
        router_abi=[],
        name="DEX2",
    )
    dex3 = ConcreteDEX(
        router_address="0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff",
        router_abi=[],
        name="DEX3",
    )

    # Mock different prices for each DEX
    dex1.get_token_price = AsyncMock(return_value=Decimal("1850.50"))
    dex2.get_token_price = AsyncMock(return_value=Decimal("1849.75"))
    dex3.get_token_price = AsyncMock(return_value=Decimal("1851.20"))

    token_address = "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619"

    prices = await DEX.fetch_concurrent_prices([dex1, dex2, dex3], token_address, mock_web3)

    assert len(prices) == 3
    assert prices["DEX1"] == Decimal("1850.50")
    assert prices["DEX2"] == Decimal("1849.75")
    assert prices["DEX3"] == Decimal("1851.20")

    # Verify all were called
    dex1.get_token_price.assert_called_once_with(token_address, mock_web3)
    dex2.get_token_price.assert_called_once_with(token_address, mock_web3)
    dex3.get_token_price.assert_called_once_with(token_address, mock_web3)


@pytest.mark.asyncio
async def test_fetch_concurrent_prices_with_failures(mock_web3):
    """Test fetching prices handles DEX failures gracefully."""
    dex1 = ConcreteDEX(
        router_address="0xE592427A0AEce92De3Edee1F18E0157C05861564",
        router_abi=[],
        name="DEX1",
    )
    dex2 = ConcreteDEX(
        router_address="0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F",
        router_abi=[],
        name="DEX2",
    )
    dex3 = ConcreteDEX(
        router_address="0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff",
        router_abi=[],
        name="DEX3",
    )

    # Mock DEX2 to fail
    dex1.get_token_price = AsyncMock(return_value=Decimal("1850.50"))
    dex2.get_token_price = AsyncMock(side_effect=Exception("Network error"))
    dex3.get_token_price = AsyncMock(return_value=Decimal("1851.20"))

    token_address = "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619"

    prices = await DEX.fetch_concurrent_prices([dex1, dex2, dex3], token_address, mock_web3)

    # Should only have successful fetches
    assert len(prices) == 2
    assert "DEX1" in prices
    assert "DEX2" not in prices  # Failed, so not included
    assert "DEX3" in prices
    assert prices["DEX1"] == Decimal("1850.50")
    assert prices["DEX3"] == Decimal("1851.20")


@pytest.mark.asyncio
async def test_fetch_concurrent_prices_empty_list(mock_web3):
    """Test fetching prices with empty DEX list."""
    token_address = "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619"

    prices = await DEX.fetch_concurrent_prices([], token_address, mock_web3)

    assert prices == {}


@pytest.mark.asyncio
async def test_fetch_concurrent_prices_all_fail(mock_web3):
    """Test fetching prices when all DEXes fail."""
    dex1 = ConcreteDEX(
        router_address="0xE592427A0AEce92De3Edee1F18E0157C05861564",
        router_abi=[],
        name="DEX1",
    )
    dex2 = ConcreteDEX(
        router_address="0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F",
        router_abi=[],
        name="DEX2",
    )

    # Mock both to fail
    dex1.get_token_price = AsyncMock(side_effect=Exception("Network error"))
    dex2.get_token_price = AsyncMock(side_effect=Exception("RPC error"))

    token_address = "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619"

    prices = await DEX.fetch_concurrent_prices([dex1, dex2], token_address, mock_web3)

    # Should return empty dict when all fail
    assert prices == {}


def test_init_dex_instances_creates_all_dexes():
    """Test that init_dex_instances creates all DEX instances."""
    env_config = {
        "POLYGON_RPC_URL": "https://rpc-mumbai.maticvigil.com/",
        "UNISWAP_V3_ROUTER": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
        "SUSHISWAP_ROUTER": "0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F",
        "QUICKSWAP_ROUTER": "0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff",
    }
    token_list = {
        "WETH": {
            "address": "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619",
            "decimals": 18,
        }
    }

    result = init_dex_instances(env_config, token_list)

    # Should create 3 DEX instances
    assert isinstance(result, dict)
    assert len(result) == 3
    assert "Uniswap V3" in result
    assert "SushiSwap" in result
    assert "QuickSwap" in result


def test_init_dex_instances_accepts_parameters():
    """Test that init_dex_instances accepts correct parameters."""
    # Should not raise any errors
    result = init_dex_instances({}, {})

    assert isinstance(result, dict)


def test_dex_str_representation(concrete_dex):
    """Test DEX string representation."""
    # The name attribute should be accessible
    assert concrete_dex.name == "TestDEX"


def test_dex_attributes_are_accessible(concrete_dex):
    """Test that all DEX attributes are properly set and accessible."""
    assert hasattr(concrete_dex, "name")
    assert hasattr(concrete_dex, "router_address")
    assert hasattr(concrete_dex, "router_abi")
    assert hasattr(concrete_dex, "contract")

    assert concrete_dex.name == "TestDEX"
    assert concrete_dex.router_address is not None
    assert concrete_dex.router_abi is not None
    assert concrete_dex.contract is None  # Not initialized yet
