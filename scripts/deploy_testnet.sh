#!/bin/bash
# Deploy bot to testnet (Mumbai)

set -e  # Exit on error

echo "========================================="
echo "Arbitrage Bot - Testnet Deployment"
echo "========================================="

# Check prerequisites
echo ""
echo "Checking prerequisites..."

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
if (( $(echo "$PYTHON_VERSION < 3.9" | bc -l) )); then
    echo "❌ Python 3.9+ required, found $PYTHON_VERSION"
    exit 1
fi
echo "✓ Python $PYTHON_VERSION"

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ .env file not found"
    echo "Please create .env from .env.example"
    exit 1
fi
echo "✓ .env file exists"

# Check environment is testnet
source .env
if [ "$ENVIRONMENT" != "testnet" ]; then
    echo "❌ ENVIRONMENT must be 'testnet' in .env"
    exit 1
fi
echo "✓ Environment set to testnet"

# Check private key exists
if [ -z "$PRIVATE_KEY" ]; then
    echo "❌ PRIVATE_KEY not set in .env"
    exit 1
fi
echo "✓ Private key configured"

# Install dependencies
echo ""
echo "Installing dependencies..."
if [ -d "venv" ]; then
    source venv/bin/activate
    pip install -r requirements.txt --quiet
else
    pip install --break-system-packages -r requirements.txt --quiet
fi
echo "✓ Dependencies installed"

# Run configuration test
echo ""
echo "Testing configuration..."
python3 src/bot/config.py
if [ $? -ne 0 ]; then
    echo "❌ Configuration test failed"
    exit 1
fi
echo "✓ Configuration valid"

# Run tests
echo ""
echo "Running test suite..."
pytest tests/ -v --tb=short -x
if [ $? -ne 0 ]; then
    echo "❌ Tests failed"
    exit 1
fi
echo "✓ All tests passed"

# Check Mumbai RPC connection
echo ""
echo "Testing Mumbai RPC connection..."
python3 -c "
from web3 import Web3
from src.bot.config import load_config

config, env, env_config, _ = load_config()
assert env == 'testnet', 'Should be using testnet'
web3 = Web3(Web3.HTTPProvider(env_config['POLYGON_RPC_URL']))

if not web3.is_connected():
    print('❌ Failed to connect to Mumbai RPC')
    exit(1)

chain_id = web3.eth.chain_id
if chain_id != 80001:
    print(f'❌ Wrong chain ID: {chain_id}, expected 80001 (Mumbai)')
    exit(1)

print(f'✓ Connected to Mumbai (Chain ID: {chain_id})')
print(f'✓ Current block: {web3.eth.block_number}')
"

# Check account balance
echo ""
echo "Checking account balance..."
python3 -c "
from decimal import Decimal
from web3 import Web3
from src.bot.config import load_config, load_env_vars

config, env, env_config, _ = load_config()
private_key, _, _ = load_env_vars()

web3 = Web3(Web3.HTTPProvider(env_config['POLYGON_RPC_URL']))
account = web3.eth.account.from_key(private_key)

balance_wei = web3.eth.get_balance(account.address)
balance_matic = Decimal(balance_wei) / Decimal(10**18)

print(f'Account: {account.address}')
print(f'Balance: {balance_matic:.6f} MATIC')

if balance_matic < Decimal('0.5'):
    print('⚠️  WARNING: Low MATIC balance for gas!')
    print('   Get testnet MATIC from: https://faucet.polygon.technology/')
"

# Create logs directory
echo ""
echo "Setting up directories..."
mkdir -p logs
mkdir -p data
mkdir -p backups
echo "✓ Directories created"

# Deployment summary
echo ""
echo "========================================="
echo "✅ Testnet Deployment Ready"
echo "========================================="
echo ""
echo "To start the bot:"
echo "  python3 -m src.bot.main"
echo ""
echo "To run in background:"
echo "  nohup python3 -m src.bot.main > logs/bot.log 2>&1 &"
echo ""
echo "To monitor logs:"
echo "  tail -f logs/bot.log"
echo ""
echo "To stop the bot:"
echo "  pkill -f 'python3 -m src.bot.main'"
echo ""
