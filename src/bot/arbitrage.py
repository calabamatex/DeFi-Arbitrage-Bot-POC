"""Arbitrage opportunity detection and execution."""

from decimal import Decimal
from typing import Dict, Tuple, Optional
from dataclasses import dataclass
from web3 import Web3
import logging
import asyncio
import time
from datetime import datetime

# Import from other modules
from .config import get_erc20_abi
from ..dex.base import DEX

logger = logging.getLogger(__name__)

# Constants
BASE_PROFIT_THRESHOLD = Decimal("0.005")  # 0.5%
SLIPPAGE_TOLERANCE = Decimal("0.005")  # 0.5%
GAS_LIMIT = 300000

# Get ERC20 ABI from config
ERC20_ABI = get_erc20_abi()


@dataclass
class ArbitrageOpportunity:
    """Represents a detected arbitrage opportunity."""

    token1: str
    token2: str
    buy_dex: str
    sell_dex: str
    expected_profit: Decimal
    amount: Decimal
    buy_price: Decimal
    sell_price: Decimal
    timestamp: datetime

    def __post_init__(self):
        """Calculate profit percentage."""
        if self.buy_price > 0:
            self.profit_percent = (
                (self.sell_price - self.buy_price) / self.buy_price * 100
            )
        else:
            self.profit_percent = Decimal("0")


async def calculate_arbitrage(
    token1: str,
    token2: str,
    web3: Web3,
    dex_instances: Dict[str, DEX],
    TOKEN_LIST: Dict,
) -> Optional[ArbitrageOpportunity]:
    """
    Calculate arbitrage opportunity across all DEXes.

    Args:
        token1: First token symbol (e.g., "WETH")
        token2: Second token symbol (e.g., "USDC")
        web3: Web3 instance
        dex_instances: Dictionary of initialized DEX instances
        TOKEN_LIST: Token configuration

    Returns:
        ArbitrageOpportunity if found, None otherwise
    """
    try:
        # Get token addresses
        token1_address = TOKEN_LIST[token1]["address"]
        token2_address = TOKEN_LIST[token2]["address"]

        # Fetch prices from all DEXes concurrently
        logger.debug(f"Fetching prices for {token1}/{token2} from all DEXes")
        prices = await DEX.fetch_concurrent_prices(
            list(dex_instances.values()), token1_address, web3
        )

        # Filter out failed price fetches (price = 0)
        valid_prices = {dex: price for dex, price in prices.items() if price > 0}

        if len(valid_prices) < 2:
            logger.debug(f"Not enough valid prices for {token1}/{token2}")
            return None

        # Find lowest and highest prices
        buy_dex = min(valid_prices, key=lambda x: valid_prices[x])
        sell_dex = max(valid_prices, key=lambda x: valid_prices[x])

        buy_price = valid_prices[buy_dex]
        sell_price = valid_prices[sell_dex]

        # Calculate gross profit
        gross_profit = sell_price - buy_price

        # If no profit, return None
        if gross_profit <= 0:
            return None

        # Create opportunity object
        opportunity = ArbitrageOpportunity(
            token1=token1,
            token2=token2,
            buy_dex=buy_dex,
            sell_dex=sell_dex,
            expected_profit=gross_profit,
            amount=Decimal("0.1"),  # Default trade amount
            buy_price=buy_price,
            sell_price=sell_price,
            timestamp=datetime.now(),
        )

        logger.info(
            f"Arbitrage opportunity found: {token1}/{token2} - "
            f"Buy on {buy_dex} at {buy_price}, sell on {sell_dex} at {sell_price}, "
            f"profit: {gross_profit} ({opportunity.profit_percent:.2f}%)"
        )

        return opportunity

    except Exception as e:
        logger.error(f"Error calculating arbitrage for {token1}/{token2}: {e}")
        return None


async def calculate_gas_cost(
    web3: Web3, gas_limit: int = GAS_LIMIT, matic_price_usd: Decimal = Decimal("1.0")
) -> Decimal:
    """
    Calculate gas cost in USD.

    Args:
        web3: Web3 instance
        gas_limit: Estimated gas limit
        matic_price_usd: Current MATIC price in USD

    Returns:
        Gas cost in USD
    """
    try:
        # Get current gas price
        gas_price = web3.eth.gas_price

        # Calculate cost in MATIC
        gas_cost_wei = gas_price * gas_limit
        gas_cost_matic = Decimal(gas_cost_wei) / Decimal(10**18)

        # Convert to USD (simplified - in production use oracle)
        gas_cost_usd = gas_cost_matic * matic_price_usd

        logger.debug(f"Gas cost: {gas_cost_matic:.6f} MATIC (${gas_cost_usd:.4f} USD)")

        return gas_cost_usd

    except Exception as e:
        logger.error(f"Error calculating gas cost: {e}")
        return Decimal("0.1")  # Default estimate if calculation fails


async def is_profitable(
    opportunity: ArbitrageOpportunity,
    web3: Web3,
    min_profit_threshold: Decimal = BASE_PROFIT_THRESHOLD,
) -> Tuple[bool, Decimal]:
    """
    Check if opportunity is profitable after gas costs.

    Args:
        opportunity: ArbitrageOpportunity to check
        web3: Web3 instance
        min_profit_threshold: Minimum profit threshold (as decimal, e.g., 0.005 = 0.5%)

    Returns:
        Tuple of (is_profitable: bool, net_profit: Decimal)
    """
    try:
        # Calculate gas cost for 2 transactions (buy + sell)
        # Each trade costs ~300k gas, so total ~600k
        total_gas_limit = GAS_LIMIT * 2
        gas_cost = await calculate_gas_cost(web3, total_gas_limit)

        # Calculate net profit
        # Note: expected_profit is already in USD terms based on token prices
        gross_profit_usd = opportunity.expected_profit * opportunity.amount
        net_profit = gross_profit_usd - gas_cost

        # Check if meets threshold
        if opportunity.buy_price > 0:
            profit_percent = net_profit / (opportunity.buy_price * opportunity.amount)
        else:
            profit_percent = Decimal("0")

        is_prof = net_profit > 0 and profit_percent >= min_profit_threshold

        logger.debug(
            f"Profitability check: Gross=${gross_profit_usd:.4f}, "
            f"Gas=${gas_cost:.4f}, Net=${net_profit:.4f}, "
            f"Percent={profit_percent*100:.2f}%, Profitable={is_prof}"
        )

        return is_prof, net_profit

    except Exception as e:
        logger.error(f"Error checking profitability: {e}")
        return False, Decimal("0")


async def validate_balance(
    account: str, token_address: str, amount: Decimal, web3: Web3
) -> bool:
    """
    Validate account has sufficient token balance.

    Args:
        account: Account address
        token_address: Token contract address
        amount: Required amount
        web3: Web3 instance

    Returns:
        True if sufficient balance, False otherwise
    """
    try:
        # Create token contract
        token_contract = web3.eth.contract(
            address=Web3.to_checksum_address(token_address), abi=ERC20_ABI
        )

        # Get balance
        balance_wei = token_contract.functions.balanceOf(account).call()
        balance = Decimal(balance_wei) / Decimal(10**18)

        # Check if sufficient
        sufficient = balance >= amount

        if not sufficient:
            logger.warning(
                f"Insufficient balance: have {balance:.6f}, need {amount:.6f}"
            )

        return sufficient

    except Exception as e:
        logger.error(f"Error validating balance: {e}")
        return False


async def execute_arbitrage(
    opportunity: ArbitrageOpportunity,
    web3: Web3,
    dex_instances: Dict[str, DEX],
    TOKEN_LIST: Dict,
    account: str,
    private_key: str,
) -> Tuple[bool, str, Decimal]:
    """
    Execute arbitrage opportunity.

    Args:
        opportunity: ArbitrageOpportunity to execute
        web3: Web3 instance
        dex_instances: Dictionary of DEX instances
        TOKEN_LIST: Token configuration
        account: Account address
        private_key: Private key for signing

    Returns:
        Tuple of (success: bool, message: str, actual_profit: Decimal)
    """
    try:
        # Checksum account address at the beginning
        checksummed_account = Web3.to_checksum_address(account)

        logger.info(
            f"Executing arbitrage: Buy {opportunity.token1} on {opportunity.buy_dex}, "
            f"sell on {opportunity.sell_dex}"
        )

        # Get token addresses
        token1_address = TOKEN_LIST[opportunity.token1]["address"]
        token2_address = TOKEN_LIST[opportunity.token2]["address"]

        # Validate balance
        has_balance = await validate_balance(
            account, token1_address, opportunity.amount, web3
        )

        if not has_balance:
            return False, "Insufficient balance", Decimal("0")

        # Get DEX instances
        buy_dex = dex_instances[opportunity.buy_dex]
        sell_dex = dex_instances[opportunity.sell_dex]

        # Step 1: Approve token spending on buy DEX
        logger.info(f"Approving {opportunity.token1} for {opportunity.buy_dex}")
        token_contract = web3.eth.contract(address=token1_address, abi=ERC20_ABI)

        # Check existing allowance
        allowance = token_contract.functions.allowance(
            account, buy_dex.router_address
        ).call()

        amount_wei = int(opportunity.amount * Decimal(10**18))

        if allowance < amount_wei:
            # Approve tokens
            approve_txn = token_contract.functions.approve(
                buy_dex.router_address, amount_wei
            ).build_transaction(
                {
                    "from": account,
                    "nonce": web3.eth.get_transaction_count(checksummed_account),
                    "gas": 100000,
                    "gasPrice": web3.eth.gas_price,
                }
            )

            signed_approve = web3.eth.account.sign_transaction(approve_txn, private_key)
            approve_hash = web3.eth.send_raw_transaction(signed_approve.raw_transaction)

            logger.info(f"Approval transaction sent: {approve_hash.hex()}")

            # Wait for approval
            web3.eth.wait_for_transaction_receipt(approve_hash, timeout=120)
            logger.info("Approval confirmed")

        # Step 2: Execute buy trade
        logger.info(
            f"Buying {opportunity.amount} {opportunity.token1} on {opportunity.buy_dex}"
        )

        buy_success, buy_result = await buy_dex.execute_trade(
            token1_address,
            token2_address,
            opportunity.amount,
            web3,
            account,
            private_key,
        )

        if not buy_success:
            logger.error(f"Buy trade failed: {buy_result}")
            return False, f"Buy trade failed: {buy_result}", Decimal("0")

        logger.info(f"Buy trade successful: {buy_result}")

        # Step 3: Approve token2 for sell DEX
        token2_contract = web3.eth.contract(address=token2_address, abi=ERC20_ABI)

        # Get actual amount received (check balance)
        received_wei = token2_contract.functions.balanceOf(account).call()
        received_amount = Decimal(received_wei) / Decimal(10**18)

        logger.info(f"Received {received_amount} {opportunity.token2}")

        # Approve token2 for sell
        approve_txn2 = token2_contract.functions.approve(
            sell_dex.router_address, received_wei
        ).build_transaction(
            {
                "from": account,
                "nonce": web3.eth.get_transaction_count(checksummed_account),
                "gas": 100000,
                "gasPrice": web3.eth.gas_price,
            }
        )

        signed_approve2 = web3.eth.account.sign_transaction(approve_txn2, private_key)
        approve_hash2 = web3.eth.send_raw_transaction(signed_approve2.raw_transaction)
        web3.eth.wait_for_transaction_receipt(approve_hash2, timeout=120)

        # Step 4: Execute sell trade
        logger.info(
            f"Selling {received_amount} {opportunity.token2} on {opportunity.sell_dex}"
        )

        sell_success, sell_result = await sell_dex.execute_trade(
            token2_address, token1_address, received_amount, web3, account, private_key
        )

        if not sell_success:
            logger.error(f"Sell trade failed: {sell_result}")
            return False, f"Sell trade failed: {sell_result}", Decimal("0")

        logger.info(f"Sell trade successful: {sell_result}")

        # Calculate actual profit
        final_balance_wei = token_contract.functions.balanceOf(account).call()
        final_balance = Decimal(final_balance_wei) / Decimal(10**18)

        # This is simplified - in production track exact amounts
        actual_profit = final_balance - opportunity.amount

        message = (
            f"Arbitrage executed successfully. "
            f"Buy: {buy_result}, Sell: {sell_result}, "
            f"Profit: {actual_profit:.6f} {opportunity.token1}"
        )

        logger.info(message)

        return True, message, actual_profit

    except Exception as e:
        logger.error(f"Error executing arbitrage: {e}")
        return False, str(e), Decimal("0")


async def log_arbitrage_attempt(
    opportunity: ArbitrageOpportunity,
    success: bool,
    message: str,
    actual_profit: Decimal,
):
    """
    Log arbitrage attempt details.

    Args:
        opportunity: The opportunity that was attempted
        success: Whether execution succeeded
        message: Result message
        actual_profit: Actual profit realized
    """
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())

    log_entry = (
        f"[{timestamp}] Arbitrage Attempt\n"
        f"  Pair: {opportunity.token1}/{opportunity.token2}\n"
        f"  Buy: {opportunity.buy_dex} @ {opportunity.buy_price}\n"
        f"  Sell: {opportunity.sell_dex} @ {opportunity.sell_price}\n"
        f"  Expected Profit: {opportunity.expected_profit}\n"
        f"  Success: {success}\n"
        f"  Actual Profit: {actual_profit}\n"
        f"  Message: {message}\n"
    )

    logger.info(log_entry)

    # Also write to file
    try:
        with open("arbitrage_log.txt", "a") as f:
            f.write(log_entry + "\n")
    except Exception as e:
        logger.error(f"Error writing to log file: {e}")
