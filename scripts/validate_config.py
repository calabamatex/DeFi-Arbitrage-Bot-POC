#!/usr/bin/env python3
"""
Configuration Validator

Checks all required env vars, connectivity, and contract addresses
before starting the bot. Run this before every deployment.

Usage:
    python scripts/validate_config.py
    python scripts/validate_config.py --chain polygon_amoy
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()


G = "\033[92m"  # green
R = "\033[91m"  # red
Y = "\033[93m"  # yellow
N = "\033[0m"   # reset


def check(label: str, condition: bool, detail: str = "") -> bool:
    if condition:
        print(f"  {G}PASS{N} {label}" + (f" — {detail}" if detail else ""))
    else:
        print(f"  {R}FAIL{N} {label}" + (f" — {detail}" if detail else ""))
    return condition


def warn(label: str, detail: str = ""):
    print(f"  {Y}WARN{N} {label}" + (f" — {detail}" if detail else ""))


def main():
    parser = argparse.ArgumentParser(description="Validate bot configuration")
    parser.add_argument("--chain", default=None, help="Specific chain to validate")
    args = parser.parse_args()

    print(f"\n{'=' * 50}")
    print("Configuration Validator")
    print(f"{'=' * 50}\n")

    passed = 0
    failed = 0

    # 1. Required env vars
    print("[1] Required Environment Variables")
    required_for_live = [
        ("FLASH_LOAN_ARBITRAGE_ADDRESS", "Arbitrage contract"),
        ("UNISWAP_V3_ADAPTER_ADDRESS", "V3 DEX adapter"),
        ("UNISWAP_V2_ADAPTER_ADDRESS", "V2 DEX adapter"),
    ]
    for var, desc in required_for_live:
        val = os.getenv(var)
        if val:
            passed += 1
            check(f"{var}", True, f"{val[:20]}...")
        else:
            warn(f"{var}", f"Not set ({desc}) — required before live execution")

    # 2. Private key
    print("\n[2] Private Key")
    ks = os.getenv("KEYSTORE_FILE")
    pk = os.getenv("PRIVATE_KEY")
    if ks:
        exists = os.path.exists(ks)
        r = check("KEYSTORE_FILE", exists, ks if exists else "File not found")
        passed += exists
        failed += not exists
    elif pk:
        warn("PRIVATE_KEY", "Set via env var (keystore recommended for production)")
        passed += 1
    else:
        r = check("Private key", False, "Neither KEYSTORE_FILE nor PRIVATE_KEY set")
        failed += 1

    # 3. RPC connectivity
    print("\n[3] RPC Connectivity")
    from src.config import Config

    chains_to_check = [args.chain] if args.chain else Config.get_active_chains()
    for chain_name in chains_to_check:
        chain = Config.CHAINS.get(chain_name)
        if not chain:
            check(f"Chain {chain_name}", False, "Not in Config.CHAINS")
            failed += 1
            continue

        try:
            from web3 import Web3

            w3 = Web3(Web3.HTTPProvider(chain.rpc_url, request_kwargs={"timeout": 5}))
            connected = w3.is_connected()
            if connected:
                cid = w3.eth.chain_id
                block = w3.eth.block_number
                match = cid == chain.chain_id
                check(f"{chain_name}", match, f"chain_id={cid} block={block}")
                passed += match
                failed += not match
            else:
                check(f"{chain_name}", False, f"Cannot connect to {chain.rpc_url[:40]}")
                failed += 1
        except Exception as e:
            check(f"{chain_name}", False, str(e)[:60])
            failed += 1

    # 4. Database
    print("\n[4] Database")
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        try:
            from src.db.database import check_db_connection

            ok = check_db_connection()
            check("Database connection", ok)
            passed += ok
            failed += not ok
        except Exception as e:
            check("Database connection", False, str(e)[:60])
            failed += 1
    else:
        warn("DATABASE_URL", "Not set — database features disabled")

    # 5. Config validation
    print("\n[5] Config Validation")
    try:
        Config.validate()
        check("Config.validate()", True)
        passed += 1
    except ValueError as e:
        check("Config.validate()", False, str(e)[:80])
        failed += 1

    # 6. Execution mode
    print("\n[6] Execution Mode")
    mode = Config.EXECUTION_MODE
    dry_run = Config.DRY_RUN
    print(f"  Mode: {mode}")
    print(f"  Dry run: {dry_run}")
    if mode == "mainnet" and not dry_run:
        warn("LIVE EXECUTION", "DRY_RUN=false on mainnet — ensure this is intentional")

    # 7. Security Validation
    print("\n[7] Security Validation")
    has_critical_security = False
    try:
        issues = Config.validate_security()
        if not issues:
            check("Security validation", True, "No issues found")
            passed += 1
        else:
            for sev, msg in issues:
                if sev == "CRITICAL":
                    check(f"[{sev}] {msg}", False)
                    failed += 1
                    has_critical_security = True
                elif sev == "WARNING":
                    warn(f"[{sev}] {msg}")
                else:
                    print(f"  {Y}INFO{N} {msg}")
    except SystemExit:
        # validate_security() raises SystemExit on mainnet with CRITICAL issues
        check("Security validation", False, "CRITICAL issues found — blocked by fail-fast")
        failed += 1
        has_critical_security = True

    # 8. DEV_MODE Status
    print("\n[8] DEV_MODE Status")
    dev_mode = os.getenv("DEV_MODE", "false").lower() == "true"
    if dev_mode:
        warn("DEV_MODE=true", "Security fail-fast is bypassed — do NOT use in production")
    else:
        check("DEV_MODE", True, "Disabled (production-safe)")
        passed += 1

    # Summary
    print(f"\n{'=' * 50}")
    total = passed + failed
    print(f"Results: {G}{passed}{N} passed, {R}{failed}{N} failed (of {total} checks)")
    if has_critical_security:
        print(f"{R}CRITICAL security issues detected — resolve before deployment{N}")
    print(f"{'=' * 50}\n")

    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
