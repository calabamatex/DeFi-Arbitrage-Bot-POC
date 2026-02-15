#!/usr/bin/env bash
#
# Deploy FlashLoanArbitrageV2 to a target chain.
#
# Usage:
#   ./script/deploy.sh polygon                         # dry run (default account: deployer)
#   ./script/deploy.sh polygon --broadcast             # actually deploy
#   ./script/deploy.sh arbitrum --broadcast --verify
#   ACCOUNT=mykey ./script/deploy.sh polygon --broadcast  # custom keystore account
#
# Prerequisites:
#   1. Import your key into Foundry's encrypted keystore:
#        cast wallet import deployer --interactive
#   2. Set the chain RPC URL (POLYGON_RPC_URL, etc.) in environment or .env
#   3. Run: forge build
#
# SECURITY: Private keys are loaded from Foundry's encrypted keystore
# (~/.foundry/keystores/). NEVER store keys in .env files.
#
set -euo pipefail

CHAIN="${1:?Usage: $0 <chain> [--broadcast] [--verify]}"
shift

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Keystore account name (default: "deployer")
ACCOUNT="${ACCOUNT:-deployer}"

# Check if keystore exists
KEYSTORE_DIR="${HOME}/.foundry/keystores"
if [ ! -f "${KEYSTORE_DIR}/${ACCOUNT}" ]; then
    echo "ERROR: No Foundry keystore found for account '${ACCOUNT}'"
    echo ""
    echo "To create one, run:"
    echo "  cast wallet import ${ACCOUNT} --interactive"
    echo ""
    echo "This will prompt for your private key and a password to encrypt it."
    echo "The encrypted keystore is stored at: ${KEYSTORE_DIR}/${ACCOUNT}"
    echo ""
    echo "NEVER store private keys in .env files."
    exit 1
fi

# Load .env for RPC URLs and contract addresses (NOT private keys)
if [ -f "$PROJECT_DIR/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "$PROJECT_DIR/.env"
    set +a
fi

# Load chain-specific env (contract addresses only)
CHAIN_ENV="$SCRIPT_DIR/chains/${CHAIN}.env"
if [ ! -f "$CHAIN_ENV" ]; then
    echo "ERROR: No chain config found at $CHAIN_ENV"
    echo "Available chains:"
    ls "$SCRIPT_DIR/chains/" 2>/dev/null | sed 's/\.env$//' | sed 's/^/  /'
    exit 1
fi

set -a
# shellcheck disable=SC1090
source "$CHAIN_ENV"
set +a

# Map chain name to RPC env var
case "$CHAIN" in
    polygon)          RPC_URL="${POLYGON_RPC_URL:?Set POLYGON_RPC_URL}" ;;
    arbitrum)         RPC_URL="${ARBITRUM_RPC_URL:?Set ARBITRUM_RPC_URL}" ;;
    arbitrum_sepolia) RPC_URL="${ARBITRUM_SEPOLIA_RPC_URL:?Set ARBITRUM_SEPOLIA_RPC_URL}" ;;
    optimism)         RPC_URL="${OPTIMISM_RPC_URL:?Set OPTIMISM_RPC_URL}" ;;
    base)             RPC_URL="${BASE_RPC_URL:?Set BASE_RPC_URL}" ;;
    *)                echo "ERROR: Unknown chain '$CHAIN'"; exit 1 ;;
esac

echo "======================================"
echo "  Deploying to: $CHAIN"
echo "  Account:  $ACCOUNT (Foundry keystore)"
echo "  RPC: ${RPC_URL:0:40}..."
echo "  Extra args: $*"
echo "======================================"

forge script script/Deploy.s.sol:DeployAll \
    --rpc-url "$RPC_URL" \
    --account "$ACCOUNT" \
    -vvvv \
    "$@"

echo ""
echo "To verify deployment, run:"
echo "  forge script script/Verify.s.sol:VerifyDeployment --rpc-url \$${CHAIN^^}_RPC_URL -vvvv"
