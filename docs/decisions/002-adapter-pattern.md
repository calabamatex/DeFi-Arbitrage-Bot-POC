# ADR-002: DEX Adapter Pattern

## Status
Accepted

## Context
The bot needs to swap tokens across multiple DEXes (Uniswap V3, Uniswap V2/QuickSwap/SushiSwap, Curve). Each DEX has different interfaces, fee structures, and swap semantics. The flash loan contract needs to call these DEXes during the `executeOperation` callback.

## Decision
Implement the Adapter pattern via a shared Solidity interface `IDEXAdapter` (`contracts/interfaces/IDEXAdapter.sol`). Each DEX gets its own adapter contract:

- `UniswapV3Adapter.sol` — handles fee tiers (500/3000/10000 bps) and `exactInputSingle`
- `UniswapV2Adapter.sol` — handles QuickSwap, SushiSwap, and any V2-compatible router
- `CurveAdapter.sol` — handles Curve's `exchange` function for stablecoin pools

The main `FlashLoanArbitrageV2.sol` contract operates on `SwapStep[]` where each step specifies an adapter address, tokens, and minimum output. Adapters must be registered (whitelisted) by the contract owner.

## Consequences
- **Positive**: Adding a new DEX requires only deploying a new adapter — no changes to the core contract.
- **Positive**: Each adapter can be tested and audited independently.
- **Positive**: The `registeredAdapters` whitelist prevents unauthorized adapters from being injected.
- **Negative**: Additional gas cost per swap (~2-5K gas for the delegatecall overhead).
- **Negative**: Adapter registration is a manual step after deployment.
