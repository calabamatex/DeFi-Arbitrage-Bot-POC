"""System health endpoints."""

import httpx
from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

router = APIRouter()


def get_db(request: Request):
    db = request.app.state.db_session_factory()
    try:
        yield db
    finally:
        db.close()


@router.get("/system/health")
async def system_health(request: Request, db: Session = Depends(get_db)):
    """Aggregate health check: bot, database, RPC."""
    bot_url = request.app.state.bot_api_url
    checks = {}

    # Bot health
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{bot_url}/health")
            checks["bot"] = {
                "status": "healthy" if resp.status_code == 200 else "unhealthy",
                "data": resp.json(),
            }
    except httpx.HTTPError as e:
        checks["bot"] = {"status": "unreachable", "error": str(e)}

    # Database health
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = {"status": "healthy"}
    except Exception as e:
        checks["database"] = {"status": "unhealthy", "error": str(e)}

    # Overall
    all_healthy = all(
        c.get("status") == "healthy" for c in checks.values()
    )

    return {
        "status": "healthy" if all_healthy else "degraded",
        "checks": checks,
    }


@router.get("/system/contracts")
async def contract_status(request: Request):
    """Get contract information from the bot."""
    bot_url = request.app.state.bot_api_url
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{bot_url}/api/status")
            resp.raise_for_status()
            data = resp.json()

        return {
            "chain_id": data.get("chain_id"),
            "running": data.get("running", False),
            "dry_run": data.get("dry_run", True),
            "uptime_seconds": data.get("uptime_seconds", 0),
        }
    except httpx.HTTPError as e:
        return {"error": f"Bot unreachable: {e}"}
