#!/usr/bin/env python3
"""Quick check if wallet is ready for testnet deployment"""

import os
import sys
from web3 import Web3
from eth_account import Account

# Load key securely (keystore or env var)
from src.utils.key_manager import load_private_key

TESTNET_RPC = os.environ.get("TESTNET_RPC_URL", "https://rpc-amoy.polygon.technology")
PRIVATE_KEY = load_private_key()

# Connect
web3 = Web3(Web3.HTTPProvider(TESTNET_RPC))
account = Account.from_key(PRIVATE_KEY)

print("Checking Testnet Status...\n")

# Check connection
if not web3.is_connected():
    print("Cannot connect to testnet")
    sys.exit(1)

print(f"Connected to chain ID: {web3.eth.chain_id}")

# Check balance
balance_wei = web3.eth.get_balance(account.address)
balance_matic = web3.from_wei(balance_wei, 'ether')

print(f"\nWallet: {account.address}")
print(f"Balance: {balance_matic} MATIC")

if balance_matic >= 0.1:
    print(f"\nREADY TO DEPLOY")
    print(f"\nRun deployment script:")
    print(f"  python deploy_to_testnet.py")
else:
    print(f"\nNeed testnet MATIC to deploy")
    print(f"\nGet testnet MATIC:")
    print(f"   1. Visit: https://faucet.polygon.technology/")
    print(f"   2. Select 'Polygon Amoy' network")
    print(f"   3. Paste address: {account.address}")
    print(f"   4. Complete CAPTCHA and submit")
    print(f"   5. Wait 1-2 minutes")
    print(f"   6. Run this script again to verify")

print(f"\nView on Explorer:")
print(f"   https://amoy.polygonscan.com/address/{account.address}")
