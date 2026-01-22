# Multi-Chain Deployment: Quick Checklist

## Pre-Flight Check ✈️

### Before Starting Any Chain Deployment

- [ ] Current Polygon bot running successfully ✅
- [ ] Have access to deployment wallet private key ✅
- [ ] Foundry installed and working ✅
- [ ] Python environment set up ✅
- [ ] PostgreSQL running ✅

---

## Per-Chain Checklist

Use this for each new chain you deploy to:

### 🔍 **Research Phase** (30 min)

- [ ] Chain name: ________________
- [ ] Chain ID: ________________
- [ ] Block explorer URL: ________________
- [ ] RPC endpoint obtained: ________________
- [ ] Aave V3 available? ⬜ Yes ⬜ No
- [ ] DEX addresses found:
  - [ ] Uniswap V3 or equivalent: ________________
  - [ ] V2 DEX: ________________
  - [ ] Native DEX (optional): ________________
- [ ] Token addresses found:
  - [ ] USDC: ________________
  - [ ] USDT: ________________
  - [ ] WETH: ________________
  - [ ] DAI: ________________
  - [ ] Other: ________________

### 💰 **Funding Phase** (15-60 min)

- [ ] Gas token needed: ________ (ETH/BNB/AVAX)
- [ ] Amount needed: 0.01-0.1 tokens
- [ ] Acquisition method: ⬜ Bridge ⬜ Exchange ⬜ Buy direct
- [ ] Tokens received in wallet
- [ ] Balance verified on block explorer
- [ ] Estimated deployment cost: $______

### ⚙️ **Configuration Phase** (15 min)

- [ ] Created `.env.[chain_name]` file
- [ ] Copied from template .env
- [ ] Updated RPC URL
- [ ] Updated chain ID
- [ ] Updated DEX addresses
- [ ] Updated token addresses
- [ ] Updated Aave addresses (if available)
- [ ] Set appropriate MIN_PROFIT for chain
- [ ] Set appropriate MAX_GAS_PRICE for chain
- [ ] Verified all addresses with block explorer

### 🚀 **Deployment Phase** (20-30 min)

- [ ] Loaded chain-specific config: `source .env.[chain_name]`
- [ ] Deployed UniswapV3AdapterFixed
  - Address: ________________
  - TX hash: ________________
  - Gas used: ________________
- [ ] Deployed UniswapV2Adapter
  - Address: ________________
  - TX hash: ________________
  - Gas used: ________________
- [ ] Deployed FlashLoanArbitrageV2
  - Address: ________________
  - TX hash: ________________
  - Gas used: ________________
- [ ] Total deployment cost: $______

### 🔗 **Registration Phase** (10 min)

- [ ] Registered V3 adapter with main contract
  - TX hash: ________________
- [ ] Registered V2 adapter with main contract
  - TX hash: ________________
- [ ] Verified adapters registered (check contract state)
- [ ] Updated .env.[chain_name] with contract addresses

### ✅ **Verification Phase** (15 min)

- [ ] Verified FlashLoanArbitrageV2 on block explorer
  - Verification URL: ________________
- [ ] Verified V3 adapter on block explorer
  - Verification URL: ________________
- [ ] Verified V2 adapter on block explorer
  - Verification URL: ________________
- [ ] All contracts show source code
- [ ] Owner address correct

### 🧪 **Testing Phase** (30 min)

- [ ] Tested RPC connection
  - Connected: ⬜ Yes ⬜ No
  - Chain ID correct: ⬜ Yes ⬜ No
  - Block number fetching: ⬜ Yes ⬜ No
- [ ] Tested contract reads
  - Contract deployed: ⬜ Yes ⬜ No
  - Owner correct: ⬜ Yes ⬜ No
  - Adapters registered: ⬜ Yes ⬜ No
- [ ] Ran test scan (dry run, 5 min)
  - Scans without errors: ⬜ Yes ⬜ No
  - Logs show activity: ⬜ Yes ⬜ No
  - Opportunities detected: _____ (0 is normal)
- [ ] Ran extended test (30 min)
  - No crashes: ⬜ Yes ⬜ No
  - Database logging works: ⬜ Yes ⬜ No
  - Memory usage stable: ⬜ Yes ⬜ No

### 📊 **Monitoring Phase** (Ongoing)

- [ ] Bot running in background
  - PID: ________________
  - Log file: ________________
- [ ] Added to monitoring dashboard
- [ ] Set up alerts for errors
- [ ] Documented in deployment tracker
  - File: deployments/[chain_name]_mainnet.json

### 📝 **Documentation Phase** (10 min)

- [ ] Created deployment record JSON file
- [ ] Updated master deployment README
- [ ] Added to multi-chain coordinator config
- [ ] Noted any special considerations
- [ ] Recorded total gas spent

---

## Chain Priority Order

Check off as you complete:

### Tier 1: Easy Wins (Start Here)
- [ ] **Arbitrum** - Highest priority, large volume
  - Difficulty: 🟡 Medium
  - Cost: $30
  - Impact: Very High
  - Time: 2-3 hours first chain

- [ ] **Base** - Easiest deployment, growing fast
  - Difficulty: 🟢 Easy
  - Cost: $30
  - Impact: High
  - Time: 1-2 hours

- [ ] **Optimism** - Similar to Base
  - Difficulty: 🟢 Easy
  - Cost: $30
  - Impact: Medium-High
  - Time: 1-2 hours

### Tier 2: High Volume
- [ ] **BSC** - High volume but needs custom flash loans ⚠️
  - Difficulty: 🔴 Hard
  - Cost: $45
  - Impact: Very High
  - Time: 4-6 hours (custom development)
  - Note: Skip unless experienced

- [ ] **Avalanche** - Good DeFi ecosystem
  - Difficulty: 🟡 Medium
  - Cost: $35
  - Impact: Medium
  - Time: 2 hours

### Tier 3: Emerging
- [ ] **Polygon zkEVM** - New, less competition but no Aave ⚠️
  - Difficulty: 🟡 Medium
  - Cost: $30
  - Impact: Low-Medium
  - Time: 2 hours
  - Note: Skip until Aave V3 deployed

---

## Quick Requirements Summary

### For 3 Chains (Arbitrum, Base, Optimism)

**Capital**: $90
- Arbitrum: $30
- Base: $30
- Optimism: $30

**Time**: 6-8 hours
- First chain: 3 hours
- Second chain: 2 hours
- Third chain: 2 hours

**Skills needed**:
- Copy/paste configuration ✅
- Run deployment scripts ✅
- Basic troubleshooting ✅

**Expected result**: 3-5x more opportunities

---

### For 6 Chains (All Tier 1 & 2 except BSC)

**Capital**: $180
- Arbitrum: $30
- Base: $30
- Optimism: $30
- Avalanche: $35
- zkEVM: $30
- Buffer: $25

**Time**: 12-16 hours
- First 3 chains: 6-8 hours
- Next 2 chains: 4 hours
- Testing all: 2-4 hours

**Expected result**: 7-10x more opportunities, $4k-10k/month

---

## Troubleshooting Checklist

If deployment fails, check:

- [ ] Sufficient gas tokens in wallet
- [ ] RPC endpoint working (test with curl)
- [ ] Correct chain selected (check chain ID)
- [ ] Constructor arguments correct
- [ ] Token addresses valid for target chain
- [ ] DEX contracts exist on chain
- [ ] Aave V3 available (if using flash loans)
- [ ] No typos in addresses
- [ ] Compiler version correct (0.8.20)
- [ ] Network not congested

If bot fails to run, check:

- [ ] Config file loaded correctly
- [ ] Contract addresses in config
- [ ] RPC endpoint in config
- [ ] Python dependencies installed
- [ ] Database accessible
- [ ] Sufficient disk space for logs
- [ ] Firewall not blocking RPC
- [ ] API key valid and not rate limited

---

## Success Criteria

### Deployment Successful When:

✅ All 3 contracts deployed
✅ All contracts verified on explorer
✅ Adapters registered
✅ Test scan runs without errors
✅ Bot can read from blockchain
✅ Logs show scanning activity
✅ Database receives records

### Ready for Production When:

✅ 24-hour test run stable
✅ No crashes or errors
✅ Opportunities being logged (if any exist)
✅ Gas costs within expected range
✅ Memory usage stable
✅ Monitoring set up

---

## Time Budget (Per Chain)

| Task | First Chain | Subsequent |
|------|-------------|-----------|
| Research | 30 min | 10 min |
| Get gas | 30 min | 10 min |
| Configure | 15 min | 10 min |
| Deploy | 30 min | 15 min |
| Test | 30 min | 15 min |
| Document | 15 min | 5 min |
| **Total** | **2.5 hours** | **1 hour** |

**3 chains**: 4.5 hours
**6 chains**: 7.5 hours

---

## Quick Commands Reference

### Check Balance
```bash
./check_balance.sh  # Polygon
# Create for other chains as needed
```

### Deploy Contracts
```bash
source .env.[chain_name]
./venv/bin/python deploy_contracts.py
```

### Test Connection
```bash
python test_rpc.py --chain [chain_name]
```

### Start Bot
```bash
python run_bot.py --config .env.[chain_name]
```

### Monitor Logs
```bash
tail -f bot_[chain_name].log
```

### Check Running Bots
```bash
ps aux | grep run_bot.py
```

---

## Daily Operations Checklist

### Once All Chains Deployed

**Morning** (5 min):
- [ ] Check all bots still running
- [ ] Review overnight logs for errors
- [ ] Check for any opportunities detected
- [ ] Verify gas balances sufficient

**Evening** (5 min):
- [ ] Review day's activity
- [ ] Check database for new opportunities
- [ ] Verify no crashes or restarts
- [ ] Plan gas refills if needed

**Weekly** (30 min):
- [ ] Analyze opportunity frequency per chain
- [ ] Adjust MIN_PROFIT if needed
- [ ] Add new trading pairs if opportunities low
- [ ] Refill gas on chains running low
- [ ] Review and optimize settings

**Monthly** (2 hours):
- [ ] Full performance review
- [ ] Calculate actual vs expected profit
- [ ] Deploy to additional chains if warranted
- [ ] Add new DEXs to existing chains
- [ ] Upgrade bot if new version available

---

## Risk Checklist

Before enabling live execution (DRY_RUN=false):

- [ ] Tested in DRY_RUN for at least 1 week
- [ ] Detected at least 3 real opportunities
- [ ] Verified profit calculations correct
- [ ] Tested on small opportunity first
- [ ] Emergency stop mechanism works
- [ ] Have sufficient gas for multiple trades
- [ ] Monitoring/alerts set up
- [ ] Understand risks of MEV frontrunning
- [ ] Comfortable with potential failed transactions
- [ ] Know how to pause bot quickly

---

## Emergency Procedures

### If Bot Malfunctions:

1. **Stop all bots immediately**:
   ```bash
   pkill -f run_bot.py
   ```

2. **Check logs for errors**:
   ```bash
   tail -100 bot_*.log | grep ERROR
   ```

3. **Verify wallet balance**:
   ```bash
   ./check_balance_multichain.sh
   ```

4. **Pause contracts** (if needed):
   ```bash
   # Call pause() on each contract
   ```

### If Opportunity Goes Wrong:

1. **Don't panic** - Flash loans can't lose principal
2. **Check transaction on explorer**
3. **Analyze revert reason**
4. **Adjust settings if needed**
5. **Resume with corrected parameters**

---

## Success Metrics to Track

### Per Chain:
- Total opportunities detected
- Opportunities executed
- Success rate
- Average profit per trade
- Total profit
- Gas spent
- Net profit

### Overall:
- Total monthly profit across all chains
- ROI on deployment capital
- Opportunity frequency
- Most profitable chain
- Most profitable pair
- Best performing DEX combination

---

## Files to Maintain

- [ ] `.env.[chain_name]` for each chain
- [ ] `deployments/[chain_name]_mainnet.json` for each chain
- [ ] `deployments/README.md` master list
- [ ] `bot_[chain_name].log` log files
- [ ] `[chain_name]_bot.pid` PID files
- [ ] `multi_chain_coordinator.py` if using coordinator

---

## Next Actions After This Document

1. **Choose first chain** (Recommend: Arbitrum)
2. **Work through checklist** for that chain
3. **Deploy and test** (2-3 hours)
4. **Let run for 24 hours** in DRY_RUN
5. **Review results**
6. **Repeat** for next chain

**Goal**: 3 chains deployed in one weekend (Saturday + Sunday)

**Result**: 3-5x more opportunities starting Monday

---

**Remember**:
- First chain takes longest (3 hours)
- Each subsequent chain faster (1-2 hours)
- Start with Arbitrum (easiest, highest impact)
- Test thoroughly before enabling execution
- Monitor closely first week

**You're ready to scale!** 🚀
