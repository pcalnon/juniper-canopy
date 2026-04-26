"""Concurrency regression tests for WebSocketManager.

CONC-01 (Phase 3B Track 3) — `check_per_ip_limit` and `_decrement_ip_count`
mutate `_per_ip_counts` with a non-atomic read-modify-write. Without
`self._ip_lock` two threads racing on the same source IP can:

  1. Both read `current = N - 1`, both pass the cap check, both write `N` —
     the cap is exceeded and the per-IP counter under-reflects the number of
     accepted connections.
  2. On disconnect: lost decrements drift the counter so connect/disconnect
     pairs no longer round-trip to zero.

In normal CPython (with GIL) the read-modify-write window is so narrow it
almost never trips in practice, so we widen it deliberately by replacing
`_per_ip_counts` with a proxy dict whose `__setitem__` sleeps for ~1 ms.
Under that magnification the race fires reliably without the lock and is
fully suppressed once `self._ip_lock` serializes the critical section.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Iterable
from unittest.mock import AsyncMock

import pytest


class _SlowSetDict(dict):
    """Dict that delays writes to widen the read-modify-write race window."""

    def __init__(self, *args: Iterable[Any], delay: float = 0.001, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._delay = delay

    def __setitem__(self, key: Any, value: Any) -> None:  # type: ignore[override]
        time.sleep(self._delay)
        super().__setitem__(key, value)


def _make_ws_with_ip(ip: str = "10.0.0.1"):
    ws = AsyncMock()
    ws.client = (ip, 12345)
    return ws


@pytest.fixture
def slow_manager():
    """WebSocketManager whose `_per_ip_counts` writes sleep ~1 ms."""
    from communication.websocket_manager import WebSocketManager

    mgr = WebSocketManager()
    # Preserve any existing entries (none, since fresh) and swap in the slow
    # proxy so the read-modify-write window is observable to other threads.
    mgr._per_ip_counts = _SlowSetDict(mgr._per_ip_counts, delay=0.001)
    return mgr


@pytest.mark.unit
class TestPerIpRace:
    """CONC-01 regression coverage."""

    def test_concurrent_check_per_ip_limit_respects_cap(self, slow_manager):
        """Concurrent checks against a cap must never accept more than `cap`."""
        ip = "10.0.0.1"
        cap = 5
        n_threads = 32
        barrier = threading.Barrier(n_threads)
        accepted = [False] * n_threads

        def worker(idx: int) -> None:
            ws = _make_ws_with_ip(ip)
            barrier.wait()
            accepted[idx] = slow_manager.check_per_ip_limit(ws, max_per_ip=cap)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        n_accepted = sum(1 for ok in accepted if ok)
        final_count = slow_manager._per_ip_counts.get(ip, 0)
        assert n_accepted <= cap, f"per-IP race: {n_accepted} threads were told 'allowed' against " f"cap={cap} — check_then_act is not atomic"
        assert n_accepted == final_count, f"per-IP race: {n_accepted} threads passed the check but counter " f"only reflects {final_count} — lost updates on _per_ip_counts"

    def test_concurrent_check_per_ip_limit_no_lost_updates(self, slow_manager):
        """When cap is generous, all threads succeed and the counter equals N."""
        ip = "10.0.0.1"
        n_threads = 32
        barrier = threading.Barrier(n_threads)

        def worker() -> None:
            ws = _make_ws_with_ip(ip)
            barrier.wait()
            slow_manager.check_per_ip_limit(ws, max_per_ip=10_000)

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert slow_manager._per_ip_counts.get(ip, 0) == n_threads

    def test_concurrent_connect_disconnect_balances(self, slow_manager):
        """connect()/disconnect() pairs from many threads must round-trip to zero."""
        ip = "10.0.0.1"
        n_threads = 16
        rounds = 8
        barrier = threading.Barrier(n_threads)

        def worker() -> None:
            barrier.wait()
            for _ in range(rounds):
                ws = _make_ws_with_ip(ip)
                if slow_manager.check_per_ip_limit(ws, max_per_ip=n_threads * rounds):
                    slow_manager._decrement_ip_count(ws)

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert slow_manager._per_ip_counts.get(ip, 0) == 0, f"per-IP race: connect/disconnect did not balance — " f"final counter = {slow_manager._per_ip_counts.get(ip)}"
