# Manual Testnet Testing Checklist

## Prerequisites

### Testnet Funds
- [ ] Have 5+ MATIC on Mumbai testnet
  - Get from: https://faucet.polygon.technology/
- [ ] Have testnet tokens (WETH, USDC, USDT, DAI)
  - Swap some MATIC on Mumbai DEXes
  - Or use testnet faucets

### Configuration
- [ ] `.env` file configured with testnet wallet
  ```bash
  PRIVATE_KEY=0x...  # Testnet wallet (DO NOT use mainnet wallet!)
  TELEGRAM_BOT_TOKEN=...
  TELEGRAM_CHAT_ID=...
  ENVIRONMENT=testnet  # CRITICAL!
  ```
- [ ] `config/config.json` has testnet section
- [ ] Telegram bot set up and tested

### Safety Checks
- [ ] ⚠️ **VERIFY** using testnet wallet (not mainnet)
- [ ] ⚠️ **VERIFY** ENVIRONMENT=testnet in .env
- [ ] ⚠️ **VERIFY** connecting to Mumbai (chain ID 80001)

---

## Setup Tests

### Configuration Tests
- [ ] Config loads testnet settings correctly
  ```bash
  python -c "from src.bot.config import load_config; _, env, _, _ = load_config(); print(f'Environment: {env}')"
  ```
  - Should print: `Environment: testnet`

- [ ] Environment variables load
  ```bash
  python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('Private key:', 'Found' if os.getenv('PRIVATE_KEY') else 'Missing')"
  ```

- [ ] RPC connection works
  ```bash
  python -c "from web3 import Web3; w3 = Web3(Web3.HTTPProvider('https://rpc-mumbai.maticvigil.com/')); print(f'Connected: {w3.is_connected()}, Chain: {w3.eth.chain_id}')"
  ```
  - Should show: `Connected: True, Chain: 80001`

- [ ] Account has sufficient balance
  ```bash
  pytest tests/integration/test_full_system.py::test_account_balance -v --testnet
  ```

---

## Component Tests

### DEX Initialization
- [ ] All 2 DEXes initialize (QuickSwap, SushiSwap)
  ```bash
  pytest tests/integration/test_full_system.py::test_dex_initialization -v --testnet
  ```

- [ ] DEX contracts have valid addresses
- [ ] No initialization errors in logs

### Price Fetching
- [ ] Can fetch prices from QuickSwap
- [ ] Can fetch prices from SushiSwap
- [ ] Prices are reasonable (not 0 or extreme)
  ```bash
  pytest tests/integration/test_full_system.py::test_fetch_real_prices -v --testnet
  ```

- [ ] Price fetching completes in < 5 seconds

### Arbitrage Detection
- [ ] Arbitrage detection structure in place
  ```bash
  pytest tests/integration/test_full_system.py::test_arbitrage_detection -v --testnet
  ```

- [ ] Can check multiple token pairs
- [ ] Detection logic doesn't crash

---

## Integration Tests

### Telegram Integration
- [ ] Telegram bot sends test message
  ```bash
  pytest tests/integration/test_full_system.py::test_telegram_notifications -v --testnet
  ```

- [ ] Receive test message on phone
- [ ] Message formatting looks correct
- [ ] No rate limiting errors

### Bot Initialization
- [ ] Bot initializes all components
  ```bash
  pytest tests/integration/test_full_system.py::test_bot_initialization -v --testnet
  ```

- [ ] Web3 connection established
- [ ] DEX instances created
- [ ] Risk manager initialized
- [ ] Transaction manager initialized
- [ ] Emergency shutdown system ready
- [ ] No initialization errors

---

## Risk Management Tests

### Position Size Limits
- [ ] Position size limits configured
- [ ] Limits are enforced (check logs when simulating large trade)
- [ ] Bot rejects trades exceeding limits

### Loss Limits
- [ ] Daily loss limit configured
- [ ] Weekly loss limit calculated correctly
- [ ] Bot stops trading when limit reached (simulate by setting very low limit)

### Circuit Breaker
- [ ] Circuit breaker triggers after consecutive losses
- [ ] Cooldown period works correctly
- [ ] Trading resumes after cooldown

### Emergency Shutdown
- [ ] Can trigger emergency shutdown manually
- [ ] All trading stops immediately
- [ ] Telegram alert sent
- [ ] Can reset with admin code
- [ ] System resumes normal operation after reset

---

## Trading Tests (MANUAL - COSTS GAS)

### ⚠️ Warning: These tests execute real transactions and cost gas

### Token Approval
- [ ] Can approve WETH for DEX router
- [ ] Can approve USDC for DEX router
- [ ] Approval transactions confirm on blockchain
- [ ] Check on PolygonScan: https://mumbai.polygonscan.com/

### Single DEX Swap
- [ ] Can execute small swap on QuickSwap (0.001 WETH → USDC)
- [ ] Transaction succeeds
- [ ] Correct amounts received (accounting for slippage)
- [ ] Gas cost reasonable (< 0.01 MATIC)
- [ ] Slippage within expected range

### Full Arbitrage Trade
- [ ] Can execute buy on one DEX
- [ ] Can execute sell on another DEX
- [ ] Net profit/loss calculated correctly
- [ ] Gas costs tracked
- [ ] Telegram notification sent with results

### Transaction Handling
- [ ] Failed transactions handled gracefully
- [ ] Error messages are clear
- [ ] System recovers from failures
- [ ] Nonce management works correctly

---

## Error Handling Tests

### Network Errors
- [ ] Handles RPC connection failures
  - Test: Disconnect internet briefly
- [ ] Retries failed requests
- [ ] Falls back to backup RPC (if configured)
- [ ] Logs errors appropriately

### Insufficient Balance
- [ ] Detects insufficient MATIC for gas
- [ ] Detects insufficient token balance
- [ ] Prevents trade execution
- [ ] Sends alert to Telegram

### Transaction Failures
- [ ] Handles transaction reversion
- [ ] Handles timeout errors
- [ ] Doesn't lose funds on failed trades
- [ ] Updates statistics correctly

### Recovery
- [ ] Bot recovers from crashes
- [ ] State is preserved (or safely reset)
- [ ] Can resume monitoring after error

---

## Long-Running Tests

### Short Run (1 Hour)
- [ ] Bot runs for 1 hour without crashing
  ```bash
  # Run with timeout
  timeout 3600 python -m src.bot.main
  ```

- [ ] No memory leaks (check with `top` or `htop`)
- [ ] Logs are clean (no repeated errors)
- [ ] Telegram notifications working
- [ ] Statistics tracking correctly

### Overnight Run (8 Hours)
- [ ] Bot runs overnight without issues
- [ ] Still responsive in morning
- [ ] Log file size reasonable (< 100 MB)
- [ ] No database corruption (if using DB)
- [ ] Statistics accumulated correctly

### Error Recovery
- [ ] Kill bot process, restart - recovers correctly
- [ ] Simulate RPC failure - reconnects automatically
- [ ] Remove internet - waits and reconnects

---

## Performance Tests

### Response Times
- [ ] Opportunity detection < 2 seconds per check
- [ ] Price fetching < 5 seconds total
- [ ] Trade execution < 10 seconds
- [ ] System responsive under load

### Resource Usage
- [ ] CPU usage < 50% average
- [ ] Memory usage < 500 MB
- [ ] Disk I/O reasonable
- [ ] Network bandwidth acceptable

### Rate Limiting
- [ ] Not hitting RPC rate limits
- [ ] Not hitting DEX query limits
- [ ] Not hitting Telegram rate limits
- [ ] Delays between checks appropriate

---

## Data Validation

### Logging
- [ ] All trades logged to file
- [ ] Errors logged with stack traces
- [ ] Timestamps accurate
- [ ] Log rotation working (if configured)

### Statistics
- [ ] Opportunities found counted correctly
- [ ] Trades executed tracked
- [ ] Success rate calculated correctly
- [ ] Profit/loss summed accurately

### Alerts
- [ ] Emergency shutdown alerts sent
- [ ] Loss limit alerts sent
- [ ] Circuit breaker alerts sent
- [ ] Trade completion alerts sent

---

## Security Checks

### Credentials
- [ ] Private keys not logged
- [ ] Private keys not in error messages
- [ ] Environment variables loaded securely
- [ ] No sensitive data in Telegram messages

### Access Control
- [ ] Emergency shutdown requires admin code
- [ ] Can't reset without correct code
- [ ] Invalid codes rejected

---

## Final Validation

### Pre-Mainnet Checklist
- [ ] All automated tests passing
- [ ] Manual testing checklist complete
- [ ] No critical errors in 24-hour run
- [ ] Telegram notifications reliable
- [ ] Risk management validated
- [ ] Emergency shutdown tested
- [ ] Comfortable with system behavior
- [ ] Logs reviewed for any concerns

### Documentation
- [ ] README updated
- [ ] Configuration documented
- [ ] Known issues documented
- [ ] Deployment guide complete

---

## Test Execution Log

Date: ___________

Tester: ___________

### Results Summary
- Total tests run: _____
- Tests passed: _____
- Tests failed: _____
- Issues found: _____

### Critical Issues Found
1. ___________________________________________
2. ___________________________________________
3. ___________________________________________

### Non-Critical Issues
1. ___________________________________________
2. ___________________________________________

### Notes
___________________________________________
___________________________________________
___________________________________________

### Sign-Off
- [ ] System ready for 48-hour testnet run (Task 7.1)
- [ ] System ready for mainnet deployment (Task 7.2)

Signature: ___________________ Date: ___________

---

## Quick Test Commands

```bash
# Run all integration tests (safe - no trades)
pytest tests/integration/test_full_system.py -v --testnet

# Test RPC connection
pytest tests/integration/test_full_system.py::test_rpc_connection -v --testnet

# Test account balance
pytest tests/integration/test_full_system.py::test_account_balance -v --testnet

# Test bot initialization
pytest tests/integration/test_full_system.py::test_bot_initialization -v --testnet

# Run bot for 10 minutes (manual test)
timeout 600 python -m src.bot.main

# Check logs for errors
grep -i "error\|exception\|failed" arbitrage_bot.log | tail -20

# Monitor bot in real-time
tail -f arbitrage_bot.log
```

---

## Support

If you encounter issues during testing:

1. Check the logs: `tail -f arbitrage_bot.log`
2. Verify configuration: Ensure ENVIRONMENT=testnet
3. Check Mumbai testnet status: https://mumbai.polygonscan.com/
4. Verify RPC endpoint is working
5. Ensure sufficient testnet MATIC for gas

**Remember: This is testnet - it's OKAY to make mistakes here. That's what it's for!**
