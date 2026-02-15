"""Trade history endpoints."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from src.db.models import Opportunity, TradeResult, Transaction, OpportunityStatus

router = APIRouter()


def get_db(request: Request):
    db = request.app.state.db_session_factory()
    try:
        yield db
    finally:
        db.close()


@router.get("/trades")
def list_trades(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    status: Optional[str] = Query(None),
    chain_id: Optional[int] = Query(None),
    success: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
):
    """List trades with pagination and filters."""
    query = db.query(
        TradeResult, Opportunity
    ).join(
        Opportunity, TradeResult.opportunity_id == Opportunity.id
    )

    if status:
        query = query.filter(Opportunity.status == status)
    if chain_id:
        query = query.filter(Opportunity.chain_id == chain_id)
    if success is not None:
        query = query.filter(TradeResult.success == success)

    total = query.count()
    results = (
        query.order_by(desc(TradeResult.executed_at))
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    trades = []
    for trade, opp in results:
        trades.append({
            "id": trade.id,
            "opportunity_id": opp.opportunity_id,
            "chain_id": opp.chain_id,
            "token_in": opp.token_in,
            "token_out": opp.token_out,
            "dex_path": opp.dex_path,
            "success": trade.success,
            "profit_usd": float(trade.profit_usd) if trade.profit_usd else None,
            "net_profit_usd": float(trade.net_profit_usd) if trade.net_profit_usd else None,
            "gas_cost_usd": float(trade.gas_cost_usd) if trade.gas_cost_usd else None,
            "execution_time_ms": trade.execution_time_ms,
            "slippage_bps": trade.slippage_bps,
            "executed_at": trade.executed_at.isoformat() if trade.executed_at else None,
        })

    return {
        "trades": trades,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
    }


@router.get("/trades/{trade_id}")
def get_trade(trade_id: int, db: Session = Depends(get_db)):
    """Get a single trade with full details."""
    result = db.query(
        TradeResult, Opportunity, Transaction
    ).join(
        Opportunity, TradeResult.opportunity_id == Opportunity.id
    ).outerjoin(
        Transaction, TradeResult.transaction_id == Transaction.id
    ).filter(
        TradeResult.id == trade_id
    ).first()

    if not result:
        return {"error": "Trade not found"}

    trade, opp, tx = result
    return {
        "id": trade.id,
        "opportunity": {
            "id": opp.opportunity_id,
            "chain_id": opp.chain_id,
            "status": opp.status.value if opp.status else None,
            "token_in": opp.token_in,
            "token_out": opp.token_out,
            "amount_in": str(opp.amount_in),
            "expected_profit_usd": float(opp.expected_profit_usd) if opp.expected_profit_usd else None,
            "dex_path": opp.dex_path,
            "token_path": opp.token_path,
            "detected_at": opp.detected_at.isoformat() if opp.detected_at else None,
        },
        "result": {
            "success": trade.success,
            "profit_usd": float(trade.profit_usd) if trade.profit_usd else None,
            "net_profit_usd": float(trade.net_profit_usd) if trade.net_profit_usd else None,
            "gas_cost_usd": float(trade.gas_cost_usd) if trade.gas_cost_usd else None,
            "flash_loan_fee_usd": float(trade.flash_loan_fee_usd) if trade.flash_loan_fee_usd else None,
            "roi_percentage": float(trade.roi_percentage) if trade.roi_percentage else None,
            "execution_time_ms": trade.execution_time_ms,
            "slippage_bps": trade.slippage_bps,
            "executed_at": trade.executed_at.isoformat() if trade.executed_at else None,
        },
        "transaction": {
            "tx_hash": tx.tx_hash if tx else None,
            "block_number": tx.block_number if tx else None,
            "gas_used": tx.gas_used if tx else None,
            "gas_price_gwei": float(tx.gas_price_gwei) if tx and tx.gas_price_gwei else None,
            "status": tx.status.value if tx and tx.status else None,
            "error_message": tx.error_message if tx else None,
        } if tx else None,
    }
