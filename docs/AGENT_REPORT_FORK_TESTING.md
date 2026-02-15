# Fork Testing / Integration Testing Agent Report

**Date:** 2026-02-12
**Agent Role:** Fork Testing / Integration Testing Specialist
**Scope:** Test infrastructure analysis, coverage gap identification, and integration test plan for the flash loan arbitrage bot

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current Test Infrastructure Inventory](#current-test-infrastructure-inventory)
3. [Test Coverage Gap Analysis](#a-test-coverage-gap-analysis)
4. [Integration Test Plan](#b-integration-test-plan)
5. [Recommended Test Suite](#c-recommended-test-suite)
6. [CI Pipeline Integration](#d-ci-pipeline-integration)
7. [Priority Matrix and Implementation Roadmap](#priority-matrix-and-implementation-roadmap)

---

## Executive Summary

The project has a solid unit test suite (~97 tests across 17 test files) with strong coverage of business logic using mocks. However, there is a **critical gap** between these mocked unit tests and real-world execution. The two existing fork test scripts (`manual_execution_test.py`, `execute_profitable_arbitrage.py`) prove the concept works against a local Anvil fork but are not automated, not in CI, not repeatable at a pinned block, and have no assertions beyond transaction status.

The most dangerous blind spot is: **every on-chain interaction is mocked in the test suite**. The detector, orchestrator, and risk manager all use `Mock()` or `MagicMock()` for `Web3`, contract calls, and transaction receipts. This means the following failure modes are completely invisible to the current test suite:

- ABI encoding mismatches between Python and Solidity
- Incorrect contract call parameters that would revert on-chain
- Flash loan repayment arithmetic errors
- Slippage tolerance values that are too tight or too loose for real pool state
- Gas estimation accuracy on real transaction data
- Database records that drift from on-chain reality
- Race conditions between detection and execution against changing pool state

---

## Current Test Infrastructure Inventory

### Test Directories and Configuration

| Location | Contents | Framework |
|----------|----------|-----------|
| `tests/` | 13 test files (root-level) | pytest, pytest-asyncio |
| `tests/unit/` | 4 test files (DEX adapters) | pytest |
| `tests/integration/` | 1 test file (Mumbai testnet, skip-by-default) | pytest |
| `test/contracts/` | 1 Foundry test file (Solidity) | Forge |
| Root directory | 2 one-off fork scripts | standalone Python |

### pytest Configuration

From `pyproject.toml`:
- Test paths: `["test", "tests"]`
- Coverage target: 80% on `src/`
- Markers defined: `slow`, `integration`, `e2e`, `unit`
- Coverage reports: HTML + terminal

From `pytest.ini`:
- Additional marker: `testnet`
- `asyncio_mode = auto`

### Existing Test Files -- Detailed Breakdown

#### Root `tests/` directory (mocked unit tests)

| File | Tests | What It Covers | Mock Level |
|------|-------|----------------|------------|
| `test_security.py` | 5 | Secret scanning, gitignore validation, no hardcoded keys | Filesystem scan (no mocks needed) |
| `test_risk_manager.py` | 14 | BalanceValidator, PositionManager, LossTracker, CircuitBreaker, RiskManager | All Web3 calls mocked |
| `test_config.py` | 16 | Config loading, env vars, RPC validation, ERC20 ABI | File I/O and Web3 mocked |
| `test_emergency_shutdown.py` | 21 | Shutdown triggers, conditions, reset, history, monitoring | Telegram mocked |
| `test_metrics_collector.py` | 11 | Opportunity recording, trade recording, JSON/Prometheus export | Pure logic (minimal mocks) |
| `test_arbitrage.py` | 18 | ArbitrageOpportunity dataclass, calculate_arbitrage, gas cost, profitability, execution | All DEX prices mocked via `AsyncMock` |
| `test_main.py` | 13 | Bot initialization, shutdown, opportunity processing, execution flow | Everything mocked (config, Web3, DEXes, Telegram, RiskManager) |
| `test_slippage_protection.py` | 16 | Min output calculation, price validation, impact estimation, budget analysis | Pure math (no mocks needed) |
| `test_transaction_manager.py` | 18 | Nonce management, tx building, signing, sending, simulation, gas estimation | Web3 fully mocked |
| `test_dex_factory.py` | 10 | DEX factory creates correct instances with correct addresses | No chain interaction |
| `test_performance.py` | ~20 | PriceCache, GasOptimizer, PerformanceMonitor, Multicall | Web3 mocked |
| `test_telegram_bot.py` | (not read) | Telegram integration | Likely mocked |
| `test_opportunity_scorer.py` | (not read) | Opportunity scoring logic | Likely mocked |

#### `tests/unit/` directory

| File | Tests | What It Covers | Mock Level |
|------|-------|----------------|------------|
| `test_dex_base.py` | 16 | DEX abstract class, contract init, concurrent price fetching | Web3 mocked |
| `test_uniswap_v3.py` | 20 | UniswapV3 adapter: pricing, fee tier selection, trade execution, liquidity depth | All contract calls mocked |
| `test_quickswap.py` | 14 | QuickSwap adapter: pricing, path building, trade execution | All contract calls mocked |
| `test_sushiswap.py` | (similar) | SushiSwap adapter | All contract calls mocked |

#### `tests/integration/test_full_system.py`

This file targets Mumbai testnet and is gated behind `--testnet`. It tests:
- RPC connection (chain ID == 80001)
- Account balance check
- DEX initialization
- Real price fetching (with tolerance for zero liquidity)
- Placeholder arbitrage detection
- Telegram notifications
- Trade execution (always skipped)
- Bot initialization
- One-hour run (always skipped)

**Problem:** Mumbai testnet was deprecated in April 2024. These tests are effectively dead code targeting a non-existent network.

#### `test/contracts/FlashLoanArbitrage.t.sol` (Foundry)

Tests the **V1** FlashLoanArbitrage contract (not V2):
- Deployment verification
- DEX whitelist management
- Min profit / max slippage setters
- Pause/unpause
- Flash loan fee calculation
- Emergency withdrawer management
- Cannot execute when paused / deadline expired

**Problem:** This tests V1, but the deployed contract used by the Python bot is `FlashLoanArbitrageV2.sol`. The V2 contract uses a completely different interface (adapter pattern with `SwapStep[]` and `ArbitrageParams`). There are **zero Foundry tests for the V2 contract**.

#### One-Off Fork Scripts (not in test suite)

**`manual_execution_test.py`:**
- Connects to `localhost:8545` (Anvil)
- Uses Anvil default account #0
- Hardcodes contract addresses from a specific deployment
- Builds a USDC -> WMATIC -> USDC arbitrage via V3 then V2
- Submits real transaction, checks receipt status
- No pytest assertions, no CI integration, no cleanup

**`execute_profitable_arbitrage.py`:**
- Same Anvil setup
- Specifically targets a known price discrepancy
- Flash loans 1300 USDC from Aave V3
- Buys WMATIC on Uniswap V3, sells on QuickSwap
- Checks contract USDC balance before/after to measure profit
- No pytest assertions, no CI integration

---

## A. Test Coverage Gap Analysis

### What Is Well-Tested (with mocks)

1. **Risk management logic** -- BalanceValidator, PositionManager, LossTracker, CircuitBreaker, and the coordinating RiskManager all have thorough unit tests covering normal paths, edge cases, and error conditions.

2. **Configuration management** -- Config loading from JSON, environment variable validation, private key format checking, RPC connection validation (mocked), and defaults are well covered.

3. **Emergency shutdown system** -- Trigger registration, condition checking, shutdown/reset flow, history tracking, and Telegram notifications are thoroughly tested.

4. **Slippage protection math** -- Pure calculation functions for minimum output, price validation, impact estimation, and budget analysis have strong coverage.

5. **Transaction management mechanics** -- Nonce allocation, sequential ordering, build/sign/send/confirm flow, retry logic, and simulation are tested (against mocked Web3).

6. **DEX adapter interfaces** -- All three adapters (UniswapV3, QuickSwap, SushiSwap) have tests for initialization, price fetching, trade execution, and error handling -- all mocked.

7. **Metrics collection** -- Recording, aggregation, and export formats are tested with pure logic.

8. **Security scanning** -- Static analysis for leaked secrets is well covered.

### What Is Completely Untested

1. **FlashLoanArbitrageV2 contract** -- Zero Foundry or Forge tests exist for the V2 contract. The only Solidity tests target V1 which has a different interface.

2. **DEX adapter Solidity contracts** -- `UniswapV3Adapter` and `UniswapV2Adapter` have no Solidity tests at all.

3. **`OpportunityDetector` (the new one in `src/opportunity_detector.py`)** -- This critical module has zero dedicated tests. The `tests/test_arbitrage.py` tests a different code path (`src/bot/arbitrage.py`). The actual detector that calls `quoteExactInputSingle` and `getAmountsOut` on real contracts, performs binary search for optimal flash loan amounts, and logs to the database is entirely untested.

4. **`FlashLoanOrchestrator` (in `src/flash_loan_orchestrator.py`)** -- This module has zero dedicated tests. It builds `ArbitrageParams` structs, encodes V3 swap data, estimates gas with real `eth_call`, sends transactions, and logs results to the database. None of this is tested.

5. **`ArbitrageBot` class (in `run_bot.py`)** -- The integration class that wires detector, orchestrator, risk manager, and metrics together is completely untested. The `tests/test_main.py` tests a different `ArbitrageBot` class in `src/bot/main.py`.

6. **Database integration** -- The `get_db()` context manager, Opportunity/Transaction/TradeResult/ExecutionLog model creation and querying, and the full write-read cycle from detection through execution logging have zero tests.

7. **`GasOptimizer` in run_bot context** -- While `GasOptimizer` has unit tests, its integration with the bot's execution flow (where it feeds gas parameters to the orchestrator) is untested.

8. **Multi-chain support** -- `run_bot.py` supports `--chain polygon|arbitrum|optimism|base` but no tests verify chain-specific configuration loading or behavior.

### What Is Tested But Only With Mocks When It Needs Real Chain Validation

| Component | What Mocks Hide | Real-Chain Risk |
|-----------|----------------|-----------------|
| `BalanceValidator.check_balance()` | Mocked `balanceOf` and `decimals` calls | Could fail with real token contracts that have non-standard decimals or revert on balance checks |
| `UniswapV3.get_token_price()` | Mocked `quoteExactInputSingle` return values | Real QuoterV2 returns a struct (4 values), and the ABI must match exactly or the call reverts silently |
| `QuickSwap.execute_trade()` | Mocked `swapExactTokensForTokens` and receipts | Real routers require token approvals, correct path arrays, and deadline timestamps that are not validated against real state |
| `TransactionManager.execute_transaction()` | Mocked nonce, gas price, signing, and receipt | Real nonce management under concurrent execution can produce replacement errors or stuck transactions |
| `RiskManager.validate_trade()` | Mocked Web3 instance | The `amount_in` to USD conversion uses `token_decimals` from the opportunity dict -- if the detector produces wrong decimals, the risk check passes but the trade is oversized |
| `FlashLoanOrchestrator.build_transaction()` | N/A (untested) | ABI encoding of the `ArbitrageParams` struct with nested `SwapStep[]` is the single most likely point of failure. One wrong type, one missing field, and the transaction reverts. This has never been tested against the real contract. |
| `OpportunityDetector.calculate_arbitrage()` | N/A (untested) | Profit calculation assumes `amount_out - amount_in - fee = profit`, but does not account for pool-specific fee structures, and the `_calculate_profit_after_fees` method only deducts the Aave flash loan fee (5 bps), not the DEX swap fees which are already embedded in the quote. If quote behavior differs from expectation, profits are miscalculated. |

---

## B. Integration Test Plan

### Fork Strategy

All integration tests should run against an **Anvil mainnet fork** of Polygon (chain ID 137). This provides:

- Real contract bytecode for Aave V3 Pool, Uniswap V3 QuoterV2, Uniswap V3 Router, QuickSwap Router
- Real pool state with actual liquidity
- Real token balances that can be impersonated
- Deterministic block state when pinned to a specific block
- No gas costs (Anvil provides unlimited ETH/MATIC to test accounts)
- Fast execution (~1s per test vs ~15s for real RPC)

### Fork Configuration

```
Chain: Polygon Mainnet (137)
RPC: Use $POLYGON_RPC_URL or a free Polygon RPC
Block: Pin to a recent block for reproducibility (e.g., --fork-block-number 68000000)
Anvil command:
  anvil --fork-url $POLYGON_RPC_URL \
        --fork-block-number 68000000 \
        --chain-id 137 \
        --block-time 2 \
        --accounts 3 \
        --balance 10000
```

### Key Addresses (Polygon Mainnet)

| Contract | Address |
|----------|---------|
| Aave V3 Pool Provider | `0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb` |
| Uniswap V3 QuoterV2 | `0x61fFE014bA17989E743c5F6cB21bF9697530B21e` |
| Uniswap V3 SwapRouter | `0xE592427A0AEce92De3Edee1F18E0157C05861564` |
| QuickSwap V2 Router | `0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff` |
| USDC (Polygon) | `0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174` |
| WMATIC | `0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270` |
| WETH (Polygon) | `0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619` |
| DAI (Polygon) | `0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063` |

### Required Fixtures

#### 1. `anvil_fork` (session-scoped)

Starts an Anvil process forking Polygon at a pinned block. Returns the RPC URL (`http://localhost:8545`). Tears down the process after all tests complete.

#### 2. `web3_fork` (session-scoped)

Creates a `Web3` instance connected to the Anvil fork. Injects POA middleware for Polygon compatibility. Validates connection and chain ID.

#### 3. `funded_account` (session-scoped)

Uses Anvil's default account #0 (pre-funded with 10000 MATIC). Also uses `anvil_impersonateAccount` to fund the account with USDC, WMATIC, and WETH by impersonating a whale address and transferring tokens. This ensures the test account has token balances for non-flash-loan tests.

#### 4. `deployed_contracts` (session-scoped)

Deploys `FlashLoanArbitrageV2`, `UniswapV3Adapter`, and `UniswapV2Adapter` to the fork using the funded account. Registers both adapters in the V2 contract. Returns a dict of contract addresses. This mirrors the real deployment but is deterministic and disposable.

#### 5. `detector_instance` (function-scoped)

Creates an `OpportunityDetector` connected to the fork's Web3 instance. Uses real contract addresses.

#### 6. `orchestrator_instance` (function-scoped)

Creates a `FlashLoanOrchestrator` connected to the fork with the deployed contract addresses and the funded account's private key. Dry run disabled.

#### 7. `risk_manager_instance` (function-scoped)

Creates a `RiskManager` with the fork's Web3 instance and conservative limits suitable for testing (e.g., max position $50,000, daily loss limit $5,000).

#### 8. `test_database` (function-scoped)

Creates a temporary SQLite database, runs migrations, and configures the `src.db.database` module to use it. Tears down after each test. This isolates database state between tests.

---

## C. Recommended Test Suite

All tests below are described as specifications. They should live in `tests/fork/` with the `@pytest.mark.integration` marker and be skippable when no Anvil fork is available.

---

### Test 1: `test_detection_against_real_pools`

**Purpose:** Verify that `OpportunityDetector` can fetch real quotes from Uniswap V3 QuoterV2 and QuickSwap Router and correctly identify price differences.

**Setup:** Create an `OpportunityDetector` connected to the Anvil fork.

**Steps:**
1. Call `detector.get_v3_quote(USDC, WMATIC, 1000 * 10**6, fee=3000)` and verify a non-None integer is returned.
2. Call `detector.get_v2_quote(USDC, WMATIC, 1000 * 10**6)` and verify a non-None integer is returned.
3. Call `detector.find_best_v3_fee(USDC, WMATIC, 1000 * 10**6)` and verify it returns a valid `(amount, fee_tier)` tuple.
4. Call `detector.calculate_arbitrage(USDC, WMATIC, 1000 * 10**6)` and verify the returned list contains dicts with all required keys (`direction`, `token_in`, `token_out`, `amount_in`, `net_profit`, `v3_fee`, `dex_path`).
5. Run `detector.scan_opportunities()` and verify it completes without error. If opportunities are found, verify each has `token_decimals` set.

**Assertions:**
- V3 quotes return positive integers within a reasonable range (not zero, not overflow).
- V2 quotes return positive integers.
- `calculate_arbitrage` returns a list (possibly empty, but no exceptions).
- All opportunity dicts conform to the expected schema.

**What this catches that unit tests cannot:** ABI mismatches with the real QuoterV2 (which returns a 4-tuple, not a single uint256), incorrect fee tier enumeration, and contract call failures due to wrong addresses or parameters.

---

### Test 2: `test_full_execution_flow`

**Purpose:** Validate the complete pipeline: detect opportunity -> validate with risk manager -> simulate via eth_call -> execute via flash loan -> verify on-chain state.

**Setup:** Deploy contracts, create detector, orchestrator, and risk manager instances.

**Steps:**
1. Scan for opportunities using the detector.
2. If no natural opportunity exists, create a synthetic one by manipulating pool state via Anvil's `anvil_setStorageAt` (or use a known block where a spread exists).
3. Pass the opportunity through `risk_manager.validate_trade()`.
4. Call `orchestrator.build_transaction(opportunity)` and verify the transaction dict has all required fields.
5. Simulate the transaction via `web3.eth.call()` and verify it does not revert.
6. Execute via `orchestrator.execute_opportunity(opportunity)`.
7. Verify the returned result dict has `success: True`, a non-null `tx_hash`, and `gas_used > 0`.

**Assertions:**
- Risk manager approves the trade.
- Transaction simulation passes.
- Transaction executes successfully on-chain.
- Gas used is within the expected range (200k-800k for a 2-step swap).

**What this catches:** ABI encoding errors in `ArbitrageParams` struct construction, incorrect adapter data encoding, flash loan callback failures, and integration bugs between Python and Solidity.

---

### Test 3: `test_flash_loan_repayment`

**Purpose:** Verify that the flash loan is always fully repaid, even when the arbitrage is unprofitable. The contract should revert (not leave debt).

**Setup:** Deploy contracts with `minProfit = 0` to allow unprofitable executions, or test with the default minProfit to ensure revert.

**Steps:**
1. Build an arbitrage that is intentionally unprofitable (e.g., swap USDC -> WMATIC -> USDC at unfavorable rates, or set `minFinalAmount` higher than what the swaps can produce).
2. Attempt to execute it.
3. Verify the transaction reverts with `InsufficientProfit` or `SwapFailed`.
4. Check the Aave V3 Pool's debt state for the contract address -- it should be zero.
5. Check the contract's USDC balance -- it should be unchanged from before the attempt.

**Assertions:**
- Unprofitable arbitrage reverts, does not create Aave debt.
- Contract token balances are unchanged after a reverted flash loan.
- The Python orchestrator correctly identifies the revert and returns `success: False`.

**What this catches:** Scenarios where the flash loan is taken but not repaid (catastrophic loss), or where the Python code misinterprets a revert as a success.

---

### Test 4: `test_profit_accounting_matches_chain`

**Purpose:** Verify that the profit recorded in the database matches the actual on-chain state change.

**Setup:** Deploy contracts, set up a test database.

**Steps:**
1. Record the contract's USDC balance before execution.
2. Execute a successful arbitrage (using a known-profitable block state or by manipulating pool reserves).
3. Record the contract's USDC balance after execution.
4. Query the database for the TradeResult and Transaction records.
5. Compare `TradeResult.profit_amount` with the actual on-chain balance difference.
6. Compare `Transaction.gas_used` with the receipt's `gasUsed`.
7. Verify `Opportunity.status` is `EXECUTED`.
8. Verify `ExecutionLog` was created with correct step and data.

**Assertions:**
- Database profit matches on-chain balance change (within rounding tolerance of 1 unit).
- Gas used matches between database and receipt.
- All database records are internally consistent (foreign keys, statuses).

**What this catches:** Off-by-one errors in profit calculation, incorrect token decimal handling in database writes, missing database commits, and foreign key violations.

---

### Test 5: `test_circuit_breaker_halts_execution`

**Purpose:** Verify that the risk manager's circuit breaker prevents execution after consecutive failures, and that this integrates correctly with the bot's execution flow.

**Setup:** Create a risk manager with `max_consecutive_losses=3`.

**Steps:**
1. Record 3 failed trade results in the risk manager.
2. Verify `circuit_breaker.is_active is True`.
3. Attempt to validate a new trade via `risk_manager.validate_trade()`.
4. Verify it returns `(False, "Circuit breaker active...")`.
5. Create an `ArbitrageBot` instance and attempt `bot.execute_opportunity(opportunity)`.
6. Verify the bot's `stats['risk_rejections']` counter increments.
7. Verify the orchestrator was never called (no transaction sent).

**Assertions:**
- Circuit breaker blocks trade validation after N consecutive losses.
- The bot's execution flow respects the risk manager's rejection.
- No transaction is sent to the chain.

**What this catches:** Integration issues where the risk manager's rejection is ignored or where the bot's execution flow bypasses risk checks under certain conditions.

---

### Test 6: `test_gas_estimation_accuracy`

**Purpose:** Compare the detector's static gas estimate (500k) and the orchestrator's `eth_estimateGas` against the actual gas consumed by a real transaction.

**Setup:** Deploy contracts, prepare a valid arbitrage.

**Steps:**
1. Record `detector.estimate_gas_cost()` (the static estimate).
2. Build a transaction via `orchestrator.build_transaction(opportunity)`.
3. Record the gas limit set by `orchestrator.estimate_gas(transaction)`.
4. Execute the transaction and get the receipt.
5. Record `receipt['gasUsed']`.
6. Calculate the ratios: `static_estimate / actual_gas` and `eth_estimate / actual_gas`.

**Assertions:**
- The `eth_estimateGas` result is within 30% of actual gas used (i.e., ratio between 0.7 and 1.3).
- The static 500k estimate is within 2x of actual gas used.
- The orchestrator's 20% buffer (`gas_estimate * 1.2`) is sufficient (i.e., `gas_limit >= actual_gas`).

**What this catches:** Scenarios where gas estimation is wildly inaccurate, causing either (a) out-of-gas reverts because the limit is too low, or (b) massive gas waste because the limit is 10x too high.

---

### Test 7: `test_detector_quote_consistency`

**Purpose:** Verify that the detector's V3 and V2 quotes are internally consistent and that the profit calculation is correct.

**Setup:** Connect detector to the fork.

**Steps:**
1. Get a V3 quote: `v3_out = detector.get_v3_quote(USDC, WMATIC, 1000e6, fee=3000)`.
2. Get a V2 quote for the reverse: `v2_out = detector.get_v2_quote(WMATIC, USDC, v3_out)`.
3. Calculate expected gross profit: `v2_out - 1000e6`.
4. Calculate expected net profit: `gross - (1000e6 * 5 / 10000)` (flash loan fee).
5. Call `detector.calculate_arbitrage(USDC, WMATIC, 1000e6)` and find the V3->V2 opportunity if it exists.
6. Compare the opportunity's `gross_profit` and `net_profit` with the manually calculated values.

**Assertions:**
- If the opportunity exists, `gross_profit` matches manual calculation exactly.
- `net_profit` matches manual calculation exactly.
- `amount_after_v3` matches the V3 quote.
- `amount_after_v2` matches the V2 quote.

**What this catches:** Bugs in `_calculate_profit_after_fees`, incorrect field assignment in the opportunity dict, and scenarios where quotes change between calls (which would indicate the test needs block pinning).

---

### Test 8: `test_flash_loan_amount_optimization`

**Purpose:** Verify that `find_optimal_flash_loan_amount` correctly identifies the amount that maximizes profit, and that it handles the slippage curve properly.

**Setup:** Connect detector to the fork with a pair that has reasonable liquidity.

**Steps:**
1. Call `detector.find_optimal_flash_loan_amount(USDC, WMATIC, 'V3->V2')` with min=$500, max=$100k.
2. If it returns an optimal opportunity, verify:
   - The `amount_in` is between min and max.
   - The `net_profit` is positive.
   - Running `calculate_arbitrage` at `amount_in * 2` yields equal or lower profit (confirming we found or are near the optimum).
3. If no opportunity exists (markets are efficient), verify the function returns `None` without error.

**Assertions:**
- The optimization terminates (does not infinite loop).
- The returned amount is a local maximum for profit.
- The function handles the "no opportunity" case gracefully.

**What this catches:** Infinite loops in the binary search, incorrect slippage curve assumptions, and edge cases where all tested amounts are unprofitable.

---

### Test 9: `test_orchestrator_abi_encoding`

**Purpose:** Verify that the orchestrator correctly encodes the `ArbitrageParams` struct, including nested `SwapStep[]`, in a format that the Solidity contract can decode.

**Setup:** Deploy the V2 contract and adapters.

**Steps:**
1. Build a valid opportunity dict (matching what the detector would produce).
2. Call `orchestrator.build_swap_steps(opportunity, deadline)`.
3. Verify the returned steps are a list of tuples with correct types: `(address, address, address, uint256, bytes)`.
4. Call `orchestrator.build_transaction(opportunity)`.
5. Decode the transaction's `data` field by ABI-decoding it against the `executeArbitrage` function selector.
6. Verify the decoded `ArbitrageParams` matches the input.
7. Submit the transaction via `eth_call` to verify the contract can decode it without revert (the actual swap may fail due to pool state, but the decoding should succeed).

**Assertions:**
- Swap steps have the correct adapter addresses.
- Token addresses are checksummed.
- `flashLoanAmount` and `flashLoanAsset` are correct.
- The `data` field for V3 steps contains correctly encoded `(uint24, uint256)` for fee and deadline.
- The V2 steps have empty `data` (`b''`).
- The contract can ABI-decode the calldata without error.

**What this catches:** The highest-risk failure mode in the entire system -- ABI encoding mismatches between Python's `web3.codec.encode` and Solidity's `abi.decode`. A single wrong type here causes every transaction to revert.

---

### Test 10: `test_contract_ownership_and_permissions`

**Purpose:** Verify that contract access controls work correctly -- only the owner can execute arbitrage, register adapters, pause, etc.

**Setup:** Deploy V2 contract from account #0.

**Steps:**
1. Verify `contract.functions.owner().call()` returns account #0.
2. From account #1 (non-owner), attempt `executeArbitrage` and verify it reverts with "OwnableUnauthorizedAccount".
3. From account #0, register an adapter and verify `registeredAdapters[adapter] == true`.
4. From account #0, pause the contract.
5. From account #0, attempt `executeArbitrage` and verify it reverts with "EnforcedPause".
6. From account #0, unpause and verify `executeArbitrage` no longer reverts (may revert for other reasons, but not for pause).

**Assertions:**
- Non-owner calls revert.
- Pause prevents execution.
- Unpause allows execution.
- Adapter registration persists.

**What this catches:** Incorrect OpenZeppelin import versions, constructor arguments that set the wrong owner, and modifier ordering issues.

---

### Test 11: `test_database_opportunity_lifecycle`

**Purpose:** Verify the full lifecycle of an opportunity in the database: DETECTED -> EXECUTING -> EXECUTED (or FAILED), with associated Transaction, TradeResult, and ExecutionLog records.

**Setup:** Configure a test SQLite database.

**Steps:**
1. Use the detector to scan for opportunities and log one via `detector.log_opportunity()`.
2. Query the database and verify the Opportunity record exists with status `DETECTED`.
3. Simulate the orchestrator picking it up: set status to `EXECUTING`.
4. Execute the opportunity via the orchestrator with the database opportunity ID.
5. Query the database and verify:
   - Opportunity status is `EXECUTED` (or `FAILED`).
   - A Transaction record exists with the correct `tx_hash`.
   - A TradeResult record exists (if successful) with `profit_amount > 0`.
   - An ExecutionLog record exists with level `INFO` or `ERROR`.

**Assertions:**
- All database records are created with correct foreign key relationships.
- The opportunity status transitions are valid.
- Timestamps are populated.

**What this catches:** SQLAlchemy model mismatches, missing commits, foreign key constraint violations, and the disconnect between the string `opportunity_id` and the integer `id` (which the orchestrator handles via a lookup).

---

### Test 12: `test_emergency_withdrawal`

**Purpose:** Verify that the contract owner can perform an emergency withdrawal of tokens from the contract.

**Setup:** Deploy V2 contract, fund it with some USDC via impersonation.

**Steps:**
1. Transfer 1000 USDC to the contract address.
2. Verify `contract.functions.getBalance(USDC).call() == 1000e6`.
3. Call `contract.functions.emergencyWithdraw(USDC, 1000e6, owner_address)` from the owner.
4. Verify the contract's USDC balance is now 0.
5. Verify the owner's USDC balance increased by 1000e6.

**Assertions:**
- Emergency withdrawal transfers the exact amount.
- Only the owner can call it.
- No funds are lost.

**What this catches:** SafeERC20 issues, incorrect balance tracking, and reentrancy vulnerabilities in the withdrawal path.

---

### Test 13: `test_concurrent_detection_execution_race`

**Purpose:** Verify that the system handles the race condition where pool prices change between detection and execution.

**Setup:** Connect detector and orchestrator to the fork.

**Steps:**
1. Detect an opportunity at the current block.
2. Mine 5 new blocks on the fork (simulating ~10 seconds of time passing).
3. Attempt to execute the previously detected opportunity.
4. If the opportunity is no longer profitable (likely), verify:
   - The orchestrator's `eth_call` simulation fails.
   - The orchestrator returns `success: False` with `error: "Simulation failed: ..."`.
   - No transaction is sent to the chain.
5. If by chance it is still profitable, verify normal execution succeeds.

**Assertions:**
- The pre-execution simulation catches stale opportunities.
- No real transaction is sent for stale/unprofitable opportunities.
- The bot handles the simulation failure gracefully (no crash, no stuck state).

**What this catches:** Missing simulation checks, simulation checks that are too permissive, and error handling bugs in the execution path.

---

### Test 14: `test_adapter_registration_validation`

**Purpose:** Verify that the V2 contract rejects execution with unregistered adapters.

**Setup:** Deploy V2 contract, deploy adapters but DO NOT register them.

**Steps:**
1. Build an `ArbitrageParams` that references the unregistered adapter addresses.
2. Attempt to execute via `executeArbitrage`.
3. Verify the transaction reverts with `UnauthorizedAdapter(adapter_address)`.
4. Register one adapter but not the other.
5. Attempt execution again.
6. Verify it still reverts with `UnauthorizedAdapter` for the second adapter.
7. Register both adapters and attempt execution.
8. Verify the transaction no longer reverts for adapter authorization (may revert for other swap-related reasons).

**Assertions:**
- Unregistered adapters cause revert.
- Partial registration still fails.
- Full registration allows execution to proceed past the adapter check.

**What this catches:** Deployment scripts that forget to register adapters, or registration transactions that silently fail.

---

## D. CI Pipeline Integration

### GitHub Actions Workflow Design

```yaml
name: Fork Integration Tests

on:
  pull_request:
    branches: [main, develop]
  push:
    branches: [main]
  schedule:
    # Run daily at 06:00 UTC to catch state-dependent regressions
    - cron: '0 6 * * *'

env:
  POLYGON_RPC_URL: ${{ secrets.POLYGON_RPC_URL }}
  ANVIL_FORK_BLOCK: 68000000  # Pin to specific block

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pytest tests/ -m "not integration and not e2e and not testnet and not slow" --tb=short

  fork-integration-tests:
    runs-on: ubuntu-latest
    needs: unit-tests  # Only run if unit tests pass
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install Foundry (for Anvil)
        uses: foundry-rs/foundry-toolchain@v1
        with:
          version: nightly

      - name: Install Python dependencies
        run: pip install -r requirements.txt

      - name: Start Anvil fork
        run: |
          anvil --fork-url $POLYGON_RPC_URL \
                --fork-block-number $ANVIL_FORK_BLOCK \
                --chain-id 137 \
                --block-time 0 \
                --accounts 3 \
                --balance 10000 \
                --silent &
          # Wait for Anvil to be ready
          for i in $(seq 1 30); do
            curl -s http://localhost:8545 -X POST \
              -H "Content-Type: application/json" \
              -d '{"jsonrpc":"2.0","method":"eth_chainId","params":[],"id":1}' \
              && break || sleep 1
          done

      - name: Run fork integration tests
        run: |
          pytest tests/fork/ -m integration \
            --tb=long \
            -v \
            --timeout=120 \
            --no-cov  # Disable coverage for fork tests (slow)
        env:
          POLYGON_RPC_URL: http://localhost:8545
          PRIVATE_KEY: "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
          DATABASE_URL: "sqlite:///test_fork.db"

      - name: Upload test artifacts
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: fork-test-logs
          path: |
            bot.log
            test_fork.db

  solidity-fork-tests:
    runs-on: ubuntu-latest
    needs: unit-tests
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
      - uses: foundry-rs/foundry-toolchain@v1
        with:
          version: nightly
      - run: npm install
      - name: Run Forge tests
        run: forge test -vvv --fork-url $POLYGON_RPC_URL --fork-block-number $ANVIL_FORK_BLOCK
        env:
          POLYGON_RPC_URL: ${{ secrets.POLYGON_RPC_URL }}
```

### Handling RPC Rate Limits in CI

1. **Pin the fork block number.** This allows Anvil to cache all state locally after the first warm-up. Subsequent calls do not hit the RPC unless they access state not yet fetched.

2. **Use a dedicated RPC endpoint for CI.** Free public RPCs (e.g., `https://polygon-rpc.com`) rate-limit at ~25 req/s. For CI, use an Alchemy or Infura key stored as a GitHub secret, which provides 100-300 req/s.

3. **Use `--silent` mode for Anvil** to reduce stdout noise.

4. **Cache the Anvil fork state.** After the first CI run, the Anvil cache directory (`~/.foundry/cache/rpc/polygon/`) can be cached as a GitHub Actions artifact to reduce RPC calls on subsequent runs:
   ```yaml
   - uses: actions/cache@v4
     with:
       path: ~/.foundry/cache
       key: anvil-fork-${{ env.ANVIL_FORK_BLOCK }}
   ```

5. **Add retry logic to the Anvil startup** in case the RPC is slow to respond.

6. **Limit the number of fork tests** that make independent RPC calls. Most tests should share the same Anvil instance (session-scoped fixtures).

### Blocking vs. Informational Tests

| Test Category | CI Behavior | Rationale |
|--------------|-------------|-----------|
| Unit tests (97 existing) | **Blocking** -- PR cannot merge if any fail | Core logic must always pass |
| Fork tests 1-3 (detection, execution, repayment) | **Blocking** -- PR cannot merge if any fail | These validate the critical execution path |
| Fork tests 4-6 (accounting, circuit breaker, gas) | **Blocking** | Safety-critical subsystems |
| Fork tests 7-8 (quote consistency, amount optimization) | **Informational** -- warn but do not block | These may fail due to pool state changes even with a pinned block if the block is too old |
| Fork tests 9-10 (ABI encoding, permissions) | **Blocking** | ABI errors are catastrophic |
| Fork tests 11-14 (database, withdrawal, race, adapters) | **Informational** initially, **Blocking** once stable | These are lower risk but still important |
| Solidity Forge tests | **Blocking** | Contract correctness is non-negotiable |

To implement this, use pytest markers:

```python
@pytest.mark.integration
@pytest.mark.blocking
def test_full_execution_flow():
    ...

@pytest.mark.integration
@pytest.mark.informational
def test_flash_loan_amount_optimization():
    ...
```

And in CI:
```bash
# Blocking tests (must pass)
pytest tests/fork/ -m "integration and blocking" --strict-markers

# Informational tests (report but don't fail)
pytest tests/fork/ -m "integration and informational" --strict-markers || true
```

---

## Priority Matrix and Implementation Roadmap

### Phase 1: Critical Path (Week 1)

| Priority | Test | Risk Mitigated |
|----------|------|----------------|
| P0 | `test_orchestrator_abi_encoding` (#9) | Every transaction reverting due to encoding bugs |
| P0 | `test_flash_loan_repayment` (#3) | Catastrophic fund loss from unreturned flash loans |
| P0 | `test_full_execution_flow` (#2) | Complete pipeline failure |
| P0 | Foundry tests for `FlashLoanArbitrageV2.sol` | Contract-level correctness |

### Phase 2: Safety Systems (Week 2)

| Priority | Test | Risk Mitigated |
|----------|------|----------------|
| P1 | `test_detection_against_real_pools` (#1) | Detector silently returning garbage data |
| P1 | `test_circuit_breaker_halts_execution` (#5) | Risk manager bypass |
| P1 | `test_contract_ownership_and_permissions` (#10) | Unauthorized execution |
| P1 | `test_adapter_registration_validation` (#14) | Deployment configuration errors |

### Phase 3: Correctness (Week 3)

| Priority | Test | Risk Mitigated |
|----------|------|----------------|
| P2 | `test_profit_accounting_matches_chain` (#4) | Incorrect profit reporting |
| P2 | `test_gas_estimation_accuracy` (#6) | Out-of-gas or gas waste |
| P2 | `test_detector_quote_consistency` (#7) | Profit miscalculation |
| P2 | `test_database_opportunity_lifecycle` (#11) | Database corruption |

### Phase 4: Robustness (Week 4)

| Priority | Test | Risk Mitigated |
|----------|------|----------------|
| P3 | `test_flash_loan_amount_optimization` (#8) | Suboptimal trade sizing |
| P3 | `test_concurrent_detection_execution_race` (#13) | Stale opportunity execution |
| P3 | `test_emergency_withdrawal` (#12) | Inability to recover stuck funds |

### Additional Recommendations

1. **Write Foundry tests for FlashLoanArbitrageV2.sol immediately.** The V1 tests in `test/contracts/FlashLoanArbitrage.t.sol` are useless for the V2 contract. At minimum, test: deployment, adapter registration, successful arbitrage execution (with MockDEX contracts), flash loan repayment, revert on insufficient profit, revert on unregistered adapter, revert on expired deadline, and emergency withdrawal.

2. **Delete or archive `tests/integration/test_full_system.py`.** It targets Mumbai testnet which no longer exists. Replace it with Anvil fork tests.

3. **Consolidate the two `ArbitrageBot` classes.** There is `src/bot/main.py:ArbitrageBot` (tested by `test_main.py`) and `run_bot.py:ArbitrageBot` (untested). The latter is the one actually used. Tests should target the real entry point.

4. **Add a `conftest.py` in `tests/fork/`** with all the session-scoped fixtures described above. This keeps fork test infrastructure isolated from unit tests.

5. **Pin fork block numbers in a config file** (e.g., `tests/fork/block_config.json`) so they can be updated periodically as pool state evolves.

---

*Report generated by Fork Testing / Integration Testing Agent*
*All file paths reference the project root at `/Users/ethanallen/Desktop/ARBITRAGE/arb_bot_cryp_eea/`*
