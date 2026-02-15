"""
Secure Private Key Management

Supports two methods for loading private keys, in priority order:
1. Encrypted keystore file (recommended) — set KEYSTORE_FILE env var
2. Runtime environment variable (fallback) — set PRIVATE_KEY env var at runtime

NEVER store private keys in .env files on disk. Use one of:
  - Encrypted keystore: python -m src.utils.key_manager create
  - Runtime injection:  PRIVATE_KEY=0x... python run_bot.py
  - Docker secrets:     docker secret create pk ./keyfile
"""

import getpass
import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

from eth_account import Account

logger = logging.getLogger(__name__)

# Well-known Hardhat/Anvil test key — only valid on local forks
_ANVIL_DEFAULT_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"


def load_private_key(
    *,
    keystore_path: Optional[str] = None,
    password: Optional[str] = None,
    allow_env: bool = True,
) -> str:
    """
    Load a private key securely.

    Priority:
        1. Encrypted keystore file (KEYSTORE_FILE env or keystore_path arg)
        2. PRIVATE_KEY environment variable (with warning)

    Args:
        keystore_path: Path to encrypted keystore JSON file.
                       Falls back to KEYSTORE_FILE env var.
        password: Keystore password. Falls back to KEYSTORE_PASSWORD env var,
                  then interactive prompt.
        allow_env: If True, fall back to PRIVATE_KEY env var when no keystore
                   is configured.

    Returns:
        Private key as hex string (0x-prefixed).

    Raises:
        SystemExit: If no key source is available or decryption fails.
    """
    # --- Method 1: Encrypted keystore file ---
    ks_path = keystore_path or os.getenv("KEYSTORE_FILE")
    if ks_path:
        return _load_from_keystore(ks_path, password)

    # --- Method 2: Environment variable (with warning) ---
    if allow_env:
        env_key = os.getenv("PRIVATE_KEY")
        if env_key:
            logger.warning(
                "Loading private key from PRIVATE_KEY env var. "
                "This is acceptable for CI/Docker secrets but NEVER store "
                "keys in .env files. Use an encrypted keystore instead: "
                "python -m src.utils.key_manager create"
            )
            return _validate_key(env_key)

    # --- No key found ---
    logger.error(
        "No private key configured. Set one of:\n"
        "  1. KEYSTORE_FILE=/path/to/keystore.json  (recommended)\n"
        "  2. PRIVATE_KEY=0x...                      (runtime only, never in .env)\n"
        "\n"
        "To create an encrypted keystore:\n"
        "  python -m src.utils.key_manager create"
    )
    sys.exit(1)


def _load_from_keystore(path: str, password: Optional[str] = None) -> str:
    """Load and decrypt a private key from an encrypted keystore file."""
    ks_file = Path(path)
    if not ks_file.exists():
        logger.error(f"Keystore file not found: {path}")
        sys.exit(1)

    try:
        with open(ks_file) as f:
            keystore_json = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Failed to read keystore file: {e}")
        sys.exit(1)

    # Get password: arg → env → interactive prompt
    pwd = password or os.getenv("KEYSTORE_PASSWORD")
    if not pwd:
        try:
            pwd = getpass.getpass(f"Enter password for keystore {ks_file.name}: ")
        except (EOFError, KeyboardInterrupt):
            logger.error("Password input cancelled")
            sys.exit(1)

    try:
        private_key = Account.decrypt(keystore_json, pwd)
        hex_key = "0x" + private_key.hex()
        logger.info(f"Private key loaded from keystore: {ks_file.name}")
        return hex_key
    except ValueError:
        logger.error("Wrong keystore password")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Keystore decryption failed: {e}")
        sys.exit(1)


def create_keystore(
    private_key: Optional[str] = None,
    output_path: Optional[str] = None,
) -> str:
    """
    Create an encrypted keystore file from a private key.

    If no private key is provided, generates a new one.

    Args:
        private_key: Hex private key (0x-prefixed). If None, generates new.
        output_path: Where to save the keystore. Defaults to ./keystore.json.

    Returns:
        Path to the created keystore file.
    """
    if private_key:
        key = _validate_key(private_key)
    else:
        # Generate new key
        account = Account.create()
        key = account.key.hex()
        if not key.startswith("0x"):
            key = "0x" + key
        print(f"Generated new wallet address: {account.address}")

    # Get password
    while True:
        pwd = getpass.getpass("Enter password for keystore encryption: ")
        pwd_confirm = getpass.getpass("Confirm password: ")
        if pwd == pwd_confirm:
            break
        print("Passwords don't match. Try again.")

    if len(pwd) < 8:
        print("WARNING: Password is shorter than 8 characters. Use a stronger password in production.")

    # Encrypt
    keystore_json = Account.encrypt(key, pwd)

    # Save
    out = Path(output_path or "keystore.json")
    with open(out, "w") as f:
        json.dump(keystore_json, f, indent=2)

    # Restrict file permissions (owner-only read/write)
    try:
        out.chmod(0o600)
    except OSError:
        pass  # Windows doesn't support chmod the same way

    account = Account.from_key(key)
    print(f"\nKeystore created: {out}")
    print(f"Address: {account.address}")
    print(f"\nTo use this keystore:")
    print(f"  export KEYSTORE_FILE={out.resolve()}")
    print(f"  python run_bot.py --chain polygon")

    return str(out)


def _validate_key(key: str) -> str:
    """Validate and normalize a hex private key."""
    key = key.strip()
    if not key.startswith("0x"):
        key = "0x" + key

    hex_part = key[2:]
    if len(hex_part) != 64:
        logger.error(f"Private key must be 64 hex characters (got {len(hex_part)})")
        sys.exit(1)

    try:
        int(hex_part, 16)
    except ValueError:
        logger.error("Private key must be a valid hex string")
        sys.exit(1)

    return key


def is_anvil_key(key: str) -> bool:
    """Check if a key is the well-known Anvil/Hardhat default test key."""
    return key.lower().strip() == _ANVIL_DEFAULT_KEY.lower()


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    parser = argparse.ArgumentParser(
        description="Secure key management for arbitrage bot"
    )
    sub = parser.add_subparsers(dest="command")

    # create subcommand
    create_parser = sub.add_parser("create", help="Create encrypted keystore")
    create_parser.add_argument(
        "--key", help="Existing private key to encrypt (omit to generate new)"
    )
    create_parser.add_argument(
        "--output", "-o", default="keystore.json", help="Output file path"
    )

    # verify subcommand
    verify_parser = sub.add_parser("verify", help="Verify a keystore file")
    verify_parser.add_argument("file", help="Keystore file path")

    args = parser.parse_args()

    if args.command == "create":
        create_keystore(private_key=args.key, output_path=args.output)

    elif args.command == "verify":
        key = _load_from_keystore(args.file)
        account = Account.from_key(key)
        print(f"Keystore valid. Address: {account.address}")

    else:
        parser.print_help()
