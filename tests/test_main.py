"""
Tests for legacy src.bot.main — REMOVED.

The legacy ArbitrageBot (direct-swap, no flash loans) has been deprecated.
These tests tested that removed code.

The primary bot is run_bot.py with FlashLoanOrchestrator.
See tests/test_flash_loan_orchestrator.py for active tests.
"""

import pytest

pytestmark = pytest.mark.skip(reason="Legacy src.bot.main has been deprecated; use run_bot.py")
