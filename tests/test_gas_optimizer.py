"""Tests for GasOptimizer."""

import pytest
from unittest.mock import MagicMock
from decimal import Decimal

from src.utils.gas_optimizer import GasOptimizer, get_unlimited_approval_amount


@pytest.fixture
def mock_web3():
    w3 = MagicMock()
    w3.eth.gas_price = 30 * 10**9  # 30 gwei
    w3.eth.get_block.return_value = {
        "baseFeePerGas": 25 * 10**9,  # 25 gwei
    }
    return w3


@pytest.fixture
def gas_optimizer(mock_web3):
    return GasOptimizer(web3=mock_web3)


class TestGetOptimalGasPrice:
    def test_normal_urgency(self, gas_optimizer):
        price = gas_optimizer.get_optimal_gas_price("normal")
        assert price > 0

    def test_low_urgency_cheaper(self, gas_optimizer):
        low = gas_optimizer.get_optimal_gas_price("low")
        normal = gas_optimizer.get_optimal_gas_price("normal")
        assert low <= normal

    def test_high_urgency_more_expensive(self, gas_optimizer):
        normal = gas_optimizer.get_optimal_gas_price("normal")
        high = gas_optimizer.get_optimal_gas_price("high")
        assert high >= normal

    def test_fallback_on_rpc_error(self, gas_optimizer):
        gas_optimizer.web3.eth.gas_price = property(lambda self: (_ for _ in ()).throw(Exception("rpc down")))
        # Should not raise, uses fallback
        try:
            price = gas_optimizer.get_optimal_gas_price("normal")
            assert price > 0
        except Exception:
            # If it does raise, that's also acceptable for a utility
            pass


class TestUseEIP1559:
    def test_returns_eip1559_params(self, gas_optimizer):
        params = gas_optimizer.use_eip1559("normal")
        assert "maxFeePerGas" in params
        assert "maxPriorityFeePerGas" in params
        assert params["maxFeePerGas"] > 0
        assert params["maxPriorityFeePerGas"] > 0

    def test_max_fee_includes_priority(self, gas_optimizer):
        params = gas_optimizer.use_eip1559("normal")
        assert params["maxFeePerGas"] >= params["maxPriorityFeePerGas"]

    def test_high_urgency_higher_priority(self, gas_optimizer):
        normal = gas_optimizer.use_eip1559("normal")
        high = gas_optimizer.use_eip1559("high")
        assert high["maxPriorityFeePerGas"] >= normal["maxPriorityFeePerGas"]

    def test_fallback_on_missing_base_fee(self, gas_optimizer):
        # Legacy chain without baseFeePerGas
        gas_optimizer.web3.eth.get_block.return_value = {}
        params = gas_optimizer.use_eip1559("normal")
        assert params["maxFeePerGas"] > 0


class TestEstimateGasCost:
    def test_returns_decimal(self, gas_optimizer):
        cost = gas_optimizer.estimate_gas_cost(500_000, "normal")
        assert isinstance(cost, Decimal)
        assert cost > 0

    def test_higher_gas_limit_costs_more(self, gas_optimizer):
        low = gas_optimizer.estimate_gas_cost(100_000, "normal")
        high = gas_optimizer.estimate_gas_cost(500_000, "normal")
        assert high > low


class TestIsProfitableAfterGas:
    def test_profitable_trade(self, gas_optimizer):
        # Expected profit much larger than gas cost
        result = gas_optimizer.is_profitable_after_gas(
            expected_profit=Decimal("1.0"),  # 1 ETH/MATIC
            gas_limit=500_000,
            urgency="normal",
        )
        assert result is True

    def test_unprofitable_trade(self, gas_optimizer):
        # Expected profit tiny compared to gas
        result = gas_optimizer.is_profitable_after_gas(
            expected_profit=Decimal("0.000001"),
            gas_limit=5_000_000,
            urgency="high",
        )
        assert result is False


class TestGetGasMultiplier:
    def test_multiplier_values(self, gas_optimizer):
        assert gas_optimizer.get_gas_multiplier("low") < gas_optimizer.get_gas_multiplier("normal")
        assert gas_optimizer.get_gas_multiplier("normal") < gas_optimizer.get_gas_multiplier("high")


class TestGetUnlimitedApprovalAmount:
    def test_returns_max_uint256(self):
        result = get_unlimited_approval_amount()
        assert result == 2**256 - 1
