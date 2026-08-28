#!/usr/bin/env python
"""F-CANOPY-036: candidate pool history is accumulated SERVER-side, not in the browser.

Ledger: juniper-ml notes/JUNIPER_2026-08-09_JUNIPER-CANOPY_E2E-VALIDATION-EVIDENCE.md

The dashboard used to append pool history in a callback whose Input was the ~1 Hz
``candidate-metrics-panel-training-state-store``. dash-renderer executes a queued
callback with the store's CURRENT value (or supersedes the queued trigger outright)
when the feeder rewrites the store first, so **any pool state shorter-lived than the
promotion delay was unrecordable**. Measured: zero cards across five training runs and
~20 candidate phases, while the SAME store's sibling consumers provably rendered live
pool values in those very runs.

The owner chose server-side accumulation over a clientside append, and the reason it is
the stronger fix is what this module pins: recording inside ``TrainingState.update_state``
**under the state lock** means there is no window in which a pool state exists and is
unobserved. The race is not narrowed, it is removed — so the decisive tests here are the
ones that drive transitions faster than any client could ever poll.

Every test in this module fails on the parent commit (6b55399).
"""

import sys
import threading
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[2]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from backend.training_monitor import TrainingState  # noqa: E402
from canopy_constants import BackendConstants  # noqa: E402


@pytest.fixture
def state():
    return TrainingState()


def _active(epoch, **kw):
    payload = {"candidate_pool_status": "Training", "current_epoch": epoch}
    payload.update(kw)
    return payload


@pytest.mark.unit
class TestAccumulationCannotMissATransition:
    """The point of moving it server-side."""

    def test_a_pool_state_that_lives_for_one_write_is_still_recorded(self, state):
        """THE regression.

        Active at epoch 1, immediately overwritten by Inactive. The client-side
        append could not see this: its feeder would have rewritten the store before
        the queued callback was promoted, which is exactly the zero-cards case.
        """
        state.update_state(**_active(1))
        state.update_state(candidate_pool_status="Inactive", current_epoch=1)

        history = state.get_pool_history()
        assert len(history) == 1, "a single-write pool state was lost — the race is still there"
        assert history[0]["epoch"] == 1
        assert history[0]["status"] == "Training"

    def test_every_phase_of_a_rapid_sequence_is_recorded(self, state):
        """20 candidate phases back-to-back with no polling in between."""
        for epoch in range(1, 21):
            state.update_state(**_active(epoch))
            state.update_state(candidate_pool_status="Inactive", current_epoch=epoch)

        history = state.get_pool_history()
        assert len(history) == BackendConstants.MAX_POOL_HISTORY_ENTRIES
        assert [h["epoch"] for h in history] == list(range(20, 0, -1)), "history is not newest-first over the full window"

    def test_concurrent_writers_lose_nothing(self, state):
        """The accumulator shares the state lock, so it is safe under the adapter's
        relay thread writing while a request thread reads."""
        errors: list = []

        def writer(lo, hi):
            try:
                for epoch in range(lo, hi):
                    state.update_state(**_active(epoch))
            except Exception as exc:  # pragma: no cover - a failure here is the point
                errors.append(exc)

        threads = [threading.Thread(target=writer, args=(i * 10 + 1, i * 10 + 11)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"concurrent writes raised: {errors}"
        history = state.get_pool_history()
        epochs = [h["epoch"] for h in history]
        assert len(epochs) == len(set(epochs)), "the same epoch was recorded twice under concurrency"
        assert len(history) == BackendConstants.MAX_POOL_HISTORY_ENTRIES


@pytest.mark.unit
class TestItPreservesTheClientSideContract:
    """Same shape and same rules as the append it replaces, so the panel's render and
    its existing tests are unaffected by WHERE the accumulation happens."""

    def test_inactive_pools_are_never_recorded(self, state):
        state.update_state(candidate_pool_status="Inactive", current_epoch=1)
        assert state.get_pool_history() == []

    def test_one_entry_per_epoch_keeping_the_first(self, state):
        state.update_state(**_active(1, top_candidate_id="first"))
        state.update_state(**_active(1, top_candidate_id="second"))
        history = state.get_pool_history()
        assert len(history) == 1
        assert history[0]["top_candidate_id"] == "first", "a later write for the same epoch overwrote the first observation"

    def test_snapshot_carries_the_fields_the_panel_renders(self, state):
        state.update_state(
            **_active(
                7,
                candidate_pool_phase="Selecting",
                candidate_pool_size=40,
                top_candidate_id="31",
                top_candidate_score=0.181,
                second_candidate_id="11",
                second_candidate_score=0.09,
            )
        )
        entry = state.get_pool_history()[0]
        assert entry["epoch"] == 7
        assert entry["status"] == "Training"
        assert entry["phase"] == "Selecting"
        assert entry["size"] == 40
        assert entry["top_candidate_id"] == "31"
        assert entry["top_candidate_score"] == pytest.approx(0.181)
        assert entry["second_candidate_id"] == "11"
        assert entry["second_candidate_score"] == pytest.approx(0.09)
        assert isinstance(entry["timestamp"], float)

    def test_selecting_best_is_an_active_status(self, state):
        """The adapter emits this one on ``adding_candidate`` — it must record."""
        state.update_state(candidate_pool_status="Selecting Best", current_epoch=3)
        assert state.get_pool_history()[0]["status"] == "Selecting Best"


@pytest.mark.unit
class TestAccessorSafety:
    def test_get_pool_history_returns_copies(self, state):
        state.update_state(**_active(1))
        state.get_pool_history()[0]["epoch"] = 999
        assert state.get_pool_history()[0]["epoch"] == 1, "the accessor handed out a live reference to the accumulator"

    def test_pool_metrics_is_copied_not_aliased(self, state):
        metrics = {"avg_loss": 0.5}
        state.update_state(**_active(1, pool_metrics=metrics))
        metrics["avg_loss"] = 999
        assert state.get_pool_history()[0]["pool_metrics"]["avg_loss"] == pytest.approx(0.5)

    def test_clear_pool_history_empties_it(self, state):
        state.update_state(**_active(1))
        assert state.get_pool_history()
        state.clear_pool_history()
        assert state.get_pool_history() == []

    def test_accumulating_does_not_disturb_get_state(self, state):
        """Forward guard: the state payload itself must be unchanged by this feature."""
        state.update_state(**_active(4, candidate_pool_size=12))
        snapshot = state.get_state()
        assert snapshot["candidate_pool_status"] == "Training"
        assert snapshot["candidate_pool_size"] == 12
        assert "pool_history" not in snapshot, "the accumulator leaked into the state payload"


@pytest.mark.unit
class TestNoClientSideWriterRemains:
    """The panel must have no writer of ``-pool-history-store`` left to race."""

    def test_the_append_callback_is_gone(self):
        src = (_SRC / "frontend" / "components" / "candidate_metrics_panel.py").read_text(encoding="utf-8")
        assert "def update_pool_history" not in src, "the client-side append is back; it cannot see short-lived pool states"

    def test_the_history_store_rides_the_existing_tab_gated_fetch(self):
        """No new poller and no new renderer slot (the F-CANOPY-027 rule)."""
        src = (_SRC / "frontend" / "components" / "candidate_metrics_panel.py").read_text(encoding="utf-8")
        assert "def fetch_training_state" in src
        assert "_fetch_pool_history" in src
        assert src.count("dcc.Interval") == 1, "a second interval appeared in the candidate panel"

    def test_the_cap_has_one_home(self):
        from frontend.components.candidate_metrics_panel import MAX_POOL_HISTORY_ENTRIES

        assert MAX_POOL_HISTORY_ENTRIES == BackendConstants.MAX_POOL_HISTORY_ENTRIES
        assert MAX_POOL_HISTORY_ENTRIES == 20, "the documented cap changed; update the panel's docstring and the ledger"
