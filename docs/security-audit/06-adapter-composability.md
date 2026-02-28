# Security Audit Report: Cross-Contract Interaction, Adapter Trust Model & Composability Risks

**Audit Agent**: 6 of 7
**Scope**: Adapter trust model, cross-contract token flows, interface compliance, callback verification, composability risks
**Contracts Audited**:
- `contracts/FlashLoanArbitrageV2.sol`
- `contracts/BalancerFlashLoan.sol`
- `contracts/FlashLoanLiquidator.sol`
- `contracts/FlashLoanArbitrage.sol` (V1)
- `contracts/adapters/UniswapV2Adapter.sol`
- `contracts/adapters/UniswapV3Adapter.sol`
- `contracts/adapters/CurveAdapter.sol`
- `contracts/interfaces/IDEXAdapter.sol`
- `contracts/libraries/DEXLibrary.sol`

---

## Finding 6.1 -- Adapter Trust Model: Pre-Transfer Pattern Creates Full-Amount Theft Window

**Severity**: HIGH

**Contracts**: `FlashLoanArbitrageV2.sol` (line 192), `BalancerFlashLoan.sol` (line 188), `FlashLoanLiquidator.sol` (line 180)

**Description**:
All three main contracts use a "transfer-then-call" pattern where the full swap amount is transferred to the adapter before invoking `swapDirect()`. This means the adapter holds the tokens before it is obligated to do anything with them. If an adapter contract is compromised (e.g., through an ownership takeover of the adapter, or if the adapter's external DEX router is a malicious proxy), the adapter has custody of the tokens with no on-chain guarantee that it will return equivalent value.

```solidity
// FlashLoanArbitrageV2.sol, line 192
IERC20(step.tokenIn).safeTransfer(step.adapter, currentAmount);

// Then calls swapDirect which the adapter could implement to do nothing
IDEXAdapter(step.adapter).swapDirect(...)
```

**Mitigating Factors Already Present**:
1. Adapters have `onlyAuthorized` modifiers restricting who can call `swapDirect()`.
2. The main contracts have an `onlyOwner` gate on `setAdapter()` / `registeredAdapters`.
3. The main contracts verify actual balance changes after each swap (lines 206-211 in V2, lines 202-206 in Balancer), so an adapter cannot lie about return amounts.

**Residual Risk**:
The balance verification only catches adapters that return less than `minAmountOut`. A compromised adapter could still execute a sandwich attack by front-running the swap on the underlying DEX, extracting MEV value that falls within the `minAmountOut` tolerance. Additionally, the adapter registry is a single point of failure -- if the owner key is compromised, a malicious adapter can be registered and the entire flash loan amount stolen in a single transaction.

**Attack Scenario**:
1. Attacker compromises the owner EOA of `FlashLoanArbitrageV2`.
2. Attacker calls `setAdapter(maliciousAdapter, true)`.
3. Attacker submits an `executeArbitrage` call where `step.adapter = maliciousAdapter`.
4. The malicious adapter receives the flash-loaned tokens and transfers them to the attacker instead of executing a swap.
5. The flash loan callback reverts due to insufficient repayment, BUT the attacker has already extracted any tokens that were sitting in the contract as accumulated profits.

**Recommended Fix**:
- Implement a timelock on `setAdapter()` so new adapters cannot be used immediately. This gives monitoring systems time to detect and respond to a compromise.
- Consider a 2-of-N multisig for adapter management operations.
- Add an adapter registration nonce or versioning so deregistered adapters cannot be trivially re-registered.

```solidity
// Example timelock pattern
mapping(address => uint256) public adapterActivationTime;
uint256 public constant ADAPTER_TIMELOCK = 24 hours;

function setAdapter(address adapter, bool status) external onlyOwner {
    if (status) {
        adapterActivationTime[adapter] = block.timestamp + ADAPTER_TIMELOCK;
    } else {
        registeredAdapters[adapter] = false;
        delete adapterActivationTime[adapter];
    }
    emit AdapterRegistered(adapter, status);
}

function activateAdapter(address adapter) external onlyOwner {
    require(adapterActivationTime[adapter] != 0, "Not pending");
    require(block.timestamp >= adapterActivationTime[adapter], "Timelock active");
    registeredAdapters[adapter] = true;
    delete adapterActivationTime[adapter];
}
```

---

## Finding 6.2 -- Adapters Do Not Explicitly Implement IDEXAdapter Interface

**Severity**: MEDIUM

**Contracts**: `UniswapV2Adapter.sol`, `UniswapV3Adapter.sol`, `CurveAdapter.sol`

**Description**:
None of the three adapter contracts declare `is IDEXAdapter` in their contract definition. They rely on matching function signatures ("duck typing") rather than explicit interface inheritance:

```solidity
// UniswapV2Adapter.sol, line 36
contract UniswapV2Adapter {  // <-- No "is IDEXAdapter"
    ...
    function swapDirect(
        address tokenIn,
        address tokenOut,
        uint256 amountIn,
        uint256 minAmountOut,
        uint256 deadline,
        address recipient,
        bytes calldata data
    ) external onlyAuthorized returns (uint256 amountOut) {
```

While this works at the ABI level because the Solidity compiler matches function selectors, it creates the following risks:

1. **Interface Drift**: If `IDEXAdapter` is ever updated (e.g., adding a new parameter, changing return types), the adapters will silently become incompatible. The compiler will not produce an error during adapter compilation since there is no `is IDEXAdapter` declaration to enforce.
2. **No Compile-Time Guarantees**: A developer could accidentally change the adapter's `swapDirect` signature (e.g., reorder parameters) and the contract would still compile without warnings, but calls from the main contract would fail at runtime.
3. **ERC-165 Incompatibility**: Without explicit interface implementation, `supportsInterface()` checks (if ever added) would not recognize these contracts as `IDEXAdapter` implementations.

**Recommended Fix**:
All adapters should explicitly declare they implement `IDEXAdapter`:

```solidity
import {IDEXAdapter} from "../interfaces/IDEXAdapter.sol";

contract UniswapV2Adapter is IDEXAdapter {
    // Compiler now enforces that swapDirect matches the interface exactly
```

---

## Finding 6.3 -- CurveAdapter Token Flow: Tokens Received But Pool Pulls From Adapter via Approve

**Severity**: LOW

**Contracts**: `CurveAdapter.sol` (lines 143-157)

**Description**:
The CurveAdapter token flow is correct but has a subtle design worth documenting for clarity. The flow is:

1. Main contract (V2/Balancer) transfers `tokenIn` to the CurveAdapter (line 192 of V2).
2. CurveAdapter approves the Curve pool to spend `tokenIn` from itself (line 144).
3. Curve pool's `exchange()` pulls `tokenIn` from the CurveAdapter via `transferFrom`.
4. Curve pool sends `tokenOut` back to the CurveAdapter (not to `recipient`).
5. CurveAdapter then forwards `tokenOut` to `recipient` (lines 155-157).

```solidity
// CurveAdapter.sol
IERC20(tokenIn).forceApprove(info.pool, amountIn);  // line 144
amountOut = ICurvePool(info.pool).exchange(info.indexA, info.indexB, amountIn, minAmountOut);  // line 147-152

// Transfer output to recipient
if (recipient != address(this)) {
    IERC20(tokenOut).safeTransfer(recipient, amountOut);  // line 156
}
```

This is correct and the approval chain works. However, there is a minor residual risk: if the Curve pool's `exchange()` reverts after the approval was set but before execution completes, the approval remains non-zero. The `forceApprove(info.pool, 0)` at line 160 would not execute, leaving a dangling approval. In practice this is not exploitable because the revert would unwind the entire transaction, including the approval.

The `if (recipient != address(this))` check on line 155 is noteworthy: it means if the main contract accidentally passes the adapter itself as the recipient, tokens stay in the adapter. However, the main contracts always pass `address(this)` (referring to the main contract), so this is not a practical issue.

**Token Residue Risk**: After a successful swap, no tokens should remain in the CurveAdapter because:
- All `tokenIn` is consumed by Curve's `exchange()`.
- All `tokenOut` is forwarded to `recipient`.
- Approvals are reset to 0.

However, if Curve's `exchange()` returns less `tokenIn` than `amountIn` (i.e., a partial fill, which is not standard Curve behavior but possible with custom pool implementations), the remainder would be stuck in the adapter. There is no sweep mechanism on the adapters.

**Recommended Fix**:
- Add an owner-callable `rescueTokens()` function to all adapters for recovering stuck tokens.
- Consider checking that the adapter's `tokenIn` balance is zero after the swap to detect partial fills.

---

## Finding 6.4 -- Balancer Callback Missing Initiator Check (Reentrancy Vector)

**Severity**: HIGH

**Contract**: `BalancerFlashLoan.sol` (lines 167-236)

**Description**:
The Balancer flash loan callback `receiveFlashLoan()` checks only that `msg.sender == address(VAULT)` (line 173). Unlike the Aave callback in `FlashLoanArbitrageV2` and `FlashLoanLiquidator`, which both verify `initiator == address(this)`, the Balancer callback has **no initiator verification**.

```solidity
// BalancerFlashLoan.sol, line 172-173
function receiveFlashLoan(...) external override {
    if (msg.sender != address(VAULT)) revert UnauthorizedCaller();
    // No initiator check!
```

Compare with the Aave callbacks:
```solidity
// FlashLoanArbitrageV2.sol, lines 175-176
require(msg.sender == address(POOL), "Caller must be Pool");
require(initiator == address(this), "Initiator must be this");
```

**Attack Scenario**:
The Balancer Vault's `flashLoan()` function can be called by anyone. An attacker could:

1. Call `VAULT.flashLoan()` with `BalancerFlashLoan` as the `recipient`.
2. The Vault calls `receiveFlashLoan()` on `BalancerFlashLoan` with `msg.sender == VAULT` (passes the check).
3. The `userData` is attacker-controlled and could be crafted to encode valid-looking `ArbitrageParams`.
4. The callback would attempt to execute swaps using registered adapters.

However, there are significant mitigating factors:
- The adapters have `onlyAuthorized` checks, and the caller of `swapDirect` would be the `BalancerFlashLoan` contract (which should be authorized).
- The tokens transferred to adapters are the flash-loaned tokens that must be repaid, so the attacker cannot profit directly since the contract has no pre-existing token balances during normal operation (profits should be withdrawn promptly).
- The `minProfit` and `minFinalAmount` checks would likely cause the transaction to revert.

**Residual Risk**:
If the `BalancerFlashLoan` contract holds accumulated profits that have not been withdrawn, an attacker could craft `ArbitrageParams` that use those token balances as part of the swap sequence. The flash-loaned amount plus the contract's existing balance could be swapped through a malicious but registered adapter path designed to extract value.

**Recommended Fix**:
Add an execution lock that prevents the callback from being triggered externally:

```solidity
bool private _executing;

function executeArbitrage(ArbitrageParams calldata params) external onlyOwner nonReentrant whenNotPaused {
    _executing = true;
    // ... flash loan call ...
    _executing = false;
}

function receiveFlashLoan(...) external override {
    if (msg.sender != address(VAULT)) revert UnauthorizedCaller();
    require(_executing, "Not initiated by this contract");
    // ...
}
```

Note: The Balancer V2 `flashLoan` interface does not pass an `initiator` parameter, so this must be handled with a state variable.

---

## Finding 6.5 -- FlashLoanLiquidator Passes minAmountOut: 0 to Adapter Swap

**Severity**: CRITICAL

**Contract**: `FlashLoanLiquidator.sol` (line 188)

**Description**:
The `FlashLoanLiquidator` passes `0` as `minAmountOut` when calling the adapter's `swapDirect()` for the collateral-to-debt-token swap:

```solidity
// FlashLoanLiquidator.sol, lines 184-192
try IDEXAdapter(liqParams.adapter).swapDirect(
    liqParams.collateralAsset,
    liqParams.debtAsset,
    collateralReceived,
    0, // min out -- we check profit below    <--- ZERO SLIPPAGE PROTECTION
    liqParams.deadline,
    address(this),
    liqParams.swapData
) returns (uint256) {
```

While the contract does check profit after the swap (lines 218-225), setting `minAmountOut` to `0` at the adapter level means:

1. **The adapter's own DEX router call uses 0 slippage protection.** For example, `UniswapV2Adapter` passes `minAmountOut` directly to `router.swapExactTokensForTokens()`. This means the underlying DEX swap itself has no slippage protection and is fully vulnerable to sandwich attacks.

2. **The profit check is a weaker protection than per-swap slippage.** A sandwich attacker can extract value up to `swapReceived - amountOwed - liqParams.minProfit`, which for large liquidations with small `minProfit` values could be substantial.

3. **MEV bots will reliably sandwich this transaction.** Setting `minAmountOut: 0` is the canonical signal that a transaction is sandwichable. Searchers monitor the mempool for exactly this pattern.

**Attack Scenario**:
1. Owner submits a `executeLiquidation()` transaction to liquidate a position worth 100 ETH of collateral.
2. MEV bot observes the pending transaction in the mempool.
3. MEV bot front-runs with a large trade that moves the collateral/debt price unfavorably.
4. The liquidation swap executes at a terrible rate (e.g., receiving 90 ETH worth of debt tokens instead of 99).
5. MEV bot back-runs to capture the 9 ETH difference.
6. The profit check may still pass if `liqParams.minProfit` is set low, so the transaction succeeds but with greatly reduced profit.

**Recommended Fix**:
Add a `minSwapAmountOut` field to `LiquidationParams` and pass it to the adapter:

```solidity
struct LiquidationParams {
    address collateralAsset;
    address debtAsset;
    address user;
    uint256 debtToCover;
    address adapter;
    bytes swapData;
    uint256 minProfit;
    uint256 minSwapAmountOut;  // NEW: slippage protection for the DEX swap
    uint256 deadline;
}

// In executeOperation:
try IDEXAdapter(liqParams.adapter).swapDirect(
    liqParams.collateralAsset,
    liqParams.debtAsset,
    collateralReceived,
    liqParams.minSwapAmountOut,  // Use caller-specified slippage
    liqParams.deadline,
    address(this),
    liqParams.swapData
) returns (uint256) {
```

Additionally, consider using Flashbots Protect or a private mempool to submit liquidation transactions, since they are inherently MEV-sensitive.

---

## Finding 6.6 -- V1 vs V2 Architecture Comparison: Security Tradeoffs

**Severity**: INFO

**Contracts**: `FlashLoanArbitrage.sol` (V1) vs `FlashLoanArbitrageV2.sol` (V2)

**Description**:

| Aspect | V1 (`FlashLoanArbitrage`) | V2 (`FlashLoanArbitrageV2`) |
|--------|---------------------------|------------------------------|
| **Token custody** | Main contract holds tokens, approves DEX router directly | Tokens transferred to adapter, adapter approves router |
| **DEX interaction** | `forceApprove(router, amount)` then low-level call | `safeTransfer` to adapter, adapter calls router |
| **Approval model** | Approve, swap, reset to 0 (lines 248, 253, 263) | Adapter handles approvals internally |
| **Trust boundary** | Trust DEX router contract directly | Trust adapter AND the DEX router behind it |
| **Attack surface** | Router must be whitelisted; tokens never leave main contract during swap | Adapter AND router must be trusted; tokens leave main contract |
| **Modularity** | Tightly coupled; adding new DEX requires code change | Loosely coupled; new DEX = deploy new adapter |

**V1 is safer from a token custody perspective** because tokens never leave the main contract. The `forceApprove` pattern means the DEX router pulls tokens from the main contract, and the output is delivered back to the main contract. The main contract maintains custody throughout.

**V2 sacrifices custody safety for modularity.** The transfer-to-adapter pattern means tokens are out of the main contract's control for the duration of the `swapDirect()` call. This is a conscious tradeoff for the ability to add new DEXes without modifying the core contract.

**Key V1 Vulnerability Not Present in V2**:
V1's `_swapOnDEX()` is a stub that reverts (line 296: `revert("DEX swap not implemented - use DEXLibrary")`). This means V1 is non-functional and exists only as a skeleton. The actual V1 implementation would have relied on `DEXLibrary`, which hardcodes `address(this)` as the recipient (line 93, 138). This is safer but less flexible.

**Key V2 Vulnerability Not Present in V1**:
V1 does not have the adapter trust issue because it interacts with DEX routers directly. A whitelisted router that implements the standard Uniswap interface is much harder to exploit than a custom adapter contract.

**Recommendation**:
The V2 adapter pattern is the correct long-term architecture for maintainability. The security gap should be addressed through the adapter timelock (Finding 6.1) and explicit interface enforcement (Finding 6.2), not by reverting to V1's approach.

---

## Finding 6.7 -- Adapter Upgrade Path: No Safe Hot-Swap Mechanism

**Severity**: MEDIUM

**Contracts**: `FlashLoanArbitrageV2.sol` (line 251), `BalancerFlashLoan.sol` (line 242)

**Description**:
If a registered adapter is discovered to have a bug, the only mechanism to disable it is `setAdapter(adapter, false)`. While this prevents future use, there are several concerns:

1. **No Atomic Upgrade**: Replacing a buggy adapter requires two transactions: (a) deregister old adapter, (b) register new adapter. Between these two transactions, any arbitrage path using that adapter is unavailable. In a competitive MEV environment, this downtime can be costly.

2. **In-Flight Transaction Safety**: The `setAdapter` function has no awareness of whether a flash loan is currently in progress. However, this is not actually dangerous because:
   - Flash loans are atomic (single transaction).
   - `setAdapter` cannot be called mid-flash-loan because the owner is the same for both and the `nonReentrant` guard prevents reentrancy.
   - Adapter validation occurs before the flash loan is initiated (lines 124-128 in V2), so deregistering an adapter mid-block would not affect a transaction that already passed validation.

3. **Stale Approvals**: When an adapter is deregistered, any residual token approvals that the adapter has granted to DEX routers remain active. While the adapter itself becomes unreachable through the main contracts, a direct call to the adapter (bypassing the main contracts) could still execute swaps if the adapter's `authorized` mapping has not been updated.

4. **No Adapter Versioning**: There is no way to distinguish between AdapterV1 and AdapterV2 for the same DEX. If a new CurveAdapter is deployed, the old one must be deregistered first, creating a window where Curve swaps are unavailable.

**Recommended Fix**:
- Add an `upgradeAdapter(address oldAdapter, address newAdapter)` function that atomically deregisters the old and registers the new in a single transaction.
- When deregistering an adapter, call a `shutdown()` or `revokeAllApprovals()` function on the adapter if such a function exists.

```solidity
function upgradeAdapter(address oldAdapter, address newAdapter) external onlyOwner {
    require(registeredAdapters[oldAdapter], "Old adapter not registered");
    require(!registeredAdapters[newAdapter], "New adapter already registered");

    registeredAdapters[oldAdapter] = false;
    registeredAdapters[newAdapter] = true;

    emit AdapterRegistered(oldAdapter, false);
    emit AdapterRegistered(newAdapter, true);
}
```

---

## Finding 6.8 -- Adapter Authorization Ownership Fragmentation

**Severity**: MEDIUM

**Contracts**: `UniswapV2Adapter.sol` (lines 58-66, 80-83), `UniswapV3Adapter.sol` (lines 86-94, 108-111), `CurveAdapter.sol` (lines 59-67, 79-83)

**Description**:
Each adapter has its own independent `owner` and `authorized` mapping. The main contracts (`FlashLoanArbitrageV2`, `BalancerFlashLoan`, `FlashLoanLiquidator`) also have their own `owner` via OpenZeppelin's `Ownable`. This creates a 2-layer authorization model:

- **Layer 1**: Main contract `registeredAdapters` mapping (managed by main contract owner)
- **Layer 2**: Adapter `authorized` mapping (managed by adapter owner)

Both layers must align for the system to function. If the main contract is authorized in an adapter's `authorized` mapping but the adapter is not in the main contract's `registeredAdapters`, the adapter is unusable. And vice versa.

**Risks**:
1. **Ownership Desync**: If the adapter owner and main contract owner are different EOAs (or if one is transferred without the other), administrative operations require coordination between two parties.
2. **Custom Ownable Implementation**: The adapters use a hand-rolled `onlyOwner` pattern (not OpenZeppelin's `Ownable`) without `renounceOwnership()` protection and with a simpler `transferOwnership()`. This is inconsistent with the main contracts' use of OpenZeppelin's `Ownable`.
3. **No Two-Step Ownership Transfer**: The adapter's `transferOwnership()` takes effect immediately. If the new owner address is wrong (typo), ownership is irrecoverably lost, and the adapter can never update its `authorized` mapping again.

**Recommended Fix**:
- Use OpenZeppelin's `Ownable2Step` for adapters to require the new owner to accept the transfer.
- Document the operational requirement that the same entity must control both main contract and adapter ownership.
- Consider having adapters inherit from a shared `BaseAdapter` contract that standardizes ownership and authorization.

---

## Finding 6.9 -- Composability Risk: Adapters Assume Single-Caller Sequential Execution

**Severity**: MEDIUM

**Contracts**: All adapters

**Description**:
The adapters are designed for a single-caller, single-use pattern where:
1. Caller transfers tokens to adapter.
2. Caller calls `swapDirect()`.
3. Adapter executes swap and sends output to `recipient`.

This pattern breaks if the adapters are used as composable building blocks in any of these scenarios:

**Scenario A -- Concurrent Callers**: If two authorized main contracts (e.g., `FlashLoanArbitrageV2` and `BalancerFlashLoan`) both use the same adapter instance and their transactions are included in the same block, there is no reentrancy protection within the adapters themselves. While individual main contracts have `nonReentrant`, the adapter does not. If a malicious token's `transfer()` callback triggers a second swap on the same adapter, the adapter could use tokens from the first caller's transfer.

**Scenario B -- Multi-Hop via Same Adapter**: If an arbitrage path uses the same adapter for two consecutive steps (e.g., UniswapV2Adapter for step 1 and step 2 with different token pairs), the second `safeTransfer` to the adapter would occur while the adapter still has the residual from step 1. The adapter does not check that its `tokenIn` balance matches `amountIn`.

**Scenario C -- Fee-on-Transfer Tokens**: If `tokenIn` is a fee-on-transfer token, the adapter receives less than `amountIn` but approves and attempts to swap the full `amountIn`. This would cause the swap to fail or, worse, use previously stuck tokens.

**Mitigation**: In practice, Scenario A is prevented by the sequential nature of EVM execution within a single block. Scenario B would cause incorrect amounts but the balance verification in the main contracts would catch discrepancies. Scenario C is not mitigated.

**Recommended Fix**:
- Adapters should determine `amountIn` from their actual balance, not from the parameter:
```solidity
function swapDirect(...) external onlyAuthorized returns (uint256 amountOut) {
    uint256 actualBalance = IERC20(tokenIn).balanceOf(address(this));
    // Use actualBalance instead of amountIn for the swap
}
```
- Add reentrancy guards to adapters.
- Document that fee-on-transfer tokens are not supported, or handle them explicitly.

---

## Finding 6.10 -- Aave Callback Verification Is Sufficient But Has a Nuance

**Severity**: LOW

**Contracts**: `FlashLoanArbitrageV2.sol` (lines 175-176), `FlashLoanLiquidator.sol` (lines 156-157)

**Description**:
The Aave flash loan callbacks verify both:
1. `msg.sender == address(POOL)` -- Only the Aave Pool can call this function.
2. `initiator == address(this)` -- The flash loan was initiated by this contract.

This is the correct and complete verification for Aave V3 flash loans. The `initiator` check prevents an attacker from calling `POOL.flashLoan()` with this contract as the `receiverAddress` to trigger the callback with attacker-controlled `params`.

**Nuance**: The `POOL` address is derived from `ADDRESSES_PROVIDER.getPool()` at construction time and stored as `immutable`. If the Aave governance changes the Pool implementation (upgradeable proxy), the `POOL` address remains the same proxy address, so the check continues to work. However, if Aave migrates to a completely new Pool contract at a different address, the immutable `POOL` would become stale and the contract would need to be redeployed.

This is a standard pattern and not a vulnerability, but it is worth noting for operational awareness.

**Recommended Fix**: No code change needed. Operational monitoring should track Aave governance proposals that might affect the Pool address.

---

## Finding 6.11 -- No Token Rescue Function on Adapters

**Severity**: LOW

**Contracts**: `UniswapV2Adapter.sol`, `UniswapV3Adapter.sol`, `CurveAdapter.sol`

**Description**:
None of the adapter contracts have a function to recover tokens that may become stuck due to:
- A DEX router upgrade that changes behavior.
- A failed swap that partially executes (e.g., Curve pool implementation that does partial fills).
- Accidental direct token transfer to the adapter by a user or contract.
- A fee-on-transfer token that leaves dust.

The main contracts have `emergencyWithdraw()` functions, but these only work for tokens held by the main contract, not by adapters.

**Recommended Fix**:
Add an owner-callable rescue function to all adapters:

```solidity
function rescueTokens(address token, uint256 amount, address to) external onlyOwner {
    IERC20(token).safeTransfer(to, amount);
}
```

---

## Finding 6.12 -- UniswapV3Adapter Fee Tier Whitelist Is Overly Restrictive

**Severity**: LOW

**Contract**: `UniswapV3Adapter.sol` (lines 148-150)

**Description**:
The adapter enforces a strict whitelist of three fee tiers:

```solidity
if (fee != FEE_LOW && fee != FEE_MEDIUM && fee != FEE_HIGH) {
    revert InvalidFee(fee);
}
```

Where `FEE_LOW = 500`, `FEE_MEDIUM = 3000`, `FEE_HIGH = 10000`.

Uniswap V3 supports a 1 basis point (100) fee tier that was added via governance after the initial launch. This fee tier is commonly used for stablecoin pairs (USDC/USDT, DAI/USDC) and offers the best execution for those swaps. The current adapter cannot use this fee tier, which means any arbitrage path involving a 1 bps pool would fail.

**Recommended Fix**:
Add the 1 bps fee tier:
```solidity
uint24 public constant FEE_LOWEST = 100;   // 0.01%

// In swapDirect:
if (fee != FEE_LOWEST && fee != FEE_LOW && fee != FEE_MEDIUM && fee != FEE_HIGH) {
    revert InvalidFee(fee);
}
```

Alternatively, remove the fee tier whitelist entirely and let any `uint24` value be passed, relying on the Uniswap router to revert if the pool does not exist. This is more future-proof.

---

## Finding 6.13 -- Shared Adapter Instances Across Multiple Main Contracts

**Severity**: MEDIUM

**Contracts**: All adapters, `FlashLoanArbitrageV2.sol`, `BalancerFlashLoan.sol`, `FlashLoanLiquidator.sol`

**Description**:
The authorization model allows a single adapter instance to be used by multiple main contracts simultaneously. For example, the same `UniswapV2Adapter` could be authorized by both `FlashLoanArbitrageV2` and `BalancerFlashLoan`.

While this is operationally convenient, it means:

1. **Deregistration from one main contract does not affect others.** If a vulnerability is discovered that requires disabling a specific adapter, the operator must remember to deregister it from ALL main contracts, not just one.
2. **Authorization scope is unclear.** The adapter's `authorized` mapping does not distinguish between "authorized for arbitrage" and "authorized for liquidation." Any authorized caller can use the adapter for any purpose.
3. **Cross-contract accounting confusion.** If both main contracts use the same adapter and one has a balance verification discrepancy, debugging which main contract's transaction caused the issue is harder.

**Recommended Fix**:
- Deploy separate adapter instances for each main contract. This provides clear ownership boundaries and simplifies emergency response.
- If shared instances are desired for gas efficiency, maintain an operational runbook that documents which adapters are registered with which main contracts, and ensure deregistration operations cover all consumers.

---

## Finding 6.14 -- CurveAdapter Deadline Parameter Ignored

**Severity**: LOW

**Contract**: `CurveAdapter.sol` (line 137)

**Description**:
The `swapDirect()` function accepts a `deadline` parameter to match the `IDEXAdapter` interface, but Curve's `exchange()` function does not accept a deadline parameter. The deadline is silently ignored:

```solidity
function swapDirect(
    address tokenIn,
    address tokenOut,
    uint256 amountIn,
    uint256 minAmountOut,
    uint256 deadline,       // <-- accepted but never used
    address recipient,
    bytes calldata data
) external onlyAuthorized returns (uint256 amountOut) {
    PoolInfo memory info = _getPool(tokenIn, tokenOut);
    IERC20(tokenIn).forceApprove(info.pool, amountIn);
    amountOut = ICurvePool(info.pool).exchange(
        info.indexA, info.indexB, amountIn, minAmountOut
        // No deadline parameter
    );
```

This means Curve swaps have no deadline protection at the adapter level. If a transaction is delayed in the mempool, the Curve swap will still execute regardless of the deadline.

**Mitigating Factor**: The main contracts check `block.timestamp > params.deadline` before initiating the flash loan (line 120 in V2, line 129 in Balancer). Since the entire arbitrage executes atomically within a single transaction, the main contract's deadline check is sufficient as long as it occurs before the flash loan call.

**Recommended Fix**:
Add an explicit deadline check within the CurveAdapter:

```solidity
function swapDirect(...) external onlyAuthorized returns (uint256 amountOut) {
    require(block.timestamp <= deadline, "CurveAdapter: deadline expired");
    // ...
}
```

---

## Summary Table

| ID | Severity | Finding | Contract(s) |
|----|----------|---------|-------------|
| 6.1 | HIGH | Pre-transfer pattern creates full-amount theft window if adapter compromised | V2, Balancer, Liquidator |
| 6.2 | MEDIUM | Adapters lack explicit `is IDEXAdapter` declaration | All adapters |
| 6.3 | LOW | CurveAdapter token flow correct but no sweep for stuck tokens | CurveAdapter |
| 6.4 | HIGH | Balancer callback missing initiator/execution-lock check | BalancerFlashLoan |
| 6.5 | CRITICAL | Liquidator passes `minAmountOut: 0` to adapter, enabling sandwich attacks | FlashLoanLiquidator |
| 6.6 | INFO | V1 vs V2 architecture comparison and tradeoff analysis | V1, V2 |
| 6.7 | MEDIUM | No atomic adapter upgrade mechanism | V2, Balancer |
| 6.8 | MEDIUM | Adapter ownership fragmentation with custom Ownable | All adapters |
| 6.9 | MEDIUM | Adapters assume single-caller sequential execution; no reentrancy guard | All adapters |
| 6.10 | LOW | Aave callback verification correct but Pool immutability noted | V2, Liquidator |
| 6.11 | LOW | No token rescue function on adapters | All adapters |
| 6.12 | LOW | V3 adapter missing 1 bps fee tier | UniswapV3Adapter |
| 6.13 | MEDIUM | Shared adapter instances across multiple main contracts | All |
| 6.14 | LOW | CurveAdapter silently ignores deadline parameter | CurveAdapter |

## Severity Distribution

- **CRITICAL**: 1 (Finding 6.5)
- **HIGH**: 2 (Findings 6.1, 6.4)
- **MEDIUM**: 5 (Findings 6.2, 6.7, 6.8, 6.9, 6.13)
- **LOW**: 5 (Findings 6.3, 6.10, 6.11, 6.12, 6.14)
- **INFO**: 1 (Finding 6.6)

## Priority Remediation Order

1. **Finding 6.5** (CRITICAL) -- Add `minSwapAmountOut` to `LiquidationParams` and pass it to the adapter. This is the most immediately exploitable finding and can result in direct value extraction via MEV.
2. **Finding 6.4** (HIGH) -- Add execution lock to `BalancerFlashLoan.receiveFlashLoan()` to prevent externally-triggered callbacks.
3. **Finding 6.1** (HIGH) -- Implement timelock on adapter registration and consider multisig for admin operations.
4. **Finding 6.2** (MEDIUM) -- Make adapters explicitly implement `IDEXAdapter` for compile-time safety.
5. **Finding 6.9** (MEDIUM) -- Add reentrancy guards and balance-based `amountIn` detection to adapters.
6. **Findings 6.7, 6.8, 6.13** (MEDIUM) -- Address adapter lifecycle and ownership management.
7. **Findings 6.3, 6.10, 6.11, 6.12, 6.14** (LOW) -- Address in subsequent development cycles.
