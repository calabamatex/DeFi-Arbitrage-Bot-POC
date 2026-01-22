# Mainnet Deployment Checklist

## Pre-Deployment (Complete ALL before proceeding)

### Validation Results
- [ ] 48-hour testnet run completed successfully
- [ ] No crashes during validation
- [ ] Performance metrics met targets
- [ ] Success rate >60% (if opportunities found)
- [ ] No critical errors
- [ ] Analysis script gave GO recommendation

**Validation Report File:** ___________________
**Validation Decision:** [ ] GO [ ] NO-GO
**Date Completed:** ___________________

### Configuration
- [ ] .env.mainnet created with mainnet keys
- [ ] ENVIRONMENT=mainnet verified
- [ ] Conservative settings in config.mainnet.json
- [ ] All contract addresses verified on PolygonScan
- [ ] Telegram bot tested on mainnet
- [ ] Admin code set and secure (12+ characters)

**Contract Addresses Verified:**
- [ ] Uniswap V3 Router: 0xE592427A0AEce92De3Edee1F18E0157C05861564
- [ ] SushiSwap Router: 0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506
- [ ] QuickSwap Router: 0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff

### Funding
- [ ] Mainnet wallet created (DEDICATED wallet, not personal)
- [ ] Private key backed up securely (offline, encrypted)
- [ ] Wallet funded with 5+ MATIC for gas
- [ ] Trading tokens deposited (\$1000+ recommended)
- [ ] All balances verified with check_balances.py

**Wallet Address:** ___________________
**Initial MATIC Balance:** ___________________ MATIC
**Initial Trading Capital:** $___________________
**Backup Location:** ___________________

### Security
- [ ] Security audit completed (SECURITY_REPORT.md)
- [ ] No critical vulnerabilities found
- [ ] .env.mainnet permissions set to 600
- [ ] Server secured (if using VPS)
- [ ] Firewall configured
- [ ] SSH key-only authentication (if VPS)

**Security Audit Status:** [ ] PASS [ ] FAIL
**Audit Date:** ___________________

### Monitoring
- [ ] Telegram alerts working
- [ ] Monitoring scripts tested
- [ ] Metrics collection working
- [ ] Report generation tested
- [ ] Log rotation configured

**Telegram Bot ID:** ___________________
**Test Alert Sent:** [ ] Yes [ ] No

### Team Readiness
- [ ] 24/7 monitoring plan established
- [ ] Emergency contacts identified
- [ ] Emergency shutdown procedure known
- [ ] Response time <1 hour guaranteed
- [ ] Backup person identified

**Primary Monitor:** ___________________
**Backup Monitor:** ___________________
**Emergency Contact:** ___________________

### Documentation
- [ ] All documentation complete (5 docs)
- [ ] Troubleshooting guide reviewed
- [ ] Emergency procedures documented
- [ ] Configuration documented
- [ ] Operations runbook created

---

## Deployment Execution

### Step 1: Final Preparation

**Date:** ___________________
**Time:** ___________________
**Operator:** ___________________

- [ ] Ran ./scripts/prepare_mainnet.sh
- [ ] Edited .env.mainnet with mainnet credentials
- [ ] Set .env.mainnet permissions to 600
- [ ] Reviewed config.mainnet.json settings
- [ ] Completed manual pre-flight checklist

**BASE_PROFIT_THRESHOLD:** _______ (Recommended: 0.02)
**MAX_POSITION_SIZE_USD:** _______ (Recommended: 100)
**DAILY_LOSS_LIMIT_USD:** _______ (Recommended: 500)
**MAX_CONSECUTIVE_LOSSES:** _______ (Recommended: 3)

**Notes:**
_________________________________________________________________

### Step 2: Activate Mainnet Environment

- [ ] Backed up current .env and config.json
- [ ] Copied .env.mainnet to .env
- [ ] Copied config.mainnet.json to config/config.json
- [ ] Verified ENVIRONMENT=mainnet
- [ ] Verified CHAIN_ID=137

**Verification Command:**
```bash
python3 -c "from src.bot.config import load_config; config, env, env_config, settings = load_config(); print(f'Environment: {env}'); print(f'Chain ID: {env_config.get(\"CHAIN_ID\")}')"
```

**Output:**
```
Environment: ___________________
Chain ID: ___________________
```

### Step 3: Pre-Deployment Checks

- [ ] Ran ./scripts/deploy_mainnet.sh
- [ ] All pre-flight checks passed
- [ ] Mainnet RPC connection verified
- [ ] Balance check passed (5+ MATIC)
- [ ] Tests passed (42+ tests)
- [ ] Typed "DEPLOY TO MAINNET" to confirm

**Pre-Flight Results:**
- Python version: ___________________
- Web3.py version: ___________________
- RPC connection: [ ] OK [ ] FAIL
- MATIC balance: ___________________ MATIC
- Tests passed: _____ / 42+

**Time:** ___________________

### Step 4: Start Bot

**Start Time:** ___________________

```bash
# Start bot in background
nohup python3 -m src.bot.main > logs/mainnet_bot.log 2>&1 &

# Record PID
echo $! > mainnet_bot.pid
```

- [ ] Bot started successfully
- [ ] Initial Telegram alert received
- [ ] Logs created (mainnet_bot.log)
- [ ] Monitoring started
- [ ] PID recorded

**Process ID:** ___________________
**Start Command:** ___________________
**Log File:** ___________________

### Step 5: Initial Verification (First 10 minutes)

**Time:** ___________________

- [ ] Bot process running (check with ps)
- [ ] Connecting to DEXes successfully
- [ ] Fetching prices from RPC
- [ ] No immediate critical errors
- [ ] Telegram alerts working
- [ ] Metrics being collected

**Initial Log Review (tail -100 logs/mainnet_bot.log):**
- [ ] "Initialization complete" message seen
- [ ] "Starting arbitrage bot" message seen
- [ ] DEX adapters initialized
- [ ] Risk manager initialized
- [ ] No error messages

**Notes:**
_________________________________________________________________
_________________________________________________________________

---

## Post-Deployment Monitoring

### Hour 1 Check

**Time:** ___________________

- [ ] Bot still running
- [ ] Opportunities being detected
- [ ] No errors in logs
- [ ] Balances unchanged (no unexpected transactions)
- [ ] Metrics updating
- [ ] CPU/Memory usage normal

**Metrics:**
- Opportunities detected: ___________________
- Trades executed: ___________________
- Errors: ___________________
- CPU: _______% (Target: <50%)
- Memory: _______ MB (Target: <500MB)

**Commands Run:**
```bash
./scripts/monitor_bot.py
./scripts/mainnet_health_check.sh
tail -100 logs/mainnet_bot.log
```

**Notes:**
_________________________________________________________________

### Hour 2 Check

**Time:** ___________________

- [ ] Bot stable
- [ ] Trading activity normal
- [ ] No concerning errors
- [ ] Balances tracking correctly

**Cumulative:**
- Opportunities: ___________________
- Trades: ___________________
- Successful: ___________________
- Failed: ___________________

**Notes:**
_________________________________________________________________

### Hour 4 Check

**Time:** ___________________

- [ ] Bot running continuously (no restarts)
- [ ] First trades executed (if opportunities found)
- [ ] All trades profitable or explained losses
- [ ] No concerning error patterns
- [ ] Resource usage stable

**Trading Summary:**
- Total trades: ___________________
- Successful: ___________________
- Success rate: _______%
- Gross profit: $___________________
- Gross loss: $___________________
- Gas costs: $___________________
- Net P/L: $___________________

**Top Errors (if any):**
_________________________________________________________________

**Notes:**
_________________________________________________________________

### Hour 8 Check

**Time:** ___________________

- [ ] Continuous operation for 8 hours
- [ ] Trading pattern normal
- [ ] Success rate acceptable (>60%)
- [ ] No loss limit concerns
- [ ] Generated first detailed report

```bash
./scripts/generate_report.py data/metrics.json
```

**8-Hour Summary:**
- Total opportunities: ___________________
- Total trades: ___________________
- Success rate: _______%
- Net P/L: $___________________
- Largest loss: $___________________
- Circuit breaker triggers: ___________________

**Notes:**
_________________________________________________________________

### Hour 12 Check

**Time:** ___________________

- [ ] Bot stable overnight (if applicable)
- [ ] No unexpected issues
- [ ] Profits tracking correctly
- [ ] Risk management working

**12-Hour Summary:**
- Total trades: ___________________
- Success rate: _______%
- Net P/L: $___________________

**Notes:**
_________________________________________________________________

### Hour 24 Check (First Day Complete) ⭐

**Time:** ___________________

- [ ] Completed first 24 hours successfully
- [ ] Generated comprehensive 24-hour report
- [ ] Reviewed all trades individually
- [ ] Checked complete error log
- [ ] Verified balances match expectations
- [ ] Analyzed performance metrics

**24-Hour Summary:**
- Uptime: _______ hours (Target: 24)
- Total opportunities: ___________________
- Total trades: ___________________
- Successful trades: ___________________
- Failed trades: ___________________
- Success rate: _______% (Target: >60%)

**Financial:**
- Gross profit: $___________________
- Gross loss: $___________________
- Net profit: $___________________
- Gas costs: $___________________
- ROI: _______%

**Performance:**
- Avg detection time: _______ seconds (Target: <2s)
- Avg execution time: _______ seconds (Target: <5s)
- CPU usage: _______% (Target: <50%)
- Memory usage: _______ MB (Target: <500MB)

**Issues Encountered:**
_________________________________________________________________
_________________________________________________________________

**24-Hour Assessment:** [ ] Excellent [ ] Good [ ] Acceptable [ ] Concerning

---

## First Week Monitoring

### Day 2

**Date:** ___________________

- [ ] Bot running normally
- [ ] Performance consistent with Day 1
- [ ] Daily report generated
- [ ] No new error types

**Daily Summary:**
- Trades: ___________________
- Success rate: _______%
- Net P/L: $___________________

**Notes:**
_________________________________________________________________

### Day 3

**Date:** ___________________

- [ ] Bot running normally
- [ ] No new issues
- [ ] Performance tracking

**Daily Summary:**
- Trades: ___________________
- Success rate: _______%
- Net P/L: $___________________

**Notes:**
_________________________________________________________________

### Day 4

**Date:** ___________________

- [ ] Bot running normally
- [ ] Consider position size increase (if profitable)
- [ ] Performance tracking

**Daily Summary:**
- Trades: ___________________
- Success rate: _______%
- Net P/L: $___________________

**Scaling Consideration:**
- Current position size: $___________________
- Proposed increase: $___________________
- Decision: [ ] Increase [ ] Keep same [ ] Decrease

**Notes:**
_________________________________________________________________

### Day 5

**Date:** ___________________

- [ ] Bot running normally
- [ ] Week almost complete
- [ ] Performance tracking

**Daily Summary:**
- Trades: ___________________
- Success rate: _______%
- Net P/L: $___________________

**Notes:**
_________________________________________________________________

### Day 6

**Date:** ___________________

- [ ] Bot running normally
- [ ] Performance tracking

**Daily Summary:**
- Trades: ___________________
- Success rate: _______%
- Net P/L: $___________________

**Notes:**
_________________________________________________________________

### Day 7 (First Week Complete) ⭐⭐

**Date:** ___________________

- [ ] Completed first week successfully
- [ ] Generated comprehensive weekly report
- [ ] Reviewed all weekly metrics
- [ ] Analyzed profitability trends
- [ ] Made scaling decision

**Weekly Summary:**
- Total uptime: _______ hours
- Total opportunities: ___________________
- Total trades: ___________________
- Success rate: _______%
- Average daily trades: ___________________

**Financial:**
- Week gross profit: $___________________
- Week gross loss: $___________________
- Week net profit: $___________________
- Week gas costs: $___________________
- Week ROI: _______%

**Performance:**
- Avg detection time: _______ seconds
- Avg execution time: _______ seconds
- Cache hit rate: _______%
- RPC calls/min: _______

**Risk Management:**
- Circuit breaker triggers: ___________________
- Max consecutive losses: ___________________
- Largest single loss: $___________________
- Position limit violations: ___________________

**Weekly Assessment:** [ ] Excellent [ ] Good [ ] Acceptable [ ] Poor

**Ready to scale:** [ ] YES [ ] NO

**Notes:**
_________________________________________________________________
_________________________________________________________________

---

## Scaling Decision

### If Profitable and Stable (Week Net Profit >$100):

**Recommended Changes:**
- [ ] Increase MAX_POSITION_SIZE_USD from 100 to 250
- [ ] Lower BASE_PROFIT_THRESHOLD from 0.02 to 0.015
- [ ] Increase DAILY_LOSS_LIMIT_USD from 500 to 1000
- [ ] Keep MAX_CONSECUTIVE_LOSSES at 3 (conservative)
- [ ] Continue 2x daily monitoring

**Implementation:**
```bash
# Edit config/config.json
# Update settings as above
# Restart bot to apply changes
```

**New Configuration:**
- BASE_PROFIT_THRESHOLD: _______
- MAX_POSITION_SIZE_USD: _______
- DAILY_LOSS_LIMIT_USD: _______

**Date Applied:** ___________________

### If Break-Even (Week Net Profit -$50 to +$50):

**Actions:**
- [ ] Keep conservative settings unchanged
- [ ] Analyze why break-even (low volume? high gas?)
- [ ] Optimize gas strategy if possible
- [ ] Consider lowering profit threshold slightly (0.015)
- [ ] Continue close monitoring for 2nd week

**Analysis:**
_________________________________________________________________
_________________________________________________________________

**Decision:** [ ] Optimize and continue [ ] Stop and re-evaluate

### If Losing (Week Net Profit <-$50):

**IMMEDIATE ACTIONS:**
- [ ] STOP bot immediately
- [ ] Analyze ALL losses in detail
- [ ] Identify root cause(s)
- [ ] Fix identified issues
- [ ] Return to testnet for validation
- [ ] Re-validate on testnet before restart

**Loss Analysis:**
_________________________________________________________________
_________________________________________________________________
_________________________________________________________________

**Root Cause(s):**
_________________________________________________________________
_________________________________________________________________

**Fixes Applied:**
_________________________________________________________________
_________________________________________________________________

**Re-validation Required:** [ ] YES [ ] NO

---

## Ongoing Operations

### Daily Tasks
- [ ] Review logs for errors
- [ ] Generate daily report
- [ ] Check balances
- [ ] Verify performance metrics
- [ ] Update operations log
- [ ] Check Telegram alerts

**Daily Log Template:**
```
Date: ___________________
Trades: ___________________
Success Rate: _______%
Net P/L: $___________________
Issues: ___________________
Actions Taken: ___________________
```

### Weekly Tasks
- [ ] Generate comprehensive weekly report
- [ ] Review all trades for the week
- [ ] Analyze profitability trends
- [ ] Review risk metrics
- [ ] Update documentation if needed
- [ ] Backup configuration
- [ ] Check for dependency updates

### Monthly Tasks
- [ ] Comprehensive performance review
- [ ] Security audit (run security_scan.sh)
- [ ] Dependency updates (pip list --outdated)
- [ ] Strategy optimization review
- [ ] Financial reconciliation
- [ ] Review and adjust risk parameters

---

## Emergency Procedures

### If Bot Crashes
1. Check logs immediately: `tail -200 logs/mainnet_bot.log`
2. Identify error cause
3. Document crash in operations log
4. Fix issue if obvious
5. Restart bot: `python3 -m src.bot.main`
6. Monitor closely for next 4 hours

### If Losing Money Rapidly
1. STOP bot immediately: `kill $(cat mainnet_bot.pid)`
2. Review recent trades in logs
3. Check if circuit breaker should have triggered
4. Analyze root cause
5. Do NOT restart until issue identified and fixed

### If Emergency Shutdown Triggered
1. Check why it triggered: `grep "Emergency shutdown" logs/mainnet_bot.log`
2. Verify it was appropriate
3. Fix underlying issue
4. Reset using admin code (if safe to continue)
5. Document incident

### If RPC Issues
1. Check RPC connectivity: `curl -X POST https://polygon-rpc.com/ -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'`
2. Switch to backup RPC if available
3. Contact RPC provider if extended outage

---

## Sign-Off

### Deployment Sign-Off

**Deployed By:** ___________________
**Date:** ___________________
**Time:** ___________________
**Signature:** ___________________

### First Week Completion Sign-Off

**Reviewed By:** ___________________
**Date:** ___________________
**Overall Assessment:** [ ] Success [ ] Acceptable [ ] Needs Improvement [ ] Failure
**Continue Operations:** [ ] YES [ ] NO
**Signature:** ___________________

---

## Notes and Observations

_________________________________________________________________
_________________________________________________________________
_________________________________________________________________
_________________________________________________________________
_________________________________________________________________
_________________________________________________________________
_________________________________________________________________
_________________________________________________________________

---

**END OF MAINNET DEPLOYMENT CHECKLIST**
