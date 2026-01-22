#!/usr/bin/env python3
"""
Create test metrics for demonstrating the monitoring dashboard.
"""

import sys
import os
from pathlib import Path
from datetime import datetime
from decimal import Decimal

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.metrics_collector import MetricsCollector


def create_test_metrics():
    """Create test metrics data."""
    print("Creating test metrics...")

    # Create metrics collector with start time 2 hours ago
    start_time = datetime.now().replace(hour=datetime.now().hour - 2)
    collector = MetricsCollector(bot_start_time=start_time)

    # Simulate some activity
    print("Simulating bot activity...")

    # Record opportunities
    for _ in range(25):
        collector.record_opportunity()

    # Record successful trades
    for _ in range(10):
        collector.record_trade(
            success=True, profit_usd=Decimal("12.50"), gas_cost_usd=Decimal("0.50")
        )
        collector.record_detection_time(1200)  # 1.2 seconds
        collector.record_execution_time(3500)  # 3.5 seconds

    # Record some failed trades
    for _ in range(2):
        collector.record_trade(
            success=False, profit_usd=Decimal("0"), gas_cost_usd=Decimal("0.50")
        )

    # Record some errors
    collector.record_error("RPC connection timeout")
    collector.record_error("Insufficient liquidity on DEX")

    # Collect metrics
    print("Collecting metrics...")
    metrics = collector.collect_metrics()

    # Create data directory
    os.makedirs("data", exist_ok=True)

    # Export to JSON
    print("Exporting to JSON...")
    collector.export_metrics_json("data/metrics.json")

    # Export to Prometheus
    print("Exporting to Prometheus format...")
    collector.export_prometheus("data/metrics.prom")

    print("\n✅ Test metrics created successfully!")
    print(f"   - data/metrics.json")
    print(f"   - data/metrics.prom")
    print()
    print("Summary:")
    print(f"  Uptime: {metrics.uptime_seconds/3600:.1f} hours")
    print(f"  Opportunities: {metrics.opportunities_found}")
    print(f"  Trades: {metrics.trades_executed}")
    print(f"  Success Rate: {metrics.success_rate*100:.1f}%")
    print(f"  Net Profit: ${metrics.net_profit_usd:.2f}")


if __name__ == "__main__":
    create_test_metrics()
