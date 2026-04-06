# ADR-003: Multicall3 Batching for Price Queries

## Status
Accepted

## Context
The `OpportunityDetector` scans trading pairs by querying Uniswap V3 and QuickSwap for price quotes. For each pair, it makes 8 sequential RPC calls:

- 3 Uniswap V3 `quoteExactInputSingle` calls (one per fee tier: 500, 3000, 10000 bps)
- 1 QuickSwap `getAmountsOut` call
- Per direction (2 directions per pair)

With 50 trading pairs, this produces 400+ sequential RPC calls per scan. Each call has 50-200ms network latency, resulting in 30-120 second scan times.

## Decision
Use Multicall3 (`0xcA11bde05977b3631167028862bE2a173976CA11`, deployed on all major EVM chains) to batch multiple view calls into a single RPC request.

Implementation in `src/utils/multicall.py`:
- `aggregate3()` batches calls with `allowFailure=True` (illiquid pairs revert gracefully)
- `aggregate3_chunked()` splits large batches into chunks of 100 to avoid gas limits
- Encoding helpers (`encode_v3_quote`, `encode_v2_amounts_out`) and decoders (`decode_v3_quote_result`, `decode_v2_amounts_out_result`) handle ABI encoding/decoding

The `OpportunityDetector.calculate_arbitrage_batched()` method batches all 8 quote calls for a pair into 2 Multicall3 calls (batch 1: independent quotes, batch 2: dependent quotes using batch 1 results).

## Metrics

| Metric | Before (Sequential) | After (Multicall3) |
|--------|--------------------|--------------------|
| RPC calls per pair | 8 | 2 |
| RPC calls for 50 pairs | 400+ | ~10-20 |
| Theoretical scan time | 60-120s | 2-5s |
| Reduction factor | — | 30-50x |

## Consequences
- **Positive**: Dramatically faster scanning — competitive with faster bots on detection latency.
- **Positive**: Fewer RPC calls reduces provider rate-limiting risk and cost.
- **Positive**: Falls back to sequential calls if Multicall3 is unavailable.
- **Negative**: More complex code — batch encoding/decoding requires careful ABI handling.
- **Negative**: All calls in a batch see the same block state (this is actually desirable for consistency).
