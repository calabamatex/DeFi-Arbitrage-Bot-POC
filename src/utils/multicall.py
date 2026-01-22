"""Multicall for batching RPC requests."""

from web3 import Web3
from typing import List, Tuple, Any
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
    """Batch multiple RPC calls into a single request."""

    def __init__(self, web3: Web3, multicall_address: str = MULTICALL_ADDRESS):
        """
        Initialize multicall.

        Args:
            web3: Web3 instance
            multicall_address: Multicall3 contract address
        """
        self.web3 = web3
        self.multicall_address = multicall_address

        try:
            self.contract = web3.eth.contract(
                address=multicall_address, abi=MULTICALL_ABI
            )
            logger.info(f"Multicall initialized at {multicall_address}")
        except Exception as e:
            logger.warning(f"Multicall contract not available: {e}")
            self.contract = None

    async def aggregate(
        self, calls: List[Tuple[str, bytes]]
    ) -> Tuple[int, List[bytes]]:
        """
        Execute multiple calls in a single RPC request.

        All calls must succeed or the entire multicall reverts.

        Args:
            calls: List of (target_address, call_data) tuples

        Returns:
            Tuple of (block_number, list of return data bytes)
        """
        if not self.contract:
            raise ValueError("Multicall contract not available")

        # Format calls
        formatted_calls = [
            {"target": target, "callData": data} for target, data in calls
        ]

        logger.debug(f"Multicall aggregating {len(calls)} calls")

        # Execute multicall
        try:
            block_number, return_data = self.contract.functions.aggregate(
                formatted_calls
            ).call()

            logger.debug(
                f"Multicall successful: block {block_number}, {len(return_data)} results"
            )
            return block_number, return_data

        except Exception as e:
            logger.error(f"Multicall aggregate failed: {e}")
            raise

    async def aggregate3(
        self, calls: List[Tuple[str, bytes, bool]]
    ) -> List[Tuple[bool, bytes]]:
        """
        Execute multiple calls with individual failure handling.

        Each call can succeed or fail independently.

        Args:
            calls: List of (target_address, call_data, allow_failure) tuples

        Returns:
            List of (success, return_data) tuples
        """
        if not self.contract:
            raise ValueError("Multicall contract not available")

        # Format calls
        formatted_calls = [
            {"target": target, "allowFailure": allow_failure, "callData": data}
            for target, data, allow_failure in calls
        ]

        logger.debug(f"Multicall aggregate3: {len(calls)} calls")

        # Execute multicall
        try:
            results = self.contract.functions.aggregate3(formatted_calls).call()

            logger.debug(f"Multicall3 successful: {len(results)} results")

            # Convert to tuple format
            return [(result["success"], result["returnData"]) for result in results]

        except Exception as e:
            logger.error(f"Multicall aggregate3 failed: {e}")
            raise

    def is_available(self) -> bool:
        """Check if multicall is available."""
        return self.contract is not None


async def batch_get_prices(
    web3: Web3,
    dex_routers: List[str],
    token_addresses: List[str],
    multicall: Multicall,
) -> List[bytes]:
    """
    Batch multiple getAmountsOut calls using multicall.

    Args:
        web3: Web3 instance
        dex_routers: List of DEX router addresses
        token_addresses: List of token pair addresses
        multicall: Multicall instance

    Returns:
        List of encoded results
    """
    # Build calls
    calls = []

    # Example: getAmountsOut for multiple DEXes
    # This would need the actual ABI and encoding

    logger.info(f"Batching {len(calls)} price queries")

    # Execute multicall
    _, results = await multicall.aggregate(calls)

    return results
