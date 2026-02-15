"""
Token Registry — loads tokens from JSON config, verifies pool liquidity,
and generates tradable pair combinations.
"""

import json
import logging
import os
from itertools import combinations
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from web3 import Web3

logger = logging.getLogger(__name__)

# Default config directory (relative to project root)
DEFAULT_TOKEN_CONFIG_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "config", "tokens"
)

# Chain ID → config filename
CHAIN_CONFIG_FILES = {
    137: "polygon.json",
    42161: "arbitrum.json",
}


class TokenInfo:
    """Represents a single token loaded from config."""

    __slots__ = ("symbol", "address", "decimals", "is_stablecoin")

    def __init__(self, symbol: str, address: str, decimals: int, is_stablecoin: bool):
        self.symbol = symbol
        self.address = Web3.to_checksum_address(address)
        self.decimals = decimals
        self.is_stablecoin = is_stablecoin

    def __repr__(self) -> str:
        return f"TokenInfo({self.symbol}, {self.address[:10]}..., dec={self.decimals})"


class TokenRegistry:
    """
    Loads tokens from a chain-specific JSON config and generates
    tradable pair combinations with optional on-chain liquidity verification.
    """

    def __init__(
        self,
        web3: Web3,
        chain_id: int = None,
        config_dir: str = None,
        max_pairs: int = 50,
    ):
        """
        Args:
            web3: Web3 instance
            chain_id: Override chain ID (default: read from web3)
            config_dir: Override token config directory
            max_pairs: Maximum pairs to return from generate_pairs()
        """
        self.web3 = web3
        self.chain_id = chain_id or web3.eth.chain_id
        self.config_dir = config_dir or os.getenv(
            "TOKEN_CONFIG_DIR", DEFAULT_TOKEN_CONFIG_DIR
        )
        self.max_pairs = max_pairs

        # symbol -> TokenInfo
        self.tokens: Dict[str, TokenInfo] = {}
        # lowercase address -> TokenInfo
        self._by_address: Dict[str, TokenInfo] = {}

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_tokens(self) -> int:
        """
        Load tokens from the JSON config file for the current chain.

        Returns:
            Number of tokens loaded.
        """
        config_file = CHAIN_CONFIG_FILES.get(self.chain_id)
        if not config_file:
            logger.warning(
                f"No token config for chain {self.chain_id}, using empty registry"
            )
            return 0

        filepath = os.path.join(self.config_dir, config_file)
        if not os.path.exists(filepath):
            logger.warning(f"Token config not found: {filepath}")
            return 0

        with open(filepath) as f:
            data = json.load(f)

        for entry in data.get("tokens", []):
            token = TokenInfo(
                symbol=entry["symbol"],
                address=entry["address"],
                decimals=entry["decimals"],
                is_stablecoin=entry.get("is_stablecoin", False),
            )
            self.tokens[token.symbol] = token
            self._by_address[token.address.lower()] = token

        logger.info(
            f"Loaded {len(self.tokens)} tokens for chain {self.chain_id} from {filepath}"
        )
        return len(self.tokens)

    # ------------------------------------------------------------------
    # Lookup helpers
    # ------------------------------------------------------------------

    def get_by_symbol(self, symbol: str) -> Optional[TokenInfo]:
        return self.tokens.get(symbol)

    def get_by_address(self, address: str) -> Optional[TokenInfo]:
        return self._by_address.get(address.lower())

    def get_decimals(self, address: str) -> int:
        """Return decimals for a token address, default 18."""
        info = self.get_by_address(address)
        return info.decimals if info else 18

    def get_all_addresses(self) -> List[str]:
        """Return all checksum addresses."""
        return [t.address for t in self.tokens.values()]

    def get_decimals_map(self) -> Dict[str, int]:
        """Return {lowercase_address: decimals} mapping."""
        return {addr: t.decimals for addr, t in self._by_address.items()}

    # ------------------------------------------------------------------
    # Pair generation
    # ------------------------------------------------------------------

    def generate_pairs(
        self,
        require_stablecoin_leg: bool = False,
    ) -> List[Tuple[str, str]]:
        """
        Generate tradable pair combinations from loaded tokens.

        Args:
            require_stablecoin_leg: If True, at least one token in each pair
                                    must be a stablecoin (useful for reducing
                                    combinatorial explosion).

        Returns:
            List of (address_a, address_b) tuples, capped at self.max_pairs.
        """
        all_tokens = list(self.tokens.values())
        pairs: List[Tuple[str, str]] = []

        for a, b in combinations(all_tokens, 2):
            if require_stablecoin_leg and not (a.is_stablecoin or b.is_stablecoin):
                continue
            pairs.append((a.address, b.address))

        # Prioritize stablecoin-volatile pairs (higher arb likelihood)
        def _priority(pair: Tuple[str, str]) -> int:
            a_info = self.get_by_address(pair[0])
            b_info = self.get_by_address(pair[1])
            if a_info and b_info:
                # One stable + one volatile = highest priority (0)
                if a_info.is_stablecoin != b_info.is_stablecoin:
                    return 0
                # Both volatile = medium priority (1)
                if not a_info.is_stablecoin:
                    return 1
                # Both stablecoins = lowest priority (2)
                return 2
            return 3

        pairs.sort(key=_priority)
        capped = pairs[: self.max_pairs]

        logger.info(
            f"Generated {len(capped)} pairs from {len(all_tokens)} tokens "
            f"(total combos: {len(pairs)}, cap: {self.max_pairs})"
        )
        return capped

    # ------------------------------------------------------------------
    # On-chain liquidity verification
    # ------------------------------------------------------------------

    def verify_v3_pool_exists(
        self,
        token_a: str,
        token_b: str,
        quoter_contract,
        amount: int = None,
        fee: int = 3000,
    ) -> bool:
        """
        Check if a V3 pool has liquidity by attempting a small quote.

        Args:
            token_a: Token A address
            token_b: Token B address
            quoter_contract: Web3 contract instance for QuoterV2
            amount: Amount to quote (default: 1 unit of token_a)
            fee: V3 fee tier

        Returns:
            True if quote succeeds (pool has liquidity)
        """
        if amount is None:
            info = self.get_by_address(token_a)
            decimals = info.decimals if info else 18
            amount = 10 ** decimals  # 1 token

        try:
            params = {
                "tokenIn": Web3.to_checksum_address(token_a),
                "tokenOut": Web3.to_checksum_address(token_b),
                "amountIn": amount,
                "fee": fee,
                "sqrtPriceLimitX96": 0,
            }
            result = quoter_contract.functions.quoteExactInputSingle(params).call()
            return result[0] > 0
        except Exception:
            return False

    def verify_v2_pool_exists(
        self,
        token_a: str,
        token_b: str,
        router_contract,
        amount: int = None,
    ) -> bool:
        """
        Check if a V2 pool has liquidity by attempting a small quote.

        Args:
            token_a: Token A address
            token_b: Token B address
            router_contract: Web3 contract instance for V2 Router
            amount: Amount to quote (default: 1 unit of token_a)

        Returns:
            True if getAmountsOut succeeds
        """
        if amount is None:
            info = self.get_by_address(token_a)
            decimals = info.decimals if info else 18
            amount = 10 ** decimals

        try:
            path = [
                Web3.to_checksum_address(token_a),
                Web3.to_checksum_address(token_b),
            ]
            result = router_contract.functions.getAmountsOut(amount, path).call()
            return result[-1] > 0
        except Exception:
            return False

    def filter_pairs_by_liquidity(
        self,
        pairs: List[Tuple[str, str]],
        quoter_contract=None,
        router_contract=None,
    ) -> List[Tuple[str, str]]:
        """
        Filter pairs to only those with on-chain liquidity on at least one DEX.

        Args:
            pairs: List of (addr_a, addr_b) tuples
            quoter_contract: V3 QuoterV2 contract (optional)
            router_contract: V2 Router contract (optional)

        Returns:
            Filtered list of pairs with verified liquidity.
        """
        if not quoter_contract and not router_contract:
            logger.warning("No contracts provided for liquidity check, returning all pairs")
            return pairs

        verified: List[Tuple[str, str]] = []
        for a, b in pairs:
            has_liquidity = False
            if quoter_contract and self.verify_v3_pool_exists(a, b, quoter_contract):
                has_liquidity = True
            if not has_liquidity and router_contract and self.verify_v2_pool_exists(a, b, router_contract):
                has_liquidity = True
            if has_liquidity:
                verified.append((a, b))

        logger.info(f"Liquidity check: {len(verified)}/{len(pairs)} pairs have liquidity")
        return verified
