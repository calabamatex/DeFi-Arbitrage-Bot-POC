"""Comprehensive tests for Risk Management System."""

import pytest
import os
from decimal import Decimal
from unittest.mock import Mock, patch
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
def risk_manager(mock_web3, mock_erc20_abi, tmp_path):
    """Create RiskManager with isolated state file."""
    config = {
        "MAX_POSITION_SIZE_USD": 10000,
        "MAX_TOTAL_EXPOSURE_USD": 50000,
        "DAILY_LOSS_LIMIT_USD": 1000,
        "MAX_CONSECUTIVE_LOSSES": 5,
    }
    # Use a temp state file so tests don't leak state to each other
    state_file = str(tmp_path / "risk_state_test.json")
    with patch.dict(os.environ, {"RISK_STATE_FILE": state_file}):
        return RiskManager(mock_web3, mock_erc20_abi, config)


@pytest.fixture
def sample_opportunity():
    """Create sample opportunity dict (new dict-based interface)."""
    return {
        'direction': 'V3->V2',
        'token_in': '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174',
        'token_out': '0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270',
        'amount_in': 1000 * 10**6,  # $1000 USDC
        'net_profit': 5 * 10**6,    # $5 profit
        'v3_fee': 3000,
        'dex_path': ['uniswap_v3', 'quickswap'],
        'token_decimals': 6,
    }


# BalanceValidator tests
@pytest.mark.asyncio
async def test_check_balance_sufficient(balance_validator):
    """Test balance check with sufficient balance."""
    mock_contract = Mock()
    mock_contract.functions.balanceOf.return_value.call.return_value = int(10 * 10**18)
    mock_contract.functions.decimals.return_value.call.return_value = 18

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
    mock_contract.functions.decimals.return_value.call.return_value = 18

    balance_validator.web3.eth.contract.return_value = mock_contract

    result = await balance_validator.check_balance(
        "0x1234567890123456789012345678901234567890",
        "0x0987654321098765432109876543210987654321",
        Decimal("5.0"),
    )

    assert result is False


@pytest.mark.asyncio
async def test_balance_validator_uses_dynamic_decimals(balance_validator):
    """Test that BalanceValidator reads decimals from contract instead of hardcoding 18."""
    mock_contract = Mock()
    # USDC: 6 decimals, balance = 1000 USDC = 1000 * 10^6 wei
    mock_contract.functions.balanceOf.return_value.call.return_value = 1000 * 10**6
    mock_contract.functions.decimals.return_value.call.return_value = 6

    balance_validator.web3.eth.contract.return_value = mock_contract

    available = await balance_validator.get_available_balance(
        "0x1234567890123456789012345678901234567890",
        "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
    )

    assert available == Decimal("1000")


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


# LossTracker tests
def test_record_and_get_daily_pnl(loss_tracker):
    """Test recording trades and getting daily P/L."""
    trade1 = TradeResult(
        success=True, timestamp=datetime.now(), profit_loss=Decimal("50"),
        token_pair="WETH/USDC", buy_dex="SushiSwap", sell_dex="Uniswap V3",
        amount=Decimal("1.0"), gas_cost=Decimal("0.5"), message="Success",
    )
    trade2 = TradeResult(
        success=True, timestamp=datetime.now(), profit_loss=Decimal("-30"),
        token_pair="WETH/DAI", buy_dex="QuickSwap", sell_dex="SushiSwap",
        amount=Decimal("0.5"), gas_cost=Decimal("0.3"), message="Success",
    )
    loss_tracker.record_trade(trade1)
    loss_tracker.record_trade(trade2)
    daily_pnl = loss_tracker.get_daily_pnl()
    assert daily_pnl == Decimal("20")


def test_check_loss_limit_ok(loss_tracker):
    """Test loss limit check - within limits."""
    trade = TradeResult(
        success=True, timestamp=datetime.now(), profit_loss=Decimal("-500"),
        token_pair="WETH/USDC", buy_dex="SushiSwap", sell_dex="Uniswap V3",
        amount=Decimal("1.0"), gas_cost=Decimal("0.5"), message="Success",
    )
    loss_tracker.record_trade(trade)
    ok, msg = loss_tracker.check_loss_limit()
    assert ok is True


def test_check_loss_limit_exceeded(loss_tracker):
    """Test loss limit check - exceeded."""
    trade = TradeResult(
        success=False, timestamp=datetime.now(), profit_loss=Decimal("-1500"),
        token_pair="WETH/USDC", buy_dex="SushiSwap", sell_dex="Uniswap V3",
        amount=Decimal("1.0"), gas_cost=Decimal("0.5"), message="Failed",
    )
    loss_tracker.record_trade(trade)
    ok, msg = loss_tracker.check_loss_limit()
    assert ok is False
    assert "Daily loss" in msg


# CircuitBreaker tests
def test_circuit_breaker_trigger(circuit_breaker):
    """Test circuit breaker triggers after max losses."""
    for _ in range(5):
        circuit_breaker.record_trade_result(False)
    assert circuit_breaker.is_active is True
    allowed, msg = circuit_breaker.is_trading_allowed()
    assert allowed is False


def test_circuit_breaker_reset_on_success(circuit_breaker):
    """Test circuit breaker resets on success."""
    circuit_breaker.record_trade_result(False)
    circuit_breaker.record_trade_result(False)
    circuit_breaker.record_trade_result(True)
    assert circuit_breaker.consecutive_losses == 0


def test_circuit_breaker_manual_reset(circuit_breaker):
    """Test manual circuit breaker reset."""
    circuit_breaker.trigger()
    assert circuit_breaker.is_active is True
    circuit_breaker.reset()
    assert circuit_breaker.is_active is False
    assert circuit_breaker.consecutive_losses == 0


# RiskManager integration tests (dict-based interface)
def test_validate_trade_approved(risk_manager, sample_opportunity):
    """Test trade validation - approved with dict-based opportunity."""
    approved, reason = risk_manager.validate_trade(
        sample_opportunity,
        "0x1234567890123456789012345678901234567890",
        "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
    )
    assert approved is True
    assert "passed" in reason


def test_validate_trade_circuit_breaker_active(risk_manager, sample_opportunity):
    """Test trade validation - circuit breaker active."""
    risk_manager.circuit_breaker.trigger()
    approved, reason = risk_manager.validate_trade(
        sample_opportunity,
        "0x1234567890123456789012345678901234567890",
        "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
    )
    assert approved is False
    assert "Circuit breaker" in reason


def test_validate_trade_shutdown_active(risk_manager, sample_opportunity):
    """Test trade validation - emergency shutdown."""
    risk_manager.emergency_shutdown("Test shutdown")
    approved, reason = risk_manager.validate_trade(
        sample_opportunity,
        "0x1234567890123456789012345678901234567890",
        "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
    )
    assert approved is False
    assert "shutdown" in reason


def test_validate_trade_position_too_large(risk_manager):
    """Test trade validation - position size exceeds limit."""
    big_opportunity = {
        'token_in': '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174',
        'token_out': '0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270',
        'amount_in': 50000 * 10**6,  # $50000 (exceeds $10000 limit)
        'net_profit': 100 * 10**6,
        'token_decimals': 6,
    }
    approved, reason = risk_manager.validate_trade(
        big_opportunity,
        "0x1234567890123456789012345678901234567890",
        "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
    )
    assert approved is False
    assert "exceeds" in reason


def test_record_trade_result(risk_manager):
    """Test recording trade result."""
    trade_result = TradeResult(
        success=True, timestamp=datetime.now(), profit_loss=Decimal("50"),
        token_pair="WETH/USDC", buy_dex="SushiSwap", sell_dex="Uniswap V3",
        amount=Decimal("1.0"), gas_cost=Decimal("0.5"), message="Success",
    )
    risk_manager.record_trade_result(trade_result)
    assert len(risk_manager.loss_tracker.trades) == 1
    assert risk_manager.circuit_breaker.consecutive_losses == 0


def test_emergency_shutdown(risk_manager):
    """Test emergency shutdown."""
    risk_manager.emergency_shutdown("Test shutdown")
    assert risk_manager.shutdown_active is True
    assert risk_manager.shutdown_reason == "Test shutdown"


def test_reset_shutdown_with_env_code(risk_manager, monkeypatch):
    """Test resetting emergency shutdown reads code from env var."""
    monkeypatch.setenv("ADMIN_RESET_CODE", "my_secret_code_123")
    risk_manager.emergency_shutdown("Test shutdown")

    # Correct code
    result = risk_manager.reset_shutdown("my_secret_code_123")
    assert result is True
    assert risk_manager.shutdown_active is False

    # Wrong code
    risk_manager.emergency_shutdown("Test shutdown 2")
    result = risk_manager.reset_shutdown("WRONG_CODE")
    assert result is False
    assert risk_manager.shutdown_active is True


def test_reset_shutdown_fails_without_env(risk_manager, monkeypatch):
    """Test that reset_shutdown fails when ADMIN_RESET_CODE is not set."""
    monkeypatch.delenv("ADMIN_RESET_CODE", raising=False)
    risk_manager.emergency_shutdown("Test shutdown")
    result = risk_manager.reset_shutdown("any_code")
    assert result is False
    assert risk_manager.shutdown_active is True


def test_get_risk_metrics(risk_manager):
    """Test getting risk metrics."""
    trade_result = TradeResult(
        success=True, timestamp=datetime.now(), profit_loss=Decimal("50"),
        token_pair="WETH/USDC", buy_dex="SushiSwap", sell_dex="Uniswap V3",
        amount=Decimal("1.0"), gas_cost=Decimal("0.5"), message="Success",
    )
    risk_manager.record_trade_result(trade_result)
    metrics = risk_manager.get_risk_metrics()
    assert isinstance(metrics, RiskMetrics)
    assert metrics.daily_pnl == Decimal("50")
    assert metrics.total_trades_today == 1
    assert metrics.trading_allowed is True
