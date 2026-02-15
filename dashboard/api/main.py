"""
Dashboard API — FastAPI backend for the arbitrage bot dashboard.

Provides REST endpoints for metrics, trades, P&L, risk status,
system health, liquidations, and config. Also serves a WebSocket
for real-time metrics streaming.

Usage:
    uvicorn dashboard.api.main:app --host 0.0.0.0 --port 8000 --reload
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from dashboard.api.routes import metrics, trades, pnl, risk, system, liquidations, config


DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/arbitrage_bot"
)
BOT_API_URL = os.getenv("BOT_API_URL", "http://localhost:8080")

engine = create_engine(DATABASE_URL, pool_size=5, max_overflow=10)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db_session_factory = SessionLocal
    app.state.bot_api_url = BOT_API_URL
    yield


app = FastAPI(
    title="Arbitrage Bot Dashboard API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(metrics.router, prefix="/api/v1", tags=["metrics"])
app.include_router(trades.router, prefix="/api/v1", tags=["trades"])
app.include_router(pnl.router, prefix="/api/v1", tags=["pnl"])
app.include_router(risk.router, prefix="/api/v1", tags=["risk"])
app.include_router(system.router, prefix="/api/v1", tags=["system"])
app.include_router(liquidations.router, prefix="/api/v1", tags=["liquidations"])
app.include_router(config.router, prefix="/api/v1", tags=["config"])


@app.get("/")
async def root():
    return {"service": "arbitrage-bot-dashboard", "version": "1.0.0"}
