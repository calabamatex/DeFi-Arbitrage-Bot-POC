"""Tests for metrics collector."""

import pytest
from datetime import datetime
from decimal import Decimal
from src.utils.metrics_collector import MetricsCollector, BotMetrics


class TestMetricsCollector:
    """Test metrics collection functionality."""

    def test_initialization(self):
        """Test metrics collector initializes correctly."""
        start_time = datetime.now()
        collector = MetricsCollector(bot_start_time=start_time)

        assert collector.start_time == start_time
        assert collector.opportunities_found == 0
        assert collector.trades_executed == 0
        assert len(collector.metrics_history) == 0

    def test_record_opportunity(self):
        """Test recording opportunities."""
        collector = MetricsCollector(bot_start_time=datetime.now())

        collector.record_opportunity()
        collector.record_opportunity()

        assert collector.opportunities_found == 2

    def test_record_successful_trade(self):
        """Test recording successful trade."""
        collector = MetricsCollector(bot_start_time=datetime.now())

        collector.record_trade(
            success=True, profit_usd=Decimal("10.5"), gas_cost_usd=Decimal("0.5")
        )

        assert collector.trades_executed == 1
        assert collector.successful_trades == 1
        assert collector.failed_trades == 0
        assert len(collector.profits) == 1
        assert collector.profits[0] == 10.5

    def test_record_failed_trade(self):
        """Test recording failed trade."""
        collector = MetricsCollector(bot_start_time=datetime.now())

        collector.record_trade(
            success=False, profit_usd=Decimal("0"), gas_cost_usd=Decimal("0.5")
        )

        assert collector.trades_executed == 1
        assert collector.successful_trades == 0
        assert collector.failed_trades == 1
        assert len(collector.losses) == 1

    def test_record_detection_time(self):
        """Test recording detection times."""
        collector = MetricsCollector(bot_start_time=datetime.now())

        collector.record_detection_time(1500)
        collector.record_detection_time(1200)

        assert len(collector.detection_times) == 2
        assert collector.detection_times[0] == 1500

    def test_record_execution_time(self):
        """Test recording execution times."""
        collector = MetricsCollector(bot_start_time=datetime.now())

        collector.record_execution_time(3000)
        collector.record_execution_time(3500)

        assert len(collector.execution_times) == 2

    def test_record_error(self):
        """Test recording errors."""
        collector = MetricsCollector(bot_start_time=datetime.now())

        collector.record_error("Test error")
        collector.record_error("Another error")

        assert len(collector.errors) == 2
        assert collector.last_error is not None

    def test_collect_metrics(self):
        """Test collecting metrics."""
        collector = MetricsCollector(bot_start_time=datetime.now())

        # Record some activity
        collector.record_opportunity()
        collector.record_opportunity()
        collector.record_trade(
            success=True, profit_usd=Decimal("10"), gas_cost_usd=Decimal("0.5")
        )
        collector.record_detection_time(1500)
        collector.record_execution_time(3000)

        metrics = collector.collect_metrics()

        assert isinstance(metrics, BotMetrics)
        assert metrics.opportunities_found == 2
        assert metrics.trades_executed == 1
        assert metrics.success_rate == 1.0
        assert metrics.net_profit_usd == 10.0

    def test_export_json(self, tmp_path):
        """Test exporting metrics to JSON."""
        collector = MetricsCollector(bot_start_time=datetime.now())

        collector.record_opportunity()
        collector.collect_metrics()

        output_file = tmp_path / "test_metrics.json"
        collector.export_metrics_json(str(output_file))

        assert output_file.exists()
        # Verify it's valid JSON
        import json

        with open(output_file) as f:
            data = json.load(f)
            assert "current_metrics" in data
            assert "metrics_history" in data

    def test_export_prometheus(self, tmp_path):
        """Test exporting metrics to Prometheus format."""
        collector = MetricsCollector(bot_start_time=datetime.now())

        collector.record_opportunity()
        collector.collect_metrics()

        output_file = tmp_path / "test_metrics.prom"
        collector.export_prometheus(str(output_file))

        assert output_file.exists()
        # Verify format
        with open(output_file) as f:
            content = f.read()
            assert "bot_uptime_seconds" in content
            assert "bot_opportunities_total" in content

    def test_detection_time_limit(self):
        """Test detection times list is limited to 100."""
        collector = MetricsCollector(bot_start_time=datetime.now())

        # Record 150 times
        for i in range(150):
            collector.record_detection_time(float(i))

        # Should only keep last 100
        assert len(collector.detection_times) == 100
        assert collector.detection_times[0] == 50.0

    def test_metrics_history_limit(self):
        """Test metrics history is limited to 1000."""
        collector = MetricsCollector(bot_start_time=datetime.now())

        # Collect 1500 metrics
        for _ in range(1500):
            collector.collect_metrics()

        # Should only keep last 1000
        assert len(collector.metrics_history) == 1000
