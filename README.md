# Polygon Arbitrage Trading Bot

Automated arbitrage trading bot for Polygon network monitoring Uniswap V3, SushiSwap, and QuickSwap for profitable trading opportunities.

## Features

✅ **Multi-DEX Arbitrage** - Monitors 3 major DEXes simultaneously
✅ **Comprehensive Risk Management** - Position limits, loss limits, circuit breakers
✅ **Slippage Protection** - Prevents losses from price impact
✅ **Emergency Shutdown** - Multiple safety triggers
✅ **Performance Optimized** - <2s opportunity detection
✅ **Full Testing** - >90% code coverage
✅ **Telegram Alerts** - Real-time notifications

## Quick Start

### Prerequisites

- Python 3.9+
- Polygon wallet with MATIC
- Telegram bot (optional but recommended)

### Installation

1. **Clone repository:**
```bash
git clone https://github.com/yourusername/arbitrage-bot.git
cd arbitrage-bot
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Configure environment:**
```bash
cp .env.example .env
# Edit .env with your settings
```

4. **Deploy to testnet:**
```bash
./scripts/deploy_testnet.sh
```

5. **Run the bot:**
```bash
python -m src.bot.main
```

## Configuration

See [docs/CONFIGURATION.md](docs/CONFIGURATION.md) for detailed configuration options.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) - System design and components
- [Deployment Guide](docs/DEPLOYMENT.md) - Step-by-step deployment
- [Configuration Reference](docs/CONFIGURATION.md) - All config options
- [Troubleshooting](docs/TROUBLESHOOTING.md) - Common issues and solutions
- [Manual Testing Guide](docs/TESTNET_MANUAL_TESTING.md) - Testnet testing checklist

## Safety & Risk Management

This bot includes comprehensive risk management:
- Position size limits
- Daily/weekly loss limits
- Circuit breakers for consecutive losses
- Slippage protection
- Emergency shutdown system

**IMPORTANT:** Always start on testnet and with small positions on mainnet.

## Performance

Target performance metrics:
- Opportunity detection: <2 seconds
- Trade execution: <5 seconds
- RPC calls: <100 per minute
- Memory usage: <500MB

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest --cov=src --cov-report=html

# Integration tests (requires testnet)
pytest tests/integration/ -v --testnet
```

## Monitoring

Generate performance reports:
```bash
./scripts/generate_report.py data/metrics.json
```

Monitor bot health:
```bash
./scripts/monitor_bot.py
```

## Scripts

- `scripts/deploy_testnet.sh` - Deploy to Mumbai testnet
- `scripts/deploy_mainnet.sh` - Deploy to Polygon mainnet (interactive)
- `scripts/check_balances.py` - Check wallet token balances
- `scripts/setup_testnet.py` - Interactive testnet setup guide
- `scripts/monitor_bot.py` - Check bot health and status
- `scripts/backup_config.sh` - Backup configuration and logs
- `scripts/generate_report.py` - Generate performance report
- `scripts/benchmark.py` - Run performance benchmarks

## Project Structure

```
arbitrage-bot/
├── src/
│   ├── bot/              # Main bot logic
│   │   ├── main.py       # Main orchestrator
│   │   ├── arbitrage.py  # Arbitrage logic
│   │   ├── config.py     # Configuration management
│   │   └── telegram_bot.py
│   ├── dex/              # DEX adapters
│   │   ├── quickswap.py
│   │   ├── sushiswap.py
│   │   └── uniswap_v3.py
│   └── utils/            # Utilities
│       ├── risk_manager.py
│       ├── transaction_manager.py
│       ├── metrics_collector.py
│       └── performance_monitor.py
├── tests/                # Test suite
├── scripts/              # Deployment and management scripts
├── config/               # Configuration files
├── docs/                 # Documentation
└── logs/                 # Log files
```

## Support

- Issues: [GitHub Issues](https://github.com/yourusername/arbitrage-bot/issues)
- Discussions: [GitHub Discussions](https://github.com/yourusername/arbitrage-bot/discussions)

## Disclaimer

This software is for educational purposes. Trading involves risk. Use at your own risk. Always start with testnet and small amounts on mainnet.

## License

MIT License - see [LICENSE](LICENSE) for details
