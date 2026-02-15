# Quickstart Guide

Get the arbitrage + liquidation bot running from zero to monitoring in 10 steps.

## Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Foundry (`curl -L https://foundry.paradigm.xyz | bash && foundryup`)
- Git

## Step 1: Clone & Install

```bash
git clone <repo-url> && cd arb_bot_cryp_eea
cp .env.example .env
make install-dev
```

## Step 2: Configure Environment

Edit `.env` with your values:

```bash
# Required — RPC endpoints (get free ones from Alchemy/Infura)
POLYGON_AMOY_RPC_URL=https://polygon-amoy.g.alchemy.com/v2/YOUR_KEY
ARBITRUM_SEPOLIA_RPC_URL=https://arb-sepolia.g.alchemy.com/v2/YOUR_KEY

# Required — Private key (option A: keystore, option B: env var)
# Option A (recommended):
python -m src.utils.key_manager create
# Then set: KEYSTORE_FILE=keystore/deployer.json

# Option B (dev/CI only):
# PRIVATE_KEY=0x...

# Optional — Telegram alerts
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

## Step 3: Validate Configuration

```bash
python scripts/validate_config.py
```

All checks should show PASS or WARN (warnings are non-blocking).

## Step 4: Start Infrastructure

```bash
make docker-up
```

This starts PostgreSQL (TimescaleDB) and Redis. Wait for health checks to pass.

## Step 5: Run Database Migrations

```bash
make migrate
```

Creates all required tables (chains, tokens, opportunities, trades, etc.).

## Step 6: Deploy Contracts (Testnet)

```bash
# Polygon Amoy
forge script script/Deploy.s.sol --rpc-url polygon_amoy --broadcast --verify

# Arbitrum Sepolia
forge script script/Deploy.s.sol --rpc-url arbitrum_sepolia --broadcast --verify
```

Copy the deployed addresses into `.env`:

```bash
FLASH_LOAN_ARBITRAGE_ADDRESS=0x...
UNISWAP_V3_ADAPTER_ADDRESS=0x...
UNISWAP_V2_ADAPTER_ADDRESS=0x...
```

## Step 7: Run Smoke Test

```bash
python scripts/testnet_smoke_test.py --chain polygon_amoy
python scripts/testnet_smoke_test.py --chain arbitrum_sepolia
```

Verifies: RPC connection, chain ID, contract deployment, DB connectivity, module imports.

## Step 8: Start Bot (Dry Run)

```bash
# Ensure dry-run is enabled (default)
# DRY_RUN=true in .env or Config defaults

# Arbitrage bot
python run_bot.py --chain polygon_amoy

# Or with Docker
docker-compose up -d arb-bot
```

The bot will scan for opportunities but not execute real transactions.

## Step 9: Monitor

```bash
# Health check
curl http://localhost:8080/health

# Full metrics
curl http://localhost:8080/api/status

# Prometheus metrics
curl http://localhost:8080/metrics

# Docker logs
make logs
```

## Step 10: Enable Live Execution

Only after 48+ hours of successful dry-run:

1. Review the [Production Checklist](PRODUCTION_CHECKLIST.md)
2. Set `DRY_RUN=false` in `.env`
3. Set `EXECUTION_MODE=mainnet`
4. Fund wallet with gas tokens
5. Restart: `docker-compose restart arb-bot`

## Makefile Reference

| Command | Description |
|---------|-------------|
| `make install` | Install runtime dependencies |
| `make install-dev` | Install runtime + dev dependencies |
| `make test` | Run Python tests with coverage |
| `make test-contracts` | Run Foundry tests |
| `make lint` | Run flake8 + mypy |
| `make format` | Auto-format with black + isort |
| `make docker-build` | Build bot Docker image |
| `make docker-up` | Start Postgres + Redis + bot |
| `make docker-down` | Stop all containers |
| `make migrate` | Run database migrations |
| `make validate` | Run config validation |
| `make smoke-test` | Run testnet smoke test |
| `make status` | Check bot health endpoint |
| `make logs` | Tail Docker logs |

## Directory Structure

```
arb_bot_cryp_eea/
├── src/                    # Python bot source
│   ├── config.py           # Chain configs, risk params
│   ├── opportunity_detector.py
│   ├── flash_loan_orchestrator.py
│   ├── liquidation_detector.py
│   ├── liquidation_orchestrator.py
│   ├── api/health.py       # Health/metrics HTTP server
│   ├── db/                 # SQLAlchemy models + DB layer
│   └── utils/              # Gas, risk, metrics, logging, price cache
├── contracts/              # Solidity contracts
├── test/                   # Foundry tests
├── tests/                  # Python tests
├── scripts/                # Validation, smoke test, deployment
├── config/                 # Prometheus, alert rules, token lists
├── alembic/                # Database migrations
├── dashboard/              # Web dashboard (API + frontend)
├── agent/                  # ARIA AI agent
├── docker-compose.yml      # Infrastructure services
├── Dockerfile              # Bot container
└── Makefile                # Quick-start targets
```

## Next Steps

- [Configuration Guide](CONFIGURATION.md) — All environment variables and config options
- [Operations Runbook](OPERATIONS_RUNBOOK.md) — Daily/weekly maintenance procedures
- [Troubleshooting](TROUBLESHOOTING.md) — Common issues and solutions
- [Security Checklist](SECURITY_CHECKLIST.md) — Pre-production security gate
- [Architecture](ARCHITECTURE.md) — System design and data flow
