"""Price caching to reduce RPC calls."""

from decimal import Decimal
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
import asyncio
import logging

logger = logging.getLogger(__name__)


class PriceCache:
    """
    Caches token prices to reduce RPC calls.

    Prices are cached for a short duration (1-5 seconds) since
    crypto prices change frequently.
    """

    def __init__(self, cache_duration_seconds: int = 3):
        """
        Initialize price cache.

        Args:
            cache_duration_seconds: How long to cache prices
        """
        self.cache_duration = timedelta(seconds=cache_duration_seconds)
        self.cache: Dict[Tuple[str, str], Tuple[Decimal, datetime]] = (
            {}
        )  # {(dex, token): (price, timestamp)}
        self._lock = asyncio.Lock()
        self.hits = 0
        self.misses = 0

        logger.info(
            f"PriceCache initialized with {cache_duration_seconds}s duration"
        )

    async def get_price(
        self, dex_name: str, token_address: str
    ) -> Optional[Decimal]:
        """
        Get cached price if valid.

        Args:
            dex_name: DEX name
            token_address: Token address

        Returns:
            Cached price or None if not cached/expired
        """
        async with self._lock:
            key = (dex_name, token_address.lower())

            if key in self.cache:
                price, timestamp = self.cache[key]

                # Check if still valid
                if datetime.now() - timestamp < self.cache_duration:
                    self.hits += 1
                    logger.debug(
                        f"Cache HIT: {dex_name} {token_address[:10]}... = {price}"
                    )
                    return price
                else:
                    # Expired, remove
                    del self.cache[key]
                    logger.debug(
                        f"Cache EXPIRED: {dex_name} {token_address[:10]}..."
                    )

            self.misses += 1
            return None

    async def set_price(
        self, dex_name: str, token_address: str, price: Decimal
    ):
        """
        Cache a price.

        Args:
            dex_name: DEX name
            token_address: Token address
            price: Price to cache
        """
        async with self._lock:
            key = (dex_name, token_address.lower())
            self.cache[key] = (price, datetime.now())
            logger.debug(
                f"Cache SET: {dex_name} {token_address[:10]}... = {price}"
            )

    def clear(self):
        """Clear all cached prices."""
        self.cache.clear()
        logger.info("Price cache cleared")

    def get_stats(self) -> Dict[str, int]:
        """
        Get cache statistics.

        Returns:
            Dict with hits, misses, and hit rate
        """
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0

        return {
            "hits": self.hits,
            "misses": self.misses,
            "total": total,
            "hit_rate_percent": round(hit_rate, 2),
            "cached_items": len(self.cache),
        }

    def __len__(self) -> int:
        """Return number of cached items."""
        return len(self.cache)
