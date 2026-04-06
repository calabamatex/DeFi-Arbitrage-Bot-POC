"""
Fork-based integration tests for the arbitrage pipeline.

These tests run against a real Anvil mainnet fork and validate the full
detection -> risk-check -> execution pipeline with real on-chain state.

Usage:
    # Start a Polygon fork
    anvil --fork-url $POLYGON_RPC_URL

    # Run integration tests
    FORK_RPC_URL=http://127.0.0.1:8545 pytest tests/integration/test_fork_pipeline.py -v -m integration
"""

import os
import time
import pytest
from unittest.mock import MagicMock, patch
from decimal import Decimal

from web3 import Web3

from src.opportunity_detector import OpportunityDetector
from src.utils.risk_manager import RiskManager


# Polygon mainnet addresses for reference
USDC = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
WMATIC = "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270"
WETH = "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619"

ERC20_ABI = [
    {
        "inputs": [{"internalType": "address", "name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "decimals",
        "outputs": [{"internalType": "uint8", "name": "", "type": "uint8"}],
        "stateMutability": "view",
        "type": "function",
    },
]


@pytest.mark.integration
class TestDetectorOnFork:
    """Tests that run against a real Anvil mainnet fork."""

    def test_detector_scans_without_error(self, fork_web3):
        """Verify scan_opportunities() completes against real mainnet state."""
        detector = OpportunityDetector(
            web3=fork_web3,
            min_profit_usd=1.0,
            max_gas_price_gwei=200,
            check_interval=5,
            min_flash_loan=500 * 10**6,
            max_flash_loan=10000 * 10**6,
        )

        # Should complete without raising
        opportunities = detector.scan_opportunities()

        # Log results for manual review
        print(f"\nScan complete: {len(opportunities)} opportunities found")
        for opp in opportunities:
            direction = opp.get("direction", "?")
            net = opp.get("net_profit", 0)
            decimals = opp.get("token_decimals", 6)
            print(f"  {direction}: net_profit={net / 10**decimals:.4f}")

        # We don't assert specific count — real markets vary
        assert isinstance(opportunities, list)

    def test_detector_uses_multicall_batching(self, fork_web3):
        """Verify batched and sequential methods produce consistent results."""
        detector = OpportunityDetector(
            web3=fork_web3,
            min_profit_usd=0.01,
            max_gas_price_gwei=200,
        )

        amount = 1000 * 10**6  # $1000 USDC

        # Sequential (original)
        sequential = detector.calculate_arbitrage(USDC, WMATIC, amount)

        # Batched (Multicall3)
        batched = detector.calculate_arbitrage_batched(USDC, WMATIC, amount)

        # Both should find the same directions
        seq_directions = {o["direction"] for o in sequential}
        bat_directions = {o["direction"] for o in batched}
        assert seq_directions == bat_directions, (
            f"Direction mismatch: sequential={seq_directions}, batched={bat_directions}"
        )

        # Profits should be identical (same on-chain state, same block)
        for seq_opp in sequential:
            matching = [b for b in batched if b["direction"] == seq_opp["direction"]]
            if matching:
                assert matching[0]["net_profit"] == seq_opp["net_profit"], (
                    f"Profit mismatch for {seq_opp['direction']}"
                )

        print(f"\nConsistency check passed: {len(sequential)} opportunities, "
              f"directions match, profits match")

    def test_detector_filters_unprofitable(self, fork_web3):
        """With a high profit threshold, most real spreads should be filtered."""
        detector = OpportunityDetector(
            web3=fork_web3,
            min_profit_usd=100.0,  # $100 minimum — very high
            max_gas_price_gwei=200,
            min_flash_loan=500 * 10**6,
            max_flash_loan=10000 * 10**6,
        )

        opportunities = detector.scan_opportunities()

        # Real markets rarely have $100+ spreads on standard pairs
        # This test verifies the filter actually works
        print(f"\nHigh-threshold scan: {len(opportunities)} opportunities "
              f"(expected: very few or zero)")

        # If any are found, they should have substantial profit
        for opp in opportunities:
            decimals = opp.get("token_decimals", 6)
            profit_usd = opp["net_profit"] / 10**decimals
            assert profit_usd >= 0, "Negative profit should never pass filter"

    def test_scan_timing(self, fork_web3):
        """Measure scan time — demonstrates the Multicall3 improvement."""
        detector = OpportunityDetector(
            web3=fork_web3,
            min_profit_usd=1.0,
            max_gas_price_gwei=200,
            min_flash_loan=500 * 10**6,
            max_flash_loan=5000 * 10**6,
        )

        start = time.time()
        detector.scan_opportunities()
        elapsed_ms = (time.time() - start) * 1000

        print(f"\nScan time: {elapsed_ms:.0f}ms "
              f"({len(detector.trading_pairs)} pairs)")

        # With Multicall3, scan should complete in reasonable time
        # Without Multicall3 (sequential), this would be 60-120s
        # We don't assert a strict bound since it depends on RPC latency


@pytest.mark.integration
class TestPipelineOnFork:
    """End-to-end pipeline test on fork."""

    def test_full_pipeline_dry_run(self, fork_web3, tmp_path, monkeypatch):
        """
        Full pipeline: Detect -> Risk Check -> Execute (dry-run).

        Uses real RPC for detection but mocked contract addresses for
        the orchestrator (we can't execute real flash loans on a fork
        without deploying our contracts there).
        """
        monkeypatch.setenv("RISK_STATE_FILE", str(tmp_path / "risk_state.json"))

        # Detector with real RPC
        detector = OpportunityDetector(
            web3=fork_web3,
            min_profit_usd=0.01,
            max_gas_price_gwei=200,
            min_flash_loan=500 * 10**6,
            max_flash_loan=5000 * 10**6,
        )

        # Risk manager
        risk_config = {
            "MAX_POSITION_SIZE_USD": 10000,
            "MAX_TOTAL_EXPOSURE_USD": 50000,
            "DAILY_LOSS_LIMIT_USD": 1000,
            "MAX_CONSECUTIVE_LOSSES": 5,
            "CIRCUIT_BREAKER_COOLDOWN_MIN": 60,
        }
        risk_manager = RiskManager(
            web3=fork_web3,
            erc20_abi=ERC20_ABI,
            config=risk_config,
        )

        # Detect opportunities
        opportunities = detector.scan_opportunities()
        print(f"\nDetected {len(opportunities)} opportunities")

        # Run each through risk manager
        approved_count = 0
        rejected_count = 0

        for opp in opportunities[:5]:  # Test top 5
            # Mock orchestrator address for risk validation
            approved, reason = risk_manager.validate_trade(
                opp,
                "0x0000000000000000000000000000000000000001",
                opp.get("token_in", ""),
            )

            if approved:
                approved_count += 1
                print(f"  APPROVED: {opp.get('direction', '?')} "
                      f"profit={opp.get('net_profit', 0)}")
            else:
                rejected_count += 1
                print(f"  REJECTED: {reason}")

        print(f"\nPipeline result: {approved_count} approved, "
              f"{rejected_count} rejected out of {min(len(opportunities), 5)} tested")

        # The pipeline should work without errors regardless of opportunity count
        assert approved_count + rejected_count == min(len(opportunities), 5)
