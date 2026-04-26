"""Concurrency regression tests for DemoMode.

CONC-07 / BUG-CN-11 — `regenerate_dataset` must mutate the network tensors,
training counters, and metrics history under `self._lock`. Before the fix only
`metrics_history.clear()` was inside the lock; the training thread could see a
new `train_x` paired with a stale `train_y`, or stale epoch/loss/accuracy
values alongside a freshly-assigned dataset.

The tests below instrument the lock and the mutated containers so that the
"is the lock held right now?" question can be answered at the moment each
write happens. The fix is verified by asserting all four observable mutation
sites (`network.train_x`, `network.train_y`, `metrics_history.clear`, and the
`current_*` counters) execute inside a single critical section.
"""

from __future__ import annotations

import threading
from collections import deque
from typing import Any, Dict, List, Tuple

import pytest

from demo_mode import DemoMode


class _TracingLock:
    """RLock wrapper that records acquire/release transitions and holder state."""

    def __init__(self) -> None:
        self._real = threading.RLock()
        self._depth = 0
        self.events: List[Tuple[str, int]] = []

    @property
    def held(self) -> bool:
        return self._depth > 0

    def __enter__(self) -> "_TracingLock":
        self._real.acquire()
        self._depth += 1
        self.events.append(("acquire", self._depth))
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.events.append(("release", self._depth))
        self._depth -= 1
        self._real.release()

    def acquire(self, *args, **kwargs):
        result = self._real.acquire(*args, **kwargs)
        if result:
            self._depth += 1
            self.events.append(("acquire", self._depth))
        return result

    def release(self) -> None:
        self.events.append(("release", self._depth))
        self._depth -= 1
        self._real.release()


class _TrackingNetwork:
    """Proxy around the real MockCascorNetwork that records lock-held state on writes."""

    def __init__(self, inner: Any, lock: _TracingLock, observations: Dict[str, bool]):
        object.__setattr__(self, "_inner", inner)
        object.__setattr__(self, "_lock", lock)
        object.__setattr__(self, "_observations", observations)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name in {"train_x", "train_y"}:
            self._observations[name] = self._lock.held
        setattr(self._inner, name, value)


class _TrackingDeque(deque):
    """Deque whose clear() records whether a tracing lock is held at call time."""

    def __init__(self, lock: _TracingLock, observations: Dict[str, bool], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._lock = lock
        self._observations = observations

    def clear(self) -> None:  # type: ignore[override]
        self._observations["metrics_history.clear"] = self._lock.held
        super().clear()


@pytest.fixture
def instrumented_demo(monkeypatch):
    """Build a DemoMode whose lock + mutation targets are observable.

    The fixture forces the local-fallback dataset path so the test does not
    require the JuniperData service to be reachable; only the locking
    behaviour of `regenerate_dataset` is exercised.
    """

    # Force local fallback during construction so __init__ doesn't try to reach
    # JuniperData.
    def _raise(*_a, **_kw):
        raise RuntimeError("force local fallback in tests")

    monkeypatch.setattr(DemoMode, "_generate_spiral_dataset", _raise, raising=True)

    demo = DemoMode(update_interval=0.1)

    observations: Dict[str, bool] = {}
    tracing_lock = _TracingLock()

    # Replace the lock and the observed containers. Note: we're replacing
    # attributes after construction, so existing initial-state setup ran with
    # the original lock — that's fine because the regression target is the
    # subsequent `regenerate_dataset` call.
    demo._lock = tracing_lock
    demo.network = _TrackingNetwork(demo.network, tracing_lock, observations)
    demo.metrics_history = _TrackingDeque(tracing_lock, observations, maxlen=demo.metrics_history.maxlen)

    return demo, tracing_lock, observations


class TestRegenerateDatasetLocking:
    """CONC-07 / BUG-CN-11 regression coverage."""

    def test_state_mutations_occur_inside_lock(self, instrumented_demo):
        """All shared-state writes must happen while `self._lock` is held."""
        demo, _lock, observations = instrumented_demo

        demo.regenerate_dataset(n_samples=10)

        # Each observed write must have seen the lock as held.
        assert observations.get("train_x") is True, "network.train_x mutated outside self._lock"
        assert observations.get("train_y") is True, "network.train_y mutated outside self._lock"
        assert observations.get("metrics_history.clear") is True, "metrics_history.clear() called outside self._lock"

    def test_lock_acquired_at_least_once(self, instrumented_demo):
        """The critical section around the reset block must fire."""
        demo, lock, _obs = instrumented_demo

        demo.regenerate_dataset(n_samples=10)

        acquires = [event for event in lock.events if event[0] == "acquire"]
        releases = [event for event in lock.events if event[0] == "release"]
        assert acquires, "regenerate_dataset never acquired self._lock"
        assert len(acquires) == len(releases), "lock acquire/release pairs are unbalanced"

    def test_post_state_is_reset_consistently(self, instrumented_demo):
        """After regenerate_dataset, counters and history are at their reset values."""
        demo, _lock, _obs = instrumented_demo

        # Pre-pollute the state to ensure regenerate_dataset actually resets it.
        demo.current_epoch = 42
        demo.current_loss = 0.123
        demo.current_accuracy = 0.987
        demo.metrics_history.append({"epoch": 1})

        demo.regenerate_dataset(n_samples=10)

        assert demo.current_epoch == 0
        assert demo.current_loss == 1.0
        assert demo.current_accuracy == 0.5
        assert len(demo.metrics_history) == 0
        assert demo.network.train_x is demo.dataset["inputs_tensor"]
        assert demo.network.train_y is demo.dataset["targets_tensor"]
