"""Comprehensive tests for Uniswap V3 DEX adapter."""

import pytest
from decimal import Decimal
from unittest.mock import MagicMock, AsyncMock, patch
from web3 import Web3

from src.dex.uniswap_v3 import UniswapV3


@pytest.fixture
def router_address():
    """Fixture providing Uniswap V3 router address."""
    return "0xE592427A0AEce92De3Edee1F18E0157C05861564"


@pytest.fixture
def factory_address():
    """Fixture providing Uniswap V3 factory address."""
    return "0x1F98431c8aD98523631AE4a59f267346ea31F984"


@pytest.fixture
def quoter_address():
    """Fixture providing Uniswap V3 quoter address."""
    return "0xb27308f9F90D607463bb33eA1BeBb41C27CE5AB6"


@pytest.fixture
def uniswap_v3(router_address, factory_address, quoter_address):
    """Fixture providing UniswapV3 instance."""
    return UniswapV3(
        router_address=router_address,
        factory_address=factory_address,
        quoter_address=quoter_address,
    )


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


def test_initialization(router_address, factory_address, quoter_address):
    """Test UniswapV3 initialization with valid parameters."""
    uniswap = UniswapV3(
        router_address=router_address,
        factory_address=factory_address,
        quoter_address=quoter_address,
        name="Test Uniswap V3",
    )

    assert uniswap.name == "Test Uniswap V3"
    assert uniswap.router_address == Web3.to_checksum_address(router_address)
    assert uniswap.factory_address == Web3.to_checksum_address(factory_address)
    assert uniswap.quoter_address == Web3.to_checksum_address(quoter_address)
    assert uniswap.factory_contract is None
    assert uniswap.quoter_contract is None
    assert len(uniswap.FEE_TIERS) == 4
    assert uniswap.FEE_TIERS == [100, 500, 3000, 10000]


def test_initialization_default_name(router_address, factory_address, quoter_address):
    """Test that default name is set correctly."""
    uniswap = UniswapV3(
        router_address=router_address,
        factory_address=factory_address,
        quoter_address=quoter_address,
    )

    assert uniswap.name == "Uniswap V3"


def test_initialization_checksums_addresses(factory_address, quoter_address):
    """Test that initialization converts addresses to checksum format."""
    lowercase_router = "0xe592427a0aece92de3edee1f18e0157c05861564"
    lowercase_factory = "0x1f98431c8ad98523631ae4a59f267346ea31f984"
    lowercase_quoter = "0xb27308f9f90d607463bb33ea1bebb41c27ce5ab6"

    uniswap = UniswapV3(
        router_address=lowercase_router,
        factory_address=lowercase_factory,
        quoter_address=lowercase_quoter,
    )

    assert uniswap.router_address == "0xE592427A0AEce92De3Edee1F18E0157C05861564"
    assert uniswap.factory_address == "0x1F98431c8aD98523631AE4a59f267346ea31F984"
    assert uniswap.quoter_address == "0xb27308f9F90D607463bb33eA1BeBb41C27CE5AB6"


@pytest.mark.asyncio
async def test_get_token_price_success(uniswap_v3, mock_web3, token_addresses):
    """Test successful token price fetching."""
    # Mock quoter contract
    mock_quoter = MagicMock()
    mock_quoter.functions.quoteExactInputSingle.return_value.call.return_value = (
        1850000000000000000000  # 1850 WETH
    )
    uniswap_v3.quoter_contract = mock_quoter

    # Mock factory contract for fee tier selection
    mock_factory = MagicMock()
    mock_factory.functions.getPool.return_value.call.return_value = (
        "0x1234567890123456789012345678901234567890"
    )
    uniswap_v3.factory_contract = mock_factory

    # Mock pool contract
    mock_pool = MagicMock()
    mock_pool.functions.liquidity.return_value.call.return_value = 1000000000000000000
    mock_web3.eth.contract.return_value = mock_pool

    price = await uniswap_v3.get_token_price(
        token_addresses["usdc"], mock_web3, Decimal("1000")
    )

    assert isinstance(price, Decimal)
    assert price == Decimal("1850")
    mock_quoter.functions.quoteExactInputSingle.assert_called_once()


@pytest.mark.asyncio
async def test_get_token_price_default_amount(uniswap_v3, mock_web3, token_addresses):
    """Test token price fetching with default amount (1 token)."""
    mock_quoter = MagicMock()
    mock_quoter.functions.quoteExactInputSingle.return_value.call.return_value = (
        1850500000000000000000  # 1850.5 WETH
    )
    uniswap_v3.quoter_contract = mock_quoter

    mock_factory = MagicMock()
    mock_factory.functions.getPool.return_value.call.return_value = (
        "0x1234567890123456789012345678901234567890"
    )
    uniswap_v3.factory_contract = mock_factory

    mock_pool = MagicMock()
    mock_pool.functions.liquidity.return_value.call.return_value = 1000000000000000000
    mock_web3.eth.contract.return_value = mock_pool

    # Call without amount parameter
    price = await uniswap_v3.get_token_price(token_addresses["usdc"], mock_web3)

    assert isinstance(price, Decimal)
    assert price == Decimal("1850.5")

    # Verify 1 token worth was queried (10^18 wei)
    call_args = mock_quoter.functions.quoteExactInputSingle.call_args[0]
    assert call_args[3] == 1000000000000000000  # 1 * 10^18


@pytest.mark.asyncio
async def test_get_token_price_error_handling(uniswap_v3, mock_web3, token_addresses):
    """Test token price fetching handles errors gracefully."""
    mock_quoter = MagicMock()
    mock_quoter.functions.quoteExactInputSingle.return_value.call.side_effect = (
        Exception("RPC error")
    )
    uniswap_v3.quoter_contract = mock_quoter

    mock_factory = MagicMock()
    mock_factory.functions.getPool.return_value.call.return_value = (
        "0x1234567890123456789012345678901234567890"
    )
    uniswap_v3.factory_contract = mock_factory

    mock_pool = MagicMock()
    mock_pool.functions.liquidity.return_value.call.return_value = 1000000000000000000
    mock_web3.eth.contract.return_value = mock_pool

    price = await uniswap_v3.get_token_price(token_addresses["usdc"], mock_web3)

    # Should return 0 on error
    assert price == Decimal("0")


@pytest.mark.asyncio
async def test_get_token_price_initializes_quoter(
    uniswap_v3, mock_web3, token_addresses
):
    """Test that get_token_price initializes quoter if not already initialized."""
    assert uniswap_v3.quoter_contract is None

    mock_quoter = MagicMock()
    mock_quoter.functions.quoteExactInputSingle.return_value.call.return_value = (
        1850000000000000000000
    )
    mock_web3.eth.contract.return_value = mock_quoter

    mock_factory = MagicMock()
    mock_factory.functions.getPool.return_value.call.return_value = (
        "0x1234567890123456789012345678901234567890"
    )
    uniswap_v3.factory_contract = mock_factory

    mock_pool = MagicMock()
    mock_pool.functions.liquidity.return_value.call.return_value = 1000000000000000000
    # Need to handle multiple contract creations
    mock_web3.eth.contract.side_effect = [mock_quoter, mock_pool]

    await uniswap_v3.get_token_price(token_addresses["usdc"], mock_web3)

    # Quoter should be initialized
    assert uniswap_v3.quoter_contract is not None


def test_get_optimal_fee_tier_selects_highest_liquidity(
    uniswap_v3, mock_web3, token_addresses
):
    """Test that optimal fee tier with highest liquidity is selected."""
    # Mock factory contract
    mock_factory = MagicMock()

    # Mock different pools with different liquidity - need to handle the call chain properly
    def mock_get_pool_func(token_in, token_out, fee):
        mock_call_result = MagicMock()
        if fee == 100:
            mock_call_result.call.return_value = "0x1111111111111111111111111111111111111111"
        elif fee == 500:
            mock_call_result.call.return_value = "0x5555555555555555555555555555555555555555"
        elif fee == 3000:
            mock_call_result.call.return_value = "0x3333333333333333333333333333333333333333"
        elif fee == 10000:
            mock_call_result.call.return_value = "0x0000000000000000000000000000000000000000"
        else:
            mock_call_result.call.return_value = "0x0000000000000000000000000000000000000000"
        return mock_call_result

    mock_factory.functions.getPool.side_effect = mock_get_pool_func
    uniswap_v3.factory_contract = mock_factory

    # Mock pool contracts with different liquidity
    def mock_contract(address, abi):
        mock_pool = MagicMock()
        if address == "0x1111111111111111111111111111111111111111":
            mock_pool.functions.liquidity.return_value.call.return_value = (
                1000000000000000000  # 1e18
            )
        elif address == "0x5555555555555555555555555555555555555555":
            mock_pool.functions.liquidity.return_value.call.return_value = (
                50000000000000000000  # 50e18 - HIGHEST
            )
        elif address == "0x3333333333333333333333333333333333333333":
            mock_pool.functions.liquidity.return_value.call.return_value = (
                10000000000000000000  # 10e18
            )
        return mock_pool

    mock_web3.eth.contract.side_effect = mock_contract

    fee = uniswap_v3._get_optimal_fee_tier(
        token_addresses["usdc"], token_addresses["weth"], mock_web3
    )

    # Should select fee tier 500 (0.05%) with highest liquidity
    assert fee == 500


def test_get_optimal_fee_tier_no_pools_returns_default(
    uniswap_v3, mock_web3, token_addresses
):
    """Test that default fee tier is returned when no pools exist."""
    mock_factory = MagicMock()
    # All pools return zero address (no pool)
    mock_factory.functions.getPool.return_value.call.return_value = (
        "0x0000000000000000000000000000000000000000"
    )
    uniswap_v3.factory_contract = mock_factory

    fee = uniswap_v3._get_optimal_fee_tier(
        token_addresses["usdc"], token_addresses["weth"], mock_web3
    )

    # Should return default 3000 (0.3%)
    assert fee == 3000


def test_get_optimal_fee_tier_initializes_factory(
    uniswap_v3, mock_web3, token_addresses
):
    """Test that _get_optimal_fee_tier initializes factory if needed."""
    assert uniswap_v3.factory_contract is None

    mock_factory = MagicMock()
    mock_factory.functions.getPool.return_value.call.return_value = (
        "0x0000000000000000000000000000000000000000"
    )
    mock_web3.eth.contract.return_value = mock_factory

    uniswap_v3._get_optimal_fee_tier(
        token_addresses["usdc"], token_addresses["weth"], mock_web3
    )

    # Factory should be initialized
    assert uniswap_v3.factory_contract is not None


@pytest.mark.asyncio
@patch("src.dex.uniswap_v3.Web3.to_checksum_address")
async def test_execute_trade_success(
    mock_checksum, uniswap_v3, mock_web3, token_addresses
):
    """Test successful trade execution."""
    # Mock Web3.to_checksum_address to return input unchanged
    mock_checksum.side_effect = lambda x: x

    # Mock contract
    mock_router = MagicMock()
    mock_build_tx = MagicMock()
    mock_router.functions.exactInputSingle.return_value.build_transaction.return_value = {
        "from": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
        "gas": 300000,
        "gasPrice": 50000000000,
        "nonce": 5,
    }
    uniswap_v3.contract = mock_router

    # Mock factory for fee tier selection
    mock_factory = MagicMock()
    mock_factory.functions.getPool.return_value.call.return_value = (
        "0x1234567890123456789012345678901234567890"
    )
    uniswap_v3.factory_contract = mock_factory

    # Mock pool contract
    mock_pool = MagicMock()
    mock_pool.functions.liquidity.return_value.call.return_value = 1000000000000000000
    mock_web3.eth.contract.return_value = mock_pool

    # Mock quoter for price check
    mock_quoter = MagicMock()
    mock_quoter.functions.quoteExactInputSingle.return_value.call.return_value = (
        1850000000000000000000  # Expected output
    )
    uniswap_v3.quoter_contract = mock_quoter

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

    success, tx_hash = await uniswap_v3.execute_trade(
        token_addresses["usdc"],
        token_addresses["weth"],
        Decimal("1000"),
        mock_web3,
        account,
        private_key,
    )

    assert success is True
    assert tx_hash == "0xabcd1234567890"
    mock_router.functions.exactInputSingle.assert_called_once()
    mock_web3.eth.send_raw_transaction.assert_called_once()


@pytest.mark.asyncio
@patch("src.dex.uniswap_v3.Web3.to_checksum_address")
async def test_execute_trade_reverted(
    mock_checksum, uniswap_v3, mock_web3, token_addresses
):
    """Test trade execution when transaction reverts."""
    # Mock Web3.to_checksum_address to return input unchanged
    mock_checksum.side_effect = lambda x: x

    mock_router = MagicMock()
    mock_router.functions.exactInputSingle.return_value.build_transaction.return_value = {
        "from": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
        "gas": 300000,
        "gasPrice": 50000000000,
        "nonce": 5,
    }
    uniswap_v3.contract = mock_router

    mock_factory = MagicMock()
    mock_factory.functions.getPool.return_value.call.return_value = (
        "0x1234567890123456789012345678901234567890"
    )
    uniswap_v3.factory_contract = mock_factory

    mock_pool = MagicMock()
    mock_pool.functions.liquidity.return_value.call.return_value = 1000000000000000000
    mock_web3.eth.contract.return_value = mock_pool

    mock_quoter = MagicMock()
    mock_quoter.functions.quoteExactInputSingle.return_value.call.return_value = (
        1850000000000000000000
    )
    uniswap_v3.quoter_contract = mock_quoter

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

    success, result = await uniswap_v3.execute_trade(
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
@patch("src.dex.uniswap_v3.Web3.to_checksum_address")
async def test_execute_trade_exception(
    mock_checksum, uniswap_v3, mock_web3, token_addresses
):
    """Test trade execution handles exceptions."""
    # Mock Web3.to_checksum_address to return input unchanged
    mock_checksum.side_effect = lambda x: x

    mock_router = MagicMock()
    mock_router.functions.exactInputSingle.return_value.build_transaction.side_effect = Exception(
        "Gas estimation failed"
    )
    uniswap_v3.contract = mock_router

    mock_factory = MagicMock()
    mock_factory.functions.getPool.return_value.call.return_value = (
        "0x1234567890123456789012345678901234567890"
    )
    uniswap_v3.factory_contract = mock_factory

    mock_pool = MagicMock()
    mock_pool.functions.liquidity.return_value.call.return_value = 1000000000000000000
    mock_web3.eth.contract.return_value = mock_pool

    mock_quoter = MagicMock()
    mock_quoter.functions.quoteExactInputSingle.return_value.call.return_value = (
        1850000000000000000000
    )
    uniswap_v3.quoter_contract = mock_quoter

    mock_web3.eth.get_block.return_value = {"timestamp": 1700000000}

    account = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb"
    private_key = "0x" + "a" * 64

    success, error_msg = await uniswap_v3.execute_trade(
        token_addresses["usdc"],
        token_addresses["weth"],
        Decimal("1000"),
        mock_web3,
        account,
        private_key,
    )

    assert success is False
    assert "Gas estimation failed" in error_msg


@pytest.mark.asyncio
async def test_execute_trade_initializes_contract(
    uniswap_v3, mock_web3, token_addresses
):
    """Test that execute_trade initializes contract if needed."""
    assert uniswap_v3.contract is None

    mock_router = MagicMock()
    mock_router.functions.exactInputSingle.return_value.build_transaction.return_value = {
        "from": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
        "gas": 300000,
        "gasPrice": 50000000000,
        "nonce": 5,
    }

    mock_factory = MagicMock()
    mock_factory.functions.getPool.return_value.call.return_value = (
        "0x1234567890123456789012345678901234567890"
    )
    uniswap_v3.factory_contract = mock_factory

    mock_pool = MagicMock()
    mock_pool.functions.liquidity.return_value.call.return_value = 1000000000000000000

    mock_quoter = MagicMock()
    mock_quoter.functions.quoteExactInputSingle.return_value.call.return_value = (
        1850000000000000000000
    )
    uniswap_v3.quoter_contract = mock_quoter

    # Set up contract creation to return router, then pool
    mock_web3.eth.contract.side_effect = [mock_router, mock_pool]

    mock_signed = MagicMock()
    mock_signed.raw_transaction = b"raw_tx_data"
    mock_web3.eth.account.sign_transaction.return_value = mock_signed

    mock_tx_hash = MagicMock()
    mock_tx_hash.hex.return_value = "0xabcd1234567890"
    mock_web3.eth.send_raw_transaction.return_value = mock_tx_hash
    mock_web3.eth.wait_for_transaction_receipt.return_value = {"status": 1}
    mock_web3.eth.get_block.return_value = {"timestamp": 1700000000}

    account = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb"
    private_key = "0x" + "a" * 64

    await uniswap_v3.execute_trade(
        token_addresses["usdc"],
        token_addresses["weth"],
        Decimal("1000"),
        mock_web3,
        account,
        private_key,
    )

    # Contract should be initialized
    assert uniswap_v3.contract is not None


@pytest.mark.asyncio
async def test_get_liquidity_depth_success(uniswap_v3, mock_web3, token_addresses):
    """Test successful liquidity depth calculation."""
    # Mock factory contract
    mock_factory = MagicMock()
    mock_factory.functions.getPool.return_value.call.return_value = (
        "0x1234567890123456789012345678901234567890"
    )
    uniswap_v3.factory_contract = mock_factory

    # Mock pool contract with liquidity
    mock_pool = MagicMock()
    mock_pool.functions.liquidity.return_value.call.return_value = (
        1000000000000000000000  # 1000 * 10^18
    )
    mock_web3.eth.contract.return_value = mock_pool

    liquidity, impact = await uniswap_v3.get_liquidity_depth(
        token_addresses["usdc"],
        token_addresses["weth"],
        mock_web3,
        Decimal("100"),  # max_amount
    )

    assert isinstance(liquidity, Decimal)
    assert isinstance(impact, Decimal)
    assert liquidity == Decimal("1000")  # 1000 tokens
    assert impact == Decimal("10")  # 100/1000 * 100 = 10%


@pytest.mark.asyncio
async def test_get_liquidity_depth_no_pool(uniswap_v3, mock_web3, token_addresses):
    """Test liquidity depth when no pool exists."""
    mock_factory = MagicMock()
    # Return zero address (no pool)
    mock_factory.functions.getPool.return_value.call.return_value = (
        "0x0000000000000000000000000000000000000000"
    )
    uniswap_v3.factory_contract = mock_factory

    liquidity, impact = await uniswap_v3.get_liquidity_depth(
        token_addresses["usdc"],
        token_addresses["weth"],
        mock_web3,
        Decimal("100"),
    )

    # Should return 0 liquidity and 100% impact
    assert liquidity == Decimal("0")
    assert impact == Decimal("100")


@pytest.mark.asyncio
async def test_get_liquidity_depth_zero_liquidity(
    uniswap_v3, mock_web3, token_addresses
):
    """Test liquidity depth with zero liquidity pool."""
    mock_factory = MagicMock()
    mock_factory.functions.getPool.return_value.call.return_value = (
        "0x1234567890123456789012345678901234567890"
    )
    uniswap_v3.factory_contract = mock_factory

    mock_pool = MagicMock()
    mock_pool.functions.liquidity.return_value.call.return_value = 0
    mock_web3.eth.contract.return_value = mock_pool

    liquidity, impact = await uniswap_v3.get_liquidity_depth(
        token_addresses["usdc"],
        token_addresses["weth"],
        mock_web3,
        Decimal("100"),
    )

    assert liquidity == Decimal("0")
    assert impact == Decimal("100")


@pytest.mark.asyncio
async def test_get_liquidity_depth_high_impact(uniswap_v3, mock_web3, token_addresses):
    """Test liquidity depth caps impact at 100%."""
    mock_factory = MagicMock()
    mock_factory.functions.getPool.return_value.call.return_value = (
        "0x1234567890123456789012345678901234567890"
    )
    uniswap_v3.factory_contract = mock_factory

    # Small liquidity
    mock_pool = MagicMock()
    mock_pool.functions.liquidity.return_value.call.return_value = (
        10000000000000000000  # 10 tokens
    )
    mock_web3.eth.contract.return_value = mock_pool

    liquidity, impact = await uniswap_v3.get_liquidity_depth(
        token_addresses["usdc"],
        token_addresses["weth"],
        mock_web3,
        Decimal("1000"),  # Large max_amount
    )

    assert liquidity == Decimal("10")
    # Impact would be 10000%, but capped at 100%
    assert impact == Decimal("100")


@pytest.mark.asyncio
async def test_get_liquidity_depth_error_handling(
    uniswap_v3, mock_web3, token_addresses
):
    """Test liquidity depth handles errors gracefully."""
    mock_factory = MagicMock()
    mock_factory.functions.getPool.return_value.call.side_effect = Exception(
        "RPC error"
    )
    uniswap_v3.factory_contract = mock_factory

    liquidity, impact = await uniswap_v3.get_liquidity_depth(
        token_addresses["usdc"],
        token_addresses["weth"],
        mock_web3,
        Decimal("100"),
    )

    # Should return 0 liquidity and 100% impact on error
    assert liquidity == Decimal("0")
    assert impact == Decimal("100")


@pytest.mark.asyncio
async def test_get_liquidity_depth_initializes_factory(
    uniswap_v3, mock_web3, token_addresses
):
    """Test that get_liquidity_depth initializes factory if needed."""
    assert uniswap_v3.factory_contract is None

    mock_factory = MagicMock()
    mock_factory.functions.getPool.return_value.call.return_value = (
        "0x1234567890123456789012345678901234567890"
    )
    mock_web3.eth.contract.side_effect = [mock_factory, MagicMock()]

    mock_pool = MagicMock()
    mock_pool.functions.liquidity.return_value.call.return_value = (
        1000000000000000000000
    )
    mock_web3.eth.contract.side_effect = [mock_factory, mock_pool]

    await uniswap_v3.get_liquidity_depth(
        token_addresses["usdc"],
        token_addresses["weth"],
        mock_web3,
        Decimal("100"),
    )

    # Factory should be initialized
    assert uniswap_v3.factory_contract is not None


def test_initialize_factory(uniswap_v3, mock_web3):
    """Test factory contract initialization."""
    assert uniswap_v3.factory_contract is None

    mock_factory = MagicMock()
    mock_web3.eth.contract.return_value = mock_factory

    uniswap_v3._initialize_factory(mock_web3)

    assert uniswap_v3.factory_contract is not None
    mock_web3.eth.contract.assert_called_once()
    call_kwargs = mock_web3.eth.contract.call_args[1]
    assert call_kwargs["address"] == uniswap_v3.factory_address
    assert "abi" in call_kwargs


def test_initialize_quoter(uniswap_v3, mock_web3):
    """Test quoter contract initialization."""
    assert uniswap_v3.quoter_contract is None

    mock_quoter = MagicMock()
    mock_web3.eth.contract.return_value = mock_quoter

    uniswap_v3._initialize_quoter(mock_web3)

    assert uniswap_v3.quoter_contract is not None
    mock_web3.eth.contract.assert_called_once()
    call_kwargs = mock_web3.eth.contract.call_args[1]
    assert call_kwargs["address"] == uniswap_v3.quoter_address
    assert "abi" in call_kwargs


def test_fee_tiers_constant(uniswap_v3):
    """Test that FEE_TIERS constant is correct."""
    assert hasattr(uniswap_v3, "FEE_TIERS")
    assert isinstance(uniswap_v3.FEE_TIERS, list)
    assert len(uniswap_v3.FEE_TIERS) == 4
    assert uniswap_v3.FEE_TIERS == [100, 500, 3000, 10000]


def test_uniswap_v3_inherits_from_dex(uniswap_v3):
    """Test that UniswapV3 properly inherits from DEX."""
    from src.dex.base import DEX

    assert isinstance(uniswap_v3, DEX)
    assert hasattr(uniswap_v3, "get_token_price")
    assert hasattr(uniswap_v3, "execute_trade")
    assert hasattr(uniswap_v3, "get_liquidity_depth")
    assert hasattr(uniswap_v3, "initialize_contract")
