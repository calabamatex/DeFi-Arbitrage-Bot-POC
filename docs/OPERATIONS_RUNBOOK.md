# Operations Runbook

## Overview

This runbook provides standard operating procedures for running and maintaining the Polygon Arbitrage Bot on an ongoing basis after successful initial deployment.

**Target Audience:** Operations team, bot operators
**Scope:** Daily, weekly, monthly operations and incident response
**Version:** 1.0
**Last Updated:** December 26, 2025

---

## Table of Contents

1. [Daily Operations](#daily-operations)
2. [Weekly Operations](#weekly-operations)
3. [Monthly Operations](#monthly-operations)
4. [Incident Response](#incident-response)
5. [Maintenance Procedures](#maintenance-procedures)
6. [Performance Optimization](#performance-optimization)
7. [Emergency Contacts](#emergency-contacts)

---

## Daily Operations

### Morning Routine (Every Day, 30 minutes)

**Time:** Within 2 hours of start of trading day

#### 1. Health Check (5 minutes)
```bash
# Check bot is running
./scripts/monitor_bot.py

# Quick health check
./scripts/mainnet_health_check.sh

# Expected output: ✅ ALL CHECKS PASSED
```

**If bot not running:**
- Check logs for crash reason
- Follow [Bot Stopped](#bot-stopped) procedure
- Document incident

#### 2. Review Overnight Activity (10 minutes)
```bash
# View recent logs
tail -500 logs/mainnet_bot.log

# Check for errors
grep -i "error\|critical" logs/mainnet_bot.log | tail -20

# Review overnight trades
grep "Trade" logs/mainnet_bot.log | grep "$(date -d yesterday +%Y-%m-%d)"
```

**What to look for:**
- ✅ Trades executing normally
- ✅ No critical errors
- ✅ No emergency shutdowns
- ⚠️ Any unusual patterns
- ⚠️ Repeated error types

####

 3. Generate Daily Report (5 minutes)
```bash
# Generate metrics report
./scripts/generate_report.py data/metrics.json

# Save with date
cp report_*.md reports/daily_$(date +%Y%m%d).md
```

**Review key metrics:**
- Net P/L for last 24 hours
- Success rate
- Number of trades
- Error count
- Resource usage

#### 4. Check Balances (5 minutes)
```bash
# Check wallet balances
./scripts/check_balances.py

# Compare to yesterday's balances
cat balances_history.log | tail -7
```

**Verify:**
- MATIC balance sufficient (>3 MATIC)
- Token balances reasonable
- No unexpected large changes
- Balances match expected from trades

#### 5. Review Telegram Alerts (3 minutes)
- Check Telegram for overnight alerts
- Review any error notifications
- Verify no missed critical alerts

#### 6. Document Day (2 minutes)
```bash
# Add to operations log
echo "$(date +%Y-%m-%d): Checked. Status: OK. Trades: X, P/L: $X.XX, Issues: None" >> operations.log

# Or if issues:
echo "$(date +%Y-%m-%d): Checked. Status: ISSUE. Details: ..." >> operations.log
```

### Evening Routine (Every Day, 15 minutes)

**Time:** Before end of trading day

#### 1. End-of-Day Report (10 minutes)
```bash
# Generate EOD report
./scripts/generate_report.py data/metrics.json

# Review full day
grep "$(date +%Y-%m-%d)" logs/mainnet_bot.log | grep "Trade" | wc -l

# Check error summary
grep "$(date +%Y-%m-%d)" logs/mainnet_bot.log | grep -i "error" | wc -l
```

#### 2. Final Health Check (3 minutes)
```bash
./scripts/mainnet_health_check.sh
```

#### 3. Evening Documentation (2 minutes)
```bash
# Update operations log
echo "$(date +%Y-%m-%d) EOD: Trades: X, Success: X%, P/L: $X.XX" >> operations.log
```

### Mid-Day Check (Optional, 10 minutes)

**Recommended during first month**

```bash
# Quick status check
./scripts/mainnet_health_check.sh

# Check recent activity
tail -100 logs/mainnet_bot.log
```

---

## Weekly Operations

### Monday: Weekly Review (1 hour)

#### 1. Generate Weekly Report
```bash
# Generate comprehensive report
./scripts/generate_report.py data/metrics.json

# Compare to previous week
diff reports/weekly_$(date -d '7 days ago' +%Y%m%d).md reports/weekly_$(date +%Y%m%d).md
```

#### 2. Analyze Performance
```bash
# Run performance analysis
./scripts/analyze_performance.py

# Review recommendations
cat performance_analysis_$(date +%Y%m%d).txt
```

#### 3. Review All Trades
```bash
# Extract all trades from past week
grep "Trade" logs/mainnet_bot.log | grep "2025-XX" > weekly_trades.log

# Analyze:
# - Most profitable pairs
# - Most common failures
# - Best performing times
# - DEX success rates
```

#### 4. Financial Reconciliation
```bash
# Check balances
./scripts/check_balances.py

# Compare to last week
# Calculate net change
# Verify matches reported P/L
```

#### 5. Update Trading Log
```markdown
## Week of [Date]

**Performance:**
- Trades: XXX
- Success Rate: XX%
- Net P/L: $XXX.XX
- Best Day: [Day] ($XX.XX)
- Worst Day: [Day] ($-XX.XX)

**Issues:**
- [List any issues encountered]

**Optimizations:**
- [Any changes made]

**Notes:**
- [Observations, learnings]
```

### Wednesday: Mid-Week Health Check (30 minutes)

#### 1. System Health
```bash
# Full health check
./scripts/monitor_bot.py

# Check resource trends
# - CPU usage over time
# - Memory usage over time
# - Disk space
```

#### 2. Review Open Issues
- Check issue tracker
- Update status of ongoing issues
- Prioritize for resolution

#### 3. Dependency Check
```bash
# Check for outdated dependencies
pip list --outdated

# Note any critical updates
# Plan update schedule
```

#### 4. Test Emergency Procedures
```bash
# Verify backup script works
./scripts/backup_config.sh

# Test Telegram alerts
python3 << 'EOF'
from src.utils.telegram_alerts import send_telegram_alert
import asyncio
asyncio.run(send_telegram_alert("🧪 Weekly alert test"))
EOF

# Check monitoring tools
./scripts/mainnet_health_check.sh
```

### Friday: Week Wrap-Up (30 minutes)

#### 1. Prepare Weekend Monitoring
- Ensure Telegram alerts working
- Verify phone notifications enabled
- Document weekend contact rotation

#### 2. Document Week's Learnings
```markdown
## Learnings - Week of [Date]

**What Worked Well:**
- [List successes]

**What Didn't Work:**
- [List challenges]

**Action Items:**
- [What to change/improve]

**Questions/Research:**
- [Topics to investigate]
```

#### 3. Plan Next Week
- Any configuration changes planned?
- Any testing to be done?
- Any optimizations to implement?

---

## Monthly Operations

### First Monday of Month: Comprehensive Review (2-3 hours)

#### 1. Generate Monthly Report
```bash
# Month-long metrics
./scripts/generate_report.py data/metrics.json

# Save monthly report
cp report_*.md reports/monthly_$(date +%Y%m).md
```

#### 2. Full Performance Analysis
```bash
# Deep performance analysis
./scripts/analyze_performance.py

# Identify optimization opportunities
./scripts/optimize_config.py

# A/B test planning
```

**Analyze:**
- Monthly P/L trend
- Success rate trend
- Best/worst performing pairs
- Gas cost trends
- Optimal trading times
- DEX performance comparison

#### 3. Security Audit
```bash
# Run security scan
./scripts/security_scan.sh

# Should show: ✅ All security checks passed

# Review:
# - No exposed secrets
# - File permissions correct
# - Dependencies secure
# - No security TODOs
```

#### 4. Dependency Updates
```bash
# Check for updates
pip list --outdated

# For each outdated package:
# 1. Review changelog
# 2. Check for breaking changes
# 3. Test on testnet first
# 4. Update if safe

# Update process:
pip install --upgrade <package>==<version>
pip freeze > requirements.txt

# Test thoroughly before mainnet update
```

#### 5. Configuration Review
```bash
# Review current configuration
cat config/config.json

# Compare to optimized recommendations
./scripts/optimize_config.py

# Questions to ask:
# - Are thresholds still appropriate?
# - Should position sizes change?
# - Are risk limits still correct?
# - Any new pairs to monitor?
```

#### 6. Backup Verification
```bash
# List backups
ls -lh backups/

# Verify recent backups exist
ls -lh backups/ | head -10

# Test backup restoration (on testnet)
# 1. Copy backup to testnet
# 2. Restore configuration
# 3. Verify bot starts
# 4. Verify configuration correct
```

#### 7. Financial Reconciliation
```markdown
## Monthly Reconciliation - [Month Year]

**Opening Balance:** $XXXX.XX
**Closing Balance:** $XXXX.XX

**Trading P/L:** $XXX.XX
**Gas Costs:** $XX.XX
**Net P/L:** $XXX.XX

**Trades Executed:** XXX
**Success Rate:** XX%
**Average Profit/Trade:** $X.XX

**ROI:** XX%

**Notes:**
- [Any discrepancies]
- [Unusual events]
- [Explanations]
```

### Monthly Strategy Review

#### Review Questions:
1. **Is the bot profitable?**
   - Yes → Continue, consider scaling
   - No → Analyze why, optimize or stop

2. **Is success rate acceptable?**
   - >70% → Excellent
   - 60-70% → Good
   - 50-60% → Acceptable
   - <50% → Needs optimization

3. **Are current pairs optimal?**
   - Which pairs are most profitable?
   - Which pairs should be removed?
   - Any new pairs to add?

4. **Is configuration optimal?**
   - Should thresholds change?
   - Should position sizes scale?
   - Should risk limits adjust?

5. **Are there new opportunities?**
   - New DEXs to integrate?
   - New strategies to test?
   - New optimizations to implement?

---

## Incident Response

### Bot Stopped

**Symptoms:** Bot process not running

**Immediate Actions:**
```bash
# 1. Check if process exists
ps aux | grep "python.*main.py"

# 2. Check logs for crash reason
tail -200 logs/mainnet_bot.log

# 3. Look for error before crash
grep -B 10 -A 5 "Traceback" logs/mainnet_bot.log | tail -20
```

**Common Causes & Solutions:**

1. **Out of Memory**
   - Symptom: "MemoryError" or "Killed"
   - Solution: Restart bot, investigate memory leak

2. **Network Error**
   - Symptom: RPC connection errors
   - Solution: Verify RPC endpoint, use backup if needed

3. **Unhandled Exception**
   - Symptom: Python traceback in logs
   - Solution: Fix bug, add error handling

**Recovery:**
```bash
# 1. Document crash
echo "$(date): Bot crashed - $(tail -5 logs/mainnet_bot.log)" >> incidents.log

# 2. Fix issue if known
# ... apply fix ...

# 3. Restart bot
nohup python3 -m src.bot.main > logs/mainnet_bot.log 2>&1 &
echo $! > mainnet_bot.pid

# 4. Monitor closely for 1 hour
watch -n 60 './scripts/mainnet_health_check.sh'
```

### Loss Limit Hit

**Symptoms:** Daily or weekly loss limit reached

**Immediate Actions:**
```bash
# 1. Check current status
./scripts/monitor_bot.py

# 2. Review recent trades
grep "Trade" logs/mainnet_bot.log | tail -20

# 3. Check loss tracking
grep "Loss limit" logs/mainnet_bot.log
```

**Analysis Questions:**
- Why did losses occur?
- Are they within normal variance?
- Is there a systemic issue?
- Should strategy change?

**Actions:**
1. If normal variance → Wait for reset
2. If systemic issue → Stop bot, fix, restart
3. If market conditions → Wait for better conditions

### Circuit Breaker Triggered

**Symptoms:** Consecutive loss limit reached, bot paused

**Immediate Actions:**
```bash
# 1. Review consecutive losses
grep "consecutive loss" logs/mainnet_bot.log | tail -10

# 2. Analyze each losing trade
# - What went wrong?
# - Slippage too tight?
# - Gas price too high?
# - Market conditions poor?
```

**Recovery:**
```bash
# Option 1: Wait for auto-reset
# Circuit breaker will reset after cooldown period

# Option 2: Manual reset (if safe)
# Use admin code to reset
# Only if losses explained and not systemic

# Option 3: Stop and fix
# If systemic issue identified
kill $(cat mainnet_bot.pid)
# Fix issue
# Test on testnet
# Restart on mainnet
```

### Security Incident

**Types:**
- Unauthorized access attempt
- Compromised API keys
- Suspicious transactions
- Unusual activity

**IMMEDIATE ACTIONS:**
```bash
# 1. STOP BOT IMMEDIATELY
kill $(cat mainnet_bot.pid)

# 2. Secure wallet
# If wallet compromised:
# - Transfer funds to new secure wallet
# - Revoke all approvals
# - Generate new private key

# 3. Review all transactions
# Check on PolygonScan:
# - All transactions from wallet
# - Any unauthorized transactions?
# - Any suspicious contract interactions?

# 4. Assess damage
# - Funds lost?
# - Data compromised?
# - Access points breached?

# 5. Fix vulnerability
# - Update credentials
# - Patch security hole
# - Enhance security measures

# 6. Full security audit
./scripts/security_scan.sh

# 7. Resume only when safe
# - All vulnerabilities fixed
# - New security measures in place
# - Tested thoroughly
```

### RPC Issues

**Symptoms:** Connection errors, timeouts, slow responses

**Immediate Actions:**
```bash
# Test RPC manually
curl -X POST https://polygon-rpc.com/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'

# Should return block number
```

**Solutions:**

1. **Temporary Issue**
   - Wait 5-10 minutes
   - RPC provider may be experiencing issues

2. **Provider Down**
   - Switch to backup RPC:
   ```bash
   nano .env
   # Update POLYGON_RPC_URL
   ```
   - Restart bot

3. **Rate Limited**
   - Check rate limit status
   - Upgrade RPC plan if needed
   - Reduce check frequency temporarily

---

## Maintenance Procedures

### Updating Dependencies

```bash
# 1. Check for updates (weekly)
pip list --outdated

# 2. For each update, review:
# - Changelog
# - Breaking changes
# - Security fixes

# 3. Test on testnet FIRST
# a. Update testnet
pip install --upgrade <package>==<version>
pip freeze > requirements.txt

# b. Restart testnet bot
# c. Monitor for 24 hours
# d. Verify no issues

# 4. Apply to mainnet (if testnet successful)
# a. Backup current environment
cp requirements.txt requirements.backup.txt

# b. Update mainnet
pip install --upgrade <package>==<version>
pip freeze > requirements.txt

# c. Restart mainnet bot
kill $(cat mainnet_bot.pid)
nohup python3 -m src.bot.main > logs/mainnet_bot.log 2>&1 &

# d. Monitor closely for 24 hours
```

### Log Management

```bash
# Weekly: Rotate logs
cd logs/
gzip bot.log.1
mv bot.log bot.log.1
# Bot will create new bot.log

# Monthly: Archive old logs
tar -czf logs_archive_$(date +%Y%m).tar.gz bot.log.*
mv logs_archive_*.tar.gz archives/

# Quarterly: Delete very old logs
find archives/ -name "logs_archive_*.tar.gz" -mtime +180 -delete
```

### Backup Management

```bash
# Daily: Auto-backup
./scripts/backup_config.sh

# Weekly: Verify backups
ls -lh backups/ | head -10

# Monthly: Test backup restoration

# Quarterly: Offsite backup
# Copy critical backups to secure offsite location
scp backups/backup_$(date +%Y%m%d)*.tar.gz user@backup-server:/backups/
```

### Configuration Updates

```bash
# Process for updating configuration:

# 1. Generate optimized config
./scripts/optimize_config.py

# 2. Review recommendations
cat config/config.optimized.json

# 3. Test on testnet (RECOMMENDED)
scp config/config.optimized.json testnet:~/bot/config/config.json
# Restart testnet bot
# Monitor for 24 hours

# 4. Backup current mainnet config
cp config/config.json config/config.backup.$(date +%Y%m%d).json

# 5. Apply to mainnet
cp config/config.optimized.json config/config.json

# 6. Restart bot
kill $(cat mainnet_bot.pid)
nohup python3 -m src.bot.main > logs/mainnet_bot.log 2>&1 &

# 7. Monitor closely for 24-48 hours
./scripts/mainnet_health_check.sh
```

---

## Performance Optimization

### Weekly Optimization Process

```bash
# 1. Analyze performance
./scripts/analyze_performance.py

# 2. Identify opportunities
# Review output for:
# - Underperforming pairs
# - Gas optimization opportunities
# - Time-based patterns
# - Success rate issues

# 3. Generate optimizations
./scripts/optimize_config.py

# 4. A/B test if possible
# Run two configurations side-by-side
# Compare results after 1 week

# 5. Implement successful changes
# Apply better performing configuration
```

### Continuous Improvement Cycle

1. **Measure** - Collect performance data
2. **Analyze** - Identify optimization opportunities
3. **Hypothesize** - Form improvement hypothesis
4. **Test** - Test on testnet or small scale
5. **Implement** - Apply if successful
6. **Monitor** - Watch for improvements
7. **Repeat** - Continue cycle

---

## Emergency Contacts

### Primary Contact
**Name:** ___________________
**Phone:** ___________________
**Email:** ___________________
**Telegram:** ___________________
**Availability:** 24/7 first month, then on-call

### Backup Contact
**Name:** ___________________
**Phone:** ___________________
**Email:** ___________________
**Telegram:** ___________________
**Availability:** Backup coverage

### Escalation Procedure

1. **Minor Issue** (bot stopped, small loss)
   - Primary contact handles
   - Document in operations log
   - Resolve within 1 hour

2. **Moderate Issue** (repeated failures, moderate loss)
   - Primary contact notifies backup
   - Joint troubleshooting
   - Resolve within 4 hours

3. **Major Issue** (security incident, large loss)
   - Both contacts engaged immediately
   - Emergency procedures activated
   - External expertise if needed

### External Contacts

**RPC Provider Support:**
Provider: ___________________
Support: ___________________
URL: ___________________

**Exchange/Wallet Support:**
Provider: ___________________
Support: ___________________

---

## Appendix: Quick Reference Commands

```bash
# Health checks
./scripts/monitor_bot.py
./scripts/mainnet_health_check.sh

# Reports
./scripts/generate_report.py data/metrics.json

# Analysis
./scripts/analyze_performance.py

# Optimization
./scripts/optimize_config.py

# Balances
./scripts/check_balances.py

# Logs
tail -f logs/mainnet_bot.log
grep -i "error" logs/mainnet_bot.log | tail -20

# Backup
./scripts/backup_config.sh

# Restart
kill $(cat mainnet_bot.pid)
nohup python3 -m src.bot.main > logs/mainnet_bot.log 2>&1 &
echo $! > mainnet_bot.pid
```

---

**Document Version:** 1.0
**Created:** December 26, 2025
**Last Updated:** December 26, 2025
**Next Review:** Monthly
