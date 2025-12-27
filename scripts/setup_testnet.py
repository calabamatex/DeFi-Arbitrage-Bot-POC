#!/usr/bin/env python3
"""
Setup testnet account with tokens from faucets.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from web3 import Web3
from src.bot.config import load_config, load_env_vars


def main():
    print("=" * 60)
    print("Testnet Setup Helper")
    print("=" * 60)
    print()

    config, env, env_config, token_list = load_config()

    if env != "testnet":
        print("❌ This script is for testnet only!")
        print(f"   Current environment: {env}")
        sys.exit(1)

    private_key, _, _ = load_env_vars()
    web3 = Web3(Web3.HTTPProvider(env_config["POLYGON_RPC_URL"]))
    account = web3.eth.account.from_key(private_key)

    print(f"Account: {account.address}")
    print()

    print("Step 1: Get Mumbai MATIC")
    print("  Visit: https://faucet.polygon.technology/")
    print(f"  Send to: {account.address}")
    print("  Amount: Request 5+ MATIC")
    print()

    input("Press Enter after you've received MATIC...")

    # Check MATIC balance
    balance = web3.eth.get_balance(account.address)
    balance_matic = balance / 10**18

    if balance_matic < 0.5:
        print(f"❌ Still insufficient MATIC: {balance_matic:.6f}")
        sys.exit(1)

    print(f"✓ MATIC balance: {balance_matic:.6f}")
    print()

    print("Step 2: Get testnet tokens")
    print()
    print("Option A - Uniswap V3 Testnet:")
    print("  Visit: https://app.uniswap.org/")
    print("  Switch to Polygon Mumbai network")
    print("  Swap some MATIC for WETH, USDC")
    print()
    print("Option B - Direct faucets (if available):")
    print("  WETH: Search for WETH Mumbai faucet")
    print("  USDC: Search for USDC Mumbai faucet")
    print()

    print("Step 3: Approve tokens on DEXes")
    print("  The bot will auto-approve on first use")
    print("  Or run approve script if available")
    print()

    print("✅ Setup guide complete")
    print()
    print("Next steps:")
    print("  1. Run: python scripts/check_balances.py")
    print("  2. Verify you have tokens")
    print("  3. Start bot: python -m src.bot.main")


if __name__ == "__main__":
    main()
