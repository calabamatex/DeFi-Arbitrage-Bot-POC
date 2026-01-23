# Polygon Mainnet Deployment Instructions

## Step 1: Fund Deployer Wallet

**Your deployer wallet needs MATIC for gas:**

```
Address: 0x21451Fc62F8Fce09E1a2Af8Abb0cED296Adb552E
Current Balance: 0 MATIC
Required: ~0.5 MATIC
```

### How to Fund:

**Option A: From Exchange (Recommended)**
1. Buy MATIC on any exchange (Coinbase, Binance, etc.)
2. Withdraw to Polygon network (NOT Ethereum!)
3. Send to: `0x21451Fc62F8Fce09E1a2Af8Abb0cED296Adb552E`
4. Amount: 0.5-1 MATIC (~$0.30-0.60)

**Option B: Bridge from Ethereum**
1. Use Polygon Bridge: https://wallet.polygon.technology/polygon/bridge
2. Bridge ETH or USDC to Polygon
3. Swap for MATIC on QuickSwap

**Option C: Use Faucet (If Available)**
- Polygon mainnet faucets are rare
- Usually require social media verification

### Verify Balance:
```bash
cd /Users/ethanallen/ARBITRAGE
./venv/bin/python -c "
from web3 import Web3
web3 = Web3(Web3.HTTPProvider('https://polygon-mainnet.g.alchemy.com/v2/iYtOHvXMFAIuDxrSlk4GU'))
balance = web3.eth.get_balance('0x21451Fc62F8Fce09E1a2Af8Abb0cED296Adb552E')
print(f'Balance: {web3.from_wei(balance, \"ether\")} MATIC')
"
```

## Step 2: Deploy Contracts (I'll do this)

Once funded, I'll deploy:
1. FlashLoanArbitrageV2
2. UniswapV3AdapterFixed
3. UniswapV2Adapter

Estimated cost: $0.15-0.30 depending on gas prices

## Step 3: Configure Bot for DRY_RUN

Set observation mode (no real transactions)

## Step 4: Start Monitoring

Bot will scan for opportunities 24/7 with zero execution

---

**Please fund the wallet and let me know when ready!**
