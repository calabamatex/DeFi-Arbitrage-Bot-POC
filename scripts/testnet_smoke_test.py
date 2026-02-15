#!/usr/bin/env python3
"""
Testnet Smoke Test

Verifies post-deployment health:
  1. RPC connection
  2. Chain ID matches expected
  3. Contract deployment (if address configured)
  4. Database connectivity
  5. Config validation
  6. Module imports

Usage:
    python scripts/testnet_smoke_test.py --chain polygon_amoy
    python scripts/testnet_smoke_test.py --chain arbitrum_sepolia
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()


def green(msg: str) -> str:
    return f"\033[92mPASS\033[0m {msg}"


def red(msg: str) -> str:
    return f"\033[91mFAIL\033[0m {msg}"


def yellow(msg: str) -> str:
    return f"\033[93mSKIP\033[0m {msg}"


def main():
    parser = argparse.ArgumentParser(description="Testnet smoke test")
    parser.add_argument(
        "--chain",
        required=True,
        choices=["polygon_amoy", "arbitrum_sepolia"],
    )
    args = parser.parse_args()

    results = []
    chain = args.chain

    print(f"\n{'=' * 50}")
    print(f"Smoke Test: {chain}")
    print(f"{'=' * 50}\n")

    # 1. Config validation
    try:
        from src.config import Config

        chain_config = Config.CHAINS.get(chain)
        assert chain_config is not None, f"Chain {chain} not in Config.CHAINS"
        results.append(green(f"Config: chain '{chain}' found (ID: {chain_config.chain_id})"))
    except Exception as e:
        results.append(red(f"Config: {e}"))

    # 2. RPC connection
    try:
        from web3 import Web3

        rpc_map = {
            "polygon_amoy": "POLYGON_AMOY_RPC_URL",
            "arbitrum_sepolia": "ARBITRUM_SEPOLIA_RPC_URL",
        }
        rpc_env = rpc_map[chain]
        rpc_url = os.getenv(rpc_env, chain_config.rpc_url)

        w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 10}))
        connected = w3.is_connected()
        assert connected, "Not connected"
        actual_chain_id = w3.eth.chain_id
        assert actual_chain_id == chain_config.chain_id, (
            f"Chain ID mismatch: expected {chain_config.chain_id}, got {actual_chain_id}"
        )
        block = w3.eth.block_number
        results.append(green(f"RPC: connected to {rpc_url[:40]}... (block {block})"))
    except Exception as e:
        results.append(red(f"RPC: {e}"))

    # 3. Contract check (if configured)
    contract_addr = os.getenv("FLASH_LOAN_ARBITRAGE_ADDRESS")
    if contract_addr:
        try:
            code = w3.eth.get_code(w3.to_checksum_address(contract_addr))
            assert len(code) > 2, "No code at address (not deployed)"
            results.append(green(f"Contract: {contract_addr[:20]}... has code"))
        except Exception as e:
            results.append(red(f"Contract: {e}"))
    else:
        results.append(yellow("Contract: FLASH_LOAN_ARBITRAGE_ADDRESS not set"))

    liquidator_addr = os.getenv("FLASH_LOAN_LIQUIDATOR_ADDRESS")
    if liquidator_addr:
        try:
            code = w3.eth.get_code(w3.to_checksum_address(liquidator_addr))
            assert len(code) > 2, "No code at address"
            results.append(green(f"Liquidator: {liquidator_addr[:20]}... has code"))
        except Exception as e:
            results.append(red(f"Liquidator: {e}"))
    else:
        results.append(yellow("Liquidator: FLASH_LOAN_LIQUIDATOR_ADDRESS not set"))

    # 4. Database connectivity
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        try:
            from src.db.database import check_db_connection

            assert check_db_connection(), "check_db_connection() returned False"
            results.append(green("Database: connected"))
        except Exception as e:
            results.append(red(f"Database: {e}"))
    else:
        results.append(yellow("Database: DATABASE_URL not set"))

    # 5. Module imports
    modules = [
        "src.opportunity_detector",
        "src.flash_loan_orchestrator",
        "src.liquidation_detector",
        "src.liquidation_orchestrator",
        "src.utils.risk_manager",
        "src.utils.metrics_collector",
        "src.utils.gas_optimizer",
        "src.utils.price_cache",
        "src.utils.logging_config",
    ]
    import importlib

    for mod_name in modules:
        try:
            importlib.import_module(mod_name)
            results.append(green(f"Import: {mod_name}"))
        except Exception as e:
            results.append(red(f"Import {mod_name}: {e}"))

    # Summary
    print()
    for r in results:
        print(f"  {r}")

    passed = sum(1 for r in results if "PASS" in r)
    failed = sum(1 for r in results if "FAIL" in r)
    skipped = sum(1 for r in results if "SKIP" in r)

    print(f"\n{'=' * 50}")
    print(f"Results: {passed} passed, {failed} failed, {skipped} skipped")
    print(f"{'=' * 50}\n")

    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
