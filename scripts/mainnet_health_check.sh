#!/bin/bash
# Quick mainnet health check
# Run this frequently during first 48 hours of mainnet operation

echo "========================================"
echo "Mainnet Health Check - $(date)"
echo "========================================"
echo ""

ISSUES_FOUND=0

# 1. Bot running?
echo "1. Checking bot status..."
if pgrep -f "python.*main.py" > /dev/null; then
    BOT_PID=$(pgrep -f "python.*main.py")
    echo "✓ Bot is running (PID: $BOT_PID)"

    # Get uptime
    if [ "$(uname)" = "Darwin" ]; then
        UPTIME=$(ps -o etime= -p "$BOT_PID" | tr -d ' ')
    else
        UPTIME=$(ps -o etime= -p "$BOT_PID" | tr -d ' ')
    fi
    echo "  Uptime: $UPTIME"
else
    echo "❌ BOT IS NOT RUNNING!"
    echo "⚠️  IMMEDIATE ACTION REQUIRED"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
    exit 1
fi
echo ""

# 2. Recent errors?
echo "2. Checking for recent errors..."
if [ -f "logs/mainnet_bot.log" ]; then
    ERROR_COUNT=$(tail -1000 logs/mainnet_bot.log | grep -c "ERROR\|CRITICAL" || echo 0)
    CRITICAL_COUNT=$(tail -1000 logs/mainnet_bot.log | grep -c "CRITICAL" || echo 0)

    if [ "$CRITICAL_COUNT" -gt 0 ]; then
        echo "❌ CRITICAL ERRORS FOUND: $CRITICAL_COUNT"
        echo "  Last critical:"
        tail -1000 logs/mainnet_bot.log | grep "CRITICAL" | tail -1
        ISSUES_FOUND=$((ISSUES_FOUND + 1))
    elif [ "$ERROR_COUNT" -gt 10 ]; then
        echo "⚠️  Warning: $ERROR_COUNT errors in last 1000 lines"
        ISSUES_FOUND=$((ISSUES_FOUND + 1))
    else
        echo "✓ Error count acceptable: $ERROR_COUNT"
    fi
elif [ -f "logs/bot.log" ]; then
    ERROR_COUNT=$(tail -1000 logs/bot.log | grep -c "ERROR\|CRITICAL" || echo 0)
    CRITICAL_COUNT=$(tail -1000 logs/bot.log | grep -c "CRITICAL" || echo 0)

    if [ "$CRITICAL_COUNT" -gt 0 ]; then
        echo "❌ CRITICAL ERRORS FOUND: $CRITICAL_COUNT"
        ISSUES_FOUND=$((ISSUES_FOUND + 1))
    elif [ "$ERROR_COUNT" -gt 10 ]; then
        echo "⚠️  Warning: $ERROR_COUNT errors"
        ISSUES_FOUND=$((ISSUES_FOUND + 1))
    else
        echo "✓ Error count acceptable: $ERROR_COUNT"
    fi
else
    echo "⚠️  Log file not found"
fi
echo ""

# 3. Check for emergency shutdown
echo "3. Checking for emergency shutdown..."
SHUTDOWN_COUNT=0
if [ -f "logs/mainnet_bot.log" ]; then
    SHUTDOWN_COUNT=$(grep -c "Emergency shutdown" logs/mainnet_bot.log || echo 0)
elif [ -f "logs/bot.log" ]; then
    SHUTDOWN_COUNT=$(grep -c "Emergency shutdown" logs/bot.log || echo 0)
fi

if [ "$SHUTDOWN_COUNT" -gt 0 ]; then
    echo "❌ EMERGENCY SHUTDOWN DETECTED ($SHUTDOWN_COUNT times)"
    echo "⚠️  IMMEDIATE INVESTIGATION REQUIRED"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
else
    echo "✓ No emergency shutdowns"
fi
echo ""

# 4. Check latest trade activity
echo "4. Checking recent trading activity..."
RECENT_TRADES=0
if [ -f "logs/mainnet_bot.log" ]; then
    RECENT_TRADES=$(tail -200 logs/mainnet_bot.log | grep -c "Trade.*executed\|Executing trade" || echo 0)
    LAST_TRADE=$(tail -200 logs/mainnet_bot.log | grep "Trade" | tail -1)
elif [ -f "logs/bot.log" ]; then
    RECENT_TRADES=$(tail -200 logs/bot.log | grep -c "Trade.*executed\|Executing trade" || echo 0)
    LAST_TRADE=$(tail -200 logs/bot.log | grep "Trade" | tail -1)
fi

if [ -n "$LAST_TRADE" ]; then
    echo "✓ Recent trading activity: $RECENT_TRADES trades in last 200 lines"
    echo "  Last: ${LAST_TRADE:0:100}..."
else
    echo "⚠️  No recent trades (may be normal if no opportunities)"
fi
echo ""

# 5. Check resource usage
echo "5. Checking resource usage..."
if [ -n "$BOT_PID" ]; then
    if [ "$(uname)" = "Darwin" ]; then
        CPU=$(ps -p "$BOT_PID" -o %cpu | tail -1 | tr -d ' ')
        MEM=$(ps -p "$BOT_PID" -o rss | tail -1)
        MEM_MB=$((MEM / 1024))
    else
        CPU=$(ps -p "$BOT_PID" -o %cpu --no-headers | tr -d ' ')
        MEM=$(ps -p "$BOT_PID" -o rss --no-headers)
        MEM_MB=$((MEM / 1024))
    fi

    echo "  CPU: ${CPU}%"
    echo "  Memory: ${MEM_MB} MB"

    # Check for issues
    if [ "$(echo "$CPU > 80" | bc -l 2>/dev/null || echo 0)" -eq 1 ]; then
        echo "⚠️  High CPU usage: ${CPU}%"
        ISSUES_FOUND=$((ISSUES_FOUND + 1))
    fi

    if [ "$MEM_MB" -gt 800 ]; then
        echo "⚠️  High memory usage: ${MEM_MB} MB (target: <500 MB)"
        ISSUES_FOUND=$((ISSUES_FOUND + 1))
    fi
fi
echo ""

# 6. Check metrics
echo "6. Checking metrics..."
if [ -f "data/metrics.json" ] && command -v python3 &> /dev/null; then
    python3 << 'EOF'
import json
import sys
from datetime import datetime

try:
    with open("data/metrics.json", "r") as f:
        metrics = json.load(f)

    print(f"  Uptime: {metrics.get('uptime_seconds', 0) / 3600:.1f} hours")
    print(f"  Opportunities: {metrics.get('opportunities_found', 0)}")
    print(f"  Trades: {metrics.get('trades_executed', 0)}")
    print(f"  Success Rate: {metrics.get('success_rate', 0):.1f}%")

    net_profit = metrics.get('net_profit_usd', 0)
    if net_profit >= 0:
        print(f"  Net Profit: ${net_profit:.2f} ✓")
    else:
        print(f"  Net Loss: ${net_profit:.2f} ⚠️")

except Exception as e:
    print(f"  ⚠️  Could not parse metrics: {e}", file=sys.stderr)
EOF
else
    echo "  ⚠️  Metrics file not found or Python not available"
fi
echo ""

# 7. Check RPC connectivity
echo "7. Checking RPC connectivity..."
if [ -f ".env" ]; then
    # Try to extract RPC URL from .env
    RPC_URL=$(grep "POLYGON_RPC_URL" .env | cut -d '=' -f2 | tr -d '"' | tr -d "'" | tr -d ' ')

    if [ -n "$RPC_URL" ]; then
        RESPONSE=$(curl -s -X POST "$RPC_URL" \
            -H "Content-Type: application/json" \
            -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' \
            --max-time 10)

        if echo "$RESPONSE" | grep -q "result"; then
            BLOCK=$(echo "$RESPONSE" | grep -o '"result":"[^"]*"' | cut -d'"' -f4)
            BLOCK_DEC=$((16#${BLOCK#0x}))
            echo "✓ RPC connected (Block: $BLOCK_DEC)"
        else
            echo "❌ RPC connection failed!"
            echo "  Response: $RESPONSE"
            ISSUES_FOUND=$((ISSUES_FOUND + 1))
        fi
    else
        echo "⚠️  Could not find RPC URL"
    fi
else
    echo "⚠️  .env file not found"
fi
echo ""

# Summary
echo "========================================"
echo "Health Check Summary"
echo "========================================"
echo ""

if [ "$ISSUES_FOUND" -eq 0 ]; then
    echo "✅ ALL CHECKS PASSED"
    echo ""
    echo "Bot is healthy and operating normally."
else
    echo "⚠️  $ISSUES_FOUND ISSUES DETECTED"
    echo ""
    echo "Review issues above and take appropriate action."
    echo ""
    echo "Commands for further investigation:"
    echo "  tail -100 logs/mainnet_bot.log    # View recent logs"
    echo "  ./scripts/monitor_bot.py          # Detailed status"
    echo "  ./scripts/generate_report.py      # Generate report"
fi
echo ""

# Exit with appropriate code
exit $ISSUES_FOUND
