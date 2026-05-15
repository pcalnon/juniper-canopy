"""P2-4 (Issue #3) — Canopy ``/api/admin/experimental_functions`` proxy routes.

Two layers:

1. ``demo_mode.JuniperCanopyDemo`` get/set methods mirror the cascor wire
   shape so the canopy backend route handler doesn't need to special-case
   demo mode (same pattern as Issue #3 Phase 1 dataset stage/cancel).

2. The FastAPI routes ``GET / POST /api/admin/experimental_functions``
   return ``{"status": "success", "data": {"enabled": bool}}`` on success
   and 502 on backend rejection, matching the established proxy-route
   contract (e.g., ``/api/stage_dataset``).

The Dash callback wiring is exercised separately via the dashboard
component tests in ``test_experimental_functions_callbacks.py``.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Layer 1 — demo backend parity
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestDemoExperimentalFunctions:
    """Demo mode tracks the gate locally; the route returns the demo value
    so the UI works without cascor."""

    def test_get_default_is_false(self):
        """A freshly-constructed demo simulator reports the gate as closed —
        the F2.10 safe default."""
        from demo_mode import DemoMode

        demo = DemoMode()
        result = demo.get_experimental_functions()
        assert result == {"ok": True, "enabled": False}

    def test_set_then_get_round_trips(self):
        from demo_mode import DemoMode

        demo = DemoMode()
        set_result = demo.set_experimental_functions(True)
        assert set_result == {"ok": True, "enabled": True}
        get_result = demo.get_experimental_functions()
        assert get_result == {"ok": True, "enabled": True}

    def test_set_false_clears(self):
        from demo_mode import DemoMode

        demo = DemoMode()
        demo.set_experimental_functions(True)
        demo.set_experimental_functions(False)
        result = demo.get_experimental_functions()
        assert result["enabled"] is False


# ---------------------------------------------------------------------------
# Layer 2 — FastAPI routes
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestExperimentalFunctionsRoutes:
    """The proxy routes mock ``main.backend`` directly so the test pins the
    route contract without spinning up cascor or the demo simulator."""

    def _get_client(self):
        from fastapi.testclient import TestClient

        from main import app

        return TestClient(app)

    def test_get_returns_enabled_true_from_backend(self):
        client = self._get_client()
        with patch("main.backend") as mock_backend:
            mock_backend.get_experimental_functions.return_value = {"ok": True, "enabled": True}
            resp = client.get("/api/admin/experimental_functions")
        assert resp.status_code == 200
        assert resp.json() == {"status": "success", "data": {"enabled": True}}

    def test_get_returns_enabled_false_from_backend(self):
        client = self._get_client()
        with patch("main.backend") as mock_backend:
            mock_backend.get_experimental_functions.return_value = {"ok": True, "enabled": False}
            resp = client.get("/api/admin/experimental_functions")
        assert resp.status_code == 200
        assert resp.json()["data"]["enabled"] is False

    def test_get_returns_502_on_backend_rejection(self):
        """When ``backend.get_experimental_functions`` returns ``ok=False``,
        the route surfaces 502 — the Dash callback treats this as "cascor
        unreachable, show toggle as OFF with a warning toast"."""
        client = self._get_client()
        with patch("main.backend") as mock_backend:
            mock_backend.get_experimental_functions.return_value = {"ok": False, "error": "connection refused"}
            resp = client.get("/api/admin/experimental_functions")
        assert resp.status_code == 502
        assert "connection refused" in resp.json()["error"]

    def test_post_forwards_enabled_true(self):
        client = self._get_client()
        with patch("main.backend") as mock_backend:
            mock_backend.set_experimental_functions.return_value = {"ok": True, "enabled": True}
            resp = client.post("/api/admin/experimental_functions", json={"enabled": True})
        assert resp.status_code == 200
        assert resp.json() == {"status": "success", "data": {"enabled": True}}
        mock_backend.set_experimental_functions.assert_called_once_with(True)

    def test_post_forwards_enabled_false(self):
        client = self._get_client()
        with patch("main.backend") as mock_backend:
            mock_backend.set_experimental_functions.return_value = {"ok": True, "enabled": False}
            resp = client.post("/api/admin/experimental_functions", json={"enabled": False})
        assert resp.status_code == 200
        mock_backend.set_experimental_functions.assert_called_once_with(False)

    def test_post_returns_server_authoritative_override(self):
        """F2.10: the response reflects cascor's authoritative state, even
        if it differs from the request. The Dash callback layer detects
        the mismatch and shows a warning toast + reverts the Switch."""
        client = self._get_client()
        with patch("main.backend") as mock_backend:
            # User requests True, cascor overrides to False.
            mock_backend.set_experimental_functions.return_value = {"ok": True, "enabled": False}
            resp = client.post("/api/admin/experimental_functions", json={"enabled": True})
        assert resp.status_code == 200
        # Response carries the AUTHORITATIVE value, not the request.
        assert resp.json()["data"]["enabled"] is False

    def test_post_returns_502_on_backend_rejection(self):
        client = self._get_client()
        with patch("main.backend") as mock_backend:
            mock_backend.set_experimental_functions.return_value = {"ok": False, "error": "HTTP 503"}
            resp = client.post("/api/admin/experimental_functions", json={"enabled": True})
        assert resp.status_code == 502
        assert "HTTP 503" in resp.json()["error"]

    def test_post_missing_enabled_field_returns_422(self):
        """Pydantic validation: ``enabled`` is required by
        ``ExperimentalFunctionsRequest``."""
        client = self._get_client()
        resp = client.post("/api/admin/experimental_functions", json={})
        assert resp.status_code == 422
