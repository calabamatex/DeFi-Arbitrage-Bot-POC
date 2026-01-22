# Deployment and Management Scripts

This directory contains scripts for deploying, monitoring, and managing the arbitrage bot.

## Scripts Overview

### 1. `deploy_testnet.sh`
**Purpose**: Deploy and validate bot on Mumbai testnet

**Usage**:
```bash
./scripts/deploy_testnet.sh
```

**What it does**:
- Checks Python version (requires 3.9+)
- Validates `.env` configuration
- Verifies ENVIRONMENT=testnet
- Installs dependencies
- Runs test suite
- Tests RPC connection to Mumbai
- Checks account balance
- Creates necessary directories

**Prerequisites**:
- `.env` file configured for testnet
- PRIVATE_KEY set in .env
- Mumbai RPC URL configured

---

### 2. `deploy_mainnet.sh`
**Purpose**: Interactive mainnet deployment with safety checks

**Usage**:
```bash
./scripts/deploy_mainnet.sh
```

**What it does**:
- Interactive safety checklist
- Requires confirmation of 48+ hour testnet run
- Validates mainnet configuration
- Runs full test suite
- Verifies connection to Polygon Mainnet (chain ID 137)
- Creates conservative startup script
- Requires typing "DEPLOY TO MAINNET" to proceed

**Safety Features**:
- Multiple confirmation prompts
- Validates testnet experience
- Checks monitoring setup
- Creates startup script with conservative limits:
  - 2% minimum profit threshold
  - $100 max position size
  - $500 daily loss limit

---

### 3. `check_balances.py`
**Purpose**: Check token balances for bot account

**Usage**:
```bash
python scripts/check_balances.py
# or
./scripts/check_balances.py
```

**Output**:
- Current environment (testnet/mainnet)
- Bot account address
- MATIC balance
- All token balances from config
- Warnings for low balances

**Example Output**:
```
============================================================
Token Balance Checker
============================================================

Environment: testnet
Account: 0x1234...5678

MATIC: 5.234567
  ⚠️  WARNING: Low MATIC for gas!

Token Balances:
------------------------------------------------------------
WETH    :        1.250000
USDC    :      500.000000
DAI     :        0.000000
          ⚠️  No DAI balance
============================================================
```

---

### 4. `setup_testnet.py`
**Purpose**: Interactive guide for setting up testnet account

**Usage**:
```bash
python scripts/setup_testnet.py
# or
./scripts/setup_testnet.py
```

**What it does**:
- Validates environment is testnet
- Displays bot account address
- Guides user through getting testnet MATIC
- Provides instructions for getting testnet tokens
- Verifies MATIC balance after faucet
- Explains token approval process

**Steps**:
1. Get Mumbai MATIC from faucet
2. Swap for testnet tokens on Uniswap
3. Verify balances
4. Start bot

---

### 5. `monitor_bot.py`
**Purpose**: Check if bot is running and healthy

**Usage**:
```bash
python scripts/monitor_bot.py
# or
./scripts/monitor_bot.py
```

**What it checks**:
- Bot process is running (requires psutil)
- Process ID and uptime
- CPU and memory usage
- Log file exists and is updating
- Recent errors in logs

**Example Output**:
```
============================================================
Bot Health Monitor
============================================================

✓ Bot is running (PID: 12345)

Uptime: 2:15:30
CPU Usage: 2.5%
Memory Usage: 85.3 MB

Latest log: bot_20231226.log
  ✓ Log file actively updating
  ✓ No recent errors

✅ Bot health check complete
```

**Note**: Install psutil for full functionality:
```bash
pip install psutil
```

---

### 6. `backup_config.sh`
**Purpose**: Backup configuration and data

**Usage**:
```bash
./scripts/backup_config.sh
```

**What it backs up**:
- `config/config.json`
- `.env` template (without secrets)
- Logs directory
- Trade history files
- Bot log files

**Backup location**: `backups/YYYYMMDD_HHMMSS/`

**What's included**:
- Configuration files
- Log files
- Trade history
- Backup metadata (timestamp, git commit, hostname)

**Excludes**:
- PRIVATE_KEY (security)
- TELEGRAM_BOT_TOKEN (security)

**To restore**:
```bash
# Copy config
cp backups/20231226_123456/config.json config/

# Manually add secrets to .env
# Use backup/env.template as reference
```

**To compress backup**:
```bash
tar -czf backups/20231226_123456.tar.gz backups/20231226_123456
```

---

### 7. `benchmark.py`
**Purpose**: Measure bot performance

**Usage**:
```bash
python scripts/benchmark.py
# or
./scripts/benchmark.py
```

**Benchmarks**:
1. Price cache performance
2. RPC call performance
3. Gas optimization calculations
4. Performance monitor overhead
5. Opportunity detection simulation

**Performance Targets**:
- Opportunity detection: < 2 seconds
- Trade execution: < 5 seconds
- RPC calls: < 100 per minute
- Memory usage: < 500 MB

---

## Typical Deployment Workflow

### For Testnet:

1. **Initial Setup**:
   ```bash
   # Setup testnet account
   ./scripts/setup_testnet.py

   # Check balances
   ./scripts/check_balances.py
   ```

2. **Deploy**:
   ```bash
   # Run deployment script
   ./scripts/deploy_testnet.sh

   # Start bot
   python3 -m src.bot.main
   ```

3. **Monitor**:
   ```bash
   # Check bot health
   ./scripts/monitor_bot.py

   # Watch logs
   tail -f bot_*.log
   ```

4. **Backup**:
   ```bash
   # Create backup
   ./scripts/backup_config.sh
   ```

### For Mainnet:

1. **Validate Testnet**:
   - Run bot on testnet for 48+ hours
   - Verify all systems working
   - Check performance metrics

2. **Deploy to Mainnet**:
   ```bash
   # Interactive deployment
   ./scripts/deploy_mainnet.sh

   # Start with conservative settings
   ./start_mainnet.sh
   ```

3. **Monitor Closely**:
   ```bash
   # Check every hour for first 24h
   ./scripts/monitor_bot.py

   # Watch for Telegram alerts
   # Review logs frequently
   ```

4. **Regular Backups**:
   ```bash
   # Daily backups
   ./scripts/backup_config.sh
   ```

---

## Troubleshooting

### Script Permission Denied
```bash
chmod +x scripts/script_name.sh
```

### Python Script Not Found
```bash
# Run from project root
cd /path/to/project
python scripts/script_name.py
```

### RPC Connection Failed
- Check .env has correct RPC URL
- Verify network connectivity
- Test RPC endpoint: `curl -X POST <RPC_URL>`

### Insufficient MATIC Balance
- Testnet: https://faucet.polygon.technology/
- Mainnet: Purchase MATIC from exchange

### Bot Not Running
```bash
# Check if process exists
ps aux | grep "src.bot.main"

# Check logs for errors
tail -100 bot_*.log | grep ERROR
```

---

## Security Notes

1. **Never commit backups** containing secrets to git
2. **Store backups securely** - they contain configuration
3. **Rotate backups** - delete old backups periodically
4. **Test restores** - verify backups work before disaster
5. **Secure .env** - keep private keys encrypted at rest

---

## Maintenance

### Daily:
- Check bot health with `monitor_bot.py`
- Review logs for errors
- Monitor Telegram alerts

### Weekly:
- Create backup with `backup_config.sh`
- Review performance with `benchmark.py`
- Check balances with `check_balances.py`

### Monthly:
- Review and archive old logs
- Compress old backups
- Update dependencies if needed

---

## Support

For issues with scripts:
1. Check script output for error messages
2. Verify prerequisites are met
3. Review logs for details
4. Ensure .env is properly configured
