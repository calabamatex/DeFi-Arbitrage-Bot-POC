#!/usr/bin/env python3
"""
Generate optimized configuration based on historical performance.
Usage: python scripts/optimize_config.py
"""

import json
import os
import sys
from datetime import datetime

def load_current_config():
    """Load current configuration."""
    if not os.path.exists('config/config.json'):
        print("Error: config/config.json not found")
        sys.exit(1)

    with open('config/config.json', 'r') as f:
        return json.load(f)

def load_metrics():
    """Load performance metrics if available."""
    if os.path.exists('data/metrics.json'):
        try:
            with open('data/metrics.json', 'r') as f:
                return json.load(f)
        except:
            return None
    return None

def analyze_and_optimize(config, metrics):
    """Analyze performance and generate optimization recommendations."""

    settings = config.get('settings', {})
    optimizations = {}

    # Analyze profit threshold
    current_threshold = float(settings.get('BASE_PROFIT_THRESHOLD', '0.02'))

    if metrics:
        success_rate = metrics.get('success_rate', 0)
        trades = metrics.get('trades_executed', 0)
        net_profit = metrics.get('net_profit_usd', 0)
        uptime_days = metrics.get('uptime_seconds', 0) / 86400

        # Threshold optimization
        if uptime_days >= 7 and trades >= 10:
            if success_rate >= 75 and net_profit > 100:
                # High success rate and profitable - can be more aggressive
                recommended_threshold = max(current_threshold * 0.75, 0.005)
                optimizations['BASE_PROFIT_THRESHOLD'] = {
                    'current': current_threshold,
                    'recommended': round(recommended_threshold, 3),
                    'reason': f'High success rate ({success_rate:.1f}%) suggests lower threshold acceptable',
                    'impact': 'More opportunities, potentially higher profit'
                }
            elif success_rate >= 60 and net_profit > 50:
                # Moderate success - slight optimization
                recommended_threshold = max(current_threshold * 0.85, 0.008)
                optimizations['BASE_PROFIT_THRESHOLD'] = {
                    'current': current_threshold,
                    'recommended': round(recommended_threshold, 3),
                    'reason': f'Moderate success rate ({success_rate:.1f}%) allows slight optimization',
                    'impact': 'Moderately more opportunities'
                }
            elif success_rate < 50:
                # Low success rate - increase threshold
                recommended_threshold = current_threshold * 1.2
                optimizations['BASE_PROFIT_THRESHOLD'] = {
                    'current': current_threshold,
                    'recommended': round(recommended_threshold, 3),
                    'reason': f'Low success rate ({success_rate:.1f}%) - increase threshold',
                    'impact': 'Fewer but more reliable opportunities'
                }
        else:
            # Not enough data - conservative recommendation
            if current_threshold > 0.015:
                optimizations['BASE_PROFIT_THRESHOLD'] = {
                    'current': current_threshold,
                    'recommended': 0.015,
                    'reason': 'After Week 1, can moderately lower threshold',
                    'impact': 'More opportunities'
                }

        # Position size optimization
        current_position = settings.get('MAX_POSITION_SIZE_USD', 100)

        if uptime_days >= 7 and net_profit > 50:
            if current_position <= 100:
                optimizations['MAX_POSITION_SIZE_USD'] = {
                    'current': current_position,
                    'recommended': 250,
                    'reason': 'Week 1 profitable - ready for first scale-up',
                    'impact': 'Higher profit per trade'
                }
            elif current_position == 250 and uptime_days >= 14 and net_profit > 150:
                optimizations['MAX_POSITION_SIZE_USD'] = {
                    'current': current_position,
                    'recommended': 500,
                    'reason': 'Week 2 profitable - ready for second scale-up',
                    'impact': 'Significantly higher profit per trade'
                }
            elif current_position == 500 and uptime_days >= 21 and net_profit > 300:
                optimizations['MAX_POSITION_SIZE_USD'] = {
                    'current': current_position,
                    'recommended': 1000,
                    'reason': 'Week 3 profitable - ready for third scale-up',
                    'impact': 'Maximum profit per trade'
                }

        # Slippage optimization
        current_slippage = float(settings.get('SLIPPAGE_TOLERANCE', '0.003'))
        failed_trades = metrics.get('failed_trades', 0)

        if trades > 10 and failed_trades > trades * 0.3:
            # High failure rate - increase slippage
            optimizations['SLIPPAGE_TOLERANCE'] = {
                'current': current_slippage,
                'recommended': min(current_slippage * 1.5, 0.01),
                'reason': f'High failure rate ({failed_trades}/{trades}) - increase slippage tolerance',
                'impact': 'Fewer failed trades'
            }
        elif trades > 10 and failed_trades < trades * 0.1:
            # Low failure rate - can tighten slippage
            optimizations['SLIPPAGE_TOLERANCE'] = {
                'current': current_slippage,
                'recommended': max(current_slippage * 0.9, 0.002),
                'reason': f'Low failure rate ({failed_trades}/{trades}) - can tighten slippage',
                'impact': 'Higher profit per trade'
            }

        # Loss limit optimization (scale with position size)
        current_loss_limit = settings.get('DAILY_LOSS_LIMIT_USD', 500)
        recommended_position = optimizations.get('MAX_POSITION_SIZE_USD', {}).get('recommended', current_position)

        if recommended_position > current_position:
            # Scale loss limit proportionally
            ratio = recommended_position / current_position
            recommended_loss_limit = int(current_loss_limit * ratio * 0.75)  # 75% of proportional
            optimizations['DAILY_LOSS_LIMIT_USD'] = {
                'current': current_loss_limit,
                'recommended': recommended_loss_limit,
                'reason': 'Scale loss limit with position size increase',
                'impact': 'Proportional risk management'
            }

    else:
        # No metrics - Week 1 default optimizations
        if current_threshold > 0.015:
            optimizations['BASE_PROFIT_THRESHOLD'] = {
                'current': current_threshold,
                'recommended': 0.015,
                'reason': 'Week 1 complete - moderate threshold reduction',
                'impact': 'More opportunities'
            }

        current_position = settings.get('MAX_POSITION_SIZE_USD', 100)
        if current_position <= 100:
            optimizations['MAX_POSITION_SIZE_USD'] = {
                'current': current_position,
                'recommended': 250,
                'reason': 'Assuming Week 1 successful - first scale-up',
                'impact': 'Higher profit per trade'
            }

    return optimizations

def create_optimized_config(config, optimizations):
    """Create new optimized configuration."""

    optimized = config.copy()

    # Apply optimizations
    for param, opt in optimizations.items():
        if param in ['BASE_PROFIT_THRESHOLD', 'SLIPPAGE_TOLERANCE']:
            optimized['settings'][param] = str(opt['recommended'])
        else:
            optimized['settings'][param] = opt['recommended']

    # Adjust related settings
    if 'MAX_POSITION_SIZE_USD' in optimizations:
        # Adjust weekly loss limit too
        position_size = optimizations['MAX_POSITION_SIZE_USD']['recommended']
        optimized['settings']['WEEKLY_LOSS_LIMIT_USD'] = int(position_size * 25)  # 25x position size

    return optimized

def main():
    """Generate optimized configuration."""

    print("=" * 80)
    print("Configuration Optimization Tool")
    print("=" * 80)
    print()

    # Load current config
    print("Loading current configuration...")
    config = load_current_config()
    print("✓ Configuration loaded")
    print()

    # Load metrics
    print("Loading performance metrics...")
    metrics = load_metrics()
    if metrics:
        uptime = metrics.get('uptime_seconds', 0) / 3600
        trades = metrics.get('trades_executed', 0)
        profit = metrics.get('net_profit_usd', 0)
        print(f"✓ Metrics loaded ({uptime:.1f} hours, {trades} trades, ${profit:.2f} profit)")
    else:
        print("⚠ No metrics found - using defaults")
    print()

    # Analyze and optimize
    print("Analyzing performance...")
    optimizations = analyze_and_optimize(config, metrics)

    if not optimizations:
        print("✓ Current configuration is optimal")
        print("  No changes recommended at this time")
        print()
        print("Reasons for no optimization:")
        print("  • Insufficient data (need 7+ days)")
        print("  • Current settings already optimal")
        print("  • Recent changes need more time to evaluate")
        print()
        return

    print(f"✓ {len(optimizations)} optimization(s) identified")
    print()

    # Display optimizations
    print("=" * 80)
    print("Recommended Optimizations")
    print("=" * 80)
    print()

    for i, (param, opt) in enumerate(optimizations.items(), 1):
        print(f"{i}. {param}")
        print(f"   Current:     {opt['current']}")
        print(f"   Recommended: {opt['recommended']}")
        print(f"   Reason:      {opt['reason']}")
        print(f"   Impact:      {opt['impact']}")
        print()

    # Create optimized config
    print("=" * 80)
    print("Creating Optimized Configuration")
    print("=" * 80)
    print()

    optimized_config = create_optimized_config(config, optimizations)

    # Save optimized config
    output_file = 'config/config.optimized.json'
    with open(output_file, 'w') as f:
        json.dump(optimized_config, f, indent=2)

    print(f"✓ Optimized configuration saved to: {output_file}")
    print()

    # Display comparison
    print("=" * 80)
    print("Configuration Comparison")
    print("=" * 80)
    print()

    print("Current Settings:")
    for param in optimizations.keys():
        value = config['settings'].get(param)
        print(f"  {param}: {value}")

    print()
    print("Optimized Settings:")
    for param in optimizations.keys():
        value = optimized_config['settings'].get(param)
        print(f"  {param}: {value}")

    print()
    print("=" * 80)
    print("How to Apply Optimizations")
    print("=" * 80)
    print()

    print("⚠️  IMPORTANT: Test on testnet first (recommended)")
    print()

    print("Steps to apply:")
    print("  1. Review optimized config:")
    print(f"     cat {output_file}")
    print()

    print("  2. OPTIONAL but RECOMMENDED - Test on testnet:")
    print("     a. Copy to testnet:")
    print(f"        scp {output_file} testnet:~/bot/config/config.json")
    print("     b. Restart testnet bot")
    print("     c. Monitor for 24 hours")
    print("     d. Verify improvements")
    print()

    print("  3. Backup current config:")
    print("     cp config/config.json config/config.backup.$(date +%Y%m%d).json")
    print()

    print("  4. Apply optimized config:")
    print(f"     cp {output_file} config/config.json")
    print()

    print("  5. Restart bot:")
    print("     kill $(cat mainnet_bot.pid)")
    print("     nohup python3 -m src.bot.main > logs/mainnet_bot.log 2>&1 &")
    print("     echo $! > mainnet_bot.pid")
    print()

    print("  6. Monitor closely for 24 hours:")
    print("     ./scripts/mainnet_health_check.sh")
    print("     ./scripts/generate_report.py data/metrics.json")
    print()

    print("  7. Rollback if issues:")
    print("     kill $(cat mainnet_bot.pid)")
    print("     cp config/config.backup.$(date +%Y%m%d).json config/config.json")
    print("     # Restart bot")
    print()

    print("=" * 80)
    print("Monitoring After Optimization")
    print("=" * 80)
    print()

    print("Monitor these metrics closely:")
    print("  • Success rate (should maintain or improve)")
    print("  • Profit per trade (should maintain or improve)")
    print("  • Error rate (should not increase)")
    print("  • Gas costs (watch ratio to profit)")
    print("  • Risk limit hits (should be rare)")
    print()

    print("Run comparison after 24 hours:")
    print("  ./scripts/analyze_performance.py")
    print()

    print("=" * 80)
    print()

if __name__ == "__main__":
    main()
