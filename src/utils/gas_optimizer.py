"""Gas price optimization."""

from decimal import Decimal
from web3 import Web3
from typing import Dict
import logging

logger = logging.getLogger(__name__)


class GasOptimizer:
    """Optimizes gas prices for transactions."""

    def __init__(self, web3: Web3):
        """
        Initialize gas optimizer.

        Args:
            web3: Web3 instance
        """
        self.web3 = web3
        logger.info("GasOptimizer initialized")

    def get_optimal_gas_price(self, urgency: str = "normal") -> int:
        """
        Get optimal gas price based on urgency.

        Args:
            urgency: "low", "normal", or "high"

        Returns:
            Gas price in wei
        """
        try:
            # Get current gas price
            current = self.web3.eth.gas_price

            if urgency == "low":
                gas_price = int(current * 0.8)  # 20% below current
                logger.debug(f"Low urgency gas price: {gas_price} wei")
            elif urgency == "high":
                gas_price = int(current * 1.2)  # 20% above current
                logger.debug(f"High urgency gas price: {gas_price} wei")
            else:
                gas_price = current
                logger.debug(f"Normal urgency gas price: {gas_price} wei")

            return gas_price

        except Exception as e:
            logger.error(f"Failed to get gas price: {e}")
            # Fallback to a reasonable default (30 gwei)
            return 30000000000

    def use_eip1559(self, urgency: str = "normal") -> Dict[str, int]:
        """
        Get EIP-1559 gas parameters.

        Args:
            urgency: Transaction urgency ("low", "normal", "high")

        Returns:
            Dict with maxFeePerGas and maxPriorityFeePerGas
        """
        try:
            # Get latest block
            latest_block = self.web3.eth.get_block("latest")
            base_fee = latest_block.get("baseFeePerGas", 30000000000)

            # Set priority fee based on urgency
            if urgency == "low":
                priority_fee = 1000000000  # 1 gwei
            elif urgency == "high":
                priority_fee = 3000000000  # 3 gwei
            else:
                priority_fee = 2000000000  # 2 gwei

            # Max fee = 2x base fee + priority (allows for base fee increase)
            max_fee = base_fee * 2 + priority_fee

            logger.debug(
                f"EIP-1559 gas: base={base_fee}, priority={priority_fee}, max={max_fee}"
            )

            return {"maxFeePerGas": max_fee, "maxPriorityFeePerGas": priority_fee}

        except Exception as e:
            logger.error(f"Failed to calculate EIP-1559 gas: {e}")
            # Fallback values
            return {
                "maxFeePerGas": 100000000000,  # 100 gwei
                "maxPriorityFeePerGas": 2000000000,  # 2 gwei
            }

    def estimate_gas_cost(
        self, gas_limit: int, urgency: str = "normal"
    ) -> Decimal:
        """
        Estimate total gas cost for a transaction.

        Args:
            gas_limit: Gas limit for transaction
            urgency: Transaction urgency

        Returns:
            Estimated cost in native token (ETH/MATIC)
        """
        gas_price = self.get_optimal_gas_price(urgency)
        cost_wei = gas_limit * gas_price
        cost_eth = Decimal(cost_wei) / Decimal(10**18)

        logger.debug(
            f"Estimated gas cost: {gas_limit} gas * {gas_price} wei = {cost_eth:.6f} ETH"
        )

        return cost_eth

    def is_profitable_after_gas(
        self, expected_profit: Decimal, gas_limit: int, urgency: str = "normal"
    ) -> bool:
        """
        Check if trade is profitable after gas costs.

        Args:
            expected_profit: Expected profit in native token
            gas_limit: Gas limit for transaction
            urgency: Transaction urgency

        Returns:
            True if profitable after gas
        """
        gas_cost = self.estimate_gas_cost(gas_limit, urgency)

        is_profitable = expected_profit > gas_cost

        logger.debug(
            f"Profit check: expected={expected_profit:.6f}, gas={gas_cost:.6f}, "
            f"profitable={is_profitable}"
        )

        return is_profitable

    def get_gas_multiplier(self, urgency: str = "normal") -> float:
        """
        Get gas price multiplier for urgency level.

        Args:
            urgency: Transaction urgency

        Returns:
            Multiplier to apply to base gas price
        """
        multipliers = {"low": 0.8, "normal": 1.0, "high": 1.2, "urgent": 1.5}

        return multipliers.get(urgency, 1.0)


# Unlimited approval constant
MAX_UINT256 = 2**256 - 1


def get_unlimited_approval_amount() -> int:
    """
    Get amount for unlimited token approval.

    Returns:
        Maximum uint256 value
    """
    return MAX_UINT256
