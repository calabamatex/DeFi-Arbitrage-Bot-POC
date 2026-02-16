"""
Liquidation Detector

Monitors Aave V3 borrower positions for health factor < 1.0
and identifies profitable liquidation opportunities.
"""

import logging
import os
from typing import Dict, List, Optional, Tuple

from web3 import Web3
from dotenv import load_dotenv

from src.utils.errors import classify_web3_exception

load_dotenv()

logger = logging.getLogger(__name__)

# Aave health factor threshold: < 1e18 means liquidatable
HEALTH_FACTOR_THRESHOLD = 10**18


class LiquidationDetector:
    """
    Detects profitable liquidation opportunities on Aave V3.

    Scans borrower positions, checks health factors, and calculates
    expected profit from liquidation bonus minus flash loan fees and swap costs.
    """

    FLASH_LOAN_FEE_BPS = 5  # 0.05%

    def __init__(
        self,
        web3: Web3,
        pool_address: str,
        data_provider_address: str,
        min_profit_usd: float = 50.0,
    ):
        """
        Args:
            web3: Web3 instance
            pool_address: Aave V3 Pool address
            data_provider_address: Aave V3 PoolDataProvider address
            min_profit_usd: Minimum profit threshold in USD
        """
        self.web3 = web3
        self.pool_address = web3.to_checksum_address(pool_address)
        self.data_provider_address = web3.to_checksum_address(data_provider_address)
        self.min_profit_usd = min_profit_usd

        self._init_contracts()

        logger.info(f"LiquidationDetector initialized")
        logger.info(f"Pool: {self.pool_address}")
        logger.info(f"DataProvider: {self.data_provider_address}")

    def _init_contracts(self):
        """Initialize Aave contract instances."""
        # Pool ABI — getUserAccountData
        pool_abi = [
            {
                "inputs": [{"type": "address", "name": "user"}],
                "name": "getUserAccountData",
                "outputs": [
                    {"type": "uint256", "name": "totalCollateralBase"},
                    {"type": "uint256", "name": "totalDebtBase"},
                    {"type": "uint256", "name": "availableBorrowsBase"},
                    {"type": "uint256", "name": "currentLiquidationThreshold"},
                    {"type": "uint256", "name": "ltv"},
                    {"type": "uint256", "name": "healthFactor"},
                ],
                "stateMutability": "view",
                "type": "function",
            }
        ]

        # DataProvider ABI — getUserReserveData, getReserveConfigurationData
        data_provider_abi = [
            {
                "inputs": [
                    {"type": "address", "name": "asset"},
                    {"type": "address", "name": "user"},
                ],
                "name": "getUserReserveData",
                "outputs": [
                    {"type": "uint256", "name": "currentATokenBalance"},
                    {"type": "uint256", "name": "currentStableDebt"},
                    {"type": "uint256", "name": "currentVariableDebt"},
                    {"type": "uint256", "name": "principalStableDebt"},
                    {"type": "int256", "name": "scaledVariableDebt"},
                    {"type": "uint256", "name": "stableBorrowRate"},
                    {"type": "uint256", "name": "liquidityRate"},
                    {"type": "uint40", "name": "stableRateLastUpdated"},
                    {"type": "bool", "name": "usageAsCollateralEnabled"},
                ],
                "stateMutability": "view",
                "type": "function",
            },
            {
                "inputs": [{"type": "address", "name": "asset"}],
                "name": "getReserveConfigurationData",
                "outputs": [
                    {"type": "uint256", "name": "decimals"},
                    {"type": "uint256", "name": "ltv"},
                    {"type": "uint256", "name": "liquidationThreshold"},
                    {"type": "uint256", "name": "liquidationBonus"},
                    {"type": "uint256", "name": "reserveFactor"},
                    {"type": "bool", "name": "usageAsCollateralEnabled"},
                    {"type": "bool", "name": "borrowingEnabled"},
                    {"type": "bool", "name": "stableBorrowRateEnabled"},
                    {"type": "bool", "name": "isActive"},
                    {"type": "bool", "name": "isFrozen"},
                ],
                "stateMutability": "view",
                "type": "function",
            },
        ]

        self.pool_contract = self.web3.eth.contract(
            address=self.pool_address, abi=pool_abi
        )
        self.data_provider_contract = self.web3.eth.contract(
            address=self.data_provider_address, abi=data_provider_abi
        )

    def get_user_account_data(self, user: str) -> Optional[Dict]:
        """
        Get user's Aave account data including health factor.

        Returns:
            Dict with totalCollateralBase, totalDebtBase, healthFactor, etc.
            or None on failure.
        """
        try:
            result = self.pool_contract.functions.getUserAccountData(
                self.web3.to_checksum_address(user)
            ).call()
            return {
                "totalCollateralBase": result[0],
                "totalDebtBase": result[1],
                "availableBorrowsBase": result[2],
                "currentLiquidationThreshold": result[3],
                "ltv": result[4],
                "healthFactor": result[5],
            }
        except (TimeoutError, ConnectionError) as e:
            classified = classify_web3_exception(e)
            logger.warning(f"RPC failure getting account data for {user[:10]} ({type(classified).__name__}): {e}")
            return None
        except Exception as e:
            classified = classify_web3_exception(e)
            logger.warning(f"{type(classified).__name__}: Failed to get account data for {user[:10]}: {e}", extra={"retryable": classified.retryable})
            return None

    def is_liquidatable(self, user: str) -> Tuple[bool, Optional[int]]:
        """
        Check if a user's position is liquidatable.

        Returns:
            Tuple of (is_liquidatable, health_factor)
        """
        data = self.get_user_account_data(user)
        if not data:
            return False, None

        hf = data["healthFactor"]
        return hf < HEALTH_FACTOR_THRESHOLD, hf

    def get_reserve_config(self, asset: str) -> Optional[Dict]:
        """Get reserve configuration including liquidation bonus."""
        try:
            result = self.data_provider_contract.functions.getReserveConfigurationData(
                self.web3.to_checksum_address(asset)
            ).call()
            return {
                "decimals": result[0],
                "ltv": result[1],
                "liquidationThreshold": result[2],
                "liquidationBonus": result[3],  # e.g., 10500 = 105% = 5% bonus
                "reserveFactor": result[4],
                "usageAsCollateralEnabled": result[5],
                "borrowingEnabled": result[6],
                "isActive": result[8],
            }
        except (TimeoutError, ConnectionError) as e:
            classified = classify_web3_exception(e)
            logger.warning(f"RPC failure getting reserve config for {asset[:10]} ({type(classified).__name__}): {e}")
            return None
        except Exception as e:
            classified = classify_web3_exception(e)
            logger.warning(f"{type(classified).__name__}: Failed to get reserve config for {asset[:10]}: {e}", extra={"retryable": classified.retryable})
            return None

    def get_user_reserve_data(self, asset: str, user: str) -> Optional[Dict]:
        """Get user's position in a specific reserve."""
        try:
            result = self.data_provider_contract.functions.getUserReserveData(
                self.web3.to_checksum_address(asset),
                self.web3.to_checksum_address(user),
            ).call()
            return {
                "aTokenBalance": result[0],
                "stableDebt": result[1],
                "variableDebt": result[2],
                "usageAsCollateralEnabled": result[8],
            }
        except (TimeoutError, ConnectionError) as e:
            classified = classify_web3_exception(e)
            logger.debug(f"RPC failure getting user reserve data ({type(classified).__name__}): {e}")
            return None
        except Exception as e:
            classified = classify_web3_exception(e)
            logger.debug(f"{type(classified).__name__}: Failed to get user reserve data: {e}", extra={"retryable": classified.retryable})
            return None

    def calculate_liquidation_profit(
        self,
        debt_amount: int,
        liquidation_bonus_bps: int,
        debt_decimals: int = 6,
        swap_slippage_bps: int = 30,
    ) -> Dict:
        """
        Calculate expected profit from a liquidation.

        Args:
            debt_amount: Amount of debt to cover
            liquidation_bonus_bps: Aave liquidation bonus (e.g., 10500 = 5% bonus)
            debt_decimals: Debt token decimals
            swap_slippage_bps: Expected swap slippage in bps

        Returns:
            Dict with gross_profit, flash_loan_fee, swap_cost, net_profit
        """
        # Bonus percentage (e.g., 10500 → 500 bps bonus)
        bonus_bps = liquidation_bonus_bps - 10000
        collateral_value = debt_amount + (debt_amount * bonus_bps) // 10000

        # Flash loan fee
        flash_loan_fee = (debt_amount * self.FLASH_LOAN_FEE_BPS) // 10000

        # Swap cost estimate (collateral → debt)
        swap_cost = (collateral_value * swap_slippage_bps) // 10000

        gross_profit = collateral_value - debt_amount
        net_profit = gross_profit - flash_loan_fee - swap_cost

        return {
            "debt_amount": debt_amount,
            "collateral_value": collateral_value,
            "gross_profit": gross_profit,
            "flash_loan_fee": flash_loan_fee,
            "swap_cost": swap_cost,
            "net_profit": net_profit,
            "net_profit_usd": net_profit / (10**debt_decimals),
        }

    def discover_active_borrowers(
        self,
        from_block: int,
        to_block: int,
    ) -> List[str]:
        """
        Discover active borrowers by scanning Borrow events.

        Args:
            from_block: Start block
            to_block: End block

        Returns:
            List of unique borrower addresses
        """
        borrow_topic = self.web3.keccak(
            text="Borrow(address,address,address,uint256,uint8,uint256,uint16)"
        )

        try:
            logs = self.web3.eth.get_logs({
                "address": self.pool_address,
                "fromBlock": from_block,
                "toBlock": to_block,
                "topics": [borrow_topic.hex()],
            })

            borrowers = set()
            for log in logs:
                # The 'onBehalfOf' (user) is the 3rd topic
                if len(log["topics"]) >= 3:
                    user = "0x" + log["topics"][2].hex()[-40:]
                    borrowers.add(self.web3.to_checksum_address(user))

            logger.info(
                f"Found {len(borrowers)} borrowers in blocks {from_block}-{to_block}"
            )
            return list(borrowers)
        except (TimeoutError, ConnectionError) as e:
            classified = classify_web3_exception(e)
            logger.error(f"RPC failure scanning borrow events ({type(classified).__name__}): {e}")
            return []
        except Exception as e:
            classified = classify_web3_exception(e)
            logger.error(f"{type(classified).__name__}: Failed to scan borrow events: {e}", extra={"retryable": classified.retryable})
            return []

    def scan_for_liquidations(
        self,
        users: List[str],
        debt_assets: List[str],
        collateral_assets: List[str],
    ) -> List[Dict]:
        """
        Scan a list of users for profitable liquidation opportunities.

        Args:
            users: List of borrower addresses to check
            debt_assets: Possible debt token addresses
            collateral_assets: Possible collateral token addresses

        Returns:
            List of profitable liquidation opportunities
        """
        opportunities = []

        for user in users:
            liquidatable, hf = self.is_liquidatable(user)
            if not liquidatable:
                continue

            logger.info(f"Liquidatable user found: {user[:10]}... HF={hf}")

            # Check each debt/collateral combination
            for debt_asset in debt_assets:
                user_debt = self.get_user_reserve_data(debt_asset, user)
                if not user_debt:
                    continue
                total_debt = user_debt["stableDebt"] + user_debt["variableDebt"]
                if total_debt == 0:
                    continue

                # Max liquidation: 50% of total debt (Aave rule)
                max_liquidation = total_debt // 2

                for collateral_asset in collateral_assets:
                    user_collateral = self.get_user_reserve_data(collateral_asset, user)
                    if not user_collateral or user_collateral["aTokenBalance"] == 0:
                        continue

                    # Get liquidation bonus
                    reserve_config = self.get_reserve_config(collateral_asset)
                    if not reserve_config:
                        continue

                    bonus = reserve_config["liquidationBonus"]
                    debt_config = self.get_reserve_config(debt_asset)
                    debt_decimals = debt_config["decimals"] if debt_config else 6

                    # Calculate profit
                    profit_info = self.calculate_liquidation_profit(
                        debt_amount=max_liquidation,
                        liquidation_bonus_bps=bonus,
                        debt_decimals=debt_decimals,
                    )

                    if profit_info["net_profit_usd"] >= self.min_profit_usd:
                        opportunities.append({
                            "user": user,
                            "debt_asset": debt_asset,
                            "collateral_asset": collateral_asset,
                            "health_factor": hf,
                            "debt_amount": max_liquidation,
                            "liquidation_bonus_bps": bonus,
                            **profit_info,
                        })
                        logger.info(
                            f"Profitable liquidation: {user[:10]}... "
                            f"debt={debt_asset[:10]} collateral={collateral_asset[:10]} "
                            f"profit=${profit_info['net_profit_usd']:.2f}"
                        )

        logger.info(f"Found {len(opportunities)} profitable liquidations from {len(users)} users")
        return opportunities
