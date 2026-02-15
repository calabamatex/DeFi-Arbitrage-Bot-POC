"""Metrics endpoints — live and historical bot metrics."""

import asyncio
import json
from datetime import datetime
from typing import Optional

import httpx
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request

router = APIRouter()


@router.get("/metrics/current")
async def get_current_metrics(request: Request):
    """Fetch live metrics from the bot's /api/status endpoint."""
    bot_url = request.app.state.bot_api_url
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{bot_url}/api/status")
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as e:
        return {"error": f"Bot unreachable: {e}", "bot_url": bot_url}


@router.websocket("/ws/metrics")
async def websocket_metrics(websocket: WebSocket, request: Request = None):
    """Stream live metrics over WebSocket every 5 seconds."""
    await websocket.accept()
    bot_url = websocket.app.state.bot_api_url

    try:
        while True:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(f"{bot_url}/api/status")
                    data = resp.json() if resp.status_code == 200 else {"error": "Bot unreachable"}
            except httpx.HTTPError:
                data = {"error": "Bot unreachable", "timestamp": datetime.utcnow().isoformat()}

            await websocket.send_json(data)
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        pass
