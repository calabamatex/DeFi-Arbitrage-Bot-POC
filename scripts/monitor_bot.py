#!/usr/bin/env python3
"""
Monitor if bot is running and healthy.
"""

import sys
import time
import os
from datetime import datetime


def find_bot_process():
    """Find bot process."""
    try:
        import psutil

        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                cmdline = proc.info["cmdline"]
                if cmdline and "src.bot.main" in " ".join(cmdline):
                    return proc
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return None
    except ImportError:
        print("⚠️  psutil not installed - cannot check if bot is running")
        print("   Install with: pip install psutil")
        return None


def main():
    print("=" * 60)
    print("Bot Health Monitor")
    print("=" * 60)
    print()

    # Check if bot is running
    proc = find_bot_process()

    if proc is None and "psutil" in sys.modules:
        print("❌ Bot is NOT running")
        print()
        print("To start the bot:")
        print("  python3 -m src.bot.main")
        sys.exit(1)
    elif proc is None:
        # psutil not available, skip process check
        print("⚠️  Cannot verify if bot is running (psutil not installed)")
        print()
    else:
        print(f"✓ Bot is running (PID: {proc.pid})")
        print()

        # Get process info
        try:
            import psutil

            with proc.oneshot():
                create_time = datetime.fromtimestamp(proc.create_time())
                uptime = datetime.now() - create_time

                cpu_percent = proc.cpu_percent(interval=1.0)
                memory_info = proc.memory_info()
                memory_mb = memory_info.rss / 1024 / 1024

                print(f"Uptime: {uptime}")
                print(f"CPU Usage: {cpu_percent:.1f}%")
                print(f"Memory Usage: {memory_mb:.1f} MB")

            print()
        except ImportError:
            pass

    # Check log file
    import glob

    log_files = sorted(glob.glob("bot_*.log"), reverse=True)

    if log_files:
        latest_log = log_files[0]
        print(f"Latest log: {latest_log}")

        # Check for recent activity
        mod_time = datetime.fromtimestamp(os.path.getmtime(latest_log))
        time_since_update = datetime.now() - mod_time

        if time_since_update.total_seconds() > 300:  # 5 minutes
            print("  ⚠️  WARNING: Log file not updated recently")
            print(f"     Last update: {time_since_update} ago")
        else:
            print("  ✓ Log file actively updating")

        # Check for errors
        with open(latest_log, "r") as f:
            lines = f.readlines()
            recent_lines = lines[-100:]  # Last 100 lines

            errors = [l for l in recent_lines if "ERROR" in l or "CRITICAL" in l]

            if errors:
                print(f"  ⚠️  Found {len(errors)} recent errors")
                print("     Run: grep ERROR " + latest_log)
            else:
                print("  ✓ No recent errors")
    else:
        print("⚠️  No log files found")
        print("   Bot may not have started yet")

    print()
    print("✅ Bot health check complete")


if __name__ == "__main__":
    main()
