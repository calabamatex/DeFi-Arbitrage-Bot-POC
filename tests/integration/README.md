# Integration Tests

## Overview

These tests validate the complete arbitrage bot system on Mumbai testnet with real blockchain interactions.

⚠️ **WARNING**: These tests make REAL transactions on testnet and cost gas (testnet MATIC).

## Prerequisites

### 1. Testnet Funds
- Get testnet MATIC from: https://faucet.polygon.technology/
- Need at least 5 MATIC for testing
- Get testnet tokens (WETH, USDC, etc.) by swapping on Mumbai DEXes

### 2. Configuration

Create/update `.env` file:
```bash
PRIVATE_KEY=0x...  # Use TESTNET wallet only!
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
ENVIRONMENT=testnet  # CRITICAL!
POLYGON_RPC_URL=https://rpc-mumbai.maticvigil.com/
```

⚠️ **NEVER use your mainnet wallet for testnet testing!**

### 3. Verify Configuration

```bash
# Check environment is testnet
python -c "from src.bot.config import load_config; _, env, _, _ = load_config(); print(f'Environment: {env}')"

# Should output: Environment: testnet
```

## Running Tests

### Run All Safe Tests (No Transactions)

```bash
# Run all integration tests
pytest tests/integration/test_full_system.py -v --testnet

# Run without --testnet flag - all tests will skip
pytest tests/integration/test_full_system.py -v
```

### Run Individual Tests

```bash
# Test RPC connection
pytest tests/integration/test_full_system.py::test_rpc_connection -v --testnet

# Test account balance
pytest tests/integration/test_full_system.py::test_account_balance -v --testnet

# Test DEX initialization
pytest tests/integration/test_full_system.py::test_dex_initialization -v --testnet

# Test price fetching
pytest tests/integration/test_full_system.py::test_fetch_real_prices -v --testnet

# Test Telegram
pytest tests/integration/test_full_system.py::test_telegram_notifications -v --testnet

# Test bot initialization
pytest tests/integration/test_full_system.py::test_bot_initialization -v --testnet
```

## Test Descriptions

### Test 1: RPC Connection
- Verifies connection to Mumbai testnet
- Checks chain ID is 80001
- Gets current block number
- **Cost**: Free

### Test 2: Account Balance
- Checks account has sufficient MATIC
- Requires at least 0.1 MATIC
- **Cost**: Free

### Test 3: DEX Initialization
- Initializes QuickSwap and SushiSwap adapters
- Verifies router addresses
- **Cost**: Free

### Test 4: Fetch Real Prices
- Fetches WETH prices from all DEXes
- May return 0 if no liquidity on testnet
- **Cost**: Free (read-only)

### Test 5: Arbitrage Detection
- Tests arbitrage detection structure
- Checks multiple token pairs
- **Cost**: Free

### Test 6: Telegram Notifications
- Sends test message to your Telegram
- Check your phone to verify!
- **Cost**: Free

### Test 7: Small Trade Execution (SKIPPED)
- Would execute a small swap on testnet
- ⚠️ **Costs gas** - run manually
- Currently skipped by default

### Test 8: Bot Initialization
- Initializes complete bot system
- Verifies all components
- **Cost**: Free

### Test 9: One Hour Run (SKIPPED)
- Would run bot for 1 hour
- Run manually when ready
- Currently skipped by default

## Manual Testing

For tests that execute transactions (cost gas), run manually:

```bash
# Run the bot for a short period
timeout 600 python -m src.bot.main

# Run with monitoring
tail -f arbitrage_bot.log
```

## Safety Checklist

Before running integration tests:

- [ ] Using testnet wallet (NOT mainnet)
- [ ] ENVIRONMENT=testnet in .env
- [ ] Sufficient testnet MATIC (5+)
- [ ] Comfortable losing testnet funds
- [ ] Verified chain ID is 80001

## Troubleshooting

### "Cannot connect to RPC"
- Check RPC URL in .env
- Try alternate Mumbai RPC: https://matic-mumbai.chainstacklabs.com

### "Insufficient balance"
- Get more testnet MATIC from faucet
- Wait for faucet cooldown (24 hours)

### "Private key not found"
- Check PRIVATE_KEY in .env file
- Ensure no spaces or quotes around key

### "Telegram message failed"
- Verify TELEGRAM_BOT_TOKEN is correct
- Verify TELEGRAM_CHAT_ID is correct
- Check you've messaged the bot first

## Expected Results

When all tests pass:

```
tests/integration/test_full_system.py::test_rpc_connection PASSED
tests/integration/test_full_system.py::test_account_balance PASSED
tests/integration/test_full_system.py::test_dex_initialization PASSED
tests/integration/test_full_system.py::test_fetch_real_prices PASSED
tests/integration/test_full_system.py::test_arbitrage_detection PASSED
tests/integration/test_full_system.py::test_telegram_notifications PASSED
tests/integration/test_full_system.py::test_small_trade_execution SKIPPED
tests/integration/test_full_system.py::test_bot_initialization PASSED
tests/integration/test_full_system.py::test_one_hour_run SKIPPED

============================== 7 passed, 2 skipped ==============================
```

## Next Steps

After integration tests pass:

1. Review the manual testing checklist: `docs/TESTNET_MANUAL_TESTING.md`
2. Complete manual testing scenarios
3. Run 48-hour testnet validation (Task 7.1)
4. Prepare for mainnet deployment (Task 7.2)

## Support

If you encounter issues:

1. Check logs: `tail -f arbitrage_bot.log`
2. Verify testnet status: https://mumbai.polygonscan.com/
3. Check configuration matches testnet addresses
4. Ensure sufficient testnet funds

**Remember**: Testnet is for learning! Failures are expected and valuable.
