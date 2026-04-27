"""Phase 3C regression tests for `DemoMode.running` / `_set_running`.

CONC-08 — `self.is_running` was inconsistently locked: writes inside the
training thread held `self._lock`, while API-side reads (`if self.is_running
...`) and the `was_running := self.is_running` walrus did not. The new
`DemoMode.running` property and `_set_running` helper give every caller a
single locked path.

These tests verify that the helpers actually serialize through `self._lock`
(by swapping the lock for a tracing wrapper) and that all the previously
unprotected access sites in the production paths now go through them.
"""

from __future__ import annotations

import re
import textwrap
import threading
from pathlib import Path

import pytest

_DEMO_MODE_SRC = Path(__file__).resolve().parents[2] / "demo_mode.py"


@pytest.mark.unit
class TestDemoModeRunningHelpersExist:
    """Source-level checks that don't require torch.

    The full behaviour tests below import DemoMode and so need torch; in
    environments where torch's C-extension is broken (`torch._C` directory
    shadowing `torch._C.so` under Python 3.14 free-threading, documented
    in auto-memory) those tests will skip via `importorskip`. These
    source-level checks always run and guard against accidental removal of
    the helpers or regression of the previously-fixed call sites.
    """

    @classmethod
    def setup_class(cls) -> None:
        cls.source = _DEMO_MODE_SRC.read_text(encoding="utf-8")

    def test_running_property_defined(self):
        assert re.search(r"^\s*@property\s*\n\s*def\s+running\s*\(self\)\s*->\s*bool\s*:", self.source, re.MULTILINE), "DemoMode.running property is missing"

    def test_set_running_helper_defined(self):
        assert re.search(r"^\s*def\s+_set_running\s*\(self,\s*value:\s*bool\s*\)\s*->\s*None\s*:", self.source, re.MULTILINE), "DemoMode._set_running helper is missing"

    def test_running_property_uses_lock(self):
        # Find the body of the `running` property and assert it acquires self._lock.
        match = re.search(
            r"@property\s*\n\s*def\s+running\s*\(self\)\s*->\s*bool\s*:\s*\n(?:\s+\"\"\".*?\"\"\"\s*\n)?(?P<body>(?:\s+.+\n)+?)(?=\n\s*def\s|\nclass\s|\Z)",
            self.source,
            re.DOTALL,
        )
        assert match is not None
        assert "with self._lock:" in textwrap.dedent(match.group("body")), "DemoMode.running does not acquire self._lock"

    @pytest.mark.parametrize(
        "expected_replacement",
        [
            # The original `if self.is_running and not reset` (start) → `self.running`
            "if self.running and not reset:",
            # Two unprotected `if not self.is_running:` reads in stop()/pause()/resume()
            "if not self.running:",
            # The walrus in reset()
            "if was_running := self.running:",
            # The thread-loop completion site
            "self._set_running(False)",
        ],
    )
    def test_call_sites_use_helpers(self, expected_replacement):
        assert expected_replacement in self.source, f"Phase 3C CONC-08 fix regressed: missing call-site `{expected_replacement}` in src/demo_mode.py"


# Local environments may have a broken torch C-extension install (the
# `torch._C` directory shadows `torch._C.so` under Python 3.14
# free-threading; documented in auto-memory). DemoMode imports torch
# transitively. Defer the import so the source-level checks above always
# run; the behavioural tests below opt-in via the `_demo_module` fixture
# and skip cleanly when torch can't load.


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


@pytest.fixture
def demo(_demo_module, monkeypatch):
    """Build a DemoMode whose dataset generator falls back to local."""
    DemoMode = _demo_module.DemoMode

    def _raise(*_a, **_kw):
        raise RuntimeError("force local fallback in tests")

    monkeypatch.setattr(DemoMode, "_generate_spiral_dataset", _raise, raising=True)
    return DemoMode(update_interval=0.1)


@pytest.mark.unit
class TestRunningPropertyUsesLock:
    """CONC-08 — both helpers must execute under `self._lock`."""

    def test_running_property_acquires_lock(self, demo):
        lock = _TracingLock()
        demo._lock = lock
        # Force a known underlying value so the read returns it.
        demo.is_running = True

        assert demo.running is True
        # Exactly one acquire + release pair.
        assert [e[0] for e in lock.events] == ["acquire", "release"]

    def test_set_running_acquires_lock_and_writes(self, demo):
        lock = _TracingLock()
        demo._lock = lock
        demo.is_running = False

        demo._set_running(True)
        assert demo.is_running is True
        assert [e[0] for e in lock.events] == ["acquire", "release"]

        demo._set_running(False)
        assert demo.is_running is False

    def test_concurrent_set_running_consistent(self, demo):
        """Many threads flipping `_set_running` must converge to the last write order's value."""
        n_threads = 32
        barrier = threading.Barrier(n_threads)
        # All threads write True — the final state must be True (no torn write).
        demo.is_running = False

        def worker() -> None:
            barrier.wait()
            demo._set_running(True)

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert demo.running is True


@pytest.mark.unit
class TestRunningPropertyWiredAtCallSites:
    """CONC-08 — the previously unprotected callers must use the new helpers."""

    def test_start_uses_running_property_for_check(self, demo, monkeypatch):
        """start() rejects re-entry when already running using the locked read."""
        lock = _TracingLock()
        demo._lock = lock
        # Pre-set the flag so the early-return path fires.
        demo.is_running = True

        # Stub state_machine.handle_command to return True so start() reaches
        # the `if self.running and not reset` check.
        monkeypatch.setattr(demo.state_machine, "handle_command", lambda *_a, **_kw: True)

        result = demo.start()
        # The early-return logs "already running" and returns the snapshot
        # from get_current_state — both paths must have acquired the lock.
        assert result is not None
        # At least one acquire/release pair fired (start() check + snapshot).
        acquires = [e for e in lock.events if e[0] == "acquire"]
        assert len(acquires) >= 1, "start() did not acquire self._lock for the running check"

    def test_stop_uses_running_property_for_early_return(self, demo, monkeypatch):
        """stop() short-circuits via the locked read when not running."""
        lock = _TracingLock()
        demo._lock = lock
        demo.is_running = False
        monkeypatch.setattr(demo.state_machine, "handle_command", lambda *_a, **_kw: True)

        # _update_training_status touches self.training_state internally;
        # short-circuit it so the test stays focused on the lock acquisition.
        monkeypatch.setattr(demo, "_update_training_status", lambda: None)

        demo.stop()
        acquires = [e for e in lock.events if e[0] == "acquire"]
        assert len(acquires) >= 1, "stop() did not acquire self._lock for the running check"
