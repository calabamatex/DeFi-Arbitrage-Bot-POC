"""Unit tests for FlashLoanOrchestrator."""

import pytest
import os
import time
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock, PropertyMock

from src.flash_loan_orchestrator import FlashLoanOrchestrator


@pytest.fixture
def mock_web3():
    """Mock Web3 instance."""
    web3 = Mock()
    web3.to_checksum_address = lambda x: x
    web3.eth.chain_id = 137
    web3.eth.gas_price = 30_000_000_000
    web3.eth.get_transaction_count = Mock(return_value=0)
    web3.to_wei = Mock(side_effect=lambda x, unit: int(x * 10**9) if unit == 'gwei' else x)
    web3.from_wei = Mock(side_effect=lambda x, unit: x / 10**9 if unit == 'gwei' else x)

    # Mock codec for ABI encoding
    web3.codec = Mock()
    web3.codec.encode = Mock(return_value=b'\x00' * 32)

    # Mock contract
    mock_contract = Mock()
    mock_contract.functions.owner.return_value.call.return_value = '0x' + 'aa' * 20
    mock_contract.functions.paused.return_value.call.return_value = False
    web3.eth.contract = Mock(return_value=mock_contract)

    # Mock block
    web3.eth.get_block = Mock(return_value={'baseFeePerGas': 30_000_000_000})
    web3.eth.estimate_gas = Mock(return_value=500000)

    return web3


@pytest.fixture
def orchestrator(mock_web3):
    """Create FlashLoanOrchestrator with mocks."""
    with patch('src.flash_loan_orchestrator.load_dotenv'), \
         patch('src.flash_loan_orchestrator.Account') as MockAccount:
        mock_account = Mock()
        mock_account.address = '0x' + 'aa' * 20
        MockAccount.from_key.return_value = mock_account

        orch = FlashLoanOrchestrator(
            web3=mock_web3,
            contract_address='0x' + '11' * 20,
            private_key='0x' + 'ff' * 32,
            v3_adapter_address='0x' + '22' * 20,
            v2_adapter_address='0x' + '33' * 20,
            dry_run=True,
            slippage_tolerance_pct=1.0,
            tx_deadline_seconds=120,
        )
    return orch


# ── Initialization ──────────────────────────────────────────────────

class TestInit:

    def test_orchestrator_init(self, orchestrator):
        assert orchestrator.dry_run is True
        assert orchestrator.slippage_tolerance_pct == 1.0
        assert orchestrator.tx_deadline_seconds == 120

    def test_env_defaults(self, mock_web3):
        """Should use env vars when params not provided."""
        with patch('src.flash_loan_orchestrator.load_dotenv'), \
             patch('src.flash_loan_orchestrator.Account') as MockAccount, \
             patch.dict(os.environ, {
                 'SLIPPAGE_TOLERANCE_PCT': '2.5',
                 'TX_DEADLINE_SECONDS': '60',
             }):
            mock_account = Mock()
            mock_account.address = '0x' + 'aa' * 20
            MockAccount.from_key.return_value = mock_account

            orch = FlashLoanOrchestrator(
                web3=mock_web3,
                contract_address='0x' + '11' * 20,
                private_key='0x' + 'ff' * 32,
                v3_adapter_address='0x' + '22' * 20,
                v2_adapter_address='0x' + '33' * 20,
            )
            assert orch.slippage_tolerance_pct == 2.5
            assert orch.tx_deadline_seconds == 60


# ── encode_v3_swap_data ─────────────────────────────────────────────

class TestEncodeV3SwapData:

    def test_encode_only_fee(self, orchestrator):
        """Should encode only the fee tier (not deadline)."""
        orchestrator.encode_v3_swap_data(3000)
        orchestrator.web3.codec.encode.assert_called_once_with(['uint24'], [3000])

    def test_encode_different_fees(self, orchestrator):
        """Should encode various fee tiers."""
        for fee in [500, 3000, 10000]:
            orchestrator.web3.codec.encode.reset_mock()
            orchestrator.encode_v3_swap_data(fee)
            orchestrator.web3.codec.encode.assert_called_once_with(['uint24'], [fee])


# ── build_swap_steps ────────────────────────────────────────────────

class TestBuildSwapSteps:

    def test_v3_then_v2_steps(self, orchestrator):
        """V3→V2 should produce 2 steps with correct adapters."""
        opp = {
            'direction': 'V3→V2',
            'token_in': '0x' + 'aa' * 20,
            'token_out': '0x' + 'bb' * 20,
            'amount_in': 1000 * 10**6,
            'v3_fee': 3000,
            'net_profit': 50 * 10**6,
            'amount_after_v3': 1050 * 10**6,
        }

        deadline = int(time.time()) + 120
        steps = orchestrator.build_swap_steps(opp, deadline)

        assert len(steps) == 2
        # Step 1: V3 adapter
        assert steps[0][0] == orchestrator.v3_adapter
        assert steps[0][1] == opp['token_in']
        assert steps[0][2] == opp['token_out']
        # Step 2: V2 adapter
        assert steps[1][0] == orchestrator.v2_adapter
        assert steps[1][1] == opp['token_out']
        assert steps[1][2] == opp['token_in']

    def test_v2_then_v3_steps(self, orchestrator):
        """V2→V3 should produce 2 steps with correct adapters."""
        opp = {
            'direction': 'V2→V3',
            'token_in': '0x' + 'aa' * 20,
            'token_out': '0x' + 'bb' * 20,
            'amount_in': 1000 * 10**6,
            'v3_fee': 500,
            'net_profit': 50 * 10**6,
            'amount_after_v2': 1050 * 10**6,
        }

        deadline = int(time.time()) + 120
        steps = orchestrator.build_swap_steps(opp, deadline)

        assert len(steps) == 2
        # Step 1: V2 adapter
        assert steps[0][0] == orchestrator.v2_adapter
        # Step 2: V3 adapter
        assert steps[1][0] == orchestrator.v3_adapter

    def test_min_amount_out_uses_intermediate(self, orchestrator):
        """First step minAmountOut should be based on expected intermediate."""
        opp = {
            'direction': 'V3→V2',
            'token_in': '0x' + 'aa' * 20,
            'token_out': '0x' + 'bb' * 20,
            'amount_in': 1000 * 10**6,
            'v3_fee': 3000,
            'net_profit': 50 * 10**6,
            'amount_after_v3': 1050 * 10**6,
        }

        deadline = int(time.time()) + 120
        steps = orchestrator.build_swap_steps(opp, deadline)

        # With 1% slippage, first step min should be ~1050 * 0.99 = 1039.5
        expected_min = int(1050 * 10**6 * 99 // 100)
        assert steps[0][3] == expected_min

    def test_v2_data_is_empty(self, orchestrator):
        """V2 step data should be empty bytes."""
        opp = {
            'direction': 'V3→V2',
            'token_in': '0x' + 'aa' * 20,
            'token_out': '0x' + 'bb' * 20,
            'amount_in': 1000 * 10**6,
            'v3_fee': 3000,
            'net_profit': 50 * 10**6,
            'amount_after_v3': 1050 * 10**6,
        }

        deadline = int(time.time()) + 120
        steps = orchestrator.build_swap_steps(opp, deadline)

        # V2 step (step 2) data should be empty
        assert steps[1][4] == b''


# ── Gas Estimation ──────────────────────────────────────────────────

class TestGasEstimation:

    def test_estimate_gas_with_buffer(self, orchestrator):
        """Should add 20% buffer to estimate."""
        tx = {'to': '0x' + '11' * 20, 'data': b''}
        gas = orchestrator.estimate_gas(tx)
        assert gas == int(500000 * 1.2)

    def test_estimate_gas_fallback(self, orchestrator):
        """Should return 600k on estimation failure."""
        orchestrator.web3.eth.estimate_gas = Mock(side_effect=Exception("fail"))
        gas = orchestrator.estimate_gas({})
        assert gas == 600000


# ── Dry Run Execution ───────────────────────────────────────────────

class TestDryRunExecution:

    def test_dry_run_success(self, orchestrator):
        """Dry run should simulate without sending tx."""
        opp = {
            'direction': 'V3→V2',
            'token_in': '0x' + 'aa' * 20,
            'token_out': '0x' + 'bb' * 20,
            'amount_in': 1000 * 10**6,
            'v3_fee': 3000,
            'net_profit': 50 * 10**6,
            'amount_after_v3': 1050 * 10**6,
            'token_decimals': 6,
        }

        # Mock the contract call chain
        mock_fn = Mock()
        mock_fn.build_transaction = Mock(return_value={
            'from': orchestrator.address,
            'to': orchestrator.contract_address,
            'data': b'',
            'gas': 0,
            'maxFeePerGas': 60_000_000_000,
            'maxPriorityFeePerGas': 2_000_000_000,
            'chainId': 137,
            'nonce': 0,
        })
        orchestrator.contract.functions.executeArbitrage = Mock(return_value=mock_fn)
        orchestrator.web3.eth.call = Mock(return_value=b'')

        result = orchestrator.execute_opportunity(opp)

        assert result['success'] is True
        assert result['profit'] == 50 * 10**6

    def test_dry_run_simulation_failure(self, orchestrator):
        """Dry run should fail on simulation error."""
        opp = {
            'direction': 'V3→V2',
            'token_in': '0x' + 'aa' * 20,
            'token_out': '0x' + 'bb' * 20,
            'amount_in': 1000 * 10**6,
            'v3_fee': 3000,
            'net_profit': 50 * 10**6,
            'amount_after_v3': 1050 * 10**6,
            'token_decimals': 6,
        }

        mock_fn = Mock()
        mock_fn.build_transaction = Mock(return_value={
            'from': orchestrator.address,
            'to': orchestrator.contract_address,
            'data': b'',
            'gas': 0,
            'maxFeePerGas': 60_000_000_000,
            'maxPriorityFeePerGas': 2_000_000_000,
            'chainId': 137,
            'nonce': 0,
        })
        orchestrator.contract.functions.executeArbitrage = Mock(return_value=mock_fn)
        orchestrator.web3.eth.call = Mock(side_effect=Exception("execution reverted"))

        result = orchestrator.execute_opportunity(opp)

        assert result['success'] is False
        assert 'Simulation failed' in result['error']

    def test_paused_contract_fails(self, orchestrator):
        """Should fail if contract is paused."""
        orchestrator.contract.functions.paused.return_value.call.return_value = True

        opp = {
            'direction': 'V3→V2',
            'token_in': '0x' + 'aa' * 20,
            'token_out': '0x' + 'bb' * 20,
            'amount_in': 1000 * 10**6,
            'v3_fee': 3000,
            'net_profit': 50 * 10**6,
            'amount_after_v3': 1050 * 10**6,
        }

        result = orchestrator.execute_opportunity(opp)
        assert result['success'] is False
        assert 'paused' in result['error'].lower()


# ── Deadline / Slippage Config ──────────────────────────────────────

class TestConfigurableParams:

    def test_deadline_used_in_build(self, orchestrator):
        """Build transaction should use configured deadline."""
        opp = {
            'direction': 'V3→V2',
            'token_in': '0x' + 'aa' * 20,
            'token_out': '0x' + 'bb' * 20,
            'amount_in': 1000 * 10**6,
            'v3_fee': 3000,
            'net_profit': 50 * 10**6,
            'amount_after_v3': 1050 * 10**6,
        }

        before = int(time.time())

        mock_fn = Mock()
        mock_fn.build_transaction = Mock(return_value={
            'from': orchestrator.address,
            'to': orchestrator.contract_address,
            'data': b'',
            'gas': 0,
            'maxFeePerGas': 60_000_000_000,
            'maxPriorityFeePerGas': 2_000_000_000,
            'chainId': 137,
            'nonce': 0,
        })
        orchestrator.contract.functions.executeArbitrage = Mock(return_value=mock_fn)

        orchestrator.build_transaction(opp)

        # Verify executeArbitrage was called with params that include a deadline
        call_args = orchestrator.contract.functions.executeArbitrage.call_args
        params_tuple = call_args[0][0]
        deadline = params_tuple[4]  # 5th element is deadline

        after = int(time.time())
        assert deadline >= before + 120
        assert deadline <= after + 120 + 1
