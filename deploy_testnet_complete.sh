#!/bin/bash
# Complete Testnet Deployment Script
# Deploys all contracts to Polygon Amoy and sets up test environment

set -e

export PATH="$HOME/.foundry/bin:$PATH"

# Configuration
RPC_URL="https://rpc-amoy.polygon.technology"
PRIVATE_KEY="0xcf4cbdb74541d0dfe888271c7f9424c0fc7e62bcd0f50a72ae9363d112a55ff9"
AAVE_POOL_PROVIDER="0x4CeDCB57Af02293231BAA9D39354D6BFDFD251e0"
UNISWAP_V3_FACTORY="0x0227628f3F023bb0B980b67D528571c95c6DaC1c"

echo "============================================================"
echo "🚀 Deploying Flash Loan Arbitrage Bot to Polygon Amoy"
echo "============================================================"

cd contracts

# Check balance
echo ""
echo "1️⃣  Checking wallet balance..."
BALANCE=$(cast balance 0x21451Fc62F8Fce09E1a2Af8Abb0cED296Adb552E --rpc-url $RPC_URL)
BALANCE_MATIC=$(cast --to-unit $BALANCE ether)
echo "   Balance: $BALANCE_MATIC MATIC"

if (( $(echo "$BALANCE_MATIC < 0.05" | bc -l) )); then
    echo "   ❌ Insufficient balance for deployment"
    exit 1
fi

echo "   ✅ Sufficient balance"

# Deploy Mock Tokens for Testing
echo ""
echo "2️⃣  Deploying Mock USDC..."
MOCK_USDC=$(forge create MockERC20 \
    --rpc-url $RPC_URL \
    --private-key $PRIVATE_KEY \
    --constructor-args "Mock USDC" "USDC" 6 \
    --json | jq -r '.deployedTo')

echo "   ✅ Mock USDC deployed: $MOCK_USDC"

echo ""
echo "3️⃣  Deploying Mock WMATIC..."
MOCK_WMATIC=$(forge create MockERC20 \
    --rpc-url $RPC_URL \
    --private-key $PRIVATE_KEY \
    --constructor-args "Wrapped MATIC" "WMATIC" 18 \
    --json | jq -r '.deployedTo')

echo "   ✅ Mock WMATIC deployed: $MOCK_WMATIC"

# Deploy Main Contract
echo ""
echo "4️⃣  Deploying FlashLoanArbitrageV2..."
FLASH_LOAN=$(forge create FlashLoanArbitrageV2 \
    --rpc-url $RPC_URL \
    --private-key $PRIVATE_KEY \
    --constructor-args $AAVE_POOL_PROVIDER \
    --json | jq -r '.deployedTo')

echo "   ✅ FlashLoanArbitrageV2: $FLASH_LOAN"

# Deploy Adapters
echo ""
echo "5️⃣  Deploying UniswapV3Adapter..."
V3_ADAPTER=$(forge create adapters/UniswapV3Adapter \
    --rpc-url $RPC_URL \
    --private-key $PRIVATE_KEY \
    --constructor-args $UNISWAP_V3_FACTORY "UniswapV3" \
    --json | jq -r '.deployedTo')

echo "   ✅ UniswapV3Adapter: $V3_ADAPTER"

# Register V3 Adapter
echo ""
echo "6️⃣  Registering UniswapV3Adapter..."
cast send $FLASH_LOAN \
    "registerAdapter(address,bool)" \
    $V3_ADAPTER \
    true \
    --rpc-url $RPC_URL \
    --private-key $PRIVATE_KEY \
    --gas-limit 200000

echo "   ✅ Adapter registered"

# Save deployment info
echo ""
echo "7️⃣  Saving deployment info..."

cat > ../testnet_deployment.json <<EOF
{
  "network": "Polygon Amoy",
  "chainId": 80002,
  "deployer": "0x21451Fc62F8Fce09E1a2Af8Abb0cED296Adb552E",
  "contracts": {
    "FlashLoanArbitrageV2": "$FLASH_LOAN",
    "UniswapV3Adapter": "$V3_ADAPTER",
    "MockUSDC": "$MOCK_USDC",
    "MockWMATIC": "$MOCK_WMATIC"
  },
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

# Update .env.testnet
echo ""
echo "8️⃣  Updating .env.testnet..."

cd ..
sed -i.bak "s|^FLASH_LOAN_ARBITRAGE_ADDRESS=.*|FLASH_LOAN_ARBITRAGE_ADDRESS=$FLASH_LOAN|" .env.testnet
sed -i.bak "s|^UNISWAP_V3_ADAPTER_ADDRESS=.*|UNISWAP_V3_ADAPTER_ADDRESS=$V3_ADAPTER|" .env.testnet
sed -i.bak "s|^USDC_ADDRESS=.*|USDC_ADDRESS=$MOCK_USDC|" .env.testnet
sed -i.bak "s|^WMATIC_ADDRESS=.*|WMATIC_ADDRESS=$MOCK_WMATIC|" .env.testnet
rm -f .env.testnet.bak

echo "   ✅ Configuration updated"

# Summary
echo ""
echo "============================================================"
echo "🎉 Deployment Complete!"
echo "============================================================"
echo ""
echo "Deployed Contracts:"
echo "  FlashLoanArbitrageV2:  $FLASH_LOAN"
echo "  UniswapV3Adapter:      $V3_ADAPTER"
echo "  Mock USDC:             $MOCK_USDC"
echo "  Mock WMATIC:           $MOCK_WMATIC"
echo ""
echo "View on Explorer:"
echo "  https://amoy.polygonscan.com/address/$FLASH_LOAN"
echo ""
echo "Next Steps:"
echo "  1. Create test liquidity pools (manual)"
echo "  2. Run: cp .env.testnet .env"
echo "  3. Run: python run_bot.py"
echo ""
echo "Deployment saved to: testnet_deployment.json"
