# Production Checklist

Every item must be completed before switching from testnet dry-run to mainnet live execution.

## 1. Testnet Validation

- [ ] Bot ran on Polygon Amoy for 48+ hours in dry-run mode
- [ ] Bot ran on Arbitrum Sepolia for 48+ hours in dry-run mode
- [ ] No crashes or unhandled exceptions during testnet run
- [ ] Smoke test passes: `python scripts/testnet_smoke_test.py --chain polygon_amoy`
- [ ] Smoke test passes: `python scripts/testnet_smoke_test.py --chain arbitrum_sepolia`
- [ ] Config validation passes: `python scripts/validate_config.py`

## 2. Test Suite

- [ ] All Python tests pass: `pytest tests/ -v` (469+ tests)
- [ ] All Foundry tests pass: `forge test -vvv` (80+ tests)
- [ ] Code coverage >= 80%: `pytest --cov=src --cov-fail-under=80`
- [ ] Foundry fuzz tests pass with 10,000 runs: `forge test --fuzz-runs 10000`

## 3. Security

- [ ] Bandit scan clean: `bandit -r src/ -c .bandit.yml`
- [ ] Dependency audit clean: `pip-audit -r requirements.txt`
- [ ] Slither scan clean (no high/medium): `slither contracts/`
- [ ] Gitleaks scan clean: no secrets in repo history
- [ ] Private key stored in encrypted keystore (not `.env`)
- [ ] Contracts verified on block explorer (Polygonscan / Arbiscan)
- [ ] All [Security Checklist](SECURITY_CHECKLIST.md) items verified

## 4. Smart Contracts

- [ ] Contracts deployed and verified on target mainnet
- [ ] Owner set to correct multisig/EOA
- [ ] DEX adapters registered via `registerAdapter()`
- [ ] Flash loan callback verifies `msg.sender == POOL`
- [ ] `minProfit` parameter set to production value
- [ ] Contract paused initially (unpause after all checks pass)

## 5. Configuration

- [ ] `EXECUTION_MODE=mainnet` in `.env`
- [ ] `DRY_RUN=false` — only set after all other items complete
- [ ] `MIN_PROFIT_USD` set to production threshold (e.g., 10-50)
- [ ] `MAX_GAS_PRICE_GWEI` set to reasonable limit (e.g., 100)
- [ ] `DAILY_LOSS_LIMIT_USD` configured
- [ ] `MAX_CONSECUTIVE_LOSSES` configured
- [ ] Contract addresses set:
  - [ ] `FLASH_LOAN_ARBITRAGE_ADDRESS`
  - [ ] `UNISWAP_V3_ADAPTER_ADDRESS`
  - [ ] `UNISWAP_V2_ADAPTER_ADDRESS`
  - [ ] `CURVE_ADAPTER_ADDRESS` (if using Curve)
  - [ ] `BALANCER_FLASH_LOAN_ADDRESS` (if using Balancer)
  - [ ] `FLASH_LOAN_LIQUIDATOR_ADDRESS` (if liquidation enabled)

## 6. Infrastructure

- [ ] Docker image builds successfully: `make docker-build`
- [ ] Database migrations applied: `make migrate`
- [ ] PostgreSQL running with non-default credentials
- [ ] Redis running with non-default password
- [ ] Health endpoint responding: `curl http://localhost:8080/health`
- [ ] Metrics endpoint responding: `curl http://localhost:8080/metrics`
- [ ] Docker containers run as non-root user

## 7. Monitoring & Alerts

- [ ] Prometheus scraping bot metrics
- [ ] Alert rules configured (BotDown, CircuitBreaker, NegativePnL)
- [ ] Telegram alerts tested and receiving messages
- [ ] Log rotation configured (50MB max, 10 backups)

## 8. Funding

- [ ] Bot wallet funded with sufficient gas tokens (MATIC/ETH)
- [ ] Minimum gas balance: 0.5 MATIC (Polygon) or 0.01 ETH (Arbitrum)
- [ ] Flash loan contracts do NOT require pre-funding (Aave/Balancer)

## 9. Operational Readiness

- [ ] [Operations Runbook](OPERATIONS_RUNBOOK.md) reviewed
- [ ] [Troubleshooting Guide](TROUBLESHOOTING.md) reviewed
- [ ] Emergency shutdown procedure tested: pause contracts, stop bot
- [ ] Rollback plan documented: previous Docker image tag noted
- [ ] On-call rotation established (if team)

## 10. Go / No-Go Decision

| Criteria | Status | Notes |
|----------|--------|-------|
| Testnet 48h run | | |
| All tests pass | | |
| Security scans clean | | |
| Contracts verified | | |
| Monitoring active | | |
| Wallet funded | | |
| Runbook reviewed | | |

**Decision:** [ ] GO / [ ] NO-GO

**Date:** _______________
**Approved by:** _______________

## Post-Deployment (First 24 Hours)

- [ ] Monitor health endpoint every 15 minutes
- [ ] Check P&L after first trade
- [ ] Verify circuit breaker is NOT active
- [ ] Review first 10 transactions on block explorer
- [ ] Confirm Telegram alerts are being received
- [ ] Check memory/CPU usage stays within bounds
