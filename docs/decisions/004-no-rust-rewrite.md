# ADR-004: No Rust Rewrite

## Status
Accepted

## Context
Flash loan arbitrage is highly competitive. Many successful MEV bots use Rust or C++ for maximum speed. The question: should this bot be rewritten in Rust for better performance?

## Analysis

Profiling the `OpportunityDetector` scan loop shows:

| Operation | % of execution time | Bottleneck type |
|-----------|-------------------|----------------|
| RPC network calls (quotes) | 90-95% | Network I/O |
| ABI encoding/decoding | 3-5% | CPU |
| Profit calculation | 1-2% | CPU |
| Transaction signing | <1% | CPU |

The bot spends 90-95% of its time waiting for RPC responses. Rust's advantage is in CPU-bound computation, which accounts for only 5-10% of execution time.

## Decision
Keep the bot in Python. Address the I/O bottleneck through Multicall3 batching (see ADR-003), which reduces 600+ sequential RPC calls to ~10-20 batched calls — a 30-50x improvement achievable in Python in days, not months.

## Alternatives Considered

| Approach | Speedup | LOE | Verdict |
|----------|---------|-----|---------|
| Rust rewrite (full) | ~2-3x overall | 3-6 months | Not justified — I/O bound |
| Rust hot path only | ~1.1x overall | 1-2 months | Minimal impact on 5% of time |
| Multicall3 batching (Python) | 30-50x on detection | 1-2 days | Chosen — addresses actual bottleneck |
| asyncio + WebSocket (Python) | Additional 2-5x | 1-2 weeks | Future option, not required now |

## Consequences
- **Positive**: No learning curve for Rust + ethers-rs/alloy ecosystem.
- **Positive**: Faster iteration — Python changes deploy instantly, no compile step.
- **Positive**: All existing tests, tooling, and infrastructure remain valid.
- **Negative**: Python GIL limits true CPU parallelism (irrelevant — bottleneck is I/O).
- **Negative**: Higher memory usage than Rust (acceptable for a single-instance bot).
