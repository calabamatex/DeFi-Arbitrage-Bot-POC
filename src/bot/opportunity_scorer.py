"""
Legacy opportunity scorer — DEPRECATED.

This scorer was used by the legacy src.bot.main.ArbitrageBot (direct-swap, no
flash loans). The flash loan system in run_bot.py uses the OpportunityDetector's
built-in profitability filtering instead.

Use `run_bot.py` as the single entry point.
"""

raise ImportError(
    "src.bot.opportunity_scorer is deprecated. The flash loan system uses "
    "src.opportunity_detector for opportunity filtering and ranking."
)
