#!/usr/bin/env python3
"""Analyze the price spread between V3 and QuickSwap"""

from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

web3 = Web3(Web3.HTTPProvider('http://localhost:8545'))
web3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

USDC = '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174'
WMATIC = '0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270'
QUICKSWAP = '0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff'

qs_abi = [
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

qs = web3.eth.contract(address=QUICKSWAP, abi=qs_abi)

print('='*80)
print('Price Analysis After 100k USDC Buy on QuickSwap')
print('='*80)

# Current QuickSwap state
test_usdc = 1000 * 10**6

print('\n1. QuickSwap Current Prices:')
print('-'*80)

# Buy WMATIC with USDC
amounts_buy = qs.functions.getAmountsOut(test_usdc, [USDC, WMATIC]).call()
wmatic_from_usdc = amounts_buy[1]
buy_price = test_usdc / wmatic_from_usdc * 10**12  # Price in USDC per WMATIC

print(f'   Buy WMATIC:  1000 USDC → {wmatic_from_usdc / 10**18:,.2f} WMATIC')
print(f'                Price: ${buy_price:.4f} per WMATIC')

# Sell WMATIC for USDC
test_wmatic = int(10000 * 10**18)
amounts_sell = qs.functions.getAmountsOut(test_wmatic, [WMATIC, USDC]).call()
usdc_from_wmatic = amounts_sell[1]
sell_price = usdc_from_wmatic / test_wmatic * 10**12  # Price in USDC per WMATIC

print(f'   Sell WMATIC: 10000 WMATIC → {usdc_from_wmatic / 10**6:,.2f} USDC')
print(f'                Price: ${sell_price:.4f} per WMATIC')

print(f'\n   Spread: {abs(buy_price - sell_price) / buy_price * 100:.2f}% (expected due to liquidity)')

# The insight: After buying 100k USDC of WMATIC:
# - QuickSwap pool now has MORE USDC, LESS WMATIC
# - So WMATIC is more expensive (harder to buy)
# - Perfect for arbitrage: Buy WMATIC elsewhere cheap, sell on QuickSwap expensive

print('\n2. Arbitrage Opportunity:')
print('-'*80)

# If we could get WMATIC from Uniswap V3 at normal price (~$0.13)
# And sell on QuickSwap at current price
assumed_v3_price = 0.13  # Normal price
qs_sell_price = sell_price

if qs_sell_price > assumed_v3_price:
    profit_per_wmatic = qs_sell_price - assumed_v3_price
    profit_pct = profit_per_wmatic / assumed_v3_price * 100

    # For 10000 WMATIC
    total_profit = profit_per_wmatic * 10000

    print(f'   Strategy: Buy WMATIC on Uniswap V3, Sell on QuickSwap')
    print(f'   ')
    print(f'   V3 Price (normal):     ${assumed_v3_price:.4f} per WMATIC')
    print(f'   QuickSwap Price:       ${qs_sell_price:.4f} per WMATIC')
    print(f'   Profit per WMATIC:     ${profit_per_wmatic:.4f}')
    print(f'   Profit %:              {profit_pct:.2f}%')
    print(f'   ')
    print(f'   For 10,000 WMATIC trade:')
    print(f'   Cost on V3:            ${assumed_v3_price * 10000:,.2f}')
    print(f'   Sell on QS:            ${usdc_from_wmatic / 10**6:,.2f}')
    print(f'   Gross Profit:          ${(usdc_from_wmatic / 10**6) - (assumed_v3_price * 10000):,.2f}')
else:
    print(f'   No opportunity - QuickSwap price too low')

print('\n3. Next Steps:')
print('-'*80)
print('   Need to execute actual arbitrage through our contract:')
print('   1. Flash loan USDC from Aave')
print('   2. Buy WMATIC on Uniswap V3')
print('   3. Sell WMATIC on QuickSwap')
print('   4. Repay flash loan')
print('   5. Keep profit')
