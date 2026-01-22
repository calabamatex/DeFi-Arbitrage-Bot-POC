# 48-Hour Testnet Validation Guide

## Overview

This guide explains how to perform the critical 48-hour testnet validation run before mainnet deployment. This is your **FINAL** validation before risking real money.

**Created:** December 26, 2025
**Status:** Ready for validation run
**Required Before:** Mainnet deployment

---

## Files Created for Validation

### 1. Automated Monitoring Script
**File:** `scripts/validation_monitor.sh`
**Size:** 7.9 KB (289 lines)
**Purpose:** Automated checks every 30 minutes during the validation run

**What it checks:**
- Bot running status and uptime
- CPU and memory usage
- Recent errors in logs
- Metrics freshness
- Disk space
- RPC connectivity
- Log file sizes

**Usage:**
```bash
# Run manually
./scripts/validation_monitor.sh

# Setup automated monitoring (every 30 minutes)
# Add to crontab:
*/30 * * * * cd /path/to/project && ./scripts/validation_monitor.sh >> logs/validation_monitor.log 2>&1
```

**Outputs:**
- Real-time console output
- `logs/validation_monitor.log` - Check history
- `data/validation_alerts.txt` - Issues found

### 2. Validation Checklist
**File:** `docs/VALIDATION_CHECKLIST.md`
**Size:** 24 KB (880 lines)
**Purpose:** Comprehensive manual checklist for monitoring every 6 hours

**What it includes:**
- Pre-start validation checklist
- Hourly quick checks (48 checks)
- Detailed 6-hour checks (8 comprehensive reviews)
- Success criteria evaluation
- Go/No-Go decision framework
- Sign-off template

**Usage:**
- Print or open in editor
- Check off items as you complete them
- Fill in all measurements and observations
- Complete final assessment
- Make mainnet deployment decision

### 3. Analysis Script
**File:** `scripts/analyze_validation_run.py`
**Size:** 17 KB (542 lines)
**Purpose:** Comprehensive analysis after 48-hour run completes

**What it analyzes:**
- Log files for errors and events
- Metrics data
- Validation monitor results
- Alerts and warnings
- Success criteria compliance

**Usage:**
```bash
# After 48-hour run completes
python scripts/analyze_validation_run.py
```

**Outputs:**
- Console report with color-coded results
- `validation_report_YYYYMMDD_HHMMSS.txt` - Detailed report file
- GO/NO-GO recommendation for mainnet
- Exit code (0 = GO, 1 = NO-GO)

---

## Step-by-Step Validation Process

### Phase 1: Pre-Validation Setup (1 hour)

#### 1.1 Complete Pre-Start Checklist
```bash
# Verify all previous work complete
✓ Security audit passed
✓ All tests passing (42+ tests)
✓ Documentation complete
✓ Testnet deployment script ready
```

#### 1.2 Configure for Testnet
```bash
# Edit .env file
ENVIRONMENT="testnet"
POLYGON_RPC_URL="<your-testnet-rpc>"
# ... other testnet settings

# Recommended testnet settings
BASE_PROFIT_THRESHOLD=0.005  # 0.5% (lower for more activity)
MAX_POSITION_SIZE_USD=10     # Small positions
DAILY_LOSS_LIMIT_USD=100     # Conservative limit
MAX_CONSECUTIVE_LOSSES=5     # More lenient
CHECK_INTERVAL_SECONDS=30    # Frequent checks
```

#### 1.3 Setup Monitoring Automation
```bash
# Option 1: Setup cron job (Linux/Mac)
crontab -e
# Add this line:
*/30 * * * * cd /Users/ethanallen/Desktop/ArbitrageBot_092624/OFF-CHAIN-BOT/101124-project && ./scripts/validation_monitor.sh >> logs/validation_monitor.log 2>&1

# Option 2: Manual monitoring
# Set reminder to run ./scripts/validation_monitor.sh every 30 minutes
```

#### 1.4 Prepare Checklist
```bash
# Print or open checklist
open docs/VALIDATION_CHECKLIST.md
# Or
cat docs/VALIDATION_CHECKLIST.md

# Have it ready to fill out
```

#### 1.5 Final Checks
```bash
# Run deployment script validation
./scripts/deploy_testnet.sh
# Should complete all 11 checks successfully

# Verify sufficient testnet MATIC
python scripts/check_balances.py
# Should show 5+ testnet MATIC
```

### Phase 2: Start Validation Run (Minutes 1-60)

#### 2.1 Record Start Time
```bash
# In VALIDATION_CHECKLIST.md, record:
# - Start date/time
# - Initial balances
# - Initial configuration
```

#### 2.2 Start the Bot
```bash
# Start bot in background
nohup python src/bot/main.py > logs/bot_console.log 2>&1 &

# Record process ID
echo $! > data/bot.pid
ps aux | grep "python.*main.py"
```

#### 2.3 Verify Startup
```bash
# Check logs
tail -f logs/bot.log

# Should see:
# - "Initialization complete"
# - "Starting arbitrage bot"
# - RPC connection successful
# - DEX adapters initialized

# Check first metrics
python scripts/monitor_bot.py
```

#### 2.4 First Manual Check (Hour 1)
- Bot running? ✓
- No critical errors? ✓
- RPC connected? ✓
- Check off in VALIDATION_CHECKLIST.md

### Phase 3: Ongoing Monitoring (Hours 1-48)

#### Every 30 Minutes: Automated Monitoring
```bash
# If using cron, it runs automatically
# If manual, run:
./scripts/validation_monitor.sh
```

#### Every Hour: Quick Manual Check
```bash
# Quick status check
ps aux | grep "python.*main.py"  # Still running?
tail -20 logs/bot.log | grep -i "critical\|error"  # Any issues?

# Check off hourly item in VALIDATION_CHECKLIST.md
```

#### Every 6 Hours: Detailed Review
**Complete full 6-hour checklist section:**

```bash
# Generate current report
python scripts/generate_report.py

# Check system health
./scripts/monitor_bot.py

# Review logs
tail -500 logs/bot.log | grep -i "error"

# Check balances
python scripts/check_balances.py

# Review validation monitor log
tail -100 logs/validation_monitor.log
```

**Fill out in VALIDATION_CHECKLIST.md:**
- System health metrics
- Log analysis
- Trading activity
- Financial status
- Risk management
- Performance metrics
- Issues and concerns

**Critical 6-Hour Checkpoints:**
- Hour 6: First detailed check
- Hour 12: Second check
- Hour 18: Third check
- **Hour 24: 24-HOUR MILESTONE** - Major checkpoint, assess if continuing
- Hour 30: Fifth check
- Hour 36: Sixth check
- Hour 42: Seventh check
- **Hour 48: FINAL VALIDATION** - Complete assessment

#### Special Attention at 24-Hour Milestone
```bash
# Generate comprehensive 24-hour report
python scripts/generate_report.py

# Review all alerts
cat data/validation_alerts.txt

# Assess health
./scripts/monitor_bot.py

# DECISION POINT: Continue to 48 hours?
# Only continue if:
✓ No critical errors
✓ Bot stable
✓ Performance acceptable
✓ Risk management working
```

### Phase 4: Completion and Analysis (Hour 48+)

#### 4.1 Stop the Bot
```bash
# Graceful shutdown
BOT_PID=$(cat data/bot.pid)
kill $BOT_PID

# Verify stopped
ps aux | grep "python.*main.py"

# Record stop time in VALIDATION_CHECKLIST.md
```

#### 4.2 Run Final Analysis
```bash
# Generate comprehensive analysis
python scripts/analyze_validation_run.py

# This will:
# - Analyze all logs
# - Review all metrics
# - Check success criteria
# - Generate detailed report
# - Provide GO/NO-GO recommendation
```

#### 4.3 Review Analysis Results
The analysis will output:

```
================================================================================
                      48-HOUR VALIDATION RUN ANALYSIS
================================================================================

VALIDATION SUMMARY
--------------------------------------------------------------------------------
Runtime: 48.2 hours
Opportunities Found: 145
Trades Executed: 23
Success Rate: 91.3%
Net Profit: $12.45

SUCCESS CRITERIA RESULTS
✓ Passed: 12
⚠ Warnings: 2
✗ Failed: 0

MAINNET DEPLOYMENT DECISION
--------------------------------------------------------------------------------
✓ RECOMMENDATION: GO FOR MAINNET

All critical criteria passed.
Bot is ready for mainnet deployment with conservative settings.
```

#### 4.4 Complete Final Checklist
In `VALIDATION_CHECKLIST.md`:
- Fill out Hour 48 section completely
- Complete "Final Validation Assessment"
- Check all success criteria
- Make Go/No-Go decision
- Sign off

#### 4.5 Save All Results
```bash
# Create validation results archive
mkdir -p validation_results
cp logs/bot.log validation_results/
cp logs/validation_monitor.log validation_results/
cp data/metrics.json validation_results/
cp data/validation_alerts.txt validation_results/
cp validation_report_*.txt validation_results/
cp docs/VALIDATION_CHECKLIST.md validation_results/validation_checklist_completed.md

# Create tarball
tar -czf validation_results_$(date +%Y%m%d).tar.gz validation_results/

echo "Validation results saved to: validation_results_$(date +%Y%m%d).tar.gz"
```

---

## Success Criteria

### Critical (Must Pass)
- [ ] No crashes or unexpected restarts for 48 hours
- [ ] Zero critical errors in logs
- [ ] No emergency shutdowns triggered
- [ ] All risk management systems functional
- [ ] RPC connectivity stable throughout
- [ ] Performance within targets (detection <2s, execution <5s)
- [ ] Memory stable (<500MB, no leaks)
- [ ] CPU usage reasonable (<80% average)

### Important (Should Pass)
- [ ] Success rate >80% (if opportunities found)
- [ ] No position limit violations
- [ ] No loss limit violations
- [ ] Error rate <5% of total operations
- [ ] Telegram alerts working
- [ ] Metrics collection working
- [ ] Logs properly formatted and complete

### Nice to Have (Optional)
- [ ] Profitable on testnet
- [ ] Multiple successful trades
- [ ] Cache hit rate >50%
- [ ] Fast average execution time

---

## Common Issues and Solutions

### Issue: Bot Keeps Restarting
**Symptoms:** Multiple start/stop cycles in logs
**Check:**
```bash
grep "Starting arbitrage bot" logs/bot.log | wc -l
# Should be 1, not multiple
```
**Solutions:**
- Check for uncaught exceptions in logs
- Verify RPC endpoint is stable
- Check system resources (memory/disk)
- Review error messages before restarts

### Issue: No Opportunities Found
**Symptoms:** 0 opportunities after several hours
**Solutions:**
- Lower BASE_PROFIT_THRESHOLD (try 0.003 for testnet)
- Verify DEX contracts are correct for testnet
- Check token pairs are actually trading
- Verify RPC is returning current prices
- Check if testnet DEXs are active

### Issue: All Trades Failing
**Symptoms:** Opportunities found but all trades fail
**Solutions:**
- Check gas estimation (may need to increase GAS_MULTIPLIER)
- Verify token approvals
- Check slippage tolerance (may need to increase)
- Verify wallet has sufficient MATIC for gas
- Check token balances are sufficient

### Issue: High Memory Usage
**Symptoms:** Memory grows over time, exceeds 500MB
**Possible causes:**
- Price cache growing too large
- Metrics history not trimmed
- Log handlers accumulating
**Solutions:**
- Check cache settings in price_cache.py
- Review metrics rolling window size
- Implement log rotation

### Issue: Monitoring Script Failing
**Symptoms:** validation_monitor.sh exits with errors
**Solutions:**
```bash
# Run manually to see errors
./scripts/validation_monitor.sh

# Common fixes:
# - Ensure jq installed: brew install jq (Mac) or apt-get install jq (Linux)
# - Check file permissions: chmod +x scripts/validation_monitor.sh
# - Verify Python installed: python3 --version
```

---

## After Validation: Next Steps

### If PASS (GO for Mainnet)

1. **Review Analysis Report**
   - Read complete `validation_report_*.txt`
   - Understand any warnings
   - Note any edge cases encountered

2. **Prepare Mainnet Configuration**
   ```bash
   # Copy .env to .env.mainnet
   cp .env .env.mainnet

   # Edit .env.mainnet with conservative settings:
   ENVIRONMENT="mainnet"
   BASE_PROFIT_THRESHOLD=0.02  # 2%
   MAX_POSITION_SIZE_USD=100
   DAILY_LOSS_LIMIT_USD=500
   MAX_CONSECUTIVE_LOSSES=3
   CHECK_INTERVAL_SECONDS=30
   ```

3. **Complete Pre-Mainnet Checklist**
   - Verify mainnet RPC endpoint
   - Ensure mainnet MATIC (5+)
   - Setup 24/7 monitoring
   - Brief team on procedures
   - Have emergency contacts ready

4. **Proceed to Task 7.2**
   - Follow mainnet deployment guide
   - Use `./scripts/deploy_mainnet.sh`
   - Start with conservative settings
   - Monitor intensively first 24 hours

### If FAIL (NO-GO for Mainnet)

1. **Review Failures**
   - Read all failure messages in analysis report
   - Identify root causes
   - Prioritize critical issues

2. **Fix Issues**
   - Address each failure systematically
   - Update code/configuration as needed
   - Run unit tests to verify fixes
   - Update documentation if needed

3. **Re-run Validation**
   - Complete another 48-hour validation run
   - Follow same procedure
   - Verify all issues resolved

4. **Do NOT Proceed to Mainnet**
   - Wait until all issues resolved
   - Complete successful 48-hour run
   - Get PASS recommendation

---

## Tips for Successful Validation

### Before Starting
- [ ] Clear all old logs: `rm -rf logs/*`
- [ ] Clear old data: `rm -rf data/*`
- [ ] Fresh start for clean results
- [ ] Ensure stable internet connection
- [ ] Have backup power if needed

### During Validation
- [ ] Set calendar reminders for 6-hour checks
- [ ] Keep terminal/logs easily accessible
- [ ] Don't modify code or configuration during run
- [ ] Document any anomalies immediately
- [ ] Take screenshots of issues

### Monitoring Tips
- Use `tmux` or `screen` to keep terminal sessions open
- Setup Telegram alerts for critical issues
- Check validation_monitor.log regularly
- Watch for patterns in errors
- Compare metrics across 6-hour periods

### Best Practices
- Don't intervene unless critical
- Let the bot handle normal situations
- Only emergency stop if absolutely necessary
- Document everything in checklist
- Be honest in assessment

---

## File Reference

### Created Files
```
scripts/validation_monitor.sh        # Automated monitoring (7.9 KB)
docs/VALIDATION_CHECKLIST.md         # Manual checklist (24 KB)
scripts/analyze_validation_run.py    # Analysis script (17 KB)
VALIDATION_GUIDE.md                  # This guide
```

### Generated During Validation
```
logs/bot.log                         # Main bot log
logs/bot_console.log                 # Console output
logs/validation_monitor.log          # Monitor checks
data/validation_alerts.txt           # Issues found
data/metrics.json                    # Latest metrics
data/bot.pid                         # Process ID
validation_report_*.txt              # Final analysis
```

---

## Summary

You now have everything needed for the 48-hour validation run:

1. **Automated monitoring** runs every 30 minutes
2. **Manual checklist** guides you every 6 hours
3. **Analysis script** evaluates final results
4. **This guide** explains the entire process

**CRITICAL REMINDERS:**
- This is your FINAL validation before mainnet
- Do NOT skip or rush this step
- Be thorough and honest in assessment
- Do NOT deploy to mainnet with a NO-GO
- Start mainnet conservatively even with GO

**Next Task:** Task 7.2 - Mainnet Deployment (only after PASS)

Good luck with your validation run! 🚀

---

**Document Version:** 1.0
**Created:** December 26, 2025
**Last Updated:** December 26, 2025
