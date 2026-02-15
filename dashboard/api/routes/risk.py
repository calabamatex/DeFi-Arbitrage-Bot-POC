"""Risk management endpoints."""

import httpx
from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/risk/status")
async def risk_status(request: Request):
    """Get current risk management status from the bot."""
    bot_url = request.app.state.bot_api_url
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{bot_url}/api/status")
            resp.raise_for_status()
            data = resp.json()

        return {
            "circuit_breaker_active": data.get("circuit_breaker_active", False),
            "consecutive_losses": data.get("consecutive_losses", 0),
            "daily_pnl_usd": data.get("daily_pnl_usd", 0.0),
            "net_profit_usd": data.get("net_profit_usd", 0.0),
            "success_rate": data.get("success_rate", 0.0),
            "total_trades": data.get("total_trades", 0),
            "successful_trades": data.get("successful_trades", 0),
            "failed_trades": data.get("failed_trades", 0),
            "scans": data.get("scans", 0),
            "opportunities": data.get("opportunities", 0),
        }
    except httpx.HTTPError as e:
        return {"error": f"Bot unreachable: {e}", "bot_url": bot_url}
