#!/usr/bin/env python
"""
Unit tests for CassandraPanel frontend component (P3-7).

Tests:
- Layout contains expected components (status badge, cluster card, schema card)
- _render_hosts_table() helper renders correctly
- _api_url() helper builds correct URLs
- Callback returns all expected outputs
- Status badge colors match status values
- Error handling for failed API calls
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

src_dir = Path(__file__).parents[3]
sys.path.insert(0, str(src_dir))


@pytest.fixture
def panel_config():
    """Basic config for CassandraPanel."""
    return {
        "interval_ms": 5000,
        "api_timeout": 3,
    }


@pytest.fixture
def panel(panel_config):
    """Create CassandraPanel instance."""
    from frontend.components.cassandra_panel import CassandraPanel

    return CassandraPanel(panel_config, component_id="test-cassandra-panel")


class TestCassandraPanelInitialization:
    """Test CassandraPanel initialization."""

    @pytest.mark.unit
    def test_init_with_default_config(self):
        """Should initialize with empty config."""
        from frontend.components.cassandra_panel import CassandraPanel

        panel = CassandraPanel({})
        assert panel is not None
        assert panel.component_id == "cassandra-panel"

    @pytest.mark.unit
    def test_init_with_custom_id(self, panel_config):
        """Should initialize with custom component ID."""
        from frontend.components.cassandra_panel import CassandraPanel

        panel = CassandraPanel(panel_config, component_id="custom-cassandra")
        assert panel.component_id == "custom-cassandra"

    @pytest.mark.unit
    def test_init_sets_interval(self, panel_config):
        """Should set interval from config."""
        from frontend.components.cassandra_panel import CassandraPanel

        panel = CassandraPanel(panel_config)
        assert panel.interval_ms == 5000

    @pytest.mark.unit
    def test_init_sets_api_timeout(self, panel_config):
        """Should set api_timeout from config."""
        from frontend.components.cassandra_panel import CassandraPanel

        panel = CassandraPanel(panel_config)
        assert panel.api_timeout == 3

    @pytest.mark.unit
    def test_init_uses_default_interval(self):
        """Should use default interval if not in config."""
        from frontend.components.cassandra_panel import (
            DEFAULT_REFRESH_INTERVAL_MS,
            CassandraPanel,
        )

        panel = CassandraPanel({})
        assert panel.interval_ms == DEFAULT_REFRESH_INTERVAL_MS

    @pytest.mark.unit
    def test_init_uses_default_timeout(self):
        """Should use default timeout if not in config."""
        from frontend.components.cassandra_panel import (
            DEFAULT_API_TIMEOUT_SECONDS,
            CassandraPanel,
        )

        panel = CassandraPanel({})
        assert panel.api_timeout == DEFAULT_API_TIMEOUT_SECONDS


class TestCassandraPanelLayout:
    """Test CassandraPanel layout generation."""

    @pytest.mark.unit
    def test_get_layout_returns_div(self, panel):
        """get_layout should return Dash Div."""
        from dash import html

        layout = panel.get_layout()
        assert layout is not None
        assert isinstance(layout, html.Div)

    @pytest.mark.unit
    def test_layout_contains_interval(self, panel):
        """Layout should contain interval component for auto-refresh."""
        from dash import dcc

        layout = panel.get_layout()

        def find_intervals(component):
            intervals = []
            if isinstance(component, dcc.Interval):
                intervals.append(component)
            if hasattr(component, "children"):
                if isinstance(component.children, list):
                    for child in component.children:
                        intervals.extend(find_intervals(child))
                elif component.children is not None:
                    intervals.extend(find_intervals(component.children))
            return intervals

        intervals = find_intervals(layout)
        assert len(intervals) > 0
        assert intervals[0].interval == panel.interval_ms

    @pytest.mark.unit
    def test_layout_contains_status_badge(self, panel):
        """Layout should contain status badge."""
        import dash_bootstrap_components as dbc

        layout = panel.get_layout()

        def find_badges(component):
            badges = []
            if isinstance(component, dbc.Badge):
                badges.append(component)
            if hasattr(component, "children"):
                if isinstance(component.children, list):
                    for child in component.children:
                        badges.extend(find_badges(child))
                elif component.children is not None:
                    badges.extend(find_badges(component.children))
            return badges

        badges = find_badges(layout)
        badge_ids = [b.id for b in badges if hasattr(b, "id") and b.id]
        assert any("status-badge" in str(bid) for bid in badge_ids)

    @pytest.mark.unit
    def test_layout_contains_cluster_card(self, panel):
        """Layout should contain cluster overview card."""
        import dash_bootstrap_components as dbc

        layout = panel.get_layout()

        def find_cards(component):
            cards = []
            if isinstance(component, dbc.Card):
                cards.append(component)
            if hasattr(component, "children"):
                if isinstance(component.children, list):
                    for child in component.children:
                        cards.extend(find_cards(child))
                elif component.children is not None:
                    cards.extend(find_cards(component.children))
            return cards

        cards = find_cards(layout)
        assert len(cards) >= 2

    @pytest.mark.unit
    def test_layout_contains_schema_card(self, panel):
        """Layout should contain schema overview card."""
        import dash_bootstrap_components as dbc
        from dash import html

        layout = panel.get_layout()

        def find_text_containing(component, text):
            found = []
            if isinstance(component, html.H5) and (hasattr(component, "children") and text in str(component.children)):
                found.append(component)
            if hasattr(component, "children"):
                if isinstance(component.children, list):
                    for child in component.children:
                        found.extend(find_text_containing(child, text))
                elif component.children is not None:
                    found.extend(find_text_containing(component.children, text))
            return found

        schema_headers = find_text_containing(layout, "Schema")
        assert len(schema_headers) > 0


class TestCassandraPanelRenderHostsTable:
    """Test _render_hosts_table() helper method."""

    @pytest.mark.unit
    def test_render_hosts_table_empty_list(self, panel):
        """Should render 'No hosts available' for empty list."""
        from dash import html

        result = panel._render_hosts_table([])

        assert isinstance(result, html.P)
        assert "No hosts available" in str(result.children)

    @pytest.mark.unit
    def test_render_hosts_table_single_host(self, panel):
        """Should render table for single host."""
        import dash_bootstrap_components as dbc

        hosts = [
            {
                "address": "192.168.1.100",
                "datacenter": "dc1",
                "rack": "rack1",
                "status": "UP",
            }
        ]

        result = panel._render_hosts_table(hosts)

        assert isinstance(result, dbc.Table)

    @pytest.mark.unit
    def test_render_hosts_table_multiple_hosts(self, panel):
        """Should render table for multiple hosts."""
        import dash_bootstrap_components as dbc

        hosts = [
            {"address": "192.168.1.100", "datacenter": "dc1", "rack": "rack1", "status": "UP"},
            {"address": "192.168.1.101", "datacenter": "dc1", "rack": "rack2", "status": "UP"},
            {"address": "192.168.1.102", "datacenter": "dc2", "rack": "rack1", "status": "DOWN"},
        ]

        result = panel._render_hosts_table(hosts)

        assert isinstance(result, dbc.Table)

    @pytest.mark.unit
    def test_render_hosts_table_missing_fields(self, panel):
        """Should handle hosts with missing fields."""
        import dash_bootstrap_components as dbc

        hosts = [
            {"address": "192.168.1.100"},
        ]

        result = panel._render_hosts_table(hosts)

        assert isinstance(result, dbc.Table)


class TestCassandraPanelApiUrl:
    """Test _api_url() helper method."""

    @pytest.mark.unit
    def test_api_url_strips_leading_slash(self, panel):
        """_api_url should strip leading slash for relative path."""
        result = panel._api_url("/api/v1/cassandra/status")
        assert result == "api/v1/cassandra/status"

    @pytest.mark.unit
    def test_api_url_handles_no_leading_slash(self, panel):
        """_api_url should handle path without leading slash."""
        result = panel._api_url("api/v1/cassandra/status")
        assert result == "api/v1/cassandra/status"


class TestCassandraPanelStatusColors:
    """Test status badge color mapping."""

    @pytest.mark.unit
    def test_status_colors_up(self, panel):
        """UP status should map to success color."""
        assert panel.STATUS_COLORS["UP"] == "success"

    @pytest.mark.unit
    def test_status_colors_down(self, panel):
        """DOWN status should map to danger color."""
        assert panel.STATUS_COLORS["DOWN"] == "danger"

    @pytest.mark.unit
    def test_status_colors_disabled(self, panel):
        """DISABLED status should map to secondary color."""
        assert panel.STATUS_COLORS["DISABLED"] == "secondary"

    @pytest.mark.unit
    def test_status_colors_unavailable(self, panel):
        """UNAVAILABLE status should map to warning color."""
        assert panel.STATUS_COLORS["UNAVAILABLE"] == "warning"

    @pytest.mark.unit
    def test_mode_colors_demo(self, panel):
        """DEMO mode should map to info color."""
        assert panel.MODE_COLORS["DEMO"] == "info"

    @pytest.mark.unit
    def test_mode_colors_live(self, panel):
        """LIVE mode should map to success color."""
        assert panel.MODE_COLORS["LIVE"] == "success"

    @pytest.mark.unit
    def test_mode_colors_disabled(self, panel):
        """DISABLED mode should map to secondary color."""
        assert panel.MODE_COLORS["DISABLED"] == "secondary"


class TestCassandraPanelCallbacks:
    """Test callback registration and execution."""

    @pytest.mark.unit
    def test_register_callbacks_creates_callback(self, panel):
        """register_callbacks should register the update callback."""
        mock_app = Mock()
        mock_app.callback = Mock(return_value=lambda f: f)

        panel.register_callbacks(mock_app)

        assert hasattr(panel, "_cb_update_cassandra_panel")
        mock_app.callback.assert_called_once()

    @pytest.mark.unit
    def test_callback_returns_expected_outputs(self, panel):
        """Callback should return expected number of outputs."""
        mock_app = Mock()
        mock_app.callback = Mock(return_value=lambda f: f)

        panel.register_callbacks(mock_app)

        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "status": "UP",
                "mode": "DEMO",
                "contact_points": ["127.0.0.1"],
                "keyspace": "test_keyspace",
                "hosts": [],
            }
            mock_get.return_value = mock_response

            result = panel._cb_update_cassandra_panel(0)

            assert len(result) == 11

    @pytest.mark.unit
    def test_callback_handles_api_success(self, panel):
        """Callback should correctly parse successful API response."""
        mock_app = Mock()
        mock_app.callback = Mock(return_value=lambda f: f)

        panel.register_callbacks(mock_app)

        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "status": "UP",
                "mode": "DEMO",
                "contact_points": ["192.168.1.100", "192.168.1.101"],
                "keyspace": "juniper_canopy",
                "hosts": [{"address": "192.168.1.100", "datacenter": "dc1", "rack": "rack1", "status": "UP"}],
            }
            mock_get.return_value = mock_response

            result = panel._cb_update_cassandra_panel(1)

            status_text, status_color, mode_text, mode_color = result[:4]
            assert status_text == "UP"
            assert status_color == "success"
            assert mode_text == "DEMO"
            assert mode_color == "info"


class TestCassandraPanelErrorHandling:
    """Test error handling for failed API calls."""

    @pytest.mark.unit
    def test_callback_handles_connection_timeout(self, panel):
        """Callback should handle connection timeout."""
        import requests

        mock_app = Mock()
        mock_app.callback = Mock(return_value=lambda f: f)

        panel.register_callbacks(mock_app)

        with patch("requests.get") as mock_get:
            mock_get.side_effect = requests.exceptions.Timeout("Connection timed out")

            result = panel._cb_update_cassandra_panel(0)

            error_area = result[-1]
            assert error_area is not None

    @pytest.mark.unit
    def test_callback_handles_connection_error(self, panel):
        """Callback should handle connection error."""
        import requests

        mock_app = Mock()
        mock_app.callback = Mock(return_value=lambda f: f)

        panel.register_callbacks(mock_app)

        with patch("requests.get") as mock_get:
            mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")

            result = panel._cb_update_cassandra_panel(0)

            error_area = result[-1]
            assert error_area is not None

    @pytest.mark.unit
    def test_callback_handles_http_503(self, panel):
        """Callback should handle HTTP 503 (service unavailable)."""
        mock_app = Mock()
        mock_app.callback = Mock(return_value=lambda f: f)

        panel.register_callbacks(mock_app)

        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 503
            mock_get.return_value = mock_response

            result = panel._cb_update_cassandra_panel(0)

            status_text = result[0]
            assert status_text == "DISABLED"

    @pytest.mark.unit
    def test_callback_handles_http_error(self, panel):
        """Callback should handle generic HTTP error."""
        mock_app = Mock()
        mock_app.callback = Mock(return_value=lambda f: f)

        panel.register_callbacks(mock_app)

        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 500
            mock_get.return_value = mock_response

            result = panel._cb_update_cassandra_panel(0)

            error_area = result[-1]
            assert error_area is not None

    @pytest.mark.unit
    def test_callback_handles_json_decode_error(self, panel):
        """Callback should handle JSON decode error."""
        mock_app = Mock()
        mock_app.callback = Mock(return_value=lambda f: f)

        panel.register_callbacks(mock_app)

        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.side_effect = ValueError("Invalid JSON")
            mock_get.return_value = mock_response

            result = panel._cb_update_cassandra_panel(0)

            error_area = result[-1]
            assert error_area is not None

    @pytest.mark.unit
    def test_callback_handles_metrics_timeout_gracefully(self, panel):
        """Callback should handle metrics timeout without crashing."""
        import requests

        mock_app = Mock()
        mock_app.callback = Mock(return_value=lambda f: f)

        panel.register_callbacks(mock_app)

        def mock_get_side_effect(url, timeout=None):
            if "status" in url:
                response = Mock()
                response.status_code = 200
                response.json.return_value = {
                    "status": "UP",
                    "mode": "DEMO",
                    "contact_points": [],
                    "keyspace": "test",
                    "hosts": [],
                }
                return response
            else:
                raise requests.exceptions.Timeout("Metrics timeout")

        with patch("requests.get", side_effect=mock_get_side_effect):
            result = panel._cb_update_cassandra_panel(0)
            assert len(result) == 11


class TestCassandraPanelComponentIds:
    """Test component ID generation."""

    @pytest.mark.unit
    def test_component_ids_use_panel_id(self, panel):
        """Component IDs should include the panel's component_id."""
        layout = panel.get_layout()

        assert layout.id == "test-cassandra-panel"

    @pytest.mark.unit
    def test_interval_id_includes_component_id(self, panel):
        """Interval ID should include component_id."""
        from dash import dcc

        layout = panel.get_layout()

        def find_interval_id(component):
            if isinstance(component, dcc.Interval):
                return component.id
            if hasattr(component, "children"):
                if isinstance(component.children, list):
                    for child in component.children:
                        result = find_interval_id(child)
                        if result:
                            return result
                elif component.children is not None:
                    return find_interval_id(component.children)
            return None

        interval_id = find_interval_id(layout)
        assert "test-cassandra-panel" in interval_id
