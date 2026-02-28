# Security Audit Report: MEV, Price Manipulation, and Front-Running

**Auditor**: Agent 4 (Security Audit Swarm)
**Scope**: Price Manipulation, MEV, and Front-Running
**Date**: 2026-02-27
**Contracts Audited**:
- `contracts/FlashLoanArbitrage.sol`
- `contracts/FlashLoanArbitrageV2.sol`
- `contracts/FlashLoanLiquidator.sol`
- `contracts/BalancerFlashLoan.sol`
- `contracts/libraries/DEXLibrary.sol`
- `contracts/adapters/UniswapV2Adapter.sol`
- `contracts/adapters/UniswapV3Adapter.sol`
- `contracts/adapters/CurveAdapter.sol`
- `contracts/interfaces/IDEXAdapter.sol`

---

## Executive Summary

This audit focuses on MEV (Maximal Extractable Value) exposure, front-running vectors, sandwich attack susceptibility, price manipulation risks, and deadline/oracle weaknesses across the flash loan arbitrage codebase. The contracts are designed for owner-only operation, which reduces the attack surface compared to publicly callable DeFi protocols. However, fundamental MEV risks remain because all transactions -- including owner transactions -- are visible in the public mempool before inclusion in a block, and several on-chain design choices amplify these risks.

**Findings Summary**:

| Severity | Count |
|----------|-------|
| CRITICAL | 2     |
| HIGH     | 5     |
| MEDIUM   | 5     |
| LOW      | 3     |
| INFO     | 3     |
| **Total** | **18** |

---

## CRITICAL Findings

### C-01: Zero `sqrtPriceLimitX96` Allows Unlimited Price Impact on Uniswap V3 Swaps

**Severity**: CRITICAL
**Affected Contracts**:
- `contracts/adapters/UniswapV3Adapter.sol` (line 164)
- `contracts/libraries/DEXLibrary.sol` (line 97)

**Description**:
Both the `UniswapV3Adapter.swapDirect()` and `DEXLibrary.swapUniswapV3()` set `sqrtPriceLimitX96: 0` in the `ExactInputSingleParams` struct. In Uniswap V3, setting this parameter to `0` is equivalent to setting it to `TickMath.MIN_SQRT_RATIO + 1` (for token0-to-token1 swaps) or `TickMath.MAX_SQRT_RATIO - 1` (for token1-to-token0 swaps). This means the swap will execute across arbitrarily many tick ranges with no price boundary.

**Attack Scenario**:
1. Attacker observes a pending `executeArbitrage()` transaction in the mempool with a large `amountIn` targeting a Uniswap V3 pool.
2. Attacker front-runs with a large swap that moves the pool price significantly in the same direction the arbitrage contract will trade.
3. Because `sqrtPriceLimitX96 = 0`, the arbitrage contract's swap executes at the now-unfavorable manipulated price, crossing many ticks and receiving far fewer tokens than expected.
4. Attacker back-runs to reverse their position, profiting from the price impact inflicted on the arbitrage contract.
5. While `minAmountOut` per step provides a floor, the absence of a price limit means the swap can fill at extreme prices within a single tick transition before reverting, making it easier for a sophisticated MEV searcher to calibrate the sandwich precisely to the `minAmountOut` threshold.

**Code Reference (UniswapV3Adapter.sol, lines 156-165)**:
```solidity
ISwapRouter.ExactInputSingleParams memory params = ISwapRouter.ExactInputSingleParams({
    tokenIn: tokenIn,
    tokenOut: tokenOut,
    fee: fee,
    recipient: recipient,
    deadline: deadline,
    amountIn: amountIn,
    amountOutMinimum: minAmountOut,
    sqrtPriceLimitX96: 0   // <-- NO PRICE LIMIT
});
```

**Code Reference (DEXLibrary.sol, lines 88-98)**:
```solidity
IUniswapV3Router.ExactInputSingleParams memory params = IUniswapV3Router
    .ExactInputSingleParams({
        tokenIn: tokenIn,
        tokenOut: tokenOut,
        fee: fee,
        recipient: address(this),
        deadline: deadline,
        amountIn: amountIn,
        amountOutMinimum: minAmountOut,
        sqrtPriceLimitX96: 0 // No price limit
    });
```

**Recommended Fix**:
1. Calculate a reasonable `sqrtPriceLimitX96` based on the expected price and acceptable deviation. Pass it as a parameter through the `data` field or as an additional struct member.
2. At minimum, compute the price limit as `currentSqrtPrice * (1 - maxSlippageBps / 10000)` before executing the swap.
3. Consider using Uniswap V3's `quoteExactInputSingle` to pre-compute the expected price and derive a limit.

```solidity
// Example fix: accept sqrtPriceLimitX96 in data alongside fee
(uint24 fee, uint160 priceLimit) = abi.decode(data, (uint24, uint160));

ISwapRouter.ExactInputSingleParams memory params = ISwapRouter.ExactInputSingleParams({
    // ...
    sqrtPriceLimitX96: priceLimit  // Enforce price boundary
});
```

---

### C-02: Zero `minAmountOut` Per-Swap Step in V1 Contract Allows Complete Value Extraction

**Severity**: CRITICAL
**Affected Contract**: `contracts/FlashLoanArbitrage.sol` (line 258)

**Description**:
In `FlashLoanArbitrage._executeSwaps()`, each individual swap call passes `0` as `minAmountOut`:

```solidity
currentAmount = _swapOnDEX(
    dexRouter,
    tokenIn,
    tokenOut,
    currentAmount,
    0, // minAmountOut calculated per swap  <-- HARDCODED ZERO
    params.deadline
);
```

The comment says "calculated per swap" but the actual value is `0`. While the overall `params.minAmountOut` is checked after all swaps complete (line 267), each intermediate swap has zero slippage protection. This means an attacker can sandwich any individual swap step to extract maximum value, as long as the cumulative output still exceeds `params.minAmountOut`.

**Attack Scenario**:
In a 3-step arbitrage (A -> B -> C -> A), an attacker can heavily sandwich the A -> B swap, extracting most of the value. Even if the B -> C and C -> A swaps execute normally, the overall amount may be just above `minAmountOut` (which the attacker can calculate precisely from the calldata), capturing the majority of the arbitrage profit.

**Note**: The V1 contract's `_swapOnDEX` currently reverts with "not implemented", but this is a design flaw that would be critical when implemented.

**Recommended Fix**:
Calculate a per-step `minAmountOut` for each swap based on expected intermediate prices and the overall `maxSlippageBps`. The V2 contract already addresses this with per-step `minAmountOut` in the `SwapStep` struct.

---

## HIGH Findings

### H-01: Public Mempool Exposure Enables Sandwich Attacks Despite `onlyOwner`

**Severity**: HIGH
**Affected Contracts**: All execution contracts
- `contracts/FlashLoanArbitrage.sol` (line 120)
- `contracts/FlashLoanArbitrageV2.sol` (line 112)
- `contracts/BalancerFlashLoan.sol` (line 121)
- `contracts/FlashLoanLiquidator.sol` (line 100)

**Description**:
All `executeArbitrage()` and `executeLiquidation()` functions are `onlyOwner`, which prevents unauthorized callers. However, the `onlyOwner` modifier does NOT protect against sandwich attacks. When the owner submits a transaction to the public mempool, the entire calldata is visible, including:
- The exact token path and amounts (`ArbitrageParams` / `LiquidationParams`)
- The DEX routers/adapters being used
- The `minAmountOut` / `minFinalAmount` values
- The deadline

A MEV searcher can decode this calldata, simulate the arbitrage, and construct a precisely calibrated sandwich attack that pushes the price exactly to the `minAmountOut` threshold, capturing most of the expected profit.

**Attack Scenario**:
1. Owner submits `executeArbitrage()` with `flashLoanAmount = 100 WETH`, targeting a USDC/WETH price discrepancy between Uniswap V2 and SushiSwap.
2. MEV bot decodes the calldata, sees `minFinalAmount = 100.05 WETH` (expecting 0.5 WETH profit).
3. Bot front-runs: buys WETH on the cheaper DEX, moving the price up.
4. Owner's arb executes at worse prices, getting ~100.05 WETH (barely above minimum).
5. Bot back-runs: sells WETH on the now-more-expensive DEX, pocketing ~0.45 WETH.
6. Owner gets 0.05 WETH profit instead of 0.5 WETH -- the bot extracted 90% of the value.

**Recommended Fix**:
1. **Use Flashbots Protect or MEV Blocker** to submit transactions via private mempools that bypass public mempool exposure. This is an off-chain solution and requires changes to the transaction submission infrastructure, not the contracts.
2. **Commit-reveal scheme**: Submit a commitment hash first, then reveal the arbitrage parameters in a second transaction. This adds latency but eliminates front-running on the parameters.
3. **Use Flashbots bundles** to atomically include the arb transaction with protection against reordering.
4. **Set aggressive `minFinalAmount`** close to the expected output (e.g., 99% of simulated output) so the sandwich profit margin is minimal.

---

### H-02: Absence of Price Oracle Integration Leads to Stale/Incorrect Profit Calculations

**Severity**: HIGH
**Affected Contracts**:
- `contracts/FlashLoanArbitrage.sol` (lines 216-217)
- `contracts/FlashLoanArbitrageV2.sol` (lines 233-235)
- `contracts/FlashLoanLiquidator.sol` (lines 222-225)

**Description**:
`FlashLoanArbitrage.sol` explicitly acknowledges the absence of oracle integration with the comment on line 216: `// Note: In production, convert to USD using price oracle`. The `minProfitUSD` variable name implies USD-denominated profit thresholds, but the comparison at line 217 compares raw token amounts against `minProfitUSD`:

```solidity
// Verify minimum profit threshold
// Note: In production, convert to USD using price oracle
if (profit < minProfitUSD) {
    revert InsufficientProfit(profit, minProfitUSD);
}
```

`profit` is denominated in the flash loan asset (e.g., USDC with 6 decimals, or WETH with 18 decimals), while `minProfitUSD` is described as "USD with 18 decimals". This mismatch means:
- For USDC (6 decimals): a `minProfitUSD` of `1e18` (1 USD) would require `1e18` USDC units = 1 trillion USDC -- effectively blocking all arbitrage.
- For WETH (18 decimals): a `minProfitUSD` of `1e18` would require 1 WETH of profit -- far too high for most arb opportunities at $3,000+/WETH.

The V2 contract renames this to `minProfit` (denominated in base token), which is more honest but still lacks USD conversion. Without oracle-based valuation, the system cannot enforce economically meaningful profit thresholds across different token types.

**Impact on MEV**: Without accurate USD-denominated profit checks, the system may execute arbs that are barely profitable in USD terms, making them prime targets for sandwich attacks where the attacker's cost (gas + tip) is easily offset by the extracted value.

**Recommended Fix**:
1. Integrate Chainlink price feeds to convert token-denominated profits to USD for threshold comparison.
2. Use TWAP (Time-Weighted Average Price) oracles from Uniswap V3 for on-chain price references.
3. At minimum, maintain per-token `minProfit` mappings that are set appropriately for each token's decimals and current market value.

```solidity
// Example using Chainlink
import {AggregatorV3Interface} from "@chainlink/contracts/src/v0.8/interfaces/AggregatorV3Interface.sol";

mapping(address => address) public priceFeeds; // token => Chainlink feed

function _getUSDValue(address token, uint256 amount) internal view returns (uint256) {
    AggregatorV3Interface feed = AggregatorV3Interface(priceFeeds[token]);
    (, int256 price,, uint256 updatedAt,) = feed.latestRoundData();
    require(block.timestamp - updatedAt < 3600, "Stale price");
    require(price > 0, "Invalid price");
    return (amount * uint256(price)) / (10 ** IERC20Metadata(token).decimals());
}
```

---

### H-03: Uniswap V2 Reserve Manipulation Before Arbitrage Execution

**Severity**: HIGH
**Affected Contracts**:
- `contracts/adapters/UniswapV2Adapter.sol` (lines 106-136)
- `contracts/libraries/DEXLibrary.sol` (lines 117-146)

**Description**:
Uniswap V2 uses a constant product AMM (`x * y = k`). The reserves of any Uniswap V2 pool can be manipulated within the same block by executing a large swap before the arbitrage transaction. The `UniswapV2Adapter` relies on `router.swapExactTokensForTokens()`, which calculates output based on the current reserve state at execution time, not at the time the arbitrage opportunity was identified.

**Attack Scenario**:
1. Attacker monitors for pending `executeArbitrage()` calls that route through a specific Uniswap V2 pool.
2. Attacker identifies a thin-liquidity pool in the arbitrage path.
3. Attacker front-runs with a large swap on that pool, significantly shifting the reserves and the effective exchange rate.
4. The arbitrage contract's swap executes at the manipulated reserve ratio, receiving far fewer tokens.
5. While per-step `minAmountOut` (in V2 contracts) provides some protection, the attacker can calibrate the manipulation to sit just at the threshold.
6. Attacker back-runs to restore reserves, profiting from the round-trip.

**Key Concern**: The `getQuote()` and `calculatePriceImpact()` functions (UniswapV2Adapter, lines 145-189) read current reserves. If these are used off-chain to determine `minAmountOut`, the values may be stale by the time the on-chain transaction executes (even within the same block, if another transaction executes first).

**Recommended Fix**:
1. Use commit-reveal or Flashbots to prevent front-running.
2. Implement on-chain TWAP checks to verify that the current reserve ratio is within acceptable deviation from the time-weighted average.
3. Set `minAmountOut` based on off-chain simulation with an additional safety margin (e.g., 2-5% below expected).
4. Consider checking `pair.getReserves()` within the adapter and reverting if price deviation from a reference (e.g., Chainlink) exceeds a threshold.

---

### H-04: FlashLoanLiquidator Swap Step Uses Zero `minAmountOut`

**Severity**: HIGH
**Affected Contract**: `contracts/FlashLoanLiquidator.sol` (line 188)

**Description**:
In the `executeOperation()` callback, the collateral-to-debt-token swap is executed with `0` as the `minAmountOut` parameter:

```solidity
try IDEXAdapter(liqParams.adapter).swapDirect(
    liqParams.collateralAsset,
    liqParams.debtAsset,
    collateralReceived,
    0, // min out -- we check profit below  <-- ZERO SLIPPAGE PROTECTION
    liqParams.deadline,
    address(this),
    liqParams.swapData
) returns (uint256) {
    // ok
} catch {
    revert SwapFailed();
}
```

The comment says "we check profit below", but the problem is that the profit check at line 218-225 only ensures `swapReceived >= amountOwed + liqParams.minProfit`. An attacker can sandwich the swap to extract `collateralReceived * liquidationBonus - liqParams.minProfit - flashLoanFee` worth of value, leaving the liquidator with exactly `minProfit`.

**Attack Scenario**:
1. A liquidation opportunity appears with a 5% liquidation bonus on 100 ETH of collateral (5 ETH bonus).
2. Owner submits `executeLiquidation()` with `minProfit = 0.1 ETH`.
3. MEV bot sandwiches the collateral-to-debt swap, extracting ~4.85 ETH of the 5 ETH bonus.
4. Liquidator receives 0.1 ETH profit -- the minimum acceptable.

**Recommended Fix**:
Calculate a reasonable `minAmountOut` for the swap based on the known collateral value and expected liquidation bonus, and pass it instead of `0`:

```solidity
// Calculate expected swap output based on known collateral value
uint256 expectedSwapOut = _estimateSwapOutput(collateralReceived);
uint256 minSwapOut = expectedSwapOut * (BPS_DENOMINATOR - maxSlippageBps) / BPS_DENOMINATOR;

IDEXAdapter(liqParams.adapter).swapDirect(
    liqParams.collateralAsset,
    liqParams.debtAsset,
    collateralReceived,
    minSwapOut,  // Actual slippage protection
    liqParams.deadline,
    address(this),
    liqParams.swapData
);
```

---

### H-05: Curve `exchange()` Lacks Deadline Enforcement

**Severity**: HIGH
**Affected Contract**: `contracts/adapters/CurveAdapter.sol` (lines 132-161)

**Description**:
The `CurveAdapter.swapDirect()` accepts a `deadline` parameter from the interface but never uses it. The comment on line 137 acknowledges this: `deadline Transaction deadline (unused by Curve, kept for interface)`. The Curve `ICurvePool.exchange()` function does not accept a deadline parameter natively.

```solidity
function swapDirect(
    address tokenIn,
    address tokenOut,
    uint256 amountIn,
    uint256 minAmountOut,
    uint256 deadline,      // <-- ACCEPTED BUT NEVER USED
    address recipient,
    bytes calldata data
) external onlyAuthorized returns (uint256 amountOut) {
    PoolInfo memory info = _getPool(tokenIn, tokenOut);
    IERC20(tokenIn).forceApprove(info.pool, amountIn);
    // No deadline check here!
    amountOut = ICurvePool(info.pool).exchange(
        info.indexA, info.indexB, amountIn, minAmountOut
    );
```

Without deadline enforcement, a Curve swap step can be held by a validator/builder and executed at a later time when the price has moved unfavorably. This is particularly dangerous for Curve stableswap pools, where a de-peg event could occur between transaction submission and execution.

**Recommended Fix**:
Add an explicit deadline check at the beginning of `swapDirect()`:

```solidity
function swapDirect(...) external onlyAuthorized returns (uint256 amountOut) {
    require(block.timestamp <= deadline, "CurveAdapter: deadline expired");
    // ... rest of function
}
```

---

## MEDIUM Findings

### M-01: `maxSlippageBps` Is Stored But Never Used On-Chain

**Severity**: MEDIUM
**Affected Contracts**:
- `contracts/FlashLoanArbitrage.sol` (lines 37-38, 323-328)
- `contracts/FlashLoanArbitrageV2.sol` (lines 32-33, 270-273)
- `contracts/BalancerFlashLoan.sol` (lines 54-55, 253-256)

**Description**:
All three arbitrage contracts define a `maxSlippageBps` state variable and provide a setter function (`setMaxSlippage()`), but the variable is never referenced in any swap execution logic. The actual slippage protection is provided solely by `minAmountOut` per step (V2) or `params.minAmountOut` overall (V1).

This means `maxSlippageBps` exists only as a governance parameter with no on-chain enforcement. The off-chain bot is presumably responsible for using this value to calculate `minAmountOut`, but if the bot is compromised or misconfigured, there is no on-chain safety net.

**Impact**: The owner can set `maxSlippageBps` to any value up to 1000 (10%) with `setMaxSlippage()`. Even at 10%, this represents significant value leakage on large flash loans. More importantly, since the value is never enforced on-chain, it provides a false sense of security.

**Recommended Fix**:
Either:
1. Remove `maxSlippageBps` to avoid confusion, documenting that slippage is controlled entirely via `minAmountOut`/`minFinalAmount` parameters.
2. OR enforce it on-chain by computing the expected output and verifying that actual slippage does not exceed `maxSlippageBps`:

```solidity
// In _executeSwaps or executeOperation:
uint256 maxAcceptableSlippage = (params.flashLoanAmount * maxSlippageBps) / BPS_DENOMINATOR;
require(
    currentAmount >= params.flashLoanAmount - maxAcceptableSlippage,
    "Slippage exceeds maxSlippageBps"
);
```

---

### M-02: `block.timestamp` Deadline Is Validator-Manipulable

**Severity**: MEDIUM
**Affected Contracts**: All contracts using `block.timestamp > deadline`
- `contracts/FlashLoanArbitrage.sol` (line 127)
- `contracts/FlashLoanArbitrageV2.sol` (line 120)
- `contracts/BalancerFlashLoan.sol` (line 129)
- `contracts/FlashLoanLiquidator.sol` (line 108)

**Description**:
All contracts check `block.timestamp > params.deadline` to prevent stale transactions from executing. However, `block.timestamp` is set by the block proposer (validator on PoS Ethereum) and can be manipulated within the allowed range.

Post-merge Ethereum uses fixed 12-second slots, so `block.timestamp` is deterministic for a given slot. However, the validator choosing which transactions to include in a block can:
1. **Delay inclusion**: Hold the transaction for future blocks where the timestamp is still within the deadline, but market conditions have changed.
2. **Reorder within a block**: The validator can place the arbitrage transaction after their own sandwich transactions while the deadline is still valid.

The deadline check uses strict greater-than (`>`), meaning a transaction with `deadline == block.timestamp` will still execute. This is correct behavior but means the deadline must be set tightly to be effective.

**Impact**: Low to medium. Post-merge, timestamp manipulation is minimal (no drift allowed beyond slot time). The primary risk is transaction delay by validators who are also MEV extractors.

**Recommended Fix**:
1. Set deadlines aggressively tight (current block + 1-2 blocks, i.e., 12-24 seconds).
2. Consider using block number-based deadlines instead of timestamp for more predictable behavior.
3. This is primarily an off-chain concern -- ensure the transaction submission bot sets short deadlines.

---

### M-03: No On-Chain Maximum for `minProfit` Can Be Set to Zero

**Severity**: MEDIUM
**Affected Contracts**:
- `contracts/FlashLoanArbitrage.sol` (lines 313-317)
- `contracts/FlashLoanArbitrageV2.sol` (lines 260-264)
- `contracts/FlashLoanLiquidator.sol` (lines 245-249)

**Description**:
The `setMinProfit()` functions have no lower bound validation. The owner can set `minProfit` to `0`, which effectively disables the profit threshold check. While this is an owner-controlled action, it removes a critical safety check that prevents the contract from executing unprofitable or barely-profitable trades.

With `minProfit = 0`, the contract would execute any trade where `finalAmount > amountOwed`, even by 1 wei. Such trades are trivially sandwichable because the attacker only needs to leave 1 wei of profit.

Additionally, in `FlashLoanLiquidator`, the `LiquidationParams` struct contains its own `minProfit` field (line 64), which is independent of the contract-level `minProfit`. The contract-level `minProfit` is never checked in the liquidator's `executeOperation()` -- only `liqParams.minProfit` is checked (line 223). This means the contract-level `minProfit` is dead code in the liquidator.

**Recommended Fix**:
1. Add a minimum threshold for `minProfit`:
```solidity
function setMinProfit(uint256 _minProfit) external onlyOwner {
    require(_minProfit >= MIN_PROFIT_FLOOR, "Profit too low");
    // ...
}
```
2. In `FlashLoanLiquidator`, enforce the contract-level `minProfit` as a floor for `liqParams.minProfit`:
```solidity
require(liqParams.minProfit >= minProfit, "Per-call minProfit below contract minimum");
```

---

### M-04: DEXLibrary `executeSwap()` Hardcodes Fee Tier to `FEE_MEDIUM` for V3

**Severity**: MEDIUM
**Affected Contract**: `contracts/libraries/DEXLibrary.sol` (lines 168-178)

**Description**:
The `DEXLibrary.executeSwap()` function hardcodes the Uniswap V3 fee tier to `FEE_MEDIUM` (3000 = 0.3%):

```solidity
if (dexType == DEXType.UNISWAP_V3) {
    amountOut = swapUniswapV3(
        router, tokenIn, tokenOut, amountIn, minAmountOut,
        FEE_MEDIUM,  // <-- HARDCODED TO 0.3% FEE TIER
        deadline
    );
}
```

This has two implications:
1. **Suboptimal routing**: If the best liquidity for a token pair is in the 0.05% or 1% fee tier pools, the swap will execute in the 0.3% pool with worse pricing or potentially fail.
2. **MEV amplification**: The 0.3% fee tier pools for major pairs (WETH/USDC, etc.) are heavily monitored by MEV bots. Using the 0.05% tier or routing through less-monitored pools could reduce MEV exposure.

**Recommended Fix**:
Accept the fee tier as a parameter:

```solidity
function executeSwap(
    DEXType dexType,
    address router,
    address tokenIn,
    address tokenOut,
    uint256 amountIn,
    uint256 minAmountOut,
    uint256 deadline,
    uint24 feeTier  // Add this parameter
) internal returns (uint256 amountOut) {
    if (dexType == DEXType.UNISWAP_V3) {
        amountOut = swapUniswapV3(
            router, tokenIn, tokenOut, amountIn, minAmountOut,
            feeTier, deadline
        );
    }
    // ...
}
```

**Note**: The V2 adapter pattern in `UniswapV3Adapter.sol` correctly accepts the fee tier via the `data` parameter, so this issue is specific to the `DEXLibrary` which appears to be a V1 artifact.

---

### M-05: Balancer Flash Loan Callback Lacks Reentrancy Guard

**Severity**: MEDIUM
**Affected Contract**: `contracts/BalancerFlashLoan.sol` (lines 167-236)

**Description**:
The `BalancerFlashLoan.receiveFlashLoan()` callback function does not have the `nonReentrant` modifier. While `executeArbitrage()` has `nonReentrant`, the callback is a separate function called by the Balancer Vault. The Balancer Vault itself is trusted to call the callback only once per flash loan, but the callback internally calls external contracts (DEX adapters) that could potentially re-enter.

By contrast, `FlashLoanArbitrageV2.executeOperation()` is protected indirectly because it is called within the same transaction as `executeArbitrage()` (which holds the reentrancy lock). The same applies to `FlashLoanArbitrage.executeOperation()`. However, `BalancerFlashLoan.receiveFlashLoan()` is called by the Balancer Vault, and the reentrancy lock from `executeArbitrage()` is already held -- so in practice this is protected, but the protection is implicit and fragile.

**Recommended Fix**:
Add explicit reentrancy protection to the callback:

```solidity
function receiveFlashLoan(...) external override nonReentrant {
    // Note: nonReentrant may conflict with the lock already held by executeArbitrage()
    // Better: add a separate flag
    require(!_inCallback, "Reentrant callback");
    _inCallback = true;
    // ... execution logic ...
    _inCallback = false;
}
```

Or more simply, verify that the function can only be called during an active flash loan by checking a flag set by `executeArbitrage()`.

---

## LOW Findings

### L-01: On-Chain Signals Leak Intent Even With Private Mempools

**Severity**: LOW
**Affected Contracts**: All execution contracts

**Description**:
Even if the owner uses Flashbots Protect or another private transaction relay to hide the arbitrage transaction from the public mempool, on-chain signals can still leak intent:

1. **Token approvals**: If the arbitrage contract calls `approve()` or `forceApprove()` as separate transactions before the arbitrage, these appear on-chain and signal upcoming swap activity.
2. **Historical patterns**: Repeated arbitrage executions from the same contract address establish a behavioral fingerprint. MEV searchers can predict future arb paths based on past executions.
3. **Adapter registration events**: `AdapterRegistered` events signal which DEXes the contract will use, narrowing the search space for MEV bots.
4. **Gas price patterns**: Consistent gas pricing or nonce gaps can indicate pending private transactions.

In this codebase, the approvals happen within the same transaction (inside `executeOperation()` or adapter `swapDirect()`), so signal #1 is partially mitigated. However, signals #2 and #3 remain.

**Recommended Fix**:
1. Avoid emitting events that reveal operational parameters during live trading.
2. Consider using multiple contract instances or proxy patterns to obscure the trading address.
3. Rotate flash loan providers (Aave vs. Balancer) to reduce predictability.
4. Use decoy transactions to add noise to the behavioral fingerprint.

---

### L-02: Multi-Block MEV Attack Against FlashLoanLiquidator

**Severity**: LOW
**Affected Contract**: `contracts/FlashLoanLiquidator.sol`

**Description**:
A sophisticated attacker could set up a multi-block MEV attack against the liquidator:

1. **Block N**: Attacker manipulates a lending protocol's collateral price (e.g., through a low-liquidity oracle source or governance attack) to make a position appear liquidatable when it should not be.
2. **Block N+1**: The bot detects the "liquidatable" position and submits `executeLiquidation()`.
3. **Block N+1** (same block): Attacker sandwiches the liquidation swap to extract the liquidation bonus.

This is a theoretical attack that requires significant capital and coordination. The primary defense is the `minProfit` check, which ensures the liquidation is economically rational. However, if the attacker can manipulate the oracle price, they may create phantom liquidation opportunities that are profitable on paper but result in losses after the sandwich.

**Recommended Fix**:
1. Verify health factors using multiple oracle sources before submitting liquidation transactions (off-chain check).
2. Implement a cooldown period between detecting a liquidation opportunity and executing it.
3. Cross-reference Chainlink prices with TWAP prices to detect manipulation.

---

### L-03: `ArbitrageExecuted` Event Emits Cumulative Profits Instead of Per-Execution Profit

**Severity**: LOW
**Affected Contract**: `contracts/FlashLoanArbitrageV2.sol` (lines 156-163)

**Description**:
The `ArbitrageExecuted` event in `FlashLoanArbitrageV2` emits `totalProfits[params.flashLoanAsset]` as the "profit" field:

```solidity
emit ArbitrageExecuted(
    params.flashLoanAsset,
    params.flashLoanAmount,
    totalProfits[params.flashLoanAsset],  // <-- CUMULATIVE, NOT PER-TX
    gasUsed
);
```

This emits the cumulative total, not the profit from the current execution. An MEV searcher monitoring these events could use the cumulative profit data to estimate the bot's profitability and justify higher gas bids for future sandwiches.

The same pattern exists in `BalancerFlashLoan.sol` (line 158).

**Recommended Fix**:
Store the pre-execution cumulative profit and emit the delta:

```solidity
uint256 profitBefore = totalProfits[params.flashLoanAsset];
// ... execute flash loan ...
uint256 thisProfit = totalProfits[params.flashLoanAsset] - profitBefore;
emit ArbitrageExecuted(params.flashLoanAsset, params.flashLoanAmount, thisProfit, gasUsed);
```

---

## INFO Findings

### I-01: V1 Contract `_swapOnDEX` Is Unimplemented

**Severity**: INFO
**Affected Contract**: `contracts/FlashLoanArbitrage.sol` (lines 285-297)

**Description**:
The `_swapOnDEX()` function in the V1 contract always reverts with "DEX swap not implemented - use DEXLibrary". This means the V1 contract is not deployable for production use. It appears to be superseded by `FlashLoanArbitrageV2.sol` which uses the adapter pattern.

If the V1 contract were to be completed by implementing `_swapOnDEX()`, the critical issues identified in C-02 (zero per-step `minAmountOut`) must be addressed.

**Recommended Fix**:
Either remove the V1 contract or clearly mark it as deprecated. Do not deploy it in its current state.

---

### I-02: DEXLibrary Does Not Support Curve Pools

**Severity**: INFO
**Affected Contract**: `contracts/libraries/DEXLibrary.sol` (lines 50-57, 192-194)

**Description**:
The `DEXType` enum includes `CURVE`, but the `executeSwap()` function reverts with "Unsupported DEX type" for Curve. This is a feature gap rather than a security issue, but it means the V1 architecture cannot route through Curve pools. The V2 adapter pattern (`CurveAdapter.sol`) addresses this.

---

### I-03: MockDEX and MockERC20 Have No Access Controls

**Severity**: INFO
**Affected Contracts**:
- `contracts/MockDEX.sol`
- `contracts/MockERC20.sol`

**Description**:
`MockDEX.withdraw()` has no access control -- anyone can drain tokens. `MockERC20.mint()` has no access control -- anyone can mint unlimited tokens. These are clearly test-only contracts (indicated by the "Mock" prefix) and should never be deployed to mainnet. If deployed, they would be immediately exploitable.

**Recommended Fix**:
Add a prominent NatSpec warning and consider adding a constructor flag or compile-time check to prevent mainnet deployment.

---

## Summary of Recommendations (Priority Order)

### Immediate (Pre-deployment, CRITICAL/HIGH)

1. **C-01**: Set non-zero `sqrtPriceLimitX96` in both `UniswapV3Adapter` and `DEXLibrary`. Accept it as a parameter through calldata.
2. **C-02**: Add per-step `minAmountOut` in V1 `_executeSwaps()` or deprecate V1 entirely in favor of V2.
3. **H-01**: Implement Flashbots Protect / MEV Blocker for transaction submission. Set aggressive `minFinalAmount` values.
4. **H-02**: Integrate Chainlink price feeds for USD-denominated profit thresholds.
5. **H-03**: Implement TWAP-based reserve manipulation detection for Uniswap V2 swaps.
6. **H-04**: Pass a calculated `minAmountOut` to the liquidator's collateral swap instead of `0`.
7. **H-05**: Add `require(block.timestamp <= deadline)` inside `CurveAdapter.swapDirect()`.

### Short-term (MEDIUM)

8. **M-01**: Either enforce `maxSlippageBps` on-chain or remove the dead variable.
9. **M-02**: Set tight deadlines (1-2 blocks) in the off-chain bot.
10. **M-03**: Add minimum floor for `setMinProfit()` and enforce contract-level minimum in liquidator.
11. **M-04**: Accept fee tier as a parameter in `DEXLibrary.executeSwap()`.
12. **M-05**: Add explicit callback protection in `BalancerFlashLoan.receiveFlashLoan()`.

### Long-term (LOW/INFO)

13. **L-01**: Minimize on-chain information leakage; rotate contract addresses.
14. **L-02**: Implement multi-oracle cross-checks for liquidation triggers.
15. **L-03**: Fix event emissions to report per-transaction profit.
16. **I-01**: Remove or deprecate V1 contract.
17. **I-02/I-03**: Housekeeping -- complete Curve support in library, add guards to mocks.

---

## Appendix: MEV Risk Matrix

| Contract | Sandwich Risk | Front-Run Risk | Back-Run Risk | Multi-Block Risk |
|----------|:------------:|:--------------:|:-------------:|:----------------:|
| FlashLoanArbitrage (V1) | HIGH | HIGH | MEDIUM | LOW |
| FlashLoanArbitrageV2 | MEDIUM | HIGH | MEDIUM | LOW |
| BalancerFlashLoan | MEDIUM | HIGH | MEDIUM | LOW |
| FlashLoanLiquidator | HIGH | HIGH | HIGH | MEDIUM |
| UniswapV2Adapter | HIGH | N/A (called internally) | N/A | LOW |
| UniswapV3Adapter | HIGH | N/A (called internally) | N/A | LOW |
| CurveAdapter | MEDIUM | N/A (called internally) | N/A | LOW |

**Rationale**: V2/Balancer contracts have per-step `minAmountOut` which provides better sandwich resistance than V1. The liquidator has the highest risk because the collateral swap uses `minAmountOut = 0` and liquidation opportunities are highly competitive MEV targets. Adapters inherit the risk profile of their calling contracts.

---

*Report generated by Security Audit Agent 4 -- MEV, Price Manipulation, and Front-Running Analysis*
