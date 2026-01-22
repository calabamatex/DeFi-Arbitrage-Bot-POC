"""Tests for DEX factory function."""

import pytest
from src.dex.base import init_dex_instances
from src.dex.uniswap_v3 import UniswapV3
from src.dex.sushiswap import SushiSwap
from src.dex.quickswap import QuickSwap


def test_init_dex_instances_testnet():
    """Test factory creates all DEXes for testnet."""
    env_config = {
        "POLYGON_RPC_URL": "https://rpc-mumbai.maticvigil.com/",
        "UNISWAP_V3_ROUTER": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
        "SUSHISWAP_ROUTER": "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506",
        "QUICKSWAP_ROUTER": "0x8954AfA98594b838bda56FE4C12a09D7739D179b",
    }

    token_list = {}

    dexes = init_dex_instances(env_config, token_list)

    assert "Uniswap V3" in dexes
    assert "SushiSwap" in dexes
    assert "QuickSwap" in dexes
    assert len(dexes) == 3

    # Verify correct types
    assert isinstance(dexes["Uniswap V3"], UniswapV3)
    assert isinstance(dexes["SushiSwap"], SushiSwap)
    assert isinstance(dexes["QuickSwap"], QuickSwap)


def test_init_dex_instances_mainnet():
    """Test factory creates all DEXes for mainnet."""
    env_config = {
        "POLYGON_RPC_URL": "https://polygon-rpc.com/",
        "UNISWAP_V3_ROUTER": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
        "SUSHISWAP_ROUTER": "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506",
        "QUICKSWAP_ROUTER": "0x8954AfA98594b838bda56FE4C12a09D7739D179b",
    }

    token_list = {}

    dexes = init_dex_instances(env_config, token_list)

    assert "Uniswap V3" in dexes
    assert "SushiSwap" in dexes
    assert "QuickSwap" in dexes
    assert len(dexes) == 3


def test_init_dex_instances_missing_addresses():
    """Test with missing addresses."""
    env_config = {"POLYGON_RPC_URL": "https://polygon-rpc.com/"}

    dexes = init_dex_instances(env_config, {})

    assert len(dexes) == 0  # No DEXes initialized


def test_init_dex_instances_partial_addresses():
    """Test with only some DEX addresses provided."""
    env_config = {
        "POLYGON_RPC_URL": "https://rpc-mumbai.maticvigil.com/",
        "UNISWAP_V3_ROUTER": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
        "SUSHISWAP_ROUTER": "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506",
        # Missing QUICKSWAP_ROUTER
    }

    dexes = init_dex_instances(env_config, {})

    assert "Uniswap V3" in dexes
    assert "SushiSwap" in dexes
    assert "QuickSwap" not in dexes
    assert len(dexes) == 2


def test_init_dex_instances_only_uniswap():
    """Test with only Uniswap V3 address."""
    env_config = {
        "POLYGON_RPC_URL": "https://rpc-mumbai.maticvigil.com/",
        "UNISWAP_V3_ROUTER": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
    }

    dexes = init_dex_instances(env_config, {})

    assert "Uniswap V3" in dexes
    assert "SushiSwap" not in dexes
    assert "QuickSwap" not in dexes
    assert len(dexes) == 1


def test_init_dex_instances_only_sushiswap():
    """Test with only SushiSwap address."""
    env_config = {
        "POLYGON_RPC_URL": "https://polygon-rpc.com/",
        "SUSHISWAP_ROUTER": "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506",
    }

    dexes = init_dex_instances(env_config, {})

    assert "Uniswap V3" not in dexes
    assert "SushiSwap" in dexes
    assert "QuickSwap" not in dexes
    assert len(dexes) == 1


def test_init_dex_instances_only_quickswap():
    """Test with only QuickSwap address."""
    env_config = {
        "POLYGON_RPC_URL": "https://polygon-rpc.com/",
        "QUICKSWAP_ROUTER": "0x8954AfA98594b838bda56FE4C12a09D7739D179b",
    }

    dexes = init_dex_instances(env_config, {})

    assert "Uniswap V3" not in dexes
    assert "SushiSwap" not in dexes
    assert "QuickSwap" in dexes
    assert len(dexes) == 1


def test_init_dex_instances_router_addresses_stored():
    """Test that router addresses are correctly stored in DEX instances."""
    env_config = {
        "POLYGON_RPC_URL": "https://rpc-mumbai.maticvigil.com/",
        "UNISWAP_V3_ROUTER": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
        "SUSHISWAP_ROUTER": "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506",
        "QUICKSWAP_ROUTER": "0x8954AfA98594b838bda56FE4C12a09D7739D179b",
    }

    dexes = init_dex_instances(env_config, {})

    # Check that router addresses match (checksummed)
    assert (
        dexes["Uniswap V3"].router_address
        == "0xE592427A0AEce92De3Edee1F18E0157C05861564"
    )
    assert (
        dexes["SushiSwap"].router_address
        == "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506"
    )
    assert (
        dexes["QuickSwap"].router_address
        == "0x8954AfA98594b838bda56FE4C12a09D7739D179b"
    )


def test_init_dex_instances_uniswap_has_factory_quoter():
    """Test that Uniswap V3 instance has factory and quoter addresses."""
    env_config = {
        "POLYGON_RPC_URL": "https://rpc-mumbai.maticvigil.com/",
        "UNISWAP_V3_ROUTER": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
    }

    dexes = init_dex_instances(env_config, {})

    uniswap = dexes["Uniswap V3"]
    assert hasattr(uniswap, "factory_address")
    assert hasattr(uniswap, "quoter_address")
    assert uniswap.factory_address == "0x1F98431c8aD98523631AE4a59f267346ea31F984"
    assert uniswap.quoter_address == "0xb27308f9F90D607463bb33eA1BeBb41C27CE5AB6"


def test_init_dex_instances_dex_names_correct():
    """Test that DEX instances have correct names."""
    env_config = {
        "POLYGON_RPC_URL": "https://rpc-mumbai.maticvigil.com/",
        "UNISWAP_V3_ROUTER": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
        "SUSHISWAP_ROUTER": "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506",
        "QUICKSWAP_ROUTER": "0x8954AfA98594b838bda56FE4C12a09D7739D179b",
    }

    dexes = init_dex_instances(env_config, {})

    assert dexes["Uniswap V3"].name == "Uniswap V3"
    assert dexes["SushiSwap"].name == "SushiSwap"
    assert dexes["QuickSwap"].name == "QuickSwap"


def test_init_dex_instances_empty_config():
    """Test with empty configuration."""
    dexes = init_dex_instances({}, {})

    assert len(dexes) == 0
    assert isinstance(dexes, dict)
