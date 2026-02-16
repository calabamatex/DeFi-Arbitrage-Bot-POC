"""Configuration management for the arbitrage bot.

This module handles bot-specific configuration (config.json loading, token
lists, ABI definitions, RPC validation).  Shared infrastructure values
(EXECUTION_MODE, database URLs, Redis, Telegram, etc.) are delegated to the
primary configuration module ``src.config.Config``.
"""

from typing import Dict, Tuple, Any, List
from decimal import Decimal
import json
import os
from pathlib import Path
from dotenv import load_dotenv
from web3 import Web3
import logging

# Primary config — single source of truth for shared infrastructure values.
from src.config import Config as _PrimaryConfig

logger = logging.getLogger(__name__)
load_dotenv()


class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing."""

    pass


def load_config() -> Tuple[Dict[str, Any], str, Dict[str, Any], Dict[str, Dict]]:
    """
    Load configuration from config.json and environment.

    The environment name (``mainnet`` / ``testnet``) is resolved from the
    ``ENVIRONMENT`` env-var.  When ``ENVIRONMENT`` is not explicitly set the
    value is derived from the primary config's ``EXECUTION_MODE`` so that
    both modules stay in sync.

    Returns:
        Tuple of (full_config, env_name, env_config, token_list)

    Raises:
        ConfigurationError: If configuration invalid or missing
    """
    # Determine environment — fall back to the primary config's EXECUTION_MODE
    # so that ``ENVIRONMENT`` and ``EXECUTION_MODE`` stay aligned.
    env = os.getenv("ENVIRONMENT") or _PrimaryConfig.EXECUTION_MODE or "testnet"
    if env not in ["mainnet", "testnet"]:
        raise ConfigurationError(
            f"Invalid ENVIRONMENT: {env}. Must be 'mainnet' or 'testnet'"
        )

    # Find config.json - check multiple possible locations
    config_paths = [
        Path(__file__).parent.parent.parent / "config" / "config.json",
        Path.cwd() / "config" / "config.json",
        Path.cwd() / "config.json",
    ]

    config_path = None
    for path in config_paths:
        if path.exists():
            config_path = path
            break

    if not config_path:
        raise ConfigurationError(
            f"config.json not found. Searched: {[str(p) for p in config_paths]}"
        )

    # Load and parse JSON
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        raise ConfigurationError(f"Invalid JSON in config.json: {e}")
    except Exception as e:
        raise ConfigurationError(f"Failed to read config.json: {e}")

    # Validate structure
    if env not in config:
        raise ConfigurationError(
            f"Configuration missing '{env}' section. Found: {list(config.keys())}"
        )

    if "tokens" not in config:
        raise ConfigurationError("Configuration missing 'tokens' section")

    env_config = config[env]

    # Validate required fields in environment config
    required_fields = [
        "POLYGON_RPC_URL",
        "ETHEREUM_RPC_URL",
        "UNISWAP_V3_ROUTER",
        "SUSHISWAP_ROUTER",
        "QUICKSWAP_ROUTER",
    ]

    for field in required_fields:
        if field not in env_config:
            raise ConfigurationError(
                f"Missing required field '{field}' in {env} configuration"
            )

    # Build token list for current environment
    tokens = config["tokens"]
    token_list = {}

    for token in tokens:
        if "symbol" not in token:
            raise ConfigurationError(f"Token missing 'symbol' field: {token}")

        symbol = token["symbol"]
        if env not in token:
            raise ConfigurationError(f"Token {symbol} missing '{env}' configuration")

        token_data = token[env]
        if "address" not in token_data:
            raise ConfigurationError(f"Token {symbol} missing 'address' in {env}")

        if "decimals" not in token_data:
            raise ConfigurationError(f"Token {symbol} missing 'decimals' in {env}")

        # Validate address format
        address = token_data["address"]
        if not Web3.is_address(address):
            raise ConfigurationError(f"Invalid address for token {symbol}: {address}")

        token_list[symbol] = {
            "address": Web3.to_checksum_address(address),
            "decimals": token_data["decimals"],
        }

    logger.info(f"Configuration loaded for {env} with {len(token_list)} tokens")

    return config, env, env_config, token_list


def load_env_vars() -> Tuple[str, str, str]:
    """
    Load sensitive data securely.

    Private key is loaded via key_manager (encrypted keystore or runtime
    env var). NEVER store keys in .env files.

    Telegram credentials are delegated to the primary ``src.config.Config``
    so there is a single source of truth.

    Returns:
        Tuple of (private_key, telegram_token, telegram_chat)

    Raises:
        ConfigurationError: If no key source available or key is invalid
    """
    from src.utils.key_manager import load_private_key

    try:
        private_key = load_private_key()
    except SystemExit:
        raise ConfigurationError(
            "No private key configured. Set KEYSTORE_FILE (recommended) "
            "or PRIVATE_KEY env var. Run: python -m src.utils.key_manager create"
        )

    # Telegram credentials — read from env at call time so monkeypatching
    # and runtime overrides work correctly (Config.telegram is resolved at
    # import time and would not reflect later env changes).
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat = os.getenv("TELEGRAM_CHAT_ID", "")

    if telegram_token and not telegram_chat:
        logger.warning(
            "TELEGRAM_BOT_TOKEN set but TELEGRAM_CHAT_ID missing. "
            "Telegram notifications will not work."
        )

    logger.info("Environment variables loaded successfully")

    return private_key, telegram_token, telegram_chat


def load_settings(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Load settings with defaults.

    Args:
        config: Full configuration dictionary

    Returns:
        Dictionary of settings with defaults applied
    """
    default_settings = {
        "BASE_PROFIT_THRESHOLD": "0.005",
        "SLIPPAGE_TOLERANCE": "0.005",
        "MAX_RETRIES": 3,
        "GAS_LIMIT": 300000,
        "MAX_POSITION_SIZE_USD": 10000,
        "DAILY_LOSS_LIMIT_USD": 1000,
    }

    # Get settings from config or use defaults
    settings = config.get("settings", {})

    # Merge with defaults
    final_settings = default_settings.copy()
    final_settings.update(settings)

    # Convert string decimals to Decimal for precision
    if isinstance(final_settings["BASE_PROFIT_THRESHOLD"], str):
        final_settings["BASE_PROFIT_THRESHOLD"] = Decimal(
            final_settings["BASE_PROFIT_THRESHOLD"]
        )

    if isinstance(final_settings["SLIPPAGE_TOLERANCE"], str):
        final_settings["SLIPPAGE_TOLERANCE"] = Decimal(
            final_settings["SLIPPAGE_TOLERANCE"]
        )

    logger.info(f"Settings loaded: {len(final_settings)} parameters")

    return final_settings


def validate_rpc_connection(rpc_url: str, network_name: str) -> bool:
    """
    Validate RPC connection works.

    Args:
        rpc_url: The RPC endpoint URL
        network_name: Name of the network (for logging)

    Returns:
        True if connection successful

    Raises:
        ConfigurationError: If connection fails
    """
    try:
        w3 = Web3(Web3.HTTPProvider(rpc_url))

        # Test connection by getting chain ID
        if not w3.is_connected():
            raise ConfigurationError(
                f"{network_name} RPC connection failed: Unable to connect to {rpc_url}"
            )

        chain_id = w3.eth.chain_id
        logger.info(
            f"✓ {network_name} RPC connection successful (Chain ID: {chain_id})"
        )

        return True

    except Exception as e:
        raise ConfigurationError(f"{network_name} RPC validation failed: {str(e)}")


def get_erc20_abi() -> List[Dict]:
    """
    Get standard ERC20 ABI.

    Returns:
        List of ABI definitions for ERC20 token interface
    """
    # Standard ERC20 ABI with essential functions
    return [
        {
            "constant": True,
            "inputs": [],
            "name": "name",
            "outputs": [{"name": "", "type": "string"}],
            "type": "function",
        },
        {
            "constant": True,
            "inputs": [],
            "name": "symbol",
            "outputs": [{"name": "", "type": "string"}],
            "type": "function",
        },
        {
            "constant": True,
            "inputs": [],
            "name": "decimals",
            "outputs": [{"name": "", "type": "uint8"}],
            "type": "function",
        },
        {
            "constant": True,
            "inputs": [],
            "name": "totalSupply",
            "outputs": [{"name": "", "type": "uint256"}],
            "type": "function",
        },
        {
            "constant": True,
            "inputs": [{"name": "_owner", "type": "address"}],
            "name": "balanceOf",
            "outputs": [{"name": "balance", "type": "uint256"}],
            "type": "function",
        },
        {
            "constant": False,
            "inputs": [
                {"name": "_to", "type": "address"},
                {"name": "_value", "type": "uint256"},
            ],
            "name": "transfer",
            "outputs": [{"name": "", "type": "bool"}],
            "type": "function",
        },
        {
            "constant": False,
            "inputs": [
                {"name": "_from", "type": "address"},
                {"name": "_to", "type": "address"},
                {"name": "_value", "type": "uint256"},
            ],
            "name": "transferFrom",
            "outputs": [{"name": "", "type": "bool"}],
            "type": "function",
        },
        {
            "constant": False,
            "inputs": [
                {"name": "_spender", "type": "address"},
                {"name": "_value", "type": "uint256"},
            ],
            "name": "approve",
            "outputs": [{"name": "", "type": "bool"}],
            "type": "function",
        },
        {
            "constant": True,
            "inputs": [
                {"name": "_owner", "type": "address"},
                {"name": "_spender", "type": "address"},
            ],
            "name": "allowance",
            "outputs": [{"name": "", "type": "uint256"}],
            "type": "function",
        },
        {
            "anonymous": False,
            "inputs": [
                {"indexed": True, "name": "from", "type": "address"},
                {"indexed": True, "name": "to", "type": "address"},
                {"indexed": False, "name": "value", "type": "uint256"},
            ],
            "name": "Transfer",
            "type": "event",
        },
        {
            "anonymous": False,
            "inputs": [
                {"indexed": True, "name": "owner", "type": "address"},
                {"indexed": True, "name": "spender", "type": "address"},
                {"indexed": False, "name": "value", "type": "uint256"},
            ],
            "name": "Approval",
            "type": "event",
        },
    ]


if __name__ == "__main__":
    """Validate configuration when run directly."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    try:
        # Show primary config alignment
        print(f"Primary config EXECUTION_MODE: {_PrimaryConfig.EXECUTION_MODE}")
        print(f"Primary config DRY_RUN:        {_PrimaryConfig.DRY_RUN}")

        # Load configuration
        config, env, env_config, token_list = load_config()
        print(f"✓ Configuration loaded for {env}")
        print(f"✓ Found {len(token_list)} tokens")

        # Load environment variables
        private_key, telegram_token, telegram_chat = load_env_vars()
        print("✓ Environment variables loaded")

        # Load settings
        settings = load_settings(config)
        print(f"✓ Settings loaded: {len(settings)} parameters")

        # Test RPC connections (non-fatal)
        try:
            validate_rpc_connection(env_config["POLYGON_RPC_URL"], "Polygon")
        except ConfigurationError as e:
            print(f"⚠ RPC validation warning: {e}")
            print("  (This is OK if you're not connected to the network)")

        # Display token list
        print(f"\nConfigured tokens for {env}:")
        for symbol, data in token_list.items():
            print(f"  - {symbol}: {data['address']} ({data['decimals']} decimals)")

        # Display settings
        print(f"\nSettings:")
        for key, value in settings.items():
            print(f"  - {key}: {value}")

        print("\n✅ All configuration checks passed!")

    except ConfigurationError as e:
        print(f"❌ Configuration error: {e}")
        exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        logger.exception("Unexpected error during configuration validation")
        exit(1)
