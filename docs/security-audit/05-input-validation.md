# Security Audit Report: Input Validation & Edge Cases

**Agent**: 5 of 7 (Input Validation & Edge Cases)
**Date**: 2026-02-27
**Scope**: All Solidity contracts in `/contracts/`
**Contracts Audited**:
- `FlashLoanArbitrage.sol` (V1)
- `FlashLoanArbitrageV2.sol` (V2)
- `BalancerFlashLoan.sol`
- `FlashLoanLiquidator.sol`
- `adapters/UniswapV2Adapter.sol`
- `adapters/UniswapV3Adapter.sol`
- `adapters/CurveAdapter.sol`
- `interfaces/IDEXAdapter.sol`
- `libraries/DEXLibrary.sol`

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 3     |
| HIGH     | 7     |
| MEDIUM   | 8     |
| LOW      | 6     |
| INFO     | 4     |
| **Total** | **28** |

---

## CRITICAL Findings

### IV-C01: V1 Array Length Mismatch Allows Out-of-Bounds Access

**Severity**: CRITICAL
**Contract**: `FlashLoanArbitrage.sol`
**Lines**: 132-141, 242-244

**Description**: In `_executeSwaps`, the loop iterates `params.dexRouters.length` times and accesses `params.path[i + 1]` on each iteration (line 244). However, the only path validation (line 132) checks that `params.path.length >= 3` and that it is circular (first == last). There is no check that `dexRouters.length == path.length - 1`.

If an attacker (the owner) provides `dexRouters.length > path.length - 1`, the loop accesses `params.path` out of bounds, which in Solidity 0.8+ causes a revert. Conversely, if `dexRouters.length < path.length - 1`, some hops in the path are silently skipped -- the swap sequence terminates early without executing all intended hops.

**Attack Scenario**: Owner submits `dexRouters = [routerA]` with `path = [USDC, WETH, WBTC, USDC]`. Only the USDC->WETH swap executes. The contract then attempts to repay the flash loan with WETH instead of USDC, causing the Aave repayment to fail. While this reverts the transaction (so no funds are lost), the owner cannot detect this off-chain without understanding the silent truncation -- the transaction simply reverts with an opaque Aave error rather than a clear "path/router mismatch" error.

More dangerously, if `dexRouters.length > path.length - 1`, the out-of-bounds array access causes a panic revert (0x32), which is indistinguishable from other failures and wastes gas.

**Recommended Fix**:
```solidity
// In executeArbitrage(), after the path.length check:
if (params.dexRouters.length != params.path.length - 1) {
    revert InvalidPath();
}
```

---

### IV-C02: No Zero Address Validation on Constructor Immutables

**Severity**: CRITICAL
**Contract**: `FlashLoanArbitrage.sol` (line 107), `FlashLoanArbitrageV2.sol` (line 102), `BalancerFlashLoan.sol` (line 112), `FlashLoanLiquidator.sol` (line 92)
**Lines**: As noted

**Description**: None of the four main contracts validate that their constructor address parameters are non-zero before storing them as `immutable` state. Since immutable variables cannot be changed after deployment, a deployment with `address(0)` permanently bricks the contract.

Specifically:
- `FlashLoanArbitrage`: `_addressProvider` is cast to `IPoolAddressesProvider` and used to derive `POOL` via `getPool()`. If `_addressProvider == address(0)`, the `getPool()` call reverts at deployment, BUT if a future Solidity or EVM change alters zero-address call behavior, the contract would be permanently broken.
- `FlashLoanArbitrageV2`: Same pattern as V1.
- `BalancerFlashLoan`: `_vault` is stored directly as `VAULT`. If zero, every flash loan call sends to `address(0)`.
- `FlashLoanLiquidator`: Same as V1/V2.

For `BalancerFlashLoan`, `_vault == address(0)` means `VAULT` is permanently `address(0)`. The `receiveFlashLoan` callback check (line 173: `msg.sender != address(VAULT)`) would then require `msg.sender == address(0)`, which is impossible in normal EVM operation. However, any function calling `VAULT.flashLoan(...)` would call `address(0)`, which succeeds silently (empty code = no revert, returns nothing), meaning the flash loan call "succeeds" but no callback ever fires. Funds sent to `address(0)` are permanently lost.

**Attack Scenario**: Deployment script has a misconfigured environment variable. `_vault` resolves to `0x0`. Contract deploys successfully. First arbitrage attempt calls `address(0).flashLoan(...)` which is a no-op. The `executeArbitrage` function completes without error (Balancer flash loan to zero address does not revert), but no profit is generated, and if any tokens were pre-funded to the contract, subsequent logic may behave unpredictably.

**Recommended Fix**:
```solidity
// In each constructor:
require(_addressProvider != address(0), "Zero address: provider");
// or
require(_vault != address(0), "Zero address: vault");
```

---

### IV-C03: Zero Flash Loan Amount Accepted Without Validation

**Severity**: CRITICAL
**Contract**: `FlashLoanArbitrage.sol`, `FlashLoanArbitrageV2.sol`, `BalancerFlashLoan.sol`, `FlashLoanLiquidator.sol`
**Lines**: V1:146, V2:138, Balancer:144, Liquidator:118

**Description**: None of the contracts validate that `params.amountIn` / `params.flashLoanAmount` / `params.debtToCover` is greater than zero. A zero-amount flash loan is technically valid on both Aave V3 and Balancer (Aave charges 0 premium, Balancer charges 0 fee). The callback executes with `amounts[0] == 0`.

In V2 and Balancer, `currentAmount` starts at 0 (line V2:182, Balancer:179). The contract then calls `safeTransfer(step.adapter, 0)` which succeeds for most ERC20 tokens. The adapter receives 0 tokens and executes a swap with 0 input, which typically returns 0. The profit check `currentAmount <= amountOwed` becomes `0 <= 0`, triggering `InsufficientProfit` -- so the transaction reverts. While this does not lose funds, it wastes gas and obscures the real issue.

More critically, in V1's `executeOperation` (line 209), if `finalAmount == 0` and `amountOwed == 0` (zero loan + zero premium), then `finalAmount <= amountOwed` is `0 <= 0` = true, but the subsequent line `finalAmount - amountOwed` underflows conceptually (though it's `0 - 0 = 0`), and the check `profit < minProfitUSD` catches it only if `minProfitUSD > 0`. If `minProfitUSD == 0` (see IV-M04), then a zero-amount flash loan "succeeds" -- incrementing `executionCount` and emitting `ArbitrageExecuted` with `profit == 0`, polluting analytics.

**Recommended Fix**:
```solidity
require(params.amountIn > 0, "Zero amount");
// or
require(params.flashLoanAmount > 0, "Zero amount");
```

---

## HIGH Findings

### IV-H01: Self-Referential Swap Path Not Detected (tokenIn == tokenOut)

**Severity**: HIGH
**Contract**: `FlashLoanArbitrageV2.sol`, `BalancerFlashLoan.sol`
**Lines**: V2:185-216, Balancer:182-211

**Description**: Neither V2 nor Balancer validates that `step.tokenIn != step.tokenOut` within each swap step. A swap step where `tokenIn == tokenOut` creates degenerate behavior.

When `tokenIn == tokenOut`:
1. `balanceBefore` records the contract's balance of the token (line V2:189)
2. `safeTransfer(step.adapter, currentAmount)` sends tokens to the adapter (line V2:192)
3. The adapter attempts to swap tokenX for tokenX. Behavior depends on the adapter:
   - UniswapV2Adapter: Creates `path = [tokenX, tokenX]`. Uniswap V2 router may revert or return garbage (pair of token with itself does not exist).
   - UniswapV3Adapter: Sends `exactInputSingle` with `tokenIn == tokenOut`. The Uniswap V3 router reverts with "Invalid tokens" or similar.
   - CurveAdapter: Looks up `_pairKey(tokenX, tokenX)`. If registered (unlikely but possible), calls `exchange(indexA, indexB, ...)` where the pool likely reverts for same-index swap.
4. The `catch` block fires, reverting with `SwapFailed(i)`.

While the external call likely reverts, this is defense-in-depth that should not be relied upon. A malicious or buggy adapter could return successfully (e.g., an adapter that simply returns the input tokens), and the contract would accept it, leading to a no-op step that reduces the effective swap path without detection.

**Attack Scenario**: A registered adapter with a bug or malicious logic simply returns `amountIn` when `tokenIn == tokenOut`. The swap step becomes a no-op fee extractor if the adapter skims tokens.

**Recommended Fix**:
```solidity
for (uint256 i = 0; i < arbParams.steps.length; i++) {
    SwapStep memory step = arbParams.steps[i];
    require(step.tokenIn != step.tokenOut, "Self-referential swap");
    // ...
}
```

---

### IV-H02: Duplicate Adapters in Swap Path Can Cause Approval Conflicts

**Severity**: HIGH
**Contract**: `FlashLoanArbitrageV2.sol`, `BalancerFlashLoan.sol`
**Lines**: V2:185-216, Balancer:182-211

**Description**: There is no validation preventing the same adapter from appearing multiple times in the steps array. While this is not inherently a vulnerability, it creates a subtle issue: the main contract transfers tokens to the adapter via `safeTransfer`, meaning the adapter holds the tokens. If the same adapter is used for step N and step N+2, and step N leaves a residual token balance in the adapter (e.g., due to rounding), step N+2 could inadvertently use those leftover tokens.

This also means the adapter must be stateless between calls. None of the current adapters store intermediate state, but this is an implicit invariant that is not enforced.

Furthermore, if a V1 path uses the same DEX router for multiple hops, the `forceApprove / forceApprove(0)` cycle (lines V1:248, 263) creates a TOCTOU window where the second hop re-approves the router for a different token before the first approval was fully consumed, though in practice Solidity's synchronous execution prevents this.

**Recommended Fix**:
```solidity
// Option A: Document that adapters must be stateless
// Option B: Add explicit check
for (uint256 i = 0; i < params.steps.length; i++) {
    for (uint256 j = i + 1; j < params.steps.length; j++) {
        require(params.steps[i].adapter != params.steps[j].adapter, "Duplicate adapter");
    }
}
// Note: Option B may be overly restrictive if legitimate use cases
// require the same adapter for different pairs. Consider documenting
// the statelessness requirement instead.
```

---

### IV-H03: No Validation of Adapter Address in `setAdapter`

**Severity**: HIGH
**Contract**: `FlashLoanArbitrageV2.sol` (line 251), `BalancerFlashLoan.sol` (line 242), `FlashLoanLiquidator.sol` (line 240)
**Lines**: As noted

**Description**: The `setAdapter` function accepts any address including `address(0)`. If `registeredAdapters[address(0)]` is set to `true`, then a swap step with `adapter == address(0)` passes the registration check. The contract then calls `safeTransfer(address(0), amount)` which transfers tokens to the zero address (permanent burn), followed by `IDEXAdapter(address(0)).swapDirect(...)` which calls address(0) -- a call to an address with no code returns success with empty returndata, which `abi.decode` would fail on, reverting the transaction.

While the revert prevents fund loss in this specific case, the tokens transferred via `safeTransfer` to `address(0)` BEFORE the swap call are already burned. The `safeTransfer` to `address(0)` succeeds for most ERC20 tokens (OpenZeppelin's ERC20 does not block transfers to zero address -- only `_mint` does).

**Wait -- correction**: OpenZeppelin ERC20 (v5.x for Solidity ^0.8.20) DOES revert on `transfer` to `address(0)` with `ERC20InvalidReceiver(address(0))`. So the `safeTransfer` to `address(0)` would revert. However, non-standard ERC20 tokens that do not follow this convention could allow it.

**Attack Scenario**: Owner accidentally whitelists `address(0)`. A swap step uses `address(0)` as adapter with a non-standard ERC20 that allows zero-address transfers. Flash-loaned tokens are burned.

**Recommended Fix**:
```solidity
function setAdapter(address adapter, bool status) external onlyOwner {
    require(adapter != address(0), "Zero address adapter");
    registeredAdapters[adapter] = status;
    emit AdapterRegistered(adapter, status);
}
```

---

### IV-H04: Adapter Constructor Missing Zero Address Checks for Router/Quoter

**Severity**: HIGH
**Contract**: `UniswapV2Adapter.sol` (line 68-69), `UniswapV3Adapter.sol` (line 96-98)
**Lines**: As noted

**Description**: Both adapters store constructor parameters as `immutable` without validation.

`UniswapV2Adapter`: `router = IUniswapV2Router02(_router)` -- if `_router == address(0)`, all swap calls go to address(0) and silently succeed (no code = no revert for low-level calls), but the `swapExactTokensForTokens` ABI-decoded return would fail, likely causing a revert. The `forceApprove(address(router), amountIn)` call approves `address(0)` for spending, which is a no-op for standard ERC20 but wastes gas. The contract is permanently non-functional.

`UniswapV3Adapter`: Both `_swapRouter` and `_quoter` can be zero. Same permanent bricking effect.

**Recommended Fix**:
```solidity
// UniswapV2Adapter constructor:
require(_router != address(0), "Zero router");

// UniswapV3Adapter constructor:
require(_swapRouter != address(0), "Zero router");
require(_quoter != address(0), "Zero quoter");
```

---

### IV-H05: Withdrawals Allow Zero Address Recipient (Permanent Fund Loss)

**Severity**: HIGH
**Contract**: `FlashLoanArbitrage.sol` (lines 366-377, 385-396), `FlashLoanArbitrageV2.sol` (lines 295-306, 314-320), `BalancerFlashLoan.sol` (lines 266-275, 277-283), `FlashLoanLiquidator.sol` (lines 254-258, 260-262)
**Lines**: As noted

**Description**: The `withdrawProfits` and `emergencyWithdraw` functions accept `to` as a parameter without validating it is not `address(0)`.

For standard OpenZeppelin ERC20 tokens, `safeTransfer(address(0), amount)` reverts with `ERC20InvalidReceiver`. However, for non-standard tokens (USDT, some bridged tokens, or tokens not following OZ v5 patterns), a transfer to `address(0)` may succeed, permanently burning the funds.

In `FlashLoanArbitrage.sol`, the `emergencyWithdraw` function is accessible to non-owner addresses (via the `emergencyWithdrawers` mapping), widening the attack surface: any authorized emergency withdrawer could accidentally burn tokens by specifying `to = address(0)`.

**Recommended Fix**:
```solidity
require(to != address(0), "Zero recipient");
```

---

### IV-H06: DEX Whitelist Accepts Zero Address (V1)

**Severity**: HIGH
**Contract**: `FlashLoanArbitrage.sol`
**Lines**: 304-307

**Description**: `setDEXWhitelist(address(0), true)` successfully whitelists the zero address. In `_executeSwaps` (line 248), the contract calls `IERC20(tokenIn).forceApprove(address(0), currentAmount)` which approves the zero address as a spender. Then `_swapOnDEX` is called with `router = address(0)`. Currently the function reverts with "DEX swap not implemented", but if it were implemented to delegate to the router, calls to `address(0)` would behave unpredictably.

**Recommended Fix**:
```solidity
function setDEXWhitelist(address dex, bool status) external onlyOwner {
    require(dex != address(0), "Zero address DEX");
    whitelistedDEXs[dex] = status;
    emit DEXWhitelisted(dex, status);
}
```

---

### IV-H07: `setAuthorized` Accepts Zero Address in Adapters

**Severity**: HIGH
**Contract**: `UniswapV2Adapter.sol` (line 80), `UniswapV3Adapter.sol` (line 108), `CurveAdapter.sol` (line 79)
**Lines**: As noted

**Description**: All three adapters allow `setAuthorized(address(0), true)`. Since `msg.sender` can never be `address(0)` in normal EVM execution, this is effectively a wasted storage write. However, it creates a false sense of security -- the owner believes they have authorized an address but it is unreachable. It also pollutes the `authorized` mapping with dead entries.

More importantly, if any EVM-compatible chain or precompile allows calls from `address(0)` (some L2s have special system contracts), this could become an access control bypass.

**Recommended Fix**:
```solidity
function setAuthorized(address account, bool status) external onlyOwner {
    require(account != address(0), "Zero address");
    authorized[account] = status;
    emit AuthorizedUpdated(account, status);
}
```

---

## MEDIUM Findings

### IV-M01: Deadline Edge Case -- `block.timestamp` Equality Passes Check

**Severity**: MEDIUM
**Contract**: `FlashLoanArbitrage.sol` (line 127), `FlashLoanArbitrageV2.sol` (line 120), `BalancerFlashLoan.sol` (line 129), `FlashLoanLiquidator.sol` (line 108)
**Lines**: As noted

**Description**: All contracts use `block.timestamp > params.deadline` as the deadline check. This means `deadline == block.timestamp` passes the check (is NOT expired). This is standard Uniswap convention and generally acceptable.

However, if `deadline == 0`, the check becomes `block.timestamp > 0`, which is always true after the genesis block, so the transaction always reverts. A zero deadline is effectively "immediately expired." This is correct behavior but undocumented -- a caller passing `deadline = 0` expecting "no deadline" (a common misconception) will always have their transaction revert.

Additionally, the deadline is only checked in the outer `executeArbitrage` function. The Aave/Balancer callback does not re-check the deadline. Between the initial check and the callback execution, time passes (especially if the flash loan pool has high utilization requiring multiple blocks). The deadline could have expired by the time the callback executes, but the swap adapters independently enforce their own deadlines, so this is partially mitigated.

**Recommended Fix**:
```solidity
// Document the deadline semantics clearly in NatSpec:
/// @param deadline Timestamp after which the transaction reverts.
///        Must be > 0. Value of block.timestamp means "this block only."
///        Recommended: block.timestamp + 300 (5 minutes).
```

---

### IV-M02: `maxSlippageBps` Can Be Set to Zero

**Severity**: MEDIUM
**Contract**: `FlashLoanArbitrage.sol` (lines 323-328), `FlashLoanArbitrageV2.sol` (lines 270-273), `BalancerFlashLoan.sol` (lines 253-256)
**Lines**: As noted

**Description**: The `setMaxSlippage` function validates `_maxSlippageBps <= 1000` but does not enforce a minimum. Setting `maxSlippageBps = 0` means zero slippage tolerance. While the `maxSlippageBps` state variable exists in all three contracts, it is never actually used in any swap logic -- it is a dead variable. The actual slippage protection is via `minAmountOut` / `minFinalAmount` in the params struct.

This means:
1. The `maxSlippageBps` gives a false impression of slippage protection being enforced at the contract level.
2. Setting it to any value (including 0 or 1000) has no effect on execution.
3. The `DEXLibrary.calculateMinAmountOut` function references a `slippageBps` parameter but is never called from the main contracts.

**Recommended Fix**: Either integrate `maxSlippageBps` into the swap logic or remove it to avoid confusion:
```solidity
// Option A: Use it in swap validation
uint256 maxAcceptableSlippage = (amounts[0] * (BPS_DENOMINATOR - maxSlippageBps)) / BPS_DENOMINATOR;
require(currentAmount >= maxAcceptableSlippage, "Contract slippage exceeded");

// Option B: Remove dead code
// Delete maxSlippageBps, setMaxSlippage, and related events
```

---

### IV-M03: CurveAdapter Pool Indices Not Validated

**Severity**: MEDIUM
**Contract**: `CurveAdapter.sol`
**Lines**: 102-119

**Description**: The `registerPool` function accepts `int128 indexA` and `int128 indexB` without any validation. Curve pools typically support indices 0-3 (for pools with 2-4 tokens). Invalid indices (negative values, values >= pool size) cause the `exchange()` call to revert at the pool level.

Specific edge cases:
- `indexA == indexB`: Registering a pool where both indices are the same creates a self-swap. Curve's `exchange` function reverts for `i == j`, but this is relying on external validation.
- `indexA < 0` or `indexB < 0`: Negative indices are technically valid `int128` values. Curve pools use `int128` for historical reasons but always expect non-negative values. A negative index causes unpredictable behavior depending on the Curve pool implementation (likely a revert, but not guaranteed for all pool versions).
- Very large positive values (e.g., `indexA = 127`): Will revert at the Curve pool level since no pool has 128 tokens.

**Recommended Fix**:
```solidity
function registerPool(
    address pool,
    address tokenA,
    address tokenB,
    int128 indexA,
    int128 indexB
) external onlyOwner {
    require(pool != address(0), "Invalid pool");
    require(indexA >= 0 && indexA <= 3, "Invalid indexA");
    require(indexB >= 0 && indexB <= 3, "Invalid indexB");
    require(indexA != indexB, "Indices must differ");
    require(tokenA != tokenB, "Tokens must differ");
    require(tokenA != address(0) && tokenB != address(0), "Zero token");
    // ...
}
```

---

### IV-M04: `minProfit` / `minProfitUSD` Can Be Set to Zero

**Severity**: MEDIUM
**Contract**: `FlashLoanArbitrage.sol` (line 313-317), `FlashLoanArbitrageV2.sol` (line 260-264), `BalancerFlashLoan.sol` (line 247-250), `FlashLoanLiquidator.sol` (line 245-249)
**Lines**: As noted

**Description**: The `setMinProfit` functions accept `_minProfit = 0` without any lower bound. Setting minimum profit to zero means the profit check `profit < minProfit` becomes `profit < 0`, which is impossible for a `uint256`. Any profit (even 1 wei) would pass, and the zero-amount flash loan scenario (IV-C03) would also succeed.

This removes the economic safeguard against dust attacks or gas-griefing, where an attacker front-runs profitable arbitrage opportunities by submitting zero-profit (or near-zero-profit) transactions that consume gas without meaningful returns.

Also applied at constructor time: the constructors accept `_minProfitUSD = 0` / `_minProfit = 0`.

**Recommended Fix**:
```solidity
function setMinProfit(uint256 _minProfit) external onlyOwner {
    require(_minProfit > 0, "Min profit must be positive");
    uint256 oldValue = minProfit;
    minProfit = _minProfit;
    emit MinProfitUpdated(oldValue, _minProfit);
}
```

---

### IV-M05: V2/Balancer Missing Token Continuity Validation in Steps

**Severity**: MEDIUM
**Contract**: `FlashLoanArbitrageV2.sol`, `BalancerFlashLoan.sol`
**Lines**: V2:185-216, Balancer:182-211

**Description**: The swap steps are provided as an array of `SwapStep` structs where each step independently specifies `tokenIn` and `tokenOut`. There is no validation that `steps[i].tokenOut == steps[i+1].tokenIn` -- i.e., that the path is contiguous.

If step 0 swaps USDC -> WETH and step 1 swaps WBTC -> USDC, the contract would:
1. Transfer USDC to adapter, get WETH back
2. Try to transfer `currentAmount` of WBTC to the next adapter -- but the contract may not hold any WBTC

The `safeTransfer` at step 1 would revert with "insufficient balance" (unless the contract happens to hold WBTC from a previous operation). The error message is opaque and does not indicate the real issue (path discontinuity).

The only path validation is the end-state check: `currentToken == assets[0]` (V2 line 219, Balancer line 214). This catches the error late, after potentially multiple wasted swap operations.

**Recommended Fix**:
```solidity
// Validate path continuity before executing swaps
require(arbParams.steps[0].tokenIn == assets[0], "First step must use flash loan token");
for (uint256 i = 1; i < arbParams.steps.length; i++) {
    require(arbParams.steps[i].tokenIn == arbParams.steps[i-1].tokenOut, "Path not contiguous");
}
require(arbParams.steps[arbParams.steps.length - 1].tokenOut == assets[0], "Must return to start token");
```

---

### IV-M06: FlashLoanLiquidator Missing `collateralAsset != debtAsset` Check

**Severity**: MEDIUM
**Contract**: `FlashLoanLiquidator.sol`
**Lines**: 100-143

**Description**: The `executeLiquidation` function does not validate that `params.collateralAsset != params.debtAsset`. If they are the same, the contract flash-loans the token, calls `liquidationCall` with collateral == debt (which Aave V3 may or may not reject depending on the user's position), and then attempts to "swap" collateral to debt (which is a no-op or reverts).

Aave V3 does reject `collateralAsset == debtAsset` in `liquidationCall`, but relying on external validation is fragile. An early revert with a clear error message saves gas and improves debuggability.

**Recommended Fix**:
```solidity
require(params.collateralAsset != params.debtAsset, "Collateral must differ from debt");
```

---

### IV-M07: CurveAdapter `registerPool` Missing Token Zero Address Check

**Severity**: MEDIUM
**Contract**: `CurveAdapter.sol`
**Lines**: 102-119

**Description**: While `pool != address(0)` is validated, `tokenA` and `tokenB` are not checked. Registering a pool with `tokenA == address(0)` creates an entry in `poolRegistry` keyed by `keccak256(abi.encodePacked(address(0), tokenB))`. If a swap step specifies `tokenIn = address(0)`, the `_getPool` lookup succeeds, and the contract attempts to call `IERC20(address(0)).forceApprove(...)` which calls address(0) -- an account with no code. The `forceApprove` uses low-level call which succeeds on empty accounts, leading to undefined behavior in the subsequent `exchange()` call.

**Recommended Fix**:
```solidity
require(tokenA != address(0) && tokenB != address(0), "Zero token address");
```

---

### IV-M08: V1 Underflow in Profit Calculation When `finalAmount <= amountOwed`

**Severity**: MEDIUM
**Contract**: `FlashLoanArbitrage.sol`
**Lines**: 209-211

**Description**: The profit check on line 209 is:
```solidity
if (finalAmount <= amountOwed) {
    revert InsufficientProfit(finalAmount - amountOwed, minProfitUSD);
}
```

When `finalAmount < amountOwed`, the expression `finalAmount - amountOwed` causes an arithmetic underflow in Solidity 0.8+, which panics (reverts with 0x11) BEFORE the custom error `InsufficientProfit` is emitted. The caller receives a generic panic instead of the informative custom error.

When `finalAmount == amountOwed`, `finalAmount - amountOwed = 0`, and the custom error fires correctly with `actual = 0`.

**Recommended Fix**:
```solidity
if (finalAmount <= amountOwed) {
    revert InsufficientProfit(0, minProfitUSD);
}
```

---

## LOW Findings

### IV-L01: `maxSlippageBps` Constructor Value Not Validated

**Severity**: LOW
**Contract**: `FlashLoanArbitrage.sol` (line 110), `FlashLoanArbitrageV2.sol` (line 105), `BalancerFlashLoan.sol` (line 114)
**Lines**: As noted

**Description**: While `setMaxSlippage` enforces `_maxSlippageBps <= 1000`, the constructor does not. A deployment with `_maxSlippageBps = 50000` (500%) would succeed, setting an invalid initial value. Although the variable is unused (see IV-M02), this inconsistency could cause confusion if the variable is later integrated into swap logic.

**Recommended Fix**:
```solidity
require(_maxSlippageBps <= 1000, "Slippage too high");
```

---

### IV-L02: `withdrawProfits` Allows Zero Amount Withdrawal

**Severity**: LOW
**Contract**: `FlashLoanArbitrage.sol` (line 371), `FlashLoanArbitrageV2.sol` (line 300), `BalancerFlashLoan.sol` (line 271), `FlashLoanLiquidator.sol` (line 255)
**Lines**: As noted

**Description**: Calling `withdrawProfits(token, 0, to)` succeeds: `0 <= totalProfits[token]` is true, `totalProfits[token] -= 0` is a no-op, and `safeTransfer(to, 0)` succeeds for most tokens. This emits a `ProfitWithdrawn` event with `amount = 0`, polluting event logs and potentially confusing off-chain monitoring.

**Recommended Fix**:
```solidity
require(amount > 0, "Zero amount");
```

---

### IV-L03: V1 `emergencyWithdrawers` Mapping Allows address(0)

**Severity**: LOW
**Contract**: `FlashLoanArbitrage.sol`
**Lines**: 348-358

**Description**: `grantEmergencyWithdrawer(address(0))` sets `emergencyWithdrawers[address(0)] = true`. Since `msg.sender` can never be `address(0)`, this entry is unreachable. It wastes gas and storage.

**Recommended Fix**:
```solidity
function grantEmergencyWithdrawer(address account) external onlyOwner {
    require(account != address(0), "Zero address");
    emergencyWithdrawers[account] = true;
}
```

---

### IV-L04: CurveAdapter `swapDirect` Does Not Validate `deadline`

**Severity**: LOW
**Contract**: `CurveAdapter.sol`
**Lines**: 132-161

**Description**: The `deadline` parameter is accepted by the `swapDirect` function to match the `IDEXAdapter` interface but is never checked. Curve's `exchange` function does not accept a deadline. A caller may set an expired deadline expecting it to be enforced, but the swap proceeds regardless.

The comment on line 128 says "unused by Curve, kept for interface" which is accurate but the lack of enforcement is still a gap -- the caller (FlashLoanArbitrageV2 or BalancerFlashLoan) checks the deadline at the top of `executeArbitrage`, but time passes between that check and the CurveAdapter swap execution.

**Recommended Fix**:
```solidity
function swapDirect(...) external onlyAuthorized returns (uint256 amountOut) {
    require(block.timestamp <= deadline, "Deadline expired");
    // ...
}
```

---

### IV-L05: UniswapV2Adapter `calculatePriceImpact` Division by Zero

**Severity**: LOW
**Contract**: `UniswapV2Adapter.sol`
**Lines**: 165-189

**Description**: If `amountIn == 0`, then `smallAmount = 0 / 100 = 0`, which is caught by the `if (smallAmount == 0) smallAmount = 1` guard. But if `amountIn` is extremely small (e.g., 1 wei), `smallAmount = 1` and the router's `getAmountsOut(1, path)` may return 0 for output (due to rounding in constant product formula). Then `baselinePrice = (0 * 1e18) / 1 = 0`, and the final line `priceImpactBps = (priceDiff * 10000) / baselinePrice` divides by zero, causing a panic revert.

**Recommended Fix**:
```solidity
if (baselinePrice == 0) return 0; // Cannot compute impact with zero baseline
```

---

### IV-L06: `emergencyWithdraw` Does Not Validate Token Address

**Severity**: LOW
**Contract**: All four main contracts
**Lines**: V1:385-396, V2:314-320, Balancer:277-283, Liquidator:260-262

**Description**: `emergencyWithdraw` does not validate that `token != address(0)`. Calling `IERC20(address(0)).safeTransfer(to, amount)` makes a low-level call to address(0). With no code at address(0), the call returns success with empty data. `SafeERC20.safeTransfer` then checks the return data length -- for an address with no code, the return is empty, and SafeERC20 reverts with `AddressEmptyCode`. So this is caught, but the error message is confusing and wastes gas.

**Recommended Fix**:
```solidity
require(token != address(0), "Zero token address");
```

---

## INFO Findings

### IV-I01: `maxSlippageBps` Boundary Value 1000 Allows 10% Slippage

**Severity**: INFO
**Contract**: `FlashLoanArbitrage.sol`, `FlashLoanArbitrageV2.sol`, `BalancerFlashLoan.sol`
**Lines**: V1:324, V2:271, Balancer:254

**Description**: The check `_maxSlippageBps <= 1000` allows exactly 1000 bps (10%) as the maximum configurable slippage. For flash loan arbitrage, 10% slippage is very high and would likely make most trades unprofitable after flash loan fees. While not a bug, a lower cap (e.g., 500 bps = 5%) might be more appropriate. Note that this variable is currently unused (IV-M02), so the impact is purely informational.

---

### IV-I02: V3 Adapter `data` Must Be Exactly 32 Bytes (ABI-Encoded uint24)

**Severity**: INFO
**Contract**: `UniswapV3Adapter.sol`
**Lines**: 144-145

**Description**: The check `data.length < 32` requires at least 32 bytes. ABI-encoding a `uint24` produces exactly 32 bytes (left-padded). If `data` is longer than 32 bytes, only the first 32 are decoded and the rest are ignored. This is standard `abi.decode` behavior but could hide errors where extra data is accidentally included.

The check does not handle `data.length == 0` specially -- it reverts with `InvalidDataLength()`. This is correct but the error could be more descriptive for the empty-data case.

---

### IV-I03: FlashLoanArbitrage V1 Swap Function Is Unimplemented

**Severity**: INFO
**Contract**: `FlashLoanArbitrage.sol`
**Lines**: 285-297

**Description**: The `_swapOnDEX` function always reverts with `"DEX swap not implemented - use DEXLibrary"`. This means the V1 contract is non-functional for actual arbitrage. While presumably this is intentional (V2 supersedes V1), the contract can still be deployed and configured, and `executeArbitrage` will always revert at the swap stage, wasting gas.

---

### IV-I04: Event Emitted with Stale Profit Data in V2/Balancer

**Severity**: INFO
**Contract**: `FlashLoanArbitrageV2.sol` (lines 157-162), `BalancerFlashLoan.sol` (lines 155-160)
**Lines**: As noted

**Description**: The `ArbitrageExecuted` event in `executeArbitrage` emits `totalProfits[params.flashLoanAsset]` as the `profit` field. This is the cumulative total profit, not the profit from this specific execution. After the first successful execution, this field contains the running total, which is misleading for event consumers. The actual per-execution profit is calculated in the callback but not propagated back to the outer function.

---

## Summary of Recommendations by Priority

### Immediate (Pre-Deployment Blockers)

1. **IV-C01**: Add `dexRouters.length == path.length - 1` validation in V1
2. **IV-C02**: Add `address(0)` checks in all constructors for immutable addresses
3. **IV-C03**: Require `flashLoanAmount > 0` / `amountIn > 0` in all entry points

### High Priority (Deploy After Fixing)

4. **IV-H01**: Validate `tokenIn != tokenOut` in each swap step
5. **IV-H03**: Prevent `address(0)` in `setAdapter`
6. **IV-H04**: Zero-address checks in adapter constructors
7. **IV-H05**: Require `to != address(0)` in withdrawal functions
8. **IV-H06**: Prevent `address(0)` in V1 `setDEXWhitelist`
9. **IV-H07**: Prevent `address(0)` in adapter `setAuthorized`
10. **IV-H02**: Document adapter statelessness requirement or prevent duplicates

### Medium Priority (Fix Before Mainnet)

11. **IV-M02**: Either use `maxSlippageBps` or remove it (dead code)
12. **IV-M03**: Validate Curve pool indices and prevent `indexA == indexB`
13. **IV-M04**: Enforce `minProfit > 0`
14. **IV-M05**: Validate token path continuity in V2/Balancer
15. **IV-M06**: Check `collateralAsset != debtAsset` in Liquidator
16. **IV-M07**: Zero-address check for token params in CurveAdapter `registerPool`
17. **IV-M08**: Fix underflow in V1 profit calculation error reporting
18. **IV-M01**: Document deadline semantics

### Low Priority (Best Practices)

19. **IV-L01**: Validate `maxSlippageBps` in constructors
20. **IV-L02**: Reject zero-amount withdrawals
21. **IV-L03**: Prevent `address(0)` in `grantEmergencyWithdrawer`
22. **IV-L04**: Enforce deadline in CurveAdapter
23. **IV-L05**: Guard against division by zero in price impact calculation
24. **IV-L06**: Validate token address in emergency withdraw

---

*Report generated by Agent 5 (Input Validation & Edge Cases) as part of a 7-agent security audit swarm.*
