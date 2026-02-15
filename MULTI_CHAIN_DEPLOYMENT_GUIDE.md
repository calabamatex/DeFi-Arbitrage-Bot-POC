# Multi-Chain Deployment Guide
## Complete Implementation Requirements & Procedures

**Purpose**: Deploy Flash Loan Arbitrage Bot to multiple EVM chains
**Audience**: Technical implementer
**Prerequisites**: Working bot on Polygon (current status ✅)

---

## Table of Contents

1. [Pre-Deployment Requirements](#pre-deployment-requirements)
2. [Chain-Specific Information](#chain-specific-information)
3. [Implementation Checklist](#implementation-checklist)
4. [Step-by-Step Deployment](#step-by-step-deployment)
5. [Testing & Verification](#testing--verification)
6. [Multi-Chain Coordination](#multi-chain-coordination)
7. [Troubleshooting](#troubleshooting)

---

## Pre-Deployment Requirements

### 1. System Prerequisites ✅ CHECK BEFORE STARTING

#### Software Requirements

| Software | Version | Purpose | Status |
|----------|---------|---------|--------|
| Python | 3.8+ | Bot runtime | ✅ Have 3.14 |
| Node.js | 16+ | Optional tooling | Check |
| Foundry | Latest | Contract deployment | ✅ Have 1.5.1 |
| Git | Any | Version control | Check |
| PostgreSQL | 12+ | Database | ✅ Running |

**Verify installations**:
```bash
python --version        # Should be 3.8+
forge --version         # Should be installed
psql --version          # Should be 12+
```

#### Python Dependencies

**Already installed** (from current setup):
```bash
./venv/bin/pip list | grep -E "(web3|eth|dotenv|psycopg2)"
```

Should show:
- web3.py
- eth-account
- python-dotenv
- psycopg2-binary

---

### 2. Financial Requirements

#### Gas Tokens Needed (Per Chain)

| Chain | Token | Amount Needed | USD Cost | Purpose |
|-------|-------|---------------|----------|---------|
| Polygon | MATIC | 0 | $0 ✅ | Already have |
| Arbitrum | ETH | 0.01 | ~$30 | Deploy + 100 trades |
| Base | ETH | 0.01 | ~$30 | Deploy + 100 trades |
| Optimism | ETH | 0.01 | ~$30 | Deploy + 100 trades |
| BSC | BNB | 0.1 | ~$45 | Deploy + 300 trades |
| Avalanche | AVAX | 1.0 | ~$35 | Deploy + 200 trades |
| Polygon zkEVM | ETH | 0.01 | ~$30 | Deploy + 100 trades |

**Total for 6 new chains**: ~$200

#### Deployment Cost Breakdown (Per Chain)

```
Contract Deployment:
  FlashLoanArbitrageV2:    ~1,500,000 gas
  UniswapV3AdapterFixed:   ~300,000 gas
  UniswapV2Adapter:        ~900,000 gas
  Total:                   ~2,700,000 gas

Adapter Registration:
  setAdapter() calls (2x): ~100,000 gas
  Total:                   ~100,000 gas

Grand Total:               ~2,800,000 gas

Cost at 50 gwei:
  Arbitrum:  2.8M × 50 = 140M wei = 0.00014 ETH = $0.42
  Base:      Similar (L2 optimized)
  BSC:       Similar but in BNB

Actual cost with buffers:  $5-15 per chain
```

---

### 3. RPC Endpoints Required

#### Option A: Alchemy (Recommended)

**Why Alchemy**:
- ✅ Free tier available
- ✅ High reliability (99.9% uptime)
- ✅ Fast response times
- ✅ Good rate limits

**Setup**:
1. Go to https://www.alchemy.com/
2. Sign up (free)
3. Create apps for each chain:
   - Arbitrum Mainnet
   - Base Mainnet
   - Optimism Mainnet
   - Polygon zkEVM

**Free Tier Limits**:
- 300M compute units/month
- ~10M requests/month
- Sufficient for arbitrage bot

#### Option B: Public RPCs (Backup)

**Free but slower**:
```bash
# Arbitrum
https://arb1.arbitrum.io/rpc

# Base
https://mainnet.base.org

# Optimism
https://mainnet.optimism.io

# BSC
https://bsc-dataseed.binance.org/

# Avalanche
https://api.avax.network/ext/bc/C/rpc
```

**Drawbacks**:
- ❌ Rate limited
- ❌ Less reliable
- ❌ Slower response times
- ⚠️ Use only for testing

#### Recommended Setup

**Production**: Alchemy for all chains
**Development**: Public RPCs okay
**Cost**: $0/month on free tier

---

### 4. Wallet Setup

#### Master Deployment Wallet

**Current wallet**: `0xE05D16622CC5E54919248C97AF12Bf6C921269AC`
- ✅ Has 14.44 MATIC on Polygon
- ❌ Needs gas tokens on other chains

#### Getting Gas Tokens

**Method 1: Bridge from Polygon** (Recommended)
```
Use official bridges to move MATIC → other chains:
- Polygon → Arbitrum: https://bridge.arbitrum.io/
- Polygon → Base: https://bridge.base.org/
- Polygon → Optimism: https://app.optimism.io/bridge

Process:
1. Bridge MATIC to ETH on destination chain
2. Or swap MATIC for desired token first
3. Takes 10-30 minutes

Cost: ~$1-5 in bridge fees
```

**Method 2: Buy Directly on Exchange**
```
Exchanges supporting withdrawals to L2s:
- Coinbase → Base (native, $0 fees)
- Binance → Arbitrum, Optimism, BSC
- Kraken → Optimism, Arbitrum

Process:
1. Buy ETH/BNB/AVAX
2. Withdraw to destination chain
3. Use same wallet address

Cost: Exchange withdrawal fees ($1-10)
```

**Method 3: Buy Directly on L2** (Fastest)
```
Use on-ramp services:
- Ramp.network
- Transak
- MoonPay

Process:
1. Connect wallet to service
2. Buy directly on target chain
3. Receive in 5-10 minutes

Cost: 2-5% fee on purchase
```

---

## Chain-Specific Information

### Arbitrum Mainnet

**Network Details**:
```
Chain ID: 42161
Native Token: ETH
Block Time: ~0.25 seconds
Average Gas Price: 0.1-1 gwei
Type: Optimistic Rollup (L2)
```

**Key Addresses**:
```bash
# DEX Infrastructure
UNISWAP_V3_ROUTER=0xE592427A0AEce92De3Edee1F18E0157C05861564
UNISWAP_V3_QUOTER=0x61fFE014bA17989E743c5F6cB21bF9697530B21e
SUSHISWAP_ROUTER=0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506
CAMELOT_ROUTER=0xc873fEcbd354f5A56E00E710B90EF4201db2448d

# Flash Loan Provider
AAVE_POOL_PROVIDER=0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb
AAVE_POOL=0x794a61358D6845594F94dc1DB02A252b5b4814aD

# Major Tokens
USDC=0xaf88d065e77c8cC2239327C5EDb3A432268e5831  # Native USDC
USDC_E=0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8  # Bridged USDC.e
USDT=0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9
WETH=0x82aF49447D8a07e3bd95BD0d56f35241523fBab1
DAI=0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1
WBTC=0x2f2a2543B76A4166549F7aaB2e75Bef0aefC5B0f
ARB=0x912CE59144191C1204E64559FE8253a0e49E6548
```

**RPC Endpoints**:
```bash
# Alchemy (Recommended)
https://arb-mainnet.g.alchemy.com/v2/YOUR_KEY

# Public (Backup)
https://arb1.arbitrum.io/rpc
https://arbitrum.llamarpc.com
```

**Block Explorer**:
- https://arbiscan.io/

**Special Considerations**:
- Very fast blocks (~0.25s) - adjust CHECK_INTERVAL
- Low gas costs - can execute smaller profits
- High MEV competition - use private RPC
- USDC vs USDC.e - two versions exist, both liquid

**Recommended Pairs** (Arbitrum):
1. USDC/USDT (high frequency)
2. USDC/WETH
3. WETH/WBTC
4. USDC/ARB (native token)
5. DAI/USDC

---

### Base Mainnet (Coinbase L2)

**Network Details**:
```
Chain ID: 8453
Native Token: ETH
Block Time: ~2 seconds
Average Gas Price: 0.1-5 gwei
Type: Optimistic Rollup (L2)
```

**Key Addresses**:
```bash
# DEX Infrastructure
UNISWAP_V3_ROUTER=0x2626664c2603336E57B271c5C0b26F421741e481
UNISWAP_V3_QUOTER=0x3d4e44Eb1374240CE5F1B871ab261CD16335B76a
SUSHISWAP_ROUTER=0x6BDED42c6DA8FBf0d2bA55B2fa120C5e0c8D7891
AERODROME_ROUTER=0xcF77a3Ba9A5CA399B7c97c74d54e5b1Beb874E43  # Base-native

# Flash Loan Provider
AAVE_POOL_PROVIDER=0xe20fCBdBfFC4Dd138cE8b2E6FBb6CB49777ad64D
AAVE_POOL=0xA238Dd80C259a72e81d7e4664a9801593F98d1c5

# Major Tokens
USDC=0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913  # Native USDC
WETH=0x4200000000000000000000000000000000000006
DAI=0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb
CBETH=0x2Ae3F1Ec7F1F5012CFEab0185bfc7aa3cf0DEc22  # Coinbase wrapped ETH
```

**RPC Endpoints**:
```bash
# Alchemy (Recommended)
https://base-mainnet.g.alchemy.com/v2/YOUR_KEY

# Public (Backup)
https://mainnet.base.org
https://base.llamarpc.com
```

**Block Explorer**:
- https://basescan.org/

**Special Considerations**:
- Coinbase native chain - good liquidity
- Growing ecosystem - less competition
- Lower MEV than Ethereum mainnet
- Aerodrome DEX is dominant on Base

**Recommended Pairs** (Base):
1. USDC/WETH
2. WETH/CBETH (Coinbase staked ETH)
3. USDC/DAI
4. WETH/DAI

---

### Optimism Mainnet

**Network Details**:
```
Chain ID: 10
Native Token: ETH
Block Time: ~2 seconds
Average Gas Price: 0.1-2 gwei
Type: Optimistic Rollup (L2)
```

**Key Addresses**:
```bash
# DEX Infrastructure
UNISWAP_V3_ROUTER=0xE592427A0AEce92De3Edee1F18E0157C05861564
UNISWAP_V3_QUOTER=0x61fFE014bA17989E743c5F6cB21bF9697530B21e
SUSHISWAP_ROUTER=0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506
VELODROME_ROUTER=0x9c12939390052919aF3155f41Bf4160Fd3666A6f  # OP-native

# Flash Loan Provider
AAVE_POOL_PROVIDER=0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb
AAVE_POOL=0x794a61358D6845594F94dc1DB02A252b5b4814aD

# Major Tokens
USDC=0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85  # Native USDC
USDC_E=0x7F5c764cBc14f9669B88837ca1490cCa17c31607  # Bridged USDC.e
USDT=0x94b008aA00579c1307B0EF2c499aD98a8ce58e58
WETH=0x4200000000000000000000000000000000000006
DAI=0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1
WBTC=0x68f180fcCe6836688e9084f035309E29Bf0A2095
OP=0x4200000000000000000000000000000000000042  # Native token
```

**RPC Endpoints**:
```bash
# Alchemy (Recommended)
https://opt-mainnet.g.alchemy.com/v2/YOUR_KEY

# Public (Backup)
https://mainnet.optimism.io
https://optimism.llamarpc.com
```

**Block Explorer**:
- https://optimistic.etherscan.io/

**Special Considerations**:
- Similar to Arbitrum architecture
- Velodrome is major DEX (AMM + ve(3,3) model)
- USDC vs USDC.e like Arbitrum
- Good for stablecoin arbitrage

**Recommended Pairs** (Optimism):
1. USDC/USDT
2. USDC/WETH
3. WETH/WBTC
4. USDC/OP (native token)
5. DAI/USDC

---

### BSC (Binance Smart Chain)

**Network Details**:
```
Chain ID: 56
Native Token: BNB
Block Time: ~3 seconds
Average Gas Price: 3-10 gwei
Type: PoS Sidechain
```

**Key Addresses**:
```bash
# DEX Infrastructure
PANCAKESWAP_V3_ROUTER=0x1b81D678ffb9C0263b24A97847620C99d213eB14
PANCAKESWAP_V2_ROUTER=0x10ED43C718714eb63d5aA57B78B54704E256024E
BISWAP_ROUTER=0x3a6d8cA21D1CF76F653A67577FA0D27453350dD8
SUSHISWAP_ROUTER=0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506

# Flash Loan Provider (Different!)
PANCAKESWAP_FLASH_LOAN=0x1b81D678ffb9C0263b24A97847620C99d213eB14
# Note: BSC doesn't have Aave V3, use PancakeSwap flash loans

# Major Tokens
USDT=0x55d398326f99059fF775485246999027B3197955  # Most liquid
USDC=0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d
WBNB=0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c
BUSD=0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56  # Binance USD
ETH=0x2170Ed0880ac9A755fd29B2688956BD959F933F8  # Wrapped ETH
BTCB=0x7130d2A12B9BCbFAe4f2634d864A1Ee1Ce3Ead9c  # Bitcoin BEP20
CAKE=0x0E09FaBB73Bd3Ade0a17ECC321fD13a19e81cE82  # PancakeSwap token
```

**RPC Endpoints**:
```bash
# Binance Official (Recommended)
https://bsc-dataseed1.binance.org/
https://bsc-dataseed2.binance.org/

# Public (Backup)
https://bsc.publicnode.com
https://bsc.rpc.blxrbdn.com
```

**Block Explorer**:
- https://bscscan.com/

**Special Considerations**:
- ⚠️ **NO AAVE V3** - Must use PancakeSwap flash loans
- Requires modified FlashLoanArbitrage contract
- Higher gas costs than L2s
- Very high trading volume
- USDT is more liquid than USDC on BSC

**Recommended Pairs** (BSC):
1. USDT/USDC (good volume)
2. USDT/BUSD
3. WBNB/USDT
4. WBNB/ETH
5. BTCB/WBNB

**⚠️ DEPLOYMENT WARNING**:
BSC requires **custom flash loan implementation** because it doesn't have Aave V3. Options:
1. Use PancakeSwap flash loans (different interface)
2. Deploy Aave-compatible fork
3. Skip BSC for now (recommended until modified)

---

### Avalanche C-Chain

**Network Details**:
```
Chain ID: 43114
Native Token: AVAX
Block Time: ~2 seconds
Average Gas Price: 25-100 nAVAX
Type: Proof of Stake
```

**Key Addresses**:
```bash
# DEX Infrastructure
TRADERJOE_V2_ROUTER=0xb4315e873dBcf96Ffd0acd8EA43f689D8c20fB30
TRADERJOE_V1_ROUTER=0x60aE616a2155Ee3d9A68541Ba4544862310933d4
PANGOLIN_ROUTER=0xE54Ca86531e17Ef3616d22Ca28b0D458b6C89106
SUSHISWAP_ROUTER=0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506

# Flash Loan Provider
AAVE_POOL_PROVIDER=0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb
AAVE_POOL=0x794a61358D6845594F94dc1DB02A252b5b4814aD

# Major Tokens
USDC=0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E  # Native USDC
USDC_E=0xA7D7079b0FEaD91F3e65f86E8915Cb59c1a4C664  # Bridged USDC.e
USDT=0x9702230A8Ea53601f5cD2dc00fDBc13d4dF4A8c7  # Tether USD
USDT_E=0xc7198437980c041c805A1EDcbA50c1Ce5db95118  # Bridged USDT.e
WAVAX=0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7
WETH_E=0x49D5c2BdFfac6CE2BFdB6640F4F80f226bc10bAB
WBTC_E=0x50b7545627a5162F82A992c33b87aDc75187B218
JOE=0x6e84a6216eA6dACC71eE8E6b0a5B7322EEbC0fDd  # TraderJoe token
```

**RPC Endpoints**:
```bash
# Avalanche Official (Recommended)
https://api.avax.network/ext/bc/C/rpc

# Public (Backup)
https://avalanche.public-rpc.com
https://avax.meowrpc.com
```

**Block Explorer**:
- https://snowtrace.io/

**Special Considerations**:
- Fast blocks (~2s)
- Native DEXs: TraderJoe, Pangolin
- Many tokens have ".e" (bridged) versions
- Good DeFi ecosystem
- Lower competition than Ethereum

**Recommended Pairs** (Avalanche):
1. USDC/USDT (or .e versions)
2. WAVAX/USDC
3. WAVAX/USDT
4. WETH.e/WAVAX
5. USDC/USDC.e (native vs bridged arb!)

---

### Polygon zkEVM

**Network Details**:
```
Chain ID: 1101
Native Token: ETH
Block Time: ~5-10 seconds
Average Gas Price: 1-10 gwei
Type: zkRollup (L2)
```

**Key Addresses**:
```bash
# DEX Infrastructure
QUICKSWAP_V3_ROUTER=0xF6Ad3CcF71Abb3E12beCf6b3D2a74C963859ADCd
PANCAKESWAP_V3_ROUTER=0x1b81D678ffb9C0263b24A97847620C99d213eB14
SUSHISWAP_ROUTER=0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506

# Flash Loan Provider
# ⚠️ No Aave V3 yet on Polygon zkEVM
# Use DEX-based flash loans or skip for now

# Major Tokens
USDC=0xA8CE8aee21bC2A48a5EF670afCc9274C7bbbC035
USDT=0x1E4a5963aBFD975d8c9021ce480b42188849D41d
WETH=0x4F9A0e7FD2Bf6067db6994CF12E4495Df938E6e9
MATIC=0xa2036f0538221a77A3937F1379699f44945018d0
```

**RPC Endpoints**:
```bash
# Polygon Official (Recommended)
https://zkevm-rpc.com

# Public (Backup)
https://polygon-zkevm.publicnode.com
```

**Block Explorer**:
- https://zkevm.polygonscan.com/

**Special Considerations**:
- ⚠️ **NEW CHAIN** - Less mature
- ⚠️ **NO AAVE V3 YET** - Limited flash loan options
- zkRollup technology - very low costs
- Growing ecosystem
- Less competition (opportunity!)

**⚠️ DEPLOYMENT WARNING**:
Polygon zkEVM lacks Aave V3. Options:
1. Wait for Aave deployment
2. Use QuickSwap flash swaps
3. Deploy custom flash loan pool
4. **Recommended**: Skip for now, revisit in 3-6 months

---

## Implementation Checklist

### Before Starting Any Chain

- [ ] RPC endpoint obtained and tested
- [ ] Gas tokens acquired (0.01+ ETH or equivalent)
- [ ] Wallet has sufficient balance for deployment
- [ ] DEX addresses researched and verified
- [ ] Token addresses researched and verified
- [ ] Block explorer bookmarked
- [ ] Test RPC connection with simple query

### Per Chain Deployment

- [ ] Create chain-specific .env file
- [ ] Deploy FlashLoanArbitrageV2 contract
- [ ] Deploy UniswapV3AdapterFixed (or V3 equivalent)
- [ ] Deploy UniswapV2Adapter (or V2 equivalent)
- [ ] Register adapters with main contract
- [ ] Verify contracts on block explorer
- [ ] Add token addresses to configuration
- [ ] Add trading pairs to configuration
- [ ] Test opportunity detection (dry run)
- [ ] Execute test arbitrage (if opportunity exists)
- [ ] Monitor for 24 hours
- [ ] Document contract addresses

### Post-Deployment

- [ ] Update master deployment tracking file
- [ ] Add chain to multi-chain coordinator
- [ ] Set up monitoring/alerts for chain
- [ ] Refill gas if needed
- [ ] Review logs daily for first week

---

## Step-by-Step Deployment

### Phase 1: Preparation (Before Deployment)

#### Step 1.1: Research Chain

**Time**: 30 minutes per chain

1. **Confirm chain specifications**:
```bash
# Check chain is EVM compatible
# Verify chain ID
# Confirm block time
# Note average gas price
```

2. **Find DEX addresses**:
```bash
# Primary: Uniswap V3 (if available)
# Secondary: Major V2 fork (SushiSwap, etc.)
# Tertiary: Native DEX
```

3. **Find token addresses**:
```bash
# USDC (native if exists)
# USDT
# WETH or native wrapped ETH
# DAI
# Major tokens (WBTC, etc.)
```

4. **Find Aave V3 addresses** (if available):
```bash
# AAVE_POOL_PROVIDER
# AAVE_POOL
```

**Document findings** in a chain-specific file:
```bash
# Create research file
touch docs/chains/arbitrum_research.md

# Document:
# - Chain ID
# - RPC endpoints
# - DEX addresses
# - Token addresses
# - Flash loan provider
# - Special considerations
```

#### Step 1.2: Get Gas Tokens

**Time**: 15-60 minutes (depending on method)

**Method A: Bridge from Polygon**
```bash
# Go to official bridge
# Example: Arbitrum
https://bridge.arbitrum.io/

Steps:
1. Connect wallet
2. Select: Polygon → Arbitrum
3. Amount: 0.02 ETH equivalent in MATIC
4. Approve transaction
5. Wait 10-30 minutes
6. Verify receipt on destination
```

**Method B: Exchange Withdrawal**
```bash
# Binance, Coinbase, etc.

Steps:
1. Buy target token (ETH, BNB, AVAX)
2. Navigate to withdrawal
3. Select network (e.g., Arbitrum for ETH)
4. Enter wallet address
5. Amount: 0.01-0.02 ETH
6. Confirm withdrawal
7. Wait 5-30 minutes
```

**Verify receipt**:
```bash
# Check balance on block explorer
# Or use script:
./check_balance_multichain.sh <chain_name>
```

#### Step 1.3: Setup RPC Endpoint

**Time**: 10 minutes

**Alchemy Setup** (Recommended):
```bash
1. Login to https://dashboard.alchemy.com/
2. Click "Create App"
3. Select chain (e.g., Arbitrum Mainnet)
4. Name: "FlashArb-Arbitrum"
5. Copy API key
6. Construct endpoint:
   https://arb-mainnet.g.alchemy.com/v2/YOUR_KEY
```

**Test RPC**:
```bash
# Create test script
cat > test_rpc.py << 'EOF'
from web3 import Web3

rpc = "https://arb-mainnet.g.alchemy.com/v2/YOUR_KEY"
web3 = Web3(Web3.HTTPProvider(rpc))

print(f"Connected: {web3.is_connected()}")
print(f"Chain ID: {web3.eth.chain_id}")
print(f"Block number: {web3.eth.block_number}")
EOF

python test_rpc.py
```

Expected output:
```
Connected: True
Chain ID: 42161
Block number: 178234567
```

---

### Phase 2: Contract Deployment

#### Step 2.1: Create Chain-Specific Configuration

**Time**: 10 minutes

```bash
# Copy template
cp .env .env.arbitrum

# Edit for Arbitrum
vim .env.arbitrum
```

**Configure** `.env.arbitrum`:
```bash
# Network
POLYGON_RPC_URL=https://arb-mainnet.g.alchemy.com/v2/YOUR_KEY
ALCHEMY_POLYGON_RPC_URL=https://arb-mainnet.g.alchemy.com/v2/YOUR_KEY
CHAIN_ID=42161
CHAIN_NAME=arbitrum

# Wallet (same key, different chain)
PRIVATE_KEY=your_private_key_here

# Execution Mode
DRY_RUN=true
DIRECT_EXECUTION=false
MIN_PROFIT_USD=3.00  # Lower on L2s (cheaper gas)
MAX_GAS_PRICE_GWEI=10  # L2 gas is cheap
CHECK_INTERVAL=5  # Faster blocks

# Flash Loan Optimization
MIN_FLASH_LOAN_USD=500
MAX_FLASH_LOAN_USD=100000

# DEX Addresses (Arbitrum)
UNISWAP_V3_FACTORY=0x1F98431c8aD98523631AE4a59f267346ea31F984
UNISWAP_V3_QUOTER_V2=0x61fFE014bA17989E743c5F6cB21bF9697530B21e
UNISWAP_V3_ROUTER=0xE592427A0AEce92De3Edee1F18E0157C05861564

SUSHISWAP_ROUTER=0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506
SUSHISWAP_FACTORY=0xc35DADB65012eC5796536bD9864eD8773aBc74C4

# Aave V3 (Arbitrum)
AAVE_POOL_ADDRESS_PROVIDER=0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb
AAVE_POOL=0x794a61358D6845594F94dc1DB02A252b5b4814aD

# Token Addresses (Arbitrum)
USDC_ADDRESS=0xaf88d065e77c8cC2239327C5EDb3A432268e5831
WMATIC_ADDRESS=0x0000000000000000000000000000000000000000  # No MATIC on Arbitrum
WETH_ADDRESS=0x82aF49447D8a07e3bd95BD0d56f35241523fBab1
DAI_ADDRESS=0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1
USDT_ADDRESS=0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9
WBTC_ADDRESS=0x2f2a2543B76A4166549F7aaB2e75Bef0aefC5B0f

# Contract Addresses (to be filled after deployment)
FLASH_LOAN_ARBITRAGE_ADDRESS=
UNISWAP_V3_ADAPTER_ADDRESS=
UNISWAP_V2_ADAPTER_ADDRESS=

# Database (shared across chains)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=arbitrage_bot
DB_USER=arbitrage_user
DB_PASSWORD=secure_password_123
```

#### Step 2.2: Deploy Contracts

**Time**: 10-20 minutes

**Option A: Use Existing Python Script** (Recommended)
```bash
# Load chain-specific config
export $(cat .env.arbitrum | xargs)

# Deploy
./venv/bin/python deploy_contracts.py
```

**Option B: Manual Deployment with Forge**
```bash
# Load config
source .env.arbitrum

# Deploy V3 Adapter
forge create contracts/adapters/UniswapV3AdapterFixed.sol:UniswapV3AdapterFixed \
    --rpc-url $POLYGON_RPC_URL \
    --private-key $PRIVATE_KEY \
    --constructor-args $UNISWAP_V3_ROUTER

# Save address
V3_ADAPTER=0x... # from output

# Deploy V2 Adapter
forge create contracts/adapters/UniswapV2Adapter.sol:UniswapV2Adapter \
    --rpc-url $POLYGON_RPC_URL \
    --private-key $PRIVATE_KEY \
    --constructor-args $SUSHISWAP_ROUTER "SushiSwap"

# Save address
V2_ADAPTER=0x... # from output

# Deploy Main Contract
forge create contracts/FlashLoanArbitrageV2.sol:FlashLoanArbitrageV2 \
    --rpc-url $POLYGON_RPC_URL \
    --private-key $PRIVATE_KEY \
    --constructor-args $AAVE_POOL_ADDRESS_PROVIDER 100000 500

# Save address
FLASH_LOAN=0x... # from output
```

**Expected Output**:
```
================================================================================
🚀 DEPLOYING TO ARBITRUM MAINNET
================================================================================

⚠️  WARNING: This will deploy to REAL Arbitrum mainnet
⚠️  Real ETH will be spent on gas (~$5-15)

Are you sure? (yes/no): yes

Network: Arbitrum Mainnet (Chain ID: 42161)
Deployer: 0xE05D16622CC5E54919248C97AF12Bf6C921269AC
Balance: 0.01 ETH

================================================================================
Deploying UniswapV3AdapterFixed...
================================================================================
  Gas estimate: 300000
  Gas price: 0.5 gwei

  TX Hash: 0x...
  Waiting for confirmation...
✅ UniswapV3AdapterFixed: 0xABC...
  Gas used: 297778
  Block: 178234567

================================================================================
Deploying UniswapV2Adapter...
================================================================================
...
✅ UniswapV2Adapter: 0xDEF...

================================================================================
Deploying FlashLoanArbitrageV2...
================================================================================
...
✅ FlashLoanArbitrageV2: 0xGHI...

================================================================================
Registering Adapters...
================================================================================
Registering V3 Adapter...
✅ V3 Adapter registered

Registering V2 Adapter...
✅ V2 Adapter registered

================================================================================
✅ DEPLOYMENT COMPLETE!
================================================================================

Deployed Contracts:
  FlashLoanArbitrageV2:   0xGHI...
  UniswapV3AdapterFixed:  0xABC...
  UniswapV2Adapter:       0xDEF...

View on Arbiscan:
  https://arbiscan.io/address/0xGHI...
```

#### Step 2.3: Verify Contracts on Block Explorer

**Time**: 10 minutes

**Why verify?**:
- Transparency
- Allows interaction via UI
- Shows source code publicly
- Required for some tools

**Using Foundry** (Easiest):
```bash
# Verify main contract
forge verify-contract \
    --chain-id 42161 \
    --constructor-args $(cast abi-encode "constructor(address,uint256,uint256)" \
        0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb 100000 500) \
    --watch \
    0xGHI... \  # Contract address
    contracts/FlashLoanArbitrageV2.sol:FlashLoanArbitrageV2 \
    YOUR_ARBISCAN_API_KEY

# Repeat for adapters
```

**Manual verification** (if forge fails):
1. Go to block explorer (e.g., arbiscan.io)
2. Find contract address
3. Click "Contract" → "Verify and Publish"
4. Select compiler version (0.8.20)
5. Paste source code
6. Submit

#### Step 2.4: Document Deployment

**Time**: 5 minutes

```bash
# Create deployment record
cat > deployments/arbitrum_mainnet.json << EOF
{
  "network": "Arbitrum Mainnet",
  "chainId": 42161,
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "deployer": "0xE05D16622CC5E54919248C97AF12Bf6C921269AC",
  "gasSpent": "0.004 ETH",
  "contracts": {
    "FlashLoanArbitrageV2": "0xGHI...",
    "UniswapV3AdapterFixed": "0xABC...",
    "UniswapV2Adapter": "0xDEF..."
  },
  "explorer": {
    "FlashLoanArbitrageV2": "https://arbiscan.io/address/0xGHI...",
    "UniswapV3AdapterFixed": "https://arbiscan.io/address/0xABC...",
    "UniswapV2Adapter": "https://arbiscan.io/address/0xDEF..."
  }
}
EOF
```

**Update master tracking**:
```bash
# Add to deployments/README.md
echo "## Arbitrum Mainnet" >> deployments/README.md
echo "- Deployed: $(date)" >> deployments/README.md
echo "- Main Contract: 0xGHI..." >> deployments/README.md
echo "- Status: Active" >> deployments/README.md
```

---

### Phase 3: Configuration & Testing

#### Step 3.1: Update Bot Configuration

**Time**: 10 minutes

**Update .env.arbitrum with deployed addresses**:
```bash
# Fill in deployed addresses
sed -i '' "s/FLASH_LOAN_ARBITRAGE_ADDRESS=/FLASH_LOAN_ARBITRAGE_ADDRESS=0xGHI.../" .env.arbitrum
sed -i '' "s/UNISWAP_V3_ADAPTER_ADDRESS=/UNISWAP_V3_ADAPTER_ADDRESS=0xABC.../" .env.arbitrum
sed -i '' "s/UNISWAP_V2_ADAPTER_ADDRESS=/UNISWAP_V2_ADAPTER_ADDRESS=0xDEF.../" .env.arbitrum
```

**Add trading pairs**:
```python
# Edit run_bot.py or create chain-specific config
ARBITRUM_PAIRS = [
    ('USDC', 'USDT'),
    ('USDC', 'WETH'),
    ('WETH', 'WBTC'),
    ('USDC', 'DAI'),
    ('WETH', 'DAI'),
]
```

#### Step 3.2: Test Connection

**Time**: 5 minutes

```bash
# Create test script
cat > test_arbitrum_connection.py << 'EOF'
from web3 import Web3
from dotenv import load_dotenv
import os

# Load Arbitrum config
load_dotenv('.env.arbitrum')

web3 = Web3(Web3.HTTPProvider(os.getenv('POLYGON_RPC_URL')))

print("="*60)
print("Arbitrum Connection Test")
print("="*60)
print(f"Connected: {web3.is_connected()}")
print(f"Chain ID: {web3.eth.chain_id}")
print(f"Block number: {web3.eth.block_number}")
print(f"Gas price: {web3.from_wei(web3.eth.gas_price, 'gwei')} gwei")

# Test contract deployed
contract_addr = os.getenv('FLASH_LOAN_ARBITRAGE_ADDRESS')
code = web3.eth.get_code(contract_addr)
print(f"Contract deployed: {len(code) > 0}")
print(f"Contract address: {contract_addr}")
print("="*60)
EOF

python test_arbitrum_connection.py
```

**Expected output**:
```
============================================================
Arbitrum Connection Test
============================================================
Connected: True
Chain ID: 42161
Block number: 178234999
Gas price: 0.1 gwei
Contract deployed: True
Contract address: 0xGHI...
============================================================
```

#### Step 3.3: Test Opportunity Detection

**Time**: 10-30 minutes

```bash
# Run bot in test mode for one scan
python run_bot.py --config .env.arbitrum --test-mode --single-scan
```

**Watch logs**:
```bash
tail -f bot_arbitrum.log
```

**Expected log output**:
```
2026-01-22 14:30:00 - INFO - OpportunityDetector initialized
2026-01-22 14:30:00 - INFO - Monitoring 5 pairs on Arbitrum
2026-01-22 14:30:00 - INFO - 🔍 Scanning 5 pairs with flash loan optimization...
2026-01-22 14:30:05 - INFO - Tested USDC/USDT: No opportunity
2026-01-22 14:30:07 - INFO - Tested USDC/WETH: No opportunity
2026-01-22 14:30:09 - INFO - Tested WETH/WBTC: No opportunity
2026-01-22 14:30:11 - INFO - Tested USDC/DAI: No opportunity
2026-01-22 14:30:13 - INFO - Tested WETH/DAI: No opportunity
2026-01-22 14:30:13 - INFO - Scan complete. Found 0 opportunities
```

**If opportunity found**:
```
2026-01-22 14:30:05 - INFO - Tested USDC/USDT: No opportunity
2026-01-22 14:30:07 - INFO - 💰 Found V3→V2 opportunity for USDC↔WETH, optimizing...
2026-01-22 14:30:07 - INFO - 🔍 Optimizing flash loan amount for V3→V2...
2026-01-22 14:30:07 - INFO -   Testing 9 amounts from $500 to $100,000
2026-01-22 14:30:08 - INFO -   $500 → $0.15 profit
2026-01-22 14:30:08 - INFO -   $1,000 → $0.32 profit
2026-01-22 14:30:09 - INFO -   $2,000 → $0.68 profit
2026-01-22 14:30:09 - INFO -   $4,000 → $1.42 profit
2026-01-22 14:30:10 - INFO -   $8,000 → $3.15 profit
2026-01-22 14:30:11 - INFO -   Slippage increasing, optimal amount found
2026-01-22 14:30:11 - INFO - ✅ Optimal: $8,000 flash loan → $3.15 profit
2026-01-22 14:30:11 - INFO - ✅ Opportunity logged: V3→V2 | Net profit: 3.150000 tokens
```

#### Step 3.4: Launch for Continuous Operation

**Time**: 5 minutes

```bash
# Run in background
nohup python run_bot.py --config .env.arbitrum > arbitrum_bot.log 2>&1 &

# Save PID
echo $! > arbitrum_bot.pid

# Monitor
tail -f arbitrum_bot.log
```

---

### Phase 4: Multi-Chain Coordination

After deploying to 2+ chains, set up multi-chain coordinator.

**Create multi_chain_coordinator.py**:
```python
#!/usr/bin/env python3
"""
Multi-Chain Flash Loan Arbitrage Coordinator

Runs separate bot instances for each chain in parallel.
"""
import os
import threading
import logging
from dotenv import load_dotenv

# Configuration for each chain
CHAINS = {
    'polygon': {
        'config_file': '.env',
        'log_file': 'bot_polygon.log',
        'pid_file': 'polygon_bot.pid'
    },
    'arbitrum': {
        'config_file': '.env.arbitrum',
        'log_file': 'bot_arbitrum.log',
        'pid_file': 'arbitrum_bot.pid'
    },
    'base': {
        'config_file': '.env.base',
        'log_file': 'bot_base.log',
        'pid_file': 'base_bot.pid'
    },
    # Add more chains as deployed
}

def run_chain_bot(chain_name, config):
    """Run bot for a specific chain."""
    logger = logging.getLogger(f"coordinator.{chain_name}")
    logger.info(f"Starting {chain_name} bot...")

    # Load chain config
    load_dotenv(config['config_file'])

    # Import and run bot
    from run_bot import main as run_bot_main
    run_bot_main()

def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    logger = logging.getLogger("coordinator")
    logger.info("="*60)
    logger.info("Multi-Chain Arbitrage Coordinator Starting")
    logger.info("="*60)

    threads = []

    for chain_name, config in CHAINS.items():
        # Check if config exists
        if not os.path.exists(config['config_file']):
            logger.warning(f"Skipping {chain_name}: Config file not found")
            continue

        logger.info(f"Launching {chain_name} bot...")
        thread = threading.Thread(
            target=run_chain_bot,
            args=(chain_name, config),
            name=f"bot-{chain_name}"
        )
        thread.daemon = False
        thread.start()
        threads.append(thread)

    logger.info(f"All bots launched ({len(threads)} chains active)")
    logger.info("Press Ctrl+C to stop all bots")

    try:
        for thread in threads:
            thread.join()
    except KeyboardInterrupt:
        logger.info("Shutting down all bots...")

if __name__ == "__main__":
    main()
```

**Run coordinator**:
```bash
chmod +x multi_chain_coordinator.py
./multi_chain_coordinator.py
```

---

## Testing & Verification

### Verification Checklist

After deploying each chain:

**Smart Contracts**:
- [ ] All 3 contracts deployed successfully
- [ ] Contracts verified on block explorer
- [ ] Adapters registered with main contract
- [ ] Owner is correct deployer address

**Configuration**:
- [ ] RPC endpoint working
- [ ] Token addresses correct for chain
- [ ] DEX addresses correct for chain
- [ ] Trading pairs configured
- [ ] Gas price limits appropriate for chain

**Bot Operation**:
- [ ] Bot connects to RPC
- [ ] Bot reads deployed contracts
- [ ] Opportunity detection runs without errors
- [ ] Logs show scanning activity
- [ ] Database records opportunities (if found)

**Monitoring**:
- [ ] Logs being written
- [ ] PID file created
- [ ] Process running in background
- [ ] No error messages in logs

### Test Scenarios

#### Scenario 1: Dry Run Test
```bash
# Purpose: Verify bot can scan without executing
# Duration: 5 minutes
# Expected: Bot scans, finds 0 or more opportunities, no execution

DRY_RUN=true python run_bot.py --config .env.arbitrum --duration 300
```

#### Scenario 2: Single Opportunity Test
```bash
# Purpose: Test full execution flow
# Duration: Until one opportunity found
# Expected: Bot finds opportunity, logs details, executes (dry run)

python run_bot.py --config .env.arbitrum --stop-after-first
```

#### Scenario 3: 24 Hour Observation
```bash
# Purpose: Validate opportunity frequency
# Duration: 24 hours
# Expected: Multiple scans, 0-5 opportunities logged

nohup python run_bot.py --config .env.arbitrum > arbitrum_24h.log 2>&1 &
```

#### Scenario 4: Real Execution Test (⚠️ Use Caution)
```bash
# Purpose: Test actual transaction execution
# Prerequisites: Opportunity must exist, sufficient gas
# Expected: Transaction submitted and confirmed

# ONLY after extensive dry run testing
DRY_RUN=false python run_bot.py --config .env.arbitrum --stop-after-first
```

---

## Troubleshooting

### Common Issues & Solutions

#### Issue: "Failed to connect to RPC"

**Symptoms**:
```
Error: Failed to connect to blockchain
HTTPConnectionPool: Max retries exceeded
```

**Causes**:
- Invalid RPC URL
- API key incorrect
- Network firewall blocking
- RPC provider down

**Solutions**:
```bash
# Test RPC manually
curl -X POST https://arb-mainnet.g.alchemy.com/v2/YOUR_KEY \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'

# Try alternative RPC
# Edit .env: use public RPC temporarily

# Check firewall
ping arb-mainnet.g.alchemy.com
```

---

#### Issue: "Insufficient funds for gas"

**Symptoms**:
```
Error: insufficient funds for gas * price + value
```

**Causes**:
- Not enough ETH/BNB/AVAX for gas
- Wrong network selected
- Gas price spike

**Solutions**:
```bash
# Check balance
./check_balance_multichain.sh arbitrum

# If low, bridge more tokens
# Or reduce gas limit in config

# Temporary: increase gas buffer
MAX_GAS_PRICE_GWEI=50  # was 10
```

---

#### Issue: "Contract deployment failed"

**Symptoms**:
```
Error: Transaction reverted
Contract: 0x0000...0000
```

**Causes**:
- Constructor arguments incorrect
- Compiler version mismatch
- Dependencies not installed
- Network congestion

**Solutions**:
```bash
# Verify constructor args
# Check target addresses exist
cast call 0xAAVE_POOL_PROVIDER "owner()" --rpc-url $RPC

# Try with more gas
forge create --gas-limit 5000000 ...

# Check compiler version matches
solc --version  # Should be 0.8.20
```

---

#### Issue: "No opportunities found"

**Symptoms**:
```
Scan complete. Found 0 opportunities
(for hours/days)
```

**Causes**:
- Efficient markets (normal!)
- MIN_PROFIT too high
- Wrong trading pairs
- Low volatility period

**Solutions**:
```bash
# This is normal - wait longer
# Or lower MIN_PROFIT
MIN_PROFIT_USD=2.00  # was 5.00

# Add more pairs
# Check high-volume pairs on DEX analytics

# Wait for volatile market conditions
```

---

#### Issue: "Opportunity detected but not profitable after gas"

**Symptoms**:
```
Found opportunity: $2.50 profit
Gas cost estimate: $3.20
Skipping: Not profitable after gas
```

**Causes**:
- Gas price too high
- Small opportunity
- Gas estimate too conservative

**Solutions**:
```bash
# Lower MIN_PROFIT
MIN_PROFIT_USD=1.00

# Adjust gas estimate
# In opportunity_detector.py:
estimated_gas = 400000  # was 500000

# Wait for lower gas prices
# Or focus on larger opportunities
```

---

#### Issue: "Transaction failed: Slippage too high"

**Symptoms**:
```
Error: execution reverted: Slippage check failed
```

**Causes**:
- Price moved between detection and execution
- Liquidity dried up
- MEV bot frontran
- maxSlippageBps too tight

**Solutions**:
```bash
# Increase slippage tolerance (carefully)
# In contract constructor:
maxSlippageBps: 500  # was 300 (5% vs 3%)

# Execute faster (reduce latency)
# Use private RPC (Flashbots)
# Accept that some trades will fail
```

---

### Debugging Tools

#### Check Contract State
```bash
# Is contract deployed?
cast code $CONTRACT_ADDRESS --rpc-url $RPC

# Is owner correct?
cast call $CONTRACT_ADDRESS "owner()" --rpc-url $RPC

# Are adapters registered?
cast call $CONTRACT_ADDRESS "adapters(address)(bool)" $ADAPTER_ADDRESS --rpc-url $RPC
```

#### Check Token Approvals
```bash
# Does contract have approval?
cast call $USDC_ADDRESS "allowance(address,address)(uint256)" \
  $OWNER_ADDRESS $CONTRACT_ADDRESS --rpc-url $RPC
```

#### Simulate Transaction
```bash
# Test transaction without executing
cast call $CONTRACT_ADDRESS "executeArbitrage((bytes32[],uint256,address,uint256,uint256))" \
  "($PARAMS)" --from $OWNER_ADDRESS --rpc-url $RPC
```

#### Monitor Gas Prices
```bash
# Current gas price
cast gas-price --rpc-url $RPC

# Convert to gwei
cast to-unit $(cast gas-price --rpc-url $RPC) gwei
```

---

## Next Steps After Deployment

### Immediate (Day 1)
1. Monitor logs continuously
2. Verify no errors
3. Confirm opportunity scanning working
4. Check database for logged opportunities

### Short-term (Week 1)
1. Analyze opportunity frequency
2. Adjust MIN_PROFIT if needed
3. Add more trading pairs
4. Optimize gas settings

### Medium-term (Month 1)
1. Deploy to additional chains
2. Add more DEXs per chain
3. Implement triangular arbitrage
4. Add liquidation monitoring

### Long-term (Quarter 1)
1. Scale to 10+ chains
2. Implement advanced MEV strategies
3. Add cross-chain arbitrage
4. Optimize for maximum profit

---

## Appendix: Quick Reference

### Chain Comparison Table

| Chain | Gas Cost | Deploy Time | Difficulty | Aave V3 | Recommended |
|-------|----------|-------------|------------|---------|-------------|
| Polygon | $0 ✅ | Done ✅ | Easy | ✅ Yes | ✅ Running |
| **Arbitrum** | **$30** | **20 min** | **Medium** | **✅ Yes** | **⭐ Best next** |
| **Base** | **$30** | **20 min** | **Easy** | **✅ Yes** | **⭐ Easy win** |
| **Optimism** | **$30** | **20 min** | **Easy** | **✅ Yes** | **✅ Good** |
| BSC | $45 | 30 min | Hard | ❌ No* | ⚠️ Need custom |
| Avalanche | $35 | 25 min | Medium | ✅ Yes | ✅ Good |
| zkEVM | $30 | 20 min | Medium | ❌ No* | ⚠️ Wait |

*BSC and zkEVM need custom flash loan implementation

### Deployment Time Estimates

| Task | First Time | Subsequent |
|------|-----------|-----------|
| Research chain | 30 min | 10 min |
| Get gas tokens | 15-60 min | 5 min |
| Setup RPC | 10 min | 5 min |
| Deploy contracts | 20 min | 15 min |
| Configure bot | 15 min | 10 min |
| Test & verify | 30 min | 15 min |
| **Total** | **2-3 hours** | **1 hour** |

### Cost Summary (All 6 New Chains)

| Chain | Gas Cost | Running Cost/mo |
|-------|----------|----------------|
| Arbitrum | $30 | $2-5 |
| Base | $30 | $2-5 |
| Optimism | $30 | $2-5 |
| BSC | $45 | $5-10 |
| Avalanche | $35 | $3-7 |
| zkEVM | $30 | $2-5 |
| **Total** | **$200** | **$16-37/mo** |

**One-time**: $200 for deployment
**Monthly**: $20-40 for gas refills
**Total first month**: $220-240

---

## Summary

**What you need to deploy to a new chain**:
1. Gas tokens ($5-50 per chain)
2. RPC endpoint (free from Alchemy)
3. Chain research (30 min - 1 hour)
4. Deployment execution (20-30 min)
5. Testing & verification (30 min)

**Total time per chain**: 2-3 hours first time, 1 hour after

**Total cost for 6 chains**: ~$200

**Expected outcome**: 7x more opportunities, 7-10x more monthly profit

**Recommendation**: Start with Arbitrum (easiest, highest impact)

---

*Document created: 2026-01-22*
*For bot version: 1.0 (Flash loan optimized)*
*Maintainer: Deploy these chains, scale to $5k-10k/month profit*
