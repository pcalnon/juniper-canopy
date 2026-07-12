"""N2 degraded-mode indicator (training-runtime defects plan §4 I-1 / §5 T2).

The WS badge historically reported only the BROWSER↔canopy socket — in the
2026-07-10 incident it showed a green "WS: Connected" for 12+ hours while the
canopy→cascor relay behind it was dead. The badge now consumes a second
dimension (`stream-health-store`, polled from GET /api/stream_health) and
downgrades an otherwise-green badge to amber "Upstream degraded" /
"Upstream reconnecting". Browser-socket-open must not masquerade as
end-to-end healthy.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

src_dir = Path(__file__).parents[3]
sys.path.insert(0, str(src_dir))

import dash  # noqa: E402
import pytest  # noqa: E402

from frontend.components.connection_indicator import CONNECTION_INDICATOR_JS  # noqa: E402
from frontend.dashboard_manager import DashboardManager  # noqa: E402


@pytest.fixture
def dashboard():
    return DashboardManager({})


@pytest.fixture
def dashboard_manager_source():
    path = src_dir / "frontend" / "dashboard_manager.py"
    return path.read_text(encoding="utf-8")


@pytest.mark.unit
class TestBadgeUpstreamDimension:
    def test_js_takes_stream_health_argument(self):
        assert "function(wsStatus, streamHealth)" in CONNECTION_INDICATOR_JS

    def test_js_has_upstream_degraded_and_reconnecting_states(self):
        assert "WS: Upstream degraded" in CONNECTION_INDICATOR_JS
        assert "WS: Upstream reconnecting" in CONNECTION_INDICATOR_JS

    def test_js_downgrades_only_when_connected(self):
        """The upstream check must live inside the connected branch — an
        offline/reconnecting browser socket keeps its original states."""
        connected_idx = CONNECTION_INDICATOR_JS.find("if (wsStatus.connected)")
        upstream_idx = CONNECTION_INDICATOR_JS.find("streamHealth.overall")
        assert connected_idx != -1 and upstream_idx != -1
        assert upstream_idx > connected_idx
        # Original 4-state behavior intact.
        assert "WS: Demo" in CONNECTION_INDICATOR_JS
        assert "WS: Connected" in CONNECTION_INDICATOR_JS
        assert "WS: Reconnecting" in CONNECTION_INDICATOR_JS
        assert "WS: Offline" in CONNECTION_INDICATOR_JS


@pytest.mark.unit
class TestStreamHealthWiring:
    def test_stream_health_store_in_layout(self, dashboard_manager_source):
        assert 'dcc.Store(id="stream-health-store"' in dashboard_manager_source

    def test_badge_callback_consumes_stream_health(self, dashboard_manager_source):
        idx = dashboard_manager_source.find('Output("ws-connection-indicator", "children")')
        assert idx != -1
        window = dashboard_manager_source[idx : idx + 400]
        assert 'Input("ws-connection-status", "data")' in window
        assert 'Input("stream-health-store", "data")' in window

    def test_poll_callback_writes_stream_health_store(self, dashboard_manager_source):
        idx = dashboard_manager_source.find('Output("stream-health-store", "data")')
        assert idx != -1
        window = dashboard_manager_source[idx : idx + 300]
        assert 'Input("slow-update-interval", "n_intervals")' in window


@pytest.mark.unit
class TestStreamHealthHandler:
    def test_handler_returns_payload_on_ok(self, dashboard):
        payload = {"overall": "degraded", "relay": {"status": "degraded"}, "control": {}}
        mock_response = MagicMock(ok=True)
        mock_response.json.return_value = payload
        with patch("requests.get", return_value=mock_response):
            assert dashboard._update_stream_health_handler(1) == payload

    def test_handler_no_update_on_http_error(self, dashboard):
        mock_response = MagicMock(ok=False, status_code=503)
        with patch("requests.get", return_value=mock_response):
            assert dashboard._update_stream_health_handler(1) is dash.no_update

    def test_handler_no_update_on_exception(self, dashboard):
        with patch("requests.get", side_effect=ConnectionError("boom")):
            assert dashboard._update_stream_health_handler(1) is dash.no_update
