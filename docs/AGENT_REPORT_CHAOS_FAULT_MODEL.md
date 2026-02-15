# Chaos Engineering Fault Model Report

## Flash Loan Arbitrage Bot -- Comprehensive Failure Analysis

**Report Generated:** 2026-02-12
**Analyst:** Chaos Engineering / Fault Injection Agent (Claude Opus 4.6)
**Scope:** All Python modules, database layer, RPC interactions, on-chain transaction lifecycle
**Classification:** CONFIDENTIAL -- INTERNAL USE ONLY

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Architecture Overview](#2-system-architecture-overview)
3. [Dependency Map](#3-dependency-map)
4. [Failure Scenario Analysis](#4-failure-scenario-analysis)
   - A. [RPC Node Failures](#a-rpc-node-failures)
   - B. [Database Failures](#b-database-failures)
   - C. [Transaction Lifecycle Failures](#c-transaction-lifecycle-failures)
   - D. [State Corruption](#d-state-corruption)
   - E. [Resource Exhaustion](#e-resource-exhaustion)
   - F. [Clock / Timing Issues](#f-clock--timing-issues)
   - G. [Smart Contract / On-Chain Failures](#g-smart-contract--on-chain-failures)
   - H. [Configuration and Secrets Failures](#h-configuration-and-secrets-failures)
5. [Failure Mode Matrix](#5-failure-mode-matrix)
6. [Critical Path Analysis](#6-critical-path-analysis)
7. [Recommended Remediation Roadmap](#7-recommended-remediation-roadmap)
8. [Appendix: Files Analyzed](#8-appendix-files-analyzed)

---

## 1. Executive Summary

This report documents **37 distinct failure scenarios** across 8 categories affecting the flash loan arbitrage bot. The analysis is based on a thorough code review of all core modules including `run_bot.py`, `opportunity_detector.py`, `flash_loan_orchestrator.py`, `risk_manager.py`, `metrics_collector.py`, `gas_optimizer.py`, `emergency_shutdown.py`, `database.py`, `models.py`, `config.py`, `transaction_manager.py`, `performance_monitor.py`, `slippage_protection.py`, and `price_cache.py`.

### Key Findings

| Severity | Count | Description |
|----------|-------|-------------|
| **CRITICAL** | 6 | Can cause direct fund loss or unrecoverable state |
| **HIGH** | 11 | Can cause missed opportunities, stuck nonces, or data corruption |
| **MEDIUM** | 12 | Degraded performance or partial data loss |
| **LOW** | 8 | Cosmetic issues or minor operational inconvenience |

### Top 5 Most Dangerous Failure Modes

1. **Nonce gap from failed transaction** -- all subsequent transactions permanently stuck until manual intervention
2. **Bot crash between send_raw_transaction and DB write** -- orphaned on-chain transaction with no record
3. **eth_call simulation passes but real tx reverts** -- gas burned, flash loan fee potentially lost on-chain
4. **Circuit breaker / risk state lost on restart** -- bot re-enters trading with no memory of prior losses
5. **RPC returns stale data** -- bot acts on phantom opportunities, executing trades against expired price state

---

## 2. System Architecture Overview

```
                    +------------------+
                    |    run_bot.py    |
                    |  (Main Loop)     |
                    +--------+---------+
                             |
              +--------------+--------------+
              |                             |
    +---------v----------+     +------------v-----------+
    | OpportunityDetector|     | FlashLoanOrchestrator  |
    | (scan_opportunities)|     | (execute_opportunity)  |
    +----+--------+------+     +---+--------+-----------+
         |        |                |        |
    +----v---+ +--v-------+  +----v---+ +--v-----------+
    | V3     | | V2       |  | Build  | | sign + send  |
    | Quoter | | Router   |  | Tx     | | raw_tx       |
    | (RPC)  | | (RPC)    |  | (RPC)  | | (RPC)        |
    +--------+ +----------+  +--------+ +--------------+
                                    |
                          +---------v---------+
                          |  wait_for_receipt  |
                          |  (RPC polling)     |
                          +---+-------+--------+
                              |       |
                 +------------v+  +---v-----------+
                 | RiskManager  |  | Database      |
                 | (in-memory)  |  | (PostgreSQL)  |
                 +--------------+  +---------------+
                        |
                 +------v--------+
                 | MetricsCollector|
                 | (in-memory +   |
                 |  JSON export)  |
                 +----------------+
```

### Threading Model

- **Direct execution mode** (`DIRECT_EXECUTION=true`): Single-threaded. The detector loop calls `execute_opportunity` inline via `time.sleep()` polling. All RPC calls, DB writes, and risk checks happen sequentially on the main thread.
- **Database queue mode** (`DIRECT_EXECUTION=false`): Two daemon threads -- `detector_thread` and `orchestrator_thread` -- share the same `Web3` instance and database engine. The main thread runs a heartbeat loop at 1-second intervals.

### External Dependencies

| Dependency | Protocol | Timeout Configured? | Retry Logic? |
|-----------|----------|---------------------|-------------|
| RPC Node (Polygon/Arbitrum) | HTTPS JSON-RPC | No explicit timeout on HTTPProvider | None |
| PostgreSQL | TCP/libpq | pool_pre_ping=True | Rollback on exception |
| Uniswap V3 QuoterV2 | RPC eth_call | No | None (bare except) |
| QuickSwap Router | RPC eth_call | No | None (bare except) |
| Aave V3 Flash Loan | On-chain | N/A (atomic) | N/A |
| File system (logs, metrics JSON) | Local I/O | No | None |

---

## 3. Dependency Map

### Per-Scan RPC Calls (Opportunity Detection)

Each `scan_opportunities()` call for 4 trading pairs with optimization makes approximately:

- **Minimum per pair**: 2 calls (1 quick-test V3 + 1 quick-test V2) if no opportunity
- **Maximum per pair**: ~60 calls (3 V3 fee tiers + 1 V2) * 15 optimization amounts
- **Gas price check**: 1 call per scan
- **Chain ID**: 1 call (cached by Web3 in some configurations)
- **Total per scan cycle**: 8 to 244+ RPC calls

### Per-Execution RPC Calls (Transaction Lifecycle)

Each `execute_opportunity()` call makes:

1. `paused()` -- 1 call
2. `get_block('latest')` -- 1 call (for base_fee)
3. `get_transaction_count(address, 'pending')` -- 1 call (for nonce)
4. `estimate_gas()` -- 1 call
5. `eth_call()` -- 1 call (simulation)
6. `send_raw_transaction()` -- 1 call
7. `wait_for_transaction_receipt()` -- N calls (polling, up to 120s timeout)
8. `chain_id` -- 1 call (in _log_execution)

**Total**: 7 + N polling calls per execution

---

## 4. Failure Scenario Analysis

---

### A. RPC Node Failures

---

#### A1. RPC Returns Stale Data (Block Number Does Not Advance)

**Trigger:** RPC load balancer routes requests to a node that is behind the chain tip. This commonly occurs with free/shared RPC endpoints (e.g., the default `https://polygon-rpc.com`) or during node resync events. The node returns valid JSON-RPC responses but the data reflects a block that is several seconds or minutes old.

**Current Behavior:** The bot has no staleness detection. In `run_bot.py` lines 345-349, there is a one-time canary check at startup (`web3.eth.get_block('latest')`), but there is no ongoing validation that block numbers are advancing. The `OpportunityDetector.scan_opportunities()` method (line 569-624) performs all quotes against whatever block the RPC returns. If the RPC is serving stale state:
- `get_v3_quote()` and `get_v2_quote()` will return prices that no longer exist on-chain
- The opportunity calculation will show a profitable spread that has already been arbitraged by someone else
- The simulation (`eth_call`) in the orchestrator may also execute against stale state if the same RPC is used, so the simulation passes
- When `send_raw_transaction()` is broadcast and mined against the real chain tip, the on-chain prices have moved and the transaction reverts

The `_heartbeat()` method (line 102-126) logs `self.web3.eth.chain_id` and `risk_metrics`, but never checks the current block number or compares it to a previous value.

**Impact:** MEDIUM-HIGH. Gas is burned on a reverted transaction. In the worst case, if the stale data creates a false negative on simulation and the swap's `minAmountOut` is calculated from stale quotes, the actual execution could result in receiving fewer tokens than expected, though the contract's `minFinalAmount` parameter provides an on-chain floor that should cause a revert rather than a loss.

**Detection:** An operator would see: (1) simulation passes but transaction reverts on-chain, (2) the heartbeat log does not report any staleness metrics, (3) block explorer shows reverted transactions. There is no automated alerting for this.

**Recommended Fix:**
- Add a `_check_rpc_freshness()` method that runs on every scan cycle. Compare `web3.eth.get_block('latest')['number']` to the previous scan's block number. If it has not advanced in 2+ cycles, skip the scan and log a warning.
- Store `latest_block_timestamp` from the block header and compare to system time. If the block is more than 30 seconds old, consider the RPC stale.
- Use multiple RPC endpoints with a fallback strategy (e.g., `web3.middleware` with `construct_simple_cache_middleware` or a custom provider that queries 2+ RPCs and takes the highest block number).

---

#### A2. RPC Returns Error on eth_call but Succeeds on send_raw_transaction

**Trigger:** Rate limiting kicks in between the simulation `eth_call` (orchestrator line 351-358) and the actual `send_raw_transaction` (line 379). Alternatively, the simulation RPC endpoint is temporarily degraded while the broadcast endpoint is healthy (common with RPC providers that route simulation and broadcast to different backends).

**Current Behavior:** In `execute_opportunity()` (line 350-363), if `eth_call` raises an exception, the code catches it, logs "Simulation FAILED", sets `result['error']`, and returns early without sending the transaction. This is the correct conservative behavior -- an `eth_call` failure prevents execution.

However, the inverse scenario is more dangerous: the `eth_call` succeeds (line 359: "Simulation passed") but the subsequent `send_raw_transaction` fails. In this case, the exception at line 379 is caught by the outer `except Exception as e` at line 411, which sets `result['error']` and returns. No nonce is leaked because the nonce was allocated in `build_transaction()` at line 296 but never successfully submitted.

**Impact:** LOW-MEDIUM. The bot correctly avoids sending if simulation fails. The main risk is opportunity cost -- a valid opportunity is skipped because the simulation RPC was temporarily erroring.

**Detection:** The `logger.error("Simulation FAILED: ...")` message at line 361 would appear in `bot.log`. The metrics collector records the error via `self.metrics.record_error()`.

**Recommended Fix:**
- Implement a retry mechanism for `eth_call` with 2-3 attempts and exponential backoff before giving up.
- Consider using a separate, more reliable RPC endpoint for simulation vs. broadcast.

---

#### A3. RPC Timeout During wait_for_transaction_receipt

**Trigger:** After `send_raw_transaction()` succeeds and the transaction is in the mempool, the bot calls `self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)` at line 384. The RPC connection drops, the node becomes unreachable, or the node returns errors during polling.

**Current Behavior:** `wait_for_transaction_receipt` will raise a `TimeExhausted` exception after 120 seconds or a `ConnectionError` / `requests.exceptions.ReadTimeout` if the RPC becomes unreachable. This exception is caught by the outer `except Exception as e` block at line 411 in `execute_opportunity()`.

The result dict is returned with `success=False` and `error` set to the exception message. The transaction hash is **not** set in `result['tx_hash']` because the code only sets it after a successful receipt (lines 390, 409). This means:
- The database `_log_execution()` call (line 421) receives a result with no `tx_hash`
- The `risk_manager.record_trade_result()` in `run_bot.py` (line 215) records a failure
- **The transaction is still live on-chain** -- it may confirm successfully minutes later

This is the **orphaned transaction problem**: the bot has no record of the pending transaction, and on restart it will use `get_transaction_count(address, 'pending')` for the nonce, which may return the correct next nonce. But the bot's internal state (risk manager, metrics) will be inconsistent with reality.

**Impact:** HIGH. The transaction may succeed on-chain (generating profit) but the bot records it as a failure. Or the transaction may fail on-chain (burning gas) but the bot has already moved on. In either case, the risk manager's P&L tracking becomes incorrect. If the transaction succeeds and earns profit, that profit is invisible to the bot.

**Detection:** The operator would need to manually check the wallet address on a block explorer to see the pending/confirmed transactions. The `bot.log` would show the error message from the timeout. There is no mechanism to reconcile on-chain state with bot state.

**Recommended Fix:**
- After `send_raw_transaction`, immediately record the `tx_hash` in the result dict and in the database **before** waiting for receipt.
- Implement a background transaction monitor that periodically checks for pending tx_hashes and updates their status.
- On bot startup, query the database for transactions in `SUBMITTED` / `PENDING` status and reconcile them against on-chain state.
- Use a separate goroutine/thread for receipt polling so it does not block the main scan loop.

---

#### A4. RPC Rate Limits Kick In Mid-Scan

**Trigger:** The `scan_opportunities()` method with flash loan optimization makes up to 244+ RPC calls per scan cycle. Free or shared RPC endpoints (Alchemy free tier: 330 CU/s, Infura free: 10 req/s, public polygon-rpc.com: variable) can easily be exhausted. Rate limiting manifests as HTTP 429 responses or JSON-RPC error codes like `-32005`.

**Current Behavior:** Each quote call (`get_v3_quote` at line 195-208, `get_v2_quote` at line 227-236) has a bare `except Exception as e` that logs a warning and returns `None`. When a quote returns `None`, the arbitrage calculation skips that path. If all quotes fail due to rate limiting, `scan_opportunities()` returns an empty list, and the bot sleeps for `check_interval` seconds before trying again.

This is a reasonable degradation -- the bot stops finding opportunities but does not crash or take harmful actions. However, there is no backoff logic. The bot will immediately retry the same rate-limited endpoint on the next cycle after `check_interval` seconds (default: 5s), which may keep it in a rate-limited state indefinitely.

The `_heartbeat()` method (line 109) also makes an RPC call (`self.web3.eth.chain_id`) that contributes to rate consumption.

**Impact:** MEDIUM. The bot becomes blind (cannot see opportunities) but does not lose funds. Extended rate limiting reduces the probability of capturing profitable opportunities. The `metrics_collector.record_error()` will accumulate errors but there is no circuit-breaker for RPC failures specifically.

**Detection:** The `bot.log` will be flooded with warning messages like "V3 quote failed for ..." and "V2 quote failed for ...". The heartbeat log will continue showing `status=OK` even when all quotes are failing, which is misleading.

**Recommended Fix:**
- Implement an RPC-specific circuit breaker: if N consecutive RPC calls fail, increase `check_interval` temporarily (exponential backoff from 5s to 30s, capped at 60s).
- Track RPC error rate in the heartbeat output so operators can see degradation.
- Use multiple RPC endpoints with round-robin or failover logic.
- The `Web3.HTTPProvider` supports a `request_kwargs` parameter -- set `timeout=10` to prevent hung connections.

---

#### A5. RPC Returns Incorrect Data (Byzantine Fault)

**Trigger:** A compromised or buggy RPC node returns plausible but incorrect data. For example, a quote for USDC->WMATIC returns an `amountOut` that is 10x larger than reality, creating a phantom arbitrage opportunity.

**Current Behavior:** There is no validation of RPC return values against expected ranges. The `get_v3_quote()` and `get_v2_quote()` methods return whatever the RPC provides. The `calculate_arbitrage()` method computes profit based on these raw values. If the values are incorrect:
- The opportunity looks highly profitable
- The simulation (`eth_call`) might also return incorrect results from the same compromised node
- The real transaction executes against the actual chain state and reverts (if using honest validators) or succeeds with actual (lower) profit

The `minFinalAmount` parameter in the smart contract provides the critical defense: if the actual output is less than `amount_in + net_profit` (as set by `build_swap_steps` line 208, 230), the contract reverts. Since `net_profit` was calculated from the Byzantine data, the `minFinalAmount` will be unrealistically high, causing a revert and protecting capital. However, gas is still burned.

**Impact:** MEDIUM. The on-chain `minFinalAmount` check protects against fund loss. The main cost is gas burned on reverted transactions. If the Byzantine node also corrupts the `eth_call` simulation, the bot will keep attempting and burning gas until the RPC issue resolves.

**Detection:** Repeated simulation-pass-but-execution-revert patterns. The `bot.log` will show large profit estimates followed by reverted transactions.

**Recommended Fix:**
- Add sanity checks on quote outputs: if `amountOut` implies a price that deviates more than X% from a cached reference price, flag it as suspicious and skip.
- Cross-validate critical quotes against a secondary RPC endpoint before executing.
- Track the ratio of simulation-pass-but-execution-fail and trigger an alert if it exceeds a threshold.

---

#### A6. Web3 HTTPProvider Has No Timeout Configured

**Trigger:** `Web3(Web3.HTTPProvider(rpc_url))` is called at `run_bot.py` line 337 without any `request_kwargs`. The default `requests` library timeout is `None` (wait forever). If the RPC node hangs (accepts TCP connection but never responds), the bot's main thread blocks indefinitely.

**Current Behavior:** The main thread (in direct execution mode) blocks on any of the following calls: `get_v3_quote`, `get_v2_quote`, `gas_price`, `get_block`, `estimate_gas`, `eth_call`, `send_raw_transaction`, `wait_for_transaction_receipt`. A single hung RPC call freezes the entire bot. The heartbeat stops, the scan loop stops, no errors are logged (because the thread is blocked, not erroring).

In database queue mode, only the affected thread blocks, but since there are only 2 daemon threads, losing one effectively halts either detection or execution.

**Impact:** HIGH. The bot becomes completely unresponsive. No trades are made. If a transaction was already sent, the receipt-waiting code has a 120-second timeout, but all other calls have none. An operator monitoring `bot.log` would see the heartbeat stop.

**Detection:** The heartbeat log (60-second interval) stops appearing. The `metrics_latest.json` file stops being updated.

**Recommended Fix:**
- Initialize Web3 with a timeout: `Web3(Web3.HTTPProvider(rpc_url, request_kwargs={'timeout': 30}))`.
- Wrap all RPC calls in a deadline context (Python `signal.alarm` on Unix or `concurrent.futures.ThreadPoolExecutor` with timeout).
- Implement a watchdog thread that checks if the scan loop has progressed within 2x the expected cycle time.

---

### B. Database Failures

---

#### B1. PostgreSQL Connection Drops Mid-Write (During _log_execution)

**Trigger:** The PostgreSQL server restarts, network blip drops the TCP connection, or the connection times out during the `db.commit()` call inside `_log_execution()` (orchestrator line 510). This can also happen inside `log_opportunity()` (detector line 527-567).

**Current Behavior:** The `get_db()` context manager (database.py line 43-61) wraps the session in a try/except. If `db.commit()` raises an exception:
1. The `except Exception` block calls `db.rollback()`
2. The `finally` block calls `db.close()`
3. The exception propagates up to the caller

In `_log_execution()` (orchestrator line 513), the exception is caught by the bare `except Exception as e` at line 513, which logs "Failed to log execution to database" and returns without re-raising. This means **the transaction execution result is silently lost** -- the on-chain transaction succeeded (or failed), but the database has no record.

In `log_opportunity()` (detector line 566), the same pattern applies -- the opportunity detection is logged but silently fails.

The engine has `pool_pre_ping=True` (database.py line 19), which validates connections before use. However, `pool_pre_ping` only checks before starting a session, not during long-running operations.

**Impact:** MEDIUM-HIGH. Loss of audit trail. The bot continues operating, but the database lacks records of executed trades. Risk management calculations that depend on trade history (from the database) are unaffected because the `RiskManager` uses its own in-memory `LossTracker`. However, post-incident forensics and P&L reporting are compromised.

**Detection:** The `bot.log` will contain "Failed to log execution to database: ..." error messages. There is no automated alerting or retry mechanism.

**Recommended Fix:**
- Implement a write-ahead pattern: write the execution intent to a local file (append-only journal) before the DB write, then reconcile on startup.
- Add retry logic (3 attempts with 1s backoff) for database writes in `_log_execution()`.
- If DB write fails after retries, queue the write for background processing rather than silently dropping it.
- Add a health check that periodically verifies the last DB write timestamp.

---

#### B2. Database Disk Full

**Trigger:** The PostgreSQL `data` directory runs out of disk space. The `execution_log` table can grow unboundedly -- every opportunity detection and execution creates rows. The `JSONB` columns (`dex_path`, `token_path`, `extra_data`, `simulation_data`, `data`, `logs`) can store arbitrarily large JSON payloads.

**Current Behavior:** All database writes fail with `DiskFull` or `OperationalError`. Due to the silent catch pattern in `_log_execution()` and `log_opportunity()`, the bot continues running but no data is persisted. The SQLAlchemy engine may also fail to create new connections if the WAL file cannot be written.

**Impact:** MEDIUM. Same as B1 -- loss of audit trail. The bot can continue trading (all critical state is in-memory), but all database features (opportunity tracking, trade history, execution logs) cease.

**Detection:** PostgreSQL will log errors to its own log file. The bot's `bot.log` will show database errors. No proactive monitoring exists in the bot.

**Recommended Fix:**
- Add a periodic disk space check (e.g., `shutil.disk_usage()`) with a warning threshold.
- Implement retention policies: delete `execution_log` rows older than 30 days, archive `opportunities` older than 90 days.
- Set up database monitoring (pg_stat_activity, pg_stat_database) external to the bot.

---

#### B3. Connection Pool Exhaustion

**Trigger:** The database engine is configured with `pool_size=10` and `max_overflow=20` (config.py line 29, database.py line 16-18). In database queue mode, two threads make concurrent database calls. If a long-running query blocks, new session requests queue up. Additionally, the `get_db_session()` function (database.py line 64-76) returns a session that must be closed manually -- if callers forget to close, connections leak.

Currently, `get_db()` (the context manager) always closes in the `finally` block, so sessions obtained through `get_db()` do not leak. But if any code path uses `get_db_session()` without proper cleanup, connections accumulate.

**Current Behavior:** When the pool is exhausted, `SessionLocal()` blocks (waits for a connection) or raises `TimeoutError` after a default timeout. In the current code, no pool timeout is configured, so the call blocks forever. This would freeze whichever thread is trying to get a DB session.

**Impact:** MEDIUM. In direct execution mode, the main thread blocks on DB access. In queue mode, one thread blocks. Since database writes are best-effort (caught exceptions), the impact is limited to logging and tracking.

**Detection:** Thread appears hung. Heartbeat log stops if the main thread is blocked.

**Recommended Fix:**
- Add `pool_timeout=10` to the `create_engine()` call to fail fast instead of blocking forever.
- Audit all uses of `get_db_session()` to ensure proper cleanup.
- Add connection pool metrics to the heartbeat output.

---

#### B4. Slow Queries Blocking the Main Loop

**Trigger:** In the `monitor_opportunities()` method (orchestrator line 544-588), the orchestrator queries for `DETECTED` opportunities ordered by `expected_profit DESC` with a limit of 5. On a large `opportunities` table without proper index maintenance (vacuuming, analyze), this query can become slow.

Additionally, in `_log_execution()`, the `db.query(Opportunity).filter_by(opportunity_id=opportunity_id).first()` query (line 442-444) may become slow if the `opportunity_id` index is fragmented.

**Current Behavior:** In direct execution mode, `_log_execution()` runs inline with the scan loop. A slow query directly delays the next scan cycle. In database queue mode, slow queries in the orchestrator thread delay execution but do not block detection.

However, the `log_opportunity()` call happens inside `scan_opportunities()` (detector line 619), which means even in queue mode, a slow DB write during detection blocks the scan loop.

**Impact:** LOW-MEDIUM. Delayed scans mean delayed opportunity detection. In a competitive arbitrage environment, even 1-second delays can mean the opportunity is taken by another bot.

**Detection:** The `metrics.record_detection_time(scan_ms)` call (run_bot.py line 141) would show increased detection times. The `PerformanceMonitor` warns if detection exceeds 2 seconds.

**Recommended Fix:**
- Make `log_opportunity()` asynchronous (fire-and-forget to a background thread/queue).
- Ensure PostgreSQL indexes are maintained with regular `VACUUM ANALYZE`.
- Add a query timeout to the database session: `engine.execute("SET statement_timeout = '5s'")`.

---

### C. Transaction Lifecycle Failures

---

#### C1. eth_call Simulation Passes but Real Transaction Reverts

**Trigger:** Between the `eth_call` simulation (orchestrator line 351-358) and the actual `send_raw_transaction` (line 379), the on-chain state changes. Another arbitrageur executes the same opportunity, a large swap moves prices, or a new block is mined with different base state. The simulation was evaluated against block N, but the transaction executes in block N+1 or later.

On Polygon, blocks are produced every ~2 seconds. The time between simulation and broadcast includes: gas estimation, transaction signing, and network round-trip. This window is typically 1-5 seconds -- enough for 1-3 blocks to pass.

**Current Behavior:** The transaction is broadcast and mined. If it reverts:
- `receipt['status'] == 0` at orchestrator line 387
- The result is logged as a failure (line 407-409)
- Gas is burned (gas_used * effectiveGasPrice)
- The flash loan fee may or may not be charged depending on where in the execution the revert occurs (Aave V3 reverts the entire operation atomically, so the flash loan fee is not charged if the arbitrage fails)
- The risk manager records a loss equal to `gas_cost_usd` (run_bot.py line 207)
- The circuit breaker increments `consecutive_losses` (risk_manager.py line 457)

**Impact:** HIGH. Gas is burned. If this happens repeatedly (e.g., during high-competition periods), the daily gas expenditure could exceed `DAILY_LOSS_LIMIT_USD` before the circuit breaker triggers (since gas losses are recorded as `Decimal('0')` for `gas_cost_usd` -- see run_bot.py line 196: `gas_cost_usd = Decimal('0')  # Simplified`). The circuit breaker counts consecutive failures, but the daily P&L tracking may not reflect gas losses accurately because `gas_cost_usd` is hardcoded to 0.

**CRITICAL SUB-FINDING**: At `run_bot.py` line 196, `gas_cost_usd = Decimal('0')  # Simplified`. This means the `LossTracker` never sees gas costs. A failed trade is recorded with `profit_loss = -gas_cost_usd = -0`. The daily P&L never decreases from gas losses. The `DAILY_LOSS_LIMIT_USD` check is effectively disabled for gas-only losses.

**Detection:** The `bot.log` shows "Transaction failed (reverted)". The circuit breaker may eventually trigger if there are 5+ consecutive failures (default `MAX_CONSECUTIVE_LOSSES=5`). But the daily loss limit does not catch gradual gas bleeding.

**Recommended Fix:**
- **Fix the gas cost tracking**: Calculate actual gas cost from the receipt and feed it to both `metrics.record_trade()` and `risk_manager.record_trade_result()`.
- Implement pre-broadcast freshness check: after simulation, check if a new block has been mined. If so, re-simulate before broadcasting.
- Use Flashbots Protect or similar MEV-protection services that allow simulation at the pending block level.
- Add a "revert rate" metric: if >30% of recent transactions revert, pause execution and increase `check_interval`.

---

#### C2. Transaction Stuck in Mempool (Gas Too Low, Never Mined)

**Trigger:** The bot calculates `maxFeePerGas` as `base_fee * 2 + max_priority` (orchestrator line 289). If gas prices spike (e.g., during network congestion), the `maxFeePerGas` may be below the minimum required by validators. The transaction sits in the mempool but is never included in a block.

**Current Behavior:** `wait_for_transaction_receipt(tx_hash, timeout=120)` at line 384 will eventually raise `TimeExhausted` after 120 seconds. The exception is caught at line 411. The transaction remains in the mempool. The nonce used by this transaction is consumed -- the bot cannot use it for another transaction.

On the next execution attempt, `get_transaction_count(self.address, 'pending')` at line 296 returns the nonce **after** the stuck transaction (because `'pending'` includes mempool transactions). So the next transaction gets the correct nonce and can be mined. However, if the stuck transaction is eventually mined later (validators include it when gas drops), it will execute with potentially stale parameters (old deadline, old prices).

The deadline parameter (line 271: `deadline = int(time.time()) + 300`) provides protection: the on-chain contract checks `block.timestamp <= deadline`, and after 5 minutes, the stuck transaction will revert when mined (deadline expired).

**Impact:** MEDIUM. The stuck transaction will eventually revert (deadline protection), burning gas. The bot can continue operating with new transactions (the `'pending'` nonce count includes the stuck tx). The main risk is if the deadline is NOT enforced by the contract for some code paths.

**Detection:** `bot.log` shows the timeout error. The wallet on-chain shows a pending transaction. The `metrics_final.json` shows a failed execution.

**Recommended Fix:**
- Implement a "speed-up" mechanism: if `wait_for_transaction_receipt` times out, re-broadcast the same transaction with a higher gas price (same nonce, higher `maxFeePerGas`).
- Track pending transaction hashes and periodically check their status.
- Consider using `maxFeePerGas = base_fee * 3 + max_priority` for higher inclusion probability.

---

#### C3. Transaction Mined but Receipt Never Received (RPC Drops Connection)

**Trigger:** Similar to A3 but more specific: the transaction is successfully mined, but the RPC connection drops during `wait_for_transaction_receipt` polling. The bot never receives the receipt.

**Current Behavior:** The `TimeExhausted` exception fires. The bot records a failure. But the transaction actually succeeded on-chain -- profit was generated but the bot does not know about it.

**Impact:** HIGH. Same as A3. The risk manager records a false loss. P&L tracking becomes inaccurate. The circuit breaker may trigger incorrectly due to "consecutive losses" that were actually successes.

**Detection:** Same as A3. Only manual block explorer verification reveals the truth.

**Recommended Fix:**
- Same as A3: persist `tx_hash` to database immediately after `send_raw_transaction`, before waiting for receipt.
- On startup, implement a reconciliation pass that checks all `SUBMITTED` status transactions against on-chain state.
- After a receipt timeout, do NOT record as failure. Instead, mark as `UNKNOWN` and schedule a background check.

---

#### C4. Nonce Gap Created by Failed Transaction

**Trigger:** The `FlashLoanOrchestrator.build_transaction()` method at line 296 fetches the nonce using `get_transaction_count(self.address, 'pending')`. If a prior transaction failed to broadcast (e.g., RPC error on `send_raw_transaction`) but the nonce was already allocated:

Scenario:
1. Transaction A gets nonce=5, `build_transaction` succeeds
2. `send_raw_transaction` for Transaction A fails (network error)
3. Transaction A is NOT in the mempool. Nonce 5 is unused on-chain.
4. Transaction B calls `get_transaction_count(address, 'pending')` which returns 5 (because nonce 5 was never used)
5. Transaction B gets nonce=5, executes successfully
6. No nonce gap -- this scenario is actually handled correctly

However, there is a more subtle scenario in the `TransactionManager` (transaction_manager.py):
1. `get_next_nonce()` allocates nonce 5 and adds it to `_pending_nonces`
2. `build_transaction()` succeeds
3. `sign_and_send()` fails
4. `release_nonce(5)` is called in the retry loop
5. On retry, `get_next_nonce()` calls `get_transaction_count('pending')` which returns 5
6. But `max(pending_nonce, tracked_max + 1)` could be incorrect if _pending_nonces still has stale entries

The actual `FlashLoanOrchestrator` does NOT use the `TransactionManager` class -- it builds transactions directly. So the nonce management is simpler but also more fragile: each call to `build_transaction()` fetches the nonce freshly from the RPC.

**Where the real nonce gap risk exists:** If `send_raw_transaction` at orchestrator line 379 succeeds (returns a tx_hash) but the transaction is dropped from the mempool (RPC node restarts, mempool cleared). The nonce is consumed from the bot's perspective but not confirmed on-chain. The next transaction gets nonce+1. When the bot broadcasts nonce+1, it is valid ONLY if nonce was in the mempool. If nonce was dropped, nonce+1 will be rejected with "nonce too high".

**Current Behavior:** The bot does not track which nonces it has used. Each `execute_opportunity` call independently fetches the pending nonce. If a nonce gap exists, the next `send_raw_transaction` will fail with "nonce too high", caught by the outer exception handler.

**Impact:** HIGH. All subsequent transactions fail until the nonce gap is resolved. The bot enters a failure loop: detect opportunity -> attempt to execute -> "nonce too high" -> record failure -> repeat. The circuit breaker would eventually trigger after `MAX_CONSECUTIVE_LOSSES` (default 5) failures, pausing trading for `CIRCUIT_BREAKER_COOLDOWN_MIN` (default 60) minutes. After cooldown, the nonce gap persists and the cycle repeats.

**Detection:** `bot.log` shows repeated "nonce too high" errors in the execution failure messages. The circuit breaker logs its activation.

**Recommended Fix:**
- After any nonce-related error, implement a recovery procedure: fetch `get_transaction_count(address, 'latest')` (not `'pending'`) and compare with `'pending'`. If they differ, there are pending transactions to wait for. If they are equal, the nonce gap exists and the bot should reset to the `'latest'` nonce.
- Alternatively, send a self-transfer (0 value) with the missing nonce to fill the gap.
- Add nonce tracking to a persistent store (database) so it survives restarts.

---

#### C5. Double-Send Due to Retry Logic

**Trigger:** The `TransactionManager.execute_transaction()` method (transaction_manager.py line 207-274) has built-in retry logic with `max_retries=3`. If a transaction is broadcast but the response is lost (network error after sending), the retry logic may attempt to re-send the same transaction with a new nonce.

**Current Behavior:** The `FlashLoanOrchestrator` does NOT use `TransactionManager` -- it sends transactions directly without retry logic. Each call to `execute_opportunity()` executes exactly once. There is no retry mechanism in the orchestrator.

However, in the `run_bot.py` `execute_opportunity()` method (line 171-223), if the orchestrator returns a failure, there is no retry at the bot level either. The opportunity is simply recorded as failed and the next scan cycle begins.

The risk of double-send is LOW in the current architecture because there is no retry logic for transaction broadcasting. However, if retry logic were added (as a recommended fix for other issues), it would need to be nonce-aware to prevent double-spending.

**Impact:** LOW. No retry mechanism currently exists for the orchestrator's transaction broadcasting. The `TransactionManager` class has retry logic but is not used in the main execution path.

**Detection:** N/A -- the scenario does not currently occur.

**Recommended Fix:**
- If adding retry logic, ensure it uses the SAME nonce for retries (with increasing gas price, i.e., replacement transaction) rather than allocating a new nonce.
- Implement idempotency keys for transactions (e.g., hash of opportunity parameters) to detect duplicate broadcasts.

---

### D. State Corruption

---

#### D1. Bot Crashes Between send_raw_transaction and Database Write

**Trigger:** The Python process is killed (OOM killer, `kill -9`, power failure) after `send_raw_transaction()` returns a tx_hash (orchestrator line 379) but before `_log_execution()` commits to the database (line 421/510).

More specifically, the crash window is:
1. After line 379 (`tx_hash = self.web3.eth.send_raw_transaction(signed_txn.raw_transaction)`)
2. Before line 421 (`self._log_execution(opportunity_id, result, execution_time)`) which is only called when `opportunity_id` is provided.

In the `run_bot.py` execution path (line 189: `result = self.orchestrator.execute_opportunity(opportunity)`), the `opportunity_id` is NOT passed to `execute_opportunity`. Looking at `execute_opportunity()` signature (line 308): `opportunity_id: Optional[str] = None`. In `run_bot.py` line 189, it is called as `self.orchestrator.execute_opportunity(opportunity)` without `opportunity_id`. This means **`_log_execution()` is never called from the main bot path** (line 420: `if opportunity_id:` -- always None).

The database write that DOES happen is in `log_opportunity()` (detector line 518-567), which records the detected opportunity. But the execution result is NOT written to the database in the `run_bot.py` direct execution path.

In the database queue mode (orchestrator line 582), `opportunity_id=opp.opportunity_id` IS passed, so `_log_execution()` IS called.

**CRITICAL SUB-FINDING**: In direct execution mode, the `_log_execution()` method is NEVER called because `run_bot.py` line 189 does not pass `opportunity_id`. Execution results are only tracked in the in-memory `risk_manager` and `metrics` objects. No execution results reach the database.

**Impact:** CRITICAL in direct execution mode. All execution results exist only in memory. A crash loses all trade history. Even without a crash, a normal shutdown loses this data (the `bot.stop()` method only exports metrics JSON, not database records).

In database queue mode, the crash window between `send_raw_transaction` and `_log_execution` completing is ~1-120 seconds (while waiting for receipt). A crash during this window orphans the on-chain transaction.

**Detection:** After a crash, the database shows opportunities as `DETECTED` but no corresponding `Transaction` or `TradeResult` rows. The wallet's on-chain transaction history shows transactions that have no database record.

**Recommended Fix:**
- **In direct execution mode**: Pass the `opportunity_id` from the detector to the orchestrator via the opportunity dict and forward it to `execute_opportunity()`.
- Write the tx_hash to the database IMMEDIATELY after `send_raw_transaction`, before waiting for receipt (with status `SUBMITTED`).
- On startup, run a reconciliation loop: query the database for opportunities with status `EXECUTING` or `SUBMITTED`, then check their on-chain status and update.

---

#### D2. Circuit Breaker State Lost on Restart

**Trigger:** The `CircuitBreaker` class (risk_manager.py line 423-525) stores all state in memory: `consecutive_losses`, `is_active`, `triggered_at`. The `LossTracker` (line 301-420) stores `trades` as an in-memory list. When the Python process restarts, all of this state is lost.

**Current Behavior:** On restart:
- `consecutive_losses` resets to 0
- `is_active` resets to False
- `triggered_at` resets to None
- `trades` list is empty

If the bot crashed BECAUSE it hit the circuit breaker (or the circuit breaker triggered and an operator restarted the bot), the protection is immediately defeated. The bot resumes trading with a clean slate, potentially re-entering the same losing pattern.

**Impact:** CRITICAL. The circuit breaker is the primary safety mechanism preventing cascade losses. If it can be defeated by a simple restart, it provides false confidence. An operator who restarts the bot during a circuit-breaker cooldown period unknowingly disables the protection.

**Detection:** After restart, the `bot.log` shows "CircuitBreaker initialized: max_losses=5, cooldown=60min" -- no warning that prior state was lost. The `HEARTBEAT` log shows `circuit_breaker=ok` immediately after restart.

**Recommended Fix:**
- Persist circuit breaker state to a file (e.g., `circuit_breaker_state.json`) on every state change.
- On startup, load the persisted state and restore the circuit breaker's state.
- Alternatively, persist to the database: add a `bot_state` table with key-value pairs for circuit breaker state.
- Consider a "startup cooldown" period where the bot does not trade for N minutes after starting, giving the operator time to verify the environment.

---

#### D3. Metrics Counters Reset on Restart

**Trigger:** The `MetricsCollector` (metrics_collector.py) stores all counters in memory: `opportunities_found`, `trades_executed`, `successful_trades`, `failed_trades`, `profits`, `losses`, `gas_costs`, `detection_times`, `execution_times`, `errors`. On restart, all counters reset to 0.

**Current Behavior:** The bot calls `self.metrics.export_metrics_json('metrics_final.json')` in `bot.stop()` (run_bot.py line 257). If the shutdown is graceful, the final metrics are persisted to a JSON file. But the file is overwritten on each export (not appended), and there is no mechanism to reload historical metrics on restart.

On a crash (no graceful shutdown), `metrics_final.json` is never written. The last checkpoint is `metrics_latest.json`, which is updated every heartbeat cycle (60 seconds). So up to 60 seconds of metrics data can be lost.

**Impact:** LOW-MEDIUM. Metrics are used for observability, not safety. The loss of historical metrics makes it harder to analyze bot performance over time. The `metrics_history` list (capped at 1000 entries) provides some intra-run historical data but is lost on restart.

**Detection:** After restart, `metrics_latest.json` will show zero counters. An operator may notice the discontinuity.

**Recommended Fix:**
- On startup, load `metrics_latest.json` and initialize counters from the last known state.
- Use an append-only log for metrics (or a time-series database like InfluxDB/Prometheus with a push gateway).
- Add a `bot_run_id` to metrics exports so historical data from different runs can be distinguished.

---

#### D4. Risk Manager Daily P&L Lost on Restart

**Trigger:** The `LossTracker.trades` list (risk_manager.py line 319) is the sole source of truth for daily and weekly P&L calculations (`get_daily_pnl()`, `get_weekly_pnl()`). On restart, this list is empty.

**Current Behavior:** After restart, `get_daily_pnl()` returns `Decimal("0")` and `check_loss_limit()` returns `(True, "Within loss limits")`. Even if the bot had accumulated significant losses before the crash, the loss limits are bypassed after restart.

Combined with D2 (circuit breaker state lost), this means a restart completely removes all risk management protection. The bot could have hit its daily loss limit, crashed, restarted, and resumed trading with no awareness of prior losses.

**Impact:** CRITICAL. The daily loss limit (`DAILY_LOSS_LIMIT_USD`, default $1000) is designed to prevent catastrophic losses in a single day. If it can be bypassed by a restart, the protection is illusory.

**Detection:** Same as D2 -- no warning on startup that prior P&L data was lost.

**Recommended Fix:**
- Persist trade results to a file or database table that survives restarts.
- On startup, load today's trades from the persistent store and initialize the `LossTracker.trades` list.
- In direct execution mode (where `_log_execution` is never called), this is even more critical because the database has no record of executions. The risk manager's in-memory state is the ONLY record.

---

#### D5. Position Manager State Lost on Restart

**Trigger:** The `PositionManager.open_positions` dict (risk_manager.py line 193) tracks open positions in memory. On restart, it is empty.

**Current Behavior:** After restart, `get_total_exposure()` returns `Decimal("0")` and `check_exposure_limit()` returns `(True, "Exposure OK")`. Any open positions from before the crash are forgotten.

For this bot, "open positions" are somewhat academic since flash loan arbitrage is atomic (borrow, swap, repay in a single transaction). There should not be persistent open positions. However, the `PositionManager` is called with `track_open_position()` but only `close_position()` is called on success (risk_manager.py line 640). If a trade fails, the position is tracked but never closed, creating phantom positions that accumulate until restart.

**Impact:** LOW. Flash loan arbitrage has no persistent positions by design. The position tracking appears to be a framework feature that is not fully integrated.

**Detection:** `risk_metrics.total_exposure` in the heartbeat log would show increasing phantom exposure over time (never decreasing on failures).

**Recommended Fix:**
- For flash loan arbitrage, close positions on both success AND failure (since flash loans are atomic -- there is never a real open position after the transaction completes).
- Or remove position tracking entirely for this use case.

---

#### D6. BalanceValidator Reserved Balances Leak

**Trigger:** The `BalanceValidator.reserved_balances` dict (risk_manager.py line 62) tracks reserved amounts. The `check_balance()` method (line 66-99) reserves balance when `reserve=True`. The `release_balance()` method (line 153-169) releases it.

However, `check_balance()` is an `async` method and is never called in the current `run_bot.py` execution path (the `validate_trade()` method at risk_manager.py line 578-623 is synchronous and does not call `check_balance()`). So `reserved_balances` is always empty.

If it were used, and a trade failed after balance was reserved but before `release_balance()` was called, the reserved amount would be permanently locked (until restart).

**Impact:** LOW. The `BalanceValidator` is not actively used in the current execution path.

**Detection:** N/A -- not currently active.

**Recommended Fix:**
- If `BalanceValidator` is integrated in the future, ensure `release_balance()` is called in all code paths (success, failure, exception).
- Use a context manager pattern for balance reservation.

---

### E. Resource Exhaustion

---

#### E1. Memory Leak in Long-Running Process

**Trigger:** The bot runs indefinitely as a long-running process. Several data structures grow without bound or with insufficient trimming:

1. `LossTracker.trades` (risk_manager.py line 319): Grows with every trade. `reset_daily()` (line 398-403) trims trades older than 7 days, but `reset_daily()` is NEVER called by any code path. There is no periodic cleanup.

2. `MetricsCollector.metrics_history` (metrics_collector.py line 73): Capped at 1000 entries (line 263). Each entry is a `BotMetrics` dataclass. At one entry per heartbeat (60s), 1000 entries = ~16.7 hours. This is properly bounded.

3. `MetricsCollector.profits`, `losses`, `gas_costs` (lines 82-84): These lists grow without bound. One entry per trade. In practice, trade volume is low enough that this is not a concern.

4. `MetricsCollector.errors` (line 91): Capped at 50 entries (line 143). Properly bounded.

5. `EmergencyShutdown.shutdown_history` (emergency_shutdown.py line 67): Grows with every shutdown event. Unlikely to be large.

6. `PriceCache.cache` (price_cache.py line 28): Entries expire after `cache_duration_seconds` (default 3s) but are only removed on access (`get_price()` line 67). If a key is never accessed again, it remains in the cache forever. Over time, the cache accumulates stale entries for token pairs that were once queried.

**Impact:** LOW-MEDIUM. The primary unbounded growth is `LossTracker.trades`. At one trade per scan cycle (5s), that is 12 trades/minute, 720/hour, 17,280/day. Each `TradeResult` dataclass is ~200 bytes, so ~3.3 MB/day. Over weeks, this could grow to hundreds of MB.

**Detection:** The `MetricsCollector.collect_metrics()` method reads `psutil.Process.memory_info().rss` and exports it. An operator monitoring `metrics_latest.json` would see memory growth.

**Recommended Fix:**
- Call `LossTracker.reset_daily()` from the heartbeat or at the start of each day (check if `datetime.now().date() > last_reset_date`).
- Bound `LossTracker.trades` to a maximum size (e.g., 10,000 entries) with FIFO eviction.
- Add periodic cleanup for `PriceCache` -- iterate and remove expired entries every N minutes.

---

#### E2. Log File Fills Disk

**Trigger:** `run_bot.py` line 36 configures `logging.FileHandler('bot.log')` with no rotation. The log level is `INFO`. Every scan cycle generates multiple log lines. In debug mode (if someone changes the level), the volume increases dramatically.

The `emergency_shutdown.py` also writes to `emergency_shutdown.log` (line 253) with no rotation.

Approximate log volume at INFO level:
- Heartbeat: ~200 bytes/minute
- Per scan (no opportunity): ~500 bytes
- Per scan (with optimization): ~2-5 KB
- Per execution: ~1-2 KB
- At 12 scans/minute: ~6-60 KB/minute = ~360 KB - 3.6 MB/hour = ~8.6 - 86 MB/day

**Impact:** MEDIUM. Disk fills over days/weeks. When disk is full:
- Log writes fail silently (Python's FileHandler catches IOError)
- Database writes may fail (if on the same disk)
- Metrics JSON export fails
- The OS may become unstable

**Detection:** Disk usage monitoring (external to the bot). No in-bot disk usage checking.

**Recommended Fix:**
- Replace `FileHandler` with `RotatingFileHandler` or `TimedRotatingFileHandler`:
  ```python
  from logging.handlers import RotatingFileHandler
  RotatingFileHandler('bot.log', maxBytes=50*1024*1024, backupCount=5)
  ```
- This limits log storage to ~250 MB (5 * 50 MB).

---

#### E3. Thread Deadlock in Database Queue Mode

**Trigger:** In database queue mode (`DIRECT_EXECUTION=false`), `run_bot.py` creates two daemon threads (lines 238-239) that share:
1. The same `Web3` instance (via `self.web3`)
2. The same SQLAlchemy engine (via the module-level `engine` in database.py)
3. The same `risk_manager` instance
4. The same `metrics` instance

The `Web3.HTTPProvider` uses `requests.Session` internally, which is thread-safe. However, the `risk_manager` and `metrics` objects have no locks. Concurrent access to `LossTracker.trades.append()`, `CircuitBreaker.consecutive_losses`, `MetricsCollector.opportunities_found`, etc. from two threads creates race conditions.

Python's GIL prevents true parallel execution of Python bytecode, so simple attribute writes are atomic at the bytecode level. However, compound operations like `self.consecutive_losses += 1` (risk_manager.py line 457) are NOT atomic -- they involve a read, increment, and write. A thread switch between read and write could lose an update.

The `get_db()` context manager is thread-safe because each call creates a new session.

True deadlock is unlikely because there are no mutex locks in the codebase. But data races are certain.

**Impact:** LOW-MEDIUM. Data races on counters could cause minor inaccuracies (lost increments). The most concerning race is on `CircuitBreaker.is_active` -- if the detector thread reads `is_active=False` while the orchestrator thread is in the process of setting it to `True`, a trade could be approved that should have been blocked.

**Detection:** Race conditions are extremely difficult to detect from logs. Inconsistent counter values might be noticed in metrics.

**Recommended Fix:**
- Add `threading.Lock()` to `CircuitBreaker`, `LossTracker`, and `PositionManager` for all state mutations.
- Consider making the `risk_manager` thread-safe by serializing access through a queue.
- Or redesign to use `asyncio` consistently (the codebase mixes sync and async patterns).

---

#### E4. Python Process Killed by OOM Killer

**Trigger:** If the bot runs on a memory-constrained system (e.g., small VPS with 1 GB RAM), the combination of E1 (memory leak from `LossTracker.trades`), Python's memory overhead, and the `psutil` library's own memory usage could push the process past the cgroup memory limit.

**Current Behavior:** The Linux OOM killer sends SIGKILL to the process. No cleanup runs. All in-memory state is lost (see D1-D5). The process exits immediately.

**Impact:** HIGH (combines all state corruption scenarios D1-D5). On restart (assuming a process supervisor like systemd), the bot starts fresh with no memory of prior state.

**Detection:** `dmesg` or `journalctl` shows OOM killer events. The `bot.log` has no entry for the shutdown (SIGKILL is not catchable).

**Recommended Fix:**
- Set a memory limit alert at 80% of the system's available memory.
- Address the memory leak in E1.
- Use a process supervisor (systemd) with `Restart=on-failure` and `MemoryMax=` to prevent uncontrolled growth.
- Implement the state persistence recommended in D2-D4 so OOM-kill recovery is clean.

---

#### E5. Unbounded metrics_history Growth (Bounded but Large)

**Trigger:** `MetricsCollector.metrics_history` is capped at 1000 entries. Each `BotMetrics` dataclass contains 23 fields. When serialized for JSON export, the full history is written to disk every heartbeat (run_bot.py line 124: `self.metrics.export_metrics_json('metrics_latest.json')`).

At 1000 entries with ~500 bytes each serialized, that is ~500 KB of JSON written every 60 seconds. This is a significant I/O operation that runs synchronously on the main thread.

**Impact:** LOW. The I/O is brief (~50ms for 500 KB). But on systems with slow storage or high I/O contention, it could introduce jitter in the scan loop timing.

**Detection:** Detection time metrics would show occasional spikes.

**Recommended Fix:**
- Write only the latest metrics entry (not the full history) to `metrics_latest.json`.
- Write the full history less frequently (e.g., every 10 minutes) to a separate file.
- Use asynchronous file I/O or a background thread for metrics export.

---

### F. Clock / Timing Issues

---

#### F1. System Clock Drift Affecting Deadline Calculations

**Trigger:** The `build_transaction()` method at orchestrator line 271 sets `deadline = int(time.time()) + 300`. This uses the system clock. If the system clock drifts significantly from the blockchain's timestamp, the deadline may be incorrect:
- **Clock ahead**: The deadline is in the "future" relative to the blockchain, giving extra time. This is safe.
- **Clock behind**: The deadline may already be in the "past" relative to the blockchain. The transaction would revert immediately with "EXPIRED" because `block.timestamp > deadline`.

On most systems, NTP keeps the clock within ~100ms of real time. But VMs, containers, and systems that have been running for long periods without NTP sync can drift by seconds or minutes.

**Current Behavior:** No clock drift detection. A deadline that is already expired will cause the `eth_call` simulation to succeed (simulation typically evaluates at the current block, not future), but the real transaction will revert when mined in a block with `timestamp > deadline`.

Wait -- actually, if the system clock is behind, `time.time()` returns a value less than the blockchain's current time. So `deadline = time.time() + 300` could be, say, `blockchain_time - 5 + 300 = blockchain_time + 295`. This is still 295 seconds in the future, which is fine. Clock drift would need to exceed 300 seconds (5 minutes) to cause deadline issues. This is extremely unlikely.

**Impact:** LOW. NTP keeps clocks accurate to well within the 300-second deadline window.

**Detection:** Reverted transactions with "EXPIRED" error.

**Recommended Fix:**
- Use the blockchain's latest block timestamp instead of system time for deadline calculations: `deadline = latest_block['timestamp'] + 300`. The bot already fetches `latest_block` at line 286 for the base_fee.

---

#### F2. Check Interval Too Slow (Opportunity Expires Before Execution)

**Trigger:** The default `check_interval` is 5 seconds (from env var `CHECK_INTERVAL`). With the flash loan optimization, a single scan can take several seconds (up to 244 RPC calls at ~50-100ms each = 12-24 seconds). The total cycle time is `scan_time + execution_time + sleep(check_interval)`.

If a profitable opportunity is detected at time T, it takes `execution_time` (2-5 seconds for tx building + gas estimation + simulation) + network propagation time before the transaction is mined. Total latency from detection to on-chain execution: 7-30+ seconds.

On Polygon (2s block time), other arbitrage bots scanning every block will have a ~2 second advantage. On Arbitrum (0.25s block time), the disadvantage is even larger.

**Current Behavior:** The bot cannot compete with block-by-block scanning bots. Opportunities that appear and disappear within a few blocks will be missed entirely.

**Impact:** MEDIUM. The bot is structurally at a latency disadvantage. This is a design limitation, not a bug. The bot's profitability depends on finding opportunities with enough margin to survive the latency.

**Detection:** High ratio of "simulation passed but execution reverted" would indicate the bot is consistently too slow.

**Recommended Fix:**
- Use WebSocket RPC connections with `newHeads` subscriptions instead of polling.
- Pre-build transaction templates so only the amounts and deadline need to be updated.
- Reduce the number of RPC calls in the optimization phase (use fewer test amounts, cache recent quotes).
- Consider using a dedicated co-located server near the RPC node for lower latency.

---

#### F3. Heartbeat Logging Blocks the Scan Loop

**Trigger:** The `_heartbeat()` method (run_bot.py line 102-126) runs inline with the scan loop. It:
1. Calls `self.web3.eth.chain_id` (RPC call)
2. Calls `self.risk_manager.get_risk_metrics()` (in-memory, fast)
3. Calls `self.metrics.collect_metrics()` which calls `psutil.Process.cpu_percent(interval=0.1)` (blocks for 100ms)
4. Calls `self.metrics.export_metrics_json()` which writes to disk (synchronous I/O)

Total heartbeat overhead: ~150-500ms every 60 seconds.

**Impact:** LOW. The heartbeat runs at most once per minute. The overhead is small compared to the scan cycle time. But `psutil.cpu_percent(interval=0.1)` is a blocking call that sleeps for 100ms to measure CPU usage. During this 100ms, the scan loop is paused.

**Detection:** Detection time metrics would show a minor spike every 60 seconds.

**Recommended Fix:**
- Use `psutil.cpu_percent(interval=None)` for non-blocking measurement (returns instantaneous value since last call).
- Move metrics export to a background thread.
- Make the heartbeat non-blocking by deferring disk I/O.

---

#### F4. No Timeout on Individual RPC Calls During Scan

**Trigger:** The `get_v3_quote()` and `get_v2_quote()` methods call `.call()` on Web3 contract objects. Each call is a synchronous HTTP request to the RPC endpoint. As discussed in A6, there is no timeout configured on the `HTTPProvider`.

If a single quote call hangs, the ENTIRE scan is blocked. With up to 244 quote calls per scan, the probability of at least one hanging (over hours of operation) is non-trivial.

**Impact:** HIGH (same as A6, but during the scan phase rather than execution phase). The bot freezes mid-scan. No heartbeat, no progress.

**Detection:** Heartbeat stops. `metrics_latest.json` stops updating.

**Recommended Fix:** Same as A6 -- configure `request_kwargs={'timeout': 10}` on the `HTTPProvider`.

---

### G. Smart Contract / On-Chain Failures

---

#### G1. Contract Is Paused

**Trigger:** The contract owner calls `pause()` on the `FlashLoanArbitrageV2` contract. The bot's `execute_opportunity()` checks `self.contract.functions.paused().call()` at orchestrator line 340.

**Current Behavior:** If paused, raises `Exception("Contract is paused")`, caught at line 411. The execution is recorded as a failure. The circuit breaker increments consecutive_losses.

**Impact:** MEDIUM. Every execution attempt fails until the contract is unpaused. The circuit breaker will trigger after `MAX_CONSECUTIVE_LOSSES` attempts, which is the correct behavior. But the error message does not distinguish "paused" from other failures, which could confuse an operator.

**Detection:** `bot.log` shows "Contract is paused" errors. The circuit breaker triggers.

**Recommended Fix:**
- Check `paused()` at the START of the scan loop (not per-execution) and skip the entire scan if paused.
- Add a specific handling path for "paused" that does not increment the circuit breaker counter (it is an expected administrative state, not a trading failure).
- Log a distinct alert for contract paused state.

---

#### G2. Contract Ownership Transfer (Unauthorized Executor)

**Trigger:** The contract's `owner` changes (via `transferOwnership()`). The bot's executor address is no longer authorized.

**Current Behavior:** At orchestrator line 134-139, the contract owner is checked during initialization. If the executor is not the owner, a warning is logged. But execution continues -- the `executeArbitrage` function may not require owner permission (depending on the contract implementation). If it does require owner/authorized caller, all transactions will revert.

**Impact:** HIGH if the contract enforces caller authorization. All executions fail, gas is burned.

**Detection:** Initialization warning "Executor is not contract owner". Subsequent execution reverts.

**Recommended Fix:**
- Make the ownership check a hard failure (exit with error) rather than a warning.
- Periodically re-verify ownership during the scan loop.

---

#### G3. Adapter Deregistered On-Chain

**Trigger:** Someone calls `setAdapter(adapter, false)` on the contract, deregistering the V3 or V2 adapter. The bot continues to reference these adapters in `build_swap_steps()`.

**Current Behavior:** The swap steps reference the deregistered adapter. The on-chain execution reverts because the adapter is not authorized. Gas is burned.

**Impact:** MEDIUM. Same as G1 -- repeated failures until the adapter is re-registered.

**Detection:** Transaction reverts with an adapter-related error.

**Recommended Fix:**
- Periodically check adapter registration status.
- Cache the adapter status and refresh every N scan cycles.

---

### H. Configuration and Secrets Failures

---

#### H1. NATIVE_TOKEN_PRICE_USD Stale or Incorrect

**Trigger:** The `NATIVE_TOKEN_PRICE_USD` environment variable (used in opportunity_detector.py line 396 and orchestrator line 397) is set at startup and never updated. If the native token price changes significantly (MATIC drops from $0.80 to $0.30), the gas cost estimation is incorrect.

**Current Behavior:** Gas costs are overestimated (if price is too high) or underestimated (if price is too low). Overestimation causes profitable opportunities to be skipped. Underestimation causes unprofitable trades to be executed (gas cost exceeds profit).

**Impact:** MEDIUM. Incorrect gas cost estimation could lead to unprofitable executions.

**Detection:** Post-trade analysis shows actual gas costs differ significantly from estimates.

**Recommended Fix:**
- Fetch the native token price from an on-chain oracle (Chainlink) at the start of each scan cycle.
- Or use the RPC's `eth_gasPrice` and the pool prices to derive a real-time gas cost in USD terms.

---

#### H2. Private Key Exposed in Environment Variable

**Trigger:** The `PRIVATE_KEY` is loaded from an environment variable (run_bot.py line 322, config.py line 73). If the `.env` file is committed to version control, or the environment is inspected via `/proc/<pid>/environ`, the key is exposed.

**Current Behavior:** No encryption or secrets management. The private key is held in plaintext in Python memory for the lifetime of the process.

**Impact:** CRITICAL (if exposed). Full control of the wallet, including all funds.

**Detection:** Code review. Git history analysis. Process environment inspection.

**Recommended Fix:**
- Use a hardware wallet or KMS (AWS KMS, HashiCorp Vault) for key management.
- At minimum, use encrypted environment variables with a master key.
- Ensure `.env` is in `.gitignore`.
- Consider using `eth_account.signers.local.LocalAccount` with an encrypted keystore file.

---

#### H3. Database URL Contains Plaintext Password

**Trigger:** `DatabaseConfig.url` (config.py line 29) defaults to `postgresql://postgres:postgres@localhost:5432/arbitrage_bot`. If a production database URL with a real password is set via `DATABASE_URL` env var, it appears in plaintext in logs and error messages.

**Impact:** MEDIUM. Database credentials exposed could allow unauthorized access to trade data.

**Detection:** Grep logs and environment for database URLs with passwords.

**Recommended Fix:**
- Use `.pgpass` file or `PGPASSWORD` environment variable for PostgreSQL authentication.
- Mask sensitive portions of URLs in log output.

---

## 5. Failure Mode Matrix

| ID | Failure Scenario | Likelihood (1-5) | Impact (1-5) | Current Mitigation | Priority |
|----|-----------------|-------------------|---------------|-------------------|----------|
| **A1** | RPC returns stale data | 4 | 3 | None | **High** |
| **A2** | RPC error on eth_call, success on send | 2 | 2 | Partial (simulation gate) | Low |
| **A3** | RPC timeout during wait_for_receipt | 3 | 4 | Partial (120s timeout) | **Critical** |
| **A4** | RPC rate limits mid-scan | 4 | 2 | Partial (bare except returns None) | **Medium** |
| **A5** | RPC Byzantine fault (incorrect data) | 1 | 3 | Partial (minFinalAmount on-chain) | Low |
| **A6** | HTTPProvider has no timeout | 4 | 4 | None | **Critical** |
| **B1** | DB connection drops mid-write | 3 | 3 | Partial (rollback + silent catch) | **High** |
| **B2** | Database disk full | 2 | 3 | None | Medium |
| **B3** | Connection pool exhaustion | 2 | 3 | Partial (pool_pre_ping) | Medium |
| **B4** | Slow queries block main loop | 2 | 2 | None | Low |
| **C1** | Simulation passes but tx reverts | 4 | 4 | None (gas_cost_usd hardcoded to 0) | **Critical** |
| **C2** | Tx stuck in mempool (gas too low) | 3 | 3 | Partial (deadline protection) | **High** |
| **C3** | Tx mined but receipt never received | 2 | 4 | Partial (120s timeout) | **High** |
| **C4** | Nonce gap from failed tx | 3 | 5 | None | **Critical** |
| **C5** | Double-send due to retry logic | 1 | 4 | Adequate (no retry in orchestrator) | Low |
| **D1** | Crash between send_raw_tx and DB write | 3 | 5 | None | **Critical** |
| **D1a** | _log_execution never called in direct mode | 5 | 4 | None | **Critical** |
| **D2** | Circuit breaker state lost on restart | 4 | 5 | None | **Critical** |
| **D3** | Metrics counters reset on restart | 4 | 2 | Partial (metrics_latest.json) | Low |
| **D4** | Risk manager daily P&L lost on restart | 4 | 5 | None | **Critical** |
| **D5** | Position manager state lost on restart | 4 | 1 | N/A (flash loans are atomic) | Low |
| **D6** | BalanceValidator reserved balances leak | 1 | 1 | N/A (not used in current path) | Low |
| **E1** | Memory leak (LossTracker.trades unbounded) | 4 | 2 | None (reset_daily never called) | Medium |
| **E2** | Log file fills disk | 3 | 3 | None (no rotation) | **High** |
| **E3** | Thread deadlock / data race in queue mode | 3 | 3 | None (no locks) | **High** |
| **E4** | OOM killer terminates process | 2 | 5 | None | **High** |
| **E5** | metrics_history I/O overhead | 2 | 1 | Partial (capped at 1000) | Low |
| **F1** | System clock drift vs. deadline | 1 | 2 | Partial (300s window) | Low |
| **F2** | Check interval too slow for competition | 5 | 3 | None (design limitation) | Medium |
| **F3** | Heartbeat blocks scan loop (100ms) | 4 | 1 | None | Low |
| **F4** | No timeout on individual RPC calls | 4 | 4 | None | **Critical** |
| **G1** | Contract is paused | 2 | 3 | Partial (check before execution) | Medium |
| **G2** | Contract ownership transfer | 1 | 4 | Partial (startup warning) | Medium |
| **G3** | Adapter deregistered on-chain | 1 | 3 | None | Low |
| **H1** | NATIVE_TOKEN_PRICE_USD stale | 4 | 3 | None | **High** |
| **H2** | Private key in env var plaintext | 3 | 5 | None | **Critical** |
| **H3** | DB password in plaintext URL | 3 | 3 | None | Medium |

### Priority Summary

| Priority | Scenarios | Risk Score (L*I) |
|----------|-----------|-----------------|
| **Critical** | A3, A6, C1, C4, D1, D1a, D2, D4, F4, H2 | 12-25 |
| **High** | A1, B1, C2, C3, E2, E3, E4, H1 | 9-12 |
| **Medium** | A4, B2, B3, E1, F2, G1, G2, H3 | 4-8 |
| **Low** | A2, A5, B4, C5, D3, D5, D6, E5, F1, F3, G3 | 1-4 |

---

## 6. Critical Path Analysis

The most dangerous sequence of failures that could cause fund loss:

```
1. RPC serves stale data (A1)
   |
   v
2. Bot detects phantom opportunity (false positive)
   |
   v
3. gas_cost_usd is hardcoded to 0 (C1 sub-finding)
   |
   v
4. Risk manager approves trade (no real gas cost check)
   |
   v
5. eth_call simulation passes against stale state (A1)
   |
   v
6. Transaction is broadcast (real nonce consumed)
   |
   v
7. Transaction reverts on-chain (prices moved)
   |
   Gas is burned (~$0.05-0.50 per reverted tx on Polygon)
   |
   v
8. Bot records failure, but with gas_cost=0 in risk manager
   |
   v
9. Daily loss limit is never triggered (D4: gas losses invisible)
   |
   v
10. Bot repeats steps 1-9 indefinitely
    |
    v
11. After 5 consecutive reverts, circuit breaker triggers (60 min cooldown)
    |
    v
12. After cooldown, bot resumes and repeats the cycle
    |
    v
13. If bot is restarted during cooldown, circuit breaker resets (D2)
    |
    v
14. Cycle restarts with no protection
```

**Total gas drain rate**: At 12 scans/minute, if every scan finds and executes a phantom opportunity: 12 reverted txs/minute * $0.10/tx = $1.20/minute = $72/hour = **$1,728/day in pure gas losses**, completely invisible to the risk manager.

In practice, not every scan would find a false positive, but the analysis shows the MECHANISM exists for undetected capital drain.

---

## 7. Recommended Remediation Roadmap

### Phase 1: CRITICAL (Implement Immediately)

1. **Fix gas cost tracking** (C1): Remove `gas_cost_usd = Decimal('0')` hardcoding. Calculate actual gas costs from receipts and feed to risk manager.

2. **Persist risk state** (D2, D4): Write circuit breaker state and daily P&L to a file or database on every state change. Load on startup.

3. **Pass opportunity_id to orchestrator** (D1a): In `run_bot.py`, pass the opportunity's database ID to `execute_opportunity()` so execution results are recorded.

4. **Write tx_hash to DB before waiting for receipt** (D1, A3, C3): After `send_raw_transaction`, immediately persist the tx_hash with status `SUBMITTED`. Update to `CONFIRMED` or `FAILED` after receipt.

5. **Add HTTP timeout to Web3 provider** (A6, F4): `Web3(Web3.HTTPProvider(rpc_url, request_kwargs={'timeout': 30}))`.

6. **Nonce recovery** (C4): After any "nonce too high" error, fetch `get_transaction_count(address, 'latest')` and reset.

7. **Secrets management** (H2): Move private key to encrypted keystore or KMS. Never store in plaintext env vars for production.

### Phase 2: HIGH (Implement Within 1 Week)

8. **RPC staleness detection** (A1): Compare block numbers across scan cycles. Skip scan if block has not advanced.

9. **Log rotation** (E2): Replace `FileHandler` with `RotatingFileHandler(maxBytes=50MB, backupCount=5)`.

10. **Thread safety** (E3): Add locks to `CircuitBreaker`, `LossTracker`, and `MetricsCollector`.

11. **RPC rate limit backoff** (A4): If >50% of RPC calls fail in a cycle, double the check_interval temporarily.

12. **DB write retry** (B1): Add 3-attempt retry with 1s backoff for `_log_execution()`.

13. **Startup reconciliation** (A3, C3): On startup, query for `SUBMITTED` transactions and reconcile against on-chain state.

14. **Native token price oracle** (H1): Fetch MATIC/ETH price from on-chain oracle at the start of each scan.

15. **OOM protection** (E4): Bound `LossTracker.trades` to 10,000 entries. Call `reset_daily()` periodically.

### Phase 3: MEDIUM (Implement Within 1 Month)

16. **Contract pause awareness** (G1): Check `paused()` once per scan, not per execution.
17. **Multiple RPC endpoints** (A1, A4): Implement failover/load-balancing across 2+ RPC providers.
18. **Transaction speed-up** (C2): Re-broadcast stuck transactions with higher gas price.
19. **Memory leak remediation** (E1): Periodic `PriceCache` cleanup.
20. **Database retention policies** (B2): Auto-archive old records.
21. **WebSocket subscriptions** (F2): Replace polling with event-driven detection.

### Phase 4: LOW (Backlog)

22. **Background metrics export** (E5, F3): Move I/O off the main thread.
23. **Cross-RPC validation** (A5): Verify quotes against secondary endpoint.
24. **Adapter status check** (G3): Periodic verification.
25. **Position manager cleanup** (D5, D6): Fix phantom position tracking.

---

## 8. Appendix: Files Analyzed

| File | Absolute Path | Lines | Key Concerns |
|------|--------------|-------|-------------|
| run_bot.py | `/Users/ethanallen/Desktop/ARBITRAGE/arb_bot_cryp_eea/run_bot.py` | 409 | No timeout on Web3 provider; gas_cost_usd hardcoded to 0; opportunity_id not passed to orchestrator; heartbeat blocks main loop |
| opportunity_detector.py | `/Users/ethanallen/Desktop/ARBITRAGE/arb_bot_cryp_eea/src/opportunity_detector.py` | 697 | Up to 244 RPC calls per scan; bare except on quotes; NATIVE_TOKEN_PRICE_USD stale; log_opportunity() silently fails |
| flash_loan_orchestrator.py | `/Users/ethanallen/Desktop/ARBITRAGE/arb_bot_cryp_eea/src/flash_loan_orchestrator.py` | 630 | No retry on broadcast; tx_hash not persisted before receipt wait; _log_execution silently catches DB errors; 120s receipt timeout |
| risk_manager.py | `/Users/ethanallen/Desktop/ARBITRAGE/arb_bot_cryp_eea/src/utils/risk_manager.py` | 710 | All state in-memory; no persistence; reset_daily() never called; no thread safety; BalanceValidator async but never used |
| metrics_collector.py | `/Users/ethanallen/Desktop/ARBITRAGE/arb_bot_cryp_eea/src/utils/metrics_collector.py` | 333 | metrics_history capped at 1000; profits/losses/gas_costs unbounded; psutil blocks for 100ms |
| gas_optimizer.py | `/Users/ethanallen/Desktop/ARBITRAGE/arb_bot_cryp_eea/src/utils/gas_optimizer.py` | 170 | Fallback to 30 gwei on error; not used by main orchestrator |
| emergency_shutdown.py | `/Users/ethanallen/Desktop/ARBITRAGE/arb_bot_cryp_eea/src/utils/emergency_shutdown.py` | 445 | async trigger_emergency_shutdown never called from sync code; shutdown_history unbounded; log file not rotated |
| database.py | `/Users/ethanallen/Desktop/ARBITRAGE/arb_bot_cryp_eea/src/db/database.py` | 136 | pool_pre_ping=True (good); no pool_timeout; get_db_session() leak risk; SQLite pragma for testing but using PostgreSQL |
| models.py | `/Users/ethanallen/Desktop/ARBITRAGE/arb_bot_cryp_eea/src/db/models.py` | 339 | JSONB columns unbounded; execution_log grows without retention; proper indexes defined |
| config.py | `/Users/ethanallen/Desktop/ARBITRAGE/arb_bot_cryp_eea/src/config.py` | 185 | Passwords in plaintext; class-level defaults evaluated at import time; singleton pattern |
| transaction_manager.py | `/Users/ethanallen/Desktop/ARBITRAGE/arb_bot_cryp_eea/src/utils/transaction_manager.py` | 332 | Not used by main orchestrator; has retry logic with nonce tracking; asyncio Lock for nonce |
| performance_monitor.py | `/Users/ethanallen/Desktop/ARBITRAGE/arb_bot_cryp_eea/src/utils/performance_monitor.py` | 202 | RPC call counter resets every 60s; psutil fallback; not integrated in main path |
| slippage_protection.py | `/Users/ethanallen/Desktop/ARBITRAGE/arb_bot_cryp_eea/src/utils/slippage_protection.py` | 338 | Not integrated in main path; comprehensive but unused |
| price_cache.py | `/Users/ethanallen/Desktop/ARBITRAGE/arb_bot_cryp_eea/src/utils/price_cache.py` | 119 | Async-only; stale entries not cleaned up; not used in detector |
| flash_loan/contract_interface.py | `/Users/ethanallen/Desktop/ARBITRAGE/arb_bot_cryp_eea/src/flash_loan/contract_interface.py` | 326 | Separate interface not used by orchestrator; no timeout on wait_for_receipt |
| dex/base.py | `/Users/ethanallen/Desktop/ARBITRAGE/arb_bot_cryp_eea/src/dex/base.py` | 212 | Abstract base; async-only; not used in main path |
| bot/main.py | `/Users/ethanallen/Desktop/ARBITRAGE/arb_bot_cryp_eea/src/bot/main.py` | 626 | Alternative bot architecture (async); not the primary entry point; execution not implemented |

---

*End of Report*

*This analysis was performed by static code review without runtime testing. Production deployment should include dynamic fault injection testing to validate the findings.*
