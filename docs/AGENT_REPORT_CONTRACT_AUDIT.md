# Smart Contract Security Audit Report

**Project:** Flash Loan Arbitrage Bot
**Auditor:** AI Security Agent (Claude Opus 4.6)
**Date:** 2026-02-12
**Solidity Version:** ^0.8.20 (0.8.19 for mocks)
**Frameworks:** Foundry, Hardhat
**Target Chains:** Polygon, Arbitrum, Optimism, Base

---

## Scope

The following contracts were audited in full:

| File | Lines | Description |
|------|-------|-------------|
| `contracts/FlashLoanArbitrageV2.sol` | 343 | Main contract (V2) with adapter pattern |
| `contracts/FlashLoanArbitrage.sol` | 415 | Original main contract (V1) |
| `contracts/adapters/UniswapV2Adapter.sol` | 240 | Uniswap V2 / QuickSwap adapter |
| `contracts/adapters/UniswapV3Adapter.sol` | 212 | Uniswap V3 adapter |
| `contracts/adapters/UniswapV3AdapterFixed.sol` | 70 | Simplified V3 adapter (fixed fee) |
| `contracts/libraries/DEXLibrary.sol` | 253 | Swap execution library |
| `contracts/MockDEX.sol` | 75 | Mock DEX for testing |
| `contracts/MockERC20.sol` | 34 | Mock ERC20 for testing |
| `test/contracts/FlashLoanArbitrage.t.sol` | 177 | Foundry test suite |

---

## Executive Summary

This audit identified **4 Critical**, **5 High**, **6 Medium**, **5 Low**, and **6 Informational** findings across the flash loan arbitrage bot's smart contract codebase. The most severe issues involve the adapter trust model allowing fund theft, an interface mismatch between the V3 adapter and the main contract that will cause runtime failures, the V1 contract's underflow bug in `executeOperation`, and missing access control on adapter swap functions. The contract demonstrates a reasonable security baseline (uses Ownable, ReentrancyGuard, Pausable from OpenZeppelin, SafeERC20, and validates the flash loan callback caller) but has significant gaps that must be addressed before mainnet deployment.

---

## Findings

### CRITICAL

---

#### C-01: UniswapV3Adapter.swapDirect Interface Mismatch Causes Silent Failure or Revert

**Severity:** CRITICAL
**Affected File:** `contracts/adapters/UniswapV3Adapter.sol` (lines 132-162)
**Affected Function:** `swapDirect()`

**Description:**
The `IDEXAdapter` interface defined in `FlashLoanArbitrageV2.sol` (line 17-24) specifies `swapDirect` with the signature:

```solidity
function swapDirect(
    address tokenIn, address tokenOut, uint256 amountIn,
    uint256 minAmountOut, uint256 deadline, address recipient
) external returns (uint256 amountOut);
```

However, `UniswapV3Adapter.swapDirect()` has a **7-parameter** signature that includes an additional `uint24 fee` parameter:

```solidity
function swapDirect(
    address tokenIn, address tokenOut, uint256 amountIn,
    uint256 minAmountOut, uint24 fee, uint256 deadline, address recipient
) external returns (uint256 amountOut);
```

When `FlashLoanArbitrageV2.executeOperation()` calls `IDEXAdapter(step.adapter).swapDirect(...)` with 6 arguments on a `UniswapV3Adapter`, the EVM will attempt to match the 4-byte selector for the 6-parameter version, which does not exist on `UniswapV3Adapter`. The call will revert with no matching function selector, causing the entire flash loan to fail and the Aave premium to still be owed (though Aave will revert the whole transaction in mode 0).

**Proof of Concept:**
1. Owner registers `UniswapV3Adapter` as a valid adapter.
2. Owner calls `executeArbitrage` with a swap step using this adapter.
3. Inside `executeOperation`, the call `IDEXAdapter(step.adapter).swapDirect(tokenIn, tokenOut, amountIn, minAmountOut, deadline, recipient)` is dispatched.
4. The 4-byte function selector for `swapDirect(address,address,uint256,uint256,uint256,address)` does not match `swapDirect(address,address,uint256,uint256,uint24,uint256,address)`.
5. The call reverts. The entire flash loan transaction reverts.

**Recommended Fix:**
Make `UniswapV3Adapter.swapDirect()` conform to the `IDEXAdapter` interface (6 parameters). Pass the fee tier via the `SwapStep.data` bytes field instead (decode it inside the adapter). `UniswapV3AdapterFixed` already follows this approach correctly by using a hardcoded fee, but a production adapter should decode it from `data`. The adapter contract should explicitly implement `IDEXAdapter` to get a compile-time check.

---

#### C-02: Adapters Have No Access Control -- Anyone Can Drain Tokens Held by Adapters

**Severity:** CRITICAL
**Affected Files:** `contracts/adapters/UniswapV2Adapter.sol` (lines 101-130), `contracts/adapters/UniswapV3Adapter.sol` (lines 132-162), `contracts/adapters/UniswapV3AdapterFixed.sol` (lines 42-69)
**Affected Function:** `swapDirect()` in all adapters

**Description:**
The `swapDirect()` function in all adapter contracts is `external` with no access restriction. The main contract's flow in `FlashLoanArbitrageV2.executeOperation()` transfers tokens to the adapter (`safeTransfer(step.adapter, currentAmount)` at line 202) **before** calling `swapDirect()`. This creates a window where tokens sit in the adapter contract.

While in a single atomic transaction this window is not exploitable (the transfer and swap happen in the same tx), the larger issue is that anyone can call `swapDirect()` at any time. If tokens are ever left in an adapter (due to a failed partial execution, rounding dust, or direct transfer), any external caller can invoke `swapDirect()` with those tokens.

More critically, the `swapMultiHop()` function in `UniswapV2Adapter` (line 141) has the same lack of access control and accepts arbitrary paths, meaning an attacker could route any tokens held by the adapter to any token and any recipient.

**Proof of Concept:**
1. Tokens accumulate in an adapter (e.g., from rounding dust across many executions, or a user accidentally sends tokens to the adapter address).
2. Attacker calls `adapter.swapDirect(tokenIn, tokenOut, balance, 0, block.timestamp + 3600, attackerAddress)`.
3. Tokens are swapped and sent to the attacker.

**Recommended Fix:**
Add access control to all adapter functions. The simplest approach is to add an `onlyAuthorized` modifier that restricts calls to the registered main arbitrage contract (set at construction or via an admin function). Alternatively, use OpenZeppelin's `Ownable` pattern on adapters.

---

#### C-03: FlashLoanArbitrage V1 -- Underflow in executeOperation Profit Check

**Severity:** CRITICAL
**Affected File:** `contracts/FlashLoanArbitrage.sol` (lines 209-211)
**Affected Function:** `executeOperation()`

**Description:**
In the V1 contract's `executeOperation()`:

```solidity
if (finalAmount <= amountOwed) {
    revert InsufficientProfit(finalAmount - amountOwed, minProfitUSD);
}
```

When `finalAmount <= amountOwed`, the expression `finalAmount - amountOwed` will underflow (since Solidity 0.8+ has checked arithmetic). This means instead of reverting with a meaningful `InsufficientProfit` error showing the shortfall, the transaction reverts with a panic due to arithmetic underflow. This obscures the actual error, making debugging impossible for the bot operator.

When `finalAmount == amountOwed`, the subtraction yields 0 which is fine, but when `finalAmount < amountOwed` (the more common failure case), it panics.

**Proof of Concept:**
1. Flash loan executes but swaps result in `finalAmount = 990` and `amountOwed = 1000`.
2. The check `990 <= 1000` is true, so we enter the revert.
3. `990 - 1000` causes a panic (arithmetic underflow), not the intended custom error.
4. Bot operator sees `Panic(0x11)` instead of `InsufficientProfit(shortfall, minProfit)`.

**Recommended Fix:**
Reverse the subtraction or use a different error parameter: `revert InsufficientProfit(0, minProfitUSD)` when `finalAmount <= amountOwed`, or compute `amountOwed - finalAmount` as the shortfall. The V2 contract correctly handles this with `revert InsufficientProfit(0, minProfit)`.

---

#### C-04: Adapter Trust Model Allows Registered Malicious Adapter to Steal All Flash-Loaned Funds

**Severity:** CRITICAL
**Affected File:** `contracts/FlashLoanArbitrageV2.sol` (lines 198-219)
**Affected Function:** `executeOperation()`

**Description:**
The main contract transfers the full `currentAmount` of tokens to the adapter before calling `swapDirect()`. The contract then trusts the return value of `swapDirect()` to update `currentAmount`. A malicious (or compromised) adapter could:

1. Receive the tokens via `safeTransfer`.
2. Keep (steal) the tokens.
3. Return an inflated `amountOut` value from `swapDirect()`.

The main contract has no way to verify that the adapter actually delivered the claimed `amountOut` tokens to `address(this)`. It simply uses the return value to continue the swap chain. Eventually the final balance check (`currentAmount >= arbParams.minFinalAmount`) will fail because the contract never actually received the tokens, but by that point the adapter has already moved the funds.

However, because Aave's flash loan in mode 0 requires full repayment within the same transaction, the transaction would ultimately revert if the contract cannot repay. So the funds would not be permanently lost in a single flash-loan context. The real risk arises if the contract holds its own capital (profits, pre-funded tokens) and an adapter is used outside the flash loan flow, or if the contract is extended to support non-flash-loan arbitrage.

**Proof of Concept:**
1. Attacker deploys a malicious adapter contract that implements `swapDirect` but simply holds all received tokens and returns a fake `amountOut`.
2. Owner (with compromised key or social engineering) registers this adapter.
3. The adapter receives the flash-loaned tokens.
4. The flash loan reverts because repayment fails, but if the contract had its own pre-funded balance, the adapter keeps those tokens.

**Recommended Fix:**
After calling `swapDirect()`, verify the actual token balance change of the contract (i.e., check `IERC20(step.tokenOut).balanceOf(address(this))` before and after the swap call, and use the actual delta instead of the return value). This is the "check actual balance" pattern used by robust DeFi protocols.

---

### HIGH

---

#### H-01: FlashLoanArbitrage V1 -- _swapOnDEX Always Reverts (Unimplemented)

**Severity:** HIGH
**Affected File:** `contracts/FlashLoanArbitrage.sol` (lines 285-297)
**Affected Function:** `_swapOnDEX()`

**Description:**
The V1 contract's `_swapOnDEX()` function unconditionally reverts:

```solidity
revert("DEX swap not implemented - use DEXLibrary");
```

This means **no arbitrage can ever execute** through the V1 contract. If this contract is deployed, any flash loan attempt will always revert. This is labeled as HIGH rather than CRITICAL because the V2 contract appears to be the intended production contract, but the V1 contract is still in the codebase and could be mistakenly deployed.

**Recommended Fix:**
Either remove V1 from the codebase to prevent accidental deployment, or implement the function using `DEXLibrary`. Clearly mark V1 as deprecated if it is kept for reference.

---

#### H-02: FlashLoanArbitrage V1 -- Per-Swap minAmountOut Hardcoded to Zero

**Severity:** HIGH
**Affected File:** `contracts/FlashLoanArbitrage.sol` (lines 253-258)
**Affected Function:** `_executeSwaps()`

**Description:**
In the V1 contract, each individual swap call passes `0` as `minAmountOut`:

```solidity
currentAmount = _swapOnDEX(
    dexRouter, tokenIn, tokenOut, currentAmount,
    0, // minAmountOut calculated per swap
    params.deadline
);
```

While a global `minAmountOut` check exists at line 267, each intermediate swap has no slippage protection. This means a sandwich attacker can manipulate individual swap steps to extract maximum MEV, as long as the final amount still exceeds `params.minAmountOut`. In a multi-step arbitrage (e.g., A->B->C->A), the attacker could heavily frontrun the A->B swap, extract value, and the bot would only catch it if the cumulative loss exceeds the global threshold.

**Proof of Concept:**
1. Bot submits a 3-hop arbitrage: USDC -> WETH -> WBTC -> USDC.
2. Attacker sandwiches the USDC -> WETH swap, extracting 1% from that leg.
3. The remaining swaps proceed but with worse rates due to the manipulated price.
4. The global `minAmountOut` check may still pass if the original opportunity was large enough, but profit is significantly reduced.

**Recommended Fix:**
Pass meaningful per-step `minAmountOut` values. The V2 contract fixes this by including `minAmountOut` in each `SwapStep` struct, which is the correct approach.

---

#### H-03: Profit Accounting Can Desynchronize from Actual Balance

**Severity:** HIGH
**Affected Files:** `contracts/FlashLoanArbitrageV2.sol` (lines 242, 299-310)
**Affected Functions:** `executeOperation()`, `withdrawProfits()`

**Description:**
The `totalProfits` mapping is incremented inside `executeOperation()` with the calculated profit value:

```solidity
totalProfits[assets[0]] += profit;
```

And `withdrawProfits()` checks:

```solidity
require(amount <= totalProfits[token], "Insufficient profits");
```

However, the `totalProfits` accounting is purely internal and can desynchronize from the actual token balance. Scenarios:

1. If someone sends tokens directly to the contract, those tokens are not reflected in `totalProfits` and can only be recovered via `emergencyWithdraw`.
2. If a fee-on-transfer token is used as the flash loan asset, the actual tokens received will be less than `amounts[0]`, but `profit` is calculated based on nominal amounts. The tracked profit would exceed actual balance.
3. The `ArbitrageExecuted` event at line 170 emits `totalProfits[params.flashLoanAsset]` (the cumulative total, not the profit from this specific execution), which is misleading.

**Proof of Concept:**
1. Execute 10 successful arbitrages, each earning 100 USDC profit. `totalProfits[USDC] = 1000`.
2. A fee-on-transfer scenario or rounding causes actual balance to be 990 USDC.
3. Owner calls `withdrawProfits(USDC, 1000, owner)`. The require passes (1000 <= 1000) but `safeTransfer` reverts because balance is only 990.
4. Owner must use `emergencyWithdraw` instead, bypassing profit tracking entirely.

**Recommended Fix:**
In `withdrawProfits`, cap the withdrawal at `min(amount, IERC20(token).balanceOf(address(this)))`. Consider adding a `syncProfits()` function that reconciles `totalProfits` with actual balances. Fix the event to emit per-execution profit, not cumulative.

---

#### H-04: FlashLoanArbitrage V1 -- emergencyWithdraw Lacks onlyOwner, Uses Separate Authorization

**Severity:** HIGH
**Affected File:** `contracts/FlashLoanArbitrage.sol` (lines 385-396)
**Affected Function:** `emergencyWithdraw()`

**Description:**
The V1 contract introduces an `emergencyWithdrawers` mapping, granting withdrawal permission to addresses beyond the owner. This expands the attack surface:

```solidity
function emergencyWithdraw(address token, uint256 amount, address to) external nonReentrant {
    if (!emergencyWithdrawers[msg.sender]) {
        revert Unauthorized();
    }
    IERC20(token).safeTransfer(to, amount);
}
```

If any `emergencyWithdrawer` address is compromised, all contract funds can be drained immediately, with funds sent to any arbitrary `to` address. The `to` parameter should at minimum be restricted to the contract owner or the caller themselves.

The V2 contract correctly restricts `emergencyWithdraw` to `onlyOwner`.

**Recommended Fix:**
Remove the `emergencyWithdrawers` pattern. Use `onlyOwner` for emergency withdrawals (as V2 does). If multiple authorized parties are needed, use OpenZeppelin's `AccessControl` with explicit roles and consider a timelock.

---

#### H-05: UniswapV3Adapter.swapDirect Does Not Verify Token Balance Before Swap

**Severity:** HIGH
**Affected File:** `contracts/adapters/UniswapV3Adapter.sol` (lines 132-162)
**Affected Function:** `swapDirect()`

**Description:**
The `swapDirect()` function approves the router for `amountIn` tokens and executes the swap, but never verifies that the adapter actually holds `amountIn` tokens of `tokenIn`. If the main contract transferred fewer tokens than expected (e.g., due to a fee-on-transfer token), the swap will either:

1. Revert (if the router tries to pull more tokens than the adapter holds).
2. Succeed with less input than expected (if the router handles partial amounts).

The `UniswapV2Adapter.swapDirect()` has the same issue but `swapExactTokensForTokens` will revert if insufficient tokens are present, making it less exploitable.

**Recommended Fix:**
Check `IERC20(tokenIn).balanceOf(address(this))` at the start of `swapDirect()` and use the actual balance as `amountIn` (or require it to be >= the passed `amountIn`). This also protects against fee-on-transfer token edge cases.

---

### MEDIUM

---

#### M-01: No Validation of `to` Address in withdrawProfits and emergencyWithdraw

**Severity:** MEDIUM
**Affected Files:** `contracts/FlashLoanArbitrageV2.sol` (lines 299-310, 318-324), `contracts/FlashLoanArbitrage.sol` (lines 366-377, 385-396)
**Affected Functions:** `withdrawProfits()`, `emergencyWithdraw()`

**Description:**
Neither function validates that the `to` address is non-zero. Transferring tokens to `address(0)` would burn them permanently. While `SafeERC20.safeTransfer` on most ERC20 implementations will revert on transfer to address(0), some tokens (e.g., those not following the standard strictly) may not.

**Recommended Fix:**
Add `require(to != address(0), "Invalid recipient")` at the start of both functions.

---

#### M-02: maxSlippageBps Is Stored But Never Used On-Chain

**Severity:** MEDIUM
**Affected File:** `contracts/FlashLoanArbitrageV2.sol` (lines 45, 118, 274-277)
**Affected Function:** N/A (storage variable)

**Description:**
The `maxSlippageBps` variable is set in the constructor, can be updated via `setMaxSlippage()`, but is never referenced in any swap execution or validation logic. The actual slippage protection relies entirely on the `minAmountOut` values set per-swap-step in `SwapStep` and `minFinalAmount` in `ArbitrageParams`, which are computed off-chain.

This means the on-chain `maxSlippageBps` setting is dead code that gives a false sense of security. An operator might set `maxSlippageBps = 50` (0.5%) thinking they are protected, but the off-chain bot could submit `minAmountOut = 0` in every step and bypass any on-chain slippage guardrail.

**Recommended Fix:**
Either enforce `maxSlippageBps` on-chain (e.g., require that each step's `minAmountOut` is within `maxSlippageBps` of an oracle price or the input amount), or remove the variable entirely to avoid confusion. If the intention is purely off-chain governance, document this clearly.

---

#### M-03: FLASH_LOAN_FEE_BPS Is Hardcoded and May Not Match Aave's Actual Fee

**Severity:** MEDIUM
**Affected Files:** `contracts/FlashLoanArbitrageV2.sol` (line 48), `contracts/FlashLoanArbitrage.sol` (line 41)
**Affected Function:** `estimateFlashLoanFee()`

**Description:**
The flash loan fee is hardcoded as `5` basis points (0.05%). However:

1. Aave V3 governance can change the flash loan fee.
2. Different pools on different chains may have different fee configurations.
3. Some Aave markets have reduced the fee to 0 for certain assets.

The `estimateFlashLoanFee()` function uses this hardcoded constant and would return incorrect estimates if the actual fee changes. While the actual fee calculation in `executeOperation()` correctly uses `premiums[0]` from Aave (so the repayment is always correct), the estimation function would mislead the off-chain bot.

**Recommended Fix:**
Query the actual flash loan premium from `POOL.FLASHLOAN_PREMIUM_TOTAL()` instead of using a hardcoded constant. Alternatively, document that `estimateFlashLoanFee()` is an approximation only.

---

#### M-04: DEXLibrary.executeSwap Hardcodes FEE_MEDIUM for Uniswap V3

**Severity:** MEDIUM
**Affected File:** `contracts/libraries/DEXLibrary.sol` (lines 167-178)
**Affected Function:** `executeSwap()`

**Description:**
When `dexType == DEXType.UNISWAP_V3`, the `executeSwap()` function always uses `FEE_MEDIUM` (3000 = 0.3%):

```solidity
amountOut = swapUniswapV3(router, tokenIn, tokenOut, amountIn, minAmountOut, FEE_MEDIUM, deadline);
```

Many profitable arbitrage opportunities exist in the 0.05% (500) and 1% (10000) fee tiers. Hardcoding 0.3% means:
- Swaps on 0.05% pools will fail (wrong pool).
- Swaps on 1% pools will fail.
- Opportunities in non-0.3% pools are completely inaccessible via this library.

**Recommended Fix:**
Accept the fee tier as a parameter in `executeSwap()`, or pass it via extra data bytes that can be decoded per-swap.

---

#### M-05: No Event Emission on maxSlippageBps Update in V2

**Severity:** MEDIUM
**Affected File:** `contracts/FlashLoanArbitrageV2.sol` (lines 274-277)
**Affected Function:** `setMaxSlippage()`

**Description:**
The V1 contract emits `MaxSlippageUpdated` when the slippage is changed, but the V2 contract's `setMaxSlippage()` does not emit any event. This makes it impossible for off-chain monitoring systems to detect configuration changes, which is important for operational security.

**Recommended Fix:**
Add a `MaxSlippageUpdated` event and emit it in `setMaxSlippage()`.

---

#### M-06: Adapters Cannot Recover Stuck Tokens

**Severity:** MEDIUM
**Affected Files:** `contracts/adapters/UniswapV2Adapter.sol`, `contracts/adapters/UniswapV3Adapter.sol`, `contracts/adapters/UniswapV3AdapterFixed.sol`

**Description:**
None of the adapter contracts have any mechanism to recover tokens that may become stuck in them. If a swap partially fails, or a token with unusual transfer mechanics leaves dust, or tokens are accidentally sent to an adapter address, those tokens are permanently locked.

The adapters have no `owner`, no `emergencyWithdraw`, and no `rescueTokens` function.

**Recommended Fix:**
Add an `Ownable` pattern to adapters with a `rescueTokens(address token, uint256 amount, address to)` function restricted to the owner.

---

### LOW

---

#### L-01: No Input Validation on Constructor Parameters

**Severity:** LOW
**Affected Files:** `contracts/FlashLoanArbitrageV2.sol` (lines 110-119), `contracts/FlashLoanArbitrage.sol` (lines 102-114)

**Description:**
Constructors accept `_addressProvider` without checking it is non-zero. If deployed with `address(0)`, `ADDRESSES_PROVIDER.getPool()` will revert at deploy time (calling a function on address(0)), but the error message will be cryptic. Neither `_minProfit` nor `_maxSlippageBps` are validated either. Setting `_maxSlippageBps` to values above 10000 would be nonsensical but is not prevented at construction.

**Recommended Fix:**
Add `require(_addressProvider != address(0))` and `require(_maxSlippageBps <= 1000)` in constructors.

---

#### L-02: setAdapter Does Not Validate Adapter Address

**Severity:** LOW
**Affected File:** `contracts/FlashLoanArbitrageV2.sol` (lines 255-258)
**Affected Function:** `setAdapter()`

**Description:**
`setAdapter()` does not check if `adapter` is `address(0)`, if it has code (is a contract), or if it implements the `IDEXAdapter` interface. Registering an EOA or a non-conforming contract as an adapter will cause silent failures during arbitrage execution.

**Recommended Fix:**
Add `require(adapter != address(0))` and consider using ERC-165 `supportsInterface` checks if the adapter interface is extended to support it. At minimum, check `adapter.code.length > 0`.

---

#### L-03: Duplicate Interface Definitions Across Multiple Files

**Severity:** LOW
**Affected Files:** All adapter files and DEXLibrary

**Description:**
`ISwapRouter` is defined independently in `UniswapV3Adapter.sol`, `UniswapV3AdapterFixed.sol`, and as `IUniswapV3Router` in `DEXLibrary.sol`. `IUniswapV2Router02` is defined in `UniswapV2Adapter.sol` and as `IUniswapV2Router` in `DEXLibrary.sol` (with slightly different function sets). If one definition is updated but not the others, the contracts will diverge.

**Recommended Fix:**
Create a single `contracts/interfaces/` directory with canonical interface definitions (`ISwapRouter.sol`, `IUniswapV2Router.sol`, `IDEXAdapter.sol`) and import them in all contracts.

---

#### L-04: Pragma Version Mismatch Between Contracts

**Severity:** LOW
**Affected Files:** `contracts/MockDEX.sol` (pragma ^0.8.19), `contracts/MockERC20.sol` (pragma ^0.8.19), all others (pragma ^0.8.20)

**Description:**
Mock contracts use `^0.8.19` while production contracts use `^0.8.20`. While this is functionally harmless for mocks, inconsistent pragma versions can lead to confusion and compilation issues if the project pins a specific compiler version.

**Recommended Fix:**
Standardize all pragmas to `^0.8.20`.

---

#### L-05: ArbitrageExecuted Event Emits Cumulative Profits, Not Per-Execution Profit

**Severity:** LOW
**Affected File:** `contracts/FlashLoanArbitrageV2.sol` (lines 169-175)
**Affected Function:** `executeArbitrage()`

**Description:**
The `ArbitrageExecuted` event emits `totalProfits[params.flashLoanAsset]` as the `profit` parameter. This is the **cumulative** profit across all executions, not the profit from this specific execution. After 100 successful trades each making 10 USDC, the event would show `profit = 1000`, not `profit = 10`.

Additionally, the event is emitted *after* `executionCount++` but the profit value was set inside the callback. If the callback didn't execute (impossible with mode 0, but defensive programming), the event would emit a stale value.

**Recommended Fix:**
Capture the profit before and after the flash loan call and emit the delta: `uint256 profitBefore = totalProfits[params.flashLoanAsset]; ... POOL.flashLoan(...); ... uint256 profitThisExecution = totalProfits[params.flashLoanAsset] - profitBefore;`

---

### INFORMATIONAL

---

#### I-01: Gas Optimization -- Loop in executeOperation Uses Memory Copy for SwapStep

**Affected File:** `contracts/FlashLoanArbitrageV2.sol` (line 199)

**Description:**
`SwapStep memory step = arbParams.steps[i];` creates a memory copy of the entire struct (including the dynamic `bytes data` field) on each iteration. For steps with large `data` fields, this wastes gas.

**Recommended Fix:**
Access struct fields directly via `arbParams.steps[i].adapter` etc., or use a reference if the compiler supports it.

---

#### I-02: Gas Optimization -- Adapter Registration Loop in executeArbitrage

**Affected File:** `contracts/FlashLoanArbitrageV2.sol` (lines 137-141)

**Description:**
The adapter validation loop iterates through all steps and checks `registeredAdapters[params.steps[i].adapter]` for each. If the same adapter is used in multiple steps, it is checked redundantly.

**Recommended Fix:**
This is minor for typical arbitrage paths (2-3 steps), but for longer paths, consider caching validated adapters in a local mapping or using a bitmap.

---

#### I-03: MockDEX Has No Access Control on withdraw()

**Affected File:** `contracts/MockDEX.sol` (lines 72-74)

**Description:**
`MockDEX.withdraw()` allows anyone to withdraw any token with no access control. This is acceptable for a testing mock but should never be deployed to a live network.

**Recommended Fix:**
Ensure MockDEX is excluded from production deployments. Consider adding a comment `// TEST ONLY - DO NOT DEPLOY` and adding it to a `.deployignore` or similar mechanism.

---

#### I-04: MockERC20.mint() Has No Access Control

**Affected File:** `contracts/MockERC20.sol` (lines 27-29)

**Description:**
`MockERC20.mint()` allows anyone to mint unlimited tokens. This is standard for test mocks but dangerous if accidentally deployed.

**Recommended Fix:**
Same as I-03. Mark clearly as test-only.

---

#### I-05: UniswapV3Adapter.getQuote Is Not a View Function

**Affected File:** `contracts/adapters/UniswapV3Adapter.sol` (lines 172-179)

**Description:**
`getQuote()` calls `quoter.quoteExactInputSingle()` which is not a `view` function in Uniswap V3's QuoterV2 (it uses `try/catch` with state-modifying calls internally). The adapter's `getQuote()` correctly omits the `view` modifier, but this means it cannot be called in a static context (e.g., `eth_call` will work but it technically modifies state and reverts). This is expected behavior with Uniswap V3 quoters but may confuse integrators.

**Recommended Fix:**
Add a NatSpec comment explaining that this function should be called via `eth_call` (static simulation) and not in an on-chain transaction, as it would waste gas.

---

#### I-06: Consider Using Solidity Custom Errors Consistently

**Affected Files:** Multiple

**Description:**
The codebase mixes `require()` with string messages and custom errors. For example, `FlashLoanArbitrageV2.executeOperation()` uses `require(msg.sender == address(POOL), "Caller must be Pool")` (string revert) alongside custom errors like `InsufficientProfit`. Custom errors are more gas-efficient and should be used consistently.

**Recommended Fix:**
Replace all `require(..., "string")` patterns with custom errors for gas savings and consistency.

---

## Test Coverage Analysis

**Test File:** `test/contracts/FlashLoanArbitrage.t.sol` (177 lines)

### What Is Tested

| Test | Coverage |
|------|----------|
| `testDeployment` | Constructor sets state correctly |
| `testSetDEXWhitelist` | Owner can whitelist DEX |
| `testSetDEXWhitelistUnauthorized` | Non-owner cannot whitelist |
| `testSetMinProfit` | Owner can update minProfit |
| `testSetMaxSlippage` | Owner can update slippage |
| `testSetMaxSlippageTooHigh` | Revert on >10% slippage |
| `testPauseUnpause` | Pause/unpause works |
| `testEstimateFlashLoanFee` | Fee calculation |
| `testEmergencyWithdrawer` | Grant/revoke withdrawer |
| `testGetBalance` | Balance query |
| `testCannotExecuteArbitrageWhenPaused` | Pause blocks execution |
| `testCannotExecuteArbitrageWithExpiredDeadline` | Deadline enforcement |

### Critical Test Gaps

1. **No tests for FlashLoanArbitrageV2** -- The test file only tests V1. The production contract (V2) has zero test coverage.

2. **No integration tests** -- No test executes an actual flash loan or swap. The `_swapOnDEX` function always reverts, so no end-to-end flow is tested.

3. **No tests for executeOperation callback** -- The flash loan callback is never tested. There are no tests verifying:
   - Caller validation (msg.sender == POOL)
   - Initiator validation
   - Profit calculation correctness
   - Token repayment approval

4. **No adapter tests** -- None of the three adapter contracts have any tests.

5. **No tests for adapter registration in V2** -- `setAdapter()` is untested.

6. **No reentrancy tests** -- No test attempts to re-enter any function.

7. **No fuzz tests** -- Despite `foundry.toml` configuring `fuzz_runs = 256`, no fuzz tests exist.

8. **No tests for emergencyWithdraw or withdrawProfits** -- Fund recovery paths are untested.

9. **No tests for edge cases** -- Zero amounts, same token in/out, empty paths, single-step paths, etc.

10. **Wrong Ownable revert message** -- Test at line 69 expects `"Ownable: caller is not the owner"` which is the OpenZeppelin v4 message. With Solidity ^0.8.20 and OpenZeppelin v5, the error is `OwnableUnauthorizedAccount(address)`. This test will fail.

11. **Wrong Pausable revert message** -- Test at line 154 expects `"Pausable: paused"` which is the OZ v4 message. OZ v5 uses `EnforcedPause()` custom error.

---

## Architecture Observations

### Positive Security Properties

1. **Ownable + nonReentrant + whenNotPaused** on `executeArbitrage()` -- correct modifier stack.
2. **Flash loan callback validates msg.sender and initiator** -- prevents unauthorized callback invocation.
3. **SafeERC20 used throughout** -- prevents silent transfer failures.
4. **forceApprove instead of approve** -- handles non-standard ERC20 approval behavior.
5. **Approval reset to 0 after swaps** in adapters -- good hygiene.
6. **Mode 0 flash loan** -- ensures loan must be repaid atomically (no debt position).
7. **Deadline enforcement** -- prevents stale transactions from executing.

### Structural Concerns

1. **V1 and V2 coexist** -- creates confusion about which contract to deploy. V1 is non-functional.
2. **No interface directory** -- interfaces are defined inline or duplicated across files.
3. **No deployment scripts** -- increases risk of misconfigured deployments.
4. **DEXLibrary is unused** -- it is defined but neither V1 nor V2 actually imports or uses it.
5. **No upgradeability** -- while this avoids proxy risks, it means any bug requires redeploying and migrating all state/funds.

---

## Summary of Findings by Severity

| Severity | Count | Key Issues |
|----------|-------|------------|
| **CRITICAL** | 4 | Interface mismatch (C-01), no adapter access control (C-02), V1 underflow (C-03), adapter trust model (C-04) |
| **HIGH** | 5 | V1 unimplemented swap (H-01), zero minAmountOut per swap (H-02), profit desync (H-03), V1 emergency withdrawer (H-04), no balance verification (H-05) |
| **MEDIUM** | 6 | No `to` validation (M-01), unused maxSlippageBps (M-02), hardcoded fee constant (M-03), hardcoded V3 fee tier (M-04), missing event (M-05), stuck tokens in adapters (M-06) |
| **LOW** | 5 | No constructor validation (L-01), no adapter address validation (L-02), duplicate interfaces (L-03), pragma mismatch (L-04), wrong event data (L-05) |
| **INFORMATIONAL** | 6 | Gas optimizations (I-01, I-02), mock access control (I-03, I-04), quoter behavior (I-05), error consistency (I-06) |

---

## Priority Recommendations

### Before Mainnet Deployment (Blockers)

1. **Fix C-01**: Make `UniswapV3Adapter.swapDirect()` conform to the `IDEXAdapter` interface. Pass fee tier via `SwapStep.data`.
2. **Fix C-02**: Add access control to all adapter `swapDirect()` and `swapMultiHop()` functions.
3. **Fix C-04**: Verify actual balance changes after adapter calls instead of trusting return values.
4. **Fix H-05**: Verify adapter holds sufficient tokens before swap execution.
5. **Remove or clearly deprecate V1** to prevent accidental deployment (fixes C-03, H-01, H-02, H-04).
6. **Write comprehensive tests** for V2 contract, including fork tests with real Aave pools and DEX routers.

### Before Production Operation (High Priority)

7. **Fix H-03**: Reconcile profit accounting with actual balances.
8. **Fix M-02**: Either enforce `maxSlippageBps` on-chain or remove it.
9. **Fix M-01**: Validate `to != address(0)` in withdrawal functions.
10. **Fix M-06**: Add token recovery mechanism to adapters.

### Ongoing Improvements

11. Consolidate interfaces into a dedicated directory (L-03).
12. Standardize pragma versions (L-04).
13. Add fuzz tests and invariant tests.
14. Consider a multisig or timelock for owner operations.
15. Add monitoring events for all state changes (M-05).

---

*End of audit report.*
