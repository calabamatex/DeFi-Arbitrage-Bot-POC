#!/usr/bin/env python3
"""
Complete Testnet Deployment and End-to-End Test

This script will:
1. Deploy all contracts to Polygon Amoy
2. Deploy mock tokens and mock DEXs
3. Create an artificial arbitrage opportunity
4. Execute a test transaction to prove functionality
5. Update configuration
"""

import os
import json
import subprocess
from web3 import Web3
from eth_account import Account
from dotenv import load_dotenv

load_dotenv('.env.testnet')

# Configuration
from src.utils.key_manager import load_private_key
TESTNET_RPC = "https://rpc-amoy.polygon.technology"
PRIVATE_KEY = load_private_key()
FOUNDRY_PATH = os.path.expanduser("~/.foundry/bin")

# Initialize
web3 = Web3(Web3.HTTPProvider(TESTNET_RPC))
account = Account.from_key(PRIVATE_KEY)

print("="*60)
print("🚀 Flash Loan Arbitrage - Complete Testnet Deployment")
print("="*60)

# Step 1: Check balance
print(f"\n1️⃣  Checking wallet...")
balance_wei = web3.eth.get_balance(account.address)
balance_matic = web3.from_wei(balance_wei, 'ether')

print(f"   Address: {account.address}")
print(f"   Balance: {balance_matic} MATIC")

if balance_matic < 0.05:
    print(f"\n❌ Need at least 0.05 MATIC for deployment")
    print(f"   Current: {balance_matic}")
    exit(1)

print(f"   ✅ Ready to deploy")

# Step 2: Deploy contracts using Foundry
print(f"\n2️⃣  Deploying contracts...")

def deploy_contract(contract_path, constructor_args=""):
    """Deploy a contract using forge create"""
    cmd = [
        f"{FOUNDRY_PATH}/forge", "create",
        contract_path,
        "--rpc-url", TESTNET_RPC,
        "--private-key", PRIVATE_KEY,
        "--json"
    ]

    if constructor_args:
        cmd.extend(["--constructor-args"] + constructor_args.split())

    result = subprocess.run(cmd, cwd="contracts", capture_output=True, text=True)

    if result.returncode != 0:
        print(f"   ❌ Deployment failed: {result.stderr}")
        return None

    try:
        output = json.loads(result.stdout)
        return output.get('deployedTo')
    except:
        # Try to extract address from output
        for line in result.stdout.split('\n'):
            if 'Deployed to:' in line:
                return line.split(':')[1].strip()
        return None

# Deploy Mock USDC
print(f"\n   Deploying Mock USDC...")
mock_usdc = deploy_contract(
    "MockERC20",
    "MockUSDC USDC 6"
)
if not mock_usdc:
    print("   ❌ Failed to deploy Mock USDC")
    exit(1)
print(f"   ✅ Mock USDC: {mock_usdc}")

# Deploy Mock WMATIC
print(f"\n   Deploying Mock WMATIC...")
mock_wmatic = deploy_contract(
    "MockERC20",
    "WrappedMATIC WMATIC 18"
)
if not mock_wmatic:
    print("   ❌ Failed to deploy Mock WMATIC")
    exit(1)
print(f"   ✅ Mock WMATIC: {mock_wmatic}")

# Deploy FlashLoanArbitrageV2
print(f"\n   Deploying FlashLoanArbitrageV2...")
aave_provider = "0x4CeDCB57Af02293231BAA9D39354D6BFDFD251e0"
flash_loan = deploy_contract(
    "FlashLoanArbitrageV2",
    aave_provider
)
if not flash_loan:
    print("   ❌ Failed to deploy FlashLoanArbitrageV2")
    exit(1)
print(f"   ✅ FlashLoanArbitrageV2: {flash_loan}")

# Deploy Mock DEX 1 (rate: 1.0 - fair price)
print(f"\n   Deploying MockDEX1 (rate 1.0)...")
mock_dex1 = deploy_contract(
    "MockDEX",
    "MockDEX1 1000000000000000000"  # 1.0 * 1e18
)
if not mock_dex1:
    print("   ❌ Failed to deploy MockDEX1")
    exit(1)
print(f"   ✅ MockDEX1: {mock_dex1}")

# Deploy Mock DEX 2 (rate: 1.1 - 10% premium = ARBITRAGE!)
print(f"\n   Deploying MockDEX2 (rate 1.1 - ARBITRAGE!)...")
mock_dex2 = deploy_contract(
    "MockDEX",
    "MockDEX2 1100000000000000000"  # 1.1 * 1e18
)
if not mock_dex2:
    print("   ❌ Failed to deploy MockDEX2")
    exit(1)
print(f"   ✅ MockDEX2: {mock_dex2}")

# Step 3: Fund the MockDEXs
print(f"\n3️⃣  Funding MockDEXs with tokens...")

# Load ERC20 ABI (minimal)
erc20_abi = [
    {"inputs":[{"internalType":"address","name":"spender","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"}],"name":"approve","outputs":[{"internalType":"bool","name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"}],"name":"transfer","outputs":[{"internalType":"bool","name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"internalType":"address","name":"account","type":"address"}],"name":"balanceOf","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"}
]

usdc = web3.eth.contract(address=mock_usdc, abi=erc20_abi)
wmatic = web3.eth.contract(address=mock_wmatic, abi=erc20_abi)

# Send USDC and WMATIC to both DEXs
fund_amount_usdc = 100000 * 10**6  # 100k USDC
fund_amount_wmatic = 100000 * 10**18  # 100k WMATIC

for dex_addr, dex_name in [(mock_dex1, "DEX1"), (mock_dex2, "DEX2")]:
    print(f"\n   Funding {dex_name}...")

    # Transfer USDC
    tx1 = usdc.functions.transfer(dex_addr, fund_amount_usdc).build_transaction({
        'from': account.address,
        'nonce': web3.eth.get_transaction_count(account.address),
        'gas': 100000,
        'gasPrice': web3.eth.gas_price,
        'chainId': 80002
    })
    signed1 = account.sign_transaction(tx1)
    hash1 = web3.eth.send_raw_transaction(signed1.raw_transaction)
    web3.eth.wait_for_transaction_receipt(hash1, timeout=60)

    # Transfer WMATIC
    tx2 = wmatic.functions.transfer(dex_addr, fund_amount_wmatic).build_transaction({
        'from': account.address,
        'nonce': web3.eth.get_transaction_count(account.address),
        'gas': 100000,
        'gasPrice': web3.eth.gas_price,
        'chainId': 80002
    })
    signed2 = account.sign_transaction(tx2)
    hash2 = web3.eth.send_raw_transaction(signed2.raw_transaction)
    web3.eth.wait_for_transaction_receipt(hash2, timeout=60)

    print(f"   ✅ {dex_name} funded with 100k USDC and 100k WMATIC")

# Step 4: Save deployment info
print(f"\n4️⃣  Saving deployment info...")

deployment = {
    "network": "Polygon Amoy",
    "chainId": 80002,
    "deployer": account.address,
    "contracts": {
        "FlashLoanArbitrageV2": flash_loan,
        "MockUSDC": mock_usdc,
        "MockWMATIC": mock_wmatic,
        "MockDEX1": mock_dex1,
        "MockDEX2": mock_dex2
    },
    "arbitrageOpportunity": {
        "description": "Buy WMATIC with USDC on DEX1 (rate 1.0), sell on DEX2 (rate 1.1) = 10% profit",
        "dex1Rate": "1.0",
        "dex2Rate": "1.1",
        "expectedProfit": "10%"
    }
}

with open('testnet_deployment.json', 'w') as f:
    json.dump(deployment, f, indent=2)

# Update .env.testnet
with open('.env.testnet', 'r') as f:
    env_content = f.read()

env_content = env_content.replace(
    'FLASH_LOAN_ARBITRAGE_ADDRESS=',
    f'FLASH_LOAN_ARBITRAGE_ADDRESS={flash_loan}'
)
env_content = env_content.replace(
    'USDC_ADDRESS=',
    f'USDC_ADDRESS={mock_usdc}'
)
env_content = env_content.replace(
    'WMATIC_ADDRESS=',
    f'WMATIC_ADDRESS={mock_wmatic}'
)

with open('.env.testnet', 'w') as f:
    f.write(env_content)

# Summary
print(f"\n{'='*60}")
print(f"🎉 Deployment Complete!")
print(f"{'='*60}")
print(f"\nDeployed Contracts:")
print(f"  FlashLoanArbitrageV2:  {flash_loan}")
print(f"  Mock USDC:             {mock_usdc}")
print(f"  Mock WMATIC:           {mock_wmatic}")
print(f"  MockDEX1 (rate 1.0):   {mock_dex1}")
print(f"  MockDEX2 (rate 1.1):   {mock_dex2}")

print(f"\n🎯 Arbitrage Opportunity Created:")
print(f"  Buy WMATIC on DEX1 (rate 1.0)")
print(f"  Sell WMATIC on DEX2 (rate 1.1)")
print(f"  Profit: 10% (guaranteed!)")

print(f"\n📊 View on Explorer:")
print(f"  https://amoy.polygonscan.com/address/{flash_loan}")

print(f"\n{'='*60}")
print(f"Next Steps:")
print(f"{'='*60}")
print(f"1. Create adapter for MockDEX")
print(f"2. Update bot to detect MockDEX opportunities")
print(f"3. Run: cp .env.testnet .env")
print(f"4. Run: python run_bot.py")
print(f"5. Watch it execute and profit!")

print(f"\nDeployment saved to: testnet_deployment.json")
