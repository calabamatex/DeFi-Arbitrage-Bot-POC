"""
Test script to diagnose price quote issues.
"""

from web3 import Web3
import os
from dotenv import load_dotenv

load_dotenv()

# Connect to blockchain
web3 = Web3(Web3.HTTPProvider('http://localhost:8545'))
print(f"Connected: {web3.is_connected()}")
print(f"Chain ID: {web3.eth.chain_id}")
print()

# Addresses
usdc = web3.to_checksum_address("0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174")
wmatic = web3.to_checksum_address("0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270")
v3_quoter = web3.to_checksum_address("0x61fFE014bA17989E743c5F6cB21bF9697530B21e")
v2_router = web3.to_checksum_address("0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff")

print(f"USDC: {usdc}")
print(f"WMATIC: {wmatic}")
print(f"V3 Quoter: {v3_quoter}")
print(f"V2 Router: {v2_router}")
print()

# Check if contracts have code
print("Checking contract code...")
v3_code = web3.eth.get_code(v3_quoter)
v2_code = web3.eth.get_code(v2_router)
print(f"V3 Quoter has code: {len(v3_code) > 0} ({len(v3_code)} bytes)")
print(f"V2 Router has code: {len(v2_code) > 0} ({len(v2_code)} bytes)")
print()

# Test V2 Router with simpler ABI
print("Testing QuickSwap Router...")
v2_abi = [
    {
        "inputs": [
            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
            {"internalType": "address[]", "name": "path", "type": "address[]"}
        ],
        "name": "getAmountsOut",
        "outputs": [
            {"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}
        ],
        "stateMutability": "view",
        "type": "function"
    }
]

router_contract = web3.eth.contract(address=v2_router, abi=v2_abi)

try:
    amount_in = 1000 * 10**6  # 1000 USDC
    path = [usdc, wmatic]
    amounts = router_contract.functions.getAmountsOut(amount_in, path).call()
    print(f"✅ V2 Quote successful!")
    print(f"   Input: {amount_in / 10**6} USDC")
    print(f"   Output: {amounts[1] / 10**18} WMATIC")
except Exception as e:
    print(f"❌ V2 Quote failed: {e}")

print()

# Test V3 Quoter - note that quoteExactInputSingle might revert
print("Testing Uniswap V3 Quoter...")

# Updated V3 Quoter ABI for QuoterV2
v3_abi = [
    {
        "inputs": [
            {
                "components": [
                    {"internalType": "address", "name": "tokenIn", "type": "address"},
                    {"internalType": "address", "name": "tokenOut", "type": "address"},
                    {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
                    {"internalType": "uint24", "name": "fee", "type": "uint24"},
                    {"internalType": "uint160", "name": "sqrtPriceLimitX96", "type": "uint160"}
                ],
                "internalType": "struct IQuoterV2.QuoteExactInputSingleParams",
                "name": "params",
                "type": "tuple"
            }
        ],
        "name": "quoteExactInputSingle",
        "outputs": [
            {"internalType": "uint256", "name": "amountOut", "type": "uint256"},
            {"internalType": "uint160", "name": "sqrtPriceX96After", "type": "uint160"},
            {"internalType": "uint32", "name": "initializedTicksCrossed", "type": "uint32"},
            {"internalType": "uint256", "name": "gasEstimate", "type": "uint256"}
        ],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]

quoter_contract = web3.eth.contract(address=v3_quoter, abi=v3_abi)

try:
    amount_in = 1000 * 10**6  # 1000 USDC

    for fee in [500, 3000, 10000]:
        try:
            params = {
                'tokenIn': usdc,
                'tokenOut': wmatic,
                'amountIn': amount_in,
                'fee': fee,
                'sqrtPriceLimitX96': 0
            }

            result = quoter_contract.functions.quoteExactInputSingle(params).call()
            amount_out = result[0]  # First element is amountOut

            print(f"✅ V3 Quote successful (fee {fee/10000}%)!")
            print(f"   Input: {amount_in / 10**6} USDC")
            print(f"   Output: {amount_out / 10**18} WMATIC")
        except Exception as e:
            print(f"❌ V3 Quote failed for fee {fee}: {str(e)[:100]}")

except Exception as e:
    print(f"❌ V3 Contract setup failed: {e}")

print("\n" + "="*60)
print("Diagnostic complete!")
