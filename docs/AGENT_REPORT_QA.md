# QA Functional Validation Report: Crypto Arbitrage Bot

**Agent Role:** QA Tester
**Date:** 2026-02-11
**Verdict:** Would NOT trust this with real money. 9 Critical bugs, 8 High bugs found.

---

## Executive Summary

1. **The entire database layer is broken.** The orchestrator references enum values (`OpportunityStatus.PROCESSING`, `TransactionStatus.SUCCESS`) that don't exist, uses wrong column names, and misses NOT NULL fields. Every DB write in the execution path will crash.

2. **The V3 fee optimization is disconnected from execution.** Python selects best fee tier (500/3000/10000), but the deployed Solidity adapter hardcodes `FEE=500` and ignores the `data` field entirely.

3. **Token decimal handling is wrong for non-USDC pairs.** All trading pairs hardcode `token_decimals=6`. For WMATIC/WETH/DAI (18 decimals), amounts are 10^12x too small.

4. **Arbitrum deployment is inoperable.** QuickSwap router doesn't exist on Arbitrum, WMATIC token doesn't exist, chain_id hardcoded to 137.

5. **First swap has minAmountOut=0** -- no sandwich attack protection on intermediate swap.

---

## Critical Bugs (Would cause immediate failure or fund loss)

| # | Bug | File:Line | Impact |
|---|---|---|---|
| C1 | Private keys committed to repo | `.env.arbitrum:22`, `.env.bak:2` | Wallet compromise |
| C2 | `OpportunityStatus.PROCESSING` doesn't exist | `flash_loan_orchestrator.py:531` | `AttributeError` on every pickup |
| C3 | `TransactionStatus.SUCCESS` doesn't exist | `flash_loan_orchestrator.py:430` | `AttributeError` on every log |
| C4 | Transaction model uses wrong columns, misses NOT NULL | `flash_loan_orchestrator.py:426-433` | `IntegrityError` on every insert |
| C5 | TradeResult model uses completely wrong columns | `flash_loan_orchestrator.py:438-448` | `TypeError` on every insert |
| C6 | ExecutionLog model uses wrong columns | `flash_loan_orchestrator.py:452-460` | `TypeError` on every insert |
| C7 | Opportunity missing required `expected_amount_out` | `opportunity_detector.py:532-547` | `IntegrityError` on insert |
| C8 | opportunity_id FK type mismatch (string vs integer) | `flash_loan_orchestrator.py:428` | FK constraint violation |
| C9 | V3 adapter ignores fee tier -- always uses 0.05% | `UniswapV3AdapterFixed.sol:33` | Wrong pool, potential losses |

---

## High Bugs (Incorrect behavior or significant risk)

| # | Bug | File:Line | Impact |
|---|---|---|---|
| H1 | QuickSwap Router doesn't exist on Arbitrum | `opportunity_detector.py:83` | All V2 quotes fail on Arbitrum |
| H2 | WMATIC address used on Arbitrum (doesn't exist) | `opportunity_detector.py:91` | 2/4 pairs always fail |
| H3 | token_decimals=6 hardcoded for 18-decimal tokens | `opportunity_detector.py:583,600` | Wrong profit calculations |
| H4 | minAmountOut=0 on first swap step | `flash_loan_orchestrator.py:195` | No sandwich protection |
| H5 | Nonce collision on multiple opportunities | `flash_loan_orchestrator.py:286` | Second tx fails |
| H6 | Chain ID hardcoded to 137 | `flash_loan_orchestrator.py:429,441,454` | Wrong chain in DB on Arbitrum |
| H7 | Gas cost assumes MATIC ($0.80) even on Arbitrum (ETH) | `opportunity_detector.py:394` | Gas underestimated ~2000x |
| H8 | Stale quotes: 5-15 second delay quote-to-execution | `opportunity_detector.py:570-610` | Spread gone at execution |

---

## Decimal & Math Validation

| Token | Actual Decimals | Code Assumption | Correct? |
|---|---|---|---|
| USDC | 6 | 6 | OK |
| USDT | 6 | 6 | OK |
| DAI | 18 | 6 | **WRONG** |
| WMATIC | 18 | 6 | **WRONG** |
| WETH | 18 | 6 | **WRONG** |

For WMATIC/WETH pair: flash loan amount_in = `500 * 10**6` = 0.0000000000005 WMATIC (~$0). Should be `500 * 10**18`.

---

## Cross-File Consistency Issues

| # | Issue | Severity |
|---|-------|----------|
| 8.1 | `OpportunityStatus.PROCESSING` not in enum (should be `EXECUTING`) | CRITICAL |
| 8.2 | `TransactionStatus.SUCCESS` not in enum (should be `CONFIRMED`) | CRITICAL |
| 8.3 | Transaction model: `gas_price` column is actually `gas_price_gwei` | CRITICAL |
| 8.4 | TradeResult: `profit`, `tx_hash`, `chain_id` don't exist in model | CRITICAL |
| 8.5 | ExecutionLog: `status`, `tx_hash`, `gas_used` don't exist in model | CRITICAL |
| 8.6 | `rawTransaction` vs `raw_transaction` (deprecated in web3.py v6+) | MEDIUM |
| 8.7 | Chain ID hardcoded to 137 in 4 places | HIGH |
| 8.8 | Polygon QuickSwap router used on Arbitrum | HIGH |

---

## Race Conditions & Timing Risks

**6.1 Stale Quotes:** 5-15 second delay between first quote and execution. Price moves in milliseconds.

**6.2 Nonce Conflicts:** Sequential execution in loop, but nonce fetched per-tx. If first tx hasn't confirmed when second starts, duplicate nonce.

**6.3 Database State:** `get_db()` auto-commit interacts poorly with manual commits in orchestrator. Partial commits possible on failure.

**6.4 Block Reorgs:** Zero handling. Confirmed tx that gets reorged = wrong profit tracking.

---

## "Would I Trust This With Real Money?"

**Absolutely not.** Required conditions:

- [ ] Generate new private key, NEVER commit to repo
- [ ] Fix all enum values
- [ ] Fix all database model column mappings
- [ ] Make V3 adapter fee configurable
- [ ] Make token addresses chain-aware
- [ ] Make token_decimals dynamic
- [ ] Set minAmountOut > 0 on intermediate swaps
- [ ] Add nonce management
- [ ] Fix chain_id to be dynamic
- [ ] Run fork/testnet dry-run for 1+ week
- [ ] Get smart contracts audited
- [ ] Wire circuit breaker into execution path

---

*Report generated by QA Tester agent.*
