"""Comprehensive tests for Telegram bot."""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
import aiohttp
import asyncio

from src.bot.telegram_bot import TelegramBot, send_telegram_alert


@pytest.fixture
def bot_token():
    """Fixture providing test bot token."""
    return "123456789:ABCdefGHIjklMNOpqrsTUVwxyz"


@pytest.fixture
def chat_id():
    """Fixture providing test chat ID."""
    return "987654321"


@pytest.fixture
def telegram_bot(bot_token, chat_id):
    """Fixture providing TelegramBot instance."""
    return TelegramBot(bot_token=bot_token, chat_id=chat_id)


@pytest.fixture
def telegram_bot_disabled():
    """Fixture providing disabled TelegramBot instance."""
    return TelegramBot(bot_token=None, chat_id=None)


def test_initialization_with_credentials(bot_token, chat_id):
    """Test TelegramBot initialization with valid credentials."""
    bot = TelegramBot(bot_token=bot_token, chat_id=chat_id)

    assert bot.bot_token == bot_token
    assert bot.chat_id == chat_id
    assert bot.enabled is True


def test_initialization_without_credentials():
    """Test TelegramBot initialization without credentials."""
    # Missing both
    bot1 = TelegramBot(bot_token=None, chat_id=None)
    assert bot1.enabled is False

    # Missing token
    bot2 = TelegramBot(bot_token=None, chat_id="123")
    assert bot2.enabled is False

    # Missing chat_id
    bot3 = TelegramBot(bot_token="token", chat_id=None)
    assert bot3.enabled is False

    # Empty strings
    bot4 = TelegramBot(bot_token="", chat_id="")
    assert bot4.enabled is False


@pytest.mark.asyncio
async def test_send_message_success(telegram_bot):
    """Test successful message sending."""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value='{"ok":true}')

    with patch("aiohttp.ClientSession") as mock_client:
        # Create async context manager for session
        mock_session = MagicMock()
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

        # Create async context manager for post
        mock_post_context = MagicMock()
        mock_post_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post_context.__aexit__ = AsyncMock(return_value=None)
        mock_session.post.return_value = mock_post_context

        result = await telegram_bot.send_message("Test message")

        assert result is True
        mock_session.post.assert_called_once()


@pytest.mark.asyncio
async def test_send_message_api_error(telegram_bot):
    """Test message sending with API error response."""
    mock_response = AsyncMock()
    mock_response.status = 400
    mock_response.text = AsyncMock(return_value='{"error":"Bad Request"}')

    mock_session = AsyncMock()
    mock_session.post.return_value.__aenter__.return_value = mock_response
    mock_session.post.return_value.__aexit__.return_value = None

    with patch("aiohttp.ClientSession") as mock_client:
        mock_client.return_value.__aenter__.return_value = mock_session
        mock_client.return_value.__aexit__.return_value = None

        result = await telegram_bot.send_message("Test message")

        assert result is False


@pytest.mark.asyncio
async def test_send_message_timeout(telegram_bot):
    """Test message sending with timeout."""
    mock_session = AsyncMock()
    mock_session.post.side_effect = asyncio.TimeoutError()

    with patch("aiohttp.ClientSession") as mock_client:
        mock_client.return_value.__aenter__.return_value = mock_session
        mock_client.return_value.__aexit__.return_value = None

        result = await telegram_bot.send_message("Test message")

        assert result is False


@pytest.mark.asyncio
async def test_send_message_http_error(telegram_bot):
    """Test message sending with HTTP client error."""
    mock_session = AsyncMock()
    mock_session.post.side_effect = aiohttp.ClientError("Connection error")

    with patch("aiohttp.ClientSession") as mock_client:
        mock_client.return_value.__aenter__.return_value = mock_session
        mock_client.return_value.__aexit__.return_value = None

        result = await telegram_bot.send_message("Test message")

        assert result is False


@pytest.mark.asyncio
async def test_send_message_disabled_bot(telegram_bot_disabled):
    """Test that disabled bot returns False without sending."""
    result = await telegram_bot_disabled.send_message("Test message")

    assert result is False


@pytest.mark.asyncio
async def test_send_alert(telegram_bot):
    """Test sending formatted alert."""
    with patch.object(telegram_bot, "send_message", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = True

        result = await telegram_bot.send_alert(
            title="Test Alert", message="This is a test", severity="INFO"
        )

        assert result is True
        mock_send.assert_called_once()
        # Check that message contains emoji and formatted text
        call_args = mock_send.call_args[0][0]
        assert "ℹ️" in call_args
        assert "*INFO*" in call_args
        assert "Test Alert" in call_args


@pytest.mark.asyncio
async def test_send_alert_different_severities(telegram_bot):
    """Test alerts with different severity levels."""
    severity_emojis = {
        "INFO": "ℹ️",
        "WARNING": "⚠️",
        "ERROR": "❌",
        "CRITICAL": "🚨",
    }

    for severity, emoji in severity_emojis.items():
        with patch.object(
            telegram_bot, "send_message", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = True

            await telegram_bot.send_alert(
                title="Test", message="Message", severity=severity
            )

            call_args = mock_send.call_args[0][0]
            assert emoji in call_args
            assert f"*{severity}*" in call_args


@pytest.mark.asyncio
async def test_trade_notification_format(telegram_bot):
    """Test trade notification formatting."""
    with patch.object(telegram_bot, "send_message", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = True

        result = await telegram_bot.send_trade_notification(
            token_in="WETH",
            token_out="USDC",
            amount_in=Decimal("1.5"),
            amount_out=Decimal("2800"),
            dex_buy="Uniswap V3",
            dex_sell="SushiSwap",
            profit=Decimal("50"),
            tx_hash="0xabcd1234",
            success=True,
        )

        assert result is True
        mock_send.assert_called_once()

        # Check message format
        call_args = mock_send.call_args[0][0]
        assert "✅" in call_args
        assert "SUCCESSFUL" in call_args
        assert "1.5 WETH" in call_args
        assert "Uniswap V3" in call_args
        assert "2800 USDC" in call_args
        assert "SushiSwap" in call_args
        assert "50" in call_args
        assert "0xabcd1234" in call_args


@pytest.mark.asyncio
async def test_trade_notification_failed(telegram_bot):
    """Test failed trade notification."""
    with patch.object(telegram_bot, "send_message", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = True

        result = await telegram_bot.send_trade_notification(
            token_in="WETH",
            token_out="USDC",
            amount_in=Decimal("1.5"),
            amount_out=Decimal("0"),
            dex_buy="Uniswap V3",
            dex_sell="SushiSwap",
            profit=Decimal("0"),
            tx_hash="0xfailed",
            success=False,
        )

        assert result is True
        call_args = mock_send.call_args[0][0]
        assert "❌" in call_args
        assert "FAILED" in call_args


@pytest.mark.asyncio
async def test_opportunity_alert_format(telegram_bot):
    """Test arbitrage opportunity alert formatting."""
    with patch.object(telegram_bot, "send_message", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = True

        result = await telegram_bot.send_opportunity_alert(
            token="WETH",
            dex_buy="Uniswap V3",
            dex_sell="SushiSwap",
            buy_price=Decimal("1850.50"),
            sell_price=Decimal("1875.75"),
            profit_percentage=Decimal("1.36"),
            estimated_profit=Decimal("25.25"),
        )

        assert result is True
        mock_send.assert_called_once()

        call_args = mock_send.call_args[0][0]
        assert "💰" in call_args
        assert "Arbitrage Opportunity" in call_args
        assert "WETH" in call_args
        assert "1850.50" in call_args
        assert "1875.75" in call_args
        assert "1.36" in call_args


@pytest.mark.asyncio
async def test_error_notification(telegram_bot):
    """Test error notification."""
    with patch.object(telegram_bot, "send_message", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = True

        result = await telegram_bot.send_error_notification(
            error_type="Network Error",
            error_message="Failed to connect to RPC",
            context={"rpc_url": "https://polygon-rpc.com", "attempts": 3},
        )

        assert result is True
        call_args = mock_send.call_args[0][0]
        assert "❌" in call_args
        assert "Network Error" in call_args
        assert "Failed to connect to RPC" in call_args
        assert "rpc_url" in call_args
        assert "attempts" in call_args


@pytest.mark.asyncio
async def test_error_notification_without_context(telegram_bot):
    """Test error notification without context."""
    with patch.object(telegram_bot, "send_message", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = True

        result = await telegram_bot.send_error_notification(
            error_type="Generic Error", error_message="Something went wrong"
        )

        assert result is True
        call_args = mock_send.call_args[0][0]
        assert "Generic Error" in call_args
        assert "Something went wrong" in call_args


@pytest.mark.asyncio
async def test_status_update(telegram_bot):
    """Test status update notification."""
    with patch.object(telegram_bot, "send_message", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = True

        result = await telegram_bot.send_status_update(
            uptime="2h 15m",
            trades_executed=5,
            total_profit=Decimal("125.50"),
            opportunities_found=12,
        )

        assert result is True
        call_args = mock_send.call_args[0][0]
        assert "📊" in call_args
        assert "Bot Status" in call_args
        assert "2h 15m" in call_args
        assert "5" in call_args
        assert "125.50" in call_args
        assert "12" in call_args


@pytest.mark.asyncio
async def test_backward_compatible_function_success(bot_token, chat_id):
    """Test backward compatible send_telegram_alert function."""
    mock_response = MagicMock()
    mock_response.status = 200

    with patch("aiohttp.ClientSession") as mock_client:
        mock_session = MagicMock()
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

        mock_post_context = MagicMock()
        mock_post_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post_context.__aexit__ = AsyncMock(return_value=None)
        mock_session.post.return_value = mock_post_context

        result = await send_telegram_alert(
            message="Test alert", bot_token=bot_token, chat_id=chat_id
        )

        assert result is True


@pytest.mark.asyncio
async def test_backward_compatible_function_disabled():
    """Test backward compatible function with missing credentials."""
    result = await send_telegram_alert(
        message="Test alert", bot_token=None, chat_id=None
    )

    assert result is False


@pytest.mark.asyncio
async def test_send_message_with_html_parse_mode(telegram_bot):
    """Test sending message with HTML parse mode."""
    mock_response = MagicMock()
    mock_response.status = 200

    with patch("aiohttp.ClientSession") as mock_client:
        mock_session = MagicMock()
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

        mock_post_context = MagicMock()
        mock_post_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post_context.__aexit__ = AsyncMock(return_value=None)
        mock_session.post.return_value = mock_post_context

        result = await telegram_bot.send_message(
            "<b>Bold text</b>", parse_mode="HTML"
        )

        assert result is True
        # Verify HTML parse mode was used
        call_kwargs = mock_session.post.call_args[1]
        assert call_kwargs["json"]["parse_mode"] == "HTML"


def test_bot_attributes(telegram_bot, bot_token, chat_id):
    """Test that bot attributes are correctly set."""
    assert telegram_bot.bot_token == bot_token
    assert telegram_bot.chat_id == chat_id
    assert telegram_bot.enabled is True
    assert telegram_bot.DEFAULT_TIMEOUT == 10


def test_api_url_format(telegram_bot, bot_token):
    """Test that API URL is formatted correctly."""
    expected_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    actual_url = telegram_bot.TELEGRAM_API_URL.format(token=bot_token)

    assert actual_url == expected_url
