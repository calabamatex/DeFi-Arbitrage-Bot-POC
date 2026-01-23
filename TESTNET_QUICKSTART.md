# 🚀 Testnet Deployment - Quick Start

## Current Status

✅ **Testnet Configuration Ready**: `.env.testnet` created
✅ **Deployment Scripts Ready**: Automated deployment prepared
✅ **Wallet Address**: `0x21451Fc62F8Fce09E1a2Af8Abb0cED296Adb552E`
⚠️ **Needs**: Testnet MATIC to deploy (free from faucet)

---

## 3-Step Deployment Process

### Step 1: Get Testnet MATIC (5 minutes)

**Visit the faucet:**
```
https://faucet.polygon.technology/
```

**Instructions:**
1. Select **"Polygon Amoy"** from dropdown
2. Paste your address: `0x21451Fc62F8Fce09E1a2Af8Abb0cED296Adb552E`
3. Complete CAPTCHA
4. Click "Submit"
5. Wait 1-2 minutes to receive 0.5 MATIC

**Verify you received funds:**
```bash
python check_testnet_ready.py
```

Expected output:
```
✅ READY TO DEPLOY!
💰 Balance: 0.5 MATIC
```

---

### Step 2: Deploy Contracts (5 minutes)

Once you have testnet MATIC:

```bash
# Build contracts (if not done already)
cd contracts
forge build
cd ..

# Deploy to testnet (automated)
python deploy_to_testnet.py
```

**The script will automatically:**
1. ✅ Check your balance
2. ✅ Deploy FlashLoanArbitrageV2 contract
3. ✅ Deploy UniswapV3Adapter contract
4. ✅ Register adapter with main contract
5. ✅ Update `.env.testnet` with addresses
6. ✅ Save deployment info to `testnet_deployment.json`

**Expected output:**
```
🎉 Deployment Complete!

Deployed Contracts:
  FlashLoanArbitrageV2:  0x...
  UniswapV3Adapter:      0x...

Next Steps:
1. Copy testnet config: cp .env.testnet .env
2. Run the bot: python run_bot.py
```

---

### Step 3: Run the Bot (immediate)

```bash
# Copy testnet configuration
cp .env.testnet .env

# Activate virtual environment
source venv/bin/activate

# Run bot on testnet (DRY_RUN=false)
python run_bot.py
```

**The bot will:**
- ✅ Connect to Polygon Amoy testnet
- ✅ Scan for arbitrage opportunities
- ✅ Execute real transactions (with worthless testnet tokens)
- ✅ Log everything to database

---

## What to Expect

### On Testnet

**Pros:**
- ✅ Test full execution flow
- ✅ Real blockchain transactions
- ✅ Verify gas estimates
- ✅ Test error handling
- ✅ No risk (testnet tokens are worthless)

**Cons:**
- ⚠️ Very few opportunities (low liquidity)
- ⚠️ No real competition (no MEV bots)
- ⚠️ Limited DEX pairs available
- ⚠️ Can't validate profitability

### Likely Outcome

```
Bot will run and scan continuously but find ZERO opportunities.

Why? Testnet DEXs have almost no liquidity or trading activity.

This is NORMAL and EXPECTED!
```

### What This Still Proves

Even with zero opportunities, you can verify:
1. ✅ Bot connects to blockchain correctly
2. ✅ Price quotes work (or show which pools don't exist)
3. ✅ Transaction building logic is correct
4. ✅ Gas estimation works
5. ✅ Error handling is robust
6. ✅ Logging captures everything

---

## Creating Test Opportunities (Optional)

If you want to see actual executions on testnet:

### Option 1: Deploy Mock Tokens & Pools

```bash
# Deploy mock tokens with price differences
# Add liquidity to multiple DEXs at different rates
# Bot will detect the arbitrage!
```

See `TESTNET_DEPLOYMENT.md` for detailed instructions.

### Option 2: Wait for Activity

Occasionally other developers test on Amoy, creating temporary opportunities.

### Option 3: Move to Mainnet Fork

Use Anvil with mainnet fork for more realistic testing:
```bash
# Already set up from before
anvil --fork-url <ALCHEMY_URL> --port 8545
```

---

## Troubleshooting

### "Failed to connect to testnet"

Check if Amoy RPC is working:
```bash
curl https://rpc-amoy.polygon.technology \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
```

### "Insufficient funds" error

Run checker:
```bash
python check_testnet_ready.py
```

If balance is 0, get more MATIC from faucet.

### "Contract not found" error

Verify deployment:
```bash
cat testnet_deployment.json
```

Check contract on explorer:
```
https://amoy.polygonscan.com/address/<CONTRACT_ADDRESS>
```

### "No opportunities found"

This is normal! Testnet has minimal activity.

Options:
1. Lower MIN_PROFIT_USD to 0.01 in `.env`
2. Create artificial opportunities
3. Be patient (rare testnet activity)
4. Consider this successful validation of the bot's scanning

---

## Quick Commands Reference

```bash
# Check if ready to deploy
python check_testnet_ready.py

# Deploy contracts to testnet
python deploy_to_testnet.py

# Copy testnet config
cp .env.testnet .env

# Run bot on testnet
python run_bot.py

# Check bot logs
tail -f bot.log

# View deployment info
cat testnet_deployment.json

# Check database
python << 'EOF'
from src.db.database import SessionLocal
from src.db.models import Opportunity
db = SessionLocal()
print(f"Opportunities: {db.query(Opportunity).count()}")
db.close()
EOF
```

---

## After Testnet Validation

Once you've confirmed the bot works on testnet:

### Ready for Mainnet Checklist

- [ ] Contracts deploy successfully
- [ ] Bot connects to testnet
- [ ] Transaction building works
- [ ] Gas estimation reasonable
- [ ] Error handling tested
- [ ] Logging captures all events
- [ ] No crashes or panics

### Mainnet Deployment

```bash
# Switch back to mainnet config
cp .env.mainnet .env

# Or update .env manually:
POLYGON_RPC_URL=http://localhost:8545  # Anvil with mainnet fork
# or
POLYGON_RPC_URL=https://polygon-mainnet.g.alchemy.com/v2/...

# Deploy contracts to mainnet
# Fund wallet with real MATIC
# Start with DRY_RUN=true
# Then DRY_RUN=false when confident
```

---

## Important Links

**Faucets:**
- Main: https://faucet.polygon.technology/
- Alchemy: https://www.alchemy.com/faucets/polygon-amoy
- QuickNode: https://faucet.quicknode.com/polygon/amoy

**Explorers:**
- Amoy: https://amoy.polygonscan.com/
- Your wallet: https://amoy.polygonscan.com/address/0x21451Fc62F8Fce09E1a2Af8Abb0cED296Adb552E

**Documentation:**
- Full guide: `TESTNET_DEPLOYMENT.md`
- Bot docs: `PROJECT_COMPLETE.md`
- Quick start: `QUICK_START.md`

---

## Summary

**Where you are now:**
- ✅ Everything is ready
- ⚠️ Just need testnet MATIC (free!)

**What to do:**
1. Get MATIC from faucet (5 min)
2. Run `python deploy_to_testnet.py` (5 min)
3. Run `python run_bot.py` (immediate)

**Total time: 10-15 minutes**

**Then you'll have:**
- ✅ Bot running on testnet
- ✅ Real transactions executing
- ✅ Full validation of system
- ✅ Ready for mainnet!

---

**Ready? Get started:**
```
https://faucet.polygon.technology/
Address: 0x21451Fc62F8Fce09E1a2Af8Abb0cED296Adb552E
```

🚀 Let's deploy!
