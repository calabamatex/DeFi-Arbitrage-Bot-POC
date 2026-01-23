#!/usr/bin/env python3
"""
Create Artificial Arbitrage Opportunity on Mainnet Fork

This script:
1. Uses a whale account to manipulate QuickSwap price
2. Creates a profitable spread between Uniswap V3 and QuickSwap
3. Verifies the price difference
4. Sets up for bot execution test
"""

from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
import time

# Initialize
web3 = Web3(Web3.HTTPProvider('http://localhost:8545'))
web3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

# Addresses
USDC = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
WMATIC = "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270"
USDC_WHALE = "0xe7804c37c13166fF0b37F5aE0BB07A3aEbb6e245"  # Has 700k+ USDC
QUICKSWAP_ROUTER = "0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff"
UNISWAP_V3_QUOTER = "0x61fFE014bA17989E743c5F6cB21bF9697530B21e"

print("="*80)
print("🎯 Creating Artificial Arbitrage Opportunity")
print("="*80)

# ERC20 ABI
erc20_abi = [
    {'inputs':[{'name':'spender','type':'address'},{'name':'amount','type':'uint256'}],'name':'approve','outputs':[{'name':'','type':'bool'}],'stateMutability':'nonpayable','type':'function'},
    {'inputs':[{'name':'account','type':'address'}],'name':'balanceOf','outputs':[{'name':'','type':'uint256'}],'stateMutability':'view','type':'function'}
]

# QuickSwap Router ABI (minimal)
router_abi = [
    {
        'inputs': [
            {'name': 'amountIn', 'type': 'uint256'},
            {'name': 'amountOutMin', 'type': 'uint256'},
            {'name': 'path', 'type': 'address[]'},
            {'name': 'to', 'type': 'address'},
            {'name': 'deadline', 'type': 'uint256'}
        ],
        'name': 'swapExactTokensForTokens',
        'outputs': [{'name': 'amounts', 'type': 'uint256[]'}],
        'stateMutability': 'nonpayable',
        'type': 'function'
    },
    {
        'inputs': [
            {'name': 'amountIn', 'type': 'uint256'},
            {'name': 'path', 'type': 'address[]'}
        ],
        'name': 'getAmountsOut',
        'outputs': [{'name': 'amounts', 'type': 'uint256[]'}],
        'stateMutability': 'view',
        'type': 'function'
    }
]

# Uniswap V3 Quoter ABI (minimal)
quoter_abi = [
    {
        'inputs': [
            {'name': 'tokenIn', 'type': 'address'},
            {'name': 'tokenOut', 'type': 'address'},
            {'name': 'fee', 'type': 'uint24'},
            {'name': 'amountIn', 'type': 'uint256'},
            {'name': 'sqrtPriceLimitX96', 'type': 'uint160'}
        ],
        'name': 'quoteExactInputSingle',
        'outputs': [
            {'name': 'amountOut', 'type': 'uint256'},
            {'name': 'sqrtPriceX96After', 'type': 'uint160'},
            {'name': 'initializedTicksCrossed', 'type': 'uint32'},
            {'name': 'gasEstimate', 'type': 'uint256'}
        ],
        'stateMutability': 'nonpayable',
        'type': 'function'
    }
]

# Contract instances
usdc = web3.eth.contract(address=USDC, abi=erc20_abi)
wmatic = web3.eth.contract(address=WMATIC, abi=erc20_abi)
quickswap = web3.eth.contract(address=QUICKSWAP_ROUTER, abi=router_abi)
uniswap_quoter = web3.eth.contract(address=UNISWAP_V3_QUOTER, abi=quoter_abi)

# Step 1: Check initial prices
print("\n1️⃣  Checking initial prices...")

test_amount = 1000 * 10**6  # 1000 USDC

# Get Uniswap V3 price
try:
    v3_quote = uniswap_quoter.functions.quoteExactInputSingle(
        USDC,
        WMATIC,
        500,  # 0.05% fee
        test_amount,
        0
    ).call()
    v3_wmatic_out = v3_quote[0]
    v3_price = (test_amount / 10**6) / (v3_wmatic_out / 10**18)
    print(f"   Uniswap V3:  1000 USDC → {v3_wmatic_out / 10**18:.4f} WMATIC")
    print(f"                Price: ${v3_price:.4f} per WMATIC")
except Exception as e:
    print(f"   ⚠️  V3 quote failed: {e}")
    v3_wmatic_out = 0
    v3_price = 0

# Get QuickSwap price
try:
    qs_amounts = quickswap.functions.getAmountsOut(
        test_amount,
        [USDC, WMATIC]
    ).call()
    qs_wmatic_out = qs_amounts[1]
    qs_price = (test_amount / 10**6) / (qs_wmatic_out / 10**18)
    print(f"   QuickSwap:   1000 USDC → {qs_wmatic_out / 10**18:.4f} WMATIC")
    print(f"                Price: ${qs_price:.4f} per WMATIC")
except Exception as e:
    print(f"   ⚠️  QuickSwap quote failed: {e}")
    qs_wmatic_out = 0
    qs_price = 0

if v3_wmatic_out > 0 and qs_wmatic_out > 0:
    initial_diff = abs(v3_wmatic_out - qs_wmatic_out) / v3_wmatic_out * 100
    print(f"\n   📊 Initial Price Difference: {initial_diff:.2f}%")

# Step 2: Manipulate QuickSwap price
print("\n2️⃣  Manipulating QuickSwap price...")
print(f"   Strategy: Buy large amount of WMATIC on QuickSwap")
print(f"   This will push WMATIC price UP on QuickSwap only")

# Impersonate whale
web3.provider.make_request('anvil_impersonateAccount', [USDC_WHALE])

# Check whale balance
whale_balance = usdc.functions.balanceOf(USDC_WHALE).call()
print(f"\n   Whale USDC balance: {whale_balance / 10**6:,.2f} USDC")

# Approve QuickSwap router
print(f"   Approving QuickSwap router...")
usdc.functions.approve(QUICKSWAP_ROUTER, whale_balance).transact({
    'from': USDC_WHALE,
    'gas': 100000
})

# Execute massive buy order on QuickSwap (buy WMATIC with USDC)
# This will make WMATIC more expensive on QuickSwap
manipulation_amount = 100000 * 10**6  # 100k USDC

print(f"\n   Executing MASSIVE buy on QuickSwap...")
print(f"   Buying WMATIC with {manipulation_amount / 10**6:,.0f} USDC")

deadline = web3.eth.get_block('latest')['timestamp'] + 3600

tx_hash = quickswap.functions.swapExactTokensForTokens(
    manipulation_amount,
    0,  # Accept any amount (we're manipulating, not trading)
    [USDC, WMATIC],
    USDC_WHALE,
    deadline
).transact({
    'from': USDC_WHALE,
    'gas': 300000
})

receipt = web3.eth.wait_for_transaction_receipt(tx_hash)

if receipt['status'] == 1:
    print(f"   ✅ Manipulation successful!")
    print(f"   TX: {tx_hash.hex()}")
else:
    print(f"   ❌ Manipulation failed")
    exit(1)

# Stop impersonating
web3.provider.make_request('anvil_stopImpersonatingAccount', [USDC_WHALE])

# Step 3: Check new prices
print("\n3️⃣  Checking prices after manipulation...")

time.sleep(1)

# Get new Uniswap V3 price (should be unchanged)
try:
    v3_quote_after = uniswap_quoter.functions.quoteExactInputSingle(
        USDC,
        WMATIC,
        500,
        test_amount,
        0
    ).call()
    v3_wmatic_after = v3_quote_after[0]
    v3_price_after = (test_amount / 10**6) / (v3_wmatic_after / 10**18)
    print(f"   Uniswap V3:  1000 USDC → {v3_wmatic_after / 10**18:.4f} WMATIC")
    print(f"                Price: ${v3_price_after:.4f} per WMATIC")
except Exception as e:
    print(f"   ⚠️  V3 quote failed: {e}")
    v3_wmatic_after = v3_wmatic_out
    v3_price_after = v3_price

# Get new QuickSwap price (should be higher)
try:
    qs_amounts_after = quickswap.functions.getAmountsOut(
        test_amount,
        [USDC, WMATIC]
    ).call()
    qs_wmatic_after = qs_amounts_after[1]
    qs_price_after = (test_amount / 10**6) / (qs_wmatic_after / 10**18)
    print(f"   QuickSwap:   1000 USDC → {qs_wmatic_after / 10**18:.4f} WMATIC")
    print(f"                Price: ${qs_price_after:.4f} per WMATIC")
except Exception as e:
    print(f"   ⚠️  QuickSwap quote failed: {e}")
    qs_wmatic_after = qs_wmatic_out
    qs_price_after = qs_price

# Step 4: Calculate arbitrage opportunity
print("\n4️⃣  Calculating arbitrage opportunity...")

if v3_wmatic_after > 0 and qs_wmatic_after > 0:
    # Arbitrage direction: Buy where it's cheaper, sell where it's more expensive

    if qs_wmatic_after > v3_wmatic_after:
        # WMATIC is cheaper on V3, more expensive on QuickSwap
        # Strategy: Buy WMATIC on V3, sell on QuickSwap
        direction = "V3 → QuickSwap"
        buy_dex = "Uniswap V3"
        sell_dex = "QuickSwap"
        wmatic_received = v3_wmatic_after  # Buy on V3

        # Get sell quote on QuickSwap (WMATIC → USDC)
        try:
            sell_amounts = quickswap.functions.getAmountsOut(
                wmatic_received,
                [WMATIC, USDC]
            ).call()
            usdc_received = sell_amounts[1]
        except Exception as e:
            print(f"   ⚠️  Could not get sell quote: {e}")
            usdc_received = 0

    else:
        # WMATIC is cheaper on QuickSwap, more expensive on V3
        # Strategy: Buy WMATIC on QuickSwap, sell on V3
        direction = "QuickSwap → V3"
        buy_dex = "QuickSwap"
        sell_dex = "Uniswap V3"
        wmatic_received = qs_wmatic_after  # Buy on QuickSwap

        # Get sell quote on V3 (WMATIC → USDC)
        try:
            sell_quote = uniswap_quoter.functions.quoteExactInputSingle(
                WMATIC,
                USDC,
                500,
                wmatic_received,
                0
            ).call()
            usdc_received = sell_quote[0]
        except Exception as e:
            print(f"   ⚠️  Could not get sell quote: {e}")
            usdc_received = 0

    if usdc_received > 0:
        # Calculate profit
        profit_usdc = (usdc_received - test_amount) / 10**6
        profit_pct = (usdc_received - test_amount) / test_amount * 100

        # Calculate with Aave flash loan fee (0.05%)
        flash_loan_fee = test_amount * 5 // 10000  # 0.05% = 5 bps
        net_profit_usdc = (usdc_received - test_amount - flash_loan_fee) / 10**6

        print(f"\n   🎯 ARBITRAGE OPPORTUNITY FOUND!")
        print(f"   {'='*60}")
        print(f"   Direction: {direction}")
        print(f"   ")
        print(f"   Step 1: Buy {wmatic_received / 10**18:.4f} WMATIC on {buy_dex}")
        print(f"           Cost: 1000.00 USDC (flash loan)")
        print(f"   ")
        print(f"   Step 2: Sell {wmatic_received / 10**18:.4f} WMATIC on {sell_dex}")
        print(f"           Receive: {usdc_received / 10**6:.2f} USDC")
        print(f"   ")
        print(f"   Gross Profit: ${profit_usdc:.2f} ({profit_pct:.2f}%)")
        print(f"   Flash Loan Fee: ${flash_loan_fee / 10**6:.2f}")
        print(f"   ")
        print(f"   💰 NET PROFIT: ${net_profit_usdc:.2f} USDC")
        print(f"   {'='*60}")

        if net_profit_usdc > 1:
            print(f"\n   ✅ PROFITABLE! Net profit > $1")
            print(f"\n   🚀 Ready for bot execution test!")
        else:
            print(f"\n   ⚠️  Profit too small (${net_profit_usdc:.2f})")
            print(f"      May need larger manipulation")
    else:
        print(f"\n   ❌ Could not calculate arbitrage")

print(f"\n{'='*80}")
print(f"Arbitrage Opportunity Created!")
print(f"{'='*80}")
print(f"\nNext Steps:")
print(f"1. Run the bot scanner to detect this opportunity")
print(f"2. Execute the arbitrage via FlashLoanArbitrageV2 contract")
print(f"3. Verify profit was captured")
