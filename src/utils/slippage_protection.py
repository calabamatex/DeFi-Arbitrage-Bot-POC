"""
Slippage Protection - Prevents losses from price movements during execution.
"""

from decimal import Decimal
from typing import Tuple, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class SlippageAnalysis:
    """Analysis of slippage for a trade."""

    expected_price: Decimal
    minimum_acceptable_price: Decimal
    maximum_slippage_percent: Decimal
    estimated_price_impact: Decimal
    total_slippage_budget: Decimal
    recommended_max_amount: Decimal


class SlippageProtection:
    """
    Protects against excessive slippage.

    Slippage sources:
    1. Market movement (price changes while executing)
    2. Price impact (our trade moves the market)
    3. DEX fees (taken from trade amount)
    4. Gas price changes (affects profitability)
    """

    def __init__(
        self,
        max_slippage_percent: Decimal = Decimal("0.005"),  # 0.5%
        max_price_impact_percent: Decimal = Decimal("0.01"),  # 1%
    ):
        """
        Initialize slippage protection.

        Args:
            max_slippage_percent: Maximum acceptable slippage (default 0.5%)
            max_price_impact_percent: Maximum acceptable price impact (default 1%)
        """
        self.max_slippage = max_slippage_percent
        self.max_price_impact = max_price_impact_percent

        logger.info(
            f"SlippageProtection initialized: max_slippage={max_slippage_percent:.2%}, "
            f"max_impact={max_price_impact_percent:.2%}"
        )

    def calculate_minimum_output(
        self, expected_output: Decimal, slippage_tolerance: Optional[Decimal] = None
    ) -> Decimal:
        """
        Calculate minimum acceptable output amount.

        Args:
            expected_output: Expected output amount
            slippage_tolerance: Slippage tolerance (uses default if None)

        Returns:
            Minimum acceptable output
        """
        tolerance = slippage_tolerance or self.max_slippage

        minimum = expected_output * (Decimal("1") - tolerance)

        logger.debug(
            f"Minimum output: {minimum:.6f} (expected: {expected_output:.6f}, "
            f"tolerance: {tolerance:.2%})"
        )

        return minimum

    def validate_execution_price(
        self,
        expected_price: Decimal,
        actual_price: Decimal,
        tolerance: Optional[Decimal] = None,
    ) -> Tuple[bool, Decimal]:
        """
        Validate actual execution price is within tolerance.

        Args:
            expected_price: Expected price
            actual_price: Actual execution price
            tolerance: Acceptable deviation (uses default if None)

        Returns:
            Tuple of (valid: bool, slippage_percent: Decimal)
        """
        tolerance = tolerance or self.max_slippage

        # Calculate slippage percentage
        if expected_price == 0:
            return False, Decimal("100")

        slippage = abs(actual_price - expected_price) / expected_price

        valid = slippage <= tolerance

        logger.debug(
            f"Price validation: expected={expected_price:.6f}, "
            f"actual={actual_price:.6f}, slippage={slippage:.2%}, "
            f"valid={valid}"
        )

        return valid, slippage

    def estimate_price_impact(
        self,
        trade_amount: Decimal,
        pool_liquidity: Decimal,
        constant_product: bool = True,
    ) -> Decimal:
        """
        Estimate price impact of a trade.

        Uses constant product formula (x * y = k) for AMM pools.

        Args:
            trade_amount: Amount being traded
            pool_liquidity: Available pool liquidity
            constant_product: Whether pool uses constant product (Uniswap-style)

        Returns:
            Estimated price impact as percentage
        """
        if pool_liquidity == 0:
            logger.warning("Zero pool liquidity, assuming 100% price impact")
            return Decimal("100")

        if constant_product:
            # Constant product formula: impact = amount / (liquidity + amount)
            impact = trade_amount / (pool_liquidity + trade_amount)
        else:
            # Simple proportional model
            impact = trade_amount / pool_liquidity

        impact_percent = impact * 100

        logger.debug(
            f"Price impact estimate: {impact_percent:.2%} "
            f"(amount={trade_amount}, liquidity={pool_liquidity})"
        )

        return impact_percent

    def check_slippage_acceptable(
        self, expected_price: Decimal, actual_price: Decimal, estimated_impact: Decimal
    ) -> Tuple[bool, str]:
        """
        Check if total slippage is acceptable.

        Args:
            expected_price: Expected price
            actual_price: Actual price
            estimated_impact: Estimated price impact percentage

        Returns:
            Tuple of (acceptable: bool, reason: str)
        """
        # Check execution slippage
        valid_price, slippage = self.validate_execution_price(
            expected_price, actual_price
        )

        if not valid_price:
            return (
                False,
                f"Execution slippage {slippage:.2%} exceeds max {self.max_slippage:.2%}",
            )

        # Check price impact
        if estimated_impact > self.max_price_impact * 100:
            return (
                False,
                f"Price impact {estimated_impact:.2%} exceeds max {self.max_price_impact:.2%}",
            )

        return True, "Slippage within acceptable limits"

    def calculate_safe_trade_amount(
        self,
        desired_amount: Decimal,
        pool_liquidity: Decimal,
        target_impact: Optional[Decimal] = None,
    ) -> Decimal:
        """
        Calculate safe trade amount to stay within price impact limits.

        Args:
            desired_amount: Amount trader wants to trade
            pool_liquidity: Available pool liquidity
            target_impact: Target price impact (uses max if None)

        Returns:
            Safe trade amount
        """
        target = target_impact or self.max_price_impact

        # Using constant product: impact = amount / (liquidity + amount)
        # Solve for amount: amount = (liquidity * impact) / (1 - impact)
        safe_amount = (pool_liquidity * target) / (Decimal("1") - target)

        # Never exceed desired amount
        safe_amount = min(safe_amount, desired_amount)

        # Never exceed 10% of liquidity (safety margin)
        safe_amount = min(safe_amount, pool_liquidity * Decimal("0.10"))

        logger.info(
            f"Safe amount calculation: desired={desired_amount:.6f}, "
            f"safe={safe_amount:.6f}, liquidity={pool_liquidity:.6f}"
        )

        return safe_amount

    def analyze_slippage_budget(
        self,
        expected_buy_price: Decimal,
        expected_sell_price: Decimal,
        buy_pool_liquidity: Decimal,
        sell_pool_liquidity: Decimal,
        amount: Decimal,
    ) -> SlippageAnalysis:
        """
        Analyze complete slippage budget for an arbitrage trade.

        Args:
            expected_buy_price: Expected price on buy DEX
            expected_sell_price: Expected price on sell DEX
            buy_pool_liquidity: Buy pool liquidity
            sell_pool_liquidity: Sell pool liquidity
            amount: Trade amount

        Returns:
            SlippageAnalysis with complete breakdown
        """
        # Estimate price impacts
        buy_impact = self.estimate_price_impact(amount, buy_pool_liquidity)
        sell_impact = self.estimate_price_impact(amount, sell_pool_liquidity)

        total_impact = buy_impact + sell_impact

        # Calculate adjusted prices after impact
        adjusted_buy_price = expected_buy_price * (Decimal("1") + buy_impact / 100)
        adjusted_sell_price = expected_sell_price * (Decimal("1") - sell_impact / 100)

        # Calculate minimum acceptable prices with slippage tolerance
        min_sell_price = self.calculate_minimum_output(
            adjusted_sell_price, self.max_slippage
        )

        # Total slippage budget
        total_slippage = self.max_slippage + (total_impact / 100)

        # Recommended max amount
        min_liquidity = min(buy_pool_liquidity, sell_pool_liquidity)
        recommended_max = self.calculate_safe_trade_amount(amount, min_liquidity)

        analysis = SlippageAnalysis(
            expected_price=expected_sell_price,
            minimum_acceptable_price=min_sell_price,
            maximum_slippage_percent=self.max_slippage,
            estimated_price_impact=total_impact,
            total_slippage_budget=total_slippage * 100,
            recommended_max_amount=recommended_max,
        )

        logger.info(
            f"Slippage analysis: buy_impact={buy_impact:.2%}, "
            f"sell_impact={sell_impact:.2%}, total_budget={total_slippage:.2%}, "
            f"recommended_max={recommended_max:.6f}"
        )

        return analysis

    def validate_arbitrage_slippage(
        self,
        buy_price: Decimal,
        sell_price: Decimal,
        expected_profit: Decimal,
        estimated_total_impact: Decimal,
    ) -> Tuple[bool, Decimal]:
        """
        Validate arbitrage opportunity accounts for slippage.

        Args:
            buy_price: Buy price
            sell_price: Sell price
            expected_profit: Expected profit
            estimated_total_impact: Total estimated price impact

        Returns:
            Tuple of (profitable_after_slippage: bool, net_profit: Decimal)
        """
        # Adjust for price impact
        impact_cost = (buy_price + sell_price) * (estimated_total_impact / 100)

        # Adjust for slippage tolerance
        slippage_cost = (buy_price + sell_price) * self.max_slippage

        # Calculate net profit after all slippage costs
        net_profit = expected_profit - impact_cost - slippage_cost

        profitable = net_profit > 0

        logger.debug(
            f"Arbitrage slippage validation: expected_profit={expected_profit:.6f}, "
            f"impact_cost={impact_cost:.6f}, slippage_cost={slippage_cost:.6f}, "
            f"net_profit={net_profit:.6f}, profitable={profitable}"
        )

        return profitable, net_profit


def get_slippage_protection(
    max_slippage: Decimal = Decimal("0.005"),
    max_price_impact: Decimal = Decimal("0.01"),
) -> SlippageProtection:
    """
    Factory function to create SlippageProtection instance.

    Args:
        max_slippage: Maximum slippage tolerance
        max_price_impact: Maximum price impact tolerance

    Returns:
        SlippageProtection instance
    """
    return SlippageProtection(max_slippage, max_price_impact)
