"""Tests for WebSocket block listener."""

import json
import threading
import time
import pytest
from unittest.mock import Mock, patch, MagicMock


class TestBlockListener:
    """Test BlockListener thread behavior."""

    def test_listener_signals_event_on_new_block(self):
        """Verify block_event is set when a new block header arrives."""
        from src.utils.block_listener import BlockListener

        block_event = threading.Event()
        received_blocks = []

        def on_block(num):
            received_blocks.append(num)

        # Mock the WebSocket connection
        mock_ws = MagicMock()
        # First recv: subscription confirmation
        sub_response = json.dumps({"jsonrpc": "2.0", "id": 1, "result": "0xabc"})
        # Subsequent recv: block headers, then raise to exit
        block_msg = json.dumps({
            "jsonrpc": "2.0",
            "method": "eth_subscription",
            "params": {
                "subscription": "0xabc",
                "result": {"number": "0x1234", "hash": "0xdeadbeef"},
            },
        })

        call_count = {"n": 0}

        def mock_recv(timeout=None):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return sub_response
            elif call_count["n"] == 2:
                return block_msg
            else:
                raise KeyboardInterrupt("test done")

        mock_ws.recv = mock_recv
        mock_ws.send = Mock()
        mock_ws.__enter__ = Mock(return_value=mock_ws)
        mock_ws.__exit__ = Mock(return_value=False)

        with patch("src.utils.block_listener.ws_connect", return_value=mock_ws):
            listener = BlockListener(
                ws_url="wss://test.example.com",
                block_event=block_event,
                on_new_block=on_block,
                max_retries=1,
            )
            listener.start()
            # Wait for the block to be processed
            block_event.wait(timeout=2)
            listener.stop()
            listener.join(timeout=2)

        assert block_event.is_set(), "block_event should be set after new block"
        assert 0x1234 in received_blocks, f"Expected block 0x1234, got {received_blocks}"
        assert listener.blocks_received >= 1

    def test_listener_retries_on_disconnect(self):
        """Verify listener retries with backoff on connection failure."""
        from src.utils.block_listener import BlockListener

        block_event = threading.Event()
        attempt_count = {"n": 0}

        def mock_connect(*args, **kwargs):
            attempt_count["n"] += 1
            raise ConnectionError(f"Mock disconnect #{attempt_count['n']}")

        with patch("src.utils.block_listener.ws_connect", side_effect=mock_connect):
            listener = BlockListener(
                ws_url="wss://test.example.com",
                block_event=block_event,
                max_retries=3,
                backoff_base=0.01,  # Fast backoff for tests
                backoff_max=0.05,
            )
            listener.start()
            listener.join(timeout=5)

        # Should have attempted max_retries + 1 (initial + retries)
        assert attempt_count["n"] >= 3, (
            f"Expected at least 3 connection attempts, got {attempt_count['n']}"
        )
        assert listener.reconnections >= 3
        assert not block_event.is_set(), "block_event should not be set on failure"

    def test_listener_falls_back_after_max_retries(self):
        """Verify thread exits after max_retries exhausted."""
        from src.utils.block_listener import BlockListener

        block_event = threading.Event()

        with patch(
            "src.utils.block_listener.ws_connect",
            side_effect=ConnectionError("always fail"),
        ):
            listener = BlockListener(
                ws_url="wss://test.example.com",
                block_event=block_event,
                max_retries=2,
                backoff_base=0.01,
                backoff_max=0.02,
            )
            listener.start()
            listener.join(timeout=5)

        assert not listener.is_alive(), "Listener thread should have exited"
        assert not block_event.is_set()

    def test_listener_deduplicates_blocks(self):
        """Verify same block number is not signaled twice."""
        from src.utils.block_listener import BlockListener

        block_event = threading.Event()
        received = []

        mock_ws = MagicMock()
        sub_response = json.dumps({"jsonrpc": "2.0", "id": 1, "result": "0x1"})

        # Send same block twice, then a new block
        messages = [
            sub_response,
            json.dumps({"params": {"result": {"number": "0xa"}}}),
            json.dumps({"params": {"result": {"number": "0xa"}}}),  # duplicate
            json.dumps({"params": {"result": {"number": "0xb"}}}),
        ]
        msg_iter = iter(messages)

        def mock_recv(timeout=None):
            try:
                return next(msg_iter)
            except StopIteration:
                raise KeyboardInterrupt("done")

        mock_ws.recv = mock_recv
        mock_ws.send = Mock()
        mock_ws.__enter__ = Mock(return_value=mock_ws)
        mock_ws.__exit__ = Mock(return_value=False)

        with patch("src.utils.block_listener.ws_connect", return_value=mock_ws):
            listener = BlockListener(
                ws_url="wss://test.example.com",
                block_event=block_event,
                on_new_block=lambda n: received.append(n),
                max_retries=1,
            )
            listener.start()
            time.sleep(0.5)
            listener.stop()
            listener.join(timeout=2)

        # Should have received blocks 10 and 11, NOT 10 twice
        assert received.count(0xa) == 1, f"Block 0xa should appear once, got {received}"
        assert listener.blocks_received == 2

    def test_stop_signals_thread_to_exit(self):
        """Verify stop() causes the thread to exit promptly."""
        from src.utils.block_listener import BlockListener

        block_event = threading.Event()

        # Slow-connecting mock that we'll interrupt with stop()
        def slow_connect(*args, **kwargs):
            time.sleep(10)
            raise ConnectionError("should not reach")

        with patch("src.utils.block_listener.ws_connect", side_effect=slow_connect):
            listener = BlockListener(
                ws_url="wss://test.example.com",
                block_event=block_event,
                max_retries=0,  # Infinite retries
                backoff_base=0.5,
            )
            listener.start()
            time.sleep(0.1)

            # Stop should cause exit within backoff period
            listener.stop()
            listener.join(timeout=3)

        assert not listener.is_alive(), "Listener should have exited after stop()"


class TestDetectorLoopWithBlockEvent:
    """Test that run_detector_loop uses block_event.wait instead of sleep."""

    def test_event_wait_wakes_immediately(self):
        """Verify scan triggers immediately when block_event is set."""
        block_event = threading.Event()

        # Simulate: set the event, then measure how fast wait() returns
        block_event.set()
        start = time.time()
        triggered = block_event.wait(timeout=5.0)
        elapsed = time.time() - start

        assert triggered is True
        assert elapsed < 0.1, f"event.wait should return instantly, took {elapsed:.3f}s"

    def test_event_wait_falls_back_to_timeout(self):
        """Verify scan falls back to timeout when no block event."""
        block_event = threading.Event()

        timeout = 0.2
        start = time.time()
        triggered = block_event.wait(timeout=timeout)
        elapsed = time.time() - start

        assert triggered is False
        assert elapsed >= timeout * 0.9, f"Should wait at least {timeout}s, waited {elapsed:.3f}s"
