#!/usr/bin/env python3
"""
Execute Profitable Arbitrage - FINAL PROOF OF CONCEPT

This script executes a real profitable arbitrage through the FlashLoanArbitrageV2
contract, proving the entire system works end-to-end with profit capture.

Arbitrage Path:
1. Flash loan 1300 USDC from Aave V3
2. Buy ~10,000 WMATIC on Uniswap V3 (cheap at $0.13)
3. Sell 10,000 WMATIC on QuickSwap (expensive at $0.2185)
4. Repay flash loan + fee
5. Capture profit (~$884)
"""

from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from eth_account import Account

# Initialize
web3 = Web3(Web3.HTTPProvider('http://localhost:8545'))
web3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

# Configuration
PRIVATE_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
account = Account.from_key(PRIVATE_KEY)

# Contract addresses
FLASH_LOAN_ADDRESS = "0x829aB11e413dc01ABB7762799FE2EaE68DB86987"
V3_ADAPTER = "0x6153F4d8AEd04C670D1cEDe9095165cB5819B074"
V2_ADAPTER = "0xae5926A1AD0FED47b868E16325b5B10853017236"

# Tokens
USDC = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
WMATIC = "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270"

print("="*80)
print("🚀 EXECUTING PROFITABLE ARBITRAGE - FINAL POC")
print("="*80)

# Contract ABI
flash_loan_abi = [
    {
        "inputs": [
            {
                "components": [
                    {
                        "components": [
                            {"internalType": "address", "name": "adapter", "type": "address"},
                            {"internalType": "address", "name": "tokenIn", "type": "address"},
                            {"internalType": "address", "name": "tokenOut", "type": "address"},
                            {"internalType": "uint256", "name": "minAmountOut", "type": "uint256"},
                            {"internalType": "bytes", "name": "data", "type": "bytes"}
                        ],
                        "internalType": "struct FlashLoanArbitrageV2.SwapStep[]",
                        "name": "steps",
                        "type": "tuple[]"
                    },
                    {"internalType": "uint256", "name": "flashLoanAmount", "type": "uint256"},
                    {"internalType": "address", "name": "flashLoanAsset", "type": "address"},
                    {"internalType": "uint256", "name": "minFinalAmount", "type": "uint256"},
                    {"internalType": "uint256", "name": "deadline", "type": "uint256"}
                ],
                "internalType": "struct FlashLoanArbitrageV2.ArbitrageParams",
                "name": "params",
                "type": "tuple"
            }
        ],
        "name": "executeArbitrage",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]

erc20_abi = [
    {'inputs':[{'name':'account','type':'address'}],'name':'balanceOf','outputs':[{'name':'','type':'uint256'}],'stateMutability':'view','type':'function'}
]

# Load contracts
flash_loan = web3.eth.contract(address=FLASH_LOAN_ADDRESS, abi=flash_loan_abi)
usdc_contract = web3.eth.contract(address=USDC, abi=erc20_abi)

print(f"\n1️⃣  Configuration")
print(f"   Executor: {account.address}")
print(f"   Contract: {FLASH_LOAN_ADDRESS}")

# Check initial balance
initial_usdc = usdc_contract.functions.balanceOf(FLASH_LOAN_ADDRESS).call()
print(f"   Contract USDC before: {initial_usdc / 10**6:.2f} USDC")

# Arbitrage parameters
flash_amount = 1300 * 10**6  # 1300 USDC flash loan
flash_loan_fee = (flash_amount * 5) // 10000  # 0.05% Aave fee
min_final_amount = flash_amount + flash_loan_fee + (50 * 10**6)  # Loan + fee + $50 profit minimum

print(f"\n2️⃣  Arbitrage Parameters")
print(f"   Flash Loan: {flash_amount / 10**6:.2f} USDC")
print(f"   Flash Fee: {flash_loan_fee / 10**6:.4f} USDC")
print(f"   Min Return: {min_final_amount / 10**6:.2f} USDC")
print(f"   Expected Profit: ~$880")

# Build swap steps
# Step 1: Buy WMATIC on Uniswap V3 (cheap)
step1 = (
    V3_ADAPTER,
    USDC,
    WMATIC,
    0,  # No minimum for intermediate swap
    b''  # Empty data (fee is fixed in adapter)
)

# Step 2: Sell WMATIC on QuickSwap (expensive)
step2 = (
    V2_ADAPTER,
    WMATIC,
    USDC,
    min_final_amount,  # Must get back loan + fee + profit
    b''  # Empty data
)

swap_steps = [step1, step2]

print(f"\n3️⃣  Swap Path")
print(f"   Step 1: USDC → WMATIC (Uniswap V3 @ $0.13/WMATIC)")
print(f"   Step 2: WMATIC → USDC (QuickSwap @ $0.2185/WMATIC)")

# Get deadline
deadline = web3.eth.get_block('latest')['timestamp'] + 3600

# Build arbitrage params
arbitrage_params = (
    swap_steps,
    flash_amount,
    USDC,
    min_final_amount,
    deadline
)

print(f"\n4️⃣  Executing Transaction...")

try:
    # Build transaction
    nonce = web3.eth.get_transaction_count(account.address)

    tx = flash_loan.functions.executeArbitrage(
        arbitrage_params
    ).build_transaction({
        'from': account.address,
        'nonce': nonce,
        'gas': 3000000,
        'gasPrice': web3.eth.gas_price,
        'chainId': 137
    })

    print(f"   Transaction built")
    print(f"   Nonce: {nonce}")
    print(f"   Gas: {tx['gas']:,}")

    # Sign
    signed_tx = account.sign_transaction(tx)
    print(f"   Transaction signed")

    # Send
    print(f"\n   📤 Sending transaction...")
    tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
    print(f"   TX Hash: {tx_hash.hex()}")

    # Wait for confirmation
    print(f"   ⏳ Waiting for confirmation...")
    receipt = web3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)

    print(f"\n{'='*80}")
    if receipt['status'] == 1:
        print(f"✅ ARBITRAGE EXECUTED SUCCESSFULLY!")
        print(f"{'='*80}")

        # Check final balance
        final_usdc = usdc_contract.functions.balanceOf(FLASH_LOAN_ADDRESS).call()
        profit = (final_usdc - initial_usdc) / 10**6

        print(f"\n📊 Results:")
        print(f"   Block: {receipt['blockNumber']}")
        print(f"   Gas Used: {receipt['gasUsed']:,}")
        print(f"   Gas Cost: {web3.from_wei(receipt['gasUsed'] * receipt['effectiveGasPrice'], 'ether'):.6f} MATIC")
        print(f"")
        print(f"   Contract USDC before: ${initial_usdc / 10**6:.2f}")
        print(f"   Contract USDC after:  ${final_usdc / 10**6:.2f}")
        print(f"")
        print(f"   💰 PROFIT CAPTURED: ${profit:.2f} USDC")
        print(f"")

        print(f"{'='*80}")
        print(f"🎉 END-TO-END PROOF COMPLETE!")
        print(f"{'='*80}")
        print(f"")
        print(f"✅ Flash loan executed from Aave V3")
        print(f"✅ Bought WMATIC on Uniswap V3")
        print(f"✅ Sold WMATIC on QuickSwap")
        print(f"✅ Flash loan repaid with fee")
        print(f"✅ PROFIT CAPTURED: ${profit:.2f}")
        print(f"")
        print(f"The arbitrage bot is FULLY FUNCTIONAL and PROFITABLE! 🚀")
        print(f"")

    else:
        print(f"❌ TRANSACTION REVERTED")
        print(f"{'='*80}")
        print(f"\n   Block: {receipt['blockNumber']}")
        print(f"   Gas Used: {receipt['gasUsed']:,}")

        # Try to decode error
        print(f"\n   Checking revert reason...")
        try:
            web3.eth.call({
                'from': account.address,
                'to': FLASH_LOAN_ADDRESS,
                'data': tx['data']
            }, receipt['blockNumber'] - 1)
        except Exception as e:
            print(f"   Revert: {e}")

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()

print(f"\n{'='*80}")
