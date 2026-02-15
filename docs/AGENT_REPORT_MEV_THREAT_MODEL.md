# MEV / Adversarial Security Threat Model

## Flash Loan Arbitrage Bot -- Comprehensive Threat Assessment

**Report Date:** 2026-02-12
**Analyst:** MEV / Adversarial Security Agent
**Scope:** Full adversarial threat model covering frontrunning, sandwich attacks, RPC trust, oracle manipulation, gas griefing, replay attacks, and block reorganization risks
**Severity Rating System:** CRITICAL / HIGH / MEDIUM / LOW

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Architecture Overview](#2-system-architecture-overview)
3. [Threat A: Frontrunning and Sandwich Attacks](#3-threat-a-frontrunning-and-sandwich-attacks)
4. [Threat B: Backrunning and Copy Trading](#4-threat-b-backrunning-and-copy-trading)
5. [Threat C: RPC Provider Trust](#5-threat-c-rpc-provider-trust)
6. [Threat D: Oracle and Price Manipulation](#6-threat-d-oracle-and-price-manipulation)
7. [Threat E: Gas Price Manipulation](#7-threat-e-gas-price-manipulation)
8. [Threat F: Nonce and Replay Attacks](#8-threat-f-nonce-and-replay-attacks)
9. [Threat G: Block Reorganization Risks](#9-threat-g-block-reorganization-risks)
10. [Cross-Cutting Concerns](#10-cross-cutting-concerns)
11. [Chain-Specific Analysis](#11-chain-specific-analysis)
12. [Prioritized Mitigation Roadmap](#12-prioritized-mitigation-roadmap)
13. [Appendix: Code References](#13-appendix-code-references)

---

## 1. Executive Summary

This report presents an adversarial threat model for the flash loan arbitrage bot operating across Polygon, Arbitrum, Optimism, and Base. The analysis is based on a line-by-line reading of the bot's Python source, Solidity contracts, gas optimization logic, and configuration.

### Critical Findings

| # | Threat | Severity | Current Status |
|---|--------|----------|----------------|
| A | **Sandwich attacks via public mempool** | **CRITICAL** | Unmitigated -- all transactions broadcast to public mempool |
| B | Backrunning / opportunity theft | HIGH | Unmitigated -- detection pattern is observable |
| C | RPC provider information leakage | HIGH | Unmitigated -- single RPC provider, `eth_call` reveals intent |
| D | Spot price manipulation / phantom arbitrage | MEDIUM | Partially mitigated by minFinalAmount checks |
| E | Gas price auction competition | MEDIUM | Partially mitigated -- static 2 gwei priority fee is inadequate |
| F | Nonce / replay vulnerabilities | LOW | Mostly mitigated -- EIP-155 chain ID present, but nonce management has race conditions |
| G | Block reorganization risk | LOW-MEDIUM | Unmitigated -- no confirmation-count checks, DB records on first receipt |

### Bottom Line

**The bot is currently not safe to operate with real capital on any chain with a public mempool (Polygon).** Every profitable transaction broadcast to Polygon's public mempool will be sandwiched by MEV bots, converting the bot's expected profit into a guaranteed loss. On L2 chains (Arbitrum, Optimism, Base), the sequencer-ordered transaction model provides *partial* protection, but the bot still leaks intent through its RPC provider and has no private submission fallback.

---

## 2. System Architecture Overview

### Transaction Lifecycle (Attack Surface Map)

```
[1] OpportunityDetector.scan_opportunities()
    |-- eth_call: QuoterV2.quoteExactInputSingle()     <-- RPC sees your opportunity
    |-- eth_call: V2Router.getAmountsOut()              <-- RPC sees your opportunity
    |-- Compares V3 vs V2 prices
    |-- find_optimal_flash_loan_amount() [up to 15 RPC calls per pair]
    |
[2] FlashLoanOrchestrator.build_transaction()
    |-- eth_call: baseFeePerGas                          <-- Gas data visible
    |-- eth_call: getTransactionCount (nonce)
    |-- build_transaction() -> tx data fully formed
    |
[3] FlashLoanOrchestrator.execute_opportunity()
    |-- eth_call: paused() check
    |-- eth_call: SIMULATION of full tx                  <-- RPC sees exact trade params
    |-- eth_sendRawTransaction -> PUBLIC MEMPOOL         <-- ALL searchers see the tx
    |-- wait_for_transaction_receipt (120s timeout)
    |
[4] On-chain: FlashLoanArbitrageV2.executeArbitrage()
    |-- Aave flash loan -> swap on DEX A -> swap on DEX B -> repay
    |-- Profit check: require(currentAmount >= minFinalAmount)
```

### Key Code Locations

| Component | File | Critical Lines |
|-----------|------|----------------|
| Transaction broadcast | `src/flash_loan_orchestrator.py` | Line 379: `send_raw_transaction` |
| Pre-execution simulation | `src/flash_loan_orchestrator.py` | Lines 351-358: `eth_call` simulation |
| Slippage tolerance | `src/flash_loan_orchestrator.py` | Line 185: `95 // 100` (5% first step) |
| Gas pricing | `src/flash_loan_orchestrator.py` | Lines 286-289: `baseFee * 2 + 2 gwei` |
| Gas pricing (utility) | `src/utils/gas_optimizer.py` | Lines 66-85: EIP-1559 parameters |
| Opportunity detection | `src/opportunity_detector.py` | Lines 176-265: quote calls |
| Flash loan optimization | `src/opportunity_detector.py` | Lines 405-516: iterative RPC calls |
| On-chain execution | `contracts/FlashLoanArbitrageV2.sol` | Lines 125-176: `executeArbitrage` |
| On-chain callback | `contracts/FlashLoanArbitrageV2.sol` | Lines 181-248: `executeOperation` |
| Nonce management | `src/utils/transaction_manager.py` | Lines 40-62: `get_next_nonce` |

---

## 3. Threat A: Frontrunning and Sandwich Attacks

### Severity: CRITICAL

### 3.1 Attack Description

A sandwich attack works as follows:

1. Bot broadcasts arbitrage transaction to public mempool
2. Searcher sees the pending transaction (including all calldata: token pair, amounts, slippage)
3. Searcher inserts a **frontrun** transaction that moves the pool price against the bot
4. Bot's transaction executes at a worse price (eating into slippage tolerance)
5. Searcher inserts a **backrun** transaction that profits from the price dislocation

### 3.2 Quantitative Exposure

The bot's slippage tolerance directly determines the maximum extractable value per sandwich:

**First swap step (intermediate):**
```python
# src/flash_loan_orchestrator.py, line 185
first_step_min = int(expected_intermediate * 95 // 100)  # 5% tolerance
```

**Final amount check:**
```python
# src/flash_loan_orchestrator.py, line 281
opportunity['amount_in'] + opportunity['net_profit']  # minFinalAmount
```

**On-chain enforcement:**
```solidity
// FlashLoanArbitrageV2.sol, line 229
require(currentAmount >= arbParams.minFinalAmount, "Slippage check failed");
```

**Maximum loss per sandwich attack:**

| Flash Loan Size | 5% of Intermediate Swap | Typical Sandwich Extraction |
|----------------|-------------------------|----------------------------|
| $500 | $25 | $5-15 |
| $10,000 | $500 | $50-200 |
| $50,000 | $2,500 | $200-1,000 |
| $100,000 | $5,000 | $500-2,500 |

On Polygon, where the mempool is public and block times are ~2 seconds, sandwich bots typically extract 50-80% of available slippage. With 5% slippage tolerance on the first hop, the bot is offering up to 2.5-4% of the intermediate swap value to sandwich bots.

**Importantly:** The bot's expected profit (typically $1-$50 on arbitrage trades) is almost always smaller than the sandwich extraction potential ($50-$2,500). This means a sandwiched trade will nearly always result in a net loss for the bot, even if the on-chain `minFinalAmount` check passes.

### 3.3 Chain-Specific Mempool Visibility

| Chain | Mempool Type | Sandwich Risk | Notes |
|-------|-------------|---------------|-------|
| **Polygon** | **Public mempool** | **CRITICAL** | Full visibility to all searchers. Bor validators can reorder. Polygon has one of the most competitive MEV environments. |
| **Arbitrum** | Sequencer-ordered (FCFS) | LOW-MEDIUM | The Arbitrum sequencer processes transactions in first-come-first-served order. No public mempool in the traditional sense. However, the RPC endpoint itself sees all pending transactions, and the sequencer operator has theoretical reordering power. |
| **Optimism** | Sequencer-ordered (FCFS) | LOW-MEDIUM | Same as Arbitrum. OP Stack sequencer uses FCFS ordering. Sequencer is currently centralized (Optimism Foundation). |
| **Base** | Sequencer-ordered (FCFS) | LOW-MEDIUM | Same as Optimism (OP Stack). Sequencer run by Coinbase. Builder API coming. |

### 3.4 Current Mitigations

- `minFinalAmount` check on-chain (prevents total loss but not partial loss)
- `minAmountOut` on first swap step at 95% (limits maximum extraction per hop)
- `deadline` parameter (5 minutes -- excessively long, should be ~30 seconds for L2s)
- `onlyOwner` modifier (prevents unauthorized contract calls)

### 3.5 What Is Missing (CRITICAL)

1. **No private transaction submission.** The bot uses `web3.eth.send_raw_transaction` which broadcasts to the public mempool on all chains.

2. **5% slippage tolerance is far too high** for an arbitrage bot. Legitimate arbitrage trades on established pairs have typical slippage of 0.1-0.5%. Setting 5% is essentially donating money to sandwich bots.

3. **The 5-minute deadline is too long.** On L2 chains with 2-second block times, a deadline of 30-60 seconds is more appropriate. A 5-minute window gives attackers extensive time to manipulate prices.

4. **No MEV protection on second swap step.** The second step's `minAmountOut` is set to `amount_in + net_profit`, which is the bare minimum to be profitable. Any price movement between detection and execution will cause the trade to revert, wasting gas.

### 3.6 Recommended Mitigations

**Priority 1 -- Private Transaction Submission (implement immediately before any mainnet deployment):**

| Chain | Private Submission Method | Endpoint |
|-------|--------------------------|----------|
| Polygon | Flashbots Protect RPC | `https://rpc.flashbots.net/polygon` |
| Polygon | MEV Blocker (by CoW Protocol) | `https://rpc.mevblocker.io` |
| Polygon | BloxRoute BDN | Requires account |
| Arbitrum | Send directly to sequencer | Default RPC behavior (already FCFS) |
| Optimism | Send directly to sequencer | Default RPC behavior (already FCFS) |
| Base | Send directly to sequencer | Default RPC behavior (already FCFS) |

For Polygon specifically, the transaction should **never** be broadcast to the public mempool. Instead:

```python
# Conceptual -- use a private RPC endpoint for tx submission
PRIVATE_RPC_ENDPOINTS = {
    137: "https://rpc.flashbots.net/polygon",   # Polygon mainnet
    42161: None,  # Arbitrum: standard RPC is fine (sequencer-ordered)
    10: None,     # Optimism: standard RPC is fine
    8453: None,   # Base: standard RPC is fine
}
```

**Priority 2 -- Reduce slippage tolerance:**

| Current | Recommended (Stable Pairs) | Recommended (Volatile Pairs) |
|---------|---------------------------|------------------------------|
| 5% | 0.3% | 1.0% |

The intermediate swap `minAmountOut` should be calculated as:
```
minAmountOut = expectedOutput * (1 - slippageTolerance)
```
Where `slippageTolerance` should be 0.3% for stablecoin pairs and 1.0% for volatile pairs -- not 5%.

**Priority 3 -- Reduce deadline:**

```python
# Current: 5 minutes
deadline = int(time.time()) + 300

# Recommended: 30 seconds for L2, 60 seconds for Polygon
if chain_id in (42161, 10, 8453):  # L2 chains
    deadline = int(time.time()) + 30
else:  # Polygon
    deadline = int(time.time()) + 60
```

**Priority 4 -- Dynamic slippage based on liquidity:**

Use the pool's liquidity depth to calculate price impact and set `minAmountOut` accordingly, rather than using a fixed percentage. The `SlippageProtection` class in `src/utils/slippage_protection.py` already has this logic (`calculate_safe_trade_amount`, `estimate_price_impact`) but it is **not integrated** into the orchestrator's transaction building.

---

## 4. Threat B: Backrunning and Copy Trading

### Severity: HIGH

### 4.1 Attack Description

A searcher (competing bot) monitors the bot's on-chain activity and RPC traffic to:

1. **Detect the same opportunity** before the bot can execute it
2. **Copy the exact trade** using a faster execution path
3. **Backrun the bot's detection** by watching for specific `eth_call` patterns on the RPC endpoint

### 4.2 Information Leakage Points

**RPC-level leakage (most dangerous):**

The opportunity detector makes a predictable, high-frequency pattern of RPC calls:

```python
# src/opportunity_detector.py, lines 176-208
# Pattern: quoteExactInputSingle -> getAmountsOut -> compare -> optimize

# For each of 4 trading pairs:
#   1. V3 QuoterV2.quoteExactInputSingle() x3 (three fee tiers)
#   2. V2 Router.getAmountsOut()
#   3. If profitable: up to 15 more calls for optimization
```

This pattern is visible to:
- The RPC provider (sees all `eth_call` requests)
- Any infrastructure between the bot and the RPC (man-in-the-middle)
- Anyone sharing the same RPC endpoint (if using a shared/free endpoint)

**On-chain activity fingerprinting:**

Once the bot has executed even one successful trade, its pattern becomes fingerprint-able:

- Same contract address every time
- Same adapter addresses every time
- Same token pairs (4 configured pairs)
- Same function signature (`executeArbitrage`)
- Predictable flash loan amounts (binary-search optimized amounts)
- Bot's EOA address is fixed and public

Any competing searcher can set up event watchers on the FlashLoanArbitrageV2 contract and the DEX pools to detect when the bot is active and which pairs it is trading.

### 4.3 Current Mitigations

None. The bot has no countermeasures against backrunning or copy trading.

### 4.4 Recommended Mitigations

**Priority 1 -- Diversify RPC providers:**

Use different RPC providers for reading (detection) vs writing (execution):
- Detection: Use a free/public RPC or a dedicated node
- Execution: Use a private RPC (Flashbots, MEV Blocker, etc.)

This prevents the execution RPC from seeing the detection pattern and correlating it with the transaction submission.

**Priority 2 -- Reduce detection fingerprint:**

- Randomize the order of pair scanning
- Add random jitter to scan intervals (currently fixed at `check_interval` seconds)
- Use Multicall to batch all quote requests into a single RPC call (the `Multicall` class exists in `src/utils/multicall.py` but is not used by the detector)
- Rotate between multiple bot EOA addresses for execution

**Priority 3 -- Speed optimization:**

The detection loop is slow because it makes sequential RPC calls:

```python
# Current: sequential calls, up to ~60 RPC calls per scan cycle
for token_a, token_b in self.trading_pairs:  # 4 pairs
    for fee in [500, 3000, 10000]:           # 3 fee tiers
        get_v3_quote(...)                     # 1 call each
    get_v2_quote(...)                         # 1 call
    # If profitable: 15 more calls for optimization
```

A competing bot using Multicall can fetch all quotes in a single RPC call, giving them a ~200-500ms advantage. The bot should batch all detection queries using the existing Multicall infrastructure.

**Priority 4 -- Commit-reveal or intent-based execution:**

For high-value trades, consider using a commit-reveal scheme where the trade parameters are committed on-chain (hashed) in one block and revealed/executed in the next. This prevents frontrunning but adds latency.

---

## 5. Threat C: RPC Provider Trust

### Severity: HIGH

### 5.1 Attack Description

The RPC provider is a trusted intermediary that sees:

1. **All `eth_call` simulations** -- including the full transaction simulation at line 351-358 of `flash_loan_orchestrator.py`, which reveals the exact trade parameters (tokens, amounts, slippage tolerances)
2. **All quote requests** -- revealing which opportunities the bot is exploring
3. **Transaction submission** -- seeing the raw signed transaction before it reaches the mempool
4. **Timing patterns** -- knowing when the bot detects an opportunity and when it submits the transaction

A malicious or compromised RPC provider can:

- **Front-run every trade** using the simulation data
- **Delay transaction propagation** to give competing bots time to act
- **Censor transactions** entirely
- **Return stale data** to cause the bot to misjudge opportunities
- **Sell the bot's transaction flow data** to MEV searchers

### 5.2 Current Configuration

```python
# .env.example -- public RPC endpoints with no authentication
POLYGON_RPC_URL=https://polygon-rpc.com
ARBITRUM_RPC_URL=https://arb1.arbitrum.io/rpc
OPTIMISM_RPC_URL=https://mainnet.optimism.io
BASE_RPC_URL=https://mainnet.base.org
```

These are free public RPC endpoints with:
- No SLA guarantees
- Rate limiting
- Shared infrastructure with other users
- No privacy guarantees
- Potential for stale/cached responses

### 5.3 Current Mitigations

- The bot uses a single RPC provider per chain (no fallback)
- A basic connection check exists at startup (`web3.is_connected()`, `get_block('latest')`)
- No mechanism to detect stale or manipulated responses

### 5.4 Recommended Mitigations

**Priority 1 -- Separate read and write RPC providers:**

```
Detection (read):  Use Provider A (e.g., Alchemy, Infura)
Simulation (read): Use Provider B (different from A)
Execution (write): Use Provider C (private relay, e.g., Flashbots)
```

This ensures no single provider sees the full lifecycle from detection to execution.

**Priority 2 -- Use authenticated, paid RPC providers:**

Free public RPCs are the most likely to sell transaction flow data. Paid providers (Alchemy, Infura, QuickNode) have stronger incentive alignment and contractual obligations around data privacy.

**Priority 3 -- Cross-validate RPC responses:**

When the detector receives a quote that suggests a profitable opportunity, verify it against a second, independent RPC provider before executing. A manipulated quote from a single provider can cause the bot to execute a trade that appears profitable off-chain but reverts or loses money on-chain.

```python
# Conceptual: verify opportunity across multiple RPCs
quote_provider_a = get_v3_quote(rpc_a, ...)
quote_provider_b = get_v3_quote(rpc_b, ...)
if abs(quote_provider_a - quote_provider_b) / quote_provider_a > 0.01:
    logger.warning("Quote discrepancy detected, skipping opportunity")
    return None
```

**Priority 4 -- Implement RPC health monitoring:**

Track RPC response times, error rates, and block heights. If a provider falls behind by more than 2 blocks or has elevated error rates, switch to a fallback.

**Priority 5 -- Run your own node:**

For maximum security, run a dedicated RPC node per chain. This eliminates RPC provider trust entirely but has significant operational cost.

---

## 6. Threat D: Oracle and Price Manipulation

### Severity: MEDIUM

### 6.1 Attack Description

An attacker can manipulate pool prices to create fake arbitrage opportunities:

1. **Flash loan attack on pool reserves:** Attacker takes a flash loan, swaps a large amount on DEX A to move its price, waits for the bot to detect the "arbitrage opportunity," then reverses their position after the bot's trade.

2. **Low-liquidity pool manipulation:** On pairs with thin liquidity, small trades can create large price dislocations that appear to be arbitrage opportunities but are actually traps.

3. **Phantom arbitrage via stale quotes:** If the bot queries DEX A and DEX B at different block heights (due to RPC delays or caching), it may see a price difference that does not actually exist at any single point in time.

### 6.2 How the Bot Detects Opportunities

```python
# src/opportunity_detector.py, lines 266-333
def calculate_arbitrage(self, token_a, token_b, amount_in):
    # Step 1: Get V3 quote (spot price, not TWAP)
    v3_out, v3_fee = self.find_best_v3_fee(token_a, token_b, amount_in)

    # Step 2: Get V2 quote (spot price from reserves)
    v2_out = self.get_v2_quote(token_b, token_a, v3_out)

    # Step 3: Simple comparison
    profit = v2_out - amount_in
```

**Critical observation:** Both quotes use **spot prices** at the time of the `eth_call`. There is no TWAP (time-weighted average price) verification, no historical price comparison, and no liquidity depth check.

### 6.3 Vulnerability Analysis

**Spot price only (no TWAP):** The V3 `quoteExactInputSingle` returns the spot swap output based on current pool state. If an attacker manipulates the pool in the same block (or the preceding block), the bot will see a fake opportunity.

**No liquidity depth check:** The bot does not check how much liquidity is available in each pool. It uses `find_optimal_flash_loan_amount` which progressively increases trade size until slippage erodes profits, but this does not detect if the liquidity itself has been artificially inflated or deflated.

**No cross-block price verification:** The bot does not compare the current detected opportunity against historical price data to determine if the price dislocation is genuine or manipulated.

### 6.4 Current Mitigations

- `minFinalAmount` check on-chain (prevents the bot from completing a losing trade)
- Flash loan fee deduction in profit calculation
- Gas cost estimation before execution
- The `minProfit` check on-chain (contract-level)

These mitigations prevent the bot from losing the flash loan capital, but the bot will still waste gas on failed transactions caused by phantom opportunities.

### 6.5 Recommended Mitigations

**Priority 1 -- Verify quotes at execution time, not just detection time:**

The pre-execution `eth_call` simulation (line 351-358) already does this implicitly -- if the opportunity has disappeared by the time the simulation runs, the simulation will revert. However, between the simulation and the actual on-chain execution, prices can change again. This is an inherent race condition that cannot be fully eliminated but can be minimized by reducing the time between simulation and broadcast.

**Priority 2 -- Add TWAP price verification:**

For Uniswap V3 pools, use the oracle functionality (`pool.observe()`) to get the TWAP price over the last N seconds. Compare the spot price to the TWAP:

```
if abs(spot_price - twap_30s) / twap_30s > 0.05:
    # Spot price deviates >5% from 30-second TWAP
    # Likely a flash loan manipulation -- skip this opportunity
    return None
```

**Priority 3 -- Check pool liquidity depth:**

Before executing, query the pool's `liquidity()` for V3 or `getReserves()` for V2. Compare against historical averages. If liquidity has changed dramatically in the last few blocks, the pool may be under manipulation.

**Priority 4 -- Implement minimum pool size thresholds:**

Only trade on pools with sufficient liquidity (e.g., minimum $100K TVL for V2, minimum liquidity parameter for V3). This makes manipulation more expensive for the attacker.

---

## 7. Threat E: Gas Price Manipulation

### Severity: MEDIUM

### 7.1 Attack Description

**Priority Gas Auctions (PGA):** When multiple bots detect the same opportunity, they compete by bidding up the gas price. This is a well-documented phenomenon in MEV research. The bot that pays the highest gas price gets included first and captures the arbitrage profit. The losing bots pay gas for failed transactions.

**Gas griefing:** A competing bot can intentionally push gas prices up on Polygon (by submitting high-gas transactions) to make the bot's trades unprofitable, then capture the opportunity at a lower gas price after the bot's `max_gas_price_gwei` check causes it to skip the opportunity.

### 7.2 Current Gas Strategy

```python
# src/flash_loan_orchestrator.py, lines 286-289
base_fee = latest_block.get('baseFeePerGas', self.web3.eth.gas_price)
max_priority = self.web3.to_wei(2, 'gwei')  # FIXED 2 gwei priority
max_fee = gas_price or (base_fee * 2 + max_priority)

# src/utils/gas_optimizer.py, lines 70-76
if urgency == "low":
    priority_fee = 1000000000   # 1 gwei
elif urgency == "high":
    priority_fee = 3000000000   # 3 gwei
else:
    priority_fee = 2000000000   # 2 gwei
```

**Problems:**

1. **Static priority fee:** A fixed 2 gwei priority fee does not adapt to network congestion or competition. On Polygon, priority fees during high-activity periods can spike to 30-100 gwei. On Arbitrum, the sequencer FCFS model means priority fee is less relevant, but timely submission matters.

2. **No dynamic adjustment:** The gas optimizer has urgency levels but uses fixed multipliers (0.8x, 1.0x, 1.2x, 1.5x). It does not monitor pending transaction competition or adjust based on the expected profit of the trade.

3. **No gas ceiling relative to profit:** The bot checks `max_gas_price_gwei` (default 100) as a hard ceiling but does not dynamically compute whether gas cost would consume the expected profit.

4. **`baseFee * 2` over-estimation:** Setting `maxFeePerGas = baseFee * 2 + priority` means the bot is willing to pay up to 2x the current base fee. On Polygon where base fees can spike, this could result in paying far more gas than necessary.

### 7.3 Current Mitigations

- `max_gas_price_gwei` hard ceiling (default 100 gwei) in the detector
- Gas cost is deducted from profit calculations before declaring an opportunity profitable
- The `GasOptimizer` class exists but uses static values

### 7.4 Recommended Mitigations

**Priority 1 -- Dynamic priority fee based on expected profit:**

```python
# Set priority fee as a fraction of expected profit
max_acceptable_gas_cost = expected_profit_wei * 0.30  # Max 30% of profit to gas
gas_limit = estimated_gas  # ~500K gas
max_priority = max_acceptable_gas_cost // gas_limit
max_priority = min(max_priority, max_cap_gwei)  # Safety cap
```

**Priority 2 -- Monitor pending transaction pool for competition:**

Use `txpool_content` or `txpool_status` RPC calls (where available) to check if competing transactions are targeting the same pools. If competition is detected, either increase gas or skip the opportunity.

**Priority 3 -- Chain-specific gas strategy:**

| Chain | Gas Strategy |
|-------|-------------|
| Polygon | EIP-1559 with dynamic priority fee based on recent blocks' priority fee percentiles. Use `eth_feeHistory` to get the 25th/50th/75th percentile priority fees. |
| Arbitrum | Fixed low priority fee is fine (sequencer is FCFS, priority fee has minimal effect). Focus on submission speed. |
| Optimism | Same as Arbitrum. |
| Base | Same as Arbitrum. |

**Priority 4 -- Implement gas cost guardrails:**

Before signing any transaction, verify:
```python
gas_cost_usd = (gas_limit * effective_gas_price) / 1e18 * native_token_price_usd
if gas_cost_usd > expected_profit_usd * 0.50:
    logger.warning("Gas cost exceeds 50% of expected profit, skipping")
    return None
```

---

## 8. Threat F: Nonce and Replay Attacks

### Severity: LOW

### 8.1 Attack Description

**Cross-chain replay:** A transaction signed for one chain could potentially be replayed on another chain if chain IDs are not enforced.

**Nonce management issues:** If the bot attempts to send multiple transactions concurrently (or retries a failed transaction), incorrect nonce management can lead to:
- Transaction stuck in mempool (nonce gap)
- Transaction replaced unintentionally (same nonce, higher gas)
- Lost gas on reverted transactions

### 8.2 Current Implementation

**EIP-155 chain ID protection:**
```python
# src/flash_loan_orchestrator.py, line 300
'chainId': self.web3.eth.chain_id
```
The `chainId` is included in the transaction, providing EIP-155 replay protection. This is correctly implemented.

**Nonce management:**
```python
# src/flash_loan_orchestrator.py, line 296
'nonce': self.web3.eth.get_transaction_count(self.address, 'pending')

# src/utils/transaction_manager.py, lines 40-62
async def get_next_nonce(self) -> int:
    async with self._nonce_lock:
        pending_nonce = self.web3.eth.get_transaction_count(self.account, "pending")
        if self._pending_nonces:
            tracked_max = max(self._pending_nonces)
            nonce = max(pending_nonce, tracked_max + 1)
        else:
            nonce = pending_nonce
        self._pending_nonces.add(nonce)
        return nonce
```

**Issues:**

1. The orchestrator uses `'pending'` nonce count directly (line 296), which is correct for single-threaded execution but could race with the `TransactionManager`'s nonce tracking if both are used simultaneously.

2. The `TransactionManager` has an `asyncio.Lock` for nonce management, but the main orchestrator does not use the `TransactionManager` -- it manages nonces directly. This creates two independent nonce management systems.

3. There is no nonce-stuck recovery mechanism. If a transaction gets stuck in the mempool (e.g., gas too low), there is no logic to bump the gas price and resubmit with the same nonce.

### 8.3 Current Mitigations

- EIP-155 chain ID is correctly included in all transactions
- `TransactionManager` has async lock-based nonce tracking (but is not used by the orchestrator)
- Single-threaded execution in the default `direct_execution` mode prevents most race conditions

### 8.4 Recommended Mitigations

**Priority 1 -- Unify nonce management:**

The orchestrator should use the `TransactionManager` for all transaction building instead of managing nonces directly. Currently there are two code paths:
- `FlashLoanOrchestrator.build_transaction()` manages nonce at line 296
- `TransactionManager.build_transaction()` manages nonce at line 95
- `FlashLoanArbitrageContract.execute_arbitrage()` manages nonce at line 186

All three should be consolidated into a single nonce manager.

**Priority 2 -- Implement nonce-stuck recovery:**

If a transaction has been pending for more than 30 seconds, submit a replacement transaction with the same nonce but higher gas:

```python
# Conceptual: nonce stuck recovery
if time.time() - tx_submit_time > 30:
    # Resubmit with 20% higher gas
    replacement_tx = original_tx.copy()
    replacement_tx['maxFeePerGas'] = int(original_tx['maxFeePerGas'] * 1.2)
    replacement_tx['maxPriorityFeePerGas'] = int(original_tx['maxPriorityFeePerGas'] * 1.2)
    web3.eth.send_raw_transaction(sign(replacement_tx))
```

**Priority 3 -- Add cancellation capability:**

If the opportunity has disappeared while the transaction is pending, submit a zero-value self-transfer with the same nonce to cancel the stuck transaction (paying only gas, not executing the trade).

---

## 9. Threat G: Block Reorganization Risks

### Severity: LOW-MEDIUM (chain-dependent)

### 9.1 Attack Description

A block reorganization occurs when a blockchain's consensus mechanism causes one or more recently confirmed blocks to be replaced by an alternative chain. If the bot's arbitrage transaction was included in a reorganized-out block:

1. The trade is effectively reversed (as if it never happened)
2. The opportunity may no longer exist in the new chain tip
3. The bot's database records the trade as successful, but the funds never moved
4. The bot's P&L tracking becomes inaccurate

### 9.2 Chain-Specific Reorg Risk

| Chain | Finality Model | Reorg Risk | Typical Finality |
|-------|---------------|------------|-----------------|
| **Polygon** | Probabilistic (Bor + Heimdall) | **MEDIUM** | ~128 blocks (~4 minutes) for Heimdall checkpoint. 1-2 block reorgs are common. |
| **Arbitrum** | Sequencer + L1 confirmation | **LOW** | Sequencer provides soft finality instantly. Full finality after L1 posting (~15 minutes). |
| **Optimism** | Sequencer + L1 confirmation | **LOW** | Same as Arbitrum. Challenge period for fraud proofs is 7 days. |
| **Base** | Sequencer + L1 confirmation | **LOW** | Same as Optimism. |

### 9.3 Current Implementation

```python
# src/flash_loan_orchestrator.py, line 384
receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

# Line 387-393: immediately records profit on first confirmation
if receipt['status'] == 1:
    result['success'] = True
    result['profit'] = opportunity['net_profit']
```

**Problem:** The bot records success immediately upon receiving the transaction receipt (1 confirmation). On Polygon, 1 confirmation provides no reorg protection. Even on L2s, 1 confirmation only provides sequencer-level finality, not L1-level finality.

### 9.4 Current Mitigations

None. The bot does not wait for additional confirmations, does not check for reorgs, and does not reconcile its database against on-chain state.

### 9.5 Recommended Mitigations

**Priority 1 -- Wait for safe confirmation count before recording profit:**

| Chain | Recommended Confirmations |
|-------|--------------------------|
| Polygon | 10 blocks (~20 seconds) |
| Arbitrum | 1 block (sequencer soft finality) |
| Optimism | 1 block (sequencer soft finality) |
| Base | 1 block (sequencer soft finality) |

**Priority 2 -- Implement post-trade reconciliation:**

After a configurable delay (e.g., 5 minutes), re-query the transaction receipt and verify:
- Transaction still exists in the canonical chain
- Block hash has not changed
- Transaction status is still `1`

If any check fails, flag the trade as "REORGED" in the database and adjust P&L.

**Priority 3 -- Use `eth_getBlockByNumber('finalized')` where available:**

Some chains support querying the finalized block number. Only consider trades truly confirmed when the block containing the trade is at or before the finalized block.

---

## 10. Cross-Cutting Concerns

### 10.1 Private Key Exposure

The private key is loaded from an environment variable and held in memory for the lifetime of the process:

```python
# src/flash_loan_orchestrator.py, line 66
self.account = Account.from_key(private_key)
```

If the bot process is compromised (e.g., via a dependency supply chain attack, RPC response injection, or server breach), the private key can be extracted. Since this key is the `onlyOwner` of the FlashLoanArbitrageV2 contract, compromise gives the attacker full control over the contract, including:
- Executing arbitrary trades
- Withdrawing all profits via `withdrawProfits` or `emergencyWithdraw`
- Registering malicious adapters via `setAdapter`
- Pausing/unpausing the contract

**Mitigation:** Consider a multi-sig or time-locked ownership model for the contract. For the bot's operational key, consider using a hardware wallet or AWS KMS for signing (not a raw key in environment variables).

### 10.2 Smart Contract Risk: Adapter Trust Model

The FlashLoanArbitrageV2 contract transfers tokens to adapter contracts and trusts them to return the swap output:

```solidity
// FlashLoanArbitrageV2.sol, lines 202-219
IERC20(step.tokenIn).safeTransfer(step.adapter, currentAmount);
try IDEXAdapter(step.adapter).swapDirect(...) returns (uint256 amountOut) {
    currentAmount = amountOut;
}
```

If a malicious adapter is registered (via a compromised owner key), it could steal all flash-loaned funds. The `registeredAdapters` mapping provides access control, but it relies entirely on the `onlyOwner` modifier.

**Mitigation:** Consider an adapter registration timelock -- require a 24-hour delay between registering a new adapter and being able to use it. This gives the operator time to detect and respond to unauthorized adapter registrations.

### 10.3 Database Integrity

The bot records opportunities, transactions, and trade results to a PostgreSQL database. This database is the source of truth for P&L tracking, but it can become inconsistent with on-chain state due to:
- Reorgs (discussed in Threat G)
- Bot crashes between transaction submission and receipt processing
- Database connection failures during logging

**Mitigation:** Implement a periodic reconciliation job that compares database trade records against on-chain transaction receipts and adjusts the database accordingly.

### 10.4 Timing Attack on Opportunity Detection

The bot's scan interval is fixed and predictable:

```python
# src/opportunity_detector.py, line 668
time.sleep(self.check_interval)  # Default: 5 seconds
```

A competing bot that knows this interval can predict exactly when the bot will submit its next trade and position itself accordingly.

**Mitigation:** Add random jitter to the scan interval:
```python
import random
jitter = random.uniform(-1.0, 1.0)
time.sleep(max(1, self.check_interval + jitter))
```

---

## 11. Chain-Specific Analysis

### 11.1 Polygon (Chain ID: 137)

**MEV Landscape:** Polygon has one of the most competitive MEV environments. Numerous sandwich bots, frontrunners, and backrunners monitor the public mempool. The Bor consensus allows validators to reorder transactions within blocks.

**Key Risks:**
- CRITICAL: Public mempool broadcast exposes every transaction
- HIGH: Active sandwich bot ecosystem will extract maximum value from 5% slippage tolerance
- MEDIUM: 1-2 block reorgs are common

**Recommended Configuration:**
```
Tx submission:     Flashbots Protect or MEV Blocker (MANDATORY)
Slippage:          0.3% (stable pairs), 0.8% (volatile pairs)
Deadline:          60 seconds
Gas priority fee:  Dynamic (eth_feeHistory 75th percentile)
Confirmations:     10 blocks before recording profit
```

### 11.2 Arbitrum (Chain ID: 42161)

**MEV Landscape:** Arbitrum uses a centralized sequencer with FCFS ordering. There is no public mempool in the traditional sense. The sequencer processes transactions in the order they are received. MEV extraction is limited compared to Polygon but not eliminated -- the sequencer operator and the RPC infrastructure can still observe and act on transaction flow.

**Key Risks:**
- MEDIUM: RPC provider can still see and potentially front-run transactions
- LOW: Sequencer-based FCFS ordering limits traditional sandwich attacks
- LOW: L2 reorg risk is minimal (sequencer provides soft finality)

**Recommended Configuration:**
```
Tx submission:     Standard Arbitrum RPC (sequencer endpoint)
Slippage:          0.5% (stable pairs), 1.0% (volatile pairs)
Deadline:          30 seconds
Gas priority fee:  1 gwei (minimal, FCFS ordering)
Confirmations:     1 block (sequencer finality sufficient for operational purposes)
```

### 11.3 Optimism (Chain ID: 10)

**MEV Landscape:** Similar to Arbitrum. OP Stack sequencer uses FCFS ordering. The sequencer is currently centralized and operated by the Optimism Foundation. There is ongoing work on decentralizing the sequencer.

**Key Risks:**
- MEDIUM: Centralized sequencer has theoretical power to reorder or censor
- LOW: No public mempool, limited traditional MEV
- LOW: L2 reorg risk is minimal

**Recommended Configuration:**
```
Tx submission:     Standard Optimism RPC
Slippage:          0.5% (stable pairs), 1.0% (volatile pairs)
Deadline:          30 seconds
Gas priority fee:  1 gwei (minimal)
Confirmations:     1 block
```

### 11.4 Base (Chain ID: 8453)

**MEV Landscape:** Same as Optimism (OP Stack). Sequencer operated by Coinbase. Coinbase has strong regulatory incentives not to engage in MEV extraction, but the technical capability exists.

**Key Risks:**
- LOW-MEDIUM: Coinbase sequencer is trusted but centralized
- LOW: No public mempool
- LOW: L2 reorg risk is minimal

**Recommended Configuration:**
```
Tx submission:     Standard Base RPC
Slippage:          0.5% (stable pairs), 1.0% (volatile pairs)
Deadline:          30 seconds
Gas priority fee:  1 gwei (minimal)
Confirmations:     1 block
```

---

## 12. Prioritized Mitigation Roadmap

### Phase 1: CRITICAL -- Implement Before Any Live Trading

| # | Mitigation | Effort | Impact |
|---|-----------|--------|--------|
| 1.1 | **Private tx submission on Polygon** (Flashbots Protect or MEV Blocker) | Low (config change + library) | Eliminates sandwich attacks on Polygon |
| 1.2 | **Reduce slippage from 5% to 0.3-1.0%** per pair | Low (config change) | Reduces sandwich extraction by 5-15x |
| 1.3 | **Reduce deadline from 300s to 30-60s** per chain | Low (config change) | Reduces attack window |
| 1.4 | **Use paid/authenticated RPC providers** | Low (account setup) | Reduces information leakage |

### Phase 2: HIGH -- Implement Within First Week of Operation

| # | Mitigation | Effort | Impact |
|---|-----------|--------|--------|
| 2.1 | Separate read/write RPC providers | Medium | Prevents RPC-level front-running |
| 2.2 | Dynamic priority fee based on expected profit | Medium | Improves gas efficiency |
| 2.3 | Batch detection queries with Multicall | Medium | Reduces latency and RPC fingerprint |
| 2.4 | Unify nonce management into TransactionManager | Medium | Prevents nonce-related failures |
| 2.5 | Add random jitter to scan interval | Low | Reduces predictability |

### Phase 3: MEDIUM -- Implement Within First Month

| # | Mitigation | Effort | Impact |
|---|-----------|--------|--------|
| 3.1 | TWAP price verification for opportunity validation | High | Detects flash loan manipulation |
| 3.2 | Pool liquidity depth checks | Medium | Avoids low-liquidity traps |
| 3.3 | Cross-provider quote verification | Medium | Detects RPC manipulation |
| 3.4 | Post-trade reconciliation job | Medium | Detects reorg-induced DB inconsistency |
| 3.5 | Nonce-stuck recovery and transaction cancellation | Medium | Prevents gas waste on stuck txs |

### Phase 4: LOW -- Implement As Resources Allow

| # | Mitigation | Effort | Impact |
|---|-----------|--------|--------|
| 4.1 | Run dedicated RPC nodes per chain | High (ops cost) | Eliminates RPC trust entirely |
| 4.2 | Adapter registration timelock | Medium (contract change) | Limits adapter compromise window |
| 4.3 | Hardware wallet / KMS for tx signing | Medium | Protects private key at rest |
| 4.4 | Multi-sig contract ownership | High (contract change) | Prevents single-key compromise |
| 4.5 | Dynamic slippage from SlippageProtection integration | Medium | Optimal per-trade protection |

---

## 13. Appendix: Code References

### Files Analyzed

| File | Path | Lines | Role |
|------|------|-------|------|
| Flash Loan Orchestrator | `/src/flash_loan_orchestrator.py` | 630 | Transaction building, signing, broadcasting |
| Opportunity Detector | `/src/opportunity_detector.py` | 697 | Price monitoring, opportunity detection |
| Main Bot Runner | `/run_bot.py` | 410 | Main loop, component orchestration |
| FlashLoanArbitrageV2 | `/contracts/FlashLoanArbitrageV2.sol` | 343 | On-chain flash loan execution |
| FlashLoanArbitrage V1 | `/contracts/FlashLoanArbitrage.sol` | 416 | Earlier version (reference) |
| Gas Optimizer | `/src/utils/gas_optimizer.py` | 170 | Gas pricing strategy |
| Risk Manager | `/src/utils/risk_manager.py` | 710 | Position sizing, loss limits, circuit breaker |
| Slippage Protection | `/src/utils/slippage_protection.py` | 338 | Slippage calculation (not integrated) |
| Transaction Manager | `/src/utils/transaction_manager.py` | 332 | Nonce management, tx retry logic |
| Emergency Shutdown | `/src/utils/emergency_shutdown.py` | 445 | Emergency stop procedures |
| Multicall | `/src/utils/multicall.py` | 203 | Batch RPC calls (not integrated) |
| Price Cache | `/src/utils/price_cache.py` | 119 | Quote caching (not integrated) |
| Config | `/src/config.py` | 185 | Chain and application configuration |
| Contract Interface | `/src/flash_loan/contract_interface.py` | 326 | Web3 contract wrapper |
| UniswapV3Adapter | `/contracts/adapters/UniswapV3Adapter.sol` | 212 | V3 swap adapter |
| UniswapV2Adapter | `/contracts/adapters/UniswapV2Adapter.sol` | 241 | V2 swap adapter |

### Key Vulnerability Summary

```
CRITICAL:
  - flash_loan_orchestrator.py:379  -> send_raw_transaction (public mempool)
  - flash_loan_orchestrator.py:185  -> 5% slippage tolerance

HIGH:
  - flash_loan_orchestrator.py:351  -> eth_call simulation visible to RPC
  - opportunity_detector.py:176-265 -> sequential quote pattern fingerprint
  - .env.example:3-9               -> public free RPC endpoints

MEDIUM:
  - flash_loan_orchestrator.py:271  -> 300s deadline
  - flash_loan_orchestrator.py:288  -> static 2 gwei priority fee
  - opportunity_detector.py:266-333 -> spot price only, no TWAP

LOW:
  - flash_loan_orchestrator.py:296  -> nonce from 'pending' (race potential)
  - flash_loan_orchestrator.py:384  -> 1-confirmation profit recording
  - run_bot.py:237-239             -> threaded mode has no shared nonce lock
```

---

**End of MEV / Adversarial Security Threat Model Report**
