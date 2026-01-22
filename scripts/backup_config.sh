#!/bin/bash
# Backup configuration and data

BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "Creating backup in $BACKUP_DIR..."

# Backup config
if [ -f "config/config.json" ]; then
    cp config/config.json "$BACKUP_DIR/"
    echo "✓ Backed up config.json"
fi

# Backup .env (without sensitive data)
if [ -f ".env" ]; then
    grep -v "PRIVATE_KEY\|TELEGRAM" .env > "$BACKUP_DIR/env.template" 2>/dev/null || true
    echo "✓ Backed up .env template (without secrets)"
fi

# Backup logs
if [ -d "logs" ]; then
    cp -r logs "$BACKUP_DIR/" 2>/dev/null || true
    echo "✓ Backed up logs directory"
fi

# Backup trade history
if [ -f "arbitrage_log.txt" ]; then
    cp arbitrage_log.txt "$BACKUP_DIR/" 2>/dev/null || true
    echo "✓ Backed up arbitrage_log.txt"
fi

# Backup any log files in root
if ls bot_*.log 1> /dev/null 2>&1; then
    cp bot_*.log "$BACKUP_DIR/" 2>/dev/null || true
    echo "✓ Backed up bot log files"
fi

# Create backup info
cat > "$BACKUP_DIR/backup_info.txt" << EOF
Backup created: $(date)
Environment: ${ENVIRONMENT:-unknown}
Bot version: $(git rev-parse HEAD 2>/dev/null || echo "unknown")
Hostname: $(hostname)
EOF

echo "✓ Created backup info"
echo ""
echo "✅ Backup created: $BACKUP_DIR"
echo ""
echo "To restore:"
echo "  cp $BACKUP_DIR/config.json config/"
echo "  # Manually restore .env with your keys"
echo ""
echo "To compress backup:"
echo "  tar -czf $BACKUP_DIR.tar.gz $BACKUP_DIR"
