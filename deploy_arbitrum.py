#!/usr/bin/env python3
"""Deploy Flash Loan Arbitrage Bot to Arbitrum Mainnet"""
import os
import json
import time
from web3 import Web3
from eth_account import Account
from dotenv import load_dotenv

# Load Arbitrum configuration
load_dotenv('.env.arbitrum')

# Connect to Arbitrum
ARBITRUM_RPC = os.getenv('ARBITRUM_RPC_URL')
PRIVATE_KEY = os.getenv('PRIVATE_KEY')
AAVE_POOL = os.getenv('AAVE_POOL')

print("=" * 80)
print("ARBITRUM MAINNET DEPLOYMENT")
print("=" * 80)

# Verify Alchemy key is set
if 'YOUR_ALCHEMY_KEY_HERE' in ARBITRUM_RPC:
    print("\n❌ ERROR: You need to set your Alchemy API key in .env.arbitrum")
    print("   Get one at: https://dashboard.alchemy.com/")
    print("   Then update ARBITRUM_RPC_URL in .env.arbitrum")
    exit(1)

# Initialize Web3
web3 = Web3(Web3.HTTPProvider(ARBITRUM_RPC))

if not web3.is_connected():
    print("\n❌ Failed to connect to Arbitrum")
    print(f"   RPC URL: {ARBITRUM_RPC[:50]}...")
    exit(1)

# Verify chain
chain_id = web3.eth.chain_id
if chain_id != 42161:
    print(f"\n❌ Wrong network! Expected Arbitrum (42161), got chain ID {chain_id}")
    exit(1)

print(f"\n✅ Connected to Arbitrum Mainnet (Chain ID: {chain_id})")

# Load account
account = Account.from_key(PRIVATE_KEY)
deployer = account.address

# Check balance
balance = web3.eth.get_balance(deployer)
balance_eth = web3.from_wei(balance, 'ether')
print(f"📊 Deployer: {deployer}")
print(f"💰 Balance: {balance_eth:.6f} ETH")

MIN_ETH_NEEDED = 0.01
if balance_eth < MIN_ETH_NEEDED:
    print(f"\n❌ Insufficient balance!")
    print(f"   Need: {MIN_ETH_NEEDED} ETH (~${MIN_ETH_NEEDED * 2500:.2f})")
    print(f"   Have: {balance_eth} ETH")
    print(f"\n📝 Get ETH on Arbitrum:")
    print(f"   1. Bridge: https://bridge.arbitrum.io/")
    print(f"   2. Buy on exchange and withdraw to Arbitrum network")
    exit(1)

print(f"✅ Sufficient balance for deployment")

# Load contract bytecode and ABI
print("\n" + "=" * 80)
print("LOADING CONTRACTS")
print("=" * 80)

def load_contract(contract_name):
    """Load compiled contract"""
    json_path = f"out/{contract_name}.sol/{contract_name}.json"
    if not os.path.exists(json_path):
        print(f"\n❌ Contract not found: {json_path}")
        print("   Run: forge build")
        exit(1)

    with open(json_path, 'r') as f:
        contract_data = json.load(f)

    return contract_data['bytecode']['object'], contract_data['abi']

# Load all contracts
uniswap_v3_bytecode, uniswap_v3_abi = load_contract('UniswapV3AdapterFixed')
uniswap_v2_bytecode, uniswap_v2_abi = load_contract('UniswapV2Adapter')
flashloan_bytecode, flashloan_abi = load_contract('FlashLoanArbitrageV2')

print("✅ All contracts loaded")

# Deploy function
def deploy_contract(name, bytecode, abi, constructor_args=None):
    """Deploy a contract and return address"""
    print(f"\n📤 Deploying {name}...")

    Contract = web3.eth.contract(abi=abi, bytecode=bytecode)

    # Build constructor transaction
    if constructor_args:
        constructor_txn = Contract.constructor(*constructor_args)
    else:
        constructor_txn = Contract.constructor()

    # Estimate gas
    gas_estimate = constructor_txn.estimate_gas({'from': deployer})
    print(f"   Gas estimate: {gas_estimate:,}")

    # Get current gas price
    gas_price = web3.eth.gas_price
    gas_price_gwei = web3.from_wei(gas_price, 'gwei')
    print(f"   Gas price: {gas_price_gwei:.2f} gwei")

    # Calculate cost
    cost_wei = gas_estimate * gas_price
    cost_eth = web3.from_wei(cost_wei, 'ether')
    cost_usd = float(cost_eth) * 2500  # Rough ETH price
    print(f"   Estimated cost: {cost_eth:.6f} ETH (~${cost_usd:.2f})")

    # Build transaction
    nonce = web3.eth.get_transaction_count(deployer)
    txn = constructor_txn.build_transaction({
        'from': deployer,
        'nonce': nonce,
        'gas': int(gas_estimate * 1.2),  # 20% buffer
        'gasPrice': gas_price
    })

    # Sign and send
    signed_txn = web3.eth.account.sign_transaction(txn, PRIVATE_KEY)
    print(f"   Sending transaction...")
    tx_hash = web3.eth.send_raw_transaction(signed_txn.rawTransaction)
    print(f"   TX Hash: {tx_hash.hex()}")
    print(f"   Waiting for confirmation...")

    # Wait for receipt
    receipt = web3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

    if receipt['status'] == 1:
        contract_address = receipt['contractAddress']
        gas_used = receipt['gasUsed']
        actual_cost_eth = web3.from_wei(gas_used * gas_price, 'ether')
        actual_cost_usd = float(actual_cost_eth) * 2500

        print(f"   ✅ Deployed at: {contract_address}")
        print(f"   Gas used: {gas_used:,}")
        print(f"   Actual cost: {actual_cost_eth:.6f} ETH (~${actual_cost_usd:.2f})")

        return contract_address, tx_hash.hex()
    else:
        print(f"   ❌ Deployment failed!")
        return None, None

# Deploy all contracts
print("\n" + "=" * 80)
print("DEPLOYING CONTRACTS")
print("=" * 80)

# 1. Deploy Uniswap V3 Adapter
v3_adapter_address, v3_tx = deploy_contract(
    'UniswapV3AdapterFixed',
    uniswap_v3_bytecode,
    uniswap_v3_abi
)

if not v3_adapter_address:
    print("\n❌ Failed to deploy Uniswap V3 Adapter")
    exit(1)

time.sleep(5)  # Wait between deployments

# 2. Deploy Uniswap V2 Adapter
v2_adapter_address, v2_tx = deploy_contract(
    'UniswapV2Adapter',
    uniswap_v2_bytecode,
    uniswap_v2_abi
)

if not v2_adapter_address:
    print("\n❌ Failed to deploy Uniswap V2 Adapter")
    exit(1)

time.sleep(5)

# 3. Deploy FlashLoanArbitrageV2
flashloan_address, flashloan_tx = deploy_contract(
    'FlashLoanArbitrageV2',
    flashloan_bytecode,
    flashloan_abi,
    constructor_args=[AAVE_POOL, deployer]
)

if not flashloan_address:
    print("\n❌ Failed to deploy FlashLoanArbitrageV2")
    exit(1)

# Summary
print("\n" + "=" * 80)
print("DEPLOYMENT COMPLETE")
print("=" * 80)

print(f"\n✅ All contracts deployed successfully!")
print(f"\n📋 Contract Addresses:")
print(f"   UniswapV3AdapterFixed: {v3_adapter_address}")
print(f"   UniswapV2Adapter: {v2_adapter_address}")
print(f"   FlashLoanArbitrageV2: {flashloan_address}")

print(f"\n🔗 View on Arbiscan:")
print(f"   https://arbiscan.io/address/{flashloan_address}")
print(f"   https://arbiscan.io/address/{v3_adapter_address}")
print(f"   https://arbiscan.io/address/{v2_adapter_address}")

# Check final balance
final_balance = web3.eth.get_balance(deployer)
final_balance_eth = web3.from_wei(final_balance, 'ether')
spent_eth = balance_eth - final_balance_eth
spent_usd = float(spent_eth) * 2500

print(f"\n💰 Deployment Cost:")
print(f"   ETH spent: {spent_eth:.6f} ETH")
print(f"   USD cost: ~${spent_usd:.2f}")
print(f"   Remaining: {final_balance_eth:.6f} ETH")

# Save deployment info
deployment_info = {
    'network': 'arbitrum',
    'chain_id': 42161,
    'deployer': deployer,
    'timestamp': time.time(),
    'contracts': {
        'FlashLoanArbitrageV2': {
            'address': flashloan_address,
            'tx_hash': flashloan_tx
        },
        'UniswapV3AdapterFixed': {
            'address': v3_adapter_address,
            'tx_hash': v3_tx
        },
        'UniswapV2Adapter': {
            'address': v2_adapter_address,
            'tx_hash': v2_tx
        }
    },
    'cost': {
        'eth': float(spent_eth),
        'usd': spent_usd
    }
}

with open('arbitrum_deployment.json', 'w') as f:
    json.dump(deployment_info, f, indent=2)

print(f"\n💾 Deployment info saved to: arbitrum_deployment.json")

print("\n" + "=" * 80)
print("NEXT STEPS")
print("=" * 80)
print("\n1. Register adapters with main contract:")
print(f"   python register_adapters_arbitrum.py")
print("\n2. Verify contracts on Arbiscan")
print("\n3. Update .env.arbitrum with contract addresses")
print("\n4. Run test scan:")
print(f"   python run_bot_arbitrum.py --test")
