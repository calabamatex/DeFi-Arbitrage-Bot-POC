"""
Web3 interface for FlashLoanArbitrageV2 contract
"""
from typing import List, Dict, Any, Optional
from web3 import Web3
from web3.contract import Contract
from web3.types import TxParams, Wei, TxReceipt
from eth_account import Account
from decimal import Decimal
import json

from src.config import config


class SwapStep:
    """Represents a single swap step in the arbitrage path"""

    def __init__(
        self,
        adapter: str,
        token_in: str,
        token_out: str,
        min_amount_out: int,
        data: bytes = b"",
    ):
        self.adapter = Web3.to_checksum_address(adapter)
        self.token_in = Web3.to_checksum_address(token_in)
        self.token_out = Web3.to_checksum_address(token_out)
        self.min_amount_out = min_amount_out
        self.data = data

    def to_tuple(self) -> tuple:
        """Convert to Solidity struct tuple"""
        return (
            self.adapter,
            self.token_in,
            self.token_out,
            self.min_amount_out,
            self.data,
        )


class FlashLoanArbitrageContract:
    """
    Interface for interacting with FlashLoanArbitrageV2 smart contract
    """

    # Contract ABI (simplified - load full ABI from artifacts)
    # This would be loaded from the compiled contract artifacts in production
    ABI = [
        {
            "inputs": [
                {
                    "components": [
                        {
                            "components": [
                                {"name": "adapter", "type": "address"},
                                {"name": "tokenIn", "type": "address"},
                                {"name": "tokenOut", "type": "address"},
                                {"name": "minAmountOut", "type": "uint256"},
                                {"name": "data", "type": "bytes"},
                            ],
                            "name": "steps",
                            "type": "tuple[]",
                        },
                        {"name": "flashLoanAmount", "type": "uint256"},
                        {"name": "flashLoanAsset", "type": "address"},
                        {"name": "minFinalAmount", "type": "uint256"},
                        {"name": "deadline", "type": "uint256"},
                    ],
                    "name": "params",
                    "type": "tuple",
                }
            ],
            "name": "executeArbitrage",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function",
        },
        {
            "inputs": [{"name": "adapter", "type": "address"}, {"name": "status", "type": "bool"}],
            "name": "setAdapter",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function",
        },
        {
            "inputs": [{"name": "token", "type": "address"}],
            "name": "getBalance",
            "outputs": [{"name": "", "type": "uint256"}],
            "stateMutability": "view",
            "type": "function",
        },
        {
            "inputs": [{"name": "amount", "type": "uint256"}],
            "name": "estimateFlashLoanFee",
            "outputs": [{"name": "fee", "type": "uint256"}],
            "stateMutability": "pure",
            "type": "function",
        },
    ]

    def __init__(self, chain_name: str, contract_address: Optional[str] = None):
        """
        Initialize contract interface

        Args:
            chain_name: Name of the chain (e.g., 'polygon', 'mumbai')
            contract_address: Deployed contract address (optional, can be set later)
        """
        self.chain_name = chain_name
        self.chain_config = config.CHAINS[chain_name]

        # Initialize Web3
        self.w3 = Web3(Web3.HTTPProvider(self.chain_config.rpc_url))

        # Verify connection
        if not self.w3.is_connected():
            raise ConnectionError(f"Failed to connect to {chain_name} RPC")

        # Load account if private key is available
        self.account = None
        if config.PRIVATE_KEY:
            self.account = Account.from_key(config.PRIVATE_KEY)

        # Initialize contract
        self.contract_address = contract_address
        self.contract: Optional[Contract] = None
        if contract_address:
            self.contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(contract_address), abi=self.ABI
            )

    def set_contract_address(self, address: str) -> None:
        """Set contract address after deployment"""
        self.contract_address = Web3.to_checksum_address(address)
        self.contract = self.w3.eth.contract(address=self.contract_address, abi=self.ABI)

    def execute_arbitrage(
        self,
        steps: List[SwapStep],
        flash_loan_amount: int,
        flash_loan_asset: str,
        min_final_amount: int,
        deadline: int,
        gas_limit: int = 500000,
        gas_price_gwei: Optional[float] = None,
    ) -> TxReceipt:
        """
        Execute flash loan arbitrage

        Args:
            steps: List of swap steps
            flash_loan_amount: Amount to borrow via flash loan
            flash_loan_asset: Token address to borrow
            min_final_amount: Minimum amount after all swaps
            deadline: Transaction deadline (Unix timestamp)
            gas_limit: Gas limit for transaction
            gas_price_gwei: Gas price in Gwei (optional, uses network price if None)

        Returns:
            Transaction receipt
        """
        if not self.contract:
            raise ValueError("Contract address not set")

        if not self.account:
            raise ValueError("Private key not configured")

        # Convert steps to tuples
        step_tuples = [step.to_tuple() for step in steps]

        # Build transaction parameters
        params_tuple = (
            step_tuples,
            flash_loan_amount,
            Web3.to_checksum_address(flash_loan_asset),
            min_final_amount,
            deadline,
        )

        # Prepare transaction
        tx_params: TxParams = {
            "from": self.account.address,
            "gas": gas_limit,
            "nonce": self.w3.eth.get_transaction_count(self.account.address),
        }

        # Set gas price
        if gas_price_gwei:
            tx_params["gasPrice"] = Web3.to_wei(gas_price_gwei, "gwei")
        else:
            tx_params["gasPrice"] = self.w3.eth.gas_price

        # Build transaction
        tx = self.contract.functions.executeArbitrage(params_tuple).build_transaction(tx_params)

        # Sign transaction
        signed_tx = self.account.sign_transaction(tx)

        # Send transaction
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        # Wait for receipt
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

        return receipt

    def get_balance(self, token_address: str) -> int:
        """
        Get contract's balance of a token

        Args:
            token_address: Token address

        Returns:
            Balance (in wei/smallest unit)
        """
        if not self.contract:
            raise ValueError("Contract address not set")

        return self.contract.functions.getBalance(
            Web3.to_checksum_address(token_address)
        ).call()

    def estimate_flash_loan_fee(self, amount: int) -> int:
        """
        Estimate flash loan fee for a given amount

        Args:
            amount: Loan amount

        Returns:
            Fee amount
        """
        if not self.contract:
            raise ValueError("Contract address not set")

        return self.contract.functions.estimateFlashLoanFee(amount).call()

    def register_adapter(
        self, adapter_address: str, status: bool = True, gas_limit: int = 100000
    ) -> TxReceipt:
        """
        Register or unregister a DEX adapter

        Args:
            adapter_address: Adapter contract address
            status: True to register, False to unregister
            gas_limit: Gas limit

        Returns:
            Transaction receipt
        """
        if not self.contract:
            raise ValueError("Contract address not set")

        if not self.account:
            raise ValueError("Private key not configured")

        # Build transaction
        tx = self.contract.functions.setAdapter(
            Web3.to_checksum_address(adapter_address), status
        ).build_transaction(
            {
                "from": self.account.address,
                "gas": gas_limit,
                "gasPrice": self.w3.eth.gas_price,
                "nonce": self.w3.eth.get_transaction_count(self.account.address),
            }
        )

        # Sign and send
        signed_tx = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        # Wait for receipt
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

        return receipt

    def get_chain_id(self) -> int:
        """Get chain ID"""
        return self.w3.eth.chain_id

    def get_latest_block(self) -> int:
        """Get latest block number"""
        return self.w3.eth.block_number

    def get_gas_price_gwei(self) -> float:
        """Get current gas price in Gwei"""
        gas_price_wei = self.w3.eth.gas_price
        return float(Web3.from_wei(gas_price_wei, "gwei"))

    @staticmethod
    def load_abi_from_file(filepath: str) -> List[Dict[str, Any]]:
        """
        Load contract ABI from compiled artifacts

        Args:
            filepath: Path to ABI JSON file

        Returns:
            Contract ABI
        """
        with open(filepath, "r") as f:
            artifact = json.load(f)
            return artifact.get("abi", [])


# Helper function to create contract instance
def get_flash_loan_contract(
    chain_name: str = "mumbai", contract_address: Optional[str] = None
) -> FlashLoanArbitrageContract:
    """
    Factory function to create FlashLoanArbitrageContract instance

    Args:
        chain_name: Chain name
        contract_address: Contract address

    Returns:
        FlashLoanArbitrageContract instance
    """
    return FlashLoanArbitrageContract(chain_name, contract_address)
