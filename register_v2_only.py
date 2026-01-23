#!/usr/bin/env python3
"""Register V2 adapter only"""
import os
import json
from web3 import Web3
from eth_account import Account
from dotenv import load_dotenv
import time

load_dotenv('.env.arbitrum')

RPC_URL = os.getenv('ARBITRUM_RPC_URL')
PRIVATE_KEY = os.getenv('PRIVATE_KEY')

web3 = Web3(Web3.HTTPProvider(RPC_URL))
account = Account.from_key(PRIVATE_KEY)
deployer = account.address

print("Registering V2 Adapter...")

# Wait a moment for nonce to settle
time.sleep(2)

# Load deployment info
with open('arbitrum_deployment.json', 'r') as f:
    deployment = json.load(f)

flashloan_address = deployment['contracts']['FlashLoanArbitrageV2']['address']
v2_adapter_address = deployment['contracts']['UniswapV2Adapter']['address']

# Load contract
with open('out/FlashLoanArbitrageV2.sol/FlashLoanArbitrageV2.json', 'r') as f:
    flashloan_data = json.load(f)
    abi = flashloan_data['abi']

contract = web3.eth.contract(address=Web3.to_checksum_address(flashloan_address), abi=abi)

# Get nonce
nonce = web3.eth.get_transaction_count(deployer)
print(f"Current nonce: {nonce}")

# Build transaction
latest_block = web3.eth.get_block('latest')
base_fee = latest_block['baseFeePerGas']
max_priority_fee = web3.to_wei(0.01, 'gwei')
max_fee = base_fee * 2 + max_priority_fee

txn = contract.functions.setAdapter(
    Web3.to_checksum_address(v2_adapter_address),
    True
).build_transaction({
    'from': deployer,
    'nonce': nonce,
    'gas': 150000,
    'maxFeePerGas': max_fee,
    'maxPriorityFeePerGas': max_priority_fee
})

# Sign and send
signed_txn = web3.eth.account.sign_transaction(txn, PRIVATE_KEY)
print(f"Sending transaction...")
tx_hash = web3.eth.send_raw_transaction(signed_txn.raw_transaction)
print(f"TX Hash: {tx_hash.hex()}")

# Wait for receipt
receipt = web3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

if receipt['status'] == 1:
    print(f"✅ V2 Adapter registered successfully!")
else:
    print(f"❌ Registration failed!")
