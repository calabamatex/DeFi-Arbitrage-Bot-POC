# 48-Hour Testnet Validation Checklist

## Validation Information

**Start Date/Time:** ___________________
**Expected End Date/Time:** ___________________
**Validator Name:** ___________________
**Environment:** Testnet (Polygon Mumbai or Amoy)

---

## Pre-Start Validation

### Initial Setup (Before Starting Bot)

- [ ] ✅ Security audit completed and passed
- [ ] ✅ All tests passing (42+ tests)
- [ ] ✅ Testnet deployment script passed all checks
- [ ] .env configured for testnet environment
- [ ] Sufficient testnet MATIC in wallet (5+ MATIC)
- [ ] Testnet tokens available for trading
- [ ] Telegram bot configured and tested
- [ ] Monitoring scripts setup and tested
- [ ] Backup of configuration created
- [ ] logs/, data/, backups/ directories exist

**Configuration Verification:**
- [ ] ENVIRONMENT = "testnet"
- [ ] BASE_PROFIT_THRESHOLD: _______ (Recommend: 0.005-0.01)
- [ ] MAX_POSITION_SIZE_USD: _______ (Recommend: 10-50)
- [ ] DAILY_LOSS_LIMIT_USD: _______ (Recommend: 100-200)
- [ ] MAX_CONSECUTIVE_LOSSES: _______ (Recommend: 5)
- [ ] CHECK_INTERVAL_SECONDS: _______ (Recommend: 30)

**Pre-Start Notes:**
_________________________________________________________________
_________________________________________________________________

---

## Validation Start

**Bot Started At:** ___________________
**Initial Process ID:** ___________________
**Initial MATIC Balance:** ___________________ MATIC
**Initial Token Balances:** ___________________

---

## Hourly Quick Checks (Every 1 Hour)

### Hour 1: ___:___
- [ ] Bot still running
- [ ] No critical errors in logs
- [ ] RPC connection active

### Hour 2: ___:___
- [ ] Bot still running
- [ ] No critical errors in logs
- [ ] RPC connection active

### Hour 3: ___:___
- [ ] Bot still running
- [ ] No critical errors in logs
- [ ] RPC connection active

### Hour 4: ___:___
- [ ] Bot still running
- [ ] No critical errors in logs
- [ ] RPC connection active

### Hour 5: ___:___
- [ ] Bot still running
- [ ] No critical errors in logs
- [ ] RPC connection active

### Hour 6: ___:___
- [ ] Bot still running
- [ ] No critical errors in logs
- [ ] RPC connection active
- [ ] **→ PROCEED TO DETAILED 6-HOUR CHECK #1**

---

## Detailed 6-Hour Checks

### 6-Hour Check #1 (Hour 6)

**Time:** ___________________

#### System Health
- [ ] Bot process running continuously (no restarts)
- [ ] CPU usage: _______% (Target: <50%)
- [ ] Memory usage: _______ MB (Target: <500MB)
- [ ] Disk space: _______% used (Target: <80%)
- [ ] Uptime: _______ hours

**Notes:**
_________________________________________________________________

#### Log Analysis
- [ ] Total error count in last 6 hours: _______
- [ ] Critical errors: _______ (Target: 0)
- [ ] Warning count: _______
- [ ] RPC timeout errors: _______
- [ ] Transaction errors: _______

**Most Common Errors (if any):**
_________________________________________________________________
_________________________________________________________________

#### Trading Activity
- [ ] Opportunities detected: _______
- [ ] Trades executed: _______
- [ ] Successful trades: _______
- [ ] Failed trades: _______
- [ ] Success rate: _______% (Target: >80% if trades executed)

**Trade Details:**
_________________________________________________________________

#### Financial Status
- [ ] Current MATIC balance: _______ MATIC
- [ ] MATIC spent on gas: _______ MATIC
- [ ] Net profit/loss: $_______ USD
- [ ] Largest single trade: $_______ USD
- [ ] Average trade size: $_______ USD

**Financial Notes:**
_________________________________________________________________

#### Risk Management
- [ ] Position limits respected (no violations)
- [ ] Loss limits respected (no violations)
- [ ] Circuit breaker NOT triggered
- [ ] No emergency shutdowns
- [ ] All risk checks functional

**Risk Events:**
_________________________________________________________________

#### Performance Metrics
- [ ] Average opportunity detection time: _______ seconds (Target: <2s)
- [ ] Average trade execution time: _______ seconds (Target: <5s)
- [ ] RPC calls per minute: _______ (Target: <100)
- [ ] Cache hit rate: _______% (Target: >50%)

**Performance Notes:**
_________________________________________________________________

#### Issues & Concerns
- [ ] No issues identified
- [ ] Issues identified (describe below)

**Issues:**
_________________________________________________________________
_________________________________________________________________

**Actions Taken:**
_________________________________________________________________
_________________________________________________________________

---

### Hour 7-12: Quick Checks

**Hour 7:** ___:___ - [ ] Running [ ] No critical errors
**Hour 8:** ___:___ - [ ] Running [ ] No critical errors
**Hour 9:** ___:___ - [ ] Running [ ] No critical errors
**Hour 10:** ___:___ - [ ] Running [ ] No critical errors
**Hour 11:** ___:___ - [ ] Running [ ] No critical errors
**Hour 12:** ___:___ - [ ] Running [ ] No critical errors

**→ PROCEED TO DETAILED 6-HOUR CHECK #2**

---

### 6-Hour Check #2 (Hour 12)

**Time:** ___________________

#### System Health
- [ ] Bot process running continuously (no restarts)
- [ ] CPU usage: _______% (Target: <50%)
- [ ] Memory usage: _______ MB (Target: <500MB)
- [ ] Disk space: _______% used (Target: <80%)
- [ ] Uptime: _______ hours

**Notes:**
_________________________________________________________________

#### Log Analysis
- [ ] Total error count (hours 6-12): _______
- [ ] Critical errors: _______ (Target: 0)
- [ ] Warning count: _______
- [ ] RPC timeout errors: _______
- [ ] Transaction errors: _______

**Most Common Errors (if any):**
_________________________________________________________________
_________________________________________________________________

#### Trading Activity
- [ ] Opportunities detected (hours 6-12): _______
- [ ] Trades executed (hours 6-12): _______
- [ ] Successful trades: _______
- [ ] Failed trades: _______
- [ ] Success rate: _______%

**Trade Details:**
_________________________________________________________________

#### Financial Status
- [ ] Current MATIC balance: _______ MATIC
- [ ] MATIC spent on gas (total): _______ MATIC
- [ ] Net profit/loss (total): $_______ USD
- [ ] Largest single trade: $_______ USD
- [ ] Average trade size: $_______ USD

**Financial Notes:**
_________________________________________________________________

#### Risk Management
- [ ] Position limits respected
- [ ] Loss limits respected
- [ ] Circuit breaker NOT triggered
- [ ] No emergency shutdowns
- [ ] All risk checks functional

**Risk Events:**
_________________________________________________________________

#### Performance Metrics
- [ ] Average detection time: _______ seconds
- [ ] Average execution time: _______ seconds
- [ ] RPC calls per minute: _______
- [ ] Cache hit rate: _______%

**Performance Notes:**
_________________________________________________________________

#### Issues & Concerns
- [ ] No issues identified
- [ ] Issues identified (describe below)

**Issues:**
_________________________________________________________________
_________________________________________________________________

**Actions Taken:**
_________________________________________________________________
_________________________________________________________________

---

### Hour 13-18: Quick Checks

**Hour 13:** ___:___ - [ ] Running [ ] No critical errors
**Hour 14:** ___:___ - [ ] Running [ ] No critical errors
**Hour 15:** ___:___ - [ ] Running [ ] No critical errors
**Hour 16:** ___:___ - [ ] Running [ ] No critical errors
**Hour 17:** ___:___ - [ ] Running [ ] No critical errors
**Hour 18:** ___:___ - [ ] Running [ ] No critical errors

**→ PROCEED TO DETAILED 6-HOUR CHECK #3**

---

### 6-Hour Check #3 (Hour 18)

**Time:** ___________________

#### System Health
- [ ] Bot process running continuously (no restarts)
- [ ] CPU usage: _______% (Target: <50%)
- [ ] Memory usage: _______ MB (Target: <500MB)
- [ ] Disk space: _______% used (Target: <80%)
- [ ] Uptime: _______ hours

**Notes:**
_________________________________________________________________

#### Log Analysis
- [ ] Total error count (hours 12-18): _______
- [ ] Critical errors: _______ (Target: 0)
- [ ] Warning count: _______
- [ ] RPC timeout errors: _______
- [ ] Transaction errors: _______

**Most Common Errors (if any):**
_________________________________________________________________
_________________________________________________________________

#### Trading Activity
- [ ] Opportunities detected (hours 12-18): _______
- [ ] Trades executed (hours 12-18): _______
- [ ] Successful trades: _______
- [ ] Failed trades: _______
- [ ] Success rate: _______%

**Trade Details:**
_________________________________________________________________

#### Financial Status
- [ ] Current MATIC balance: _______ MATIC
- [ ] MATIC spent on gas (total): _______ MATIC
- [ ] Net profit/loss (total): $_______ USD
- [ ] Largest single trade: $_______ USD
- [ ] Average trade size: $_______ USD

**Financial Notes:**
_________________________________________________________________

#### Risk Management
- [ ] Position limits respected
- [ ] Loss limits respected
- [ ] Circuit breaker NOT triggered
- [ ] No emergency shutdowns
- [ ] All risk checks functional

**Risk Events:**
_________________________________________________________________

#### Performance Metrics
- [ ] Average detection time: _______ seconds
- [ ] Average execution time: _______ seconds
- [ ] RPC calls per minute: _______
- [ ] Cache hit rate: _______%

**Performance Notes:**
_________________________________________________________________

#### Issues & Concerns
- [ ] No issues identified
- [ ] Issues identified (describe below)

**Issues:**
_________________________________________________________________
_________________________________________________________________

**Actions Taken:**
_________________________________________________________________
_________________________________________________________________

---

### Hour 19-24: Quick Checks

**Hour 19:** ___:___ - [ ] Running [ ] No critical errors
**Hour 20:** ___:___ - [ ] Running [ ] No critical errors
**Hour 21:** ___:___ - [ ] Running [ ] No critical errors
**Hour 22:** ___:___ - [ ] Running [ ] No critical errors
**Hour 23:** ___:___ - [ ] Running [ ] No critical errors
**Hour 24:** ___:___ - [ ] Running [ ] No critical errors

**→ PROCEED TO DETAILED 6-HOUR CHECK #4 (24-HOUR MILESTONE)**

---

### 6-Hour Check #4 (Hour 24) - 24-HOUR MILESTONE

**Time:** ___________________

#### System Health
- [ ] Bot process running continuously (no restarts)
- [ ] CPU usage: _______% (Target: <50%)
- [ ] Memory usage: _______ MB (Target: <500MB)
- [ ] Disk space: _______% used (Target: <80%)
- [ ] Uptime: _______ hours

**Notes:**
_________________________________________________________________

#### Log Analysis
- [ ] Total error count (hours 18-24): _______
- [ ] Critical errors: _______ (Target: 0)
- [ ] Warning count: _______
- [ ] RPC timeout errors: _______
- [ ] Transaction errors: _______

**Most Common Errors (if any):**
_________________________________________________________________
_________________________________________________________________

#### Trading Activity
- [ ] Opportunities detected (hours 18-24): _______
- [ ] Trades executed (hours 18-24): _______
- [ ] Successful trades: _______
- [ ] Failed trades: _______
- [ ] Success rate: _______%

**24-Hour Totals:**
- [ ] Total opportunities: _______
- [ ] Total trades: _______
- [ ] Overall success rate: _______%

#### Financial Status
- [ ] Current MATIC balance: _______ MATIC
- [ ] MATIC spent on gas (total): _______ MATIC
- [ ] Net profit/loss (total): $_______ USD
- [ ] Largest single trade: $_______ USD
- [ ] Average trade size: $_______ USD

**Financial Notes:**
_________________________________________________________________

#### Risk Management
- [ ] Position limits respected
- [ ] Loss limits respected
- [ ] Circuit breaker NOT triggered
- [ ] No emergency shutdowns
- [ ] All risk checks functional

**Risk Events:**
_________________________________________________________________

#### Performance Metrics
- [ ] Average detection time: _______ seconds
- [ ] Average execution time: _______ seconds
- [ ] RPC calls per minute: _______
- [ ] Cache hit rate: _______%

**Performance Notes:**
_________________________________________________________________

#### 24-Hour Assessment
- [ ] No critical issues in first 24 hours
- [ ] Performance within targets
- [ ] Risk management functional
- [ ] Continue to 48 hours: YES / NO

**Issues & Concerns:**
_________________________________________________________________
_________________________________________________________________

**Actions Taken:**
_________________________________________________________________
_________________________________________________________________

**Decision:** [ ] Continue to 48 hours [ ] Stop and fix issues

---

### Hour 25-30: Quick Checks

**Hour 25:** ___:___ - [ ] Running [ ] No critical errors
**Hour 26:** ___:___ - [ ] Running [ ] No critical errors
**Hour 27:** ___:___ - [ ] Running [ ] No critical errors
**Hour 28:** ___:___ - [ ] Running [ ] No critical errors
**Hour 29:** ___:___ - [ ] Running [ ] No critical errors
**Hour 30:** ___:___ - [ ] Running [ ] No critical errors

**→ PROCEED TO DETAILED 6-HOUR CHECK #5**

---

### 6-Hour Check #5 (Hour 30)

**Time:** ___________________

#### System Health
- [ ] Bot process running continuously (no restarts)
- [ ] CPU usage: _______% (Target: <50%)
- [ ] Memory usage: _______ MB (Target: <500MB)
- [ ] Disk space: _______% used (Target: <80%)
- [ ] Uptime: _______ hours

**Notes:**
_________________________________________________________________

#### Log Analysis
- [ ] Total error count (hours 24-30): _______
- [ ] Critical errors: _______ (Target: 0)
- [ ] Warning count: _______
- [ ] RPC timeout errors: _______
- [ ] Transaction errors: _______

**Most Common Errors (if any):**
_________________________________________________________________
_________________________________________________________________

#### Trading Activity
- [ ] Opportunities detected (hours 24-30): _______
- [ ] Trades executed (hours 24-30): _______
- [ ] Successful trades: _______
- [ ] Failed trades: _______
- [ ] Success rate: _______%

#### Financial Status
- [ ] Current MATIC balance: _______ MATIC
- [ ] MATIC spent on gas (total): _______ MATIC
- [ ] Net profit/loss (total): $_______ USD

#### Risk Management
- [ ] Position limits respected
- [ ] Loss limits respected
- [ ] Circuit breaker NOT triggered
- [ ] No emergency shutdowns

#### Performance Metrics
- [ ] Average detection time: _______ seconds
- [ ] Average execution time: _______ seconds
- [ ] RPC calls per minute: _______
- [ ] Cache hit rate: _______%

#### Issues & Concerns
- [ ] No issues identified
- [ ] Issues identified (describe below)

**Issues:**
_________________________________________________________________

**Actions Taken:**
_________________________________________________________________

---

### Hour 31-36: Quick Checks

**Hour 31:** ___:___ - [ ] Running [ ] No critical errors
**Hour 32:** ___:___ - [ ] Running [ ] No critical errors
**Hour 33:** ___:___ - [ ] Running [ ] No critical errors
**Hour 34:** ___:___ - [ ] Running [ ] No critical errors
**Hour 35:** ___:___ - [ ] Running [ ] No critical errors
**Hour 36:** ___:___ - [ ] Running [ ] No critical errors

**→ PROCEED TO DETAILED 6-HOUR CHECK #6**

---

### 6-Hour Check #6 (Hour 36)

**Time:** ___________________

#### System Health
- [ ] Bot process running continuously (no restarts)
- [ ] CPU usage: _______% (Target: <50%)
- [ ] Memory usage: _______ MB (Target: <500MB)
- [ ] Disk space: _______% used (Target: <80%)
- [ ] Uptime: _______ hours

**Notes:**
_________________________________________________________________

#### Log Analysis
- [ ] Total error count (hours 30-36): _______
- [ ] Critical errors: _______ (Target: 0)
- [ ] Warning count: _______
- [ ] RPC timeout errors: _______
- [ ] Transaction errors: _______

**Most Common Errors (if any):**
_________________________________________________________________
_________________________________________________________________

#### Trading Activity
- [ ] Opportunities detected (hours 30-36): _______
- [ ] Trades executed (hours 30-36): _______
- [ ] Successful trades: _______
- [ ] Failed trades: _______
- [ ] Success rate: _______%

#### Financial Status
- [ ] Current MATIC balance: _______ MATIC
- [ ] MATIC spent on gas (total): _______ MATIC
- [ ] Net profit/loss (total): $_______ USD

#### Risk Management
- [ ] Position limits respected
- [ ] Loss limits respected
- [ ] Circuit breaker NOT triggered
- [ ] No emergency shutdowns

#### Performance Metrics
- [ ] Average detection time: _______ seconds
- [ ] Average execution time: _______ seconds
- [ ] RPC calls per minute: _______
- [ ] Cache hit rate: _______%

#### Issues & Concerns
- [ ] No issues identified
- [ ] Issues identified (describe below)

**Issues:**
_________________________________________________________________

**Actions Taken:**
_________________________________________________________________

---

### Hour 37-42: Quick Checks

**Hour 37:** ___:___ - [ ] Running [ ] No critical errors
**Hour 38:** ___:___ - [ ] Running [ ] No critical errors
**Hour 39:** ___:___ - [ ] Running [ ] No critical errors
**Hour 40:** ___:___ - [ ] Running [ ] No critical errors
**Hour 41:** ___:___ - [ ] Running [ ] No critical errors
**Hour 42:** ___:___ - [ ] Running [ ] No critical errors

**→ PROCEED TO DETAILED 6-HOUR CHECK #7**

---

### 6-Hour Check #7 (Hour 42)

**Time:** ___________________

#### System Health
- [ ] Bot process running continuously (no restarts)
- [ ] CPU usage: _______% (Target: <50%)
- [ ] Memory usage: _______ MB (Target: <500MB)
- [ ] Disk space: _______% used (Target: <80%)
- [ ] Uptime: _______ hours

**Notes:**
_________________________________________________________________

#### Log Analysis
- [ ] Total error count (hours 36-42): _______
- [ ] Critical errors: _______ (Target: 0)
- [ ] Warning count: _______
- [ ] RPC timeout errors: _______
- [ ] Transaction errors: _______

**Most Common Errors (if any):**
_________________________________________________________________
_________________________________________________________________

#### Trading Activity
- [ ] Opportunities detected (hours 36-42): _______
- [ ] Trades executed (hours 36-42): _______
- [ ] Successful trades: _______
- [ ] Failed trades: _______
- [ ] Success rate: _______%

#### Financial Status
- [ ] Current MATIC balance: _______ MATIC
- [ ] MATIC spent on gas (total): _______ MATIC
- [ ] Net profit/loss (total): $_______ USD

#### Risk Management
- [ ] Position limits respected
- [ ] Loss limits respected
- [ ] Circuit breaker NOT triggered
- [ ] No emergency shutdowns

#### Performance Metrics
- [ ] Average detection time: _______ seconds
- [ ] Average execution time: _______ seconds
- [ ] RPC calls per minute: _______
- [ ] Cache hit rate: _______%

#### Issues & Concerns
- [ ] No issues identified
- [ ] Issues identified (describe below)

**Issues:**
_________________________________________________________________

**Actions Taken:**
_________________________________________________________________

---

### Hour 43-48: Quick Checks

**Hour 43:** ___:___ - [ ] Running [ ] No critical errors
**Hour 44:** ___:___ - [ ] Running [ ] No critical errors
**Hour 45:** ___:___ - [ ] Running [ ] No critical errors
**Hour 46:** ___:___ - [ ] Running [ ] No critical errors
**Hour 47:** ___:___ - [ ] Running [ ] No critical errors
**Hour 48:** ___:___ - [ ] Running [ ] No critical errors

**→ PROCEED TO FINAL 6-HOUR CHECK #8 (48-HOUR COMPLETION)**

---

### 6-Hour Check #8 (Hour 48) - FINAL VALIDATION

**Time:** ___________________

#### System Health
- [ ] Bot process running continuously (no restarts)
- [ ] CPU usage: _______% (Target: <50%)
- [ ] Memory usage: _______ MB (Target: <500MB)
- [ ] Disk space: _______% used (Target: <80%)
- [ ] Uptime: _______ hours

**Notes:**
_________________________________________________________________

#### Log Analysis
- [ ] Total error count (hours 42-48): _______
- [ ] Critical errors: _______ (Target: 0)
- [ ] Warning count: _______
- [ ] RPC timeout errors: _______
- [ ] Transaction errors: _______

**Most Common Errors (if any):**
_________________________________________________________________
_________________________________________________________________

#### Trading Activity
- [ ] Opportunities detected (hours 42-48): _______
- [ ] Trades executed (hours 42-48): _______
- [ ] Successful trades: _______
- [ ] Failed trades: _______
- [ ] Success rate: _______%

**48-Hour Totals:**
- [ ] Total opportunities: _______
- [ ] Total trades: _______
- [ ] Overall success rate: _______%

#### Financial Status
- [ ] Current MATIC balance: _______ MATIC
- [ ] MATIC spent on gas (total): _______ MATIC
- [ ] Net profit/loss (total): $_______ USD
- [ ] ROI: _______%

#### Risk Management
- [ ] Position limits respected (all 48 hours)
- [ ] Loss limits respected (all 48 hours)
- [ ] Circuit breaker NOT triggered
- [ ] No emergency shutdowns
- [ ] All risk checks functional

#### Performance Metrics
- [ ] Average detection time: _______ seconds
- [ ] Average execution time: _______ seconds
- [ ] RPC calls per minute: _______
- [ ] Cache hit rate: _______%

---

## Final Validation Assessment

### Stop Bot and Generate Final Report

**Bot Stopped At:** ___________________
**Total Runtime:** _______ hours

Run the analysis script:
```bash
python scripts/analyze_validation_run.py
```

### Critical Success Criteria

#### Must Pass (Critical)
- [ ] No crashes or unexpected restarts for 48 hours
- [ ] Zero critical errors in logs
- [ ] No emergency shutdowns triggered
- [ ] All risk management systems functional
- [ ] RPC connectivity stable throughout
- [ ] Performance within targets (detection <2s, execution <5s)
- [ ] Memory stable (<500MB, no leaks)
- [ ] CPU usage reasonable (<80% average)

#### Should Pass (Important)
- [ ] Success rate >80% (if opportunities found)
- [ ] No position limit violations
- [ ] No loss limit violations
- [ ] Error rate <5% of total operations
- [ ] Telegram alerts working
- [ ] Metrics collection working
- [ ] Logs properly formatted and complete

#### Nice to Have (Optional)
- [ ] Profitable on testnet
- [ ] Multiple successful trades
- [ ] Cache hit rate >50%
- [ ] Fast average execution time

---

## Go/No-Go Decision for Mainnet

### Assessment Summary

**Critical Issues Found:** _______ (Must be 0 to proceed)
**Important Issues Found:** _______ (Should be 0 to proceed)
**Minor Issues Found:** _______

**Overall Stability:** [ ] Excellent [ ] Good [ ] Fair [ ] Poor

**Performance:** [ ] Above Target [ ] At Target [ ] Below Target

**Risk Management:** [ ] Fully Functional [ ] Mostly Functional [ ] Issues Found

### Final Decision

**MAINNET DEPLOYMENT DECISION:** [ ] GO [ ] NO-GO

**Decision Rationale:**
_________________________________________________________________
_________________________________________________________________
_________________________________________________________________
_________________________________________________________________

**If NO-GO, Required Actions:**
_________________________________________________________________
_________________________________________________________________
_________________________________________________________________

**If GO, Mainnet Configuration Recommendations:**
_________________________________________________________________
_________________________________________________________________
_________________________________________________________________

---

## Sign-Off

**Validation Completed By:** ___________________
**Date:** ___________________
**Signature:** ___________________

**Reviewed By (if applicable):** ___________________
**Date:** ___________________
**Signature:** ___________________

---

## Appendix: Command Reference

### Start Validation Run
```bash
# Start bot
python src/bot/main.py

# Or use deployment script
./scripts/deploy_testnet.sh
```

### Monitor During Run
```bash
# Automated monitoring (run every 30 min via cron)
./scripts/validation_monitor.sh

# Manual checks
./scripts/monitor_bot.py
./scripts/check_balances.py
```

### Check Logs
```bash
# View recent logs
tail -f logs/bot.log

# Search for errors
grep -i "error" logs/bot.log | tail -20
grep -i "critical" logs/bot.log
```

### Generate Reports
```bash
# Metrics report
python scripts/generate_report.py

# Final analysis (after 48 hours)
python scripts/analyze_validation_run.py
```

### Emergency Stop
```bash
# Find process
ps aux | grep "python.*main.py"

# Stop gracefully
kill <PID>

# Force stop if needed
kill -9 <PID>
```

---

**END OF VALIDATION CHECKLIST**
