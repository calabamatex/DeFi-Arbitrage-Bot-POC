"""
Legacy full system integration tests — REMOVED.

These tests used the legacy src.bot.main ArbitrageBot (direct-swap, no flash
loans). The primary bot is now run_bot.py with FlashLoanOrchestrator.

TODO: Replace with integration tests that exercise:
    OpportunityDetector -> FlashLoanOrchestrator -> FlashLoanArbitrageV2 contract
    on an Anvil mainnet fork.
"""

import pytest

pytestmark = pytest.mark.skip(reason="Legacy integration tests; see run_bot.py for primary system")
