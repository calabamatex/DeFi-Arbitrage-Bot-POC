# Security Audit Report: Access Control & Authorization

**Auditor**: Agent 2 (Access Control Specialist)
**Date**: 2026-02-27
**Scope**: All contracts in `/contracts/`
**Focus**: Owner privileges, adapter authorization, emergency functions, missing access control, ownership transfer, centralization risks

---

## Executive Summary

The codebase exhibits a heavily centralized ownership model across all contracts. While the main arbitrage and liquidation contracts correctly use OpenZeppelin's `Ownable`, `ReentrancyGuard`, and `Pausable`, the three DEX adapter contracts roll their own access control instead of using battle-tested OZ `AccessControl` or `Ownable2Step`. Several critical findings relate to the owner's unchecked ability to drain all funds, the lack of timelocks on critical administrative operations, and single-step ownership transfer in adapters that can permanently brick access. Mock contracts have no access control at all, which is expected for testing but dangerous if ever deployed to mainnet.

**Total Findings**: 14
- CRITICAL: 3
- HIGH: 5
- MEDIUM: 4
- LOW: 1
- INFO: 1

---

## Findings

### AC-01: Owner Can Drain All Funds via emergencyWithdraw Without Timelock

**Severity**: CRITICAL

**Contracts Affected**:
- `FlashLoanArbitrageV2.sol` (lines 314-320)
- `BalancerFlashLoan.sol` (lines 277-283)
- `FlashLoanLiquidator.sol` (lines 260-262)

**Description**:
The `emergencyWithdraw()` function in V2, Balancer, and Liquidator contracts allows the owner to transfer arbitrary amounts of any ERC20 token to any address with zero delay, zero governance oversight, and no upper bound. Unlike `withdrawProfits()` which is bounded by `totalProfits[token]`, `emergencyWithdraw()` has no such constraint -- it can transfer the full contract balance.

**Code (FlashLoanArbitrageV2.sol lines 314-320)**:
```solidity
function emergencyWithdraw(
    address token,
    uint256 amount,
    address to
) external onlyOwner nonReentrant {
    IERC20(token).safeTransfer(to, amount);
}
```

**Attack Scenario**:
1. Owner's private key is compromised (phishing, malware, social engineering).
2. Attacker calls `emergencyWithdraw(USDC, fullBalance, attackerAddress)` on all three contracts.
3. All funds are drained in a single transaction per contract with no cooldown, no multisig requirement, and no event emitted (in V2 and Balancer -- only V1 emits `EmergencyWithdrawal`).

**Additional Note**: The V2 and Balancer `emergencyWithdraw` functions do NOT emit any events, making the drain harder to detect via off-chain monitoring compared to V1 which emits `EmergencyWithdrawal`.

**Recommended Fix**:
1. Implement a timelock (e.g., 24-48 hours) on emergency withdrawals using a two-step pattern: `requestEmergencyWithdraw()` followed by `executeEmergencyWithdraw()` after the delay.
2. Require a multisig wallet as the owner rather than an EOA.
3. Add an event emission to all `emergencyWithdraw()` implementations.
4. Consider using OpenZeppelin's `TimelockController` for governance over critical operations.

---

### AC-02: Single-Step Ownership Transfer in All Three Adapters -- Permanent Lockout Risk

**Severity**: CRITICAL

**Contracts Affected**:
- `UniswapV2Adapter.sol` (lines 89-93)
- `UniswapV3Adapter.sol` (lines 117-121)
- `CurveAdapter.sol` (lines 88-92)

**Description**:
All three adapter contracts implement a custom single-step `transferOwnership()` function. If the owner accidentally transfers ownership to an incorrect or zero-length-but-non-zero address (e.g., a typo that passes the `!= address(0)` check), ownership is irrecoverably lost. The adapter becomes permanently locked -- no one can update authorized callers, register pools (Curve), or transfer ownership again.

**Code (UniswapV2Adapter.sol lines 89-93)**:
```solidity
function transferOwnership(address newOwner) external onlyOwner {
    require(newOwner != address(0), "Invalid owner");
    emit OwnershipTransferred(owner, newOwner);
    owner = newOwner;
}
```

**Attack Scenario**:
1. Admin calls `transferOwnership(0x1234...wrong)` with a typo in the address.
2. Ownership transfers immediately with no confirmation step.
3. The adapter is now permanently unmanageable. The main contract still has it registered but its authorization mappings can never be updated.
4. If a security incident occurs, there is no way to de-authorize callers on that adapter.

**Recommended Fix**:
Replace custom ownership with OpenZeppelin `Ownable2Step`, which requires the new owner to call `acceptOwnership()`:
```solidity
import {Ownable2Step, Ownable} from "@openzeppelin/contracts/access/Ownable2Step.sol";

contract UniswapV2Adapter is Ownable2Step {
    constructor(address _router, string memory _dexName) Ownable(msg.sender) {
        // ...
    }
}
```

---

### AC-03: Owner Can Register Malicious Adapter to Steal Flash-Loaned Funds

**Severity**: CRITICAL

**Contracts Affected**:
- `FlashLoanArbitrageV2.sol` (lines 251-254)
- `BalancerFlashLoan.sol` (lines 242-245)
- `FlashLoanLiquidator.sol` (lines 240-243)

**Description**:
The `setAdapter()` function allows the owner to register any arbitrary address as a "DEX adapter." During arbitrage execution, the contract transfers flash-loaned tokens to the adapter via `safeTransfer` and then calls `swapDirect()` on it. A malicious adapter can simply receive the tokens and return a fabricated `amountOut` -- although the balance verification check (C-04 fix) in V2 and Balancer mitigates the return value lie, the tokens are already transferred to the malicious adapter before the check.

The balance verification will cause a revert, but a more sophisticated attack could use a reentrant or selfdestruct-based adapter that transfers the tokens elsewhere during the `swapDirect` call (before the balance check), causing the entire flash loan to fail and the Aave/Balancer pool to seize any collateral or cause a DoS.

More critically, this can be combined with a social engineering attack: the owner registers a malicious adapter, constructs params where the "swap" routes through that adapter, and extracts tokens. Even with the balance check, a malicious adapter could perform the swap on a real DEX but route profits to a different address.

**Code (FlashLoanArbitrageV2.sol lines 192, 251-254)**:
```solidity
// Tokens sent to adapter BEFORE verification
IERC20(step.tokenIn).safeTransfer(step.adapter, currentAmount);

// Registration has no validation
function setAdapter(address adapter, bool status) external onlyOwner {
    registeredAdapters[adapter] = status;
    emit AdapterRegistered(adapter, status);
}
```

**Recommended Fix**:
1. Implement a timelock on adapter registration (e.g., 48-hour delay).
2. Add adapter interface validation (check that the address implements `IDEXAdapter` via ERC-165 `supportsInterface`).
3. Consider an adapter whitelist governance mechanism with multiple signers.
4. Emit events that off-chain monitoring can alert on, and add a delay before the adapter becomes active.

---

### AC-04: V1 emergencyWithdrawers Mapping -- Privilege Escalation Without Revocation Guarantee

**Severity**: HIGH

**Contract Affected**: `FlashLoanArbitrage.sol` (lines 49-51, 348-358, 385-396)

**Description**:
The V1 contract uses an `emergencyWithdrawers` mapping that grants withdrawal privileges to multiple addresses. The owner can grant this permission via `grantEmergencyWithdrawer()`, but there is no mechanism to enumerate all granted addresses. If the owner forgets who has been granted access, or if the owner's key is compromised and the attacker silently grants themselves emergency access before the owner notices, there is no way to perform a blanket revocation.

Furthermore, `emergencyWithdraw()` in V1 is NOT restricted to `onlyOwner` -- it checks the `emergencyWithdrawers` mapping directly, expanding the attack surface beyond just the owner.

**Code (FlashLoanArbitrage.sol lines 385-396)**:
```solidity
function emergencyWithdraw(
    address token,
    uint256 amount,
    address to
) external nonReentrant {
    if (!emergencyWithdrawers[msg.sender]) {
        revert Unauthorized();
    }
    IERC20(token).safeTransfer(to, amount);
    emit EmergencyWithdrawal(token, amount, to);
}
```

**Attack Scenario**:
1. Owner's key is compromised.
2. Attacker calls `grantEmergencyWithdrawer(attackerBackdoorAddress)`.
3. Even after the owner recovers their key (e.g., via social recovery), the attacker's backdoor address still has emergency withdrawal rights.
4. No enumeration means the owner cannot audit who has access without scanning all historical `grantEmergencyWithdrawer` events.

**Recommended Fix**:
1. Use an enumerable set (e.g., OZ `EnumerableSet.AddressSet`) to track all emergency withdrawers so they can be audited.
2. Add a `revokeAllEmergencyWithdrawers()` function for emergency use.
3. Emit granular events for all grant/revoke operations (already done).
4. Consider replacing this pattern entirely with a multisig requirement.

---

### AC-05: Custom Access Control in Adapters Instead of OZ AccessControl

**Severity**: HIGH

**Contracts Affected**:
- `UniswapV2Adapter.sol` (lines 39-66)
- `UniswapV3Adapter.sol` (lines 60-94)
- `CurveAdapter.sol` (lines 34-67)

**Description**:
All three adapters implement custom `owner` state variables, `onlyOwner` modifiers, and `authorized` mappings from scratch rather than using OpenZeppelin's `AccessControl` or `Ownable` contracts. Custom access control is a well-known source of bugs because:

1. The `owner` variable is `public` but has no getter that matches OZ's interface, creating integration friction.
2. The `Unauthorized()` error is used for both owner and authorized-caller checks, making error diagnosis ambiguous.
3. No `renounceOwnership()` function exists, which could be desirable or undesirable depending on the use case, but the choice was made implicitly rather than explicitly.
4. The `authorized` mapping provides no role hierarchy or enumeration -- it is a flat boolean mapping.

The custom implementation is functionally correct for basic use cases, but it has not been audited to the same degree as OpenZeppelin's battle-tested `AccessControl`.

**Recommended Fix**:
Replace custom access control with OZ `Ownable2Step` for ownership and OZ `AccessControl` for the authorized-caller pattern:
```solidity
import {Ownable2Step, Ownable} from "@openzeppelin/contracts/access/Ownable2Step.sol";
import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";

contract UniswapV2Adapter is Ownable2Step, AccessControl {
    bytes32 public constant CALLER_ROLE = keccak256("CALLER_ROLE");

    constructor(address _router, string memory _dexName) Ownable(msg.sender) {
        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
        _grantRole(CALLER_ROLE, msg.sender);
        // ...
    }

    function swapDirect(...) external onlyRole(CALLER_ROLE) returns (uint256) {
        // ...
    }
}
```

---

### AC-06: No Timelock on Any Critical Administrative Operation

**Severity**: HIGH

**Contracts Affected**: ALL contracts

**Description**:
None of the contracts implement any form of timelock or delay on critical administrative operations. The following operations all execute immediately upon owner call:

| Operation | Contract(s) | Risk |
|-----------|-------------|------|
| `setAdapter()` / `setDEXWhitelist()` | V2, Balancer, Liquidator, V1 | Register malicious adapter/router |
| `setMinProfit()` | All | Set to 0, enabling unprofitable (loss) trades |
| `setMaxSlippage()` | V1, V2, Balancer | Increase slippage tolerance to drain value |
| `emergencyWithdraw()` | All | Drain all funds instantly |
| `pause()` / `unpause()` | All | DoS the contract or unpause prematurely |
| `grantEmergencyWithdrawer()` | V1 | Expand withdrawal privileges |
| `registerPool()` | CurveAdapter | Register malicious Curve pool |

**Recommended Fix**:
Implement a two-tier governance model:
1. **Immediate operations**: `pause()` (emergency pause should remain instant).
2. **Timelocked operations**: All other admin functions should go through a `TimelockController` with a minimum 24-48 hour delay.

---

### AC-07: Owner Can Set minProfit to Zero, Enabling Sandwich/Loss Trades

**Severity**: HIGH

**Contracts Affected**:
- `FlashLoanArbitrageV2.sol` (line 260)
- `FlashLoanArbitrage.sol` (line 313)
- `BalancerFlashLoan.sol` (line 247)
- `FlashLoanLiquidator.sol` (line 245)

**Description**:
The `setMinProfit()` function has no lower bound validation. The owner can set `minProfit` to `0`, which would allow arbitrage executions that result in zero or negligible profit. While the contract still requires `profit > 0` (due to `currentAmount <= amountOwed` check), a profit of `1 wei` would pass. This enables:

1. MEV sandwich attacks where the owner (or a compromised key) intentionally executes unprofitable trades that benefit a searcher.
2. Gas-wasting attacks that drain the owner's ETH balance through repeated dust-profit executions.

**Code (FlashLoanArbitrageV2.sol line 260)**:
```solidity
function setMinProfit(uint256 _minProfit) external onlyOwner {
    uint256 oldValue = minProfit;
    minProfit = _minProfit;
    emit MinProfitUpdated(oldValue, _minProfit);
}
```

**Recommended Fix**:
Add a minimum floor for `minProfit`:
```solidity
uint256 public constant MIN_PROFIT_FLOOR = 1e6; // e.g., 1 USDC worth

function setMinProfit(uint256 _minProfit) external onlyOwner {
    require(_minProfit >= MIN_PROFIT_FLOOR, "Below minimum floor");
    // ...
}
```

---

### AC-08: Adapter Owner Can Rug by De-authorizing the Main Contract

**Severity**: HIGH

**Contracts Affected**:
- `UniswapV2Adapter.sol` (lines 80-83)
- `UniswapV3Adapter.sol` (lines 108-111)
- `CurveAdapter.sol` (lines 79-82)

**Description**:
The adapter owner (which may differ from the main contract owner if ownership was transferred) can call `setAuthorized(mainContractAddress, false)` to de-authorize the main arbitrage contract. This would cause all subsequent arbitrage transactions to revert at the adapter's `onlyAuthorized` modifier, effectively bricking the arbitrage system without affecting the main contract's state.

If the adapter and main contract have different owners (which is possible since adapter ownership can be transferred independently), this creates a cross-contract authorization dependency that is not enforced by any on-chain mechanism.

**Attack Scenario**:
1. Adapter deployed by address A, main contract deployed by address A.
2. Adapter ownership transferred to address B (perhaps a compromised or malicious party).
3. B calls `setAuthorized(mainContract, false)` on all adapters.
4. All arbitrage execution reverts. Funds in the main contract are safe but the system is DoS'd.

**Recommended Fix**:
1. Ensure adapter ownership cannot diverge from main contract ownership, or
2. Implement the adapters as non-upgradeable with immutable authorization, or
3. Add a recovery mechanism in the main contract to handle adapter authorization failures.

---

### AC-09: Missing Event Emission on emergencyWithdraw in V2 and Balancer

**Severity**: MEDIUM

**Contracts Affected**:
- `FlashLoanArbitrageV2.sol` (lines 314-320)
- `BalancerFlashLoan.sol` (lines 277-283)
- `FlashLoanLiquidator.sol` (lines 260-262)

**Description**:
The `emergencyWithdraw()` function in V2, Balancer, and Liquidator contracts does not emit any event. This makes it impossible to monitor emergency withdrawals via off-chain event listeners or subgraphs. By contrast, V1's `emergencyWithdraw()` correctly emits an `EmergencyWithdrawal` event.

**Code (FlashLoanArbitrageV2.sol lines 314-320)**:
```solidity
function emergencyWithdraw(
    address token,
    uint256 amount,
    address to
) external onlyOwner nonReentrant {
    IERC20(token).safeTransfer(to, amount);
    // No event emitted!
}
```

**Recommended Fix**:
Add event emission matching V1's pattern:
```solidity
event EmergencyWithdrawal(address indexed token, uint256 amount, address indexed to);

function emergencyWithdraw(
    address token,
    uint256 amount,
    address to
) external onlyOwner nonReentrant {
    IERC20(token).safeTransfer(to, amount);
    emit EmergencyWithdrawal(token, amount, to);
}
```

---

### AC-10: Missing Event Emission on setMaxSlippage in V2 and Balancer

**Severity**: MEDIUM

**Contracts Affected**:
- `FlashLoanArbitrageV2.sol` (lines 270-273)
- `BalancerFlashLoan.sol` (lines 253-256)

**Description**:
The `setMaxSlippage()` function in V2 and Balancer does not emit an event when the slippage parameter is changed. V1's `setMaxSlippage()` correctly emits `MaxSlippageUpdated`. Without events, off-chain monitoring cannot detect when slippage tolerance has been modified, which is a precondition for value-extraction attacks.

**Code (FlashLoanArbitrageV2.sol lines 270-273)**:
```solidity
function setMaxSlippage(uint256 _maxSlippageBps) external onlyOwner {
    require(_maxSlippageBps <= 1000, "Slippage too high");
    maxSlippageBps = _maxSlippageBps;
    // No event emitted!
}
```

**Recommended Fix**:
```solidity
event MaxSlippageUpdated(uint256 oldValue, uint256 newValue);

function setMaxSlippage(uint256 _maxSlippageBps) external onlyOwner {
    require(_maxSlippageBps <= 1000, "Slippage too high");
    uint256 oldValue = maxSlippageBps;
    maxSlippageBps = _maxSlippageBps;
    emit MaxSlippageUpdated(oldValue, _maxSlippageBps);
}
```

---

### AC-11: Owner Can Pause Contracts Indefinitely With No Escape Hatch

**Severity**: MEDIUM

**Contracts Affected**: All four main contracts (V1, V2, Balancer, Liquidator)

**Description**:
The `pause()` and `unpause()` functions are both restricted to `onlyOwner`. If the owner's private key is lost, the contract can never be unpaused. If the owner maliciously pauses, there is no governance mechanism, emergency unpause, or time-limited auto-unpause to restore operations.

While `emergencyWithdraw()` still works when paused (it does not have `whenNotPaused`), the arbitrage execution functions are permanently blocked.

**Recommended Fix**:
1. Implement an auto-unpause timer (e.g., contract auto-unpauses after 7 days unless re-paused).
2. Add a secondary "guardian" role that can unpause.
3. Use a multisig as the owner to prevent single-point-of-failure key loss.

---

### AC-12: Inconsistent Emergency Withdrawal Model Between V1 and V2/Balancer/Liquidator

**Severity**: MEDIUM

**Contracts Affected**:
- `FlashLoanArbitrage.sol` (V1) -- uses `emergencyWithdrawers` mapping
- `FlashLoanArbitrageV2.sol` -- uses `onlyOwner`
- `BalancerFlashLoan.sol` -- uses `onlyOwner`
- `FlashLoanLiquidator.sol` -- uses `onlyOwner`

**Description**:
V1 implements a more granular emergency withdrawal model with a dedicated `emergencyWithdrawers` mapping, `grantEmergencyWithdrawer()`, and `revokeEmergencyWithdrawer()`. V2, Balancer, and Liquidator simplified this to just `onlyOwner`. This inconsistency means:

1. If the same EOA operates all contracts, the security posture differs across contracts.
2. If V1 emergency withdrawers are granted but the system migrates to V2, those addresses lose their emergency access without explicit communication.
3. V1 has a broader attack surface (multiple addresses can withdraw) but also better resilience (multiple addresses can respond to emergencies).

**Recommended Fix**:
Standardize the emergency withdrawal model across all contracts. Either adopt V1's multi-address approach everywhere (with enumeration, per AC-04) or V2's owner-only approach everywhere.

---

### AC-13: MockDEX and MockERC20 Have No Access Control

**Severity**: LOW

**Contracts Affected**:
- `MockDEX.sol` (lines 65-74) -- `fund()` and `withdraw()` are unrestricted
- `MockERC20.sol` (line 27) -- `mint()` is unrestricted

**Description**:
The `MockDEX.withdraw()` function allows anyone to drain all tokens from the mock DEX. The `MockERC20.mint()` function allows anyone to mint arbitrary amounts. While these are clearly test contracts, they have no `// @dev DO NOT DEPLOY TO MAINNET` warnings and use a different Solidity version (`^0.8.19`) from the production contracts (`^0.8.20`), suggesting they may have been written separately and could be deployed accidentally.

**Recommended Fix**:
1. Add prominent NatSpec warnings: `/// @custom:security DO NOT DEPLOY TO MAINNET - NO ACCESS CONTROL`.
2. Move mock contracts to a `contracts/test/` or `contracts/mocks/` directory.
3. Add a deployment script check that excludes mock contracts from mainnet deployments.

---

### AC-14: Adapters Do Not Implement IDEXAdapter Interface Explicitly

**Severity**: INFO

**Contracts Affected**:
- `UniswapV2Adapter.sol`
- `UniswapV3Adapter.sol`
- `CurveAdapter.sol`

**Description**:
None of the three adapter contracts explicitly declare `is IDEXAdapter` in their contract definition. They implement the `swapDirect()` function with a matching signature, but without explicit interface inheritance the compiler does not verify ABI compatibility. This is not a direct access control issue, but it weakens the type safety of the adapter registration system -- the main contract's `setAdapter()` cannot verify at registration time whether the provided address actually implements `IDEXAdapter`.

**Recommended Fix**:
Have all adapters explicitly implement the interface:
```solidity
import {IDEXAdapter} from "../interfaces/IDEXAdapter.sol";

contract UniswapV2Adapter is IDEXAdapter {
    // ...
}
```
Additionally, consider adding ERC-165 `supportsInterface` to enable on-chain adapter validation during registration.

---

## Owner Privilege Map

The following table shows all owner-controlled functions across all contracts:

| Function | V1 | V2 | Balancer | Liquidator | Timelocked | Risk |
|----------|----|----|----------|------------|------------|------|
| `executeArbitrage()` | onlyOwner | onlyOwner | onlyOwner | onlyOwner | No | Execution gating |
| `setAdapter()` / `setDEXWhitelist()` | onlyOwner | onlyOwner | onlyOwner | onlyOwner | No | Malicious adapter |
| `setMinProfit()` | onlyOwner | onlyOwner | onlyOwner | onlyOwner | No | Enable dust trades |
| `setMaxSlippage()` | onlyOwner | onlyOwner | onlyOwner | N/A | No | Increase tolerance |
| `pause()` | onlyOwner | onlyOwner | onlyOwner | onlyOwner | No | DoS |
| `unpause()` | onlyOwner | onlyOwner | onlyOwner | onlyOwner | No | Premature resume |
| `withdrawProfits()` | onlyOwner | onlyOwner | onlyOwner | onlyOwner | No | Fund extraction |
| `emergencyWithdraw()` | emergencyWithdrawers | onlyOwner | onlyOwner | onlyOwner | No | **Full drain** |
| `grantEmergencyWithdrawer()` | onlyOwner | N/A | N/A | N/A | No | Privilege escalation |
| `revokeEmergencyWithdrawer()` | onlyOwner | N/A | N/A | N/A | No | De-escalation |

**Adapter Owner Functions**:

| Function | V2Adapter | V3Adapter | CurveAdapter | Risk |
|----------|-----------|-----------|--------------|------|
| `setAuthorized()` | onlyOwner | onlyOwner | onlyOwner | De-authorize main contract |
| `transferOwnership()` | onlyOwner | onlyOwner | onlyOwner | Permanent lockout |
| `registerPool()` | N/A | N/A | onlyOwner | Malicious pool |

---

## Centralization Risk Summary

The owner (a single EOA unless deployed behind a multisig) has the unilateral and instant ability to:

1. **Drain all funds** from any contract via `emergencyWithdraw()` to any address.
2. **Register malicious adapters** that could steal flash-loaned funds or extract MEV.
3. **Set minimum profit to zero**, enabling unprofitable or dust-profit trades.
4. **Increase slippage tolerance to 10%**, enabling sandwich attack extraction.
5. **Pause contracts indefinitely** with no governance override.
6. **Grant emergency withdrawal rights** (V1) to arbitrary addresses.
7. **Register malicious Curve pools** that could manipulate exchange rates.
8. **Transfer adapter ownership** to unrecoverable addresses, bricking the adapter.

None of these operations have any delay, multi-signature requirement, or on-chain governance check.

---

## Recommendations Summary (Priority Order)

1. **[CRITICAL]** Deploy all owner contracts behind a multisig (e.g., Gnosis Safe) -- this single change mitigates the majority of centralization risks.
2. **[CRITICAL]** Replace custom adapter ownership with OZ `Ownable2Step` to prevent permanent lockout.
3. **[CRITICAL]** Implement a `TimelockController` for all non-emergency administrative operations (adapter registration, parameter changes, emergency withdrawer grants).
4. **[HIGH]** Add minimum floor validation to `setMinProfit()`.
5. **[HIGH]** Standardize emergency withdrawal model across all contracts.
6. **[HIGH]** Add event emissions to all state-changing admin functions (emergencyWithdraw, setMaxSlippage in V2/Balancer).
7. **[HIGH]** Use OZ `AccessControl` with role-based permissions in adapters instead of flat boolean mapping.
8. **[MEDIUM]** Implement auto-unpause mechanism or guardian role for pause recovery.
9. **[MEDIUM]** Add ERC-165 interface checking to adapter registration.
10. **[LOW]** Add deployment safeguards for mock contracts.
