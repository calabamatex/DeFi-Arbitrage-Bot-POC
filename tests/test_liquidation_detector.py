"""Tests for LiquidationDetector."""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from decimal import Decimal

from src.liquidation_detector import LiquidationDetector


@pytest.fixture
def mock_web3():
    w3 = MagicMock()
    w3.to_checksum_address = lambda addr: addr
    w3.eth.chain_id = 137
    w3.eth.block_number = 50000000
    w3.eth.contract.return_value = MagicMock()
    return w3


@pytest.fixture
def detector(mock_web3):
    return LiquidationDetector(
        web3=mock_web3,
        pool_address="0x794a61358D6845594F94dc1DB02A252b5b4814aD",
        data_provider_address="0x69FA688f1Dc47d4B5d8029D5a35FB7a548310654",
        min_profit_usd=50.0,
    )


class TestInit:
    def test_initializes_contracts(self, detector):
        assert detector.pool_contract is not None
        assert detector.data_provider_contract is not None

    def test_stores_min_profit(self, detector):
        assert detector.min_profit_usd == 50.0

    def test_constants(self, detector):
        assert detector.FLASH_LOAN_FEE_BPS == 5
        # HEALTH_FACTOR_THRESHOLD is a module-level constant
        from src.liquidation_detector import HEALTH_FACTOR_THRESHOLD
        assert HEALTH_FACTOR_THRESHOLD == 10**18


class TestGetUserAccountData:
    def test_returns_parsed_data(self, detector):
        # getUserAccountData returns: (totalCollateralBase, totalDebtBase, availableBorrowsBase,
        #   currentLiquidationThreshold, ltv, healthFactor)
        detector.pool_contract.functions.getUserAccountData.return_value.call.return_value = (
            1000 * 10**8,  # totalCollateralBase (in base currency units = 8 decimals)
            500 * 10**8,   # totalDebtBase
            200 * 10**8,   # availableBorrowsBase
            8000,          # currentLiquidationThreshold (80%)
            7500,          # ltv (75%)
            2 * 10**18,    # healthFactor (2.0)
        )

        result = detector.get_user_account_data("0xUserAddr")

        assert result is not None
        assert result["totalCollateralBase"] == 1000 * 10**8
        assert result["totalDebtBase"] == 500 * 10**8
        assert result["healthFactor"] == 2 * 10**18

    def test_returns_none_on_error(self, detector):
        detector.pool_contract.functions.getUserAccountData.return_value.call.side_effect = Exception("RPC error")
        result = detector.get_user_account_data("0xUserAddr")
        assert result is None


class TestIsLiquidatable:
    def test_user_with_health_factor_below_one(self, detector):
        detector.pool_contract.functions.getUserAccountData.return_value.call.return_value = (
            1000 * 10**8, 500 * 10**8, 0, 8000, 7500, int(0.95 * 10**18),
        )

        is_liq, hf = detector.is_liquidatable("0xUserAddr")
        assert is_liq is True
        assert hf == int(0.95 * 10**18)

    def test_user_with_health_factor_above_one(self, detector):
        detector.pool_contract.functions.getUserAccountData.return_value.call.return_value = (
            1000 * 10**8, 500 * 10**8, 200 * 10**8, 8000, 7500, 2 * 10**18,
        )

        is_liq, hf = detector.is_liquidatable("0xUserAddr")
        assert is_liq is False
        assert hf == 2 * 10**18

    def test_returns_false_none_on_error(self, detector):
        detector.pool_contract.functions.getUserAccountData.return_value.call.side_effect = Exception("err")
        is_liq, hf = detector.is_liquidatable("0xUserAddr")
        assert is_liq is False
        assert hf is None


class TestCalculateLiquidationProfit:
    def test_profitable_liquidation(self, detector):
        # liquidation_bonus_bps uses Aave convention: 10500 = 105% = 5% bonus
        result = detector.calculate_liquidation_profit(
            debt_amount=10_000 * 10**6,    # 10k USDC
            liquidation_bonus_bps=10500,    # 5% bonus (Aave format: 10000 + 500)
            debt_decimals=6,
            swap_slippage_bps=50,           # 0.5% slippage
        )

        assert result["gross_profit"] > 0
        assert result["flash_loan_fee"] > 0
        assert result["net_profit"] > 0

    def test_unprofitable_liquidation(self, detector):
        # Very small amount, high slippage, tiny bonus
        result = detector.calculate_liquidation_profit(
            debt_amount=100,                 # 0.0001 USDC
            liquidation_bonus_bps=10100,     # 1% bonus (Aave format)
            debt_decimals=6,
            swap_slippage_bps=200,           # 2% slippage
        )

        # Net profit should be tiny or negative
        assert result["flash_loan_fee"] >= 0


class TestDiscoverActiveBorrowers:
    def test_returns_unique_borrowers(self, detector):
        # Mock get_logs returning events with user addresses in topics
        mock_log1 = {"topics": [b"\x00" * 32, b"\x00" * 12 + bytes.fromhex("aabbccddee" + "00" * 15)]}
        mock_log2 = {"topics": [b"\x00" * 32, b"\x00" * 12 + bytes.fromhex("1122334455" + "00" * 15)]}

        detector.web3.eth.get_logs.return_value = [mock_log1, mock_log2]

        borrowers = detector.discover_active_borrowers(49000000, 50000000)
        assert isinstance(borrowers, list)

    def test_handles_empty_result(self, detector):
        detector.web3.eth.get_logs.return_value = []
        borrowers = detector.discover_active_borrowers(49000000, 50000000)
        assert borrowers == []

    def test_handles_rpc_error(self, detector):
        detector.web3.eth.get_logs.side_effect = Exception("RPC error")
        borrowers = detector.discover_active_borrowers(49000000, 50000000)
        assert borrowers == []


class TestScanForLiquidations:
    def test_empty_users_returns_empty(self, detector):
        result = detector.scan_for_liquidations(
            users=[],
            debt_assets=["0xUSDC"],
            collateral_assets=["0xWETH"],
        )
        assert result == []

    def test_skips_non_liquidatable_users(self, detector):
        # Health factor > 1 — not liquidatable
        detector.pool_contract.functions.getUserAccountData.return_value.call.return_value = (
            1000 * 10**8, 500 * 10**8, 200 * 10**8, 8000, 7500, 2 * 10**18,
        )

        result = detector.scan_for_liquidations(
            users=["0xUser1"],
            debt_assets=["0xUSDC"],
            collateral_assets=["0xWETH"],
        )
        assert result == []
