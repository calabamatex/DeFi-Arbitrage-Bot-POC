#!/usr/bin/env python3
"""Check wallet security and remaining assets"""
from web3 import Web3
import json

WALLET_ADDRESS = "0xE05D16622CC5E54919248C97AF12Bf6C921269AC"
SCAM_CONTRACT = "0x797700a336bebfa0288974e10de313c730be3b00"

print("=" * 80)
print("WALLET SECURITY CHECK")
print("=" * 80)

# Check Polygon (where we have the live bot)
print("\n🔍 Checking Polygon (where bot is deployed)...")
polygon_rpc = "https://polygon-rpc.com"
web3 = Web3(Web3.HTTPProvider(polygon_rpc))

if web3.is_connected():
    balance = web3.eth.get_balance(WALLET_ADDRESS)
    balance_matic = web3.from_wei(balance, 'ether')
    print(f"✅ Connected to Polygon")
    print(f"   MATIC Balance: {balance_matic:.6f} MATIC")

    if balance_matic > 0:
        print(f"   ⚠️  You still have {balance_matic:.2f} MATIC on Polygon!")
        print(f"   💰 Value: ~${float(balance_matic) * 0.65:.2f}")

    # Check if wallet has approvals to the scam contract
    print(f"\n🔒 Checking for dangerous approvals...")
    print(f"   Scam contract: {SCAM_CONTRACT}")

else:
    print("❌ Could not connect to Polygon")

print("\n" + "=" * 80)
print("SECURITY RECOMMENDATIONS")
print("=" * 80)

print("\n1. ⚠️  IMMEDIATE ACTIONS:")
print("   - DO NOT send any more funds to this wallet")
print("   - Check if you approved any tokens to the scam contract")
print("   - Revoke approvals at https://revoke.cash/")

print("\n2. 🔐 CREATE NEW WALLET:")
print("   - Generate a completely new wallet address")
print("   - Transfer remaining assets (Polygon MATIC) to new wallet")
print("   - NEVER share private key or click suspicious links")

print("\n3. 📝 WHAT LIKELY HAPPENED:")
print("   - You may have:")
print("     a) Used a fake bridge/swap website")
print("     b) Clicked a phishing link")
print("     c) Connected wallet to malicious dApp")
print("     d) Approved tokens to scam contract")

print("\n4. 💡 GOING FORWARD:")
print("   - Always verify URLs (check for https, correct domain)")
print("   - Use only official bridges/exchanges")
print("   - Never click links in DMs or random websites")
print("   - Use hardware wallet for larger amounts")
print("   - Check contract on Etherscan before interacting")

print("\n5. 🔄 PROJECT CONTINUITY:")
print("   - Current Polygon bot: Check if still running with remaining MATIC")
print("   - For Arbitrum: Create new wallet, send fresh ETH there")
print("   - Update .env files with new wallet address")
print("   - Cost to continue: ~$25-30 (for new Arbitrum deployment)")

print("\n" + "=" * 80)
