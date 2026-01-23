#!/bin/bash
# Deploy Flash Loan Arbitrage Bot to Polygon Mainnet

set -e

source .env

echo "================================================================================"
echo "🚀 DEPLOYING TO POLYGON MAINNET"
echo "================================================================================"
echo ""
echo "⚠️  WARNING: This will deploy to REAL Polygon mainnet"
echo "⚠️  Real MATIC will be spent on gas (~\$0.15-0.30)"
echo ""
read -p "Are you sure? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Deployment cancelled"
    exit 1
fi

echo ""
echo "Network: Polygon Mainnet"
echo "RPC: ${ALCHEMY_POLYGON_RPC_URL:0:50}..."
echo "Deployer: Using private key from .env"
echo ""

# Polygon mainnet addresses
UNISWAP_V3_ROUTER="0xE592427A0AEce92De3Edee1F18E0157C05861564"
UNISWAP_V3_QUOTER="0x61fFE014bA17989E743c5F6cB21bF9697530B21e"
QUICKSWAP_ROUTER="0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff"
AAVE_POOL_PROVIDER="0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb"

echo "================================================================================"
echo "1️⃣  Deploying UniswapV3AdapterFixed..."
echo "================================================================================"

V3_ADAPTER=$(~/.foundry/bin/forge create UniswapV3AdapterFixed \
    --rpc-url $ALCHEMY_POLYGON_RPC_URL \
    --private-key $PRIVATE_KEY \
    --constructor-args $UNISWAP_V3_ROUTER \
    --json 2>/dev/null | jq -r '.deployedTo')

if [ -z "$V3_ADAPTER" ] || [ "$V3_ADAPTER" == "null" ]; then
    echo "❌ Failed to deploy UniswapV3AdapterFixed"
    exit 1
fi

echo "✅ UniswapV3AdapterFixed: $V3_ADAPTER"
echo ""

sleep 2

echo "================================================================================"
echo "2️⃣  Deploying UniswapV2Adapter..."
echo "================================================================================"

V2_ADAPTER=$(~/.foundry/bin/forge create UniswapV2Adapter \
    --rpc-url $ALCHEMY_POLYGON_RPC_URL \
    --private-key $PRIVATE_KEY \
    --constructor-args $QUICKSWAP_ROUTER "QuickSwap" \
    --json 2>/dev/null | jq -r '.deployedTo')

if [ -z "$V2_ADAPTER" ] || [ "$V2_ADAPTER" == "null" ]; then
    echo "❌ Failed to deploy UniswapV2Adapter"
    exit 1
fi

echo "✅ UniswapV2Adapter: $V2_ADAPTER"
echo ""

sleep 2

echo "================================================================================"
echo "3️⃣  Deploying FlashLoanArbitrageV2..."
echo "================================================================================"

# minProfit: 100000 wei (0.0001 MATIC, very low for testing)
# maxSlippageBps: 500 (5%)
FLASH_LOAN=$(~/.foundry/bin/forge create FlashLoanArbitrageV2 \
    --rpc-url $ALCHEMY_POLYGON_RPC_URL \
    --private-key $PRIVATE_KEY \
    --constructor-args $AAVE_POOL_PROVIDER 100000 500 \
    --json 2>/dev/null | jq -r '.deployedTo')

if [ -z "$FLASH_LOAN" ] || [ "$FLASH_LOAN" == "null" ]; then
    echo "❌ Failed to deploy FlashLoanArbitrageV2"
    exit 1
fi

echo "✅ FlashLoanArbitrageV2: $FLASH_LOAN"
echo ""

echo "================================================================================"
echo "4️⃣  Registering Adapters..."
echo "================================================================================"

# Create Python script to register adapters
cat > /tmp/register_adapters.py << 'PYEOF'
import os
import sys
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from eth_account import Account
from dotenv import load_dotenv

load_dotenv()

web3 = Web3(Web3.HTTPProvider(os.getenv('ALCHEMY_POLYGON_RPC_URL')))
web3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

account = Account.from_key(os.getenv('PRIVATE_KEY'))

flash_loan_addr = sys.argv[1]
v3_adapter = sys.argv[2]
v2_adapter = sys.argv[3]

abi = [{'inputs': [{'name': 'adapter', 'type': 'address'}, {'name': 'status', 'type': 'bool'}], 'name': 'setAdapter', 'outputs': [], 'stateMutability': 'nonpayable', 'type': 'function'}]

contract = web3.eth.contract(address=flash_loan_addr, abi=abi)

print("Registering V3 Adapter...")
tx1 = contract.functions.setAdapter(v3_adapter, True).build_transaction({
    'from': account.address,
    'nonce': web3.eth.get_transaction_count(account.address),
    'gas': 100000,
    'gasPrice': web3.eth.gas_price,
    'chainId': 137
})
signed1 = account.sign_transaction(tx1)
hash1 = web3.eth.send_raw_transaction(signed1.raw_transaction)
web3.eth.wait_for_transaction_receipt(hash1)
print(f"✅ V3 Adapter registered")

print("\nRegistering V2 Adapter...")
tx2 = contract.functions.setAdapter(v2_adapter, True).build_transaction({
    'from': account.address,
    'nonce': web3.eth.get_transaction_count(account.address),
    'gas': 100000,
    'gasPrice': web3.eth.gas_price,
    'chainId': 137
})
signed2 = account.sign_transaction(tx2)
hash2 = web3.eth.send_raw_transaction(signed2.raw_transaction)
web3.eth.wait_for_transaction_receipt(hash2)
print(f"✅ V2 Adapter registered")
PYEOF

./venv/bin/python /tmp/register_adapters.py $FLASH_LOAN $V3_ADAPTER $V2_ADAPTER

echo ""
echo "================================================================================"
echo "✅ DEPLOYMENT COMPLETE!"
echo "================================================================================"
echo ""
echo "Deployed Contracts:"
echo "  FlashLoanArbitrageV2:   $FLASH_LOAN"
echo "  UniswapV3AdapterFixed:  $V3_ADAPTER"
echo "  UniswapV2Adapter:       $V2_ADAPTER"
echo ""
echo "View on PolygonScan:"
echo "  https://polygonscan.com/address/$FLASH_LOAN"
echo ""

# Update .env file
echo ""
echo "================================================================================"
echo "5️⃣  Updating .env file..."
echo "================================================================================"

# Backup current .env
cp .env .env.backup

# Update addresses
sed -i.bak "s|^FLASH_LOAN_ARBITRAGE_ADDRESS=.*|FLASH_LOAN_ARBITRAGE_ADDRESS=$FLASH_LOAN|" .env
sed -i.bak "s|^UNISWAP_V3_ADAPTER_ADDRESS=.*|UNISWAP_V3_ADAPTER_ADDRESS=$V3_ADAPTER|" .env
sed -i.bak "s|^UNISWAP_V2_ADAPTER_ADDRESS=.*|UNISWAP_V2_ADAPTER_ADDRESS=$V2_ADAPTER|" .env

# Ensure mainnet RPC
sed -i.bak "s|^POLYGON_RPC_URL=.*|POLYGON_RPC_URL=$ALCHEMY_POLYGON_RPC_URL|" .env

# Ensure DRY_RUN is true
sed -i.bak "s|^DRY_RUN=.*|DRY_RUN=true|" .env

rm .env.bak

echo "✅ .env updated with mainnet addresses"
echo ""

# Save deployment info
cat > mainnet_deployment.json << EOF
{
  "network": "Polygon Mainnet",
  "chainId": 137,
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "contracts": {
    "FlashLoanArbitrageV2": "$FLASH_LOAN",
    "UniswapV3AdapterFixed": "$V3_ADAPTER",
    "UniswapV2Adapter": "$V2_ADAPTER"
  },
  "polygonscan": {
    "FlashLoanArbitrageV2": "https://polygonscan.com/address/$FLASH_LOAN",
    "UniswapV3AdapterFixed": "https://polygonscan.com/address/$V3_ADAPTER",
    "UniswapV2Adapter": "https://polygonscan.com/address/$V2_ADAPTER"
  }
}
EOF

echo "✅ Deployment info saved to mainnet_deployment.json"
echo ""

echo "================================================================================"
echo "🎉 READY FOR DRY_RUN OBSERVATION MODE"
echo "================================================================================"
echo ""
echo "Next steps:"
echo "  1. Review .env to confirm DRY_RUN=true"
echo "  2. Run: python run_bot.py"
echo "  3. Bot will scan for opportunities but NOT execute"
echo "  4. Observe for 1-2 weeks"
echo "  5. Analyze results before enabling execution"
echo ""
