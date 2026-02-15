"""
Flash Loan Provider Selection

Selects between Aave (0.05% fee) and Balancer (0% fee) flash loan providers
based on token liquidity in each protocol's pools.
"""

import logging
import os
from enum import Enum
from typing import Optional

from web3 import Web3

logger = logging.getLogger(__name__)

# Balancer V2 Vault — same address on all EVM chains
BALANCER_VAULT = "0xBA12222222228d8Ba445958a75a0704d566BF2C8"


class FlashLoanProvider(Enum):
    AAVE = "aave"
    BALANCER = "balancer"


class FlashLoanSelector:
    """
    Selects the optimal flash loan provider for a given token and amount.

    Strategy:
    - Prefer Balancer (0% fee) when the token has sufficient liquidity in the Vault.
    - Fall back to Aave (0.05% fee) otherwise.
    """

    AAVE_FEE_BPS = 5       # 0.05%
    BALANCER_FEE_BPS = 0   # 0%

    def __init__(
        self,
        web3: Web3,
        aave_contract_address: str,
        balancer_contract_address: Optional[str] = None,
    ):
        """
        Args:
            web3: Web3 instance
            aave_contract_address: FlashLoanArbitrageV2 address
            balancer_contract_address: BalancerFlashLoan address (None = Balancer disabled)
        """
        self.web3 = web3
        self.aave_contract_address = web3.to_checksum_address(aave_contract_address)
        self.balancer_contract_address = (
            web3.to_checksum_address(balancer_contract_address)
            if balancer_contract_address
            else None
        )
        self.balancer_vault = web3.to_checksum_address(BALANCER_VAULT)

    def select_provider(
        self,
        token_address: str,
        amount: int,
    ) -> tuple[FlashLoanProvider, str, int]:
        """
        Select the best flash loan provider for a token and amount.

        Args:
            token_address: The token to borrow
            amount: Amount to borrow

        Returns:
            Tuple of (provider, contract_address, fee_bps)
        """
        # If Balancer contract not deployed, always use Aave
        if not self.balancer_contract_address:
            return (
                FlashLoanProvider.AAVE,
                self.aave_contract_address,
                self.AAVE_FEE_BPS,
            )

        # Check Balancer Vault balance for the token
        if self._balancer_has_liquidity(token_address, amount):
            logger.info(
                f"Using Balancer (0% fee) for {token_address[:10]}... "
                f"amount={amount}"
            )
            return (
                FlashLoanProvider.BALANCER,
                self.balancer_contract_address,
                self.BALANCER_FEE_BPS,
            )

        logger.info(
            f"Balancer insufficient liquidity, using Aave (0.05%) for "
            f"{token_address[:10]}..."
        )
        return (
            FlashLoanProvider.AAVE,
            self.aave_contract_address,
            self.AAVE_FEE_BPS,
        )

    def _balancer_has_liquidity(self, token_address: str, amount: int) -> bool:
        """
        Check if the Balancer Vault has enough of a token for the flash loan.

        Simply checks the token balance of the vault address.
        """
        try:
            # Minimal ERC20 balanceOf ABI
            erc20_abi = [
                {
                    "inputs": [{"type": "address", "name": "account"}],
                    "name": "balanceOf",
                    "outputs": [{"type": "uint256"}],
                    "stateMutability": "view",
                    "type": "function",
                }
            ]
            token = self.web3.eth.contract(
                address=self.web3.to_checksum_address(token_address),
                abi=erc20_abi,
            )
            vault_balance = token.functions.balanceOf(self.balancer_vault).call()
            return vault_balance >= amount
        except Exception as e:
            logger.warning(f"Balancer liquidity check failed: {e}")
            return False

    def estimate_savings(self, amount: int) -> int:
        """
        Estimate savings from using Balancer (0% fee) vs Aave (0.05% fee).

        Args:
            amount: Flash loan amount

        Returns:
            Savings in token units
        """
        aave_fee = (amount * self.AAVE_FEE_BPS) // 10000
        return aave_fee  # Balancer fee is 0, so savings = full Aave fee
