"""
Opportunity Detector for Flash Loan Arbitrage Bot

Monitors DEX prices and identifies profitable arbitrage opportunities.
"""

import os
import time
import logging
from typing import List, Dict, Optional, Tuple
from decimal import Decimal
from datetime import datetime
import asyncio

from web3 import Web3
from web3.contract import Contract
from dotenv import load_dotenv

from src.db.database import get_db
from src.db.models import Opportunity, OpportunityStatus, Chain, DEX, Token

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class OpportunityDetector:
    """
    Detects arbitrage opportunities across DEXs.

    Monitors price differences between Uniswap V3 and QuickSwap,
    calculates profitability after fees, and logs opportunities to database.
    """

    # Flash loan fee from Aave V3 (0.05%)
    FLASH_LOAN_FEE_BPS = 5

    # Uniswap V3 fee tiers
    V3_FEE_LOW = 500      # 0.05%
    V3_FEE_MEDIUM = 3000  # 0.3%
    V3_FEE_HIGH = 10000   # 1%

    def __init__(
        self,
        web3: Web3,
        min_profit_usd: float = 1.0,
        max_gas_price_gwei: int = 100,
        check_interval: int = 5
    ):
        """
        Initialize the opportunity detector.

        Args:
            web3: Web3 instance connected to blockchain
            min_profit_usd: Minimum profit threshold in USD
            max_gas_price_gwei: Maximum acceptable gas price
            check_interval: Seconds between price checks
        """
        self.web3 = web3
        self.min_profit_usd = min_profit_usd
        self.max_gas_price_gwei = max_gas_price_gwei
        self.check_interval = check_interval

        # Contract addresses from environment
        self.v3_quoter = self.web3.to_checksum_address(
            os.getenv("UNISWAP_V3_QUOTER", "0x61fFE014bA17989E743c5F6cB21bF9697530B21e")
        )
        self.v2_router = self.web3.to_checksum_address(
            os.getenv("QUICKSWAP_ROUTER", "0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff")
        )

        # Token addresses
        self.usdc = self.web3.to_checksum_address(
            os.getenv("USDC_ADDRESS", "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174")
        )
        self.wmatic = self.web3.to_checksum_address(
            os.getenv("WMATIC_ADDRESS", "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270")
        )
        self.weth = self.web3.to_checksum_address(
            os.getenv("WETH_ADDRESS", "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619")
        )
        self.dai = self.web3.to_checksum_address(
            os.getenv("DAI_ADDRESS", "0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063")
        )

        # Initialize contracts
        self._init_contracts()

        # Trading pairs to monitor
        self.trading_pairs = [
            (self.usdc, self.wmatic),
            (self.usdc, self.weth),
            (self.wmatic, self.weth),
            (self.dai, self.usdc),
        ]

        logger.info(f"OpportunityDetector initialized")
        logger.info(f"Min profit: ${min_profit_usd}")
        logger.info(f"Max gas: {max_gas_price_gwei} gwei")
        logger.info(f"Monitoring {len(self.trading_pairs)} pairs")

    def _init_contracts(self):
        """Initialize Web3 contract instances."""
        # Uniswap V3 QuoterV2 ABI (updated for struct input)
        quoter_abi = [
            {
                "inputs": [
                    {
                        "components": [
                            {"internalType": "address", "name": "tokenIn", "type": "address"},
                            {"internalType": "address", "name": "tokenOut", "type": "address"},
                            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
                            {"internalType": "uint24", "name": "fee", "type": "uint24"},
                            {"internalType": "uint160", "name": "sqrtPriceLimitX96", "type": "uint160"}
                        ],
                        "internalType": "struct IQuoterV2.QuoteExactInputSingleParams",
                        "name": "params",
                        "type": "tuple"
                    }
                ],
                "name": "quoteExactInputSingle",
                "outputs": [
                    {"internalType": "uint256", "name": "amountOut", "type": "uint256"},
                    {"internalType": "uint160", "name": "sqrtPriceX96After", "type": "uint160"},
                    {"internalType": "uint32", "name": "initializedTicksCrossed", "type": "uint32"},
                    {"internalType": "uint256", "name": "gasEstimate", "type": "uint256"}
                ],
                "stateMutability": "nonpayable",
                "type": "function"
            }
        ]

        # QuickSwap Router ABI (minimal)
        router_abi = [
            {
                "inputs": [
                    {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
                    {"internalType": "address[]", "name": "path", "type": "address[]"}
                ],
                "name": "getAmountsOut",
                "outputs": [
                    {"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}
                ],
                "stateMutability": "view",
                "type": "function"
            }
        ]

        self.v3_quoter_contract = self.web3.eth.contract(
            address=self.v3_quoter,
            abi=quoter_abi
        )

        self.v2_router_contract = self.web3.eth.contract(
            address=self.v2_router,
            abi=router_abi
        )

    def get_v3_quote(
        self,
        token_in: str,
        token_out: str,
        amount_in: int,
        fee: int = V3_FEE_MEDIUM
    ) -> Optional[int]:
        """
        Get quote from Uniswap V3.

        Args:
            token_in: Input token address
            token_out: Output token address
            amount_in: Amount to swap
            fee: Fee tier (500, 3000, or 10000)

        Returns:
            Amount out or None if quote fails
        """
        try:
            params = {
                'tokenIn': token_in,
                'tokenOut': token_out,
                'amountIn': amount_in,
                'fee': fee,
                'sqrtPriceLimitX96': 0
            }
            result = self.v3_quoter_contract.functions.quoteExactInputSingle(params).call()
            amount_out = result[0]  # First element is amountOut
            return amount_out
        except Exception as e:
            logger.debug(f"V3 quote failed for {token_in[:6]}→{token_out[:6]} fee={fee}: {e}")
            return None

    def get_v2_quote(
        self,
        token_in: str,
        token_out: str,
        amount_in: int
    ) -> Optional[int]:
        """
        Get quote from QuickSwap (Uniswap V2 fork).

        Args:
            token_in: Input token address
            token_out: Output token address
            amount_in: Amount to swap

        Returns:
            Amount out or None if quote fails
        """
        try:
            path = [token_in, token_out]
            amounts = self.v2_router_contract.functions.getAmountsOut(
                amount_in,
                path
            ).call()
            return amounts[-1]  # Last element is output amount
        except Exception as e:
            logger.debug(f"V2 quote failed for {token_in[:6]}→{token_out[:6]}: {e}")
            return None

    def find_best_v3_fee(
        self,
        token_in: str,
        token_out: str,
        amount_in: int
    ) -> Tuple[Optional[int], Optional[int]]:
        """
        Find the best Uniswap V3 fee tier for a swap.

        Args:
            token_in: Input token address
            token_out: Output token address
            amount_in: Amount to swap

        Returns:
            Tuple of (best_amount_out, best_fee) or (None, None)
        """
        best_amount = None
        best_fee = None

        for fee in [self.V3_FEE_LOW, self.V3_FEE_MEDIUM, self.V3_FEE_HIGH]:
            amount_out = self.get_v3_quote(token_in, token_out, amount_in, fee)
            if amount_out and (best_amount is None or amount_out > best_amount):
                best_amount = amount_out
                best_fee = fee

        return best_amount, best_fee

    def calculate_arbitrage(
        self,
        token_a: str,
        token_b: str,
        amount_in: int
    ) -> List[Dict]:
        """
        Calculate arbitrage opportunities for a token pair.

        Checks both directions:
        1. V3 (A→B) then V2 (B→A)
        2. V2 (A→B) then V3 (B→A)

        Args:
            token_a: First token address
            token_b: Second token address
            amount_in: Flash loan amount

        Returns:
            List of profitable opportunities
        """
        opportunities = []

        # Path 1: Uniswap V3 then QuickSwap
        v3_out, v3_fee = self.find_best_v3_fee(token_a, token_b, amount_in)
        if v3_out:
            v2_out = self.get_v2_quote(token_b, token_a, v3_out)
            if v2_out:
                profit = v2_out - amount_in
                profit_after_fees = self._calculate_profit_after_fees(amount_in, profit)

                if profit_after_fees > 0:
                    opportunities.append({
                        'direction': 'V3→V2',
                        'token_in': token_a,
                        'token_out': token_b,
                        'amount_in': amount_in,
                        'v3_fee': v3_fee,
                        'amount_after_v3': v3_out,
                        'amount_after_v2': v2_out,
                        'gross_profit': profit,
                        'net_profit': profit_after_fees,
                        'dex_path': ['uniswap_v3', 'quickswap']
                    })

        # Path 2: QuickSwap then Uniswap V3
        v2_out = self.get_v2_quote(token_a, token_b, amount_in)
        if v2_out:
            v3_out, v3_fee = self.find_best_v3_fee(token_b, token_a, v2_out)
            if v3_out:
                profit = v3_out - amount_in
                profit_after_fees = self._calculate_profit_after_fees(amount_in, profit)

                if profit_after_fees > 0:
                    opportunities.append({
                        'direction': 'V2→V3',
                        'token_in': token_a,
                        'token_out': token_b,
                        'amount_in': amount_in,
                        'amount_after_v2': v2_out,
                        'v3_fee': v3_fee,
                        'amount_after_v3': v3_out,
                        'gross_profit': profit,
                        'net_profit': profit_after_fees,
                        'dex_path': ['quickswap', 'uniswap_v3']
                    })

        return opportunities

    def _calculate_profit_after_fees(self, amount_in: int, gross_profit: int) -> int:
        """
        Calculate net profit after flash loan fees.

        Args:
            amount_in: Flash loan amount
            gross_profit: Profit before fees

        Returns:
            Net profit after fees
        """
        # Flash loan fee: 0.05% = 5 basis points
        flash_loan_fee = (amount_in * self.FLASH_LOAN_FEE_BPS) // 10000
        return gross_profit - flash_loan_fee

    def estimate_gas_cost(self) -> int:
        """
        Estimate gas cost for executing arbitrage.

        Returns:
            Estimated gas cost in wei
        """
        # Rough estimates for flash loan arbitrage
        # Flash loan: ~200k gas
        # Two swaps: ~150k gas each
        # Total: ~500k gas
        estimated_gas = 500000

        try:
            gas_price = self.web3.eth.gas_price
        except Exception as e:
            logger.warning(f"Failed to get gas price: {e}")
            gas_price = self.web3.to_wei(self.max_gas_price_gwei, 'gwei')

        return estimated_gas * gas_price

    def is_profitable_after_gas(
        self,
        net_profit_tokens: int,
        token_address: str,
        token_decimals: int = 6
    ) -> bool:
        """
        Check if opportunity is profitable after gas costs.

        Args:
            net_profit_tokens: Net profit in token units
            token_address: Token address (for price lookup)
            token_decimals: Token decimals

        Returns:
            True if profitable after gas
        """
        # Convert profit to USD (simplified - assumes 1:1 for stablecoins)
        # In production, you'd fetch real prices from an oracle
        profit_usd = net_profit_tokens / (10 ** token_decimals)

        # Get gas cost in ETH
        gas_cost_wei = self.estimate_gas_cost()
        gas_cost_eth = gas_cost_wei / 10**18

        # Assume MATIC price ~$0.80 (in production, fetch from oracle)
        matic_price_usd = 0.80
        gas_cost_usd = gas_cost_eth * matic_price_usd

        net_profit_usd = profit_usd - gas_cost_usd

        logger.debug(f"Profit: ${profit_usd:.2f}, Gas: ${gas_cost_usd:.2f}, Net: ${net_profit_usd:.2f}")

        return net_profit_usd >= self.min_profit_usd

    def log_opportunity(self, opportunity: Dict, token_decimals: int = 6):
        """
        Log opportunity to database.

        Args:
            opportunity: Opportunity details
            token_decimals: Token decimals for display
        """
        try:
            with get_db() as db:
                # Generate opportunity ID
                opp_id = self.web3.keccak(
                    text=f"{opportunity['token_in']}-{opportunity['token_out']}-{time.time()}"
                ).hex()

                # Create opportunity record
                opp = Opportunity(
                    opportunity_id=opp_id,
                    chain_id=137,  # Polygon
                    status=OpportunityStatus.DETECTED,
                    token_in=opportunity['token_in'],
                    token_out=opportunity['token_out'],
                    amount_in=opportunity['amount_in'],
                    expected_profit=opportunity['net_profit'],
                    dex_path=opportunity['dex_path'],
                    token_path=[opportunity['token_in'], opportunity['token_out'], opportunity['token_in']],
                    extra_data={
                        'direction': opportunity['direction'],
                        'gross_profit': opportunity['gross_profit'],
                        'v3_fee': opportunity.get('v3_fee'),
                        'gas_estimate': self.estimate_gas_cost()
                    }
                )

                db.add(opp)
                db.commit()

                profit_display = opportunity['net_profit'] / (10 ** token_decimals)
                logger.info(f"✅ Opportunity logged: {opportunity['direction']} | "
                           f"Net profit: {profit_display:.6f} tokens | ID: {opp_id[:10]}...")

        except Exception as e:
            logger.error(f"Failed to log opportunity: {e}")

    def scan_opportunities(self) -> List[Dict]:
        """
        Scan all trading pairs for arbitrage opportunities.

        Returns:
            List of profitable opportunities
        """
        all_opportunities = []

        # Test amounts (in smallest unit - e.g., USDC has 6 decimals)
        test_amounts = [
            1000 * 10**6,   # $1,000
            5000 * 10**6,   # $5,000
            10000 * 10**6,  # $10,000
        ]

        logger.info(f"🔍 Scanning {len(self.trading_pairs)} pairs with {len(test_amounts)} amounts...")

        for token_a, token_b in self.trading_pairs:
            for amount in test_amounts:
                try:
                    opportunities = self.calculate_arbitrage(token_a, token_b, amount)

                    for opp in opportunities:
                        # Check if profitable after gas
                        if self.is_profitable_after_gas(
                            opp['net_profit'],
                            opp['token_in'],
                            token_decimals=6
                        ):
                            all_opportunities.append(opp)
                            self.log_opportunity(opp)

                except Exception as e:
                    logger.error(f"Error scanning {token_a[:6]}↔{token_b[:6]}: {e}")

        return all_opportunities

    def run(self, continuous: bool = True):
        """
        Run the opportunity detector.

        Args:
            continuous: If True, run continuously. If False, run once.
        """
        logger.info("🚀 Starting Opportunity Detector")

        iteration = 0
        try:
            while True:
                iteration += 1
                logger.info(f"\n{'='*60}")
                logger.info(f"Iteration #{iteration} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                logger.info(f"{'='*60}")

                # Check gas price
                try:
                    current_gas = self.web3.eth.gas_price
                    current_gas_gwei = self.web3.from_wei(current_gas, 'gwei')
                    logger.info(f"Current gas price: {current_gas_gwei:.2f} gwei")

                    if current_gas_gwei > self.max_gas_price_gwei:
                        logger.warning(f"⚠️  Gas too high ({current_gas_gwei:.2f} > {self.max_gas_price_gwei}), skipping...")
                        time.sleep(self.check_interval)
                        continue
                except Exception as e:
                    logger.warning(f"Failed to check gas price: {e}")

                # Scan for opportunities
                opportunities = self.scan_opportunities()

                if opportunities:
                    logger.info(f"🎯 Found {len(opportunities)} profitable opportunities!")
                else:
                    logger.info("No profitable opportunities found this iteration.")

                if not continuous:
                    break

                logger.info(f"Sleeping for {self.check_interval} seconds...")
                time.sleep(self.check_interval)

        except KeyboardInterrupt:
            logger.info("\n⛔ Detector stopped by user")
        except Exception as e:
            logger.error(f"❌ Detector error: {e}", exc_info=True)


if __name__ == "__main__":
    # Initialize Web3
    rpc_url = os.getenv("POLYGON_RPC_URL", "http://localhost:8545")
    web3 = Web3(Web3.HTTPProvider(rpc_url))

    if not web3.is_connected():
        logger.error("❌ Failed to connect to blockchain")
        exit(1)

    logger.info(f"✅ Connected to blockchain (Chain ID: {web3.eth.chain_id})")

    # Initialize detector
    detector = OpportunityDetector(
        web3=web3,
        min_profit_usd=float(os.getenv("MIN_PROFIT_USD", "1.0")),
        max_gas_price_gwei=int(os.getenv("MAX_GAS_PRICE_GWEI", "100")),
        check_interval=5
    )

    # Run detector
    detector.run(continuous=True)
