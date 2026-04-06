# System Architecture

## Overview

The bot has two independent execution paths sharing common infrastructure:

```
                    ┌─────────────────────────┐
                    │      run_bot.py          │
                    │    (ArbitrageBot)        │
                    └────────────┬────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                   │
              ▼                  ▼                   ▼
    ┌──────────────────┐  ┌───────────────┐  ┌──────────────┐
    │ OpportunityDetector│  │ RiskManager   │  │ GasOptimizer │
    │ (price scanning)  │  │ (circuit      │  │ (EIP-1559)   │
    └────────┬─────────┘  │  breaker,     │  └──────────────┘
             │             │  loss limits) │
             ▼             └───────────────┘
    ┌──────────────────┐
    │ FlashLoanOrch.   │
    │ (tx building &   │
    │  submission)     │
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────────────────────────────┐
    │         ON-CHAIN (Solidity)               │
    │                                           │
    │  FlashLoanArbitrageV2.sol                │
    │    ├── Aave V3 flash loan callback       │
    │    ├── N-step swap execution              │
    │    └── Profit verification & repayment    │
    │                                           │
    │  DEX Adapters (IDEXAdapter interface)     │
    │    ├── UniswapV3Adapter (fee tiers)       │
    │    ├── UniswapV2Adapter (QuickSwap/Sushi) │
    │    └── CurveAdapter (stablecoins)         │
    └──────────────────────────────────────────┘
```

## Entry Points

| Command | System | Description |
|---------|--------|-------------|
| `python run_bot.py --chain polygon` | Arbitrage | Flash loan arbitrage bot (primary) |
| `python run_liquidation_bot.py` | Liquidation | Aave V3 liquidation bot (separate) |

## Execution Flow (Arbitrage)

1. **OpportunityDetector.scan_opportunities()** queries Uniswap V3 Quoter and V2 Router contracts for price quotes across configured token pairs
2. For each pair, it tests both directions (V3->V2 and V2->V3) across multiple fee tiers
3. Profitable opportunities pass to **ArbitrageBot.execute_opportunity()** which gates on the **RiskManager** (position limits, circuit breaker, daily loss)
4. **FlashLoanOrchestrator.execute_opportunity()** builds the on-chain transaction:
   - Selects flash loan provider (Aave V3 at 0.05% or Balancer at 0%)
   - Constructs SwapStep[] (adapter address, tokens, minAmountOut per step)
   - Simulates via `eth_call` before submission
   - Signs and submits (or logs in dry-run mode)
5. **FlashLoanArbitrageV2.sol** receives the flash loan callback, executes all swap steps through adapters, verifies profit exceeds minimum, and repays the loan atomically

## Execution Flow (Liquidation)

1. **LiquidationDetector** discovers Aave V3 borrowers via recent block events
2. Checks `getUserAccountData()` for health factors < 1.0
3. Calculates liquidation bonus profit minus flash loan fee and swap costs
4. **LiquidationOrchestrator** executes via **FlashLoanLiquidator.sol**

## Key Components

### Detection Layer
- **OpportunityDetector** (`src/opportunity_detector.py`) - Scans DEX prices, calculates profitability after fees
- **LiquidationDetector** (`src/liquidation_detector.py`) - Monitors Aave V3 health factors

### Execution Layer
- **FlashLoanOrchestrator** (`src/flash_loan_orchestrator.py`) - Builds and submits flash loan arbitrage transactions
- **LiquidationOrchestrator** (`src/liquidation_orchestrator.py`) - Builds and submits liquidation transactions
- **FlashLoanSelector** (`src/flash_loan_providers.py`) - Chooses Aave V3 vs Balancer based on token availability

### Risk & Safety
- **RiskManager** (`src/utils/risk_manager.py`) - Circuit breaker, position limits, daily loss tracking
- **SlippageProtection** (`src/utils/slippage_protection.py`) - Price impact estimation, minimum output calculation
- **GasOptimizer** (`src/utils/gas_optimizer.py`) - EIP-1559 fee estimation with urgency tiers
- **MEVProtection** (`src/utils/mev_protection.py`) - Flashbots Protect integration for private tx submission
- **EmergencyShutdown** (`src/utils/emergency_shutdown.py`) - Admin-triggered halt with Telegram alerts

### Infrastructure
- **TransactionManager** (`src/utils/transaction_manager.py`) - Nonce management, signing, retry with gas bumps
- **MetricsCollector** (`src/utils/metrics_collector.py`) - Prometheus metrics export
- **HealthServer** (`src/api/health.py`) - Liveness/readiness probes, metrics endpoint
- **Database** (`src/db/`) - PostgreSQL + TimescaleDB for opportunity and trade logging

## Smart Contract Design

The adapter pattern decouples the core flash loan logic from DEX-specific swap mechanics:

```
FlashLoanArbitrageV2
    │
    ├── executeArbitrage(params)     [owner-only, nonReentrant]
    │     ├── Request flash loan from Aave V3 Pool
    │     └── executeOperation()     [callback from Aave]
    │           ├── For each SwapStep:
    │           │     ├── Approve adapter for tokenIn
    │           │     ├── adapter.swap(tokenIn, tokenOut, amount, minOut, data)
    │           │     └── Verify actual balance >= minAmountOut
    │           ├── Verify final balance >= loanAmount + fee + minProfit
    │           └── Approve Pool to reclaim loan + fee
    │
    ├── registerAdapter(addr)        [owner-only]
    ├── pause() / unpause()          [owner-only]
    └── withdrawProfit(token, to)    [owner-only]
```

## Known Limitations

1. **Sequential RPC calls** - The detector makes 600+ sequential HTTP calls per scan. Multicall3 batching infrastructure exists (`src/utils/multicall.py`) but is not yet wired into the detector.
2. **No WebSocket subscriptions** - Detection uses polling (every 5s), not event-driven block subscriptions.
3. **No Flashbots integration in execution** - MEV protection module exists but is not connected to the orchestrator's transaction submission path.
4. **Single admin key** - No multi-sig support for contract ownership.
