# Flash Loan Arbitrage Bot - Quick Start Guide

## 🚀 Running the Bot

### Prerequisites
```bash
# 1. Ensure Anvil is running with Alchemy RPC
ps aux | grep anvil
# Should see: anvil --fork-url https://polygon-mainnet.g.alchemy.com/v2/...

# 2. Database is running
docker ps | grep postgres
# Should see postgres container

# 3. Virtual environment is activated
source venv/bin/activate
```

### Start the Bot

**Dry Run Mode (Safe - No Real Transactions):**
```bash
# Edit .env to ensure:
# DRY_RUN=true

python run_bot.py
```

**Production Mode (Real Transactions):**
```bash
# DANGER: This will execute real transactions!
# Edit .env:
# DRY_RUN=false

# Ensure executor wallet has MATIC for gas
python run_bot.py
```

---

## 📊 Monitoring

### View Live Logs
```bash
# In another terminal
tail -f bot.log

# Or with filtering
tail -f bot.log | grep "Opportunity"
```

### Check Database
```python
python << 'EOF'
from src.db.database import SessionLocal
from src.db.models import Opportunity

db = SessionLocal()
opps = db.query(Opportunity).count()
print(f"Total opportunities detected: {opps}")

recent = db.query(Opportunity).order_by(
    Opportunity.created_at.desc()
).limit(5).all()

for opp in recent:
    print(f"{opp.direction}: ${opp.expected_profit_usd:.2f}")
db.close()
EOF
```

### View Statistics
The bot prints statistics periodically:
```
============================================================
Bot Statistics
============================================================
Total scans: 100
Opportunities found: 5
Opportunities executed: 3
Successful: 2
Failed: 1
Total profit: 15.50 tokens
Average profit per trade: 7.75 tokens
============================================================
```

---

## ⚙️ Configuration

### Key Settings in `.env`

```bash
# Execution Mode
DRY_RUN=true                    # true = safe testing, false = real txs
DIRECT_EXECUTION=true           # true = immediate, false = database queue

# Profitability Filters
MIN_PROFIT_USD=1.0             # Minimum profit threshold
MAX_GAS_PRICE_GWEI=100         # Maximum gas price to accept

# Scanning
CHECK_INTERVAL=5               # Seconds between scans

# Network
POLYGON_RPC_URL=http://localhost:8545
```

### Adjusting for More Opportunities

If you want to see more opportunities (even tiny profits):
```bash
MIN_PROFIT_USD=0.01   # See any profit > 1 cent
```

If you want only profitable trades after gas:
```bash
MIN_PROFIT_USD=10.0   # Conservative threshold
```

---

## 🧪 Testing

### Test Price Quotes
```bash
python test_live_detection.py
```

Output:
```
Uniswap V3 (0.05%): 7337.950472 WMATIC
QuickSwap V2:       7334.739819 WMATIC
Price difference:   0.0438%
```

### Test Full Execution Flow
```bash
python test_full_execution.py
```

This simulates executing 2 profitable opportunities in dry run mode.

### Test Orchestrator Only
```bash
python test_orchestrator.py
```

Tests transaction building without real opportunities.

---

## 🛠️ Troubleshooting

### Bot Not Finding Opportunities

**This is normal!** Real arbitrage opportunities are rare because:
- Professional bots capture them instantly (<500ms)
- Markets are highly efficient
- You're competing with optimized MEV bots

**What to check:**
```bash
# 1. Verify price quotes are working
python test_live_detection.py

# 2. Lower profit threshold temporarily
# In .env: MIN_PROFIT_USD=0.01

# 3. Check if detector is scanning
tail -f bot.log | grep "Scanning"
```

### RPC Errors (503, timeouts)

**Alchemy free tier has rate limits.**

Solutions:
```bash
# 1. Increase scan interval (fewer requests)
CHECK_INTERVAL=10

# 2. Upgrade Alchemy plan ($50/month)

# 3. Use alternative RPC
POLYGON_RPC_URL=https://polygon-rpc.com
```

### Database Connection Errors

```bash
# Check if PostgreSQL is running
docker ps | grep postgres

# Restart database
docker start arbitrage-db

# Verify connection
python -c "from src.db.database import check_db_connection; print(check_db_connection())"
```

### Transactions Failing

If you see execution failures:
```bash
# 1. Check contract is not paused
cast call $FLASH_LOAN_ARBITRAGE_ADDRESS "paused()(bool)"

# 2. Verify you're the owner
cast call $FLASH_LOAN_ARBITRAGE_ADDRESS "owner()(address)"

# 3. Check gas prices
cast gas-price --rpc-url http://localhost:8545

# 4. Ensure adapters are registered
cast call $FLASH_LOAN_ARBITRAGE_ADDRESS \
  "registeredAdapters(address)(bool)" \
  $UNISWAP_V3_ADAPTER_ADDRESS
```

---

## 📈 Scaling Up

### Add More Trading Pairs

Edit `src/opportunity_detector.py`:
```python
self.pairs = [
    ('USDC', 'WMATIC'),
    ('USDC', 'WETH'),
    ('WMATIC', 'WETH'),
    ('DAI', 'USDC'),
    # Add more:
    ('USDT', 'USDC'),
    ('WBTC', 'WETH'),
]
```

### Add More Amount Tiers

```python
self.amounts = {
    'USDC': [1000 * 10**6, 5000 * 10**6, 10000 * 10**6, 50000 * 10**6],
    # Test larger flash loans
}
```

### Faster Scanning

```bash
# In .env
CHECK_INTERVAL=2  # Scan every 2 seconds (more RPC calls)
```

⚠️ **Warning**: Faster scanning = more RPC calls = higher rate limit risk

---

## 🎯 Production Deployment Checklist

Before going to mainnet:

- [ ] Test on Amoy testnet for 1+ week
- [ ] Verify all executions successful
- [ ] Test error recovery (kill bot, restart)
- [ ] Set up monitoring/alerts
- [ ] Fund executor wallet with MATIC (0.5+)
- [ ] Start with conservative MIN_PROFIT_USD (10+)
- [ ] Use premium RPC (not free tier)
- [ ] Consider MEV protection (Flashbots)
- [ ] Set up automatic restarts (systemd/supervisor)
- [ ] Keep private keys secure (hardware wallet)

---

## 📚 Additional Resources

- **Architecture**: See `PROJECT_COMPLETE.md`
- **Detector Details**: See `DETECTOR_README.md`
- **Orchestrator Details**: See `ORCHESTRATOR_README.md`
- **Test Results**: See `BOT_TEST_SUMMARY.md`
- **Contract Deployment**: See deployment logs in repo

---

## 🆘 Getting Help

### Check Logs
```bash
# Bot logs
cat bot.log

# Test logs
ls -lah *.log

# Database logs
docker logs arbitrage-db
```

### Debug Mode

For more detailed logging, edit `run_bot.py`:
```python
logging.basicConfig(
    level=logging.DEBUG,  # Changed from INFO
    ...
)
```

### Common Issues

**"No module named 'dotenv'"**
```bash
pip install python-dotenv web3 sqlalchemy psycopg2-binary
```

**"Database connection failed"**
```bash
docker start arbitrage-db
```

**"Not contract owner"**
```bash
# Verify PRIVATE_KEY matches deployed contract owner
# Redeploy contracts if needed
```

---

## 💡 Pro Tips

1. **Start Conservative**: Use high MIN_PROFIT_USD (10+) initially
2. **Monitor Closely**: Watch first 24 hours carefully
3. **Log Everything**: Keep detailed logs for analysis
4. **Test Exhaustively**: Don't rush to production
5. **Backup Keys**: Store private keys securely offline
6. **Scale Gradually**: Add pairs/amounts slowly
7. **Track Metrics**: Monitor success rate, gas costs, profits
8. **Stay Updated**: Follow Polygon/Aave for changes

---

**Last Updated**: 2026-01-21
**Version**: 1.0.0
**Status**: Production Ready
