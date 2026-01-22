#!/bin/bash
# Mainnet deployment - Interactive checklist

set -e

echo "========================================="
echo "Arbitrage Bot - MAINNET Deployment"
echo "========================================="
echo ""
echo "⚠️  WARNING: This will deploy to MAINNET with REAL MONEY"
echo ""

# Interactive confirmation
read -p "Have you completed 48+ hour testnet run? (yes/no): " testnet_run
if [ "$testnet_run" != "yes" ]; then
    echo "❌ Complete testnet validation first"
    exit 1
fi

read -p "Have you reviewed all security checks? (yes/no): " security
if [ "$security" != "yes" ]; then
    echo "❌ Complete security audit first"
    exit 1
fi

read -p "Is your .env configured for mainnet? (yes/no): " env_config
if [ "$env_config" != "yes" ]; then
    echo "❌ Configure .env for mainnet first"
    exit 1
fi

read -p "Do you have at least 5 MATIC on mainnet? (yes/no): " balance
if [ "$balance" != "yes" ]; then
    echo "❌ Insufficient mainnet MATIC"
    exit 1
fi

read -p "Have you setup monitoring alerts? (yes/no): " monitoring
if [ "$monitoring" != "yes" ]; then
    echo "❌ Setup monitoring first"
    exit 1
fi

echo ""
echo "Proceeding with mainnet deployment..."
echo ""

# Verify environment
source .env
if [ "$ENVIRONMENT" != "mainnet" ]; then
    echo "❌ ENVIRONMENT must be 'mainnet' in .env"
    exit 1
fi

# Run all checks
echo "Running pre-deployment checks..."

# Install dependencies
if [ -d "venv" ]; then
    source venv/bin/activate
    pip install -r requirements.txt --quiet
else
    pip install --break-system-packages -r requirements.txt --quiet
fi

# Test configuration
python3 src/bot/config.py
if [ $? -ne 0 ]; then
    echo "❌ Configuration test failed"
    exit 1
fi

# Run tests
pytest tests/ -v --tb=short -x
if [ $? -ne 0 ]; then
    echo "❌ Tests failed"
    exit 1
fi

# Verify mainnet connection
python3 -c "
from web3 import Web3
from src.bot.config import load_config

config, env, env_config, _ = load_config()
web3 = Web3(Web3.HTTPProvider(env_config['POLYGON_RPC_URL']))

chain_id = web3.eth.chain_id
if chain_id != 137:
    print(f'❌ Wrong chain: {chain_id}, expected 137 (Polygon Mainnet)')
    exit(1)

print('✓ Connected to Polygon Mainnet')
"

# Final confirmation
echo ""
echo "========================================="
echo "⚠️  FINAL CONFIRMATION"
echo "========================================="
echo ""
echo "You are about to deploy to MAINNET with REAL FUNDS"
echo ""
read -p "Type 'DEPLOY TO MAINNET' to continue: " confirm

if [ "$confirm" != "DEPLOY TO MAINNET" ]; then
    echo "❌ Deployment cancelled"
    exit 1
fi

echo ""
echo "Starting mainnet deployment..."

# Start bot with conservative settings
echo ""
echo "Starting bot in CONSERVATIVE mode..."
echo "  - Profit threshold: 2%"
echo "  - Max position: \$100"
echo "  - Daily loss limit: \$500"
echo ""

# Create startup script with conservative parameters
cat > start_mainnet.sh << 'EOF'
#!/bin/bash
python3 -m src.bot.main \
  --min-profit 0.02 \
  --max-position 100 \
  --daily-loss-limit 500
EOF

chmod +x start_mainnet.sh

echo "✅ Mainnet deployment complete"
echo ""
echo "To start:"
echo "  ./start_mainnet.sh"
echo ""
echo "IMPORTANT:"
echo "  - Monitor Telegram alerts constantly"
echo "  - Check logs every hour for first 24h"
echo "  - Be ready to emergency shutdown"
echo "  - Start with small positions"
echo ""
