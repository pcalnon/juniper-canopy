"""Thread-safety regression tests for WebSocketManager (Phase 3C).

Covers BUG-CN-09 (`active_connections`/`connection_metadata` not thread-safe)
and BUG-CN-10 (`message_count += 1` not atomic).

Pre-fix behaviour:
  * `active_connections` is a bare `set` mutated from FastAPI endpoints (event
    loop) and read from `broadcast_from_thread` / shutdown / stats getters
    (background threads), producing `RuntimeError: Set changed size during
    iteration` once the schedule lines up.
  * `self.message_count += 1` in `broadcast()` is a non-atomic
    read-modify-write — concurrent broadcasts lose increments.

The tests below exercise the sync entry points (which is where the lock
guarantees actually have to hold) and use a barrier + populated state so the
race window is observable. Both fail reliably on the pre-fix code (sets +
unprotected counter) and pass once `_connections_lock` covers every site.
"""

from __future__ import annotations

import threading
import time
from typing import Any
from unittest.mock import AsyncMock

import pytest


class _FakeWS:
    """Hashable stand-in for a starlette/FastAPI WebSocket.

    Only the attributes touched by sync-side `disconnect()` and the metadata
    bookkeeping are populated — `connect()` and `broadcast()` are exercised
    via direct state manipulation instead of going through `await`. Identity
    hashing matches the real WebSocket-as-set-element semantics.
    """

    __slots__ = ("client", "label")

    def __init__(self, label: str = "ws") -> None:
        self.label = label
        self.client = ("127.0.0.1", 12345 + (hash(label) % 1000))


def _make_ws(label: str = "ws") -> _FakeWS:
    return _FakeWS(label)


def _seed_manager(mgr: Any, n: int) -> list:
    """Pre-populate the manager with `n` fake websockets and metadata."""
    websockets = [_make_ws(f"ws-{i}") for i in range(n)]
    with mgr._connections_lock:
        for ws in websockets:
            mgr.active_connections.add(ws)
            mgr.connection_metadata[ws] = {
                "client_id": ws.label,
                "connected_at": "now",
                "messages_sent": 0,
                "last_message_at": None,
            }
        # Mirror the per-IP counter so `_decrement_ip_count` doesn't underflow.
        mgr._per_ip_counts["127.0.0.1"] = n
    return websockets


@pytest.mark.unit
class TestActiveConnectionsThreadSafety:
    """BUG-CN-09 regression coverage."""

    def test_concurrent_disconnect_does_not_crash_iteration(self):
        """disconnect()/get_connection_info() racing must not raise RuntimeError."""
        from communication.websocket_manager import WebSocketManager

        mgr = WebSocketManager()
        websockets = _seed_manager(mgr, n=200)

        stop = threading.Event()
        crashes: list = []

        def reader() -> None:
            while not stop.is_set():
                try:
                    # Both should snapshot under the lock; without the fix the
                    # raw `for meta in self.connection_metadata.values()`
                    # could raise `RuntimeError: dictionary changed size
                    # during iteration`, and `len(self.active_connections)`
                    # could see torn state.
                    mgr.get_connection_info()
                    mgr.get_connection_count()
                except RuntimeError as exc:
                    crashes.append(exc)
                    return

        reader_threads = [threading.Thread(target=reader) for _ in range(4)]
        for t in reader_threads:
            t.start()

        # Hammer disconnect() from many threads, each owning a slice.
        chunks = [websockets[i::8] for i in range(8)]
        barrier = threading.Barrier(len(chunks))

        def disconnector(slot: int) -> None:
            barrier.wait()
            for ws in chunks[slot]:
                mgr.disconnect(ws)

        disc_threads = [threading.Thread(target=disconnector, args=(i,)) for i in range(len(chunks))]
        for t in disc_threads:
            t.start()
        for t in disc_threads:
            t.join()

        # Let readers see the final, fully-empty state then stop them.
        time.sleep(0.05)
        stop.set()
        for t in reader_threads:
            t.join()

        assert not crashes, f"BUG-CN-09: snapshot iteration raised {crashes!r}"
        assert mgr.get_connection_count() == 0
        assert mgr.get_connection_info() == []

    def test_shutdown_snapshot_tolerates_concurrent_disconnect(self):
        """shutdown()'s `for ws in active_connections` must use a snapshot."""
        from communication.websocket_manager import WebSocketManager

        mgr = WebSocketManager()
        _seed_manager(mgr, n=50)

        # Take the same snapshot path shutdown() uses and mutate the set on
        # another thread mid-iteration. Pre-fix: bare `for ws in
        # self.active_connections` raises; post-fix: shutdown() snapshots
        # under `self._connections_lock` first.
        seen: list = []
        crash: list = []

        def iterate() -> None:
            try:
                with mgr._connections_lock:
                    snapshot = list(mgr.active_connections)
                for ws in snapshot:
                    seen.append(ws)
                    time.sleep(0)  # yield so the mutator gets scheduled
            except RuntimeError as exc:
                crash.append(exc)

        def mutate() -> None:
            for ws in list(mgr.active_connections):
                mgr.disconnect(ws)

        t1 = threading.Thread(target=iterate)
        t2 = threading.Thread(target=mutate)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert not crash
        assert len(seen) == 50  # snapshot was complete


@pytest.mark.unit
class TestMessageCountAtomicity:
    """BUG-CN-10 regression coverage."""

    def test_broadcast_message_count_no_lost_updates(self):
        """N concurrent `broadcast()`s must increment `message_count` exactly N times."""
        import asyncio

        from communication.websocket_manager import WebSocketManager

        mgr = WebSocketManager()
        # Need at least one connection so broadcast() doesn't bail at the
        # early-out. Use AsyncMock so `await connection.send_json` resolves.
        ws = AsyncMock()
        with mgr._connections_lock:
            mgr.active_connections.add(ws)
            mgr.connection_metadata[ws] = {
                "client_id": "test",
                "connected_at": "now",
                "messages_sent": 0,
                "last_message_at": None,
            }

        n_broadcasts = 64

        async def driver() -> None:
            await asyncio.gather(*(mgr.broadcast({"type": "ping", "i": i}) for i in range(n_broadcasts)))

        asyncio.run(driver())

        # Every broadcast that didn't bail must have been counted; the early
        # bail can only happen when no connections exist (we seeded one).
        assert mgr.message_count == n_broadcasts, f"BUG-CN-10: lost message_count updates — got {mgr.message_count} of {n_broadcasts}"
