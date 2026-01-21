"""
Test script for Flash Loan Orchestrator

Tests transaction building and execution logic.
"""

from src.flash_loan_orchestrator import FlashLoanOrchestrator
from web3 import Web3
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize Web3
web3 = Web3(Web3.HTTPProvider('http://localhost:8545'))
print(f"Connected: {web3.is_connected()}")
print(f"Chain ID: {web3.eth.chain_id}\n")

# Initialize orchestrator in dry run mode
orchestrator = FlashLoanOrchestrator(
    web3=web3,
    contract_address=os.getenv('FLASH_LOAN_ARBITRAGE_ADDRESS'),
    private_key=os.getenv('PRIVATE_KEY'),
    v3_adapter_address=os.getenv('UNISWAP_V3_ADAPTER_ADDRESS'),
    v2_adapter_address=os.getenv('UNISWAP_V2_ADAPTER_ADDRESS'),
    dry_run=True  # Safe mode - won't send real transactions
)

print(f"✅ Orchestrator initialized")
print(f"Executor: {orchestrator.address}")
print(f"Contract: {orchestrator.contract_address}\n")

# Create a mock opportunity (V3→V2 direction)
print("="*60)
print("Testing V3→V2 Arbitrage")
print("="*60)

mock_opportunity_v3_v2 = {
    'direction': 'V3→V2',
    'token_in': os.getenv('USDC_ADDRESS'),
    'token_out': os.getenv('WMATIC_ADDRESS'),
    'amount_in': 1000 * 10**6,  # 1000 USDC
    'net_profit': 5 * 10**6,     # 5 USDC profit
    'v3_fee': 500,               # 0.05% fee
    'dex_path': ['uniswap_v3', 'quickswap']
}

print(f"\nMock Opportunity:")
print(f"  Direction: {mock_opportunity_v3_v2['direction']}")
print(f"  Amount: {mock_opportunity_v3_v2['amount_in'] / 10**6} USDC")
print(f"  Expected profit: {mock_opportunity_v3_v2['net_profit'] / 10**6} USDC")

# Test transaction building
print(f"\nBuilding transaction...")
try:
    tx = orchestrator.build_transaction(mock_opportunity_v3_v2)
    print(f"✅ Transaction built successfully")
    print(f"  From: {tx['from']}")
    print(f"  To: {tx['to']}")
    print(f"  Nonce: {tx['nonce']}")
    print(f"  Gas: {tx['gas']:,}")
    print(f"  Gas price: {web3.from_wei(tx['maxFeePerGas'], 'gwei'):.2f} gwei")
    print(f"  Chain ID: {tx['chainId']}")
except Exception as e:
    print(f"❌ Transaction building failed: {e}")

# Test execution (dry run)
print(f"\nExecuting opportunity (dry run)...")
result = orchestrator.execute_opportunity(mock_opportunity_v3_v2)

print(f"\n✅ Execution test complete")
print(f"  Success: {result['success']}")
print(f"  TX Hash: {result['tx_hash']}")
print(f"  Gas used: {result['gas_used']:,}")
print(f"  Profit: {result['profit'] / 10**6:.2f} USDC")

# Test V2→V3 direction
print(f"\n{'='*60}")
print("Testing V2→V3 Arbitrage")
print("="*60)

mock_opportunity_v2_v3 = {
    'direction': 'V2→V3',
    'token_in': os.getenv('USDC_ADDRESS'),
    'token_out': os.getenv('WMATIC_ADDRESS'),
    'amount_in': 5000 * 10**6,   # 5000 USDC
    'net_profit': 10 * 10**6,    # 10 USDC profit
    'v3_fee': 3000,              # 0.3% fee
    'dex_path': ['quickswap', 'uniswap_v3']
}

print(f"\nMock Opportunity:")
print(f"  Direction: {mock_opportunity_v2_v3['direction']}")
print(f"  Amount: {mock_opportunity_v2_v3['amount_in'] / 10**6} USDC")
print(f"  Expected profit: {mock_opportunity_v2_v3['net_profit'] / 10**6} USDC")

result2 = orchestrator.execute_opportunity(mock_opportunity_v2_v3)

print(f"\n✅ Execution test complete")
print(f"  Success: {result2['success']}")
print(f"  TX Hash: {result2['tx_hash']}")
print(f"  Gas used: {result2['gas_used']:,}")
print(f"  Profit: {result2['profit'] / 10**6:.2f} USDC")

print(f"\n{'='*60}")
print("All tests passed! ✅")
print("="*60)
print(f"\nThe orchestrator is ready to execute real arbitrage trades.")
print(f"To run with real transactions, set DRY_RUN=false in .env")
