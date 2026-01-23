#!/usr/bin/env python3
"""Quick check if wallet is ready for testnet deployment"""

from web3 import Web3
from eth_account import Account

# Configuration
TESTNET_RPC = "https://rpc-amoy.polygon.technology"
PRIVATE_KEY = "0xcf4cbdb74541d0dfe888271c7f9424c0fc7e62bcd0f50a72ae9363d112a55ff9"

# Connect
web3 = Web3(Web3.HTTPProvider(TESTNET_RPC))
account = Account.from_key(PRIVATE_KEY)

print("🔍 Checking Testnet Status...\n")

# Check connection
if not web3.is_connected():
    print("❌ Cannot connect to Polygon Amoy testnet")
    exit(1)

print(f"✅ Connected to Polygon Amoy (Chain ID: {web3.eth.chain_id})")

# Check balance
balance_wei = web3.eth.get_balance(account.address)
balance_matic = web3.from_wei(balance_wei, 'ether')

print(f"\n📍 Wallet: {account.address}")
print(f"💰 Balance: {balance_matic} MATIC")

if balance_matic >= 0.1:
    print(f"\n✅ READY TO DEPLOY!")
    print(f"\nRun deployment script:")
    print(f"  python deploy_to_testnet.py")
else:
    print(f"\n⚠️  Need testnet MATIC to deploy")
    print(f"\n🚰 Get testnet MATIC:")
    print(f"   1. Visit: https://faucet.polygon.technology/")
    print(f"   2. Select 'Polygon Amoy' network")
    print(f"   3. Paste address: {account.address}")
    print(f"   4. Complete CAPTCHA and submit")
    print(f"   5. Wait 1-2 minutes")
    print(f"   6. Run this script again to verify")
    print(f"\n   Alternative faucets:")
    print(f"   - https://www.alchemy.com/faucets/polygon-amoy")
    print(f"   - https://faucet.quicknode.com/polygon/amoy")

print(f"\n📊 View on Explorer:")
print(f"   https://amoy.polygonscan.com/address/{account.address}")
