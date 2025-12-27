#!/bin/bash
# Automated security scanning

echo "========================================="
echo "Security Scan - Arbitrage Bot"
echo "========================================="
echo ""

ISSUES_FOUND=0

# 1. Check for hardcoded secrets
echo "1. Checking for hardcoded secrets..."
if grep -r "PRIVATE_KEY.*=.*0x" src/ 2>/dev/null | grep -v "load_env_vars\|getenv"; then
    echo "❌ Found hardcoded private keys!"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
else
    echo "✓ No hardcoded secrets found"
fi
echo ""

# 2. Check for exposed API keys
echo "2. Checking for exposed API keys..."
if grep -r "api.*key.*=.*['\"]" src/ 2>/dev/null | grep -v "getenv\|env\|config"; then
    echo "❌ Found exposed API keys!"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
else
    echo "✓ No exposed API keys"
fi
echo ""

# 3. Check file permissions
echo "3. Checking file permissions..."
if [ -f .env ]; then
    if [ "$(uname)" = "Darwin" ]; then
        # macOS
        PERM=$(stat -f "%OLp" .env)
    else
        # Linux
        PERM=$(stat -c "%a" .env)
    fi

    if [ "$PERM" != "600" ] && [ "$PERM" != "400" ]; then
        echo "⚠️  .env permissions: $PERM (should be 600 or 400)"
        echo "   Fix with: chmod 600 .env"
        ISSUES_FOUND=$((ISSUES_FOUND + 1))
    else
        echo "✓ .env permissions correct ($PERM)"
    fi
else
    echo "⚠️  .env file not found"
fi
echo ""

# 4. Check for .env in gitignore
echo "4. Checking .gitignore..."
if [ -f .gitignore ]; then
    if grep -q "^\.env$" .gitignore; then
        echo "✓ .env in .gitignore"
    else
        echo "❌ .env NOT in .gitignore!"
        ISSUES_FOUND=$((ISSUES_FOUND + 1))
    fi
else
    echo "⚠️  .gitignore not found"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
fi
echo ""

# 5. Check for vulnerable packages
echo "5. Checking for vulnerable packages..."
if command -v pip-audit &> /dev/null; then
    if pip-audit --desc 2>/dev/null; then
        echo "✓ No known vulnerabilities"
    else
        echo "⚠️  Vulnerabilities found"
        ISSUES_FOUND=$((ISSUES_FOUND + 1))
    fi
else
    echo "⚠️  pip-audit not installed (optional)"
    echo "   Install with: pip install pip-audit"
fi
echo ""

# 6. Check dependencies are pinned
echo "6. Checking requirements.txt..."
if [ -f requirements.txt ]; then
    UNPINNED=$(grep -v "==" requirements.txt | grep -v "^#" | grep -v "^$" | wc -l)
    if [ "$UNPINNED" -gt 0 ]; then
        echo "⚠️  $UNPINNED dependencies not pinned"
        echo "   Consider pinning with specific versions"
    else
        echo "✓ All dependencies pinned"
    fi
else
    echo "❌ requirements.txt not found!"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
fi
echo ""

# 7. Check for insecure HTTP connections
echo "7. Checking for insecure HTTP connections..."
if grep -r "http://" config/ src/ 2>/dev/null | grep -v "https://" | grep -v "#"; then
    echo "❌ Found insecure HTTP connections!"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
else
    echo "✓ All connections use HTTPS"
fi
echo ""

# 8. Check for TODO security items
echo "8. Checking for security TODOs..."
SECURITY_TODOS=$(grep -r "TODO.*security\|FIXME.*security" src/ 2>/dev/null | wc -l)
if [ "$SECURITY_TODOS" -gt 0 ]; then
    echo "⚠️  Found $SECURITY_TODOS security TODOs:"
    grep -r "TODO.*security\|FIXME.*security" src/ 2>/dev/null
else
    echo "✓ No security TODOs found"
fi
echo ""

# 9. Check for exception handling
echo "9. Checking exception handling..."
TRY_COUNT=$(grep -r "try:" src/ 2>/dev/null | wc -l)
EXCEPT_COUNT=$(grep -r "except" src/ 2>/dev/null | wc -l)

if [ "$TRY_COUNT" -gt 0 ]; then
    echo "✓ Found $TRY_COUNT try blocks with exception handling"
else
    echo "⚠️  No exception handling found"
fi
echo ""

# 10. Check for sensitive data in logs
echo "10. Checking logs for sensitive data..."
if [ -d logs ]; then
    if grep -r "0x[a-fA-F0-9]\{64\}" logs/ 2>/dev/null; then
        echo "❌ Found potential private keys in logs!"
        ISSUES_FOUND=$((ISSUES_FOUND + 1))
    else
        echo "✓ No sensitive data in logs"
    fi
else
    echo "⚠️  logs directory not found (may be first run)"
fi
echo ""

# Summary
echo "========================================="
echo "Security Scan Complete"
echo "========================================="
echo ""

if [ "$ISSUES_FOUND" -eq 0 ]; then
    echo "✅ All security checks passed!"
    echo ""
    echo "Next steps:"
    echo "  1. Review manual security checklist"
    echo "  2. Test on testnet for 48+ hours"
    echo "  3. Monitor for any issues"
    echo "  4. Deploy to mainnet with conservative settings"
    exit 0
else
    echo "⚠️  Found $ISSUES_FOUND security issues"
    echo ""
    echo "Please address all issues before mainnet deployment!"
    exit 1
fi
