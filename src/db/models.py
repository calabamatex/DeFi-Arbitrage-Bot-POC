"""
Database models for Flash Loan Arbitrage Bot
SQLAlchemy ORM models based on DATABASE_SCHEMA.md
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column,
    Integer,
    String,
    Numeric,
    Boolean,
    DateTime,
    Text,
    ForeignKey,
    Index,
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum

Base = declarative_base()


class OpportunityStatus(enum.Enum):
    """Opportunity status enum"""
    DETECTED = "detected"
    SIMULATED = "simulated"
    EXECUTING = "executing"
    EXECUTED = "executed"
    FAILED = "failed"
    REJECTED = "rejected"


class TransactionStatus(enum.Enum):
    """Transaction status enum"""
    PENDING = "pending"
    SUBMITTED = "submitted"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    REVERTED = "reverted"


class Opportunity(Base):
    """Arbitrage opportunities detected"""
    __tablename__ = "opportunities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    opportunity_id = Column(String(66), unique=True, nullable=False, index=True)

    # Chain and timing
    chain_id = Column(Integer, nullable=False, index=True)
    detected_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    executed_at = Column(DateTime, nullable=True)

    # Status
    status = Column(SQLEnum(OpportunityStatus), nullable=False, default=OpportunityStatus.DETECTED, index=True)

    # Tokens and amounts
    token_in = Column(String(42), nullable=False)
    token_out = Column(String(42), nullable=False)
    amount_in = Column(Numeric(78, 0), nullable=False)  # uint256
    expected_amount_out = Column(Numeric(78, 0), nullable=False)
    actual_amount_out = Column(Numeric(78, 0), nullable=True)

    # Profitability
    expected_profit = Column(Numeric(78, 0), nullable=False)
    expected_profit_usd = Column(Numeric(20, 6), nullable=True)
    actual_profit = Column(Numeric(78, 0), nullable=True)
    actual_profit_usd = Column(Numeric(20, 6), nullable=True)

    # DEX path
    dex_path = Column(JSONB, nullable=False)  # Array of DEX names
    token_path = Column(JSONB, nullable=False)  # Array of token addresses

    # Gas estimation
    estimated_gas = Column(Integer, nullable=True)
    gas_price_gwei = Column(Numeric(20, 9), nullable=True)
    estimated_gas_cost_usd = Column(Numeric(20, 6), nullable=True)

    # Risk assessment
    slippage_tolerance_bps = Column(Integer, nullable=False, default=100)
    price_impact_bps = Column(Integer, nullable=True)

    # Simulation
    simulation_success = Column(Boolean, nullable=True)
    simulation_data = Column(JSONB, nullable=True)

    # Execution
    transaction_hash = Column(String(66), nullable=True, index=True)
    block_number = Column(Integer, nullable=True, index=True)

    # Rejection reason (if not executed)
    rejection_reason = Column(Text, nullable=True)

    # Metadata
    extra_data = Column(JSONB, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    transaction = relationship("Transaction", back_populates="opportunity", uselist=False)

    __table_args__ = (
        Index("idx_opportunities_status_chain", "status", "chain_id"),
        Index("idx_opportunities_detected_at_status", "detected_at", "status"),
    )


class Transaction(Base):
    """Blockchain transactions"""
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    opportunity_id = Column(Integer, ForeignKey("opportunities.id"), nullable=False, index=True)

    # Transaction details
    tx_hash = Column(String(66), unique=True, nullable=False, index=True)
    chain_id = Column(Integer, nullable=False, index=True)
    from_address = Column(String(42), nullable=False)
    to_address = Column(String(42), nullable=False)

    # Status
    status = Column(SQLEnum(TransactionStatus), nullable=False, default=TransactionStatus.PENDING, index=True)

    # Block info
    block_number = Column(Integer, nullable=True, index=True)
    block_timestamp = Column(DateTime, nullable=True)
    transaction_index = Column(Integer, nullable=True)

    # Gas
    gas_limit = Column(Integer, nullable=False)
    gas_used = Column(Integer, nullable=True)
    gas_price_gwei = Column(Numeric(20, 9), nullable=False)
    effective_gas_price_gwei = Column(Numeric(20, 9), nullable=True)

    # Value
    value_wei = Column(Numeric(78, 0), nullable=False, default=0)

    # Nonce
    nonce = Column(Integer, nullable=False)

    # Input data
    input_data = Column(Text, nullable=True)

    # Receipt data
    logs = Column(JSONB, nullable=True)
    contract_address = Column(String(42), nullable=True)

    # Error handling
    error_message = Column(Text, nullable=True)
    revert_reason = Column(Text, nullable=True)

    # Timestamps
    submitted_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    confirmed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    opportunity = relationship("Opportunity", back_populates="transaction")

    __table_args__ = (
        Index("idx_transactions_status_chain", "status", "chain_id"),
        Index("idx_transactions_block", "chain_id", "block_number"),
    )


class TradeResult(Base):
    """Final trade results"""
    __tablename__ = "trade_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    opportunity_id = Column(Integer, ForeignKey("opportunities.id"), unique=True, nullable=False)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), unique=True, nullable=False)

    # Success
    success = Column(Boolean, nullable=False)

    # Financial results
    profit_token = Column(String(42), nullable=False)
    profit_amount = Column(Numeric(78, 0), nullable=False)
    profit_usd = Column(Numeric(20, 6), nullable=True)

    # Costs
    gas_cost_wei = Column(Numeric(78, 0), nullable=False)
    gas_cost_usd = Column(Numeric(20, 6), nullable=True)
    flash_loan_fee = Column(Numeric(78, 0), nullable=False)
    flash_loan_fee_usd = Column(Numeric(20, 6), nullable=True)

    # Net profit
    net_profit_amount = Column(Numeric(78, 0), nullable=False)
    net_profit_usd = Column(Numeric(20, 6), nullable=True)
    roi_percentage = Column(Numeric(10, 4), nullable=True)

    # Execution stats
    execution_time_ms = Column(Integer, nullable=True)
    slippage_bps = Column(Integer, nullable=True)

    # Timestamps
    executed_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class Chain(Base):
    """Blockchain network configurations"""
    __tablename__ = "chains"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chain_id = Column(Integer, unique=True, nullable=False, index=True)
    name = Column(String(50), nullable=False)
    rpc_url = Column(String(255), nullable=False)
    explorer_url = Column(String(255), nullable=True)
    native_token = Column(String(10), nullable=False)

    # Status
    is_active = Column(Boolean, nullable=False, default=True)
    is_testnet = Column(Boolean, nullable=False, default=False)

    # Contract addresses
    flash_loan_contract = Column(String(42), nullable=True)
    aave_pool_address_provider = Column(String(42), nullable=True)

    # Limits
    min_profit_usd = Column(Numeric(20, 6), nullable=False, default=10.0)
    max_gas_price_gwei = Column(Numeric(20, 9), nullable=False, default=100.0)
    max_slippage_bps = Column(Integer, nullable=False, default=200)

    # Health monitoring
    last_block_number = Column(Integer, nullable=True)
    last_block_timestamp = Column(DateTime, nullable=True)
    is_synced = Column(Boolean, nullable=False, default=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class DEX(Base):
    """DEX configurations"""
    __tablename__ = "dexes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chain_id = Column(Integer, ForeignKey("chains.chain_id"), nullable=False, index=True)
    name = Column(String(50), nullable=False)
    dex_type = Column(String(20), nullable=False)  # uniswap_v2, uniswap_v3, sushiswap, etc.

    # Addresses
    router_address = Column(String(42), nullable=False)
    factory_address = Column(String(42), nullable=True)
    quoter_address = Column(String(42), nullable=True)  # For Uniswap V3

    # Status
    is_active = Column(Boolean, nullable=False, default=True)
    is_whitelisted = Column(Boolean, nullable=False, default=False)

    # Adapter
    adapter_address = Column(String(42), nullable=True)

    # Fees (for Uniswap V3)
    default_fee_tier = Column(Integer, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_dexes_chain_active", "chain_id", "is_active"),
    )


class Token(Base):
    """Token registry"""
    __tablename__ = "tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chain_id = Column(Integer, ForeignKey("chains.chain_id"), nullable=False, index=True)
    address = Column(String(42), nullable=False, index=True)
    symbol = Column(String(20), nullable=False)
    name = Column(String(100), nullable=True)
    decimals = Column(Integer, nullable=False)

    # Price data
    price_usd = Column(Numeric(20, 10), nullable=True)
    price_updated_at = Column(DateTime, nullable=True)

    # Status
    is_active = Column(Boolean, nullable=False, default=True)
    is_stablecoin = Column(Boolean, nullable=False, default=False)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_tokens_chain_address", "chain_id", "address", unique=True),
        Index("idx_tokens_symbol", "symbol"),
    )


class LiquidationOpportunity(Base):
    """Aave liquidation opportunities detected and executed"""
    __tablename__ = "liquidation_opportunities"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Chain and timing
    chain_id = Column(Integer, nullable=False, index=True)
    detected_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    executed_at = Column(DateTime, nullable=True)

    # Borrower
    user_address = Column(String(42), nullable=False, index=True)
    health_factor = Column(Numeric(78, 0), nullable=False)

    # Assets
    debt_asset = Column(String(42), nullable=False)
    collateral_asset = Column(String(42), nullable=False)
    debt_amount = Column(Numeric(78, 0), nullable=False)

    # Profitability
    liquidation_bonus_bps = Column(Integer, nullable=False)
    gross_profit = Column(Numeric(78, 0), nullable=True)
    flash_loan_fee = Column(Numeric(78, 0), nullable=True)
    swap_cost = Column(Numeric(78, 0), nullable=True)
    net_profit = Column(Numeric(78, 0), nullable=True)
    net_profit_usd = Column(Numeric(20, 6), nullable=True)

    # Execution
    status = Column(String(20), nullable=False, default="detected", index=True)
    transaction_hash = Column(String(66), nullable=True, index=True)
    gas_used = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_liquidations_status", "status"),
        Index("idx_liquidations_user", "user_address"),
    )


class ExecutionLog(Base):
    """Detailed execution logs"""
    __tablename__ = "execution_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    opportunity_id = Column(Integer, ForeignKey("opportunities.id"), nullable=False, index=True)

    # Log details
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    level = Column(String(10), nullable=False)  # INFO, WARNING, ERROR
    message = Column(Text, nullable=False)

    # Context
    step = Column(String(50), nullable=True)  # detection, simulation, execution, etc.
    data = Column(JSONB, nullable=True)

    # Error tracking
    error_type = Column(String(100), nullable=True)
    stack_trace = Column(Text, nullable=True)


# Export all models
__all__ = [
    "Base",
    "Opportunity",
    "Transaction",
    "TradeResult",
    "Chain",
    "DEX",
    "Token",
    "LiquidationOpportunity",
    "ExecutionLog",
    "OpportunityStatus",
    "TransactionStatus",
]
