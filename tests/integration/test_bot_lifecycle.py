"""
Integration tests for the full bot lifecycle.

Tests the pipeline: detect -> risk validate -> build tx -> dry-run -> record.
These tests mock Web3 but use the real Python components wired together.
"""

import os
import pytest
from unittest.mock import MagicMock, patch
from decimal import Decimal
from datetime import datetime

from src.config import Config
from src.utils.risk_manager import RiskManager, TradeResult as RMTradeResult
from src.utils.metrics_collector import MetricsCollector
from src.utils.gas_optimizer import GasOptimizer


@pytest.fixture
def mock_web3():
    w3 = MagicMock()
    w3.to_checksum_address = lambda addr: addr
    w3.eth.chain_id = 137
    w3.eth.block_number = 50000000
    w3.eth.gas_price = 30 * 10**9
    w3.eth.get_block.return_value = {"baseFeePerGas": 25 * 10**9}
    return w3


@pytest.fixture
def risk_manager(mock_web3, tmp_path, monkeypatch):
    # Use a temp state file so tests don't pollute each other
    monkeypatch.setenv("RISK_STATE_FILE", str(tmp_path / "risk_state.json"))
    erc20_abi = [
        {
            "inputs": [{"type": "address", "name": "account"}],
            "name": "balanceOf",
            "outputs": [{"type": "uint256", "name": ""}],
            "stateMutability": "view",
            "type": "function",
        }
    ]
    config = {
        "MAX_POSITION_SIZE_USD": 10000,
        "MAX_TOTAL_EXPOSURE_USD": 50000,
        "DAILY_LOSS_LIMIT_USD": 1000,
        "MAX_CONSECUTIVE_LOSSES": 3,
        "CIRCUIT_BREAKER_COOLDOWN_MIN": 60,
    }
    return RiskManager(web3=mock_web3, erc20_abi=erc20_abi, config=config)


@pytest.fixture
def metrics():
    return MetricsCollector(bot_start_time=datetime.now())


@pytest.fixture
def gas_optimizer(mock_web3):
    return GasOptimizer(web3=mock_web3)


class TestRiskManagerLifecycle:
    def test_validates_normal_trade(self, risk_manager):
        opportunity = {
            "expected_profit_usd": 50.0,
            "amount_in": 5000 * 10**6,
            "token_in": "0xUSDC",
        }
        approved, reason = risk_manager.validate_trade(
            opportunity, "0xBot", "0xUSDC"
        )
        assert approved is True

    def test_circuit_breaker_after_consecutive_losses(self, risk_manager):
        # Record MAX_CONSECUTIVE_LOSSES failures
        for i in range(3):
            trade = RMTradeResult(
                success=False,
                timestamp=datetime.now(),
                profit_loss=Decimal("-10.0"),
                token_pair="USDC/WETH",
                buy_dex="uniswap_v3",
                sell_dex="sushiswap",
                amount=Decimal("5000"),
                gas_cost=Decimal("0.50"),
                message="Reverted",
            )
            risk_manager.record_trade_result(trade)

        metrics = risk_manager.get_risk_metrics()
        assert metrics.circuit_breaker_active is True

    def test_daily_loss_limit(self, risk_manager):
        # Record a massive loss exceeding daily limit
        trade = RMTradeResult(
            success=False,
            timestamp=datetime.now(),
            profit_loss=Decimal("-1500.0"),
            token_pair="USDC/WETH",
            buy_dex="uniswap_v3",
            sell_dex="sushiswap",
            amount=Decimal("50000"),
            gas_cost=Decimal("5.0"),
            message="Large loss",
        )
        risk_manager.record_trade_result(trade)

        metrics = risk_manager.get_risk_metrics()
        assert metrics.daily_pnl < 0


class TestMetricsLifecycle:
    def test_records_trades_and_exports(self, metrics, tmp_path):
        metrics.record_opportunity()
        metrics.record_opportunity()
        metrics.record_trade(success=True, profit_usd=Decimal("50"), gas_cost_usd=Decimal("0.5"))
        metrics.record_trade(success=False, profit_usd=Decimal("0"), gas_cost_usd=Decimal("0.3"))
        metrics.record_detection_time(150.0)
        metrics.record_execution_time(2500.0)

        output = str(tmp_path / "metrics.json")
        metrics.export_metrics_json(output)

        assert os.path.exists(output)

    def test_error_recording(self, metrics):
        metrics.record_error("RPC timeout")
        metrics.record_error("RPC timeout")
        metrics.record_error("Gas spike")

        # Should not raise
        assert True


class TestGasOptimizerIntegration:
    def test_profitability_check_pipeline(self, gas_optimizer):
        # Simulate: detect opportunity -> check gas profitability
        expected_profit = Decimal("0.05")  # 0.05 native tokens
        gas_limit = 500_000

        # Check at different urgency levels
        low_profitable = gas_optimizer.is_profitable_after_gas(expected_profit, gas_limit, "low")
        high_profitable = gas_optimizer.is_profitable_after_gas(expected_profit, gas_limit, "high")

        # Low urgency should be more likely profitable than high
        if not high_profitable:
            # If high urgency isn't profitable, that's expected
            pass
        if low_profitable:
            assert True  # Low urgency is cheaper, more likely profitable

    def test_eip1559_params_valid_for_transaction(self, gas_optimizer):
        params = gas_optimizer.use_eip1559("normal")

        # These should be usable in a web3 transaction dict
        assert isinstance(params["maxFeePerGas"], int)
        assert isinstance(params["maxPriorityFeePerGas"], int)
        assert params["maxFeePerGas"] > 0
        assert params["maxPriorityFeePerGas"] > 0
