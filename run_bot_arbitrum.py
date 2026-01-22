#!/usr/bin/env python3
"""Run the Flash Loan Arbitrage Bot on Arbitrum"""
import os
import sys
import time
import argparse
from dotenv import load_dotenv
from web3 import Web3

# Load Arbitrum configuration
load_dotenv('.env.arbitrum')

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from opportunity_detector import OpportunityDetector

def main():
    parser = argparse.ArgumentParser(description='Run Arbitrage Bot on Arbitrum')
    parser.add_argument('--test', action='store_true', help='Run 5-minute test')
    args = parser.parse_args()

    print("=" * 80)
    print("FLASH LOAN ARBITRAGE BOT - ARBITRUM")
    print("=" * 80)

    # Connect to Arbitrum
    ARBITRUM_RPC = os.getenv('ARBITRUM_RPC_URL')

    if 'YOUR_ALCHEMY_KEY_HERE' in ARBITRUM_RPC:
        print("\n❌ ERROR: Set your Alchemy API key in .env.arbitrum")
        exit(1)

    web3 = Web3(Web3.HTTPProvider(ARBITRUM_RPC))

    if not web3.is_connected():
        print(f"\n❌ Failed to connect to Arbitrum")
        exit(1)

    chain_id = web3.eth.chain_id
    print(f"\n✅ Connected to Arbitrum (Chain ID: {chain_id})")

    # Get bot configuration
    min_profit = float(os.getenv("MIN_PROFIT_USD", "5.0"))
    max_gas_price = int(os.getenv("MAX_GAS_PRICE_GWEI", "2"))
    check_interval = int(os.getenv("CHECK_INTERVAL", "3"))
    min_flash_loan = int(os.getenv("MIN_FLASH_LOAN_USD", "500")) * 10**6
    max_flash_loan = int(os.getenv("MAX_FLASH_LOAN_USD", "100000")) * 10**6
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"

    print(f"\n⚙️  Configuration:")
    print(f"   Network: Arbitrum Mainnet")
    print(f"   Min Profit: ${min_profit}")
    print(f"   Max Gas Price: {max_gas_price} gwei")
    print(f"   Check Interval: {check_interval}s")
    print(f"   Flash Loan Range: ${min_flash_loan/10**6:,.0f} - ${max_flash_loan/10**6:,.0f}")
    print(f"   Mode: {'DRY RUN (observation only)' if dry_run else 'LIVE EXECUTION'}")

    if not dry_run:
        print("\n⚠️  WARNING: LIVE EXECUTION MODE!")
        response = input("   Are you sure you want to execute real trades? (yes/no): ")
        if response.lower() != 'yes':
            print("   Aborted.")
            exit(0)

    # Initialize detector
    print(f"\n🔍 Initializing Opportunity Detector...")
    detector = OpportunityDetector(
        web3=web3,
        min_profit_usd=min_profit,
        max_gas_price_gwei=max_gas_price,
        check_interval=check_interval,
        min_flash_loan=min_flash_loan,
        max_flash_loan=max_flash_loan
    )
    print(f"✅ Detector initialized")
    print(f"   Trading pairs: {len(detector.trading_pairs)}")

    # Test mode
    if args.test:
        print("\n" + "=" * 80)
        print("TEST MODE - 5 MINUTE SCAN")
        print("=" * 80)
        print("\nScanning for 5 minutes...\n")

        start_time = time.time()
        scan_count = 0

        while time.time() - start_time < 300:  # 5 minutes
            print(f"🔄 Scan #{scan_count + 1}")
            opportunities = detector.scan_opportunities()

            if opportunities:
                print(f"✅ Found {len(opportunities)} opportunities!")
                for opp in opportunities:
                    profit_usd = opp['net_profit'] / 10**6
                    amount_usd = opp['amount_in'] / 10**6
                    print(f"   💰 {opp['direction']}: ${amount_usd:,.0f} → ${profit_usd:.2f} profit")
            else:
                print(f"   No opportunities found")

            scan_count += 1
            time.sleep(check_interval)

        print(f"\n✅ Test complete!")
        print(f"   Total scans: {scan_count}")
        print(f"   Duration: 5 minutes")
        return

    # Production mode
    print("\n" + "=" * 80)
    print("STARTING BOT - ARBITRUM")
    print("=" * 80)
    print(f"\n🤖 Bot running...")
    print(f"   Press Ctrl+C to stop\n")

    scan_count = 0
    opportunities_found = 0

    try:
        while True:
            scan_count += 1
            current_time = time.strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{current_time}] Scan #{scan_count} (Arbitrum)")

            opportunities = detector.scan_opportunities()

            if opportunities:
                opportunities_found += len(opportunities)
                print(f"🎯 Found {len(opportunities)} opportunities!")
                for opp in opportunities:
                    profit_usd = opp['net_profit'] / 10**6
                    amount_usd = opp['amount_in'] / 10**6
                    print(f"   💰 {opp['direction']}: ${amount_usd:,.0f} → ${profit_usd:.2f} profit")

                    if not dry_run:
                        # TODO: Execute trade
                        pass
            else:
                print(f"   ⏳ No opportunities")

            time.sleep(check_interval)

    except KeyboardInterrupt:
        print(f"\n\n⛔ Stopping bot...")
        print(f"\n📊 Session Summary:")
        print(f"   Network: Arbitrum")
        print(f"   Total scans: {scan_count}")
        print(f"   Opportunities found: {opportunities_found}")
        print(f"\n✅ Bot stopped cleanly")

if __name__ == "__main__":
    main()
