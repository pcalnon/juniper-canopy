#!/usr/bin/env python
"""Per-file coverage-gate tests for ``demo_mode.py`` (part 2 of 2).

Focuses on the dataset-surface methods the existing suite reaches only through
the ``DemoBackend`` adapter (so the ``DemoMode`` bodies stay uncovered):

* ``_install_sequence_dataset`` branch variants (X_train fallback, bad-rank
  raise, missing-Δt zero-fill, y_train fallback, empty-histogram, stop-when-
  running).
* The pending-dataset staging surface (``stage_dataset`` /
  ``cancel_pending_dataset`` / ``get_pending_dataset``).
* The experimental-functions toggle.
* The live dataset-swap surface (``swap_dataset_live`` /
  ``cancel_swap_dataset_live``) and its event feed
  (``get_dataset_swap_events`` / ``get_snapshot_dataset_swaps``).

Every test asserts observable behaviour.
Companion file: ``test_demo_mode_gate_coverage.py``.
"""

import numpy as np
import pytest

from backend.training_state_machine import Command
from demo_mode import DemoMode

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# _install_sequence_dataset branch variants
# ---------------------------------------------------------------------------
class TestInstallSequenceDataset:
    def test_sequence_x_train_no_dt_nan_targets(self):
        """X_train fallback, absent Δt (zero-fill), y_train fallback, empty histogram.

        Covers lines 1926, 1932, 1944-1945, 1952, 1962, 1971.
        """
        X3 = np.random.RandomState(1).randn(3, 4, 2).astype(np.float32)  # (W=3, L=4, F=2)
        npz = {
            "X_train": X3,  # no X_full -> X_train fallback (1926)
            "y_train": np.array([np.nan, np.nan, np.nan], dtype=np.float64),  # no y_full (1952); all-NaN -> empty hist (1962)
            # no dt_full / dt_train -> zero-fill (1944-1945) + dt_hist None (1971)
        }
        demo = DemoMode()

        result = demo._install_sequence_dataset(npz, source_label="seq-branch")

        assert result["dataset_kind"] == "sequence"
        assert result["n_windows"] == 3
        assert result["lookback"] == 4
        assert result["n_features"] == 2
        seq = result["sequence"]
        # Δt was absent -> per-window Δt zero-filled to lookback length.
        assert seq["windows_dt"][0] == [0.0, 0.0, 0.0, 0.0]
        assert seq["dt_hist"] is None
        # All-NaN target -> bounded histogram returns None.
        assert seq["target_hist"] is None
        # Display-only install must NOT touch the trainable tensors.
        assert demo.network.train_x is not None  # unchanged from constructor
        assert demo.dataset is result

    def test_sequence_bad_rank_raises(self):
        """Neither X_full nor X_train present -> ValueError after the fallback (lines 1928-1929)."""
        demo = DemoMode()
        with pytest.raises(ValueError, match="sequence install expects a 3-D X"):
            demo._install_sequence_dataset({}, source_label="seq-bad")

    def test_sequence_with_dt_stops_when_running(self):
        """A valid Δt-bearing sequence install stops an active run (lines 1995-1996)."""
        X3 = np.random.RandomState(2).randn(2, 3, 2).astype(np.float32)
        dt = np.random.RandomState(3).rand(2, 3).astype(np.float32)
        y = np.random.RandomState(4).randn(2, 1).astype(np.float32)
        npz = {"X_full": X3, "dt_full": dt, "y_full": y}

        demo = DemoMode()
        demo.state_machine.handle_command(Command.START)
        demo._set_running(True)
        assert demo.running is True

        result = demo._install_sequence_dataset(npz, source_label="seq-running")

        assert demo.running is False  # stop() ran before the swap
        assert result["dataset_kind"] == "sequence"
        # Δt present -> a real histogram, not None.
        assert result["sequence"]["dt_hist"] is not None
        assert set(result["sequence"]["dt_hist"]) == {"edges", "counts"}


# ---------------------------------------------------------------------------
# Pending-dataset staging surface
# ---------------------------------------------------------------------------
class TestPendingDatasetSurface:
    def test_stage_dataset_records_config(self):
        """Non-empty config is staged (lines 2253-2259)."""
        demo = DemoMode()
        resp = demo.stage_dataset(dataset_type="spiral", n_samples=300, ignored=None)

        assert resp["ok"] is True
        assert resp["data"]["status"] == "staged"
        assert resp["data"]["config"] == {"dataset_type": "spiral", "n_samples": 300}
        # None-valued keys are filtered out.
        assert "ignored" not in resp["data"]["config"]
        assert demo._pending_dataset_config == {"dataset_type": "spiral", "n_samples": 300}

    def test_stage_dataset_empty_clears(self):
        """An all-None config clears any pending stage (lines 2255-2257)."""
        demo = DemoMode()
        demo._pending_dataset_config = {"dataset_type": "old"}

        resp = demo.stage_dataset(dataset_type=None)

        assert resp["data"]["status"] == "cleared"
        assert resp["data"]["config"] is None
        assert demo._pending_dataset_config is None

    def test_cancel_pending_dataset_discards(self):
        """cancel_pending_dataset returns the discarded config and clears it (lines 2262-2265)."""
        demo = DemoMode()
        demo.stage_dataset(dataset_type="xor")

        resp = demo.cancel_pending_dataset()

        assert resp["ok"] is True
        assert resp["data"]["status"] == "cleared"
        assert resp["data"]["discarded"] == {"dataset_type": "xor"}
        assert demo._pending_dataset_config is None

    def test_get_pending_dataset_reports_stage(self):
        """get_pending_dataset reflects the staged config (lines 2268-2269)."""
        demo = DemoMode()
        assert demo.get_pending_dataset() == {"ok": True, "pending": None}

        demo.stage_dataset(dataset_type="moon")
        resp = demo.get_pending_dataset()
        assert resp["ok"] is True
        assert resp["pending"] == {"dataset_type": "moon"}


# ---------------------------------------------------------------------------
# Experimental-functions toggle
# ---------------------------------------------------------------------------
class TestExperimentalFunctions:
    def test_experimental_functions_default_and_toggle(self):
        """Toggle defaults to False, then honours set_experimental_functions (lines 2277-2283)."""
        demo = DemoMode()
        assert demo.get_experimental_functions() == {"ok": True, "enabled": False}

        set_resp = demo.set_experimental_functions(True)
        assert set_resp == {"ok": True, "enabled": True}
        assert demo.get_experimental_functions() == {"ok": True, "enabled": True}

        # And back off again.
        assert demo.set_experimental_functions(False)["enabled"] is False
        assert demo.get_experimental_functions()["enabled"] is False


# ---------------------------------------------------------------------------
# Live dataset-swap surface + event feed
# ---------------------------------------------------------------------------
class TestSwapDatasetLive:
    def test_swap_dataset_live_empty_config_rejected(self):
        """An all-None config is rejected without swapping (lines 2296-2299)."""
        demo = DemoMode()
        resp = demo.swap_dataset_live(dataset_type=None)

        assert resp["ok"] is False
        assert "no dataset config" in resp["error"]

    def test_swap_dataset_live_records_event(self):
        """A successful swap fabricates the response and appends an event (lines 2305-2347)."""
        demo = DemoMode()
        assert not hasattr(demo, "_dataset_swap_events")

        resp = demo.swap_dataset_live(dataset_type="xor", n_samples=250)

        assert resp["ok"] is True
        data = resp["data"]
        assert data["status"] == "swapped"
        assert data["after_cfg"] == {"dataset_type": "xor", "n_samples": 250}
        assert data["pre_swap_snapshot_id"] == "demo_snapshot_pre_000"
        assert data["post_swap_snapshot_id"] == "demo_snapshot_post_000"
        # A live swap supersedes any pending stage.
        assert demo._pending_dataset_config is None
        # The event feed grew by exactly one entry.
        assert len(demo._dataset_swap_events) == 1
        assert demo._dataset_swap_events[0]["post_swap_snapshot_id"] == "demo_snapshot_post_000"

        # Second swap increments the snapshot index (list already exists).
        resp2 = demo.swap_dataset_live(dataset_type="moon")
        assert resp2["data"]["pre_swap_snapshot_id"] == "demo_snapshot_pre_001"
        assert len(demo._dataset_swap_events) == 2

    def test_cancel_swap_dataset_live_is_noop(self):
        """Demo has no in-flight swap to cancel (line 2352)."""
        demo = DemoMode()
        resp = demo.cancel_swap_dataset_live()

        assert resp["ok"] is False
        assert resp["error"] == "no_swap_in_progress"


class TestSwapEventFeed:
    def test_get_dataset_swap_events_filtering(self):
        """get_dataset_swap_events returns all events, or filters by since (lines 2357-2361)."""
        demo = DemoMode()
        demo.swap_dataset_live(dataset_type="xor")
        demo.swap_dataset_live(dataset_type="moon")

        all_resp = demo.get_dataset_swap_events()
        assert all_resp["ok"] is True
        assert len(all_resp["events"]) == 2

        # Filtering with a timestamp beyond every event yields an empty slice.
        future = "9999-01-01T00:00:00+00:00"
        filtered = demo.get_dataset_swap_events(since=future)
        assert filtered["events"] == []

        # Filtering with an epoch-early timestamp keeps everything.
        past = "0001-01-01T00:00:00+00:00"
        assert len(demo.get_dataset_swap_events(since=past)["events"]) == 2

    def test_get_snapshot_dataset_swaps_slices(self):
        """Snapshot IDs map to the right event slices; bad IDs report not-found.

        Covers lines 2377-2378, 2380-2384, 2386-2390, 2392.
        """
        demo = DemoMode()
        demo.swap_dataset_live(dataset_type="xor")  # produces ..._000 ids
        demo.swap_dataset_live(dataset_type="moon")  # produces ..._001 ids

        # pre-swap snapshot of index 1 -> events[:1] (before swap 1 appended).
        pre = demo.get_snapshot_dataset_swaps("demo_snapshot_pre_001")
        assert pre["ok"] is True
        assert len(pre["events"]) == 1

        # post-swap snapshot of index 1 -> events[:2] (after swap 1 appended).
        post = demo.get_snapshot_dataset_swaps("demo_snapshot_post_001")
        assert post["ok"] is True
        assert len(post["events"]) == 2

        # A non-numeric pre-suffix hits the ValueError/pass branch, then not-found.
        bad_pre = demo.get_snapshot_dataset_swaps("demo_snapshot_pre_notanint")
        assert bad_pre["ok"] is False
        assert "not found" in bad_pre["error"]

        # A non-numeric post-suffix hits the other ValueError/pass branch.
        bad_post = demo.get_snapshot_dataset_swaps("demo_snapshot_post_notanint")
        assert bad_post["ok"] is False

        # A wholly unrecognised id falls straight through to not-found.
        unknown = demo.get_snapshot_dataset_swaps("something-else")
        assert unknown["ok"] is False
        assert unknown["events"] == []
