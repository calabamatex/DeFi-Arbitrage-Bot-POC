"""
Flash Loan Orchestrator for Arbitrage Bot

Executes arbitrage opportunities using Aave V3 flash loans.
"""

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

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
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
        dry_run: bool = False
    ):
        """
        Initialize the orchestrator.

        Args:
            web3: Web3 instance
            contract_address: FlashLoanArbitrageV2 address
            private_key: Private key for signing transactions
            v3_adapter_address: UniswapV3Adapter address
            v2_adapter_address: UniswapV2Adapter address
            dry_run: If True, simulate without sending transactions
        """
        self.web3 = web3
        self.contract_address = web3.to_checksum_address(contract_address)
        self.v3_adapter = web3.to_checksum_address(v3_adapter_address)
        self.v2_adapter = web3.to_checksum_address(v2_adapter_address)
        self.dry_run = dry_run

        # Initialize account
        self.account = Account.from_key(private_key)
        self.address = self.account.address

        logger.info(f"FlashLoanOrchestrator initialized")
        logger.info(f"Contract: {self.contract_address}")
        logger.info(f"Executor: {self.address}")
        logger.info(f"Dry run: {dry_run}")

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
        except Exception as e:
            logger.error(f"Failed to verify contract: {e}")

    def encode_v3_swap_data(self, fee: int, deadline: int) -> bytes:
        """
        Encode Uniswap V3 swap data.

        Args:
            fee: Fee tier (500, 3000, or 10000)
            deadline: Transaction deadline

        Returns:
            Encoded bytes
        """
        # For V3, we encode: fee (uint24) + deadline (uint256)
        return self.web3.codec.encode(
            ['uint24', 'uint256'],
            [fee, deadline]
        )

    def build_swap_steps(
        self,
        opportunity: Dict,
        deadline: int
    ) -> List[Tuple]:
        """
        Build swap steps from opportunity data.

        Args:
            opportunity: Opportunity dict from detector
            deadline: Transaction deadline timestamp

        Returns:
            List of swap step tuples
        """
        steps = []

        direction = opportunity['direction']
        token_in = opportunity['token_in']
        token_out = opportunity['token_out']
        amount_in = opportunity['amount_in']

        if direction == 'V3→V2':
            # Step 1: Uniswap V3 (token_in → token_out)
            v3_fee = opportunity['v3_fee']
            v3_data = self.encode_v3_swap_data(v3_fee, deadline)

            steps.append((
                self.v3_adapter,              # adapter
                token_in,                     # tokenIn
                token_out,                    # tokenOut
                0,                            # minAmountOut (will calculate)
                v3_data                       # data
            ))

            # Step 2: QuickSwap (token_out → token_in)
            steps.append((
                self.v2_adapter,              # adapter
                token_out,                    # tokenIn
                token_in,                     # tokenOut
                opportunity['amount_in'] + opportunity['net_profit'],  # minAmountOut
                b''                           # data (empty for V2)
            ))

        elif direction == 'V2→V3':
            # Step 1: QuickSwap (token_in → token_out)
            steps.append((
                self.v2_adapter,              # adapter
                token_in,                     # tokenIn
                token_out,                    # tokenOut
                0,                            # minAmountOut
                b''                           # data
            ))

            # Step 2: Uniswap V3 (token_out → token_in)
            v3_fee = opportunity['v3_fee']
            v3_data = self.encode_v3_swap_data(v3_fee, deadline)

            steps.append((
                self.v3_adapter,              # adapter
                token_out,                    # tokenIn
                token_in,                     # tokenOut
                opportunity['amount_in'] + opportunity['net_profit'],  # minAmountOut
                v3_data                       # data
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
        except Exception as e:
            logger.warning(f"Gas estimation failed: {e}, using default")
            # Default: 600k gas for flash loan arbitrage
            return 600000

    def build_transaction(
        self,
        opportunity: Dict,
        gas_price: Optional[int] = None
    ) -> Dict:
        """
        Build the arbitrage transaction.

        Args:
            opportunity: Opportunity data
            gas_price: Optional gas price (uses network price if None)

        Returns:
            Transaction dict ready to sign
        """
        # Get deadline (5 minutes from now)
        deadline = int(time.time()) + 300

        # Build swap steps
        steps = self.build_swap_steps(opportunity, deadline)

        # Build arbitrage params
        params = (
            steps,                           # steps
            opportunity['amount_in'],        # flashLoanAmount
            opportunity['token_in'],         # flashLoanAsset
            opportunity['amount_in'] + opportunity['net_profit'],  # minFinalAmount
            deadline                         # deadline
        )

        # Build transaction
        transaction = self.contract.functions.executeArbitrage(
            params
        ).build_transaction({
            'from': self.address,
            'nonce': self.web3.eth.get_transaction_count(self.address),
            'gas': 0,  # Will be estimated
            'maxFeePerGas': gas_price or self.web3.eth.gas_price,
            'maxPriorityFeePerGas': self.web3.to_wei(2, 'gwei'),
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

            if self.dry_run:
                logger.info("  [DRY RUN] Transaction built successfully")
                result['success'] = True
                result['tx_hash'] = '0x' + '0' * 64
                result['gas_used'] = transaction['gas']
                result['gas_price'] = transaction['maxFeePerGas']
                result['profit'] = opportunity['net_profit']

            else:
                # Sign transaction
                signed_txn = self.account.sign_transaction(transaction)

                # Send transaction
                logger.info("  📤 Sending transaction...")
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
                    gas_cost_tokens = gas_cost / 10**18 * 0.80  # Assume MATIC = $0.80
                    actual_profit = (opportunity['net_profit'] / 10**6) - gas_cost_tokens

                    logger.info(f"  💰 Gross profit: {opportunity['net_profit'] / 10**6:.6f} tokens")
                    logger.info(f"  ⛽ Gas cost: ~${gas_cost_tokens:.4f}")
                    logger.info(f"  💵 Net profit: ~${actual_profit:.4f}")

                else:
                    logger.error(f"  ❌ Transaction failed (reverted)")
                    result['error'] = "Transaction reverted"
                    result['tx_hash'] = receipt['transactionHash'].hex()

        except Exception as e:
            logger.error(f"  ❌ Execution failed: {e}")
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
            opportunity_id: Opportunity ID
            result: Execution result
            execution_time: Time taken to execute
        """
        try:
            with get_db() as db:
                # Update opportunity status
                opp = db.query(Opportunity).filter_by(
                    opportunity_id=opportunity_id
                ).first()

                if opp:
                    if result['success']:
                        opp.status = OpportunityStatus.EXECUTED
                    else:
                        opp.status = OpportunityStatus.FAILED

                    # Create transaction record
                    if result['tx_hash']:
                        transaction = Transaction(
                            tx_hash=result['tx_hash'],
                            opportunity_id=opportunity_id,
                            chain_id=137,
                            status=TransactionStatus.SUCCESS if result['success'] else TransactionStatus.FAILED,
                            gas_used=result['gas_used'],
                            gas_price=result['gas_price']
                        )
                        db.add(transaction)

                        # Create trade result if successful
                        if result['success']:
                            trade_result = TradeResult(
                                tx_hash=result['tx_hash'],
                                opportunity_id=opportunity_id,
                                chain_id=137,
                                token_in=opp.token_in,
                                token_out=opp.token_out,
                                amount_in=opp.amount_in,
                                amount_out=opp.amount_in + result['profit'],
                                profit=result['profit'],
                                gas_cost_wei=result['gas_used'] * result['gas_price']
                            )
                            db.add(trade_result)

                    # Log execution
                    exec_log = ExecutionLog(
                        opportunity_id=opportunity_id,
                        chain_id=137,
                        status='success' if result['success'] else 'failed',
                        tx_hash=result['tx_hash'],
                        gas_used=result['gas_used'],
                        execution_time_ms=int(execution_time * 1000),
                        error_message=result.get('error')
                    )
                    db.add(exec_log)

                    db.commit()
                    logger.info(f"  📝 Logged to database: {opportunity_id[:10]}...")

        except Exception as e:
            logger.error(f"Failed to log execution to database: {e}")

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

                            # Mark as processing
                            opp.status = OpportunityStatus.PROCESSING
                            db.commit()

                            # Execute
                            self.execute_opportunity(
                                opportunity_dict,
                                opportunity_id=opp.opportunity_id
                            )

                time.sleep(check_interval)

        except KeyboardInterrupt:
            logger.info("\n⛔ Orchestrator stopped by user")
        except Exception as e:
            logger.error(f"❌ Orchestrator error: {e}", exc_info=True)


if __name__ == "__main__":
    # Load configuration
    rpc_url = os.getenv("POLYGON_RPC_URL", "http://localhost:8545")
    contract_address = os.getenv("FLASH_LOAN_ARBITRAGE_ADDRESS")
    private_key = os.getenv("PRIVATE_KEY")
    v3_adapter = os.getenv("UNISWAP_V3_ADAPTER_ADDRESS")
    v2_adapter = os.getenv("UNISWAP_V2_ADAPTER_ADDRESS")
    dry_run = os.getenv("DRY_RUN", "false").lower() == "true"

    if not all([contract_address, private_key, v3_adapter, v2_adapter]):
        logger.error("❌ Missing required environment variables")
        logger.error("Required: FLASH_LOAN_ARBITRAGE_ADDRESS, PRIVATE_KEY, UNISWAP_V3_ADAPTER_ADDRESS, UNISWAP_V2_ADAPTER_ADDRESS")
        exit(1)

    # Initialize Web3
    web3 = Web3(Web3.HTTPProvider(rpc_url))

    if not web3.is_connected():
        logger.error("❌ Failed to connect to blockchain")
        exit(1)

    logger.info(f"✅ Connected to blockchain (Chain ID: {web3.eth.chain_id})")

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
