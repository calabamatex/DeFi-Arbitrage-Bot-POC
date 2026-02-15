"""Liquidation opportunity endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import desc
from sqlalchemy.orm import Session

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from src.db.models import LiquidationOpportunity

router = APIRouter()


def get_db(request: Request):
    db = request.app.state.db_session_factory()
    try:
        yield db
    finally:
        db.close()


@router.get("/liquidations")
def list_liquidations(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    status: Optional[str] = Query(None),
    chain_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """List liquidation opportunities with pagination."""
    query = db.query(LiquidationOpportunity)

    if status:
        query = query.filter(LiquidationOpportunity.status == status)
    if chain_id:
        query = query.filter(LiquidationOpportunity.chain_id == chain_id)

    total = query.count()
    results = (
        query.order_by(desc(LiquidationOpportunity.detected_at))
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    items = []
    for liq in results:
        items.append({
            "id": liq.id,
            "chain_id": liq.chain_id,
            "user_address": liq.user_address,
            "health_factor": str(liq.health_factor),
            "debt_asset": liq.debt_asset,
            "collateral_asset": liq.collateral_asset,
            "debt_amount": str(liq.debt_amount),
            "liquidation_bonus_bps": liq.liquidation_bonus_bps,
            "net_profit_usd": float(liq.net_profit_usd) if liq.net_profit_usd else None,
            "status": liq.status,
            "transaction_hash": liq.transaction_hash,
            "detected_at": liq.detected_at.isoformat() if liq.detected_at else None,
            "executed_at": liq.executed_at.isoformat() if liq.executed_at else None,
            "error_message": liq.error_message,
        })

    return {
        "liquidations": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
    }
