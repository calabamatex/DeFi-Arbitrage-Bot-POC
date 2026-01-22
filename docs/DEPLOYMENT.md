# Deployment Guide

Complete guide for deploying the arbitrage bot to testnet and mainnet.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Testnet Deployment](#testnet-deployment)
3. [Mainnet Deployment](#mainnet-deployment)
4. [Security Best Practices](#security-best-practices)
5. [Monitoring Setup](#monitoring-setup)

## Prerequisites

### System Requirements

- **OS**: Ubuntu 22.04+ (recommended) or macOS
- **Python**: 3.9 or higher
- **RAM**: 2GB minimum, 4GB recommended
- **Storage**: 10GB available
- **Network**: Stable internet connection

### Accounts Needed

- Polygon wallet with funds
- Telegram bot (optional but recommended)
- RPC provider account (optional for dedicated RPC)

### Get Mumbai Testnet MATIC

```bash
# Visit faucet
https://faucet.polygon.technology/

# Enter your wallet address
# Request 5+ MATIC
```

## Testnet Deployment

### Step 1: Clone and Setup

```bash
# Clone repository
git clone https://github.com/yourusername/arbitrage-bot.git
cd arbitrage-bot

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Configure Environment

```bash
# Copy example env file
cp .env.example .env

# Edit .env file
nano .env
```

Required settings:
```bash
# CRITICAL: Must be 'testnet' for Mumbai
ENVIRONMENT=testnet

# Your wallet private key (KEEP SECRET!)
PRIVATE_KEY=0xyour_private_key_here

# Telegram (optional but recommended)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Admin code for emergency shutdown reset
ADMIN_CODE=your_secure_admin_code
```

### Step 3: Run Deployment Script

```bash
./scripts/deploy_testnet.sh
```

This script will:
- ✅ Check Python version
- ✅ Validate .env configuration
- ✅ Install dependencies
- ✅ Test configuration
- ✅ Run test suite
- ✅ Check RPC connection
- ✅ Verify account balance
- ✅ Setup directories

### Step 4: Get Testnet Tokens

```bash
# Run setup helper
./scripts/setup_testnet.py

# Or manually:
# 1. Visit https://app.uniswap.org/
# 2. Switch to Polygon Mumbai network
# 3. Swap MATIC for WETH, USDC, USDT
```

### Step 5: Start Bot

```bash
# Start in foreground (recommended for first test)
python -m src.bot.main

# Or start in background
nohup python -m src.bot.main > logs/bot.log 2>&1 &

# Monitor logs
tail -f logs/bot.log
```

### Step 6: Verify Operation

```bash
# Check bot is running
./scripts/monitor_bot.py

# Check balances
./scripts/check_balances.py

# Wait a bit for metrics
sleep 60

# Generate report
./scripts/generate_report.py data/metrics.json
```

## Mainnet Deployment

⚠️ **WARNING: Mainnet deployment involves REAL MONEY. Complete ALL testnet validation first!**

### Mainnet Checklist

Before deploying to mainnet, verify:

- [ ] Bot ran successfully on testnet for 48+ hours
- [ ] No critical errors in testnet logs
- [ ] All security checks passed
- [ ] Risk management tested and working
- [ ] Emergency shutdown tested
- [ ] Monitoring and alerts configured
- [ ] Backup procedures tested
- [ ] At least 5 MATIC on mainnet for gas
- [ ] At least $1,000 in trading capital
- [ ] Team member available for first 24h

### Step 1: Update Configuration

```bash
# Edit .env
nano .env

# Change to mainnet
ENVIRONMENT=mainnet

# Verify mainnet wallet has funds
./scripts/check_balances.py
```

### Step 2: Run Mainnet Deployment

```bash
./scripts/deploy_mainnet.sh
```

This will:
- Ask confirmation questions
- Verify all prerequisites
- Run full test suite
- Verify mainnet connection
- Require final confirmation ("DEPLOY TO MAINNET")

### Step 3: Start with Conservative Settings

```bash
# Edit config.json for conservative settings
nano config/config.json
```

Recommended initial settings:
```json
{
  "settings": {
    "BASE_PROFIT_THRESHOLD": "0.02",     // 2% minimum
    "MAX_POSITION_SIZE_USD": 100,         // Small positions
    "DAILY_LOSS_LIMIT_USD": 500,          // Conservative limit
    "MAX_CONSECUTIVE_LOSSES": 3,          // Quick circuit breaker
    "SLIPPAGE_TOLERANCE": "0.003"         // 0.3% slippage
  }
}
```

### Step 4: Start Bot

```bash
# Start bot with mainnet script
./start_mainnet.sh

# Monitor CONSTANTLY for first 24 hours
tail -f logs/bot_*.log
```

### Step 5: Monitor Aggressively

**First 24 hours:**
- Check logs every 1-2 hours
- Monitor Telegram alerts constantly
- Check metrics dashboard frequently
- Be ready to emergency shutdown

**First week:**
- Daily log review
- Daily metrics review
- Gradual increase in position sizes
- Monitor for any anomalies

### Step 6: Scale Gradually

**Week 1:** $100 positions, 2% profit threshold
**Week 2:** $250 positions, 1.5% threshold (if successful)
**Week 3:** $500 positions, 1% threshold (if successful)
**Month 2+:** $1000+ positions (if consistently profitable)

## Security Best Practices

### Wallet Security

1. **Use dedicated wallet** - Don't use your main wallet
2. **Limit funds** - Only keep trading capital in wallet
3. **Backup private key** - Store securely offline
4. **Rotate periodically** - Consider new wallet every 6 months

### Server Security

```bash
# If using VPS:

# 1. Setup firewall
sudo ufw allow 22/tcp  # SSH only
sudo ufw enable

# 2. Disable root login
sudo nano /etc/ssh/sshd_config
# Set: PermitRootLogin no

# 3. Setup automatic security updates
sudo apt install unattended-upgrades
sudo dpkg-reconfigure unattended-upgrades

# 4. Setup fail2ban
sudo apt install fail2ban
sudo systemctl enable fail2ban
```

### Operational Security

1. **Never share private key**
2. **Use strong admin code**
3. **Encrypt .env file at rest**
4. **Review logs for suspicious activity**
5. **Keep software updated**

## Monitoring Setup

### Basic Monitoring

```bash
# Cron job to check bot every 5 minutes
crontab -e

# Add:
*/5 * * * * /path/to/scripts/monitor_bot.py >> /path/to/logs/monitor.log 2>&1
```

### Hourly Reports

```bash
# Cron job to generate reports
crontab -e

# Add:
0 * * * * /path/to/scripts/generate_report.py /path/to/data/metrics.json
```

### Advanced Monitoring (Optional)

Setup Prometheus + Grafana for production monitoring.

## Troubleshooting Deployment

### Bot won't start

```bash
# Check Python version
python3 --version

# Check dependencies
pip list | grep web3

# Check configuration
python src/bot/config.py

# Check logs
tail -100 logs/bot_*.log
```

### RPC connection fails

```bash
# Test RPC manually
python3 -c "
from web3 import Web3
w3 = Web3(Web3.HTTPProvider('YOUR_RPC_URL'))
print(w3.is_connected())
"

# Try alternative RPC providers:
# - Alchemy
# - Infura
# - QuickNode
```

### Insufficient balance errors

```bash
# Check balances
./scripts/check_balances.py

# Get more testnet MATIC
https://faucet.polygon.technology/

# For mainnet, send more MATIC to wallet
```

## Recovery Procedures

### Emergency Stop

```bash
# Stop bot immediately
pkill -f 'python3 -m src.bot.main'

# Verify stopped
./scripts/monitor_bot.py
```

### Restore from Backup

```bash
# List backups
ls backups/

# Restore config
cp backups/TIMESTAMP/config.json config/

# Restore env (manually add your keys)
# Don't overwrite PRIVATE_KEY!
```

### Reset Everything

```bash
# Stop bot
pkill -f 'python3 -m src.bot.main'

# Backup current state
./scripts/backup_config.sh

# Delete data
rm -rf data/*
rm -rf logs/*

# Re-deploy
./scripts/deploy_testnet.sh

# Reconfigure
nano .env
nano config/config.json

# Restart
python -m src.bot.main
```

## Production Deployment (VPS)

### Recommended VPS Setup

```bash
# 1. Update system
sudo apt update && sudo apt upgrade -y

# 2. Install Python
sudo apt install python3.11 python3.11-venv python3-pip -y

# 3. Create bot user
sudo useradd -m -s /bin/bash botuser
sudo su - botuser

# 4. Clone and setup
git clone https://github.com/yourusername/arbitrage-bot.git
cd arbitrage-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 5. Configure
cp .env.example .env
nano .env  # Add your settings

# 6. Deploy
./scripts/deploy_mainnet.sh
```

### Setup as System Service

```bash
# Create systemd service file
sudo nano /etc/systemd/system/arbitrage-bot.service
```

```ini
[Unit]
Description=Arbitrage Trading Bot
After=network.target

[Service]
Type=simple
User=botuser
WorkingDirectory=/home/botuser/arbitrage-bot
Environment="PATH=/home/botuser/arbitrage-bot/venv/bin"
ExecStart=/home/botuser/arbitrage-bot/venv/bin/python -m src.bot.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable arbitrage-bot
sudo systemctl start arbitrage-bot

# Check status
sudo systemctl status arbitrage-bot

# View logs
sudo journalctl -u arbitrage-bot -f
```

## Rollback Procedure

If mainnet deployment has issues:

```bash
# 1. Immediate shutdown
sudo systemctl stop arbitrage-bot

# Or manually
pkill -f 'python3 -m src.bot.main'

# 2. Verify stopped
./scripts/monitor_bot.py

# 3. Restore from backup
cp backups/TIMESTAMP/config.json config/

# 4. Investigate issue
grep ERROR logs/bot_*.log

# 5. Fix and test on testnet first

# 6. Re-deploy when ready
./scripts/deploy_mainnet.sh
```

## Support

If you encounter issues:
1. Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
2. Search GitHub issues
3. Create new issue with logs and diagnostics
