# Security Audit Report: Token Handling & Financial Logic

**Agent**: 3 of 7 -- Token Handling & Financial Logic
**Scope**: All contracts in `/contracts/` -- ERC20 edge cases, SafeERC20 usage, approval patterns, profit accounting, balance verification, rounding/precision, overflow/underflow, and FlashLoanLiquidator profit calculation.
**Date**: 2026-02-27
**Solidity Version**: ^0.8.20

---

## Executive Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 3     |
| HIGH     | 6     |
| MEDIUM   | 5     |
| LOW      | 4     |
| INFO     | 3     |
| **Total** | **21** |

The codebase demonstrates solid fundamentals -- SafeERC20 is consistently used in production contracts, `forceApprove` is used instead of raw `approve`, and balance-before/after patterns are employed for swap verification. However, several critical issues were identified including emergency withdrawal bypassing profit tracking, underflow revert in profit calculation, a redundant dead-code profit check in the liquidator, missing fee-on-transfer token handling, and unsafe raw ERC20 calls in mock/test contracts that could mask integration bugs.

---

## CRITICAL Findings

### C-01: `emergencyWithdraw` Bypasses Profit Accounting in All Contracts

**Severity**: CRITICAL
**Contracts**: `FlashLoanArbitrage.sol` (L385-396), `FlashLoanArbitrageV2.sol` (L314-320), `BalancerFlashLoan.sol` (L277-283), `FlashLoanLiquidator.sol` (L260-262)

**Description**: In every contract, `emergencyWithdraw` transfers tokens without decrementing `totalProfits`. After an emergency withdrawal, the `totalProfits` mapping still reflects the old (higher) value. A subsequent call to `withdrawProfits` would attempt to transfer tokens that no longer exist, either reverting (best case) or, if the contract has received new tokens from subsequent arbitrage, double-counting previously withdrawn funds.

**Code (FlashLoanArbitrageV2, lines 314-320)**:
```solidity
function emergencyWithdraw(
    address token,
    uint256 amount,
    address to
) external onlyOwner nonReentrant {
    IERC20(token).safeTransfer(to, amount);  // totalProfits NOT adjusted
}
```

Meanwhile `withdrawProfits` checks:
```solidity
require(amount <= totalProfits[token], "Insufficient profits");
totalProfits[token] -= amount;
```

**Attack Scenario**:
1. Contract accumulates 100 USDC in profits (`totalProfits[USDC] = 100`).
2. Owner calls `emergencyWithdraw(USDC, 100, owner)` -- all 100 USDC leave the contract.
3. `totalProfits[USDC]` still reads 100.
4. Contract earns 50 more USDC from new arbitrage (`totalProfits[USDC] = 150`, actual balance = 50).
5. Owner calls `withdrawProfits(USDC, 150, owner)` -- attempts to transfer 150 USDC but only 50 exists, causing a revert or (with fee-on-transfer tokens) partial drain of other users' funds.

**Recommended Fix**:
```solidity
function emergencyWithdraw(address token, uint256 amount, address to) external onlyOwner nonReentrant {
    // Reduce tracked profits by the withdrawn amount (saturating at 0)
    if (amount <= totalProfits[token]) {
        totalProfits[token] -= amount;
    } else {
        totalProfits[token] = 0;
    }
    IERC20(token).safeTransfer(to, amount);
}
```

---

### C-02: Underflow Revert in `executeOperation` Profit Check (FlashLoanArbitrage V1)

**Severity**: CRITICAL
**Contract**: `FlashLoanArbitrage.sol`, lines 209-211

**Description**: When `finalAmount <= amountOwed`, the code attempts to revert with a value computed as `finalAmount - amountOwed`. Since Solidity 0.8.x has built-in overflow/underflow protection, this subtraction will revert with a panic (arithmetic underflow) before the custom error `InsufficientProfit` is triggered.

**Code (lines 209-211)**:
```solidity
if (finalAmount <= amountOwed) {
    revert InsufficientProfit(finalAmount - amountOwed, minProfitUSD);
    //                        ^^^^^^^^^^^^^^^^^^^^^^^^ underflows when finalAmount < amountOwed
}
```

**Impact**: When a swap fails to produce profit, the transaction reverts with an opaque arithmetic underflow panic (`Panic(0x11)`) instead of the descriptive `InsufficientProfit` error. This makes off-chain monitoring, error handling, and bot retry logic unreliable -- the bot cannot distinguish between a genuine arithmetic bug and a "no profit" situation.

**Recommended Fix**:
```solidity
if (finalAmount <= amountOwed) {
    revert InsufficientProfit(0, minProfitUSD);
}
```

---

### C-03: Redundant Dead-Code Profit Check in FlashLoanLiquidator

**Severity**: CRITICAL
**Contract**: `FlashLoanLiquidator.sol`, lines 200-225

**Description**: The profit calculation section contains a redundant, unreachable check that reveals confused accounting logic. The first check on line 203 uses `swapReceived + amounts[0]`, which is logically incorrect given the flow:

```solidity
// Line 203 -- INCORRECT CHECK:
if (swapReceived + amounts[0] <= amountOwed) {
    revert InsufficientProfit(0, liqParams.minProfit);
}

// Line 218 -- CORRECT CHECK (makes the above redundant):
if (swapReceived < amountOwed) {
    revert InsufficientProfit(0, liqParams.minProfit);
}
```

As the inline comments on lines 210-216 correctly explain: the flash loan gave `amounts[0]` of debt tokens, which were entirely spent on the `liquidationCall`. After the swap, the contract holds exactly `swapReceived` debt tokens. The repayment obligation is `amountOwed = amounts[0] + premiums[0]`.

The first check (`swapReceived + amounts[0] <= amountOwed`) is always false when `swapReceived >= premiums[0]` (i.e., whenever the swap returned at least the flash loan fee). This means the check provides zero protection for the vast majority of liquidation attempts -- it only triggers when the swap catastrophically fails to return even the fee amount. The second check on line 218 is the correct and sufficient guard.

**Impact**: The dead check does not cause direct fund loss, but it indicates confused profit accounting that could lead to incorrect modifications in future code changes. It also means the inline comments explicitly acknowledging the first check is wrong were left in production code.

**Recommended Fix**: Remove lines 203-207 entirely. The check on line 218 correctly handles all cases.

---

## HIGH Findings

### H-01: Fee-on-Transfer Tokens Break Profit Accounting Across All Contracts

**Severity**: HIGH
**Contracts**: `FlashLoanArbitrage.sol`, `FlashLoanArbitrageV2.sol`, `BalancerFlashLoan.sol`, `FlashLoanLiquidator.sol`

**Description**: Tokens like USDT (which has a transfer fee mechanism, currently set to 0 but can be enabled by Tether), PAXG (0.02% transfer fee), and deflationary tokens charge a fee on every transfer. The contracts calculate profit based on swap return values without accounting for transfer fees deducted during the final repayment.

In `FlashLoanArbitrage.sol` (lines 221-225):
```solidity
totalProfits[assets[0]] += profit;
IERC20(assets[0]).forceApprove(address(POOL), amountOwed);
```

The `totalProfits` counter records a profit amount that assumes the full `amountOwed` will be transferred to the Pool. If the token has a transfer fee, the Pool receives less than `amountOwed`, causing the flash loan repayment to fail. Even worse, if a fee-on-transfer token is used as an intermediate token, the `balanceBefore/balanceAfter` check in V2 and Balancer contracts correctly catches the received amount but the `safeTransfer` to the next adapter will deliver less than `currentAmount`, breaking subsequent swap calculations.

**Attack Scenario**: If PAXG (0.02% fee) is the flash loan asset and the profit margin is tight (e.g., 0.01%), the transfer fee on repayment causes the flash loan to fail, wasting gas. More critically, if the fee structure changes after deployment, previously profitable strategies begin failing silently.

**Recommended Fix**:
1. Maintain an explicit allowlist of supported tokens that have been verified to not charge transfer fees.
2. For maximum safety, use the balance-before/after pattern on the final repayment transfer as well.
3. Add a `supportedTokens` mapping and validate flash loan assets against it.

---

### H-02: `FlashLoanArbitrage` V1 Does Not Verify Actual Balance Received from Swaps

**Severity**: HIGH
**Contract**: `FlashLoanArbitrage.sol`, lines 238-272

**Description**: Unlike `FlashLoanArbitrageV2` and `BalancerFlashLoan` which use `balanceBefore/balanceAfter` to verify actual token receipt, the V1 contract in `_executeSwaps` trusts the return value of `_swapOnDEX` without any balance verification.

```solidity
function _executeSwaps(ArbitrageParams memory params) internal returns (uint256) {
    uint256 currentAmount = params.amountIn;
    for (uint256 i = 0; i < params.dexRouters.length; i++) {
        // ...
        currentAmount = _swapOnDEX(router, tokenIn, tokenOut, currentAmount, 0, params.deadline);
        // ^^^ No balance verification -- trusts return value
    }
    return currentAmount;
}
```

**Impact**: A malicious or buggy DEX router could report inflated output amounts, leading the contract to believe it has more tokens than it actually does. This could cause the flash loan repayment to fail, or worse, if the router is compromised, it could report profits that don't exist, inflating `totalProfits`.

Note: The `_swapOnDEX` function currently reverts with "not implemented", so this is latent until DEX logic is implemented. But the architecture is fundamentally flawed compared to V2/Balancer.

**Recommended Fix**: Add the same `balanceBefore/balanceAfter` pattern used in V2 and Balancer to verify actual token receipt.

---

### H-03: Rebasing Tokens (stETH, AMPL) Break Balance Verification Logic

**Severity**: HIGH
**Contracts**: `FlashLoanArbitrageV2.sol` (L189-211), `BalancerFlashLoan.sol` (L185-211), `FlashLoanLiquidator.sol` (L165-176, L182-198)

**Description**: Rebasing tokens change balances between transactions (stETH positive rebase, AMPL neutral/negative). The `balanceBefore/balanceAfter` verification pattern assumes balances only change due to the contract's own actions within the same transaction. While rebases typically occur at specific times, a rebase triggered in the same block (e.g., Lido's oracle report) could cause `balanceAfter - balanceBefore` to be incorrect.

```solidity
uint256 balanceBefore = IERC20(step.tokenOut).balanceOf(address(this));
// ... execute swap ...
uint256 balanceAfter = IERC20(step.tokenOut).balanceOf(address(this));
uint256 actualReceived = balanceAfter - balanceBefore;
```

If a positive rebase occurs between the `balanceBefore` and `balanceAfter` reads, `actualReceived` would be inflated, leading to an overcount of profit. Conversely, a negative rebase would cause an undercount and potential swap failure.

**Recommended Fix**: Maintain a token allowlist that explicitly excludes rebasing tokens (stETH, AMPL, OHM, etc.). If rebasing tokens must be supported, use wrapped versions (wstETH instead of stETH).

---

### H-04: BalancerFlashLoan `receiveFlashLoan` Missing Reentrancy Guard

**Severity**: HIGH
**Contract**: `BalancerFlashLoan.sol`, lines 167-236

**Description**: The `receiveFlashLoan` callback lacks the `nonReentrant` modifier. While the entry point `executeArbitrage` has `nonReentrant`, the callback itself is a separate function call from the Balancer Vault. A malicious adapter called during the swap loop could invoke the Balancer Vault to trigger another flash loan, re-entering `receiveFlashLoan`.

```solidity
function receiveFlashLoan(
    IERC20[] calldata tokens,
    uint256[] calldata amounts,
    uint256[] calldata feeAmounts,
    bytes calldata userData
) external override {  // <-- NO nonReentrant modifier
    if (msg.sender != address(VAULT)) revert UnauthorizedCaller();
    // ...
```

**Impact**: While the Vault caller check prevents arbitrary external callers, a malicious or compromised adapter that is authorized could construct a reentrancy attack via the Vault by triggering another flash loan from within the swap callback. This could manipulate `totalProfits` or token balances.

Note: In practice, Balancer V2's Vault does not allow reentrancy in its own flash loan mechanism. However, defense-in-depth dictates that the callback should still be protected.

**Recommended Fix**: The `nonReentrant` modifier on `executeArbitrage` already sets the reentrancy lock. Since `receiveFlashLoan` is called within the execution of `executeArbitrage` (the lock is already held), the callback is implicitly protected by the outer call's lock -- re-entering `executeArbitrage` would fail. However, `receiveFlashLoan` itself can be called externally if someone calls the Vault directly. Add an explicit state flag:
```solidity
bool private _inFlashLoan;

function executeArbitrage(...) external onlyOwner nonReentrant whenNotPaused {
    _inFlashLoan = true;
    // ... flash loan ...
    _inFlashLoan = false;
}

function receiveFlashLoan(...) external override {
    require(_inFlashLoan, "Not in flash loan");
    require(msg.sender == address(VAULT), "Unauthorized");
    // ...
}
```

---

### H-05: `FlashLoanArbitrage` V1 `emergencyWithdrawers` Mapping Allows Non-Owner Withdrawal

**Severity**: HIGH
**Contract**: `FlashLoanArbitrage.sol`, lines 385-396

**Description**: In V1, `emergencyWithdraw` does not require `onlyOwner`. Instead, it uses a separate `emergencyWithdrawers` mapping. While the owner can grant/revoke this role, a compromised emergency withdrawer can drain all tokens, not just tracked profits.

```solidity
function emergencyWithdraw(
    address token,
    uint256 amount,
    address to
) external nonReentrant {  // <-- NO onlyOwner
    if (!emergencyWithdrawers[msg.sender]) {
        revert Unauthorized();
    }
    IERC20(token).safeTransfer(to, amount);
}
```

**Impact**: An authorized `emergencyWithdrawer` can withdraw any amount of any token to any address, without any logging of who initiated the withdrawal (only the `to` address is logged). If the withdrawer's private key is compromised, the attacker has full access to all contract funds.

**Recommended Fix**:
1. Restrict `emergencyWithdraw` to `onlyOwner` only (as done in V2 and Balancer).
2. If the multi-party emergency withdrawal is required, add a timelock or multi-sig requirement.
3. Log `msg.sender` in the `EmergencyWithdrawal` event.

---

### H-06: Tokens with Blocklists (USDC, USDT) Can Permanently Lock Profits

**Severity**: HIGH
**Contracts**: All contracts with `withdrawProfits` and `emergencyWithdraw`

**Description**: USDC and USDT implement blocklist functionality where Circle/Tether can blacklist addresses, causing all `transfer`/`transferFrom` calls to revert. If the contract address is blacklisted (e.g., due to interaction with a sanctioned address), all tokens of that type become permanently locked. The `totalProfits` mapping would show available profits, but `withdrawProfits` and `emergencyWithdraw` would always revert.

**Impact**: Permanent loss of all funds in the affected token for the contract. This is particularly relevant for arbitrage contracts that interact with many counterparties, increasing the surface area for inadvertent contact with sanctioned entities.

**Recommended Fix**:
1. Implement a `rescueTokens` function that uses `IERC20.approve` to allow a designated address to pull tokens (since `approve` is not blocked on USDC/USDT, only `transfer`).
2. Document the blocklist risk in operator documentation.
3. Consider deploying behind a proxy so the contract address can be migrated if blocklisted.

---

## MEDIUM Findings

### M-01: Flash Loan Fee Rounding Truncation May Cause Dust Losses

**Severity**: MEDIUM
**Contracts**: `FlashLoanArbitrage.sol` (L412-414), `FlashLoanArbitrageV2.sol` (L336-338), `FlashLoanLiquidator.sol` (L33-35)

**Description**: The flash loan fee estimation uses integer division which truncates:
```solidity
fee = (amount * FLASH_LOAN_FEE_BPS) / BPS_DENOMINATOR;
//   = (amount * 5) / 10000
```

For amounts not evenly divisible by 2000 (since 10000/5 = 2000), the fee estimate is truncated. For example:
- `amount = 1999` => `fee = (1999 * 5) / 10000 = 9995 / 10000 = 0` (actual fee should be ~1)
- `amount = 3999` => `fee = (3999 * 5) / 10000 = 19995 / 10000 = 1` (actual fee should be ~2)

The `estimateFlashLoanFee` function is marked `pure` and is for off-chain estimation, but if this estimate is used to calculate `minAmountOut` parameters, the underestimated fee could cause the profit check to fail unexpectedly.

**Impact**: The contract's own profit checks use the Aave Pool's actual `premiums[0]` parameter (not this function), so on-chain execution is not affected. However, off-chain bots relying on `estimateFlashLoanFee` for profitability simulation will underestimate costs for small loan amounts.

**Recommended Fix**: Add rounding-up option for fee calculation:
```solidity
function estimateFlashLoanFee(uint256 amount) external pure returns (uint256 fee) {
    fee = (amount * FLASH_LOAN_FEE_BPS + BPS_DENOMINATOR - 1) / BPS_DENOMINATOR;
}
```

---

### M-02: No Maximum Bound on `minProfit` / `minProfitUSD` Setters

**Severity**: MEDIUM
**Contracts**: All contracts with `setMinProfit`

**Description**: The `setMinProfit` functions accept arbitrary `uint256` values with no upper bound check. Setting `minProfit` to `type(uint256).max` would effectively disable the contract permanently, as no arbitrage would ever meet the profit threshold.

```solidity
function setMinProfit(uint256 _minProfit) external onlyOwner {
    uint256 oldValue = minProfit;
    minProfit = _minProfit;  // No upper bound check
    emit MinProfitUpdated(oldValue, _minProfit);
}
```

**Impact**: A compromised owner key or fat-finger error could permanently brick the contract by setting an impossibly high profit threshold. While `onlyOwner` limits access, this is an admin-level self-DOS vector.

**Recommended Fix**: Add a reasonable upper bound, e.g.:
```solidity
require(_minProfit <= 1e24, "Profit threshold too high");  // 1M tokens with 18 decimals
```

---

### M-03: `ArbitrageExecuted` Event in V2/Balancer Emits Cumulative Profit, Not Per-Execution Profit

**Severity**: MEDIUM
**Contracts**: `FlashLoanArbitrageV2.sol` (L157-162), `BalancerFlashLoan.sol` (L155-160)

**Description**: The `ArbitrageExecuted` event is emitted after `executeArbitrage` returns, using `totalProfits[params.flashLoanAsset]` as the profit field. This is the cumulative total profit, not the profit from the current execution.

```solidity
emit ArbitrageExecuted(
    params.flashLoanAsset,
    params.flashLoanAmount,
    totalProfits[params.flashLoanAsset],  // <-- cumulative, not per-execution
    gasUsed
);
```

Compare to V1's `FlashLoanArbitrage.sol` (line 227), which correctly emits the per-execution profit:
```solidity
emit ArbitrageExecuted(assets[0], amounts[0], profit, block.timestamp);
```

**Impact**: Off-chain monitoring systems parsing events will get incorrect per-execution profit figures. The first execution may look correct, but subsequent executions will report inflated profits. This breaks analytics, tax reporting, and P&L tracking.

**Recommended Fix**: Record per-execution profit in a local variable before the flash loan call, then compute the delta:
```solidity
uint256 profitBefore = totalProfits[params.flashLoanAsset];
POOL.flashLoan(...);
uint256 executionProfit = totalProfits[params.flashLoanAsset] - profitBefore;
emit ArbitrageExecuted(params.flashLoanAsset, params.flashLoanAmount, executionProfit, gasUsed);
```

---

### M-04: CurveAdapter `swapDirect` Trusts `exchange()` Return Value Without Balance Check

**Severity**: MEDIUM
**Contract**: `CurveAdapter.sol`, lines 146-157

**Description**: The CurveAdapter's `swapDirect` transfers the amount returned by `ICurvePool.exchange()` to the recipient without verifying that the adapter actually received that amount.

```solidity
amountOut = ICurvePool(info.pool).exchange(info.indexA, info.indexB, amountIn, minAmountOut);
if (recipient != address(this)) {
    IERC20(tokenOut).safeTransfer(recipient, amountOut);
}
```

While the calling contracts (V2, Balancer) do their own `balanceBefore/balanceAfter` check, the CurveAdapter itself could silently fail to receive the correct amount from certain Curve pool implementations (especially meta-pools or pools with admin fees). The `safeTransfer` to recipient would then revert with an insufficient balance error, providing a poor error message.

**Recommended Fix**: Add balance verification within the adapter:
```solidity
uint256 balBefore = IERC20(tokenOut).balanceOf(address(this));
ICurvePool(info.pool).exchange(info.indexA, info.indexB, amountIn, minAmountOut);
amountOut = IERC20(tokenOut).balanceOf(address(this)) - balBefore;
```

---

### M-05: UniswapV2Adapter Routes Output Directly to Recipient, Bypassing Caller's Balance Check

**Severity**: MEDIUM
**Contract**: `UniswapV2Adapter.sol`, lines 124-132

**Description**: The V2 adapter calls `swapExactTokensForTokens` with the `recipient` address directly as the `to` parameter. This means tokens go directly from the Uniswap router to the recipient, bypassing the adapter.

```solidity
uint256[] memory amounts = router.swapExactTokensForTokens(
    amountIn,
    minAmountOut,
    path,
    recipient,   // <-- tokens go directly to recipient, never touch the adapter
    deadline
);
amountOut = amounts[amounts.length - 1];
```

However, in `FlashLoanArbitrageV2.executeOperation` (line 192), the calling contract first transfers tokens TO the adapter (`safeTransfer(step.adapter, currentAmount)`), then calls `swapDirect` on the adapter. The adapter then approves the router and swaps. The output goes directly back to the caller (recipient = `address(this)` of the arbitrage contract).

The issue: the adapter's `amountOut` return value is the router's reported output, not a verified balance. The calling contract does perform `balanceBefore/balanceAfter` verification, so the return value mismatch is caught. However, with fee-on-transfer tokens, the router's reported `amounts` would not match the actual tokens received by the recipient, and while the caller's balance check catches this, it creates inconsistency between the return value and actual receipt.

**Recommended Fix**: For consistency and safety, have the adapter route through itself:
```solidity
uint256[] memory amounts = router.swapExactTokensForTokens(
    amountIn, minAmountOut, path, address(this), deadline
);
uint256 received = IERC20(tokenOut).balanceOf(address(this));
if (recipient != address(this)) {
    IERC20(tokenOut).safeTransfer(recipient, received);
}
amountOut = received;
```

---

## LOW Findings

### L-01: MockDEX Uses Raw `transfer` and `transferFrom` Without SafeERC20

**Severity**: LOW
**Contract**: `MockDEX.sol`, lines 37, 44, 66, 73

**Description**: The MockDEX contract uses raw `IERC20.transfer()` and `IERC20.transferFrom()` calls instead of SafeERC20 wrappers.

```solidity
IERC20(tokenIn).transferFrom(msg.sender, address(this), amountIn);  // line 37
IERC20(tokenOut).transfer(msg.sender, amountOut);                    // line 44
```

Tokens like USDT that return no value on `transfer`/`transferFrom` would cause these calls to revert when compiled with Solidity 0.8.x (which expects a `bool` return). While this is a test contract, it means tests cannot accurately simulate behavior with non-standard tokens.

**Recommended Fix**: Use SafeERC20 in MockDEX to ensure tests accurately reflect production behavior.

---

### L-02: MockERC20 Has Unrestricted `mint` Function

**Severity**: LOW
**Contract**: `MockERC20.sol`, line 27-29

**Description**: The `mint` function has no access control -- anyone can mint arbitrary amounts.

```solidity
function mint(address to, uint256 amount) external {
    _mint(to, amount);
}
```

While this is clearly a test mock, if deployed to a testnet or accidentally to mainnet, it would create a worthless token. This is acceptable for testing purposes but should be documented.

**Recommended Fix**: Add a comment `// TESTING ONLY -- no access control by design` and/or add `onlyOwner` modifier.

---

### L-03: Missing Zero-Address Validation in Critical Functions

**Severity**: LOW
**Contracts**: All contracts

**Description**: Multiple functions accept address parameters without validating they are non-zero:
- `withdrawProfits(token, amount, to)` -- `to` could be `address(0)`
- `emergencyWithdraw(token, amount, to)` -- `to` could be `address(0)`
- `setDEXWhitelist(dex, status)` -- `dex` could be `address(0)`
- `setAdapter(adapter, status)` -- `adapter` could be `address(0)`
- Adapter `setAuthorized(account, status)` -- `account` could be `address(0)`

**Impact**: Sending tokens to `address(0)` would permanently burn them. While most ERC20 implementations revert on transfer to zero address, it is not guaranteed by the standard.

**Recommended Fix**: Add `require(to != address(0))` checks to all fund transfer functions.

---

### L-04: `executionCount` / `liquidationCount` Can Overflow After ~2^256 Executions

**Severity**: LOW
**Contracts**: All contracts

**Description**: The execution counters are `uint256` and increment without any overflow consideration. In Solidity 0.8.x, overflow would cause a revert. Practically, reaching `type(uint256).max` is impossible, but the counter provides no value if not used for logic and adds gas cost.

**Impact**: Negligible. The counter cannot realistically overflow.

**Recommended Fix**: Acceptable as-is. If gas optimization is desired, consider making counters `unchecked` or removing them if unused in on-chain logic.

---

## INFO Findings

### I-01: Solidity 0.8.20 Default EVM Version May Not Support All Chains

**Severity**: INFO
**Contracts**: All

**Description**: All contracts use `pragma solidity ^0.8.20`. Solidity 0.8.20+ defaults to the Shanghai EVM version which includes the `PUSH0` opcode. This opcode is not supported on all L2s (e.g., Arbitrum, some older versions). If deploying to chains without `PUSH0` support, compilation must specify `--evm-version paris` or earlier.

**Recommended Fix**: Explicitly specify EVM version in hardhat/foundry config, or document deployment chain requirements.

---

### I-02: `FlashLoanArbitrage` V1 `_swapOnDEX` Always Reverts

**Severity**: INFO
**Contract**: `FlashLoanArbitrage.sol`, lines 285-297

**Description**: The `_swapOnDEX` function is a placeholder that always reverts:
```solidity
revert("DEX swap not implemented - use DEXLibrary");
```

This means the V1 contract is non-functional. It appears to be superseded by V2 which uses the adapter pattern.

**Recommended Fix**: Either remove V1 from production deployment or implement the DEX logic. Consider marking V1 as deprecated.

---

### I-03: DEXLibrary `executeSwap` Hardcodes `FEE_MEDIUM` for V3 Swaps

**Severity**: INFO
**Contract**: `DEXLibrary.sol`, lines 168-178

**Description**: When `executeSwap` is called with `DEXType.UNISWAP_V3`, it always uses the `FEE_MEDIUM` (0.3%) tier. This may not be optimal for all token pairs -- stablecoin pairs typically use the 0.05% tier, and exotic pairs may use the 1% tier.

```solidity
if (dexType == DEXType.UNISWAP_V3) {
    amountOut = swapUniswapV3(router, tokenIn, tokenOut, amountIn, minAmountOut, FEE_MEDIUM, deadline);
}
```

**Recommended Fix**: Accept fee tier as a parameter or implement automatic fee tier detection (as done in `UniswapV3Adapter.findBestFee`).

---

## Summary of Approval Pattern Analysis

All production contracts correctly use `forceApprove` from OpenZeppelin's SafeERC20 (which handles USDT's non-standard approval behavior). Approvals are properly reset to 0 after use in adapters and the DEXLibrary. The approval to the Aave Pool for flash loan repayment uses `forceApprove` and is set to the exact `amountOwed`, which is correct.

| Contract | SafeERC20 Used | forceApprove | Approval Reset | Rating |
|----------|---------------|-------------|----------------|--------|
| FlashLoanArbitrage | Yes | Yes | Yes (L263) | Good |
| FlashLoanArbitrageV2 | Yes | Yes | N/A (adapters handle) | Good |
| BalancerFlashLoan | Yes | Yes | N/A (adapters handle) | Good |
| FlashLoanLiquidator | Yes | Yes | N/A (adapters handle) | Good |
| DEXLibrary | Yes | Yes | Yes (L104, L145) | Good |
| CurveAdapter | Yes | Yes | Yes (L160) | Good |
| UniswapV2Adapter | Yes | Yes | Yes (L135) | Good |
| UniswapV3Adapter | Yes | Yes | Yes (L170) | Good |
| MockDEX | **NO** | **NO** | **N/A** | **Fail** |
| MockERC20 | N/A | N/A | N/A | N/A |

---

## Summary of Balance Verification Pattern Analysis

| Contract | Balance Check Used | Notes |
|----------|-------------------|-------|
| FlashLoanArbitrage (V1) | **NO** | Trusts return value -- H-02 |
| FlashLoanArbitrageV2 | Yes (L189-211) | Correctly uses actualReceived |
| BalancerFlashLoan | Yes (L185-211) | Correctly uses actualReceived |
| FlashLoanLiquidator | Yes (L165-176, L182-198) | Separate checks for liquidation and swap |

---

## Summary of Integer Overflow/Underflow Analysis

All contracts use Solidity 0.8.20 with built-in overflow/underflow protection. No `unchecked` blocks were found in any contract. The only arithmetic concern is C-02 (underflow in error reporting in V1).

| Operation | Contract | Safe? | Notes |
|-----------|----------|-------|-------|
| `totalProfits += profit` | All | Yes | Protected by 0.8.x; theoretical max ~2^256 |
| `totalProfits -= amount` | All | Yes | Guarded by `require(amount <= totalProfits[token])` |
| `finalAmount - amountOwed` | V1 L210 | **NO** | C-02: Underflows when finalAmount < amountOwed |
| `amounts[0] + premiums[0]` | All | Yes | Aave premiums are small relative to amounts |
| `balanceAfter - balanceBefore` | V2, Balancer | Yes | balanceAfter >= balanceBefore guaranteed by swap |
| `(amount * 5) / 10000` | All | Yes | No overflow possible for reasonable amounts |
