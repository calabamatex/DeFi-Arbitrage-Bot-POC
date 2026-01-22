# Scaling Strategy

## Overview

This document outlines the strategy for gradually scaling the bot's operations from initial conservative settings to optimized performance based on real data and proven profitability.

**Key Principle:** Scale gradually, based on data, with ability to rollback.

---

## Scaling Principles

### 1. Data-Driven Decision Making
- Scale only with proof of profitability
- Require minimum data period (1 week per level)
- Track key metrics for each scaling level
- Compare performance before/after scaling

### 2. Gradual Incremental Increases
- Small steps reduce risk
- Maximum 2x increase per step
- Wait 1 week minimum between increases
- Validate each level before next increase

### 3. Reversible Changes
- Always backup configuration before changes
- Can quickly rollback if issues arise
- Document rollback procedures
- Test rollback process

### 4. Close Monitoring
- Intensive monitoring during scale-up
- Watch for degraded performance
- Quick response to issues
- Daily review during scaling period

---

## Scaling Schedule

### Week 1: Initial Operation (Baseline)

**Configuration:**
```json
{
  "MAX_POSITION_SIZE_USD": 100,
  "BASE_PROFIT_THRESHOLD": "0.02",
  "DAILY_LOSS_LIMIT_USD": 500,
  "MAX_CONSECUTIVE_LOSSES": 3,
  "SLIPPAGE_TOLERANCE": "0.003"
}
```

**Goal:** Prove stability and basic profitability
**Success Criteria:**
- No crashes for 7 days
- Success rate >60%
- Net profit ≥ $0 (break-even or better)
- No emergency shutdowns
- Risk management working

**Monitoring:**
- Check 2x daily
- Generate daily reports
- Document all trades
- Track error patterns

**End of Week Decision:**
- ✅ PASS: Proceed to Week 2 scaling
- ⚠️ MARGINAL: Continue Week 1 settings, optimize
- ❌ FAIL: Return to testnet, fix issues

---

### Week 2: First Increase

**Pre-Scaling Checklist:**
- [ ] Week 1 net profit >$50
- [ ] Success rate >65%
- [ ] No critical errors
- [ ] Risk management validated
- [ ] Team confident to scale

**Configuration Changes:**
```json
{
  "MAX_POSITION_SIZE_USD": 250,        // +150% increase
  "BASE_PROFIT_THRESHOLD": "0.015",   // -25% (find more opportunities)
  "DAILY_LOSS_LIMIT_USD": 750,        // +50% (proportional to position size)
  "MAX_CONSECUTIVE_LOSSES": 3,        // Keep same (conservative)
  "SLIPPAGE_TOLERANCE": "0.003"       // Keep same initially
}
```

**Goal:** Validate scalability, increase profit
**Expected Impact:**
- More opportunities (lower threshold)
- Higher profit per trade (larger positions)
- ~2-3x increase in daily profit potential

**Success Criteria:**
- Net profit >Week 1 profit
- Success rate maintained (>60%)
- No increase in error rate
- Risk limits respected

**Monitoring:**
- Check 3x daily for first 3 days
- Then 2x daily for remainder
- Compare metrics to Week 1
- Watch for degradation

**Rollback Triggers:**
- Success rate drops below 50%
- 2 consecutive losing days
- Multiple system errors
- Circuit breaker triggers frequently

---

### Week 3: Second Increase

**Pre-Scaling Checklist:**
- [ ] Week 2 net profit >Week 1 profit
- [ ] Success rate maintained or improved
- [ ] No major issues
- [ ] Positive performance trend
- [ ] Team confident

**Configuration Changes:**
```json
{
  "MAX_POSITION_SIZE_USD": 500,        // +100% increase
  "BASE_PROFIT_THRESHOLD": "0.01",    // -33% (more aggressive)
  "DAILY_LOSS_LIMIT_USD": 1000,       // +33% increase
  "MAX_CONSECUTIVE_LOSSES": 3,        // Keep same
  "SLIPPAGE_TOLERANCE": "0.005"       // Slight increase if needed
}
```

**Goal:** Optimize profit while maintaining success rate
**Expected Impact:**
- Significantly more opportunities
- Higher total daily profit
- Potentially lower per-trade profit margin

**Success Criteria:**
- Net profit >Week 2 profit
- Success rate >55% (slight tolerance for more aggressive strategy)
- Efficient execution
- Risk management effective

**Monitoring:**
- Daily detailed review
- Watch profit/trade ratio
- Monitor gas cost impact
- Verify risk limits effective

---

### Week 4: Third Increase

**Pre-Scaling Checklist:**
- [ ] Week 3 net profit >Week 2 profit
- [ ] Success rate acceptable (>55%)
- [ ] System stable
- [ ] Risk management proven
- [ ] Ready for target operations

**Configuration Changes:**
```json
{
  "MAX_POSITION_SIZE_USD": 1000,       // +100% increase
  "BASE_PROFIT_THRESHOLD": "0.008",   // -20% (highly aggressive)
  "DAILY_LOSS_LIMIT_USD": 2000,       // +100% increase
  "MAX_CONSECUTIVE_LOSSES": 3,        // Consider 4 if data supports
  "SLIPPAGE_TOLERANCE": "0.005"       // Adjust based on Week 3 data
}
```

**Goal:** Reach target operational level
**Expected Impact:**
- Maximum opportunity capture
- Highest daily profit potential
- May need more capital deployed

**Success Criteria:**
- Net profit >Week 3 profit
- Success rate >50% (acceptable for aggressive strategy)
- ROI meets targets
- Sustainable operations

---

### Month 2+: Optimization Phase

**Configuration Range:**
```json
{
  "MAX_POSITION_SIZE_USD": 2000-5000,   // Based on capital and performance
  "BASE_PROFIT_THRESHOLD": "0.005-0.008", // Fine-tuned
  "DAILY_LOSS_LIMIT_USD": 3000-5000,     // Risk-appropriate
  "MAX_CONSECUTIVE_LOSSES": 3-5,         // Based on data
  "SLIPPAGE_TOLERANCE": "0.005-0.008"    // Market-dependent
}
```

**Goal:** Maximize ROI while managing risk
**Activities:**
- Continuous optimization
- A/B testing strategies
- Advanced techniques
- Market condition adaptation

**Focus Areas:**
1. Time-based optimization
2. Token pair selection
3. DEX routing optimization
4. Gas cost reduction
5. Execution speed improvement

---

## Scaling Criteria Matrix

### Before Each Scale-Up

| Criterion | Minimum | Target | Excellent |
|-----------|---------|--------|-----------|
| Previous Period Net Profit | $0 | $50+ | $200+ |
| Success Rate | >50% | >60% | >75% |
| Days Without Critical Error | 7 | 14 | 30 |
| Circuit Breaker Triggers | <3 | <2 | 0 |
| Team Confidence | Medium | High | Very High |

**All "Minimum" criteria must be met to scale.**
**Prefer "Target" or better before scaling.**

---

## Rollback Criteria

### Immediate Rollback Triggers
Scale back immediately if ANY occur:
- 3+ consecutive losing days
- Success rate drops below 40%
- Multiple critical system errors
- Emergency shutdown triggered
- Daily loss limit hit repeatedly
- Position limits violated
- Team uncomfortable

### Rollback Procedure
```bash
# 1. Stop bot immediately
kill $(cat mainnet_bot.pid)

# 2. Restore previous configuration
cp config/config.backup.json config/config.json

# 3. Document rollback reason
echo "$(date): Rollback to previous config - REASON" >> rollback.log

# 4. Restart with previous settings
nohup python3 -m src.bot.main > logs/mainnet_bot.log 2>&1 &

# 5. Monitor closely
./scripts/mainnet_health_check.sh

# 6. Analyze what went wrong
./scripts/analyze_performance.py

# 7. Fix issues before attempting scale-up again
```

---

## Position Size Recommendations by Capital

### Conservative Strategy (Recommended)

| Trading Capital | Position Size | Daily Limit | Profit Threshold |
|----------------|---------------|-------------|------------------|
| $1,000 | $50 | $200 | 2.0% |
| $2,500 | $100 | $500 | 1.5% |
| $5,000 | $250 | $750 | 1.2% |
| $10,000 | $500 | $1,000 | 1.0% |
| $25,000 | $1,000 | $2,000 | 0.8% |
| $50,000 | $2,000 | $3,000 | 0.6% |
| $100,000+ | $5,000 | $5,000 | 0.5% |

### Moderate Strategy

| Trading Capital | Position Size | Daily Limit | Profit Threshold |
|----------------|---------------|-------------|------------------|
| $1,000 | $100 | $300 | 1.5% |
| $2,500 | $250 | $750 | 1.2% |
| $5,000 | $500 | $1,000 | 1.0% |
| $10,000 | $1,000 | $2,000 | 0.8% |
| $25,000 | $2,500 | $4,000 | 0.6% |
| $50,000 | $5,000 | $6,000 | 0.5% |
| $100,000+ | $10,000 | $8,000 | 0.4% |

### Aggressive Strategy (Only After Proven Success)

| Trading Capital | Position Size | Daily Limit | Profit Threshold |
|----------------|---------------|-------------|------------------|
| $1,000 | $200 | $500 | 1.0% |
| $2,500 | $500 | $1,000 | 0.8% |
| $5,000 | $1,000 | $2,000 | 0.6% |
| $10,000 | $2,000 | $3,000 | 0.5% |
| $25,000 | $5,000 | $5,000 | 0.4% |
| $50,000 | $10,000 | $8,000 | 0.3% |
| $100,000+ | $20,000 | $10,000 | 0.2% |

**Important Notes:**
- Start with Conservative strategy
- Move to Moderate only after 4+ weeks of consistent profitability
- Move to Aggressive only after 3+ months of proven success
- Never exceed 10% of capital in single position
- Never exceed 20% of capital in daily loss limit

---

## Risk Management During Scaling

### Position Size Limits
- Never increase position size more than 2x per step
- Wait minimum 1 week between increases
- Keep max position ≤10% of total capital
- Adjust loss limits proportionally

### Success Rate Monitoring
- Track success rate daily
- Alert if drops >10% from baseline
- Rollback if drops >20% from baseline
- Investigate any sudden changes

### Loss Limits
- Keep daily loss limit ≤20% of capital
- Keep weekly loss limit ≤40% of capital
- Adjust circuit breaker sensitivity during scaling
- Monitor closely for limit violations

### Circuit Breaker Tuning
- Start conservative (3 consecutive losses)
- Can increase to 4-5 after proven success
- Reset to 3 during market volatility
- Always err on side of caution

---

## Scaling Timeline Example

### Scenario: $5,000 Starting Capital

**Week 1: Initial**
- Position: $100
- Threshold: 2%
- Expected daily profit: $5-20
- Goal: Prove stability

**Week 2: First Scale**
- Position: $250
- Threshold: 1.5%
- Expected daily profit: $15-50
- Goal: Validate scalability

**Week 3: Second Scale**
- Position: $500
- Threshold: 1%
- Expected daily profit: $30-100
- Goal: Optimize profit

**Week 4: Third Scale**
- Position: $1,000
- Threshold: 0.8%
- Expected daily profit: $50-200
- Goal: Target operations

**Month 2+: Optimization**
- Position: $1,500-2,000
- Threshold: 0.5-0.7%
- Expected daily profit: $100-300
- Goal: Maximize ROI

**Total Expected Growth:**
- Month 1 profit: $500-1,500
- Month 2 profit: $2,000-6,000 (if optimal)
- ROI: 10-30% per month (excellent case)

---

## Monitoring During Scaling

### Daily Checks (During Scaling Period)
```bash
# Morning routine
./scripts/mainnet_health_check.sh
./scripts/generate_report.py data/metrics.json

# Compare to previous period
grep "Success Rate" report_*.md | tail -7

# Check for degradation
./scripts/analyze_performance.py
```

### Key Metrics to Watch
1. **Success Rate** - Must not drop significantly
2. **Profit per Trade** - Should remain positive
3. **Gas Cost Ratio** - Gas/profit should be <20%
4. **Error Rate** - Should not increase
5. **Execution Time** - Should remain fast

### Red Flags
- ⚠️ Success rate drops >10%
- ⚠️ Multiple failing trades in row
- ⚠️ Increasing error frequency
- ⚠️ Gas costs eating profits
- ⚠️ Slower execution times
- ⚠️ Risk limits frequently hit

---

## Documentation During Scaling

### Scaling Log Template

```
Date: ___________
Scaling Step: Week X → Week Y

Previous Configuration:
- Position Size: $___
- Profit Threshold: ___%
- Daily Loss Limit: $___

New Configuration:
- Position Size: $___
- Profit Threshold: ___%
- Daily Loss Limit: $___

Previous Period Performance:
- Net Profit: $_____
- Success Rate: ____%
- Trades: _____
- Issues: _____

Scaling Rationale:
_________________________________

Expected Impact:
_________________________________

Monitoring Plan:
_________________________________

Rollback Triggers:
_________________________________
```

---

## Advanced Scaling Techniques

### A/B Testing
- Run two configurations simultaneously
- Split capital 50/50
- Compare performance over 1 week
- Adopt better performing config

### Adaptive Scaling
- Automatically adjust based on performance
- Increase position size after X profitable days
- Decrease after Y losing days
- Requires automation

### Market-Condition-Based Scaling
- Scale up during favorable conditions
- Scale back during volatility
- Monitor market indicators
- Adapt strategy accordingly

---

## Conclusion

Scaling is a gradual, data-driven process. Success comes from:
- 📊 **Data-driven decisions** - Scale based on proof
- 🐢 **Patience** - Don't rush scaling
- 📈 **Monitoring** - Watch metrics closely
- 🛡️ **Risk management** - Protect capital first
- 🔄 **Adaptability** - Rollback when needed

**Remember:** It's better to scale too slowly than too quickly!

---

**Document Version:** 1.0
**Created:** December 26, 2025
**Last Updated:** December 26, 2025
