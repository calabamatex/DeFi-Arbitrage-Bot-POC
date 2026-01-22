"""Comprehensive tests for Slippage Protection."""

import pytest
from decimal import Decimal
from src.utils.slippage_protection import (
    SlippageProtection,
    SlippageAnalysis,
    get_slippage_protection,
)


@pytest.fixture
def slippage_protection():
    """Create SlippageProtection instance."""
    return SlippageProtection(
        max_slippage_percent=Decimal("0.005"),  # 0.5%
        max_price_impact_percent=Decimal("0.01"),  # 1%
    )


def test_initialization(slippage_protection):
    """Test SlippageProtection initialization."""
    assert slippage_protection.max_slippage == Decimal("0.005")
    assert slippage_protection.max_price_impact == Decimal("0.01")


def test_calculate_minimum_output(slippage_protection):
    """Test minimum output calculation."""
    expected = Decimal("100")
    minimum = slippage_protection.calculate_minimum_output(expected)

    # Should be 99.5 with 0.5% slippage
    assert minimum == Decimal("99.5")


def test_calculate_minimum_output_custom_tolerance(slippage_protection):
    """Test minimum output with custom tolerance."""
    expected = Decimal("100")
    minimum = slippage_protection.calculate_minimum_output(
        expected, slippage_tolerance=Decimal("0.01")  # 1%
    )

    # Should be 99.0 with 1% slippage
    assert minimum == Decimal("99")


def test_validate_execution_price_ok(slippage_protection):
    """Test price validation - within tolerance."""
    valid, slippage = slippage_protection.validate_execution_price(
        expected_price=Decimal("2000"), actual_price=Decimal("2005")
    )

    # 0.25% slippage should be OK (< 0.5%)
    assert valid is True
    assert slippage < Decimal("0.005")


def test_validate_execution_price_exceeded(slippage_protection):
    """Test price validation - exceeds tolerance."""
    valid, slippage = slippage_protection.validate_execution_price(
        expected_price=Decimal("2000"), actual_price=Decimal("2020")
    )

    # 1% slippage should fail (> 0.5%)
    assert valid is False
    assert slippage > Decimal("0.005")


def test_validate_execution_price_zero_expected(slippage_protection):
    """Test price validation with zero expected price."""
    valid, slippage = slippage_protection.validate_execution_price(
        expected_price=Decimal("0"), actual_price=Decimal("100")
    )

    # Should handle zero gracefully
    assert valid is False
    assert slippage == Decimal("100")


def test_validate_execution_price_custom_tolerance(slippage_protection):
    """Test price validation with custom tolerance."""
    valid, slippage = slippage_protection.validate_execution_price(
        expected_price=Decimal("2000"),
        actual_price=Decimal("2015"),
        tolerance=Decimal("0.01"),  # 1%
    )

    # 0.75% slippage should be OK with 1% tolerance
    assert valid is True


def test_estimate_price_impact_low(slippage_protection):
    """Test price impact estimation - low impact."""
    impact = slippage_protection.estimate_price_impact(
        trade_amount=Decimal("1"), pool_liquidity=Decimal("1000")
    )

    # Should be very low
    assert impact < Decimal("1")  # < 1%


def test_estimate_price_impact_high(slippage_protection):
    """Test price impact estimation - high impact."""
    impact = slippage_protection.estimate_price_impact(
        trade_amount=Decimal("100"), pool_liquidity=Decimal("500")
    )

    # Should be significant
    assert impact > Decimal("10")  # > 10%


def test_estimate_price_impact_zero_liquidity(slippage_protection):
    """Test price impact with zero liquidity."""
    impact = slippage_protection.estimate_price_impact(
        trade_amount=Decimal("10"), pool_liquidity=Decimal("0")
    )

    # Should return 100% impact
    assert impact == Decimal("100")


def test_estimate_price_impact_non_constant_product(slippage_protection):
    """Test price impact with non-constant product model."""
    impact = slippage_protection.estimate_price_impact(
        trade_amount=Decimal("10"),
        pool_liquidity=Decimal("100"),
        constant_product=False,
    )

    # Should use simple proportional model
    assert impact == Decimal("10")  # 10/100 = 10%


def test_check_slippage_acceptable_ok(slippage_protection):
    """Test slippage check - acceptable."""
    acceptable, reason = slippage_protection.check_slippage_acceptable(
        expected_price=Decimal("2000"),
        actual_price=Decimal("2005"),
        estimated_impact=Decimal("0.5"),
    )

    assert acceptable is True
    assert "acceptable" in reason


def test_check_slippage_acceptable_price_exceeded(slippage_protection):
    """Test slippage check - price slippage exceeded."""
    acceptable, reason = slippage_protection.check_slippage_acceptable(
        expected_price=Decimal("2000"),
        actual_price=Decimal("2020"),
        estimated_impact=Decimal("0.5"),
    )

    assert acceptable is False
    assert "slippage" in reason.lower()


def test_check_slippage_acceptable_impact_exceeded(slippage_protection):
    """Test slippage check - price impact exceeded."""
    acceptable, reason = slippage_protection.check_slippage_acceptable(
        expected_price=Decimal("2000"),
        actual_price=Decimal("2005"),
        estimated_impact=Decimal("2"),  # 2% > 1% limit
    )

    assert acceptable is False
    assert "impact" in reason.lower()


def test_calculate_safe_trade_amount(slippage_protection):
    """Test safe trade amount calculation."""
    safe = slippage_protection.calculate_safe_trade_amount(
        desired_amount=Decimal("100"), pool_liquidity=Decimal("10000")
    )

    # Should be less than or equal to desired
    assert safe <= Decimal("100")
    assert safe > 0


def test_calculate_safe_trade_amount_limited_by_desired(slippage_protection):
    """Test safe amount limited by desired amount."""
    safe = slippage_protection.calculate_safe_trade_amount(
        desired_amount=Decimal("10"), pool_liquidity=Decimal("100000")
    )

    # Should not exceed desired
    assert safe <= Decimal("10")


def test_calculate_safe_trade_amount_limited_by_liquidity(slippage_protection):
    """Test safe amount limited by liquidity."""
    safe = slippage_protection.calculate_safe_trade_amount(
        desired_amount=Decimal("1000"), pool_liquidity=Decimal("100")
    )

    # Should not exceed 10% of liquidity
    assert safe <= Decimal("10")


def test_calculate_safe_trade_amount_custom_target(slippage_protection):
    """Test safe amount with custom target impact."""
    safe = slippage_protection.calculate_safe_trade_amount(
        desired_amount=Decimal("100"),
        pool_liquidity=Decimal("10000"),
        target_impact=Decimal("0.005"),  # 0.5% target
    )

    # Should be more conservative with lower target
    assert safe > 0
    assert safe <= Decimal("100")


def test_analyze_slippage_budget(slippage_protection):
    """Test complete slippage analysis."""
    analysis = slippage_protection.analyze_slippage_budget(
        expected_buy_price=Decimal("2000"),
        expected_sell_price=Decimal("2010"),
        buy_pool_liquidity=Decimal("10000"),
        sell_pool_liquidity=Decimal("10000"),
        amount=Decimal("1"),
    )

    assert isinstance(analysis, SlippageAnalysis)
    assert analysis.expected_price == Decimal("2010")
    assert analysis.minimum_acceptable_price > 0
    assert analysis.estimated_price_impact >= 0
    assert analysis.recommended_max_amount > 0
    assert analysis.total_slippage_budget > 0


def test_analyze_slippage_budget_large_trade(slippage_protection):
    """Test slippage analysis for large trade."""
    analysis = slippage_protection.analyze_slippage_budget(
        expected_buy_price=Decimal("2000"),
        expected_sell_price=Decimal("2010"),
        buy_pool_liquidity=Decimal("1000"),
        sell_pool_liquidity=Decimal("1000"),
        amount=Decimal("100"),  # Large relative to liquidity
    )

    # Should have significant price impact
    assert analysis.estimated_price_impact > Decimal("5")
    # Recommended max should be less than requested
    assert analysis.recommended_max_amount < Decimal("100")


def test_validate_arbitrage_slippage_profitable(slippage_protection):
    """Test arbitrage validation - profitable after slippage."""
    profitable, net = slippage_protection.validate_arbitrage_slippage(
        buy_price=Decimal("2000"),
        sell_price=Decimal("2050"),  # 2.5% profit
        expected_profit=Decimal("50"),
        estimated_total_impact=Decimal("0.3"),  # 0.3% impact
    )

    # Should still be profitable after slippage costs
    # impact_cost = (2000 + 2050) * 0.003 = 12.15
    # slippage_cost = (2000 + 2050) * 0.005 = 20.25
    # net = 50 - 12.15 - 20.25 = 17.6
    assert profitable is True
    assert net > 0


def test_validate_arbitrage_slippage_not_profitable(slippage_protection):
    """Test arbitrage validation - not profitable after slippage."""
    profitable, net = slippage_protection.validate_arbitrage_slippage(
        buy_price=Decimal("2000"),
        sell_price=Decimal("2005"),  # 0.25% profit
        expected_profit=Decimal("5"),
        estimated_total_impact=Decimal("1"),  # 1% impact
    )

    # Should NOT be profitable after slippage
    assert profitable is False
    assert net <= 0


def test_validate_arbitrage_slippage_marginal(slippage_protection):
    """Test arbitrage validation - marginal profit."""
    profitable, net = slippage_protection.validate_arbitrage_slippage(
        buy_price=Decimal("2000"),
        sell_price=Decimal("2030"),  # 1.5% profit
        expected_profit=Decimal("30"),
        estimated_total_impact=Decimal("0.8"),  # 0.8% impact
    )

    # Calculate expected costs
    # impact_cost = (2000 + 2030) * 0.008 = 32.24
    # slippage_cost = (2000 + 2030) * 0.005 = 20.15
    # net = 30 - 32.24 - 20.15 = negative
    # So should not be profitable
    assert profitable is False


def test_get_slippage_protection_factory():
    """Test factory function."""
    protection = get_slippage_protection()

    assert isinstance(protection, SlippageProtection)
    assert protection.max_slippage == Decimal("0.005")
    assert protection.max_price_impact == Decimal("0.01")


def test_get_slippage_protection_custom_params():
    """Test factory function with custom parameters."""
    protection = get_slippage_protection(
        max_slippage=Decimal("0.01"), max_price_impact=Decimal("0.02")
    )

    assert protection.max_slippage == Decimal("0.01")
    assert protection.max_price_impact == Decimal("0.02")
