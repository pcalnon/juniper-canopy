"""Phase 3D regression tests for `DemoMode._perform_reset` lock scope.

BUG-CN-01 — `_perform_reset()` released `self._lock` after writing
`is_running = False` but before clearing the `_stop` and `_pause`
``threading.Event``s. Any reader observing ``is_running`` (e.g. the start
path's `if self.running and not reset:` check, or the training loop's
`if self._stop.is_set(): break`) could see ``is_running == False`` while
``_stop`` was still set, leaving the next start() racing against a stale
stop signal that gets cleared a moment later.

The fix moves both `self._stop.clear()` and `self._pause.clear()` inside
the same `with self._lock:` block as `self.is_running = False`, making the
shutdown transition atomic.

Source-level checks below run unconditionally; behavioural tests defer the
torch import via a fixture so the JuniperCanopy env's broken torch
C-extension (auto-memory) doesn't gate them.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

_DEMO_MODE_SRC = Path(__file__).resolve().parents[2] / "demo_mode.py"


@pytest.mark.unit
class TestPerformResetSourceLevel:
    """Source-level guards for the BUG-CN-01 fix.

    Uses Python's ast module so the indentation structure (which is the
    whole point of "is X inside the with-block?") is checked properly.
    """

    @classmethod
    def setup_class(cls) -> None:
        import ast

        cls.source = _DEMO_MODE_SRC.read_text(encoding="utf-8")
        cls._tree = ast.parse(cls.source)

    def _find_method(self, class_name: str, method_name: str):
        import ast

        for node in ast.walk(self._tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name == method_name:
                        return item
        return None

    @staticmethod
    def _call_chain(call) -> list[str]:
        """Return the dotted attribute chain of `call.func` (or empty)."""
        import ast

        node = call.func
        chain: list[str] = []
        while isinstance(node, ast.Attribute):
            chain.append(node.attr)
            node = node.value
        if isinstance(node, ast.Name):
            chain.append(node.id)
        chain.reverse()
        return chain

    def _calls_under(self, body) -> list[list[str]]:
        import ast

        out = []
        for node in body:
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call):
                    out.append(self._call_chain(sub))
        return out

    def _assignments_under(self, body) -> list[str]:
        """Return a list of dotted-target names assigned in the body."""
        import ast

        out = []
        for node in body:
            for sub in ast.walk(node):
                if isinstance(sub, ast.Assign):
                    for target in sub.targets:
                        chain: list[str] = []
                        cur = target
                        while isinstance(cur, ast.Attribute):
                            chain.append(cur.attr)
                            cur = cur.value
                        if isinstance(cur, ast.Name):
                            chain.append(cur.id)
                        chain.reverse()
                        out.append(".".join(chain))
        return out

    def test_perform_reset_holds_lock_across_event_clears(self):
        """`_stop.clear()` and `_pause.clear()` must live inside the same `with self._lock:` as `is_running = False`."""
        import ast

        method = self._find_method("DemoMode", "_perform_reset")
        assert method is not None, "could not locate DemoMode._perform_reset"

        with_blocks = []
        for node in ast.walk(method):
            if isinstance(node, ast.With):
                for item in node.items:
                    ctx = item.context_expr
                    if isinstance(ctx, ast.Attribute) and ctx.attr == "_lock" and isinstance(ctx.value, ast.Name) and ctx.value.id == "self":
                        with_blocks.append(node)

        assert with_blocks, "_perform_reset no longer uses `with self._lock:`"

        # Some `with self._lock:` block must contain ALL three: the
        # `self.is_running = False` write, the `self._stop.clear()` call,
        # and the `self._pause.clear()` call.
        for block in with_blocks:
            assigns = self._assignments_under(block.body)
            calls = self._calls_under(block.body)
            has_running_clear = "self.is_running" in assigns
            has_stop_clear = ["self", "_stop", "clear"] in calls
            has_pause_clear = ["self", "_pause", "clear"] in calls
            if has_running_clear and has_stop_clear and has_pause_clear:
                return
        pytest.fail("BUG-CN-01 regressed: no `with self._lock:` block in _perform_reset contains all of self.is_running = False, self._stop.clear(), and self._pause.clear()")


@pytest.fixture(scope="module")
def _demo_module():
    pytest.importorskip("torch", exc_type=ImportError)
    import demo_mode

    return demo_mode


class _TracingLock:
    """RLock wrapper that records each acquire/release transition."""

    def __init__(self) -> None:
        self._real = threading.RLock()
        self._depth = 0
        self.events: list = []

    @property
    def held(self) -> bool:
        return self._depth > 0

    def __enter__(self) -> "_TracingLock":
        self._real.acquire()
        self._depth += 1
        self.events.append(("acquire", self._depth))
        return self

    def __exit__(self, *_a) -> None:
        self.events.append(("release", self._depth))
        self._depth -= 1
        self._real.release()


class _TracingEvent:
    """`threading.Event` wrapper that records lock-held state at clear() time."""

    def __init__(self, lock: _TracingLock) -> None:
        self._real = threading.Event()
        self._lock = lock
        self.observations: list = []

    def is_set(self) -> bool:
        return self._real.is_set()

    def set(self) -> None:
        self._real.set()

    def clear(self) -> None:
        self.observations.append(("clear", self._lock.held))
        self._real.clear()

    def wait(self, timeout: float | None = None) -> bool:
        return self._real.wait(timeout)


@pytest.fixture
def demo(_demo_module, monkeypatch):
    DemoMode = _demo_module.DemoMode

    def _raise(*_a, **_kw):
        raise RuntimeError("force local fallback in tests")

    monkeypatch.setattr(DemoMode, "_generate_spiral_dataset", _raise, raising=True)
    return DemoMode(update_interval=0.1)


@pytest.mark.unit
class TestPerformResetEventClearsUnderLock:
    """BUG-CN-01 behavioural coverage."""

    def test_perform_reset_clears_events_under_lock(self, demo):
        """`_stop.clear()` and `_pause.clear()` must observe the lock as held."""
        lock = _TracingLock()
        demo._lock = lock
        demo._stop = _TracingEvent(lock)
        demo._pause = _TracingEvent(lock)
        demo._stop.set()
        demo._pause.set()

        demo._perform_reset()

        # Both events should have been cleared, and both clears should have
        # happened while the lock was held.
        assert demo._stop.observations == [("clear", True)], "BUG-CN-01: _stop.clear() fired outside lock"
        assert demo._pause.observations == [("clear", True)], "BUG-CN-01: _pause.clear() fired outside lock"
        # Lock acquire+release pair fired exactly once.
        acquires = [e for e in lock.events if e[0] == "acquire"]
        releases = [e for e in lock.events if e[0] == "release"]
        assert len(acquires) == len(releases) == 1
