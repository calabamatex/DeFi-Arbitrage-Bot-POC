"""Comprehensive tests for Emergency Shutdown System."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from decimal import Decimal
from src.utils.emergency_shutdown import (
    EmergencyShutdown,
    ShutdownTrigger,
    ShutdownEvent,
    create_loss_limit_trigger,
    create_circuit_breaker_trigger,
    create_balance_trigger,
)


@pytest.fixture
def mock_telegram():
    """Mock Telegram bot."""
    telegram = AsyncMock()
    telegram.send_alert = AsyncMock()
    return telegram


@pytest.fixture
def shutdown_system(mock_telegram):
    """Create EmergencyShutdown instance."""
    return EmergencyShutdown(telegram_bot=mock_telegram, admin_code="TEST_CODE")


def test_initialization(shutdown_system):
    """Test EmergencyShutdown initialization."""
    assert shutdown_system.shutdown_active is False
    assert shutdown_system.shutdown_reason is None
    assert shutdown_system.admin_code == "TEST_CODE"
    assert len(shutdown_system.triggers) == 0
    assert len(shutdown_system.shutdown_history) == 0


def test_initialization_without_telegram():
    """Test initialization without Telegram bot."""
    shutdown = EmergencyShutdown(telegram_bot=None, admin_code="TEST")

    assert shutdown.telegram_bot is None
    assert shutdown.shutdown_active is False


def test_register_trigger(shutdown_system):
    """Test registering a shutdown trigger."""

    def test_condition():
        return False

    shutdown_system.register_shutdown_trigger(
        "test_trigger", test_condition, "HIGH", "Test trigger", auto_trigger=True
    )

    assert "test_trigger" in shutdown_system.triggers
    assert shutdown_system.triggers["test_trigger"].severity == "HIGH"
    assert shutdown_system.triggers["test_trigger"].auto_trigger is True


def test_register_multiple_triggers(shutdown_system):
    """Test registering multiple triggers."""

    def cond1():
        return False

    def cond2():
        return False

    shutdown_system.register_shutdown_trigger(
        "trigger1", cond1, "CRITICAL", "First trigger"
    )
    shutdown_system.register_shutdown_trigger(
        "trigger2", cond2, "MEDIUM", "Second trigger"
    )

    assert len(shutdown_system.triggers) == 2


def test_check_conditions_not_met(shutdown_system):
    """Test checking conditions when none are met."""

    def always_false():
        return False

    shutdown_system.register_shutdown_trigger(
        "test", always_false, "HIGH", "Test", auto_trigger=True
    )

    triggered = shutdown_system.check_shutdown_conditions()

    assert triggered is None


def test_check_conditions_met(shutdown_system):
    """Test checking conditions when one is met."""

    def always_true():
        return True

    shutdown_system.register_shutdown_trigger(
        "test", always_true, "CRITICAL", "Test", auto_trigger=True
    )

    triggered = shutdown_system.check_shutdown_conditions()

    assert triggered == "test"


def test_check_conditions_met_auto_trigger_disabled(shutdown_system):
    """Test checking conditions with auto-trigger disabled."""

    def always_true():
        return True

    shutdown_system.register_shutdown_trigger(
        "test", always_true, "HIGH", "Test", auto_trigger=False
    )

    triggered = shutdown_system.check_shutdown_conditions()

    # Should not trigger because auto_trigger is False
    assert triggered is None


def test_check_conditions_exception_handling(shutdown_system):
    """Test condition check handles exceptions gracefully."""

    def raising_condition():
        raise Exception("Test error")

    shutdown_system.register_shutdown_trigger(
        "test", raising_condition, "HIGH", "Test", auto_trigger=True
    )

    # Should not raise, returns None
    triggered = shutdown_system.check_shutdown_conditions()
    assert triggered is None


@pytest.mark.asyncio
async def test_trigger_shutdown(shutdown_system):
    """Test triggering emergency shutdown."""
    await shutdown_system.trigger_emergency_shutdown(
        reason="Test shutdown", triggered_by="manual", severity="HIGH"
    )

    assert shutdown_system.is_shutdown_active() is True
    assert shutdown_system.shutdown_reason == "Test shutdown"
    assert shutdown_system.triggered_by == "manual"
    assert len(shutdown_system.shutdown_history) == 1


@pytest.mark.asyncio
async def test_trigger_shutdown_already_active(shutdown_system):
    """Test triggering shutdown when already active."""
    # First shutdown
    await shutdown_system.trigger_emergency_shutdown(
        reason="First", triggered_by="manual", severity="HIGH"
    )

    # Try second shutdown
    await shutdown_system.trigger_emergency_shutdown(
        reason="Second", triggered_by="manual", severity="HIGH"
    )

    # Should still have first shutdown
    assert shutdown_system.shutdown_reason == "First"
    # Should only have one event
    assert len(shutdown_system.shutdown_history) == 1


@pytest.mark.asyncio
async def test_trigger_shutdown_with_metrics(shutdown_system):
    """Test triggering shutdown with metrics."""
    metrics = {"daily_pnl": -500, "trades_today": 10}

    await shutdown_system.trigger_emergency_shutdown(
        reason="Loss limit",
        triggered_by="loss_tracker",
        severity="CRITICAL",
        metrics=metrics,
    )

    event = shutdown_system.shutdown_history[-1]
    assert event.metrics_at_shutdown == metrics


@pytest.mark.asyncio
async def test_trigger_shutdown_telegram_notification(shutdown_system, mock_telegram):
    """Test Telegram notification on shutdown."""
    await shutdown_system.trigger_emergency_shutdown(
        reason="Test", triggered_by="manual", severity="HIGH"
    )

    # Verify Telegram alert was sent
    mock_telegram.send_alert.assert_called_once()


@pytest.mark.asyncio
async def test_trigger_shutdown_no_telegram(mock_telegram):
    """Test shutdown without Telegram bot."""
    shutdown = EmergencyShutdown(telegram_bot=None)

    # Should not raise error
    await shutdown.trigger_emergency_shutdown(
        reason="Test", triggered_by="manual", severity="HIGH"
    )

    assert shutdown.is_shutdown_active() is True


def test_is_shutdown_active_false(shutdown_system):
    """Test checking shutdown status when not active."""
    assert shutdown_system.is_shutdown_active() is False


def test_is_shutdown_active_true(shutdown_system):
    """Test checking shutdown status when active."""
    shutdown_system.shutdown_active = True
    assert shutdown_system.is_shutdown_active() is True


def test_get_shutdown_status(shutdown_system):
    """Test getting shutdown status."""
    status = shutdown_system.get_shutdown_status()

    assert "active" in status
    assert "reason" in status
    assert "time" in status
    assert "triggered_by" in status
    assert "registered_triggers" in status
    assert "shutdown_count" in status
    assert status["active"] is False


def test_get_shutdown_status_active(shutdown_system):
    """Test getting shutdown status when active."""
    shutdown_system.shutdown_active = True
    shutdown_system.shutdown_reason = "Test"
    shutdown_system.shutdown_time = datetime.now()

    status = shutdown_system.get_shutdown_status()

    assert status["active"] is True
    assert status["reason"] == "Test"
    assert status["time"] is not None


def test_reset_shutdown_invalid_code(shutdown_system):
    """Test reset with invalid admin code."""
    shutdown_system.shutdown_active = True

    result = shutdown_system.reset_shutdown("WRONG_CODE")

    assert result is False
    assert shutdown_system.is_shutdown_active() is True


def test_reset_shutdown_valid_code(shutdown_system):
    """Test reset with valid admin code."""
    shutdown_system.shutdown_active = True
    shutdown_system.shutdown_reason = "Test"

    result = shutdown_system.reset_shutdown("TEST_CODE", "Resetting test")

    assert result is True
    assert shutdown_system.is_shutdown_active() is False
    assert shutdown_system.shutdown_reason is None


def test_reset_shutdown_not_active(shutdown_system):
    """Test reset when shutdown not active."""
    result = shutdown_system.reset_shutdown("TEST_CODE")

    assert result is False


def test_get_shutdown_history_empty(shutdown_system):
    """Test getting shutdown history when empty."""
    history = shutdown_system.get_shutdown_history()

    assert len(history) == 0


def test_get_shutdown_history_with_events(shutdown_system):
    """Test getting shutdown history with events."""
    # Add some events
    for i in range(5):
        shutdown_system.shutdown_history.append(
            ShutdownEvent(
                trigger_name=f"test{i}",
                reason=f"Test {i}",
                severity="HIGH",
                timestamp=datetime.now(),
                auto_triggered=True,
                metrics_at_shutdown={},
            )
        )

    history = shutdown_system.get_shutdown_history(limit=3)

    # Should return last 3
    assert len(history) == 3
    assert history[-1].trigger_name == "test4"


def test_get_shutdown_history_limit(shutdown_system):
    """Test shutdown history respects limit."""
    # Add 20 events
    for i in range(20):
        shutdown_system.shutdown_history.append(
            ShutdownEvent(
                trigger_name=f"test{i}",
                reason=f"Test {i}",
                severity="HIGH",
                timestamp=datetime.now(),
                auto_triggered=True,
                metrics_at_shutdown={},
            )
        )

    history = shutdown_system.get_shutdown_history(limit=10)

    assert len(history) == 10


@pytest.mark.asyncio
async def test_monitor_conditions_no_trigger(shutdown_system):
    """Test monitoring when no conditions are met."""

    def always_false():
        return False

    shutdown_system.register_shutdown_trigger("test", always_false, "HIGH", "Test")

    # Run one iteration
    task = asyncio.create_task(shutdown_system.monitor_conditions(check_interval=0.1))
    await asyncio.sleep(0.2)
    task.cancel()

    try:
        await task
    except asyncio.CancelledError:
        pass

    # Should not trigger shutdown
    assert shutdown_system.is_shutdown_active() is False


def test_create_loss_limit_trigger():
    """Test creating loss limit trigger."""
    mock_loss_tracker = Mock()
    mock_loss_tracker.check_loss_limit.return_value = (False, "Limit exceeded")

    trigger = create_loss_limit_trigger(mock_loss_tracker)

    # Trigger should return True when limit exceeded
    assert trigger() is True


def test_create_loss_limit_trigger_ok():
    """Test loss limit trigger when OK."""
    mock_loss_tracker = Mock()
    mock_loss_tracker.check_loss_limit.return_value = (True, "OK")

    trigger = create_loss_limit_trigger(mock_loss_tracker)

    # Trigger should return False when within limits
    assert trigger() is False


def test_create_circuit_breaker_trigger():
    """Test creating circuit breaker trigger."""
    mock_circuit_breaker = Mock()
    mock_circuit_breaker.is_trading_allowed.return_value = (
        False,
        "Circuit breaker active",
    )

    trigger = create_circuit_breaker_trigger(mock_circuit_breaker)

    # Trigger should return True when trading not allowed
    assert trigger() is True


def test_create_circuit_breaker_trigger_ok():
    """Test circuit breaker trigger when OK."""
    mock_circuit_breaker = Mock()
    mock_circuit_breaker.is_trading_allowed.return_value = (True, "OK")

    trigger = create_circuit_breaker_trigger(mock_circuit_breaker)

    # Trigger should return False when trading allowed
    assert trigger() is False


def test_save_shutdown_log(shutdown_system, tmp_path):
    """Test saving shutdown log to file."""
    event = ShutdownEvent(
        trigger_name="test",
        reason="Test shutdown",
        severity="HIGH",
        timestamp=datetime.now(),
        auto_triggered=False,
        metrics_at_shutdown={"test": "value"},
    )

    # Mock to use temp path
    with patch("builtins.open", create=True):
        shutdown_system._save_shutdown_log(event)

    # If no exception raised, test passes


def test_shutdown_trigger_dataclass():
    """Test ShutdownTrigger dataclass."""

    def test_cond():
        return True

    trigger = ShutdownTrigger(
        name="test",
        condition=test_cond,
        severity="HIGH",
        description="Test",
        auto_trigger=True,
    )

    assert trigger.name == "test"
    assert trigger.severity == "HIGH"
    assert trigger.auto_trigger is True
    assert trigger.condition() is True


def test_shutdown_event_dataclass():
    """Test ShutdownEvent dataclass."""
    now = datetime.now()
    event = ShutdownEvent(
        trigger_name="test",
        reason="Test reason",
        severity="CRITICAL",
        timestamp=now,
        auto_triggered=True,
        metrics_at_shutdown={"key": "value"},
    )

    assert event.trigger_name == "test"
    assert event.reason == "Test reason"
    assert event.severity == "CRITICAL"
    assert event.timestamp == now
    assert event.auto_triggered is True
    assert event.metrics_at_shutdown == {"key": "value"}
