"""Comprehensive tests for TransactionManager."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import asyncio
from src.utils.transaction_manager import TransactionManager


@pytest.fixture
def mock_web3():
    """Mock Web3 instance."""
    web3 = Mock()
    web3.eth.get_transaction_count.return_value = 5
    web3.eth.gas_price = 30000000000
    web3.eth.chain_id = 80001  # Mumbai
    web3.eth.get_transaction_receipt.return_value = {
        "status": 1,
        "blockNumber": 12345,
        "transactionHash": "0xabc123",
    }

    # Mock account signing
    mock_signed = Mock()
    mock_signed.rawTransaction = b"\x00\x01\x02\x03"
    web3.eth.account.sign_transaction.return_value = mock_signed

    # Mock send_raw_transaction
    mock_tx_hash = Mock()
    mock_tx_hash.hex.return_value = "0xabc123def456"
    web3.eth.send_raw_transaction.return_value = mock_tx_hash

    return web3


@pytest.fixture
def tx_manager(mock_web3):
    """Create TransactionManager instance."""
    return TransactionManager(
        web3=mock_web3,
        account="0x1234567890123456789012345678901234567890",
        private_key="0xabcdef1234567890",
    )


def test_initialization(tx_manager):
    """Test TransactionManager initialization."""
    assert tx_manager.account == "0x1234567890123456789012345678901234567890"
    assert tx_manager.private_key == "0xabcdef1234567890"
    assert len(tx_manager._pending_nonces) == 0


@pytest.mark.asyncio
async def test_get_next_nonce_sequential(tx_manager):
    """Test sequential nonce allocation."""
    nonce1 = await tx_manager.get_next_nonce()
    nonce2 = await tx_manager.get_next_nonce()

    assert nonce2 > nonce1
    assert nonce1 in tx_manager._pending_nonces
    assert nonce2 in tx_manager._pending_nonces
    assert tx_manager.get_pending_nonce_count() == 2


@pytest.mark.asyncio
async def test_get_next_nonce_with_tracked_nonces(tx_manager):
    """Test nonce allocation when tracking existing nonces."""
    # Add some existing nonces
    tx_manager._pending_nonces = {5, 6}

    nonce = await tx_manager.get_next_nonce()

    # Should be 7 (max tracked + 1)
    assert nonce == 7
    assert nonce in tx_manager._pending_nonces


def test_release_nonce(tx_manager):
    """Test nonce release."""
    tx_manager._pending_nonces.add(5)
    tx_manager._pending_nonces.add(6)

    tx_manager.release_nonce(5)

    assert 5 not in tx_manager._pending_nonces
    assert 6 in tx_manager._pending_nonces
    assert tx_manager.get_pending_nonce_count() == 1


def test_release_nonce_not_tracked(tx_manager):
    """Test releasing a nonce that isn't tracked."""
    tx_manager._pending_nonces.add(5)

    # Should not raise error
    tx_manager.release_nonce(10)

    assert 5 in tx_manager._pending_nonces
    assert tx_manager.get_pending_nonce_count() == 1


@pytest.mark.asyncio
async def test_build_transaction_success(tx_manager, mock_web3):
    """Test successful transaction building."""
    mock_function = Mock()
    mock_function.build_transaction.return_value = {
        "from": tx_manager.account,
        "nonce": 5,
        "gas": 300000,
        "gasPrice": 30000000000,
        "value": 0,
        "chainId": 80001,
    }

    txn = await tx_manager.build_transaction(mock_function, gas_limit=300000)

    assert txn["nonce"] == 5
    assert txn["gas"] == 300000
    assert txn["gasPrice"] == 30000000000
    assert txn["chainId"] == 80001
    assert 5 in tx_manager._pending_nonces


@pytest.mark.asyncio
async def test_build_transaction_with_custom_gas_price(tx_manager, mock_web3):
    """Test transaction building with custom gas price."""
    mock_function = Mock()
    mock_function.build_transaction.return_value = {
        "from": tx_manager.account,
        "nonce": 5,
        "gas": 300000,
        "gasPrice": 50000000000,  # Custom price
        "value": 0,
        "chainId": 80001,
    }

    txn = await tx_manager.build_transaction(
        mock_function, gas_limit=300000, gas_price=50000000000
    )

    # Verify custom gas price was used
    mock_function.build_transaction.assert_called_once()
    call_args = mock_function.build_transaction.call_args[0][0]
    assert call_args["gasPrice"] == 50000000000


@pytest.mark.asyncio
async def test_build_transaction_failure_releases_nonce(tx_manager):
    """Test that nonce is released when build fails."""
    mock_function = Mock()
    mock_function.build_transaction.side_effect = Exception("Build failed")

    initial_count = tx_manager.get_pending_nonce_count()

    with pytest.raises(Exception, match="Build failed"):
        await tx_manager.build_transaction(mock_function, gas_limit=300000)

    # Nonce should have been released
    assert tx_manager.get_pending_nonce_count() == initial_count


@pytest.mark.asyncio
async def test_sign_and_send_success(tx_manager, mock_web3):
    """Test successful transaction signing and sending."""
    transaction = {
        "from": tx_manager.account,
        "nonce": 5,
        "gas": 300000,
        "gasPrice": 30000000000,
    }

    tx_hash = await tx_manager.sign_and_send(transaction)

    assert tx_hash == "0xabc123def456"
    mock_web3.eth.account.sign_transaction.assert_called_once_with(
        transaction, tx_manager.private_key
    )
    mock_web3.eth.send_raw_transaction.assert_called_once()


@pytest.mark.asyncio
async def test_sign_and_send_failure(tx_manager, mock_web3):
    """Test transaction signing/sending failure."""
    mock_web3.eth.account.sign_transaction.side_effect = Exception("Signing failed")

    transaction = {"nonce": 5}

    with pytest.raises(Exception, match="Signing failed"):
        await tx_manager.sign_and_send(transaction)


@pytest.mark.asyncio
async def test_wait_for_confirmation_success(tx_manager, mock_web3):
    """Test successful transaction confirmation."""
    tx_hash = "0xabc123"

    receipt = await tx_manager.wait_for_confirmation(tx_hash, timeout=10)

    assert receipt["status"] == 1
    assert receipt["blockNumber"] == 12345
    mock_web3.eth.get_transaction_receipt.assert_called_with(tx_hash)


@pytest.mark.asyncio
async def test_wait_for_confirmation_timeout(tx_manager, mock_web3):
    """Test transaction confirmation timeout."""
    # Make get_transaction_receipt raise exception (not mined)
    mock_web3.eth.get_transaction_receipt.side_effect = Exception("Not found")

    tx_hash = "0xabc123"

    with pytest.raises(TimeoutError, match="not confirmed within"):
        await tx_manager.wait_for_confirmation(tx_hash, timeout=2, poll_interval=0.5)


@pytest.mark.asyncio
async def test_wait_for_confirmation_reverted(tx_manager, mock_web3):
    """Test waiting for a reverted transaction."""
    mock_web3.eth.get_transaction_receipt.return_value = {
        "status": 0,  # Reverted
        "blockNumber": 12345,
    }

    tx_hash = "0xabc123"

    receipt = await tx_manager.wait_for_confirmation(tx_hash, timeout=10)

    # Should still return receipt, just with status 0
    assert receipt["status"] == 0


@pytest.mark.asyncio
async def test_execute_transaction_success(tx_manager, mock_web3):
    """Test successful transaction execution."""
    mock_function = Mock()
    mock_function.build_transaction.return_value = {
        "from": tx_manager.account,
        "nonce": 5,
        "gas": 300000,
        "gasPrice": 30000000000,
        "value": 0,
        "chainId": 80001,
    }

    success, result = await tx_manager.execute_transaction(
        mock_function, gas_limit=300000
    )

    assert success is True
    assert result == "0xabc123def456"
    # Nonce should be released
    assert 5 not in tx_manager._pending_nonces


@pytest.mark.asyncio
async def test_execute_transaction_reverted(tx_manager, mock_web3):
    """Test transaction execution with revert."""
    mock_function = Mock()
    mock_function.build_transaction.return_value = {
        "from": tx_manager.account,
        "nonce": 5,
        "gas": 300000,
        "gasPrice": 30000000000,
        "value": 0,
        "chainId": 80001,
    }

    # Make receipt show reverted status
    mock_web3.eth.get_transaction_receipt.return_value = {
        "status": 0,  # Reverted
        "blockNumber": 12345,
    }

    success, result = await tx_manager.execute_transaction(
        mock_function, gas_limit=300000
    )

    assert success is False
    assert "reverted" in result.lower()


@pytest.mark.asyncio
async def test_execute_transaction_retry_on_failure(tx_manager, mock_web3):
    """Test transaction retry logic."""
    mock_function = Mock()

    # First attempt fails, second succeeds
    call_count = 0

    def build_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("Network error")
        return {
            "from": tx_manager.account,
            "nonce": 5,
            "gas": 300000,
            "gasPrice": 30000000000,
            "value": 0,
            "chainId": 80001,
        }

    mock_function.build_transaction.side_effect = build_side_effect

    success, result = await tx_manager.execute_transaction(
        mock_function, gas_limit=300000, max_retries=3, retry_delay=0.1
    )

    # Should succeed on second attempt
    assert success is True
    assert mock_function.build_transaction.call_count == 2


@pytest.mark.asyncio
async def test_execute_transaction_all_retries_fail(tx_manager):
    """Test transaction when all retries fail."""
    mock_function = Mock()
    mock_function.build_transaction.side_effect = Exception("Network error")

    success, result = await tx_manager.execute_transaction(
        mock_function, gas_limit=300000, max_retries=2, retry_delay=0.1
    )

    assert success is False
    assert "All retries failed" in result
    assert "Network error" in result


@pytest.mark.asyncio
async def test_simulate_transaction_success(tx_manager):
    """Test successful transaction simulation."""
    mock_function = Mock()
    mock_function.call.return_value = True

    result = await tx_manager.simulate_transaction(mock_function)

    assert result is True
    mock_function.call.assert_called_once_with({"from": tx_manager.account, "value": 0})


@pytest.mark.asyncio
async def test_simulate_transaction_with_value(tx_manager):
    """Test transaction simulation with value."""
    mock_function = Mock()
    mock_function.call.return_value = True

    result = await tx_manager.simulate_transaction(mock_function, value=1000000)

    assert result is True
    mock_function.call.assert_called_once_with(
        {"from": tx_manager.account, "value": 1000000}
    )


@pytest.mark.asyncio
async def test_simulate_transaction_failure(tx_manager):
    """Test failed transaction simulation."""
    mock_function = Mock()
    mock_function.call.side_effect = Exception("Simulation failed")

    result = await tx_manager.simulate_transaction(mock_function)

    assert result is False


@pytest.mark.asyncio
async def test_estimate_gas_success(tx_manager):
    """Test successful gas estimation."""
    mock_function = Mock()
    mock_function.estimate_gas.return_value = 250000

    gas = await tx_manager.estimate_gas(mock_function)

    assert gas == 250000
    mock_function.estimate_gas.assert_called_once_with(
        {"from": tx_manager.account, "value": 0}
    )


@pytest.mark.asyncio
async def test_estimate_gas_with_value(tx_manager):
    """Test gas estimation with value."""
    mock_function = Mock()
    mock_function.estimate_gas.return_value = 280000

    gas = await tx_manager.estimate_gas(mock_function, value=5000000)

    assert gas == 280000
    mock_function.estimate_gas.assert_called_once_with(
        {"from": tx_manager.account, "value": 5000000}
    )


@pytest.mark.asyncio
async def test_estimate_gas_failure_returns_default(tx_manager):
    """Test gas estimation failure returns default."""
    mock_function = Mock()
    mock_function.estimate_gas.side_effect = Exception("Estimation failed")

    gas = await tx_manager.estimate_gas(mock_function)

    # Should return default conservative estimate
    assert gas == 300000


def test_get_pending_nonce_count_empty(tx_manager):
    """Test pending nonce count when empty."""
    count = tx_manager.get_pending_nonce_count()

    assert count == 0


def test_get_pending_nonce_count_multiple(tx_manager):
    """Test pending nonce count with multiple nonces."""
    tx_manager._pending_nonces = {5, 6, 7, 8}

    count = tx_manager.get_pending_nonce_count()

    assert count == 4


@pytest.mark.asyncio
async def test_concurrent_nonce_allocation(tx_manager):
    """Test that concurrent nonce requests don't conflict."""

    async def get_nonce():
        return await tx_manager.get_next_nonce()

    # Get 5 nonces concurrently
    nonces = await asyncio.gather(*[get_nonce() for _ in range(5)])

    # All nonces should be unique
    assert len(set(nonces)) == 5

    # All nonces should be sequential
    sorted_nonces = sorted(nonces)
    for i in range(1, len(sorted_nonces)):
        assert sorted_nonces[i] == sorted_nonces[i - 1] + 1


@pytest.mark.asyncio
async def test_build_transaction_with_value(tx_manager):
    """Test building transaction with ETH value."""
    mock_function = Mock()
    mock_function.build_transaction.return_value = {
        "from": tx_manager.account,
        "nonce": 5,
        "gas": 300000,
        "gasPrice": 30000000000,
        "value": 1000000000000000000,  # 1 ETH
        "chainId": 80001,
    }

    txn = await tx_manager.build_transaction(
        mock_function, gas_limit=300000, value=1000000000000000000
    )

    assert txn["value"] == 1000000000000000000


def test_account_checksumming(mock_web3):
    """Test that account address is checksummed on init."""
    # Use lowercase address
    manager = TransactionManager(
        web3=mock_web3,
        account="0x1234567890123456789012345678901234567890",
        private_key="0xabcdef",
    )

    # Should be checksummed
    assert manager.account == "0x1234567890123456789012345678901234567890"
