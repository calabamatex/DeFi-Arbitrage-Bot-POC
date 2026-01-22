#!/usr/bin/env python3
"""Register DEX adapters with FlashLoanArbitrageV2 on Arbitrum"""
import os
import json
from web3 import Web3
from eth_account import Account
from dotenv import load_dotenv

# Load Arbitrum configuration
load_dotenv('.env.arbitrum')

print("=" * 80)
print("REGISTER ADAPTERS - ARBITRUM")
print("=" * 80)

# Load deployment info
if not os.path.exists('arbitrum_deployment.json'):
    print("\n❌ Deployment file not found: arbitrum_deployment.json")
    print("   Run deploy_arbitrum.py first")
    exit(1)

with open('arbitrum_deployment.json', 'r') as f:
    deployment = json.load(f)

# Connect to Arbitrum
ARBITRUM_RPC = os.getenv('ARBITRUM_RPC_URL')
PRIVATE_KEY = os.getenv('PRIVATE_KEY')

web3 = Web3(Web3.HTTPProvider(ARBITRUM_RPC))

if not web3.is_connected():
    print(f"\n❌ Failed to connect to Arbitrum")
    exit(1)

print(f"\n✅ Connected to Arbitrum (Chain ID: {web3.eth.chain_id})")

# Load account
account = Account.from_key(PRIVATE_KEY)
deployer = account.address

# Check balance
balance = web3.eth.get_balance(deployer)
balance_eth = web3.from_wei(balance, 'ether')
print(f"📊 Deployer: {deployer}")
print(f"💰 Balance: {balance_eth:.6f} ETH")

# Get contract addresses
flashloan_address = deployment['contracts']['FlashLoanArbitrageV2']['address']
v3_adapter_address = deployment['contracts']['UniswapV3AdapterFixed']['address']
v2_adapter_address = deployment['contracts']['UniswapV2Adapter']['address']

print(f"\n📋 Contract Addresses:")
print(f"   Main: {flashloan_address}")
print(f"   V3 Adapter: {v3_adapter_address}")
print(f"   V2 Adapter: {v2_adapter_address}")

# Load FlashLoanArbitrageV2 ABI
with open('out/FlashLoanArbitrageV2.sol/FlashLoanArbitrageV2.json', 'r') as f:
    flashloan_data = json.load(f)
    flashloan_abi = flashloan_data['abi']

# Create contract instance
flashloan_contract = web3.eth.contract(
    address=Web3.to_checksum_address(flashloan_address),
    abi=flashloan_abi
)

# Register adapters
def register_adapter(adapter_address, adapter_type):
    """Register an adapter with the main contract"""
    type_name = "Uniswap V3" if adapter_type == 0 else "Uniswap V2"
    print(f"\n📝 Registering {type_name} adapter...")
    print(f"   Address: {adapter_address}")

    # Build transaction
    nonce = web3.eth.get_transaction_count(deployer)
    gas_price = web3.eth.gas_price

    txn = flashloan_contract.functions.registerAdapter(
        Web3.to_checksum_address(adapter_address),
        adapter_type
    ).build_transaction({
        'from': deployer,
        'nonce': nonce,
        'gas': 150000,
        'gasPrice': gas_price
    })

    # Sign and send
    signed_txn = web3.eth.account.sign_transaction(txn, PRIVATE_KEY)
    print(f"   Sending transaction...")
    tx_hash = web3.eth.send_raw_transaction(signed_txn.rawTransaction)
    print(f"   TX Hash: {tx_hash.hex()}")

    # Wait for receipt
    receipt = web3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

    if receipt['status'] == 1:
        gas_used = receipt['gasUsed']
        cost_eth = web3.from_wei(gas_used * gas_price, 'ether')
        cost_usd = float(cost_eth) * 2500
        print(f"   ✅ Registered successfully!")
        print(f"   Gas used: {gas_used:,}")
        print(f"   Cost: {cost_eth:.6f} ETH (~${cost_usd:.2f})")
        return True
    else:
        print(f"   ❌ Registration failed!")
        return False

# Register V3 adapter
success_v3 = register_adapter(v3_adapter_address, 0)  # Type 0 = V3

# Register V2 adapter
success_v2 = register_adapter(v2_adapter_address, 1)  # Type 1 = V2

# Summary
print("\n" + "=" * 80)
print("REGISTRATION COMPLETE")
print("=" * 80)

if success_v3 and success_v2:
    print("\n✅ All adapters registered successfully!")

    # Check final balance
    final_balance = web3.eth.get_balance(deployer)
    final_balance_eth = web3.from_wei(final_balance, 'ether')
    spent_eth = balance_eth - final_balance_eth
    spent_usd = float(spent_eth) * 2500

    print(f"\n💰 Registration Cost:")
    print(f"   ETH spent: {spent_eth:.6f} ETH")
    print(f"   USD cost: ~${spent_usd:.2f}")
    print(f"   Remaining: {final_balance_eth:.6f} ETH")

    print("\n" + "=" * 80)
    print("NEXT STEPS")
    print("=" * 80)
    print("\n1. Verify contracts on Arbiscan:")
    print(f"   https://arbiscan.io/address/{flashloan_address}#code")
    print("\n2. Update .env.arbitrum with contract addresses")
    print("\n3. Run test scan:")
    print(f"   python run_bot_arbitrum.py --test")
else:
    print("\n❌ Some registrations failed. Check errors above.")
