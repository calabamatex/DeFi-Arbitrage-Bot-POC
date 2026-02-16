"""
Health and metrics HTTP endpoint.

Lightweight server that exposes:
  GET /health       -> 200/503 JSON health status (backwards compat)
  GET /healthz      -> 200 liveness probe (always 200 if server is running)
  GET /readyz       -> 200/503 readiness probe (checks bot initialized)
  GET /metrics      -> Prometheus text format (auth required if token set)
  GET /api/status   -> Full JSON metrics snapshot (auth required if token set)

Runs in a background thread — does not block the bot.

Usage:
    from src.api.health import start_health_server
    start_health_server(bot, port=8080)
"""

import json
import logging
import os
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from typing import Any, Optional
from urllib.parse import urlparse

try:
    from prometheus_client import (
        Counter,
        Gauge,
        generate_latest,
        CONTENT_TYPE_LATEST,
    )

    HAS_PROMETHEUS = True
except ImportError:
    HAS_PROMETHEUS = False

logger = logging.getLogger(__name__)

# Auth token — if set, /api/status and /metrics require Bearer auth
_AUTH_TOKEN: Optional[str] = os.getenv("HEALTH_AUTH_TOKEN") or None

# Endpoints that never require auth (for container orchestrators)
_PUBLIC_PATHS = frozenset({"/health", "/healthz", "/readyz"})


# -- Prometheus metrics (registered once at module level) --
if HAS_PROMETHEUS:
    BOT_UPTIME = Gauge("bot_uptime_seconds", "Bot uptime in seconds")
    BOT_SCANS = Counter("bot_scans_total", "Total scan cycles")
    BOT_OPPORTUNITIES = Counter("bot_opportunities_total", "Total opportunities found")
    BOT_TRADES = Counter("bot_trades_total", "Total trades executed", ["result"])
    BOT_NET_PROFIT = Gauge("bot_net_profit_usd", "Cumulative net profit in USD")
    BOT_CIRCUIT_BREAKER = Gauge("bot_circuit_breaker_active", "Circuit breaker active (1/0)")
    BOT_MEMORY_MB = Gauge("bot_memory_usage_mb", "Process memory usage in MB")


@dataclass
class BotHealthStatus:
    """Snapshot of bot health for the /health endpoint."""

    running: bool
    uptime_seconds: float
    chain_id: int
    scans: int
    opportunities_found: int
    trades_executed: int
    successful_trades: int
    failed_trades: int
    circuit_breaker_active: bool
    dry_run: bool
    timestamp: str


class _BotRef:
    """Weak reference holder so the health server can read bot state."""

    bot: Any = None
    start_time: float = time.time()


_ref = _BotRef()


def _get_health() -> BotHealthStatus:
    """Build current health status from the bot reference."""
    bot = _ref.bot
    uptime = time.time() - _ref.start_time

    if bot is None:
        return BotHealthStatus(
            running=False,
            uptime_seconds=uptime,
            chain_id=0,
            scans=0,
            opportunities_found=0,
            trades_executed=0,
            successful_trades=0,
            failed_trades=0,
            circuit_breaker_active=False,
            dry_run=True,
            timestamp=datetime.utcnow().isoformat(),
        )

    stats = getattr(bot, "stats", {})
    chain_id = 0
    try:
        chain_id = bot.web3.eth.chain_id
    except Exception:
        pass

    circuit_active = False
    try:
        if hasattr(bot, "risk_manager"):
            rm = bot.risk_manager.get_risk_metrics()
            circuit_active = rm.circuit_breaker_active
    except Exception:
        pass

    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"

    return BotHealthStatus(
        running=getattr(bot, "running", False),
        uptime_seconds=round(uptime, 1),
        chain_id=chain_id,
        scans=stats.get("scans", 0),
        opportunities_found=stats.get("opportunities_found", stats.get("liquidations_found", 0)),
        trades_executed=stats.get("opportunities_executed", stats.get("liquidations_executed", 0)),
        successful_trades=stats.get("successful_executions", stats.get("successful", 0)),
        failed_trades=stats.get("failed_executions", stats.get("failed", 0)),
        circuit_breaker_active=circuit_active,
        dry_run=dry_run,
        timestamp=datetime.utcnow().isoformat(),
    )


def _update_prometheus():
    """Push current stats into Prometheus gauges/counters."""
    if not HAS_PROMETHEUS:
        return
    health = _get_health()
    BOT_UPTIME.set(health.uptime_seconds)
    BOT_CIRCUIT_BREAKER.set(1 if health.circuit_breaker_active else 0)

    try:
        import resource

        mem = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 / 1024  # MB on macOS
        BOT_MEMORY_MB.set(mem)
    except Exception:
        pass


class HealthHandler(BaseHTTPRequestHandler):
    """HTTP request handler for health/metrics/status."""

    def log_message(self, format, *args):
        # Suppress default access log; we log via logger instead
        pass

    def _check_auth(self) -> bool:
        """Check Bearer auth token. Returns True if authorized."""
        if not _AUTH_TOKEN:
            return True
        # Strip query string before comparing against public paths
        clean_path = urlparse(self.path).path
        if clean_path in _PUBLIC_PATHS:
            return True
        auth_header = self.headers.get("Authorization", "")
        if auth_header == f"Bearer {_AUTH_TOKEN}":
            return True
        logger.warning("Auth failure on %s from %s", self.path, self.client_address[0])
        self._send_json(401, {"error": "unauthorized"})
        return False

    def _send_json(self, status_code: int, data: dict):
        body = json.dumps(data).encode()
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        # Strip query string so /health?foo=bar still matches /health
        path = urlparse(self.path).path

        if path == "/health":
            self._handle_health()
        elif path == "/healthz":
            self._handle_liveness()
        elif path == "/readyz":
            self._handle_readiness()
        elif path == "/metrics":
            if self._check_auth():
                self._handle_metrics()
        elif path == "/api/status":
            if self._check_auth():
                self._handle_status()
        else:
            self._send_json(404, {"error": "not found"})

        logger.debug("%s %s -> response sent", self.command, self.path)

    def _handle_health(self):
        health = _get_health()
        status_code = 200 if health.running else 503
        self._send_json(status_code, {"status": "ok" if health.running else "down"})

    def _handle_liveness(self):
        """Liveness probe: always 200 if the server process is alive."""
        self._send_json(200, {"status": "alive"})

    def _handle_readiness(self):
        """Readiness probe: 200 only if bot is initialized and can accept work."""
        bot = _ref.bot
        checks = {}
        ready = True

        # Bot reference exists
        if bot is None:
            checks["bot_initialized"] = False
            ready = False
        else:
            checks["bot_initialized"] = True

            # Bot is running (not shutdown)
            running = getattr(bot, "running", False)
            checks["bot_running"] = running
            if not running:
                ready = False

            # RPC connected
            try:
                bot.web3.eth.chain_id
                checks["rpc_connected"] = True
            except Exception:
                checks["rpc_connected"] = False
                ready = False

        status_code = 200 if ready else 503
        self._send_json(status_code, {"ready": ready, "checks": checks})

    def _handle_metrics(self):
        if HAS_PROMETHEUS:
            _update_prometheus()
            output = generate_latest()
            self.send_response(200)
            self.send_header("Content-Type", CONTENT_TYPE_LATEST)
            self.end_headers()
            self.wfile.write(output)
        else:
            self._send_json(501, {"error": "prometheus_client not installed"})

    def _handle_status(self):
        health = _get_health()
        body = json.dumps(asdict(health), default=str).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)


def start_health_server(bot: Any = None, port: int = None):
    """
    Start the health/metrics HTTP server in a background daemon thread.

    Args:
        bot: The ArbitrageBot or LiquidationBot instance.
        port: Port to listen on (default: HEALTH_PORT env or 8080).
    """
    _ref.bot = bot
    _ref.start_time = time.time()

    if port is None:
        port = int(os.getenv("HEALTH_PORT", "8080"))

    bind_address = os.getenv("HEALTH_BIND_ADDRESS", "127.0.0.1")

    server = ThreadingHTTPServer((bind_address, port), HealthHandler)

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    auth_status = "auth=on" if _AUTH_TOKEN else "auth=off"
    logger.info(f"Health server started on {bind_address}:{port} ({auth_status})")
    return server
