"""
Tests for legacy src.bot.opportunity_scorer — REMOVED.

The legacy OpportunityScorer has been deprecated. The flash loan system
uses OpportunityDetector's built-in profitability filtering instead.
"""

import pytest

pytestmark = pytest.mark.skip(reason="Legacy src.bot.opportunity_scorer has been deprecated")
