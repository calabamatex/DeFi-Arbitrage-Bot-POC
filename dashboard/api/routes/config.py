"""Read-only config endpoint."""

from fastapi import APIRouter

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from src.config import Config

router = APIRouter()


@router.get("/config")
def get_config():
    """Return current bot configuration (read-only, no secrets)."""
    chains = {}
    for name, chain in Config.CHAINS.items():
        chains[name] = {
            "chain_id": chain.chain_id,
            "rpc_url": chain.rpc_url[:30] + "..." if len(chain.rpc_url) > 30 else chain.rpc_url,
            "native_token": chain.native_token,
            "is_testnet": chain.is_testnet,
        }

    return {
        "execution_mode": Config.EXECUTION_MODE,
        "dry_run": Config.DRY_RUN,
        "min_profit_usd": Config.MIN_PROFIT_USD,
        "max_gas_price_gwei": Config.MAX_GAS_PRICE_GWEI,
        "scan_interval_seconds": Config.SCAN_INTERVAL_SECONDS,
        "max_flash_loan_amount_usd": Config.MAX_FLASH_LOAN_AMOUNT_USD,
        "slippage_tolerance_bps": Config.SLIPPAGE_TOLERANCE_BPS,
        "daily_loss_limit_usd": Config.DAILY_LOSS_LIMIT_USD,
        "max_consecutive_losses": Config.MAX_CONSECUTIVE_LOSSES,
        "chains": chains,
        "active_chains": Config.get_active_chains(),
    }
