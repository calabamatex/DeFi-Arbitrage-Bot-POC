# Operations Runbook — Production Deployment & Management

> **Pre-requisite:** Complete the [Production Checklist](PRODUCTION_CHECKLIST.md) before any production deployment.
>
> **For dev/testnet setup, see [Quickstart](QUICKSTART.md).**

---

## Table of Contents

1. [Pre-Production Checklist](#pre-production-checklist)
2. [Production Environment Setup](#production-environment-setup)
3. [Deployment Procedure](#deployment-procedure)
4. [Monitoring Setup](#monitoring-setup)
5. [Daily Operations](#daily-operations)
6. [Incident Response](#incident-response)
7. [Emergency Procedures](#emergency-procedures)
8. [Maintenance](#maintenance)

---

## Pre-Production Checklist

Before deploying to production, verify every item in [docs/PRODUCTION_CHECKLIST.md](PRODUCTION_CHECKLIST.md):

```bash
# Validate config (fail-fast on default credentials)
python -m src.config doctor

# Full validation
python scripts/validate_config.py

# Test suite
make test
make test-contracts
```

All checks must pass with no CRITICAL findings before proceeding.

---

## Production Environment Setup

### Secret Injection

**Production secrets MUST NOT live in `.env` files.** Use one of:

| Method | Usage |
|--------|-------|
| Docker secrets | `docker secret create` + service `secrets:` stanza |
| Vault (HashiCorp) | Dynamic secrets via API |
| AWS Secrets Manager | `--env-file` from Secrets Manager |
| CI/CD env vars | GitHub Actions secrets → container environment |

Required production secrets:

```
POSTGRES_PASSWORD      — Database password (strong, unique)
REDIS_PASSWORD         — Redis AUTH password (strong, unique)
HEALTH_AUTH_TOKEN      — Bearer token for /api/status and /metrics
ADMIN_RESET_CODE       — HMAC code for emergency shutdown reset
GRAFANA_ADMIN_PASSWORD — Grafana admin password (if monitoring profile)
```

**Key management:** Use encrypted keystores exclusively. Never set `PRIVATE_KEY` in environment.

```bash
# Create encrypted keystore
python -m src.utils.key_manager create

# Set in production environment
KEYSTORE_FILE=/secure/path/deployer.json
```

### Production docker-compose overrides

```bash
# Start core services (bot + infra)
docker compose up -d postgres redis arb-bot

# Start with monitoring
docker compose --profile monitoring up -d

# Start with liquidation bot
docker compose --profile liquidation up -d
```

The `docker-compose.yml` uses `${VAR:?error}` syntax — services refuse to start without required secrets.

---

## Deployment Procedure

### Via GitHub Actions (Recommended)

1. Push to `main` branch or trigger `.github/workflows/deploy-production.yml` manually
2. CI runs: lint, test, security scan, Foundry tests
3. Requires manual approval via GitHub Environment `production`
4. Builds and pushes Docker image with commit SHA tag
5. Deploys to production server
6. Runs 30-minute canary validation (health check loop)
7. Sends Telegram notification on success/failure

### Manual Deployment

```bash
# 1. Build image
make docker-build

# 2. Run config doctor
python -m src.config doctor

# 3. Run migrations
make migrate

# 4. Start services
docker compose up -d

# 5. Verify health
curl -H "Authorization: Bearer <HEALTH_AUTH_TOKEN>" http://localhost:8080/api/status

# 6. Monitor first 30 minutes
make logs
```

### Rollback

```bash
# Roll back to previous image tag
docker compose down arb-bot
docker compose up -d arb-bot  # uses previous image
# Or specify exact tag:
# IMAGE_TAG=<previous-sha> docker compose up -d arb-bot
```

---

## Monitoring Setup

### Prometheus + Grafana

```bash
# Start monitoring stack
docker compose --profile monitoring up -d

# Prometheus: http://localhost:9090 (bound to 127.0.0.1)
# Grafana:    http://localhost:3001 (bound to 127.0.0.1)
```

Prometheus scrapes:
- `arb-bot:8080/metrics` every 15s
- `liquidation-bot:8080/metrics` every 15s (if running)

Alert rules configured in `config/alert_rules.yml`:
- **BotDown** — bot unreachable for 2 minutes
- **CircuitBreakerActive** — circuit breaker engaged
- **NegativeDailyPnL** — daily P/L below threshold
- **HighErrorRate** — >50% failure rate over 1 hour
- **HighConsecutiveLosses** — 3+ consecutive losses
- **HighMemoryUsage** — >500MB for 10 minutes

### Telegram Alerts

Set in production environment:
```
TELEGRAM_BOT_TOKEN=<BOT_TOKEN>
TELEGRAM_CHAT_ID=<CHAT_ID>
TELEGRAM_ENABLED=true
```

Bot sends alerts for: circuit breaker events, emergency shutdowns, critical errors, daily P/L reports.

### Health Endpoints

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `GET /healthz` | No | Liveness probe (always 200) |
| `GET /readyz` | No | Readiness probe (checks bot + RPC) |
| `GET /health` | No | Legacy health check (200/503) |
| `GET /metrics` | Bearer | Prometheus metrics |
| `GET /api/status` | Bearer | Full JSON status snapshot |

```bash
# Liveness (no auth)
curl http://localhost:8080/healthz

# Readiness (no auth)
curl http://localhost:8080/readyz

# Full status (auth required)
curl -H "Authorization: Bearer <HEALTH_AUTH_TOKEN>" http://localhost:8080/api/status
```

---

## Daily Operations

### Morning Check (15 min)

```bash
# 1. Health check
curl http://localhost:8080/readyz

# 2. Full status
curl -H "Authorization: Bearer $HEALTH_AUTH_TOKEN" http://localhost:8080/api/status | python -m json.tool

# 3. Check logs for errors
docker compose logs --since 24h arb-bot | grep -i "error\|critical" | tail -20

# 4. Review Telegram alerts from overnight
```

### Key Metrics to Monitor

- **Net P/L** — positive trend expected
- **Success rate** — should be >60%
- **Circuit breaker** — should be inactive
- **Memory usage** — should be <500MB
- **Scan count** — should increase steadily

---

## Incident Response

### Circuit Breaker Activated

**Symptom:** Bot stops trading, `circuit_breaker_active: true` in `/api/status`.

**Response:**
1. Check via `/api/status` — note `consecutive_losses` count
2. Review recent failed trades in logs
3. Wait for automatic cooldown (default: 60 minutes)
4. If false positive: use ADMIN_RESET_CODE to reset manually

```bash
# Check status
curl -H "Authorization: Bearer $HEALTH_AUTH_TOKEN" http://localhost:8080/api/status

# Circuit breaker resets automatically after cooldown
# DO NOT reset unless you understand why it triggered
```

### Emergency Shutdown Triggered

**Symptom:** Bot fully stopped, requires admin code to restart.

**Response:**
1. Investigate root cause (daily loss limit, manual trigger, critical error)
2. Fix underlying issue
3. Reset with ADMIN_RESET_CODE:

```bash
# The bot's emergency shutdown requires HMAC-verified ADMIN_RESET_CODE
# This is set via environment variable and verified cryptographically
# Recovery process depends on your deployment method
```

### Transaction Stuck (Pending)

**Symptom:** Transaction submitted but not mined after expected time.

**Response:**
1. Check transaction status on block explorer
2. Use replacement policy: same nonce, higher gas price

```bash
# The TransactionManager handles stuck txs automatically via:
# - Replacement with 10% gas bump after timeout
# - Nonce tracking and recovery
# If manual intervention needed, use cast:
cast send --nonce <STUCK_NONCE> --gas-price <HIGHER_GAS> ...
```

### Database Connection Lost

**Symptom:** Bot continues scanning but cannot log trades/metrics.

**Response:**
1. Bot continues operating (DB failure is non-fatal)
2. Check PostgreSQL container health:
   ```bash
   docker compose ps postgres
   docker compose logs --tail 50 postgres
   ```
3. Restart PostgreSQL if needed:
   ```bash
   docker compose restart postgres
   ```
4. Restart bot to re-establish connection pool:
   ```bash
   docker compose restart arb-bot
   ```

### RPC Provider Failure

**Symptom:** Connection errors, timeouts in logs.

**Response:**
1. Test RPC manually:
   ```bash
   cast block-number --rpc-url $POLYGON_RPC_URL
   ```
2. Switch to backup RPC if available
3. Update `.env` with new RPC URL and restart

---

## Emergency Procedures

### Full Emergency Stop

```bash
# Stop all bot services immediately
docker compose stop arb-bot liquidation-bot

# Pause smart contracts (if owner)
cast send <CONTRACT_ADDRESS> "pause()" --rpc-url $POLYGON_RPC_URL --keystore <KEYSTORE>
```

### Recover from Emergency Shutdown

1. Identify and fix root cause
2. Run full validation:
   ```bash
   python -m src.config doctor
   python scripts/validate_config.py
   make test
   ```
3. Start in dry-run mode first:
   ```bash
   DRY_RUN=true docker compose up -d arb-bot
   ```
4. Monitor for 1 hour
5. If stable, switch to live: set `DRY_RUN=false` and restart

### Fund Wallet Emergency

```bash
# Check current balance
cast balance <BOT_WALLET> --rpc-url $POLYGON_RPC_URL

# Send gas tokens from funded wallet
cast send <BOT_WALLET> --value 1ether --rpc-url $POLYGON_RPC_URL --keystore <FUNDED_KEYSTORE>
```

---

## Maintenance

### Key Rotation

Rotate encrypted keystores periodically:

```bash
# 1. Create new keystore
python -m src.utils.key_manager create --output keystore/deployer_new.json

# 2. Update KEYSTORE_FILE in production secrets
# 3. Transfer ownership of contracts if needed
# 4. Restart bot
# 5. Verify operation
# 6. Delete old keystore securely
```

### Dependency Updates

```bash
# 1. Check for updates
pip list --outdated
pip-audit -r requirements.txt

# 2. Update on testnet first
pip install --upgrade <package>==<version>

# 3. Run full test suite
make test && make test-contracts

# 4. Deploy to testnet, monitor 24h
# 5. Deploy to production
```

### Database Backups

```bash
# Manual backup
docker compose exec postgres pg_dump -U postgres arbitrage_bot > backup_$(date +%Y%m%d).sql

# Restore from backup
docker compose exec -T postgres psql -U postgres arbitrage_bot < backup_YYYYMMDD.sql
```

### Database Migrations

```bash
# Apply pending migrations
make migrate

# Check migration status
alembic history
alembic current

# Rollback last migration (if needed)
alembic downgrade -1
```

### Log Management

Logs are managed via Docker's logging driver. For JSON structured logs:

```bash
# View recent logs
docker compose logs --tail 200 arb-bot

# Follow logs
make logs

# Export logs for analysis
docker compose logs arb-bot > arb_bot_$(date +%Y%m%d).log
```

---

**Document Version:** 2.0
**Last Updated:** February 2026
**Next Review:** Monthly
