#!/usr/bin/env python3
"""Deploy only FlashLoanArbitrageV2 to Arbitrum"""
import os
import json
from web3 import Web3
from eth_account import Account
from dotenv import load_dotenv

load_dotenv('.env.arbitrum')

RPC_URL = os.getenv('ARBITRUM_RPC_URL')
PRIVATE_KEY = os.getenv('PRIVATE_KEY')
AAVE_POOL_PROVIDER = "0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb"
MIN_PROFIT = 5 * 10**6  # $5 in USDC
MAX_SLIPPAGE_BPS = 100  # 1% max slippage

print("=" * 80)
print("DEPLOYING FLASHLOAN ARBITRAGE V2 ONLY")
print("=" * 80)

web3 = Web3(Web3.HTTPProvider(RPC_URL))
account = Account.from_key(PRIVATE_KEY)
deployer = account.address

print(f"\n✅ Connected to Arbitrum (Chain ID: {web3.eth.chain_id})")
print(f"📊 Deployer: {deployer}")

balance = web3.eth.get_balance(deployer)
balance_eth = web3.from_wei(balance, 'ether')
print(f"💰 Balance: {balance_eth:.6f} ETH")

# Load contract
with open('out/FlashLoanArbitrageV2.sol/FlashLoanArbitrageV2.json', 'r') as f:
    contract_data = json.load(f)
    bytecode = contract_data['bytecode']['object']
    abi = contract_data['abi']

Contract = web3.eth.contract(abi=abi, bytecode=bytecode)

# Build constructor
constructor_txn = Contract.constructor(AAVE_POOL_PROVIDER, MIN_PROFIT, MAX_SLIPPAGE_BPS)

# Estimate gas
gas_estimate = constructor_txn.estimate_gas({'from': deployer})
print(f"\n📤 Deploying FlashLoanArbitrageV2...")
print(f"   Constructor args:")
print(f"   - Address Provider: {AAVE_POOL_PROVIDER}")
print(f"   - Min Profit: ${MIN_PROFIT / 10**6}")
print(f"   - Max Slippage: {MAX_SLIPPAGE_BPS/100}%")
print(f"   Gas estimate: {gas_estimate:,}")

# Get gas pricing (EIP-1559)
latest_block = web3.eth.get_block('latest')
base_fee = latest_block['baseFeePerGas']
max_priority_fee = web3.to_wei(0.01, 'gwei')
max_fee = base_fee * 2 + max_priority_fee

# Build transaction
nonce = web3.eth.get_transaction_count(deployer)
txn = constructor_txn.build_transaction({
    'from': deployer,
    'nonce': nonce,
    'gas': int(gas_estimate * 1.5),
    'maxFeePerGas': max_fee,
    'maxPriorityFeePerGas': max_priority_fee
})

# Sign and send
signed_txn = web3.eth.account.sign_transaction(txn, PRIVATE_KEY)
print(f"   Sending transaction...")
tx_hash = web3.eth.send_raw_transaction(signed_txn.raw_transaction)
print(f"   TX Hash: {tx_hash.hex()}")
print(f"   Waiting for confirmation...")

# Wait for receipt
receipt = web3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

if receipt['status'] == 1:
    contract_address = receipt['contractAddress']
    gas_used = receipt['gasUsed']
    effective_gas_price = receipt['effectiveGasPrice']
    actual_cost_eth = web3.from_wei(gas_used * effective_gas_price, 'ether')
    actual_cost_usd = float(actual_cost_eth) * 2500

    print(f"   ✅ Deployed at: {contract_address}")
    print(f"   Gas used: {gas_used:,}")
    print(f"   Actual cost: {actual_cost_eth:.6f} ETH (~${actual_cost_usd:.2f})")

    # Save deployment info
    deployment_info = {
        'network': 'arbitrum',
        'chain_id': 42161,
        'deployer': deployer,
        'contracts': {
            'FlashLoanArbitrageV2': {
                'address': contract_address,
                'tx_hash': tx_hash.hex()
            },
            'UniswapV3AdapterFixed': {
                'address': '0x5c66347c2c6DdCa4176bf7F81eaded03F4cE5e85',
                'tx_hash': 'aee359f9344d5e8560acc694c598a0dd3a9ae5d9bcdc01d592561f5aa46b0ad4'
            },
            'UniswapV2Adapter': {
                'address': '0x0CA37D06c5d9b0061d029F32d0C1FCdc250b1e8A',
                'tx_hash': '558fb75c979da05ffeaec8ac01e5758a83e7e68cf0e98ac9888ba46a9b721034'
            }
        }
    }

    with open('arbitrum_deployment.json', 'w') as f:
        json.dump(deployment_info, f, indent=2)

    print(f"\n💾 Deployment info saved to: arbitrum_deployment.json")
    print(f"\n✅ ALL CONTRACTS DEPLOYED!")
    print(f"\n📋 Contract Addresses:")
    print(f"   FlashLoanArbitrageV2: {contract_address}")
    print(f"   UniswapV3AdapterFixed: 0x5c66347c2c6DdCa4176bf7F81eaded03F4cE5e85")
    print(f"   UniswapV2Adapter: 0x0CA37D06c5d9b0061d029F32d0C1FCdc250b1e8A")

else:
    print(f"   ❌ Deployment failed!")
