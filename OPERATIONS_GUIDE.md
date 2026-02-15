# Operations Guide - Flash Loan Arbitrage Bot

## Table of Contents

1. [Pre-Flight Checklist](#pre-flight-checklist)
2. [Environment Configuration](#environment-configuration)
3. [Starting the Bot](#starting-the-bot)
4. [Monitoring](#monitoring)
5. [Risk Management](#risk-management)
6. [Emergency Procedures](#emergency-procedures)
7. [Troubleshooting](#troubleshooting)
8. [Maintenance](#maintenance)

---

## Pre-Flight Checklist

Before starting the bot on any chain, verify:

- [ ] `.env` file exists with all required variables (see below)
- [ ] `PRIVATE_KEY` is set in `.env` (never hardcoded in source)
- [ ] Wallet has sufficient native token for gas (0.5+ MATIC/ETH)
- [ ] Database (PostgreSQL) is running and accessible
- [ ] RPC endpoint is responsive (`curl -s <RPC_URL> -X POST -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'`)
- [ ] Smart contracts are deployed and adapters registered
- [ ] `DRY_RUN=true` for initial runs
- [ ] `ADMIN_RESET_CODE` is set (required for emergency shutdown reset)

---

## Environment Configuration

### Required Variables

```bash
# Blockchain
POLYGON_RPC_URL=https://polygon-mainnet.g.alchemy.com/v2/<YOUR_KEY>
ARBITRUM_RPC_URL=https://arb-mainnet.g.alchemy.com/v2/<YOUR_KEY>
PRIVATE_KEY=<your_private_key>                    # Never commit this

# Smart Contracts
FLASH_LOAN_ARBITRAGE_ADDRESS=<deployed_address>
UNISWAP_V3_ADAPTER_ADDRESS=<deployed_address>
UNISWAP_V2_ADAPTER_ADDRESS=<deployed_address>

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/arb_bot

# Security
ADMIN_RESET_CODE=<strong_random_string>           # For emergency shutdown reset
```

### Optional Variables

```bash
# Execution
DRY_RUN=true                      # true = simulate only, false = real execution
DIRECT_EXECUTION=true             # true = execute immediately, false = queue to DB
NATIVE_TOKEN_PRICE_USD=0.80       # Current price of native gas token

# Detection Tuning
MIN_PROFIT_USD=1.0                # Minimum profit to trigger execution
MAX_GAS_PRICE_GWEI=100            # Skip opportunities when gas is above this
CHECK_INTERVAL=5                  # Seconds between scans
MIN_FLASH_LOAN_USD=500            # Minimum flash loan amount
MAX_FLASH_LOAN_USD=100000         # Maximum flash loan amount

# Risk Limits
MAX_POSITION_SIZE_USD=10000       # Max single trade size
MAX_TOTAL_EXPOSURE_USD=50000      # Max total open exposure
DAILY_LOSS_LIMIT_USD=1000         # Daily loss limit before circuit breaker
MAX_CONSECUTIVE_LOSSES=5          # Consecutive losses before circuit breaker
CIRCUIT_BREAKER_COOLDOWN_MIN=60   # Minutes to wait after circuit breaker trips

# Notifications (optional)
TELEGRAM_BOT_TOKEN=<token>
TELEGRAM_CHAT_ID=<chat_id>
```

### Chain-Specific Notes

| Chain    | Native Token | Typical Gas | RPC Env Var         |
|----------|-------------|-------------|---------------------|
| Polygon  | MATIC       | 30-100 gwei | POLYGON_RPC_URL     |
| Arbitrum | ETH         | 0.1-1 gwei  | ARBITRUM_RPC_URL    |
| Optimism | ETH         | 0.001 gwei  | OPTIMISM_RPC_URL    |
| Base     | ETH         | 0.001 gwei  | BASE_RPC_URL        |

---

## Starting the Bot

### Single Chain

```bash
source .venv/bin/activate

# Polygon (default)
python run_bot.py

# Arbitrum
python run_bot.py --chain arbitrum

# With explicit chain
python run_bot.py --chain optimism
```

### Startup Sequence

The bot performs these checks in order:

1. **Config validation** - verifies all required env vars are set
2. **Database connection** - verifies PostgreSQL is accessible
3. **RPC connection** - verifies blockchain node responds
4. **Canary block fetch** - verifies RPC returns real data
5. **Component init** - initializes detector, orchestrator, risk manager, metrics, gas optimizer
6. **Main loop** - starts scanning for opportunities

If any check fails, the bot exits with an error message.

### Recommended First Run

```bash
DRY_RUN=true MIN_PROFIT_USD=0.01 python run_bot.py
```

This will scan for opportunities and log them without executing.

---

## Monitoring

### Log Output

The bot logs to both `bot.log` and stdout. Key log patterns:

```
HEARTBEAT chain=137 scans=100 uptime=1.5h opps=3 executed=1 success=1 daily_pnl=$0.50 circuit_breaker=ok status=OK
```

### Heartbeat Fields

| Field           | Meaning                              |
|----------------|--------------------------------------|
| `chain`         | Chain ID (137=Polygon, 42161=Arb)    |
| `scans`         | Total scan cycles completed          |
| `uptime`        | Time since bot start                 |
| `opps`          | Opportunities detected               |
| `executed`      | Opportunities attempted              |
| `success`       | Successful executions                |
| `daily_pnl`     | Today's profit/loss in USD           |
| `circuit_breaker`| `ok` or `ACTIVE` if tripped         |

### Metrics Files

- `metrics_latest.json` - updated every heartbeat (60s)
- `metrics_final.json` - written on clean shutdown

### What to Watch For

- **circuit_breaker=ACTIVE** - bot has stopped trading due to losses
- **scans increasing but opps=0** - normal in low-volatility markets
- **RPC failure warnings** - RPC node may be rate-limited or down
- **Gas price above threshold** - opportunities skipped (by design)

---

## Risk Management

### Circuit Breaker

The circuit breaker automatically halts trading when:

- Daily losses exceed `DAILY_LOSS_LIMIT_USD`
- Consecutive losses exceed `MAX_CONSECUTIVE_LOSSES`

When active, the bot continues scanning but will not execute trades.

The circuit breaker auto-resets:
- After `CIRCUIT_BREAKER_COOLDOWN_MIN` minutes
- After a successful trade (resets consecutive loss counter)

### Position Limits

Every opportunity is validated against:

1. **Position size** - single trade cannot exceed `MAX_POSITION_SIZE_USD`
2. **Total exposure** - all open positions cannot exceed `MAX_TOTAL_EXPOSURE_USD`
3. **Daily loss** - cumulative daily losses cannot exceed `DAILY_LOSS_LIMIT_USD`

### Pre-Execution Simulation

Before sending any real transaction, the bot:

1. Simulates the transaction via `eth_call`
2. If simulation reverts, the trade is skipped (no gas wasted)
3. Only transactions that pass simulation are broadcast

### Slippage Protection

- First swap step: 5% slippage tolerance (calculates `minAmountOut` from expected intermediate)
- Final output: `minFinalAmount` set based on flash loan repayment + fee
- Transaction deadline: prevents stale transactions from executing

---

## Emergency Procedures

### Emergency Shutdown

If you need to stop all trading immediately:

```python
from src.utils.emergency_shutdown import EmergencyShutdown
shutdown = EmergencyShutdown(risk_manager=risk_manager)
shutdown.trigger_shutdown(reason="Manual emergency stop")
```

Or simply kill the process: `Ctrl+C` (the bot handles SIGINT gracefully).

### Reset After Shutdown

To reset after an emergency shutdown:

1. Set the `ADMIN_RESET_CODE` environment variable
2. Call `risk_manager.reset_shutdown(admin_code)` with the correct code
3. The code is verified with `hmac.compare_digest` (timing-safe)

### Smart Contract Pause

If the on-chain contract needs to be paused:

```bash
cast send $FLASH_LOAN_ARBITRAGE_ADDRESS "pause()" --private-key $PRIVATE_KEY --rpc-url $RPC_URL
```

To unpause:

```bash
cast send $FLASH_LOAN_ARBITRAGE_ADDRESS "unpause()" --private-key $PRIVATE_KEY --rpc-url $RPC_URL
```

---

## Troubleshooting

### Bot won't start

| Symptom                          | Cause                        | Fix                                    |
|----------------------------------|------------------------------|----------------------------------------|
| "Missing required env var"       | `.env` incomplete            | Check all required vars are set        |
| "Database connection failed"     | PostgreSQL down              | Start DB, check `DATABASE_URL`         |
| "Failed to connect to blockchain"| RPC unreachable              | Check RPC URL, network, API key        |
| "RPC canary check failed"       | RPC connected but broken     | Try a different RPC provider           |
| "Config error"                   | Config.validate() failed     | Check `src/config.py` requirements     |

### Bot runs but finds no opportunities

This is normal. Real arbitrage opportunities are rare and compete with MEV bots.

- Lower `MIN_PROFIT_USD` temporarily to see if any are detected
- Verify token pairs have sufficient liquidity on both DEXs
- Check that gas price is below `MAX_GAS_PRICE_GWEI`

### Transaction reverts

- **"Simulation failed"** - pre-execution simulation caught a revert (no gas spent)
- **On-chain revert** - check the transaction on block explorer for revert reason
- Common causes: slippage exceeded, insufficient liquidity, pool state changed

### High gas costs

- Adjust `MAX_GAS_PRICE_GWEI` lower to skip expensive periods
- The gas optimizer uses EIP-1559 pricing: `maxFeePerGas = baseFee * 2 + maxPriorityFeePerGas`

---

## Maintenance

### Database

```bash
# Check database size
psql $DATABASE_URL -c "SELECT pg_size_pretty(pg_database_size(current_database()));"

# View recent trades
psql $DATABASE_URL -c "SELECT * FROM trade_results ORDER BY created_at DESC LIMIT 10;"

# View opportunity stats
psql $DATABASE_URL -c "SELECT status, COUNT(*) FROM opportunities GROUP BY status;"
```

### Log Rotation

The bot writes to `bot.log` continuously. Set up log rotation:

```bash
# /etc/logrotate.d/arb_bot
/path/to/arb_bot_cryp_eea/bot.log {
    daily
    rotate 14
    compress
    missingok
    notifempty
    copytruncate
}
```

### Updating RPC Providers

If your RPC provider becomes unreliable:

1. Stop the bot (`Ctrl+C`)
2. Update the RPC URL in `.env`
3. Restart the bot

### Key Rotation

If you suspect your private key is compromised:

1. **Immediately** stop the bot
2. **Immediately** transfer all funds from the compromised wallet
3. Generate a new wallet: `python generate_new_wallet.py`
4. Update `PRIVATE_KEY` in `.env`
5. Transfer the contract ownership to the new wallet
6. Re-deploy adapters if needed
7. Fund the new wallet with gas tokens
8. Restart the bot

### Running Tests

```bash
source .venv/bin/activate

# Security tests (should always pass)
python -m pytest tests/test_security.py -v --override-ini="addopts="

# Risk manager tests
python -m pytest tests/test_risk_manager.py -v --override-ini="addopts="

# All core tests
python -m pytest tests/test_security.py tests/test_risk_manager.py tests/test_emergency_shutdown.py tests/test_metrics_collector.py tests/test_config.py -v --override-ini="addopts="
```

---

## Architecture Overview

```
run_bot.py (entry point)
  |
  +-- OpportunityDetector     scans DEX prices, finds arbitrage
  |     |
  |     +-- QuoterV2          Uniswap V3 price quotes
  |     +-- QuickSwap Router  Uniswap V2 price quotes
  |
  +-- FlashLoanOrchestrator   builds and sends transactions
  |     |
  |     +-- FlashLoanArbitrageV2.sol  (on-chain)
  |     +-- UniswapV3Adapter.sol      (on-chain)
  |     +-- UniswapV2Adapter.sol      (on-chain)
  |
  +-- RiskManager             validates trades, circuit breaker
  +-- MetricsCollector        records performance data
  +-- GasOptimizer            EIP-1559 gas pricing
  +-- Config                  chain-specific configuration
```

### Execution Flow

1. **Detect**: `OpportunityDetector` queries V3 QuoterV2 + V2 Router for price differences
2. **Validate**: `RiskManager` checks position size, exposure, daily loss, circuit breaker
3. **Simulate**: `eth_call` simulates the transaction off-chain
4. **Execute**: `FlashLoanOrchestrator` signs and broadcasts the transaction
5. **Record**: Trade result logged to database, metrics, and risk manager
6. **Report**: Heartbeat logs and metrics JSON updated periodically
