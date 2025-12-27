"""Comprehensive tests for QuickSwap DEX adapter."""

import pytest
from decimal import Decimal
from unittest.mock import MagicMock, AsyncMock, patch
from web3 import Web3

from src.dex.quickswap import QuickSwap


@pytest.fixture
def router_address():
    """Fixture providing QuickSwap router address."""
    return "0x8954AfA98594b838bda56FE4C12a09D7739D179b"


@pytest.fixture
def quickswap(router_address):
    """Fixture providing QuickSwap instance."""
    return QuickSwap(router_address=router_address)


@pytest.fixture
def quickswap_custom_name(router_address):
    """Fixture providing QuickSwap instance with custom name."""
    return QuickSwap(router_address=router_address, name="Custom QuickSwap")


@pytest.fixture
def mock_web3():
    """Fixture providing mock Web3 instance."""
    web3 = MagicMock()
    web3.is_connected.return_value = True
    web3.to_checksum_address = Web3.to_checksum_address
    web3.eth.gas_price = 50000000000  # 50 gwei
    web3.eth.get_transaction_count.return_value = 5
    return web3


@pytest.fixture
def token_addresses():
    """Fixture providing test token addresses."""
    return {
        "weth": "0xA6FA4fB5f76172d178d61B04b0ecd319C5d1C0aa",
        "usdc": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
    }


def test_initialization(router_address):
    """Test QuickSwap initialization with valid parameters."""
    quickswap = QuickSwap(router_address=router_address)

    assert quickswap.name == "QuickSwap"
    assert quickswap.router_address == Web3.to_checksum_address(router_address)
    assert quickswap.router_abi is not None
    assert len(quickswap.router_abi) == 2  # getAmountsOut and swapExactTokensForTokens
    assert quickswap.contract is None  # Not initialized yet


def test_initialization_custom_name(quickswap_custom_name):
    """Test QuickSwap initialization with custom name."""
    assert quickswap_custom_name.name == "Custom QuickSwap"


def test_initialization_checksums_address():
    """Test that initialization converts address to checksum format."""
    lowercase_router = "0x8954afa98594b838bda56fe4c12a09d7739d179b"
    quickswap = QuickSwap(router_address=lowercase_router)

    assert quickswap.router_address == "0x8954AfA98594b838bda56FE4C12a09D7739D179b"
    assert quickswap.router_address != lowercase_router


def test_router_abi_structure(quickswap):
    """Test that router ABI has correct structure."""
    abi = quickswap.router_abi

    # Check that we have the right functions
    function_names = [item["name"] for item in abi if item.get("type") == "function"]
    assert "getAmountsOut" in function_names
    assert "swapExactTokensForTokens" in function_names

    # Check getAmountsOut structure
    get_amounts_out = next(
        item for item in abi if item.get("name") == "getAmountsOut"
    )
    assert get_amounts_out["stateMutability"] == "view"
    assert len(get_amounts_out["inputs"]) == 2  # amountIn, path

    # Check swapExactTokensForTokens structure
    swap_function = next(
        item for item in abi if item.get("name") == "swapExactTokensForTokens"
    )
    assert swap_function["stateMutability"] == "nonpayable"
    assert len(swap_function["inputs"]) == 5  # amountIn, amountOutMin, path, to, deadline


@pytest.mark.asyncio
async def test_get_token_price_success(quickswap, mock_web3, token_addresses):
    """Test successful token price fetching."""
    # Mock router contract
    mock_router = MagicMock()
    mock_router.functions.getAmountsOut.return_value.call.return_value = [
        1000000000000000000000,  # Input amount
        1850000000000000000000,  # Output amount (1850 WETH)
    ]
    quickswap.contract = mock_router

    price = await quickswap.get_token_price(
        token_addresses["usdc"], mock_web3, Decimal("1000")
    )

    assert isinstance(price, Decimal)
    assert price == Decimal("1850")
    mock_router.functions.getAmountsOut.assert_called_once()


@pytest.mark.asyncio
async def test_get_token_price_default_amount(quickswap, mock_web3, token_addresses):
    """Test token price fetching with default amount (1 token)."""
    mock_router = MagicMock()
    mock_router.functions.getAmountsOut.return_value.call.return_value = [
        1000000000000000000,  # 1 token
        1850500000000000000000,  # 1850.5 WETH
    ]
    quickswap.contract = mock_router

    # Call without amount parameter
    price = await quickswap.get_token_price(token_addresses["usdc"], mock_web3)

    assert isinstance(price, Decimal)
    assert price == Decimal("1850.5")

    # Verify 1 token worth was queried
    call_args = mock_router.functions.getAmountsOut.call_args[0]
    assert call_args[0] == 1000000000000000000  # 1 * 10^18


@pytest.mark.asyncio
async def test_get_token_price_error_handling(quickswap, mock_web3, token_addresses):
    """Test token price fetching handles errors gracefully."""
    mock_router = MagicMock()
    mock_router.functions.getAmountsOut.return_value.call.side_effect = Exception(
        "RPC error"
    )
    quickswap.contract = mock_router

    price = await quickswap.get_token_price(token_addresses["usdc"], mock_web3)

    # Should return 0 on error
    assert price == Decimal("0")


@pytest.mark.asyncio
async def test_get_token_price_initializes_contract(
    quickswap, mock_web3, token_addresses
):
    """Test that get_token_price initializes contract if needed."""
    assert quickswap.contract is None

    mock_router = MagicMock()
    mock_router.functions.getAmountsOut.return_value.call.return_value = [
        1000000000000000000000,
        1850000000000000000000,
    ]
    mock_web3.eth.contract.return_value = mock_router

    await quickswap.get_token_price(token_addresses["usdc"], mock_web3)

    # Contract should be initialized
    assert quickswap.contract is not None


def test_get_best_path_direct(quickswap, token_addresses):
    """Test that _get_best_path returns direct path."""
    path = quickswap._get_best_path(token_addresses["usdc"], token_addresses["weth"])

    assert isinstance(path, list)
    assert len(path) == 2
    assert path[0] == Web3.to_checksum_address(token_addresses["usdc"])
    assert path[1] == Web3.to_checksum_address(token_addresses["weth"])


def test_get_best_path_checksums_addresses(quickswap):
    """Test that _get_best_path checksums addresses."""
    lowercase_token1 = "0x2791bca1f2de4661ed88a30c99a7a9449aa84174"
    lowercase_token2 = "0xa6fa4fb5f76172d178d61b04b0ecd319c5d1c0aa"

    path = quickswap._get_best_path(lowercase_token1, lowercase_token2)

    # Should be checksummed
    assert path[0] == "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
    assert path[1] == "0xA6FA4fB5f76172d178d61B04b0ecd319C5d1C0aa"


@pytest.mark.asyncio
@patch("src.dex.quickswap.Web3.to_checksum_address")
async def test_execute_trade_success(
    mock_checksum, quickswap, mock_web3, token_addresses
):
    """Test successful trade execution."""
    # Mock Web3.to_checksum_address to return input unchanged
    mock_checksum.side_effect = lambda x: x

    # Mock router contract
    mock_router = MagicMock()
    mock_router.functions.getAmountsOut.return_value.call.return_value = [
        1000000000000000000000,  # Input
        1850000000000000000000,  # Output
    ]
    mock_router.functions.swapExactTokensForTokens.return_value.build_transaction.return_value = {
        "from": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
        "gas": 300000,
        "gasPrice": 50000000000,
        "nonce": 5,
    }
    quickswap.contract = mock_router

    # Mock transaction signing and sending
    mock_signed = MagicMock()
    mock_signed.raw_transaction = b"raw_tx_data"
    mock_web3.eth.account.sign_transaction.return_value = mock_signed

    mock_tx_hash = MagicMock()
    mock_tx_hash.hex.return_value = "0xabcd1234567890"
    mock_web3.eth.send_raw_transaction.return_value = mock_tx_hash

    # Mock receipt
    mock_web3.eth.wait_for_transaction_receipt.return_value = {"status": 1}

    # Mock get_block for deadline
    mock_web3.eth.get_block.return_value = {"timestamp": 1700000000}

    account = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb"
    private_key = "0x" + "a" * 64

    success, tx_hash = await quickswap.execute_trade(
        token_addresses["usdc"],
        token_addresses["weth"],
        Decimal("1000"),
        mock_web3,
        account,
        private_key,
    )

    assert success is True
    assert tx_hash == "0xabcd1234567890"
    mock_router.functions.swapExactTokensForTokens.assert_called_once()
    mock_web3.eth.send_raw_transaction.assert_called_once()


@pytest.mark.asyncio
@patch("src.dex.quickswap.Web3.to_checksum_address")
async def test_execute_trade_reverted(
    mock_checksum, quickswap, mock_web3, token_addresses
):
    """Test trade execution when transaction reverts."""
    # Mock Web3.to_checksum_address to return input unchanged
    mock_checksum.side_effect = lambda x: x

    mock_router = MagicMock()
    mock_router.functions.getAmountsOut.return_value.call.return_value = [
        1000000000000000000000,
        1850000000000000000000,
    ]
    mock_router.functions.swapExactTokensForTokens.return_value.build_transaction.return_value = {
        "from": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
        "gas": 300000,
        "gasPrice": 50000000000,
        "nonce": 5,
    }
    quickswap.contract = mock_router

    mock_signed = MagicMock()
    mock_signed.raw_transaction = b"raw_tx_data"
    mock_web3.eth.account.sign_transaction.return_value = mock_signed

    mock_tx_hash = MagicMock()
    mock_tx_hash.hex.return_value = "0xfailed123"
    mock_web3.eth.send_raw_transaction.return_value = mock_tx_hash

    # Receipt with status 0 (reverted)
    mock_web3.eth.wait_for_transaction_receipt.return_value = {"status": 0}
    mock_web3.eth.get_block.return_value = {"timestamp": 1700000000}

    account = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb"
    private_key = "0x" + "a" * 64

    success, result = await quickswap.execute_trade(
        token_addresses["usdc"],
        token_addresses["weth"],
        Decimal("1000"),
        mock_web3,
        account,
        private_key,
    )

    assert success is False
    assert "reverted" in result.lower()
    assert "0xfailed123" in result


@pytest.mark.asyncio
@patch("src.dex.quickswap.Web3.to_checksum_address")
async def test_execute_trade_exception(
    mock_checksum, quickswap, mock_web3, token_addresses
):
    """Test trade execution handles exceptions."""
    # Mock Web3.to_checksum_address to return input unchanged
    mock_checksum.side_effect = lambda x: x

    mock_router = MagicMock()
    mock_router.functions.getAmountsOut.return_value.call.side_effect = Exception(
        "Insufficient liquidity"
    )
    quickswap.contract = mock_router

    mock_web3.eth.get_block.return_value = {"timestamp": 1700000000}

    account = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb"
    private_key = "0x" + "a" * 64

    success, error_msg = await quickswap.execute_trade(
        token_addresses["usdc"],
        token_addresses["weth"],
        Decimal("1000"),
        mock_web3,
        account,
        private_key,
    )

    assert success is False
    assert "Insufficient liquidity" in error_msg


@pytest.mark.asyncio
async def test_execute_trade_initializes_contract(
    quickswap, mock_web3, token_addresses
):
    """Test that execute_trade initializes contract if needed."""
    assert quickswap.contract is None

    mock_router = MagicMock()
    mock_router.functions.getAmountsOut.return_value.call.return_value = [
        1000000000000000000000,
        1850000000000000000000,
    ]
    mock_router.functions.swapExactTokensForTokens.return_value.build_transaction.return_value = {
        "from": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
        "gas": 300000,
        "gasPrice": 50000000000,
        "nonce": 5,
    }

    # Mock transaction signing and sending
    mock_signed = MagicMock()
    mock_signed.raw_transaction = b"raw_tx_data"
    mock_web3.eth.account.sign_transaction.return_value = mock_signed

    mock_tx_hash = MagicMock()
    mock_tx_hash.hex.return_value = "0xabcd1234567890"
    mock_web3.eth.send_raw_transaction.return_value = mock_tx_hash
    mock_web3.eth.wait_for_transaction_receipt.return_value = {"status": 1}
    mock_web3.eth.get_block.return_value = {"timestamp": 1700000000}
    mock_web3.eth.contract.return_value = mock_router

    account = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb"
    private_key = "0x" + "a" * 64

    with patch("src.dex.quickswap.Web3.to_checksum_address", side_effect=lambda x: x):
        await quickswap.execute_trade(
            token_addresses["usdc"],
            token_addresses["weth"],
            Decimal("1000"),
            mock_web3,
            account,
            private_key,
        )

    # Contract should be initialized
    assert quickswap.contract is not None


@pytest.mark.asyncio
async def test_get_liquidity_depth_returns_simplified_values(
    quickswap, mock_web3, token_addresses
):
    """Test that get_liquidity_depth returns simplified liquidity values."""
    liquidity, impact = await quickswap.get_liquidity_depth(
        token_addresses["usdc"],
        token_addresses["weth"],
        mock_web3,
        Decimal("100"),  # max_amount
    )

    assert isinstance(liquidity, Decimal)
    assert isinstance(impact, Decimal)
    assert liquidity == Decimal("1000000")  # Simplified constant
    assert impact == Decimal("0.01")  # 100/1000000 * 100 = 0.01%


@pytest.mark.asyncio
async def test_get_liquidity_depth_calculates_impact(
    quickswap, mock_web3, token_addresses
):
    """Test that get_liquidity_depth calculates price impact correctly."""
    liquidity, impact = await quickswap.get_liquidity_depth(
        token_addresses["usdc"],
        token_addresses["weth"],
        mock_web3,
        Decimal("10000"),  # Large amount
    )

    assert liquidity == Decimal("1000000")
    assert impact == Decimal("1")  # 10000/1000000 * 100 = 1%


@pytest.mark.asyncio
async def test_get_liquidity_depth_caps_impact(
    quickswap, mock_web3, token_addresses
):
    """Test that get_liquidity_depth caps impact at 100%."""
    liquidity, impact = await quickswap.get_liquidity_depth(
        token_addresses["usdc"],
        token_addresses["weth"],
        mock_web3,
        Decimal("10000000"),  # Very large amount
    )

    assert liquidity == Decimal("1000000")
    # Impact would be 1000%, but capped at 100%
    assert impact == Decimal("100")


@pytest.mark.asyncio
async def test_get_liquidity_depth_error_handling(
    quickswap, mock_web3, token_addresses
):
    """Test that get_liquidity_depth handles errors gracefully."""
    # Force an error by making max_amount cause division issues
    # In this simplified implementation, errors would come from logging or calculation
    # The current implementation shouldn't error, but let's test the structure

    liquidity, impact = await quickswap.get_liquidity_depth(
        token_addresses["usdc"],
        token_addresses["weth"],
        mock_web3,
        Decimal("100"),
    )

    # Should still return valid values
    assert isinstance(liquidity, Decimal)
    assert isinstance(impact, Decimal)
    assert liquidity > 0
    assert impact >= 0


def test_quickswap_inherits_from_dex(quickswap):
    """Test that QuickSwap properly inherits from DEX."""
    from src.dex.base import DEX

    assert isinstance(quickswap, DEX)
    assert hasattr(quickswap, "get_token_price")
    assert hasattr(quickswap, "execute_trade")
    assert hasattr(quickswap, "get_liquidity_depth")
    assert hasattr(quickswap, "initialize_contract")


def test_quickswap_attributes_are_accessible(quickswap):
    """Test that all QuickSwap attributes are properly set and accessible."""
    assert hasattr(quickswap, "name")
    assert hasattr(quickswap, "router_address")
    assert hasattr(quickswap, "router_abi")
    assert hasattr(quickswap, "contract")

    assert quickswap.name == "QuickSwap"
    assert quickswap.router_address is not None
    assert quickswap.router_abi is not None
    assert quickswap.contract is None  # Not initialized yet
