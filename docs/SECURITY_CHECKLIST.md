# Security Checklist

Pre-production security gate. Every item must be verified before mainnet deployment.

## Smart Contracts

- [ ] All admin functions are `onlyOwner`
- [ ] `ReentrancyGuard` on all state-changing external functions
- [ ] `Pausable` — emergency stop on all execution paths
- [ ] Flash loan callback verifies `msg.sender == POOL` and `initiator == address(this)`
- [ ] Balance checks before/after each operation (no silent failures)
- [ ] DEX adapters require registration via `registeredAdapters` mapping
- [ ] `minProfit` enforced — reverts if profit below threshold
- [ ] `deadline` enforced — reverts on expired transactions
- [ ] `SafeERC20` used for all token transfers
- [ ] `forceApprove` used instead of `approve` (handles non-standard tokens)
- [ ] No unbounded loops in contract code
- [ ] Slither static analysis passes with no high/medium findings
- [ ] Foundry fuzz tests run with 10,000+ runs (CI profile)

## Python Bot

- [ ] Private keys stored in encrypted keystore (`python -m src.utils.key_manager create`)
- [ ] No secrets in `.env` files — only references to keystore paths
- [ ] No secrets logged (private keys, keystore passwords filtered)
- [ ] HTTP timeouts on all RPC calls (`WEB3_HTTP_TIMEOUT` env var)
- [ ] Circuit breaker limits consecutive losses (`MAX_CONSECUTIVE_LOSSES`)
- [ ] Daily loss limit enforced (`DAILY_LOSS_LIMIT_USD`)
- [ ] Max position size enforced (`MAX_POSITION_SIZE_USD`)
- [ ] Transaction simulation (`eth_call`) before every live execution
- [ ] Dry-run mode enabled by default (`DRY_RUN=true`)
- [ ] Admin Telegram commands require HMAC verification

## Infrastructure

- [ ] Docker containers run as non-root user (`botuser`)
- [ ] `.dockerignore` excludes secrets, tests, build artifacts
- [ ] GitHub secret scanning enabled (Gitleaks in CI)
- [ ] Dependency vulnerability scanning (`pip-audit` in CI)
- [ ] Python security scanning (`bandit` in CI)
- [ ] GitHub environment protection rules on `production` environment
- [ ] Production deployments require manual approval
- [ ] Database credentials rotated from defaults
- [ ] Redis password set and not default

## Pre-Mainnet Deployment

- [ ] 48+ hours of testnet dry-run with no errors
- [ ] All tests pass (Python 462+ tests, Foundry 80+ tests)
- [ ] Security scan clean (bandit, Slither, pip-audit, Gitleaks)
- [ ] Contract verified on block explorer
- [ ] Monitoring and alerts configured (Prometheus + Telegram)
- [ ] Runbook reviewed by operator
- [ ] Emergency shutdown procedure tested
- [ ] Wallet funded with sufficient gas tokens
- [ ] Flash loan contracts funded (if required)
