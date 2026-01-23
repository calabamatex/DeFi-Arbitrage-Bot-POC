#!/usr/bin/env python3
"""Check wallet balance on multiple networks"""
from web3 import Web3

WALLET_ADDRESS = "0xE05D16622CC5E54919248C97AF12Bf6C921269AC"

networks = {
    "Ethereum Mainnet": "https://eth-mainnet.g.alchemy.com/v2/demo",
    "Arbitrum": "https://arb1.arbitrum.io/rpc",
    "Polygon": "https://polygon-rpc.com",
    "Optimism": "https://mainnet.optimism.io",
    "Base": "https://mainnet.base.org"
}

print("=" * 80)
print("CHECKING WALLET BALANCE ACROSS NETWORKS")
print("=" * 80)
print(f"\nWallet: {WALLET_ADDRESS}\n")

for network_name, rpc_url in networks.items():
    try:
        web3 = Web3(Web3.HTTPProvider(rpc_url))
        if not web3.is_connected():
            print(f"❌ {network_name}: Connection failed")
            continue

        balance_wei = web3.eth.get_balance(WALLET_ADDRESS)
        balance_eth = web3.from_wei(balance_wei, 'ether')
        balance_usd = float(balance_eth) * 2500

        if balance_eth > 0:
            print(f"✅ {network_name}:")
            print(f"   Balance: {balance_eth:.6f} ETH (${balance_usd:.2f})")
        else:
            print(f"⚪ {network_name}: 0 ETH")

    except Exception as e:
        print(f"❌ {network_name}: Error - {str(e)[:50]}")

print("\n" + "=" * 80)
