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
        adapter._client._request.assert_called_once_with("GET", "/v1/history/dataset_swaps", params=None)

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
        adapter._client._request.assert_called_once_with("GET", "/v1/history/dataset_swaps", params={"since": "2026-05-15T11:00:00+00:00"})

    def test_returns_error_on_cascor_failure(self, adapter):
        """Cascor unreachable / 5xx surfaces as ok=False with the error
        string + an empty events list so the callback layer can degrade
        gracefully (panels show "no events known")."""
        adapter._client._request.side_effect = JuniperCascorClientError("connection refused")
        result = adapter.get_dataset_swap_events()
        assert result["ok"] is False
        assert "connection refused" in result["error"]
        assert result["events"] == []
