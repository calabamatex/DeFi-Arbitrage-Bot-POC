# Database Schema & Migration Plan

**Project:** Flash Loan Arbitrage Bot
**Database:** PostgreSQL 15+ with TimescaleDB extension
**Version:** 1.0
**Date:** 2026-01-19

---

## Table of Contents

1. [Schema Overview](#schema-overview)
2. [Core Tables](#core-tables)
3. [Time-Series Tables](#time-series-tables)
4. [Configuration Tables](#configuration-tables)
5. [Indexes & Constraints](#indexes--constraints)
6. [Migration Strategy](#migration-strategy)
7. [Data Retention Policies](#data-retention-policies)
8. [Backup & Recovery](#backup--recovery)

---

## Schema Overview

### Database Architecture

```
arbitrage_bot (Database)
├── Core Transactional Tables
│   ├── opportunities
│   ├── transactions
│   ├── trade_results
│   └── execution_log
│
├── Time-Series Tables (Hypertables)
│   ├── gas_price_history
│   ├── price_snapshots
│   ├── chain_metrics
│   └── performance_metrics
│
├── Configuration Tables
│   ├── chains
│   ├── dexes
│   ├── tokens
│   └── risk_config
│
└── Operational Tables
    ├── rpc_providers
    ├── alerts
    └── audit_log
```

### Design Principles

1. **Normalization with Strategic Denormalization**
   - Normalized core data for consistency
   - Denormalized display fields for query performance

2. **Time-Series Optimization**
   - Use TimescaleDB hypertables for time-series data
   - Automatic partitioning by time
   - Compression for historical data

3. **Append-Only Where Possible**
   - Immutable records for auditability
   - Updates via new records with versioning

4. **Strong Typing**
   - Use appropriate PostgreSQL types
   - CHECK constraints for data validation
   - ENUMs for categorical data

---

## Core Tables

### opportunities

Stores detected arbitrage opportunities.

```sql
CREATE TABLE opportunities (
    id BIGSERIAL PRIMARY KEY,

    -- Identification
    opportunity_hash VARCHAR(66) UNIQUE NOT NULL,  -- Unique hash of opportunity

    -- Timing
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,  -- Opportunity age limit

    -- Chain & Tokens
    chain_id INTEGER NOT NULL,
    chain_name VARCHAR(50) NOT NULL,  -- Denormalized for queries
    token_in VARCHAR(42) NOT NULL,    -- Token address
    token_in_symbol VARCHAR(20) NOT NULL,  -- For display
    token_out VARCHAR(42) NOT NULL,
    token_out_symbol VARCHAR(20) NOT NULL,

    -- DEX Information
    buy_dex VARCHAR(50) NOT NULL,     -- DEX name (e.g., 'uniswap_v3')
    buy_dex_address VARCHAR(42) NOT NULL,
    buy_price_usd NUMERIC(20,8) NOT NULL,

    sell_dex VARCHAR(50) NOT NULL,
    sell_dex_address VARCHAR(42) NOT NULL,
    sell_price_usd NUMERIC(20,8) NOT NULL,

    -- Trade Parameters
    loan_amount NUMERIC(30,0) NOT NULL,  -- Wei amount
    loan_amount_usd NUMERIC(12,2) NOT NULL,

    -- Profitability
    price_diff_percent NUMERIC(8,4) NOT NULL,
    gross_profit_usd NUMERIC(12,2) NOT NULL,
    estimated_gas_cost_usd NUMERIC(10,4) NOT NULL,
    flash_loan_fee_usd NUMERIC(10,4) NOT NULL,
    net_profit_usd NUMERIC(12,2) NOT NULL,
    roi_percent NUMERIC(8,4) NOT NULL,

    -- Status
    status VARCHAR(20) NOT NULL CHECK (
        status IN ('detected', 'validating', 'executing', 'completed', 'failed', 'expired', 'rejected')
    ),
    rejection_reason TEXT,

    -- Execution Reference
    transaction_id BIGINT REFERENCES transactions(id),

    -- Metadata
    source VARCHAR(50) NOT NULL,  -- Which scanner detected this
    metadata JSONB,  -- Additional flexible data

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_opportunities_detected_at ON opportunities(detected_at DESC);
CREATE INDEX idx_opportunities_chain_id ON opportunities(chain_id, detected_at DESC);
CREATE INDEX idx_opportunities_status ON opportunities(status) WHERE status IN ('detected', 'validating');
CREATE INDEX idx_opportunities_hash ON opportunities(opportunity_hash);

-- Composite index for common queries
CREATE INDEX idx_opportunities_chain_status_time
ON opportunities(chain_id, status, detected_at DESC);

-- Partial index for active opportunities
CREATE INDEX idx_active_opportunities
ON opportunities(chain_id, status, detected_at DESC)
WHERE status IN ('detected', 'validating', 'executing');

-- GIN index for JSONB queries
CREATE INDEX idx_opportunities_metadata ON opportunities USING GIN(metadata);

-- Trigger for updated_at
CREATE TRIGGER update_opportunities_updated_at
    BEFORE UPDATE ON opportunities
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
```

---

### transactions

Stores blockchain transactions.

```sql
CREATE TABLE transactions (
    id BIGSERIAL PRIMARY KEY,

    -- Transaction Identity
    tx_hash VARCHAR(66) UNIQUE NOT NULL,
    chain_id INTEGER NOT NULL,

    -- Transaction Details
    from_address VARCHAR(42) NOT NULL,
    to_address VARCHAR(42) NOT NULL,
    value NUMERIC(30,0) NOT NULL DEFAULT 0,  -- Wei
    input_data TEXT,  -- Calldata (can be large)

    -- Gas
    gas_limit BIGINT NOT NULL,
    gas_used BIGINT,
    gas_price NUMERIC(30,0),  -- Wei
    max_fee_per_gas NUMERIC(30,0),  -- EIP-1559
    max_priority_fee_per_gas NUMERIC(30,0),  -- EIP-1559
    effective_gas_price NUMERIC(30,0),  -- Actual gas price paid

    -- Cost Calculation
    gas_cost_native NUMERIC(30,0),  -- Cost in native token (wei)
    gas_cost_usd NUMERIC(10,4),  -- Cost in USD

    -- Block Information
    block_number BIGINT,
    block_timestamp TIMESTAMPTZ,
    transaction_index INTEGER,

    -- Status
    status VARCHAR(20) NOT NULL CHECK (
        status IN ('pending', 'confirmed', 'failed', 'reverted')
    ),
    error_message TEXT,
    revert_reason TEXT,

    -- Timing
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    confirmed_at TIMESTAMPTZ,

    -- Nonce Management
    nonce BIGINT NOT NULL,

    -- Relationship
    opportunity_id BIGINT REFERENCES opportunities(id),

    -- Metadata
    metadata JSONB,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE UNIQUE INDEX idx_transactions_hash ON transactions(tx_hash);
CREATE INDEX idx_transactions_opportunity ON transactions(opportunity_id);
CREATE INDEX idx_transactions_chain_status ON transactions(chain_id, status);
CREATE INDEX idx_transactions_submitted_at ON transactions(submitted_at DESC);
CREATE INDEX idx_transactions_nonce ON transactions(chain_id, from_address, nonce);

-- Composite index for recent transactions
CREATE INDEX idx_transactions_recent
ON transactions(chain_id, status, submitted_at DESC)
WHERE status IN ('pending', 'confirmed');
```

---

### trade_results

Stores final results of completed trades.

```sql
CREATE TABLE trade_results (
    id BIGSERIAL PRIMARY KEY,

    -- References
    opportunity_id BIGINT NOT NULL REFERENCES opportunities(id),
    transaction_id BIGINT NOT NULL REFERENCES transactions(id),

    -- Chain & Timing
    chain_id INTEGER NOT NULL,
    executed_at TIMESTAMPTZ NOT NULL,

    -- Trade Details
    token_in VARCHAR(42) NOT NULL,
    token_out VARCHAR(42) NOT NULL,
    loan_amount NUMERIC(30,0) NOT NULL,

    -- Financial Results
    gross_profit_usd NUMERIC(12,2) NOT NULL,
    gas_cost_usd NUMERIC(10,4) NOT NULL,
    flash_loan_fee_usd NUMERIC(10,4) NOT NULL,
    slippage_cost_usd NUMERIC(10,4),
    net_profit_usd NUMERIC(12,2) NOT NULL,
    roi_percent NUMERIC(8,4) NOT NULL,

    -- Execution Metrics
    execution_time_ms INTEGER NOT NULL,  -- Time from detection to confirmation
    gas_used BIGINT NOT NULL,
    gas_efficiency_score NUMERIC(5,2),  -- Custom metric

    -- Success/Failure
    success BOOLEAN NOT NULL,
    failure_reason TEXT,

    -- Slippage Analysis
    expected_amount_out NUMERIC(30,0),
    actual_amount_out NUMERIC(30,0),
    slippage_percent NUMERIC(8,4),

    -- Metadata
    metadata JSONB,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_trade_results_executed_at ON trade_results(executed_at DESC);
CREATE INDEX idx_trade_results_chain ON trade_results(chain_id, executed_at DESC);
CREATE INDEX idx_trade_results_success ON trade_results(success, executed_at DESC);
CREATE INDEX idx_trade_results_opportunity ON trade_results(opportunity_id);
CREATE INDEX idx_trade_results_transaction ON trade_results(transaction_id);

-- Materialized view for daily P&L
CREATE MATERIALIZED VIEW daily_pnl AS
SELECT
    DATE(executed_at) AS trade_date,
    chain_id,
    COUNT(*) AS total_trades,
    SUM(CASE WHEN success THEN 1 ELSE 0 END) AS successful_trades,
    SUM(gross_profit_usd) AS total_gross_profit,
    SUM(gas_cost_usd) AS total_gas_cost,
    SUM(flash_loan_fee_usd) AS total_flash_fees,
    SUM(net_profit_usd) AS total_net_profit,
    AVG(CASE WHEN success THEN net_profit_usd ELSE NULL END) AS avg_profit_per_success,
    AVG(execution_time_ms) AS avg_execution_time_ms
FROM trade_results
GROUP BY DATE(executed_at), chain_id
ORDER BY trade_date DESC, chain_id;

CREATE UNIQUE INDEX idx_daily_pnl_date_chain ON daily_pnl(trade_date DESC, chain_id);
```

---

### execution_log

Detailed log of execution steps for debugging.

```sql
CREATE TABLE execution_log (
    id BIGSERIAL PRIMARY KEY,

    -- References
    opportunity_id BIGINT REFERENCES opportunities(id),
    transaction_id BIGINT REFERENCES transactions(id),

    -- Log Entry
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    log_level VARCHAR(10) NOT NULL CHECK (
        log_level IN ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
    ),
    component VARCHAR(50) NOT NULL,  -- Which part of system logged this
    message TEXT NOT NULL,

    -- Context
    chain_id INTEGER,
    step VARCHAR(50),  -- Which step in execution pipeline

    -- Additional Data
    data JSONB,

    -- Error Info
    error_type VARCHAR(100),
    stack_trace TEXT
);

-- Indexes
CREATE INDEX idx_execution_log_timestamp ON execution_log(timestamp DESC);
CREATE INDEX idx_execution_log_opportunity ON execution_log(opportunity_id);
CREATE INDEX idx_execution_log_level ON execution_log(log_level)
WHERE log_level IN ('ERROR', 'CRITICAL');

-- Partition by month for performance
CREATE TABLE execution_log_partitioned (
    LIKE execution_log INCLUDING ALL
) PARTITION BY RANGE (timestamp);

-- Create partitions (example for 2026)
CREATE TABLE execution_log_2026_01 PARTITION OF execution_log_partitioned
    FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');
-- ... more partitions as needed
```

---

## Time-Series Tables

### gas_price_history

Stores historical gas prices for cost analysis.

```sql
CREATE TABLE gas_price_history (
    timestamp TIMESTAMPTZ NOT NULL,
    chain_id INTEGER NOT NULL,

    -- Gas Prices
    gas_price_gwei NUMERIC(10,2) NOT NULL,
    base_fee_gwei NUMERIC(10,2),  -- EIP-1559
    priority_fee_gwei NUMERIC(10,2),  -- EIP-1559

    -- Native Token Price
    native_token_price_usd NUMERIC(10,2),

    -- Block Info
    block_number BIGINT NOT NULL,

    -- Cost Estimates (denormalized for fast queries)
    simple_transfer_cost_usd NUMERIC(8,4),
    dex_swap_cost_usd NUMERIC(8,4),
    flash_arbitrage_cost_usd NUMERIC(8,4),

    -- Congestion Indicator
    congestion_level VARCHAR(20),

    PRIMARY KEY (timestamp, chain_id)
);

-- Convert to TimescaleDB hypertable
SELECT create_hypertable(
    'gas_price_history',
    'timestamp',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- Create index on chain_id for faster queries
CREATE INDEX idx_gas_price_chain ON gas_price_history(chain_id, timestamp DESC);

-- Add compression policy (compress data older than 7 days)
SELECT add_compression_policy(
    'gas_price_history',
    INTERVAL '7 days',
    if_not_exists => TRUE
);

-- Add retention policy (keep data for 90 days)
SELECT add_retention_policy(
    'gas_price_history',
    INTERVAL '90 days',
    if_not_exists => TRUE
);

-- Continuous aggregate for hourly averages
CREATE MATERIALIZED VIEW gas_price_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', timestamp) AS hour,
    chain_id,
    AVG(gas_price_gwei) AS avg_gas_price_gwei,
    MIN(gas_price_gwei) AS min_gas_price_gwei,
    MAX(gas_price_gwei) AS max_gas_price_gwei,
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY gas_price_gwei) AS median_gas_price_gwei,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY gas_price_gwei) AS p95_gas_price_gwei,
    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY gas_price_gwei) AS p99_gas_price_gwei,
    AVG(flash_arbitrage_cost_usd) AS avg_arbitrage_cost_usd
FROM gas_price_history
GROUP BY hour, chain_id
WITH NO DATA;

-- Refresh policy for continuous aggregate
SELECT add_continuous_aggregate_policy(
    'gas_price_hourly',
    start_offset => INTERVAL '3 hours',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);
```

---

### price_snapshots

Stores DEX price snapshots for opportunity detection and analysis.

```sql
CREATE TABLE price_snapshots (
    timestamp TIMESTAMPTZ NOT NULL,
    chain_id INTEGER NOT NULL,
    dex_name VARCHAR(50) NOT NULL,

    -- Token Pair
    token_in VARCHAR(42) NOT NULL,
    token_out VARCHAR(42) NOT NULL,
    pair_symbol VARCHAR(50) NOT NULL,  -- E.g., "WETH-USDC"

    -- Price
    price NUMERIC(30,18) NOT NULL,  -- Price of token_out in terms of token_in
    price_usd NUMERIC(12,6),  -- If one token is stablecoin

    -- Liquidity
    liquidity_usd NUMERIC(14,2),
    volume_24h_usd NUMERIC(14,2),

    -- Pool Info
    pool_address VARCHAR(42),

    PRIMARY KEY (timestamp, chain_id, dex_name, token_in, token_out)
);

-- Convert to hypertable
SELECT create_hypertable(
    'price_snapshots',
    'timestamp',
    chunk_time_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);

-- Indexes
CREATE INDEX idx_price_snapshots_chain_pair
ON price_snapshots(chain_id, pair_symbol, timestamp DESC);

CREATE INDEX idx_price_snapshots_dex
ON price_snapshots(dex_name, timestamp DESC);

-- Compression policy
SELECT add_compression_policy(
    'price_snapshots',
    INTERVAL '24 hours',
    if_not_exists => TRUE
);

-- Retention policy (30 days)
SELECT add_retention_policy(
    'price_snapshots',
    INTERVAL '30 days',
    if_not_exists => TRUE
);
```

---

### chain_metrics

Stores operational metrics for each chain.

```sql
CREATE TABLE chain_metrics (
    timestamp TIMESTAMPTZ NOT NULL,
    chain_id INTEGER NOT NULL,

    -- RPC Health
    rpc_latency_ms INTEGER,
    rpc_error_rate NUMERIC(5,4),
    rpc_requests_count INTEGER,

    -- Block Info
    current_block_number BIGINT,
    block_time_seconds NUMERIC(5,2),

    -- Gas Metrics (snapshot)
    current_gas_price_gwei NUMERIC(10,2),

    -- Trading Activity
    opportunities_detected_count INTEGER DEFAULT 0,
    opportunities_executed_count INTEGER DEFAULT 0,
    trades_successful_count INTEGER DEFAULT 0,
    trades_failed_count INTEGER DEFAULT 0,

    -- Profitability (for this time window)
    total_profit_usd NUMERIC(12,2) DEFAULT 0,
    total_gas_cost_usd NUMERIC(10,4) DEFAULT 0,

    -- Health Score
    health_score NUMERIC(5,2),  -- 0-100

    PRIMARY KEY (timestamp, chain_id)
);

-- Convert to hypertable
SELECT create_hypertable(
    'chain_metrics',
    'timestamp',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- Compression
SELECT add_compression_policy(
    'chain_metrics',
    INTERVAL '7 days',
    if_not_exists => TRUE
);

-- Continuous aggregate for daily stats
CREATE MATERIALIZED VIEW chain_daily_stats
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', timestamp) AS day,
    chain_id,
    AVG(rpc_latency_ms) AS avg_rpc_latency_ms,
    MAX(rpc_latency_ms) AS max_rpc_latency_ms,
    AVG(rpc_error_rate) AS avg_rpc_error_rate,
    SUM(opportunities_detected_count) AS total_opportunities,
    SUM(opportunities_executed_count) AS total_executions,
    SUM(trades_successful_count) AS total_successful,
    SUM(total_profit_usd) AS total_profit,
    SUM(total_gas_cost_usd) AS total_gas_cost,
    AVG(health_score) AS avg_health_score
FROM chain_metrics
GROUP BY day, chain_id
WITH NO DATA;
```

---

### performance_metrics

Generic time-series metrics table for application performance.

```sql
CREATE TABLE performance_metrics (
    timestamp TIMESTAMPTZ NOT NULL,

    -- Metric Identity
    metric_name VARCHAR(100) NOT NULL,
    metric_type VARCHAR(20) NOT NULL CHECK (
        metric_type IN ('counter', 'gauge', 'histogram', 'summary')
    ),

    -- Value
    value NUMERIC(20,6) NOT NULL,

    -- Tags (for grouping/filtering)
    tags JSONB,

    PRIMARY KEY (timestamp, metric_name, tags)
);

-- Convert to hypertable
SELECT create_hypertable(
    'performance_metrics',
    'timestamp',
    chunk_time_interval => INTERVAL '6 hours',
    if_not_exists => TRUE
);

-- Indexes
CREATE INDEX idx_performance_metrics_name
ON performance_metrics(metric_name, timestamp DESC);

CREATE INDEX idx_performance_metrics_tags
ON performance_metrics USING GIN(tags);

-- Compression policy (aggressive - compress after 1 day)
SELECT add_compression_policy(
    'performance_metrics',
    INTERVAL '1 day',
    if_not_exists => TRUE
);

-- Retention policy (keep for 30 days)
SELECT add_retention_policy(
    'performance_metrics',
    INTERVAL '30 days',
    if_not_exists => TRUE
);
```

---

## Configuration Tables

### chains

Stores supported blockchain configurations.

```sql
CREATE TABLE chains (
    id SERIAL PRIMARY KEY,

    -- Identity
    chain_id INTEGER UNIQUE NOT NULL,  -- Blockchain chain ID
    name VARCHAR(50) UNIQUE NOT NULL,
    chain_type VARCHAR(20) NOT NULL CHECK (chain_type IN ('mainnet', 'testnet')),

    -- Blockchain Properties
    native_token VARCHAR(10) NOT NULL,  -- ETH, MATIC, etc.
    supports_eip1559 BOOLEAN NOT NULL DEFAULT FALSE,
    target_block_time_seconds INTEGER NOT NULL,

    -- Smart Contracts
    flash_loan_contract_address VARCHAR(42),
    aave_pool_provider_address VARCHAR(42),

    -- Operational Config
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    priority INTEGER NOT NULL,  -- Lower = higher priority

    -- Economic Parameters
    min_net_profit_usd NUMERIC(8,2) NOT NULL DEFAULT 10.00,
    min_roi_percent NUMERIC(6,3) NOT NULL DEFAULT 0.100,
    max_flash_loan_usd NUMERIC(12,2) NOT NULL DEFAULT 100000.00,
    slippage_tolerance NUMERIC(6,5) NOT NULL DEFAULT 0.00500,  -- 0.5%
    max_gas_price_gwei NUMERIC(10,2),

    -- Metadata
    metadata JSONB,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Insert initial chains
INSERT INTO chains (chain_id, name, chain_type, native_token, supports_eip1559, target_block_time_seconds, priority) VALUES
    (137, 'Polygon', 'mainnet', 'MATIC', TRUE, 2, 1),
    (42161, 'Arbitrum', 'mainnet', 'ETH', TRUE, 1, 2),
    (10, 'Optimism', 'mainnet', 'ETH', TRUE, 2, 3),
    (8453, 'Base', 'mainnet', 'ETH', TRUE, 2, 4),
    (80001, 'Mumbai', 'testnet', 'MATIC', TRUE, 2, 10);

-- Indexes
CREATE UNIQUE INDEX idx_chains_chain_id ON chains(chain_id);
CREATE INDEX idx_chains_enabled ON chains(enabled, priority);
```

---

### dexes

Stores DEX configurations per chain.

```sql
CREATE TABLE dexes (
    id SERIAL PRIMARY KEY,

    -- Identity
    chain_id INTEGER NOT NULL REFERENCES chains(id),
    name VARCHAR(50) NOT NULL,  -- uniswap_v3, sushiswap, etc.
    dex_type VARCHAR(20) NOT NULL CHECK (dex_type IN ('v2', 'v3', 'stable', 'other')),

    -- Contract Addresses
    router_address VARCHAR(42) NOT NULL,
    factory_address VARCHAR(42) NOT NULL,
    quoter_address VARCHAR(42),  -- For V3 DEXes

    -- Configuration
    fee_tiers INTEGER[],  -- For V3: [500, 3000, 10000] = [0.05%, 0.3%, 1%]
    supports_multihop BOOLEAN NOT NULL DEFAULT TRUE,

    -- Operational
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    priority INTEGER NOT NULL DEFAULT 1,

    -- Metadata
    metadata JSONB,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(chain_id, name)
);

-- Insert initial DEXes (Polygon)
INSERT INTO dexes (chain_id, name, dex_type, router_address, factory_address, quoter_address, fee_tiers, priority) VALUES
    (1, 'uniswap_v3', 'v3', '0xE592427A0AEce92De3Edee1F18E0157C05861564', '0x1F98431c8aD98523631AE4a59f267346ea31F984', '0xb27308f9F90D607463bb33eA1BeBb41C27CE5AB6', ARRAY[500, 3000, 10000], 1),
    (1, 'sushiswap', 'v2', '0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506', '0xc35DADB65012eC5796536bD9864eD8773aBc74C4', NULL, NULL, 2),
    (1, 'quickswap', 'v2', '0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff', '0x5757371414417b8C6CAad45bAeF941aBc7d3Ab32', NULL, NULL, 3);

-- Indexes
CREATE INDEX idx_dexes_chain ON dexes(chain_id, enabled);
```

---

### tokens

Stores token configurations per chain.

```sql
CREATE TABLE tokens (
    id SERIAL PRIMARY KEY,

    -- Identity
    chain_id INTEGER NOT NULL REFERENCES chains(id),
    address VARCHAR(42) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    name VARCHAR(100),
    decimals INTEGER NOT NULL,

    -- Classification
    token_type VARCHAR(20) CHECK (token_type IN ('stable', 'wrapped', 'native', 'governance', 'other')),

    -- Trading Config
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    min_trade_amount NUMERIC(30,0),  -- Minimum amount in wei
    max_trade_amount NUMERIC(30,0),  -- Maximum amount in wei

    -- Metadata
    logo_url TEXT,
    coingecko_id VARCHAR(100),
    metadata JSONB,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(chain_id, address)
);

-- Insert common tokens (Polygon)
INSERT INTO tokens (chain_id, address, symbol, name, decimals, token_type, enabled) VALUES
    (1, '0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619', 'WETH', 'Wrapped Ether', 18, 'wrapped', TRUE),
    (1, '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174', 'USDC', 'USD Coin', 6, 'stable', TRUE),
    (1, '0xc2132D05D31c914a87C6611C10748AEb04B58e8F', 'USDT', 'Tether USD', 6, 'stable', TRUE),
    (1, '0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063', 'DAI', 'Dai Stablecoin', 18, 'stable', TRUE),
    (1, '0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270', 'WMATIC', 'Wrapped MATIC', 18, 'wrapped', TRUE);

-- Indexes
CREATE INDEX idx_tokens_chain_symbol ON tokens(chain_id, symbol);
CREATE INDEX idx_tokens_address ON tokens(chain_id, address);
```

---

### risk_config

Stores risk management configuration.

```sql
CREATE TABLE risk_config (
    id SERIAL PRIMARY KEY,

    -- Scope (NULL = global, chain_id = chain-specific)
    chain_id INTEGER REFERENCES chains(id),

    -- Position Limits
    max_position_size_usd NUMERIC(12,2),
    max_total_exposure_usd NUMERIC(14,2),
    max_concentration_percent NUMERIC(5,2),  -- Max % in single token

    -- Loss Limits
    daily_loss_limit_usd NUMERIC(10,2),
    weekly_loss_limit_usd NUMERIC(10,2),
    monthly_loss_limit_usd NUMERIC(12,2),

    -- Circuit Breaker
    consecutive_failures_warning INTEGER DEFAULT 3,
    consecutive_failures_cooldown INTEGER DEFAULT 5,
    consecutive_failures_shutdown INTEGER DEFAULT 10,
    cooldown_duration_seconds INTEGER DEFAULT 300,

    -- Rate Limiting
    max_trades_per_minute INTEGER DEFAULT 10,
    max_trades_per_hour INTEGER DEFAULT 200,
    max_trades_per_day INTEGER DEFAULT 1000,

    -- Emergency
    emergency_shutdown BOOLEAN DEFAULT FALSE,
    emergency_shutdown_reason TEXT,
    emergency_shutdown_at TIMESTAMPTZ,

    -- Metadata
    updated_by VARCHAR(100),
    notes TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(chain_id)  -- One config per chain (NULL for global)
);

-- Insert global config
INSERT INTO risk_config (
    chain_id,
    max_position_size_usd,
    max_total_exposure_usd,
    max_concentration_percent,
    daily_loss_limit_usd,
    weekly_loss_limit_usd,
    consecutive_failures_shutdown
) VALUES (
    NULL,  -- Global
    100000,
    500000,
    30.00,
    5000,
    15000,
    10
);
```

---

## Operational Tables

### rpc_providers

Stores RPC provider configurations and health metrics.

```sql
CREATE TABLE rpc_providers (
    id SERIAL PRIMARY KEY,

    -- Identity
    chain_id INTEGER NOT NULL REFERENCES chains(id),
    name VARCHAR(50) NOT NULL,
    url TEXT NOT NULL,

    -- Configuration
    priority INTEGER NOT NULL DEFAULT 1,  -- Lower = higher priority
    rate_limit_per_second INTEGER NOT NULL DEFAULT 10,
    supports_websocket BOOLEAN DEFAULT FALSE,
    requires_api_key BOOLEAN DEFAULT FALSE,

    -- Health Metrics (updated periodically)
    is_healthy BOOLEAN DEFAULT TRUE,
    last_health_check_at TIMESTAMPTZ,
    consecutive_failures INTEGER DEFAULT 0,
    total_requests BIGINT DEFAULT 0,
    total_errors BIGINT DEFAULT 0,
    avg_latency_ms NUMERIC(8,2),

    -- Operational
    enabled BOOLEAN DEFAULT TRUE,

    -- Metadata
    metadata JSONB,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Insert RPC providers for Polygon
INSERT INTO rpc_providers (chain_id, name, url, priority, rate_limit_per_second, requires_api_key) VALUES
    (1, 'Alchemy', 'https://polygon-mainnet.g.alchemy.com/v2/{API_KEY}', 1, 25, TRUE),
    (1, 'Ankr', 'https://rpc.ankr.com/polygon', 2, 10, FALSE),
    (1, 'Polygon Public', 'https://polygon-rpc.com', 3, 5, FALSE);

-- Indexes
CREATE INDEX idx_rpc_providers_chain ON rpc_providers(chain_id, enabled, priority);
```

---

### alerts

Stores system alerts.

```sql
CREATE TABLE alerts (
    id BIGSERIAL PRIMARY KEY,

    -- Alert Details
    alert_type VARCHAR(50) NOT NULL,  -- gas_spike, loss_limit, circuit_breaker, etc.
    severity VARCHAR(20) NOT NULL CHECK (
        severity IN ('info', 'warning', 'critical')
    ),
    title VARCHAR(200) NOT NULL,
    message TEXT NOT NULL,

    -- Context
    chain_id INTEGER,
    opportunity_id BIGINT REFERENCES opportunities(id),
    transaction_id BIGINT REFERENCES transactions(id),

    -- Status
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (
        status IN ('active', 'acknowledged', 'resolved')
    ),
    acknowledged_at TIMESTAMPTZ,
    acknowledged_by VARCHAR(100),
    resolved_at TIMESTAMPTZ,
    resolved_by VARCHAR(100),

    -- Notification
    notified_via VARCHAR(50)[],  -- ['telegram', 'email', 'pagerduty']
    notified_at TIMESTAMPTZ,

    -- Additional Data
    data JSONB,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_alerts_created_at ON alerts(created_at DESC);
CREATE INDEX idx_alerts_status ON alerts(status) WHERE status = 'active';
CREATE INDEX idx_alerts_severity ON alerts(severity, created_at DESC)
WHERE status = 'active';
```

---

### audit_log

Stores all configuration changes and admin actions.

```sql
CREATE TABLE audit_log (
    id BIGSERIAL PRIMARY KEY,

    -- Action
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    action_type VARCHAR(50) NOT NULL,  -- config_change, emergency_pause, etc.
    action VARCHAR(200) NOT NULL,

    -- User/System
    performed_by VARCHAR(100) NOT NULL,  -- user_id or 'system'
    user_ip VARCHAR(45),

    -- Context
    table_name VARCHAR(100),
    record_id BIGINT,

    -- Changes
    old_values JSONB,
    new_values JSONB,

    -- Metadata
    notes TEXT,
    metadata JSONB
);

-- Indexes
CREATE INDEX idx_audit_log_timestamp ON audit_log(timestamp DESC);
CREATE INDEX idx_audit_log_performed_by ON audit_log(performed_by, timestamp DESC);
CREATE INDEX idx_audit_log_action_type ON audit_log(action_type, timestamp DESC);

-- Partition by month
CREATE TABLE audit_log_partitioned (
    LIKE audit_log INCLUDING ALL
) PARTITION BY RANGE (timestamp);
```

---

## Helper Functions & Triggers

### Update Timestamp Trigger

```sql
-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply to all tables with updated_at
CREATE TRIGGER update_opportunities_updated_at
    BEFORE UPDATE ON opportunities
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_transactions_updated_at
    BEFORE UPDATE ON transactions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_chains_updated_at
    BEFORE UPDATE ON chains
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- (Apply to other tables similarly)
```

---

### Audit Trigger

```sql
-- Function to log config changes
CREATE OR REPLACE FUNCTION log_config_change()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO audit_log (
        action_type,
        action,
        performed_by,
        table_name,
        record_id,
        old_values,
        new_values
    ) VALUES (
        'config_change',
        TG_OP,  -- INSERT, UPDATE, DELETE
        current_user,
        TG_TABLE_NAME,
        COALESCE(NEW.id, OLD.id),
        to_jsonb(OLD),
        to_jsonb(NEW)
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply to config tables
CREATE TRIGGER audit_chains_changes
    AFTER INSERT OR UPDATE OR DELETE ON chains
    FOR EACH ROW
    EXECUTE FUNCTION log_config_change();

CREATE TRIGGER audit_risk_config_changes
    AFTER INSERT OR UPDATE OR DELETE ON risk_config
    FOR EACH ROW
    EXECUTE FUNCTION log_config_change();
```

---

## Migration Strategy

### Migration 001: Initial Schema

```sql
-- migrations/001_initial_schema.up.sql

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Create tables in dependency order
-- (All table creation statements from above)

-- Create indexes
-- (All index creation statements from above)

-- Create hypertables
-- (All hypertable creation statements from above)

-- Create materialized views
-- (All materialized view creation statements from above)

-- Insert seed data
-- (All seed data insertion statements from above)
```

```sql
-- migrations/001_initial_schema.down.sql

-- Drop in reverse order
DROP MATERIALIZED VIEW IF EXISTS gas_price_hourly CASCADE;
DROP MATERIALIZED VIEW IF EXISTS chain_daily_stats CASCADE;
DROP MATERIALIZED VIEW IF EXISTS daily_pnl CASCADE;

DROP TABLE IF EXISTS audit_log CASCADE;
DROP TABLE IF EXISTS alerts CASCADE;
DROP TABLE IF EXISTS rpc_providers CASCADE;
DROP TABLE IF EXISTS risk_config CASCADE;
DROP TABLE IF EXISTS tokens CASCADE;
DROP TABLE IF EXISTS dexes CASCADE;
DROP TABLE IF EXISTS chains CASCADE;

DROP TABLE IF EXISTS performance_metrics CASCADE;
DROP TABLE IF EXISTS chain_metrics CASCADE;
DROP TABLE IF EXISTS price_snapshots CASCADE;
DROP TABLE IF EXISTS gas_price_history CASCADE;

DROP TABLE IF EXISTS execution_log CASCADE;
DROP TABLE IF EXISTS trade_results CASCADE;
DROP TABLE IF EXISTS transactions CASCADE;
DROP TABLE IF EXISTS opportunities CASCADE;

DROP FUNCTION IF EXISTS update_updated_at_column CASCADE;
DROP FUNCTION IF EXISTS log_config_change CASCADE;
```

---

## Data Retention Policies

### Automatic Cleanup

```sql
-- Already defined with hypertables:
-- - gas_price_history: 90 days
-- - price_snapshots: 30 days
-- - chain_metrics: compress after 7 days
-- - performance_metrics: 30 days

-- Additional manual cleanup for non-hypertables

-- Archive old opportunities (>30 days)
CREATE OR REPLACE FUNCTION archive_old_opportunities()
RETURNS void AS $$
BEGIN
    -- Move to archive table (if needed)
    -- Or simply delete
    DELETE FROM opportunities
    WHERE detected_at < NOW() - INTERVAL '30 days'
      AND status IN ('completed', 'failed', 'expired', 'rejected');
END;
$$ LANGUAGE plpgsql;

-- Schedule via cron or pg_cron
SELECT cron.schedule('archive-opportunities', '0 2 * * *', 'SELECT archive_old_opportunities()');
```

---

## Backup & Recovery

### Backup Strategy

```bash
#!/bin/bash
# Daily backup script

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups/postgres"
DB_NAME="arbitrage_bot"

# Full backup
pg_dump -Fc $DB_NAME > $BACKUP_DIR/full_backup_$TIMESTAMP.dump

# Compress
gzip $BACKUP_DIR/full_backup_$TIMESTAMP.dump

# Upload to S3
aws s3 cp $BACKUP_DIR/full_backup_$TIMESTAMP.dump.gz \
    s3://my-backups/postgres/

# Delete local backups older than 7 days
find $BACKUP_DIR -name "*.dump.gz" -mtime +7 -delete

# Delete S3 backups older than 30 days
aws s3 ls s3://my-backups/postgres/ | \
    awk '{if ($1 < "'$(date --date='30 days ago' +%Y-%m-%d)'") print $4}' | \
    xargs -I {} aws s3 rm s3://my-backups/postgres/{}
```

### Point-in-Time Recovery

```bash
# Enable WAL archiving in postgresql.conf
wal_level = replica
archive_mode = on
archive_command = 'aws s3 cp %p s3://my-backups/postgres/wal/%f'
```

---

**Document Status:** Complete
**Last Updated:** 2026-01-19
**Version:** 1.0
