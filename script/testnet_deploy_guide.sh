#!/usr/bin/env bash
#
# Arbitrum Sepolia Testnet Deployment Guide
#
# This script walks through deploying to a LIVE testnet.
# It checks prerequisites before attempting deployment.
#
# Prerequisites:
#   1. Funded wallet on Arbitrum Sepolia (get ETH from faucet)
#   2. Foundry keystore set up: cast wallet import deployer --interactive
#   3. ARBITRUM_SEPOLIA_RPC_URL set in .env or environment
#
# Usage:
#   ./script/testnet_deploy_guide.sh              # check prerequisites
#   ./script/testnet_deploy_guide.sh --deploy      # actually deploy
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

ACCOUNT="${ACCOUNT:-deployer}"
CHAIN="arbitrum_sepolia"
RPC_URL="${ARBITRUM_SEPOLIA_RPC_URL:-https://sepolia-rollup.arbitrum.io/rpc}"

echo "======================================================"
echo "  ARBITRUM SEPOLIA TESTNET DEPLOYMENT"
echo "======================================================"
echo ""

# ── Check 1: Foundry keystore ────────────────────────────────
echo "[1/5] Checking Foundry keystore..."
KEYSTORE_DIR="${HOME}/.foundry/keystores"
if [ -f "${KEYSTORE_DIR}/${ACCOUNT}" ]; then
    echo "  OK: Keystore found for '${ACCOUNT}'"
else
    echo "  MISSING: No keystore for '${ACCOUNT}'"
    echo ""
    echo "  To create one:"
    echo "    cast wallet import ${ACCOUNT} --interactive"
    echo ""
    echo "  This will ask for your private key and a password."
    echo "  The key is encrypted at: ${KEYSTORE_DIR}/${ACCOUNT}"
    echo ""
    exit 1
fi

# ── Check 2: RPC connectivity ────────────────────────────────
echo "[2/5] Checking Arbitrum Sepolia RPC..."
CHAIN_ID=$(cast chain-id --rpc-url "$RPC_URL" 2>/dev/null || echo "FAIL")
if [ "$CHAIN_ID" = "421614" ]; then
    echo "  OK: Connected (Chain ID: 421614)"
else
    echo "  FAIL: Cannot connect to $RPC_URL"
    echo "  Set ARBITRUM_SEPOLIA_RPC_URL in .env or environment"
    exit 1
fi

# ── Check 3: Wallet balance ──────────────────────────────────
echo "[3/5] Checking wallet balance..."
# Get address from keystore
DEPLOYER_ADDR=$(cast wallet address --account "$ACCOUNT" 2>/dev/null || echo "FAIL")
if [ "$DEPLOYER_ADDR" = "FAIL" ]; then
    echo "  FAIL: Could not read address from keystore"
    echo "  You may need to enter your keystore password"
    exit 1
fi
echo "  Address: $DEPLOYER_ADDR"

BALANCE=$(cast balance "$DEPLOYER_ADDR" --rpc-url "$RPC_URL" 2>/dev/null || echo "0")
BALANCE_ETH=$(cast from-wei "$BALANCE" 2>/dev/null || echo "0")
echo "  Balance: $BALANCE_ETH ETH"

# Need ~0.01 ETH for deployment (~3 contract deploys + 4 config txs)
MIN_BALANCE="10000000000000000"  # 0.01 ETH in wei
if [ "$(echo "$BALANCE" | tr -d '[:space:]')" -lt "$MIN_BALANCE" ] 2>/dev/null; then
    echo ""
    echo "  WARNING: Balance may be insufficient for deployment"
    echo "  Need ~0.01 ETH. Get testnet ETH from:"
    echo "    https://faucet.quicknode.com/arbitrum/sepolia"
    echo "    https://www.alchemy.com/faucets/arbitrum-sepolia"
    echo ""
    if [ "${1:-}" != "--deploy" ]; then
        exit 1
    fi
fi

# ── Check 4: Build contracts ─────────────────────────────────
echo "[4/5] Building contracts..."
forge build --quiet 2>&1 | tail -1 || true
echo "  Build complete"

# ── Check 5: Chain config ────────────────────────────────────
echo "[5/5] Loading chain config..."
set -a
source "$SCRIPT_DIR/chains/${CHAIN}.env"
set +a
echo "  Aave Pool Provider: $AAVE_POOL_PROVIDER"
echo "  V3 Router:          $UNISWAP_V3_ROUTER"
echo "  V3 Quoter:          $UNISWAP_V3_QUOTER"
echo "  V2 Router:          $V2_ROUTER"
echo ""

# ── Deploy ────────────────────────────────────────────────────
if [ "${1:-}" = "--deploy" ]; then
    echo "======================================================"
    echo "  DEPLOYING TO ARBITRUM SEPOLIA (LIVE TESTNET)"
    echo "======================================================"
    echo ""

    forge script script/Deploy.s.sol:DeployAll \
        --rpc-url "$RPC_URL" \
        --account "$ACCOUNT" \
        --broadcast \
        -vvvv

    echo ""
    echo "======================================================"
    echo "  DEPLOYMENT COMPLETE"
    echo "======================================================"
    echo ""
    echo "Next steps:"
    echo "  1. Copy the deployed addresses to your .env"
    echo "  2. Verify: forge script script/Verify.s.sol:VerifyDeployment \\"
    echo "       --rpc-url \$ARBITRUM_SEPOLIA_RPC_URL -vvvv"
    echo "  3. Verify on Arbiscan (optional):"
    echo "       forge verify-contract <ADDRESS> FlashLoanArbitrageV2 \\"
    echo "         --chain arbitrum-sepolia --etherscan-api-key \$ARBISCAN_API_KEY"
else
    echo "======================================================"
    echo "  ALL PREREQUISITES MET"
    echo "======================================================"
    echo ""
    echo "  To deploy, run:"
    echo "    ./script/testnet_deploy_guide.sh --deploy"
    echo ""
    echo "  Or use deploy.sh directly:"
    echo "    ./script/deploy.sh arbitrum_sepolia --broadcast"
fi
