# Testing Guide — Flash Loan Arbitrage Bot

Step-by-step implementation for testing from local unit tests through mainnet.

---

## Phase 0: Local Unit Tests (no network needed)

Baseline: **211 Python tests + 91 Solidity tests passing**.

```bash
# Activate venv
source .venv/bin/activate

# Python tests (all mocked, no RPC needed)
python -m pytest tests/ -q --no-cov

# Solidity tests (local EVM, no fork)
forge test --no-match-contract "Fork"
```

---

## Phase 1: Local Fork Testing (Anvil)

Tests the full pipeline against real on-chain state without spending gas.

### Step 1 — Enable Polygon on Alchemy

Your Alchemy app needs MATIC_MAINNET enabled. Go to:
`https://dashboard.alchemy.com/apps/<your-app-id>/networks` and enable Polygon.

### Step 2 — Start a local fork

```bash
# Terminal 1: Start Anvil forking Polygon mainnet
anvil --fork-url $POLYGON_RPC_URL --block-time 2
```

Anvil gives you 10 funded accounts with 10,000 ETH each. Note the first private key it prints.

### Step 3 — Run Forge fork tests against Anvil

```bash
# Terminal 2: Run fork tests against local Anvil
forge test --fork-url http://localhost:8545 -vvv
```

### Step 4 — Deploy contracts to local fork

```bash
# Set env vars for deploy script
export AAVE_POOL_PROVIDER=0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb
export UNISWAP_V3_ROUTER=0xE592427A0AEce92De3Edee1F18E0157C05861564
export UNISWAP_V3_QUOTER=0x61fFE014bA17989E743c5F6cB21bF9697530B21e
export V2_ROUTER=0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff
export BALANCER_VAULT=0xBA12222222228d8Ba445958a75a0704d566BF2C8

# Dry-run first (no broadcast)
forge script script/Deploy.s.sol:DeployAll \
  --rpc-url http://localhost:8545 \
  --private-key 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80 \
  -vvvv

# If clean, broadcast to local fork
forge script script/Deploy.s.sol:DeployAll \
  --rpc-url http://localhost:8545 \
  --private-key 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80 \
  --broadcast -vvvv
```

Save the output addresses — you'll need them for the bot.

### Step 5 — Run the bot against local fork

Create a `.env.local` (do NOT commit this):

```bash
ENVIRONMENT=mainnet
EXECUTION_MODE=mainnet
DRY_RUN=true

PRIVATE_KEY=0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
POLYGON_RPC_URL=http://localhost:8545

QUICKSWAP_ROUTER=0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff
SUSHISWAP_ROUTER=0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506
UNISWAP_V3_ROUTER=0xE592427A0AEce92De3Edee1F18E0157C05861564
UNISWAP_V3_FACTORY=0x1F98431c8aD98523631AE4a59f267346ea31F984
UNISWAP_V3_QUOTER=0x61fFE014bA17989E743c5F6cB21bF9697530B21e

FLASH_LOAN_ARBITRAGE_ADDRESS=<from deploy output>

MEV_PROTECTION_ENABLED=false
```

```bash
# Load local env and run bot in DRY_RUN mode
cp .env .env.backup && cp .env.local .env
python -m src.bot.main
# Watch logs — should see "Checking WETH/USDC..." every 5 seconds
# DRY_RUN=true means it simulates but never submits transactions
# Ctrl+C to stop, then restore: cp .env.backup .env
```

### Step 6 — Run the dry-run mainnet script

```bash
python scripts/dry_run_mainnet.py \
  --chain polygon \
  --rpc-url http://localhost:8545 \
  --duration 60 \
  --verbose
```

This scans for real arbitrage opportunities against forked state for 60 seconds.

---

## Phase 2: Testnet (Polygon Amoy)

### Step 1 — Get testnet funds

```bash
# Check your account address
python -c "
from eth_account import Account
import os
from dotenv import load_dotenv
load_dotenv()
acct = Account.from_key(os.getenv('PRIVATE_KEY'))
print(f'Address: {acct.address}')
"
```

Get Amoy MATIC from: `https://faucet.polygon.technology/` (select Amoy network)

### Step 2 — Configure `.env` for testnet

```bash
ENVIRONMENT=testnet
EXECUTION_MODE=testnet
DRY_RUN=true

POLYGON_AMOY_RPC_URL=https://polygon-amoy.g.alchemy.com/v2/YOUR_KEY
POLYGONSCAN_API_KEY=YOUR_KEY
```

### Step 3 — Run smoke test

```bash
python scripts/testnet_smoke_test.py --chain polygon_amoy
```

This checks: RPC connectivity, chain ID, account balance, config validation, module imports.

### Step 4 — Deploy contracts to Amoy

```bash
# Import your key into Foundry's encrypted keystore (safer than env var)
cast wallet import deployer --interactive

# Set Amoy-specific addresses
export AAVE_POOL_PROVIDER=0x...  # Aave V3 Amoy provider
export UNISWAP_V3_ROUTER=0x...  # V3 on Amoy (if deployed)
export V2_ROUTER=0x...           # QuickSwap on Amoy

# Deploy
forge script script/Deploy.s.sol:DeployAll \
  --rpc-url $POLYGON_AMOY_RPC_URL \
  --account deployer \
  --broadcast --verify -vvvv
```

### Step 5 — Run bot on testnet (DRY_RUN=true first)

```bash
python -m src.bot.main
# Monitor logs/bot.log for 24-48 hours
# Verify: opportunity detection works, no crashes, metrics export
```

### Step 6 — Switch to live execution on testnet

```bash
# In .env:
DRY_RUN=false
```

```bash
python -m src.bot.main
# Watch for actual transactions on Amoy explorer
# Verify: transactions submit, receipts come back, profit tracking works
```

---

## Phase 3: Mainnet (Real Money)

### Pre-flight checklist (all must be YES)

| Check | Command |
|-------|---------|
| All unit tests pass | `python -m pytest tests/ --no-cov` |
| All Solidity tests pass | `forge test --no-match-contract Fork` |
| Fork tests pass | `forge test --fork-url $POLYGON_RPC_URL` |
| Dry-run found opportunities | Check `dry_run_mainnet.py` output |
| Testnet ran 48h+ without crash | Check logs |
| Testnet executed trades | Check Amoy explorer |
| Config doctor passes | `python -m src.config doctor` |
| Multisig wallet set up | Gnosis Safe on Polygon |

### Step 1 — Configure mainnet `.env`

```bash
ENVIRONMENT=mainnet
EXECUTION_MODE=mainnet
DRY_RUN=true                          # Start with dry-run!

POLYGON_RPC_URL=https://polygon-mainnet.g.alchemy.com/v2/YOUR_KEY
POLYGON_RPC_URLS=url1,url2,url3       # For RPC failover

MEV_PROTECTION_ENABLED=true
FLASHBOTS_AUTH_KEY=0x...

TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...

# Conservative limits
MIN_PROFIT_USD=50
MAX_FLASH_LOAN_AMOUNT_USD=10000
MAX_SLIPPAGE_PERCENTAGE=1.0
```

### Step 2 — Deploy to mainnet

```bash
forge script script/Deploy.s.sol:DeployAll \
  --rpc-url $POLYGON_RPC_URL \
  --account deployer \
  --broadcast --verify -vvvv
```

### Step 3 — Dry-run on mainnet (reads only, no txs)

```bash
DRY_RUN=true python -m src.bot.main
# Monitor for 24 hours. Verify it finds real opportunities.
```

### Step 4 — Go live with conservative settings

```bash
DRY_RUN=false python -m src.bot.main
```

Monitor via Telegram alerts and `tail -f logs/bot.log`.

---

## Testing Progression Summary

```
Phase 0: Unit Tests          -> No network, mocked, fast (3 seconds)
Phase 1: Local Fork (Anvil)  -> Real state, no gas cost, instant blocks
Phase 2: Testnet (Amoy)      -> Real network, fake money, real latency
Phase 3: Mainnet DRY_RUN     -> Real network, real money, read-only
Phase 4: Mainnet LIVE        -> Full execution, start conservative
```

Each phase gates the next. Don't advance until the current phase runs clean for the minimum duration.

---

## Key Addresses Reference

### Polygon Mainnet

| Contract | Address |
|----------|---------|
| Aave V3 PoolAddressesProvider | `0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb` |
| Uniswap V3 SwapRouter | `0xE592427A0AEce92De3Edee1F18E0157C05861564` |
| Uniswap V3 QuoterV2 | `0x61fFE014bA17989E743c5F6cB21bF9697530B21e` |
| Uniswap V3 Factory | `0x1F98431c8aD98523631AE4a59f267346ea31F984` |
| QuickSwap V2 Router | `0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff` |
| SushiSwap Router | `0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506` |
| Balancer Vault | `0xBA12222222228d8Ba445958a75a0704d566BF2C8` |

### Token Addresses (Polygon Mainnet)

| Token | Address | Decimals |
|-------|---------|----------|
| WETH | `0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619` | 18 |
| USDC | `0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174` | 6 |
| USDT | `0xc2132D05D31c914a87C6611C10748AEb04B58e8F` | 6 |
| DAI | `0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063` | 18 |
