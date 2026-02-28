# Security Audit Report #07: Gas Optimization, DoS Vectors & Deployment Readiness

**Auditor**: Agent 7 (Security Audit Swarm)
**Date**: 2026-02-27
**Scope**: All Solidity contracts in `/contracts/` and subdirectories
**Focus**: Gas optimization, denial-of-service vectors, code quality, deployment readiness

---

## Executive Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 2     |
| HIGH     | 5     |
| MEDIUM   | 6     |
| LOW      | 5     |
| INFO     | 6     |
| **Total**| **24**|

The codebase contains two critical deployment-blocking issues: the V1 contract's `_swapOnDEX` function always reverts (rendering it non-functional), and unbounded loop iterations across all arbitrage/flash-loan contracts expose the system to block gas limit failures on complex paths. Several high-severity gas optimization opportunities exist, including redundant approval resets, repeated storage reads for event emission, and an inefficient struct-copy pattern in hot loops. Multiple code quality issues -- missing NatSpec on admin functions, inconsistent compiler pragmas, and dead code -- reduce auditability and increase deployment risk.

---

## Findings

### G-01: V1 `_swapOnDEX` Always Reverts -- Contract Is Non-Functional

**Severity**: CRITICAL
**Contract**: `FlashLoanArbitrage.sol`
**Lines**: 285-297

**Description**:
The internal function `_swapOnDEX` unconditionally reverts with the string `"DEX swap not implemented - use DEXLibrary"`. Because `_executeSwaps` (line 238) calls `_swapOnDEX` on every iteration, and `executeArbitrage` calls `_executeSwaps` inside the flash loan callback, every arbitrage attempt on V1 will revert -- after the flash loan is already drawn. While the revert will unwind the transaction (no funds lost), gas is wasted and the contract is completely non-functional.

```solidity
function _swapOnDEX(
    address router,
    address tokenIn,
    address tokenOut,
    uint256 amountIn,
    uint256 minAmountOut,
    uint256 deadline
) internal returns (uint256) {
    // TODO: Implement specific DEX logic
    // This will be implemented in the DEXLibrary
    // For now, return amountIn as placeholder
    revert("DEX swap not implemented - use DEXLibrary");
}
```

**Impact**: FlashLoanArbitrage (V1) cannot execute any arbitrage. Any transaction that reaches this code path will revert, consuming gas for flash loan initiation, calldata decoding, and loop setup before hitting the revert.

**Recommendation**:
- **Option A**: Remove V1 from production deployment entirely if V2 (adapter pattern) is the intended production contract.
- **Option B**: Integrate `DEXLibrary` calls into `_swapOnDEX` with proper router-type dispatch. However, given that V2 already solves this with the adapter pattern, option A is strongly preferred.
- At minimum, mark the contract as `abstract` or add a prominent deprecation notice.

---

### G-02: Unbounded Loop Iterations -- Block Gas Limit Risk

**Severity**: CRITICAL
**Contracts**: `FlashLoanArbitrageV2.sol`, `BalancerFlashLoan.sol`, `FlashLoanArbitrage.sol`
**Lines**: V2 lines 124-128 and 185-216; Balancer lines 133-137 and 182-211; V1 lines 137-141 and 242-264

**Description**:
All three arbitrage contracts iterate over user-supplied arrays (`params.steps[]` in V2/Balancer, `params.dexRouters[]` in V1) without enforcing an upper bound on the number of elements. Each swap step involves:
- An ERC20 `balanceOf` call (~2,600 gas)
- A `safeTransfer` to the adapter (~25,000-65,000 gas depending on token)
- An external `swapDirect` call to the adapter, which internally performs another approval + swap + approval reset (~100,000-300,000 gas per DEX interaction)
- Another `balanceOf` call (~2,600 gas)
- Memory struct copy and local variable updates

A single swap step costs approximately 150,000-400,000 gas. With the Ethereum block gas limit at 30M gas and the overhead of the flash loan itself (~150,000 gas), a path with more than approximately 50-75 steps could exceed the block gas limit and always revert.

More critically, on L2 chains (Polygon, Arbitrum, Optimism, Base -- all configured in `hardhat.config.js`), gas limits and pricing differ. On Arbitrum, the effective gas limit can be lower for complex calldata.

```solidity
// V2 executeOperation, line 185 -- no bound check on arbParams.steps.length
for (uint256 i = 0; i < arbParams.steps.length; i++) {
    SwapStep memory step = arbParams.steps[i];
    // ... expensive operations per step
}
```

**Impact**: Transactions with too many steps will always revert at the block gas limit, wasting the gas up to that point. While the owner controls the input, a misconfigured off-chain bot could repeatedly submit over-gas-limit transactions, burning ETH on reverts.

**Recommendation**:
Add a maximum steps constant and enforce it at the beginning of `executeArbitrage`:

```solidity
uint256 public constant MAX_STEPS = 10;

// In executeArbitrage:
if (params.steps.length > MAX_STEPS) revert TooManySteps();
```

Ten steps is a reasonable upper bound -- most profitable arbitrage opportunities are 2-4 hops. This also makes gas estimation predictable for the off-chain bot.

---

### G-03: Event Emits Cumulative `totalProfits` Storage Read Instead of Calculated Profit

**Severity**: HIGH
**Contracts**: `FlashLoanArbitrageV2.sol`, `BalancerFlashLoan.sol`
**Lines**: V2 lines 157-162; Balancer lines 155-160

**Description**:
After `executeOperation` / `receiveFlashLoan` returns, the `executeArbitrage` function emits an event with `totalProfits[params.flashLoanAsset]` as the `profit` field:

```solidity
emit ArbitrageExecuted(
    params.flashLoanAsset,
    params.flashLoanAmount,
    totalProfits[params.flashLoanAsset],  // SLOAD: ~2,100 gas (warm)
    gasUsed
);
```

This has two problems:
1. **Gas cost**: This is a storage read (`SLOAD`, 2,100 gas warm) that could be avoided by returning the profit from the callback or caching it.
2. **Semantic error**: The event's `profit` field contains the *cumulative* total profit for that token across all executions, not the profit from *this* execution. Any off-chain monitoring, analytics, or event-based accounting will misinterpret this value.

**Impact**: Incorrect profit data emitted in events; wasted gas on unnecessary storage read.

**Recommendation**:
Store the profit from the current execution in a transient storage variable or a contract-level variable that the callback sets:

```solidity
// Add to contract state:
uint256 private _lastProfit;

// In executeOperation / receiveFlashLoan, before return:
_lastProfit = profit;

// In executeArbitrage, emit:
emit ArbitrageExecuted(
    params.flashLoanAsset,
    params.flashLoanAmount,
    _lastProfit,  // current execution profit
    gasUsed
);
```

On Solidity 0.8.24+ (if the pragma is updated), use EIP-1153 transient storage (`tstore`/`tload`) for zero-cost cross-function communication within the same transaction.

---

### G-04: Redundant Approval Reset After `forceApprove`

**Severity**: HIGH
**Contracts**: `FlashLoanArbitrage.sol`, `DEXLibrary.sol`, `UniswapV2Adapter.sol`, `UniswapV3Adapter.sol`, `CurveAdapter.sol`
**Lines**: V1 line 263; DEXLibrary lines 104, 145; UniswapV2Adapter line 135; UniswapV3Adapter line 170; CurveAdapter line 160

**Description**:
The codebase follows a pattern of `forceApprove(spender, amount)` before a swap, then `forceApprove(spender, 0)` after the swap. While resetting approvals to zero is a security best practice (prevents lingering approvals if the spender is compromised), the reset is redundant when:
1. The spender consumed the full approved amount during the swap (common for `exactInput` style swaps).
2. `forceApprove` is used on the next call anyway, which overwrites whatever the current allowance is.

Each `forceApprove(spender, 0)` costs approximately 5,000 gas (warm SSTORE from non-zero to zero, with the EIP-2929 warm access cost). In a 4-step arbitrage, this adds 20,000 gas of overhead purely from approval resets.

```solidity
// In V1 _executeSwaps loop:
IERC20(tokenIn).forceApprove(dexRouter, currentAmount);
currentAmount = _swapOnDEX(dexRouter, tokenIn, tokenOut, currentAmount, 0, params.deadline);
IERC20(tokenIn).forceApprove(dexRouter, 0);  // 5,000 gas wasted if fully consumed
```

**Impact**: 5,000 gas per step wasted, ~20,000+ gas per multi-hop arbitrage. Over thousands of executions, this is material.

**Recommendation**:
Remove the approval resets from the hot path (adapters and V1 loop). The `forceApprove` at the start of each step already handles non-zero-to-non-zero transitions safely. If lingering approval risk is a concern, consider using `safeIncreaseAllowance` by the exact amount, or check the remaining allowance post-swap and only reset if non-zero:

```solidity
// Only reset if there's a remaining allowance (swap didn't consume all)
uint256 remaining = IERC20(tokenIn).allowance(address(this), spender);
if (remaining > 0) {
    IERC20(tokenIn).forceApprove(spender, 0);
}
```

However, even the `allowance` check costs ~2,600 gas (external call). The simplest gas-optimal approach: remove the reset entirely and rely on `forceApprove` overwriting on the next call.

---

### G-05: Struct Memory Copy in Hot Loop

**Severity**: HIGH
**Contracts**: `FlashLoanArbitrageV2.sol`, `BalancerFlashLoan.sol`
**Lines**: V2 line 186; Balancer line 183

**Description**:
Inside the swap loop in `executeOperation` / `receiveFlashLoan`, the code copies a `SwapStep` from the `ArbitrageParams memory` struct into a new `memory` variable:

```solidity
SwapStep memory step = arbParams.steps[i];
```

The `SwapStep` struct contains 5 fields including a `bytes data` field. When `arbParams` is decoded from calldata via `abi.decode`, the entire struct array is already in memory. Assigning `step` creates a reference (not a deep copy) for fixed-size fields, but the `bytes data` field remains a pointer. This is actually cheaper than accessing `arbParams.steps[i]` repeatedly -- so the current pattern is acceptable for the fixed fields.

However, the entire `ArbitrageParams` struct (including all steps) is first decoded from calldata into memory at line 179/176:
```solidity
ArbitrageParams memory arbParams = abi.decode(params, (ArbitrageParams));
```

This `abi.decode` copies all step data from calldata to memory, which is O(n) in the number of steps and their data sizes. For large `bytes data` fields or many steps, this memory allocation is significant.

**Impact**: Gas overhead scales linearly with the number of steps and the size of adapter-specific `data` fields. For a 5-step path with 32-byte data each, this adds approximately 5,000-10,000 gas for the memory copies.

**Recommendation**:
Consider accessing calldata directly where possible instead of decoding the entire struct into memory. Since `params` is `calldata` in `executeOperation`, you could decode individual fields lazily. However, Solidity's ABI decoder makes this difficult for nested dynamic types. The current approach is acceptable but should be paired with the MAX_STEPS limit from G-02 to bound memory allocation.

---

### G-06: Missing Initiator Check in `BalancerFlashLoan.receiveFlashLoan`

**Severity**: HIGH
**Contract**: `BalancerFlashLoan.sol`
**Lines**: 167-172

**Description**:
The Balancer flash loan callback `receiveFlashLoan` only checks that `msg.sender` is the Vault:

```solidity
function receiveFlashLoan(
    IERC20[] calldata tokens,
    uint256[] calldata amounts,
    uint256[] calldata feeAmounts,
    bytes calldata userData
) external override {
    if (msg.sender != address(VAULT)) revert UnauthorizedCaller();
    // ... no check that this contract initiated the flash loan
```

Unlike the Aave-based contracts (V1 and V2), which verify `initiator == address(this)`, the Balancer callback does not verify the initiator. While Balancer's flash loan design does not pass an `initiator` parameter, this means any contract that can trigger Balancer to call `receiveFlashLoan` on this contract could potentially execute arbitrary swap paths using this contract's funds.

In practice, Balancer's Vault only calls `receiveFlashLoan` on the `recipient` address passed to `flashLoan()`. Since only `executeArbitrage` (which is `onlyOwner`) calls `VAULT.flashLoan(address(this), ...)`, and `receiveFlashLoan` is called by the Vault in the same transaction, this is partially mitigated. However, if another contract passes `address(this)` as the recipient in a direct call to the Vault, the callback would execute with attacker-controlled `userData`.

**Impact**: A sophisticated attacker could craft a flash loan via Balancer's Vault with this contract as recipient, passing malicious `userData` that decodes to valid `ArbitrageParams` with malicious adapter addresses. The adapter whitelist check in `executeArbitrage` would NOT apply because the callback is reached directly. However, the adapters referenced in `userData` must still be registered (checked in `executeArbitrage` before the flash loan), and the callback does not re-check adapter registration.

**Recommendation**:
Add a reentrancy-style execution flag to ensure `receiveFlashLoan` is only callable when preceded by `executeArbitrage`:

```solidity
bool private _executing;

function executeArbitrage(...) external onlyOwner nonReentrant whenNotPaused {
    _executing = true;
    // ... flash loan call ...
    _executing = false;
    // ...
}

function receiveFlashLoan(...) external override {
    if (msg.sender != address(VAULT)) revert UnauthorizedCaller();
    if (!_executing) revert UnauthorizedCaller();
    // ...
}
```

Additionally, re-validate adapter registration inside `receiveFlashLoan` before executing swaps.

---

### G-07: `executionCount` Increment Is a Warm SSTORE on Every Execution

**Severity**: MEDIUM
**Contracts**: `FlashLoanArbitrage.sol`, `FlashLoanArbitrageV2.sol`, `BalancerFlashLoan.sol`, `FlashLoanLiquidator.sol`
**Lines**: V1 line 175; V2 line 154; Balancer line 152; Liquidator line 132

**Description**:
Each contract increments a storage counter `executionCount++` (or `liquidationCount++`) on every successful execution. This is a warm SSTORE operation costing 5,000 gas (non-zero to non-zero). For a MEV bot that may execute hundreds of times per day, this is wasted gas for a counter that provides no on-chain utility.

```solidity
executionCount++;  // 5,000 gas per execution
```

**Impact**: 5,000 gas per execution. Over 1,000 executions, that is 5M gas -- approximately $2-10 USD at typical gas prices.

**Recommendation**:
Remove the storage counter if it serves no on-chain purpose. The execution count can be derived off-chain from event logs. If it must remain on-chain (e.g., for a front-end), consider using EIP-1153 transient storage or batching the counter update.

---

### G-08: Adapter Validation Loop Iterates Before Flash Loan -- Duplicated Gas on Revert

**Severity**: MEDIUM
**Contracts**: `FlashLoanArbitrageV2.sol`, `BalancerFlashLoan.sol`
**Lines**: V2 lines 124-128; Balancer lines 133-137

**Description**:
The adapter validation loop in `executeArbitrage` iterates over all steps to check that each adapter is registered:

```solidity
for (uint256 i = 0; i < params.steps.length; i++) {
    if (!registeredAdapters[params.steps[i].adapter]) {
        revert UnauthorizedAdapter(params.steps[i].adapter);
    }
}
```

This is good for failing fast. However, `params.steps[i].adapter` is accessed from calldata on each iteration, which involves ABI decoding of the dynamic array offset. For small step counts (2-4), this is negligible. For the maximum steps (if G-02 is not implemented), this could be costly.

Additionally, the loop uses `i++` instead of `++i`, which is slightly more gas-expensive in Solidity versions before 0.8.22 (the compiler may not optimize this automatically with `viaIR` enabled).

**Impact**: Minor gas overhead per step (a few hundred gas). The `i++` vs `++i` difference is ~3-5 gas per iteration.

**Recommendation**:
- Use `unchecked { ++i; }` in the loop increment (the overflow is impossible given the bounded array length after G-02 is applied).
- This applies to ALL loops in the codebase.

```solidity
for (uint256 i = 0; i < params.steps.length; ) {
    if (!registeredAdapters[params.steps[i].adapter]) {
        revert UnauthorizedAdapter(params.steps[i].adapter);
    }
    unchecked { ++i; }
}
```

---

### G-09: DoS via Malicious or Reverting Token Transfers

**Severity**: MEDIUM
**Contracts**: `FlashLoanArbitrageV2.sol`, `BalancerFlashLoan.sol`, `FlashLoanLiquidator.sol`
**Lines**: V2 line 192; Balancer line 188; Liquidator line 180

**Description**:
The contracts use `safeTransfer` to send tokens to adapters before executing swaps. If a token's `transfer` function always reverts (e.g., a paused token, a blocklisted address, or a malicious token), the entire arbitrage transaction reverts.

```solidity
IERC20(step.tokenIn).safeTransfer(step.adapter, currentAmount);
```

While the owner controls which tokens are used in arbitrage paths, the following scenarios could cause DoS:
1. A token admin pauses the token mid-execution (sandwich attack timing)
2. The contract address gets blocklisted on USDC/USDT (Circle/Tether can blocklist addresses)
3. A token with fee-on-transfer silently reduces the amount, causing the subsequent swap to fail with insufficient input

**Impact**: Certain token types (pausable, blocklist-enabled, fee-on-transfer) could cause transactions to always revert for specific paths.

**Recommendation**:
- Document the supported token types clearly (standard ERC20 only, no fee-on-transfer, no rebasing).
- Add balance-before/after checks for the `safeTransfer` to adapters (similar to what is already done for swap outputs).
- For blocklist-prone tokens (USDC, USDT), monitor the blocklist status off-chain before submitting transactions.

---

### G-10: DoS via Adapter Revert -- Single Malicious Adapter Blocks All Paths

**Severity**: MEDIUM
**Contracts**: `FlashLoanArbitrageV2.sol`, `BalancerFlashLoan.sol`
**Lines**: V2 lines 195-215; Balancer lines 191-211

**Description**:
If a registered adapter's `swapDirect` function always reverts (due to a bug, upgrade, or malicious behavior), any arbitrage path that includes that adapter will fail. The `try/catch` block catches the revert but then reverts the entire transaction with `SwapFailed(i)`:

```solidity
try IDEXAdapter(step.adapter).swapDirect(...) returns (uint256 amountOut) {
    // ...
} catch {
    revert SwapFailed(i);
}
```

This is the correct behavior for atomicity (you do not want to continue a partial arbitrage path). However, a compromised or buggy adapter could prevent the owner from executing any arbitrage path that routes through it.

**Impact**: A single failing adapter blocks all paths that include it. The owner must detect the failure and unregister the adapter.

**Recommendation**:
- Implement adapter health monitoring off-chain (track consecutive failures and auto-unregister).
- Consider an `adapterTimelock` mechanism where newly registered adapters have a grace period before they can be used, giving the owner time to verify.
- The existing `setAdapter(address, false)` mechanism is sufficient for manual response, but automated detection is recommended.

---

### G-11: Gas Griefing via External `balanceOf` Calls in Swap Loop

**Severity**: MEDIUM
**Contracts**: `FlashLoanArbitrageV2.sol`, `BalancerFlashLoan.sol`
**Lines**: V2 lines 189, 207; Balancer lines 185, 202

**Description**:
Each swap step makes two `balanceOf` calls -- one before and one after the swap -- to verify the actual amount received:

```solidity
uint256 balanceBefore = IERC20(step.tokenOut).balanceOf(address(this));
// ... swap ...
uint256 balanceAfter = IERC20(step.tokenOut).balanceOf(address(this));
```

This is a critical security check (prevents adapter return value manipulation, referenced as C-04 in the code). However, each `balanceOf` is an external call costing ~2,600 gas (warm). With N steps, that is 5,200 * N gas overhead.

If a malicious token has an expensive `balanceOf` implementation (e.g., iterating over a large data structure), this could be used for gas griefing.

**Impact**: 5,200 gas per step for the balance checks. A malicious token could amplify this significantly.

**Recommendation**:
- Keep the balance verification -- it is a critical security control. The gas cost is acceptable for the security benefit.
- Mitigate gas griefing by only using well-known, audited tokens in arbitrage paths (enforce off-chain).
- The MAX_STEPS limit from G-02 bounds the total overhead.

---

### G-12: Compiler Pragma `^0.8.20` Allows Range -- Should Be Pinned for Production

**Severity**: MEDIUM
**Contracts**: All production contracts (V1, V2, Balancer, Liquidator, all adapters, DEXLibrary, IDEXAdapter)
**Lines**: Line 2 in each contract

**Description**:
All production contracts use `pragma solidity ^0.8.20;` which allows compilation with any 0.8.x version >= 0.8.20. While `hardhat.config.js` pins the compiler to `0.8.20`, a different build tool or a developer using a different config could compile with 0.8.21+ which may have different optimizer behavior or introduce new opcodes (e.g., `PUSH0` was introduced in 0.8.20 for the Shanghai upgrade and is not supported on all L2s).

The mock contracts use `^0.8.19` which is inconsistent with the production contracts.

**Impact**: Inconsistent compilation across environments. On chains that do not support Shanghai EVM (pre-Dencun), the `PUSH0` opcode from 0.8.20+ will cause deployment failure.

**Recommendation**:
Pin the pragma to an exact version for all production contracts:

```solidity
pragma solidity 0.8.20;
```

Verify `PUSH0` support on all target chains (Polygon, Arbitrum, Optimism, Base). At the time of writing, all listed target chains support Shanghai, so 0.8.20 is safe. But pinning prevents accidental compilation with a different version.

---

### G-13: `FlashLoanLiquidator.executeLiquidation` Emits Stale `collateralReceived` (Always 0)

**Severity**: LOW
**Contract**: `FlashLoanLiquidator.sol`
**Lines**: 135-143

**Description**:
The `LiquidationExecuted` event is emitted in `executeLiquidation` with `collateralReceived: 0`:

```solidity
emit LiquidationExecuted(
    params.user,
    params.debtAsset,
    params.collateralAsset,
    params.debtToCover,
    0, // filled in callback  <-- this comment is incorrect, it is never filled
    totalProfits[params.debtAsset],
    gasUsed
);
```

The comment says "filled in callback" but the callback (`executeOperation`) does not emit any event, so the actual collateral received is never recorded in events. Additionally, like G-03, `totalProfits[params.debtAsset]` is the cumulative profit, not this execution's profit.

**Impact**: Off-chain monitoring cannot determine collateral received or per-execution profit from events alone.

**Recommendation**:
Use the same transient-variable pattern recommended in G-03 to pass `collateralReceived` and `profit` from the callback to the event emission.

---

### G-14: MockDEX and MockERC20 Have No Access Control

**Severity**: LOW
**Contracts**: `MockDEX.sol`, `MockERC20.sol`
**Lines**: MockDEX line 72; MockERC20 line 27

**Description**:
`MockDEX.withdraw` and `MockERC20.mint` are callable by anyone:

```solidity
// MockDEX
function withdraw(address token, uint256 amount) external {
    IERC20(token).transfer(msg.sender, amount);
}

// MockERC20
function mint(address to, uint256 amount) external {
    _mint(to, amount);
}
```

**Impact**: If these contracts are accidentally deployed to a production network, anyone can drain the DEX or mint unlimited tokens.

**Recommendation**:
- Add `onlyOwner` modifiers or equivalent access control.
- More importantly, ensure these contracts are in a `test/` or `mocks/` directory and explicitly excluded from production deployment scripts.
- Consider adding a check: `require(block.chainid == 31337, "Mock only")` to prevent mainnet deployment.

---

### G-15: Adapters Use Custom Ownership Instead of OpenZeppelin Ownable

**Severity**: LOW
**Contracts**: `UniswapV2Adapter.sol`, `UniswapV3Adapter.sol`, `CurveAdapter.sol`
**Lines**: All adapter contracts

**Description**:
All three adapter contracts implement custom `owner` state variables and `onlyOwner`/`transferOwnership` logic instead of inheriting from OpenZeppelin's `Ownable` (which the main contracts use). This is inconsistent and misses features:
- No `renounceOwnership` (which may be intentional -- but should be documented)
- No event emitted on construction for initial owner
- `transferOwnership` does not use a two-step pattern (no pending owner confirmation)
- The `Unauthorized()` error is redefined in each adapter instead of sharing a common definition

**Impact**: Inconsistent access control implementation across the codebase. The custom implementation is functionally correct but less battle-tested than OpenZeppelin's.

**Recommendation**:
Either:
- Inherit `Ownable` from OpenZeppelin for consistency, or
- Use `Ownable2Step` from OpenZeppelin for a safer two-step ownership transfer pattern.

---

### G-16: `FlashLoanArbitrage.sol` V1 Loop Does Not Use `unchecked` Increment

**Severity**: LOW
**Contract**: `FlashLoanArbitrage.sol`
**Lines**: 137, 242

**Description**:
The V1 contract uses standard `i++` in its loops:

```solidity
for (uint256 i = 0; i < params.dexRouters.length; i++) {
```

Since `i` is bounded by the array length (which fits in `uint256`), overflow is impossible. Using `unchecked { ++i; }` saves approximately 30-60 gas per iteration by skipping the overflow check.

**Impact**: Minor gas savings (~30-60 gas per loop iteration).

**Recommendation**:
Apply `unchecked { ++i; }` to all loop increments across the codebase. This applies to every `for` loop in every contract.

---

### G-17: Missing `receive()` and `fallback()` Functions

**Severity**: LOW
**Contracts**: All production contracts

**Description**:
None of the production contracts define `receive()` or `fallback()` functions. If native ETH is accidentally sent to any contract (e.g., from a DEX router returning ETH, or a user mistakenly sending ETH), the transaction will revert and the ETH is not lost -- but it could cause unexpected failures in integrations.

If any adapter wraps/unwraps WETH as part of a swap path, the contract would need a `receive()` function to accept ETH.

**Impact**: Cannot interact with ETH-based swap paths. ETH sent to contracts is safely rejected.

**Recommendation**:
If WETH wrapping/unwrapping is planned:
```solidity
receive() external payable {}
```

If not, the current behavior (rejecting ETH) is acceptable. Document this limitation.

---

### G-18: Missing NatSpec on Admin Functions in BalancerFlashLoan and FlashLoanLiquidator

**Severity**: INFO
**Contracts**: `BalancerFlashLoan.sol`, `FlashLoanLiquidator.sol`
**Lines**: Balancer lines 242-283; Liquidator lines 240-266

**Description**:
The admin functions in `BalancerFlashLoan` (lines 242-283) and several in `FlashLoanLiquidator` (lines 240-266) have no NatSpec documentation:

```solidity
// BalancerFlashLoan -- no NatSpec:
function setAdapter(address adapter, bool status) external onlyOwner { ... }
function setMinProfit(uint256 _minProfit) external onlyOwner { ... }
function setMaxSlippage(uint256 _maxSlippageBps) external onlyOwner { ... }
function pause() external onlyOwner { ... }
function unpause() external onlyOwner { ... }
function withdrawProfits(...) external onlyOwner nonReentrant { ... }
function emergencyWithdraw(...) external onlyOwner nonReentrant { ... }
function getBalance(address token) external view returns (uint256) { ... }
```

The V1 and V2 contracts have NatSpec on most functions, but these were omitted for the admin functions in the later contracts.

**Impact**: Reduced code auditability. Missing NatSpec makes it harder for future auditors and developers to understand function behavior and parameter constraints.

**Recommendation**:
Add NatSpec to all public/external functions following the format used in V1/V2.

---

### G-19: `IDEXAdapter` Interface Does Not Declare `getQuote`

**Severity**: INFO
**Contract**: `interfaces/IDEXAdapter.sol`
**Lines**: 1-18

**Description**:
The `IDEXAdapter` interface only declares `swapDirect`. All three adapters implement `getQuote` but with different signatures:
- `UniswapV2Adapter.getQuote(address, address, uint256)` -- 3 params
- `UniswapV3Adapter.getQuote(address, address, uint256, uint24)` -- 4 params
- `CurveAdapter.getQuote(address, address, uint256)` -- 3 params

Since `getQuote` is not in the interface, callers cannot generically query quotes through the adapter pattern.

**Impact**: Off-chain systems cannot use a unified interface for quote fetching. Each adapter must be called with its specific signature.

**Recommendation**:
Add a `getQuote` function to `IDEXAdapter` with `bytes calldata data` for adapter-specific parameters (matching the `swapDirect` pattern):

```solidity
function getQuote(
    address tokenIn,
    address tokenOut,
    uint256 amountIn,
    bytes calldata data
) external returns (uint256 amountOut);
```

---

### G-20: TODO Comment Left in Production Code

**Severity**: INFO
**Contract**: `FlashLoanArbitrage.sol`
**Lines**: 293-294

**Description**:
```solidity
// TODO: Implement specific DEX logic
// This will be implemented in the DEXLibrary
```

TODO comments in production code indicate incomplete implementation.

**Impact**: Code quality issue. Indicates the V1 contract is not production-ready.

**Recommendation**:
Remove the TODO and either implement the function or remove the V1 contract from the deployment.

---

### G-21: `DEXLibrary.executeSwap` Does Not Support Curve DEXType

**Severity**: INFO
**Contract**: `DEXLibrary.sol`
**Lines**: 159-195

**Description**:
The `DEXType` enum includes `CURVE` (line 56), but `executeSwap` does not handle it -- the function falls through to `revert("Unsupported DEX type")`:

```solidity
enum DEXType {
    UNISWAP_V2,
    UNISWAP_V3,
    SUSHISWAP,
    QUICKSWAP,
    CURVE       // Declared but not handled
}
```

**Impact**: Attempting to use `DEXLibrary.executeSwap` with `DEXType.CURVE` will revert. Since V2 uses the adapter pattern instead of `DEXLibrary`, this is primarily a dead code concern.

**Recommendation**:
Either implement Curve support in `DEXLibrary.executeSwap` or remove `CURVE` from the enum to avoid confusion.

---

### G-22: `FlashLoanArbitrage.sol` (V1) `maxSlippageBps` Is Set But Never Used

**Severity**: INFO
**Contract**: `FlashLoanArbitrage.sol`
**Lines**: 37, 110, 323-328

**Description**:
The V1 contract declares `maxSlippageBps`, allows the owner to set it via `setMaxSlippage`, but never reads it in the swap execution logic. The slippage check in `_executeSwaps` uses `params.minAmountOut` which is provided by the caller:

```solidity
if (currentAmount < params.minAmountOut) {
    revert SlippageExceeded(currentAmount, params.minAmountOut);
}
```

The `maxSlippageBps` state variable is never used to calculate or validate slippage.

**Impact**: Dead state variable. Gas is wasted on `setMaxSlippage` transactions that have no effect.

**Recommendation**:
Either integrate `maxSlippageBps` into the slippage validation logic or remove it.

---

### G-23: V2 `setMaxSlippage` Does Not Emit an Event

**Severity**: INFO
**Contracts**: `FlashLoanArbitrageV2.sol`, `BalancerFlashLoan.sol`
**Lines**: V2 lines 270-273; Balancer lines 253-256

**Description**:
`setMaxSlippage` in V2 and Balancer updates the storage variable but does not emit an event:

```solidity
function setMaxSlippage(uint256 _maxSlippageBps) external onlyOwner {
    require(_maxSlippageBps <= 1000, "Slippage too high");
    maxSlippageBps = _maxSlippageBps;
}
```

By contrast, `setMinProfit` emits `MinProfitUpdated`. This inconsistency means configuration changes to slippage are not auditable via events.

**Impact**: Off-chain monitoring cannot track slippage configuration changes.

**Recommendation**:
Add a `MaxSlippageUpdated(uint256 oldValue, uint256 newValue)` event and emit it in `setMaxSlippage`.

---

### G-24: `FlashLoanLiquidator.executeOperation` Has Redundant Profit Check

**Severity**: INFO (Gas Waste)
**Contract**: `FlashLoanLiquidator.sol`
**Lines**: 203-224

**Description**:
The liquidator's `executeOperation` performs two sequential profit checks:

```solidity
// Check 1 (line 203):
if (swapReceived + amounts[0] <= amountOwed) {
    revert InsufficientProfit(0, liqParams.minProfit);
}

// Check 2 (line 218):
if (swapReceived < amountOwed) {
    revert InsufficientProfit(0, liqParams.minProfit);
}
```

Check 1 is logically incorrect in context. As the comments on lines 210-216 explain, after liquidation the contract has 0 debt tokens, and after the swap it has `swapReceived` debt tokens. The relevant check is `swapReceived < amountOwed` (Check 2). Check 1 tests `swapReceived + amounts[0] <= amountOwed`, which will almost never trigger because `amounts[0]` is the full flash loan amount. Check 1 is effectively dead code.

**Impact**: Wasted gas on an always-passing check (~200 gas for the comparison and addition).

**Recommendation**:
Remove Check 1 (lines 203-207) and keep only Check 2.

---

## Gas Optimization Summary

### Per-Transaction Savings (Estimated)

| Optimization | Savings per Tx | Priority |
|---|---|---|
| G-04: Remove approval resets in hot path | ~20,000 gas (4-step path) | HIGH |
| G-03: Emit profit from local var instead of SLOAD | ~2,100 gas | HIGH |
| G-07: Remove `executionCount` storage increment | ~5,000 gas | MEDIUM |
| G-08: Use `unchecked { ++i; }` in all loops | ~200 gas (4-step path) | LOW |
| G-11: Balance checks are necessary (keep) | N/A (security-critical) | N/A |

### Total estimated savings per 4-step arbitrage: ~27,300 gas (~$0.01-0.05 at typical gas prices)

Over 1,000 executions: ~27.3M gas saved (~$10-50 USD)

### Deployment Readiness Checklist

| Item | Status | Notes |
|---|---|---|
| V1 contract functional | FAIL | `_swapOnDEX` always reverts (G-01) |
| V2 contract functional | PASS | Adapter pattern works correctly |
| Balancer contract functional | PASS | With G-06 fix recommended |
| Liquidator contract functional | PASS | With G-13 event fix recommended |
| Bounded loops | FAIL | No MAX_STEPS limit (G-02) |
| Compiler version pinned | FAIL | Uses `^0.8.20` range (G-12) |
| All functions documented | FAIL | Admin functions missing NatSpec (G-18) |
| No TODO comments | FAIL | V1 has TODO (G-20) |
| No dead code | FAIL | V1 placeholder, DEXLibrary Curve gap (G-21, G-22) |
| Events accurate | FAIL | Cumulative profit emitted, not per-tx (G-03, G-13) |
| Adapters use standard Ownable | WARN | Custom implementation (G-15) |

### Recommended Deployment Order

1. Fix G-01 (remove V1 from deployment or mark abstract)
2. Fix G-02 (add MAX_STEPS constant to V2, Balancer, and Liquidator)
3. Fix G-06 (add execution guard to Balancer callback)
4. Fix G-03 and G-13 (correct event emission for profit tracking)
5. Fix G-12 (pin compiler pragma)
6. Apply gas optimizations G-04, G-07, G-08
7. Address all INFO-level items before mainnet deployment
