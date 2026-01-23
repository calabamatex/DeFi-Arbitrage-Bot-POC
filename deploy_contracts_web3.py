#!/usr/bin/env python3
"""
Deploy all contracts to Anvil fork using web3.py
This avoids some RPC limitations that forge create hits
"""

import json
import subprocess
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from eth_account import Account

# Configuration
RPC_URL = "http://localhost:8545"
PRIVATE_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"

# Contract addresses (Polygon Mainnet)
UNISWAP_V3_ROUTER = "0xE592427A0AEce92De3Edee1F18E0157C05861564"
UNISWAP_V3_QUOTER = "0x61fFE014bA17989E743c5F6cB21bF9697530B21e"
QUICKSWAP_ROUTER = "0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff"
AAVE_POOL_PROVIDER = "0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb"

# Initialize web3
web3 = Web3(Web3.HTTPProvider(RPC_URL))
web3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
account = Account.from_key(PRIVATE_KEY)

print("="*60)
print("🚀 Deploying Contracts to Anvil Fork")
print("="*60)
print(f"\nDeployer: {account.address}")
print(f"Balance: {web3.from_wei(web3.eth.get_balance(account.address), 'ether')} MATIC\n")

def compile_and_get_bytecode(contract_name):
    """Compile contract and extract bytecode"""
    print(f"  Compiling {contract_name}...")

    # Run forge build
    result = subprocess.run(
        ["~/.foundry/bin/forge", "build", "--silent"],
        cwd=".",
        capture_output=True,
        shell=True
    )

    # Read the artifact
    artifact_path = f"out/{contract_name}.sol/{contract_name}.json"
    try:
        with open(artifact_path, 'r') as f:
            artifact = json.load(f)
            return artifact['bytecode']['object'], artifact['abi']
    except Exception as e:
        print(f"  ❌ Failed to load artifact: {e}")
        return None, None

def deploy_contract(name, bytecode, abi, *constructor_args):
    """Deploy a contract"""
    print(f"\n{'='*60}")
    print(f"Deploying {name}...")
    print(f"{'='*60}")

    # Create contract instance
    contract = web3.eth.contract(abi=abi, bytecode=bytecode)

    # Build constructor transaction
    if constructor_args:
        print(f"  Constructor args: {constructor_args}")
        constructor_txn = contract.constructor(*constructor_args).build_transaction({
            'from': account.address,
            'nonce': web3.eth.get_transaction_count(account.address),
            'gas': 3000000,
            'gasPrice': web3.eth.gas_price,
            'chainId': 137
        })
    else:
        constructor_txn = contract.constructor().build_transaction({
            'from': account.address,
            'nonce': web3.eth.get_transaction_count(account.address),
            'gas': 3000000,
            'gasPrice': web3.eth.gas_price,
            'chainId': 137
        })

    # Sign and send
    signed_txn = account.sign_transaction(constructor_txn)
    tx_hash = web3.eth.send_raw_transaction(signed_txn.raw_transaction)
    print(f"  TX Hash: {tx_hash.hex()}")

    # Wait for receipt
    receipt = web3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

    if receipt['status'] == 1:
        address = receipt['contractAddress']
        print(f"  ✅ Deployed to: {address}")
        print(f"  Gas Used: {receipt['gasUsed']:,}")
        return address
    else:
        print(f"  ❌ Deployment failed")
        return None

# Deploy contracts
try:
    # 1. Deploy UniswapV3Adapter
    print("\n1️⃣  UniswapV3Adapter")
    bytecode, abi = compile_and_get_bytecode("UniswapV3Adapter")
    if bytecode and abi:
        v3_adapter = deploy_contract(
            "UniswapV3Adapter",
            bytecode,
            abi,
            UNISWAP_V3_ROUTER,
            UNISWAP_V3_QUOTER
        )
    else:
        print("  ❌ Failed to compile")
        v3_adapter = None

    # 2. Deploy UniswapV2Adapter
    print("\n2️⃣  UniswapV2Adapter")
    bytecode, abi = compile_and_get_bytecode("UniswapV2Adapter")
    if bytecode and abi:
        v2_adapter = deploy_contract(
            "UniswapV2Adapter",
            bytecode,
            abi,
            QUICKSWAP_ROUTER,
            "QuickSwap"
        )
    else:
        print("  ❌ Failed to compile")
        v2_adapter = None

    # 3. Deploy FlashLoanArbitrageV2
    print("\n3️⃣  FlashLoanArbitrageV2")
    bytecode, abi = compile_and_get_bytecode("FlashLoanArbitrageV2")
    if bytecode and abi:
        flash_loan = deploy_contract(
            "FlashLoanArbitrageV2",
            bytecode,
            abi,
            AAVE_POOL_PROVIDER,
            100000,  # minProfitWei (0.0001 MATIC)
            500  # maxSlippageBps (5%)
        )
    else:
        print("  ❌ Failed to compile")
        flash_loan = None

    # Summary
    print(f"\n{'='*60}")
    print(f"📋 Deployment Summary")
    print(f"{'='*60}")
    if v3_adapter:
        print(f"✅ UniswapV3Adapter: {v3_adapter}")
    else:
        print(f"❌ UniswapV3Adapter: FAILED")

    if v2_adapter:
        print(f"✅ UniswapV2Adapter:  {v2_adapter}")
    else:
        print(f"❌ UniswapV2Adapter: FAILED")

    if flash_loan:
        print(f"✅ FlashLoanArbitrageV2: {flash_loan}")
    else:
        print(f"❌ FlashLoanArbitrageV2: FAILED")

    # Save to .env
    if v3_adapter and v2_adapter and flash_loan:
        print(f"\n{'='*60}")
        print(f"💾 Updating .env file...")
        print(f"{'='*60}")

        with open('.env', 'r') as f:
            env_content = f.read()

        env_content = env_content.replace(
            'FLASH_LOAN_ARBITRAGE_ADDRESS=0xae5926A1AD0FED47b868E16325b5B10853017236',
            f'FLASH_LOAN_ARBITRAGE_ADDRESS={flash_loan}'
        )
        env_content = env_content.replace(
            'UNISWAP_V3_ADAPTER_ADDRESS=0x829aB11e413dc01ABB7762799FE2EaE68DB86987',
            f'UNISWAP_V3_ADAPTER_ADDRESS={v3_adapter}'
        )
        env_content = env_content.replace(
            'UNISWAP_V2_ADAPTER_ADDRESS=0x814274Bb96F910538873c8966D30C7b1948EFa9E',
            f'UNISWAP_V2_ADAPTER_ADDRESS={v2_adapter}'
        )

        with open('.env', 'w') as f:
            f.write(env_content)

        print(f"✅ .env updated with new addresses")

        print(f"\n{'='*60}")
        print(f"🎉 All contracts deployed successfully!")
        print(f"{'='*60}")
        print(f"\nReady to run: ./venv/bin/python manual_execution_test.py")

except Exception as e:
    print(f"\n❌ Deployment failed: {e}")
    import traceback
    traceback.print_exc()
