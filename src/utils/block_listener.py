"""
WebSocket block listener for event-driven opportunity detection.

Instead of polling every 5 seconds (wasting RPC calls between blocks),
this module subscribes to ``newHeads`` via WebSocket and signals the bot
loop only when a new block is produced.

Usage::

    from src.utils.block_listener import BlockListener

    block_event = threading.Event()
    listener = BlockListener(
        ws_url="wss://polygon-mainnet.g.alchemy.com/v2/KEY",
        block_event=block_event,
    )
    listener.start()

    # In the scan loop:
    while running:
        block_event.wait(timeout=10)  # wakes on new block OR times out
        block_event.clear()
        scan_opportunities()

Falls back gracefully: if WS connection fails after ``max_retries``, the
listener thread exits and the bot reverts to timer-based polling (the
``event.wait(timeout=...)`` simply times out every interval).
"""

import json
import logging
import threading
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)

try:
    from websockets.sync.client import connect as ws_connect

    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False
    logger.debug("websockets package not installed — BlockListener unavailable")


class BlockListener(threading.Thread):
    """
    Daemon thread that subscribes to ``newHeads`` over WebSocket.

    On each new block it sets a :class:`threading.Event` so the main
    detector loop can wake immediately instead of waiting for a timer.

    Args:
        ws_url: WebSocket RPC endpoint (``wss://...``)
        block_event: Event to set when a new block arrives
        on_new_block: Optional callback ``(block_number: int) -> None``
        max_retries: Reconnection attempts before giving up (0 = infinite)
        backoff_base: Initial backoff in seconds (doubles each retry)
        backoff_max: Maximum backoff in seconds
    """

    def __init__(
        self,
        ws_url: str,
        block_event: threading.Event,
        on_new_block: Optional[Callable[[int], None]] = None,
        max_retries: int = 10,
        backoff_base: float = 1.0,
        backoff_max: float = 30.0,
    ):
        super().__init__(daemon=True, name="BlockListener")
        self.ws_url = ws_url
        self.block_event = block_event
        self.on_new_block = on_new_block
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.backoff_max = backoff_max

        self._stop_event = threading.Event()
        self._last_block: Optional[int] = None
        self.blocks_received = 0
        self.reconnections = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def stop(self):
        """Signal the listener to shut down."""
        self._stop_event.set()

    @property
    def is_listening(self) -> bool:
        return self.is_alive() and not self._stop_event.is_set()

    # ------------------------------------------------------------------
    # Thread body
    # ------------------------------------------------------------------

    def run(self):
        if not HAS_WEBSOCKETS:
            logger.warning(
                "BlockListener: websockets package not installed. "
                "Install with: pip install websockets"
            )
            return

        retries = 0
        backoff = self.backoff_base

        while not self._stop_event.is_set():
            try:
                self._listen()
                # If _listen returns normally, connection was closed cleanly
                if self._stop_event.is_set():
                    break
            except Exception as e:
                retries += 1
                self.reconnections += 1
                logger.warning(
                    f"BlockListener: connection error (attempt {retries}): {e}"
                )

                if self.max_retries > 0 and retries > self.max_retries:
                    logger.error(
                        f"BlockListener: max retries ({self.max_retries}) exceeded. "
                        f"Exiting — bot will fall back to polling."
                    )
                    return

                # Exponential backoff
                logger.info(f"BlockListener: reconnecting in {backoff:.1f}s...")
                self._stop_event.wait(timeout=backoff)
                backoff = min(backoff * 2, self.backoff_max)

        logger.info("BlockListener: stopped")

    def _listen(self):
        """Connect, subscribe, and process newHeads until disconnection."""
        logger.info(f"BlockListener: connecting to {self.ws_url[:60]}...")

        with ws_connect(self.ws_url, open_timeout=10, close_timeout=5) as ws:
            # Subscribe to newHeads
            subscribe_msg = json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "eth_subscribe",
                    "params": ["newHeads"],
                }
            )
            ws.send(subscribe_msg)

            # Read subscription confirmation
            response = json.loads(ws.recv(timeout=10))
            if "error" in response:
                raise RuntimeError(
                    f"Subscription failed: {response['error']}"
                )
            sub_id = response.get("result")
            logger.info(
                f"BlockListener: subscribed to newHeads (sub_id={sub_id})"
            )

            # Reset backoff on successful connection
            # (handled by caller after _listen returns without exception)

            # Process incoming block headers
            while not self._stop_event.is_set():
                try:
                    raw = ws.recv(timeout=5)
                except TimeoutError:
                    # No message within 5s — check stop flag and continue
                    continue

                msg = json.loads(raw)
                params = msg.get("params", {})
                result = params.get("result", {})
                block_hex = result.get("number")

                if block_hex is None:
                    continue

                block_number = int(block_hex, 16)

                # Deduplicate (shouldn't happen but guard against it)
                if self._last_block is not None and block_number <= self._last_block:
                    continue

                self._last_block = block_number
                self.blocks_received += 1

                logger.debug(f"BlockListener: new block #{block_number}")

                # Signal the detector loop
                self.block_event.set()

                # Optional callback
                if self.on_new_block:
                    try:
                        self.on_new_block(block_number)
                    except Exception as cb_err:
                        logger.warning(f"BlockListener: callback error: {cb_err}")
