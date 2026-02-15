"""Unit tests for OpportunityDetector."""

import pytest
import os
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock, PropertyMock

from src.opportunity_detector import OpportunityDetector


@pytest.fixture
def mock_web3():
    """Mock Web3 instance."""
    web3 = Mock()
    web3.to_checksum_address = lambda x: x
    web3.eth.gas_price = 30_000_000_000  # 30 gwei
    web3.eth.chain_id = 137
    web3.to_wei = Mock(side_effect=lambda x, unit: int(x * 10**9) if unit == 'gwei' else x)
    web3.from_wei = Mock(side_effect=lambda x, unit: x / 10**9 if unit == 'gwei' else x)
    web3.keccak = Mock(return_value=b'\x00' * 32)

    # Mock QuoterV2 contract
    v3_contract = Mock()
    v2_contract = Mock()
    web3.eth.contract = Mock(side_effect=lambda **kwargs: v3_contract if 'quoteExactInputSingle' in str(kwargs.get('abi', '')) else v2_contract)

    return web3


@pytest.fixture
def detector(mock_web3):
    """Create OpportunityDetector with mocks."""
    with patch('src.opportunity_detector.load_dotenv'):
        det = OpportunityDetector(
            web3=mock_web3,
            min_profit_usd=1.0,
            max_gas_price_gwei=100,
            check_interval=5,
            min_flash_loan=500 * 10**6,
            max_flash_loan=100000 * 10**6,
        )
    return det


# ── Flash Loan Fee Calculation ──────────────────────────────────────

class TestFlashLoanFeeCalc:

    def test_flash_loan_fee_basic(self, detector):
        """Flash loan fee should be 0.05% (5 bps)."""
        amount = 1000 * 10**6  # 1000 USDC
        gross_profit = 10 * 10**6  # 10 USDC
        expected_fee = (amount * 5) // 10000  # 500000 = 0.5 USDC
        expected_net = gross_profit - expected_fee

        result = detector._calculate_profit_after_fees(amount, gross_profit)
        assert result == expected_net

    def test_flash_loan_fee_zero_profit(self, detector):
        """Zero gross profit should yield negative net (fee only)."""
        amount = 10000 * 10**6
        result = detector._calculate_profit_after_fees(amount, 0)
        assert result < 0

    def test_flash_loan_fee_large_amount(self, detector):
        """Fee calculation for large amounts."""
        amount = 100000 * 10**6  # 100k USDC
        gross_profit = 500 * 10**6  # 500 USDC
        fee = (amount * 5) // 10000  # 50 USDC
        expected = gross_profit - fee

        result = detector._calculate_profit_after_fees(amount, gross_profit)
        assert result == expected

    def test_flash_loan_fee_bps_constant(self, detector):
        """Verify the fee constant is 5 bps."""
        assert detector.FLASH_LOAN_FEE_BPS == 5


# ── Gas Cost Estimation ─────────────────────────────────────────────

class TestGasCostEstimation:

    def test_estimate_gas_cost(self, detector):
        """Gas cost = 500k gas * gas_price."""
        gas_cost = detector.estimate_gas_cost()
        expected = 500000 * 30_000_000_000  # 500k * 30 gwei
        assert gas_cost == expected

    def test_gas_cost_fallback(self, detector):
        """Should use fallback on RPC failure."""
        type(detector.web3.eth).gas_price = PropertyMock(side_effect=Exception("RPC down"))
        # Fallback uses max_gas_price_gwei via to_wei
        gas_cost = detector.estimate_gas_cost()
        assert gas_cost > 0


# ── Profitability Check ─────────────────────────────────────────────

class TestProfitabilityCheck:

    def test_profitable_after_gas(self, detector):
        """Should return True when net profit > min_profit_usd."""
        with patch.dict(os.environ, {'NATIVE_TOKEN_PRICE_USD': '0.80'}):
            # profit = 5 USDC, gas cost = 500k * 30gwei * 0.80 = ~0.012 USD
            result = detector.is_profitable_after_gas(
                net_profit_tokens=5 * 10**6,  # 5 USDC
                token_address='0x' + '00' * 20,
                token_decimals=6,
            )
            assert result is True

    def test_not_profitable_after_gas(self, detector):
        """Should return False when profit is tiny."""
        with patch.dict(os.environ, {'NATIVE_TOKEN_PRICE_USD': '0.80'}):
            result = detector.is_profitable_after_gas(
                net_profit_tokens=100,  # 0.0001 USDC
                token_address='0x' + '00' * 20,
                token_decimals=6,
            )
            assert result is False


# ── V3 Fee Tiers ────────────────────────────────────────────────────

class TestV3FeeTiers:

    def test_fee_tier_constants(self, detector):
        assert detector.V3_FEE_LOW == 500
        assert detector.V3_FEE_MEDIUM == 3000
        assert detector.V3_FEE_HIGH == 10000


# ── Calculate Arbitrage ─────────────────────────────────────────────

class TestCalculateArbitrage:

    def test_v3_then_v2_opportunity(self, detector):
        """Should detect V3→V2 opportunity when profitable."""
        # Mock V3 quote: 1000 USDC → 1050 output
        detector.get_v3_quote = Mock(return_value=1050 * 10**6)
        detector.find_best_v3_fee = Mock(return_value=(1050 * 10**6, 3000))

        # Mock V2 quote: 1050 → 1060 (10 profit + covers flash loan fee)
        detector.get_v2_quote = Mock(return_value=1060 * 10**6)

        opps = detector.calculate_arbitrage(
            detector.usdc, detector.weth, 1000 * 10**6
        )

        assert len(opps) >= 1
        v3_v2 = [o for o in opps if o['direction'] == 'V3→V2']
        assert len(v3_v2) == 1
        assert v3_v2[0]['gross_profit'] == 60 * 10**6
        assert v3_v2[0]['net_profit'] > 0
        assert v3_v2[0]['v3_fee'] == 3000

    def test_no_opportunity_when_unprofitable(self, detector):
        """Should return empty when no profit after fees."""
        detector.find_best_v3_fee = Mock(return_value=(1000 * 10**6, 3000))
        detector.get_v2_quote = Mock(return_value=999 * 10**6)  # Loss

        opps = detector.calculate_arbitrage(
            detector.usdc, detector.weth, 1000 * 10**6
        )

        # Filter for V3→V2 (should be none since unprofitable)
        v3_v2 = [o for o in opps if o['direction'] == 'V3→V2']
        assert len(v3_v2) == 0

    def test_v3_quote_fails_gracefully(self, detector):
        """Should handle V3 quote failure."""
        detector.find_best_v3_fee = Mock(return_value=(None, None))
        detector.get_v2_quote = Mock(return_value=None)

        opps = detector.calculate_arbitrage(
            detector.usdc, detector.weth, 1000 * 10**6
        )
        assert opps == []


# ── Log Opportunity ─────────────────────────────────────────────────

class TestLogOpportunity:

    def test_log_opportunity_attaches_id(self, detector):
        """log_opportunity should set opportunity_id on the dict."""
        opp = {
            'direction': 'V3→V2',
            'token_in': '0x' + 'aa' * 20,
            'token_out': '0x' + 'bb' * 20,
            'amount_in': 1000 * 10**6,
            'net_profit': 50 * 10**6,
            'gross_profit': 55 * 10**6,
            'dex_path': ['uniswap_v3', 'quickswap'],
            'amount_after_v2': 1050 * 10**6,
        }

        with patch('src.opportunity_detector.get_db') as mock_db:
            mock_session = MagicMock()
            mock_db.return_value.__enter__ = Mock(return_value=mock_session)
            mock_db.return_value.__exit__ = Mock(return_value=False)

            result = detector.log_opportunity(opp, token_decimals=6)

        assert result is not None
        assert 'opportunity_id' in opp


# ── Token Decimals ──────────────────────────────────────────────────

class TestTokenDecimals:

    def test_token_decimals_registry(self, detector):
        """Token decimals should be registered for known tokens."""
        assert detector.token_decimals.get(detector.usdc.lower()) == 6
        assert detector.token_decimals.get(detector.wmatic.lower()) == 18
        assert detector.token_decimals.get(detector.weth.lower()) == 18
        assert detector.token_decimals.get(detector.dai.lower()) == 18
