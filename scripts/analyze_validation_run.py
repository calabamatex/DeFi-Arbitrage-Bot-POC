#!/usr/bin/env python3
"""
Validation Run Analyzer
Analyzes the 48-hour testnet validation run and generates a comprehensive report.
Usage: python scripts/analyze_validation_run.py
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Any
from collections import Counter
import re

# Color codes for terminal output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(text: str):
    """Print a formatted header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 80}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text.center(80)}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 80}{Colors.END}\n")

def print_section(text: str):
    """Print a section header"""
    print(f"\n{Colors.BOLD}{text}{Colors.END}")
    print("-" * 80)

def print_pass(text: str):
    """Print a passing check"""
    print(f"{Colors.GREEN}✓{Colors.END} {text}")

def print_fail(text: str):
    """Print a failing check"""
    print(f"{Colors.RED}✗{Colors.END} {text}")

def print_warn(text: str):
    """Print a warning"""
    print(f"{Colors.YELLOW}⚠{Colors.END} {text}")

def analyze_logs(log_file: str = "logs/bot.log") -> Dict[str, Any]:
    """Analyze bot logs for errors, warnings, and key events"""

    if not os.path.exists(log_file):
        return {
            "error": f"Log file not found: {log_file}",
            "total_lines": 0,
            "errors": [],
            "warnings": [],
            "critical": [],
            "trades": 0,
            "opportunities": 0,
            "shutdowns": 0
        }

    errors = []
    warnings = []
    critical = []
    trades = 0
    opportunities = 0
    shutdowns = 0
    total_lines = 0

    with open(log_file, 'r') as f:
        for line in f:
            total_lines += 1
            line_lower = line.lower()

            # Count different log levels
            if 'critical' in line_lower:
                critical.append(line.strip())
            elif 'error' in line_lower and 'no error' not in line_lower:
                errors.append(line.strip())
            elif 'warning' in line_lower:
                warnings.append(line.strip())

            # Count events
            if 'executing trade' in line_lower or 'trade executed' in line_lower:
                trades += 1
            if 'opportunity found' in line_lower or 'profitable opportunity' in line_lower:
                opportunities += 1
            if 'emergency shutdown' in line_lower:
                shutdowns += 1

    return {
        "total_lines": total_lines,
        "errors": errors,
        "warnings": warnings,
        "critical": critical,
        "trades": trades,
        "opportunities": opportunities,
        "shutdowns": shutdowns
    }

def analyze_metrics(metrics_file: str = "data/metrics.json") -> Dict[str, Any]:
    """Analyze metrics file"""

    if not os.path.exists(metrics_file):
        return {"error": f"Metrics file not found: {metrics_file}"}

    try:
        with open(metrics_file, 'r') as f:
            metrics = json.load(f)
        return metrics
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON in metrics file: {e}"}
    except Exception as e:
        return {"error": f"Error reading metrics: {e}"}

def analyze_validation_log(log_file: str = "logs/validation_monitor.log") -> Dict[str, Any]:
    """Analyze validation monitor logs"""

    if not os.path.exists(log_file):
        return {
            "error": f"Validation log not found: {log_file}",
            "checks": 0,
            "passes": 0,
            "failures": 0
        }

    checks = 0
    passes = 0
    failures = 0

    with open(log_file, 'r') as f:
        content = f.read()
        checks = content.count("=== Validation Check at")
        passes = content.count("Status: PASS")
        failures = content.count("Status: FAIL")

    return {
        "checks": checks,
        "passes": passes,
        "failures": failures,
        "pass_rate": (passes / checks * 100) if checks > 0 else 0
    }

def analyze_alerts(alert_file: str = "data/validation_alerts.txt") -> List[str]:
    """Analyze alert file"""

    if not os.path.exists(alert_file):
        return []

    with open(alert_file, 'r') as f:
        alerts = f.readlines()

    return [alert.strip() for alert in alerts if alert.strip()]

def check_success_criteria(
    log_analysis: Dict,
    metrics: Dict,
    validation_log: Dict,
    alerts: List[str]
) -> Tuple[List[str], List[str], List[str]]:
    """Check against success criteria and return passes, warnings, and failures"""

    passes = []
    warnings = []
    failures = []

    # Critical criteria (must pass)
    if log_analysis.get("shutdowns", 0) == 0:
        passes.append("No emergency shutdowns")
    else:
        failures.append(f"Emergency shutdowns detected: {log_analysis['shutdowns']}")

    if log_analysis.get("critical", []) == []:
        passes.append("No critical errors")
    else:
        failures.append(f"Critical errors found: {len(log_analysis['critical'])}")

    if not metrics.get("error"):
        uptime_hours = metrics.get("uptime_seconds", 0) / 3600
        if uptime_hours >= 48:
            passes.append(f"Bot ran for {uptime_hours:.1f} hours (target: 48+)")
        elif uptime_hours >= 24:
            warnings.append(f"Bot ran for {uptime_hours:.1f} hours (target: 48+)")
        else:
            failures.append(f"Bot ran for only {uptime_hours:.1f} hours (target: 48+)")

    if not metrics.get("error"):
        avg_detection = metrics.get("avg_detection_time_seconds", 0)
        if avg_detection > 0 and avg_detection < 2:
            passes.append(f"Detection time within target: {avg_detection:.2f}s")
        elif avg_detection > 0 and avg_detection < 5:
            warnings.append(f"Detection time slow: {avg_detection:.2f}s (target: <2s)")
        elif avg_detection > 0:
            failures.append(f"Detection time too slow: {avg_detection:.2f}s (target: <2s)")

    if not metrics.get("error"):
        avg_execution = metrics.get("avg_execution_time_seconds", 0)
        if avg_execution > 0 and avg_execution < 5:
            passes.append(f"Execution time within target: {avg_execution:.2f}s")
        elif avg_execution > 0 and avg_execution < 10:
            warnings.append(f"Execution time slow: {avg_execution:.2f}s (target: <5s)")
        elif avg_execution > 0:
            failures.append(f"Execution time too slow: {avg_execution:.2f}s (target: <5s)")

    if not metrics.get("error"):
        memory_mb = metrics.get("memory_usage_mb", 0)
        if memory_mb > 0 and memory_mb < 500:
            passes.append(f"Memory usage within target: {memory_mb:.0f} MB")
        elif memory_mb > 0 and memory_mb < 800:
            warnings.append(f"Memory usage high: {memory_mb:.0f} MB (target: <500 MB)")
        elif memory_mb > 0:
            failures.append(f"Memory usage too high: {memory_mb:.0f} MB (target: <500 MB)")

    if not metrics.get("error"):
        cpu_pct = metrics.get("cpu_usage_percent", 0)
        if cpu_pct > 0 and cpu_pct < 50:
            passes.append(f"CPU usage within target: {cpu_pct:.1f}%")
        elif cpu_pct > 0 and cpu_pct < 80:
            warnings.append(f"CPU usage elevated: {cpu_pct:.1f}% (target: <50%)")
        elif cpu_pct > 0:
            warnings.append(f"CPU usage high: {cpu_pct:.1f}% (target: <50%)")

    # Important criteria
    if not metrics.get("error"):
        success_rate = metrics.get("success_rate", 0)
        trades = metrics.get("trades_executed", 0)
        if trades > 0:
            if success_rate >= 80:
                passes.append(f"Success rate good: {success_rate:.1f}%")
            elif success_rate >= 60:
                warnings.append(f"Success rate low: {success_rate:.1f}% (target: >80%)")
            else:
                failures.append(f"Success rate poor: {success_rate:.1f}% (target: >80%)")
        else:
            warnings.append("No trades executed during validation")

    error_count = len(log_analysis.get("errors", []))
    if error_count == 0:
        passes.append("No errors in logs")
    elif error_count < 10:
        warnings.append(f"Few errors found: {error_count}")
    else:
        warnings.append(f"Many errors found: {error_count}")

    if len(alerts) == 0:
        passes.append("No validation alerts")
    else:
        warnings.append(f"Validation alerts: {len(alerts)}")

    return passes, warnings, failures

def generate_report(
    log_analysis: Dict,
    metrics: Dict,
    validation_log: Dict,
    alerts: List[str],
    passes: List[str],
    warnings: List[str],
    failures: List[str]
):
    """Generate and print the validation report"""

    print_header("48-HOUR VALIDATION RUN ANALYSIS")

    print(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Report Generated By: analyze_validation_run.py")

    # Summary
    print_section("VALIDATION SUMMARY")

    if not metrics.get("error"):
        print(f"Runtime: {metrics.get('uptime_seconds', 0) / 3600:.1f} hours")
        print(f"Opportunities Found: {metrics.get('opportunities_found', 0)}")
        print(f"Trades Executed: {metrics.get('trades_executed', 0)}")
        print(f"Success Rate: {metrics.get('success_rate', 0):.1f}%")
        print(f"Net Profit: ${metrics.get('net_profit_usd', 0):.2f}")
    else:
        print_warn(f"Metrics Error: {metrics['error']}")

    # Success Criteria
    print_section("SUCCESS CRITERIA RESULTS")

    print(f"\n{Colors.BOLD}✓ Passed: {len(passes)}{Colors.END}")
    for p in passes:
        print_pass(p)

    if warnings:
        print(f"\n{Colors.BOLD}⚠ Warnings: {len(warnings)}{Colors.END}")
        for w in warnings:
            print_warn(w)

    if failures:
        print(f"\n{Colors.BOLD}✗ Failed: {len(failures)}{Colors.END}")
        for f in failures:
            print_fail(f)

    # Detailed Metrics
    print_section("DETAILED METRICS")

    if not metrics.get("error"):
        print(f"\nPerformance:")
        print(f"  Detection Time: {metrics.get('avg_detection_time_seconds', 0):.3f}s (target: <2s)")
        print(f"  Execution Time: {metrics.get('avg_execution_time_seconds', 0):.3f}s (target: <5s)")
        print(f"  RPC Calls/Min: {metrics.get('rpc_calls_per_minute', 0):.1f} (target: <100)")

        print(f"\nResources:")
        print(f"  CPU Usage: {metrics.get('cpu_usage_percent', 0):.1f}% (target: <50%)")
        print(f"  Memory Usage: {metrics.get('memory_usage_mb', 0):.0f} MB (target: <500 MB)")

        print(f"\nTrading:")
        print(f"  Total Opportunities: {metrics.get('opportunities_found', 0)}")
        print(f"  Total Trades: {metrics.get('trades_executed', 0)}")
        print(f"  Successful Trades: {metrics.get('successful_trades', 0)}")
        print(f"  Failed Trades: {metrics.get('failed_trades', 0)}")

        print(f"\nFinancial:")
        print(f"  Gross Profit: ${metrics.get('gross_profit_usd', 0):.2f}")
        print(f"  Gross Loss: ${metrics.get('gross_loss_usd', 0):.2f}")
        print(f"  Net Profit: ${metrics.get('net_profit_usd', 0):.2f}")
        print(f"  Total Gas Spent: ${metrics.get('total_gas_spent_usd', 0):.2f}")

    # Log Analysis
    print_section("LOG ANALYSIS")

    if not log_analysis.get("error"):
        print(f"Total Log Lines: {log_analysis.get('total_lines', 0):,}")
        print(f"Critical Errors: {len(log_analysis.get('critical', []))}")
        print(f"Errors: {len(log_analysis.get('errors', []))}")
        print(f"Warnings: {len(log_analysis.get('warnings', []))}")
        print(f"Emergency Shutdowns: {log_analysis.get('shutdowns', 0)}")

        if log_analysis.get('critical'):
            print(f"\n{Colors.RED}Critical Errors Found:{Colors.END}")
            for i, error in enumerate(log_analysis['critical'][:5], 1):
                print(f"  {i}. {error[:120]}")
            if len(log_analysis['critical']) > 5:
                print(f"  ... and {len(log_analysis['critical']) - 5} more")

        if log_analysis.get('errors') and len(log_analysis['errors']) > 0:
            print(f"\n{Colors.YELLOW}Sample Errors:{Colors.END}")
            for i, error in enumerate(log_analysis['errors'][:3], 1):
                print(f"  {i}. {error[:120]}")
            if len(log_analysis['errors']) > 3:
                print(f"  ... and {len(log_analysis['errors']) - 3} more")
    else:
        print_warn(log_analysis['error'])

    # Validation Monitoring
    print_section("VALIDATION MONITORING")

    if not validation_log.get("error"):
        print(f"Total Checks: {validation_log.get('checks', 0)}")
        print(f"Passed Checks: {validation_log.get('passes', 0)}")
        print(f"Failed Checks: {validation_log.get('failures', 0)}")
        print(f"Pass Rate: {validation_log.get('pass_rate', 0):.1f}%")
    else:
        print_warn(validation_log['error'])

    if alerts:
        print(f"\n{Colors.YELLOW}Validation Alerts ({len(alerts)}):{Colors.END}")
        for alert in alerts[-10:]:  # Show last 10
            print(f"  • {alert}")
    else:
        print_pass("No validation alerts")

    # Final Decision
    print_section("MAINNET DEPLOYMENT DECISION")

    critical_pass = len(failures) == 0
    important_pass = len(failures) == 0 and len(warnings) < 5

    if critical_pass and important_pass:
        print(f"\n{Colors.GREEN}{Colors.BOLD}✓ RECOMMENDATION: GO FOR MAINNET{Colors.END}")
        print("\nAll critical criteria passed.")
        print("Bot is ready for mainnet deployment with conservative settings.")
        print("\nRecommended mainnet configuration:")
        print("  • BASE_PROFIT_THRESHOLD: 0.02 (2%)")
        print("  • MAX_POSITION_SIZE_USD: 100")
        print("  • DAILY_LOSS_LIMIT_USD: 500")
        print("  • MAX_CONSECUTIVE_LOSSES: 3")
        decision = "GO"
    elif critical_pass:
        print(f"\n{Colors.YELLOW}{Colors.BOLD}⚠ RECOMMENDATION: GO WITH CAUTION{Colors.END}")
        print("\nCritical criteria passed, but some warnings present.")
        print("Consider addressing warnings before mainnet, or proceed with extra caution.")
        print("\nIf proceeding:")
        print("  • Use even more conservative settings")
        print("  • Monitor very closely for first 24 hours")
        print("  • Be ready for emergency shutdown")
        decision = "GO_WITH_CAUTION"
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}✗ RECOMMENDATION: NO-GO{Colors.END}")
        print("\nCritical issues found. Do NOT deploy to mainnet yet.")
        print("\nRequired actions:")
        for failure in failures:
            print(f"  • Fix: {failure}")
        print("\nRun another 48-hour validation after fixes.")
        decision = "NO_GO"

    # Save report to file
    print_section("REPORT OUTPUT")

    report_file = f"validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

    try:
        with open(report_file, 'w') as f:
            f.write("=" * 80 + "\n")
            f.write("48-HOUR VALIDATION RUN ANALYSIS\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            f.write("VALIDATION SUMMARY\n")
            f.write("-" * 80 + "\n")
            if not metrics.get("error"):
                f.write(f"Runtime: {metrics.get('uptime_seconds', 0) / 3600:.1f} hours\n")
                f.write(f"Opportunities Found: {metrics.get('opportunities_found', 0)}\n")
                f.write(f"Trades Executed: {metrics.get('trades_executed', 0)}\n")
                f.write(f"Success Rate: {metrics.get('success_rate', 0):.1f}%\n")
                f.write(f"Net Profit: ${metrics.get('net_profit_usd', 0):.2f}\n\n")

            f.write("SUCCESS CRITERIA\n")
            f.write("-" * 80 + "\n")
            f.write(f"✓ Passed: {len(passes)}\n")
            for p in passes:
                f.write(f"  ✓ {p}\n")
            if warnings:
                f.write(f"\n⚠ Warnings: {len(warnings)}\n")
                for w in warnings:
                    f.write(f"  ⚠ {w}\n")
            if failures:
                f.write(f"\n✗ Failed: {len(failures)}\n")
                for fail in failures:
                    f.write(f"  ✗ {fail}\n")

            f.write(f"\n\nFINAL DECISION: {decision}\n")
            f.write("=" * 80 + "\n")

        print(f"✓ Report saved to: {report_file}")
    except Exception as e:
        print_warn(f"Could not save report: {e}")

    return decision

def main():
    """Main analysis function"""

    # Check if we're in the right directory
    if not os.path.exists("src/bot/main.py"):
        print_fail("Error: Run this script from the project root directory")
        print("Usage: python scripts/analyze_validation_run.py")
        sys.exit(1)

    # Analyze all data
    print("Analyzing validation run data...\n")

    log_analysis = analyze_logs("logs/bot.log")
    metrics = analyze_metrics("data/metrics.json")
    validation_log = analyze_validation_log("logs/validation_monitor.log")
    alerts = analyze_alerts("data/validation_alerts.txt")

    # Check success criteria
    passes, warnings, failures = check_success_criteria(
        log_analysis, metrics, validation_log, alerts
    )

    # Generate report
    decision = generate_report(
        log_analysis, metrics, validation_log, alerts,
        passes, warnings, failures
    )

    # Exit with appropriate code
    if decision == "GO":
        sys.exit(0)
    elif decision == "GO_WITH_CAUTION":
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
