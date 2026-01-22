#!/usr/bin/env python3
"""Check wallet balance on Arbitrum"""
import os
from web3 import Web3

# Arbitrum mainnet RPC (using public endpoint for now)
ARBITRUM_RPC = "https://arb1.arbitrum.io/rpc"
WALLET_ADDRESS = "0xE05D16622CC5E54919248C97AF12Bf6C921269AC"

def check_balance():
    """Check ETH balance on Arbitrum"""
    try:
        web3 = Web3(Web3.HTTPProvider(ARBITRUM_RPC))

        # Check connection
        if not web3.is_connected():
            print("❌ Failed to connect to Arbitrum RPC")
            return

        # Get chain ID to confirm we're on Arbitrum
        chain_id = web3.eth.chain_id
        print(f"✅ Connected to Arbitrum (Chain ID: {chain_id})")

        # Get ETH balance
        balance_wei = web3.eth.get_balance(WALLET_ADDRESS)
        balance_eth = web3.from_wei(balance_wei, 'ether')

        # Get ETH price estimate ($2,500 approximate)
        balance_usd = float(balance_eth) * 2500

        print(f"\n📊 Wallet: {WALLET_ADDRESS}")
        print(f"💰 ETH Balance: {balance_eth:.6f} ETH")
        print(f"💵 USD Value: ${balance_usd:.2f} (approximate)")

        # Check if sufficient for deployment
        MIN_ETH_NEEDED = 0.01
        if balance_eth >= MIN_ETH_NEEDED:
            print(f"\n✅ Sufficient balance for deployment (need {MIN_ETH_NEEDED} ETH)")
        else:
            needed = MIN_ETH_NEEDED - float(balance_eth)
            print(f"\n⚠️  Insufficient balance!")
            print(f"   Need: {MIN_ETH_NEEDED} ETH")
            print(f"   Have: {balance_eth} ETH")
            print(f"   Missing: {needed:.6f} ETH (${needed*2500:.2f})")
            print(f"\n📝 How to get ETH on Arbitrum:")
            print(f"   1. Bridge from Ethereum: https://bridge.arbitrum.io/")
            print(f"   2. Buy on exchange (Coinbase, Binance) and withdraw to Arbitrum")
            print(f"   3. Use multichain bridge: https://app.multichain.org/")

        return balance_eth

    except Exception as e:
        print(f"❌ Error checking balance: {e}")
        return None

if __name__ == "__main__":
    print("🔍 Checking Arbitrum Balance...\n")
    check_balance()
