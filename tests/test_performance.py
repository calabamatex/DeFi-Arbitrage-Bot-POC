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


class TestMulticallBatching:
    """Test that Multicall3 batching reduces RPC call count."""

    def test_batched_fewer_rpc_calls(self):
        """
        Verify calculate_arbitrage_batched() makes fewer RPC calls than
        sequential calculate_arbitrage().

        Sequential: 8 individual RPC calls (3 V3 fees + 1 V2 per direction)
        Batched: 2 Multicall3 aggregate3() calls
        """
        from src.opportunity_detector import OpportunityDetector
        from src.utils.multicall import Multicall

        # Create detector with mocked web3
        mock_web3 = Mock()
        mock_web3.to_checksum_address = lambda x: x
        mock_web3.eth.chain_id = 137
        mock_web3.eth.gas_price = 30 * 10**9
        mock_web3.to_wei = lambda val, unit: val * 10**9 if unit == "gwei" else val

        # Track RPC calls
        rpc_call_count = {"sequential": 0, "batched": 0}

        # Mock V3 quoter — each .call() is one RPC
        mock_v3_result = [1000 * 10**6, 0, 0, 200000]  # amountOut, sqrtPrice, ticks, gas
        mock_v3_fn = Mock()
        mock_v3_fn.call = Mock(return_value=mock_v3_result)
        mock_v3_contract = Mock()
        mock_v3_contract.functions.quoteExactInputSingle = Mock(return_value=mock_v3_fn)

        # Mock V2 router
        mock_v2_result = [500 * 10**6, 1050 * 10**6]  # [amountIn, amountOut]
        mock_v2_fn = Mock()
        mock_v2_fn.call = Mock(return_value=mock_v2_result)
        mock_v2_contract = Mock()
        mock_v2_contract.functions.getAmountsOut = Mock(return_value=mock_v2_fn)

        # Count sequential calls
        original_v3_call = mock_v3_fn.call
        original_v2_call = mock_v2_fn.call

        def count_v3(*args, **kwargs):
            rpc_call_count["sequential"] += 1
            return original_v3_call(*args, **kwargs)

        def count_v2(*args, **kwargs):
            rpc_call_count["sequential"] += 1
            return original_v2_call(*args, **kwargs)

        mock_v3_fn.call = count_v3
        mock_v2_fn.call = count_v2

        # Patch detector construction to use mocks
        with patch.object(OpportunityDetector, "__init__", lambda self, **kw: None):
            detector = OpportunityDetector.__new__(OpportunityDetector)
            detector.web3 = mock_web3
            detector.v3_quoter = "0xQuoter"
            detector.v2_router = "0xRouter"
            detector.v3_quoter_contract = mock_v3_contract
            detector.v2_router_contract = mock_v2_contract
            detector.curve_adapter_contract = None
            detector.V3_FEE_LOW = 500
            detector.V3_FEE_MEDIUM = 3000
            detector.V3_FEE_HIGH = 10000
            detector.FLASH_LOAN_FEE_BPS = 5
            detector.multicall = Mock(spec=Multicall)
            detector.multicall.is_available.return_value = False  # Force sequential

            # Run sequential
            token_a = "0xTokenA"
            token_b = "0xTokenB"
            detector.calculate_arbitrage(token_a, token_b, 1000 * 10**6)
            sequential_calls = rpc_call_count["sequential"]

        # Now test batched path — Multicall3 should make exactly 2 aggregate3 calls
        mock_multicall = Mock(spec=Multicall)
        mock_multicall.is_available.return_value = True

        # Mock aggregate3 to return successful results
        # Batch 1: 4 calls (3 V3 + 1 V2)
        batch1_results = [
            (True, (1000 * 10**6).to_bytes(32, "big") + b"\x00" * 96),  # V3 fee 500
            (True, (1000 * 10**6).to_bytes(32, "big") + b"\x00" * 96),  # V3 fee 3000
            (True, (1000 * 10**6).to_bytes(32, "big") + b"\x00" * 96),  # V3 fee 10000
            (True, b"\x00" * 32 + (2).to_bytes(32, "big") + (500 * 10**6).to_bytes(32, "big") + (1050 * 10**6).to_bytes(32, "big")),  # V2
        ]
        # Batch 2: dependent calls
        batch2_results = [
            (True, b"\x00" * 32 + (2).to_bytes(32, "big") + (1000 * 10**6).to_bytes(32, "big") + (1005 * 10**6).to_bytes(32, "big")),  # V2 B->A
            (True, (1005 * 10**6).to_bytes(32, "big") + b"\x00" * 96),  # V3 B->A fee 500
            (True, (1005 * 10**6).to_bytes(32, "big") + b"\x00" * 96),  # V3 B->A fee 3000
            (True, (1005 * 10**6).to_bytes(32, "big") + b"\x00" * 96),  # V3 B->A fee 10000
        ]

        mock_multicall.aggregate3.side_effect = [batch1_results, batch2_results]

        with patch.object(OpportunityDetector, "__init__", lambda self, **kw: None):
            detector2 = OpportunityDetector.__new__(OpportunityDetector)
            detector2.web3 = mock_web3
            detector2.v3_quoter = "0xQuoter"
            detector2.v2_router = "0xRouter"
            detector2.v3_quoter_contract = mock_v3_contract
            detector2.v2_router_contract = mock_v2_contract
            detector2.curve_adapter_contract = None
            detector2.V3_FEE_LOW = 500
            detector2.V3_FEE_MEDIUM = 3000
            detector2.V3_FEE_HIGH = 10000
            detector2.FLASH_LOAN_FEE_BPS = 5
            detector2.multicall = mock_multicall

            detector2.calculate_arbitrage_batched(token_a, token_b, 1000 * 10**6)
            batched_calls = mock_multicall.aggregate3.call_count

        print(f"\nRPC call comparison:")
        print(f"  Sequential: {sequential_calls} individual RPC calls")
        print(f"  Batched: {batched_calls} Multicall3 aggregate3() calls")
        print(f"  Reduction: {sequential_calls}x -> {batched_calls}x ({sequential_calls / max(batched_calls, 1):.0f}x fewer)")

        # Batched should use significantly fewer calls
        assert batched_calls <= 2, f"Expected at most 2 Multicall3 calls, got {batched_calls}"
        assert sequential_calls >= 6, f"Expected at least 6 sequential calls, got {sequential_calls}"

