#!/usr/bin/env python3
"""
ARIA — Arbitrage Runtime Intelligence Agent

AI Operations Manager acting as both Project Manager and Product Owner.
Monitors bot health, triages errors, generates reports, and manages
operational decisions via Telegram.

Usage:
    python agent/pm_agent.py
    # or via Docker:
    docker-compose --profile agent up -d pm-agent
"""

import asyncio
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ARIA")


# ============================================================
# Configuration
# ============================================================

BOT_API_URL = os.getenv("BOT_API_URL", "http://localhost:8080")
DASHBOARD_API_URL = os.getenv("DASHBOARD_API_URL", "http://localhost:8000")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
HEALTH_CHECK_INTERVAL = int(os.getenv("HEALTH_CHECK_INTERVAL", "60"))


class Severity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class Alert:
    severity: Severity
    title: str
    message: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    resolved: bool = False


# ============================================================
# Telegram Integration
# ============================================================

class TelegramBot:
    """Handles sending and receiving Telegram messages."""

    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.last_update_id = 0

    async def send_message(self, text: str, parse_mode: str = "HTML"):
        """Send a message to the configured chat."""
        if not self.token or not self.chat_id:
            logger.warning("Telegram not configured — message not sent")
            return

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/sendMessage",
                    json={
                        "chat_id": self.chat_id,
                        "text": text[:4096],
                        "parse_mode": parse_mode,
                    },
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        logger.error(f"Telegram send failed: {resp.status}")
        except Exception as e:
            logger.error(f"Telegram send error: {e}")

    async def get_updates(self) -> list:
        """Poll for new commands."""
        if not self.token:
            return []

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/getUpdates",
                    params={"offset": self.last_update_id + 1, "timeout": 5},
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status != 200:
                        return []
                    data = await resp.json()
                    updates = data.get("result", [])
                    if updates:
                        self.last_update_id = updates[-1]["update_id"]
                    return updates
        except Exception as e:
            logger.debug(f"Telegram poll error: {e}")
            return []


# ============================================================
# Bot API Client
# ============================================================

class BotAPIClient:
    """Fetches data from the bot's health/status endpoints."""

    def __init__(self, bot_url: str, dashboard_url: str):
        self.bot_url = bot_url
        self.dashboard_url = dashboard_url

    async def get_health(self) -> Optional[dict]:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.bot_url}/health",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    return await resp.json() if resp.status == 200 else None
        except Exception:
            return None

    async def get_status(self) -> Optional[dict]:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.bot_url}/api/status",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    return await resp.json() if resp.status == 200 else None
        except Exception:
            return None

    async def get_pnl_summary(self) -> Optional[dict]:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.dashboard_url}/api/v1/pnl/summary",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    return await resp.json() if resp.status == 200 else None
        except Exception:
            return None

    async def get_recent_trades(self, limit: int = 10) -> Optional[dict]:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.dashboard_url}/api/v1/trades?per_page={limit}",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    return await resp.json() if resp.status == 200 else None
        except Exception:
            return None


# ============================================================
# ARIA Agent Core
# ============================================================

class ARIAAgent:
    """
    Arbitrage Runtime Intelligence Agent.

    Responsibilities:
    - Monitor bot health every 60s
    - Triage errors by severity
    - Generate daily/weekly reports
    - Handle operator commands via Telegram
    - Escalate critical issues immediately
    """

    def __init__(self):
        self.telegram = TelegramBot(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
        self.bot_client = BotAPIClient(BOT_API_URL, DASHBOARD_API_URL)
        self.scheduler = AsyncIOScheduler()
        self.alerts: list[Alert] = []
        self.start_time = datetime.utcnow()
        self.consecutive_health_failures = 0
        self.last_status: Optional[dict] = None
        self.circuit_breaker_alerted = False

    # -- Health Monitoring --

    async def check_health(self):
        """Periodic health check — runs every HEALTH_CHECK_INTERVAL seconds."""
        health = await self.bot_client.get_health()
        status = await self.bot_client.get_status()

        if health is None:
            self.consecutive_health_failures += 1
            if self.consecutive_health_failures >= 3:
                await self.escalate(
                    Severity.CRITICAL,
                    "Bot Down",
                    f"Bot unreachable for {self.consecutive_health_failures} consecutive checks "
                    f"({self.consecutive_health_failures * HEALTH_CHECK_INTERVAL}s).",
                )
            return

        self.consecutive_health_failures = 0

        if status:
            self.last_status = status
            await self._analyze_status(status)

    async def _analyze_status(self, status: dict):
        """Analyze bot status and trigger alerts if needed."""
        # Circuit breaker
        if status.get("circuit_breaker_active") and not self.circuit_breaker_alerted:
            self.circuit_breaker_alerted = True
            await self.escalate(
                Severity.CRITICAL,
                "Circuit Breaker Activated",
                "Trading is paused due to consecutive losses. "
                f"Consecutive losses: {status.get('consecutive_losses', '?')}",
            )
        elif not status.get("circuit_breaker_active"):
            self.circuit_breaker_alerted = False

        # Daily P&L check
        daily_pnl = status.get("daily_pnl_usd", 0)
        if daily_pnl < -500:
            await self.escalate(
                Severity.HIGH,
                "High Daily Loss",
                f"Daily P&L: ${daily_pnl:.2f}. Exceeds $500 loss threshold.",
            )

        # Memory check
        memory_mb = status.get("memory_mb", 0)
        if memory_mb > 500:
            await self.escalate(
                Severity.MEDIUM,
                "High Memory Usage",
                f"Memory: {memory_mb:.0f}MB (threshold: 500MB).",
            )

        # Low success rate
        success_rate = status.get("success_rate", 100)
        total_trades = status.get("total_trades", 0)
        if total_trades >= 10 and success_rate < 40:
            await self.escalate(
                Severity.HIGH,
                "Low Success Rate",
                f"Success rate: {success_rate:.1f}% over {total_trades} trades.",
            )

    async def escalate(self, severity: Severity, title: str, message: str):
        """Create alert and send to Telegram based on severity."""
        alert = Alert(severity=severity, title=title, message=message)
        self.alerts.append(alert)

        # Deduplicate: don't re-alert the same title within 30 min
        recent = [
            a for a in self.alerts
            if a.title == title
            and a.timestamp > datetime.utcnow() - timedelta(minutes=30)
            and not a.resolved
        ]
        if len(recent) > 1:
            return

        severity_emoji = {
            Severity.CRITICAL: "🔴",
            Severity.HIGH: "🟠",
            Severity.MEDIUM: "🟡",
            Severity.LOW: "🔵",
        }

        text = (
            f"{severity_emoji[severity]} <b>[{severity.value.upper()}] {title}</b>\n\n"
            f"{message}\n\n"
            f"<i>{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</i>"
        )
        await self.telegram.send_message(text)
        logger.warning(f"ALERT [{severity.value}]: {title} — {message}")

    # -- Reports --

    async def daily_report(self):
        """Generate and send daily performance report."""
        status = await self.bot_client.get_status()
        pnl = await self.bot_client.get_pnl_summary()
        trades_data = await self.bot_client.get_recent_trades(10)

        lines = ["<b>📊 ARIA Daily Report</b>", ""]

        if status:
            lines.extend([
                f"<b>Bot Status:</b> {'Running' if status.get('running') else 'Stopped'}",
                f"<b>Uptime:</b> {status.get('uptime_seconds', 0) / 3600:.1f}h",
                f"<b>Circuit Breaker:</b> {'🔴 ACTIVE' if status.get('circuit_breaker_active') else '🟢 OK'}",
                f"<b>Daily P&L:</b> ${status.get('daily_pnl_usd', 0):.2f}",
                f"<b>Net Profit:</b> ${status.get('net_profit_usd', 0):.2f}",
                f"<b>Scans:</b> {status.get('scans', 0)}",
                f"<b>Opportunities:</b> {status.get('opportunities', 0)}",
                "",
            ])

        if pnl:
            lines.extend([
                "<b>All-Time Stats:</b>",
                f"  Trades: {pnl.get('total_trades', 0)}",
                f"  Win Rate: {pnl.get('win_rate', 0):.1f}%",
                f"  Avg Profit: ${pnl.get('avg_profit_per_trade_usd', 0):.2f}",
                f"  Best: ${pnl.get('best_trade_usd', 0):.2f}",
                f"  Worst: ${pnl.get('worst_trade_usd', 0):.2f}",
                f"  Gas Cost: ${pnl.get('total_gas_cost_usd', 0):.2f}",
                "",
            ])

        # Recent alerts
        today = datetime.utcnow().date()
        today_alerts = [a for a in self.alerts if a.timestamp.date() == today]
        if today_alerts:
            lines.append(f"<b>Alerts Today:</b> {len(today_alerts)}")
            for a in today_alerts[-5:]:
                lines.append(f"  [{a.severity.value}] {a.title}")
        else:
            lines.append("<b>Alerts Today:</b> None ✅")

        lines.extend(["", f"<i>{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</i>"])
        await self.telegram.send_message("\n".join(lines))
        logger.info("Daily report sent")

    async def weekly_report(self):
        """Generate and send weekly summary."""
        pnl = await self.bot_client.get_pnl_summary()

        lines = ["<b>📈 ARIA Weekly Report</b>", ""]

        if pnl:
            lines.extend([
                f"<b>Total Trades:</b> {pnl.get('total_trades', 0)}",
                f"<b>Net Profit:</b> ${pnl.get('total_net_profit_usd', 0):.2f}",
                f"<b>Win Rate:</b> {pnl.get('win_rate', 0):.1f}%",
                f"<b>Gas Spent:</b> ${pnl.get('total_gas_cost_usd', 0):.2f}",
                f"<b>Flash Loan Fees:</b> ${pnl.get('total_flash_loan_fees_usd', 0):.2f}",
                "",
            ])

        # Alert summary for the week
        week_ago = datetime.utcnow() - timedelta(days=7)
        week_alerts = [a for a in self.alerts if a.timestamp > week_ago]
        crit = sum(1 for a in week_alerts if a.severity == Severity.CRITICAL)
        high = sum(1 for a in week_alerts if a.severity == Severity.HIGH)
        lines.append(f"<b>Alerts This Week:</b> {len(week_alerts)} ({crit} critical, {high} high)")

        lines.extend(["", f"<i>{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</i>"])
        await self.telegram.send_message("\n".join(lines))
        logger.info("Weekly report sent")

    # -- Command Handler --

    async def handle_command(self, text: str) -> str:
        """Process a Telegram command and return a response."""
        cmd = text.strip().lower().split()[0] if text.strip() else ""

        if cmd == "/status":
            status = await self.bot_client.get_status()
            if not status:
                return "Bot unreachable."
            return (
                f"<b>Bot Status</b>\n"
                f"Running: {status.get('running')}\n"
                f"Dry Run: {status.get('dry_run')}\n"
                f"Uptime: {status.get('uptime_seconds', 0) / 3600:.1f}h\n"
                f"Scans: {status.get('scans', 0)}\n"
                f"Trades: {status.get('total_trades', 0)}\n"
                f"Profit: ${status.get('net_profit_usd', 0):.2f}\n"
                f"Circuit Breaker: {'ACTIVE' if status.get('circuit_breaker_active') else 'OK'}"
            )

        elif cmd == "/pnl":
            pnl = await self.bot_client.get_pnl_summary()
            if not pnl:
                return "P&L data unavailable."
            return (
                f"<b>P&L Summary</b>\n"
                f"Net Profit: ${pnl.get('total_net_profit_usd', 0):.2f}\n"
                f"Trades: {pnl.get('total_trades', 0)}\n"
                f"Win Rate: {pnl.get('win_rate', 0):.1f}%\n"
                f"Best: ${pnl.get('best_trade_usd', 0):.2f}\n"
                f"Worst: ${pnl.get('worst_trade_usd', 0):.2f}\n"
                f"Gas: ${pnl.get('total_gas_cost_usd', 0):.2f}"
            )

        elif cmd == "/health":
            health = await self.bot_client.get_health()
            if not health:
                return "🔴 Bot health endpoint unreachable."
            running = health.get("running", False)
            return f"{'🟢' if running else '🔴'} Bot: {'running' if running else 'down'}"

        elif cmd == "/trades":
            trades = await self.bot_client.get_recent_trades(5)
            if not trades or not trades.get("trades"):
                return "No recent trades."
            lines = ["<b>Recent Trades</b>"]
            for t in trades["trades"][:5]:
                profit = t.get("net_profit_usd")
                icon = "✅" if t.get("success") else "❌"
                p_str = f"${profit:.2f}" if profit is not None else "N/A"
                lines.append(f"  {icon} {p_str} — {t.get('executed_at', '?')[:16]}")
            return "\n".join(lines)

        elif cmd == "/risk":
            status = await self.bot_client.get_status()
            if not status:
                return "Bot unreachable."
            return (
                f"<b>Risk Status</b>\n"
                f"Circuit Breaker: {'🔴 ACTIVE' if status.get('circuit_breaker_active') else '🟢 OK'}\n"
                f"Consecutive Losses: {status.get('consecutive_losses', 0)}\n"
                f"Daily P&L: ${status.get('daily_pnl_usd', 0):.2f}\n"
                f"Success Rate: {status.get('success_rate', 0):.1f}%"
            )

        elif cmd == "/report":
            await self.daily_report()
            return "Report sent."

        elif cmd == "/help":
            return (
                "<b>ARIA Commands</b>\n"
                "/status — Bot status\n"
                "/pnl — P&L summary\n"
                "/trades — Recent trades\n"
                "/risk — Risk status\n"
                "/health — Health check\n"
                "/report — Generate daily report\n"
                "/help — This message"
            )

        else:
            return f"Unknown command: {cmd}. Try /help"

    async def poll_commands(self):
        """Check for new Telegram commands."""
        updates = await self.telegram.get_updates()
        for update in updates:
            msg = update.get("message", {})
            text = msg.get("text", "")
            chat_id = str(msg.get("chat", {}).get("id", ""))

            # Only respond to the configured chat
            if chat_id != self.chat_id and self.chat_id:
                continue

            if text.startswith("/"):
                response = await self.handle_command(text)
                await self.telegram.send_message(response)

    @property
    def chat_id(self):
        return TELEGRAM_CHAT_ID

    # -- Lifecycle --

    async def start(self):
        """Start the ARIA agent."""
        logger.info("ARIA agent starting...")

        # Schedule health checks
        self.scheduler.add_job(
            self.check_health,
            "interval",
            seconds=HEALTH_CHECK_INTERVAL,
            id="health_check",
        )

        # Schedule command polling
        if TELEGRAM_BOT_TOKEN:
            self.scheduler.add_job(
                self.poll_commands,
                "interval",
                seconds=3,
                id="command_poll",
            )

        # Schedule daily report at 00:00 UTC
        self.scheduler.add_job(
            self.daily_report,
            "cron",
            hour=0,
            minute=0,
            id="daily_report",
        )

        # Schedule weekly report Monday 00:00 UTC
        self.scheduler.add_job(
            self.weekly_report,
            "cron",
            day_of_week="mon",
            hour=0,
            minute=0,
            id="weekly_report",
        )

        self.scheduler.start()

        # Announce startup
        await self.telegram.send_message(
            "🤖 <b>ARIA Online</b>\n\n"
            "Arbitrage Runtime Intelligence Agent is now monitoring.\n"
            "Type /help for available commands."
        )

        logger.info(f"ARIA agent started. Monitoring {BOT_API_URL}")
        logger.info(f"Health check interval: {HEALTH_CHECK_INTERVAL}s")
        logger.info(f"Telegram: {'configured' if TELEGRAM_BOT_TOKEN else 'not configured'}")

        # Run initial health check
        await self.check_health()

        # Keep running
        try:
            while True:
                await asyncio.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            logger.info("ARIA agent shutting down...")
            self.scheduler.shutdown()
            await self.telegram.send_message("🔴 <b>ARIA Offline</b> — Agent shutting down.")


async def main():
    agent = ARIAAgent()
    await agent.start()


if __name__ == "__main__":
    asyncio.run(main())
