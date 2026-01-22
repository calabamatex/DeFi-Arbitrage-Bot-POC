"""
Opportunity Scorer - Scores and prioritizes arbitrage opportunities.
"""

from decimal import Decimal
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from web3 import Web3
import logging

# Import from arbitrage module
from .arbitrage import ArbitrageOpportunity

logger = logging.getLogger(__name__)


@dataclass
class OpportunityScore:
    """Scored arbitrage opportunity."""

    opportunity: ArbitrageOpportunity
    score: Decimal
    profit_score: Decimal
    liquidity_score: Decimal
    speed_score: Decimal
    reliability_score: Decimal
    priority: str  # HIGH, MEDIUM, LOW

    def __repr__(self):
        return (
            f"OpportunityScore(score={self.score:.2f}, "
            f"priority={self.priority}, "
            f"pair={self.opportunity.token1}/{self.opportunity.token2})"
        )


class OpportunityScorer:
    """
    Scores arbitrage opportunities based on multiple factors.

    Factors considered:
    - Expected profit (higher = better)
    - Gas cost efficiency (profit/gas ratio)
    - Liquidity depth (can we execute?)
    - Execution speed (how fast can we do this?)
    - Historical success rate
    - Network congestion
    """

    def __init__(self):
        """Initialize opportunity scorer."""
        self.historical_success: Dict[
            str, float
        ] = {}  # Track success by pair/dex combo
        self.last_scored_time: Dict[
            str, datetime
        ] = {}  # Track when opportunities were last scored

        logger.info("OpportunityScorer initialized")

    def score_opportunity(
        self,
        opportunity: ArbitrageOpportunity,
        web3: Web3,
        gas_cost: Decimal,
        available_liquidity: Optional[Decimal] = None,
        historical_data: Optional[Dict] = None,
    ) -> OpportunityScore:
        """
        Score an arbitrage opportunity.

        Args:
            opportunity: ArbitrageOpportunity to score
            web3: Web3 instance
            gas_cost: Estimated gas cost in USD
            available_liquidity: Available liquidity (if known)
            historical_data: Historical performance data

        Returns:
            OpportunityScore with detailed breakdown
        """
        logger.debug(f"Scoring opportunity: {opportunity.token1}/{opportunity.token2}")

        # 1. Profit Score (0-40 points)
        # Higher profit = higher score
        profit_score = self._calculate_profit_score(
            opportunity.expected_profit, opportunity.amount, gas_cost
        )

        # 2. Liquidity Score (0-30 points)
        # Can we execute without major price impact?
        liquidity_score = self._calculate_liquidity_score(
            opportunity.amount, available_liquidity
        )

        # 3. Speed Score (0-15 points)
        # How fast can we execute?
        speed_score = self._calculate_speed_score(
            opportunity.buy_dex, opportunity.sell_dex, web3
        )

        # 4. Reliability Score (0-15 points)
        # Historical success rate
        reliability_score = self._calculate_reliability_score(
            opportunity, historical_data
        )

        # Total score (0-100)
        total_score = profit_score + liquidity_score + speed_score + reliability_score

        # Determine priority
        if total_score >= 80:
            priority = "HIGH"
        elif total_score >= 60:
            priority = "MEDIUM"
        else:
            priority = "LOW"

        scored = OpportunityScore(
            opportunity=opportunity,
            score=total_score,
            profit_score=profit_score,
            liquidity_score=liquidity_score,
            speed_score=speed_score,
            reliability_score=reliability_score,
            priority=priority,
        )

        logger.info(
            f"Scored {opportunity.token1}/{opportunity.token2}: "
            f"{total_score:.2f}/100 ({priority}) - "
            f"Profit:{profit_score:.1f}, Liquidity:{liquidity_score:.1f}, "
            f"Speed:{speed_score:.1f}, Reliability:{reliability_score:.1f}"
        )

        return scored

    def _calculate_profit_score(
        self, expected_profit: Decimal, amount: Decimal, gas_cost: Decimal
    ) -> Decimal:
        """
        Calculate profit score (0-40 points).

        Args:
            expected_profit: Expected profit amount
            amount: Trade amount
            gas_cost: Gas cost in USD

        Returns:
            Profit score
        """
        # Calculate net profit
        gross_profit_usd = expected_profit * amount
        net_profit = gross_profit_usd - gas_cost

        # Calculate profit percentage
        if amount > 0 and expected_profit * amount > 0:
            profit_percent = (net_profit / (expected_profit * amount)) * 100
        else:
            profit_percent = Decimal("0")

        # Score based on profit percentage
        # 0% = 0 points
        # 1% = 20 points
        # 2% = 30 points
        # 5%+ = 40 points
        if profit_percent <= 0:
            score = Decimal("0")
        elif profit_percent < 1:
            score = profit_percent * 20
        elif profit_percent < 2:
            score = 20 + (profit_percent - 1) * 10
        elif profit_percent < 5:
            score = 30 + (profit_percent - 2) * Decimal("3.33")
        else:
            score = Decimal("40")

        return min(score, Decimal("40"))

    def _calculate_liquidity_score(
        self, amount: Decimal, available_liquidity: Optional[Decimal]
    ) -> Decimal:
        """
        Calculate liquidity score (0-30 points).

        Args:
            amount: Trade amount
            available_liquidity: Available liquidity

        Returns:
            Liquidity score
        """
        if available_liquidity is None:
            # Unknown liquidity, give medium score
            return Decimal("15")

        if available_liquidity == 0:
            return Decimal("0")

        # Calculate liquidity ratio
        liquidity_ratio = amount / available_liquidity

        # Score based on liquidity ratio
        # <1% of liquidity = 30 points
        # 1-5% = 20 points
        # 5-10% = 10 points
        # >10% = 5 points
        if liquidity_ratio < Decimal("0.01"):
            score = Decimal("30")
        elif liquidity_ratio < Decimal("0.05"):
            score = Decimal("20")
        elif liquidity_ratio < Decimal("0.10"):
            score = Decimal("10")
        else:
            score = Decimal("5")

        return score

    def _calculate_speed_score(
        self, buy_dex: str, sell_dex: str, web3: Web3
    ) -> Decimal:
        """
        Calculate speed score (0-15 points).

        Args:
            buy_dex: DEX to buy from
            sell_dex: DEX to sell on
            web3: Web3 instance

        Returns:
            Speed score
        """
        # Check network congestion
        try:
            gas_price = web3.eth.gas_price

            # Normal gas: 30-50 gwei = 15 points
            # High gas: 50-100 gwei = 10 points
            # Very high gas: 100+ gwei = 5 points
            gas_gwei = gas_price / 10**9

            if gas_gwei < 50:
                score = Decimal("15")
            elif gas_gwei < 100:
                score = Decimal("10")
            else:
                score = Decimal("5")

        except Exception as e:
            logger.error(f"Error checking gas price: {e}")
            score = Decimal("10")  # Default medium score

        return score

    def _calculate_reliability_score(
        self, opportunity: ArbitrageOpportunity, historical_data: Optional[Dict]
    ) -> Decimal:
        """
        Calculate reliability score (0-15 points).

        Args:
            opportunity: ArbitrageOpportunity
            historical_data: Historical success data

        Returns:
            Reliability score
        """
        # Create key for this pair/dex combination
        key = f"{opportunity.token1}/{opportunity.token2}_{opportunity.buy_dex}_{opportunity.sell_dex}"

        if key in self.historical_success:
            success_rate = self.historical_success[key]
            # 100% success = 15 points
            # 50% success = 7.5 points
            # 0% success = 0 points
            score = Decimal(str(success_rate)) * 15
        else:
            # No history, give medium score
            score = Decimal("10")

        return min(score, Decimal("15"))

    def record_execution_result(self, opportunity: ArbitrageOpportunity, success: bool):
        """
        Record execution result for future scoring.

        Args:
            opportunity: Executed opportunity
            success: Whether execution succeeded
        """
        key = f"{opportunity.token1}/{opportunity.token2}_{opportunity.buy_dex}_{opportunity.sell_dex}"

        if key not in self.historical_success:
            self.historical_success[key] = 1.0 if success else 0.0
        else:
            # Exponential moving average
            alpha = 0.3  # Weight for new observation
            old_rate = self.historical_success[key]
            new_value = 1.0 if success else 0.0
            self.historical_success[key] = alpha * new_value + (1 - alpha) * old_rate

        logger.info(
            f"Updated success rate for {key}: " f"{self.historical_success[key]:.2%}"
        )

    def prioritize_opportunities(
        self,
        opportunities: List[ArbitrageOpportunity],
        web3: Web3,
        gas_cost: Decimal,
        min_score: Decimal = Decimal("50"),
    ) -> List[OpportunityScore]:
        """
        Score and prioritize multiple opportunities.

        Args:
            opportunities: List of opportunities to score
            web3: Web3 instance
            gas_cost: Gas cost estimate
            min_score: Minimum score to include

        Returns:
            List of OpportunityScore, sorted by score (highest first)
        """
        logger.info(f"Prioritizing {len(opportunities)} opportunities")

        scored_opportunities = []

        for opp in opportunities:
            scored = self.score_opportunity(opp, web3, gas_cost)

            # Only include if meets minimum score
            if scored.score >= min_score:
                scored_opportunities.append(scored)

        # Sort by score (highest first)
        scored_opportunities.sort(key=lambda x: x.score, reverse=True)

        logger.info(
            f"Filtered to {len(scored_opportunities)} opportunities "
            f"meeting min score {min_score}"
        )

        return scored_opportunities

    def should_execute(
        self, scored_opportunity: OpportunityScore, min_score: Decimal = Decimal("60")
    ) -> bool:
        """
        Determine if opportunity should be executed.

        Args:
            scored_opportunity: Scored opportunity
            min_score: Minimum score required

        Returns:
            True if should execute, False otherwise
        """
        should_exec = scored_opportunity.score >= min_score

        logger.debug(
            f"Execution decision for {scored_opportunity.opportunity.token1}/"
            f"{scored_opportunity.opportunity.token2}: "
            f"score={scored_opportunity.score:.2f}, "
            f"min={min_score}, execute={should_exec}"
        )

        return should_exec
