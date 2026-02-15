"""Comprehensive tests for configuration management."""

import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock, Mock
from decimal import Decimal

from src.bot.config import (
    ConfigurationError,
    load_config,
    load_env_vars,
    load_settings,
    validate_rpc_connection,
    get_erc20_abi,
)


@pytest.fixture
def valid_config():
    """Fixture providing valid configuration data."""
    return {
        "mainnet": {
            "POLYGON_RPC_URL": "https://polygon-rpc.com/",
            "ETHEREUM_RPC_URL": "https://mainnet.infura.io/v3/test",
            "UNISWAP_V3_ROUTER": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
            "SUSHISWAP_ROUTER": "0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F",
            "QUICKSWAP_ROUTER": "0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff",
        },
        "testnet": {
            "POLYGON_RPC_URL": "https://rpc-mumbai.maticvigil.com/",
            "ETHEREUM_RPC_URL": "https://goerli.infura.io/v3/test",
            "UNISWAP_V3_ROUTER": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
            "SUSHISWAP_ROUTER": "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506",
            "QUICKSWAP_ROUTER": "0x8954AfA98594b838bda56FE4C12a09D7739D179b",
        },
        "tokens": [
            {
                "symbol": "WETH",
                "mainnet": {
                    "address": "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619",
                    "decimals": 18,
                },
                "testnet": {
                    "address": "0xA6FA4fB5f76172d178d61B04b0ecd319C5d1C0aa",
                    "decimals": 18,
                },
            },
            {
                "symbol": "USDC",
                "mainnet": {
                    "address": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
                    "decimals": 6,
                },
                "testnet": {
                    "address": "0xe11A86849d99F524cAC3E7A0Ec1241828e332C62",
                    "decimals": 6,
                },
            },
        ],
        "settings": {
            "BASE_PROFIT_THRESHOLD": "0.005",
            "SLIPPAGE_TOLERANCE": "0.01",
            "MAX_RETRIES": 5,
        },
    }


@pytest.fixture
def mock_config_file(valid_config, tmp_path):
    """Create a temporary config file."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_file = config_dir / "config.json"
    config_file.write_text(json.dumps(valid_config))
    return config_file


def test_load_config_testnet(valid_config, monkeypatch):
    """Test loading configuration for testnet environment."""
    # Setup
    monkeypatch.setenv("ENVIRONMENT", "testnet")

    config_json = json.dumps(valid_config)

    with patch("builtins.open", mock_open(read_data=config_json)):
        with patch("pathlib.Path.exists", return_value=True):
            # Execute
            config, env, env_config, token_list = load_config()

            # Assert
            assert env == "testnet"
            assert env_config["POLYGON_RPC_URL"] == "https://rpc-mumbai.maticvigil.com/"
            assert len(token_list) == 2
            assert "WETH" in token_list
            assert "USDC" in token_list
            assert (
                token_list["WETH"]["address"]
                == "0xA6FA4fB5f76172d178d61B04b0ecd319C5d1C0aa"
            )
            assert token_list["WETH"]["decimals"] == 18


def test_load_config_mainnet(valid_config, monkeypatch):
    """Test loading configuration for mainnet environment."""
    # Setup
    monkeypatch.setenv("ENVIRONMENT", "mainnet")
    config_json = json.dumps(valid_config)

    with patch("builtins.open", mock_open(read_data=config_json)):
        with patch("pathlib.Path.exists", return_value=True):
            # Execute
            config, env, env_config, token_list = load_config()

            # Assert
            assert env == "mainnet"
            assert env_config["POLYGON_RPC_URL"] == "https://polygon-rpc.com/"
            assert (
                token_list["WETH"]["address"]
                == "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619"
            )


def test_load_config_missing_environment(valid_config, monkeypatch):
    """Test that invalid environment raises ConfigurationError."""
    # Setup
    monkeypatch.setenv("ENVIRONMENT", "invalid_env")
    config_json = json.dumps(valid_config)

    with patch("builtins.open", mock_open(read_data=config_json)):
        with patch("pathlib.Path.exists", return_value=True):
            # Execute & Assert
            with pytest.raises(ConfigurationError, match="Invalid ENVIRONMENT"):
                load_config()


def test_load_config_invalid_json(monkeypatch):
    """Test that invalid JSON raises ConfigurationError."""
    # Setup
    monkeypatch.setenv("ENVIRONMENT", "testnet")

    with patch("builtins.open", mock_open(read_data="{invalid json content")):
        with patch("pathlib.Path.exists", return_value=True):
            # Execute & Assert
            with pytest.raises(ConfigurationError, match="Invalid JSON"):
                load_config()


def test_load_config_missing_file(monkeypatch):
    """Test that missing config file raises ConfigurationError."""
    # Setup
    monkeypatch.setenv("ENVIRONMENT", "testnet")

    with patch("pathlib.Path.exists", return_value=False):
        # Execute & Assert
        with pytest.raises(ConfigurationError, match="config.json not found"):
            load_config()


def test_load_config_missing_env_section(valid_config, monkeypatch):
    """Test that missing environment section raises ConfigurationError."""
    # Setup
    del valid_config["testnet"]
    monkeypatch.setenv("ENVIRONMENT", "testnet")
    config_json = json.dumps(valid_config)

    with patch("builtins.open", mock_open(read_data=config_json)):
        with patch("pathlib.Path.exists", return_value=True):
            # Execute & Assert
            with pytest.raises(
                ConfigurationError, match="Configuration missing 'testnet'"
            ):
                load_config()


def test_load_config_missing_tokens_section(valid_config, monkeypatch):
    """Test that missing tokens section raises ConfigurationError."""
    # Setup
    del valid_config["tokens"]
    monkeypatch.setenv("ENVIRONMENT", "testnet")
    config_json = json.dumps(valid_config)

    with patch("builtins.open", mock_open(read_data=config_json)):
        with patch("pathlib.Path.exists", return_value=True):
            # Execute & Assert
            with pytest.raises(ConfigurationError, match="missing 'tokens' section"):
                load_config()


def test_load_config_invalid_token_address(valid_config, monkeypatch):
    """Test that invalid token address raises ConfigurationError."""
    # Setup
    valid_config["tokens"][0]["testnet"]["address"] = "invalid_address"
    monkeypatch.setenv("ENVIRONMENT", "testnet")
    config_json = json.dumps(valid_config)

    with patch("builtins.open", mock_open(read_data=config_json)):
        with patch("pathlib.Path.exists", return_value=True):
            # Execute & Assert
            with pytest.raises(ConfigurationError, match="Invalid address"):
                load_config()


def test_load_env_vars_success(monkeypatch):
    """Test successful loading of environment variables."""
    # Setup — ensure no keystore takes priority
    monkeypatch.delenv("KEYSTORE_FILE", raising=False)
    monkeypatch.setenv("PRIVATE_KEY", "0x" + "a" * 64)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")

    # Execute
    private_key, telegram_token, telegram_chat = load_env_vars()

    # Assert
    assert private_key == "0x" + "a" * 64
    assert telegram_token == "test_token"
    assert telegram_chat == "12345"


def test_load_env_vars_missing_private_key(monkeypatch):
    """Test that missing key source raises ConfigurationError."""
    # Setup — no keystore, no env var
    monkeypatch.delenv("KEYSTORE_FILE", raising=False)
    monkeypatch.delenv("PRIVATE_KEY", raising=False)

    # Execute & Assert
    with pytest.raises(ConfigurationError, match="No private key configured"):
        load_env_vars()


def test_load_env_vars_invalid_private_key_length(monkeypatch):
    """Test that invalid private key length raises ConfigurationError."""
    # Setup
    monkeypatch.delenv("KEYSTORE_FILE", raising=False)
    monkeypatch.setenv("PRIVATE_KEY", "0x123")  # Too short

    # Execute & Assert — key_manager exits on invalid key, converted to ConfigurationError
    with pytest.raises(ConfigurationError, match="No private key configured"):
        load_env_vars()


def test_load_env_vars_invalid_private_key_format(monkeypatch):
    """Test that invalid private key format raises ConfigurationError."""
    # Setup
    monkeypatch.delenv("KEYSTORE_FILE", raising=False)
    monkeypatch.setenv("PRIVATE_KEY", "0x" + "z" * 64)  # Invalid hex

    # Execute & Assert
    with pytest.raises(ConfigurationError, match="No private key configured"):
        load_env_vars()


def test_load_env_vars_without_0x_prefix(monkeypatch):
    """Test that private key without 0x prefix is handled correctly."""
    # Setup
    monkeypatch.delenv("KEYSTORE_FILE", raising=False)
    monkeypatch.setenv("PRIVATE_KEY", "a" * 64)

    # Execute
    private_key, _, _ = load_env_vars()

    # Assert
    assert private_key.startswith("0x")
    assert len(private_key) == 66  # 0x + 64 chars


def test_load_settings_with_defaults(valid_config):
    """Test loading settings with default values."""
    # Execute
    settings = load_settings(valid_config)

    # Assert
    assert "BASE_PROFIT_THRESHOLD" in settings
    assert "SLIPPAGE_TOLERANCE" in settings
    assert "MAX_RETRIES" in settings
    assert "GAS_LIMIT" in settings
    assert settings["MAX_RETRIES"] == 5  # From config
    assert settings["GAS_LIMIT"] == 300000  # Default value
    assert isinstance(settings["BASE_PROFIT_THRESHOLD"], Decimal)
    assert isinstance(settings["SLIPPAGE_TOLERANCE"], Decimal)


def test_load_settings_all_defaults():
    """Test loading settings with all defaults when settings section missing."""
    # Setup
    config = {"mainnet": {}, "testnet": {}, "tokens": []}

    # Execute
    settings = load_settings(config)

    # Assert
    assert settings["BASE_PROFIT_THRESHOLD"] == Decimal("0.005")
    assert settings["SLIPPAGE_TOLERANCE"] == Decimal("0.005")
    assert settings["MAX_RETRIES"] == 3
    assert settings["GAS_LIMIT"] == 300000


def test_validate_rpc_connection_success(monkeypatch):
    """Test successful RPC connection validation."""
    # Setup
    mock_w3 = MagicMock()
    mock_w3.is_connected.return_value = True
    mock_w3.eth.chain_id = 137

    with patch("src.bot.config.Web3") as mock_web3_class:
        mock_web3_class.return_value = mock_w3

        # Execute
        result = validate_rpc_connection("https://polygon-rpc.com/", "Polygon")

        # Assert
        assert result is True
        mock_w3.is_connected.assert_called_once()


def test_validate_rpc_connection_failure(monkeypatch):
    """Test RPC connection validation failure."""
    # Setup
    mock_w3 = MagicMock()
    mock_w3.is_connected.return_value = False

    with patch("src.bot.config.Web3") as mock_web3_class:
        mock_web3_class.return_value = mock_w3

        # Execute & Assert
        with pytest.raises(ConfigurationError, match="RPC connection failed"):
            validate_rpc_connection("https://invalid-rpc.com/", "Polygon")


def test_validate_rpc_connection_exception(monkeypatch):
    """Test RPC connection validation with exception."""
    # Setup
    with patch("src.bot.config.Web3") as mock_web3_class:
        mock_web3_class.side_effect = Exception("Connection error")

        # Execute & Assert
        with pytest.raises(ConfigurationError, match="RPC validation failed"):
            validate_rpc_connection("https://invalid-rpc.com/", "Polygon")


def test_get_erc20_abi():
    """Test that get_erc20_abi returns valid ERC20 ABI."""
    # Execute
    abi = get_erc20_abi()

    # Assert
    assert isinstance(abi, list)
    assert len(abi) > 0

    # Check for essential ERC20 functions
    function_names = [
        item.get("name") for item in abi if item.get("type") == "function"
    ]
    assert "balanceOf" in function_names
    assert "transfer" in function_names
    assert "approve" in function_names
    assert "allowance" in function_names
    assert "transferFrom" in function_names

    # Check for events
    event_names = [item.get("name") for item in abi if item.get("type") == "event"]
    assert "Transfer" in event_names
    assert "Approval" in event_names


def test_load_config_missing_required_field(valid_config, monkeypatch):
    """Test that missing required field raises ConfigurationError."""
    # Setup
    del valid_config["testnet"]["POLYGON_RPC_URL"]
    monkeypatch.setenv("ENVIRONMENT", "testnet")
    config_json = json.dumps(valid_config)

    with patch("builtins.open", mock_open(read_data=config_json)):
        with patch("pathlib.Path.exists", return_value=True):
            # Execute & Assert
            with pytest.raises(ConfigurationError, match="Missing required field"):
                load_config()


def test_load_config_token_missing_symbol(valid_config, monkeypatch):
    """Test that token missing symbol raises ConfigurationError."""
    # Setup
    del valid_config["tokens"][0]["symbol"]
    monkeypatch.setenv("ENVIRONMENT", "testnet")
    config_json = json.dumps(valid_config)

    with patch("builtins.open", mock_open(read_data=config_json)):
        with patch("pathlib.Path.exists", return_value=True):
            # Execute & Assert
            with pytest.raises(ConfigurationError, match="Token missing 'symbol'"):
                load_config()


def test_load_config_defaults_to_testnet(valid_config, monkeypatch):
    """Test that ENVIRONMENT defaults to testnet when not set."""
    # Setup
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    config_json = json.dumps(valid_config)

    with patch("builtins.open", mock_open(read_data=config_json)):
        with patch("pathlib.Path.exists", return_value=True):
            # Execute
            config, env, env_config, token_list = load_config()

            # Assert
            assert env == "testnet"
