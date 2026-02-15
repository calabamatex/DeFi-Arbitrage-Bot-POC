# Technical Architecture Review Report

**Agent Role:** Technical Architect
**Date:** 2026-02-11
**Scope:** Full architectural review across 8 analysis areas

---

## Executive Summary

1. **Sequential RPC calls** in the hot path make the bot 50-200x slower than competitors using Multicall3 or concurrent requests.
2. **Private keys committed in plaintext** in `.env.arbitrum` and `MULTI_CHAIN_DEPLOYMENT_GUIDE.md`.
3. **Two parallel, disconnected DEX abstraction layers** -- one async (unused), one inline (used).
4. **No pre-execution simulation** -- transactions sent blind without `eth_call` or Tenderly.
5. **Multi-chain is documentation-only** -- all runtime code hardcodes `chain_id=137` and Polygon addresses.
6. **ORM models diverge from DATABASE_SCHEMA.md** and orchestrator passes incompatible types.

**Verdict:** Solid proof-of-concept requiring significant refactoring before mainnet deployment with real capital.

---

## Architecture Diagram

```
+-------------------------------------------------------------------+
|                        ENTRY POINTS                                |
|   run_bot.py (ArbitrageBot)   |   run_bot_arbitrum.py             |
+-------------------------------------------------------------------+
         |                                    |
         v                                    v
+---------------------------+    +---------------------------+
| OpportunityDetector       |    | FlashLoanOrchestrator     |
| src/opportunity_detector  |    | src/flash_loan_orchestr.. |
|                           |    |                           |
| - get_v3_quote()     [S]  |    | - build_swap_steps()      |
| - get_v2_quote()     [S]  |    | - build_transaction()     |
| - find_best_v3_fee() [S]  |    | - execute_opportunity()   |
| - calculate_arbitrage()   |    | - monitor_opportunities() |
| - scan_opportunities()    |    |                           |
+---------------------------+    +---------------------------+
         |                                    |
         v                                    v
+---------------------------+    +---------------------------+
| Database Layer             |    | Blockchain (Web3)        |
| src/db/database.py        |    | Polygon RPC (HTTP)        |
| src/db/models.py          |    | chain_id=137 hardcoded    |
+---------------------------+    +---------------------------+
                                              |
                                              v
+-------------------------------------------------------------------+
| SMART CONTRACTS (Solidity)                                         |
| FlashLoanArbitrageV2.sol  <-- ACTIVE (adapter pattern)             |
|   UniswapV3AdapterFixed   <-- DEPLOYED (fee=500 hardcoded)         |
|   UniswapV2Adapter        <-- DEPLOYED                             |
+-------------------------------------------------------------------+

+-------------------------------------------------------------------+
| DISCONNECTED SUBSYSTEMS (not wired into hot path)                  |
| src/dex/base.py         - Async DEX ABC (NEVER USED)              |
| src/utils/multicall.py  - Multicall3 wrapper (NEVER IMPORTED)     |
| src/utils/gas_optimizer.py - EIP-1559 gas (NEVER IMPORTED)        |
| src/utils/risk_manager.py  - Risk mgmt (NEVER IN HOT PATH)       |
| src/config.py           - ChainConfig registry (NEVER CONSUMED)   |
+-------------------------------------------------------------------+

[S] = Sequential synchronous RPC call (performance bottleneck)
```

---

## Area 1: Detection Pipeline (CRITICAL)

**File:** `src/opportunity_detector.py` (682 lines)

| # | Severity | Finding | Location |
|---|----------|---------|----------|
| 1.1 | CRITICAL | Sequential RPC calls: 3 calls per fee tier test | Lines 255-259 |
| 1.2 | CRITICAL | No concurrent scanning across 4 pairs | Lines 571-608 |
| 1.3 | HIGH | Hardcoded MATIC price ($0.80) | Line 394 |
| 1.4 | HIGH | Hardcoded chain_id=137 | Line 534 |

**Performance Impact:**
```
4 pairs x 2 directions x 15 iterations x 4 calls = 480 RPC calls
At 100ms each = 48 SECONDS per scan cycle
Competitors using Multicall3: ~200ms total (50-200x faster)
```

**Fix:** `src/utils/multicall.py` already exists but is never imported. Use it.

---

## Area 2: Execution Pipeline (CRITICAL)

**File:** `src/flash_loan_orchestrator.py` (583 lines)

| # | Severity | Finding | Location |
|---|----------|---------|----------|
| 2.1 | CRITICAL | No pre-execution simulation (eth_call or Tenderly) | Lines 328-395 |
| 2.2 | CRITICAL | First swap step has minAmountOut=0 | Lines 191-197 |
| 2.3 | HIGH | Incorrect EIP-1559 maxFeePerGas | Line 288 |
| 2.4 | HIGH | Naive nonce management | Line 286 |
| 2.5 | HIGH | Blocking wait_for_transaction_receipt (120s) | Line 358 |

**Fix:** Add `self.web3.eth.call(transaction)` before every `send_raw_transaction()`. Use `gas_optimizer.py` (already built, not imported).

---

## Area 3: Smart Contract Architecture (HIGH)

| # | Severity | Finding | Location |
|---|----------|---------|----------|
| 3.1 | HIGH | UniswapV3AdapterFixed hardcodes fee=500 (0.05% only) | UniswapV3AdapterFixed.sol:33 |
| 3.2 | HIGH | IDEXAdapter interface mismatch (6 vs 7 params) | V3Adapter vs V2 contract |
| 3.3 | MEDIUM | ArbitrageExecuted emits cumulative totalProfits, not per-trade | FlashLoanArbitrageV2.sol:173 |

**Strength:** V2 contract has proper security: onlyOwner, nonReentrant, whenNotPaused, adapter registration.

---

## Area 4: Data Architecture (HIGH)

| # | Severity | Finding | Location |
|---|----------|---------|----------|
| 4.1 | HIGH | ORM models diverge from DATABASE_SCHEMA.md | models.py vs schema |
| 4.2 | HIGH | Transaction.opportunity_id is Integer FK but orchestrator passes string | models.py:119 |
| 4.3 | MEDIUM | get_db() auto-commits (dangerous for read-only) | database.py:55-56 |

---

## Area 5: Multi-Chain Readiness (CRITICAL)

- `.env.arbitrum` contains private key committed to git
- ChainConfig in `config.py` is never consumed by detector/orchestrator
- All runtime code hardcodes `chain_id=137` and Polygon addresses
- QuickSwap router address doesn't exist on Arbitrum

---

## Area 6: Dependencies (HIGH)

`requirements.txt` missing `sqlalchemy`, `psycopg2-binary`, `eth-account`. Fresh install would fail.

---

## Area 7: Code Quality (HIGH)

Two disconnected DEX abstraction layers: `src/dex/` (async, better design, UNUSED) vs inline calls in `opportunity_detector.py` (sync, in hot path). `quickswap.py` and `sushiswap.py` are 99% copy-paste.

Risk manager (714 lines, excellent design) is completely isolated from hot path.

---

## Area 8: Performance (CRITICAL)

| Operation | Current | Target | Improvement |
|-----------|---------|--------|-------------|
| Price quotes (4 pairs) | 1.6-6.4s | 100-200ms | 16-32x via Multicall3 |
| Optimal amount search | 6-48s | 500ms-1s | 12-48x via batch + binary search |
| Full scan cycle | 10-55s | 1-2s | 10-55x |

---

## Severity Summary

| Severity | Count | Key Issues |
|----------|-------|------------|
| CRITICAL | 6 | Sequential RPC, private keys, no simulation, minAmountOut=0 |
| HIGH | 10 | Interface mismatch, hardcoded values, incomplete deps, dual DEX layers |
| MEDIUM | 12 | Token custody, auto-commit, copy-paste, ABI duplication |

---

## Prioritized Technical Roadmap

### Phase 1: Security (Week 1) -- MANDATORY
1. Rotate all exposed private keys
2. Update `.gitignore`
3. Add minAmountOut calculation for first swap step
4. Add `eth_call` simulation before every transaction

### Phase 2: Performance (Weeks 2-3)
1. Integrate Multicall3 for batch price quotes
2. Switch to WebSocket provider
3. Implement asyncio for concurrent scanning
4. Replace doubling search with binary search

### Phase 3: Architecture Cleanup (Weeks 3-4)
1. Merge DEX abstraction layers -- use `src/dex/` async adapters
2. Wire RiskManager into FlashLoanOrchestrator
3. Wire GasOptimizer (EIP-1559) into orchestrator
4. Fix ORM/schema divergence -- add Alembic migrations

### Phase 4: Smart Contract (Weeks 4-5)
1. Redesign V3 adapter to decode fee from `bytes data`
2. Remove dead contracts (V1, DEXLibrary)
3. Deploy updated adapter supporting all fee tiers

### Phase 5: Multi-Chain (Weeks 5-8)
1. Implement chain-aware detector and orchestrator using ChainConfig
2. Deploy to Arbitrum, Optimism, Base
3. Per-chain token registries and gas strategies

---

## File Inventory

| File | Lines | Status | Notes |
|------|-------|--------|-------|
| `src/opportunity_detector.py` | 682 | ACTIVE | Hot path, needs Multicall3 |
| `src/flash_loan_orchestrator.py` | 583 | ACTIVE | Needs simulation, risk mgmt |
| `src/config.py` | 185 | UNUSED | Good design, needs integration |
| `src/utils/multicall.py` | 203 | UNUSED | Solution to perf problem |
| `src/utils/gas_optimizer.py` | 170 | UNUSED | Has correct EIP-1559 |
| `src/utils/risk_manager.py` | 714 | PARALLEL | Excellent, not in hot path |
| `contracts/FlashLoanArbitrageV2.sol` | 343 | DEPLOYED | Strong security |
| `contracts/FlashLoanArbitrage.sol` | 416 | DEAD | Always reverts |
| `contracts/adapters/UniswapV3AdapterFixed.sol` | 70 | DEPLOYED | fee=500 only |

---

*Report generated by Technical Architect agent.*
