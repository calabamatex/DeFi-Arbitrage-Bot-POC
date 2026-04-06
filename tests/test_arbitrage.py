"""
Tests for legacy src.bot.arbitrage — REMOVED.

The legacy direct-swap arbitrage module has been deprecated.
The flash loan system uses src.opportunity_detector and
src.flash_loan_orchestrator instead.

See tests/test_flash_loan_orchestrator.py and
tests/test_opportunity_detector.py for active tests.
"""

import pytest

pytestmark = pytest.mark.skip(reason="Legacy src.bot.arbitrage has been deprecated")
