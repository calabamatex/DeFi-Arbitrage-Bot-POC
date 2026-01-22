# Configuration Reference

Complete reference for all configuration options.

## Environment Variables (.env)

### Required Variables

```bash
# Environment (REQUIRED)
# Values: "testnet" or "mainnet"
ENVIRONMENT=testnet

# Private Key (REQUIRED)
# Your wallet's private key (64 hex characters)
# KEEP THIS SECRET!
PRIVATE_KEY=0x1234567890abcdef...
```

### Optional Variables

```bash
# Telegram Bot (Highly Recommended)
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789

# Admin Code for Emergency Shutdown Reset
ADMIN_CODE=your_secure_admin_code_here

# RPC URLs (uses defaults if not set)
POLYGON_MAINNET_RPC_URL=https://polygon-rpc.com/
POLYGON_TESTNET_RPC_URL=https://rpc-mumbai.maticvigil.com/
```

## Configuration File (config/config.json)

### Network Configurations

```json
{
  "testnet": {
    "POLYGON_RPC_URL": "https://rpc-mumbai.maticvigil.com/",
    "UNISWAP_V3_ROUTER": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
    "SUSHISWAP_ROUTER": "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506",
    "QUICKSWAP_ROUTER": "0x8954AfA98594b838bda56FE4C12a09D7739D179b",
    "CHAIN_ID": 80001
  },
  "mainnet": {
    "POLYGON_RPC_URL": "https://polygon-rpc.com/",
    "UNISWAP_V3_ROUTER": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
    "SUSHISWAP_ROUTER": "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506",
    "QUICKSWAP_ROUTER": "0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff",
    "CHAIN_ID": 137
  }
}
```

### Token Configurations

```json
{
  "tokens": [
    {
      "symbol": "WETH",
      "mainnet": {
        "address": "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619",
        "decimals": 18
      },
      "testnet": {
        "address": "0xA6FA4fB5f76172d178d61B04b0ecd319C5d1C0aa",
        "decimals": 18
      }
    },
    {
      "symbol": "USDC",
      "mainnet": {
        "address": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
        "decimals": 6
      },
      "testnet": {
        "address": "0xE097d6B3100777DC31B34dC2c58fB524C2e76921",
        "decimals": 6
      }
    }
  ]
}
```

### Settings

```json
{
  "settings": {
    // Profitability Thresholds
    "BASE_PROFIT_THRESHOLD": "0.005",        // 0.5% minimum profit
    "SLIPPAGE_TOLERANCE": "0.005",            // 0.5% max slippage
    "MAX_PRICE_IMPACT": "0.01",               // 1% max price impact

    // Position Limits
    "MAX_POSITION_SIZE_USD": 10000,           // Max single position
    "MAX_TOTAL_EXPOSURE_USD": 50000,          // Max total exposure
    "MAX_CONCENTRATION": "0.30",              // 30% max per token

    // Loss Limits
    "DAILY_LOSS_LIMIT_USD": 1000,             // Max daily loss
    "WEEKLY_LOSS_LIMIT_USD": 5000,            // Max weekly loss

    // Circuit Breaker
    "MAX_CONSECUTIVE_LOSSES": 5,              // Losses before shutdown
    "CIRCUIT_BREAKER_COOLDOWN_MIN": 60,       // Cooldown period

    // Performance
    "GAS_LIMIT": 300000,                      // Gas limit per transaction
    "MAX_RETRIES": 3,                         // Transaction retries
    "CHECK_INTERVAL_SECONDS": 10,             // Seconds between checks

    // Cache
    "PRICE_CACHE_DURATION_SECONDS": 3,        // Price cache TTL

    // Admin
    "ADMIN_CODE": "EMERGENCY_SHUTDOWN_2024"   // Emergency reset code
  }
}
```

## Setting Recommendations

### Conservative (Recommended for Start)

For first deployment and testing:

```json
{
  "BASE_PROFIT_THRESHOLD": "0.02",           // 2% profit
  "MAX_POSITION_SIZE_USD": 100,              // $100 positions
  "DAILY_LOSS_LIMIT_USD": 500,               // $500 daily loss
  "MAX_CONSECUTIVE_LOSSES": 3,               // 3 losses shutdown
  "SLIPPAGE_TOLERANCE": "0.003"              // 0.3% slippage
}
```

### Moderate (After Validation)

After 1+ weeks of successful operation:

```json
{
  "BASE_PROFIT_THRESHOLD": "0.01",           // 1% profit
  "MAX_POSITION_SIZE_USD": 1000,             // $1000 positions
  "DAILY_LOSS_LIMIT_USD": 2000,              // $2000 daily loss
  "MAX_CONSECUTIVE_LOSSES": 5,               // 5 losses shutdown
  "SLIPPAGE_TOLERANCE": "0.005"              // 0.5% slippage
}
```

### Aggressive (Only if Consistently Profitable)

Only after 1+ months of consistent profitability:

```json
{
  "BASE_PROFIT_THRESHOLD": "0.005",          // 0.5% profit
  "MAX_POSITION_SIZE_USD": 5000,             // $5000 positions
  "DAILY_LOSS_LIMIT_USD": 5000,              // $5000 daily loss
  "MAX_CONSECUTIVE_LOSSES": 7,               // 7 losses shutdown
  "SLIPPAGE_TOLERANCE": "0.005"              // 0.5% slippage
}
```

## Configuration Option Details

### BASE_PROFIT_THRESHOLD

**Type:** Decimal (string)
**Range:** 0.001 - 0.10 (0.1% - 10%)
**Default:** 0.005 (0.5%)

Minimum profit percentage required to execute trade (after gas).

**Lower values:**
- More opportunities found
- Lower profit per trade
- Higher gas cost ratio

**Higher values:**
- Fewer opportunities
- Higher profit per trade
- Better risk/reward

### MAX_POSITION_SIZE_USD

**Type:** Integer
**Range:** 10 - 100000
**Default:** 10000

Maximum size for a single position in USD.

**Limits risk exposure per trade.**

### MAX_TOTAL_EXPOSURE_USD

**Type:** Integer
**Range:** 100 - 1000000
**Default:** 50000

Maximum total exposure across all positions.

**Prevents over-leverage.**

### DAILY_LOSS_LIMIT_USD

**Type:** Integer
**Range:** 100 - 100000
**Default:** 1000

Maximum acceptable loss in a single day. Bot stops when exceeded.

**Critical risk management parameter.**

### MAX_CONSECUTIVE_LOSSES

**Type:** Integer
**Range:** 1 - 20
**Default:** 5

Number of consecutive losses before circuit breaker activates.

**Lower = more conservative**
**Higher = tolerates more variance**

### SLIPPAGE_TOLERANCE

**Type:** Decimal (string)
**Range:** 0.001 - 0.05 (0.1% - 5%)
**Default:** 0.005 (0.5%)

Maximum acceptable slippage for trades.

**Lower = fewer filled trades, better prices**
**Higher = more filled trades, worse prices**

### GAS_LIMIT

**Type:** Integer
**Range:** 100000 - 1000000
**Default:** 300000

Gas limit for each transaction.

**Increase if trades fail with "out of gas"**

## Network-Specific Defaults

### Testnet (Mumbai)

```json
{
  "BASE_PROFIT_THRESHOLD": "0.01",           // 1%
  "MAX_POSITION_SIZE_USD": 100,
  "DAILY_LOSS_LIMIT_USD": 500,
  "MAX_CONSECUTIVE_LOSSES": 3,
  "GAS_LIMIT": 300000
}
```

### Mainnet

```json
{
  "BASE_PROFIT_THRESHOLD": "0.005",          // 0.5%
  "MAX_POSITION_SIZE_USD": 10000,
  "DAILY_LOSS_LIMIT_USD": 1000,
  "MAX_CONSECUTIVE_LOSSES": 5,
  "GAS_LIMIT": 300000
}
```

## Validation

After changing configuration:

```bash
# Test configuration loading
python src/bot/config.py

# Should show:
# ✓ Configuration loaded for testnet/mainnet
# ✓ Found X tokens
# ✓ Environment variables loaded
# ✓ Settings loaded: X parameters
# ✓ RPC connection successful
```

## Configuration Best Practices

1. **Start Conservative**
   - Low position sizes
   - High profit thresholds
   - Tight loss limits

2. **Test on Testnet First**
   - Validate all changes on Mumbai
   - Run for 24+ hours
   - Monitor for issues

3. **Scale Gradually**
   - Increase limits slowly
   - Monitor performance
   - Be ready to rollback

4. **Keep Backups**
   ```bash
   # Before changing config
   ./scripts/backup_config.sh
   ```

5. **Document Changes**
   - Keep changelog of config modifications
   - Note reasons for changes
   - Record results

## Advanced Configuration

### Custom RPC Endpoints

For better reliability, use dedicated RPC providers:

```bash
# In .env
POLYGON_MAINNET_RPC_URL=https://polygon-mainnet.g.alchemy.com/v2/YOUR-KEY
POLYGON_TESTNET_RPC_URL=https://polygon-mumbai.g.alchemy.com/v2/YOUR-KEY
```

Recommended providers:
- **Alchemy**: Free tier available
- **Infura**: Good reliability
- **QuickNode**: Fast, paid
- **Ankr**: Free public endpoints

### Multiple Token Pairs

Edit `token_pairs` in `src/bot/main.py`:

```python
self.token_pairs = [
    ("WETH", "USDC"),
    ("WETH", "USDT"),
    ("WETH", "DAI"),
    ("USDC", "USDT"),
    ("USDC", "DAI"),
    ("WMATIC", "USDC"),  # Add custom pairs
]
```

### Performance Tuning

For higher throughput:

```json
{
  "CHECK_INTERVAL_SECONDS": 5,              // Check more frequently
  "PRICE_CACHE_DURATION_SECONDS": 2,        // Shorter cache
  "MAX_RETRIES": 5                          // More retries
}
```

For lower resource usage:

```json
{
  "CHECK_INTERVAL_SECONDS": 30,             // Check less frequently
  "PRICE_CACHE_DURATION_SECONDS": 5,        // Longer cache
  "MAX_RETRIES": 2                          // Fewer retries
}
```

## Security Notes

1. **Never commit .env to git**
   ```bash
   # Add to .gitignore
   echo ".env" >> .gitignore
   ```

2. **Use strong ADMIN_CODE**
   ```bash
   # Generate random code
   openssl rand -base64 32
   ```

3. **Rotate PRIVATE_KEY periodically**
   - Every 3-6 months
   - After any security incident
   - When decommissioning bot

4. **Keep backups of working configs**
   ```bash
   # Regular backups
   ./scripts/backup_config.sh
   ```

5. **Test changes on testnet first**
   - Never test config changes on mainnet
   - Validate for 24+ hours on testnet
   - Monitor for unexpected behavior

## Troubleshooting Configuration

### Bot won't start after config change

```bash
# Validate JSON syntax
python -m json.tool config/config.json

# Test config loading
python src/bot/config.py

# Check logs
tail -100 logs/bot_*.log
```

### Settings not taking effect

```bash
# Ensure bot restarted after config change
pkill -f 'python3 -m src.bot.main'
python -m src.bot.main

# Verify settings loaded in logs
grep "Settings loaded" logs/bot_*.log
```

### Wrong network configured

```bash
# Check environment
grep ENVIRONMENT .env

# Verify chain ID
python -c "
from web3 import Web3
from src.bot.config import load_config
_, env, env_config, _ = load_config()
w3 = Web3(Web3.HTTPProvider(env_config['POLYGON_RPC_URL']))
print(f'Environment: {env}')
print(f'Chain ID: {w3.eth.chain_id}')
"
```
