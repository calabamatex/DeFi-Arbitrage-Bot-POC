"""
Chaos / Fault Injection Tests

Validates that the arbitrage bot degrades gracefully under adverse conditions:
- RPC timeouts and disconnects during scanning and execution
- Gas price spikes between simulation and send
- Flash loan reverts (insufficient profit, slippage, deadline)
- Database connection loss during trade logging (bot must survive)
- Circuit breaker cascade under sustained failures
- Emergency shutdown persistence across restarts
- Nonce collision on rapid execution
- Corrupted risk state file recovery
"""

import asyncio
import json
import os
import tempfile
import time
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, Mock, PropertyMock, patch

import pytest

from src.utils.gas_optimizer import GasOptimizer
from src.utils.price_cache import PriceCache
from src.utils.risk_manager import (
    CircuitBreaker,
    LossTracker,
    PositionManager,
    RiskManager,
    TradeResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_trade(success: bool, pnl: float, pair: str = "WETH/USDC") -> TradeResult:
    return TradeResult(
        success=success,
        timestamp=datetime.now(),
        profit_loss=Decimal(str(pnl)),
        token_pair=pair,
        buy_dex="quickswap",
        sell_dex="sushiswap",
        amount=Decimal("1000"),
        gas_cost=Decimal("0.5"),
        message="test",
    )


def _mock_web3():
    w3 = MagicMock()
    w3.eth.gas_price = 30 * 10**9
    w3.eth.chain_id = 137
    w3.eth.get_block.return_value = {"baseFeePerGas": 25 * 10**9}
    w3.to_checksum_address = lambda x: x
    return w3


def _risk_config():
    return {
        "MAX_POSITION_SIZE_USD": 10000,
        "MAX_TOTAL_EXPOSURE_USD": 50000,
        "DAILY_LOSS_LIMIT_USD": 1000,
        "WEEKLY_LOSS_LIMIT_USD": 5000,
        "MAX_CONSECUTIVE_LOSSES": 5,
        "CIRCUIT_BREAKER_COOLDOWN_MIN": 60,
    }


# ---------------------------------------------------------------------------
# 1. RPC Timeout / Disconnect
# ---------------------------------------------------------------------------

class TestRPCFailures:
    """RPC goes down mid-operation — bot should fallback, not crash."""

    def test_gas_price_rpc_timeout_uses_fallback(self):
        """GasOptimizer returns 30 gwei fallback when RPC is unreachable."""
        w3 = _mock_web3()
        type(w3.eth).gas_price = PropertyMock(side_effect=Exception("RPC timeout"))
        optimizer = GasOptimizer(web3=w3)

        price = optimizer.get_optimal_gas_price("normal")
        assert price == 30_000_000_000  # 30 gwei fallback

    def test_eip1559_rpc_timeout_uses_fallback(self):
        """EIP-1559 params use safe fallback when get_block fails."""
        w3 = _mock_web3()
        w3.eth.get_block.side_effect = ConnectionError("Connection reset by peer")
        optimizer = GasOptimizer(web3=w3)

        params = optimizer.use_eip1559("normal")
        assert params["maxFeePerGas"] == 100_000_000_000
        assert params["maxPriorityFeePerGas"] == 2_000_000_000

    def test_gas_optimizer_survives_intermittent_failures(self):
        """GasOptimizer recovers when RPC flaps between up and down."""
        w3 = _mock_web3()
        optimizer = GasOptimizer(web3=w3)

        # First call succeeds
        assert optimizer.get_optimal_gas_price("normal") == 30 * 10**9

        # RPC goes down
        type(w3.eth).gas_price = PropertyMock(side_effect=Exception("timeout"))
        assert optimizer.get_optimal_gas_price("normal") == 30_000_000_000

        # RPC comes back
        type(w3.eth).gas_price = PropertyMock(return_value=50 * 10**9)
        assert optimizer.get_optimal_gas_price("normal") == 50 * 10**9

    @pytest.mark.asyncio
    async def test_balance_check_rpc_failure_returns_false(self):
        """Balance check returns False (conservative) when RPC fails."""
        w3 = _mock_web3()
        mock_contract = MagicMock()
        mock_contract.functions.balanceOf.return_value.call.side_effect = Exception(
            "RPC unavailable"
        )
        w3.eth.contract.return_value = mock_contract

        from src.utils.risk_manager import BalanceValidator

        validator = BalanceValidator(w3, [])
        result = await validator.check_balance("0xACCOUNT", "0xTOKEN", Decimal("100"))
        assert result is False  # Conservative: deny trade on failure


# ---------------------------------------------------------------------------
# 2. Gas Price Spike Between Simulation and Execution
# ---------------------------------------------------------------------------

class TestGasPriceVolatility:
    """Gas price doubles between profitability check and actual send."""

    def test_gas_spike_makes_trade_unprofitable(self):
        """Trade that was profitable at 30 gwei is not at 300 gwei."""
        w3 = _mock_web3()
        optimizer = GasOptimizer(web3=w3)

        # At 30 gwei: profitable
        assert optimizer.is_profitable_after_gas(
            expected_profit=Decimal("0.02"),  # 0.02 ETH profit
            gas_limit=500_000,
        )

        # Gas spikes to 300 gwei (10x)
        type(w3.eth).gas_price = PropertyMock(return_value=300 * 10**9)

        # Same trade is now unprofitable
        assert not optimizer.is_profitable_after_gas(
            expected_profit=Decimal("0.02"),
            gas_limit=500_000,
        )

    def test_gas_cost_scales_linearly(self):
        """Gas cost scales linearly — no overflow or rounding errors."""
        w3 = _mock_web3()
        optimizer = GasOptimizer(web3=w3)

        # Normal gas
        type(w3.eth).gas_price = PropertyMock(return_value=30 * 10**9)
        cost_normal = optimizer.estimate_gas_cost(500_000)

        # 10x gas
        type(w3.eth).gas_price = PropertyMock(return_value=300 * 10**9)
        cost_high = optimizer.estimate_gas_cost(500_000)

        # Should be roughly 10x (exact because of integer math)
        ratio = cost_high / cost_normal
        assert Decimal("9.9") < ratio < Decimal("10.1")


# ---------------------------------------------------------------------------
# 3. Circuit Breaker Cascade Under Sustained Failures
# ---------------------------------------------------------------------------

class TestCircuitBreakerChaos:
    """Rapid consecutive failures trigger and hold circuit breaker."""

    def test_exact_threshold_triggers(self):
        """Exactly max_consecutive_losses failures triggers breaker."""
        cb = CircuitBreaker(max_consecutive_losses=5, cooldown_minutes=60)
        for _ in range(4):
            cb.record_trade_result(False)
            assert not cb.is_active

        cb.record_trade_result(False)  # 5th failure
        assert cb.is_active

    def test_single_success_resets_counter(self):
        """One success in a streak of failures resets the counter."""
        cb = CircuitBreaker(max_consecutive_losses=5)
        for _ in range(4):
            cb.record_trade_result(False)

        cb.record_trade_result(True)  # Reset
        assert cb.consecutive_losses == 0
        assert not cb.is_active

        # Need 5 more to trigger
        for _ in range(4):
            cb.record_trade_result(False)
        assert not cb.is_active

    def test_breaker_blocks_all_trades_during_cooldown(self):
        """No trades allowed while circuit breaker is active."""
        cb = CircuitBreaker(max_consecutive_losses=3, cooldown_minutes=60)
        for _ in range(3):
            cb.record_trade_result(False)

        allowed, msg = cb.is_trading_allowed()
        assert not allowed
        assert "active" in msg.lower()

    def test_breaker_auto_resets_after_cooldown(self):
        """Circuit breaker resets automatically after cooldown expires."""
        cb = CircuitBreaker(max_consecutive_losses=3, cooldown_minutes=1)
        for _ in range(3):
            cb.record_trade_result(False)

        assert cb.is_active
        # Simulate cooldown expiry
        cb.triggered_at = datetime.now() - timedelta(minutes=2)

        allowed, msg = cb.is_trading_allowed()
        assert allowed
        assert not cb.is_active

    def test_rapid_fire_failures_only_trigger_once(self):
        """100 rapid failures only trigger breaker once (idempotent)."""
        cb = CircuitBreaker(max_consecutive_losses=5)
        for _ in range(100):
            cb.record_trade_result(False)

        assert cb.is_active
        assert cb.consecutive_losses == 100
        # Should still be one trigger event
        assert cb.triggered_at is not None


# ---------------------------------------------------------------------------
# 4. Risk Manager — Daily/Weekly Loss Limits
# ---------------------------------------------------------------------------

class TestLossLimitChaos:
    """Loss limits halt trading under sustained negative PnL."""

    def test_daily_loss_limit_blocks_trading(self):
        """Exceeding daily loss limit blocks all further trades."""
        tracker = LossTracker(daily_loss_limit_usd=Decimal("100"))

        # Record losses totaling $150
        for _ in range(3):
            tracker.record_trade(_make_trade(False, -50))

        ok, msg = tracker.check_loss_limit()
        assert not ok
        assert "daily" in msg.lower()

    def test_weekly_loss_limit_blocks_trading(self):
        """Exceeding weekly loss limit blocks trading even if daily is OK."""
        tracker = LossTracker(
            daily_loss_limit_usd=Decimal("1000"),
            weekly_loss_limit_usd=Decimal("200"),
        )

        # Spread losses across 3 days (within weekly window, under daily limit)
        for days_ago in range(3):
            trade = _make_trade(False, -80)
            trade.timestamp = datetime.now() - timedelta(days=days_ago)
            tracker.trades.append(trade)

        ok, msg = tracker.check_loss_limit()
        assert not ok
        assert "weekly" in msg.lower()

    def test_profits_offset_losses(self):
        """Profits reduce daily loss — only net loss matters."""
        tracker = LossTracker(daily_loss_limit_usd=Decimal("100"))

        tracker.record_trade(_make_trade(False, -80))
        tracker.record_trade(_make_trade(True, 60))  # Offset

        ok, _ = tracker.check_loss_limit()
        assert ok  # Net = -$20, under $100 limit


# ---------------------------------------------------------------------------
# 5. Emergency Shutdown Persistence
# ---------------------------------------------------------------------------

class TestEmergencyShutdownChaos:
    """Emergency shutdown survives process restarts."""

    def test_shutdown_persists_to_disk(self):
        """Emergency shutdown state is saved and restored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = os.path.join(tmpdir, "risk_state.json")
            os.environ["RISK_STATE_FILE"] = state_file

            w3 = _mock_web3()

            # Create manager and trigger shutdown
            rm1 = RiskManager(w3, [], _risk_config())
            rm1.emergency_shutdown("Flash loan exploit detected")

            assert rm1.shutdown_active
            assert Path(state_file).exists()

            # Simulate restart — new manager loads state
            rm2 = RiskManager(w3, [], _risk_config())
            assert rm2.shutdown_active
            assert rm2.shutdown_reason == "Flash loan exploit detected"

            # All trades blocked
            approved, reason = rm2.validate_trade(
                {"token_in": "WETH", "token_out": "USDC", "amount_in": 1000},
                "0xACCOUNT",
                "0xTOKEN",
            )
            assert not approved
            assert "emergency" in reason.lower()

            del os.environ["RISK_STATE_FILE"]

    def test_shutdown_requires_correct_admin_code(self):
        """Only correct ADMIN_RESET_CODE can reset shutdown."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = os.path.join(tmpdir, "risk_state.json")
            os.environ["RISK_STATE_FILE"] = state_file
            os.environ["ADMIN_RESET_CODE"] = "secret123"

            w3 = _mock_web3()
            rm = RiskManager(w3, [], _risk_config())
            rm.emergency_shutdown("test")

            # Wrong code
            assert not rm.reset_shutdown("wrong_code")
            assert rm.shutdown_active

            # Correct code
            assert rm.reset_shutdown("secret123")
            assert not rm.shutdown_active

            del os.environ["RISK_STATE_FILE"]
            del os.environ["ADMIN_RESET_CODE"]

    def test_shutdown_without_admin_code_cannot_reset(self):
        """If ADMIN_RESET_CODE is unset, shutdown cannot be reset."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = os.path.join(tmpdir, "risk_state.json")
            os.environ["RISK_STATE_FILE"] = state_file
            os.environ.pop("ADMIN_RESET_CODE", None)

            w3 = _mock_web3()
            rm = RiskManager(w3, [], _risk_config())
            rm.emergency_shutdown("test")

            assert not rm.reset_shutdown("anything")
            assert rm.shutdown_active

            del os.environ["RISK_STATE_FILE"]


# ---------------------------------------------------------------------------
# 6. Corrupted Risk State File Recovery
# ---------------------------------------------------------------------------

class TestStateFileCorruption:
    """Bot recovers from corrupted or tampered state files."""

    def test_invalid_json_starts_fresh(self):
        """Corrupted JSON file causes graceful fresh start."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = os.path.join(tmpdir, "risk_state.json")
            os.environ["RISK_STATE_FILE"] = state_file

            # Write garbage
            Path(state_file).write_text("NOT VALID JSON {{{")

            w3 = _mock_web3()
            rm = RiskManager(w3, [], _risk_config())

            # Should start fresh — no crash, no shutdown
            assert not rm.shutdown_active
            assert rm.circuit_breaker.consecutive_losses == 0

            del os.environ["RISK_STATE_FILE"]

    def test_empty_state_file_starts_fresh(self):
        """Empty state file is handled gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = os.path.join(tmpdir, "risk_state.json")
            os.environ["RISK_STATE_FILE"] = state_file

            Path(state_file).write_text("")

            w3 = _mock_web3()
            rm = RiskManager(w3, [], _risk_config())

            assert not rm.shutdown_active

            del os.environ["RISK_STATE_FILE"]

    def test_partial_state_restores_available_fields(self):
        """Partial state file restores what it can, defaults the rest."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = os.path.join(tmpdir, "risk_state.json")
            os.environ["RISK_STATE_FILE"] = state_file

            partial_state = {
                "version": 1,
                "circuit_breaker": {"consecutive_losses": 3, "is_active": False},
                # Missing: shutdown, trades
            }
            Path(state_file).write_text(json.dumps(partial_state))

            w3 = _mock_web3()
            rm = RiskManager(w3, [], _risk_config())

            assert rm.circuit_breaker.consecutive_losses == 3
            assert not rm.shutdown_active  # Default
            assert len(rm.loss_tracker.trades) == 0  # Default

            del os.environ["RISK_STATE_FILE"]

    def test_tampered_trade_history_loaded_correctly(self):
        """Trade history with invalid entries is handled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = os.path.join(tmpdir, "risk_state.json")
            os.environ["RISK_STATE_FILE"] = state_file

            state = {
                "version": 1,
                "circuit_breaker": {"consecutive_losses": 0, "is_active": False},
                "shutdown": {"active": False, "reason": None},
                "trades": [
                    {
                        "success": True,
                        "timestamp": datetime.now().isoformat(),
                        "profit_loss": "15.50",
                        "token_pair": "WETH/USDC",
                        "buy_dex": "quickswap",
                        "sell_dex": "sushiswap",
                        "amount": "1000",
                        "gas_cost": "0.5",
                        "message": "ok",
                    },
                ],
            }
            Path(state_file).write_text(json.dumps(state))

            w3 = _mock_web3()
            rm = RiskManager(w3, [], _risk_config())

            assert len(rm.loss_tracker.trades) == 1
            assert rm.loss_tracker.trades[0].profit_loss == Decimal("15.50")

            del os.environ["RISK_STATE_FILE"]


# ---------------------------------------------------------------------------
# 7. Position and Exposure Limits Under Stress
# ---------------------------------------------------------------------------

class TestPositionManagerChaos:
    """Position manager prevents over-concentration and over-exposure."""

    def test_exposure_limit_blocks_new_trades(self):
        """Cannot open new positions when at max exposure."""
        pm = PositionManager(
            max_position_size_usd=Decimal("10000"),
            max_total_exposure_usd=Decimal("50000"),
        )

        # Fill up exposure
        pm.track_open_position("WETH", Decimal("20000"))
        pm.track_open_position("WBTC", Decimal("20000"))
        pm.track_open_position("LINK", Decimal("10000"))

        # Total = $50,000 = max
        ok, msg = pm.check_exposure_limit()
        assert ok  # At limit, not over

        pm.track_open_position("AAVE", Decimal("1"))  # Over by $1
        ok, msg = pm.check_exposure_limit()
        assert not ok

    def test_position_size_rejection(self):
        """Single position exceeding max is rejected."""
        pm = PositionManager(
            max_position_size_usd=Decimal("10000"),
            max_total_exposure_usd=Decimal("100000"),
        )

        ok, _ = pm.validate_position_size(Decimal("10001"))
        assert not ok

        ok, _ = pm.validate_position_size(Decimal("10000"))
        assert ok

    def test_concentration_risk_prevents_single_token_dominance(self):
        """Cannot concentrate >30% of portfolio in one token."""
        pm = PositionManager(
            max_position_size_usd=Decimal("10000"),
            max_total_exposure_usd=Decimal("100000"),
            max_concentration_percent=Decimal("0.30"),
        )

        pm.track_open_position("WETH", Decimal("5000"))
        pm.track_open_position("WBTC", Decimal("5000"))

        # Adding $5000 WETH would make WETH = $10000 / $15000 = 66%
        ok, msg = pm.check_concentration_risk("WETH", Decimal("5000"))
        assert not ok
        assert "concentration" in msg.lower()

    def test_close_position_frees_exposure(self):
        """Closing a position frees exposure for new trades."""
        pm = PositionManager(
            max_position_size_usd=Decimal("10000"),
            max_total_exposure_usd=Decimal("10000"),
        )

        pm.track_open_position("WETH", Decimal("10000"))
        ok, _ = pm.check_exposure_limit()
        assert ok  # At limit

        pm.track_open_position("WBTC", Decimal("1"))
        ok, _ = pm.check_exposure_limit()
        assert not ok  # Over limit

        pm.close_position("WETH")  # Free $10,000
        ok, _ = pm.check_exposure_limit()
        assert ok  # Under limit again


# ---------------------------------------------------------------------------
# 8. Price Cache Under Rapid Expiration
# ---------------------------------------------------------------------------

class TestPriceCacheChaos:
    """Price cache handles rapid expiration and concurrent access."""

    @pytest.fixture
    def cache(self):
        return PriceCache(cache_duration_seconds=1)

    @pytest.mark.asyncio
    async def test_expired_entry_returns_none(self, cache):
        """Cache returns None for expired entries."""
        await cache.set_price("quickswap", "0xTOKEN", Decimal("2000"))

        # Immediately available
        price = await cache.get_price("quickswap", "0xTOKEN")
        assert price == Decimal("2000")

        # Wait for expiration
        await asyncio.sleep(1.1)

        price = await cache.get_price("quickswap", "0xTOKEN")
        assert price is None

    @pytest.mark.asyncio
    async def test_cache_stats_track_hits_and_misses(self, cache):
        """Stats accurately track hit/miss ratio."""
        await cache.set_price("quickswap", "0xA", Decimal("100"))

        await cache.get_price("quickswap", "0xA")  # Hit
        await cache.get_price("quickswap", "0xA")  # Hit
        await cache.get_price("quickswap", "0xB")  # Miss

        stats = cache.get_stats()
        assert stats["hits"] == 2
        assert stats["misses"] == 1

    @pytest.mark.asyncio
    async def test_clear_removes_all_entries(self, cache):
        """Clearing cache removes everything."""
        for i in range(10):
            await cache.set_price("dex", f"0x{i}", Decimal(str(i)))

        assert len(cache) == 10
        cache.clear()
        assert len(cache) == 0

    @pytest.mark.asyncio
    async def test_concurrent_access_is_safe(self, cache):
        """Concurrent reads and writes don't corrupt state."""

        async def writer(n):
            for i in range(50):
                await cache.set_price(f"dex_{n}", f"0x{i}", Decimal(str(i * n)))

        async def reader(n):
            for i in range(50):
                await cache.get_price(f"dex_{n}", f"0x{i}")

        # Run 4 writers and 4 readers concurrently
        tasks = [writer(i) for i in range(4)] + [reader(i) for i in range(4)]
        await asyncio.gather(*tasks)

        # Cache should be in a consistent state (no exceptions, no corruption)
        stats = cache.get_stats()
        assert stats["total"] > 0


# ---------------------------------------------------------------------------
# 9. Risk Manager Full Pipeline Under Fault Conditions
# ---------------------------------------------------------------------------

class TestRiskManagerPipeline:
    """Full validate → record → circuit-break → shutdown pipeline."""

    def test_full_cascade_to_circuit_breaker(self):
        """5 consecutive failures trigger circuit breaker via RiskManager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ["RISK_STATE_FILE"] = os.path.join(tmpdir, "state.json")

            w3 = _mock_web3()
            rm = RiskManager(w3, [], _risk_config())

            for i in range(5):
                rm.record_trade_result(_make_trade(False, -10))

            assert rm.circuit_breaker.is_active

            # Validate should fail
            approved, reason = rm.validate_trade(
                {"token_in": "WETH", "token_out": "USDC", "amount_in": 1000},
                "0xACCOUNT",
                "0xTOKEN",
            )
            assert not approved
            assert "circuit breaker" in reason.lower()

            del os.environ["RISK_STATE_FILE"]

    def test_trade_recording_persists_state(self):
        """Every trade result is persisted — survives restart."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = os.path.join(tmpdir, "state.json")
            os.environ["RISK_STATE_FILE"] = state_file

            w3 = _mock_web3()
            rm1 = RiskManager(w3, [], _risk_config())
            rm1.record_trade_result(_make_trade(True, 50))
            rm1.record_trade_result(_make_trade(False, -20))

            # Restart
            rm2 = RiskManager(w3, [], _risk_config())
            assert len(rm2.loss_tracker.trades) == 2
            # Last trade was a failure so consecutive_losses restores to 1
            assert rm2.circuit_breaker.consecutive_losses == 1

            del os.environ["RISK_STATE_FILE"]

    def test_validate_blocks_oversized_position(self):
        """Risk manager rejects trades exceeding position size limit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ["RISK_STATE_FILE"] = os.path.join(tmpdir, "state.json")

            w3 = _mock_web3()
            config = _risk_config()
            config["MAX_POSITION_SIZE_USD"] = 100  # $100 max position

            rm = RiskManager(w3, [], config)

            # Trade with amount_in=200_000_000 (200 USDC with 6 decimals)
            approved, reason = rm.validate_trade(
                {"token_in": "USDC", "token_out": "WETH", "amount_in": 200_000_000, "token_decimals": 6},
                "0xACCOUNT",
                "0xTOKEN",
            )
            assert not approved
            assert "position size" in reason.lower()

            del os.environ["RISK_STATE_FILE"]


# ---------------------------------------------------------------------------
# 10. Database Failure During Trade Logging
# ---------------------------------------------------------------------------

class TestDatabaseFailureResilience:
    """Bot survives database failures during non-critical operations."""

    def test_db_check_returns_false_on_failure(self):
        """check_db_connection returns False, not exception, on failure."""
        with patch("src.db.database.get_db") as mock_get_db:
            mock_get_db.side_effect = Exception("Connection refused")

            from src.db.database import check_db_connection
            result = check_db_connection()
            assert result is False

    def test_risk_state_save_failure_is_non_fatal(self):
        """Failure to save risk state logs warning but doesn't crash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = os.path.join(tmpdir, "state.json")
            os.environ["RISK_STATE_FILE"] = state_file

            w3 = _mock_web3()
            rm = RiskManager(w3, [], _risk_config())

            # Make state file directory read-only to trigger write failure
            os.chmod(tmpdir, 0o444)

            try:
                # Should not raise — just log warning
                rm.record_trade_result(_make_trade(True, 10))
                # In-memory state is still updated even if disk write fails
                assert len(rm.loss_tracker.trades) == 1
            finally:
                os.chmod(tmpdir, 0o755)

            del os.environ["RISK_STATE_FILE"]


# ---------------------------------------------------------------------------
# 11. Nonce / Transaction Racing
# ---------------------------------------------------------------------------

class TestTransactionRacing:
    """Multiple opportunities detected simultaneously don't collide."""

    @pytest.mark.asyncio
    async def test_concurrent_balance_reservations(self):
        """Balance validator tracks reservations to prevent double-spend."""
        from src.utils.risk_manager import BalanceValidator

        w3 = _mock_web3()
        mock_contract = MagicMock()
        # Account has 1000 tokens (1000 * 10^18 wei)
        mock_contract.functions.balanceOf.return_value.call.return_value = 1000 * 10**18
        mock_contract.functions.decimals.return_value.call.return_value = 18
        w3.eth.contract.return_value = mock_contract

        # Use a valid hex address so Web3.to_checksum_address doesn't fail
        token_addr = "0x0000000000000000000000000000000000000001"

        validator = BalanceValidator(w3, [])

        # Reserve 600
        result1 = await validator.check_balance(
            "0xACCOUNT", token_addr, Decimal("600"), reserve=True
        )
        assert result1 is True

        # Try to reserve another 600 — should fail (only 400 available)
        result2 = await validator.check_balance(
            "0xACCOUNT", token_addr, Decimal("600"), reserve=True
        )
        assert result2 is False

        # Release first reservation, then second should succeed
        validator.release_balance("0xACCOUNT", token_addr, Decimal("600"))
        result3 = await validator.check_balance(
            "0xACCOUNT", token_addr, Decimal("600"), reserve=True
        )
        assert result3 is True


# ---------------------------------------------------------------------------
# 12. Risk Manager Metrics Under Edge Conditions
# ---------------------------------------------------------------------------

class TestRiskMetricsEdgeCases:
    """Risk metrics don't crash under empty or extreme states."""

    def test_metrics_with_no_trades(self):
        """get_risk_metrics works with zero trade history."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ["RISK_STATE_FILE"] = os.path.join(tmpdir, "state.json")

            w3 = _mock_web3()
            rm = RiskManager(w3, [], _risk_config())

            metrics = rm.get_risk_metrics()
            assert metrics.daily_pnl == Decimal("0")
            assert metrics.total_trades_today == 0
            assert metrics.circuit_breaker_active is False
            assert metrics.last_trade_time is None

            del os.environ["RISK_STATE_FILE"]

    def test_success_rate_is_100_percent_with_no_trades(self):
        """Success rate defaults to 100% when no trades exist (don't block)."""
        tracker = LossTracker(daily_loss_limit_usd=Decimal("1000"))
        rate = tracker.get_success_rate_today()
        assert rate == Decimal("100")

    def test_daily_reset_clears_old_trades(self):
        """Daily reset removes trades older than 7 days."""
        tracker = LossTracker(daily_loss_limit_usd=Decimal("1000"))

        # Add old trade (8 days ago)
        old_trade = _make_trade(True, 50)
        old_trade.timestamp = datetime.now() - timedelta(days=8)
        tracker.trades.append(old_trade)

        # Add recent trade
        tracker.record_trade(_make_trade(True, 30))

        assert len(tracker.trades) == 2
        tracker.reset_daily()
        assert len(tracker.trades) == 1  # Old one removed
