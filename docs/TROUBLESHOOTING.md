# Troubleshooting Guide

Common issues and solutions for the arbitrage bot.

## Configuration Issues

### "Configuration error: Missing PRIVATE_KEY"

**Cause**: PRIVATE_KEY not set in .env file

**Solution**:
```bash
# Edit .env file
nano .env

# Add your private key (without quotes)
PRIVATE_KEY=0xyour_64_character_private_key_here

# Verify it's set
grep PRIVATE_KEY .env
```

### "Wrong chain ID: got X, expected Y"

**Cause**: ENVIRONMENT in .env doesn't match actual network

**Solution**:
```bash
# For testnet (Mumbai)
ENVIRONMENT=testnet  # Chain ID should be 80001

# For mainnet (Polygon)
ENVIRONMENT=mainnet  # Chain ID should be 137

# Verify connection
python3 -c "
from web3 import Web3
from src.bot.config import load_config
_, env, env_config, _ = load_config()
w3 = Web3(Web3.HTTPProvider(env_config['POLYGON_RPC_URL']))
print(f'Environment: {env}')
print(f'Connected: {w3.is_connected()}')
print(f'Chain ID: {w3.eth.chain_id}')
"
```

### "JSON decode error in config.json"

**Cause**: Invalid JSON syntax in configuration file

**Solution**:
```bash
# Validate JSON
python -m json.tool config/config.json

# Common issues:
# - Missing commas between items
# - Trailing commas (last item)
# - Unquoted strings
# - Comments (not allowed in JSON)

# Fix and re-validate
nano config/config.json
python -m json.tool config/config.json
```

## Connection Issues

### "Failed to connect to RPC"

**Cause**: RPC endpoint down or rate limited

**Solutions**:

1. **Try alternative RPC**:
```bash
# Edit config.json
nano config/config.json

# Use alternative endpoints:
# Testnet:
"POLYGON_RPC_URL": "https://polygon-mumbai.g.alchemy.com/v2/demo"
"POLYGON_RPC_URL": "https://rpc-mumbai.maticvigil.com/"

# Mainnet:
"POLYGON_RPC_URL": "https://polygon-rpc.com/"
"POLYGON_RPC_URL": "https://rpc-mainnet.maticvigil.com/"
```

2. **Check network connectivity**:
```bash
# Test endpoint
curl -X POST https://rpc-mumbai.maticvigil.com/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'

# Should return a block number
```

3. **Check rate limiting**:
```bash
# If using public RPC, you may be rate limited
# Solution: Get free API key from:
# - Alchemy: https://www.alchemy.com/
# - Infura: https://infura.io/
# - QuickNode: https://www.quicknode.com/
```

### "Transaction timeout"

**Cause**: Network congestion or wrong gas price

**Solutions**:

1. **Increase gas price**:
```json
// In config.json, increase gas multiplier
"GAS_MULTIPLIER": 1.2  // 20% higher gas
```

2. **Check network status**:
```bash
# Visit Polygonscan
# Testnet: https://mumbai.polygonscan.com/
# Mainnet: https://polygonscan.com/

# Check for:
# - Network congestion
# - High gas prices
# - Node issues
```

3. **Increase timeout**:
```python
# In transaction_manager.py
# receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
```

## Balance Issues

### "Insufficient balance for gas"

**Causes & Solutions**:

**For testnet MATIC**:
```bash
# 1. Check current balance
./scripts/check_balances.py

# 2. Get testnet MATIC from faucet
# Visit: https://faucet.polygon.technology/
# Enter your wallet address
# Request 5+ MATIC

# 3. Wait 1-2 minutes and check again
./scripts/check_balances.py
```

**For mainnet MATIC**:
```bash
# Send MATIC to your bot wallet
# Minimum: 5 MATIC for gas
# Recommended: 10+ MATIC
```

### "Insufficient token balance"

**For testnet tokens**:
```bash
# Option 1: Use Uniswap testnet interface
# 1. Visit https://app.uniswap.org/
# 2. Connect wallet
# 3. Switch to Polygon Mumbai network
# 4. Swap MATIC for WETH, USDC, etc.

# Option 2: Use QuickSwap testnet
# Visit their testnet interface and swap
```

**For mainnet tokens**:
```bash
# Send tokens to your bot wallet
# Or swap MATIC for tokens on DEX
```

### "Insufficient allowance"

**Cause**: Tokens not approved for DEX spending

**Solution**: Bot auto-approves, but if it fails:
```bash
# Check logs for approval status
grep "approval" logs/bot_*.log

# Look for:
# - "Approving token..."
# - "Token approved successfully"
# - Any approval errors

# If approval fails, check:
# - Sufficient MATIC for gas
# - Correct token address
# - DEX router address
```

## Trading Issues

### "No opportunities found"

**This is often normal!** The bot only trades when profitable opportunities exist.

**Diagnostics**:
```bash
# 1. Check if prices are being fetched
grep "Fetching prices" logs/bot_*.log

# 2. Check detected opportunities
grep "opportunity" logs/bot_*.log

# 3. Verify DEX connections
grep "DEX" logs/bot_*.log

# 4. Check profit threshold
grep "profit threshold" logs/bot_*.log
```

**Possible causes**:
1. **Market conditions** (most common)
   - All DEXes have similar prices
   - No arbitrage opportunities available
   - This is normal and expected

2. **Profit threshold too high**:
```json
// Lower threshold (carefully!)
"BASE_PROFIT_THRESHOLD": "0.003"  // 0.3%
```

3. **Insufficient liquidity**:
```bash
# Check token liquidity on each DEX
# Visit DEX interfaces and check pool sizes
```

4. **Price fetching issues**:
```bash
# Check RPC connection
python src/bot/config.py

# Check for RPC errors in logs
grep "RPC" logs/bot_*.log
```

### "Trade failed: transaction reverted"

**Common causes**:

1. **Slippage too high**:
```json
// Increase slippage tolerance
"SLIPPAGE_TOLERANCE": "0.01"  // 1%
```

2. **Insufficient liquidity**:
```bash
# Solution: Lower position size
"MAX_POSITION_SIZE_USD": 100
```

3. **Price moved during execution**:
```bash
# This is normal in volatile markets
# Bot will try next opportunity
```

4. **Token approval expired**:
```bash
# Check logs
grep "approval" logs/bot_*.log

# Bot should auto-reapprove
# If not, restart bot
```

### "Circuit breaker triggered"

**Cause**: Too many consecutive losses

**Recovery steps**:

1. **Review what went wrong**:
```bash
# Check recent trades
grep "Trade failed" logs/bot_*.log

# Look for patterns:
# - All on same DEX?
# - Same token pair?
# - Slippage issues?
# - Gas estimation problems?
```

2. **Fix underlying issues**:
```bash
# Common fixes:
# - Increase slippage tolerance
# - Lower position sizes
# - Adjust profit threshold
# - Check RPC connection
```

3. **Wait for auto-reset**:
```bash
# Circuit breaker auto-resets after cooldown
# Default: 60 minutes

# Check status
grep "circuit breaker" logs/bot_*.log
```

4. **Manual reset** (if needed):
```bash
# Requires admin code
# Bot will prompt for admin code
# Or restart bot after fixing issues
```

## Performance Issues

### Bot is slow / High detection times

**Diagnostics**:
```bash
# 1. Check current performance
./scripts/monitor_bot.py

# 2. Check detection times in logs
grep "detection time" logs/bot_*.log

# 3. Check system resources
top  # or htop

# 4. Check RPC latency
time curl -X POST YOUR_RPC_URL -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
```

**Solutions**:

1. **Use faster RPC**:
```bash
# Switch to dedicated RPC provider
# - Alchemy
# - Infura
# - QuickNode
```

2. **Enable/optimize caching**:
```json
"PRICE_CACHE_DURATION_SECONDS": 3
```

3. **Increase check interval**:
```json
"CHECK_INTERVAL_SECONDS": 15  // Check less frequently
```

4. **Upgrade server** (if on VPS):
```bash
# More CPU and RAM
# Lower latency network
```

### High memory usage

**Diagnostics**:
```bash
# Check memory
./scripts/monitor_bot.py

# Or use system tools
free -h  # Linux
top      # All systems
```

**Solutions**:

1. **Rotate logs**:
```bash
# Delete old logs
find logs/ -name "*.log" -mtime +7 -delete

# Or compress old logs
find logs/ -name "*.log" -mtime +1 -exec gzip {} \;
```

2. **Clear old metrics**:
```bash
# Metrics auto-limited to last 1000
# But can manually clear if needed
rm data/metrics.json
```

3. **Restart bot periodically**:
```bash
# Add to cron (restart daily at 3 AM)
0 3 * * * pkill -f 'python3 -m src.bot.main' && sleep 10 && cd /path/to/bot && python3 -m src.bot.main
```

### "Rate limited by RPC"

**Cause**: Too many RPC requests

**Solutions**:

1. **Use dedicated RPC with higher limits**:
```bash
# Get API key from provider
# Add to .env
POLYGON_MAINNET_RPC_URL=https://polygon-mainnet.g.alchemy.com/v2/YOUR-KEY
```

2. **Enable price caching**:
```json
"PRICE_CACHE_DURATION_SECONDS": 5  // Cache prices for 5 seconds
```

3. **Slow down polling**:
```json
"CHECK_INTERVAL_SECONDS": 20  // Check every 20 seconds instead of 10
```

## Error Messages

### "Nonce too low"

**Cause**: Nonce management issue or pending transaction

**Solution**:
```bash
# TransactionManager handles this automatically
# If persists:

# 1. Check for pending transactions
# Visit Polygonscan with your wallet address

# 2. Wait for pending transactions to complete

# 3. Restart bot
pkill -f 'python3 -m src.bot.main'
python -m src.bot.main
```

### "Gas price too high"

**Cause**: Network congestion

**Solutions**:

1. **Wait for lower gas**:
```bash
# Check gas prices:
# Testnet: https://mumbai.polygonscan.com/gastracker
# Mainnet: https://polygonscan.com/gastracker
```

2. **Adjust gas price strategy**:
```json
"GAS_MULTIPLIER": 0.9  // Use lower gas price
```

3. **Use EIP-1559**:
```python
# Already implemented in gas_optimizer.py
# Automatically uses EIP-1559 when available
```

### "Emergency shutdown active"

**Causes**:
- Loss limit exceeded
- Circuit breaker triggered
- Manual shutdown

**Recovery**:

1. **Check shutdown reason**:
```bash
grep "Emergency shutdown" logs/bot_*.log
grep "shutdown reason" logs/bot_*.log
```

2. **Fix underlying issue**:
```bash
# Based on reason:
# - Losses: Review trading strategy
# - Circuit breaker: Check for errors
# - Manual: Intentional, no action needed
```

3. **Reset** (after fixing issues):
```bash
# Option 1: Wait for auto-reset
# Circuit breaker auto-resets after cooldown

# Option 2: Manual reset with admin code
# Bot will prompt for ADMIN_CODE from .env

# Option 3: Restart bot
pkill -f 'python3 -m src.bot.main'
python -m src.bot.main
```

## Deployment Issues

### Tests fail during deployment

**Solution**:
```bash
# 1. Run tests directly to see details
pytest tests/ -v

# 2. Run specific failing test
pytest tests/test_MODULE.py::test_function -v

# 3. Check for common issues:
# - Missing dependencies
# - Wrong Python version
# - Configuration errors

# 4. Install missing dependencies
pip install -r requirements.txt

# 5. Re-run deployment
./scripts/deploy_testnet.sh
```

### Bot starts then immediately exits

**Diagnostics**:
```bash
# 1. Check recent logs
tail -100 logs/bot_*.log

# 2. Look for startup errors
grep -A 10 "ERROR" logs/bot_*.log

# 3. Common issues:
# - Missing PRIVATE_KEY
# - Wrong ENVIRONMENT
# - RPC connection failed
# - Configuration errors
```

**Solution**:
```bash
# Test configuration manually
python src/bot/config.py

# Should show no errors and display:
# - Environment
# - Number of tokens
# - RPC connection status
```

### Wrong network configured

**Diagnostics**:
```bash
# Check environment setting
grep ENVIRONMENT .env

# Verify actual network
python -c "
from web3 import Web3
from src.bot.config import load_config
_, env, env_config, _ = load_config()
w3 = Web3(Web3.HTTPProvider(env_config['POLYGON_RPC_URL']))
print(f'Environment in .env: {env}')
print(f'Actual Chain ID: {w3.eth.chain_id}')
print(f'Expected Chain ID: {80001 if env==\"testnet\" else 137}')
"
```

**Solution**:
```bash
# Fix .env
nano .env

# Set correct environment
ENVIRONMENT=testnet  # or mainnet

# Verify
python src/bot/config.py
```

## Recovery Procedures

### Emergency Stop

```bash
# Method 1: Kill process
pkill -f 'python3 -m src.bot.main'

# Method 2: If running as service
sudo systemctl stop arbitrage-bot

# Method 3: Emergency shutdown via Telegram
# Send: /emergency_shutdown
# Enter admin code when prompted

# Verify stopped
./scripts/monitor_bot.py
# Should show: "Bot is NOT running"
```

### Restore from Backup

```bash
# 1. List available backups
ls -lt backups/

# 2. Choose backup to restore
BACKUP_DIR="backups/20231226_123456"

# 3. Stop bot
pkill -f 'python3 -m src.bot.main'

# 4. Backup current state
./scripts/backup_config.sh

# 5. Restore configuration
cp $BACKUP_DIR/config.json config/

# 6. Manually restore .env secrets
# Don't overwrite PRIVATE_KEY!
# Review backup/env.template for other settings

# 7. Test configuration
python src/bot/config.py

# 8. Restart bot
python -m src.bot.main
```

### Reset Everything

```bash
# CAUTION: This deletes all data and logs!

# 1. Stop bot
pkill -f 'python3 -m src.bot.main'

# 2. Backup current state (optional but recommended)
./scripts/backup_config.sh

# 3. Delete data and logs
rm -rf data/*
rm -rf logs/*
rm -f *.log

# 4. Keep configuration
# Do NOT delete config/ or .env

# 5. Re-deploy
./scripts/deploy_testnet.sh

# 6. Restart
python -m src.bot.main
```

## Getting Help

### Collect Diagnostic Information

```bash
# 1. System information
uname -a
python3 --version
pip list | grep -E 'web3|eth'

# 2. Configuration
python src/bot/config.py

# 3. Bot status
./scripts/monitor_bot.py

# 4. Balances
./scripts/check_balances.py

# 5. Recent logs
tail -100 logs/bot_*.log

# 6. Recent errors
grep -A 5 "ERROR" logs/bot_*.log | tail -50

# 7. Generate report (if bot ran)
./scripts/generate_report.py data/metrics.json 2>/dev/null
```

### Create GitHub Issue

If problem persists, create issue with:

1. **Clear description** of the problem
2. **Steps to reproduce**
3. **Expected behavior**
4. **Actual behavior**
5. **Diagnostic information** (from above)
6. **Relevant log excerpts**

### Common Misunderstandings

1. **"Bot not finding opportunities"**
   - This is often normal
   - Arbitrage opportunities are rare
   - May be hours between opportunities

2. **"Gas costs eating profits"**
   - Polygon gas is cheap, but adds up
   - Increase MIN_PROFIT_THRESHOLD
   - Larger positions have better profit/gas ratio

3. **"Circuit breaker keeps triggering"**
   - It's working as designed
   - Prevents runaway losses
   - Review and fix underlying issues

4. **"Trades failing on execution"**
   - Price moved during execution (normal)
   - Slippage protection working (good!)
   - Consider adjusting slippage tolerance

5. **"Bot seems slow"**
   - Detection target is <2 seconds
   - Network latency affects this
   - Use dedicated RPC for better performance
