"""
Bot utility modules.

NOTE: The legacy ArbitrageBot (src.bot.main) and direct-swap arbitrage logic
(src.bot.arbitrage) have been deprecated. The primary bot entry point is
run_bot.py, which uses:
    - src.opportunity_detector.OpportunityDetector
    - src.flash_loan_orchestrator.FlashLoanOrchestrator

Remaining modules in this package:
    - src.bot.config: Configuration loading (shared by scripts)
    - src.bot.telegram_bot: Telegram notification support
"""
