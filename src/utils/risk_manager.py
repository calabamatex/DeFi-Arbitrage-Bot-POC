"""
Risk Management System - Protects capital with multiple safety mechanisms.
"""

import os
from decimal import Decimal
from typing import Tuple, Dict, Optional, List
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from web3 import Web3
import json
import logging
import asyncio


logger = logging.getLogger(__name__)


@dataclass
class TradeResult:
    """Result of a trade execution."""

    success: bool
    timestamp: datetime
    profit_loss: Decimal
    token_pair: str
    buy_dex: str
    sell_dex: str
    amount: Decimal
    gas_cost: Decimal
    message: str


@dataclass
class RiskMetrics:
    """Current risk metrics."""

    daily_pnl: Decimal
    weekly_pnl: Decimal
    total_trades_today: int
    successful_trades_today: int
    consecutive_losses: int
    total_exposure: Decimal
    largest_position: Decimal
    circuit_breaker_active: bool
    trading_allowed: bool
    last_trade_time: Optional[datetime]


class BalanceValidator:
    """Validates account has sufficient balance before trading."""

    def __init__(self, web3: Web3, erc20_abi: list):
        """
        Initialize balance validator.

        Args:
            web3: Web3 instance
            erc20_abi: ERC20 ABI for token contracts
        """
        self.web3 = web3
        self.erc20_abi = erc20_abi
        self.reserved_balances: Dict[str, Decimal] = {}  # Track reserved amounts

        logger.info("BalanceValidator initialized")

    async def check_balance(
        self, account: str, token_address: str, amount: Decimal, reserve: bool = True
    ) -> bool:
        """
        Check if account has sufficient balance.

        Args:
            account: Account address
            token_address: Token contract address
            amount: Required amount
            reserve: Whether to reserve this amount

        Returns:
            True if sufficient balance available
        """
        try:
            available = await self.get_available_balance(account, token_address)

            sufficient = available >= amount

            if sufficient and reserve:
                self.reserve_balance(account, token_address, amount)

            logger.debug(
                f"Balance check: {token_address} - "
                f"Available: {available:.6f}, Required: {amount:.6f}, "
                f"Sufficient: {sufficient}"
            )

            return sufficient

        except Exception as e:
            logger.error(f"Error checking balance: {e}")
            return False

    async def get_available_balance(self, account: str, token_address: str) -> Decimal:
        """
        Get available (unreserved) balance.

        Args:
            account: Account address
            token_address: Token address

        Returns:
            Available balance
        """
        # Get total balance
        checksum_address = Web3.to_checksum_address(token_address)
        token_contract = self.web3.eth.contract(
            address=checksum_address, abi=self.erc20_abi
        )

        balance_wei = token_contract.functions.balanceOf(account).call()
        # Detect token decimals dynamically
        try:
            decimals = token_contract.functions.decimals().call()
        except Exception:
            decimals = 18  # Default to 18 if call fails
        total_balance = Decimal(balance_wei) / Decimal(10**decimals)

        # Subtract reserved amount
        key = f"{account}_{token_address}"
        reserved = self.reserved_balances.get(key, Decimal("0"))

        available = total_balance - reserved

        result = max(available, Decimal("0"))
        return Decimal(str(result))

    def reserve_balance(self, account: str, token_address: str, amount: Decimal):
        """
        Reserve balance for pending trade.

        Args:
            account: Account address
            token_address: Token address
            amount: Amount to reserve
        """
        key = f"{account}_{token_address}"

        if key in self.reserved_balances:
            self.reserved_balances[key] += amount
        else:
            self.reserved_balances[key] = amount

        logger.debug(f"Reserved {amount} of {token_address}")

    def release_balance(self, account: str, token_address: str, amount: Decimal):
        """
        Release reserved balance.

        Args:
            account: Account address
            token_address: Token address
            amount: Amount to release
        """
        key = f"{account}_{token_address}"

        if key in self.reserved_balances:
            self.reserved_balances[key] -= amount
            if self.reserved_balances[key] <= 0:
                del self.reserved_balances[key]

        logger.debug(f"Released {amount} of {token_address}")


class PositionManager:
    """Manages position sizes and exposure limits."""

    def __init__(
        self,
        max_position_size_usd: Decimal,
        max_total_exposure_usd: Decimal,
        max_concentration_percent: Decimal = Decimal("0.30"),
    ):
        """
        Initialize position manager.

        Args:
            max_position_size_usd: Maximum single position size
            max_total_exposure_usd: Maximum total exposure
            max_concentration_percent: Max % of portfolio in single token (default 30%)
        """
        self.max_position_size = max_position_size_usd
        self.max_total_exposure = max_total_exposure_usd
        self.max_concentration = max_concentration_percent

        self.open_positions: Dict[str, Decimal] = {}  # Track open positions by token

        logger.info(
            f"PositionManager initialized: max_position=${max_position_size_usd}, "
            f"max_exposure=${max_total_exposure_usd}"
        )

    def validate_position_size(self, amount_usd: Decimal) -> Tuple[bool, str]:
        """
        Validate position size is within limits.

        Args:
            amount_usd: Position size in USD

        Returns:
            Tuple of (valid: bool, message: str)
        """
        if amount_usd > self.max_position_size:
            return (
                False,
                f"Position size ${amount_usd} exceeds max ${self.max_position_size}",
            )

        return True, "Position size OK"

    def track_open_position(self, token: str, amount_usd: Decimal):
        """
        Track an open position.

        Args:
            token: Token symbol
            amount_usd: Position size in USD
        """
        if token in self.open_positions:
            self.open_positions[token] += amount_usd
        else:
            self.open_positions[token] = amount_usd

        logger.debug(f"Tracking position: {token} = ${self.open_positions[token]}")

    def close_position(self, token: str):
        """
        Close a position.

        Args:
            token: Token symbol
        """
        if token in self.open_positions:
            del self.open_positions[token]
            logger.debug(f"Closed position: {token}")

    def get_total_exposure(self) -> Decimal:
        """
        Get total exposure across all positions.

        Returns:
            Total exposure in USD
        """
        total = sum(self.open_positions.values())
        return Decimal(str(total)) if total else Decimal("0")

    def check_exposure_limit(self) -> Tuple[bool, str]:
        """
        Check if total exposure is within limit.

        Returns:
            Tuple of (within_limit: bool, message: str)
        """
        total = self.get_total_exposure()

        if total > self.max_total_exposure:
            return (
                False,
                f"Total exposure ${total} exceeds max ${self.max_total_exposure}",
            )

        return True, "Exposure OK"

    def check_concentration_risk(
        self, token: str, amount_usd: Decimal
    ) -> Tuple[bool, str]:
        """
        Check if adding position would exceed concentration limit.

        Args:
            token: Token symbol
            amount_usd: Position size to add

        Returns:
            Tuple of (ok: bool, message: str)
        """
        total_exposure = self.get_total_exposure() + amount_usd

        if total_exposure == 0:
            return True, "No exposure"

        token_exposure = self.open_positions.get(token, Decimal("0")) + amount_usd
        concentration = token_exposure / total_exposure

        if concentration > self.max_concentration:
            return (
                False,
                f"Token concentration {concentration:.1%} exceeds max {self.max_concentration:.1%}",
            )

        return True, "Concentration OK"


class LossTracker:
    """Tracks profit/loss over time."""

    def __init__(
        self,
        daily_loss_limit_usd: Decimal,
        weekly_loss_limit_usd: Optional[Decimal] = None,
    ):
        """
        Initialize loss tracker.

        Args:
            daily_loss_limit_usd: Maximum loss per day
            weekly_loss_limit_usd: Maximum loss per week (optional)
        """
        self.daily_loss_limit = daily_loss_limit_usd
        self.weekly_loss_limit = weekly_loss_limit_usd or (daily_loss_limit_usd * 5)

        self.trades: List[TradeResult] = []  # List of TradeResult objects

        logger.info(
            f"LossTracker initialized: daily_limit=${daily_loss_limit_usd}, "
            f"weekly_limit=${self.weekly_loss_limit}"
        )

    def record_trade(self, trade_result: TradeResult):
        """
        Record a trade result.

        Args:
            trade_result: TradeResult object
        """
        self.trades.append(trade_result)

        logger.info(
            f"Recorded trade: {trade_result.token_pair} - "
            f"P/L: ${trade_result.profit_loss:.2f}"
        )

    def get_daily_pnl(self) -> Decimal:
        """
        Get profit/loss for current day.

        Returns:
            Daily P/L
        """
        today = datetime.now().date()

        daily_pnl = sum(
            trade.profit_loss
            for trade in self.trades
            if trade.timestamp.date() == today
        )

        return Decimal(str(daily_pnl)) if daily_pnl else Decimal("0")

    def get_weekly_pnl(self) -> Decimal:
        """
        Get profit/loss for current week.

        Returns:
            Weekly P/L
        """
        week_ago = datetime.now() - timedelta(days=7)

        weekly_pnl = sum(
            trade.profit_loss for trade in self.trades if trade.timestamp >= week_ago
        )

        return Decimal(str(weekly_pnl)) if weekly_pnl else Decimal("0")

    def check_loss_limit(self) -> Tuple[bool, str]:
        """
        Check if loss limits have been exceeded.

        Returns:
            Tuple of (ok: bool, message: str)
        """
        daily_pnl = self.get_daily_pnl()
        weekly_pnl = self.get_weekly_pnl()

        # Check daily limit
        if daily_pnl < -self.daily_loss_limit:
            return (
                False,
                f"Daily loss ${abs(daily_pnl):.2f} exceeds limit ${self.daily_loss_limit}",
            )

        # Check weekly limit
        if weekly_pnl < -self.weekly_loss_limit:
            return (
                False,
                f"Weekly loss ${abs(weekly_pnl):.2f} exceeds limit ${self.weekly_loss_limit}",
            )

        return True, "Within loss limits"

    def reset_daily(self):
        """Reset daily tracking (call at midnight)."""
        # Remove trades older than 7 days
        week_ago = datetime.now() - timedelta(days=7)
        self.trades = [t for t in self.trades if t.timestamp >= week_ago]

        logger.info("Daily reset complete")

    def get_trade_count_today(self) -> int:
        """Get number of trades today."""
        today = datetime.now().date()
        return len([t for t in self.trades if t.timestamp.date() == today])

    def get_success_rate_today(self) -> Decimal:
        """Get success rate for today."""
        today = datetime.now().date()
        today_trades = [t for t in self.trades if t.timestamp.date() == today]

        if not today_trades:
            return Decimal("100")  # No trades = 100% to not block trading

        successful = len([t for t in today_trades if t.success])
        return Decimal(successful) / Decimal(len(today_trades)) * 100


class CircuitBreaker:
    """Implements circuit breaker for consecutive losses."""

    def __init__(self, max_consecutive_losses: int = 5, cooldown_minutes: int = 60):
        """
        Initialize circuit breaker.

        Args:
            max_consecutive_losses: Losses before triggering
            cooldown_minutes: Cooldown period in minutes
        """
        self.max_consecutive_losses = max_consecutive_losses
        self.cooldown_period = timedelta(minutes=cooldown_minutes)

        self.consecutive_losses = 0
        self.is_active = False
        self.triggered_at: Optional[datetime] = None

        logger.info(
            f"CircuitBreaker initialized: max_losses={max_consecutive_losses}, "
            f"cooldown={cooldown_minutes}min"
        )

    def record_trade_result(self, success: bool):
        """
        Record trade result.

        Args:
            success: Whether trade succeeded
        """
        if success:
            self.consecutive_losses = 0
            logger.debug("Trade successful, reset consecutive losses")
        else:
            self.consecutive_losses += 1
            logger.warning(
                f"Trade failed, consecutive losses: {self.consecutive_losses}"
            )

            # Check if should trigger
            if self.consecutive_losses >= self.max_consecutive_losses:
                self.trigger()

    def trigger(self):
        """Trigger circuit breaker."""
        self.is_active = True
        self.triggered_at = datetime.now()

        logger.error(
            f"🚨 CIRCUIT BREAKER TRIGGERED! "
            f"{self.consecutive_losses} consecutive losses. "
            f"Trading paused for {self.cooldown_period.total_seconds()/60:.0f} minutes"
        )

    def is_trading_allowed(self) -> Tuple[bool, str]:
        """
        Check if trading is allowed.

        Returns:
            Tuple of (allowed: bool, message: str)
        """
        if not self.is_active:
            return True, "Circuit breaker inactive"

        # Check if cooldown period has passed
        if self.triggered_at:
            cooldown_end = self.triggered_at + self.cooldown_period

            if datetime.now() >= cooldown_end:
                self.reset()
                return True, "Cooldown period ended, circuit breaker reset"
            else:
                time_remaining = cooldown_end - datetime.now()
                return (
                    False,
                    f"Circuit breaker active, {time_remaining.total_seconds()/60:.1f}min remaining",
                )

        return False, "Circuit breaker active"

    def reset(self):
        """Reset circuit breaker."""
        self.is_active = False
        self.consecutive_losses = 0
        self.triggered_at = None

        logger.info("Circuit breaker reset")

    def get_status(self) -> Dict:
        """
        Get circuit breaker status.

        Returns:
            Status dictionary
        """
        return {
            "active": self.is_active,
            "consecutive_losses": self.consecutive_losses,
            "max_losses": self.max_consecutive_losses,
            "triggered_at": self.triggered_at.isoformat()
            if self.triggered_at
            else None,
        }


class RiskManager:
    """
    Coordinates all risk management components.

    This is the main class that other parts of the system interact with.
    """

    # Default state file path
    DEFAULT_STATE_FILE = "risk_state.json"

    def __init__(self, web3: Web3, erc20_abi: list, config: Dict):
        """
        Initialize risk manager.

        Args:
            web3: Web3 instance
            erc20_abi: ERC20 ABI
            config: Configuration with risk parameters
        """
        self.web3 = web3
        self.state_file = Path(
            os.getenv("RISK_STATE_FILE", self.DEFAULT_STATE_FILE)
        )

        # Initialize sub-components
        self.balance_validator = BalanceValidator(web3, erc20_abi)

        self.position_manager = PositionManager(
            max_position_size_usd=Decimal(
                str(config.get("MAX_POSITION_SIZE_USD", 10000))
            ),
            max_total_exposure_usd=Decimal(
                str(config.get("MAX_TOTAL_EXPOSURE_USD", 50000))
            ),
            max_concentration_percent=Decimal(
                str(config.get("MAX_CONCENTRATION", 0.30))
            ),
        )

        self.loss_tracker = LossTracker(
            daily_loss_limit_usd=Decimal(str(config.get("DAILY_LOSS_LIMIT_USD", 1000))),
            weekly_loss_limit_usd=Decimal(
                str(config.get("WEEKLY_LOSS_LIMIT_USD", 5000))
            ),
        )

        self.circuit_breaker = CircuitBreaker(
            max_consecutive_losses=config.get("MAX_CONSECUTIVE_LOSSES", 5),
            cooldown_minutes=config.get("CIRCUIT_BREAKER_COOLDOWN_MIN", 60),
        )

        self.shutdown_active = False
        self.shutdown_reason: Optional[str] = None

        # Restore state from disk if available
        self._load_state()

        logger.info("RiskManager initialized with all components")

    def validate_trade(
        self, opportunity: Dict, account: str, token_address: str
    ) -> Tuple[bool, str]:
        """
        Validate trade against all risk checks (synchronous).

        Args:
            opportunity: Opportunity dict with keys: token_in, token_out, amount_in, net_profit
            account: Trading account address
            token_address: Token contract address

        Returns:
            Tuple of (approved: bool, reason: str)
        """
        token_in = opportunity.get('token_in', 'unknown')[:10]
        token_out = opportunity.get('token_out', 'unknown')[:10]
        logger.info(f"Validating trade: {token_in}/{token_out}")

        # 1. Check if emergency shutdown active
        if self.shutdown_active:
            return False, f"Emergency shutdown active: {self.shutdown_reason}"

        # 2. Check circuit breaker
        allowed, msg = self.circuit_breaker.is_trading_allowed()
        if not allowed:
            return False, msg

        # 3. Check position size (use amount_in as proxy for USD exposure)
        token_decimals = opportunity.get('token_decimals', 6)
        amount_usd = Decimal(str(opportunity.get('amount_in', 0))) / Decimal(10**token_decimals)
        valid_size, size_msg = self.position_manager.validate_position_size(amount_usd)
        if not valid_size:
            return False, size_msg

        # 4. Check total exposure
        within_exposure, exposure_msg = self.position_manager.check_exposure_limit()
        if not within_exposure:
            return False, exposure_msg

        # 5. Check loss limits
        within_limits, limit_msg = self.loss_tracker.check_loss_limit()
        if not within_limits:
            return False, limit_msg

        logger.info("Trade approved by risk manager")
        return True, "All risk checks passed"

    def record_trade_result(self, trade_result: TradeResult):
        """
        Record trade result in all relevant trackers and persist to disk.

        Args:
            trade_result: TradeResult object
        """
        # Record in loss tracker
        self.loss_tracker.record_trade(trade_result)

        # Record in circuit breaker
        self.circuit_breaker.record_trade_result(trade_result.success)

        # Update positions
        if trade_result.success:
            self.position_manager.close_position(trade_result.token_pair.split("/")[0])

        # Persist state after every trade so it survives restarts
        self._save_state()

        logger.info(f"Trade result recorded: {trade_result.success}")

    def get_risk_metrics(self) -> RiskMetrics:
        """
        Get current risk metrics.

        Returns:
            RiskMetrics object
        """
        return RiskMetrics(
            daily_pnl=self.loss_tracker.get_daily_pnl(),
            weekly_pnl=self.loss_tracker.get_weekly_pnl(),
            total_trades_today=self.loss_tracker.get_trade_count_today(),
            successful_trades_today=int(
                self.loss_tracker.get_success_rate_today()
                * self.loss_tracker.get_trade_count_today()
                / 100
            ),
            consecutive_losses=self.circuit_breaker.consecutive_losses,
            total_exposure=self.position_manager.get_total_exposure(),
            largest_position=max(
                self.position_manager.open_positions.values(), default=Decimal("0")
            ),
            circuit_breaker_active=self.circuit_breaker.is_active,
            trading_allowed=not self.shutdown_active,
            last_trade_time=self.loss_tracker.trades[-1].timestamp
            if self.loss_tracker.trades
            else None,
        )

    def emergency_shutdown(self, reason: str):
        """
        Trigger emergency shutdown.

        Args:
            reason: Reason for shutdown
        """
        self.shutdown_active = True
        self.shutdown_reason = reason
        self._save_state()

        logger.critical(f"🚨 EMERGENCY SHUTDOWN: {reason}")

    def reset_shutdown(self, admin_code: str) -> bool:
        """
        Reset emergency shutdown (requires admin code).

        Args:
            admin_code: Admin verification code from ADMIN_RESET_CODE env var

        Returns:
            True if reset successful
        """
        import os
        import hmac

        expected_code = os.environ.get("ADMIN_RESET_CODE", "")
        if not expected_code:
            logger.error("ADMIN_RESET_CODE env var not set -- cannot reset shutdown")
            return False

        if hmac.compare_digest(admin_code, expected_code):
            self.shutdown_active = False
            self.shutdown_reason = None
            logger.info("Emergency shutdown reset by admin")
            return True

        logger.warning("Invalid admin code for shutdown reset")
        return False

    def _save_state(self):
        """Persist critical risk state to disk so it survives restarts."""
        try:
            # Serialize recent trades (last 7 days only)
            week_ago = datetime.now() - timedelta(days=7)
            trade_dicts = []
            for t in self.loss_tracker.trades:
                if t.timestamp >= week_ago:
                    trade_dicts.append({
                        'success': t.success,
                        'timestamp': t.timestamp.isoformat(),
                        'profit_loss': str(t.profit_loss),
                        'token_pair': t.token_pair,
                        'buy_dex': t.buy_dex,
                        'sell_dex': t.sell_dex,
                        'amount': str(t.amount),
                        'gas_cost': str(t.gas_cost),
                        'message': t.message,
                    })

            state = {
                'version': 1,
                'saved_at': datetime.now().isoformat(),
                'circuit_breaker': {
                    'consecutive_losses': self.circuit_breaker.consecutive_losses,
                    'is_active': self.circuit_breaker.is_active,
                    'triggered_at': self.circuit_breaker.triggered_at.isoformat()
                    if self.circuit_breaker.triggered_at else None,
                },
                'shutdown': {
                    'active': self.shutdown_active,
                    'reason': self.shutdown_reason,
                },
                'trades': trade_dicts,
            }

            # Atomic write: write to temp file then rename
            tmp_path = self.state_file.with_suffix('.tmp')
            with open(tmp_path, 'w') as f:
                json.dump(state, f, indent=2)
            tmp_path.replace(self.state_file)

            logger.debug(f"Risk state saved ({len(trade_dicts)} trades)")

        except Exception as e:
            logger.warning(f"Failed to save risk state: {e}")

    def _load_state(self):
        """Restore risk state from disk on startup."""
        if not self.state_file.exists():
            logger.info("No previous risk state found, starting fresh")
            return

        try:
            with open(self.state_file, 'r') as f:
                state = json.load(f)

            # Restore circuit breaker
            cb = state.get('circuit_breaker', {})
            self.circuit_breaker.consecutive_losses = cb.get('consecutive_losses', 0)
            self.circuit_breaker.is_active = cb.get('is_active', False)
            if cb.get('triggered_at'):
                self.circuit_breaker.triggered_at = datetime.fromisoformat(cb['triggered_at'])

            # Restore shutdown state
            sd = state.get('shutdown', {})
            self.shutdown_active = sd.get('active', False)
            self.shutdown_reason = sd.get('reason')

            # Restore trade history
            for td in state.get('trades', []):
                trade = TradeResult(
                    success=td['success'],
                    timestamp=datetime.fromisoformat(td['timestamp']),
                    profit_loss=Decimal(td['profit_loss']),
                    token_pair=td['token_pair'],
                    buy_dex=td['buy_dex'],
                    sell_dex=td['sell_dex'],
                    amount=Decimal(td['amount']),
                    gas_cost=Decimal(td['gas_cost']),
                    message=td['message'],
                )
                self.loss_tracker.trades.append(trade)

            saved_at = state.get('saved_at', 'unknown')
            logger.info(
                f"Risk state restored from {self.state_file} "
                f"(saved={saved_at}, trades={len(self.loss_tracker.trades)}, "
                f"circuit_breaker={'ACTIVE' if self.circuit_breaker.is_active else 'ok'})"
            )

            if self.shutdown_active:
                logger.warning(f"Emergency shutdown was active: {self.shutdown_reason}")

        except Exception as e:
            logger.warning(f"Failed to load risk state (starting fresh): {e}")
