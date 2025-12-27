"""Comprehensive tests for Risk Management System."""

import pytest
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
from src.utils.risk_manager import (
    BalanceValidator,
    PositionManager,
    LossTracker,
    CircuitBreaker,
    RiskManager,
    TradeResult,
    RiskMetrics,
)
from src.bot.arbitrage import ArbitrageOpportunity


@pytest.fixture
def mock_web3():
    """Mock Web3 instance."""
    web3 = Mock()
    return web3


@pytest.fixture
def mock_erc20_abi():
    """Mock ERC20 ABI."""
    return []


@pytest.fixture
def balance_validator(mock_web3, mock_erc20_abi):
    """Create BalanceValidator."""
    return BalanceValidator(mock_web3, mock_erc20_abi)


@pytest.fixture
def position_manager():
    """Create PositionManager."""
    return PositionManager(
        max_position_size_usd=Decimal("10000"),
        max_total_exposure_usd=Decimal("50000"),
    )


@pytest.fixture
def loss_tracker():
    """Create LossTracker."""
    return LossTracker(daily_loss_limit_usd=Decimal("1000"))


@pytest.fixture
def circuit_breaker():
    """Create CircuitBreaker."""
    return CircuitBreaker(max_consecutive_losses=5, cooldown_minutes=60)


@pytest.fixture
def risk_manager(mock_web3, mock_erc20_abi):
    """Create RiskManager."""
    config = {
        "MAX_POSITION_SIZE_USD": 10000,
        "MAX_TOTAL_EXPOSURE_USD": 50000,
        "DAILY_LOSS_LIMIT_USD": 1000,
        "MAX_CONSECUTIVE_LOSSES": 5,
    }
    return RiskManager(mock_web3, mock_erc20_abi, config)


@pytest.fixture
def sample_opportunity():
    """Create sample arbitrage opportunity."""
    return ArbitrageOpportunity(
        token1="WETH",
        token2="USDC",
        buy_dex="SushiSwap",
        sell_dex="Uniswap V3",
        expected_profit=Decimal("10"),
        amount=Decimal("1.0"),
        buy_price=Decimal("2000"),
        sell_price=Decimal("2010"),
        timestamp=datetime.now(),
    )


# BalanceValidator tests
@pytest.mark.asyncio
async def test_check_balance_sufficient(balance_validator):
    """Test balance check with sufficient balance."""
    mock_contract = Mock()
    mock_contract.functions.balanceOf.return_value.call.return_value = int(
        10 * 10**18
    )

    balance_validator.web3.eth.contract.return_value = mock_contract

    result = await balance_validator.check_balance(
        "0x1234567890123456789012345678901234567890",
        "0x0987654321098765432109876543210987654321",
        Decimal("5.0"),
    )

    assert result is True


@pytest.mark.asyncio
async def test_check_balance_insufficient(balance_validator):
    """Test balance check with insufficient balance."""
    mock_contract = Mock()
    mock_contract.functions.balanceOf.return_value.call.return_value = int(2 * 10**18)

    balance_validator.web3.eth.contract.return_value = mock_contract

    result = await balance_validator.check_balance(
        "0x1234567890123456789012345678901234567890",
        "0x0987654321098765432109876543210987654321",
        Decimal("5.0"),
    )

    assert result is False


@pytest.mark.asyncio
async def test_get_available_balance(balance_validator):
    """Test getting available balance."""
    mock_contract = Mock()
    mock_contract.functions.balanceOf.return_value.call.return_value = int(
        10 * 10**18
    )

    balance_validator.web3.eth.contract.return_value = mock_contract

    available = await balance_validator.get_available_balance(
        "0x1234567890123456789012345678901234567890",
        "0x0987654321098765432109876543210987654321",
    )

    assert available == Decimal("10")


@pytest.mark.asyncio
async def test_reserve_and_release_balance(balance_validator):
    """Test reserving and releasing balance."""
    mock_contract = Mock()
    mock_contract.functions.balanceOf.return_value.call.return_value = int(
        10 * 10**18
    )

    balance_validator.web3.eth.contract.return_value = mock_contract

    account = "0x1234567890123456789012345678901234567890"
    token = "0x0987654321098765432109876543210987654321"

    # Reserve balance
    balance_validator.reserve_balance(account, token, Decimal("3.0"))

    # Check available (should be reduced)
    available = await balance_validator.get_available_balance(account, token)
    assert available == Decimal("7.0")

    # Release balance
    balance_validator.release_balance(account, token, Decimal("3.0"))

    # Check available (should be restored)
    available = await balance_validator.get_available_balance(account, token)
    assert available == Decimal("10.0")


@pytest.mark.asyncio
async def test_check_balance_with_error(balance_validator):
    """Test balance check with error."""
    balance_validator.web3.eth.contract.side_effect = Exception("Contract error")

    result = await balance_validator.check_balance(
        "0x1234567890123456789012345678901234567890",
        "0x0987654321098765432109876543210987654321",
        Decimal("5.0"),
    )

    assert result is False


# PositionManager tests
def test_validate_position_size_ok(position_manager):
    """Test position size validation - OK."""
    valid, msg = position_manager.validate_position_size(Decimal("5000"))

    assert valid is True
    assert "OK" in msg


def test_validate_position_size_too_large(position_manager):
    """Test position size validation - too large."""
    valid, msg = position_manager.validate_position_size(Decimal("15000"))

    assert valid is False
    assert "exceeds" in msg


def test_track_and_get_exposure(position_manager):
    """Test tracking positions and getting exposure."""
    position_manager.track_open_position("WETH", Decimal("5000"))
    position_manager.track_open_position("USDC", Decimal("3000"))

    exposure = position_manager.get_total_exposure()

    assert exposure == Decimal("8000")


def test_close_position(position_manager):
    """Test closing a position."""
    position_manager.track_open_position("WETH", Decimal("5000"))
    position_manager.track_open_position("USDC", Decimal("3000"))

    position_manager.close_position("WETH")

    assert "WETH" not in position_manager.open_positions
    assert position_manager.get_total_exposure() == Decimal("3000")


def test_check_exposure_limit_ok(position_manager):
    """Test exposure limit check - OK."""
    position_manager.track_open_position("WETH", Decimal("20000"))

    within_limit, msg = position_manager.check_exposure_limit()

    assert within_limit is True


def test_check_exposure_limit_exceeded(position_manager):
    """Test exposure limit check - exceeded."""
    position_manager.track_open_position("WETH", Decimal("60000"))

    within_limit, msg = position_manager.check_exposure_limit()

    assert within_limit is False
    assert "exceeds" in msg


def test_check_concentration_risk_ok(position_manager):
    """Test concentration risk - OK."""
    # Add diversified positions first
    position_manager.track_open_position("WETH", Decimal("3000"))
    position_manager.track_open_position("USDC", Decimal("5000"))
    position_manager.track_open_position("DAI", Decimal("5000"))

    # Adding more to WETH should be OK since it keeps it under 30%
    # New total: 3000+500=3500 / (3000+5000+5000+500)=3500/13500 = 26% < 30%
    ok, msg = position_manager.check_concentration_risk("WETH", Decimal("500"))

    assert ok is True


def test_check_concentration_risk_exceeded(position_manager):
    """Test concentration risk - exceeded."""
    # Add large position to create high concentration
    position_manager.track_open_position("WETH", Decimal("40000"))

    ok, msg = position_manager.check_concentration_risk("WETH", Decimal("20000"))

    # Should fail concentration check
    assert ok is False


# LossTracker tests
def test_record_and_get_daily_pnl(loss_tracker):
    """Test recording trades and getting daily P/L."""
    trade1 = TradeResult(
        success=True,
        timestamp=datetime.now(),
        profit_loss=Decimal("50"),
        token_pair="WETH/USDC",
        buy_dex="SushiSwap",
        sell_dex="Uniswap V3",
        amount=Decimal("1.0"),
        gas_cost=Decimal("0.5"),
        message="Success",
    )

    trade2 = TradeResult(
        success=True,
        timestamp=datetime.now(),
        profit_loss=Decimal("-30"),
        token_pair="WETH/DAI",
        buy_dex="QuickSwap",
        sell_dex="SushiSwap",
        amount=Decimal("0.5"),
        gas_cost=Decimal("0.3"),
        message="Success",
    )

    loss_tracker.record_trade(trade1)
    loss_tracker.record_trade(trade2)

    daily_pnl = loss_tracker.get_daily_pnl()

    assert daily_pnl == Decimal("20")  # 50 - 30


def test_get_weekly_pnl(loss_tracker):
    """Test getting weekly P/L."""
    # Add recent trade
    trade1 = TradeResult(
        success=True,
        timestamp=datetime.now(),
        profit_loss=Decimal("100"),
        token_pair="WETH/USDC",
        buy_dex="SushiSwap",
        sell_dex="Uniswap V3",
        amount=Decimal("1.0"),
        gas_cost=Decimal("0.5"),
        message="Success",
    )

    # Add old trade (more than 7 days ago)
    trade2 = TradeResult(
        success=True,
        timestamp=datetime.now() - timedelta(days=8),
        profit_loss=Decimal("50"),
        token_pair="WETH/DAI",
        buy_dex="QuickSwap",
        sell_dex="SushiSwap",
        amount=Decimal("0.5"),
        gas_cost=Decimal("0.3"),
        message="Success",
    )

    loss_tracker.record_trade(trade1)
    loss_tracker.record_trade(trade2)

    weekly_pnl = loss_tracker.get_weekly_pnl()

    # Should only include recent trade
    assert weekly_pnl == Decimal("100")


def test_check_loss_limit_ok(loss_tracker):
    """Test loss limit check - within limits."""
    trade = TradeResult(
        success=True,
        timestamp=datetime.now(),
        profit_loss=Decimal("-500"),  # Within limit
        token_pair="WETH/USDC",
        buy_dex="SushiSwap",
        sell_dex="Uniswap V3",
        amount=Decimal("1.0"),
        gas_cost=Decimal("0.5"),
        message="Success",
    )

    loss_tracker.record_trade(trade)

    ok, msg = loss_tracker.check_loss_limit()

    assert ok is True


def test_check_loss_limit_exceeded(loss_tracker):
    """Test loss limit check - exceeded."""
    trade = TradeResult(
        success=False,
        timestamp=datetime.now(),
        profit_loss=Decimal("-1500"),  # Exceeds limit
        token_pair="WETH/USDC",
        buy_dex="SushiSwap",
        sell_dex="Uniswap V3",
        amount=Decimal("1.0"),
        gas_cost=Decimal("0.5"),
        message="Failed",
    )

    loss_tracker.record_trade(trade)

    ok, msg = loss_tracker.check_loss_limit()

    assert ok is False
    assert "Daily loss" in msg


def test_get_trade_count_today(loss_tracker):
    """Test getting trade count for today."""
    trade1 = TradeResult(
        success=True,
        timestamp=datetime.now(),
        profit_loss=Decimal("50"),
        token_pair="WETH/USDC",
        buy_dex="SushiSwap",
        sell_dex="Uniswap V3",
        amount=Decimal("1.0"),
        gas_cost=Decimal("0.5"),
        message="Success",
    )

    trade2 = TradeResult(
        success=True,
        timestamp=datetime.now() - timedelta(days=1),
        profit_loss=Decimal("30"),
        token_pair="WETH/DAI",
        buy_dex="QuickSwap",
        sell_dex="SushiSwap",
        amount=Decimal("0.5"),
        gas_cost=Decimal("0.3"),
        message="Success",
    )

    loss_tracker.record_trade(trade1)
    loss_tracker.record_trade(trade2)

    count = loss_tracker.get_trade_count_today()

    assert count == 1


def test_get_success_rate_today(loss_tracker):
    """Test getting success rate for today."""
    trade1 = TradeResult(
        success=True,
        timestamp=datetime.now(),
        profit_loss=Decimal("50"),
        token_pair="WETH/USDC",
        buy_dex="SushiSwap",
        sell_dex="Uniswap V3",
        amount=Decimal("1.0"),
        gas_cost=Decimal("0.5"),
        message="Success",
    )

    trade2 = TradeResult(
        success=False,
        timestamp=datetime.now(),
        profit_loss=Decimal("-30"),
        token_pair="WETH/DAI",
        buy_dex="QuickSwap",
        sell_dex="SushiSwap",
        amount=Decimal("0.5"),
        gas_cost=Decimal("0.3"),
        message="Failed",
    )

    loss_tracker.record_trade(trade1)
    loss_tracker.record_trade(trade2)

    success_rate = loss_tracker.get_success_rate_today()

    assert success_rate == Decimal("50")


def test_reset_daily(loss_tracker):
    """Test daily reset."""
    # Add old trade
    old_trade = TradeResult(
        success=True,
        timestamp=datetime.now() - timedelta(days=8),
        profit_loss=Decimal("50"),
        token_pair="WETH/USDC",
        buy_dex="SushiSwap",
        sell_dex="Uniswap V3",
        amount=Decimal("1.0"),
        gas_cost=Decimal("0.5"),
        message="Success",
    )

    # Add recent trade
    recent_trade = TradeResult(
        success=True,
        timestamp=datetime.now(),
        profit_loss=Decimal("30"),
        token_pair="WETH/DAI",
        buy_dex="QuickSwap",
        sell_dex="SushiSwap",
        amount=Decimal("0.5"),
        gas_cost=Decimal("0.3"),
        message="Success",
    )

    loss_tracker.record_trade(old_trade)
    loss_tracker.record_trade(recent_trade)

    loss_tracker.reset_daily()

    # Should only have recent trade
    assert len(loss_tracker.trades) == 1


# CircuitBreaker tests
def test_circuit_breaker_trigger(circuit_breaker):
    """Test circuit breaker triggers after max losses."""
    # Record consecutive losses
    for _ in range(5):
        circuit_breaker.record_trade_result(False)

    assert circuit_breaker.is_active is True

    allowed, msg = circuit_breaker.is_trading_allowed()
    assert allowed is False


def test_circuit_breaker_reset_on_success(circuit_breaker):
    """Test circuit breaker resets on success."""
    circuit_breaker.record_trade_result(False)
    circuit_breaker.record_trade_result(False)
    circuit_breaker.record_trade_result(True)  # Success resets

    assert circuit_breaker.consecutive_losses == 0


def test_circuit_breaker_manual_reset(circuit_breaker):
    """Test manual circuit breaker reset."""
    circuit_breaker.trigger()
    assert circuit_breaker.is_active is True

    circuit_breaker.reset()
    assert circuit_breaker.is_active is False
    assert circuit_breaker.consecutive_losses == 0


def test_circuit_breaker_status(circuit_breaker):
    """Test getting circuit breaker status."""
    circuit_breaker.record_trade_result(False)
    circuit_breaker.record_trade_result(False)

    status = circuit_breaker.get_status()

    assert status["consecutive_losses"] == 2
    assert status["max_losses"] == 5
    assert status["active"] is False


def test_circuit_breaker_consecutive_count(circuit_breaker):
    """Test consecutive loss counting."""
    circuit_breaker.record_trade_result(False)
    circuit_breaker.record_trade_result(False)
    circuit_breaker.record_trade_result(False)

    assert circuit_breaker.consecutive_losses == 3


# RiskManager integration tests
@pytest.mark.asyncio
async def test_validate_trade_approved(risk_manager, sample_opportunity):
    """Test trade validation - approved."""
    # Add existing positions to avoid 100% concentration issue
    risk_manager.position_manager.track_open_position("USDC", Decimal("5000"))
    risk_manager.position_manager.track_open_position("DAI", Decimal("5000"))

    # Mock balance check
    with patch.object(
        risk_manager.balance_validator, "check_balance", return_value=True
    ):
        approved, reason = await risk_manager.validate_trade(
            sample_opportunity,
            "0x1234567890123456789012345678901234567890",
            "0x0987654321098765432109876543210987654321",
        )

    assert approved is True
    assert "passed" in reason


@pytest.mark.asyncio
async def test_validate_trade_insufficient_balance(risk_manager, sample_opportunity):
    """Test trade validation - insufficient balance."""
    # Mock balance check to fail
    with patch.object(
        risk_manager.balance_validator, "check_balance", return_value=False
    ):
        approved, reason = await risk_manager.validate_trade(
            sample_opportunity,
            "0x1234567890123456789012345678901234567890",
            "0x0987654321098765432109876543210987654321",
        )

    assert approved is False
    assert "balance" in reason


@pytest.mark.asyncio
async def test_validate_trade_circuit_breaker_active(risk_manager, sample_opportunity):
    """Test trade validation - circuit breaker active."""
    # Trigger circuit breaker
    risk_manager.circuit_breaker.trigger()

    approved, reason = await risk_manager.validate_trade(
        sample_opportunity,
        "0x1234567890123456789012345678901234567890",
        "0x0987654321098765432109876543210987654321",
    )

    assert approved is False
    assert "Circuit breaker" in reason


@pytest.mark.asyncio
async def test_validate_trade_shutdown_active(risk_manager, sample_opportunity):
    """Test trade validation - emergency shutdown."""
    risk_manager.emergency_shutdown("Test shutdown")

    approved, reason = await risk_manager.validate_trade(
        sample_opportunity,
        "0x1234567890123456789012345678901234567890",
        "0x0987654321098765432109876543210987654321",
    )

    assert approved is False
    assert "shutdown" in reason


def test_record_trade_result(risk_manager):
    """Test recording trade result."""
    trade_result = TradeResult(
        success=True,
        timestamp=datetime.now(),
        profit_loss=Decimal("50"),
        token_pair="WETH/USDC",
        buy_dex="SushiSwap",
        sell_dex="Uniswap V3",
        amount=Decimal("1.0"),
        gas_cost=Decimal("0.5"),
        message="Success",
    )

    risk_manager.record_trade_result(trade_result)

    # Check it was recorded
    assert len(risk_manager.loss_tracker.trades) == 1
    assert risk_manager.circuit_breaker.consecutive_losses == 0


def test_emergency_shutdown(risk_manager):
    """Test emergency shutdown."""
    risk_manager.emergency_shutdown("Test shutdown")

    assert risk_manager.shutdown_active is True
    assert risk_manager.shutdown_reason == "Test shutdown"


def test_reset_shutdown(risk_manager):
    """Test resetting emergency shutdown."""
    risk_manager.emergency_shutdown("Test shutdown")

    # Try reset with correct code
    result = risk_manager.reset_shutdown("RESET_SHUTDOWN")
    assert result is True
    assert risk_manager.shutdown_active is False

    # Try reset with wrong code
    risk_manager.emergency_shutdown("Test shutdown 2")
    result = risk_manager.reset_shutdown("WRONG_CODE")
    assert result is False
    assert risk_manager.shutdown_active is True


def test_get_risk_metrics(risk_manager):
    """Test getting risk metrics."""
    # Record a trade
    trade_result = TradeResult(
        success=True,
        timestamp=datetime.now(),
        profit_loss=Decimal("50"),
        token_pair="WETH/USDC",
        buy_dex="SushiSwap",
        sell_dex="Uniswap V3",
        amount=Decimal("1.0"),
        gas_cost=Decimal("0.5"),
        message="Success",
    )
    risk_manager.record_trade_result(trade_result)

    metrics = risk_manager.get_risk_metrics()

    assert isinstance(metrics, RiskMetrics)
    assert metrics.daily_pnl == Decimal("50")
    assert metrics.total_trades_today == 1
    assert metrics.trading_allowed is True
