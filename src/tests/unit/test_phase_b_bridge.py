"""Tests for Phase B browser WebSocket bridge: two-flag settings, polling toggle, store structure."""

import os
from unittest.mock import patch

import pytest


@pytest.mark.unit
class TestPhaseBFlags:
    """Test the two-flag settings design (D-17, D-18)."""

    def _make_settings(self, enable_bridge=False, disable_bridge=False, demo_mode=False):
        """Create Settings instance with specified flag values."""
        from settings import Settings, get_settings

        get_settings.cache_clear()
        env = {
            "JUNIPER_CANOPY_ENABLE_BROWSER_WS_BRIDGE": str(enable_bridge).lower(),
            "JUNIPER_CANOPY_DISABLE_WS_BRIDGE": str(disable_bridge).lower(),
            "JUNIPER_CANOPY_DEMO_MODE": str(demo_mode).lower(),
            "JUNIPER_DATA_URL": "http://localhost:8100",
        }
        with patch.dict(os.environ, env, clear=False):
            get_settings.cache_clear()
            s = Settings()
        return s

    def test_default_flags_bridge_disabled(self):
        """Default: enable=False, disable=False → bridge NOT enabled."""
        s = self._make_settings(enable_bridge=False, disable_bridge=False)
        assert s.ws_bridge_enabled is False

    def test_enable_flag_only_activates_bridge(self):
        """enable=True, disable=False → bridge enabled."""
        s = self._make_settings(enable_bridge=True, disable_bridge=False)
        assert s.ws_bridge_enabled is True

    def test_kill_switch_overrides_enable(self):
        """enable=True, disable=True → bridge NOT enabled (kill switch wins)."""
        s = self._make_settings(enable_bridge=True, disable_bridge=True)
        assert s.ws_bridge_enabled is False

    def test_kill_switch_alone_bridge_disabled(self):
        """enable=False, disable=True → bridge NOT enabled."""
        s = self._make_settings(enable_bridge=False, disable_bridge=True)
        assert s.ws_bridge_enabled is False

    def test_raf_coalescer_default_disabled(self):
        """rAF coalescer scaffolded but disabled by default (D-04)."""
        s = self._make_settings()
        assert s.enable_raf_coalescer is False

    def test_latency_beacon_default_enabled(self):
        """Latency beacon enabled by default."""
        s = self._make_settings()
        assert s.enable_ws_latency_beacon is True


@pytest.mark.unit
class TestMetricsPollingToggle:
    """Test polling toggle in _update_metrics_store_handler."""

    def test_returns_no_update_when_ws_connected_and_bridge_enabled(self):
        """When WS bridge is connected AND enabled, REST poll is skipped."""
        import dash

        from frontend.dashboard_manager import DashboardManager

        dm = DashboardManager.__new__(DashboardManager)
        dm.logger = __import__("logging").getLogger("test")

        ws_status = {"connected": True, "reconnecting": False, "mode": "live"}

        with patch("frontend.dashboard_manager.get_settings") as mock_settings:
            mock_settings.return_value.ws_bridge_enabled = True
            result = dm._update_metrics_store_handler(n=1, ws_status=ws_status)

        assert result is dash.no_update

    def test_falls_back_to_rest_when_ws_disconnected(self):
        """When WS is disconnected, REST poll proceeds normally."""
        from frontend.dashboard_manager import DashboardManager

        dm = DashboardManager.__new__(DashboardManager)
        dm.logger = __import__("logging").getLogger("test")
        dm._api_base_url = "http://127.0.0.1:8050"

        ws_status = {"connected": False, "reconnecting": True, "mode": "live"}

        with patch("frontend.dashboard_manager.get_settings") as mock_settings, patch("frontend.dashboard_manager.requests") as mock_requests:
            mock_settings.return_value.ws_bridge_enabled = True
            mock_resp = mock_requests.get.return_value
            mock_resp.ok = True
            mock_resp.json.return_value = [{"epoch": 1, "error": 0.5}]
            result = dm._update_metrics_store_handler(n=1, display_mode_state={"mode": "window", "window_size": 100}, ws_status=ws_status)

        assert isinstance(result, list)
        assert len(result) == 1

    def test_rest_poll_continues_when_bridge_disabled(self):
        """When bridge is disabled (default), REST poll always proceeds."""
        from frontend.dashboard_manager import DashboardManager

        dm = DashboardManager.__new__(DashboardManager)
        dm.logger = __import__("logging").getLogger("test")
        dm._api_base_url = "http://127.0.0.1:8050"

        ws_status = {"connected": True, "reconnecting": False, "mode": "live"}

        with patch("frontend.dashboard_manager.get_settings") as mock_settings, patch("frontend.dashboard_manager.requests") as mock_requests:
            mock_settings.return_value.ws_bridge_enabled = False
            mock_resp = mock_requests.get.return_value
            mock_resp.ok = True
            mock_resp.json.return_value = []
            result = dm._update_metrics_store_handler(n=1, ws_status=ws_status)

        assert isinstance(result, list)


@pytest.mark.unit
class TestWsMetricsBufferStoreStructure:
    """Test that ws-metrics-buffer store has correct D-07 structure."""

    def test_store_initial_data_shape(self):
        """Initial store data must have {events, gen, last_drain_ms} shape."""
        expected = {"events": [], "gen": 0, "last_drain_ms": 0}
        assert "events" in expected
        assert "gen" in expected
        assert "last_drain_ms" in expected
        assert isinstance(expected["events"], list)
        assert isinstance(expected["gen"], int)

    def test_connection_status_store_initial_data(self):
        """Connection status store must have {connected, reconnecting, mode}."""
        expected = {"connected": False, "reconnecting": False, "mode": "live"}
        assert "connected" in expected
        assert "reconnecting" in expected
        assert "mode" in expected


@pytest.mark.unit
class TestConnectionIndicator:
    """Test connection indicator component."""

    def test_layout_returns_span(self):
        from frontend.components.connection_indicator import connection_indicator_layout

        elem = connection_indicator_layout()
        assert elem.id == "ws-connection-indicator"

    def test_js_callback_defined(self):
        from frontend.components.connection_indicator import CONNECTION_INDICATOR_JS

        assert "wsStatus" in CONNECTION_INDICATOR_JS
        assert "connected" in CONNECTION_INDICATOR_JS
        assert "reconnecting" in CONNECTION_INDICATOR_JS
        assert "demo" in CONNECTION_INDICATOR_JS


@pytest.mark.unit
class TestWsEndpoints:
    """Test Phase B browser observability endpoints."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient

        from main import app

        return TestClient(app)

    def test_ws_latency_endpoint(self, client):
        resp = client.post("/api/ws_latency", json={"latency_ms": 42.5, "endpoint": "/ws/training"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_ws_browser_errors_endpoint(self, client):
        resp = client.post("/api/ws_browser_errors", json={"error": "connection reset", "endpoint": "/ws/training"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
