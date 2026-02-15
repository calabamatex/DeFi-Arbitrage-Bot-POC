#!/bin/bash
# Simple Testnet Deployment to Polygon Amoy

set -e

export PATH="$HOME/.foundry/bin:$PATH"

RPC="https://rpc-amoy.polygon.technology"
KEY="${PRIVATE_KEY:?Error: PRIVATE_KEY environment variable must be set}"

echo "🚀 Deploying to Polygon Amoy Testnet"
echo ""

cd contracts

# Deploy Mock USDC
echo "1. Deploying Mock USDC..."
USDC=$(forge create MockERC20 \
  --rpc-url $RPC \
  --private-key $KEY \
  --constructor-args "MockUSDC" "USDC" 6 \
  --broadcast \
  --json | jq -r '.deployedTo')
echo "   ✅ $USDC"

# Deploy FlashLoanArbitrageV2
echo "2. Deploying FlashLoanArbitrageV2..."
FLASH=$(forge create FlashLoanArbitrageV2 \
  --rpc-url $RPC \
  --private-key $KEY \
  --constructor-args "0x4CeDCB57Af02293231BAA9D39354D6BFDFD251e0" \
  --broadcast \
  --json | jq -r '.deployedTo')
echo "   ✅ $FLASH"

cd ..

# Save to file
cat > testnet_addresses.txt <<EOF
Polygon Amoy Testnet Deployment

Mock USDC:              $USDC
FlashLoanArbitrageV2:   $FLASH

View on Explorer:
https://amoy.polygonscan.com/address/$FLASH
EOF

echo ""
echo "🎉 Deployment complete!"
echo ""
cat testnet_addresses.txt
