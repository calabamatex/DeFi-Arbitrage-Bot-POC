#!/usr/bin/env python3
"""Test live opportunity detection with detailed output"""

import os
import sys
from web3 import Web3
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, os.path.dirname(__file__))

load_dotenv()

from src.opportunity_detector import OpportunityDetector

# Initialize
web3 = Web3(Web3.HTTPProvider('http://localhost:8545'))
detector = OpportunityDetector(
    web3=web3,
    min_profit_usd=0.01,  # Very low threshold to see any price differences
    max_gas_price_gwei=100,
    check_interval=5
)

print("="*60)
print("Testing Price Quotes for USDC→WMATIC")
print("="*60)

usdc = os.getenv('USDC_ADDRESS')
wmatic = os.getenv('WMATIC_ADDRESS')
amount = 1000 * 10**6  # 1000 USDC

# Get V3 quotes for all fee tiers
print("\nUniswap V3 Quotes (1000 USDC → WMATIC):")
for fee in [500, 3000, 10000]:
    quote = detector.get_v3_quote(usdc, wmatic, amount, fee)
    if quote:
        print(f"  Fee {fee/10000:.2f}%: {quote / 10**18:.6f} WMATIC")
    else:
        print(f"  Fee {fee/10000:.2f}%: ❌ Failed")

# Get V2 quote
print("\nQuickSwap (V2) Quote (1000 USDC → WMATIC):")
v2_quote = detector.get_v2_quote(usdc, wmatic, amount)
if v2_quote:
    print(f"  {v2_quote / 10**18:.6f} WMATIC")
else:
    print("  ❌ Failed")

# Calculate price difference
if v2_quote:
    v3_best = detector.get_v3_quote(usdc, wmatic, amount, 500)  # Best V3 rate (lowest fee)
    if v3_best:
        diff = abs(v3_best - v2_quote)
        diff_pct = (diff / v3_best) * 100
        print(f"\nPrice Difference:")
        print(f"  V3 (0.05%): {v3_best / 10**18:.6f} WMATIC")
        print(f"  V2:         {v2_quote / 10**18:.6f} WMATIC")
        print(f"  Difference: {diff / 10**18:.6f} WMATIC ({diff_pct:.4f}%)")

# Now test complete arbitrage detection
print("\n" + "="*60)
print("Running Complete Arbitrage Scan")
print("="*60)

opps = detector.scan_opportunities()
print(f"\n✅ Scan complete: Found {len(opps)} opportunities above $0.01 threshold\n")

if opps:
    for i, opp in enumerate(opps[:5], 1):
        print(f"Opportunity #{i}:")
        print(f"  Direction: {opp['direction']}")
        print(f"  Pair: {opp['token_in_symbol']} → {opp['token_out_symbol']}")
        print(f"  Amount: {opp['amount_in'] / 10**6:.2f} USDC")
        print(f"  Net Profit: ${opp['net_profit'] / 10**6:.4f}")
        print(f"  V3 Fee Tier: {opp['v3_fee']/10000:.2f}%")
        print()
else:
    print("ℹ️  No profitable opportunities found")
    print("   This is normal for mainnet fork - arbitrage is very rare!")
    print("   Real traders continuously arbitrage away price differences.")

print("="*60)
print("Test Complete")
print("="*60)
