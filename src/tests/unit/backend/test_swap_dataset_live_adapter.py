"""P2-5 (Issue #3) — ``CascorServiceAdapter`` live-swap methods.

Covers ``swap_dataset_live(**canopy_params)`` + ``cancel_swap_dataset_live()``.
The adapter proxies cascor's ``POST/DELETE /v1/training/dataset/live``
(shipped P2-1a + P2-1b + P2-1d + P2-2 + P2-3). Canopy backend's
``/api/live_dataset_swap`` route consumes these.
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


class TestSwapDatasetLive:
    def test_maps_canopy_keys_to_cascor_keys(self, adapter):
        """Same _DATASET_PARAM_MAP as stage_dataset — nn_dataset_type →
        dataset_type, nn_dataset_elements → n_samples, etc. The live-swap
        endpoint accepts the same body shape as the cold-swap endpoint."""
        adapter._client._request.return_value = {"data": {"status": "swapped", "arch_changes": {"input_delta": 0}}}
        result = adapter.swap_dataset_live(
            nn_dataset_type="spirals",
            nn_dataset_elements=200,
            nn_dataset_noise=0.05,
            nn_spiral_rotations=2.5,
            nn_spiral_number=2,
            nn_unrelated_field="ignored",
        )
        assert result["ok"] is True
        call = adapter._client._request.call_args
        assert call.args[:2] == ("POST", "/training/dataset/live")
        body = call.kwargs["json"]
        assert body == {
            "dataset_type": "spirals",
            "n_samples": 200,
            "noise": 0.05,
            "rotations": 2.5,
            "n_spirals": 2,
        }

    def test_returns_full_response_data_on_success(self, adapter):
        """The §3.3 response carries arch_changes, snapshot IDs, mode —
        all of which the canopy callback layer surfaces in the outcome
        alert / P2-7 timeline. Adapter must pass them through unchanged."""
        response_data = {
            "status": "swapped",
            "before_cfg": {"dataset_type": "spirals"},
            "after_cfg": {"dataset_type": "moons"},
            "arch_changes": {"input_delta": 2, "output_delta": 0},
            "pre_swap_snapshot_id": "snapshot_20260515T120000Z",
            "post_swap_snapshot_id": "snapshot_20260515T120001Z",
            "mode": "output_training_first",
        }
        adapter._client._request.return_value = {"data": response_data}
        result = adapter.swap_dataset_live(nn_dataset_type="moons")
        assert result["ok"] is True
        assert result["data"] == response_data

    def test_returns_cancelled_status_passthrough(self, adapter):
        """Cancelled-swap responses (cascor P2-1b) carry status=cancelled.
        The adapter doesn't distinguish — it's the callback layer's job
        to render the cancelled outcome."""
        adapter._client._request.return_value = {"data": {"status": "cancelled"}}
        result = adapter.swap_dataset_live(nn_dataset_type="moons")
        assert result["ok"] is True
        assert result["data"]["status"] == "cancelled"

    def test_drops_none_params(self, adapter):
        """Sidebar inputs left untouched come through as None — they
        must NOT be POSTed to cascor (would shadow whatever cascor's
        current value is)."""
        adapter._client._request.return_value = {"data": {}}
        adapter.swap_dataset_live(nn_dataset_type="moons", nn_dataset_elements=None, nn_dataset_noise=None)
        body = adapter._client._request.call_args.kwargs["json"]
        assert body == {"dataset_type": "moons"}, "None-valued params must be filtered out"

    def test_returns_error_on_cascor_failure(self, adapter):
        adapter._client._request.side_effect = JuniperCascorClientError("HTTP 502")
        result = adapter.swap_dataset_live(nn_dataset_type="moons")
        assert result["ok"] is False
        assert "HTTP 502" in result["error"]


class TestCancelSwapDatasetLive:
    def test_deletes_live_swap_endpoint(self, adapter):
        adapter._client._request.return_value = {"data": {"status": "cancel_requested"}}
        result = adapter.cancel_swap_dataset_live()
        assert result["ok"] is True
        adapter._client._request.assert_called_once_with("DELETE", "/training/dataset/live")

    def test_returns_error_on_404_no_swap(self, adapter):
        """Cascor returns 404 when no swap is in flight. The client wraps
        that as JuniperCascorClientError; the adapter surfaces it as
        ok=False so the callback layer can show a "no swap in flight"
        message (or just no-op the cancel)."""
        adapter._client._request.side_effect = JuniperCascorClientError("HTTP 404 — no swap in progress")
        result = adapter.cancel_swap_dataset_live()
        assert result["ok"] is False
        assert "404" in result["error"]

    def test_returns_error_on_other_failure(self, adapter):
        adapter._client._request.side_effect = JuniperCascorClientError("connection refused")
        result = adapter.cancel_swap_dataset_live()
        assert result["ok"] is False
        assert "connection refused" in result["error"]
