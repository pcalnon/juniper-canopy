"""P2-7 (Issue #3) — Canopy ``GET /api/history/dataset_swaps`` proxy route
and ``DemoMode.get_dataset_swap_events`` parity.

The canopy proxy forwards to cascor's follow-up B endpoint
(``GET /v1/history/dataset_swaps``). Three P2-7 UI panels (replay
timeline marker, History paired-diff, Snapshots tab badges) poll this
route via ``dataset-swap-events-store``.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.mark.integration
class TestDemoDatasetSwapEvents:
    def test_empty_by_default(self):
        """A freshly-constructed demo has no recorded swaps."""
        from demo_mode import DemoMode

        demo = DemoMode()
        result = demo.get_dataset_swap_events()
        assert result == {"ok": True, "events": []}

    def test_appends_event_per_swap(self):
        """Each successful demo swap appends an event with unique
        snapshot IDs so the Snapshots-tab badge cross-reference works
        as it would against real cascor."""
        from demo_mode import DemoMode

        demo = DemoMode()
        demo.swap_dataset_live(dataset_type="moons")
        demo.swap_dataset_live(dataset_type="spirals")
        result = demo.get_dataset_swap_events()
        assert result["ok"] is True
        assert len(result["events"]) == 2
        # Distinct snapshot IDs across events.
        ids = [(e["pre_swap_snapshot_id"], e["post_swap_snapshot_id"]) for e in result["events"]]
        assert len(set(ids)) == 2

    def test_since_filter_returns_strictly_newer(self):
        """``since`` is exclusive — events with timestamp equal to
        ``since`` are NOT returned (lets a poller pass last-seen)."""
        from demo_mode import DemoMode

        demo = DemoMode()
        demo.swap_dataset_live(dataset_type="moons")
        first_ts = demo.get_dataset_swap_events()["events"][0]["timestamp"]
        demo.swap_dataset_live(dataset_type="spirals")
        result = demo.get_dataset_swap_events(since=first_ts)
        # The first event (ts == since) is excluded; the second is included.
        assert len(result["events"]) == 1
        assert result["events"][0]["after_cfg"]["dataset_type"] == "spirals"


@pytest.mark.integration
class TestDatasetSwapEventsRoute:
    def _get_client(self):
        from fastapi.testclient import TestClient

        from main import app

        return TestClient(app)

    def test_get_returns_events_from_backend(self):
        client = self._get_client()
        events_payload = [{"timestamp": "T1", "before_cfg": {"dataset_type": "spirals"}, "after_cfg": {"dataset_type": "moons"}, "arch_changes": {}, "pre_swap_snapshot_id": "snap_pre", "post_swap_snapshot_id": "snap_post"}]
        with patch("main.backend") as mock_backend:
            mock_backend.get_dataset_swap_events.return_value = {"ok": True, "events": events_payload}
            resp = client.get("/api/history/dataset_swaps")
        assert resp.status_code == 200
        assert resp.json() == {"status": "success", "data": {"events": events_payload}}

    def test_get_returns_empty_list_when_no_events(self):
        client = self._get_client()
        with patch("main.backend") as mock_backend:
            mock_backend.get_dataset_swap_events.return_value = {"ok": True, "events": []}
            resp = client.get("/api/history/dataset_swaps")
        assert resp.status_code == 200
        assert resp.json()["data"]["events"] == []

    def test_get_passes_since_param(self):
        """Route forwards ``?since=`` verbatim to ``backend.get_dataset_swap_events``."""
        client = self._get_client()
        with patch("main.backend") as mock_backend:
            mock_backend.get_dataset_swap_events.return_value = {"ok": True, "events": []}
            resp = client.get("/api/history/dataset_swaps?since=2026-05-15T12:00:00%2B00:00")
        assert resp.status_code == 200
        mock_backend.get_dataset_swap_events.assert_called_once_with(since="2026-05-15T12:00:00+00:00")

    def test_get_returns_502_on_backend_rejection(self):
        client = self._get_client()
        with patch("main.backend") as mock_backend:
            mock_backend.get_dataset_swap_events.return_value = {"ok": False, "error": "connection refused", "events": []}
            resp = client.get("/api/history/dataset_swaps")
        assert resp.status_code == 502
        assert "connection refused" in resp.json()["error"]


# ---------------------------------------------------------------------------
# P2-7 follow-up: per-snapshot swap history demo + route (cascor #259).
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestDemoSnapshotDatasetSwaps:
    def test_unknown_snapshot_id_returns_ok_false(self):
        """Unknown demo snapshot ID mirrors cascor's 404 — ok=False so
        the canopy proxy maps to a 502, which the timeline degrades
        from gracefully (live-event-only render)."""
        from demo_mode import DemoMode

        demo = DemoMode()
        result = demo.get_snapshot_dataset_swaps("not-a-real-snapshot")
        assert result["ok"] is False
        assert result["events"] == []

    def test_pre_swap_id_returns_history_strictly_before_swap(self):
        """``demo_snapshot_pre_<NNN>`` resolves to events ``[0:NNN]``.
        The pre-swap snapshot was taken **before** swap NNN appended
        itself, so the snapshot's history must NOT include swap NNN."""
        from demo_mode import DemoMode

        demo = DemoMode()
        demo.swap_dataset_live(dataset_type="moons")  # creates _pre_000 / _post_000
        demo.swap_dataset_live(dataset_type="spirals")  # creates _pre_001 / _post_001
        result = demo.get_snapshot_dataset_swaps("demo_snapshot_pre_001")
        assert result["ok"] is True
        assert len(result["events"]) == 1
        assert result["events"][0]["after_cfg"]["dataset_type"] == "moons"

    def test_post_swap_id_includes_the_swap_that_produced_it(self):
        """``demo_snapshot_post_<NNN>`` resolves to events ``[0:NNN+1]``
        because the post-swap snapshot was taken **after** swap NNN
        appended itself."""
        from demo_mode import DemoMode

        demo = DemoMode()
        demo.swap_dataset_live(dataset_type="moons")
        demo.swap_dataset_live(dataset_type="spirals")
        result = demo.get_snapshot_dataset_swaps("demo_snapshot_post_001")
        assert result["ok"] is True
        assert len(result["events"]) == 2
        assert result["events"][1]["after_cfg"]["dataset_type"] == "spirals"

    def test_pre_swap_id_for_first_swap_returns_empty_history(self):
        """``demo_snapshot_pre_000`` is the snapshot taken right before
        the very first swap — its history is empty by definition."""
        from demo_mode import DemoMode

        demo = DemoMode()
        demo.swap_dataset_live(dataset_type="moons")
        result = demo.get_snapshot_dataset_swaps("demo_snapshot_pre_000")
        assert result == {"ok": True, "events": []}


@pytest.mark.integration
class TestSnapshotDatasetSwapsRoute:
    def _get_client(self):
        from fastapi.testclient import TestClient

        from main import app

        return TestClient(app)

    def test_get_returns_events_from_backend(self):
        client = self._get_client()
        events_payload = [{"timestamp": "T1", "before_cfg": {"dataset_type": "spirals"}, "after_cfg": {"dataset_type": "moons"}, "arch_changes": {}, "pre_swap_snapshot_id": "snap_pre", "post_swap_snapshot_id": "snap_post"}]
        with patch("main.backend") as mock_backend:
            mock_backend.get_snapshot_dataset_swaps.return_value = {"ok": True, "events": events_payload}
            resp = client.get("/api/snapshots/snap_a/history/dataset_swaps")
        assert resp.status_code == 200
        assert resp.json() == {"status": "success", "data": {"events": events_payload}}
        mock_backend.get_snapshot_dataset_swaps.assert_called_once_with(snapshot_id="snap_a")

    def test_get_returns_empty_list_when_no_events(self):
        client = self._get_client()
        with patch("main.backend") as mock_backend:
            mock_backend.get_snapshot_dataset_swaps.return_value = {"ok": True, "events": []}
            resp = client.get("/api/snapshots/snap_empty/history/dataset_swaps")
        assert resp.status_code == 200
        assert resp.json()["data"]["events"] == []

    def test_get_returns_502_on_backend_rejection(self):
        """Cascor 404 / connection error reaches the route as
        ``ok=False`` — proxy returns 502 so the timeline's degrade-on-
        error path fires."""
        client = self._get_client()
        with patch("main.backend") as mock_backend:
            mock_backend.get_snapshot_dataset_swaps.return_value = {"ok": False, "error": "snapshot not found", "events": []}
            resp = client.get("/api/snapshots/snap_missing/history/dataset_swaps")
        assert resp.status_code == 502
        assert "snapshot not found" in resp.json()["error"]

    def test_get_threads_snapshot_id_verbatim(self):
        """The ``snapshot_id`` path param flows to the backend kwarg
        unchanged so cascor sees the same ID format canopy received."""
        client = self._get_client()
        with patch("main.backend") as mock_backend:
            mock_backend.get_snapshot_dataset_swaps.return_value = {"ok": True, "events": []}
            resp = client.get("/api/snapshots/snapshot_20260515T120000Z/history/dataset_swaps")
        assert resp.status_code == 200
        mock_backend.get_snapshot_dataset_swaps.assert_called_once_with(snapshot_id="snapshot_20260515T120000Z")
