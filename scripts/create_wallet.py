#!/usr/bin/env python3
"""
Create a new Ethereum wallet for testnet use
WARNING: This is for TESTNET ONLY. Never use this for mainnet!
"""
from eth_account import Account
import secrets

# Generate new account
private_key = "0x" + secrets.token_hex(32)
account = Account.from_key(private_key)

print("=" * 60)
print("NEW TESTNET WALLET CREATED")
print("=" * 60)
print()
print("⚠️  WARNING: This is for TESTNET ONLY!")
print("⚠️  DO NOT send real funds to this address!")
print()
print(f"Address:     {account.address}")
print(f"Private Key: {private_key}")
print()
print("=" * 60)
print("NEXT STEPS:")
print("=" * 60)
print()
print("1. Copy your private key (keep it secret!)")
print("2. Add it to .env file:")
print(f"   PRIVATE_KEY={private_key}")
print()
print("3. Get testnet MATIC from faucet:")
print(f"   https://mumbaifaucet.com/")
print(f"   Enter your address: {account.address}")
print()
print("4. Verify balance:")
print(f"   https://mumbai.polygonscan.com/address/{account.address}")
print()
print("=" * 60)
