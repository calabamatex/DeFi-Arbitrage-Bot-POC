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
from src.utils.key_manager import load_private_key
ARBITRUM_RPC = os.getenv('ARBITRUM_RPC_URL')
PRIVATE_KEY = load_private_key()

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
def register_adapter(adapter_address, adapter_name):
    """Register an adapter with the main contract"""
    print(f"\n📝 Registering {adapter_name} adapter...")
    print(f"   Address: {adapter_address}")

    # Build transaction (EIP-1559 for Arbitrum)
    nonce = web3.eth.get_transaction_count(deployer)
    latest_block = web3.eth.get_block('latest')
    base_fee = latest_block['baseFeePerGas']
    max_priority_fee = web3.to_wei(0.01, 'gwei')
    max_fee = base_fee * 2 + max_priority_fee

    txn = flashloan_contract.functions.setAdapter(
        Web3.to_checksum_address(adapter_address),
        True  # Enable this adapter
    ).build_transaction({
        'from': deployer,
        'nonce': nonce,
        'gas': 150000,
        'maxFeePerGas': max_fee,
        'maxPriorityFeePerGas': max_priority_fee
    })

    # Sign and send
    signed_txn = web3.eth.account.sign_transaction(txn, PRIVATE_KEY)
    print(f"   Sending transaction...")
    tx_hash = web3.eth.send_raw_transaction(signed_txn.raw_transaction)
    print(f"   TX Hash: {tx_hash.hex()}")

    # Wait for receipt
    receipt = web3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

    if receipt['status'] == 1:
        gas_used = receipt['gasUsed']
        effective_gas_price = receipt['effectiveGasPrice']
        cost_eth = web3.from_wei(gas_used * effective_gas_price, 'ether')
        cost_usd = float(cost_eth) * 2500
        print(f"   ✅ Registered successfully!")
        print(f"   Gas used: {gas_used:,}")
        print(f"   Cost: {cost_eth:.6f} ETH (~${cost_usd:.2f})")
        return True
    else:
        print(f"   ❌ Registration failed!")
        return False

# Register V3 adapter
success_v3 = register_adapter(v3_adapter_address, "Uniswap V3")

# Register V2 adapter
success_v2 = register_adapter(v2_adapter_address, "Uniswap V2 (SushiSwap)")

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
