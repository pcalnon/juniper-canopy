"""P2-7 (Issue #3) — ``CascorServiceAdapter.get_dataset_swap_events``.

Adapter test covering the canopy → cascor proxy for cascor follow-up B
(``GET /v1/history/dataset_swaps``). Three P2-7 UI panels (replay
timeline marker, History paired-diff, Snapshots tab badges) all consume
the list returned by this method via the canopy ``/api/history/dataset_swaps``
route.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

_jcc = pytest.importorskip("juniper_cascor_client", reason="juniper-cascor-client not installed")
if getattr(_jcc, "_is_stub", False):
    pytest.skip("juniper-cascor-client is a test stub", allow_module_level=True)

from juniper_cascor_client.exceptions import JuniperCascorClientError

from backend.cascor_service_adapter import CascorServiceAdapter


@pytest.fixture
def adapter():
    a = CascorServiceAdapter(service_url="http://localhost:8200")
    a._client = MagicMock()
    return a


class TestGetDatasetSwapEvents:
    def test_returns_events_list_on_success(self, adapter):
        events_payload = [
            {"timestamp": "2026-05-15T12:00:00+00:00", "before_cfg": {"dataset_type": "spirals"}, "after_cfg": {"dataset_type": "moons"}, "arch_changes": {}, "pre_swap_snapshot_id": "snap_pre_1", "post_swap_snapshot_id": "snap_post_1"},
        ]
        adapter._client._request.return_value = {"data": {"events": events_payload}}
        result = adapter.get_dataset_swap_events()
        assert result == {"ok": True, "events": events_payload}
        adapter._client._request.assert_called_once_with("GET", "/history/dataset_swaps", params=None)

    def test_returns_empty_list_when_no_events(self, adapter):
        """No swaps yet → empty events list (not an error)."""
        adapter._client._request.return_value = {"data": {"events": []}}
        result = adapter.get_dataset_swap_events()
        assert result == {"ok": True, "events": []}

    def test_returns_empty_list_when_data_missing(self, adapter):
        """Defensive: cascor returns a structurally-different payload.
        Adapter falls back to empty list rather than KeyError'ing."""
        adapter._client._request.return_value = {}
        result = adapter.get_dataset_swap_events()
        assert result == {"ok": True, "events": []}

    def test_passes_since_param_when_supplied(self, adapter):
        """The ``since`` filter forwards to cascor as a query param so
        long-running pollers can pull only newer events."""
        adapter._client._request.return_value = {"data": {"events": []}}
        adapter.get_dataset_swap_events(since="2026-05-15T11:00:00+00:00")
        adapter._client._request.assert_called_once_with("GET", "/history/dataset_swaps", params={"since": "2026-05-15T11:00:00+00:00"})

    def test_returns_error_on_cascor_failure(self, adapter):
        """Cascor unreachable / 5xx surfaces as ok=False with the error
        string + an empty events list so the callback layer can degrade
        gracefully (panels show "no events known")."""
        adapter._client._request.side_effect = JuniperCascorClientError("connection refused")
        result = adapter.get_dataset_swap_events()
        assert result["ok"] is False
        assert "connection refused" in result["error"]
        assert result["events"] == []


# ---------------------------------------------------------------------------
# P2-7 follow-up: per-snapshot swap history (cascor #259 endpoint).
# ---------------------------------------------------------------------------


class TestGetSnapshotDatasetSwaps:
    def test_returns_events_list_on_success(self, adapter):
        events_payload = [
            {"timestamp": "2026-05-15T12:00:00+00:00", "before_cfg": {"dataset_type": "spirals"}, "after_cfg": {"dataset_type": "moons"}, "arch_changes": {}, "pre_swap_snapshot_id": "snap_pre_1", "post_swap_snapshot_id": "snap_post_1"},
        ]
        adapter._client._request.return_value = {"data": {"events": events_payload}}
        result = adapter.get_snapshot_dataset_swaps("snap_a")
        assert result == {"ok": True, "events": events_payload}
        adapter._client._request.assert_called_once_with("GET", "/snapshots/snap_a/history/dataset_swaps")

    def test_returns_empty_list_when_no_events(self, adapter):
        """Snapshot exists but has no swaps in its history (pre-P2-2 or
        no live-swap during that training run) → empty list, ok=True."""
        adapter._client._request.return_value = {"data": {"events": []}}
        result = adapter.get_snapshot_dataset_swaps("snap_empty")
        assert result == {"ok": True, "events": []}

    def test_returns_empty_list_when_data_missing(self, adapter):
        """Defensive: cascor returns a structurally-different payload."""
        adapter._client._request.return_value = {}
        result = adapter.get_snapshot_dataset_swaps("snap_a")
        assert result == {"ok": True, "events": []}

    def test_returns_error_on_cascor_404(self, adapter):
        """Cascor 404 (snapshot missing) → ok=False with the error
        string and empty events list. Timeline degrades to live-event-
        only render rather than hard error."""
        adapter._client._request.side_effect = JuniperCascorClientError("404 snapshot 'snap_missing' not found")
        result = adapter.get_snapshot_dataset_swaps("snap_missing")
        assert result["ok"] is False
        assert "not found" in result["error"]
        assert result["events"] == []

    def test_url_encodes_snapshot_id_in_path(self, adapter):
        """The snapshot_id flows into the URL path — the request layer's
        normal encoding handles unusual characters. Adapter does not
        pre-encode; this test pins that contract."""
        adapter._client._request.return_value = {"data": {"events": []}}
        adapter.get_snapshot_dataset_swaps("snapshot_20260515T120000Z")
        adapter._client._request.assert_called_once_with("GET", "/snapshots/snapshot_20260515T120000Z/history/dataset_swaps")
