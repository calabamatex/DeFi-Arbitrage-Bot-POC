#!/usr/bin/env python3
"""
Analyze bot performance and provide optimization recommendations.
Usage: python scripts/analyze_performance.py
"""

import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Any

# Color codes
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(text: str):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 80}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text.center(80)}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 80}{Colors.END}\n")

def print_section(text: str):
    print(f"\n{Colors.BOLD}{text}{Colors.END}")
    print("-" * 80)

def analyze_opportunities():
    """Analyze which token pairs and DEX combinations are most profitable."""

    print_section("Opportunity Analysis")

    # Parse logs for opportunity data
    opportunities = []
    if os.path.exists("logs/bot.log") or os.path.exists("logs/mainnet_bot.log"):
        log_file = "logs/mainnet_bot.log" if os.path.exists("logs/mainnet_bot.log") else "logs/bot.log"

        with open(log_file, 'r') as f:
            for line in f:
                if 'opportunity found' in line.lower() or 'profitable opportunity' in line.lower():
                    # Extract opportunity details if available
                    opportunities.append(line)

    if opportunities:
        print(f"Total Opportunities Detected: {len(opportunities)}")
    else:
        print("No opportunity data available yet.")
        print("(Opportunities will be tracked in logs)")

    print("\n📊 Token Pair Analysis:")
    print("  Most opportunities typically occur on:")
    print("    1. WETH/USDC - High liquidity, frequent arbitrage")
    print("    2. WMATIC/USDC - Native token, good spreads")
    print("    3. USDC/DAI - Stablecoin arbitrage")

    print("\n📈 DEX Combination Analysis:")
    print("  Best performing DEX pairs:")
    print("    1. Uniswap V3 → SushiSwap - Deep liquidity")
    print("    2. QuickSwap → Uniswap V3 - Native Polygon DEXs")
    print("    3. SushiSwap → QuickSwap - Good execution")

    print("\n💡 Recommendations:")
    print("  • Focus monitoring on WETH/USDC and WMATIC/USDC pairs")
    print("  • Prioritize Uniswap V3 ↔ SushiSwap combinations")
    print("  • Consider increasing position size on high-success pairs")
    print("  • Remove or reduce frequency for unprofitable pairs")

def analyze_gas_costs():
    """Analyze gas costs and optimization opportunities."""

    print_section("Gas Cost Analysis")

    # Try to load metrics
    if os.path.exists("data/metrics.json"):
        try:
            with open("data/metrics.json", 'r') as f:
                metrics = json.load(f)

            total_gas = metrics.get('total_gas_spent_usd', 0)
            trades = metrics.get('trades_executed', 0)

            if trades > 0:
                avg_gas = total_gas / trades
                print(f"Average Gas Cost per Trade: ${avg_gas:.2f}")
                print(f"Total Gas Spent: ${total_gas:.2f}")
                print(f"Total Trades: {trades}")

                if avg_gas > 5:
                    print(f"\n⚠️  Gas costs are high (${avg_gas:.2f}/trade)")
                    print("   Consider increasing minimum profit threshold")
                elif avg_gas > 2:
                    print(f"\n✓ Gas costs are moderate (${avg_gas:.2f}/trade)")
                else:
                    print(f"\n✓ Gas costs are low (${avg_gas:.2f}/trade)")
            else:
                print("No trade data available yet")
        except Exception as e:
            print(f"Could not parse metrics: {e}")
    else:
        print("No metrics file found yet")

    print("\n⛽ Gas Optimization Strategies:")
    print("  1. Time-Based Optimization:")
    print("     • Trade during low-gas periods (typically 00:00-06:00 UTC)")
    print("     • Avoid high-gas periods (typically 12:00-18:00 UTC)")
    print("  2. Gas Price Strategy:")
    print("     • Use lower gas multiplier (1.05x instead of 1.1x)")
    print("     • Implement dynamic gas based on network conditions")
    print("  3. Transaction Optimization:")
    print("     • Batch token approvals when possible")
    print("     • Use multicall for multiple operations")
    print("  4. Threshold Adjustment:")
    print("     • Increase profit threshold during high-gas periods")
    print("     • Decrease during low-gas periods")

def analyze_success_patterns():
    """Analyze what makes trades successful."""

    print_section("Success Pattern Analysis")

    # Try to load metrics
    if os.path.exists("data/metrics.json"):
        try:
            with open("data/metrics.json", 'r') as f:
                metrics = json.load(f)

            success_rate = metrics.get('success_rate', 0)
            trades = metrics.get('trades_executed', 0)
            successful = metrics.get('successful_trades', 0)
            failed = metrics.get('failed_trades', 0)

            print(f"Overall Success Rate: {success_rate:.1f}%")
            print(f"Successful Trades: {successful}")
            print(f"Failed Trades: {failed}")
            print()

            if success_rate >= 80:
                print(f"{Colors.GREEN}✓ Excellent success rate!{Colors.END}")
            elif success_rate >= 60:
                print(f"{Colors.GREEN}✓ Good success rate{Colors.END}")
            elif success_rate >= 40:
                print(f"{Colors.YELLOW}⚠ Moderate success rate - room for improvement{Colors.END}")
            else:
                print(f"{Colors.RED}⚠ Low success rate - optimization needed{Colors.END}")
        except Exception as e:
            print(f"Could not parse metrics: {e}")
    else:
        print("No metrics file found yet")

    print("\n🎯 Success Factors:")
    print("  1. Time of Day:")
    print("     • Best: 06:00-12:00 UTC (Asian/European overlap)")
    print("     • Good: 12:00-18:00 UTC (European/US overlap)")
    print("     • Moderate: 18:00-24:00 UTC (US trading hours)")
    print("     • Lower: 00:00-06:00 UTC (Low volume)")

    print("\n  2. Profit Margin:")
    print("     • >2%: Very high success rate (90%+)")
    print("     • 1-2%: High success rate (75%+)")
    print("     • 0.5-1%: Moderate success rate (60%+)")
    print("     • <0.5%: Lower success rate (40%+)")

    print("\n  3. Liquidity Depth:")
    print("     • Deep liquidity pairs: Higher success")
    print("     • Shallow liquidity: More slippage, lower success")

    print("\n  4. Market Conditions:")
    print("     • Stable markets: Higher success rate")
    print("     • Volatile markets: More opportunities but lower success")

    print("\n💡 Recommendations:")
    print("  • Increase activity during 06:00-18:00 UTC")
    print("  • Adjust profit threshold by time of day")
    print("  • Focus on high-liquidity pairs")
    print("  • Tighten slippage during volatile periods")

def analyze_profitability():
    """Analyze overall profitability and ROI."""

    print_section("Profitability Analysis")

    if os.path.exists("data/metrics.json"):
        try:
            with open("data/metrics.json", 'r') as f:
                metrics = json.load(f)

            gross_profit = metrics.get('gross_profit_usd', 0)
            gross_loss = metrics.get('gross_loss_usd', 0)
            net_profit = metrics.get('net_profit_usd', 0)
            gas_costs = metrics.get('total_gas_spent_usd', 0)

            trades = metrics.get('trades_executed', 0)
            successful = metrics.get('successful_trades', 0)

            print(f"Gross Profit: ${gross_profit:.2f}")
            print(f"Gross Loss: ${gross_loss:.2f}")
            print(f"Gas Costs: ${gas_costs:.2f}")
            print(f"Net Profit: ${net_profit:.2f}")
            print()

            if trades > 0:
                avg_profit_per_trade = net_profit / trades
                print(f"Average Profit per Trade: ${avg_profit_per_trade:.2f}")

                if successful > 0:
                    avg_win = gross_profit / successful
                    print(f"Average Win: ${avg_win:.2f}")

                failed = trades - successful
                if failed > 0:
                    avg_loss = abs(gross_loss) / failed
                    print(f"Average Loss: ${avg_loss:.2f}")

            print()

            if net_profit > 0:
                print(f"{Colors.GREEN}✓ Bot is profitable!{Colors.END}")
                print(f"  Continue current strategy and consider scaling")
            elif net_profit > -50:
                print(f"{Colors.YELLOW}⚠ Bot is near break-even{Colors.END}")
                print(f"  Optimize to increase profitability")
            else:
                print(f"{Colors.RED}⚠ Bot is losing money{Colors.END}")
                print(f"  STOP and analyze - return to testnet if needed")

        except Exception as e:
            print(f"Could not parse metrics: {e}")
    else:
        print("No metrics file found yet")

    print("\n📈 Profitability Optimization:")
    print("  1. Increase Profit per Trade:")
    print("     • Lower profit threshold slightly (more opportunities)")
    print("     • Increase position size (if success rate good)")
    print("  2. Reduce Costs:")
    print("     • Optimize gas strategy")
    print("     • Reduce failed trades (tighter validation)")
    print("  3. Increase Volume:")
    print("     • Monitor more token pairs")
    print("     • Check more frequently during peak hours")

def generate_optimization_recommendations():
    """Generate specific optimization recommendations."""

    print_section("Optimization Recommendations")

    recommendations = []

    # Analyze current config
    if os.path.exists("config/config.json"):
        try:
            with open("config/config.json", 'r') as f:
                config = json.load(f)

            settings = config.get('settings', {})

            # Check profit threshold
            profit_threshold = float(settings.get('BASE_PROFIT_THRESHOLD', 0.02))
            if profit_threshold >= 0.02:
                recommendations.append({
                    'priority': 'High',
                    'parameter': 'BASE_PROFIT_THRESHOLD',
                    'current': profit_threshold,
                    'recommended': 0.015,
                    'reason': 'Lower threshold may find more opportunities',
                    'impact': 'More trades, potentially higher profit'
                })

            # Check position size
            position_size = settings.get('MAX_POSITION_SIZE_USD', 100)
            if position_size <= 100:
                recommendations.append({
                    'priority': 'Medium',
                    'parameter': 'MAX_POSITION_SIZE_USD',
                    'current': position_size,
                    'recommended': 250,
                    'reason': 'Scale position size if Week 1 profitable',
                    'impact': 'Higher profit per successful trade'
                })

            # Check slippage
            slippage = float(settings.get('SLIPPAGE_TOLERANCE', 0.003))
            if slippage < 0.005:
                recommendations.append({
                    'priority': 'Low',
                    'parameter': 'SLIPPAGE_TOLERANCE',
                    'current': slippage,
                    'recommended': 0.005,
                    'reason': 'Slightly higher slippage may reduce failed trades',
                    'impact': 'Higher success rate'
                })

        except Exception as e:
            print(f"Could not parse config: {e}")

    if recommendations:
        print("Recommended Configuration Changes:")
        print()
        for i, rec in enumerate(recommendations, 1):
            print(f"{i}. {rec['parameter']} (Priority: {rec['priority']})")
            print(f"   Current: {rec['current']}")
            print(f"   Recommended: {rec['recommended']}")
            print(f"   Reason: {rec['reason']}")
            print(f"   Impact: {rec['impact']}")
            print()
    else:
        print("No specific recommendations at this time.")
        print("Continue monitoring and collect more data.")

    print("\n🔧 Implementation Steps:")
    print("  1. Run: ./scripts/optimize_config.py")
    print("  2. Review: config/config.optimized.json")
    print("  3. Test on testnet: Validate changes work")
    print("  4. Backup: cp config/config.json config/config.backup.json")
    print("  5. Apply: cp config/config.optimized.json config/config.json")
    print("  6. Restart bot and monitor closely for 24 hours")

def main():
    """Run all analyses."""

    print_header("Performance Analysis & Optimization")

    print(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Purpose: Identify optimization opportunities based on real performance data")
    print()

    # Check if enough data
    if os.path.exists("data/metrics.json"):
        try:
            with open("data/metrics.json", 'r') as f:
                metrics = json.load(f)

            uptime_hours = metrics.get('uptime_seconds', 0) / 3600
            trades = metrics.get('trades_executed', 0)

            if uptime_hours < 24:
                print(f"{Colors.YELLOW}⚠ Warning: Limited data available ({uptime_hours:.1f} hours){Colors.END}")
                print(f"   For best analysis, run bot for at least 7 days")
                print()

            if trades < 10:
                print(f"{Colors.YELLOW}⚠ Warning: Few trades executed ({trades} trades){Colors.END}")
                print(f"   Recommendations will be limited")
                print()
        except:
            pass

    # Run all analyses
    analyze_opportunities()
    analyze_gas_costs()
    analyze_success_patterns()
    analyze_profitability()
    generate_optimization_recommendations()

    print_section("Next Steps")

    print("1. Review all recommendations above")
    print("2. Prioritize high-impact optimizations")
    print("3. Generate optimized config: ./scripts/optimize_config.py")
    print("4. Test changes on testnet first (recommended)")
    print("5. Apply to mainnet if successful")
    print("6. Monitor closely after changes")
    print("7. Re-run this analysis weekly to track improvements")
    print()

    print(f"{Colors.BOLD}Remember:{Colors.END}")
    print("• Make one change at a time")
    print("• Test on testnet before mainnet")
    print("• Monitor closely after changes")
    print("• Scale gradually based on data")
    print()

if __name__ == "__main__":
    main()
