"""Unit tests for TokenRegistry."""

import json
import os
import tempfile
import pytest
from unittest.mock import Mock, MagicMock

from src.utils.token_registry import TokenRegistry, TokenInfo


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def token_config_dir(tmp_path):
    """Create a temp directory with a Polygon token config."""
    config = {
        "chain_id": 137,
        "chain_name": "polygon",
        "tokens": [
            {"symbol": "USDC", "address": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174", "decimals": 6, "is_stablecoin": True},
            {"symbol": "USDT", "address": "0xc2132D05D31c914a87C6611C10748AEb04B58e8F", "decimals": 6, "is_stablecoin": True},
            {"symbol": "DAI", "address": "0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063", "decimals": 18, "is_stablecoin": True},
            {"symbol": "WMATIC", "address": "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270", "decimals": 18, "is_stablecoin": False},
            {"symbol": "WETH", "address": "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619", "decimals": 18, "is_stablecoin": False},
            {"symbol": "WBTC", "address": "0x1BFD67037B42Cf73acF2047067bd4F2C47D9BfD6", "decimals": 8, "is_stablecoin": False},
        ],
    }
    filepath = tmp_path / "polygon.json"
    filepath.write_text(json.dumps(config))
    return str(tmp_path)


@pytest.fixture
def mock_web3():
    """Mock Web3 with chain_id 137."""
    web3 = Mock()
    web3.eth.chain_id = 137
    return web3


@pytest.fixture
def registry(mock_web3, token_config_dir):
    """Create a registry loaded from the temp config."""
    reg = TokenRegistry(
        web3=mock_web3,
        chain_id=137,
        config_dir=token_config_dir,
        max_pairs=50,
    )
    reg.load_tokens()
    return reg


# ── Loading ───────────────────────────────────────────────────────────

class TestLoading:

    def test_load_tokens_count(self, registry):
        assert len(registry.tokens) == 6

    def test_load_tokens_returns_count(self, mock_web3, token_config_dir):
        reg = TokenRegistry(web3=mock_web3, chain_id=137, config_dir=token_config_dir)
        count = reg.load_tokens()
        assert count == 6

    def test_load_unknown_chain(self, mock_web3, tmp_path):
        """Unknown chain ID returns 0 tokens."""
        reg = TokenRegistry(web3=mock_web3, chain_id=99999, config_dir=str(tmp_path))
        count = reg.load_tokens()
        assert count == 0
        assert len(reg.tokens) == 0

    def test_load_missing_file(self, mock_web3, tmp_path):
        """Missing config file returns 0 tokens."""
        reg = TokenRegistry(web3=mock_web3, chain_id=137, config_dir=str(tmp_path))
        count = reg.load_tokens()
        assert count == 0


# ── Lookups ───────────────────────────────────────────────────────────

class TestLookups:

    def test_get_by_symbol(self, registry):
        usdc = registry.get_by_symbol("USDC")
        assert usdc is not None
        assert usdc.decimals == 6
        assert usdc.is_stablecoin is True

    def test_get_by_symbol_missing(self, registry):
        assert registry.get_by_symbol("SHIB") is None

    def test_get_by_address(self, registry):
        info = registry.get_by_address("0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174")
        assert info is not None
        assert info.symbol == "USDC"

    def test_get_by_address_case_insensitive(self, registry):
        info = registry.get_by_address("0x2791bca1f2de4661ed88a30c99a7a9449aa84174")
        assert info is not None
        assert info.symbol == "USDC"

    def test_get_decimals(self, registry):
        assert registry.get_decimals("0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174") == 6
        assert registry.get_decimals("0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270") == 18

    def test_get_decimals_unknown_address(self, registry):
        assert registry.get_decimals("0x" + "00" * 20) == 18  # default

    def test_get_all_addresses(self, registry):
        addrs = registry.get_all_addresses()
        assert len(addrs) == 6

    def test_get_decimals_map(self, registry):
        dm = registry.get_decimals_map()
        assert len(dm) == 6
        # Keys should be lowercase
        for k in dm:
            assert k == k.lower()


# ── Pair Generation ───────────────────────────────────────────────────

class TestPairGeneration:

    def test_generate_all_pairs(self, registry):
        """6 tokens → C(6,2) = 15 pairs."""
        pairs = registry.generate_pairs()
        assert len(pairs) == 15

    def test_generate_pairs_capped(self, mock_web3, token_config_dir):
        """Respect max_pairs cap."""
        reg = TokenRegistry(web3=mock_web3, chain_id=137, config_dir=token_config_dir, max_pairs=5)
        reg.load_tokens()
        pairs = reg.generate_pairs()
        assert len(pairs) == 5

    def test_stablecoin_leg_filter(self, registry):
        """require_stablecoin_leg filters to pairs with at least one stablecoin."""
        pairs = registry.generate_pairs(require_stablecoin_leg=True)
        for a, b in pairs:
            a_info = registry.get_by_address(a)
            b_info = registry.get_by_address(b)
            assert a_info.is_stablecoin or b_info.is_stablecoin

    def test_stablecoin_pairs_prioritized(self, registry):
        """Stablecoin-volatile pairs should come first in sorted output."""
        pairs = registry.generate_pairs()
        # First pair should be stablecoin-volatile
        a_info = registry.get_by_address(pairs[0][0])
        b_info = registry.get_by_address(pairs[0][1])
        assert a_info.is_stablecoin != b_info.is_stablecoin

    def test_pairs_are_tuples_of_addresses(self, registry):
        pairs = registry.generate_pairs()
        for a, b in pairs:
            assert a.startswith("0x")
            assert b.startswith("0x")
            assert a != b


# ── Liquidity Verification ────────────────────────────────────────────

class TestLiquidityVerification:

    def test_verify_v3_pool_success(self, registry):
        quoter = Mock()
        quoter.functions.quoteExactInputSingle.return_value.call.return_value = [1000, 0, 0, 0]
        result = registry.verify_v3_pool_exists(
            "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
            "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270",
            quoter,
        )
        assert result is True

    def test_verify_v3_pool_failure(self, registry):
        quoter = Mock()
        quoter.functions.quoteExactInputSingle.return_value.call.side_effect = Exception("no pool")
        result = registry.verify_v3_pool_exists(
            "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
            "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270",
            quoter,
        )
        assert result is False

    def test_verify_v2_pool_success(self, registry):
        router = Mock()
        router.functions.getAmountsOut.return_value.call.return_value = [10**18, 500 * 10**6]
        result = registry.verify_v2_pool_exists(
            "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270",
            "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
            router,
        )
        assert result is True

    def test_filter_pairs_no_contracts(self, registry):
        """Without contracts, all pairs are returned."""
        pairs = [("0xA", "0xB"), ("0xC", "0xD")]
        result = registry.filter_pairs_by_liquidity(pairs)
        assert result == pairs

    def test_filter_pairs_with_v3(self, registry):
        quoter = Mock()
        # First pair has liquidity, second doesn't
        quoter.functions.quoteExactInputSingle.return_value.call.side_effect = [
            [1000, 0, 0, 0],
            Exception("no pool"),
        ]
        pairs = [
            ("0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174", "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270"),
            ("0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174", "0x" + "00" * 20),
        ]
        result = registry.filter_pairs_by_liquidity(pairs, quoter_contract=quoter)
        assert len(result) == 1


# ── TokenInfo ─────────────────────────────────────────────────────────

class TestTokenInfo:

    def test_repr(self):
        t = TokenInfo("USDC", "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174", 6, True)
        assert "USDC" in repr(t)
        assert "dec=6" in repr(t)

    def test_checksum_address(self):
        t = TokenInfo("USDC", "0x2791bca1f2de4661ed88a30c99a7a9449aa84174", 6, True)
        assert t.address == "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
