#!/usr/bin/env python3
"""Generate a new secure wallet with encrypted keystore.

Creates an encrypted keystore file instead of printing raw private keys.
Usage:
    python generate_new_wallet.py                    # interactive
    python generate_new_wallet.py -o my_keystore.json  # custom path
"""
import argparse
import sys

from src.utils.key_manager import create_keystore

print("=" * 80)
print("GENERATING NEW SECURE WALLET")
print("=" * 80)

parser = argparse.ArgumentParser(description="Generate new wallet with encrypted keystore")
parser.add_argument("-o", "--output", default="keystore.json", help="Output keystore file path")
args = parser.parse_args()

keystore_path = create_keystore(output_path=args.output)

print("\n" + "=" * 80)
print("SECURITY INSTRUCTIONS")
print("=" * 80)
print("\n1. The keystore file is encrypted with your password")
print("2. NEVER commit the keystore file to git (it is in .gitignore)")
print("3. Back up the keystore file securely (separate from password)")
print("4. Fund the wallet address shown above with gas before deploying")
print("\n5. To use with the bot:")
print(f"     export KEYSTORE_FILE={keystore_path}")
print("     python run_bot.py --chain polygon")
print("\n6. To use with Foundry, also import the key:")
print("     cast wallet import deployer --interactive")
print("=" * 80)
