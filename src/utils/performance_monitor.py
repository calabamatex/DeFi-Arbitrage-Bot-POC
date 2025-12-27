"""Monitor bot performance metrics."""

import time
from dataclasses import dataclass
from typing import Dict, List
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance metrics snapshot."""

    avg_opportunity_detection_time: Decimal
    avg_trade_execution_time: Decimal
    rpc_calls_per_minute: int
    memory_usage_mb: float
    cpu_percent: float
    total_detections: int
    total_executions: int


class PerformanceMonitor:
    """Monitor and log performance metrics."""

    def __init__(self):
        """Initialize performance monitor."""
        self.detection_times: List[float] = []
        self.execution_times: List[float] = []
        self.rpc_call_count = 0
        self.last_rpc_reset = time.time()
        self.start_time = time.time()

        logger.info("PerformanceMonitor initialized")

    def record_detection_time(self, seconds: float):
        """
        Record opportunity detection time.

        Args:
            seconds: Detection time in seconds
        """
        self.detection_times.append(seconds)

        # Keep only last 100 measurements
        if len(self.detection_times) > 100:
            self.detection_times = self.detection_times[-100:]

        # Log warning if slow
        if seconds > 2.0:
            logger.warning(
                f"Slow opportunity detection: {seconds:.3f}s (target: <2s)"
            )
        else:
            logger.debug(f"Detection time: {seconds:.3f}s")

    def record_execution_time(self, seconds: float):
        """
        Record trade execution time.

        Args:
            seconds: Execution time in seconds
        """
        self.execution_times.append(seconds)

        # Keep only last 100 measurements
        if len(self.execution_times) > 100:
            self.execution_times = self.execution_times[-100:]

        # Log warning if slow
        if seconds > 5.0:
            logger.warning(
                f"Slow trade execution: {seconds:.3f}s (target: <5s)"
            )
        else:
            logger.debug(f"Execution time: {seconds:.3f}s")

    def record_rpc_call(self):
        """Record an RPC call."""
        self.rpc_call_count += 1

        # Reset counter every minute
        current_time = time.time()
        if current_time - self.last_rpc_reset > 60:
            # Log if exceeding target
            if self.rpc_call_count > 100:
                logger.warning(
                    f"High RPC call rate: {self.rpc_call_count}/min (target: <100/min)"
                )

            self.rpc_call_count = 0
            self.last_rpc_reset = current_time

    def get_metrics(self) -> PerformanceMetrics:
        """
        Get current performance metrics.

        Returns:
            PerformanceMetrics snapshot
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

        # Calculate averages
        avg_detection = (
            Decimal(str(sum(self.detection_times) / len(self.detection_times)))
            if self.detection_times
            else Decimal("0")
        )

        avg_execution = (
            Decimal(str(sum(self.execution_times) / len(self.execution_times)))
            if self.execution_times
            else Decimal("0")
        )

        return PerformanceMetrics(
            avg_opportunity_detection_time=avg_detection,
            avg_trade_execution_time=avg_execution,
            rpc_calls_per_minute=self.rpc_call_count,
            memory_usage_mb=memory_mb,
            cpu_percent=cpu_percent,
            total_detections=len(self.detection_times),
            total_executions=len(self.execution_times),
        )

    def log_metrics(self):
        """Log current performance metrics."""
        metrics = self.get_metrics()

        logger.info(
            f"\n{'='*60}\n"
            f"Performance Metrics\n"
            f"{'='*60}\n"
            f"Avg Detection Time: {metrics.avg_opportunity_detection_time:.3f}s (target: <2s)\n"
            f"Avg Execution Time: {metrics.avg_trade_execution_time:.3f}s (target: <5s)\n"
            f"RPC Calls/min: {metrics.rpc_calls_per_minute} (target: <100)\n"
            f"Memory Usage: {metrics.memory_usage_mb:.1f} MB (target: <500 MB)\n"
            f"CPU Usage: {metrics.cpu_percent:.1f}%\n"
            f"Total Detections: {metrics.total_detections}\n"
            f"Total Executions: {metrics.total_executions}\n"
            f"{'='*60}"
        )

    def check_performance_targets(self) -> Dict[str, bool]:
        """
        Check if performance targets are being met.

        Returns:
            Dict of target name to whether it's being met
        """
        metrics = self.get_metrics()

        targets = {
            "detection_speed": metrics.avg_opportunity_detection_time
            < Decimal("2.0"),
            "execution_speed": metrics.avg_trade_execution_time < Decimal("5.0"),
            "rpc_rate": metrics.rpc_calls_per_minute < 100,
            "memory_usage": metrics.memory_usage_mb < 500.0,
        }

        # Log warnings for missed targets
        for target_name, met in targets.items():
            if not met:
                logger.warning(f"Performance target MISSED: {target_name}")

        return targets

    def get_uptime(self) -> float:
        """
        Get bot uptime in seconds.

        Returns:
            Uptime in seconds
        """
        return time.time() - self.start_time

    def reset_statistics(self):
        """Reset all performance statistics."""
        self.detection_times.clear()
        self.execution_times.clear()
        self.rpc_call_count = 0
        self.last_rpc_reset = time.time()

        logger.info("Performance statistics reset")
