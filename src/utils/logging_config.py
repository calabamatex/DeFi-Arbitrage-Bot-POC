"""
Structured logging configuration.

Production: JSON format (machine-parseable, compatible with log aggregators).
Development: Plaintext format (human-readable).

Usage:
    from src.utils.logging_config import configure_logging
    configure_logging()  # call once at startup
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler

try:
    from pythonjsonlogger import jsonlogger

    HAS_JSON_LOGGER = True
except ImportError:
    HAS_JSON_LOGGER = False


class CustomJsonFormatter(jsonlogger.JsonFormatter if HAS_JSON_LOGGER else logging.Formatter):
    """JSON formatter that adds standard fields to every log record."""

    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        log_record["level"] = record.levelname
        log_record["logger"] = record.name
        log_record["environment"] = os.getenv("ENV", "development")
        log_record["bot_type"] = os.getenv("BOT_TYPE", "arbitrage")

        chain_id = os.getenv("CHAIN_ID")
        if chain_id:
            log_record["chain_id"] = int(chain_id)

        # Propagate trace_id if present
        trace_id = getattr(record, "trace_id", None)
        if trace_id:
            log_record["trace_id"] = trace_id


def configure_logging(
    log_file: str = None,
    level: str = None,
    max_bytes: int = 50 * 1024 * 1024,  # 50 MB
    backup_count: int = 10,
):
    """
    Configure logging for the application.

    Args:
        log_file: Path to log file. Defaults to BOT_TYPE-based name.
        level: Log level string. Defaults to LOG_LEVEL env var or INFO.
        max_bytes: Max size per log file before rotation.
        backup_count: Number of rotated log files to keep.
    """
    env = os.getenv("ENV", "development")
    use_json = env in ("production", "staging") and HAS_JSON_LOGGER
    level_name = level or os.getenv("LOG_LEVEL", "INFO")
    log_level = getattr(logging, level_name.upper(), logging.INFO)

    bot_type = os.getenv("BOT_TYPE", "arbitrage")
    if log_file is None:
        log_file = f"{bot_type}_bot.log"

    # Build handlers
    handlers = []

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    if use_json:
        console.setFormatter(CustomJsonFormatter(
            "%(asctime)s %(level)s %(name)s %(message)s"
        ))
    else:
        console.setFormatter(logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        ))
    handlers.append(console)

    # File handler with rotation (prevents disk exhaustion)
    try:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
        )
        if use_json:
            file_handler.setFormatter(CustomJsonFormatter(
                "%(asctime)s %(level)s %(name)s %(message)s"
            ))
        else:
            file_handler.setFormatter(logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            ))
        handlers.append(file_handler)
    except (OSError, PermissionError):
        # If we can't write to the log file (e.g., read-only fs), continue without it
        pass

    # Configure root logger
    root = logging.getLogger()
    root.setLevel(log_level)

    # Remove existing handlers to avoid duplicates
    for h in root.handlers[:]:
        root.removeHandler(h)

    for h in handlers:
        root.addHandler(h)

    # Suppress noisy third-party loggers
    for noisy in ("urllib3", "web3", "asyncio", "websockets"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.getLogger(__name__).debug(
        f"Logging configured: level={level_name} json={use_json} file={log_file}"
    )
