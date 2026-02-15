"""
Liquidation Orchestrator

Builds and executes liquidation transactions via the FlashLoanLiquidator contract.
"""

import os
import time
import logging
from typing import Dict, List, Optional
from decimal import Decimal
from datetime import datetime

from web3 import Web3
from eth_account import Account
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class LiquidationOrchestrator:
    """
    Executes profitable liquidations through the FlashLoanLiquidator contract.

    Takes liquidation opportunities from the LiquidationDetector
    and submits them on-chain.
    """

    def __init__(
        self,
        web3: Web3,
        liquidator_address: str,
        private_key: str,
        v3_adapter_address: str,
        v2_adapter_address: str,
        dry_run: bool = False,
        tx_deadline_seconds: int = None,
        curve_adapter_address: str = None,
    ):
        """
        Args:
            web3: Web3 instance
            liquidator_address: FlashLoanLiquidator contract address
            private_key: Private key for signing transactions
            v3_adapter_address: UniswapV3Adapter address
            v2_adapter_address: UniswapV2Adapter address
            dry_run: If True, simulate without sending transactions
            tx_deadline_seconds: Transaction deadline in seconds
            curve_adapter_address: Optional CurveAdapter address
        """
        self.web3 = web3
        self.liquidator_address = web3.to_checksum_address(liquidator_address)
        self.v3_adapter = web3.to_checksum_address(v3_adapter_address)
        self.v2_adapter = web3.to_checksum_address(v2_adapter_address)
        self.curve_adapter = (
            web3.to_checksum_address(curve_adapter_address) if curve_adapter_address else None
        )
        self.dry_run = dry_run
        self.tx_deadline_seconds = tx_deadline_seconds or int(
            os.getenv('TX_DEADLINE_SECONDS', '120')
        )

        self.account = Account.from_key(private_key)
        self.address = self.account.address

        self._init_contract()

        logger.info(f"LiquidationOrchestrator initialized")
        logger.info(f"Liquidator contract: {self.liquidator_address}")
        logger.info(f"Executor: {self.address}")
        logger.info(f"Dry run: {dry_run}")

    def _init_contract(self):
        """Initialize the FlashLoanLiquidator contract."""
        abi = [
            {
                "inputs": [
                    {
                        "components": [
                            {"internalType": "address", "name": "collateralAsset", "type": "address"},
                            {"internalType": "address", "name": "debtAsset", "type": "address"},
                            {"internalType": "address", "name": "user", "type": "address"},
                            {"internalType": "uint256", "name": "debtToCover", "type": "uint256"},
                            {"internalType": "address", "name": "adapter", "type": "address"},
                            {"internalType": "bytes", "name": "swapData", "type": "bytes"},
                            {"internalType": "uint256", "name": "minProfit", "type": "uint256"},
                            {"internalType": "uint256", "name": "deadline", "type": "uint256"},
                        ],
                        "internalType": "struct FlashLoanLiquidator.LiquidationParams",
                        "name": "params",
                        "type": "tuple",
                    }
                ],
                "name": "executeLiquidation",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function",
            },
            {
                "inputs": [],
                "name": "paused",
                "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
                "stateMutability": "view",
                "type": "function",
            },
            {
                "inputs": [],
                "name": "owner",
                "outputs": [{"internalType": "address", "name": "", "type": "address"}],
                "stateMutability": "view",
                "type": "function",
            },
            {
                "inputs": [{"internalType": "address", "name": "", "type": "address"}],
                "name": "totalProfits",
                "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function",
            },
            {
                "inputs": [],
                "name": "liquidationCount",
                "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function",
            },
        ]

        self.contract = self.web3.eth.contract(
            address=self.liquidator_address,
            abi=abi,
        )

        try:
            owner = self.contract.functions.owner().call()
            logger.info(f"Contract owner: {owner}")
            if owner.lower() != self.address.lower():
                logger.warning(f"Executor {self.address} is not contract owner {owner}")
        except Exception as e:
            logger.error(f"Failed to verify contract: {e}")

    def select_adapter(self, collateral_asset: str, debt_asset: str) -> str:
        """
        Select the best DEX adapter for swapping collateral → debt.

        For now, defaults to V3 adapter. Could be extended with
        quote comparison logic.

        Args:
            collateral_asset: Collateral token address
            debt_asset: Debt token address

        Returns:
            Adapter address
        """
        # Default to V3 adapter (deepest liquidity on most chains)
        return self.v3_adapter

    def encode_swap_data(self, adapter: str, fee: int = 3000) -> bytes:
        """Encode adapter-specific swap data."""
        if adapter == self.v3_adapter:
            return self.web3.codec.encode(['uint24'], [fee])
        return b''

    def build_liquidation_params(
        self,
        opportunity: Dict,
        min_profit: int = 0,
    ) -> tuple:
        """
        Build LiquidationParams tuple from an opportunity dict.

        Args:
            opportunity: Liquidation opportunity from detector
            min_profit: Minimum profit in debt token units

        Returns:
            LiquidationParams tuple
        """
        collateral = self.web3.to_checksum_address(opportunity['collateral_asset'])
        debt = self.web3.to_checksum_address(opportunity['debt_asset'])
        user = self.web3.to_checksum_address(opportunity['user'])
        debt_to_cover = opportunity['debt_amount']

        adapter = self.select_adapter(collateral, debt)
        swap_data = self.encode_swap_data(adapter)
        deadline = int(time.time()) + self.tx_deadline_seconds

        return (
            collateral,
            debt,
            user,
            debt_to_cover,
            adapter,
            swap_data,
            min_profit,
            deadline,
        )

    def estimate_gas(self, transaction: Dict) -> int:
        """Estimate gas for a liquidation transaction."""
        try:
            gas_estimate = self.web3.eth.estimate_gas(transaction)
            return int(gas_estimate * 1.2)
        except Exception as e:
            logger.warning(f"Gas estimation failed: {e}, using default")
            return 800000

    def execute_liquidation(
        self,
        opportunity: Dict,
    ) -> Dict:
        """
        Execute a liquidation opportunity.

        Args:
            opportunity: Liquidation opportunity from detector

        Returns:
            Execution result dict
        """
        user_short = opportunity['user'][:10]
        logger.info(
            f"{'[DRY RUN] ' if self.dry_run else ''}Executing liquidation: "
            f"user={user_short}... debt={opportunity['debt_asset'][:10]}..."
        )
        logger.info(f"  Debt to cover: {opportunity['debt_amount']}")
        logger.info(f"  Expected profit: ${opportunity.get('net_profit_usd', 0):.2f}")

        start_time = time.time()
        result = {
            'success': False,
            'tx_hash': None,
            'gas_used': 0,
            'gas_price': 0,
            'profit': 0,
            'error': None,
            'user': opportunity['user'],
        }

        try:
            if self.contract.functions.paused().call():
                raise Exception("Contract is paused")

            # Build params
            min_profit = max(0, int(opportunity.get('net_profit', 0) * 0.5))
            params = self.build_liquidation_params(opportunity, min_profit=min_profit)

            # Get gas pricing
            latest_block = self.web3.eth.get_block('latest')
            base_fee = latest_block.get('baseFeePerGas', self.web3.eth.gas_price)
            max_priority = self.web3.to_wei(2, 'gwei')
            max_fee = base_fee * 2 + max_priority

            transaction = self.contract.functions.executeLiquidation(
                params
            ).build_transaction({
                'from': self.address,
                'nonce': self.web3.eth.get_transaction_count(self.address, 'pending'),
                'gas': 0,
                'maxFeePerGas': max_fee,
                'maxPriorityFeePerGas': max_priority,
                'chainId': self.web3.eth.chain_id,
            })

            transaction['gas'] = self.estimate_gas(transaction)

            # Simulate
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
            except Exception as sim_err:
                logger.error(f"  Simulation FAILED: {sim_err}")
                result['error'] = f"Simulation failed: {sim_err}"
                return result

            if self.dry_run:
                logger.info("  [DRY RUN] Transaction simulated successfully")
                result['success'] = True
                result['tx_hash'] = '0x' + '0' * 64
                result['gas_used'] = transaction['gas']
                result['profit'] = opportunity.get('net_profit', 0)
            else:
                signed_txn = self.account.sign_transaction(transaction)
                tx_hash = self.web3.eth.send_raw_transaction(signed_txn.raw_transaction)
                logger.info(f"  Transaction sent: {tx_hash.hex()}")

                receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

                if receipt['status'] == 1:
                    logger.info("  Transaction successful!")
                    result['success'] = True
                    result['tx_hash'] = receipt['transactionHash'].hex()
                    result['gas_used'] = receipt['gasUsed']
                    result['gas_price'] = receipt['effectiveGasPrice']
                    result['profit'] = opportunity.get('net_profit', 0)

                    gas_cost = receipt['gasUsed'] * receipt['effectiveGasPrice']
                    native_price_usd = float(os.getenv('NATIVE_TOKEN_PRICE_USD', '0.80'))
                    gas_cost_usd = gas_cost / 10**18 * native_price_usd
                    logger.info(f"  Gas cost: ~${gas_cost_usd:.4f}")
                    logger.info(f"  Expected profit: ~${opportunity.get('net_profit_usd', 0):.2f}")
                else:
                    logger.error("  Transaction failed (reverted)")
                    result['error'] = "Transaction reverted"
                    result['tx_hash'] = receipt['transactionHash'].hex()

        except Exception as e:
            logger.error(f"  Execution failed: {e}")
            result['error'] = str(e)

        execution_time = time.time() - start_time
        logger.info(f"  Execution time: {execution_time:.2f}s")

        return result

    def execute_batch(
        self,
        opportunities: List[Dict],
    ) -> List[Dict]:
        """
        Execute a batch of liquidation opportunities.

        Args:
            opportunities: List of liquidation opportunities

        Returns:
            List of execution results
        """
        results = []
        for opp in opportunities:
            result = self.execute_liquidation(opp)
            results.append(result)

            # Small delay between transactions to avoid nonce issues
            if not self.dry_run and result['success']:
                time.sleep(1)

        successful = sum(1 for r in results if r['success'])
        logger.info(
            f"Batch complete: {successful}/{len(results)} successful"
        )
        return results

    def get_contract_stats(self) -> Dict:
        """Get current contract statistics."""
        try:
            count = self.contract.functions.liquidationCount().call()
            paused = self.contract.functions.paused().call()
            return {
                'liquidation_count': count,
                'paused': paused,
                'contract': self.liquidator_address,
            }
        except Exception as e:
            logger.error(f"Failed to get contract stats: {e}")
            return {}
