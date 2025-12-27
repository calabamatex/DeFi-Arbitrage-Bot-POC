"""Performance tests."""

import pytest
import time
import asyncio
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch

from src.utils.price_cache import PriceCache
from src.utils.gas_optimizer import GasOptimizer, get_unlimited_approval_amount
from src.utils.performance_monitor import PerformanceMonitor
from src.utils.multicall import Multicall


class TestPriceCache:
    """Test price caching functionality."""

    @pytest.mark.asyncio
    async def test_cache_initialization(self):
        """Test cache initializes with correct settings."""
        cache = PriceCache(cache_duration_seconds=5)

        assert cache.cache_duration.total_seconds() == 5
        assert len(cache) == 0
        assert cache.hits == 0
        assert cache.misses == 0

    @pytest.mark.asyncio
    async def test_cache_set_and_get(self):
        """Test setting and getting cached prices."""
        cache = PriceCache(cache_duration_seconds=10)

        # Set a price
        await cache.set_price("uniswap", "0xabc123", Decimal("100.5"))

        # Get it back
        price = await cache.get_price("uniswap", "0xabc123")

        assert price == Decimal("100.5")
        assert cache.hits == 1
        assert cache.misses == 0

    @pytest.mark.asyncio
    async def test_cache_miss(self):
        """Test cache miss for non-existent price."""
        cache = PriceCache(cache_duration_seconds=5)

        price = await cache.get_price("uniswap", "0xnonexistent")

        assert price is None
        assert cache.misses == 1
        assert cache.hits == 0

    @pytest.mark.asyncio
    async def test_cache_expiration(self):
        """Test cached prices expire after duration."""
        cache = PriceCache(cache_duration_seconds=1)

        # Set a price
        await cache.set_price("uniswap", "0xabc", Decimal("100"))

        # Immediately get it (should hit)
        price1 = await cache.get_price("uniswap", "0xabc")
        assert price1 == Decimal("100")
        assert cache.hits == 1

        # Wait for expiration
        await asyncio.sleep(1.5)

        # Try to get it again (should miss - expired)
        price2 = await cache.get_price("uniswap", "0xabc")
        assert price2 is None
        assert cache.misses == 1

    @pytest.mark.asyncio
    async def test_cache_case_insensitive(self):
        """Test cache handles address case insensitively."""
        cache = PriceCache()

        await cache.set_price("uniswap", "0xABC123", Decimal("100"))

        # Should find with lowercase
        price = await cache.get_price("uniswap", "0xabc123")
        assert price == Decimal("100")

    @pytest.mark.asyncio
    async def test_cache_stats(self):
        """Test cache statistics tracking."""
        cache = PriceCache()

        # Set some prices
        await cache.set_price("dex1", "0xa", Decimal("1"))
        await cache.set_price("dex2", "0xb", Decimal("2"))

        # Generate hits and misses
        await cache.get_price("dex1", "0xa")  # hit
        await cache.get_price("dex1", "0xa")  # hit
        await cache.get_price("dex1", "0xc")  # miss

        stats = cache.get_stats()

        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["total"] == 3
        assert stats["hit_rate_percent"] == pytest.approx(66.67, rel=0.1)
        assert stats["cached_items"] == 2

    def test_cache_clear(self):
        """Test clearing cache."""
        cache = PriceCache()

        asyncio.run(cache.set_price("dex", "0x1", Decimal("100")))
        assert len(cache) == 1

        cache.clear()
        assert len(cache) == 0


class TestGasOptimizer:
    """Test gas optimization functionality."""

    def test_gas_optimizer_initialization(self):
        """Test gas optimizer initializes correctly."""
        mock_web3 = Mock()
        optimizer = GasOptimizer(mock_web3)

        assert optimizer.web3 == mock_web3

    def test_get_optimal_gas_price_normal(self):
        """Test normal urgency gas price."""
        mock_web3 = Mock()
        mock_web3.eth.gas_price = 30000000000  # 30 gwei

        optimizer = GasOptimizer(mock_web3)
        gas_price = optimizer.get_optimal_gas_price("normal")

        assert gas_price == 30000000000

    def test_get_optimal_gas_price_low(self):
        """Test low urgency gas price."""
        mock_web3 = Mock()
        mock_web3.eth.gas_price = 30000000000

        optimizer = GasOptimizer(mock_web3)
        gas_price = optimizer.get_optimal_gas_price("low")

        assert gas_price == int(30000000000 * 0.8)

    def test_get_optimal_gas_price_high(self):
        """Test high urgency gas price."""
        mock_web3 = Mock()
        mock_web3.eth.gas_price = 30000000000

        optimizer = GasOptimizer(mock_web3)
        gas_price = optimizer.get_optimal_gas_price("high")

        assert gas_price == int(30000000000 * 1.2)

    def test_use_eip1559(self):
        """Test EIP-1559 gas parameters."""
        mock_web3 = Mock()
        mock_block = {"baseFeePerGas": 30000000000}
        mock_web3.eth.get_block.return_value = mock_block

        optimizer = GasOptimizer(mock_web3)
        params = optimizer.use_eip1559("normal")

        assert "maxFeePerGas" in params
        assert "maxPriorityFeePerGas" in params
        assert params["maxPriorityFeePerGas"] == 2000000000  # 2 gwei

    def test_estimate_gas_cost(self):
        """Test gas cost estimation."""
        mock_web3 = Mock()
        mock_web3.eth.gas_price = 30000000000  # 30 gwei

        optimizer = GasOptimizer(mock_web3)
        cost = optimizer.estimate_gas_cost(gas_limit=200000, urgency="normal")

        # 200000 * 30 gwei = 0.006 ETH
        expected = Decimal("0.006")
        assert cost == expected

    def test_is_profitable_after_gas(self):
        """Test profitability check after gas costs."""
        mock_web3 = Mock()
        mock_web3.eth.gas_price = 30000000000

        optimizer = GasOptimizer(mock_web3)

        # Profitable case
        profitable = optimizer.is_profitable_after_gas(
            expected_profit=Decimal("0.01"), gas_limit=200000, urgency="normal"
        )
        assert profitable is True

        # Not profitable case
        not_profitable = optimizer.is_profitable_after_gas(
            expected_profit=Decimal("0.001"), gas_limit=200000, urgency="normal"
        )
        assert not_profitable is False

    def test_get_gas_multiplier(self):
        """Test gas multiplier retrieval."""
        mock_web3 = Mock()
        optimizer = GasOptimizer(mock_web3)

        assert optimizer.get_gas_multiplier("low") == 0.8
        assert optimizer.get_gas_multiplier("normal") == 1.0
        assert optimizer.get_gas_multiplier("high") == 1.2
        assert optimizer.get_gas_multiplier("urgent") == 1.5

    def test_unlimited_approval_amount(self):
        """Test unlimited approval constant."""
        amount = get_unlimited_approval_amount()

        assert amount == 2**256 - 1
        assert amount > 0


class TestPerformanceMonitor:
    """Test performance monitoring functionality."""

    def test_performance_monitor_initialization(self):
        """Test monitor initializes correctly."""
        monitor = PerformanceMonitor()

        assert len(monitor.detection_times) == 0
        assert len(monitor.execution_times) == 0
        assert monitor.rpc_call_count == 0

    def test_record_detection_time(self):
        """Test recording detection times."""
        monitor = PerformanceMonitor()

        monitor.record_detection_time(1.5)
        monitor.record_detection_time(1.8)

        assert len(monitor.detection_times) == 2
        assert monitor.detection_times == [1.5, 1.8]

    def test_record_detection_time_limit(self):
        """Test detection times list is limited to 100."""
        monitor = PerformanceMonitor()

        # Record 150 times
        for i in range(150):
            monitor.record_detection_time(float(i))

        # Should only keep last 100
        assert len(monitor.detection_times) == 100
        assert monitor.detection_times[0] == 50.0

    def test_record_execution_time(self):
        """Test recording execution times."""
        monitor = PerformanceMonitor()

        monitor.record_execution_time(3.5)
        monitor.record_execution_time(4.2)

        assert len(monitor.execution_times) == 2

    def test_record_rpc_call(self):
        """Test recording RPC calls."""
        monitor = PerformanceMonitor()

        monitor.record_rpc_call()
        monitor.record_rpc_call()
        monitor.record_rpc_call()

        assert monitor.rpc_call_count == 3

    def test_get_metrics(self):
        """Test getting performance metrics."""
        monitor = PerformanceMonitor()

        # Record some data
        monitor.record_detection_time(1.0)
        monitor.record_detection_time(2.0)
        monitor.record_execution_time(3.0)
        monitor.record_execution_time(4.0)

        metrics = monitor.get_metrics()

        assert metrics.avg_opportunity_detection_time == Decimal("1.5")
        assert metrics.avg_trade_execution_time == Decimal("3.5")
        assert metrics.total_detections == 2
        assert metrics.total_executions == 2

    def test_check_performance_targets(self):
        """Test performance target checking."""
        monitor = PerformanceMonitor()

        # Record good performance
        monitor.record_detection_time(1.0)
        monitor.record_execution_time(3.0)

        targets = monitor.check_performance_targets()

        assert targets["detection_speed"] is True
        assert targets["execution_speed"] is True

    def test_check_performance_targets_missed(self):
        """Test detecting missed performance targets."""
        monitor = PerformanceMonitor()

        # Record poor performance
        monitor.record_detection_time(5.0)  # > 2s target
        monitor.record_execution_time(10.0)  # > 5s target

        targets = monitor.check_performance_targets()

        assert targets["detection_speed"] is False
        assert targets["execution_speed"] is False

    def test_get_uptime(self):
        """Test uptime calculation."""
        monitor = PerformanceMonitor()

        time.sleep(0.1)

        uptime = monitor.get_uptime()
        assert uptime >= 0.1

    def test_reset_statistics(self):
        """Test resetting statistics."""
        monitor = PerformanceMonitor()

        # Record some data
        monitor.record_detection_time(1.0)
        monitor.record_execution_time(2.0)
        monitor.record_rpc_call()

        # Reset
        monitor.reset_statistics()

        assert len(monitor.detection_times) == 0
        assert len(monitor.execution_times) == 0
        assert monitor.rpc_call_count == 0


class TestMulticall:
    """Test multicall functionality."""

    def test_multicall_initialization(self):
        """Test multicall initializes correctly."""
        mock_web3 = Mock()
        mock_web3.eth.contract.return_value = Mock()

        multicall = Multicall(mock_web3)

        assert multicall.web3 == mock_web3
        assert multicall.contract is not None

    def test_multicall_is_available(self):
        """Test checking if multicall is available."""
        mock_web3 = Mock()
        mock_web3.eth.contract.return_value = Mock()

        multicall = Multicall(mock_web3)

        assert multicall.is_available() is True

    @pytest.mark.asyncio
    async def test_multicall_aggregate(self):
        """Test multicall aggregate function."""
        mock_web3 = Mock()
        mock_contract = Mock()
        mock_web3.eth.contract.return_value = mock_contract

        # Mock the aggregate function
        mock_aggregate = Mock()
        mock_aggregate.call.return_value = (12345, [b"result1", b"result2"])
        mock_contract.functions.aggregate.return_value = mock_aggregate

        multicall = Multicall(mock_web3)

        calls = [("0xabc", b"data1"), ("0xdef", b"data2")]
        block_number, results = await multicall.aggregate(calls)

        assert block_number == 12345
        assert len(results) == 2
        assert results[0] == b"result1"


# Performance benchmarks (run manually)
@pytest.mark.slow
@pytest.mark.asyncio
async def test_cache_performance_benefit():
    """Benchmark cache performance benefit."""
    cache = PriceCache(cache_duration_seconds=10)

    # Simulate fetching without cache
    start = time.time()
    for _ in range(100):
        await asyncio.sleep(0.01)  # Simulate RPC call
    no_cache_time = time.time() - start

    # Simulate fetching with cache
    await cache.set_price("dex", "0xtoken", Decimal("100"))

    start = time.time()
    for _ in range(100):
        await cache.get_price("dex", "0xtoken")  # Cached, no RPC
    cached_time = time.time() - start

    # Cache should be significantly faster
    assert cached_time < no_cache_time / 10

    print(f"\nCache performance:")
    print(f"  Without cache: {no_cache_time:.3f}s")
    print(f"  With cache: {cached_time:.3f}s")
    print(f"  Speedup: {no_cache_time/cached_time:.1f}x")
