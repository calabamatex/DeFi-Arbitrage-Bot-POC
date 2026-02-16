"""
Opportunity Detector for Flash Loan Arbitrage Bot

Monitors DEX prices and identifies profitable arbitrage opportunities.
"""

import os
import time
import random
import logging
from itertools import combinations, permutations
from typing import List, Dict, Optional, Tuple
from decimal import Decimal
from datetime import datetime
import asyncio

from web3 import Web3
from web3.contract import Contract
from dotenv import load_dotenv

from src.db.database import get_db
from src.db.models import Opportunity, OpportunityStatus, Chain, DEX, Token
from src.utils.token_registry import TokenRegistry
from src.utils.errors import classify_web3_exception, DatabaseError

# Load environment variables
load_dotenv()

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
        check_interval: int = 5,
        min_flash_loan: int = None,
        max_flash_loan: int = None,
        token_config_dir: str = None,
        max_pairs: int = None,
    ):
        """
        Initialize the opportunity detector.

        Args:
            web3: Web3 instance connected to blockchain
            min_profit_usd: Minimum profit threshold in USD
            max_gas_price_gwei: Maximum acceptable gas price
            check_interval: Seconds between price checks
            min_flash_loan: Minimum flash loan amount (in smallest unit, e.g., USDC has 6 decimals)
            max_flash_loan: Maximum flash loan amount (in smallest unit)
            token_config_dir: Directory containing token JSON configs (default: config/tokens/)
            max_pairs: Maximum trading pairs to scan per iteration
        """
        self.web3 = web3
        self.min_profit_usd = min_profit_usd
        self.max_gas_price_gwei = max_gas_price_gwei
        self.check_interval = check_interval

        # Flash loan optimization bounds
        self.min_flash_loan = min_flash_loan or 500 * 10**6      # Default: $500
        self.max_flash_loan = max_flash_loan or 100000 * 10**6   # Default: $100k

        # Contract addresses from environment
        self.v3_quoter = self.web3.to_checksum_address(
            os.getenv("UNISWAP_V3_QUOTER", "0x61fFE014bA17989E743c5F6cB21bF9697530B21e")
        )
        self.v2_router = self.web3.to_checksum_address(
            os.getenv("QUICKSWAP_ROUTER", "0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff")
        )

        # Initialize contracts
        self._init_contracts()

        # Well-known token shortcuts (always available for backward compat)
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

        # --- Dynamic token loading via TokenRegistry ---
        _max_pairs = max_pairs or int(os.getenv("MAX_PAIRS_PER_SCAN", "50"))
        self.token_registry = TokenRegistry(
            web3=web3,
            config_dir=token_config_dir or os.getenv("TOKEN_CONFIG_DIR"),
            max_pairs=_max_pairs,
        )
        loaded = self.token_registry.load_tokens()

        if loaded > 0:
            # Use registry for decimals and pairs
            self.token_decimals = self.token_registry.get_decimals_map()
            self.trading_pairs = self.token_registry.generate_pairs(
                require_stablecoin_leg=False,
            )
        else:
            # Fallback: hardcoded defaults (backward compat for tests / missing config)
            logger.warning("No token config loaded — using hardcoded defaults")
            self.token_decimals = {
                self.usdc.lower(): 6,
                self.wmatic.lower(): 18,
                self.weth.lower(): 18,
                self.dai.lower(): 18,
            }
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

        # Curve adapter (optional — initialized if CURVE_ADAPTER_ADDRESS is set)
        self.curve_adapter_address = os.getenv("CURVE_ADAPTER_ADDRESS")
        self.curve_adapter_contract = None
        if self.curve_adapter_address:
            curve_adapter_abi = [
                {
                    "inputs": [
                        {"internalType": "address", "name": "tokenIn", "type": "address"},
                        {"internalType": "address", "name": "tokenOut", "type": "address"},
                        {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
                    ],
                    "name": "getQuote",
                    "outputs": [{"internalType": "uint256", "name": "amountOut", "type": "uint256"}],
                    "stateMutability": "view",
                    "type": "function",
                },
                {
                    "inputs": [
                        {"internalType": "address", "name": "tokenIn", "type": "address"},
                        {"internalType": "address", "name": "tokenOut", "type": "address"},
                    ],
                    "name": "hasPool",
                    "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
                    "stateMutability": "view",
                    "type": "function",
                },
            ]
            self.curve_adapter_contract = self.web3.eth.contract(
                address=self.web3.to_checksum_address(self.curve_adapter_address),
                abi=curve_adapter_abi,
            )
            logger.info(f"Curve adapter configured: {self.curve_adapter_address}")

    def get_curve_quote(
        self,
        token_in: str,
        token_out: str,
        amount_in: int,
    ) -> Optional[int]:
        """
        Get quote from Curve via the CurveAdapter's on-chain getQuote.

        Args:
            token_in: Input token address
            token_out: Output token address
            amount_in: Amount to swap

        Returns:
            Amount out or None if quote fails or Curve not configured
        """
        if not self.curve_adapter_contract:
            return None
        try:
            amount_out = self.curve_adapter_contract.functions.getQuote(
                token_in, token_out, amount_in
            ).call()
            return amount_out
        except (TimeoutError, ConnectionError) as e:
            classified = classify_web3_exception(e)
            logger.debug(f"Curve quote RPC failure ({type(classified).__name__}) for {token_in[:6]}→{token_out[:6]}: {e}")
            return None
        except Exception as e:
            classified = classify_web3_exception(e)
            logger.debug(f"Curve quote failed ({type(classified).__name__}) for {token_in[:6]}→{token_out[:6]}: {e}", extra={"retryable": classified.retryable})
            return None

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
        except (TimeoutError, ConnectionError) as e:
            classified = classify_web3_exception(e)
            logger.warning(f"V3 quote RPC failure ({type(classified).__name__}) for {token_in[:6]}→{token_out[:6]} fee={fee}: {e}")
            return None
        except Exception as e:
            classified = classify_web3_exception(e)
            logger.warning(f"V3 quote failed ({type(classified).__name__}) for {token_in[:6]}→{token_out[:6]} fee={fee}: {e}", extra={"retryable": classified.retryable})
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
        except (TimeoutError, ConnectionError) as e:
            classified = classify_web3_exception(e)
            logger.warning(f"V2 quote RPC failure ({type(classified).__name__}) for {token_in[:6]}→{token_out[:6]}: {e}")
            return None
        except Exception as e:
            classified = classify_web3_exception(e)
            logger.warning(f"V2 quote failed ({type(classified).__name__}) for {token_in[:6]}→{token_out[:6]}: {e}", extra={"retryable": classified.retryable})
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

    def _calculate_profit_after_fees(self, amount_in: int, gross_profit: int, flash_loan_fee_bps: int = None) -> int:
        """
        Calculate net profit after flash loan fees.

        Args:
            amount_in: Flash loan amount
            gross_profit: Profit before fees
            flash_loan_fee_bps: Flash loan fee in bps (default: FLASH_LOAN_FEE_BPS)

        Returns:
            Net profit after fees
        """
        fee_bps = flash_loan_fee_bps if flash_loan_fee_bps is not None else self.FLASH_LOAN_FEE_BPS
        flash_loan_fee = (amount_in * fee_bps) // 10000
        return gross_profit - flash_loan_fee

    # ------------------------------------------------------------------
    # Multi-DEX quote aggregation
    # ------------------------------------------------------------------

    def _get_all_dex_quotes(
        self,
        token_in: str,
        token_out: str,
        amount_in: int,
    ) -> List[Tuple[str, int, Optional[int]]]:
        """
        Get quotes from all available DEXs for a single swap.

        Returns:
            List of (dex_name, amount_out, fee_or_none) tuples, sorted best first.
        """
        quotes: List[Tuple[str, int, Optional[int]]] = []

        # Uniswap V3 — try all fee tiers
        v3_out, v3_fee = self.find_best_v3_fee(token_in, token_out, amount_in)
        if v3_out:
            quotes.append(('uniswap_v3', v3_out, v3_fee))

        # QuickSwap / V2
        v2_out = self.get_v2_quote(token_in, token_out, amount_in)
        if v2_out:
            quotes.append(('quickswap', v2_out, None))

        # Curve
        curve_out = self.get_curve_quote(token_in, token_out, amount_in)
        if curve_out:
            quotes.append(('curve', curve_out, None))

        # Sort by best output descending
        quotes.sort(key=lambda q: q[1], reverse=True)
        return quotes

    # ------------------------------------------------------------------
    # Triangular arbitrage detection
    # ------------------------------------------------------------------

    def calculate_triangular_arbitrage(
        self,
        token_a: str,
        token_b: str,
        token_c: str,
        amount_in: int,
    ) -> Optional[Dict]:
        """
        Find best 3-leg arbitrage path: A → B → C → A.

        Tests all DEX combinations per leg and picks the best.

        Args:
            token_a: Flash loan token (start and end)
            token_b: Intermediate token 1
            token_c: Intermediate token 2
            amount_in: Flash loan amount

        Returns:
            Opportunity dict or None
        """
        # Leg 1: A → B
        leg1_quotes = self._get_all_dex_quotes(token_a, token_b, amount_in)
        if not leg1_quotes:
            return None
        dex1, amount_after_1, fee1 = leg1_quotes[0]

        # Leg 2: B → C
        leg2_quotes = self._get_all_dex_quotes(token_b, token_c, amount_after_1)
        if not leg2_quotes:
            return None
        dex2, amount_after_2, fee2 = leg2_quotes[0]

        # Leg 3: C → A
        leg3_quotes = self._get_all_dex_quotes(token_c, token_a, amount_after_2)
        if not leg3_quotes:
            return None
        dex3, amount_after_3, fee3 = leg3_quotes[0]

        gross_profit = amount_after_3 - amount_in
        net_profit = self._calculate_profit_after_fees(amount_in, gross_profit)

        if net_profit <= 0:
            return None

        return {
            'direction': 'triangular',
            'token_in': token_a,
            'token_out': token_a,  # same as token_in for triangular
            'amount_in': amount_in,
            'token_path': [token_a, token_b, token_c, token_a],
            'dex_path': [dex1, dex2, dex3],
            'amounts': [amount_in, amount_after_1, amount_after_2, amount_after_3],
            'fees': [fee1, fee2, fee3],
            'gross_profit': gross_profit,
            'net_profit': net_profit,
        }

    def scan_triangular_opportunities(self) -> List[Dict]:
        """
        Scan 3-token combinations for triangular arbitrage.

        Returns:
            List of profitable triangular opportunities.
        """
        all_opportunities: List[Dict] = []
        tokens = list({addr for pair in self.trading_pairs for addr in pair})

        if len(tokens) < 3:
            return all_opportunities

        # Generate 3-token combos and test all orderings
        tested = 0
        for combo in combinations(tokens, 3):
            for perm in permutations(combo):
                a, b, c = perm
                tested += 1

                # Quick test at min flash loan amount
                decimals_a = self.token_decimals.get(a.lower(), 18)
                test_amount = self.min_flash_loan

                opp = self.calculate_triangular_arbitrage(a, b, c, test_amount)
                if opp and self.is_profitable_after_gas(
                    opp['net_profit'], a, token_decimals=decimals_a
                ):
                    opp['token_decimals'] = decimals_a
                    all_opportunities.append(opp)
                    logger.info(
                        f"Triangular opportunity: "
                        f"{' → '.join(opp['dex_path'])} | "
                        f"Profit: {opp['net_profit'] / 10**decimals_a:.4f}"
                    )

        logger.info(
            f"Scanned {tested} triangular paths, "
            f"found {len(all_opportunities)} profitable"
        )
        return all_opportunities

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
        except (TimeoutError, ConnectionError) as e:
            classified = classify_web3_exception(e)
            logger.warning(f"RPC failure fetching gas price ({type(classified).__name__}): {e}")
            gas_price = self.web3.to_wei(self.max_gas_price_gwei, 'gwei')
        except Exception as e:
            classified = classify_web3_exception(e)
            logger.warning(f"{type(classified).__name__}: Failed to get gas price: {e}", extra={"retryable": classified.retryable})
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

        native_price_usd = float(os.getenv('NATIVE_TOKEN_PRICE_USD', '0.80'))
        gas_cost_usd = gas_cost_eth * native_price_usd

        net_profit_usd = profit_usd - gas_cost_usd

        logger.debug(f"Profit: ${profit_usd:.2f}, Gas: ${gas_cost_usd:.2f}, Net: ${net_profit_usd:.2f}")

        return net_profit_usd >= self.min_profit_usd

    def find_optimal_flash_loan_amount(
        self,
        token_a: str,
        token_b: str,
        direction: str,
        min_amount: int = 500 * 10**6,      # $500 minimum
        max_amount: int = 100000 * 10**6,   # $100k maximum
        token_decimals: int = 6
    ) -> Optional[Dict]:
        """
        Find optimal flash loan amount using binary search with profit sampling.

        Strategy:
        1. Start with initial test to confirm opportunity exists
        2. Use adaptive search to find inflection point where slippage reduces profit
        3. Return amount with maximum net profit

        Args:
            token_a: First token address
            token_b: Second token address
            direction: 'V3→V2' or 'V2→V3'
            min_amount: Minimum flash loan amount to test
            max_amount: Maximum flash loan amount to test
            token_decimals: Token decimals for logging

        Returns:
            Optimal opportunity dict or None if no profitable amount found
        """
        logger.info(f"🔍 Optimizing flash loan amount for {direction}...")

        # Test initial small amount to confirm opportunity exists
        initial_opps = self.calculate_arbitrage(token_a, token_b, min_amount)
        if not initial_opps:
            logger.debug(f"No opportunity at minimum amount ${min_amount / 10**token_decimals:,.0f}")
            return None

        # Filter for the specific direction
        initial_opp = None
        for opp in initial_opps:
            if opp['direction'] == direction:
                initial_opp = opp
                break

        if not initial_opp:
            logger.debug(f"No {direction} opportunity found")
            return None

        # Check if profitable after gas at minimum amount
        if not self.is_profitable_after_gas(initial_opp['net_profit'], token_a, token_decimals):
            logger.debug(f"Not profitable after gas at minimum amount")
            return None

        # Adaptive search: test increasing amounts to find optimal
        best_opp = initial_opp
        best_profit = initial_opp['net_profit']

        # Start with doubling strategy, then refine
        test_amounts = []
        current = min_amount
        while current <= max_amount:
            test_amounts.append(current)
            current *= 2

        # Add some intermediate points for precision
        test_amounts.append(max_amount)
        test_amounts = sorted(set(test_amounts))[:15]  # Limit to 15 tests for speed

        logger.info(f"  Testing {len(test_amounts)} amounts from ${test_amounts[0]/10**token_decimals:,.0f} to ${test_amounts[-1]/10**token_decimals:,.0f}")

        for amount in test_amounts[1:]:  # Skip first (already tested)
            opps = self.calculate_arbitrage(token_a, token_b, amount)
            if not opps:
                # Hit liquidity limit, stop searching higher
                logger.debug(f"  No liquidity at ${amount/10**token_decimals:,.0f}, stopping")
                break

            # Find matching direction
            matching_opp = None
            for opp in opps:
                if opp['direction'] == direction:
                    matching_opp = opp
                    break

            if not matching_opp:
                # Direction no longer profitable
                logger.debug(f"  {direction} not profitable at ${amount/10**token_decimals:,.0f}")
                break

            current_profit = matching_opp['net_profit']

            # Check if still profitable after gas
            if not self.is_profitable_after_gas(current_profit, token_a, token_decimals):
                logger.debug(f"  Not profitable after gas at ${amount/10**token_decimals:,.0f}")
                break

            profit_usd = current_profit / 10**token_decimals
            logger.info(f"  ${amount/10**token_decimals:,.0f} → ${profit_usd:.2f} profit")

            if current_profit > best_profit:
                best_profit = current_profit
                best_opp = matching_opp
            else:
                # Profit decreasing due to slippage, we've passed the optimum
                logger.info(f"  Slippage increasing, optimal amount found")
                break

        optimal_amount = best_opp['amount_in']
        optimal_profit_usd = best_profit / 10**token_decimals

        logger.info(f"✅ Optimal: ${optimal_amount/10**token_decimals:,.0f} flash loan → ${optimal_profit_usd:.2f} profit")

        return best_opp

    def log_opportunity(self, opportunity: Dict, token_decimals: int = 6) -> Optional[str]:
        """
        Log opportunity to database and attach the ID to the opportunity dict.

        Args:
            opportunity: Opportunity details (mutated: 'opportunity_id' key added)
            token_decimals: Token decimals for display

        Returns:
            The generated opportunity_id string, or None on failure
        """
        try:
            with get_db() as db:
                # Generate opportunity ID
                opp_id = self.web3.keccak(
                    text=f"{opportunity['token_in']}-{opportunity['token_out']}-{time.time()}"
                ).hex()

                # Create opportunity record
                # Determine expected_amount_out based on direction
                if opportunity['direction'] == 'V3→V2':
                    expected_amount_out = opportunity.get('amount_after_v2', opportunity['amount_in'] + opportunity['net_profit'])
                else:
                    expected_amount_out = opportunity.get('amount_after_v3', opportunity['amount_in'] + opportunity['net_profit'])

                opp = Opportunity(
                    opportunity_id=opp_id,
                    chain_id=self.web3.eth.chain_id,
                    status=OpportunityStatus.DETECTED,
                    token_in=opportunity['token_in'],
                    token_out=opportunity['token_out'],
                    amount_in=opportunity['amount_in'],
                    expected_amount_out=expected_amount_out,
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

                # Attach ID to opportunity dict so callers can reference it
                opportunity['opportunity_id'] = opp_id

                profit_display = opportunity['net_profit'] / (10 ** token_decimals)
                logger.info(f"✅ Opportunity logged: {opportunity['direction']} | "
                           f"Net profit: {profit_display:.6f} tokens | ID: {opp_id[:10]}...")

                return opp_id

        except (OSError, ConnectionError) as e:
            classified = DatabaseError(str(e))
            logger.error(f"Database connection failure ({type(classified).__name__}): {e}")
            return None
        except Exception as e:
            classified = classify_web3_exception(e)
            logger.error(f"{type(classified).__name__}: Failed to log opportunity: {e}", extra={"retryable": classified.retryable})
            return None

    def scan_opportunities(self) -> List[Dict]:
        """
        Scan all trading pairs for arbitrage opportunities with optimized flash loan amounts.

        Returns:
            List of profitable opportunities (optimized for maximum profit)
        """
        all_opportunities = []

        logger.info(f"🔍 Scanning {len(self.trading_pairs)} pairs with flash loan optimization...")

        for token_a, token_b in self.trading_pairs:
            try:
                # Determine token_a decimals for this pair
                decimals_a = self.token_decimals.get(token_a.lower(), 18)

                # Quick test with minimum amount to check if any opportunity exists
                quick_test = self.calculate_arbitrage(token_a, token_b, self.min_flash_loan)

                if not quick_test:
                    logger.debug(f"No opportunity for {token_a[:6]}↔{token_b[:6]}")
                    continue

                # Extract directions that are profitable
                profitable_directions = []
                for opp in quick_test:
                    opp_decimals = self.token_decimals.get(opp['token_in'].lower(), decimals_a)
                    if self.is_profitable_after_gas(opp['net_profit'], opp['token_in'], token_decimals=opp_decimals):
                        profitable_directions.append(opp['direction'])

                if not profitable_directions:
                    logger.debug(f"No profitable direction after gas for {token_a[:6]}↔{token_b[:6]}")
                    continue

                # For each profitable direction, find optimal flash loan amount
                for direction in profitable_directions:
                    logger.info(f"Found {direction} opportunity for {token_a[:6]}↔{token_b[:6]}, optimizing...")

                    optimal_opp = self.find_optimal_flash_loan_amount(
                        token_a,
                        token_b,
                        direction,
                        min_amount=self.min_flash_loan,
                        max_amount=self.max_flash_loan,
                        token_decimals=decimals_a
                    )

                    if optimal_opp:
                        optimal_opp['token_decimals'] = decimals_a
                        all_opportunities.append(optimal_opp)
                        self.log_opportunity(optimal_opp, token_decimals=decimals_a)

            except (TimeoutError, ConnectionError) as e:
                classified = classify_web3_exception(e)
                logger.error(f"RPC failure scanning {token_a[:6]}↔{token_b[:6]} ({type(classified).__name__}): {e}")
            except Exception as e:
                classified = classify_web3_exception(e)
                logger.error(f"{type(classified).__name__}: Error scanning {token_a[:6]}↔{token_b[:6]}: {e}", extra={"retryable": classified.retryable})

        # Triangular scan
        try:
            tri_opps = self.scan_triangular_opportunities()
            for opp in tri_opps:
                all_opportunities.append(opp)
                self.log_opportunity(opp, token_decimals=opp.get('token_decimals', 6))
        except (TimeoutError, ConnectionError) as e:
            classified = classify_web3_exception(e)
            logger.error(f"RPC failure in triangular scan ({type(classified).__name__}): {e}")
        except Exception as e:
            classified = classify_web3_exception(e)
            logger.error(f"{type(classified).__name__}: Error in triangular scan: {e}", extra={"retryable": classified.retryable})

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
                        time.sleep(self.check_interval + random.uniform(0, self.check_interval * 0.5))
                        continue
                except (TimeoutError, ConnectionError) as e:
                    classified = classify_web3_exception(e)
                    logger.warning(f"RPC failure checking gas price ({type(classified).__name__}): {e}")
                except Exception as e:
                    classified = classify_web3_exception(e)
                    logger.warning(f"{type(classified).__name__}: Failed to check gas price: {e}", extra={"retryable": classified.retryable})

                # Scan for opportunities
                opportunities = self.scan_opportunities()

                if opportunities:
                    logger.info(f"🎯 Found {len(opportunities)} profitable opportunities!")
                else:
                    logger.info("No profitable opportunities found this iteration.")

                if not continuous:
                    break

                # Add random jitter (0-50% of interval) to avoid predictable timing
                jitter = random.uniform(0, self.check_interval * 0.5)
                sleep_time = self.check_interval + jitter
                logger.info(f"Sleeping for {sleep_time:.1f} seconds...")
                time.sleep(sleep_time)

        except KeyboardInterrupt:
            logger.info("\n⛔ Detector stopped by user")
        except (TimeoutError, ConnectionError) as e:
            classified = classify_web3_exception(e)
            logger.error(f"❌ Detector RPC failure ({type(classified).__name__}): {e}", exc_info=True)
        except Exception as e:
            classified = classify_web3_exception(e)
            logger.error(f"❌ Detector error ({type(classified).__name__}): {e}", exc_info=True, extra={"retryable": classified.retryable})


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
