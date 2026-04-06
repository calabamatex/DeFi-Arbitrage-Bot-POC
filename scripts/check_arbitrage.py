#!/usr/bin/env python3
"""Check the arbitrage opportunity we created"""

from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

web3 = Web3(Web3.HTTPProvider('http://localhost:8545'))
web3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

# Addresses
USDC = '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174'
WMATIC = '0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270'
QUICKSWAP = '0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff'

qs_router_abi = [
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

quickswap = web3.eth.contract(address=QUICKSWAP, abi=qs_router_abi)

print('='*80)
print('Arbitrage Opportunity Analysis')
print('='*80)

# The manipulation made WMATIC expensive on QuickSwap
# Normal price: ~$0.13 per WMATIC
# After manipulation: ~$0.22 per WMATIC

# This means selling WMATIC on QuickSwap is profitable
# We need to BUY WMATIC somewhere else cheap, then SELL on QuickSwap

print('\nQuickSwap Prices (After Manipulation):')
print('-'*80)

# Check how much USDC we get for selling WMATIC
test_wmatic_amounts = [1000, 5000, 10000, 20000, 50000]

for wmatic_amt in test_wmatic_amounts:
    wmatic_wei = int(wmatic_amt * 10**18)
    try:
        amounts = quickswap.functions.getAmountsOut(wmatic_wei, [WMATIC, USDC]).call()
        usdc_out = amounts[1]
        price_per_wmatic = usdc_out / wmatic_amt / 10**12
        print(f'Sell {wmatic_amt:>6,} WMATIC → Get {usdc_out / 10**6:>10,.2f} USDC (Price: ${price_per_wmatic:.4f}/WMATIC)')
    except Exception as e:
        print(f'{wmatic_amt} WMATIC: Failed')

print('\n' + '='*80)
print('ARBITRAGE STRATEGY:')
print('='*80)
print('Since QuickSwap has inflated WMATIC prices:')
print('1. Buy WMATIC on Uniswap V3 at normal price (~7600 WMATIC for 1000 USDC)')
print('2. Sell that WMATIC on QuickSwap at inflated price')
print('3. Profit = Difference')
print()
print('Problem: We need to verify Uniswap V3 still has normal prices')
print('(V3 quoter was failing, but the pool should work)')
