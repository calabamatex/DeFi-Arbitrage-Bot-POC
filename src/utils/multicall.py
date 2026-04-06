"""
Multicall3 for batching RPC requests.

Reduces hundreds of sequential RPC calls to a handful of batched calls.
Multicall3 is deployed at the same address on all major EVM chains.
"""

from web3 import Web3
from web3.contract import Contract
from typing import List, Tuple, Optional, Any
import logging

logger = logging.getLogger(__name__)

# Multicall3 is deployed on many chains at this address
MULTICALL_ADDRESS = "0xcA11bde05977b3631167028862bE2a173976CA11"

MULTICALL_ABI = [
    {
        "inputs": [
            {
                "components": [
                    {"internalType": "address", "name": "target", "type": "address"},
                    {"internalType": "bytes", "name": "callData", "type": "bytes"},
                ],
                "internalType": "struct Multicall3.Call[]",
                "name": "calls",
                "type": "tuple[]",
            }
        ],
        "name": "aggregate",
        "outputs": [
            {"internalType": "uint256", "name": "blockNumber", "type": "uint256"},
            {"internalType": "bytes[]", "name": "returnData", "type": "bytes[]"},
        ],
        "stateMutability": "payable",
        "type": "function",
    },
    {
        "inputs": [
            {
                "components": [
                    {"internalType": "address", "name": "target", "type": "address"},
                    {
                        "internalType": "bool",
                        "name": "allowFailure",
                        "type": "bool",
                    },
                    {"internalType": "bytes", "name": "callData", "type": "bytes"},
                ],
                "internalType": "struct Multicall3.Call3[]",
                "name": "calls",
                "type": "tuple[]",
            }
        ],
        "name": "aggregate3",
        "outputs": [
            {
                "components": [
                    {"internalType": "bool", "name": "success", "type": "bool"},
                    {"internalType": "bytes", "name": "returnData", "type": "bytes"},
                ],
                "internalType": "struct Multicall3.Result[]",
                "name": "returnData",
                "type": "tuple[]",
            }
        ],
        "stateMutability": "payable",
        "type": "function",
    },
]


class Multicall:
    """Batch multiple RPC calls into a single request via Multicall3."""

    # Maximum calls per batch to avoid gas limit issues
    MAX_BATCH_SIZE = 100

    def __init__(self, web3: Web3, multicall_address: str = MULTICALL_ADDRESS):
        self.web3 = web3
        self.multicall_address = multicall_address
        self.contract: Optional[Contract] = None

        try:
            self.contract = web3.eth.contract(
                address=web3.to_checksum_address(multicall_address),
                abi=MULTICALL_ABI,
            )
            logger.info(f"Multicall3 initialized at {multicall_address}")
        except Exception as e:
            logger.warning(f"Multicall3 contract not available: {e}")

    def is_available(self) -> bool:
        return self.contract is not None

    def aggregate3(
        self, calls: List[Tuple[str, bytes, bool]]
    ) -> List[Tuple[bool, bytes]]:
        """
        Execute multiple calls with individual failure handling.

        Args:
            calls: List of (target_address, call_data, allow_failure) tuples

        Returns:
            List of (success, return_data) tuples
        """
        if not self.contract:
            raise ValueError("Multicall3 contract not available")

        formatted_calls = [
            {"target": target, "allowFailure": allow_failure, "callData": data}
            for target, data, allow_failure in calls
        ]

        logger.debug(f"Multicall3 aggregate3: {len(calls)} calls")

        results = self.contract.functions.aggregate3(formatted_calls).call()

        logger.debug(f"Multicall3 returned {len(results)} results")
        return [(r["success"], r["returnData"]) for r in results]

    def aggregate3_chunked(
        self, calls: List[Tuple[str, bytes, bool]]
    ) -> List[Tuple[bool, bytes]]:
        """
        Execute calls in chunks to avoid gas limit issues.

        Splits large batches into MAX_BATCH_SIZE chunks and concatenates results.
        """
        if len(calls) <= self.MAX_BATCH_SIZE:
            return self.aggregate3(calls)

        all_results = []
        for i in range(0, len(calls), self.MAX_BATCH_SIZE):
            chunk = calls[i : i + self.MAX_BATCH_SIZE]
            results = self.aggregate3(chunk)
            all_results.extend(results)

        return all_results


# ---------------------------------------------------------------------------
# ABI encoding helpers for common DEX quote calls
# ---------------------------------------------------------------------------

def encode_v3_quote(
    web3: Web3,
    quoter_contract: Contract,
    token_in: str,
    token_out: str,
    amount_in: int,
    fee: int,
) -> bytes:
    """
    Encode a Uniswap V3 QuoterV2.quoteExactInputSingle call.

    Returns raw calldata bytes suitable for Multicall3.
    """
    params = {
        "tokenIn": token_in,
        "tokenOut": token_out,
        "amountIn": amount_in,
        "fee": fee,
        "sqrtPriceLimitX96": 0,
    }
    return quoter_contract.functions.quoteExactInputSingle(params)._encode_transaction_data()


def encode_v2_amounts_out(
    web3: Web3,
    router_contract: Contract,
    amount_in: int,
    path: List[str],
) -> bytes:
    """
    Encode a UniswapV2 Router.getAmountsOut call.

    Returns raw calldata bytes suitable for Multicall3.
    """
    return router_contract.functions.getAmountsOut(amount_in, path)._encode_transaction_data()


def decode_v3_quote_result(result_data: bytes) -> Optional[int]:
    """
    Decode the return data from quoteExactInputSingle.

    Returns amountOut or None if data is invalid.
    """
    if not result_data or len(result_data) < 32:
        return None
    try:
        # quoteExactInputSingle returns (uint256 amountOut, uint160, uint32, uint256)
        # First 32 bytes = amountOut
        amount_out = int.from_bytes(result_data[:32], "big")
        return amount_out if amount_out > 0 else None
    except Exception:
        return None


def decode_v2_amounts_out_result(result_data: bytes) -> Optional[int]:
    """
    Decode the return data from getAmountsOut.

    Returns the final output amount or None if data is invalid.
    """
    if not result_data or len(result_data) < 128:
        return None
    try:
        # getAmountsOut returns uint256[] (dynamic array)
        # Layout: offset (32) + length (32) + element0 (32) + element1 (32)
        offset = int.from_bytes(result_data[:32], "big")
        length = int.from_bytes(result_data[offset : offset + 32], "big")
        if length < 2:
            return None
        # Last element is the output amount
        last_offset = offset + 32 + (length - 1) * 32
        amount_out = int.from_bytes(result_data[last_offset : last_offset + 32], "big")
        return amount_out if amount_out > 0 else None
    except Exception:
        return None
