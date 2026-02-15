"""Tests for LiquidationOrchestrator."""

import time
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from decimal import Decimal

from src.liquidation_orchestrator import LiquidationOrchestrator


@pytest.fixture
def mock_web3():
    w3 = MagicMock()
    w3.to_checksum_address = lambda addr: addr
    w3.eth.chain_id = 137
    w3.eth.block_number = 50000000
    w3.eth.gas_price = 30 * 10**9
    w3.eth.get_transaction_count.return_value = 0
    w3.to_wei = lambda val, unit: val * 10**9 if unit == 'gwei' else val

    # Mock contract
    contract_mock = MagicMock()
    contract_mock.functions.owner.return_value.call.return_value = "0xOwnerAddress"
    contract_mock.functions.paused.return_value.call.return_value = False
    contract_mock.functions.liquidationCount.return_value.call.return_value = 42
    w3.eth.contract.return_value = contract_mock

    # Mock codec for swap data encoding
    w3.codec.encode.return_value = b"\x00" * 32

    return w3


@pytest.fixture
def orchestrator(mock_web3):
    with patch("src.liquidation_orchestrator.Account") as mock_account_cls:
        mock_account = MagicMock()
        mock_account.address = "0xOwnerAddress"
        mock_account_cls.from_key.return_value = mock_account

        return LiquidationOrchestrator(
            web3=mock_web3,
            liquidator_address="0xLiquidatorContract",
            private_key="0x" + "ab" * 32,
            v3_adapter_address="0xV3Adapter",
            v2_adapter_address="0xV2Adapter",
            dry_run=True,
        )


@pytest.fixture
def sample_opportunity():
    return {
        "collateral_asset": "0xWETH",
        "debt_asset": "0xUSDC",
        "user": "0xBorrower",
        "debt_amount": 10_000 * 10**6,  # 10k USDC
        "net_profit": 500 * 10**6,       # $500 profit
        "net_profit_usd": 500.0,
    }


class TestInit:
    def test_stores_addresses(self, orchestrator):
        assert orchestrator.liquidator_address == "0xLiquidatorContract"
        assert orchestrator.v3_adapter == "0xV3Adapter"
        assert orchestrator.v2_adapter == "0xV2Adapter"

    def test_dry_run_mode(self, orchestrator):
        assert orchestrator.dry_run is True

    def test_curve_adapter_none_by_default(self, orchestrator):
        assert orchestrator.curve_adapter is None

    def test_curve_adapter_when_provided(self, mock_web3):
        with patch("src.liquidation_orchestrator.Account") as mock_cls:
            mock_cls.from_key.return_value = MagicMock(address="0xOwnerAddress")
            orch = LiquidationOrchestrator(
                web3=mock_web3,
                liquidator_address="0xLiq",
                private_key="0x" + "ab" * 32,
                v3_adapter_address="0xV3",
                v2_adapter_address="0xV2",
                curve_adapter_address="0xCurve",
            )
            assert orch.curve_adapter == "0xCurve"


class TestSelectAdapter:
    def test_defaults_to_v3(self, orchestrator):
        result = orchestrator.select_adapter("0xWETH", "0xUSDC")
        assert result == "0xV3Adapter"


class TestEncodeSwapData:
    def test_encodes_v3_fee(self, orchestrator):
        result = orchestrator.encode_swap_data(orchestrator.v3_adapter, fee=500)
        assert isinstance(result, bytes)

    def test_empty_for_unknown_adapter(self, orchestrator):
        result = orchestrator.encode_swap_data("0xUnknown")
        assert result == b""


class TestBuildLiquidationParams:
    def test_builds_correct_tuple(self, orchestrator, sample_opportunity):
        params = orchestrator.build_liquidation_params(sample_opportunity, min_profit=100)

        assert params[0] == "0xWETH"           # collateral
        assert params[1] == "0xUSDC"           # debt
        assert params[2] == "0xBorrower"       # user
        assert params[3] == 10_000 * 10**6     # debt_to_cover
        assert params[4] == "0xV3Adapter"      # adapter
        assert isinstance(params[5], bytes)    # swap_data
        assert params[6] == 100                # min_profit
        assert params[7] > time.time()         # deadline in future

    def test_default_min_profit_zero(self, orchestrator, sample_opportunity):
        params = orchestrator.build_liquidation_params(sample_opportunity)
        assert params[6] == 0


class TestEstimateGas:
    def test_adds_buffer(self, orchestrator):
        orchestrator.web3.eth.estimate_gas.return_value = 500_000
        result = orchestrator.estimate_gas({"data": "0x"})
        assert result == 600_000  # 500k * 1.2

    def test_fallback_on_error(self, orchestrator):
        orchestrator.web3.eth.estimate_gas.side_effect = Exception("estimation failed")
        result = orchestrator.estimate_gas({"data": "0x"})
        assert result == 800_000  # default


class TestExecuteLiquidation:
    def test_dry_run_simulation_pass(self, orchestrator, sample_opportunity):
        # Mock gas pricing
        orchestrator.web3.eth.get_block.return_value = {"baseFeePerGas": 30 * 10**9}
        orchestrator.web3.eth.estimate_gas.return_value = 500_000

        # Mock build_transaction
        orchestrator.contract.functions.executeLiquidation.return_value.build_transaction.return_value = {
            "from": orchestrator.address,
            "to": orchestrator.liquidator_address,
            "data": "0x1234",
            "gas": 0,
            "maxFeePerGas": 60 * 10**9,
            "maxPriorityFeePerGas": 2 * 10**9,
        }

        # Simulation passes
        orchestrator.web3.eth.call.return_value = b""

        result = orchestrator.execute_liquidation(sample_opportunity)

        assert result["success"] is True
        assert result["tx_hash"] == "0x" + "0" * 64

    def test_simulation_failure_returns_error(self, orchestrator, sample_opportunity):
        orchestrator.web3.eth.get_block.return_value = {"baseFeePerGas": 30 * 10**9}
        orchestrator.web3.eth.estimate_gas.return_value = 500_000

        orchestrator.contract.functions.executeLiquidation.return_value.build_transaction.return_value = {
            "from": orchestrator.address,
            "to": orchestrator.liquidator_address,
            "data": "0x1234",
            "gas": 0,
            "maxFeePerGas": 60 * 10**9,
            "maxPriorityFeePerGas": 2 * 10**9,
        }

        orchestrator.web3.eth.call.side_effect = Exception("InsufficientProfit")

        result = orchestrator.execute_liquidation(sample_opportunity)

        assert result["success"] is False
        assert "Simulation failed" in result["error"]

    def test_paused_contract_returns_error(self, orchestrator, sample_opportunity):
        orchestrator.contract.functions.paused.return_value.call.return_value = True

        result = orchestrator.execute_liquidation(sample_opportunity)

        assert result["success"] is False
        assert "paused" in result["error"].lower()


class TestExecuteBatch:
    def test_executes_each_opportunity(self, orchestrator, sample_opportunity):
        # Make all simulations fail so we get fast results
        orchestrator.contract.functions.paused.return_value.call.return_value = True

        opps = [sample_opportunity, sample_opportunity]
        results = orchestrator.execute_batch(opps)

        assert len(results) == 2
        assert all(not r["success"] for r in results)


class TestGetContractStats:
    def test_returns_stats(self, orchestrator):
        orchestrator.contract.functions.liquidationCount.return_value.call.return_value = 42
        orchestrator.contract.functions.paused.return_value.call.return_value = False

        stats = orchestrator.get_contract_stats()

        assert stats["liquidation_count"] == 42
        assert stats["paused"] is False
        assert stats["contract"] == "0xLiquidatorContract"

    def test_returns_empty_on_error(self, orchestrator):
        orchestrator.contract.functions.liquidationCount.return_value.call.side_effect = Exception("err")
        stats = orchestrator.get_contract_stats()
        assert stats == {}
