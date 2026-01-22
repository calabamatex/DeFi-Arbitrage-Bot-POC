# System Architecture

## Overview

The arbitrage bot is a modular system with clear separation of concerns:

```
┌─────────────────────────────────────────────────┐
│              Main Orchestrator                  │
│           (src/bot/main.py)                     │
└─────────────────┬───────────────────────────────┘
                  │
        ┌─────────┴─────────┐
        │                   │
        ▼                   ▼
┌──────────────┐    ┌──────────────┐
│     DEX      │    │   Arbitrage  │
│  Adapters    │    │    Logic     │
└──────────────┘    └──────────────┘
        │                   │
        └─────────┬─────────┘
                  │
        ┌─────────┴─────────┐
        │                   │
        ▼                   ▼
┌──────────────┐    ┌──────────────┐
│     Risk     │    │ Transaction  │
│  Management  │    │   Manager    │
└──────────────┘    └──────────────┘
```

## Core Components

### 1. Main Orchestrator (`src/bot/main.py`)
- Initializes all components
- Runs main trading loop
- Coordinates opportunity detection and execution
- Handles graceful shutdown

### 2. DEX Adapters (`src/dex/`)
- **Uniswap V3**: Concentrated liquidity, multiple fee tiers
- **SushiSwap**: Uniswap V2 fork
- **QuickSwap**: Uniswap V2 fork, Polygon-native

Each adapter implements:
- `get_token_price()` - Fetch current price
- `execute_trade()` - Execute swap
- `get_liquidity_depth()` - Check available liquidity

### 3. Arbitrage Logic (`src/bot/arbitrage.py`)
- Fetches prices from all DEXes concurrently
- Identifies price discrepancies
- Calculates expected profit
- Accounts for gas costs
- Validates profitability

### 4. Risk Management (`src/utils/risk_manager.py`)

Five-layer protection:

1. **BalanceValidator** - Ensures sufficient funds
2. **PositionManager** - Enforces size/exposure limits
3. **LossTracker** - Monitors P/L, enforces loss limits
4. **CircuitBreaker** - Stops trading after consecutive losses
5. **RiskManager** - Coordinates all risk checks

### 5. Transaction Management (`src/utils/transaction_manager.py`)
- Thread-safe nonce management
- Transaction building and signing
- Confirmation monitoring
- Retry logic

### 6. Slippage Protection (`src/utils/slippage_protection.py`)
- Calculates minimum acceptable output
- Validates execution price
- Estimates price impact
- Determines safe trade sizes

### 7. Emergency Shutdown (`src/utils/emergency_shutdown.py`)
- Automatic triggers (loss limits, etc.)
- Manual emergency stop
- Admin-protected reset
- Telegram alerts

### 8. Metrics Collection (`src/utils/metrics_collector.py`)
- Tracks all bot activity
- Records opportunities, trades, profits/losses
- Monitors performance metrics
- Exports to JSON and Prometheus formats

### 9. Performance Monitoring (`src/utils/performance_monitor.py`)
- Tracks detection and execution times
- Monitors RPC call rates
- Measures memory and CPU usage
- Validates against performance targets

## Data Flow

### Opportunity Detection Flow

```
1. Main loop triggers detection
2. For each token pair:
   a. Fetch prices from all DEXes (parallel)
   b. Find min/max prices
   c. Calculate gross profit
   d. Subtract gas costs
   e. Validate profitability
3. Score and prioritize opportunities
4. Return best opportunities
```

### Trade Execution Flow

```
1. Risk manager validates trade
   - Check balance
   - Check position size
   - Check exposure limits
   - Check loss limits
   - Check circuit breaker
2. If approved:
   a. Approve tokens (if needed)
   b. Execute buy trade
   c. Execute sell trade
   d. Record results
3. Update all trackers
4. Send notifications
```

## Design Decisions

### Why Polygon?
- Lower gas costs than Ethereum
- Less MEV bot competition
- Fast block times (2s)
- Growing DeFi ecosystem

### Why These DEXes?
- **Uniswap V3**: Most liquidity, price leader
- **SushiSwap**: Second-most liquidity
- **QuickSwap**: Polygon-native, different user base

### Why Async/Await?
- Parallel price fetching (3x faster)
- Non-blocking I/O operations
- Better resource utilization

### Why Multiple Risk Layers?
- Defense in depth
- No single point of failure
- Progressive warnings before shutdown

## Performance Optimizations

1. **Price Caching** - 3-second cache reduces RPC calls
2. **Connection Pooling** - Reuse HTTP connections
3. **Parallel Fetching** - `asyncio.gather()` for prices
4. **Token Approvals** - Approve unlimited once
5. **Gas Optimization** - EIP-1559 for better pricing
6. **Multicall** - Batch RPC requests
7. **Rolling Windows** - Keep only recent metrics data

## Security Measures

1. **No hardcoded keys** - All secrets in .env
2. **Input validation** - All user inputs validated
3. **Error handling** - Comprehensive try/catch
4. **Logging** - Security events logged
5. **Rate limiting** - Prevent RPC abuse
6. **Circuit breakers** - Auto-stop on losses
7. **Emergency shutdown** - Multiple safety triggers

## Testing Strategy

- **Unit Tests**: Individual components (30+ tests)
- **Integration Tests**: Component interactions (9 tests)
- **Testnet Tests**: Real blockchain validation
- **Performance Tests**: Speed/efficiency benchmarks
- **Edge Case Tests**: Boundary conditions

Target: >90% code coverage

## Deployment Architecture

### Testnet
```
Developer Machine
  ├── Bot Process
  ├── Logs (local files)
  └── Metrics (local files)
```

### Mainnet (Recommended)
```
Cloud Server (VPS)
  ├── Bot Process (systemd service)
  ├── Logs (rotated daily)
  ├── Metrics (exported hourly)
  └── Monitoring (Prometheus/Grafana)
```

## Component Dependencies

```
Main Orchestrator
  ├── DEX Adapters (QuickSwap, SushiSwap, UniswapV3)
  ├── Risk Manager
  │   ├── Balance Validator
  │   ├── Position Manager
  │   ├── Loss Tracker
  │   └── Circuit Breaker
  ├── Transaction Manager
  ├── Slippage Protection
  ├── Emergency Shutdown
  ├── Opportunity Scorer
  ├── Metrics Collector
  ├── Performance Monitor
  └── Telegram Bot
```

## Future Enhancements

Potential improvements:
- Cross-chain arbitrage
- Flash loan integration
- MEV protection
- Machine learning for opportunity prediction
- Multi-account support
- Advanced order types
- Dynamic gas pricing
- Liquidity aggregation

## Technical Stack

- **Language**: Python 3.9+
- **Blockchain**: Web3.py 7.7.0
- **Async**: asyncio
- **Testing**: pytest, pytest-asyncio
- **Formatting**: Black
- **Type Checking**: mypy (optional)
- **Monitoring**: Prometheus metrics
- **Notifications**: python-telegram-bot

## Key Design Patterns

1. **Strategy Pattern**: DEX adapters
2. **Factory Pattern**: Configuration loading
3. **Observer Pattern**: Event notifications
4. **Singleton Pattern**: RiskManager, MetricsCollector
5. **Decorator Pattern**: Performance monitoring
6. **Command Pattern**: Emergency shutdown

## Error Handling Philosophy

- **Fail gracefully**: Never crash the bot
- **Log everything**: All errors logged with context
- **Alert on critical**: Emergency shutdown triggers alerts
- **Retry logic**: Network errors get retries
- **Circuit breakers**: Auto-stop on repeated failures
