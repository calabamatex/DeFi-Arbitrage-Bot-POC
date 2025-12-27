"""
Metrics collection and reporting system.
"""

import json
import time
from decimal import Decimal
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class BotMetrics:
    """Bot performance metrics."""

    timestamp: str
    uptime_seconds: float

    # Opportunity metrics
    opportunities_found: int
    opportunities_per_hour: float

    # Trade metrics
    trades_executed: int
    successful_trades: int
    failed_trades: int
    success_rate: float

    # Financial metrics
    total_profit_usd: float
    total_loss_usd: float
    net_profit_usd: float
    avg_profit_per_trade: float

    # Gas metrics
    total_gas_cost_usd: float
    avg_gas_per_trade: float

    # Performance metrics
    avg_detection_time_ms: float
    avg_execution_time_ms: float

    # System metrics
    rpc_calls_per_minute: int
    memory_usage_mb: float
    cpu_usage_percent: float

    # Risk metrics
    circuit_breaker_active: bool
    consecutive_losses: int
    daily_pnl: float

    # Error metrics
    error_count: int
    last_error_time: Optional[str]


class MetricsCollector:
    """Collects and exports bot metrics."""

    def __init__(self, bot_start_time: datetime):
        """
        Initialize metrics collector.

        Args:
            bot_start_time: When bot started
        """
        self.start_time = bot_start_time
        self.metrics_history = []

        # Counters
        self.opportunities_found = 0
        self.trades_executed = 0
        self.successful_trades = 0
        self.failed_trades = 0

        # Financial tracking
        self.profits = []  # List of profit amounts
        self.losses = []  # List of loss amounts
        self.gas_costs = []  # List of gas costs

        # Performance tracking
        self.detection_times = []
        self.execution_times = []

        # Errors
        self.errors = []
        self.last_error = None

        logger.info("MetricsCollector initialized")

    def record_opportunity(self):
        """Record an opportunity found."""
        self.opportunities_found += 1

    def record_trade(self, success: bool, profit_usd: Decimal, gas_cost_usd: Decimal):
        """
        Record a trade execution.

        Args:
            success: Whether trade succeeded
            profit_usd: Profit/loss amount
            gas_cost_usd: Gas cost
        """
        self.trades_executed += 1

        if success:
            self.successful_trades += 1
            if profit_usd > 0:
                self.profits.append(float(profit_usd))
            else:
                self.losses.append(float(abs(profit_usd)))
        else:
            self.failed_trades += 1
            # Failed trades are losses
            self.losses.append(float(gas_cost_usd))

        self.gas_costs.append(float(gas_cost_usd))

    def record_detection_time(self, milliseconds: float):
        """Record opportunity detection time."""
        self.detection_times.append(milliseconds)
        # Keep only last 100
        if len(self.detection_times) > 100:
            self.detection_times = self.detection_times[-100:]

    def record_execution_time(self, milliseconds: float):
        """Record trade execution time."""
        self.execution_times.append(milliseconds)
        if len(self.execution_times) > 100:
            self.execution_times = self.execution_times[-100:]

    def record_error(self, error: str):
        """Record an error."""
        self.errors.append({"timestamp": datetime.now().isoformat(), "error": error})
        self.last_error = datetime.now()

        # Keep only last 50 errors
        if len(self.errors) > 50:
            self.errors = self.errors[-50:]

    def collect_metrics(
        self, risk_manager=None, performance_monitor=None
    ) -> BotMetrics:
        """
        Collect current metrics snapshot.

        Args:
            risk_manager: RiskManager instance (optional)
            performance_monitor: PerformanceMonitor instance (optional)

        Returns:
            BotMetrics object
        """
        try:
            import psutil
            import os

            process = psutil.Process(os.getpid())
            memory_mb = process.memory_info().rss / 1024 / 1024
            cpu_percent = process.cpu_percent(interval=0.1)
        except ImportError:
            logger.warning("psutil not available, using fallback metrics")
            memory_mb = 0.0
            cpu_percent = 0.0
        except Exception as e:
            logger.error(f"Error getting system metrics: {e}")
            memory_mb = 0.0
            cpu_percent = 0.0

        # Calculate uptime
        uptime = (datetime.now() - self.start_time).total_seconds()
        hours = uptime / 3600

        # Calculate rates
        opp_per_hour = self.opportunities_found / max(hours, 0.01)

        # Calculate success rate
        if self.trades_executed > 0:
            success_rate = self.successful_trades / self.trades_executed
        else:
            success_rate = 0.0

        # Calculate financial metrics
        total_profit = sum(self.profits)
        total_loss = sum(self.losses)
        net_profit = total_profit - total_loss

        if self.trades_executed > 0:
            avg_profit = net_profit / self.trades_executed
        else:
            avg_profit = 0.0

        # Calculate gas metrics
        total_gas = sum(self.gas_costs)
        if self.trades_executed > 0:
            avg_gas = total_gas / self.trades_executed
        else:
            avg_gas = 0.0

        # Performance metrics
        if self.detection_times:
            avg_detection = sum(self.detection_times) / len(self.detection_times)
        else:
            avg_detection = 0.0

        if self.execution_times:
            avg_execution = sum(self.execution_times) / len(self.execution_times)
        else:
            avg_execution = 0.0

        # Risk metrics from risk manager
        if risk_manager:
            circuit_breaker_active = risk_manager.circuit_breaker.is_active
            consecutive_losses = risk_manager.circuit_breaker.consecutive_losses
            daily_pnl = float(risk_manager.loss_tracker.get_daily_pnl())
        else:
            circuit_breaker_active = False
            consecutive_losses = 0
            daily_pnl = net_profit

        # Performance metrics from monitor
        if performance_monitor:
            rpc_per_min = performance_monitor.rpc_call_count
        else:
            rpc_per_min = 0

        metrics = BotMetrics(
            timestamp=datetime.now().isoformat(),
            uptime_seconds=uptime,
            opportunities_found=self.opportunities_found,
            opportunities_per_hour=opp_per_hour,
            trades_executed=self.trades_executed,
            successful_trades=self.successful_trades,
            failed_trades=self.failed_trades,
            success_rate=success_rate,
            total_profit_usd=total_profit,
            total_loss_usd=total_loss,
            net_profit_usd=net_profit,
            avg_profit_per_trade=avg_profit,
            total_gas_cost_usd=total_gas,
            avg_gas_per_trade=avg_gas,
            avg_detection_time_ms=avg_detection,
            avg_execution_time_ms=avg_execution,
            rpc_calls_per_minute=rpc_per_min,
            memory_usage_mb=memory_mb,
            cpu_usage_percent=cpu_percent,
            circuit_breaker_active=circuit_breaker_active,
            consecutive_losses=consecutive_losses,
            daily_pnl=daily_pnl,
            error_count=len(self.errors),
            last_error_time=self.last_error.isoformat() if self.last_error else None,
        )

        # Store in history
        self.metrics_history.append(metrics)

        # Keep only last 1000 metrics
        if len(self.metrics_history) > 1000:
            self.metrics_history = self.metrics_history[-1000:]

        return metrics

    def export_metrics_json(self, filepath: str):
        """
        Export metrics to JSON file.

        Args:
            filepath: Output file path
        """
        data = {
            "export_time": datetime.now().isoformat(),
            "uptime_hours": (datetime.now() - self.start_time).total_seconds() / 3600,
            "current_metrics": (
                asdict(self.metrics_history[-1]) if self.metrics_history else None
            ),
            "metrics_history": [asdict(m) for m in self.metrics_history],
            "recent_errors": self.errors[-10:],
        }

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Metrics exported to {filepath}")

    def export_prometheus(self, filepath: str):
        """
        Export metrics in Prometheus format.

        Args:
            filepath: Output file path
        """
        if not self.metrics_history:
            return

        metrics = self.metrics_history[-1]

        lines = [
            f"# HELP bot_uptime_seconds Bot uptime in seconds",
            f"# TYPE bot_uptime_seconds gauge",
            f"bot_uptime_seconds {metrics.uptime_seconds}",
            "",
            f"# HELP bot_opportunities_total Total opportunities found",
            f"# TYPE bot_opportunities_total counter",
            f"bot_opportunities_total {metrics.opportunities_found}",
            "",
            f"# HELP bot_trades_total Total trades executed",
            f"# TYPE bot_trades_total counter",
            f"bot_trades_total {metrics.trades_executed}",
            "",
            f"# HELP bot_success_rate Trade success rate",
            f"# TYPE bot_success_rate gauge",
            f"bot_success_rate {metrics.success_rate}",
            "",
            f"# HELP bot_net_profit_usd Net profit in USD",
            f"# TYPE bot_net_profit_usd gauge",
            f"bot_net_profit_usd {metrics.net_profit_usd}",
            "",
            f"# HELP bot_memory_usage_mb Memory usage in MB",
            f"# TYPE bot_memory_usage_mb gauge",
            f"bot_memory_usage_mb {metrics.memory_usage_mb}",
            "",
        ]

        with open(filepath, "w") as f:
            f.write("\n".join(lines))

        logger.info(f"Prometheus metrics exported to {filepath}")
