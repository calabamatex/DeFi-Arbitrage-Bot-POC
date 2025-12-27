#!/usr/bin/env python3
"""
Check token balances for the bot account.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from decimal import Decimal
from web3 import Web3
from src.bot.config import load_config, load_env_vars, get_erc20_abi


def main():
    print("=" * 60)
    print("Token Balance Checker")
    print("=" * 60)
    print()

    # Load config
    config, env, env_config, token_list = load_config()
    private_key, _, _ = load_env_vars()

    print(f"Environment: {env}")
    print()

    # Setup Web3
    web3 = Web3(Web3.HTTPProvider(env_config["POLYGON_RPC_URL"]))
    account = web3.eth.account.from_key(private_key)

    print(f"Account: {account.address}")
    print()

    # Check MATIC balance
    balance_wei = web3.eth.get_balance(account.address)
    balance_matic = Decimal(balance_wei) / Decimal(10**18)

    print(f"MATIC: {balance_matic:.6f}")

    if balance_matic < Decimal("0.5"):
        print("  ⚠️  WARNING: Low MATIC for gas!")

    print()

    # Check token balances
    erc20_abi = get_erc20_abi()

    print("Token Balances:")
    print("-" * 60)

    for token in token_list:
        symbol = token["symbol"]
        address = token["address"]
        decimals = token["decimals"]

        try:
            contract = web3.eth.contract(address=address, abi=erc20_abi)
            balance_raw = contract.functions.balanceOf(account.address).call()
            balance = Decimal(balance_raw) / Decimal(10**decimals)

            print(f"{symbol:8s}: {balance:>15.6f}")

            if balance == 0:
                print(f"          ⚠️  No {symbol} balance")

        except Exception as e:
            print(f"{symbol:8s}: Error - {e}")

    print()
    print("=" * 60)


if __name__ == "__main__":
    main()
