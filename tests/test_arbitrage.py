"""Comprehensive tests for arbitrage module."""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from decimal import Decimal
from datetime import datetime
from web3 import Web3

from src.bot.arbitrage import (
    ArbitrageOpportunity,
    calculate_arbitrage,
    calculate_gas_cost,
    is_profitable,
    validate_balance,
    execute_arbitrage,
    log_arbitrage_attempt,
    BASE_PROFIT_THRESHOLD,
    GAS_LIMIT,
)
from src.dex.base import DEX


@pytest.fixture
def mock_web3():
    """Fixture providing mock Web3 instance."""
    web3 = Mock()
    web3.is_connected.return_value = True
    web3.eth.gas_price = 30000000000  # 30 Gwei
    web3.eth.get_transaction_count.return_value = 1
    web3.eth.wait_for_transaction_receipt.return_value = {"status": 1}
    web3.eth.send_raw_transaction.return_value = b"\x12\x34\x56\x78"
    web3.eth.account.sign_transaction.return_value = Mock(raw_transaction=b"\x00\x01")
    web3.to_checksum_address = Web3.to_checksum_address

    # Mock contract
    mock_contract = Mock()
    mock_balance_of = Mock()
    mock_balance_of.call.return_value = int(10 * 10**18)  # 10 tokens
    mock_contract.functions.balanceOf.return_value = mock_balance_of

    mock_allowance = Mock()
    mock_allowance.call.return_value = 0
    mock_contract.functions.allowance.return_value = mock_allowance

    mock_approve = Mock()
    mock_approve.build_transaction.return_value = {
        "from": "0x1234567890123456789012345678901234567890",
        "nonce": 1,
        "gas": 100000,
        "gasPrice": 30000000000,
    }
    mock_contract.functions.approve.return_value = mock_approve

    web3.eth.contract.return_value = mock_contract

    return web3


@pytest.fixture
def token_list():
    """Fixture providing token configuration."""
    return {
        "WETH": {
            "address": "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619",
            "decimals": 18,
        },
        "USDC": {
            "address": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
            "decimals": 6,
        },
    }


@pytest.fixture
def mock_dex_instances():
    """Fixture providing mock DEX instances."""
    dex1 = Mock(spec=DEX)
    dex1.name = "Uniswap V3"
    dex1.router_address = "0xE592427A0AEce92De3Edee1F18E0157C05861564"
    dex1.get_token_price = AsyncMock(return_value=Decimal("1850.50"))
    dex1.execute_trade = AsyncMock(return_value=(True, "0xabc123"))

    dex2 = Mock(spec=DEX)
    dex2.name = "SushiSwap"
    dex2.router_address = "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506"
    dex2.get_token_price = AsyncMock(return_value=Decimal("1849.75"))
    dex2.execute_trade = AsyncMock(return_value=(True, "0xdef456"))

    dex3 = Mock(spec=DEX)
    dex3.name = "QuickSwap"
    dex3.router_address = "0x8954AfA98594b838bda56FE4C12a09D7739D179b"
    dex3.get_token_price = AsyncMock(return_value=Decimal("1851.20"))
    dex3.execute_trade = AsyncMock(return_value=(True, "0xghi789"))

    return {
        "Uniswap V3": dex1,
        "SushiSwap": dex2,
        "QuickSwap": dex3,
    }


@pytest.fixture
def sample_opportunity():
    """Fixture providing sample arbitrage opportunity."""
    return ArbitrageOpportunity(
        token1="WETH",
        token2="USDC",
        buy_dex="SushiSwap",
        sell_dex="QuickSwap",
        expected_profit=Decimal("1.45"),
        amount=Decimal("0.1"),
        buy_price=Decimal("1849.75"),
        sell_price=Decimal("1851.20"),
        timestamp=datetime.now(),
    )


def test_arbitrage_opportunity_dataclass():
    """Test ArbitrageOpportunity dataclass initialization."""
    opp = ArbitrageOpportunity(
        token1="WETH",
        token2="USDC",
        buy_dex="Uniswap V3",
        sell_dex="SushiSwap",
        expected_profit=Decimal("10.0"),
        amount=Decimal("1.0"),
        buy_price=Decimal("1850.0"),
        sell_price=Decimal("1860.0"),
        timestamp=datetime.now(),
    )

    assert opp.token1 == "WETH"
    assert opp.token2 == "USDC"
    assert opp.buy_dex == "Uniswap V3"
    assert opp.sell_dex == "SushiSwap"
    assert opp.expected_profit == Decimal("10.0")
    assert opp.amount == Decimal("1.0")
    assert opp.buy_price == Decimal("1850.0")
    assert opp.sell_price == Decimal("1860.0")
    assert isinstance(opp.timestamp, datetime)


def test_arbitrage_opportunity_profit_percent():
    """Test profit percentage calculation in __post_init__."""
    opp = ArbitrageOpportunity(
        token1="WETH",
        token2="USDC",
        buy_dex="Uniswap V3",
        sell_dex="SushiSwap",
        expected_profit=Decimal("10.0"),
        amount=Decimal("1.0"),
        buy_price=Decimal("1850.0"),
        sell_price=Decimal("1860.0"),
        timestamp=datetime.now(),
    )

    # (1860 - 1850) / 1850 * 100 = 0.54054...%
    assert hasattr(opp, "profit_percent")
    assert opp.profit_percent > Decimal("0.5")
    assert opp.profit_percent < Decimal("0.6")


def test_arbitrage_opportunity_profit_percent_zero_buy_price():
    """Test profit percentage with zero buy price."""
    opp = ArbitrageOpportunity(
        token1="WETH",
        token2="USDC",
        buy_dex="Uniswap V3",
        sell_dex="SushiSwap",
        expected_profit=Decimal("10.0"),
        amount=Decimal("1.0"),
        buy_price=Decimal("0"),
        sell_price=Decimal("1860.0"),
        timestamp=datetime.now(),
    )

    assert opp.profit_percent == Decimal("0")


@pytest.mark.asyncio
async def test_calculate_arbitrage_found(mock_web3, token_list, mock_dex_instances):
    """Test calculate_arbitrage finds opportunity."""
    # Mock DEX.fetch_concurrent_prices to return different prices
    with patch.object(
        DEX,
        "fetch_concurrent_prices",
        new=AsyncMock(
            return_value={
                "Uniswap V3": Decimal("1850.50"),
                "SushiSwap": Decimal("1849.75"),
                "QuickSwap": Decimal("1851.20"),
            }
        ),
    ):
        opportunity = await calculate_arbitrage(
            "WETH", "USDC", mock_web3, mock_dex_instances, token_list
        )

    assert opportunity is not None
    assert isinstance(opportunity, ArbitrageOpportunity)
    assert opportunity.token1 == "WETH"
    assert opportunity.token2 == "USDC"
    assert opportunity.buy_dex == "SushiSwap"  # Lowest price
    assert opportunity.sell_dex == "QuickSwap"  # Highest price
    assert opportunity.buy_price == Decimal("1849.75")
    assert opportunity.sell_price == Decimal("1851.20")
    assert opportunity.expected_profit == Decimal("1.45")  # 1851.20 - 1849.75
    assert opportunity.amount == Decimal("0.1")


@pytest.mark.asyncio
async def test_calculate_arbitrage_none_found_no_profit(
    mock_web3, token_list, mock_dex_instances
):
    """Test calculate_arbitrage returns None when no profit."""
    # Mock same prices across all DEXes
    with patch.object(
        DEX,
        "fetch_concurrent_prices",
        new=AsyncMock(
            return_value={
                "Uniswap V3": Decimal("1850.00"),
                "SushiSwap": Decimal("1850.00"),
                "QuickSwap": Decimal("1850.00"),
            }
        ),
    ):
        opportunity = await calculate_arbitrage(
            "WETH", "USDC", mock_web3, mock_dex_instances, token_list
        )

    assert opportunity is None


@pytest.mark.asyncio
async def test_calculate_arbitrage_none_found_insufficient_dexes(
    mock_web3, token_list, mock_dex_instances
):
    """Test calculate_arbitrage returns None with insufficient valid DEXes."""
    # Mock only 1 valid price
    with patch.object(
        DEX,
        "fetch_concurrent_prices",
        new=AsyncMock(
            return_value={
                "Uniswap V3": Decimal("1850.00"),
                # Other DEXes failed (price = 0)
            }
        ),
    ):
        opportunity = await calculate_arbitrage(
            "WETH", "USDC", mock_web3, mock_dex_instances, token_list
        )

    assert opportunity is None


@pytest.mark.asyncio
async def test_calculate_arbitrage_filters_zero_prices(
    mock_web3, token_list, mock_dex_instances
):
    """Test that zero prices are filtered out."""
    # Mock with some zero prices
    with patch.object(
        DEX,
        "fetch_concurrent_prices",
        new=AsyncMock(
            return_value={
                "Uniswap V3": Decimal("1850.50"),
                "SushiSwap": Decimal("0"),  # Failed fetch
                "QuickSwap": Decimal("1851.20"),
            }
        ),
    ):
        opportunity = await calculate_arbitrage(
            "WETH", "USDC", mock_web3, mock_dex_instances, token_list
        )

    assert opportunity is not None
    # Should only consider Uniswap and QuickSwap
    assert opportunity.buy_dex in ["Uniswap V3", "QuickSwap"]
    assert opportunity.sell_dex in ["Uniswap V3", "QuickSwap"]


@pytest.mark.asyncio
async def test_calculate_arbitrage_exception_handling(
    mock_web3, token_list, mock_dex_instances
):
    """Test calculate_arbitrage handles exceptions gracefully."""
    # Mock fetch_concurrent_prices to raise exception
    with patch.object(
        DEX,
        "fetch_concurrent_prices",
        new=AsyncMock(side_effect=Exception("Network error")),
    ):
        opportunity = await calculate_arbitrage(
            "WETH", "USDC", mock_web3, mock_dex_instances, token_list
        )

    assert opportunity is None


@pytest.mark.asyncio
async def test_calculate_gas_cost(mock_web3):
    """Test calculate_gas_cost calculates correctly."""
    gas_cost = await calculate_gas_cost(mock_web3, GAS_LIMIT, Decimal("1.0"))

    # gas_price = 30 Gwei = 30 * 10^9 wei
    # gas_cost_wei = 30 * 10^9 * 300000 = 9 * 10^15 wei
    # gas_cost_matic = 9 * 10^15 / 10^18 = 0.009 MATIC
    # gas_cost_usd = 0.009 * 1.0 = 0.009 USD
    expected = Decimal("0.009")
    assert gas_cost == expected


@pytest.mark.asyncio
async def test_calculate_gas_cost_with_matic_price(mock_web3):
    """Test calculate_gas_cost with different MATIC price."""
    matic_price = Decimal("0.80")
    gas_cost = await calculate_gas_cost(mock_web3, GAS_LIMIT, matic_price)

    # gas_cost_matic = 0.009 MATIC
    # gas_cost_usd = 0.009 * 0.80 = 0.0072 USD
    expected = Decimal("0.009") * matic_price
    assert gas_cost == expected


@pytest.mark.asyncio
async def test_calculate_gas_cost_exception_returns_default(mock_web3):
    """Test calculate_gas_cost returns default on exception."""
    # Mock gas_price to raise exception
    mock_web3.eth.gas_price = None

    gas_cost = await calculate_gas_cost(mock_web3)

    # Should return default estimate
    assert gas_cost == Decimal("0.1")


@pytest.mark.asyncio
async def test_is_profitable_true(mock_web3, sample_opportunity):
    """Test is_profitable returns True for profitable opportunity."""
    # Opportunity: profit = 1.45, amount = 0.1
    # gross_profit_usd = 1.45 * 0.1 = 0.145
    # gas_cost = 0.009 * 2 = 0.018 (for 2 trades)
    # net_profit = 0.145 - 0.018 = 0.127
    # profit_percent = 0.127 / (1849.75 * 0.1) = 0.127 / 184.975 = 0.0006866... = 0.06866%

    # This is > 0 but < 0.5% threshold, so it will be False
    # Let's adjust the opportunity to be more profitable
    sample_opportunity.expected_profit = Decimal("20.0")

    is_prof, net_profit = await is_profitable(sample_opportunity, mock_web3)

    # gross_profit_usd = 20.0 * 0.1 = 2.0
    # gas_cost = 0.018
    # net_profit = 2.0 - 0.018 = 1.982
    # profit_percent = 1.982 / (1849.75 * 0.1) = 1.982 / 184.975 = 0.0107... = 1.07%

    assert is_prof is True
    assert net_profit > Decimal("1.9")


@pytest.mark.asyncio
async def test_is_profitable_false_below_threshold(mock_web3, sample_opportunity):
    """Test is_profitable returns False when below threshold."""
    # Keep default opportunity: profit = 1.45
    # This should be below threshold after gas

    is_prof, net_profit = await is_profitable(sample_opportunity, mock_web3)

    # Should be False because profit is too small
    assert is_prof is False


@pytest.mark.asyncio
async def test_is_profitable_false_negative_profit(mock_web3, sample_opportunity):
    """Test is_profitable returns False for negative profit."""
    # Set very small profit
    sample_opportunity.expected_profit = Decimal("0.01")

    is_prof, net_profit = await is_profitable(sample_opportunity, mock_web3)

    # gross_profit_usd = 0.01 * 0.1 = 0.001
    # gas_cost = 0.018
    # net_profit = 0.001 - 0.018 = -0.017 (negative)

    assert is_prof is False
    assert net_profit < Decimal("0")


@pytest.mark.asyncio
async def test_is_profitable_custom_threshold(mock_web3, sample_opportunity):
    """Test is_profitable with custom threshold."""
    sample_opportunity.expected_profit = Decimal("10.0")

    # Use very high threshold (10%)
    is_prof, net_profit = await is_profitable(
        sample_opportunity, mock_web3, min_profit_threshold=Decimal("0.1")
    )

    # Should be False because profit won't reach 10%
    assert is_prof is False


@pytest.mark.asyncio
async def test_is_profitable_exception_handling(mock_web3, sample_opportunity):
    """Test is_profitable handles exceptions."""
    # Mock calculate_gas_cost to raise exception
    with patch(
        "src.bot.arbitrage.calculate_gas_cost",
        new=AsyncMock(side_effect=Exception("Gas calculation failed")),
    ):
        is_prof, net_profit = await is_profitable(sample_opportunity, mock_web3)

    assert is_prof is False
    assert net_profit == Decimal("0")


@pytest.mark.asyncio
async def test_validate_balance_sufficient(mock_web3, token_list):
    """Test validate_balance returns True for sufficient balance."""
    account = "0x1234567890123456789012345678901234567890"
    token_address = token_list["WETH"]["address"]
    amount = Decimal("5.0")  # Have 10, need 5

    result = await validate_balance(account, token_address, amount, mock_web3)

    assert result is True


@pytest.mark.asyncio
async def test_validate_balance_insufficient(mock_web3, token_list):
    """Test validate_balance returns False for insufficient balance."""
    account = "0x1234567890123456789012345678901234567890"
    token_address = token_list["WETH"]["address"]
    amount = Decimal("15.0")  # Have 10, need 15

    result = await validate_balance(account, token_address, amount, mock_web3)

    assert result is False


@pytest.mark.asyncio
async def test_validate_balance_exact_amount(mock_web3, token_list):
    """Test validate_balance with exact amount."""
    account = "0x1234567890123456789012345678901234567890"
    token_address = token_list["WETH"]["address"]
    amount = Decimal("10.0")  # Exactly what we have

    result = await validate_balance(account, token_address, amount, mock_web3)

    assert result is True


@pytest.mark.asyncio
async def test_validate_balance_exception_handling(mock_web3, token_list):
    """Test validate_balance handles exceptions."""
    account = "0x1234567890123456789012345678901234567890"
    token_address = token_list["WETH"]["address"]

    # Mock contract to raise exception
    mock_web3.eth.contract.side_effect = Exception("Contract error")

    result = await validate_balance(account, token_address, Decimal("1.0"), mock_web3)

    assert result is False


@pytest.mark.asyncio
async def test_execute_arbitrage_insufficient_balance(
    mock_web3, sample_opportunity, mock_dex_instances, token_list
):
    """Test execute_arbitrage fails with insufficient balance."""
    # Use a known valid Ethereum address
    account = "0x1234567890123456789012345678901234567890"
    private_key = "0x" + "a" * 64

    # Mock validate_balance to return False
    with patch("src.bot.arbitrage.validate_balance", new=AsyncMock(return_value=False)):
        success, message, profit = await execute_arbitrage(
            sample_opportunity,
            mock_web3,
            mock_dex_instances,
            token_list,
            account,
            private_key,
        )

    assert success is False
    assert "Insufficient balance" in message
    assert profit == Decimal("0")


@pytest.mark.asyncio
async def test_execute_arbitrage_buy_trade_fails(
    mock_web3, sample_opportunity, mock_dex_instances, token_list
):
    """Test execute_arbitrage handles buy trade failure."""
    account = "0x1234567890123456789012345678901234567890"
    private_key = "0x" + "a" * 64

    # Mock buy DEX to fail
    mock_dex_instances["SushiSwap"].execute_trade = AsyncMock(
        return_value=(False, "Trade failed")
    )

    with patch("src.bot.arbitrage.validate_balance", new=AsyncMock(return_value=True)):
        success, message, profit = await execute_arbitrage(
            sample_opportunity,
            mock_web3,
            mock_dex_instances,
            token_list,
            account,
            private_key,
        )

    assert success is False
    assert "Buy trade failed" in message
    assert profit == Decimal("0")


@pytest.mark.asyncio
async def test_execute_arbitrage_sell_trade_fails(
    mock_web3, sample_opportunity, mock_dex_instances, token_list
):
    """Test execute_arbitrage handles sell trade failure."""
    account = "0x1234567890123456789012345678901234567890"
    private_key = "0x" + "a" * 64

    # Mock sell DEX to fail
    mock_dex_instances["QuickSwap"].execute_trade = AsyncMock(
        return_value=(False, "Trade failed")
    )

    with patch("src.bot.arbitrage.validate_balance", new=AsyncMock(return_value=True)):
        success, message, profit = await execute_arbitrage(
            sample_opportunity,
            mock_web3,
            mock_dex_instances,
            token_list,
            account,
            private_key,
        )

    assert success is False
    assert "Sell trade failed" in message
    assert profit == Decimal("0")


@pytest.mark.asyncio
async def test_execute_arbitrage_success(
    mock_web3, sample_opportunity, mock_dex_instances, token_list
):
    """Test execute_arbitrage completes successfully."""
    account = "0x1234567890123456789012345678901234567890"
    private_key = "0x" + "a" * 64

    with patch("src.bot.arbitrage.validate_balance", new=AsyncMock(return_value=True)):
        success, message, profit = await execute_arbitrage(
            sample_opportunity,
            mock_web3,
            mock_dex_instances,
            token_list,
            account,
            private_key,
        )

    assert success is True
    assert "Arbitrage executed successfully" in message
    assert isinstance(profit, Decimal)


@pytest.mark.asyncio
async def test_execute_arbitrage_exception_handling(
    mock_web3, sample_opportunity, mock_dex_instances, token_list
):
    """Test execute_arbitrage handles exceptions."""
    account = "0x1234567890123456789012345678901234567890"
    private_key = "0x" + "a" * 64

    # Mock validate_balance to raise exception
    with patch(
        "src.bot.arbitrage.validate_balance",
        new=AsyncMock(side_effect=Exception("Network error")),
    ):
        success, message, profit = await execute_arbitrage(
            sample_opportunity,
            mock_web3,
            mock_dex_instances,
            token_list,
            account,
            private_key,
        )

    assert success is False
    assert "Network error" in message
    assert profit == Decimal("0")


@pytest.mark.asyncio
async def test_log_arbitrage_attempt(sample_opportunity, tmp_path):
    """Test log_arbitrage_attempt logs correctly."""
    # Change to temp directory for test
    import os

    original_dir = os.getcwd()
    os.chdir(tmp_path)

    try:
        await log_arbitrage_attempt(
            sample_opportunity,
            success=True,
            message="Test successful",
            actual_profit=Decimal("0.5"),
        )

        # Check file was created
        log_file = tmp_path / "arbitrage_log.txt"
        assert log_file.exists()

        # Check contents
        contents = log_file.read_text()
        assert "Arbitrage Attempt" in contents
        assert "WETH/USDC" in contents
        assert "SushiSwap" in contents
        assert "QuickSwap" in contents
        assert "Success: True" in contents
        assert "Actual Profit: 0.5" in contents
        assert "Test successful" in contents
    finally:
        os.chdir(original_dir)


@pytest.mark.asyncio
async def test_log_arbitrage_attempt_file_error(sample_opportunity):
    """Test log_arbitrage_attempt handles file write errors."""
    # Mock open() to raise exception
    with patch("builtins.open", side_effect=PermissionError("Permission denied")):
        # Should not raise exception
        try:
            await log_arbitrage_attempt(
                sample_opportunity,
                success=False,
                message="Test failed",
                actual_profit=Decimal("0"),
            )
        except Exception as e:
            pytest.fail(f"log_arbitrage_attempt raised exception: {e}")
