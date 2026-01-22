#!/bin/bash
# Prepare for mainnet deployment

echo "========================================="
echo "Mainnet Deployment Preparation"
echo "========================================="
echo ""

# 1. Backup current configuration
echo "1. Creating backup..."
./scripts/backup_config.sh
echo "✓ Backup created"
echo ""

# 2. Create mainnet .env
echo "2. Creating mainnet .env..."

if [ ! -f .env.mainnet ]; then
    cat > .env.mainnet << 'EOF'
# MAINNET CONFIGURATION
# ⚠️  REAL MONEY - BE CAREFUL!

# Environment
ENVIRONMENT=mainnet

# Wallet (USE DEDICATED WALLET)
PRIVATE_KEY=0x_YOUR_MAINNET_PRIVATE_KEY_HERE

# Telegram
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id

# Admin code (USE STRONG CODE)
ADMIN_CODE=your_secure_admin_code_here

# RPC (Use reliable provider)
POLYGON_RPC_URL=https://polygon-rpc.com/
EOF

    echo "✓ Created .env.mainnet template"
    echo "⚠️  IMPORTANT: Edit .env.mainnet with your mainnet credentials"
else
    echo "✓ .env.mainnet already exists"
fi
echo ""

# 3. Create conservative mainnet config
echo "3. Creating conservative mainnet config..."

cat > config/config.mainnet.json << 'EOF'
{
  "mainnet": {
    "POLYGON_RPC_URL": "https://polygon-rpc.com/",
    "CHAIN_ID": 137,
    "UNISWAP_V3_ROUTER": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
    "UNISWAP_V3_QUOTER": "0xb27308f9F90D607463bb33eA1BeBb41C27CE5AB6",
    "SUSHISWAP_ROUTER": "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506",
    "QUICKSWAP_ROUTER": "0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff",
    "WMATIC_ADDRESS": "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270",
    "USDC_ADDRESS": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
    "WETH_ADDRESS": "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619",
    "DAI_ADDRESS": "0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063",
    "MULTICALL3_ADDRESS": "0xcA11bde05977b3631167028862bE2a173976CA11"
  },
  "settings": {
    "BASE_PROFIT_THRESHOLD": "0.02",
    "SLIPPAGE_TOLERANCE": "0.003",
    "MAX_PRICE_IMPACT": "0.01",
    "MAX_POSITION_SIZE_USD": 100,
    "MAX_TOTAL_EXPOSURE_USD": 500,
    "MAX_CONCENTRATION": "0.30",
    "DAILY_LOSS_LIMIT_USD": 500,
    "WEEKLY_LOSS_LIMIT_USD": 2500,
    "MAX_CONSECUTIVE_LOSSES": 3,
    "CIRCUIT_BREAKER_COOLDOWN_MIN": 120,
    "GAS_LIMIT": 300000,
    "GAS_MULTIPLIER": "1.1",
    "MAX_RETRIES": 3,
    "CHECK_INTERVAL_SECONDS": 30,
    "CACHE_DURATION_SECONDS": 3
  }
}
EOF

echo "✓ Conservative mainnet config created"
echo ""

# 4. Pre-flight checklist
echo "4. Pre-Flight Checklist:"
echo ""

echo "Manual checks required:"
echo "  [ ] Reviewed validation run results (48-hour testnet)"
echo "  [ ] Validation run PASSED"
echo "  [ ] All tests passed"
echo "  [ ] Security audit complete"
echo "  [ ] Mainnet wallet created (DEDICATED wallet)"
echo "  [ ] Mainnet wallet funded (5+ MATIC)"
echo "  [ ] Trading capital deposited (\$1000+ recommended)"
echo "  [ ] Private key backed up offline"
echo "  [ ] Telegram alerts tested"
echo "  [ ] Team ready for 24/7 monitoring"
echo "  [ ] Emergency procedures documented"
echo "  [ ] Backup recovery tested"
echo ""

echo "Configuration files created:"
echo "  ✓ .env.mainnet (template)"
echo "  ✓ config/config.mainnet.json (conservative settings)"
echo ""

echo "To proceed:"
echo "  1. Complete manual checklist above"
echo "  2. Edit .env.mainnet with your credentials:"
echo "     nano .env.mainnet"
echo "  3. Set secure file permissions:"
echo "     chmod 600 .env.mainnet"
echo "  4. Review mainnet config:"
echo "     cat config/config.mainnet.json"
echo "  5. Activate mainnet environment:"
echo "     cp .env.mainnet .env"
echo "     cp config/config.mainnet.json config/config.json"
echo "  6. Verify configuration:"
echo "     python3 src/bot/config.py"
echo "  7. Check balances:"
echo "     ./scripts/check_balances.py"
echo "  8. Run deployment script:"
echo "     ./scripts/deploy_mainnet.sh"
echo ""

echo "⚠️  WARNING: Mainnet deployment involves REAL MONEY!"
echo "⚠️  Only proceed if you've completed 48-hour testnet validation!"
echo ""
