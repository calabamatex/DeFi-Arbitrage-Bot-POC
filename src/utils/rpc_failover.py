"""Multi-RPC provider failover with health checking and automatic recovery.

Provides resilient Web3 connectivity by managing multiple RPC endpoints per
chain. When the active provider fails, the manager transparently switches to
the next healthy provider. Unhealthy providers are periodically re-checked.

Usage:
    manager = RpcFailoverManager.from_chain("polygon")
    web3 = manager.get_web3()
"""

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Dict, List

from web3 import Web3

logger = logging.getLogger(__name__)

MAX_CONSECUTIVE_ERRORS = 3
HEALTH_CHECK_INTERVAL = 30   # seconds between routine health checks
RECOVERY_CHECK_INTERVAL = 60  # seconds between re-checking unhealthy providers
REQUEST_TIMEOUT = 10          # seconds per RPC request

# Chain key -> (env var for comma-separated URLs, fallback single-URL env var)
_CHAIN_ENV_MAP: Dict[str, tuple] = {
    "polygon":          ("POLYGON_RPC_URLS",          "POLYGON_RPC_URL"),
    "arbitrum":         ("ARBITRUM_RPC_URLS",         "ARBITRUM_RPC_URL"),
    "optimism":         ("OPTIMISM_RPC_URLS",         "OPTIMISM_RPC_URL"),
    "base":             ("BASE_RPC_URLS",             "BASE_RPC_URL"),
    "polygon_amoy":     ("POLYGON_AMOY_RPC_URLS",    "POLYGON_AMOY_RPC_URL"),
    "arbitrum_sepolia": ("ARBITRUM_SEPOLIA_RPC_URLS", "ARBITRUM_SEPOLIA_RPC_URL"),
}


@dataclass
class RpcProvider:
    """State for a single RPC endpoint."""

    url: str
    name: str
    priority: int
    is_healthy: bool = True
    last_check: float = 0.0
    avg_latency_ms: float = 0.0
    error_count: int = 0
    _latency_samples: List[float] = field(default_factory=list, repr=False)

    def record_success(self, latency_ms: float) -> None:
        self.error_count = 0
        self.is_healthy = True
        self.last_check = time.monotonic()
        self._latency_samples.append(latency_ms)
        if len(self._latency_samples) > 10:
            self._latency_samples = self._latency_samples[-10:]
        self.avg_latency_ms = sum(self._latency_samples) / len(self._latency_samples)

    def record_failure(self) -> None:
        self.error_count += 1
        self.last_check = time.monotonic()
        if self.error_count >= MAX_CONSECUTIVE_ERRORS:
            self.is_healthy = False
            logger.warning(
                "Provider %s marked unhealthy after %d consecutive errors",
                self.name, self.error_count,
            )


class RpcFailoverManager:
    """Manages multiple RPC providers for a single chain with automatic failover."""

    def __init__(self, urls: List[str], chain_name: str = "unknown") -> None:
        if not urls:
            raise ValueError(f"At least one RPC URL is required for chain '{chain_name}'")

        self.chain_name = chain_name
        self.providers: List[RpcProvider] = []
        for idx, url in enumerate(urls):
            url = url.strip()
            if not url:
                continue
            self.providers.append(RpcProvider(
                url=url, name=f"{chain_name}-rpc-{idx}", priority=idx,
            ))

        if not self.providers:
            raise ValueError(f"No valid RPC URLs provided for chain '{chain_name}'")

        self._active_index: int = 0
        self._web3_cache: Dict[int, Web3] = {}
        self._last_health_check: float = 0.0
        self._last_recovery_check: float = 0.0
        logger.info(
            "RpcFailoverManager initialized for %s with %d provider(s)",
            chain_name, len(self.providers),
        )

    @classmethod
    def from_chain(cls, chain_key: str) -> "RpcFailoverManager":
        """Build a manager from environment variables for the given chain key."""
        env_multi, env_single = _CHAIN_ENV_MAP.get(
            chain_key, (f"{chain_key.upper()}_RPC_URLS", f"{chain_key.upper()}_RPC_URL"),
        )
        raw = os.getenv(env_multi, "")
        if raw.strip():
            urls = [u for u in raw.split(",") if u.strip()]
        else:
            single = os.getenv(env_single, "")
            urls = [single] if single.strip() else []
        return cls(urls=urls, chain_name=chain_key)

    def get_web3(self) -> Web3:
        """Return a Web3 instance connected to the best healthy provider.

        Triggers periodic health checks and automatic failover.
        """
        now = time.monotonic()
        if now - self._last_health_check >= HEALTH_CHECK_INTERVAL:
            self._run_health_checks()
        if now - self._last_recovery_check >= RECOVERY_CHECK_INTERVAL:
            self._try_recover_providers()
        provider = self._select_provider()
        return self._get_or_create_web3(provider)

    def health_check(self) -> List[Dict]:
        """Run health checks on all providers and return status summaries."""
        self._run_health_checks()
        return [
            {
                "name": p.name,
                "url": p.url[:40] + "..." if len(p.url) > 40 else p.url,
                "healthy": p.is_healthy,
                "latency_ms": round(p.avg_latency_ms, 1),
                "error_count": p.error_count,
            }
            for p in self.providers
        ]

    def _get_or_create_web3(self, provider: RpcProvider) -> Web3:
        idx = self.providers.index(provider)
        if idx not in self._web3_cache:
            self._web3_cache[idx] = Web3(
                Web3.HTTPProvider(provider.url, request_kwargs={"timeout": REQUEST_TIMEOUT})
            )
        return self._web3_cache[idx]

    def _ping_provider(self, provider: RpcProvider) -> bool:
        """Ping a provider by requesting the block number."""
        w3 = self._get_or_create_web3(provider)
        start = time.monotonic()
        try:
            w3.eth.block_number
            provider.record_success((time.monotonic() - start) * 1000)
            return True
        except Exception as exc:
            provider.record_failure()
            logger.debug("Ping failed for %s: %s", provider.name, exc)
            return False

    def _run_health_checks(self) -> None:
        self._last_health_check = time.monotonic()
        for provider in self.providers:
            if provider.is_healthy:
                self._ping_provider(provider)

    def _try_recover_providers(self) -> None:
        self._last_recovery_check = time.monotonic()
        for provider in self.providers:
            if not provider.is_healthy:
                logger.info("Attempting recovery for %s", provider.name)
                if self._ping_provider(provider):
                    logger.info("Provider %s recovered", provider.name)

    def _select_provider(self) -> RpcProvider:
        """Select the best healthy provider, or fall back to the first one."""
        active = self.providers[self._active_index]
        if active.is_healthy:
            return active

        # Failover: healthy provider with the lowest priority value
        healthy = [p for p in self.providers if p.is_healthy]
        if healthy:
            best = min(healthy, key=lambda p: (p.priority, p.avg_latency_ms))
            new_index = self.providers.index(best)
            logger.warning(
                "Failover on %s: %s -> %s",
                self.chain_name, active.name, best.name,
            )
            self._active_index = new_index
            return best

        # All providers unhealthy -- last resort
        logger.error(
            "All providers unhealthy for %s, falling back to %s",
            self.chain_name, self.providers[0].name,
        )
        self._active_index = 0
        return self.providers[0]
