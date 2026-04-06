# ADR-001: Flash Loans Over Trading Capital

## Status
Accepted

## Context
Arbitrage bots traditionally require significant upfront capital to execute trades. This creates barriers to entry and exposes capital to smart contract risk, exchange risk, and opportunity cost.

## Decision
Use Aave V3 flash loans (0.05% fee) and Balancer V2 flash loans (0% fee) to execute all arbitrage and liquidation trades with zero upfront capital. The `FlashLoanSelector` in `src/flash_loan_providers.py` automatically routes through Balancer when the token is available there (saving the 0.05% fee), falling back to Aave V3.

## Consequences
- **Positive**: Zero capital requirement. No funds at risk between trades. No opportunity cost on idle capital.
- **Positive**: Atomicity — if any step fails, the entire transaction reverts and no funds are lost.
- **Negative**: 0.05% fee per trade (Aave) eats into already-thin margins. Mitigated by preferring Balancer (0% fee).
- **Negative**: Flash loan providers can be paused or drained, making the bot inoperable. No fallback to capital-based trading exists.
