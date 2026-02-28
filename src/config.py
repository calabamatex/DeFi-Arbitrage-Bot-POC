"""
Configuration management for Flash Loan Arbitrage Bot

This is the PRIMARY configuration module. All other config modules (e.g.
src.bot.config) should delegate to this module for shared values such as
EXECUTION_MODE, database URLs, Redis passwords, etc.

Security validation:
    Config.validate_security()   -- fail-fast check for default credentials
    config_doctor()              -- print all resolved values with status
    python -m src.config doctor  -- CLI entrypoint for config_doctor()
"""
import logging
import os
import sys
from typing import Dict, List, Optional
from dataclasses import dataclass, fields
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

    # Private key: loaded at runtime via src.utils.key_manager (keystore or env var).
    # NEVER store private keys in .env files. See: python -m src.utils.key_manager create
    KEYSTORE_FILE: Optional[str] = os.getenv("KEYSTORE_FILE")

    # Profit thresholds
    MIN_PROFIT_USD: float = float(os.getenv("MIN_PROFIT_USD", "10.0"))
    MIN_PROFIT_PERCENTAGE: float = float(os.getenv("MIN_PROFIT_PERCENTAGE", "0.5"))

    # Gas settings
    MAX_GAS_PRICE_GWEI: float = float(os.getenv("MAX_GAS_PRICE_GWEI", "100.0"))
    GAS_PRICE_BUFFER_PERCENTAGE: float = float(os.getenv("GAS_PRICE_BUFFER_PERCENTAGE", "10.0"))

    # Risk management
    MAX_FLASH_LOAN_AMOUNT_USD: float = float(os.getenv("MAX_FLASH_LOAN_AMOUNT_USD", "100000.0"))
    MAX_SLIPPAGE_PERCENTAGE: float = float(os.getenv("MAX_SLIPPAGE_PERCENTAGE", "2.0"))

    # Token / pair scanning
    TOKEN_CONFIG_DIR: str = os.getenv(
        "TOKEN_CONFIG_DIR",
        os.path.join(os.path.dirname(__file__), "..", "config", "tokens"),
    )
    MAX_PAIRS_PER_SCAN: int = int(os.getenv("MAX_PAIRS_PER_SCAN", "50"))

    # MEV Protection
    MEV_PROTECTION_ENABLED: bool = os.getenv("MEV_PROTECTION_ENABLED", "true").lower() == "true"
    FLASHBOTS_RPC_URL: str = os.getenv("FLASHBOTS_RPC_URL", "https://rpc.flashbots.net")
    FLASHBOTS_AUTH_KEY: Optional[str] = os.getenv("FLASHBOTS_AUTH_KEY")
    PRIVATE_TX_MAX_WAIT: int = int(os.getenv("PRIVATE_TX_MAX_WAIT", "25"))

    # Uniswap V3 addresses
    UNISWAP_V3_ROUTER: Optional[str] = os.getenv("UNISWAP_V3_ROUTER")
    UNISWAP_V3_FACTORY: Optional[str] = os.getenv("UNISWAP_V3_FACTORY")
    UNISWAP_V3_QUOTER: Optional[str] = os.getenv("UNISWAP_V3_QUOTER")

    # Liquidation settings
    LIQUIDATION_ENABLED: bool = os.getenv("LIQUIDATION_ENABLED", "false").lower() == "true"
    LIQUIDATION_MIN_PROFIT_USD: float = float(os.getenv("LIQUIDATION_MIN_PROFIT_USD", "50"))
    LIQUIDATION_SCAN_INTERVAL: int = int(os.getenv("LIQUIDATION_SCAN_INTERVAL", "30"))

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
        # -- Mainnets --
        "polygon": ChainConfig(
            chain_id=137,
            name="Polygon",
            rpc_url=os.getenv("POLYGON_RPC_URL", "https://polygon-rpc.com"),
            explorer_url="https://polygonscan.com",
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
        # -- Testnets --
        "polygon_amoy": ChainConfig(
            chain_id=80002,
            name="Polygon Amoy Testnet",
            rpc_url=os.getenv("POLYGON_AMOY_RPC_URL", "https://rpc-amoy.polygon.technology"),
            explorer_url="https://amoy.polygonscan.com",
            native_token="MATIC",
        ),
        "arbitrum_sepolia": ChainConfig(
            chain_id=421614,
            name="Arbitrum Sepolia Testnet",
            rpc_url=os.getenv("ARBITRUM_SEPOLIA_RPC_URL", "https://sepolia-rollup.arbitrum.io/rpc"),
            explorer_url="https://sepolia.arbiscan.io",
            native_token="ETH",
        ),
    }

    # Active chains (based on execution mode)
    @classmethod
    def get_active_chains(cls) -> List[str]:
        """Get list of active chains based on execution mode"""
        if cls.EXECUTION_MODE == "testnet":
            return ["polygon_amoy", "arbitrum_sepolia"]
        else:
            return ["polygon", "arbitrum", "optimism", "base"]

    @classmethod
    def validate(cls) -> None:
        """Validate configuration"""
        errors = []

        if not cls.KEYSTORE_FILE and not os.getenv("PRIVATE_KEY") and cls.EXECUTION_MODE != "testnet":
            errors.append(
                "No private key configured for mainnet. Set KEYSTORE_FILE (recommended) "
                "or PRIVATE_KEY env var. Run: python -m src.utils.key_manager create"
            )

        if cls.telegram.enabled and (not cls.telegram.bot_token or not cls.telegram.chat_id):
            errors.append("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID required when Telegram is enabled")

        if cls.tenderly.enabled and not cls.tenderly.access_key:
            errors.append("TENDERLY_ACCESS_KEY required when Tenderly is enabled")

        # Validate RPC URLs for active chains
        for chain_name in cls.get_active_chains():
            chain_config = cls.CHAINS.get(chain_name)
            if not chain_config or not chain_config.rpc_url:
                errors.append(f"RPC URL not configured for chain: {chain_name}")

        # MEV protection warning (non-fatal)
        if cls.MEV_PROTECTION_ENABLED and not cls.FLASHBOTS_AUTH_KEY and cls.EXECUTION_MODE == "mainnet":
            import warnings
            warnings.warn(
                "MEV_PROTECTION_ENABLED is true but FLASHBOTS_AUTH_KEY is not set. "
                "Private transactions will not be authenticated on mainnet."
            )

        if errors:
            raise ValueError(f"Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors))

    @classmethod
    def validate_security(cls) -> list:
        """Fail-fast check for default/insecure credentials.

        Returns a list of (severity, message) tuples. Raises SystemExit
        in mainnet mode if any CRITICAL issues are found.
        """
        issues = []
        dev_mode = os.getenv("DEV_MODE", "false").lower() == "true"

        # Database URL with default password
        db_url = cls.db.url
        if "postgres:postgres@" in db_url or "CHANGE_ME" in db_url:
            issues.append(("CRITICAL", "DATABASE_URL uses default password"))

        # Redis with default or empty password
        redis_pw = cls.redis.password
        if redis_pw in (None, "", "redis_password"):
            issues.append(("CRITICAL", "REDIS_PASSWORD is default or empty"))

        # PRIVATE_KEY set directly in environment (not keystore)
        if os.getenv("PRIVATE_KEY") and not cls.KEYSTORE_FILE:
            issues.append(("WARNING", "PRIVATE_KEY set as env var — use encrypted keystore instead"))

        # Health auth token not set
        if not os.getenv("HEALTH_AUTH_TOKEN"):
            issues.append(("WARNING", "HEALTH_AUTH_TOKEN not set — status endpoints are unauthenticated"))

        # Admin reset code not set
        if not os.getenv("ADMIN_RESET_CODE"):
            issues.append(("WARNING", "ADMIN_RESET_CODE not set — emergency shutdown reset unavailable"))

        # Mainnet with DRY_RUN still true
        if cls.EXECUTION_MODE == "mainnet" and cls.DRY_RUN:
            issues.append(("INFO", "Mainnet mode with DRY_RUN=true — no live trades will execute"))

        # Fail hard if CRITICAL issues on mainnet (unless DEV_MODE)
        critical = [msg for sev, msg in issues if sev == "CRITICAL"]
        if critical and cls.EXECUTION_MODE == "mainnet" and not dev_mode:
            log = logging.getLogger(__name__)
            for sev, msg in issues:
                log.error(f"[{sev}] {msg}")
            raise SystemExit(
                f"FATAL: {len(critical)} critical security issue(s) in mainnet config. "
                "Fix before starting. Run: python -m src.config doctor"
            )

        return issues


# Singleton instance
config = Config()


def config_doctor():
    """Print all resolved configuration values with status indicators."""
    G = "\033[92m"
    R = "\033[91m"
    Y = "\033[93m"
    C = "\033[96m"
    N = "\033[0m"

    print(f"\n{'=' * 60}")
    print(f"  Configuration Doctor")
    print(f"{'=' * 60}\n")

    # Environment
    print(f"{C}[Environment]{N}")
    print(f"  ENV:             {config.ENV}")
    print(f"  EXECUTION_MODE:  {config.EXECUTION_MODE}")
    print(f"  DRY_RUN:         {config.DRY_RUN}")
    print(f"  DEV_MODE:        {os.getenv('DEV_MODE', 'false')}")
    print(f"  DEBUG:           {config.DEBUG}")

    # Key management
    print(f"\n{C}[Key Management]{N}")
    ks = config.KEYSTORE_FILE
    pk = os.getenv("PRIVATE_KEY")
    if ks:
        exists = os.path.exists(ks)
        print(f"  KEYSTORE_FILE:   {G}set{N} ({ks}) {'exists' if exists else R + 'FILE NOT FOUND' + N}")
    elif pk:
        print(f"  PRIVATE_KEY:     {Y}set via env var{N} (keystore recommended)")
    else:
        print(f"  Private key:     {R}NOT CONFIGURED{N}")

    # Active chains
    print(f"\n{C}[Active Chains]{N}")
    for chain_name in config.get_active_chains():
        chain = config.CHAINS.get(chain_name)
        if chain:
            print(f"  {chain.name}: chain_id={chain.chain_id} rpc={chain.rpc_url[:50]}...")

    # Database
    print(f"\n{C}[Database]{N}")
    db_url = config.db.url
    masked = db_url.split("@")[0].rsplit(":", 1)[0] + ":***@" + db_url.split("@")[-1] if "@" in db_url else db_url
    print(f"  DATABASE_URL:    {masked}")

    # Redis
    print(f"\n{C}[Redis]{N}")
    redis_url = config.redis.url
    print(f"  REDIS_URL:       {redis_url}")
    pw = config.redis.password
    if pw in (None, "", "redis_password"):
        print(f"  REDIS_PASSWORD:  {R}default/empty{N}")
    else:
        print(f"  REDIS_PASSWORD:  {G}set{N}")

    # Trading params
    print(f"\n{C}[Trading Parameters]{N}")
    print(f"  MIN_PROFIT_USD:           {config.MIN_PROFIT_USD}")
    print(f"  MAX_GAS_PRICE_GWEI:       {config.MAX_GAS_PRICE_GWEI}")
    print(f"  MAX_FLASH_LOAN_AMOUNT_USD: {config.MAX_FLASH_LOAN_AMOUNT_USD}")
    print(f"  MAX_SLIPPAGE_PERCENTAGE:   {config.MAX_SLIPPAGE_PERCENTAGE}")

    # MEV Protection
    print(f"\n{C}[MEV Protection]{N}")
    print(f"  ENABLED:         {config.MEV_PROTECTION_ENABLED}")
    print(f"  FLASHBOTS_RPC:   {config.FLASHBOTS_RPC_URL}")
    print(f"  AUTH_KEY:        {'set' if config.FLASHBOTS_AUTH_KEY else 'not set'}")
    print(f"  MAX_WAIT:        {config.PRIVATE_TX_MAX_WAIT} blocks")

    # Uniswap V3 Addresses
    print(f"\n{C}[Uniswap V3 Addresses]{N}")
    print(f"  ROUTER:          {config.UNISWAP_V3_ROUTER or 'not set'}")
    print(f"  FACTORY:         {config.UNISWAP_V3_FACTORY or 'not set'}")
    print(f"  QUOTER:          {config.UNISWAP_V3_QUOTER or 'not set'}")

    # Liquidation
    print(f"\n{C}[Liquidation]{N}")
    print(f"  ENABLED:         {config.LIQUIDATION_ENABLED}")
    print(f"  MIN_PROFIT_USD:  {config.LIQUIDATION_MIN_PROFIT_USD}")
    print(f"  SCAN_INTERVAL:   {config.LIQUIDATION_SCAN_INTERVAL}s")

    # Security check
    print(f"\n{C}[Security Validation]{N}")
    issues = config.validate_security()
    if not issues:
        print(f"  {G}No issues found{N}")
    for sev, msg in issues:
        color = R if sev == "CRITICAL" else Y if sev == "WARNING" else N
        print(f"  {color}[{sev}]{N} {msg}")

    # Config.validate()
    print(f"\n{C}[Config Validation]{N}")
    try:
        config.validate()
        print(f"  {G}PASS{N} Config.validate()")
    except ValueError as e:
        print(f"  {R}FAIL{N} {e}")

    print(f"\n{'=' * 60}\n")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "doctor":
        config_doctor()
    else:
        try:
            config.validate()
            print("Configuration validated successfully")
            print(f"\nActive chains: {', '.join(config.get_active_chains())}")
            print(f"Execution mode: {config.EXECUTION_MODE}")
            print(f"Dry run: {config.DRY_RUN}")
            print("\nRun 'python -m src.config doctor' for detailed diagnostics.")
        except ValueError as e:
            print(f"Configuration validation failed:\n{e}")
            sys.exit(1)
