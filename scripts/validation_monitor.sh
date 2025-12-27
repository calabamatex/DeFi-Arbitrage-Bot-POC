#!/bin/bash
# Validation Monitor - Run every 30 minutes during 48-hour testnet validation
# Usage: ./scripts/validation_monitor.sh

echo "========================================"
echo "Validation Monitor - $(date)"
echo "========================================"
echo ""

VALIDATION_LOG="logs/validation_monitor.log"
ALERT_FILE="data/validation_alerts.txt"

# Ensure directories exist
mkdir -p logs data

# Log this check
echo "=== Validation Check at $(date) ===" >> "$VALIDATION_LOG"

ISSUES_FOUND=0

# 1. Check if bot is running
echo "1. Checking bot status..."
BOT_RUNNING=$(ps aux | grep "python.*main.py" | grep -v grep | wc -l)

if [ "$BOT_RUNNING" -eq 0 ]; then
    echo "❌ BOT NOT RUNNING!"
    echo "[$(date)] CRITICAL: Bot not running" >> "$ALERT_FILE"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
else
    echo "✓ Bot is running (PID: $(pgrep -f 'python.*main.py'))"

    # Get uptime
    BOT_PID=$(pgrep -f 'python.*main.py')
    if [ -n "$BOT_PID" ]; then
        UPTIME=$(ps -o etime= -p "$BOT_PID" | tr -d ' ')
        echo "  Uptime: $UPTIME"
        echo "  Uptime: $UPTIME" >> "$VALIDATION_LOG"
    fi
fi
echo ""

# 2. Check CPU and Memory usage
echo "2. Checking resource usage..."
if [ "$BOT_RUNNING" -gt 0 ]; then
    BOT_PID=$(pgrep -f 'python.*main.py')

    if [ "$(uname)" = "Darwin" ]; then
        # macOS
        CPU=$(ps -p "$BOT_PID" -o %cpu | tail -1 | tr -d ' ')
        MEM=$(ps -p "$BOT_PID" -o rss | tail -1)
        MEM_MB=$((MEM / 1024))
    else
        # Linux
        CPU=$(ps -p "$BOT_PID" -o %cpu --no-headers | tr -d ' ')
        MEM=$(ps -p "$BOT_PID" -o rss --no-headers)
        MEM_MB=$((MEM / 1024))
    fi

    echo "  CPU: ${CPU}%"
    echo "  Memory: ${MEM_MB} MB"
    echo "  CPU: ${CPU}%, Memory: ${MEM_MB} MB" >> "$VALIDATION_LOG"

    # Alert if usage too high
    if [ "$(echo "$CPU > 80" | bc -l 2>/dev/null || echo 0)" -eq 1 ]; then
        echo "⚠️  High CPU usage: ${CPU}%"
        echo "[$(date)] WARNING: High CPU usage: ${CPU}%" >> "$ALERT_FILE"
        ISSUES_FOUND=$((ISSUES_FOUND + 1))
    fi

    if [ "$MEM_MB" -gt 800 ]; then
        echo "⚠️  High memory usage: ${MEM_MB} MB"
        echo "[$(date)] WARNING: High memory usage: ${MEM_MB} MB" >> "$ALERT_FILE"
        ISSUES_FOUND=$((ISSUES_FOUND + 1))
    fi
fi
echo ""

# 3. Check recent errors in logs
echo "3. Checking for recent errors..."
if [ -f "logs/bot.log" ]; then
    RECENT_ERRORS=$(tail -1000 logs/bot.log | grep -i "error\|critical\|exception" | wc -l)
    CRITICAL_ERRORS=$(tail -1000 logs/bot.log | grep -i "critical" | wc -l)

    echo "  Recent errors (last 1000 lines): $RECENT_ERRORS"
    echo "  Critical errors: $CRITICAL_ERRORS"
    echo "  Errors: $RECENT_ERRORS, Critical: $CRITICAL_ERRORS" >> "$VALIDATION_LOG"

    if [ "$CRITICAL_ERRORS" -gt 0 ]; then
        echo "❌ CRITICAL ERRORS FOUND!"
        echo "[$(date)] CRITICAL: $CRITICAL_ERRORS critical errors in logs" >> "$ALERT_FILE"
        echo "  Last critical error:"
        tail -1000 logs/bot.log | grep -i "critical" | tail -1
        ISSUES_FOUND=$((ISSUES_FOUND + 1))
    fi

    # Check for emergency shutdown
    SHUTDOWN=$(tail -100 logs/bot.log | grep -i "emergency shutdown" | wc -l)
    if [ "$SHUTDOWN" -gt 0 ]; then
        echo "❌ EMERGENCY SHUTDOWN DETECTED!"
        echo "[$(date)] CRITICAL: Emergency shutdown triggered" >> "$ALERT_FILE"
        ISSUES_FOUND=$((ISSUES_FOUND + 1))
    fi
else
    echo "⚠️  Bot log file not found"
fi
echo ""

# 4. Check metrics
echo "4. Checking metrics..."
if [ -f "data/metrics.json" ]; then
    # Check if metrics were updated recently (within last hour)
    if [ "$(uname)" = "Darwin" ]; then
        METRICS_AGE=$(( $(date +%s) - $(stat -f %m "data/metrics.json") ))
    else
        METRICS_AGE=$(( $(date +%s) - $(stat -c %Y "data/metrics.json") ))
    fi

    if [ "$METRICS_AGE" -gt 7200 ]; then
        echo "⚠️  Metrics not updated recently (${METRICS_AGE}s ago)"
        echo "[$(date)] WARNING: Metrics stale (${METRICS_AGE}s)" >> "$ALERT_FILE"
        ISSUES_FOUND=$((ISSUES_FOUND + 1))
    else
        echo "✓ Metrics updated recently (${METRICS_AGE}s ago)"

        # Try to extract key metrics using Python
        if command -v python3 &> /dev/null; then
            python3 << 'EOF'
import json
import sys
try:
    with open("data/metrics.json", "r") as f:
        metrics = json.load(f)
    print(f"  Uptime: {metrics.get('uptime_seconds', 0) / 3600:.1f} hours")
    print(f"  Opportunities: {metrics.get('opportunities_found', 0)}")
    print(f"  Trades: {metrics.get('trades_executed', 0)}")
    print(f"  Success Rate: {metrics.get('success_rate', 0):.1f}%")
    print(f"  Net Profit: ${metrics.get('net_profit_usd', 0):.2f}")
except Exception as e:
    print(f"  Could not parse metrics: {e}", file=sys.stderr)
EOF
        fi
    fi
else
    echo "⚠️  Metrics file not found"
fi
echo ""

# 5. Check disk space
echo "5. Checking disk space..."
if [ "$(uname)" = "Darwin" ]; then
    DISK_USAGE=$(df -h . | tail -1 | awk '{print $5}' | tr -d '%')
else
    DISK_USAGE=$(df -h . | tail -1 | awk '{print $5}' | tr -d '%')
fi

echo "  Disk usage: ${DISK_USAGE}%"
echo "  Disk usage: ${DISK_USAGE}%" >> "$VALIDATION_LOG"

if [ "$DISK_USAGE" -gt 90 ]; then
    echo "⚠️  Low disk space: ${DISK_USAGE}% used"
    echo "[$(date)] WARNING: Low disk space: ${DISK_USAGE}%" >> "$ALERT_FILE"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
fi
echo ""

# 6. Check RPC connectivity
echo "6. Checking RPC connectivity..."
if [ -f ".env" ]; then
    RPC_URL=$(grep "POLYGON_RPC_URL" .env | cut -d '=' -f2 | tr -d '"' | tr -d "'" | tr -d ' ')

    if [ -n "$RPC_URL" ]; then
        # Test RPC with a simple eth_blockNumber call
        RESPONSE=$(curl -s -X POST "$RPC_URL" \
            -H "Content-Type: application/json" \
            -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' \
            --max-time 10)

        if echo "$RESPONSE" | grep -q "result"; then
            BLOCK=$(echo "$RESPONSE" | grep -o '"result":"[^"]*"' | cut -d'"' -f4)
            BLOCK_DEC=$((16#${BLOCK#0x}))
            echo "✓ RPC connected (Block: $BLOCK_DEC)"
            echo "  RPC OK, Block: $BLOCK_DEC" >> "$VALIDATION_LOG"
        else
            echo "❌ RPC connection failed!"
            echo "[$(date)] CRITICAL: RPC connection failed" >> "$ALERT_FILE"
            ISSUES_FOUND=$((ISSUES_FOUND + 1))
        fi
    else
        echo "⚠️  Could not find RPC URL in .env"
    fi
else
    echo "⚠️  .env file not found"
fi
echo ""

# 7. Check log file sizes
echo "7. Checking log file sizes..."
if [ -d "logs" ]; then
    TOTAL_LOG_SIZE=$(du -sh logs/ | awk '{print $1}')
    echo "  Total log size: $TOTAL_LOG_SIZE"
    echo "  Log size: $TOTAL_LOG_SIZE" >> "$VALIDATION_LOG"

    # List large log files
    if [ "$(uname)" = "Darwin" ]; then
        find logs/ -type f -size +100M 2>/dev/null | while read -r file; do
            SIZE=$(du -h "$file" | awk '{print $1}')
            echo "  Large file: $file ($SIZE)"
        done
    else
        find logs/ -type f -size +100M 2>/dev/null | while read -r file; do
            SIZE=$(du -h "$file" | awk '{print $1}')
            echo "  Large file: $file ($SIZE)"
        done
    fi
fi
echo ""

# 8. Generate quick report
echo "8. Validation Summary..."
echo "  Checks run: 7"
echo "  Issues found: $ISSUES_FOUND"

if [ "$ISSUES_FOUND" -eq 0 ]; then
    echo "  Status: ✅ ALL CHECKS PASSED"
    echo "[$(date)] Status: PASS" >> "$VALIDATION_LOG"
else
    echo "  Status: ⚠️  $ISSUES_FOUND ISSUES DETECTED"
    echo "[$(date)] Status: FAIL ($ISSUES_FOUND issues)" >> "$VALIDATION_LOG"

    # Show alert file if exists
    if [ -f "$ALERT_FILE" ]; then
        echo ""
        echo "Recent alerts:"
        tail -5 "$ALERT_FILE"
    fi
fi
echo ""

echo "========================================"
echo "Monitor check complete at $(date)"
echo "========================================"
echo ""

# Return exit code based on issues
if [ "$ISSUES_FOUND" -gt 0 ]; then
    exit 1
else
    exit 0
fi
