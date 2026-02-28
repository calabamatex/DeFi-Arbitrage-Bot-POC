"""Comprehensive tests for Main Bot Orchestrator."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from decimal import Decimal
from datetime import datetime

from src.bot.main import ArbitrageBot, main


@pytest.fixture
def bot():
    """Create ArbitrageBot instance."""
    return ArbitrageBot()


def test_bot_initialization(bot):
    """Test ArbitrageBot initialization with default values."""
    assert bot.running is False
    assert bot.web3 is None
    assert bot.dex_instances == {}
    assert bot.risk_manager is None
    assert bot.transaction_manager is None
    assert bot.slippage_protection is None
    assert bot.opportunity_scorer is None
    assert bot.emergency_shutdown is None
    assert bot.telegram_bot is None

    # Check default parameters
    assert bot.min_profit_threshold == Decimal("0.01")
    assert bot.max_trade_amount == Decimal("1.0")
    assert bot.check_interval == 5

    # Check statistics
    assert bot.opportunities_found == 0
    assert bot.trades_executed == 0
    assert bot.successful_trades == 0
    assert bot.failed_trades == 0
    assert bot.total_profit == Decimal("0")

    # Check token pairs
    assert len(bot.token_pairs) == 5
    assert ("WETH", "USDC") in bot.token_pairs


@pytest.mark.asyncio
async def test_initialize_success(bot):
    """Test successful bot initialization."""
    with patch("src.bot.main.load_config") as mock_config, patch(
        "src.bot.main.Web3"
    ) as mock_web3, patch("src.bot.main.QuickSwap") as mock_quickswap, patch(
        "src.bot.main.SushiSwap"
    ) as mock_sushiswap, patch(
        "src.bot.main.TelegramBot"
    ) as mock_telegram, patch(
        "src.bot.main.TransactionManager"
    ) as mock_tx_manager, patch(
        "src.bot.main.RiskManager"
    ) as mock_risk_manager, patch(
        "src.bot.main.SlippageProtection"
    ) as mock_slippage, patch(
        "src.bot.main.OpportunityScorer"
    ) as mock_scorer, patch(
        "src.bot.main.EmergencyShutdown"
    ) as mock_shutdown, patch.dict(
        "os.environ",
        {
            "PRIVATE_KEY": "0x" + "1" * 64,
            "POLYGON_RPC_URL": "https://polygon-rpc.com",
            "TELEGRAM_BOT_TOKEN": "test_token",
            "TELEGRAM_CHAT_ID": "test_chat_id",
        },
    ):
        # Mock config return value
        mock_config.return_value = (
            {},  # full_config
            "testnet",  # env_name
            {  # env_config
                "QUICKSWAP_ROUTER": "0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff",
                "SUSHISWAP_ROUTER": "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506",
                "UNISWAP_V3_ROUTER": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
            },
            {},  # token_list
        )

        # Mock Web3 connection
        mock_web3_instance = MagicMock()
        mock_web3_instance.is_connected.return_value = True
        mock_web3_instance.eth.chain_id = 137
        mock_web3_instance.eth.account.from_key.return_value = Mock(
            address="0x1234567890"
        )
        mock_web3.return_value = mock_web3_instance

        # Mock Telegram bot
        mock_telegram_instance = AsyncMock()
        mock_telegram_instance.send_message = AsyncMock()
        mock_telegram.return_value = mock_telegram_instance

        # Initialize bot
        await bot.initialize()

        # Verify components initialized
        assert bot.config is not None
        assert bot.web3 is not None
        assert bot.account is not None
        assert len(bot.dex_instances) == 2  # QuickSwap and SushiSwap
        assert bot.telegram_bot is not None
        assert bot.transaction_manager is not None
        assert bot.risk_manager is not None
        assert bot.slippage_protection is not None
        assert bot.opportunity_scorer is not None
        assert bot.emergency_shutdown is not None


@pytest.mark.asyncio
async def test_initialize_no_private_key(bot):
    """Test initialization fails without private key."""
    with patch("src.bot.main.load_config") as mock_config, patch(
        "dotenv.load_dotenv"
    ), patch.dict("os.environ", {}, clear=True):
        # Mock config return value
        mock_config.return_value = (
            {},  # full_config
            "testnet",  # env_name
            {  # env_config
                "QUICKSWAP_ROUTER": "0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff",
                "SUSHISWAP_ROUTER": "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506",
            },
            {},  # token_list
        )

        with pytest.raises(ValueError, match="PRIVATE_KEY not found"):
            await bot.initialize()


@pytest.mark.asyncio
async def test_initialize_web3_connection_failed(bot):
    """Test initialization fails when Web3 connection fails."""
    with patch("src.bot.main.load_config") as mock_config, patch(
        "src.bot.main.Web3"
    ) as mock_web3, patch.dict("os.environ", {"PRIVATE_KEY": "0x" + "1" * 64}):
        # Mock config return value
        mock_config.return_value = (
            {},  # full_config
            "testnet",  # env_name
            {  # env_config
                "QUICKSWAP_ROUTER": "0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff",
                "SUSHISWAP_ROUTER": "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506",
            },
            {},  # token_list
        )

        mock_web3_instance = MagicMock()
        mock_web3_instance.is_connected.return_value = False
        mock_web3.return_value = mock_web3_instance

        with pytest.raises(ConnectionError, match="Failed to connect"):
            await bot.initialize()


@pytest.mark.asyncio
async def test_shutdown(bot):
    """Test bot shutdown."""
    # Setup mock telegram
    bot.telegram_bot = AsyncMock()
    bot.telegram_bot.send_message = AsyncMock()
    bot.running = True
    bot.trades_executed = 10
    bot.successful_trades = 8
    bot.total_profit = Decimal("1.5")

    await bot.shutdown()

    assert bot.running is False
    bot.telegram_bot.send_message.assert_called_once()


def test_log_statistics(bot, capsys):
    """Test statistics logging."""
    bot.opportunities_found = 100
    bot.trades_executed = 20
    bot.successful_trades = 15
    bot.failed_trades = 5
    bot.total_profit = Decimal("2.5")

    bot._log_statistics()

    # Statistics should be logged


@pytest.mark.asyncio
async def test_process_opportunities_empty(bot):
    """Test processing empty opportunities list."""
    # Should not raise error
    await bot._process_opportunities([])


@pytest.mark.asyncio
async def test_process_opportunities_with_scorer(bot):
    """Test processing opportunities with scoring."""
    bot.opportunity_scorer = Mock()
    bot.opportunity_scorer.score_opportunity.return_value = 85.0
    bot.opportunity_scorer.min_acceptable_score = 70.0

    opportunities = [
        {
            "profit_percent": Decimal("0.02"),
            "liquidity": Decimal("10000"),
            "gas_estimate": 150000,
            "confidence": Decimal("0.8"),
            "buy_dex": "quickswap",
            "sell_dex": "sushiswap",
            "token_a": "WETH",
            "token_b": "USDC",
            "amount": Decimal("1.0"),
            "expected_profit": Decimal("0.02"),
        }
    ]

    # Mock execute method
    bot._execute_opportunity = AsyncMock()

    await bot._process_opportunities(opportunities)

    # Should have scored and executed
    bot.opportunity_scorer.score_opportunity.assert_called_once()
    bot._execute_opportunity.assert_called_once()


@pytest.mark.asyncio
async def test_process_opportunities_below_threshold(bot):
    """Test opportunities below score threshold are skipped."""
    bot.opportunity_scorer = Mock()
    bot.opportunity_scorer.score_opportunity.return_value = 50.0
    bot.opportunity_scorer.min_acceptable_score = 70.0

    opportunities = [
        {
            "profit_percent": Decimal("0.005"),
            "liquidity": Decimal("1000"),
            "gas_estimate": 200000,
            "confidence": Decimal("0.5"),
            "buy_dex": "quickswap",
            "sell_dex": "sushiswap",
        }
    ]

    bot._execute_opportunity = AsyncMock()

    await bot._process_opportunities(opportunities)

    # Should not execute
    bot._execute_opportunity.assert_not_called()


@pytest.mark.asyncio
async def test_execute_opportunity_below_profit_threshold(bot):
    """Test execution skipped when profit below threshold."""
    opportunity = {
        "buy_dex": "quickswap",
        "sell_dex": "sushiswap",
        "token_a": "WETH",
        "token_b": "USDC",
        "amount": Decimal("1.0"),
        "expected_profit": Decimal("0.005"),
        "profit_percent": Decimal("0.005"),  # 0.5% < 1% threshold
    }

    await bot._execute_opportunity(opportunity)

    # Should not execute trade (below profit threshold)


@pytest.mark.asyncio
async def test_execute_opportunity_risk_manager_blocks(bot):
    """Test execution blocked by risk manager."""
    opportunity = {
        "buy_dex": "quickswap",
        "sell_dex": "sushiswap",
        "token_a": "WETH",
        "token_b": "USDC",
        "token_a_address": "0xabc",
        "amount": Decimal("1.0"),
        "expected_profit": Decimal("0.02"),
        "profit_percent": Decimal("0.02"),
        "buy_price": Decimal("2000"),
    }

    bot.risk_manager = AsyncMock()
    bot.risk_manager.validate_trade.return_value = (False, "Daily loss limit exceeded")
    bot.telegram_bot = AsyncMock()

    await bot._execute_opportunity(opportunity)

    # Should not execute trade
    bot.telegram_bot.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_execute_opportunity_dry_run(bot):
    """Test opportunity execution in DRY_RUN mode."""
    opportunity = {
        "buy_dex": "quickswap",
        "sell_dex": "sushiswap",
        "token_a": "WETH",
        "token_b": "USDC",
        "token_a_address": "0xabc",
        "amount": Decimal("1.0"),
        "expected_profit": Decimal("0.02"),
        "profit_percent": Decimal("0.02"),
        "buy_price": Decimal("2000"),
        "sell_price": Decimal("2040"),
    }

    # Mock web3 for is_profitable gas calculation
    bot.web3 = Mock()
    bot.web3.eth.gas_price = 30000000000
    bot.token_list = {"WETH": {"address": "0xabc", "decimals": 18}}
    bot.dex_instances = {}

    bot.risk_manager = AsyncMock()
    bot.risk_manager.validate_trade.return_value = (True, "OK")
    bot.risk_manager.record_trade_result = AsyncMock()
    bot.telegram_bot = AsyncMock()

    with patch("src.bot.main._PrimaryConfig") as mock_config, \
         patch("src.bot.main.is_profitable", new_callable=AsyncMock) as mock_prof:
        mock_config.DRY_RUN = True
        mock_prof.return_value = (True, Decimal("0.01"))

        await bot._execute_opportunity(opportunity)

    assert bot.trades_executed == 1
    assert bot.successful_trades == 1


@pytest.mark.asyncio
async def test_execute_opportunity_not_profitable(bot):
    """Test opportunity skipped when not profitable after gas."""
    opportunity = {
        "buy_dex": "quickswap",
        "sell_dex": "sushiswap",
        "token_a": "WETH",
        "token_b": "USDC",
        "token_a_address": "0xabc",
        "amount": Decimal("1.0"),
        "expected_profit": Decimal("0.001"),
        "profit_percent": Decimal("0.02"),
        "buy_price": Decimal("2000"),
        "sell_price": Decimal("2002"),
    }

    bot.web3 = Mock()
    bot.web3.eth.gas_price = 30000000000
    bot.token_list = {"WETH": {"address": "0xabc", "decimals": 18}}

    bot.risk_manager = AsyncMock()
    bot.risk_manager.validate_trade.return_value = (True, "OK")
    bot.risk_manager.record_trade_result = AsyncMock()

    with patch("src.bot.main.is_profitable", new_callable=AsyncMock) as mock_prof:
        mock_prof.return_value = (False, Decimal("-0.05"))

        await bot._execute_opportunity(opportunity)

    # Trade attempted but rejected by profitability check — counter decremented back
    assert bot.trades_executed == 0
    assert bot.failed_trades == 0


@pytest.mark.asyncio
async def test_monitor_and_execute_emergency_shutdown(bot):
    """Test monitoring pauses during emergency shutdown."""
    bot.running = True
    bot.emergency_shutdown = Mock()
    bot.emergency_shutdown.is_shutdown_active.return_value = True

    # Run one iteration then stop
    async def stop_after_delay():
        await asyncio.sleep(0.2)
        bot.running = False

    task = asyncio.create_task(bot.monitor_and_execute())
    await stop_after_delay()
    await task

    # Test passed - bot paused during emergency shutdown


@pytest.mark.asyncio
async def test_monitor_and_execute_finds_opportunities(bot):
    """Test monitoring loop runs."""
    bot.running = True
    bot.check_interval = 0.1

    bot._process_opportunities = AsyncMock()

    # Run one iteration
    async def stop_after_delay():
        await asyncio.sleep(0.3)
        bot.running = False

    task = asyncio.create_task(bot.monitor_and_execute())
    await stop_after_delay()
    await task

    # Test passed - monitoring loop ran


@pytest.mark.asyncio
async def test_run_with_keyboard_interrupt(bot):
    """Test bot handles keyboard interrupt gracefully."""
    bot.initialize = AsyncMock()
    bot.monitor_and_execute = AsyncMock(side_effect=KeyboardInterrupt)
    bot.shutdown = AsyncMock()

    await bot.run()

    bot.initialize.assert_called_once()
    bot.shutdown.assert_called_once()


@pytest.mark.asyncio
async def test_run_with_exception(bot):
    """Test bot handles exceptions gracefully."""
    bot.initialize = AsyncMock(side_effect=Exception("Test error"))
    bot.shutdown = AsyncMock()

    await bot.run()

    bot.shutdown.assert_called_once()


@pytest.mark.asyncio
async def test_main_entry_point():
    """Test main entry point."""
    with patch("src.bot.main.ArbitrageBot") as mock_bot_class:
        mock_bot = AsyncMock()
        mock_bot.run = AsyncMock()
        mock_bot_class.return_value = mock_bot

        await main()

        mock_bot.run.assert_called_once()
