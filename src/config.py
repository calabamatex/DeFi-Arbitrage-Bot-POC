"""
Configuration management for Flash Loan Arbitrage Bot
"""
import os
from typing import Dict, List, Optional
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@dataclass
class ChainConfig:
    """Configuration for a blockchain network"""
    chain_id: int
    name: str
    rpc_url: str
    explorer_url: str
    native_token: str
    flash_loan_contract: Optional[str] = None
    min_profit_usd: float = 10.0
    max_gas_price_gwei: float = 100.0


@dataclass
class DatabaseConfig:
    """Database configuration"""
    url: str = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/arbitrage_bot")
    pool_size: int = 10
    max_overflow: int = 20
    echo: bool = os.getenv("DB_ECHO", "false").lower() == "true"


@dataclass
class RedisConfig:
    """Redis configuration"""
    url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    password: Optional[str] = os.getenv("REDIS_PASSWORD", "redis_password")
    db: int = 0
    decode_responses: bool = True


@dataclass
class TelegramConfig:
    """Telegram bot configuration"""
    enabled: bool = os.getenv("TELEGRAM_ENABLED", "false").lower() == "true"
    bot_token: Optional[str] = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id: Optional[str] = os.getenv("TELEGRAM_CHAT_ID")


@dataclass
class TenderlyConfig:
    """Tenderly simulation configuration"""
    enabled: bool = os.getenv("TENDERLY_ENABLED", "false").lower() == "true"
    access_key: Optional[str] = os.getenv("TENDERLY_ACCESS_KEY")
    project: Optional[str] = os.getenv("TENDERLY_PROJECT")
    username: Optional[str] = os.getenv("TENDERLY_USERNAME")


class Config:
    """Main application configuration"""

    # Environment
    ENV: str = os.getenv("ENV", "development")
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"

    # Execution mode
    EXECUTION_MODE: str = os.getenv("EXECUTION_MODE", "testnet")  # testnet or mainnet
    DRY_RUN: bool = os.getenv("DRY_RUN", "true").lower() == "true"

    # Private key for transactions
    PRIVATE_KEY: Optional[str] = os.getenv("PRIVATE_KEY")

    # Profit thresholds
    MIN_PROFIT_USD: float = float(os.getenv("MIN_PROFIT_USD", "10.0"))
    MIN_PROFIT_PERCENTAGE: float = float(os.getenv("MIN_PROFIT_PERCENTAGE", "0.5"))

    # Gas settings
    MAX_GAS_PRICE_GWEI: float = float(os.getenv("MAX_GAS_PRICE_GWEI", "100.0"))
    GAS_PRICE_BUFFER_PERCENTAGE: float = float(os.getenv("GAS_PRICE_BUFFER_PERCENTAGE", "10.0"))

    # Risk management
    MAX_FLASH_LOAN_AMOUNT_USD: float = float(os.getenv("MAX_FLASH_LOAN_AMOUNT_USD", "100000.0"))
    MAX_SLIPPAGE_PERCENTAGE: float = float(os.getenv("MAX_SLIPPAGE_PERCENTAGE", "2.0"))

    # Database
    db = DatabaseConfig()

    # Redis
    redis = RedisConfig()

    # Telegram
    telegram = TelegramConfig()

    # Tenderly
    tenderly = TenderlyConfig()

    # Supported chains configuration
    CHAINS: Dict[str, ChainConfig] = {
        "polygon": ChainConfig(
            chain_id=137,
            name="Polygon",
            rpc_url=os.getenv("POLYGON_RPC_URL", "https://polygon-rpc.com"),
            explorer_url="https://polygonscan.com",
            native_token="MATIC",
        ),
        "mumbai": ChainConfig(
            chain_id=80001,
            name="Mumbai Testnet",
            rpc_url=os.getenv("MUMBAI_RPC_URL", "https://rpc-mumbai.maticvigil.com"),
            explorer_url="https://mumbai.polygonscan.com",
            native_token="MATIC",
        ),
        "arbitrum": ChainConfig(
            chain_id=42161,
            name="Arbitrum One",
            rpc_url=os.getenv("ARBITRUM_RPC_URL", "https://arb1.arbitrum.io/rpc"),
            explorer_url="https://arbiscan.io",
            native_token="ETH",
        ),
        "optimism": ChainConfig(
            chain_id=10,
            name="Optimism",
            rpc_url=os.getenv("OPTIMISM_RPC_URL", "https://mainnet.optimism.io"),
            explorer_url="https://optimistic.etherscan.io",
            native_token="ETH",
        ),
        "base": ChainConfig(
            chain_id=8453,
            name="Base",
            rpc_url=os.getenv("BASE_RPC_URL", "https://mainnet.base.org"),
            explorer_url="https://basescan.org",
            native_token="ETH",
        ),
    }

    # Active chains (based on execution mode)
    @classmethod
    def get_active_chains(cls) -> List[str]:
        """Get list of active chains based on execution mode"""
        if cls.EXECUTION_MODE == "testnet":
            return ["mumbai"]
        else:
            return ["polygon", "arbitrum", "optimism", "base"]

    @classmethod
    def validate(cls) -> None:
        """Validate configuration"""
        errors = []

        if not cls.PRIVATE_KEY and cls.EXECUTION_MODE != "testnet":
            errors.append("PRIVATE_KEY is required for mainnet execution")

        if cls.telegram.enabled and (not cls.telegram.bot_token or not cls.telegram.chat_id):
            errors.append("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID required when Telegram is enabled")

        if cls.tenderly.enabled and not cls.tenderly.access_key:
            errors.append("TENDERLY_ACCESS_KEY required when Tenderly is enabled")

        # Validate RPC URLs for active chains
        for chain_name in cls.get_active_chains():
            chain_config = cls.CHAINS.get(chain_name)
            if not chain_config or not chain_config.rpc_url:
                errors.append(f"RPC URL not configured for chain: {chain_name}")

        if errors:
            raise ValueError(f"Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors))


# Singleton instance
config = Config()


if __name__ == "__main__":
    # Validate configuration when run directly
    try:
        config.validate()
        print("✅ Configuration validated successfully")
        print(f"\nActive chains: {', '.join(config.get_active_chains())}")
        print(f"Execution mode: {config.EXECUTION_MODE}")
        print(f"Dry run: {config.DRY_RUN}")
    except ValueError as e:
        print(f"❌ Configuration validation failed:\n{e}")
