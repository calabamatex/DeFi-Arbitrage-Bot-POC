"""Structured error taxonomy for the arbitrage bot.

Provides a hierarchy of exceptions with retryable/severity metadata,
a classify_web3_exception() helper to map raw errors into the taxonomy,
and a RETRY_MATRIX for backoff configuration.
"""


class BotError(Exception):
    """Base exception for all bot errors."""
    retryable: bool = False
    severity: str = "ERROR"  # DEBUG, INFO, WARNING, ERROR, CRITICAL


# ---------------------------------------------------------------------------
# RPC / blockchain communication errors
# ---------------------------------------------------------------------------

class RPCError(BotError):
    """Base for all RPC/blockchain communication errors."""
    retryable = True


class RPCTimeoutError(RPCError):
    """RPC call timed out."""
    pass


class RPCConnectionError(RPCError):
    """Cannot connect to RPC endpoint."""
    pass


class ContractCallError(RPCError):
    """Smart contract call failed (not revert)."""
    pass


# ---------------------------------------------------------------------------
# Transaction errors
# ---------------------------------------------------------------------------

class TransactionError(BotError):
    """Base for transaction-related errors."""


class TransactionRevertError(TransactionError):
    """Transaction reverted on-chain."""
    retryable = False


class NonceTooLowError(TransactionError):
    """Nonce already used — need to sync."""
    retryable = True


class InsufficientFundsError(TransactionError):
    """Not enough gas token for transaction."""
    retryable = False
    severity = "CRITICAL"


class GasTooHighError(TransactionError):
    """Gas price exceeds configured maximum."""
    retryable = True  # Gas may drop


# ---------------------------------------------------------------------------
# Execution-flow errors
# ---------------------------------------------------------------------------

class ExecutionError(BotError):
    """Errors in the arbitrage execution flow."""


class SlippageExceededError(ExecutionError):
    """Actual slippage exceeded tolerance."""
    retryable = False


class ProfitBelowMinimumError(ExecutionError):
    """Profit doesn't meet minimum threshold after gas."""
    retryable = False


class FlashLoanError(ExecutionError):
    """Flash loan request failed."""
    retryable = True


# ---------------------------------------------------------------------------
# Data errors
# ---------------------------------------------------------------------------

class DataError(BotError):
    """Errors in data retrieval or processing."""


class PriceUnavailableError(DataError):
    """Cannot fetch price for token pair."""
    retryable = True


class TokenNotFoundError(DataError):
    """Token not found in registry or on-chain."""
    retryable = False


# ---------------------------------------------------------------------------
# Infrastructure errors
# ---------------------------------------------------------------------------

class InfrastructureError(BotError):
    """Database, Redis, or other infrastructure errors."""
    retryable = True


class DatabaseError(InfrastructureError):
    """Database operation failed."""
    pass


# ---------------------------------------------------------------------------
# Configuration errors
# ---------------------------------------------------------------------------

class ConfigurationError(BotError):
    """Invalid or missing configuration."""
    retryable = False
    severity = "CRITICAL"


# ---------------------------------------------------------------------------
# Retry matrix
# ---------------------------------------------------------------------------

RETRY_MATRIX = {
    RPCTimeoutError:     {"max_retries": 3, "backoff_seconds": 2},
    RPCConnectionError:  {"max_retries": 5, "backoff_seconds": 5},
    ContractCallError:   {"max_retries": 2, "backoff_seconds": 1},
    NonceTooLowError:    {"max_retries": 1, "backoff_seconds": 0},
    GasTooHighError:     {"max_retries": 3, "backoff_seconds": 30},
    FlashLoanError:      {"max_retries": 1, "backoff_seconds": 5},
    PriceUnavailableError: {"max_retries": 2, "backoff_seconds": 1},
    DatabaseError:       {"max_retries": 3, "backoff_seconds": 2},
}


def classify_web3_exception(e: Exception) -> BotError:
    """Classify a raw web3/requests exception into our taxonomy.

    Maps common error strings to specific exception types so callers
    can handle and retry appropriately.
    """
    error_str = str(e).lower()

    if "timeout" in error_str or "timed out" in error_str:
        return RPCTimeoutError(str(e))
    elif "connection" in error_str or "connect" in error_str:
        return RPCConnectionError(str(e))
    elif "nonce too low" in error_str:
        return NonceTooLowError(str(e))
    elif "insufficient funds" in error_str:
        return InsufficientFundsError(str(e))
    elif "execution reverted" in error_str or "revert" in error_str:
        return TransactionRevertError(str(e))
    elif "gas" in error_str and ("too high" in error_str or "exceeds" in error_str):
        return GasTooHighError(str(e))
    elif "slippage" in error_str:
        return SlippageExceededError(str(e))
    elif "flash loan" in error_str:
        return FlashLoanError(str(e))
    else:
        return RPCError(str(e))


def get_retry_config(error: BotError) -> dict:
    """Look up retry configuration for a given error instance.

    Returns {"max_retries": N, "backoff_seconds": N} or
    {"max_retries": 0, "backoff_seconds": 0} if not retryable.
    """
    for error_class, config in RETRY_MATRIX.items():
        if isinstance(error, error_class):
            return config
    if error.retryable:
        return {"max_retries": 1, "backoff_seconds": 1}
    return {"max_retries": 0, "backoff_seconds": 0}
