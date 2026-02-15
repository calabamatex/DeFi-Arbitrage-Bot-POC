#!/usr/bin/env bash
#
# Path 2: Anvil Fork End-to-End Test
#
# Tests the FULL pipeline: deploy contracts → Python bot connects →
# detector scans → orchestrator builds transactions → dry-run execution.
#
# Usage:
#   ./script/anvil_e2e_test.sh
#
# Prerequisites:
#   - anvil, forge, cast installed (foundryup)
#   - Python venv with dependencies (.venv/)
#   - forge build completed
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# Anvil's well-known test account #0 (only safe on local forks)
ANVIL_KEY="0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
ANVIL_ADDR="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
RPC_URL="http://localhost:8545"
FORK_RPC="${POLYGON_RPC_URL:-https://polygon-bor-rpc.publicnode.com}"
ANVIL_PID=""

cleanup() {
    echo ""
    echo "Cleaning up..."
    if [ -n "$ANVIL_PID" ] && kill -0 "$ANVIL_PID" 2>/dev/null; then
        kill "$ANVIL_PID" 2>/dev/null || true
        wait "$ANVIL_PID" 2>/dev/null || true
        echo "  Anvil stopped (PID $ANVIL_PID)"
    fi
}
trap cleanup EXIT

echo "======================================================"
echo "  ANVIL FORK END-TO-END TEST"
echo "======================================================"
echo ""

# ── Step 1: Start Anvil forking Polygon ─────────────────────
echo "[1/5] Starting Anvil fork of Polygon mainnet..."
echo "  Fork RPC: ${FORK_RPC:0:50}..."

anvil \
    --fork-url "$FORK_RPC" \
    --chain-id 137 \
    --port 8545 \
    --silent &
ANVIL_PID=$!

# Wait for Anvil to be ready
for i in $(seq 1 30); do
    if cast chain-id --rpc-url "$RPC_URL" 2>/dev/null | grep -q "137"; then
        echo "  Anvil ready (PID $ANVIL_PID, Chain ID: 137)"
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "  ERROR: Anvil failed to start within 30 seconds"
        exit 1
    fi
    sleep 1
done

echo ""

# ── Step 2: Build contracts ─────────────────────────────────
echo "[2/5] Building contracts..."
forge build --quiet 2>&1 | tail -1 || true
echo "  Build complete"
echo ""

# ── Step 3: Deploy contracts to local fork ───────────────────
echo "[3/5] Deploying contracts to Anvil fork..."

# Load Polygon chain config for contract addresses
set -a
source "$SCRIPT_DIR/chains/polygon.env"
set +a

DEPLOY_OUTPUT=$(forge script script/Deploy.s.sol:DeployAll \
    --rpc-url "$RPC_URL" \
    --private-key "$ANVIL_KEY" \
    --broadcast \
    -vvv 2>&1)

# Parse deployed addresses from output
FLASH_LOAN_ARBITRAGE_ADDRESS=$(echo "$DEPLOY_OUTPUT" | grep "FlashLoanArbitrageV2:" | tail -1 | awk '{print $NF}')
UNISWAP_V3_ADAPTER_ADDRESS=$(echo "$DEPLOY_OUTPUT" | grep "UniswapV3Adapter:" | tail -1 | awk '{print $NF}')
UNISWAP_V2_ADAPTER_ADDRESS=$(echo "$DEPLOY_OUTPUT" | grep "UniswapV2Adapter:" | tail -1 | awk '{print $NF}')

if [ -z "$FLASH_LOAN_ARBITRAGE_ADDRESS" ] || [ -z "$UNISWAP_V3_ADAPTER_ADDRESS" ] || [ -z "$UNISWAP_V2_ADAPTER_ADDRESS" ]; then
    echo "  ERROR: Failed to parse deployed addresses"
    echo "$DEPLOY_OUTPUT" | tail -30
    exit 1
fi

echo "  FlashLoanArbitrageV2: $FLASH_LOAN_ARBITRAGE_ADDRESS"
echo "  UniswapV3Adapter:     $UNISWAP_V3_ADAPTER_ADDRESS"
echo "  UniswapV2Adapter:     $UNISWAP_V2_ADAPTER_ADDRESS"
echo ""

# ── Step 4: Verify deployment wiring ────────────────────────
echo "[4/5] Verifying deployment wiring..."

FLASH_LOAN_ARBITRAGE_ADDRESS="$FLASH_LOAN_ARBITRAGE_ADDRESS" \
UNISWAP_V3_ADAPTER_ADDRESS="$UNISWAP_V3_ADAPTER_ADDRESS" \
UNISWAP_V2_ADAPTER_ADDRESS="$UNISWAP_V2_ADAPTER_ADDRESS" \
forge script script/Verify.s.sol:VerifyDeployment \
    --rpc-url "$RPC_URL" \
    -vvv 2>&1 | grep -E "\[(OK|FAIL|WARN)\]|ALL CHECKS|FAILURES"

echo ""

# ── Step 5: Run Python E2E test ─────────────────────────────
echo "[5/5] Running Python end-to-end test against fork..."
echo ""

POLYGON_RPC_URL="$RPC_URL" \
PRIVATE_KEY="$ANVIL_KEY" \
FLASH_LOAN_ARBITRAGE_ADDRESS="$FLASH_LOAN_ARBITRAGE_ADDRESS" \
UNISWAP_V3_ADAPTER_ADDRESS="$UNISWAP_V3_ADAPTER_ADDRESS" \
UNISWAP_V2_ADAPTER_ADDRESS="$UNISWAP_V2_ADAPTER_ADDRESS" \
DRY_RUN="true" \
.venv/bin/python script/e2e_fork_test.py

echo ""
echo "======================================================"
echo "  E2E TEST COMPLETE"
echo "======================================================"
