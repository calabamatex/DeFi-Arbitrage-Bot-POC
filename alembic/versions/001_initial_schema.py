"""Initial schema — all tables from models.py

Revision ID: 001
Revises: None
Create Date: 2026-02-11

This migration creates the full initial schema. If tables already exist
(from prior use of Base.metadata.create_all()), the migration detects
them and skips creation, then stamps the DB as up-to-date.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    """Check if a table already exists in the database."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = :name)"
        ),
        {"name": table_name},
    )
    return result.scalar()


def upgrade() -> None:
    # Skip if tables already exist (e.g., from prior create_all())
    if _table_exists("opportunities"):
        return

    # -- chains --
    op.create_table(
        "chains",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("chain_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("rpc_url", sa.String(255), nullable=False),
        sa.Column("explorer_url", sa.String(255), nullable=True),
        sa.Column("native_token", sa.String(10), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_testnet", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("flash_loan_contract", sa.String(42), nullable=True),
        sa.Column("aave_pool_address_provider", sa.String(42), nullable=True),
        sa.Column("min_profit_usd", sa.Numeric(20, 6), nullable=False, server_default="10.0"),
        sa.Column("max_gas_price_gwei", sa.Numeric(20, 9), nullable=False, server_default="100.0"),
        sa.Column("max_slippage_bps", sa.Integer(), nullable=False, server_default="200"),
        sa.Column("last_block_number", sa.Integer(), nullable=True),
        sa.Column("last_block_timestamp", sa.DateTime(), nullable=True),
        sa.Column("is_synced", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chain_id"),
    )
    op.create_index("ix_chains_chain_id", "chains", ["chain_id"])

    # -- dexes --
    op.create_table(
        "dexes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("chain_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("dex_type", sa.String(20), nullable=False),
        sa.Column("router_address", sa.String(42), nullable=False),
        sa.Column("factory_address", sa.String(42), nullable=True),
        sa.Column("quoter_address", sa.String(42), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_whitelisted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("adapter_address", sa.String(42), nullable=True),
        sa.Column("default_fee_tier", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["chain_id"], ["chains.chain_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_dexes_chain_active", "dexes", ["chain_id", "is_active"])

    # -- tokens --
    op.create_table(
        "tokens",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("chain_id", sa.Integer(), nullable=False),
        sa.Column("address", sa.String(42), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("name", sa.String(100), nullable=True),
        sa.Column("decimals", sa.Integer(), nullable=False),
        sa.Column("price_usd", sa.Numeric(20, 10), nullable=True),
        sa.Column("price_updated_at", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_stablecoin", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["chain_id"], ["chains.chain_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_tokens_chain_address", "tokens", ["chain_id", "address"], unique=True)
    op.create_index("idx_tokens_symbol", "tokens", ["symbol"])

    # -- opportunities --
    op.create_table(
        "opportunities",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("opportunity_id", sa.String(66), nullable=False),
        sa.Column("chain_id", sa.Integer(), nullable=False),
        sa.Column("detected_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("executed_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.Enum("DETECTED", "SIMULATED", "EXECUTING", "EXECUTED", "FAILED", "REJECTED", name="opportunitystatus"), nullable=False, server_default="DETECTED"),
        sa.Column("token_in", sa.String(42), nullable=False),
        sa.Column("token_out", sa.String(42), nullable=False),
        sa.Column("amount_in", sa.Numeric(78, 0), nullable=False),
        sa.Column("expected_amount_out", sa.Numeric(78, 0), nullable=False),
        sa.Column("actual_amount_out", sa.Numeric(78, 0), nullable=True),
        sa.Column("expected_profit", sa.Numeric(78, 0), nullable=False),
        sa.Column("expected_profit_usd", sa.Numeric(20, 6), nullable=True),
        sa.Column("actual_profit", sa.Numeric(78, 0), nullable=True),
        sa.Column("actual_profit_usd", sa.Numeric(20, 6), nullable=True),
        sa.Column("dex_path", postgresql.JSONB(), nullable=False),
        sa.Column("token_path", postgresql.JSONB(), nullable=False),
        sa.Column("estimated_gas", sa.Integer(), nullable=True),
        sa.Column("gas_price_gwei", sa.Numeric(20, 9), nullable=True),
        sa.Column("estimated_gas_cost_usd", sa.Numeric(20, 6), nullable=True),
        sa.Column("slippage_tolerance_bps", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("price_impact_bps", sa.Integer(), nullable=True),
        sa.Column("simulation_success", sa.Boolean(), nullable=True),
        sa.Column("simulation_data", postgresql.JSONB(), nullable=True),
        sa.Column("transaction_hash", sa.String(66), nullable=True),
        sa.Column("block_number", sa.Integer(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("extra_data", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("opportunity_id"),
    )
    op.create_index("ix_opportunities_opportunity_id", "opportunities", ["opportunity_id"])
    op.create_index("ix_opportunities_chain_id", "opportunities", ["chain_id"])
    op.create_index("ix_opportunities_detected_at", "opportunities", ["detected_at"])
    op.create_index("ix_opportunities_status", "opportunities", ["status"])
    op.create_index("ix_opportunities_transaction_hash", "opportunities", ["transaction_hash"])
    op.create_index("ix_opportunities_block_number", "opportunities", ["block_number"])
    op.create_index("idx_opportunities_status_chain", "opportunities", ["status", "chain_id"])
    op.create_index("idx_opportunities_detected_at_status", "opportunities", ["detected_at", "status"])

    # -- transactions --
    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("opportunity_id", sa.Integer(), nullable=False),
        sa.Column("tx_hash", sa.String(66), nullable=False),
        sa.Column("chain_id", sa.Integer(), nullable=False),
        sa.Column("from_address", sa.String(42), nullable=False),
        sa.Column("to_address", sa.String(42), nullable=False),
        sa.Column("status", sa.Enum("PENDING", "SUBMITTED", "CONFIRMED", "FAILED", "REVERTED", name="transactionstatus"), nullable=False, server_default="PENDING"),
        sa.Column("block_number", sa.Integer(), nullable=True),
        sa.Column("block_timestamp", sa.DateTime(), nullable=True),
        sa.Column("transaction_index", sa.Integer(), nullable=True),
        sa.Column("gas_limit", sa.Integer(), nullable=False),
        sa.Column("gas_used", sa.Integer(), nullable=True),
        sa.Column("gas_price_gwei", sa.Numeric(20, 9), nullable=False),
        sa.Column("effective_gas_price_gwei", sa.Numeric(20, 9), nullable=True),
        sa.Column("value_wei", sa.Numeric(78, 0), nullable=False, server_default="0"),
        sa.Column("nonce", sa.Integer(), nullable=False),
        sa.Column("input_data", sa.Text(), nullable=True),
        sa.Column("logs", postgresql.JSONB(), nullable=True),
        sa.Column("contract_address", sa.String(42), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("revert_reason", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tx_hash"),
    )
    op.create_index("ix_transactions_opportunity_id", "transactions", ["opportunity_id"])
    op.create_index("ix_transactions_tx_hash", "transactions", ["tx_hash"])
    op.create_index("ix_transactions_chain_id", "transactions", ["chain_id"])
    op.create_index("ix_transactions_status", "transactions", ["status"])
    op.create_index("ix_transactions_block_number", "transactions", ["block_number"])
    op.create_index("idx_transactions_status_chain", "transactions", ["status", "chain_id"])
    op.create_index("idx_transactions_block", "transactions", ["chain_id", "block_number"])

    # -- trade_results --
    op.create_table(
        "trade_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("opportunity_id", sa.Integer(), nullable=False),
        sa.Column("transaction_id", sa.Integer(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("profit_token", sa.String(42), nullable=False),
        sa.Column("profit_amount", sa.Numeric(78, 0), nullable=False),
        sa.Column("profit_usd", sa.Numeric(20, 6), nullable=True),
        sa.Column("gas_cost_wei", sa.Numeric(78, 0), nullable=False),
        sa.Column("gas_cost_usd", sa.Numeric(20, 6), nullable=True),
        sa.Column("flash_loan_fee", sa.Numeric(78, 0), nullable=False),
        sa.Column("flash_loan_fee_usd", sa.Numeric(20, 6), nullable=True),
        sa.Column("net_profit_amount", sa.Numeric(78, 0), nullable=False),
        sa.Column("net_profit_usd", sa.Numeric(20, 6), nullable=True),
        sa.Column("roi_percentage", sa.Numeric(10, 4), nullable=True),
        sa.Column("execution_time_ms", sa.Integer(), nullable=True),
        sa.Column("slippage_bps", sa.Integer(), nullable=True),
        sa.Column("executed_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"]),
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("opportunity_id"),
        sa.UniqueConstraint("transaction_id"),
    )

    # -- liquidation_opportunities --
    op.create_table(
        "liquidation_opportunities",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("chain_id", sa.Integer(), nullable=False),
        sa.Column("detected_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("executed_at", sa.DateTime(), nullable=True),
        sa.Column("user_address", sa.String(42), nullable=False),
        sa.Column("health_factor", sa.Numeric(78, 0), nullable=False),
        sa.Column("debt_asset", sa.String(42), nullable=False),
        sa.Column("collateral_asset", sa.String(42), nullable=False),
        sa.Column("debt_amount", sa.Numeric(78, 0), nullable=False),
        sa.Column("liquidation_bonus_bps", sa.Integer(), nullable=False),
        sa.Column("gross_profit", sa.Numeric(78, 0), nullable=True),
        sa.Column("flash_loan_fee", sa.Numeric(78, 0), nullable=True),
        sa.Column("swap_cost", sa.Numeric(78, 0), nullable=True),
        sa.Column("net_profit", sa.Numeric(78, 0), nullable=True),
        sa.Column("net_profit_usd", sa.Numeric(20, 6), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="detected"),
        sa.Column("transaction_hash", sa.String(66), nullable=True),
        sa.Column("gas_used", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_liquidation_opportunities_chain_id", "liquidation_opportunities", ["chain_id"])
    op.create_index("ix_liquidation_opportunities_detected_at", "liquidation_opportunities", ["detected_at"])
    op.create_index("idx_liquidations_status", "liquidation_opportunities", ["status"])
    op.create_index("idx_liquidations_user", "liquidation_opportunities", ["user_address"])

    # -- execution_log --
    op.create_table(
        "execution_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("opportunity_id", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("level", sa.String(10), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("step", sa.String(50), nullable=True),
        sa.Column("data", postgresql.JSONB(), nullable=True),
        sa.Column("error_type", sa.String(100), nullable=True),
        sa.Column("stack_trace", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_execution_log_opportunity_id", "execution_log", ["opportunity_id"])
    op.create_index("ix_execution_log_timestamp", "execution_log", ["timestamp"])


def downgrade() -> None:
    op.drop_table("execution_log")
    op.drop_table("liquidation_opportunities")
    op.drop_table("trade_results")
    op.drop_table("transactions")
    op.drop_table("opportunities")
    op.drop_table("tokens")
    op.drop_table("dexes")
    op.drop_table("chains")

    # Drop enums
    op.execute("DROP TYPE IF EXISTS opportunitystatus")
    op.execute("DROP TYPE IF EXISTS transactionstatus")
