"""
Legacy arbitrage module — DEPRECATED.

The direct-swap arbitrage logic that was previously here has been removed.
It executed trades using the user's own capital (no flash loans) and was
disconnected from the primary flash loan execution pipeline.

The flash loan system uses:
    - src.opportunity_detector.OpportunityDetector (detection)
    - src.flash_loan_orchestrator.FlashLoanOrchestrator (execution)

Use `run_bot.py` as the single entry point.
"""

raise ImportError(
    "src.bot.arbitrage is deprecated. The flash loan system uses "
    "src.opportunity_detector and src.flash_loan_orchestrator instead."
)
