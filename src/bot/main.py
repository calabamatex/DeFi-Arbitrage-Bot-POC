"""
Legacy bot module — DEPRECATED.

The async direct-swap ArbitrageBot that was previously here has been removed.
It did not use flash loans and was disconnected from the primary execution system.

Use `run_bot.py` as the single entry point for the flash loan arbitrage bot.

    python run_bot.py --chain polygon
"""

raise ImportError(
    "src.bot.main is deprecated. Use run_bot.py as the entry point. "
    "See run_bot.py for the flash-loan-based ArbitrageBot."
)
