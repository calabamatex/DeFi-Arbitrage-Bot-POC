#!/usr/bin/env python3
"""
Deploy Flash Loan Arbitrage contracts to Polygon Mainnet
"""
import json
import os
import sys
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from eth_account import Account
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

# Connect to Polygon
web3 = Web3(Web3.HTTPProvider(os.getenv('ALCHEMY_POLYGON_RPC_URL')))
web3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

# Load account
account = Account.from_key(os.getenv('PRIVATE_KEY'))

print("="*80)
print("🚀 DEPLOYING TO POLYGON MAINNET")
print("="*80)
print()
print("⚠️  WARNING: This will deploy to REAL Polygon mainnet")
print("⚠️  Real MATIC will be spent on gas (~$0.15-0.30)")
print()
confirm = input("Are you sure? (yes/no): ")

if confirm != "yes":
    print("Deployment cancelled")
    sys.exit(1)

print()
print(f"Network: Polygon Mainnet (Chain ID: {web3.eth.chain_id})")
print(f"Deployer: {account.address}")
print(f"Balance: {web3.from_wei(web3.eth.get_balance(account.address), 'ether')} MATIC")
print()

# Polygon mainnet addresses
UNISWAP_V3_ROUTER = "0xE592427A0AEce92De3Edee1F18E0157C05861564"
QUICKSWAP_ROUTER = "0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff"
AAVE_POOL_PROVIDER = "0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb"

def load_contract_artifact(contract_name):
    """Load compiled contract artifact"""
    artifact_path = Path(f"out/{contract_name}.sol/{contract_name}.json")
    with open(artifact_path) as f:
        artifact = json.load(f)
    return artifact['abi'], artifact['bytecode']['object']

def deploy_contract(contract_name, constructor_args=None):
    """Deploy a contract"""
    print("="*80)
    print(f"Deploying {contract_name}...")
    print("="*80)

    abi, bytecode = load_contract_artifact(contract_name)

    # Create contract object
    Contract = web3.eth.contract(abi=abi, bytecode=bytecode)

    # Build constructor transaction
    if constructor_args:
        constructor_tx = Contract.constructor(*constructor_args)
    else:
        constructor_tx = Contract.constructor()

    # Build transaction
    tx = constructor_tx.build_transaction({
        'from': account.address,
        'nonce': web3.eth.get_transaction_count(account.address),
        'gas': 3000000,
        'maxFeePerGas': web3.eth.gas_price * 2,
        'maxPriorityFeePerGas': web3.to_wei(30, 'gwei'),
        'chainId': 137
    })

    print(f"  Gas estimate: {tx['gas']}")
    print(f"  Gas price: {web3.from_wei(tx['maxFeePerGas'], 'gwei')} gwei")
    print()

    # Sign and send transaction
    signed_tx = account.sign_transaction(tx)
    tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)

    print(f"  TX Hash: {tx_hash.hex()}")
    print(f"  Waiting for confirmation...")

    # Wait for receipt
    receipt = web3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)

    if receipt['status'] == 1:
        contract_address = receipt['contractAddress']
        print(f"✅ {contract_name}: {contract_address}")
        print(f"  Gas used: {receipt['gasUsed']}")
        print(f"  Block: {receipt['blockNumber']}")
        print()
        return contract_address
    else:
        print(f"❌ Deployment failed!")
        sys.exit(1)

# Deploy contracts
try:
    # 1. Deploy UniswapV3AdapterFixed
    v3_adapter = deploy_contract(
        "UniswapV3AdapterFixed",
        constructor_args=[UNISWAP_V3_ROUTER]
    )

    # 2. Deploy UniswapV2Adapter
    v2_adapter = deploy_contract(
        "UniswapV2Adapter",
        constructor_args=[QUICKSWAP_ROUTER, "QuickSwap"]
    )

    # 3. Deploy FlashLoanArbitrageV2
    # minProfit: 100000 wei, maxSlippageBps: 500 (5%)
    flash_loan = deploy_contract(
        "FlashLoanArbitrageV2",
        constructor_args=[AAVE_POOL_PROVIDER, 100000, 500]
    )

    # 4. Register adapters
    print("="*80)
    print("Registering Adapters...")
    print("="*80)

    flash_loan_abi = load_contract_artifact("FlashLoanArbitrageV2")[0]
    flash_loan_contract = web3.eth.contract(address=flash_loan, abi=flash_loan_abi)

    # Register V3 adapter
    print("Registering V3 Adapter...")
    tx1 = flash_loan_contract.functions.setAdapter(v3_adapter, True).build_transaction({
        'from': account.address,
        'nonce': web3.eth.get_transaction_count(account.address),
        'gas': 100000,
        'maxFeePerGas': web3.eth.gas_price * 2,
        'maxPriorityFeePerGas': web3.to_wei(30, 'gwei'),
        'chainId': 137
    })
    signed1 = account.sign_transaction(tx1)
    hash1 = web3.eth.send_raw_transaction(signed1.raw_transaction)
    web3.eth.wait_for_transaction_receipt(hash1)
    print(f"✅ V3 Adapter registered")

    # Register V2 adapter
    print("Registering V2 Adapter...")
    tx2 = flash_loan_contract.functions.setAdapter(v2_adapter, True).build_transaction({
        'from': account.address,
        'nonce': web3.eth.get_transaction_count(account.address),
        'gas': 100000,
        'maxFeePerGas': web3.eth.gas_price * 2,
        'maxPriorityFeePerGas': web3.to_wei(30, 'gwei'),
        'chainId': 137
    })
    signed2 = account.sign_transaction(tx2)
    hash2 = web3.eth.send_raw_transaction(signed2.raw_transaction)
    web3.eth.wait_for_transaction_receipt(hash2)
    print(f"✅ V2 Adapter registered")
    print()

    # Summary
    print("="*80)
    print("✅ DEPLOYMENT COMPLETE!")
    print("="*80)
    print()
    print("Deployed Contracts:")
    print(f"  FlashLoanArbitrageV2:   {flash_loan}")
    print(f"  UniswapV3AdapterFixed:  {v3_adapter}")
    print(f"  UniswapV2Adapter:       {v2_adapter}")
    print()
    print("View on PolygonScan:")
    print(f"  https://polygonscan.com/address/{flash_loan}")
    print()

    # Update .env file
    print("="*80)
    print("Updating .env file...")
    print("="*80)

    # Read current .env
    with open('.env', 'r') as f:
        env_lines = f.readlines()

    # Update addresses
    new_lines = []
    for line in env_lines:
        if line.startswith('FLASH_LOAN_ARBITRAGE_ADDRESS='):
            new_lines.append(f'FLASH_LOAN_ARBITRAGE_ADDRESS={flash_loan}\n')
        elif line.startswith('UNISWAP_V3_ADAPTER_ADDRESS='):
            new_lines.append(f'UNISWAP_V3_ADAPTER_ADDRESS={v3_adapter}\n')
        elif line.startswith('UNISWAP_V2_ADAPTER_ADDRESS='):
            new_lines.append(f'UNISWAP_V2_ADAPTER_ADDRESS={v2_adapter}\n')
        else:
            new_lines.append(line)

    # Write updated .env
    with open('.env', 'w') as f:
        f.writelines(new_lines)

    print("✅ .env updated with mainnet addresses")
    print()

    # Save deployment info
    deployment_info = {
        "network": "Polygon Mainnet",
        "chainId": 137,
        "timestamp": web3.eth.get_block('latest')['timestamp'],
        "contracts": {
            "FlashLoanArbitrageV2": flash_loan,
            "UniswapV3AdapterFixed": v3_adapter,
            "UniswapV2Adapter": v2_adapter
        },
        "polygonscan": {
            "FlashLoanArbitrageV2": f"https://polygonscan.com/address/{flash_loan}",
            "UniswapV3AdapterFixed": f"https://polygonscan.com/address/{v3_adapter}",
            "UniswapV2Adapter": f"https://polygonscan.com/address/{v2_adapter}"
        }
    }

    with open('mainnet_deployment.json', 'w') as f:
        json.dump(deployment_info, f, indent=2)

    print("✅ Deployment info saved to mainnet_deployment.json")
    print()

    print("="*80)
    print("🎉 READY FOR DRY_RUN OBSERVATION MODE")
    print("="*80)
    print()
    print("Next steps:")
    print("  1. Review .env to confirm DRY_RUN=true")
    print("  2. Run: python run_bot.py")
    print("  3. Bot will scan for opportunities but NOT execute")
    print("  4. Observe for 1-2 weeks")
    print("  5. Analyze results before enabling execution")
    print()

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
