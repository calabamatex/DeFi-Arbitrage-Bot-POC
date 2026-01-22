"""Telegram notification system for trading alerts and status updates."""

import logging
from typing import Optional, Dict, Any
from decimal import Decimal
import aiohttp
import asyncio

logger = logging.getLogger(__name__)


class TelegramBot:
    """Telegram bot for sending trading notifications."""

    TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"
    DEFAULT_TIMEOUT = 10  # seconds

    def __init__(self, bot_token: Optional[str], chat_id: Optional[str]):
        """
        Initialize Telegram bot.

        Args:
            bot_token: Telegram bot token (from @BotFather)
            chat_id: Telegram chat ID to send messages to

        Note:
            If credentials are missing, bot will log warnings but continue
            operating. All send methods will return False without attempting
            to send messages.
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = bool(bot_token and chat_id)

        if not self.enabled:
            logger.warning(
                "Telegram bot not configured (missing bot_token or chat_id). "
                "Notifications will be disabled."
            )
        else:
            logger.info("Telegram bot initialized successfully")

    async def send_message(
        self, message: str, parse_mode: str = "Markdown"
    ) -> bool:
        """
        Send a message via Telegram.

        Args:
            message: Message text to send
            parse_mode: Parse mode for formatting (Markdown or HTML)

        Returns:
            True if message sent successfully, False otherwise
        """
        if not self.enabled:
            logger.warning("Telegram not configured, skipping message")
            return False

        url = self.TELEGRAM_API_URL.format(token=self.bot_token)
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": parse_mode,
        }

        try:
            timeout = aiohttp.ClientTimeout(total=self.DEFAULT_TIMEOUT)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        logger.debug("Telegram message sent successfully")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(
                            f"Telegram API error (status {response.status}): {error_text}"
                        )
                        return False

        except asyncio.TimeoutError:
            logger.error(
                f"Telegram API timeout after {self.DEFAULT_TIMEOUT} seconds"
            )
            return False
        except aiohttp.ClientError as e:
            logger.error(f"Telegram HTTP client error: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending Telegram message: {e}")
            return False

    async def send_alert(
        self, title: str, message: str, severity: str = "INFO"
    ) -> bool:
        """
        Send a formatted alert message.

        Args:
            title: Alert title
            message: Alert message body
            severity: Severity level (INFO, WARNING, ERROR, CRITICAL)

        Returns:
            True if alert sent successfully, False otherwise
        """
        # Map severity to emoji
        severity_emoji = {
            "INFO": "ℹ️",
            "WARNING": "⚠️",
            "ERROR": "❌",
            "CRITICAL": "🚨",
        }

        emoji = severity_emoji.get(severity.upper(), "📢")
        formatted_message = f"{emoji} *{severity.upper()}*: {title}\n\n{message}"

        return await self.send_message(formatted_message)

    async def send_trade_notification(
        self,
        token_in: str,
        token_out: str,
        amount_in: Decimal,
        amount_out: Decimal,
        dex_buy: str,
        dex_sell: str,
        profit: Decimal,
        tx_hash: str,
        success: bool = True,
    ) -> bool:
        """
        Send a trade execution notification.

        Args:
            token_in: Input token symbol
            token_out: Output token symbol
            amount_in: Input amount
            amount_out: Output amount
            dex_buy: DEX used for buying
            dex_sell: DEX used for selling
            profit: Profit amount
            tx_hash: Transaction hash
            success: Whether trade was successful

        Returns:
            True if notification sent successfully, False otherwise
        """
        emoji = "✅" if success else "❌"
        status = "SUCCESSFUL" if success else "FAILED"

        message = (
            f"{emoji} *Trade {status}*\n\n"
            f"*Buy:* {amount_in} {token_in} on {dex_buy}\n"
            f"*Sell:* {amount_out} {token_out} on {dex_sell}\n"
            f"*Profit:* {profit} {token_out}\n"
            f"*TX:* `{tx_hash}`"
        )

        return await self.send_message(message)

    async def send_opportunity_alert(
        self,
        token: str,
        dex_buy: str,
        dex_sell: str,
        buy_price: Decimal,
        sell_price: Decimal,
        profit_percentage: Decimal,
        estimated_profit: Decimal,
    ) -> bool:
        """
        Send an arbitrage opportunity alert.

        Args:
            token: Token symbol
            dex_buy: DEX with lower price (buy here)
            dex_sell: DEX with higher price (sell here)
            buy_price: Price on buy DEX
            sell_price: Price on sell DEX
            profit_percentage: Profit as percentage
            estimated_profit: Estimated profit amount

        Returns:
            True if alert sent successfully, False otherwise
        """
        message = (
            f"💰 *Arbitrage Opportunity Detected*\n\n"
            f"*Token:* {token}\n"
            f"*Buy:* {dex_buy} @ {buy_price}\n"
            f"*Sell:* {dex_sell} @ {sell_price}\n"
            f"*Profit:* {profit_percentage}% (~{estimated_profit})\n"
        )

        return await self.send_message(message)

    async def send_error_notification(
        self, error_type: str, error_message: str, context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Send an error notification.

        Args:
            error_type: Type/category of error
            error_message: Detailed error message
            context: Optional context information

        Returns:
            True if notification sent successfully, False otherwise
        """
        message = f"❌ *Error: {error_type}*\n\n{error_message}"

        if context:
            message += "\n\n*Context:*\n"
            for key, value in context.items():
                message += f"• {key}: {value}\n"

        return await self.send_message(message)

    async def send_status_update(
        self,
        uptime: str,
        trades_executed: int,
        total_profit: Decimal,
        opportunities_found: int,
    ) -> bool:
        """
        Send a periodic status update.

        Args:
            uptime: Bot uptime
            trades_executed: Number of trades executed
            total_profit: Total profit earned
            opportunities_found: Number of opportunities found

        Returns:
            True if status sent successfully, False otherwise
        """
        message = (
            f"📊 *Bot Status Update*\n\n"
            f"*Uptime:* {uptime}\n"
            f"*Trades Executed:* {trades_executed}\n"
            f"*Total Profit:* {total_profit}\n"
            f"*Opportunities Found:* {opportunities_found}"
        )

        return await self.send_message(message)


async def send_telegram_alert(
    message: str,
    bot_token: Optional[str] = None,
    chat_id: Optional[str] = None,
) -> bool:
    """
    Backward compatible alert function for simple message sending.

    This function provides a simpler interface for sending alerts without
    needing to instantiate a TelegramBot object.

    Args:
        message: Message text to send
        bot_token: Telegram bot token (if None, will be disabled)
        chat_id: Telegram chat ID (if None, will be disabled)

    Returns:
        True if message sent successfully, False otherwise

    Example:
        >>> success = await send_telegram_alert(
        ...     "Trade executed successfully!",
        ...     bot_token="123456:ABC-DEF...",
        ...     chat_id="987654321"
        ... )
    """
    bot = TelegramBot(bot_token=bot_token, chat_id=chat_id)
    return await bot.send_message(message)
