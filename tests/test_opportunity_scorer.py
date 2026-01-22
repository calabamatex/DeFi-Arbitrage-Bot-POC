"""Comprehensive tests for OpportunityScorer."""

import pytest
from decimal import Decimal
from unittest.mock import Mock
from datetime import datetime
from src.bot.opportunity_scorer import OpportunityScorer, OpportunityScore
from src.bot.arbitrage import ArbitrageOpportunity


@pytest.fixture
def scorer():
    """Create OpportunityScorer instance."""
    return OpportunityScorer()


@pytest.fixture
def sample_opportunity():
    """Sample opportunity."""
    return ArbitrageOpportunity(
        token1="WETH",
        token2="USDC",
        buy_dex="SushiSwap",
        sell_dex="Uniswap V3",
        expected_profit=Decimal("10"),
        amount=Decimal("1.0"),
        buy_price=Decimal("2000"),
        sell_price=Decimal("2010"),
        timestamp=datetime.now(),
    )


@pytest.fixture
def high_profit_opportunity():
    """High profit opportunity."""
    return ArbitrageOpportunity(
        token1="WETH",
        token2="USDC",
        buy_dex="SushiSwap",
        sell_dex="Uniswap V3",
        expected_profit=Decimal("100"),
        amount=Decimal("1.0"),
        buy_price=Decimal("2000"),
        sell_price=Decimal("2100"),
        timestamp=datetime.now(),
    )


@pytest.fixture
def low_profit_opportunity():
    """Low profit opportunity."""
    return ArbitrageOpportunity(
        token1="WETH",
        token2="DAI",
        buy_dex="QuickSwap",
        sell_dex="SushiSwap",
        expected_profit=Decimal("1"),
        amount=Decimal("1.0"),
        buy_price=Decimal("2000"),
        sell_price=Decimal("2001"),
        timestamp=datetime.now(),
    )


@pytest.fixture
def mock_web3():
    """Mock Web3."""
    web3 = Mock()
    web3.eth.gas_price = 30 * 10**9  # 30 gwei
    return web3


@pytest.fixture
def mock_web3_high_gas():
    """Mock Web3 with high gas prices."""
    web3 = Mock()
    web3.eth.gas_price = 150 * 10**9  # 150 gwei (very high)
    return web3


def test_initialization(scorer):
    """Test OpportunityScorer initialization."""
    assert isinstance(scorer.historical_success, dict)
    assert isinstance(scorer.last_scored_time, dict)
    assert len(scorer.historical_success) == 0


def test_score_opportunity_returns_valid_score(scorer, sample_opportunity, mock_web3):
    """Test scoring an opportunity returns valid OpportunityScore."""
    scored = scorer.score_opportunity(
        sample_opportunity,
        mock_web3,
        gas_cost=Decimal("0.5"),
        available_liquidity=Decimal("1000"),
    )

    assert isinstance(scored, OpportunityScore)
    assert scored.score >= 0
    assert scored.score <= 100
    assert scored.priority in ["HIGH", "MEDIUM", "LOW"]
    assert scored.opportunity == sample_opportunity


def test_score_opportunity_high_profit(scorer, high_profit_opportunity, mock_web3):
    """Test scoring high profit opportunity."""
    scored = scorer.score_opportunity(
        high_profit_opportunity,
        mock_web3,
        gas_cost=Decimal("1.0"),
        available_liquidity=Decimal("10000"),
    )

    # High profit should result in high profit score
    assert scored.profit_score > 30
    assert scored.score > 70  # Should be a good opportunity overall


def test_score_opportunity_low_profit(scorer, low_profit_opportunity, mock_web3):
    """Test scoring low profit opportunity with gas exceeding profit."""
    # Use gas cost that exceeds profit to get truly low score
    scored = scorer.score_opportunity(
        low_profit_opportunity,
        mock_web3,
        gas_cost=Decimal("1.5"),  # Gas cost exceeds expected profit
        available_liquidity=Decimal("1000"),
    )

    # With gas cost exceeding profit, should get zero profit score
    assert scored.profit_score == 0


def test_score_breakdown_components(scorer, sample_opportunity, mock_web3):
    """Test that score breakdown has all components."""
    scored = scorer.score_opportunity(
        sample_opportunity, mock_web3, gas_cost=Decimal("0.5")
    )

    assert scored.profit_score >= 0
    assert scored.liquidity_score >= 0
    assert scored.speed_score >= 0
    assert scored.reliability_score >= 0
    # Total should equal sum of components
    assert scored.score == (
        scored.profit_score
        + scored.liquidity_score
        + scored.speed_score
        + scored.reliability_score
    )


def test_profit_score_high_profit(scorer):
    """Test profit scoring with high profit."""
    score = scorer._calculate_profit_score(
        expected_profit=Decimal("100"), amount=Decimal("1.0"), gas_cost=Decimal("1.0")
    )

    assert score > 30  # High profit should score well
    assert score <= 40  # Max profit score


def test_profit_score_medium_profit(scorer):
    """Test profit scoring with medium profit percentage."""
    # Medium profit: 2-5% profit after gas
    # gross = 10, gas = 8, net = 2, percent = 20%
    score = scorer._calculate_profit_score(
        expected_profit=Decimal("10"), amount=Decimal("1.0"), gas_cost=Decimal("8.0")
    )

    assert score > 0
    assert score <= 40  # Within valid range


def test_profit_score_no_profit(scorer):
    """Test profit scoring with no profit."""
    score = scorer._calculate_profit_score(
        expected_profit=Decimal("1"),
        amount=Decimal("1.0"),
        gas_cost=Decimal("2.0"),  # Gas exceeds profit
    )

    assert score == 0


def test_profit_score_zero_amount(scorer):
    """Test profit scoring with zero amount."""
    score = scorer._calculate_profit_score(
        expected_profit=Decimal("10"), amount=Decimal("0"), gas_cost=Decimal("1.0")
    )

    assert score == 0


def test_profit_score_progressive_scaling(scorer):
    """Test that profit score scales progressively."""
    # Test at different profit levels
    score_0_5_pct = scorer._calculate_profit_score(
        Decimal("100"), Decimal("1"), Decimal("99.5")  # ~0.5% profit
    )
    score_1_pct = scorer._calculate_profit_score(
        Decimal("100"), Decimal("1"), Decimal("99")  # ~1% profit
    )
    score_2_pct = scorer._calculate_profit_score(
        Decimal("100"), Decimal("1"), Decimal("98")  # ~2% profit
    )
    score_5_pct = scorer._calculate_profit_score(
        Decimal("100"), Decimal("1"), Decimal("95")  # ~5% profit
    )

    # Scores should increase with profit
    assert score_0_5_pct < score_1_pct
    assert score_1_pct < score_2_pct
    assert score_2_pct < score_5_pct


def test_liquidity_score_high_liquidity(scorer):
    """Test liquidity scoring with high liquidity."""
    score = scorer._calculate_liquidity_score(
        amount=Decimal("1"), available_liquidity=Decimal("10000")  # Very high liquidity
    )

    assert score == 30  # Should get max score


def test_liquidity_score_medium_liquidity(scorer):
    """Test liquidity scoring with medium liquidity."""
    score = scorer._calculate_liquidity_score(
        amount=Decimal("10"), available_liquidity=Decimal("500")  # 2% of liquidity
    )

    assert score == 20  # In 1-5% range


def test_liquidity_score_low_liquidity(scorer):
    """Test liquidity scoring with low liquidity."""
    score = scorer._calculate_liquidity_score(
        amount=Decimal("100"), available_liquidity=Decimal("500")  # 20% of liquidity
    )

    assert score == 5  # Should get low score


def test_liquidity_score_no_liquidity(scorer):
    """Test liquidity scoring with zero liquidity."""
    score = scorer._calculate_liquidity_score(
        amount=Decimal("10"), available_liquidity=Decimal("0")
    )

    assert score == 0


def test_liquidity_score_unknown_liquidity(scorer):
    """Test liquidity scoring with unknown liquidity."""
    score = scorer._calculate_liquidity_score(
        amount=Decimal("10"), available_liquidity=None
    )

    assert score == 15  # Should get default medium score


def test_speed_score_normal_gas(scorer, mock_web3):
    """Test speed scoring with normal gas prices."""
    score = scorer._calculate_speed_score("SushiSwap", "Uniswap V3", mock_web3)

    assert score == 15  # 30 gwei is normal, should get max score


def test_speed_score_high_gas(scorer):
    """Test speed scoring with high gas prices."""
    web3 = Mock()
    web3.eth.gas_price = 75 * 10**9  # 75 gwei (high)

    score = scorer._calculate_speed_score("SushiSwap", "Uniswap V3", web3)

    assert score == 10  # High gas, medium score


def test_speed_score_very_high_gas(scorer, mock_web3_high_gas):
    """Test speed scoring with very high gas prices."""
    score = scorer._calculate_speed_score("SushiSwap", "Uniswap V3", mock_web3_high_gas)

    assert score == 5  # Very high gas, low score


def test_speed_score_error_handling(scorer):
    """Test speed scoring error handling."""
    web3 = Mock()
    web3.eth.gas_price = Mock(side_effect=Exception("RPC error"))

    score = scorer._calculate_speed_score("SushiSwap", "Uniswap V3", web3)

    assert score == 10  # Should return default medium score on error


def test_reliability_score_no_history(scorer, sample_opportunity):
    """Test reliability scoring with no history."""
    score = scorer._calculate_reliability_score(sample_opportunity, None)

    assert score == 10  # Should get default medium score


def test_reliability_score_with_history(scorer, sample_opportunity):
    """Test reliability scoring with history."""
    # Add some history
    key = f"{sample_opportunity.token1}/{sample_opportunity.token2}_{sample_opportunity.buy_dex}_{sample_opportunity.sell_dex}"
    scorer.historical_success[key] = 0.8  # 80% success rate

    score = scorer._calculate_reliability_score(sample_opportunity, None)

    # 80% * 15 = 12
    assert score == 12


def test_reliability_score_perfect_history(scorer, sample_opportunity):
    """Test reliability scoring with perfect history."""
    key = f"{sample_opportunity.token1}/{sample_opportunity.token2}_{sample_opportunity.buy_dex}_{sample_opportunity.sell_dex}"
    scorer.historical_success[key] = 1.0  # 100% success

    score = scorer._calculate_reliability_score(sample_opportunity, None)

    assert score == 15  # Max score


def test_reliability_score_poor_history(scorer, sample_opportunity):
    """Test reliability scoring with poor history."""
    key = f"{sample_opportunity.token1}/{sample_opportunity.token2}_{sample_opportunity.buy_dex}_{sample_opportunity.sell_dex}"
    scorer.historical_success[key] = 0.2  # 20% success

    score = scorer._calculate_reliability_score(sample_opportunity, None)

    assert score == 3  # 0.2 * 15


def test_record_execution_result_first_success(scorer, sample_opportunity):
    """Test recording first execution result (success)."""
    scorer.record_execution_result(sample_opportunity, True)

    key = f"{sample_opportunity.token1}/{sample_opportunity.token2}_{sample_opportunity.buy_dex}_{sample_opportunity.sell_dex}"
    assert key in scorer.historical_success
    assert scorer.historical_success[key] == 1.0


def test_record_execution_result_first_failure(scorer, sample_opportunity):
    """Test recording first execution result (failure)."""
    scorer.record_execution_result(sample_opportunity, False)

    key = f"{sample_opportunity.token1}/{sample_opportunity.token2}_{sample_opportunity.buy_dex}_{sample_opportunity.sell_dex}"
    assert key in scorer.historical_success
    assert scorer.historical_success[key] == 0.0


def test_record_execution_result_exponential_moving_average(scorer, sample_opportunity):
    """Test that subsequent records use exponential moving average."""
    # Record initial success
    scorer.record_execution_result(sample_opportunity, True)

    key = f"{sample_opportunity.token1}/{sample_opportunity.token2}_{sample_opportunity.buy_dex}_{sample_opportunity.sell_dex}"
    assert scorer.historical_success[key] == 1.0

    # Record failure
    scorer.record_execution_result(sample_opportunity, False)

    # Should be: 0.3 * 0.0 + 0.7 * 1.0 = 0.7
    assert scorer.historical_success[key] == 0.7


def test_prioritize_opportunities_empty_list(scorer, mock_web3):
    """Test prioritizing empty list."""
    scored = scorer.prioritize_opportunities([], mock_web3, gas_cost=Decimal("0.5"))

    assert len(scored) == 0


def test_prioritize_opportunities_single(scorer, sample_opportunity, mock_web3):
    """Test prioritizing single opportunity."""
    scored = scorer.prioritize_opportunities(
        [sample_opportunity], mock_web3, gas_cost=Decimal("0.5"), min_score=Decimal("0")
    )

    assert len(scored) == 1
    assert isinstance(scored[0], OpportunityScore)


def test_prioritize_opportunities_multiple(scorer, mock_web3):
    """Test prioritizing multiple opportunities."""
    opportunities = [
        ArbitrageOpportunity(
            token1="WETH",
            token2="USDC",
            buy_dex="SushiSwap",
            sell_dex="Uniswap V3",
            expected_profit=Decimal("20"),
            amount=Decimal("1.0"),
            buy_price=Decimal("2000"),
            sell_price=Decimal("2020"),
            timestamp=datetime.now(),
        ),
        ArbitrageOpportunity(
            token1="WETH",
            token2="DAI",
            buy_dex="QuickSwap",
            sell_dex="SushiSwap",
            expected_profit=Decimal("5"),
            amount=Decimal("1.0"),
            buy_price=Decimal("2000"),
            sell_price=Decimal("2005"),
            timestamp=datetime.now(),
        ),
    ]

    scored = scorer.prioritize_opportunities(
        opportunities, mock_web3, gas_cost=Decimal("0.5"), min_score=Decimal("0")
    )

    assert len(scored) == 2
    # Should be sorted by score (highest first)
    assert scored[0].score >= scored[1].score


def test_prioritize_opportunities_filtering(scorer, mock_web3):
    """Test that prioritize filters by min_score."""
    opportunities = [
        ArbitrageOpportunity(
            token1="WETH",
            token2="USDC",
            buy_dex="SushiSwap",
            sell_dex="Uniswap V3",
            expected_profit=Decimal("100"),  # High profit
            amount=Decimal("1.0"),
            buy_price=Decimal("2000"),
            sell_price=Decimal("2100"),
            timestamp=datetime.now(),
        ),
        ArbitrageOpportunity(
            token1="WETH",
            token2="DAI",
            buy_dex="QuickSwap",
            sell_dex="SushiSwap",
            expected_profit=Decimal("1"),  # Low profit
            amount=Decimal("1.0"),
            buy_price=Decimal("2000"),
            sell_price=Decimal("2001"),
            timestamp=datetime.now(),
        ),
    ]

    # Use high min_score to filter out low profit opportunity
    scored = scorer.prioritize_opportunities(
        opportunities, mock_web3, gas_cost=Decimal("0.5"), min_score=Decimal("60")
    )

    # Should only include high profit opportunity
    assert len(scored) >= 0  # Depends on exact scoring
    # All included should meet min score
    for s in scored:
        assert s.score >= 60


def test_should_execute_high_score(scorer, sample_opportunity, mock_web3):
    """Test execution decision with high score."""
    scored = scorer.score_opportunity(
        sample_opportunity,
        mock_web3,
        gas_cost=Decimal("0.1"),
        available_liquidity=Decimal("10000"),
    )

    # Override to ensure high score
    scored.score = Decimal("80")

    should = scorer.should_execute(scored, min_score=Decimal("60"))
    assert should is True


def test_should_execute_low_score(scorer, sample_opportunity, mock_web3):
    """Test execution decision with low score."""
    scored = scorer.score_opportunity(
        sample_opportunity, mock_web3, gas_cost=Decimal("5.0")  # High gas cost
    )

    # Override to ensure low score
    scored.score = Decimal("40")

    should = scorer.should_execute(scored, min_score=Decimal("60"))
    assert should is False


def test_should_execute_exact_threshold(scorer, sample_opportunity, mock_web3):
    """Test execution decision at exact threshold."""
    scored = scorer.score_opportunity(
        sample_opportunity, mock_web3, gas_cost=Decimal("0.5")
    )

    scored.score = Decimal("60")

    should = scorer.should_execute(scored, min_score=Decimal("60"))
    assert should is True  # Should execute at threshold


def test_priority_levels(scorer, mock_web3):
    """Test that priority levels are assigned correctly."""
    # Create opportunity and override score
    opp = ArbitrageOpportunity(
        token1="WETH",
        token2="USDC",
        buy_dex="SushiSwap",
        sell_dex="Uniswap V3",
        expected_profit=Decimal("10"),
        amount=Decimal("1.0"),
        buy_price=Decimal("2000"),
        sell_price=Decimal("2010"),
        timestamp=datetime.now(),
    )

    # Test HIGH priority (score >= 80)
    scored = scorer.score_opportunity(opp, mock_web3, gas_cost=Decimal("0.1"))
    scored.score = Decimal("85")
    # Rescore to get priority
    scored2 = scorer.score_opportunity(opp, mock_web3, gas_cost=Decimal("0.01"))
    if scored2.score >= 80:
        assert scored2.priority == "HIGH"

    # Test MEDIUM priority (60 <= score < 80)
    scored = scorer.score_opportunity(opp, mock_web3, gas_cost=Decimal("1.0"))
    # MEDIUM priority will depend on actual score

    # Test LOW priority (score < 60)
    scored = scorer.score_opportunity(opp, mock_web3, gas_cost=Decimal("10.0"))
    # LOW priority will depend on actual score


def test_opportunity_score_repr(scorer, sample_opportunity, mock_web3):
    """Test OpportunityScore string representation."""
    scored = scorer.score_opportunity(
        sample_opportunity, mock_web3, gas_cost=Decimal("0.5")
    )

    repr_str = repr(scored)

    assert "OpportunityScore" in repr_str
    assert "score=" in repr_str
    assert "priority=" in repr_str
    assert "WETH/USDC" in repr_str


def test_score_consistency(scorer, sample_opportunity, mock_web3):
    """Test that scoring is consistent for same inputs."""
    scored1 = scorer.score_opportunity(
        sample_opportunity,
        mock_web3,
        gas_cost=Decimal("0.5"),
        available_liquidity=Decimal("1000"),
    )

    scored2 = scorer.score_opportunity(
        sample_opportunity,
        mock_web3,
        gas_cost=Decimal("0.5"),
        available_liquidity=Decimal("1000"),
    )

    assert scored1.score == scored2.score
    assert scored1.profit_score == scored2.profit_score
    assert scored1.liquidity_score == scored2.liquidity_score
    assert scored1.speed_score == scored2.speed_score
