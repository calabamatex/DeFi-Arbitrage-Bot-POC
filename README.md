# Preamble
This repo was created based upon a challenge from a collegue. The challnege was to create a functional crypto arbitrage bot though vibe coding. Why a crypto arbitrage bot? Becasue of the complexity of architecting/coding such a system in tradiotnal methods, hence a extreme challenge for vibe coding. The project was a chllenge given the state of vibe coding at the time. Does this repo succedd in its ambitions? Yes, mostly, though to fully implement this bot at scale requires additional hardware, netoworking, etc that is outside of what can be vibe coded. This bot does work on testnets, though it not a sufficient proof point for working on active networks. I am not actively using this repo and do not plan updates.  


# Flash Loan Arbitrage Bot

A DeFi trading system that captures arbitrage spreads across decentralized exchanges using flash loans (zero upfront capital). Built as an educational project to demonstrate smart contract development, DeFi protocol integration, and MEV-aware bot architecture.

## What It Does

Monitors on-chain pricing across multiple DEXes (Uniswap V3, QuickSwap, SushiSwap, Curve) on EVM chains. When it detects a price discrepancy, it borrows tokens via flash loan, buys low on one DEX, sells high on another, repays the loan, and keeps the profit — all in a single atomic transaction.

A secondary subsystem monitors Aave V3 lending positions for under-collateralized borrowers and executes liquidations for the protocol-defined bonus.

## Architecture

```
Entry Point: run_bot.py --chain polygon

    OpportunityDetector          LiquidationDetector
    (scans DEX prices)           (monitors Aave health factors)
            |                            |
    FlashLoanOrchestrator        LiquidationOrchestrator
    (builds + submits tx)        (executes liquidations)
            |                            |
    FlashLoanArbitrageV2.sol     FlashLoanLiquidator.sol
    (on-chain execution)         (on-chain execution)
            |
    DEX Adapters (V2, V3, Curve)
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for full system design.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Bot | Python 3.11+, web3.py, asyncio |
| Contracts | Solidity 0.8.20, OpenZeppelin, Aave V3 |
| DEX Integration | Uniswap V3/V2, QuickSwap, SushiSwap, Curve |
| Flash Loans | Aave V3 (0.05% fee), Balancer V2 (0% fee) |
| Database | PostgreSQL + TimescaleDB |
| Monitoring | Prometheus, Grafana, Telegram alerts |
| Testing | pytest (Python), Foundry/forge (Solidity) |
| Infrastructure | Docker Compose, GitHub Actions CI/CD |

## Supported Chains

| Chain | Type | Contracts Deployed |
|-------|------|-------------------|
| Polygon | Mainnet | Yes |
| Arbitrum One | Mainnet | Yes |
| Optimism | Mainnet | Pending |
| Base | Mainnet | Pending |
| Polygon Amoy | Testnet | Yes |
| Arbitrum Sepolia | Testnet | Yes |

## Quick Start

```bash
# Clone and install
git clone <repo-url> && cd arb_bot_cryp_eea
pip install -r requirements.txt
cp .env.example .env   # Edit with your RPC URLs and config

# Run in dry-run mode (default - no real transactions)
python run_bot.py --chain polygon

# Run the dry-run validator against a mainnet fork
anvil --fork-url $POLYGON_RPC_URL
python scripts/dry_run_mainnet.py --chain polygon --rpc-url http://127.0.0.1:8545

# Run tests
pytest tests/ -v
forge test -vvv
```

## Risk Controls

- **Circuit Breaker** - Halts trading after N consecutive losses (default: 5)
- **Daily Loss Limit** - Stops execution when daily P&L breaches threshold
- **Position Sizing** - Caps individual trade size and total exposure
- **Slippage Protection** - Reverts transactions exceeding tolerance
- **Dry-Run Mode** - Enabled by default; simulates without executing
- **Transaction Simulation** - Every trade simulated via `eth_call` before broadcast

## Smart Contracts

| Contract | Purpose | Lines |
|----------|---------|-------|
| `FlashLoanArbitrageV2.sol` | Multi-step flash loan arbitrage executor | 356 |
| `FlashLoanLiquidator.sol` | Aave V3 liquidation via flash loan | 265 |
| `BalancerFlashLoan.sol` | 0% fee flash loan alternative | 306 |
| `UniswapV3Adapter.sol` | V3 swap integration | 227 |
| `UniswapV2Adapter.sol` | V2/QuickSwap/SushiSwap integration | 174 |
| `CurveAdapter.sol` | Curve stablecoin swap integration | 188 |

All contracts use OpenZeppelin's `ReentrancyGuard`, `Pausable`, and `Ownable`. Static analysis via Slither runs in CI. **No formal security audit has been performed** - see [docs/SECURITY_AUDIT.md](docs/SECURITY_AUDIT.md) for the internal review.

## Project Structure

```
run_bot.py                    # Primary entry point (flash loan bot)
run_liquidation_bot.py        # Liquidation bot entry point
src/
  opportunity_detector.py     # DEX price scanning & opportunity detection
  flash_loan_orchestrator.py  # Flash loan execution engine
  liquidation_detector.py     # Aave V3 health factor monitoring
  liquidation_orchestrator.py # Liquidation execution
  config.py                   # Configuration management
  utils/                      # Risk manager, gas optimizer, MEV protection, etc.
  api/                        # Health endpoint & Prometheus metrics
  db/                         # PostgreSQL models & migrations
contracts/                    # Solidity smart contracts
  adapters/                   # DEX adapter contracts
tests/                        # Python tests (pytest)
test/                         # Solidity tests (Foundry)
config/                       # Token lists, Prometheus config
docs/                         # Architecture, deployment, security audit
scripts/                      # Deployment, monitoring, benchmarking tools
```

## Lessons Learned

This project taught several hard truths about MEV and on-chain arbitrage:

1. **Competition is extreme.** Real-world DEX arbitrage in 2025-2026 is dominated by teams running Rust/C++ bots on co-located infrastructure with sub-millisecond latency and proprietary orderflow agreements. A Python bot polling every 5 seconds cannot compete on major pairs.

2. **Real spreads are tiny.** The proof-of-concept validated contract execution against an artificial 70% spread on a local fork. Real spreads on liquid pairs are 0.01-0.5% and last milliseconds. Most are unprofitable after gas + flash loan fees.

3. **The bottleneck is I/O, not CPU.** The opportunity detector makes 600+ sequential RPC calls per scan cycle. Parallelization via Multicall3 batching and async I/O would yield 10-50x improvement - a bigger gain than rewriting in Rust.

4. **Liquidation opportunities are more accessible.** Aave V3 liquidations on L2 chains are less competitive than DEX arbitrage, with higher per-event profit ($50-500 vs $0.10-5).

5. **Flash loans eliminate capital risk but not execution risk.** Zero upfront capital is powerful, but unaudited contracts, gas estimation errors, and MEV frontrunning remain real risks.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) - System design and data flow
- [Deployment](docs/DEPLOYMENT.md) - Testnet and mainnet deployment
- [Security Audit](docs/SECURITY_AUDIT.md) - Internal security review (Slither + manual)
- [Testing Guide](docs/testing-guide.md) - How to run and write tests

## License

MIT
