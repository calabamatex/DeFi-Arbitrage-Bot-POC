#!/usr/bin/env python3
"""
Deploy Flash Loan Arbitrage Bot to Polygon Amoy Testnet

This script will:
1. Check wallet balance
2. Deploy all contracts
3. Register adapters
4. Update .env.testnet with addresses
5. Verify deployment
"""

import os
import json
from web3 import Web3
from eth_account import Account
from dotenv import load_dotenv

# Load environment
load_dotenv('.env.testnet')

# Configuration
from src.utils.key_manager import load_private_key
TESTNET_RPC = "https://rpc-amoy.polygon.technology"
PRIVATE_KEY = load_private_key()
AAVE_POOL_PROVIDER = "0x4CeDCB57Af02293231BAA9D39354D6BFDFD251e0"
UNISWAP_V3_FACTORY = "0x0227628f3F023bb0B980b67D528571c95c6DaC1c"

# Initialize Web3
web3 = Web3(Web3.HTTPProvider(TESTNET_RPC))
account = Account.from_key(PRIVATE_KEY)

print("="*60)
print("🚀 Polygon Amoy Testnet Deployment")
print("="*60)

# Step 1: Check connection and balance
print(f"\n1️⃣  Checking connection...")
if not web3.is_connected():
    print("❌ Failed to connect to Amoy testnet")
    exit(1)

print(f"✅ Connected to Amoy (Chain ID: {web3.eth.chain_id})")
print(f"   Latest block: {web3.eth.block_number}")

balance_wei = web3.eth.get_balance(account.address)
balance_matic = web3.from_wei(balance_wei, 'ether')

print(f"\n2️⃣  Checking wallet balance...")
print(f"   Address: {account.address}")
print(f"   Balance: {balance_matic} MATIC")

if balance_matic < 0.1:
    print(f"\n⚠️  INSUFFICIENT BALANCE!")
    print(f"   Need at least 0.1 MATIC for deployment")
    print(f"   Current: {balance_matic} MATIC")
    print(f"\n   Get testnet MATIC:")
    print(f"   1. Visit: https://faucet.polygon.technology/")
    print(f"   2. Select 'Polygon Amoy'")
    print(f"   3. Paste address: {account.address}")
    print(f"   4. Wait 1-2 minutes")
    print(f"   5. Run this script again")
    exit(1)

print(f"✅ Sufficient balance for deployment")

# Step 3: Load contract bytecode and ABI
print(f"\n3️⃣  Loading contract artifacts...")

def load_contract_artifact(path):
    """Load compiled contract from Foundry output"""
    try:
        with open(path, 'r') as f:
            artifact = json.load(f)
            return {
                'abi': artifact.get('abi', []),
                'bytecode': artifact.get('bytecode', {}).get('object', '')
            }
    except FileNotFoundError:
        return None

# Try to load artifacts
flash_loan_artifact = load_contract_artifact('contracts/out/FlashLoanArbitrageV2.sol/FlashLoanArbitrageV2.json')
v3_adapter_artifact = load_contract_artifact('contracts/out/UniswapV3Adapter.sol/UniswapV3Adapter.json')
v2_adapter_artifact = load_contract_artifact('contracts/out/UniswapV2Adapter.sol/UniswapV2Adapter.json')

if not flash_loan_artifact:
    print("❌ Contract artifacts not found!")
    print("   Please compile contracts first:")
    print("   cd contracts && forge build")
    exit(1)

print("✅ Contract artifacts loaded")

# Step 4: Deploy contracts
print(f"\n4️⃣  Deploying FlashLoanArbitrageV2...")
print(f"   Constructor: aavePoolProvider={AAVE_POOL_PROVIDER}")

FlashLoan = web3.eth.contract(
    abi=flash_loan_artifact['abi'],
    bytecode=flash_loan_artifact['bytecode']
)

# Build deployment transaction
nonce = web3.eth.get_transaction_count(account.address)
gas_price = web3.eth.gas_price

flash_loan_constructor = FlashLoan.constructor(AAVE_POOL_PROVIDER)

try:
    gas_estimate = flash_loan_constructor.estimate_gas({'from': account.address})
except Exception as e:
    print(f"   Gas estimation failed, using default: {e}")
    gas_estimate = 3000000

flash_loan_tx = flash_loan_constructor.build_transaction({
    'from': account.address,
    'nonce': nonce,
    'gas': int(gas_estimate * 1.2),
    'gasPrice': gas_price,
    'chainId': 80002
})

# Sign and send
signed_flash_loan = account.sign_transaction(flash_loan_tx)
flash_loan_hash = web3.eth.send_raw_transaction(signed_flash_loan.raw_transaction)

print(f"   Transaction sent: {flash_loan_hash.hex()}")
print(f"   Waiting for confirmation...")

flash_loan_receipt = web3.eth.wait_for_transaction_receipt(flash_loan_hash, timeout=120)

if flash_loan_receipt['status'] != 1:
    print("❌ FlashLoanArbitrageV2 deployment failed!")
    exit(1)

flash_loan_address = flash_loan_receipt['contractAddress']
print(f"✅ FlashLoanArbitrageV2 deployed: {flash_loan_address}")

# Step 5: Deploy UniswapV3Adapter
print(f"\n5️⃣  Deploying UniswapV3Adapter...")

V3Adapter = web3.eth.contract(
    abi=v3_adapter_artifact['abi'],
    bytecode=v3_adapter_artifact['bytecode']
)

nonce = web3.eth.get_transaction_count(account.address)

v3_adapter_constructor = V3Adapter.constructor(UNISWAP_V3_FACTORY, "UniswapV3")
gas_estimate = 2000000

v3_adapter_tx = v3_adapter_constructor.build_transaction({
    'from': account.address,
    'nonce': nonce,
    'gas': gas_estimate,
    'gasPrice': gas_price,
    'chainId': 80002
})

signed_v3 = account.sign_transaction(v3_adapter_tx)
v3_hash = web3.eth.send_raw_transaction(signed_v3.raw_transaction)

print(f"   Transaction sent: {v3_hash.hex()}")
print(f"   Waiting for confirmation...")

v3_receipt = web3.eth.wait_for_transaction_receipt(v3_hash, timeout=120)

if v3_receipt['status'] != 1:
    print("❌ UniswapV3Adapter deployment failed!")
    exit(1)

v3_adapter_address = v3_receipt['contractAddress']
print(f"✅ UniswapV3Adapter deployed: {v3_adapter_address}")

# Step 6: Register V3 Adapter
print(f"\n6️⃣  Registering UniswapV3Adapter with main contract...")

flash_loan_contract = web3.eth.contract(
    address=flash_loan_address,
    abi=flash_loan_artifact['abi']
)

nonce = web3.eth.get_transaction_count(account.address)

register_tx = flash_loan_contract.functions.registerAdapter(
    v3_adapter_address,
    True
).build_transaction({
    'from': account.address,
    'nonce': nonce,
    'gas': 200000,
    'gasPrice': gas_price,
    'chainId': 80002
})

signed_register = account.sign_transaction(register_tx)
register_hash = web3.eth.send_raw_transaction(signed_register.raw_transaction)

print(f"   Transaction sent: {register_hash.hex()}")
register_receipt = web3.eth.wait_for_transaction_receipt(register_hash, timeout=120)

if register_receipt['status'] != 1:
    print("❌ Adapter registration failed!")
else:
    print(f"✅ UniswapV3Adapter registered")

# Step 7: Update .env.testnet
print(f"\n7️⃣  Updating .env.testnet...")

# Read current .env.testnet
with open('.env.testnet', 'r') as f:
    env_content = f.read()

# Update addresses
env_content = env_content.replace(
    'FLASH_LOAN_ARBITRAGE_ADDRESS=',
    f'FLASH_LOAN_ARBITRAGE_ADDRESS={flash_loan_address}'
)
env_content = env_content.replace(
    'UNISWAP_V3_ADAPTER_ADDRESS=',
    f'UNISWAP_V3_ADAPTER_ADDRESS={v3_adapter_address}'
)

# Write back
with open('.env.testnet', 'w') as f:
    f.write(env_content)

print(f"✅ Configuration updated")

# Step 8: Summary
print(f"\n{'='*60}")
print(f"🎉 Deployment Complete!")
print(f"{'='*60}")
print(f"\nDeployed Contracts:")
print(f"  FlashLoanArbitrageV2:  {flash_loan_address}")
print(f"  UniswapV3Adapter:      {v3_adapter_address}")
print(f"\nView on Explorer:")
print(f"  https://amoy.polygonscan.com/address/{flash_loan_address}")
print(f"\nRemaining Balance: {web3.from_wei(web3.eth.get_balance(account.address), 'ether')} MATIC")

print(f"\n{'='*60}")
print(f"Next Steps:")
print(f"{'='*60}")
print(f"1. Copy testnet config: cp .env.testnet .env")
print(f"2. Run the bot: python run_bot.py")
print(f"3. Watch for opportunities!")
print(f"\nNote: Testnet has low liquidity - opportunities will be rare.")
print(f"Consider creating artificial arbitrage for testing.")

# Save deployment info
deployment_info = {
    'network': 'Polygon Amoy',
    'chainId': 80002,
    'deployer': account.address,
    'contracts': {
        'FlashLoanArbitrageV2': flash_loan_address,
        'UniswapV3Adapter': v3_adapter_address,
    },
    'block': web3.eth.block_number,
}

with open('testnet_deployment.json', 'w') as f:
    json.dump(deployment_info, f, indent=2)

print(f"\n✅ Deployment details saved to testnet_deployment.json")
