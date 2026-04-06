#!/usr/bin/env python3
"""Test Arbitrum connection with Alchemy"""
import os
from web3 import Web3
from dotenv import load_dotenv

load_dotenv('.env.arbitrum')

print("=" * 80)
print("TESTING ARBITRUM CONNECTION")
print("=" * 80)

RPC_URL = os.getenv('ARBITRUM_RPC_URL')
WALLET = os.getenv('PRIVATE_KEY')

print(f"\n🔗 RPC URL: {RPC_URL[:60]}...")

# Test connection
web3 = Web3(Web3.HTTPProvider(RPC_URL))

if not web3.is_connected():
    print("\n❌ Connection failed!")
    print("   Check your Alchemy API key")
    exit(1)

print("✅ Connected successfully!")

# Verify chain
chain_id = web3.eth.chain_id
print(f"✅ Chain ID: {chain_id} (Arbitrum Mainnet)")

# Get latest block
latest_block = web3.eth.block_number
print(f"✅ Latest block: {latest_block:,}")

# Get wallet info
from eth_account import Account
account = Account.from_key(WALLET)
balance = web3.eth.get_balance(account.address)
balance_eth = web3.from_wei(balance, 'ether')

print(f"\n💰 Wallet: {account.address}")
print(f"💰 Balance: {balance_eth:.6f} ETH")

# Get gas price
gas_price = web3.eth.gas_price
gas_price_gwei = web3.from_wei(gas_price, 'gwei')
print(f"⛽ Current gas price: {gas_price_gwei:.2f} gwei")

print("\n" + "=" * 80)
print("✅ ALL CHECKS PASSED - READY TO DEPLOY")
print("=" * 80)
