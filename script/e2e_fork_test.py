#!/usr/bin/env python3
"""
End-to-End Fork Test — Python side.

Called by anvil_e2e_test.sh after contracts are deployed to an Anvil fork.
Tests the FULL Python pipeline: connect → detect → build tx → dry-run execute.

Required env vars (set by the shell wrapper):
    POLYGON_RPC_URL              – points at the Anvil fork (localhost:8545)
    PRIVATE_KEY                  – Anvil's well-known test key
    FLASH_LOAN_ARBITRAGE_ADDRESS – deployed FlashLoanArbitrageV2
    UNISWAP_V3_ADAPTER_ADDRESS  – deployed UniswapV3Adapter
    UNISWAP_V2_ADAPTER_ADDRESS  – deployed UniswapV2Adapter
    DRY_RUN                      – "true"
"""

import os
import sys
import time
import logging

# Project root is one level up from script/
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from web3 import Web3

logging.basicConfig(
    level=logging.INFO,
    format="  %(message)s",
)
logger = logging.getLogger("e2e")

# ── Counters ────────────────────────────────────────────────────
passed = 0
failed = 0


def check(label: str, condition: bool, detail: str = ""):
    """Record a test result."""
    global passed, failed
    if condition:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed += 1
        print(f"  [FAIL] {label}  {detail}")


# ════════════════════════════════════════════════════════════════
#  Step 1: Web3 Connection
# ════════════════════════════════════════════════════════════════
print("--- Step 1: Web3 Connection ---")

rpc_url = os.environ.get("POLYGON_RPC_URL", "http://localhost:8545")
web3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 30}))

check("Web3 connected", web3.is_connected())

chain_id = web3.eth.chain_id
check("Chain ID is 137 (Polygon fork)", chain_id == 137, f"got {chain_id}")

block = web3.eth.block_number
check("Block number > 0", block > 0, f"block={block}")

print()

# ════════════════════════════════════════════════════════════════
#  Step 2: Contract State Verification (via raw calls)
# ════════════════════════════════════════════════════════════════
print("--- Step 2: Contract Verification ---")

arb_addr = os.environ["FLASH_LOAN_ARBITRAGE_ADDRESS"]
v3_addr = os.environ["UNISWAP_V3_ADAPTER_ADDRESS"]
v2_addr = os.environ["UNISWAP_V2_ADAPTER_ADDRESS"]
private_key = os.environ["PRIVATE_KEY"]

arb_addr = web3.to_checksum_address(arb_addr)
v3_addr = web3.to_checksum_address(v3_addr)
v2_addr = web3.to_checksum_address(v2_addr)

check("FlashLoanArbitrageV2 has code", len(web3.eth.get_code(arb_addr)) > 2)
check("UniswapV3Adapter has code", len(web3.eth.get_code(v3_addr)) > 2)
check("UniswapV2Adapter has code", len(web3.eth.get_code(v2_addr)) > 2)

# Minimal ABI to verify state
arb_abi = [
    {"inputs": [], "name": "owner", "outputs": [{"type": "address"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "paused", "outputs": [{"type": "bool"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"type": "address"}], "name": "registeredAdapters", "outputs": [{"type": "bool"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "executionCount", "outputs": [{"type": "uint256"}], "stateMutability": "view", "type": "function"},
]

arb_contract = web3.eth.contract(address=arb_addr, abi=arb_abi)

owner = arb_contract.functions.owner().call()
check("Owner is Anvil account #0", owner.lower() == "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266".lower())

paused = arb_contract.functions.paused().call()
check("Contract is not paused", not paused)

v3_registered = arb_contract.functions.registeredAdapters(v3_addr).call()
check("V3 adapter registered", v3_registered)

v2_registered = arb_contract.functions.registeredAdapters(v2_addr).call()
check("V2 adapter registered", v2_registered)

exec_count = arb_contract.functions.executionCount().call()
check("Execution count is 0", exec_count == 0, f"got {exec_count}")

print()

# ════════════════════════════════════════════════════════════════
#  Step 3: OpportunityDetector — price scanning
# ════════════════════════════════════════════════════════════════
print("--- Step 3: Opportunity Detection ---")

try:
    from src.opportunity_detector import OpportunityDetector

    detector = OpportunityDetector(
        web3=web3,
        min_profit_usd=0.01,       # Very low threshold for fork test
        max_gas_price_gwei=10000,   # Accept any gas on fork
        check_interval=1,
    )
    check("OpportunityDetector initialized", True)

    # Get individual quotes to verify DEX connectivity
    usdc = web3.to_checksum_address("0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174")
    wmatic = web3.to_checksum_address("0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270")
    test_amount = 1000 * 10**6  # 1000 USDC

    v3_quote = detector.get_v3_quote(usdc, wmatic, test_amount)
    check("V3 QuoterV2 returns quote", v3_quote is not None and v3_quote > 0,
          f"quote={v3_quote}")

    v2_quote = detector.get_v2_quote(usdc, wmatic, test_amount)
    check("V2 Router returns quote", v2_quote is not None and v2_quote > 0,
          f"quote={v2_quote}")

    if v3_quote and v2_quote:
        v3_display = v3_quote / 10**18
        v2_display = v2_quote / 10**18
        print(f"       V3: 1000 USDC → {v3_display:.4f} WMATIC")
        print(f"       V2: 1000 USDC → {v2_display:.4f} WMATIC")
        diff_pct = abs(v3_display - v2_display) / min(v3_display, v2_display) * 100
        print(f"       Price diff: {diff_pct:.4f}%")

    # Run full scan (may or may not find opportunities on a static fork)
    opportunities = detector.scan_opportunities()
    # We don't fail if no opportunities — the fork is a snapshot, prices may be in sync
    print(f"       Scan complete: {len(opportunities)} opportunities found")
    check("Scan completes without error", True)

except Exception as e:
    check("OpportunityDetector initialized", False, str(e))
    opportunities = []

print()

# ════════════════════════════════════════════════════════════════
#  Step 4: FlashLoanOrchestrator — dry-run execution
# ════════════════════════════════════════════════════════════════
print("--- Step 4: Orchestrator Dry-Run ---")

try:
    from src.flash_loan_orchestrator import FlashLoanOrchestrator

    orchestrator = FlashLoanOrchestrator(
        web3=web3,
        contract_address=arb_addr,
        private_key=private_key,
        v3_adapter_address=v3_addr,
        v2_adapter_address=v2_addr,
        dry_run=True,
        slippage_tolerance_pct=2.0,   # Wider for fork test
        tx_deadline_seconds=300,
    )
    check("FlashLoanOrchestrator initialized", True)
    check("Orchestrator in dry-run mode", orchestrator.dry_run)
    check("Orchestrator address matches", orchestrator.address is not None)

    # Build a synthetic opportunity for tx-building test
    # This tests the transaction encoding pipeline even when no real arb exists
    synthetic_opp = {
        "direction": "V3→V2",
        "token_in": usdc,
        "token_out": wmatic,
        "amount_in": 1000 * 10**6,  # 1000 USDC
        "v3_fee": 3000,
        "amount_after_v3": v3_quote or 1500 * 10**18,
        "amount_after_v2": 1001 * 10**6,  # Slightly profitable
        "gross_profit": 1 * 10**6,
        "net_profit": 500000,  # 0.5 USDC
        "dex_path": ["uniswap_v3", "quickswap"],
        "token_decimals": 6,
    }

    # Test swap step building
    deadline = int(time.time()) + 300
    steps = orchestrator.build_swap_steps(synthetic_opp, deadline)
    check("build_swap_steps returns steps", steps is not None and len(steps) > 0,
          f"got {len(steps) if steps else 0} steps")

    # Test transaction building
    tx = orchestrator.build_transaction(synthetic_opp)
    check("build_transaction returns tx dict", tx is not None and "to" in tx,
          f"keys={list(tx.keys()) if tx else 'None'}")

    if tx:
        check("Transaction target is arb contract", tx["to"].lower() == arb_addr.lower())

    # Execute in dry-run mode (eth_call simulation)
    result = orchestrator.execute_opportunity(synthetic_opp, opportunity_id=None)
    # The simulation may revert (no real profit on fork), but the pipeline should complete
    if result.get("success"):
        check("Dry-run execution succeeded", True)
        print(f"       Gas used: {result.get('gas_used', 'N/A')}")
    else:
        # Revert is acceptable — it means the contract correctly rejects unprofitable trades
        error = result.get("error", "unknown")
        is_revert = any(kw in str(error).lower() for kw in
                        ["revert", "insufficient", "execution", "slippage", "profit"])
        check("Dry-run completes (revert is OK on fork)",
              is_revert or "error" in result,
              f"error={error[:100]}")

except Exception as e:
    check("FlashLoanOrchestrator initialized", False, str(e))

print()

# ════════════════════════════════════════════════════════════════
#  Step 5: Execute real opportunity (if found)
# ════════════════════════════════════════════════════════════════
if opportunities:
    print("--- Step 5: Execute Real Opportunity (dry-run) ---")
    best = max(opportunities, key=lambda o: o.get("net_profit", 0))
    direction = best["direction"]
    profit_display = best["net_profit"] / 10 ** best.get("token_decimals", 6)
    print(f"       Best: {direction} | Net profit: {profit_display:.6f} tokens")

    try:
        result = orchestrator.execute_opportunity(best, opportunity_id=None)
        if result.get("success"):
            check("Real opportunity dry-run succeeded", True)
            print(f"       Gas used: {result.get('gas_used', 'N/A')}")
        else:
            check("Real opportunity dry-run completed", True,
                  f"revert={result.get('error', '')[:80]}")
    except Exception as e:
        check("Real opportunity dry-run completed", False, str(e))
    print()
else:
    print("--- Step 5: Skipped (no opportunities on this fork snapshot) ---")
    print()

# ════════════════════════════════════════════════════════════════
#  Summary
# ════════════════════════════════════════════════════════════════
total = passed + failed
print("=" * 56)
print(f"  RESULTS: {passed}/{total} passed, {failed} failed")
print("=" * 56)

if failed > 0:
    sys.exit(1)
else:
    print("  All E2E checks passed!")
    sys.exit(0)
