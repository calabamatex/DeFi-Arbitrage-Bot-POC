"""
Flash Loan Orchestrator for Arbitrage Bot

Executes arbitrage opportunities using Aave V3 flash loans.
"""

import asyncio
import os
import time
import logging
from typing import List, Dict, Optional, Tuple
from decimal import Decimal
from datetime import datetime

from web3 import Web3
from web3.contract import Contract
from eth_account import Account
from dotenv import load_dotenv

from src.db.database import get_db
from src.db.models import (
    Opportunity, Transaction, TradeResult, ExecutionLog,
    OpportunityStatus, TransactionStatus
)
from src.flash_loan_providers import FlashLoanSelector, FlashLoanProvider
from src.utils.errors import classify_web3_exception, DatabaseError

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class FlashLoanOrchestrator:
    """
    Orchestrates flash loan arbitrage execution.

    Takes opportunities from the detector and executes them through
    the deployed FlashLoanArbitrageV2 contract.
    """

    def __init__(
        self,
        web3: Web3,
        contract_address: str,
        private_key: str,
        v3_adapter_address: str,
        v2_adapter_address: str,
        dry_run: bool = False,
        slippage_tolerance_pct: float = None,
        tx_deadline_seconds: int = None,
        curve_adapter_address: str = None,
        balancer_contract_address: str = None,
        mev_protection=None,
        tx_manager=None,
    ):
        """
        Initialize the orchestrator.

        Args:
            web3: Web3 instance
            contract_address: FlashLoanArbitrageV2 address (Aave)
            private_key: Private key for signing transactions
            v3_adapter_address: UniswapV3Adapter address
            v2_adapter_address: UniswapV2Adapter address
            dry_run: If True, simulate without sending transactions
            slippage_tolerance_pct: Max slippage % for intermediate swaps (default: env or 1.0)
            tx_deadline_seconds: Transaction deadline in seconds (default: env or 120)
            curve_adapter_address: Optional CurveAdapter address
            balancer_contract_address: Optional BalancerFlashLoan address (0% fee)
            mev_protection: Optional FlashbotsProvider for private tx submission
            tx_manager: Optional TransactionManager for nonce management and retry
        """
        self.web3 = web3
        self.contract_address = web3.to_checksum_address(contract_address)
        self.v3_adapter = web3.to_checksum_address(v3_adapter_address)
        self.v2_adapter = web3.to_checksum_address(v2_adapter_address)
        self.curve_adapter = (
            web3.to_checksum_address(curve_adapter_address) if curve_adapter_address else None
        )
        self.balancer_contract_address = (
            web3.to_checksum_address(balancer_contract_address) if balancer_contract_address else None
        )
        self.dry_run = dry_run

        # Flash loan provider selector (Aave vs Balancer)
        self.flash_loan_selector = FlashLoanSelector(
            web3=web3,
            aave_contract_address=contract_address,
            balancer_contract_address=balancer_contract_address,
        )
        self.slippage_tolerance_pct = slippage_tolerance_pct or float(
            os.getenv('SLIPPAGE_TOLERANCE_PCT', '1.0')
        )
        self.tx_deadline_seconds = tx_deadline_seconds or int(
            os.getenv('TX_DEADLINE_SECONDS', '120')
        )

        # Optional: MEV protection (Flashbots) and TransactionManager
        self.mev_protection = mev_protection
        self.tx_manager = tx_manager

        # Initialize account
        self.account = Account.from_key(private_key)
        self.address = self.account.address

        if mev_protection:
            logger.info("MEV protection enabled (FlashbotsProvider)")
        if tx_manager:
            logger.info("TransactionManager wired (nonce locking + retry enabled)")

        logger.info(f"FlashLoanOrchestrator initialized")
        logger.info(f"Contract: {self.contract_address}")
        logger.info(f"Executor: {self.address}")
        logger.info(f"Dry run: {dry_run}")
        logger.info(f"Slippage tolerance: {self.slippage_tolerance_pct}%")
        logger.info(f"TX deadline: {self.tx_deadline_seconds}s")

        # Initialize contract
        self._init_contract()

    def _init_contract(self):
        """Initialize the FlashLoanArbitrageV2 contract."""
        # Minimal ABI for executeArbitrage
        abi = [
            {
                "inputs": [
                    {
                        "components": [
                            {
                                "components": [
                                    {"internalType": "address", "name": "adapter", "type": "address"},
                                    {"internalType": "address", "name": "tokenIn", "type": "address"},
                                    {"internalType": "address", "name": "tokenOut", "type": "address"},
                                    {"internalType": "uint256", "name": "minAmountOut", "type": "uint256"},
                                    {"internalType": "bytes", "name": "data", "type": "bytes"}
                                ],
                                "internalType": "struct FlashLoanArbitrageV2.SwapStep[]",
                                "name": "steps",
                                "type": "tuple[]"
                            },
                            {"internalType": "uint256", "name": "flashLoanAmount", "type": "uint256"},
                            {"internalType": "address", "name": "flashLoanAsset", "type": "address"},
                            {"internalType": "uint256", "name": "minFinalAmount", "type": "uint256"},
                            {"internalType": "uint256", "name": "deadline", "type": "uint256"}
                        ],
                        "internalType": "struct FlashLoanArbitrageV2.ArbitrageParams",
                        "name": "params",
                        "type": "tuple"
                    }
                ],
                "name": "executeArbitrage",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            },
            {
                "inputs": [],
                "name": "paused",
                "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [],
                "name": "owner",
                "outputs": [{"internalType": "address", "name": "", "type": "address"}],
                "stateMutability": "view",
                "type": "function"
            }
        ]

        self.contract = self.web3.eth.contract(
            address=self.contract_address,
            abi=abi
        )

        # Verify contract ownership
        try:
            owner = self.contract.functions.owner().call()
            logger.info(f"Contract owner: {owner}")
            if owner.lower() != self.address.lower():
                logger.warning(f"⚠️  Executor {self.address} is not contract owner {owner}")
        except (TimeoutError, ConnectionError) as e:
            classified = classify_web3_exception(e)
            logger.error(f"RPC failure ({type(classified).__name__}): {e}")
        except Exception as e:
            classified = classify_web3_exception(e)
            logger.error(f"{type(classified).__name__}: Failed to verify contract: {e}", extra={"retryable": classified.retryable})

    def encode_v3_swap_data(self, fee: int) -> bytes:
        """
        Encode Uniswap V3 swap data (fee tier only).

        The deadline is passed separately via the IDEXAdapter interface,
        so data only contains the V3 pool fee tier.

        Args:
            fee: Fee tier (500, 3000, or 10000)

        Returns:
            ABI-encoded uint24 fee
        """
        return self.web3.codec.encode(['uint24'], [fee])

    def _get_adapter_for_dex(self, dex_name: str) -> str:
        """Map DEX name to adapter address."""
        mapping = {
            'uniswap_v3': self.v3_adapter,
            'quickswap': self.v2_adapter,
            'sushiswap': self.v2_adapter,
        }
        if self.curve_adapter:
            mapping['curve'] = self.curve_adapter
        adapter = mapping.get(dex_name)
        if not adapter:
            raise ValueError(f"No adapter for DEX: {dex_name}")
        return adapter

    def _encode_dex_data(self, dex_name: str, fee: Optional[int]) -> bytes:
        """Encode adapter-specific data for a swap step."""
        if dex_name == 'uniswap_v3' and fee is not None:
            return self.encode_v3_swap_data(fee)
        return b''

    def build_swap_steps(
        self,
        opportunity: Dict,
        deadline: int
    ) -> List[Tuple]:
        """
        Build swap steps from opportunity data.

        Supports both legacy 2-step format (direction: V3→V2 / V2→V3)
        and new N-step format (direction: triangular, with token_path/dex_path/amounts/fees).

        Args:
            opportunity: Opportunity dict from detector
            deadline: Transaction deadline timestamp

        Returns:
            List of swap step tuples
        """
        direction = opportunity['direction']

        # ── N-step path (triangular and beyond) ────────────────
        if direction == 'triangular' and 'token_path' in opportunity:
            return self._build_nstep_swap_steps(opportunity)

        # ── Legacy 2-step path ─────────────────────────────────
        return self._build_legacy_swap_steps(opportunity)

    def _build_nstep_swap_steps(self, opportunity: Dict) -> List[Tuple]:
        """Build swap steps for N-step paths (triangular, etc.)."""
        steps = []
        token_path = opportunity['token_path']
        dex_path = opportunity['dex_path']
        amounts = opportunity['amounts']
        fees = opportunity['fees']
        slippage_factor = int(100 - self.slippage_tolerance_pct)

        num_legs = len(dex_path)
        for i in range(num_legs):
            adapter = self._get_adapter_for_dex(dex_path[i])
            token_in = token_path[i]
            token_out = token_path[i + 1]
            expected_out = amounts[i + 1]
            data = self._encode_dex_data(dex_path[i], fees[i])

            if i < num_legs - 1:
                # Intermediate step: apply slippage tolerance
                min_out = int(expected_out * slippage_factor // 100)
            else:
                # Final step: require at least amount_in + net_profit
                min_out = opportunity['amount_in'] + opportunity['net_profit']

            steps.append((adapter, token_in, token_out, min_out, data))

        return steps

    def _build_legacy_swap_steps(self, opportunity: Dict) -> List[Tuple]:
        """Build swap steps for legacy V3→V2 / V2→V3 format."""
        steps = []
        direction = opportunity['direction']
        token_in = opportunity['token_in']
        token_out = opportunity['token_out']
        amount_in = opportunity['amount_in']

        slippage_factor = int(100 - self.slippage_tolerance_pct)
        if direction == 'V3→V2':
            expected_intermediate = opportunity.get('amount_after_v3', 0)
        else:
            expected_intermediate = opportunity.get('amount_after_v2', 0)
        if expected_intermediate > 0:
            first_step_min = int(expected_intermediate * slippage_factor // 100)
        else:
            fallback_factor = max(int(100 - self.slippage_tolerance_pct * 2), 90)
            first_step_min = int(amount_in * fallback_factor // 100)

        if direction == 'V3→V2':
            v3_fee = opportunity['v3_fee']
            v3_data = self.encode_v3_swap_data(v3_fee)

            steps.append((
                self.v3_adapter, token_in, token_out,
                first_step_min, v3_data
            ))
            steps.append((
                self.v2_adapter, token_out, token_in,
                opportunity['amount_in'] + opportunity['net_profit'], b''
            ))

        elif direction == 'V2→V3':
            steps.append((
                self.v2_adapter, token_in, token_out,
                first_step_min, b''
            ))
            v3_fee = opportunity['v3_fee']
            v3_data = self.encode_v3_swap_data(v3_fee)
            steps.append((
                self.v3_adapter, token_out, token_in,
                opportunity['amount_in'] + opportunity['net_profit'], v3_data
            ))

        return steps

    def estimate_gas(self, transaction: Dict) -> int:
        """
        Estimate gas for transaction.

        Args:
            transaction: Transaction dict

        Returns:
            Estimated gas units
        """
        try:
            gas_estimate = self.web3.eth.estimate_gas(transaction)
            # Add 20% buffer
            return int(gas_estimate * 1.2)
        except (TimeoutError, ConnectionError) as e:
            classified = classify_web3_exception(e)
            logger.warning(f"RPC failure during gas estimation ({type(classified).__name__}): {e}, using default")
            return 600000
        except Exception as e:
            classified = classify_web3_exception(e)
            logger.warning(f"{type(classified).__name__}: Gas estimation failed: {e}, using default", extra={"retryable": classified.retryable})
            # Default: 600k gas for flash loan arbitrage
            return 600000

    def build_transaction(
        self,
        opportunity: Dict,
        gas_price: Optional[int] = None
    ) -> Dict:
        """
        Build the arbitrage transaction.

        NOTE: When a TransactionManager is wired in (self.tx_manager), nonce
        tracking and EIP-1559 fee calculation are delegated to it. Otherwise
        falls back to inline logic for backward compatibility.

        Args:
            opportunity: Opportunity data
            gas_price: Optional gas price (uses network price if None)

        Returns:
            Transaction dict ready to sign
        """
        # Get deadline (configurable, default 120s)
        deadline = int(time.time()) + self.tx_deadline_seconds

        # Build swap steps
        steps = self.build_swap_steps(opportunity, deadline)

        # Select flash loan provider (Balancer 0% fee preferred)
        provider, provider_contract_addr, fee_bps = self.flash_loan_selector.select_provider(
            token_address=opportunity['token_in'],
            amount=opportunity['amount_in'],
        )
        opportunity['_flash_loan_provider'] = provider.value
        opportunity['_flash_loan_fee_bps'] = fee_bps

        # Use the selected contract (both share the same executeArbitrage ABI)
        active_contract = self.web3.eth.contract(
            address=provider_contract_addr,
            abi=self.contract.abi,
        )

        # Build arbitrage params
        params = (
            steps,                           # steps
            opportunity['amount_in'],        # flashLoanAmount
            opportunity['token_in'],         # flashLoanAsset
            opportunity['amount_in'] + opportunity['net_profit'],  # minFinalAmount
            deadline                         # deadline
        )

        # Get EIP-1559 gas pricing and nonce
        if self.tx_manager:
            # Delegate to TransactionManager for centralized fee calculation
            try:
                fees = self.tx_manager._get_eip1559_fees("normal")
                max_fee = gas_price or fees["maxFeePerGas"]
                max_priority = fees["maxPriorityFeePerGas"]
            except Exception:
                # Fallback if TxManager fee calc fails
                latest_block = self.web3.eth.get_block('latest')
                base_fee = latest_block.get('baseFeePerGas', self.web3.eth.gas_price)
                max_priority = self.web3.to_wei(2, 'gwei')
                max_fee = gas_price or (base_fee * 2 + max_priority)

            nonce = asyncio.get_event_loop().run_until_complete(
                self.tx_manager.get_next_nonce()
            ) if asyncio.get_event_loop().is_running() is False else self.web3.eth.get_transaction_count(self.address, 'pending')
        else:
            latest_block = self.web3.eth.get_block('latest')
            base_fee = latest_block.get('baseFeePerGas', self.web3.eth.gas_price)
            max_priority = self.web3.to_wei(2, 'gwei')
            max_fee = gas_price or (base_fee * 2 + max_priority)
            nonce = self.web3.eth.get_transaction_count(self.address, 'pending')

        # Build transaction
        transaction = active_contract.functions.executeArbitrage(
            params
        ).build_transaction({
            'from': self.address,
            'nonce': nonce,
            'gas': 0,  # Will be estimated
            'maxFeePerGas': max_fee,
            'maxPriorityFeePerGas': max_priority,
            'chainId': self.web3.eth.chain_id
        })

        # Estimate gas
        transaction['gas'] = self.estimate_gas(transaction)

        return transaction

    def execute_opportunity(
        self,
        opportunity: Dict,
        opportunity_id: Optional[str] = None
    ) -> Dict:
        """
        Execute an arbitrage opportunity.

        When a TransactionManager is wired in, nonce tracking and EIP-1559
        fees are delegated to it. When a FlashbotsProvider is wired in,
        transactions are routed through private relays to avoid frontrunning.

        Args:
            opportunity: Opportunity data from detector
            opportunity_id: Optional opportunity ID for database tracking

        Returns:
            Execution result dict
        """
        logger.info(f"{'[DRY RUN] ' if self.dry_run else ''}Executing opportunity: {opportunity['direction']}")
        logger.info(f"  Token pair: {opportunity['token_in'][:10]} ↔ {opportunity['token_out'][:10]}")
        logger.info(f"  Amount: {opportunity['amount_in'] / 10**6:.2f} tokens")
        logger.info(f"  Expected profit: {opportunity['net_profit'] / 10**6:.6f} tokens")

        start_time = time.time()
        result = {
            'success': False,
            'tx_hash': None,
            'gas_used': 0,
            'gas_price': 0,
            'profit': 0,
            'error': None
        }

        try:
            # Check if contract is paused
            if self.contract.functions.paused().call():
                raise Exception("Contract is paused")

            # Build transaction
            transaction = self.build_transaction(opportunity)

            logger.info(f"  Gas limit: {transaction['gas']:,}")
            logger.info(f"  Gas price: {self.web3.from_wei(transaction['maxFeePerGas'], 'gwei'):.2f} gwei")

            # Pre-execution simulation via eth_call
            try:
                self.web3.eth.call({
                    'from': transaction['from'],
                    'to': transaction['to'],
                    'data': transaction['data'],
                    'gas': transaction['gas'],
                    'maxFeePerGas': transaction['maxFeePerGas'],
                    'maxPriorityFeePerGas': transaction['maxPriorityFeePerGas'],
                })
                logger.info("  Simulation passed")
            except (TimeoutError, ConnectionError) as sim_err:
                classified = classify_web3_exception(sim_err)
                logger.error(f"  Simulation RPC failure ({type(classified).__name__}): {sim_err}")
                result['error'] = f"Simulation RPC failure: {sim_err}"
                return result
            except Exception as sim_err:
                classified = classify_web3_exception(sim_err)
                logger.error(f"  Simulation FAILED ({type(classified).__name__}): {sim_err}", extra={"retryable": classified.retryable})
                result['error'] = f"Simulation failed: {sim_err}"
                return result

            if self.dry_run:
                logger.info("  [DRY RUN] Transaction built and simulated successfully")
                result['success'] = True
                result['tx_hash'] = '0x' + '0' * 64
                result['gas_used'] = transaction['gas']
                result['gas_price'] = transaction['maxFeePerGas']
                result['profit'] = opportunity['net_profit']

            else:
                # Sign transaction
                signed_txn = self.account.sign_transaction(transaction)

                # Send transaction — use MEV protection if available
                logger.info("  Sending transaction...")
                if self.mev_protection:
                    try:
                        tx_hash = asyncio.get_event_loop().run_until_complete(
                            self.mev_protection.send_private_transaction(
                                signed_txn.raw_transaction
                            )
                        )
                        logger.info(f"  ✅ Transaction sent via MEV protection: {tx_hash.hex()}")
                    except Exception as mev_err:
                        logger.warning(f"  MEV protection failed, falling back to public mempool: {mev_err}")
                        tx_hash = self.web3.eth.send_raw_transaction(signed_txn.raw_transaction)
                        logger.info(f"  ✅ Transaction sent (public): {tx_hash.hex()}")
                else:
                    tx_hash = self.web3.eth.send_raw_transaction(signed_txn.raw_transaction)
                    logger.info(f"  ✅ Transaction sent: {tx_hash.hex()}")

                # Wait for receipt
                logger.info("  ⏳ Waiting for confirmation...")
                receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

                # Parse result
                if receipt['status'] == 1:
                    logger.info(f"  ✅ Transaction successful!")
                    result['success'] = True
                    result['tx_hash'] = receipt['transactionHash'].hex()
                    result['gas_used'] = receipt['gasUsed']
                    result['gas_price'] = receipt['effectiveGasPrice']
                    result['profit'] = opportunity['net_profit']

                    # Calculate actual profit after gas
                    gas_cost = receipt['gasUsed'] * receipt['effectiveGasPrice']
                    native_price_usd = float(os.getenv('NATIVE_TOKEN_PRICE_USD', '0.80'))
                    gas_cost_usd = gas_cost / 10**18 * native_price_usd
                    token_decimals = opportunity.get('token_decimals', 6)
                    actual_profit = (opportunity['net_profit'] / 10**token_decimals) - gas_cost_usd

                    logger.info(f"  💰 Gross profit: {opportunity['net_profit'] / 10**6:.6f} tokens")
                    logger.info(f"  ⛽ Gas cost: ~${gas_cost_usd:.4f}")
                    logger.info(f"  💵 Net profit: ~${actual_profit:.4f}")

                else:
                    logger.error(f"  ❌ Transaction failed (reverted)")
                    result['error'] = "Transaction reverted"
                    result['tx_hash'] = receipt['transactionHash'].hex()

        except (TimeoutError, ConnectionError) as e:
            classified = classify_web3_exception(e)
            logger.error(f"  ❌ RPC failure ({type(classified).__name__}): {e}")
            result['error'] = str(e)
        except Exception as e:
            classified = classify_web3_exception(e)
            logger.error(f"  ❌ Execution failed ({type(classified).__name__}): {e}", extra={"retryable": classified.retryable})
            result['error'] = str(e)

        # Log execution time
        execution_time = time.time() - start_time
        logger.info(f"  ⏱️  Execution time: {execution_time:.2f}s")

        # Update database if opportunity_id provided
        if opportunity_id:
            self._log_execution(opportunity_id, result, execution_time)

        return result

    def _log_execution(
        self,
        opportunity_id: str,
        result: Dict,
        execution_time: float
    ):
        """
        Log execution result to database.

        Args:
            opportunity_id: Opportunity string ID (opportunity_id column)
            result: Execution result
            execution_time: Time taken to execute
        """
        try:
            with get_db() as db:
                # Look up opportunity by string ID, get integer PK
                opp = db.query(Opportunity).filter_by(
                    opportunity_id=opportunity_id
                ).first()

                if not opp:
                    logger.warning(f"Opportunity {opportunity_id} not found in DB")
                    return

                # Update opportunity status
                if result['success']:
                    opp.status = OpportunityStatus.EXECUTED
                    opp.executed_at = datetime.utcnow()
                    opp.transaction_hash = result.get('tx_hash')
                else:
                    opp.status = OpportunityStatus.FAILED

                chain_id = self.web3.eth.chain_id
                gas_price_gwei = Decimal(str(result.get('gas_price', 0))) / Decimal(10**9) if result.get('gas_price') else Decimal(0)

                # Create transaction record using integer FK
                tx_record = None
                if result.get('tx_hash'):
                    tx_record = Transaction(
                        tx_hash=result['tx_hash'],
                        opportunity_id=opp.id,  # Integer FK
                        chain_id=chain_id,
                        from_address=self.address,
                        to_address=self.contract_address,
                        status=TransactionStatus.CONFIRMED if result['success'] else TransactionStatus.FAILED,
                        gas_limit=result.get('gas_used', 600000),
                        gas_used=result.get('gas_used'),
                        gas_price_gwei=gas_price_gwei,
                        nonce=result.get('nonce', 0),
                    )
                    db.add(tx_record)
                    db.flush()  # Get tx_record.id

                    # Create trade result if successful
                    if result['success']:
                        gas_cost_wei = (result.get('gas_used', 0) or 0) * (result.get('gas_price', 0) or 0)
                        # Flash loan fee: 0.05% (5 bps)
                        flash_loan_fee = (opp.amount_in * 5) // 10000
                        # result['profit'] is already net of flash loan fee (from detector)
                        # so gross = net + fee, and net_profit_amount = result['profit']
                        trade_result = TradeResult(
                            opportunity_id=opp.id,  # Integer FK
                            transaction_id=tx_record.id,  # Integer FK
                            success=True,
                            profit_token=opp.token_in,
                            profit_amount=result.get('profit', 0) + flash_loan_fee,
                            gas_cost_wei=gas_cost_wei,
                            flash_loan_fee=flash_loan_fee,
                            net_profit_amount=result.get('profit', 0),
                            execution_time_ms=int(execution_time * 1000),
                        )
                        db.add(trade_result)

                # Log execution step
                exec_log = ExecutionLog(
                    opportunity_id=opp.id,  # Integer FK
                    level='INFO' if result['success'] else 'ERROR',
                    message=f"Execution {'succeeded' if result['success'] else 'failed'}: {result.get('error', 'OK')}",
                    step='execution',
                    data={
                        'tx_hash': result.get('tx_hash'),
                        'gas_used': result.get('gas_used'),
                        'execution_time_ms': int(execution_time * 1000),
                        'error': result.get('error'),
                    }
                )
                db.add(exec_log)

                db.commit()
                logger.info(f"Logged to database: {opportunity_id[:10]}...")

        except (OSError, ConnectionError) as e:
            classified = DatabaseError(str(e))
            logger.error(f"Database connection failure ({type(classified).__name__}): {e}")
        except Exception as e:
            classified = classify_web3_exception(e)
            logger.error(f"{type(classified).__name__}: Failed to log execution to database: {e}", extra={"retryable": classified.retryable})

    def check_balance(self, token_address: str) -> int:
        """
        Check token balance of executor address.

        Args:
            token_address: Token address to check

        Returns:
            Balance in token units
        """
        # ERC20 balanceOf ABI
        abi = [
            {
                "inputs": [{"internalType": "address", "name": "account", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function"
            }
        ]

        token = self.web3.eth.contract(
            address=self.web3.to_checksum_address(token_address),
            abi=abi
        )

        return token.functions.balanceOf(self.address).call()

    def monitor_opportunities(self, check_interval: int = 5):
        """
        Monitor database for new opportunities and execute them.

        Args:
            check_interval: Seconds between database checks
        """
        logger.info("🚀 Starting Orchestrator - monitoring for opportunities...")

        try:
            while True:
                with get_db() as db:
                    # Find detected opportunities
                    opportunities = db.query(Opportunity).filter(
                        Opportunity.status == OpportunityStatus.DETECTED
                    ).order_by(
                        Opportunity.expected_profit.desc()
                    ).limit(5).all()

                    if opportunities:
                        logger.info(f"Found {len(opportunities)} pending opportunities")

                        for opp in opportunities:
                            # Convert to dict
                            opportunity_dict = {
                                'direction': opp.dex_path[0] + '→' + opp.dex_path[1] if len(opp.dex_path) >= 2 else 'unknown',
                                'token_in': opp.token_in,
                                'token_out': opp.token_out,
                                'amount_in': opp.amount_in,
                                'net_profit': opp.expected_profit,
                                'v3_fee': opp.extra_data.get('v3_fee', 3000) if opp.extra_data else 3000
                            }

                            # Mark as executing
                            opp.status = OpportunityStatus.EXECUTING
                            db.commit()

                            # Execute
                            self.execute_opportunity(
                                opportunity_dict,
                                opportunity_id=opp.opportunity_id
                            )

                time.sleep(check_interval)

        except KeyboardInterrupt:
            logger.info("\n⛔ Orchestrator stopped by user")
        except (TimeoutError, ConnectionError) as e:
            classified = classify_web3_exception(e)
            logger.error(f"❌ Orchestrator RPC failure ({type(classified).__name__}): {e}", exc_info=True)
        except Exception as e:
            classified = classify_web3_exception(e)
            logger.error(f"❌ Orchestrator error ({type(classified).__name__}): {e}", exc_info=True, extra={"retryable": classified.retryable})


if __name__ == "__main__":
    from src.utils.key_manager import load_private_key

    # Load configuration
    rpc_url = os.getenv("POLYGON_RPC_URL", "http://localhost:8545")
    contract_address = os.getenv("FLASH_LOAN_ARBITRAGE_ADDRESS")
    v3_adapter = os.getenv("UNISWAP_V3_ADAPTER_ADDRESS")
    v2_adapter = os.getenv("UNISWAP_V2_ADAPTER_ADDRESS")
    dry_run = os.getenv("DRY_RUN", "false").lower() == "true"

    if not all([contract_address, v3_adapter, v2_adapter]):
        logger.error("Missing required environment variables")
        logger.error("Required: FLASH_LOAN_ARBITRAGE_ADDRESS, UNISWAP_V3_ADAPTER_ADDRESS, UNISWAP_V2_ADAPTER_ADDRESS")
        logger.error("Key: Set KEYSTORE_FILE or PRIVATE_KEY env var")
        exit(1)

    # Load private key securely (keystore or env var)
    private_key = load_private_key()

    # Initialize Web3
    web3 = Web3(Web3.HTTPProvider(rpc_url))

    if not web3.is_connected():
        logger.error("Failed to connect to blockchain")
        exit(1)

    logger.info(f"Connected to blockchain (Chain ID: {web3.eth.chain_id})")

    # Initialize orchestrator
    orchestrator = FlashLoanOrchestrator(
        web3=web3,
        contract_address=contract_address,
        private_key=private_key,
        v3_adapter_address=v3_adapter,
        v2_adapter_address=v2_adapter,
        dry_run=dry_run
    )

    # Start monitoring
    orchestrator.monitor_opportunities()
