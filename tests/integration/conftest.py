"""Shared fixtures for integration tests."""

import os
import pytest
from unittest.mock import MagicMock
from web3 import Web3


@pytest.fixture
def fork_web3():
    """
    Connect to an Anvil/Hardhat mainnet fork, or skip.

    Set FORK_RPC_URL to point at a running fork:
        anvil --fork-url $POLYGON_RPC_URL
        FORK_RPC_URL=http://127.0.0.1:8545 pytest tests/integration/ -m integration
    """
    rpc = os.getenv("FORK_RPC_URL", "http://127.0.0.1:8545")
    w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 15}))
    if not w3.is_connected():
        pytest.skip("No Anvil fork available (set FORK_RPC_URL)")
    return w3


@pytest.fixture
def mock_web3():
    """Standard mock Web3 for unit-style integration tests."""
    w3 = MagicMock()
    w3.to_checksum_address = Web3.to_checksum_address
    w3.eth.chain_id = 137
    w3.eth.block_number = 50_000_000
    w3.eth.gas_price = 30 * 10**9
    w3.eth.get_block.return_value = {"baseFeePerGas": 25 * 10**9}
    w3.eth.get_transaction_count.return_value = 0
    w3.from_wei = Web3.from_wei
    w3.to_wei = Web3.to_wei
    return w3
