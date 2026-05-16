"""P2-5 (Issue #3) — Canopy ``/api/live_dataset_swap`` proxy routes.

Two layers:

1. ``demo_mode.DemoMode`` swap_dataset_live + cancel_swap_dataset_live —
   demo parity so the UI works without cascor.

2. The FastAPI routes ``POST / DELETE /api/live_dataset_swap`` mirror the
   existing ``/api/stage_dataset`` contract: 200 with ``{"status":
   "success", "data": {...}}`` on success, 502 on backend rejection.

The Dash callback wiring is exercised separately via direct handler-
invocation tests against ``DashboardManager`` (no Playwright per the
``project_playwright_dash_react_input_gap`` memory).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Layer 1 — demo backend parity
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestDemoSwapDatasetLive:
    """Demo mode fabricates a §3.3-shaped response so the canopy UI can
    exercise the full success flow without cascor."""

    def test_swap_returns_swapped_status(self):
        from demo_mode import DemoMode

        demo = DemoMode()
        result = demo.swap_dataset_live(dataset_type="moons", n_samples=200)
        assert result["ok"] is True
        assert result["data"]["status"] == "swapped"
        assert result["data"]["after_cfg"]["dataset_type"] == "moons"

    def test_swap_returns_arch_changes_skeleton(self):
        """Demo doesn't have a real network to resize; arch_changes is
        zero-delta but structurally complete so the canopy callback can
        parse it without special-casing demo."""
        from demo_mode import DemoMode

        demo = DemoMode()
        result = demo.swap_dataset_live(dataset_type="moons")
        arch = result["data"]["arch_changes"]
        for key in ("input_delta", "output_delta", "hidden_preserved", "appended_nodes", "prepended_layers", "abandoned_candidate_pool_size", "active_output_dim"):
            assert key in arch, f"demo response missing arch_changes field {key!r}"

    def test_swap_returns_demo_snapshot_ids(self):
        from demo_mode import DemoMode

        demo = DemoMode()
        result = demo.swap_dataset_live(dataset_type="moons")
        assert result["data"]["pre_swap_snapshot_id"] == "demo_snapshot_pre"
        assert result["data"]["post_swap_snapshot_id"] == "demo_snapshot_post"

    def test_swap_with_no_config_rejects(self):
        """Demo refuses an empty config — mirrors cascor's behaviour
        (cascor would reject with 422 dim-mismatch or similar)."""
        from demo_mode import DemoMode

        demo = DemoMode()
        result = demo.swap_dataset_live()
        assert result["ok"] is False

    def test_cancel_returns_no_swap_in_progress(self):
        """Demo has no real in-flight HTTP request; cancel is a no-op
        that returns ok=False mirroring cascor's 404."""
        from demo_mode import DemoMode

        demo = DemoMode()
        result = demo.cancel_swap_dataset_live()
        assert result["ok"] is False
        assert "no_swap_in_progress" in result["error"]


# ---------------------------------------------------------------------------
# Layer 2 — FastAPI routes
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestLiveDatasetSwapRoutes:
    def _get_client(self):
        from fastapi.testclient import TestClient

        from main import app

        return TestClient(app)

    def test_post_returns_success_data_on_swap(self):
        client = self._get_client()
        swap_data = {"status": "swapped", "arch_changes": {"input_delta": 2}, "pre_swap_snapshot_id": "snap_pre"}
        with patch("main.backend") as mock_backend:
            mock_backend.swap_dataset_live.return_value = {"ok": True, "data": swap_data, "config": {"dataset_type": "moons"}}
            resp = client.post("/api/live_dataset_swap", json={"nn_dataset_type": "moons", "nn_dataset_elements": 200})
        assert resp.status_code == 200
        body = resp.json()
        assert body == {"status": "success", "data": swap_data}
        # Canopy-keys forwarded to the backend method as kwargs.
        mock_backend.swap_dataset_live.assert_called_once_with(nn_dataset_type="moons", nn_dataset_elements=200)

    def test_post_returns_cancelled_status_passthrough(self):
        """Cancelled-mid-flight swaps return status=cancelled in the data
        payload (cascor P2-1b). Route must pass through unchanged so the
        Dash callback renders the right outcome alert."""
        client = self._get_client()
        with patch("main.backend") as mock_backend:
            mock_backend.swap_dataset_live.return_value = {"ok": True, "data": {"status": "cancelled"}}
            resp = client.post("/api/live_dataset_swap", json={"nn_dataset_type": "moons"})
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "cancelled"

    def test_post_returns_502_on_backend_rejection(self):
        """Cascor's 403/409/422/504 all collapse to canopy 502 with the
        error string surfaced verbatim per spec §4.3."""
        client = self._get_client()
        with patch("main.backend") as mock_backend:
            mock_backend.swap_dataset_live.return_value = {"ok": False, "error": "HTTP 409 — swap already in progress"}
            resp = client.post("/api/live_dataset_swap", json={"nn_dataset_type": "moons"})
        assert resp.status_code == 502
        assert "swap already in progress" in resp.json()["error"]

    def test_post_handles_empty_body(self):
        """Empty body → all StageDatasetRequest fields default to None →
        backend gets an empty kwargs dict. Cascor will reject with 422
        if it actually requires a dim change; canopy passes through."""
        client = self._get_client()
        with patch("main.backend") as mock_backend:
            mock_backend.swap_dataset_live.return_value = {"ok": True, "data": {}}
            resp = client.post("/api/live_dataset_swap", json={})
        assert resp.status_code == 200
        mock_backend.swap_dataset_live.assert_called_once_with()

    def test_delete_returns_success_on_cancel(self):
        client = self._get_client()
        with patch("main.backend") as mock_backend:
            mock_backend.cancel_swap_dataset_live.return_value = {"ok": True, "data": {"status": "cancel_requested"}}
            resp = client.delete("/api/live_dataset_swap")
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "cancel_requested"

    def test_delete_returns_502_when_no_swap_in_flight(self):
        """Cascor 404 (no swap) surfaces as canopy 502 with the error
        string. The Dash cancel callback treats this as "Cancel had no
        effect" and leaves the UI alone."""
        client = self._get_client()
        with patch("main.backend") as mock_backend:
            mock_backend.cancel_swap_dataset_live.return_value = {"ok": False, "error": "HTTP 404 — no swap in progress"}
            resp = client.delete("/api/live_dataset_swap")
        assert resp.status_code == 502
        assert "no swap in progress" in resp.json()["error"]
