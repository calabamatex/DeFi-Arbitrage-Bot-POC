"""
Emergency Shutdown System - Last line of defense to protect capital.
"""

from typing import Callable, Dict, Optional, List
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import logging
import asyncio

logger = logging.getLogger(__name__)


@dataclass
class ShutdownTrigger:
    """Configuration for an automatic shutdown trigger."""

    name: str
    condition: Callable[[], bool]
    severity: str  # CRITICAL, HIGH, MEDIUM
    description: str
    auto_trigger: bool


@dataclass
class ShutdownEvent:
    """Record of a shutdown event."""

    trigger_name: str
    reason: str
    severity: str
    timestamp: datetime
    auto_triggered: bool
    metrics_at_shutdown: Dict


class EmergencyShutdown:
    """
    Emergency shutdown system with automatic triggers and manual controls.

    Shutdown can be triggered by:
    1. Automatic conditions (circuit breakers, loss limits, etc.)
    2. Manual admin command
    3. External signals (abnormal market conditions)
    """

    def __init__(self, telegram_bot=None, admin_code: str = None):
        """
        Initialize emergency shutdown system.

        Args:
            telegram_bot: TelegramBot instance for notifications
            admin_code: Code required to reset shutdown
        """
        import os

        self.telegram_bot = telegram_bot
        self.admin_code = admin_code or os.environ.get("ADMIN_RESET_CODE", "")

        self.shutdown_active = False
        self.shutdown_reason: Optional[str] = None
        self.shutdown_time: Optional[datetime] = None
        self.triggered_by: Optional[str] = None

        self.triggers: Dict[str, ShutdownTrigger] = {}  # Registered triggers
        self.shutdown_history: List[ShutdownEvent] = []  # List of ShutdownEvent

        # Register default triggers
        self._register_default_triggers()

        logger.info("EmergencyShutdown system initialized")

    def _register_default_triggers(self):
        """Register default shutdown triggers."""
        # These would be connected to actual conditions in production
        # For now, they're placeholders

        logger.info("Default shutdown triggers registered")

    def register_shutdown_trigger(
        self,
        trigger_name: str,
        condition: Callable[[], bool],
        severity: str,
        description: str,
        auto_trigger: bool = True,
    ):
        """
        Register an automatic shutdown trigger.

        Args:
            trigger_name: Unique name for trigger
            condition: Callable that returns True when should shutdown
            severity: CRITICAL, HIGH, or MEDIUM
            description: Human-readable description
            auto_trigger: Whether to automatically trigger shutdown
        """
        trigger = ShutdownTrigger(
            name=trigger_name,
            condition=condition,
            severity=severity,
            description=description,
            auto_trigger=auto_trigger,
        )

        self.triggers[trigger_name] = trigger

        logger.info(
            f"Registered shutdown trigger: {trigger_name} "
            f"(severity: {severity}, auto: {auto_trigger})"
        )

    def check_shutdown_conditions(self) -> Optional[str]:
        """
        Check all registered shutdown triggers.

        Returns:
            Trigger name if any condition met, None otherwise
        """
        for trigger_name, trigger in self.triggers.items():
            try:
                # Check condition
                if trigger.condition():
                    logger.warning(
                        f"Shutdown trigger activated: {trigger_name} - "
                        f"{trigger.description}"
                    )

                    if trigger.auto_trigger:
                        return trigger_name
                    else:
                        logger.warning(
                            f"Trigger {trigger_name} activated but auto-trigger disabled"
                        )

            except Exception as e:
                logger.error(f"Error checking trigger {trigger_name}: {e}")

        return None

    async def trigger_emergency_shutdown(
        self,
        reason: str,
        triggered_by: str = "manual",
        severity: str = "HIGH",
        metrics: Optional[Dict] = None,
    ):
        """
        Trigger emergency shutdown.

        Args:
            reason: Reason for shutdown
            triggered_by: What/who triggered it
            severity: Severity level
            metrics: Current system metrics
        """
        if self.shutdown_active:
            logger.warning("Emergency shutdown already active")
            return

        self.shutdown_active = True
        self.shutdown_reason = reason
        self.shutdown_time = datetime.now()
        self.triggered_by = triggered_by

        # Record event
        event = ShutdownEvent(
            trigger_name=triggered_by,
            reason=reason,
            severity=severity,
            timestamp=self.shutdown_time,
            auto_triggered=(triggered_by != "manual"),
            metrics_at_shutdown=metrics or {},
        )
        self.shutdown_history.append(event)

        # Log
        logger.critical(
            f"🚨 EMERGENCY SHUTDOWN TRIGGERED 🚨\n"
            f"Reason: {reason}\n"
            f"Triggered by: {triggered_by}\n"
            f"Severity: {severity}\n"
            f"Time: {self.shutdown_time}"
        )

        # Send Telegram alert
        if self.telegram_bot:
            await self._send_shutdown_alert(reason, severity, metrics)

        # Save to file
        self._save_shutdown_log(event)

    async def _send_shutdown_alert(
        self, reason: str, severity: str, metrics: Optional[Dict]
    ):
        """
        Send Telegram alert for shutdown.

        Args:
            reason: Shutdown reason
            severity: Severity level
            metrics: System metrics
        """
        try:
            alert_message = (
                f"🚨 *EMERGENCY SHUTDOWN* 🚨\n\n"
                f"*Severity:* {severity}\n"
                f"*Reason:* {reason}\n"
                f"*Time:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            )

            if metrics:
                alert_message += "*Metrics at shutdown:*\n"
                for key, value in metrics.items():
                    alert_message += f"• {key}: {value}\n"

            alert_message += "\n⚠️ *All trading stopped*"

            await self.telegram_bot.send_alert(
                "Emergency Shutdown", alert_message, severity="CRITICAL"
            )

        except Exception as e:
            logger.error(f"Failed to send shutdown alert: {e}")

    def _save_shutdown_log(self, event: ShutdownEvent):
        """
        Save shutdown event to log file.

        Args:
            event: ShutdownEvent to log
        """
        try:
            log_entry = (
                f"\n{'='*60}\n"
                f"EMERGENCY SHUTDOWN\n"
                f"{'='*60}\n"
                f"Timestamp: {event.timestamp}\n"
                f"Trigger: {event.trigger_name}\n"
                f"Reason: {event.reason}\n"
                f"Severity: {event.severity}\n"
                f"Auto-triggered: {event.auto_triggered}\n"
            )

            if event.metrics_at_shutdown:
                log_entry += "\nMetrics:\n"
                for key, value in event.metrics_at_shutdown.items():
                    log_entry += f"  {key}: {value}\n"

            log_entry += f"{'='*60}\n"

            with open("emergency_shutdown.log", "a") as f:
                f.write(log_entry)

        except Exception as e:
            logger.error(f"Failed to save shutdown log: {e}")

    def is_shutdown_active(self) -> bool:
        """
        Check if shutdown is currently active.

        Returns:
            True if shutdown active
        """
        return self.shutdown_active

    def get_shutdown_status(self) -> Dict:
        """
        Get current shutdown status.

        Returns:
            Status dictionary
        """
        return {
            "active": self.shutdown_active,
            "reason": self.shutdown_reason,
            "time": self.shutdown_time.isoformat() if self.shutdown_time else None,
            "triggered_by": self.triggered_by,
            "registered_triggers": len(self.triggers),
            "shutdown_count": len(self.shutdown_history),
        }

    def reset_shutdown(self, admin_code: str, reason: str = "") -> bool:
        """
        Reset shutdown (requires admin code).

        Args:
            admin_code: Admin verification code
            reason: Reason for reset

        Returns:
            True if reset successful
        """
        import hmac

        if not self.admin_code:
            logger.error("No admin code configured -- cannot reset shutdown")
            return False

        if not hmac.compare_digest(admin_code, self.admin_code):
            logger.warning("Invalid admin code for shutdown reset")
            return False

        if not self.shutdown_active:
            logger.info("No active shutdown to reset")
            return False

        # Reset
        self.shutdown_active = False
        old_reason = self.shutdown_reason
        self.shutdown_reason = None
        self.shutdown_time = None
        self.triggered_by = None

        logger.warning(
            f"Emergency shutdown reset by admin\n"
            f"Previous reason: {old_reason}\n"
            f"Reset reason: {reason}"
        )

        return True

    def get_shutdown_history(self, limit: int = 10) -> List[ShutdownEvent]:
        """
        Get shutdown history.

        Args:
            limit: Maximum number of events to return

        Returns:
            List of recent ShutdownEvent objects
        """
        return self.shutdown_history[-limit:]

    async def monitor_conditions(self, check_interval: int = 60):
        """
        Continuously monitor shutdown conditions.

        Args:
            check_interval: Seconds between checks
        """
        logger.info(
            f"Starting shutdown condition monitoring (interval: {check_interval}s)"
        )

        while True:
            try:
                # Check if already shutdown
                if self.shutdown_active:
                    await asyncio.sleep(check_interval)
                    continue

                # Check all conditions
                triggered = self.check_shutdown_conditions()

                if triggered:
                    trigger = self.triggers[triggered]
                    await self.trigger_emergency_shutdown(
                        reason=trigger.description,
                        triggered_by=triggered,
                        severity=trigger.severity,
                    )

                await asyncio.sleep(check_interval)

            except Exception as e:
                logger.error(f"Error in shutdown monitoring: {e}")
                await asyncio.sleep(check_interval)


# Pre-defined shutdown conditions


def create_loss_limit_trigger(
    loss_tracker, limit_name: str = "daily"
) -> Callable[[], bool]:
    """
    Create a shutdown trigger for loss limits.

    Args:
        loss_tracker: LossTracker instance
        limit_name: "daily" or "weekly"

    Returns:
        Condition function
    """

    def check_loss_limit():
        ok, msg = loss_tracker.check_loss_limit()
        return not ok

    return check_loss_limit


def create_circuit_breaker_trigger(circuit_breaker) -> Callable[[], bool]:
    """
    Create a shutdown trigger for circuit breaker.

    Args:
        circuit_breaker: CircuitBreaker instance

    Returns:
        Condition function
    """

    def check_circuit_breaker():
        allowed, msg = circuit_breaker.is_trading_allowed()
        return not allowed

    return check_circuit_breaker


def create_balance_trigger(
    balance_validator, account: str, token_address: str, minimum_balance: Decimal
) -> Callable[[], bool]:
    """
    Create a shutdown trigger for minimum balance.

    Args:
        balance_validator: BalanceValidator instance
        account: Account address
        token_address: Token address
        minimum_balance: Minimum required balance

    Returns:
        Condition function
    """

    async def check_balance():
        balance = await balance_validator.get_available_balance(account, token_address)
        return balance < minimum_balance

    # For synchronous checking
    def sync_check():
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(check_balance())
        except:
            return False

    return sync_check
