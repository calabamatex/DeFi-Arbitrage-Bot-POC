# Quickstart — Development & Testnet Setup

Get the arbitrage + liquidation bot running from zero to first dry-run in 8 steps.

> **For production deployment, see [docs/OPERATIONS_RUNBOOK.md](OPERATIONS_RUNBOOK.md).**

## Prerequisites

- **Python 3.11+** (`python3 --version`)
- **Docker & Docker Compose** (`docker compose version`)
- **Foundry** (`curl -L https://foundry.paradigm.xyz | bash && foundryup`)
- **Git** (`git --version`)

---

## 1. Clone the Repository

```bash
git clone <REPO_URL> && cd arb_bot_cryp_eea
```

## 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and fill in:

| Variable | What to set |
|----------|-------------|
| `POSTGRES_PASSWORD` | Generate: `openssl rand -base64 32` |
| `REDIS_PASSWORD` | Generate: `openssl rand -base64 32` |
| `POLYGON_AMOY_RPC_URL` | Free endpoint from Alchemy/Infura for Polygon Amoy (chain 80002) |
| `ARBITRUM_SEPOLIA_RPC_URL` | Free endpoint from Alchemy/Infura for Arbitrum Sepolia (chain 421614) |

Leave `EXECUTION_MODE=testnet` and `DRY_RUN=true` (defaults).

## 3. Create Encrypted Keystore

```bash
python -m src.utils.key_manager create
```

Follow the prompts to encrypt your deployer private key. Then set:

```bash
# In .env
KEYSTORE_FILE=keystore/deployer.json
```

> **Never set `PRIVATE_KEY` directly in `.env`.** Use the encrypted keystore for all key management.

## 4. Set Up Infrastructure

```bash
make setup
```

This runs:
- Installs Python dependencies
- Starts PostgreSQL (TimescaleDB) and Redis via Docker
- Runs database migrations
- Validates configuration

## 5. Deploy Contracts to Testnet

```bash
make deploy-testnet CHAIN=polygon_amoy
```

Copy the deployed addresses into `.env`:

```bash
FLASH_LOAN_ARBITRAGE_ADDRESS=0x...
UNISWAP_V3_ADAPTER_ADDRESS=0x...
UNISWAP_V2_ADAPTER_ADDRESS=0x...
```

Repeat for Arbitrum Sepolia if desired:

```bash
make deploy-testnet CHAIN=arbitrum_sepolia
```

## 6. Run in Dry-Run Mode

```bash
make run-bot DRY_RUN=true
```

The bot scans for arbitrage opportunities but simulates (does not send) transactions.

## 7. Verify

```bash
# Health check
make status

# Smoke test
make smoke-test
```

Expected output:
- `make status` → `{"status": "ok"}` (200)
- `make smoke-test` → all checks PASS

## 8. Enable Live Testnet Execution

After verifying dry-run works:

1. Set `DRY_RUN=false` in `.env`
2. Restart: `docker compose restart arb-bot`
3. Monitor: `make logs`

---

## Troubleshooting

### 1. `docker compose up` fails with "Set POSTGRES_PASSWORD"

**Cause:** Required secrets not configured in `.env`.

**Fix:** Generate and set passwords:
```bash
echo "POSTGRES_PASSWORD=$(openssl rand -base64 32)" >> .env
echo "REDIS_PASSWORD=$(openssl rand -base64 32)" >> .env
```

### 2. `make migrate` fails with "connection refused"

**Cause:** PostgreSQL container not ready yet.

**Fix:** Wait for health check, then retry:
```bash
docker compose up -d postgres && sleep 10 && make migrate
```

### 3. Bot reports "No private key configured"

**Cause:** `KEYSTORE_FILE` not set or file doesn't exist.

**Fix:** Create the keystore:
```bash
python -m src.utils.key_manager create
# Then set KEYSTORE_FILE=keystore/deployer.json in .env
```

### 4. RPC connection timeout

**Cause:** RPC endpoint unreachable or rate-limited.

**Fix:**
- Verify the URL is correct for the chain (Amoy = 80002, Arb Sepolia = 421614)
- Switch to a different RPC provider
- Run: `python scripts/validate_config.py` to test connectivity

### 5. Tests fail with import errors

**Cause:** Missing dependencies.

**Fix:**
```bash
pip install -r requirements.txt -r requirements-dev.txt
```

---

## Makefile Reference

| Command | Description |
|---------|-------------|
| `make setup` | Full setup: deps + infra + migrations + validate |
| `make install-dev` | Install runtime + dev dependencies |
| `make test` | Run Python tests with coverage |
| `make test-contracts` | Run Foundry tests |
| `make lint` | Run flake8 + mypy |
| `make format` | Auto-format with black + isort |
| `make docker-build` | Build bot Docker image |
| `make docker-up` | Start all containers |
| `make docker-down` | Stop all containers |
| `make migrate` | Run database migrations |
| `make validate` | Run config validation |
| `make smoke-test` | Run testnet smoke test |
| `make status` | Check bot health endpoint |
| `make logs` | Tail Docker logs |
| `make run-bot` | Start arbitrage bot |

---

## Next Steps

- [Operations Runbook](OPERATIONS_RUNBOOK.md) — Production deployment & management
- [Production Checklist](PRODUCTION_CHECKLIST.md) — Pre-production gate
- [Security Checklist](SECURITY_CHECKLIST.md) — Security review items
