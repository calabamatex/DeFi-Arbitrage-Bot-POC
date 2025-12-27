# Mainnet Deployment Guide

## Overview

This guide explains how to deploy the Polygon Arbitrage Bot to mainnet and operate it safely during the critical first week. **This involves REAL MONEY** - proceed with extreme caution!

**Created:** December 26, 2025
**Status:** Ready for mainnet deployment
**Prerequisites:** Successful 48-hour testnet validation (Task 7.1 PASSED)

---

## ⚠️ CRITICAL WARNINGS

**Before you proceed:**
- ✅ You MUST have completed 48-hour testnet validation successfully
- ✅ You MUST have received a GO recommendation from analyze_validation_run.py
- ✅ You MUST be prepared for 24/7 monitoring for at least the first 48 hours
- ✅ You MUST use a DEDICATED wallet (not your personal wallet)
- ✅ You MUST start with conservative settings ($100 position size, 2% profit threshold)
- ⚠️ You can LOSE MONEY - only risk what you can afford to lose
- ⚠️ DeFi is risky - smart contract bugs, network issues, MEV bots all pose risks

**If you're not 100% ready, STOP HERE and return to testnet.**

---

## Files Created for Mainnet Deployment

### 1. Preparation Script
**File:** `scripts/prepare_mainnet.sh`
**Size:** 4.0 KB
**Purpose:** Creates mainnet configuration templates and runs pre-flight checklist

**What it creates:**
- `.env.mainnet` - Mainnet environment variables template
- `config/config.mainnet.json` - Conservative mainnet configuration

**Usage:**
```bash
./scripts/prepare_mainnet.sh
```

### 2. Deployment Checklist
**File:** `docs/MAINNET_DEPLOYMENT_CHECKLIST.md`
**Size:** 32 KB (870+ lines)
**Purpose:** Comprehensive checklist for entire deployment process

**What it includes:**
- Pre-deployment verification (all prerequisites)
- Deployment execution steps (5 steps)
- Post-deployment monitoring (hourly for 24 hours)
- First week daily monitoring
- Scaling decision framework
- Emergency procedures
- Sign-off templates

### 3. Health Check Script
**File:** `scripts/mainnet_health_check.sh`
**Size:** 6.8 KB
**Purpose:** Quick health checks during mainnet operation

**What it checks:**
- Bot running status
- Error counts
- Emergency shutdowns
- Recent trades
- Resource usage (CPU/Memory)
- Metrics
- RPC connectivity

**Usage:**
```bash
# Run manually anytime
./scripts/mainnet_health_check.sh

# Returns exit code 0 if healthy, >0 if issues found
```

### 4. Existing Deployment Script
**File:** `scripts/deploy_mainnet.sh` (already exists from Task 6.1)
**Purpose:** Automated deployment with safety checks

---

## Step-by-Step Deployment Process

### Phase 1: Pre-Deployment Preparation (2-4 hours)

#### 1.1 Verify Testnet Validation Results

```bash
# Review validation report
cat validation_report_*.txt

# Must show:
# - 48+ hours runtime
# - 0 critical errors
# - Performance targets met
# - GO recommendation

# If not PASS, return to testnet!
```

**Required validation metrics:**
- ✅ Runtime: 48+ hours
- ✅ Uptime: 100% (no crashes)
- ✅ Critical errors: 0
- ✅ Success rate: >60%
- ✅ Detection time: <2 seconds
- ✅ Execution time: <5 seconds
- ✅ Memory: <500 MB stable
- ✅ CPU: <80% average

#### 1.2 Create Dedicated Mainnet Wallet

**IMPORTANT:** Use a DEDICATED wallet, not your personal wallet!

```bash
# Generate new wallet (using any tool)
# Examples:
# - MetaMask: Create new account
# - Python: Use Web3.py to generate
# - Hardware wallet: Create new account

# Document wallet address
WALLET_ADDRESS="0x..."
echo $WALLET_ADDRESS > mainnet_wallet.txt
```

**Security:**
- ✅ Backup private key offline (encrypted USB, paper wallet)
- ✅ Store backup in secure location (safe, safety deposit box)
- ✅ NEVER share private key
- ✅ Test wallet with small transaction first

#### 1.3 Fund Mainnet Wallet

```bash
# Required funding:
# 1. MATIC for gas: 5+ MATIC (~$5-10)
# 2. Trading capital: $1000+ recommended

# Tokens needed:
# - USDC: Primary trading token
# - WETH: Secondary trading token
# - DAI: Tertiary trading token
# - WMATIC: Gas token

# Recommended initial allocation:
# - 5-10 MATIC for gas
# - $400-500 in USDC
# - $300-400 in WETH
# - $200-300 in DAI

# Transfer from exchange or your main wallet
```

**Verify balances:**
```bash
# After funding, verify with check_balances.py
./scripts/check_balances.py

# Should show:
# MATIC: 5+ MATIC
# USDC: $400+
# WETH: $300+
# DAI: $200+
```

#### 1.4 Run Preparation Script

```bash
./scripts/prepare_mainnet.sh

# This will:
# 1. Backup current configuration
# 2. Create .env.mainnet template
# 3. Create config.mainnet.json with conservative settings
# 4. Display pre-flight checklist
```

#### 1.5 Configure Mainnet Environment

```bash
# Edit .env.mainnet
nano .env.mainnet

# Set:
# - ENVIRONMENT=mainnet
# - PRIVATE_KEY=0x<your_mainnet_private_key>
# - TELEGRAM_BOT_TOKEN=<your_bot_token>
# - TELEGRAM_CHAT_ID=<your_chat_id>
# - ADMIN_CODE=<strong_12+_character_code>
# - POLYGON_RPC_URL=<reliable_mainnet_rpc>

# Secure file permissions
chmod 600 .env.mainnet
ls -l .env.mainnet
# Should show: -rw-------
```

**RPC Provider Recommendations:**
- Alchemy: https://polygon-mainnet.g.alchemy.com/v2/YOUR-API-KEY
- Infura: https://polygon-mainnet.infura.io/v3/YOUR-API-KEY
- QuickNode: https://your-endpoint.polygon.quiknode.pro/YOUR-KEY/
- Public (less reliable): https://polygon-rpc.com/

#### 1.6 Review Conservative Configuration

```bash
# Review mainnet config
cat config/config.mainnet.json

# Conservative settings should include:
# - BASE_PROFIT_THRESHOLD: 0.02 (2%)
# - MAX_POSITION_SIZE_USD: 100
# - DAILY_LOSS_LIMIT_USD: 500
# - MAX_CONSECUTIVE_LOSSES: 3
# - SLIPPAGE_TOLERANCE: 0.003 (0.3%)
```

**Why conservative?**
- Higher profit threshold (2%) reduces false positives
- Smaller position size ($100) limits per-trade risk
- Strict loss limits protect capital
- More sensitive circuit breaker stops losses quickly

#### 1.7 Test Telegram Alerts

```bash
# Send test alert
python3 << 'EOF'
from src.utils.telegram_alerts import send_telegram_alert
import asyncio

async def test():
    await send_telegram_alert("🚀 Mainnet deployment test - If you receive this, alerts are working!")

asyncio.run(test())
EOF

# Check your Telegram - you should receive message
```

#### 1.8 Complete Pre-Deployment Checklist

Open and complete: `docs/MAINNET_DEPLOYMENT_CHECKLIST.md`

**Pre-Deployment section - ALL items must be checked:**
- [ ] Validation results verified
- [ ] Configuration complete
- [ ] Wallet funded
- [ ] Security measures in place
- [ ] Monitoring ready
- [ ] Team ready (24/7 coverage)
- [ ] Documentation reviewed

### Phase 2: Deployment Execution (30-60 minutes)

#### 2.1 Activate Mainnet Environment

```bash
# IMPORTANT: Backup current files first
cp .env .env.backup
cp config/config.json config/config.json.backup

# Activate mainnet
cp .env.mainnet .env
cp config/config.mainnet.json config/config.json

# Verify mainnet environment
python3 -c "from src.bot.config import load_config; config, env, env_config, settings = load_config(); print(f'Environment: {env}'); print(f'Chain ID: {env_config.get(\"CHAIN_ID\")}')"

# MUST show:
# Environment: mainnet
# Chain ID: 137
```

#### 2.2 Run Pre-Flight Checks

```bash
./scripts/deploy_mainnet.sh

# This will:
# 1. Verify Python version
# 2. Check .env configuration
# 3. Verify mainnet environment
# 4. Check MATIC balance (5+ required)
# 5. Run all tests (42+ must pass)
# 6. Display final safety checklist
# 7. Require "DEPLOY TO MAINNET" confirmation

# ALL checks must pass!
```

**If any check fails:**
- STOP immediately
- Fix the issue
- Re-run deploy_mainnet.sh
- Do NOT proceed manually

#### 2.3 Final Confirmation

The deployment script will ask multiple confirmations:

```
⚠️  WARNING: You are about to deploy to MAINNET with REAL MONEY!

Have you completed 48-hour testnet validation? (yes/no): yes
Did testnet validation PASS? (yes/no): yes
Are you prepared for 24/7 monitoring? (yes/no): yes
Have you read all documentation? (yes/no): yes

Type exactly 'DEPLOY TO MAINNET' to proceed: DEPLOY TO MAINNET
```

**Think carefully before typing "DEPLOY TO MAINNET"!**

#### 2.4 Start the Bot

```bash
# Start bot in background with logging
nohup python3 -m src.bot.main > logs/mainnet_bot.log 2>&1 &

# Record process ID
echo $! > mainnet_bot.pid
BOT_PID=$(cat mainnet_bot.pid)
echo "Bot started with PID: $BOT_PID"

# Verify started
ps -p $BOT_PID
```

#### 2.5 Initial Verification (First 10 Minutes)

**Watch logs in real-time:**
```bash
tail -f logs/mainnet_bot.log

# Should see:
# - "Starting initialization"
# - "Connecting to network: mainnet"
# - "Chain ID: 137"
# - "Initializing DEX adapters"
# - "Initialization complete"
# - "Starting arbitrage bot"
```

**Check for immediate errors:**
```bash
# In another terminal
grep -i "error\|critical" logs/mainnet_bot.log

# Should be empty or only minor warnings
```

**Run health check:**
```bash
./scripts/mainnet_health_check.sh

# Should show:
# ✓ Bot is running
# ✓ Error count acceptable
# ✓ No emergency shutdowns
# ✓ RPC connected
# ✅ ALL CHECKS PASSED
```

**Verify Telegram alert received:**
- Check your Telegram
- Should receive "Bot started on mainnet" message
- If not, check Telegram configuration

### Phase 3: Intensive Monitoring (First 24 Hours)

#### Hour 1: Critical Watch Period

**Every 15 minutes:**
```bash
# Quick health check
./scripts/mainnet_health_check.sh

# Watch for:
# - Bot still running
# - No critical errors
# - Opportunities being detected (maybe)
# - No unexpected transactions
```

**Verify balances haven't changed unexpectedly:**
```bash
./scripts/check_balances.py

# Compare with initial balances
# Should only change if trades executed
```

**Check Telegram constantly:**
- Alerts should be working
- Watch for any error notifications

#### Hour 2-4: First Trades

**The bot may execute first trades:**
```bash
# Check for trades
grep "Trade" logs/mainnet_bot.log

# For each trade, verify:
# - Was it profitable?
# - Was slippage acceptable?
# - Did risk management work?

# Generate first report
./scripts/generate_report.py data/metrics.json
```

**If first trade is a loss:**
- DON'T PANIC (occasional losses are normal)
- Verify it was within slippage tolerance
- Check if it triggered loss tracking
- Continue monitoring
- If multiple consecutive losses, investigate

#### Hour 4-8: Pattern Monitoring

```bash
# Every 1-2 hours:

# 1. Health check
./scripts/mainnet_health_check.sh

# 2. Generate report
./scripts/generate_report.py data/metrics.json

# 3. Check cumulative P/L
grep "Net Profit" report_*.md

# 4. Verify risk management
grep "Circuit breaker\|Loss limit" logs/mainnet_bot.log

# 5. Check for error patterns
grep "ERROR" logs/mainnet_bot.log | sort | uniq -c
```

**Look for:**
- ✅ Consistent opportunity detection
- ✅ Reasonable success rate (>60%)
- ✅ Positive or break-even P/L
- ✅ No repeated error types
- ⚠️ Warning signs: high failure rate, repeated errors, excessive gas costs

#### Hour 8-24: Overnight Monitoring

**Before bed (if running overnight):**
```bash
# Final check before sleep
./scripts/mainnet_health_check.sh
./scripts/generate_report.py data/metrics.json

# Ensure Telegram alerts are loud
# Set phone to not silence alerts from your bot
```

**During night:**
- Keep phone nearby
- Wake up for Telegram alerts
- Quick check every 4-6 hours if possible

**Morning check:**
```bash
# First thing in morning
./scripts/mainnet_health_check.sh

# Review overnight activity
grep "Trade" logs/mainnet_bot.log | tail -20

# Generate overnight report
./scripts/generate_report.py data/metrics.json
```

#### Hour 24: First Day Complete ⭐

**Comprehensive 24-hour review:**
```bash
# Generate detailed report
./scripts/generate_report.py data/metrics.json

# Review ALL trades
grep "Trade.*SUCCESS\|Trade.*FAIL" logs/mainnet_bot.log

# Check error summary
grep "ERROR" logs/mainnet_bot.log | wc -l
grep "CRITICAL" logs/mainnet_bot.log | wc -l
# Criticals should be 0

# Verify balances
./scripts/check_balances.py
```

**Complete 24-hour checklist section in:**
`docs/MAINNET_DEPLOYMENT_CHECKLIST.md`

**Key metrics to document:**
- Total trades executed
- Success rate (target: >60%)
- Net P/L (hopefully positive!)
- Gas costs
- Largest trade
- Any issues encountered

**Decision point:**
- ✅ If going well: Continue to Week 1
- ⚠️ If break-even: Continue but investigate
- ❌ If losing: STOP and analyze

### Phase 4: First Week Operation (Days 2-7)

#### Daily Routine

**Morning (within 2 hours of waking):**
```bash
# 1. Health check
./scripts/mainnet_health_check.sh

# 2. Generate daily report
./scripts/generate_report.py data/metrics.json

# 3. Review yesterday's trades
grep "$(date -d yesterday +%Y-%m-%d)" logs/mainnet_bot.log | grep "Trade"

# 4. Check for errors
grep "$(date -d yesterday +%Y-%m-%d)" logs/mainnet_bot.log | grep "ERROR" | wc -l

# 5. Update checklist
# Fill in daily section in MAINNET_DEPLOYMENT_CHECKLIST.md
```

**Evening (before bed):**
```bash
# Quick health check
./scripts/mainnet_health_check.sh

# Generate evening report
./scripts/generate_report.py data/metrics.json

# Verify no issues
grep "CRITICAL\|Emergency" logs/mainnet_bot.log | tail -5
```

**During day:**
- Check Telegram alerts regularly
- Run health check if alert received
- Monitor not constant, but responsive

#### Day 7: First Week Complete ⭐⭐

**Weekly comprehensive review:**
```bash
# Generate week-long report
./scripts/generate_report.py data/metrics.json

# Should show:
# - 7 days uptime
# - Multiple trades (if opportunities found)
# - Success rate trend
# - Net weekly P/L
```

**Complete "Day 7" section in checklist**

**Key decisions:**
1. **If profitable (>$100 weekly profit):**
   - Consider scaling up
   - Increase position size to $250
   - Lower profit threshold to 1.5%
   - Continue monitoring

2. **If break-even (-$50 to +$50):**
   - Keep conservative settings
   - Analyze why break-even
   - Continue for 2nd week
   - Optimize if needed

3. **If losing (<-$50):**
   - STOP immediately
   - Comprehensive loss analysis
   - Fix issues
   - Return to testnet
   - Re-validate before restart

---

## Scaling After First Week

### When to Scale

**Conditions for scaling:**
- ✅ Week 1 net profit >$100
- ✅ No critical errors
- ✅ Success rate >70%
- ✅ Risk management working
- ✅ Stable performance

### How to Scale (Conservative)

```bash
# Edit config/config.json
nano config/config.json

# Change:
# BASE_PROFIT_THRESHOLD: 0.02 → 0.015 (1.5%)
# MAX_POSITION_SIZE_USD: 100 → 250
# DAILY_LOSS_LIMIT_USD: 500 → 1000

# Restart bot to apply
kill $(cat mainnet_bot.pid)
nohup python3 -m src.bot.main > logs/mainnet_bot.log 2>&1 &
echo $! > mainnet_bot.pid

# Monitor closely for next 24 hours!
```

### Gradual Scaling Plan

**Week 1:** $100 positions, 2% threshold
**Week 2:** $250 positions, 1.5% threshold (if Week 1 successful)
**Week 3:** $500 positions, 1% threshold (if Week 2 successful)
**Month 2+:** Scale based on consistent profitability

**Never scale faster than weekly intervals!**

---

## Emergency Procedures

### Emergency Shutdown

**When to emergency shutdown:**
- Multiple consecutive losses (>5)
- Critical error detected
- Unusual behavior
- Rapid money loss
- When in doubt!

**How to emergency shutdown:**
```bash
# Option 1: Kill process
kill $(cat mainnet_bot.pid)

# Option 2: Force kill
kill -9 $(cat mainnet_bot.pid)

# Option 3: Trigger via code
# (If bot still responsive)
# Use admin code through bot interface
```

**After emergency shutdown:**
1. Check logs immediately
2. Identify root cause
3. Document in checklist
4. Fix issue
5. Test fix on testnet
6. Only restart when confident issue resolved

### Bot Crashed

**If bot stops unexpectedly:**
```bash
# Check what happened
tail -200 logs/mainnet_bot.log

# Look for error before crash
grep -B 10 -A 5 "Traceback" logs/mainnet_bot.log | tail -20

# Document crash
echo "$(date): Bot crashed - $(tail -5 logs/mainnet_bot.log)" >> crashes.log

# Fix issue (if obvious)

# Restart
nohup python3 -m src.bot.main > logs/mainnet_bot.log 2>&1 &
echo $! > mainnet_bot.pid

# Monitor closely for 4 hours
```

### Losing Money Fast

**If losing >$100 in short period:**

1. **STOP IMMEDIATELY:**
   ```bash
   kill $(cat mainnet_bot.pid)
   ```

2. **Analyze all recent trades:**
   ```bash
   grep "Trade" logs/mainnet_bot.log | tail -20
   ```

3. **Identify pattern:**
   - High slippage?
   - Failed trades?
   - Gas costs too high?
   - Circuit breaker not working?

4. **Fix root cause**

5. **Test fix on testnet**

6. **Only restart after confident fix works**

### RPC Issues

**If RPC connection failing:**
```bash
# Test RPC manually
curl -X POST https://polygon-rpc.com/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'

# Should return block number

# If fails, switch to backup RPC:
nano .env
# Update POLYGON_RPC_URL to backup

# Restart bot
kill $(cat mainnet_bot.pid)
nohup python3 -m src.bot.main > logs/mainnet_bot.log 2>&1 &
echo $! > mainnet_bot.pid
```

---

## Monitoring Tools Summary

### Quick Reference

```bash
# Health check (run anytime)
./scripts/mainnet_health_check.sh

# Detailed monitoring
./scripts/monitor_bot.py

# Generate report
./scripts/generate_report.py data/metrics.json

# Check balances
./scripts/check_balances.py

# View live logs
tail -f logs/mainnet_bot.log

# Search for errors
grep -i "error\|critical" logs/mainnet_bot.log

# Count trades
grep -c "Trade.*executed" logs/mainnet_bot.log

# Check latest trade
grep "Trade" logs/mainnet_bot.log | tail -1
```

### Checklist Files

- `docs/MAINNET_DEPLOYMENT_CHECKLIST.md` - Complete deployment checklist
- Print or keep open during deployment
- Fill in all sections as you go
- Sign off when complete

---

## Success Criteria

### First 24 Hours
- ✅ No crashes
- ✅ No critical errors
- ✅ Risk management working
- ✅ Net P/L ≥ $0 (break-even or better)

### First Week
- ✅ 7 days stable operation
- ✅ Success rate >60%
- ✅ Net weekly P/L ≥ $0
- ✅ No emergency shutdowns
- ✅ Ready for continued operation or scaling

---

## Common Issues

### No Opportunities Found
**Cause:** Profit threshold too high for mainnet conditions
**Solution:** Lower BASE_PROFIT_THRESHOLD from 0.02 to 0.015 after Week 1

### All Trades Failing
**Cause:** Slippage, gas price, or approval issues
**Solution:**
- Check gas price (may need higher GAS_MULTIPLIER)
- Check slippage tolerance
- Verify token approvals
- Check RPC is fast enough

### High Gas Costs
**Cause:** Gas prices high on Polygon or inefficient strategy
**Solution:**
- Monitor gas costs vs. profits
- May need higher profit threshold
- Consider only trading during lower gas times

### Break-Even Performance
**Cause:** Gas costs eating profits
**Solution:**
- Optimize gas strategy
- Lower gas costs where possible
- May need to trade less frequently but larger size

---

## Final Reminders

**DO:**
- ✅ Monitor constantly first 48 hours
- ✅ Start with conservative settings
- ✅ Use dedicated wallet
- ✅ Keep Telegram alerts enabled
- ✅ Document everything
- ✅ Be patient - scale slowly
- ✅ Stop if losing money

**DON'T:**
- ❌ Skip testnet validation
- ❌ Use large position sizes initially
- ❌ Scale too quickly
- ❌ Ignore warning signs
- ❌ Leave unmonitored for long periods
- ❌ Use personal wallet
- ❌ Disable risk management

---

## Next Steps

After successful first week on mainnet:

1. **Continue Operations** (if profitable/break-even)
   - Follow daily monitoring routine
   - Generate weekly reports
   - Scale gradually if appropriate

2. **Optimize** (Task 7.3 - future)
   - Analyze performance patterns
   - Optimize parameters
   - Improve profitability

3. **Document Learnings**
   - What worked well?
   - What didn't work?
   - What would you change?

---

## Support and Resources

**Documentation:**
- `README.md` - Project overview
- `docs/DEPLOYMENT.md` - General deployment guide
- `docs/TROUBLESHOOTING.md` - Troubleshooting common issues
- `docs/CONFIGURATION.md` - Configuration reference
- `docs/MAINNET_DEPLOYMENT_CHECKLIST.md` - Deployment checklist

**Scripts:**
- `scripts/prepare_mainnet.sh` - Preparation
- `scripts/deploy_mainnet.sh` - Deployment with safety checks
- `scripts/mainnet_health_check.sh` - Health monitoring
- `scripts/monitor_bot.py` - Detailed monitoring
- `scripts/generate_report.py` - Reports
- `scripts/check_balances.py` - Balance checking

**Getting Help:**
- Review documentation thoroughly
- Check troubleshooting guide
- Analyze logs carefully
- Test fixes on testnet first

---

## Conclusion

Mainnet deployment is the culmination of all your preparation work. Take it seriously, follow the checklists, monitor intensively, and be ready to stop if things go wrong.

**Remember:**
- You've built a solid foundation with security audits and testnet validation
- You have comprehensive monitoring and emergency procedures
- You're starting conservatively to minimize risk
- Success comes from patience, monitoring, and gradual scaling

**Good luck with your mainnet deployment! 🚀💰**

---

**Document Version:** 1.0
**Created:** December 26, 2025
**Last Updated:** December 26, 2025
