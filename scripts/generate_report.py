#!/usr/bin/env python3
"""
Generate performance report from bot metrics.
"""

import json
import sys
from datetime import datetime
from decimal import Decimal


def generate_markdown_report(metrics_file: str) -> str:
    """Generate markdown report from metrics JSON."""

    with open(metrics_file, "r") as f:
        data = json.load(f)

    current = data.get("current_metrics")
    if not current:
        return "No metrics available"

    # Build report
    report = f"""# Arbitrage Bot Performance Report

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Report Period:** {data['uptime_hours']:.1f} hours

---

## Summary

| Metric | Value |
|--------|-------|
| **Uptime** | {current['uptime_seconds']/3600:.1f} hours |
| **Opportunities Found** | {current['opportunities_found']} ({current['opportunities_per_hour']:.1f}/hour) |
| **Trades Executed** | {current['trades_executed']} |
| **Success Rate** | {current['success_rate']*100:.1f}% |
| **Net Profit** | ${current['net_profit_usd']:.2f} |

---

## Financial Performance

| Metric | Value |
|--------|-------|
| Total Profit | ${current['total_profit_usd']:.2f} |
| Total Loss | ${current['total_loss_usd']:.2f} |
| **Net Profit** | **${current['net_profit_usd']:.2f}** |
| Avg Profit/Trade | ${current['avg_profit_per_trade']:.2f} |
| Total Gas Cost | ${current['total_gas_cost_usd']:.2f} |
| Avg Gas/Trade | ${current['avg_gas_per_trade']:.2f} |

---

## Trade Statistics

| Metric | Value |
|--------|-------|
| Successful Trades | {current['successful_trades']} |
| Failed Trades | {current['failed_trades']} |
| Success Rate | {current['success_rate']*100:.1f}% |
| Consecutive Losses | {current['consecutive_losses']} |

---

## Performance Metrics

| Metric | Value | Target |
|--------|-------|--------|
| Avg Detection Time | {current['avg_detection_time_ms']:.0f}ms | <2000ms |
| Avg Execution Time | {current['avg_execution_time_ms']:.0f}ms | <5000ms |
| RPC Calls/Minute | {current['rpc_calls_per_minute']} | <100 |
| Memory Usage | {current['memory_usage_mb']:.1f}MB | <500MB |
| CPU Usage | {current['cpu_usage_percent']:.1f}% | <50% |

---

## Risk Management

| Metric | Status |
|--------|--------|
| Circuit Breaker | {'🔴 ACTIVE' if current['circuit_breaker_active'] else '🟢 Inactive'} |
| Daily P/L | ${current['daily_pnl']:.2f} |
| Consecutive Losses | {current['consecutive_losses']} |

---

## System Health

| Metric | Value |
|--------|-------|
| Error Count | {current['error_count']} |
| Last Error | {current['last_error_time'] or 'None'} |
| Uptime | {current['uptime_seconds']/3600:.1f} hours |

---

## Recent Errors

"""

    # Add recent errors
    errors = data.get("recent_errors", [])
    if errors:
        for err in errors[-5:]:
            report += f"- **{err['timestamp']}**: {err['error']}\n"
    else:
        report += "*No recent errors*\n"

    report += "\n---\n\n*End of Report*\n"

    return report


def main():
    if len(sys.argv) < 2:
        print("Usage: generate_report.py <metrics_file.json>")
        sys.exit(1)

    metrics_file = sys.argv[1]

    try:
        report = generate_markdown_report(metrics_file)

        # Save to file
        output_file = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        with open(output_file, "w") as f:
            f.write(report)

        print(f"✅ Report generated: {output_file}")
        print()
        print(report)

        # Also send via Telegram if configured
        try:
            from pathlib import Path

            sys.path.insert(0, str(Path(__file__).parent.parent))

            from src.bot.config import load_env_vars
            from src.bot.telegram_bot import TelegramBot
            import asyncio

            _, telegram_token, telegram_chat = load_env_vars()

            if telegram_token and telegram_chat:
                bot = TelegramBot(telegram_token, telegram_chat)

                # Send summary via Telegram
                async def send_report():
                    await bot.send_message(
                        f"📊 *Performance Report*\n\n{report[:1000]}..."
                    )

                asyncio.run(send_report())
                print("✅ Report sent via Telegram")

        except Exception as e:
            print(f"Note: Could not send via Telegram: {e}")

    except Exception as e:
        print(f"❌ Error generating report: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
