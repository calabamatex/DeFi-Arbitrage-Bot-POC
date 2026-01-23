# Testnet Deployment Guide - Polygon Amoy

## Current Status

✅ **Testnet RPC Connected**: Polygon Amoy (Chain ID: 80002)
✅ **Executor Wallet**: `0x21451Fc62F8Fce09E1a2Af8Abb0cED296Adb552E`
⚠️  **Wallet Balance**: 0 MATIC (needs funding)

---

## Step 1: Get Testnet MATIC

### Option 1: Polygon Official Faucet (Recommended)

1. Visit: https://faucet.polygon.technology/
2. Select **"Polygon Amoy"** from network dropdown
3. Paste your address: `0x21451Fc62F8Fce09E1a2Af8Abb0cED296Adb552E`
4. Complete CAPTCHA
5. Click "Submit"
6. Wait 1-2 minutes to receive **0.5 MATIC**

### Option 2: Alchemy Faucet

1. Visit: https://www.alchemy.com/faucets/polygon-amoy
2. Sign in with your Alchemy account
3. Enter address: `0x21451Fc62F8Fce09E1a2Af8Abb0cED296Adb552E`
4. Receive **0.5 MATIC**

### Option 3: QuickNode Faucet

1. Visit: https://faucet.quicknode.com/polygon/amoy
2. Connect wallet or enter address
3. Request testnet MATIC

### Verify You Received Funds

```bash
# Run this to check balance:
./venv/bin/python << 'EOF'
from web3 import Web3
web3 = Web3(Web3.HTTPProvider("https://rpc-amoy.polygon.technology"))
balance = web3.eth.get_balance("0x21451Fc62F8Fce09E1a2Af8Abb0cED296Adb552E")
print(f"Balance: {web3.from_wei(balance, 'ether')} MATIC")
EOF
```

Expected: `Balance: 0.5 MATIC` or similar

---

## Step 2: Deploy Contracts to Testnet

Once you have testnet MATIC, deploy the contracts:

### Deploy Smart Contracts

```bash
cd contracts

# Set testnet RPC in contracts/.env
echo "POLYGON_RPC_URL=https://rpc-amoy.polygon.technology" >> .env

# Deploy FlashLoanArbitrageV2
forge create src/FlashLoanArbitrageV2.sol:FlashLoanArbitrageV2 \
  --rpc-url https://rpc-amoy.polygon.technology \
  --private-key 0xcf4cbdb74541d0dfe888271c7f9424c0fc7e62bcd0f50a72ae9363d112a55ff9 \
  --constructor-args 0x4CeDCB57Af02293231BAA9D39354D6BFDFD251e0

# Save the deployed address!

# Deploy UniswapV3Adapter
forge create src/UniswapV3Adapter.sol:UniswapV3Adapter \
  --rpc-url https://rpc-amoy.polygon.technology \
  --private-key 0xcf4cbdb74541d0dfe888271c7f9424c0fc7e62bcd0f50a72ae9363d112a55ff9 \
  --constructor-args 0x0227628f3F023bb0B980b67D528571c95c6DaC1c "UniswapV3"

# Deploy UniswapV2Adapter (for QuickSwap, if available)
forge create src/UniswapV2Adapter.sol:UniswapV2Adapter \
  --rpc-url https://rpc-amoy.polygon.technology \
  --private-key 0xcf4cbdb74541d0dfe888271c7f9424c0fc7e62bcd0f50a72ae9363d112a55ff9 \
  --constructor-args <QUICKSWAP_ROUTER_ADDRESS> "QuickSwap"
```

### Register Adapters

```bash
# Register V3 Adapter with main contract
cast send <FLASH_LOAN_ADDRESS> \
  "registerAdapter(address,bool)" \
  <V3_ADAPTER_ADDRESS> \
  true \
  --rpc-url https://rpc-amoy.polygon.technology \
  --private-key 0xcf4cbdb74541d0dfe888271c7f9424c0fc7e62bcd0f50a72ae9363d112a55ff9

# Register V2 Adapter
cast send <FLASH_LOAN_ADDRESS> \
  "registerAdapter(address,bool)" \
  <V2_ADAPTER_ADDRESS> \
  true \
  --rpc-url https://rpc-amoy.polygon.technology \
  --private-key 0xcf4cbdb74541d0dfe888271c7f9424c0fc7e62bcd0f50a72ae9363d112a55ff9
```

---

## Step 3: Update Bot Configuration

Update `.env.testnet` with deployed addresses:

```bash
# Edit .env.testnet
nano .env.testnet

# Update these values:
FLASH_LOAN_ARBITRAGE_ADDRESS=<deployed_address>
UNISWAP_V3_ADAPTER_ADDRESS=<deployed_address>
UNISWAP_V2_ADAPTER_ADDRESS=<deployed_address>
```

---

## Step 4: Get Test Tokens

### Testnet USDC

Unfortunately, most DEX test tokens aren't available on Amoy yet. You have options:

**Option A: Deploy Mock Tokens**

```bash
# Deploy mock ERC20 tokens for testing
forge create MockERC20 \
  --rpc-url https://rpc-amoy.polygon.technology \
  --private-key 0xcf4cbdb74541d0dfe888271c7f9424c0fc7e62bcd0f50a72ae9363d112a55ff9 \
  --constructor-args "Mock USDC" "USDC" 6

# Mint yourself some tokens
cast send <USDC_ADDRESS> \
  "mint(address,uint256)" \
  0x21451Fc62F8Fce09E1a2Af8Abb0cED296Adb552E \
  1000000000000 \
  --rpc-url https://rpc-amoy.polygon.technology \
  --private-key 0xcf4cbdb74541d0dfe888271c7f9424c0fc7e62bcd0f50a72ae9363d112a55ff9
```

**Option B: Use Existing Testnet Pools**

Check if Uniswap V3 has testnet pools on Amoy:
- https://app.uniswap.org/ (switch to Amoy testnet)
- Look for existing pools with liquidity

**Option C: Create Your Own Liquidity**

1. Deploy mock tokens
2. Mint tokens to yourself
3. Add liquidity to Uniswap V3 pool
4. Create price differences manually for testing

---

## Step 5: Run Bot on Testnet

### Update Environment

```bash
# Copy testnet config to main .env
cp .env.testnet .env

# Verify configuration
cat .env | grep -E "(POLYGON_RPC|DRY_RUN|FLASH_LOAN)"
```

### Start the Bot

```bash
# Activate virtual environment
source venv/bin/activate

# Run bot (DRY_RUN=false for real testnet transactions)
python run_bot.py
```

### What to Expect

**On Testnet:**
```
✅ Bot will connect to Amoy
✅ Will scan for arbitrage opportunities
⚠️  May find ZERO opportunities (testnet has low liquidity)
✅ Any opportunities found WILL execute (real transactions!)
✅ No real money at risk (testnet tokens are worthless)
```

**Success Looks Like:**
```
2026-01-21 - INFO - 🚀 Flash Loan Arbitrage Bot Starting
2026-01-21 - INFO - ✅ Connected to blockchain (Chain ID: 80002)
2026-01-21 - INFO - Mode: Direct Execution
2026-01-21 - INFO - Dry run: False
2026-01-21 - INFO - 🔍 Scanning 4 pairs with 3 amounts...
```

---

## Step 6: Create Test Opportunities (Optional)

If no natural opportunities appear, create artificial ones:

### Manual Arbitrage Setup

```python
# create_test_opportunity.py
from web3 import Web3

w3 = Web3(Web3.HTTPProvider("https://rpc-amoy.polygon.technology"))

# 1. Deploy two mock DEXs with different prices
# 2. Add liquidity at different ratios
# 3. Your bot should detect the arbitrage!

# Example:
# DEX A: 1 USDC = 1000 TokenB
# DEX B: 1 USDC = 1100 TokenB
# Arbitrage: Buy on A, sell on B = 10% profit
```

---

## Important Notes

### Testnet Limitations

⚠️ **Low Liquidity**: Testnet DEXs have minimal liquidity
⚠️ **Few Pairs**: Most tokens don't exist on testnet
⚠️ **Slow Blocks**: Testnet can be slower than mainnet
⚠️ **No Real Profit**: Tokens are worthless (but great for testing!)

### What You Can Test

✅ **Transaction Building**: Verify transactions are built correctly
✅ **Gas Estimation**: See actual gas usage
✅ **Execution Flow**: Full end-to-end execution
✅ **Error Handling**: Test failure scenarios
✅ **Database Logging**: Verify all data is logged
✅ **Smart Contracts**: Test flash loan + swap logic

### What You Can't Test

❌ **Real Competition**: No MEV bots on testnet
❌ **Market Conditions**: No real price movements
❌ **Profitability**: Can't verify real profit potential
❌ **MEV Protection**: No Flashbots on testnet

---

## Troubleshooting

### "Insufficient Funds" Error

```bash
# Check balance
./venv/bin/python -c "
from web3 import Web3
w3 = Web3(Web3.HTTPProvider('https://rpc-amoy.polygon.technology'))
balance = w3.eth.get_balance('0x21451Fc62F8Fce09E1a2Af8Abb0cED296Adb552E')
print(f'{w3.from_wei(balance, \"ether\")} MATIC')
"

# Get more from faucet if needed
```

### "Pool Does Not Exist" Error

Uniswap V3 pool might not exist on testnet for that pair.

Solution:
1. Check existing pools on Uniswap testnet
2. Use only pairs with liquidity
3. Or deploy your own pools

### Contract Deployment Fails

```bash
# Check gas price
cast gas-price --rpc-url https://rpc-amoy.polygon.technology

# Use higher gas limit
forge create ... --gas-limit 3000000
```

### Bot Finds No Opportunities

This is expected on testnet!

Options:
1. Lower MIN_PROFIT_USD to 0.01 in .env
2. Create artificial arbitrage opportunities
3. Add liquidity to pools yourself
4. Wait for other testnet users to create opportunities

---

## Next Steps After Testnet

Once you've successfully tested on testnet:

1. ✅ Verified transactions execute correctly
2. ✅ Confirmed gas estimates are reasonable
3. ✅ Tested error handling
4. ✅ Database logging works
5. ✅ All components integrated properly

**Then you're ready for mainnet!**

### Mainnet Deployment Checklist

- [ ] Fund wallet with real MATIC (0.5-1.0)
- [ ] Deploy contracts to Polygon mainnet
- [ ] Start with high MIN_PROFIT_USD (10+)
- [ ] Use DRY_RUN=true initially
- [ ] Monitor closely for 24 hours
- [ ] Gradually lower thresholds
- [ ] Scale up as confidence grows

---

## Current Testnet Info

**Network**: Polygon Amoy
**Chain ID**: 80002
**RPC**: https://rpc-amoy.polygon.technology
**Explorer**: https://amoy.polygonscan.com/

**Your Wallet**: 0x21451Fc62F8Fce09E1a2Af8Abb0cED296Adb552E
**Balance**: Check at https://amoy.polygonscan.com/address/0x21451Fc62F8Fce09E1a2Af8Abb0cED296Adb552E

**Faucets**:
- https://faucet.polygon.technology/
- https://www.alchemy.com/faucets/polygon-amoy
- https://faucet.quicknode.com/polygon/amoy

---

**Ready to proceed?**

1. Get testnet MATIC from faucet (5 minutes)
2. Deploy contracts (10 minutes)
3. Run bot (immediate)
4. Celebrate first testnet execution! 🎉
