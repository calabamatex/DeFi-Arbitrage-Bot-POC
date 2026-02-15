#!/usr/bin/env python3
"""
Create a new Ethereum wallet with encrypted keystore.
WARNING: This is for TESTNET ONLY. Never use this for mainnet!
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.key_manager import create_keystore

print("=" * 60)
print("NEW TESTNET WALLET — ENCRYPTED KEYSTORE")
print("=" * 60)
print()
print("WARNING: This is for TESTNET ONLY!")
print("DO NOT send real funds to this address!")
print()

keystore_path = create_keystore(output_path="testnet_keystore.json")

print()
print("=" * 60)
print("NEXT STEPS:")
print("=" * 60)
print()
print("1. Your keystore is encrypted with your password")
print(f"2. Set the env var:  export KEYSTORE_FILE={keystore_path}")
print("3. Get testnet MATIC from a faucet")
print("4. Run the bot:  python run_bot.py --chain polygon")
print()
print("=" * 60)
