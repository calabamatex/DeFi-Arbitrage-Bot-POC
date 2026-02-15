"""Tests for PriceCache."""

import asyncio
import pytest
from decimal import Decimal
from datetime import timedelta

from src.utils.price_cache import PriceCache


@pytest.fixture
def cache():
    return PriceCache(cache_duration_seconds=1)


@pytest.mark.asyncio
async def test_set_and_get_price(cache):
    await cache.set_price("uniswap_v3", "0xUSDC", Decimal("1.001"))
    price = await cache.get_price("uniswap_v3", "0xUSDC")
    assert price == Decimal("1.001")


@pytest.mark.asyncio
async def test_get_missing_price_returns_none(cache):
    price = await cache.get_price("uniswap_v3", "0xNonExistent")
    assert price is None


@pytest.mark.asyncio
async def test_ttl_expiration(cache):
    # Use very short TTL
    short_cache = PriceCache(cache_duration_seconds=0)
    await short_cache.set_price("uniswap_v3", "0xUSDC", Decimal("1.0"))

    # Small delay to ensure expiry
    await asyncio.sleep(0.05)

    price = await short_cache.get_price("uniswap_v3", "0xUSDC")
    assert price is None


@pytest.mark.asyncio
async def test_overwrite_price(cache):
    await cache.set_price("uniswap_v3", "0xUSDC", Decimal("1.0"))
    await cache.set_price("uniswap_v3", "0xUSDC", Decimal("1.05"))
    price = await cache.get_price("uniswap_v3", "0xUSDC")
    assert price == Decimal("1.05")


@pytest.mark.asyncio
async def test_different_dex_keys(cache):
    await cache.set_price("uniswap_v3", "0xUSDC", Decimal("1.001"))
    await cache.set_price("sushiswap", "0xUSDC", Decimal("0.999"))

    v3_price = await cache.get_price("uniswap_v3", "0xUSDC")
    sushi_price = await cache.get_price("sushiswap", "0xUSDC")

    assert v3_price == Decimal("1.001")
    assert sushi_price == Decimal("0.999")


@pytest.mark.asyncio
async def test_clear(cache):
    await cache.set_price("uniswap_v3", "0xUSDC", Decimal("1.0"))
    await cache.set_price("sushiswap", "0xWETH", Decimal("3000.0"))
    assert len(cache) == 2

    cache.clear()
    assert len(cache) == 0

    price = await cache.get_price("uniswap_v3", "0xUSDC")
    assert price is None


@pytest.mark.asyncio
async def test_stats_tracking(cache):
    # Start with clean stats
    stats = cache.get_stats()
    assert stats["hits"] == 0
    assert stats["misses"] == 0

    # Miss
    await cache.get_price("uniswap_v3", "0xUSDC")
    stats = cache.get_stats()
    assert stats["misses"] == 1
    assert stats["hits"] == 0

    # Set + hit
    await cache.set_price("uniswap_v3", "0xUSDC", Decimal("1.0"))
    await cache.get_price("uniswap_v3", "0xUSDC")
    stats = cache.get_stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["cached_items"] == 1

    # Hit rate
    assert stats["hit_rate_percent"] == 50


@pytest.mark.asyncio
async def test_len(cache):
    assert len(cache) == 0
    await cache.set_price("uniswap_v3", "0xUSDC", Decimal("1.0"))
    assert len(cache) == 1
    await cache.set_price("sushiswap", "0xWETH", Decimal("3000"))
    assert len(cache) == 2


@pytest.mark.asyncio
async def test_concurrent_access():
    """Verify lock prevents data races."""
    cache = PriceCache(cache_duration_seconds=5)

    async def writer(i):
        await cache.set_price("dex", f"0xToken{i}", Decimal(str(i)))

    async def reader(i):
        return await cache.get_price("dex", f"0xToken{i}")

    # Write 50 entries concurrently
    await asyncio.gather(*[writer(i) for i in range(50)])
    assert len(cache) == 50

    # Read them all back
    results = await asyncio.gather(*[reader(i) for i in range(50)])
    for i, result in enumerate(results):
        assert result == Decimal(str(i))
