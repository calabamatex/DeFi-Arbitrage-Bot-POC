# Infrastructure & Deployment Readiness Report

## Flash Loan Arbitrage Bot -- Production Infrastructure Assessment

**Report Date:** 2026-02-12
**Agent Role:** Deployment / Infrastructure Specialist
**Scope:** Full analysis of deployment readiness across containerization, secrets, CI/CD, process supervision, logging, database management, network security, and multi-chain operations

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current State Assessment](#2-current-state-assessment)
3. [A -- Containerization](#3-a----containerization)
4. [B -- Secret Management](#4-b----secret-management)
5. [C -- CI/CD Pipeline](#5-c----cicd-pipeline)
6. [D -- Process Supervision](#6-d----process-supervision)
7. [E -- Logging & Monitoring](#7-e----logging--monitoring)
8. [F -- Database Management](#8-f----database-management)
9. [G -- Network & Security](#9-g----network--security)
10. [H -- Multi-Chain Operations](#10-h----multi-chain-operations)
11. [Recommended Architecture](#11-recommended-architecture)
12. [Implementation Priority & Migration Path](#12-implementation-priority--migration-path)

---

## 1. Executive Summary

This bot has well-designed application-level safety (risk manager, circuit breaker, emergency shutdown) but lacks nearly all production infrastructure. It currently runs as a bare Python process on the developer's machine, reading secrets from plaintext `.env` files, writing unbounded logs to a single file, with no container, no CI pipeline, no process supervision, no health endpoint, and no metrics aggregation. A single process crash or host reboot would halt all trading with no notification and no automatic recovery.

**Critical Risk:** If the bot crashes at 3 AM, nobody restarts it. Missed arbitrage windows during a volatile market event could represent significant lost opportunity -- or worse, an in-flight transaction could leave the system in an inconsistent state.

**Severity Assessment:**

| Area | Current Maturity | Risk Level | Effort to Fix |
|------|-----------------|------------|---------------|
| Containerization | None (no Dockerfile) | HIGH | Medium |
| Secret Management | Plaintext `.env` on disk | CRITICAL | Medium |
| CI/CD | None | HIGH | Medium |
| Process Supervision | None (manual `python run_bot.py`) | CRITICAL | Low |
| Logging & Monitoring | File-only, no rotation, no aggregation | HIGH | Medium |
| Database Management | No migrations, no backups | HIGH | Low-Medium |
| Network & Security | Minimal firewall awareness | MEDIUM | Low |
| Multi-Chain Ops | Separate `.env` files, `nohup` | HIGH | Medium |

---

## 2. Current State Assessment

### What Exists

**Application layer (well-built):**
- `run_bot.py` -- clean entry point with startup validation, heartbeat loop, graceful `KeyboardInterrupt` handling
- `src/config.py` -- `Config` class with `validate()`, chain-specific `ChainConfig` dataclasses, database/Redis/Telegram configs
- `src/db/database.py` -- SQLAlchemy engine with `QueuePool`, `pool_pre_ping=True`, context-managed sessions, health check function
- `src/db/models.py` -- 7 ORM models (Opportunity, Transaction, TradeResult, Chain, DEX, Token, ExecutionLog) with proper indexes
- `src/utils/risk_manager.py` -- BalanceValidator, PositionManager, LossTracker, CircuitBreaker, RiskManager coordinator
- `src/utils/emergency_shutdown.py` -- async shutdown triggers, admin-code-protected reset with `hmac.compare_digest`
- `src/utils/metrics_collector.py` -- `BotMetrics` dataclass, JSON file export, Prometheus text-format file export (both write to disk only)
- `docker-compose.yml` -- PostgreSQL (TimescaleDB) + Redis + PgAdmin + Redis Commander
- `Makefile` -- targets for install, test, lint, format, docker, migrate, compile
- `scripts/security_scan.sh` -- basic secret and dependency scanning
- `scripts/init-db.sql` -- TimescaleDB extension initialization

**Documentation (extensive):**
- `OPERATIONS_GUIDE.md` -- pre-flight checklist, environment config, monitoring, emergency procedures, troubleshooting
- `TESTNET_DEPLOYMENT.md` -- Polygon Amoy testnet guide
- `MULTI_CHAIN_DEPLOYMENT_GUIDE.md` -- detailed per-chain addresses, deployment steps, cost estimates
- `SECURITY_REPORT.md` -- audit report (notes private key in `.env` as "standard practice")
- Multiple other guides in `docs/`

### What Is Missing

| Component | Gap |
|-----------|-----|
| Dockerfile | Does not exist |
| Docker Compose bot service | `docker-compose.yml` has DB/Redis but NOT the bot |
| CI/CD pipeline | No `.github/workflows/`, no CI config of any kind |
| Process supervisor | No systemd unit, no supervisord, no Docker restart |
| Health check endpoint | No HTTP server, no `/healthz` |
| Structured logging | Logs are unstructured `%(asctime)s - %(name)s - %(levelname)s - %(message)s` |
| Log rotation | `OPERATIONS_GUIDE.md` documents logrotate config but it is not implemented |
| Prometheus metrics endpoint | `export_prometheus()` writes to a file; no HTTP scrape endpoint |
| Alembic migrations | `Makefile` references `alembic upgrade head` but no `alembic/` directory exists |
| Database backups | No backup script, no scheduled dumps |
| Secret encryption | `.env` files are plaintext, `.env.bak` and `.env.bak2` exist in the repo directory |
| Dependency pinning | `requirements.txt` has only 7 packages; many transitive deps are unpinned; no `requirements.lock` |
| Signal handling | Only `KeyboardInterrupt` (SIGINT); no explicit SIGTERM handler |
| Multi-instance coordination | Multi-chain guide suggests `nohup ... &` and PID files |

---

## 3. A -- Containerization

### Current State

- **No Dockerfile exists.**
- `docker-compose.yml` provides PostgreSQL (TimescaleDB image) and Redis, but not the bot itself.
- The bot runs from `.venv/` with `python run_bot.py --chain polygon`.
- `setup.sh` references Docker Desktop for macOS.

### Findings

1. The bot writes to `bot.log` in the current working directory (hardcoded relative path in `run_bot.py` line 36). This makes containerization harder since the log path needs to be configurable or stdout-only.
2. `metrics_latest.json` and `metrics_final.json` are written to the working directory. In a container, these would need to go to a mounted volume or be replaced with a metrics endpoint.
3. `emergency_shutdown.log` is appended to in the working directory (`emergency_shutdown.py` line 253).
4. The `load_dotenv()` call at module import time (`config.py` line 10, `run_bot.py` line 29) expects `.env` on disk.

### Recommendations

**Dockerfile (multi-stage build):**

```
# Stage 1: Builder
FROM python:3.11-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim AS runtime
WORKDIR /app

# Install only runtime system deps (libpq for psycopg2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY src/ src/
COPY run_bot.py .
COPY config/ config/

# Non-root user for security
RUN useradd -r -s /bin/false botuser && chown -R botuser:botuser /app
USER botuser

# Health check (requires adding a lightweight HTTP health endpoint)
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8080/healthz || exit 1

ENTRYPOINT ["python", "run_bot.py"]
CMD ["--chain", "polygon"]
```

Key design points:
- Multi-stage build keeps the image small (no build tools in runtime).
- `python:3.11-slim` rather than Alpine, since Alpine causes issues with compiled C extensions like `psycopg2`.
- Non-root user (`botuser`) prevents container escape privilege escalation.
- `HEALTHCHECK` requires adding a minimal HTTP health endpoint to the bot (see Process Supervision section).
- No `.env` file copied in -- secrets injected via environment variables at runtime.

**Docker Compose addition for the bot:**

```yaml
services:
  arb-bot:
    build: .
    container_name: arb_bot_polygon
    environment:
      - CHAIN=polygon
      - DATABASE_URL=postgresql://postgres:${DB_PASSWORD}@postgres:5432/arbitrage_bot
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379
      # All other env vars injected from host or Docker secrets
    env_file:
      - .env  # Only for development; production uses secrets manager
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '1.0'
    networks:
      - arbitrage_network
    logging:
      driver: json-file
      options:
        max-size: "50m"
        max-file: "5"
```

**Immediate action required before containerizing:**
- Refactor `run_bot.py` logging to use stdout-only when `LOG_TO_FILE` env var is not set (Docker captures stdout).
- Make `bot.log` path configurable via environment variable.
- Make `metrics_latest.json` path configurable or replace with HTTP endpoint.

---

## 4. B -- Secret Management

### Current State

- All secrets stored in plaintext `.env` files on disk.
- `.env.bak` and `.env.bak2` exist in the project directory (backup copies of secrets).
- `.env.arbitrum` previously contained secrets (now redacted, per the file comment: "REDACTED - Private keys and API keys were committed here. They have been rotated.").
- `.gitignore` correctly excludes `.env` and `.env.*`.
- `ADMIN_RESET_CODE` is used for emergency shutdown reset, verified with `hmac.compare_digest`.
- `PRIVATE_KEY` is the Ethereum private key controlling all funds.

### Critical Finding

**The `.env.arbitrum` file explicitly states that private keys and API keys WERE committed to this file and had to be rotated.** This confirms the risk of plaintext `.env` management. Any backup, copy, or version-controlled snapshot could leak the private key and compromise all funds across all chains (same key is used for all chains).

### Risk Hierarchy

The `PRIVATE_KEY` is the single most sensitive secret. Compromise means instant, irreversible loss of all on-chain funds. It is categorically different from an API key.

### Recommendations (in order of increasing security)

**Tier 1 -- Minimum Viable (do immediately):**
- Remove `.env.bak` and `.env.bak2` from disk.
- Ensure `.env` file permissions are `chmod 600` (the security scan checks for this but it is not enforced).
- Never store the private key in any file that could be copied, backed up, or synced to cloud storage.

**Tier 2 -- Docker Secrets (for Docker Compose deployments):**
- Use Docker secrets for `PRIVATE_KEY`, `DATABASE_URL`, and `ADMIN_RESET_CODE`.
- Secrets are mounted as files at `/run/secrets/<name>` inside the container, never in environment variables or process listings.
- Modify `src/config.py` to read from `/run/secrets/` when running in Docker:

```python
def get_secret(name: str, env_fallback: str = None) -> str:
    secret_path = f"/run/secrets/{name.lower()}"
    if os.path.exists(secret_path):
        with open(secret_path, 'r') as f:
            return f.read().strip()
    return os.getenv(env_fallback or name, "")
```

**Tier 3 -- Cloud Secrets Manager (for VPS/cloud deployments):**
- **AWS SSM Parameter Store** (cheapest, simplest for a single bot): Store `PRIVATE_KEY` as a SecureString parameter. Bot fetches at startup via `boto3`. Cost: free for standard parameters.
- **AWS Secrets Manager** (if you want automatic rotation): Supports scheduled rotation, but rotation for an Ethereum private key requires generating a new key and transferring contract ownership, so this is complex.
- **HashiCorp Vault** (if self-hosting on dedicated infrastructure): Full-featured, supports transit encryption, dynamic secrets, audit logging. Overkill for a single bot but excellent for a fleet.

**Tier 4 -- Hardware Security Module (for high-value deployments):**
- Use a cloud HSM (AWS CloudHSM, GCP Cloud KMS) to sign transactions without the private key ever being in memory.
- Requires modifying `FlashLoanOrchestrator` to use a remote signer instead of `web3.eth.account.sign_transaction()`.

**Key Rotation Procedure:**
The `OPERATIONS_GUIDE.md` documents key rotation at a high level. A production procedure must include:

1. Generate new wallet on an air-gapped machine or hardware wallet.
2. Transfer contract ownership: `cast send $CONTRACT "transferOwnership(address)" $NEW_OWNER`.
3. Transfer all funds from old wallet to new wallet.
4. Update secret store with new private key.
5. Restart bot (verify with dry run first).
6. Verify old key has zero balance and no ownership.
7. Invalidate old key in secret store.

---

## 5. C -- CI/CD Pipeline

### Current State

- No `.github/workflows/` directory.
- No CI configuration of any kind.
- `Makefile` has `test`, `lint`, `format` targets but they are not run automatically.
- `pyproject.toml` has comprehensive pytest configuration with markers (`unit`, `integration`, `e2e`, `slow`) and 80% coverage threshold.
- `requirements.txt` has only 7 direct dependencies; many are test/dev only (pytest, black, mypy).
- `foundry.toml` has a `[profile.ci]` section with `fuzz_runs = 10000`, suggesting CI was planned.

### Recommended GitHub Actions Pipeline

**Pipeline stages:**

```
[push/PR] -> lint -> unit-test -> security-scan -> build-image -> integration-test -> deploy
```

**Stage details:**

1. **Lint** (`~30s`): `black --check`, `isort --check`, `mypy src/`, `flake8 src/`
   - Blocks merge on failure.

2. **Unit Tests** (`~60s`): `pytest tests/unit -m unit --override-ini="addopts="`
   - Blocks merge on failure.
   - Must pass at 80% coverage (already configured in `pyproject.toml`).

3. **Security Scan** (`~120s`):
   - `pip-audit` for Python dependency vulnerabilities.
   - `trivy` for container image scanning (after build).
   - `gitleaks` for secret detection in code.
   - `scripts/security_scan.sh` (the existing script, adapted for CI).
   - Blocks merge on HIGH/CRITICAL findings.

4. **Smart Contract Tests** (`~180s`): `forge test -vvv` with `[profile.ci]` fuzz settings.
   - Blocks merge on failure.
   - Run in parallel with Python tests.

5. **Build Docker Image** (`~120s`): Multi-stage build, tag with git SHA.
   - Push to container registry (Docker Hub, GitHub Container Registry, or AWS ECR).

6. **Integration Tests** (`~300s`):
   - Spin up PostgreSQL and Redis via `docker-compose`.
   - Run `pytest tests/integration -m integration`.
   - Optionally run Anvil fork tests: `anvil --fork-url $POLYGON_RPC_URL` in a sidecar, then run bot in dry-run mode for N seconds.
   - These should WARN but not block deployment (flaky due to RPC dependency).

7. **Deploy** (manual trigger or auto on `main`):
   - Pull new image on production host.
   - Rolling restart (stop old container, start new).
   - Verify health check passes within 60s.
   - Rollback if health check fails.

**Anvil Fork Tests in CI:**
- Use a GitHub Actions service container running `ghcr.io/foundry-rs/foundry:latest` with `anvil --fork-url`.
- Store `POLYGON_RPC_URL` as a GitHub Actions secret.
- Run tests against the forked chain.
- Set a timeout (5 minutes) to prevent CI from hanging.

**Deployment Strategy:**
For a single-instance bot, **blue-green deployment** is the safest:
- Start new container alongside old container (new container in dry-run mode).
- Verify new container passes health check and detects opportunities.
- Stop old container.
- Switch new container out of dry-run.
- Advantage: zero downtime, instant rollback by restarting old container.

**Dependency Pinning:**
The current `requirements.txt` is dangerously incomplete. It lists 7 packages but the bot imports `sqlalchemy`, `psutil`, `psycopg2`, and others that are not listed. To fix:

```bash
pip freeze > requirements.lock
```

Use `requirements.txt` for direct deps with `>=` constraints, and `requirements.lock` for exact reproducible builds in CI/Docker. Better yet, adopt Poetry (already in `pyproject.toml`) and use `poetry.lock`.

---

## 6. D -- Process Supervision

### Current State

- Bot runs as `python run_bot.py --chain polygon` in a terminal.
- Multi-chain guide suggests `nohup python run_bot.py ... > bot.log 2>&1 &` with PID files.
- `run_bot.py` handles `KeyboardInterrupt` (SIGINT) but NOT `SIGTERM`.
- The `running` flag on `ArbitrageBot` is set to `False` on shutdown, but daemon threads in non-direct mode may not exit cleanly.
- No watchdog, no auto-restart, no crash notification.

### Critical Gaps

1. **No SIGTERM handling.** Docker sends SIGTERM on `docker stop`, systemd sends SIGTERM on `systemctl stop`. Without a handler, the bot gets forcefully killed after the grace period, potentially mid-transaction.

2. **No liveness detection.** The bot could deadlock (e.g., RPC call hangs indefinitely, `web3.eth.get_block()` with no timeout) and the heartbeat would stop updating, but nothing would notice or restart it.

3. **No crash notification.** If the bot exits with an exception, the only evidence is a line in `bot.log` (if log flushing completed before the crash).

### Recommendations

**Tier 1 -- Docker restart policy (simplest, do first):**
- `restart: unless-stopped` in Docker Compose (already present for postgres/redis).
- Add `stop_grace_period: 30s` to give the bot time to finish in-flight transactions.
- Docker handles restart on crash with default backoff (1s, 2s, 4s, ..., capped at 5 minutes).

**Tier 2 -- SIGTERM handler in `run_bot.py`:**

```python
import signal

def main():
    # ... existing setup ...

    def handle_signal(signum, frame):
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        bot.stop()
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    try:
        bot.run()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        bot.stop()
        sys.exit(1)
```

**Tier 3 -- Health check endpoint:**
Add a minimal HTTP server thread that exposes `/healthz`:

```python
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading, json

class HealthHandler(BaseHTTPRequestHandler):
    bot_ref = None

    def do_GET(self):
        if self.path == '/healthz':
            if self.bot_ref and self.bot_ref.running:
                # Check last heartbeat was within 2x interval
                stale = (time.time() - self.bot_ref.last_heartbeat) > (self.bot_ref.heartbeat_interval * 2)
                if stale:
                    self.send_response(503)
                    self.end_headers()
                    self.wfile.write(b'{"status":"stale"}')
                else:
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(json.dumps(self.bot_ref.stats).encode())
            else:
                self.send_response(503)
                self.end_headers()
                self.wfile.write(b'{"status":"stopped"}')
        elif self.path == '/metrics':
            # Prometheus metrics scrape endpoint
            ...
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress access logs
```

This enables Docker `HEALTHCHECK`, load balancer health probes, and external monitoring (UptimeRobot, Datadog synthetic).

**Tier 4 -- systemd (for bare-metal VPS):**
If running without Docker:

```ini
[Unit]
Description=Flash Loan Arbitrage Bot (Polygon)
After=postgresql.service network-online.target
Wants=network-online.target

[Service]
Type=simple
User=botuser
WorkingDirectory=/opt/arb_bot
EnvironmentFile=/opt/arb_bot/.env
ExecStart=/opt/arb_bot/.venv/bin/python run_bot.py --chain polygon
ExecStop=/bin/kill -SIGTERM $MAINPID
Restart=on-failure
RestartSec=30
StartLimitBurst=5
StartLimitIntervalSec=300
StandardOutput=journal
StandardError=journal
SyslogIdentifier=arb-bot-polygon

[Install]
WantedBy=multi-user.target
```

systemd provides: auto-restart on crash, rate limiting (5 restarts per 5 minutes), journal logging, status monitoring (`systemctl status`), boot start.

---

## 7. E -- Logging & Monitoring

### Current State

- Logging to `bot.log` (FileHandler) and stdout (StreamHandler).
- Format: `%(asctime)s - %(name)s - %(levelname)s - %(message)s` (unstructured text).
- No log rotation configured (mentioned in `OPERATIONS_GUIDE.md` as a logrotate snippet, but not implemented).
- `bot.log` grows unbounded. On a 24/7 bot scanning every 5 seconds, this will reach hundreds of MB per day.
- Metrics exported to `metrics_latest.json` file every 60s. No HTTP endpoint for scraping.
- `export_prometheus()` method exists but writes to a file, not an HTTP endpoint.
- `psutil` used for memory/CPU but is not in `requirements.txt`.

### Gaps

1. **Unstructured logs** cannot be parsed by log aggregation tools (ELK, CloudWatch Logs, Datadog).
2. **No log rotation** means disk will fill up, eventually crashing the bot.
3. **No centralized logging** means you cannot search or alert on logs from a remote host.
4. **No Prometheus scrape endpoint** means Grafana/Prometheus cannot collect metrics.
5. **No alerting** on critical events (circuit breaker trip, RPC failure, process crash). Telegram integration exists in the code but is optional and not wired into the main bot runner.

### Recommendations

**Structured JSON Logging:**
Replace the `basicConfig` in `run_bot.py` with:

```python
import json
import logging

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "chain": getattr(record, 'chain', None),
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)
```

This enables:
- CloudWatch Logs Insights queries (`filter level = "ERROR" | stats count() by logger`)
- Datadog log parsing
- ELK stack ingestion
- `jq` filtering on the command line

**Log Shipping Options:**

| Option | Cost | Complexity | Best For |
|--------|------|------------|----------|
| Docker json-file driver + Promtail -> Loki | Free | Medium | Self-hosted Grafana |
| CloudWatch Logs agent | ~$0.50/GB | Low | AWS deployments |
| Datadog agent | $15/host/mo | Low | Full observability platform |
| Vector + S3 | ~$0.02/GB | Medium | Cost-sensitive, archival |

**Recommended: Grafana Loki** (open-source, pairs with Grafana for dashboards, minimal cost on a single host).

**Prometheus Metrics Endpoint:**
Add to the health check HTTP server:

```python
elif self.path == '/metrics':
    self.send_response(200)
    self.end_headers()
    metrics_text = self.bot_ref.metrics.generate_prometheus_text()
    self.wfile.write(metrics_text.encode())
```

Then configure Prometheus to scrape `http://arb-bot:8080/metrics` every 15s.

**Grafana Dashboard Design:**

The dashboard should have these panels:

| Panel | Metric | Alert Threshold |
|-------|--------|-----------------|
| Bot Uptime | `bot_uptime_seconds` | < 60s (just restarted) |
| Scan Rate | `rate(bot_scans_total[5m])` | 0 for > 5 minutes |
| Opportunities Found | `bot_opportunities_total` | 0 for > 24 hours |
| Trade Success Rate | `bot_success_rate` | < 50% over 1 hour |
| Net PnL | `bot_net_profit_usd` | Decreasing trend |
| Circuit Breaker | `bot_circuit_breaker_active` | == 1 |
| RPC Latency | `bot_rpc_latency_ms` | > 5000ms |
| Memory Usage | `bot_memory_usage_mb` | > 400MB |
| Error Rate | `rate(bot_errors_total[5m])` | > 1/min |
| Gas Price | `bot_gas_price_gwei` | Above chain threshold |

**Alerting Rules (critical):**

1. **Bot down:** No heartbeat metric for > 3 minutes. Page immediately.
2. **Circuit breaker tripped:** `bot_circuit_breaker_active == 1`. Page immediately.
3. **RPC failures:** Error rate > 5/min with "RPC" in message. Warn (may be transient).
4. **No opportunities in 24h:** Zero increment on `bot_opportunities_total` for 24h. Warn (may be normal in low-volatility).
5. **Daily loss limit approaching:** `daily_pnl < -(DAILY_LOSS_LIMIT * 0.8)`. Warn.
6. **Process crash:** Container restart count > 3 in 1 hour. Page.

**Missing dependency:** Add `psutil` to `requirements.txt` (it is imported in `metrics_collector.py` but not listed).

---

## 8. F -- Database Management

### Current State

- `docker-compose.yml` runs `timescale/timescaledb:latest-pg16` with data on a named volume `postgres_data`.
- `src/db/database.py` uses SQLAlchemy with `QueuePool` (pool_size=10, max_overflow=20, pool_pre_ping=True).
- `src/db/models.py` defines 7 tables with proper indexes.
- `scripts/init-db.sql` creates TimescaleDB extension and a health_check table.
- `Makefile` has `migrate` target running `alembic upgrade head`.
- `setup.sh` attempts to initialize Alembic.
- **BUT: No `alembic/` directory exists in the repository.** Alembic has never been initialized.
- Schema is created via `Base.metadata.create_all(bind=engine)` in `init_db()` -- direct DDL, no versioning.
- No backup strategy exists.
- Database credentials are `postgres:postgres` (hardcoded in `docker-compose.yml` and as default in `DatabaseConfig`).

### Gaps

1. **No schema versioning.** If you change a model, you must manually alter the table or drop and recreate. This will lose production data.
2. **No migration history.** Cannot roll back schema changes.
3. **No backups.** A disk failure or accidental `DROP TABLE` loses all trade history.
4. **Default credentials.** `postgres:postgres` is the worst possible database password.
5. **No connection string encryption.** `DATABASE_URL` in `.env` contains password in plaintext.
6. **TimescaleDB `latest` tag.** Unpinned image version means a `docker pull` could introduce breaking changes.

### Recommendations

**1. Initialize Alembic (immediate):**

```bash
cd /path/to/project
source .venv/bin/activate
pip install alembic
alembic init alembic
```

Configure `alembic/env.py` to import `Base` from `src.db.models` and use `config.db.url`.
Generate initial migration:

```bash
alembic revision --autogenerate -m "initial_schema"
alembic upgrade head
```

**2. Pin TimescaleDB image version:**

```yaml
image: timescale/timescaledb:2.14.2-pg16  # Pin to specific version
```

**3. Automated backups:**

```bash
# Daily backup script (cron or systemd timer)
#!/bin/bash
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR=/backups/postgres
mkdir -p $BACKUP_DIR

docker exec arbitrage_postgres pg_dump -U postgres -Fc arbitrage_bot \
    > "$BACKUP_DIR/arb_bot_$TIMESTAMP.dump"

# Retain 30 days
find $BACKUP_DIR -name "*.dump" -mtime +30 -delete

# Optional: upload to S3
# aws s3 cp "$BACKUP_DIR/arb_bot_$TIMESTAMP.dump" s3://your-bucket/backups/
```

**4. Connection pooling tuning:**
Current settings (pool_size=10, max_overflow=20) are reasonable for a single bot instance. For multi-chain with shared DB:
- Each bot instance gets its own pool.
- 4 chains x 10 connections = 40 connections (well within PostgreSQL default of 100).
- Consider PgBouncer if scaling beyond 10 chains.

**5. Change default credentials:**
- Generate a strong password.
- Store in secret manager (not `.env`).
- Update `docker-compose.yml` to use `${DB_PASSWORD}` variable.

---

## 9. G -- Network & Security

### Current State

- Bot is a pure client (outbound connections only): RPC endpoints (HTTPS), PostgreSQL (TCP 5432), Redis (TCP 6379).
- No inbound ports needed for bot operation (no API server, no webhook receiver).
- Health check endpoint (proposed) would need inbound port 8080 but only from monitoring infrastructure.
- RPC endpoints use Alchemy (HTTPS with API key in URL path).
- Docker Compose exposes PostgreSQL on `0.0.0.0:5432` and Redis on `0.0.0.0:6379` (host-accessible).

### Findings

1. **PostgreSQL exposed on all interfaces.** If the host has a public IP, the database is accessible from the internet with `postgres:postgres` credentials. This is a critical vulnerability on a VPS.
2. **Redis exposed on all interfaces** with a weak password (`redis_password`).
3. **PgAdmin exposed on port 5050** (in the `tools` profile, so not started by default).
4. **RPC API keys in URL path.** If logs capture the full URL (e.g., error messages from `requests` or `web3`), the API key is leaked to log files.

### Recommendations

**Firewall Rules (iptables/ufw on Linux VPS):**

```bash
# Allow SSH
ufw allow 22/tcp

# Allow health check from monitoring (optional, restrict to monitoring IP)
ufw allow from 10.0.0.0/8 to any port 8080

# Block everything else inbound
ufw default deny incoming
ufw default allow outgoing
ufw enable
```

**Docker Compose network binding:**
Change port bindings to `127.0.0.1` only:

```yaml
ports:
  - "127.0.0.1:5432:5432"  # PostgreSQL only on localhost
  - "127.0.0.1:6379:6379"  # Redis only on localhost
```

**RPC endpoint security:**
- Use environment variables for RPC URLs (already done).
- Ensure RPC API keys are not logged: configure web3 provider to suppress URL in error messages, or use a proxy that injects the API key.
- Set rate limits on Alchemy dashboard.
- Consider a private RPC (e.g., Flashbots Protect) for transaction submission to prevent frontrunning.

**SSH hardening (for VPS):**
- Disable password authentication, use SSH keys only.
- Use a non-standard port.
- Consider Tailscale or WireGuard VPN for access.
- Enable `fail2ban`.

---

## 10. H -- Multi-Chain Operations

### Current State

- `run_bot.py` supports `--chain polygon|arbitrum|optimism|base`.
- Chain-specific config via separate `.env` files (`.env.arbitrum`, `.env.base`, etc.).
- `MULTI_CHAIN_DEPLOYMENT_GUIDE.md` proposes running separate processes per chain with `nohup ... &` and PID files.
- `src/config.py` defines all chains in `Config.CHAINS` dict.
- The multi-chain coordinator example in the deployment guide uses Python threads (sharing the same `load_dotenv()` call, which is incorrect -- `load_dotenv` sets OS-level env vars, so later calls overwrite earlier ones).
- Single wallet (`PRIVATE_KEY`) used across all chains.
- Shared PostgreSQL database (tables have `chain_id` column).

### Findings

1. **The threading-based multi-chain coordinator is broken.** `load_dotenv('.env.arbitrum')` in one thread will overwrite env vars read by another thread running `.env.polygon`. Environment variables are process-global.
2. **No per-chain isolation.** A bug in the Arbitrum instance could corrupt shared database state for Polygon.
3. **Single private key = single point of failure.** If compromised, all chains are compromised.
4. **No independent scaling.** Cannot run 2 instances on Arbitrum (fast blocks) and 1 on Polygon (slower).

### Recommendations

**Architecture: One container per chain, shared database.**

```
                        +------------------+
                        |   PostgreSQL     |
                        |  (shared, with   |
                        |  chain_id column)|
                        +--------+---------+
                                 |
              +------------------+------------------+
              |                  |                  |
    +---------+-------+ +-------+---------+ +------+--------+
    | arb-bot-polygon | | arb-bot-arbitrum| | arb-bot-base  |
    | CHAIN=polygon   | | CHAIN=arbitrum  | | CHAIN=base    |
    | Port 8081       | | Port 8082       | | Port 8083     |
    +-----------------+ +-----------------+ +---------------+
```

**Docker Compose for multi-chain:**

```yaml
services:
  arb-bot-polygon:
    build: .
    environment:
      CHAIN: polygon
      POLYGON_RPC_URL: ${POLYGON_RPC_URL}
      DATABASE_URL: postgresql://botuser:${DB_PASSWORD}@postgres:5432/arbitrage_bot
      HEALTH_PORT: "8081"
    # ... (secrets, depends_on, restart, etc.)

  arb-bot-arbitrum:
    build: .
    environment:
      CHAIN: arbitrum
      ARBITRUM_RPC_URL: ${ARBITRUM_RPC_URL}
      DATABASE_URL: postgresql://botuser:${DB_PASSWORD}@postgres:5432/arbitrage_bot
      HEALTH_PORT: "8082"
      CHECK_INTERVAL: "2"  # Faster for Arbitrum's 0.25s blocks
    # ...

  arb-bot-base:
    build: .
    environment:
      CHAIN: base
      BASE_RPC_URL: ${BASE_RPC_URL}
      DATABASE_URL: postgresql://botuser:${DB_PASSWORD}@postgres:5432/arbitrage_bot
      HEALTH_PORT: "8083"
    # ...
```

Advantages:
- Each chain is an independent container with its own restart policy.
- Environment variables are container-scoped (no `load_dotenv` conflicts).
- Independent scaling (run 2 Arbitrum instances with different pair sets).
- One chain crashing does not affect others.
- Shared database is fine since all tables have `chain_id` for filtering.

**Per-chain configuration:**
Modify `run_bot.py` to accept the chain from the `CHAIN` environment variable (not just `--chain` CLI arg), so the Docker Compose `environment` block drives it.

**Wallet isolation (future):**
Consider separate wallets per chain to limit blast radius of a key compromise. This adds operational complexity (funding multiple wallets) but limits damage.

---

## 11. Recommended Architecture

### Target Production Architecture (Single Host / VPS)

```
+-------------------------------------------------------------------+
|  VPS (Ubuntu 22.04, 4 CPU, 8GB RAM)                              |
|                                                                    |
|  +--Docker Compose-------------------------------------------+    |
|  |                                                            |    |
|  |  +-postgres---------+  +-redis---------+                   |    |
|  |  | TimescaleDB 2.14 |  | Redis 7       |                   |    |
|  |  | Port 5432 (local)|  | Port 6379     |                   |    |
|  |  | Volume: pgdata   |  | (local only)  |                   |    |
|  |  +------------------+  +---------------+                   |    |
|  |                                                            |    |
|  |  +-arb-bot-polygon--+  +-arb-bot-arbitrum+  +-arb-bot-base+|   |
|  |  | Python 3.11      |  | Python 3.11     |  | Python 3.11 ||   |
|  |  | :8081/healthz    |  | :8082/healthz   |  | :8083/healthz||  |
|  |  | restart: always  |  | restart: always  |  | restart:    ||   |
|  |  +------------------+  +-----------------+  +-------------+|   |
|  |                                                            |    |
|  |  +-prometheus--------+  +-grafana--------+                 |    |
|  |  | Scrapes /metrics  |  | Dashboards     |                 |    |
|  |  | Port 9090 (local) |  | Port 3000      |                 |    |
|  |  +-------------------+  +----------------+                 |    |
|  |                                                            |    |
|  |  +-loki--------------+  +-promtail------+                  |    |
|  |  | Log aggregation   |  | Reads Docker  |                  |    |
|  |  | Port 3100 (local) |  | json-file logs|                  |    |
|  |  +-------------------+  +---------------+                  |    |
|  +------------------------------------------------------------+    |
|                                                                    |
|  Cron: pg_dump daily, upload to S3                                |
|  UFW: SSH only + Grafana (restricted IP)                          |
+-------------------------------------------------------------------+
```

### Resource Estimates

| Component | CPU | RAM | Disk |
|-----------|-----|-----|------|
| PostgreSQL | 0.5 cores | 1 GB | 10 GB (grows with trade history) |
| Redis | 0.1 cores | 256 MB | 100 MB |
| Bot (per chain) | 0.5 cores | 256 MB | Minimal (logs to Docker) |
| Prometheus | 0.2 cores | 512 MB | 5 GB (2 weeks retention) |
| Grafana | 0.2 cores | 256 MB | 1 GB |
| Loki + Promtail | 0.2 cores | 512 MB | 5 GB |
| **Total (3 chains)** | **~3 cores** | **~4 GB** | **~25 GB** |

A $20-40/month VPS (4 CPU, 8 GB RAM, 80 GB SSD) from Hetzner, DigitalOcean, or Vultr is sufficient.

---

## 12. Implementation Priority & Migration Path

### Phase 1: Survival (Week 1) -- Stop the bleeding

These items prevent the "bot crashed, nobody noticed" scenario.

| # | Task | Effort | Impact |
|---|------|--------|--------|
| 1.1 | Add SIGTERM handler to `run_bot.py` | 30 min | Prevents data corruption on shutdown |
| 1.2 | Remove `.env.bak` and `.env.bak2` from disk | 5 min | Eliminates secret copies |
| 1.3 | Restrict `.env` permissions to `chmod 600` | 5 min | Prevents accidental reads |
| 1.4 | Add `psutil` to `requirements.txt` | 5 min | Fixes missing dependency |
| 1.5 | Pin all dependencies with `pip freeze > requirements.lock` | 15 min | Reproducible builds |
| 1.6 | Create Dockerfile (multi-stage) | 2 hours | Container foundation |
| 1.7 | Add bot service to `docker-compose.yml` with `restart: unless-stopped` | 1 hour | Auto-restart on crash |
| 1.8 | Bind postgres/redis ports to `127.0.0.1` only | 15 min | Closes network exposure |

### Phase 2: Observability (Week 2) -- Know when something is wrong

| # | Task | Effort | Impact |
|---|------|--------|--------|
| 2.1 | Add HTTP health check endpoint (`/healthz`) | 3 hours | Enables container health check and external monitoring |
| 2.2 | Switch logging to stdout-only in container mode | 1 hour | Docker captures logs natively |
| 2.3 | Add JSON log formatter (structured logging) | 2 hours | Enables log search and alerting |
| 2.4 | Add Prometheus metrics HTTP endpoint (`/metrics`) | 3 hours | Enables Grafana dashboards |
| 2.5 | Add Prometheus + Grafana to docker-compose | 2 hours | Visualization and alerting |
| 2.6 | Configure Grafana alerts (bot down, circuit breaker, PnL) | 2 hours | Proactive notifications |
| 2.7 | Wire Telegram alerts into `run_bot.py` for fatal errors | 1 hour | Immediate crash notification |

### Phase 3: Safety (Week 3) -- Protect funds and data

| # | Task | Effort | Impact |
|---|------|--------|--------|
| 3.1 | Initialize Alembic, generate initial migration | 2 hours | Schema versioning |
| 3.2 | Create automated pg_dump backup script + cron | 1 hour | Prevent data loss |
| 3.3 | Move secrets to Docker secrets (compose secrets) | 2 hours | Secrets not in env vars |
| 3.4 | Change default database password | 15 min | Eliminate trivial credential |
| 3.5 | Pin TimescaleDB image version | 15 min | Prevent breaking upgrades |
| 3.6 | Add UFW firewall rules on VPS | 30 min | Network hardening |

### Phase 4: Automation (Week 4) -- CI/CD pipeline

| # | Task | Effort | Impact |
|---|------|--------|--------|
| 4.1 | Create `.github/workflows/ci.yml` (lint + test) | 3 hours | Automated quality gates |
| 4.2 | Add security scanning (pip-audit, gitleaks, trivy) to CI | 2 hours | Catch vulnerabilities early |
| 4.3 | Add Docker image build + push to CI | 2 hours | Automated container builds |
| 4.4 | Add Foundry contract tests to CI | 1 hour | Catch contract regressions |
| 4.5 | Create deployment script (pull image, restart container, verify health) | 3 hours | Reproducible deployments |
| 4.6 | Add Loki + Promtail for log aggregation | 2 hours | Centralized log search |

### Phase 5: Multi-Chain Production (Week 5-6)

| # | Task | Effort | Impact |
|---|------|--------|--------|
| 5.1 | Refactor `run_bot.py` to read chain from `CHAIN` env var | 1 hour | Docker Compose driven |
| 5.2 | Add per-chain bot services to Docker Compose | 2 hours | Independent containers |
| 5.3 | Per-chain Grafana dashboards | 2 hours | Per-chain visibility |
| 5.4 | Per-chain alerting rules | 1 hour | Chain-specific thresholds |
| 5.5 | Deploy to VPS with all chains | 4 hours | Production multi-chain |
| 5.6 | 48-hour monitoring period in dry-run | 48 hours | Validate infrastructure |

### Phase 6: Hardening (Month 2+)

| # | Task | Effort | Impact |
|---|------|--------|--------|
| 6.1 | Migrate to AWS SSM/Secrets Manager for private key | 4 hours | Enterprise-grade secret management |
| 6.2 | Add Anvil fork integration tests in CI | 4 hours | Realistic testing |
| 6.3 | Blue-green deployment strategy | 4 hours | Zero-downtime deploys |
| 6.4 | Per-chain wallet isolation | 4 hours | Limit blast radius |
| 6.5 | PgBouncer connection pooling (if > 5 chains) | 2 hours | Database scaling |
| 6.6 | Kubernetes migration (if scaling to 10+ chains) | 2 weeks | Container orchestration at scale |

---

## Appendix A: Files Reviewed

| File | Path | Key Observations |
|------|------|-----------------|
| Entry point | `run_bot.py` | Hardcoded `bot.log` path, no SIGTERM, `load_dotenv()` at import |
| Dependencies | `requirements.txt` | Only 7 packages, missing `sqlalchemy`, `psutil`, `psycopg2` |
| Project config | `pyproject.toml` | Good pytest config, Poetry build system declared but not used |
| Git ignore | `.gitignore` | Properly excludes `.env`, `.env.*`, logs, wallet files |
| Operations | `OPERATIONS_GUIDE.md` | Thorough manual, documents logrotate but does not implement it |
| Testnet guide | `TESTNET_DEPLOYMENT.md` | Polygon Amoy deployment instructions |
| Multi-chain guide | `MULTI_CHAIN_DEPLOYMENT_GUIDE.md` | Broken threading-based coordinator, good chain research |
| Deploy scripts | `deploy_testnet_complete.sh`, `deploy_testnet_simple.sh` | Foundry-based, well-structured |
| Config system | `src/config.py` | `load_dotenv()` at module scope, dataclass configs, chain definitions |
| Database | `src/db/database.py` | SQLAlchemy QueuePool, health check, no Alembic |
| DB models | `src/db/models.py` | 7 tables, proper indexes, `chain_id` on all relevant tables |
| Metrics | `src/utils/metrics_collector.py` | File-only export, Prometheus file export (not HTTP), `psutil` not in deps |
| Risk manager | `src/utils/risk_manager.py` | Well-designed: BalanceValidator, PositionManager, LossTracker, CircuitBreaker |
| Emergency shutdown | `src/utils/emergency_shutdown.py` | Async triggers, `hmac.compare_digest` admin code, file logging |
| Docker Compose | `docker-compose.yml` | PostgreSQL + Redis, no bot service, ports on 0.0.0.0 |
| Makefile | `Makefile` | References `alembic` but it is not initialized |
| Setup script | `setup.sh` | Docker check, Alembic init, `.env` setup |
| Security scan | `scripts/security_scan.sh` | 10-point check, good for local use |
| Security report | `SECURITY_REPORT.md` | Notes private key in `.env` as acceptable |
| Init SQL | `scripts/init-db.sql` | TimescaleDB extension, health_check table |
| Foundry config | `foundry.toml` | CI profile, Solc 0.8.20, optimizer enabled |
| Env example | `.env.example` | 43 lines, documents all variables |
| Env arbitrum | `.env.arbitrum` | **Previously contained leaked secrets (now redacted)** |
| Env backups | `.env.bak`, `.env.bak2` | **Should be deleted immediately** |

## Appendix B: Tool & Service Recommendations Summary

| Area | Recommended Tool | Alternative | Rationale |
|------|-----------------|-------------|-----------|
| Container runtime | Docker Compose | Kubernetes (at scale) | Simplest for 1-5 chains on single host |
| Container registry | GitHub Container Registry | Docker Hub, AWS ECR | Free for public, integrates with GitHub Actions |
| Secret management | Docker Secrets (near-term), AWS SSM (long-term) | HashiCorp Vault | Docker Secrets is zero-cost; SSM is $0 for standard params |
| CI/CD | GitHub Actions | GitLab CI, CircleCI | Repository is already on GitHub (`.git` dir exists) |
| Process supervision | Docker restart policy | systemd (bare-metal) | Built into Docker, zero config |
| Structured logging | Python `json` formatter | `structlog` library | Minimal dependency, full control |
| Log aggregation | Grafana Loki + Promtail | ELK, CloudWatch, Datadog | Free, lightweight, pairs with Grafana |
| Metrics | Prometheus + Grafana | Datadog, CloudWatch | Free, industry standard, rich alerting |
| Alerting | Grafana Alerting -> Telegram | PagerDuty, OpsGenie | Telegram already integrated in bot code |
| Database | TimescaleDB (already used) | Plain PostgreSQL | TimescaleDB adds time-series optimizations for trade data |
| DB migrations | Alembic | Django-style, raw SQL | Already referenced in Makefile, standard for SQLAlchemy |
| DB backups | `pg_dump` + cron + S3 | pgBackRest, WAL-E | Simplest, sufficient for single database |
| Security scanning | `pip-audit` + `trivy` + `gitleaks` | Snyk, Dependabot | Free, CI-native |
| VPS provider | Hetzner (EU) or DigitalOcean | AWS EC2, Vultr | Best price/performance for single-host deployment |

---

**End of Infrastructure Report.**

*Generated by Infrastructure Agent -- 2026-02-12*
