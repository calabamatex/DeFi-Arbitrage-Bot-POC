"""P&L analytics endpoints."""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, cast, Date
from sqlalchemy.orm import Session

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from src.db.models import TradeResult, Opportunity

router = APIRouter()


def get_db(request: Request):
    db = request.app.state.db_session_factory()
    try:
        yield db
    finally:
        db.close()


def _pnl_aggregation(db: Session, start: datetime, end: datetime, group_by_expr):
    """Aggregate PnL data grouped by a date expression."""
    results = (
        db.query(
            group_by_expr.label("period"),
            func.count(TradeResult.id).label("trade_count"),
            func.sum(TradeResult.net_profit_usd).label("net_profit"),
            func.sum(TradeResult.gas_cost_usd).label("gas_cost"),
            func.sum(TradeResult.flash_loan_fee_usd).label("flash_loan_fees"),
            func.count(func.nullif(TradeResult.success, False)).label("wins"),
        )
        .filter(TradeResult.executed_at >= start)
        .filter(TradeResult.executed_at < end)
        .group_by(group_by_expr)
        .order_by(group_by_expr)
        .all()
    )

    return [
        {
            "period": str(r.period),
            "trade_count": r.trade_count,
            "net_profit_usd": float(r.net_profit) if r.net_profit else 0.0,
            "gas_cost_usd": float(r.gas_cost) if r.gas_cost else 0.0,
            "flash_loan_fees_usd": float(r.flash_loan_fees) if r.flash_loan_fees else 0.0,
            "wins": r.wins,
            "win_rate": round(r.wins / r.trade_count * 100, 1) if r.trade_count > 0 else 0,
        }
        for r in results
    ]


@router.get("/pnl/daily")
def daily_pnl(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """Daily P&L for the last N days."""
    end = datetime.utcnow()
    start = end - timedelta(days=days)
    return {
        "period": "daily",
        "days": days,
        "data": _pnl_aggregation(db, start, end, cast(TradeResult.executed_at, Date)),
    }


@router.get("/pnl/weekly")
def weekly_pnl(
    weeks: int = Query(12, ge=1, le=52),
    db: Session = Depends(get_db),
):
    """Weekly P&L for the last N weeks."""
    end = datetime.utcnow()
    start = end - timedelta(weeks=weeks)
    # Group by ISO week: date_trunc('week', executed_at)
    week_expr = func.date_trunc("week", TradeResult.executed_at)
    return {
        "period": "weekly",
        "weeks": weeks,
        "data": _pnl_aggregation(db, start, end, week_expr),
    }


@router.get("/pnl/monthly")
def monthly_pnl(
    months: int = Query(12, ge=1, le=24),
    db: Session = Depends(get_db),
):
    """Monthly P&L for the last N months."""
    end = datetime.utcnow()
    start = end - timedelta(days=months * 30)
    month_expr = func.date_trunc("month", TradeResult.executed_at)
    return {
        "period": "monthly",
        "months": months,
        "data": _pnl_aggregation(db, start, end, month_expr),
    }


@router.get("/pnl/summary")
def pnl_summary(db: Session = Depends(get_db)):
    """Overall P&L summary statistics."""
    result = db.query(
        func.count(TradeResult.id).label("total_trades"),
        func.sum(TradeResult.net_profit_usd).label("total_net_profit"),
        func.sum(TradeResult.gas_cost_usd).label("total_gas_cost"),
        func.sum(TradeResult.flash_loan_fee_usd).label("total_flash_loan_fees"),
        func.avg(TradeResult.net_profit_usd).label("avg_profit_per_trade"),
        func.max(TradeResult.net_profit_usd).label("best_trade"),
        func.min(TradeResult.net_profit_usd).label("worst_trade"),
        func.count(func.nullif(TradeResult.success, False)).label("wins"),
        func.avg(TradeResult.execution_time_ms).label("avg_execution_time_ms"),
    ).first()

    total = result.total_trades or 0
    wins = result.wins or 0

    return {
        "total_trades": total,
        "total_net_profit_usd": float(result.total_net_profit) if result.total_net_profit else 0.0,
        "total_gas_cost_usd": float(result.total_gas_cost) if result.total_gas_cost else 0.0,
        "total_flash_loan_fees_usd": float(result.total_flash_loan_fees) if result.total_flash_loan_fees else 0.0,
        "avg_profit_per_trade_usd": float(result.avg_profit_per_trade) if result.avg_profit_per_trade else 0.0,
        "best_trade_usd": float(result.best_trade) if result.best_trade else 0.0,
        "worst_trade_usd": float(result.worst_trade) if result.worst_trade else 0.0,
        "win_count": wins,
        "loss_count": total - wins,
        "win_rate": round(wins / total * 100, 1) if total > 0 else 0,
        "avg_execution_time_ms": float(result.avg_execution_time_ms) if result.avg_execution_time_ms else 0.0,
    }
