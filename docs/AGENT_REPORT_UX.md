# UX Audit Report: Crypto Arbitrage Bot

**Agent Role:** UX Lead
**Date:** 2026-02-11
**Scope:** Full codebase operator-experience audit

---

## Executive Summary

1. **CRITICAL -- Private keys are committed to version control.** `.env.arbitrum` (line 22) and `deploy_testnet_complete.sh` (line 11) contain real private keys in plaintext, checked into git.

2. **Configuration is scattered across 7+ locations** (`.env`, `.env.arbitrum`, `config/config.json`, `src/config.py`, `src/bot/config.py`, `foundry.toml`, `hardhat.config.js`) with overlapping and sometimes contradictory settings.

3. **Two completely separate bot entrypoints** (`run_bot.py` for Polygon, `run_bot_arbitrum.py` for Arbitrum) with different logging patterns, feature sets, and config loading.

4. **No live monitoring, dashboards, or health-check endpoints exist.** The `MetricsCollector` writes to JSON files but nothing reads them. No Prometheus/Grafana. No HTTP health endpoint.

5. **Documentation sprawl is severe** -- 55+ markdown files, many overlapping/contradictory. No canonical "start here" path.

---

## 1. Console Output & Logging

### Severity: High

**1.1 Two entrypoints, two logging paradigms**

`run_bot.py` uses Python's `logging` module with file + stream handlers.
`run_bot_arbitrum.py` uses raw `print()` statements throughout.

**Impact:** Arbitrum operator gets no log file, no severity levels, no log rotation.

**1.2 Duplicate logging configuration**

`logging.basicConfig()` called in 3 separate files (`run_bot.py:25`, `src/opportunity_detector.py:27`, `src/flash_loan_orchestrator.py:29`). Only first call takes effect -- behavior depends on import order.

**1.3 No structured logging (JSON)**

All log output is human-readable strings. Cannot be ingested by ELK/Loki/Datadog.

**1.4 Token amounts displayed inconsistently**

`run_bot.py:153` displays as "tokens". `run_bot_arbitrum.py:98` displays as USD.

**1.5 No periodic heartbeat / status summary**

During long periods with no opportunities, the operator sees nothing and cannot tell if the bot is alive.

### Recommendations

| # | Action | Priority |
|---|--------|----------|
| 1.A | Unify both entrypoints into a single `run_bot.py --chain polygon\|arbitrum` | High |
| 1.B | Centralize logging in a single `src/utils/logging.py` module | High |
| 1.C | Add JSON log format option via `LOG_FORMAT=json` | Medium |
| 1.D | Add periodic heartbeat log (every 60s) | High |
| 1.E | Standardize all profit displays with explicit currency | Medium |

**Before / After for heartbeat:**

Before (during dry spell):
```
2026-02-11 10:00:05 - INFO - Scanning 4 pairs...
2026-02-11 10:00:07 - INFO - No profitable opportunities found this iteration.
[... repeats for hours ...]
```

After:
```
2026-02-11 10:01:00 - HEARTBEAT - chain=polygon scans=720 uptime=1h00m opportunities=0 wallet=4.23MATIC gas=32gwei last_opp=never status=OK
```

---

## 2. Configuration UX

### Severity: Critical (secrets) / High (fragmentation)

**2.1 CRITICAL: Private keys committed to git**

- `.env.arbitrum:22`: Private key in plaintext
- `deploy_testnet_complete.sh:11`: Private key in plaintext
- `.gitignore` excludes `.env` but NOT `.env.arbitrum` or `.env.bak*`

**2.2 Configuration scattered across 7+ locations**

`MIN_PROFIT_USD` defaults to `10` in `.env.example`, `1.0` in `run_bot.py:238`, `5.0` in `.env.arbitrum`, `10.0` in `src/config.py:76`.

**2.3 No configuration validation at startup**

Bot checks for 4 required env vars but silently falls back to defaults for everything else.

**2.4 Hardcoded MATIC price**

`src/opportunity_detector.py:394`: `matic_price_usd = 0.80` -- directly affects profitability calculations, cannot be changed without editing source code.

### Recommendations

| # | Action | Priority |
|---|--------|----------|
| 2.A | IMMEDIATELY rotate all committed private keys. Add `.env.*` to `.gitignore`. Use BFG to scrub git history. | Critical |
| 2.B | Consolidate to single config system: `.env` for secrets, `config.yaml` for everything else | High |
| 2.C | Add startup config validation that fails fast | High |
| 2.D | Fetch token prices from oracle instead of hardcoding | Medium |

---

## 3. Deployment Experience

### Severity: High

**3.1 No single deployment entrypoint** -- 8 deployment scripts, none call each other.

**3.2 `deploy_mainnet.sh` creates a temp Python file** at `/tmp/register_adapters.py` -- fragile and opaque.

**3.3 Deployment scripts hardcode protocol addresses** instead of pulling from config.

**3.4 No idempotency or rollback** -- partial deployment requires full restart.

### Recommendations

| # | Action | Priority |
|---|--------|----------|
| 3.A | Create a single `deploy.py --chain polygon\|arbitrum\|testnet` | High |
| 3.B | Add deployment state tracking for resume | Medium |
| 3.C | Move hardcoded protocol addresses to config | Medium |

---

## 4. Monitoring & Observability

### Severity: Critical

**4.1 No live monitoring infrastructure** -- docker-compose has PostgreSQL/Redis but no Prometheus/Grafana.

**4.2 MetricsCollector is disconnected** -- `src/utils/metrics_collector.py` has `export_prometheus()` and `export_metrics_json()` but neither `run_bot.py` nor `run_bot_arbitrum.py` ever imports it. Fully built, just not wired up.

**4.3 No health-check endpoint** -- only way to check is SSH + tail logs.

### Recommendations

| # | Action | Priority |
|---|--------|----------|
| 4.A | Wire up `MetricsCollector` in `run_bot.py` -- already built | Critical |
| 4.B | Add Prometheus + Grafana to `docker-compose.yml` | High |
| 4.C | Add HTTP health endpoint returning JSON status | High |

---

## 5. Documentation Quality

### Severity: High

55+ markdown files with overlapping topics. Deployment alone has 6+ competing guides. README has 3 versions. Script references point to nonexistent files.

---

## 6. Error Experience

### Severity: Medium-High

**6.1** Generic error messages without actionable guidance.
**6.2** RPC failures logged at DEBUG level -- invisible to operator at default INFO level. Looks like "no opportunities" when RPC is actually down.
**6.3** Exception swallowing in scan loop -- infinite loop of identical errors with no escalation.
**6.4** Circuit breaker messages lack investigation guidance.

### Recommendations

| # | Action | Priority |
|---|--------|----------|
| 6.A | Add actionable guidance to every error message | High |
| 6.B | Elevate RPC failures from DEBUG to WARNING/ERROR with counters | High |
| 6.C | Implement startup canary check before entering main loop | High |

---

## Prioritized Action Plan

### Phase 1: Security Emergency (Do Today)
1. Rotate ALL private keys. Transfer funds from compromised wallets.
2. Add `.env.*`, `*.bak*` to `.gitignore`.
3. Use BFG to remove secret history from git.

### Phase 2: Operator Sanity (This Week)
4. Wire up `MetricsCollector` in `run_bot.py`.
5. Add periodic heartbeat log (every 60s).
6. Add startup config validation.
7. Elevate RPC failures from DEBUG to WARNING/ERROR.
8. Archive 40+ non-canonical markdown files.

### Phase 3: Configuration Consolidation (Next Sprint)
9. Unify entrypoints into single `run_bot.py --chain` flag.
10. Consolidate config into `.env` + `config.yaml` + one loader.
11. Consolidate deployment scripts into `deploy.py --chain`.
12. Add HTTP health endpoint.

### Phase 4: Production Readiness (Following Sprint)
13. Add Prometheus + Grafana to docker-compose.
14. Add structured JSON logging.
15. Fetch live token prices from oracle.
16. Write one canonical set of operator docs.

---

*Report generated by UX Lead agent.*
