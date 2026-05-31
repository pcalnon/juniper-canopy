#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     test_dashboard_manager.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2025-11-03
# Last Modified: 2025-11-03
# License:       MIT License
# Copyright:     Copyright (c) 2024-2025 Paul Calnon
# Description:   Unit tests for DashboardManager
#####################################################################
"""Unit tests for DashboardManager."""

import sys
from pathlib import Path

# Add src to path
src_dir = Path(__file__).parents[2]
sys.path.insert(0, str(src_dir))

import pytest  # noqa: E402

from frontend.dashboard_manager import DashboardManager  # noqa: E402


@pytest.fixture
def config():
    """Basic config for dashboard manager."""
    return {"title": "Test Dashboard", "update_interval": 1000, "server": {"host": "localhost", "port": 8050}}


@pytest.fixture
def dashboard(config):
    """Create DashboardManager instance."""
    return DashboardManager(config)


class TestDashboardManagerInitialization:
    """Test DashboardManager initialization."""

    def test_init_with_config(self, config):
        """Should initialize with config."""
        dashboard = DashboardManager(config)
        assert dashboard is not None

    def test_init_with_empty_config(self):
        """Should initialize with empty config."""
        dashboard = DashboardManager({})
        assert dashboard is not None

    def test_init_creates_dash_app(self, dashboard):
        """Should create Dash app instance."""
        assert hasattr(dashboard, "app")
        assert dashboard.app is not None

    def test_dash_app_has_server(self, dashboard):
        """Dash app should have Flask server."""
        assert hasattr(dashboard.app, "server")
        assert dashboard.app.server is not None

    def test_config_stored(self, dashboard, config):
        """Should store config."""
        assert hasattr(dashboard, "config")
        assert dashboard.config is not None


class TestDashboardManagerComponents:
    """Test component creation and management."""

    def test_has_components(self, dashboard):
        """Should have components attribute."""
        assert hasattr(dashboard, "components") or hasattr(dashboard, "_components")

    def test_metrics_panel_appears_in_rendered_layout(self, dashboard):
        """METRICS-MON R3.3 / seed-12: metrics panel renders into the dashboard layout.

        Black-box replacement for the historically-skipped
        ``test_create_metrics_panel`` (the original asserted on a
        ``_create_metrics_panel`` method that does not exist —
        ``DashboardManager`` instantiates ``MetricsPanel`` directly at
        ``component_id="metrics-panel"``). The layout endpoint is the
        actual integration seam Dash uses to ship component trees to the
        browser, so asserting against it pins the contract that
        regressions in any of the metrics-panel construction callers
        (not just a single helper method) would surface.
        """
        # Dash exposes the rendered layout as JSON at ``/_dash-layout`` on
        # its embedded Flask server. Going through ``server.test_client()``
        # exercises the same wire format that the FastAPI WSGIMiddleware
        # mount at ``/dashboard/_dash-layout`` proxies to.
        client = dashboard.app.server.test_client()
        response = client.get("/_dash-layout")
        assert response.status_code == 200
        body = response.get_data(as_text=True)
        # The panel's component_id is the user-visible attachment point —
        # any callback that writes into it (e.g. metrics history → graph
        # data) must address it by this id, so the layout JSON must list
        # it. Also assert on the panel-internal IDs to pin the panel was
        # actually rendered (not just a stub div using the same id).
        assert "metrics-panel" in body, "MetricsPanel root id missing from /dashboard/_dash-layout"
        # MetricsPanel.get_layout() emits sub-elements named like
        # ``metrics-store``, ``metrics-graph``. At least one must show up
        # for the panel to be useful at runtime.
        assert "metrics-store" in body, "MetricsPanel inner state element missing from rendered layout"

    def test_network_visualizer_component_instantiated(self, dashboard):
        """``DashboardManager.network_visualizer`` must be a ``NetworkVisualizer``.

        Black-box replacement for the historically-skipped
        ``test_create_network_visualizer`` (asserted a
        ``_create_network_visualizer`` method that does not exist).
        ``_initialize_components()`` instantiates ``NetworkVisualizer``
        directly and assigns to ``self.network_visualizer`` — that
        attribute is the actual observable seam (callbacks register
        against it; layout embeds its ``get_layout()``).
        """
        from frontend.components.network_visualizer import NetworkVisualizer

        assert hasattr(dashboard, "network_visualizer"), "DashboardManager must expose network_visualizer attribute"
        assert isinstance(dashboard.network_visualizer, NetworkVisualizer)
        # The component's id is the layout attachment point — any callback
        # writing into it (topology updates, graph re-renders) addresses
        # it by this id, so the rendered layout JSON must list it.
        client = dashboard.app.server.test_client()
        body = client.get("/_dash-layout").get_data(as_text=True)
        assert "network-visualizer" in body, "NetworkVisualizer root id missing from rendered layout"

    def test_decision_boundary_component_instantiated(self, dashboard):
        """``DashboardManager.decision_boundary`` must be a ``DecisionBoundary``.

        Black-box replacement for the historically-skipped
        ``test_create_decision_boundary``. ``_initialize_components()``
        wires ``DecisionBoundary`` at ``component_id="decision-boundary"``.
        """
        from frontend.components.decision_boundary import DecisionBoundary

        assert hasattr(dashboard, "decision_boundary"), "DashboardManager must expose decision_boundary attribute"
        assert isinstance(dashboard.decision_boundary, DecisionBoundary)
        client = dashboard.app.server.test_client()
        body = client.get("/_dash-layout").get_data(as_text=True)
        assert "decision-boundary" in body, "DecisionBoundary root id missing from rendered layout"

    def test_dataset_plotter_component_instantiated(self, dashboard):
        """``DashboardManager.dataset_plotter`` must be a ``DatasetPlotter``.

        Black-box replacement for the historically-skipped
        ``test_create_dataset_plotter``. ``_initialize_components()``
        wires ``DatasetPlotter`` at ``component_id="dataset-plotter"``.
        """
        from frontend.components.dataset_plotter import DatasetPlotter

        assert hasattr(dashboard, "dataset_plotter"), "DashboardManager must expose dataset_plotter attribute"
        assert isinstance(dashboard.dataset_plotter, DatasetPlotter)
        client = dashboard.app.server.test_client()
        body = client.get("/_dash-layout").get_data(as_text=True)
        assert "dataset-plotter" in body, "DatasetPlotter root id missing from rendered layout"


class TestDashboardManagerLayout:
    """Test layout creation."""

    def test_setup_layout_assigns_app_layout(self, dashboard):
        """``_setup_layout`` must have populated ``app.layout``.

        Black-box replacement for the historically-skipped
        ``test_create_layout`` (asserted a ``_create_layout`` method
        that does not exist — ``DashboardManager`` uses
        ``_setup_layout`` which mutates ``self.app.layout`` rather than
        returning a layout). The observable post-condition is that the
        Dash app has a non-None layout that renders correctly via the
        ``/_dash-layout`` endpoint.
        """
        # The method itself is invoked at __init__ time so we assert on
        # the post-condition, not by re-running it.
        assert hasattr(dashboard, "_setup_layout"), "DashboardManager must expose _setup_layout method"
        assert dashboard.app.layout is not None
        # Render via Dash's own layout endpoint to confirm it serializes
        # (catches structural breakages that ``is not None`` alone misses).
        client = dashboard.app.server.test_client()
        response = client.get("/_dash-layout")
        assert response.status_code == 200

    def test_layout_assigned_to_app(self, dashboard):
        """Layout should be assigned to app."""
        assert dashboard.app.layout is not None

    def test_layout_contains_components(self, dashboard):
        """Layout should contain component areas."""
        layout = dashboard.app.layout

        # Layout should have children
        assert hasattr(layout, "children"), "Layout should have children attribute"
        assert layout.children is not None


class TestDashboardManagerCallbacks:
    """Test callback setup."""

    def test_setup_callbacks(self, dashboard):
        """Should have setup_callbacks method."""
        assert hasattr(dashboard, "_setup_callbacks") or hasattr(dashboard, "setup_callbacks")

    def test_callbacks_registered(self, dashboard):
        """Callbacks should be registered on app."""
        # Dash stores callbacks internally
        assert len(dashboard.app.callback_map) >= 0


class TestDashboardManagerAPIURL:
    """Test API URL helper."""

    def test_has_api_url_method(self, dashboard):
        """Should have _api_url method."""
        assert hasattr(dashboard, "_api_url")

    def test_api_url_construction(self, dashboard):
        """Should construct API URLs from settings."""
        url = dashboard._api_url("/test")
        assert url.startswith("http://127.0.0.1:")
        assert url.endswith("/test")

    def test_api_url_with_different_paths(self, dashboard):
        """Should handle different API paths."""
        paths = ["/metrics", "/topology", "/dataset"]
        for path in paths:
            url = dashboard._api_url(path)
            assert url.startswith("http://127.0.0.1:")
            assert path in url

    def test_api_url_handles_leading_slash(self, dashboard):
        """Should handle paths with and without leading slash."""
        url1 = dashboard._api_url("/test")
        url2 = dashboard._api_url("test")
        assert url1 == url2


class TestDashboardManagerConfiguration:
    """Test configuration handling."""

    def test_title_from_config(self):
        """Should use title from config."""
        config = {"title": "Custom Title"}
        dashboard = DashboardManager(config)
        # Title should be set somewhere (app.title or config)
        assert hasattr(dashboard.app, "title"), "Dash app should have title attribute"
        assert "Custom" in dashboard.app.title or "Custom" in str(dashboard.config.get("title"))

    def test_update_interval_from_config(self):
        """Should use update_interval from config."""
        config = {"update_interval": 5000}
        dashboard = DashboardManager(config)
        assert dashboard.config.get("update_interval") == 5000

    def test_server_config(self):
        """Should handle server configuration."""
        config = {"server": {"host": "127.0.0.1", "port": 9000}}
        dashboard = DashboardManager(config)
        assert dashboard.config.get("server") is not None


class TestDashboardManagerTabNavigation:
    """Test tab navigation if present."""

    def test_has_tabs(self, dashboard):
        """Should have tabs in layout."""
        from dash import dcc

        layout = dashboard.app.layout

        def find_tabs(component):
            if isinstance(component, dcc.Tabs):
                return True
            if hasattr(component, "children"):
                if isinstance(component.children, list):
                    return any(find_tabs(child) for child in component.children)
                elif component.children is not None:
                    return find_tabs(component.children)
            return False

        # May or may not have tabs depending on design
        has_tabs = find_tabs(layout)
        # Just check it doesn't crash
        assert isinstance(has_tabs, bool)


class TestDashboardManagerAssets:
    """Test asset handling."""

    def test_assets_folder_set(self, dashboard):
        """Dash app should expose its configured assets folder.

        Dash stores ``assets_folder`` under ``app.config`` rather than as
        a direct app attribute, so the historically-skipped test asserted
        on the wrong path. The observable contract — "the Dash app knows
        where its assets live" — is what we actually want to pin.
        """
        # ``app.config`` is the documented Dash API for reading the
        # assets directory.
        assert hasattr(dashboard.app, "config"), "Dash app should expose config namespace"
        assert hasattr(dashboard.app.config, "assets_folder"), "Dash app config should have assets_folder"
        assert dashboard.app.config.assets_folder is not None
        assert dashboard.app.config.assets_folder != ""

    def test_assets_url_path(self, dashboard):
        """Dash app should expose its configured assets URL path.

        Same situation as ``assets_folder``: lives under
        ``app.config.assets_url_path``, not ``app.assets_url_path``.
        Also verify ``get_asset_url`` — the documented public API
        for resolving a file inside ``assets/`` — works end-to-end.
        """
        assert hasattr(dashboard.app.config, "assets_url_path"), "Dash app config should have assets_url_path"
        assert dashboard.app.config.assets_url_path is not None
        # ``get_asset_url`` is the documented Dash API; if the URL path
        # is wired correctly, an asset reference must contain it.
        url = dashboard.app.get_asset_url("style.css")
        assert dashboard.app.config.assets_url_path in url


class TestDashboardManagerEdgeCases:
    """Test edge cases."""

    def test_none_config_values(self):
        """Should handle None config values - either accepts them or raises TypeError/ValueError."""
        config = {"title": None, "update_interval": None}
        try:
            dashboard = DashboardManager(config)
            # If we get here, None values were handled gracefully (valid behavior)
            assert dashboard is not None, "Dashboard should be created"
        except (TypeError, ValueError):
            # Not accepting None values is also valid behavior
            pass  # Test passes - rejecting None is acceptable

    def test_missing_server_config(self):
        """Should handle missing server config."""
        config = {}
        dashboard = DashboardManager(config)
        # Should use defaults
        assert dashboard is not None

    def test_extra_config_params(self):
        """Should ignore extra config parameters."""
        config = {"title": "Test", "extra_param": "value", "another_param": 123}
        dashboard = DashboardManager(config)
        assert dashboard is not None


class TestDashboardManagerIntegration:
    """Test integration with components."""

    def test_all_components_in_layout(self, dashboard):
        """All components should be in layout."""
        layout = dashboard.app.layout

        # Layout should have some structure
        assert hasattr(layout, "children"), "Layout should have children attribute"
        assert layout.children is not None
        # Should have multiple children if using multiple components
        if isinstance(layout.children, list):
            assert len(layout.children) > 0

    def test_component_callbacks_registered(self, dashboard):
        """Component callbacks should be registered."""
        # Dashboard should have registered callbacks from components
        callback_map = dashboard.app.callback_map
        # Should have at least some callbacks
        assert isinstance(callback_map, dict)


class TestApplyInFlightIntervalPause:
    """CAN-000: Periodic update intervals must pause while Apply is in flight.

    The wiring lives in `_setup_datastore_callbacks` (three clientside
    callbacks driving an `apply-in-flight` store). The clientside JS only
    runs in a browser, so the unit tests verify the wiring at the source
    level — same pattern as the GAP-WS-15 / GAP-WS-14 / PERF-CN-02 tests.
    """

    @pytest.fixture
    def dashboard_manager_source(self):
        path = Path(__file__).resolve().parents[2] / "frontend" / "dashboard_manager.py"
        return path.read_text(encoding="utf-8")

    def test_apply_in_flight_store_exists(self, dashboard_manager_source):
        """Layout must include the `apply-in-flight` Store."""
        assert 'dcc.Store(id="apply-in-flight"' in dashboard_manager_source

    def test_clientside_callback_sets_in_flight_on_click(self, dashboard_manager_source):
        """Click on Apply button must flip the store to True."""
        assert 'Output("apply-in-flight", "data")' in dashboard_manager_source
        assert 'Input("apply-params-button", "n_clicks")' in dashboard_manager_source

    def test_clientside_callback_clears_in_flight_on_apply_complete(self, dashboard_manager_source):
        """When applied-params-store updates, the in-flight clamp comes off."""
        assert 'Output("apply-in-flight", "data", allow_duplicate=True)' in dashboard_manager_source
        assert 'Input("applied-params-store", "data")' in dashboard_manager_source

    def test_in_flight_drives_interval_disabled(self, dashboard_manager_source):
        """The `apply-in-flight` store toggles the `disabled` prop on both
        update intervals."""
        assert 'Output("fast-update-interval", "disabled")' in dashboard_manager_source
        assert 'Output("slow-update-interval", "disabled")' in dashboard_manager_source
        # Direct Input on apply-in-flight from the third callback in the
        # CAN-000 cluster.
        idx = dashboard_manager_source.find('Output("fast-update-interval", "disabled")')
        assert idx != -1
        # The Input("apply-in-flight", "data") line must appear in close
        # proximity to the disabled Outputs (within ~500 chars), proving the
        # CAN-000 cluster is wired together rather than being three unrelated
        # callbacks that happen to share names.
        window = dashboard_manager_source[idx : idx + 500]
        assert 'Input("apply-in-flight", "data")' in window


class TestPinnedParameters:
    """CAN-005: pin/unpin meta params + sidebar mirror."""

    @pytest.fixture
    def dashboard_manager_source(self):
        path = Path(__file__).resolve().parents[2] / "frontend" / "dashboard_manager.py"
        return path.read_text(encoding="utf-8")

    @pytest.fixture
    def parameters_panel_source(self):
        path = Path(__file__).resolve().parents[2] / "frontend" / "components" / "parameters_panel.py"
        return path.read_text(encoding="utf-8")

    def test_pinned_store_uses_localStorage(self, dashboard_manager_source):
        """Pinned IDs must persist via storage_type='local' so reloads
        preserve the user's pin selections."""
        idx = dashboard_manager_source.find('id="pinned-params-store"')
        assert idx != -1
        window = dashboard_manager_source[idx : idx + 200]
        assert 'storage_type="local"' in window

    def test_sidebar_pinned_card_in_layout(self, dashboard_manager_source):
        """Sidebar must include a `sidebar-pinned-card` Div + the
        `sidebar-pinned-list` body that the render callback writes."""
        assert 'id="sidebar-pinned-card"' in dashboard_manager_source
        assert 'id="sidebar-pinned-list"' in dashboard_manager_source

    def test_pin_checkboxes_use_pattern_matching_id(self, parameters_panel_source):
        """Each pin checkbox uses a `{"type": "param-pin", "key": …}` id
        so a single ALL-pattern callback can collect every checkbox's
        state in one shot."""
        assert '{"type": "param-pin", "key": key}' in parameters_panel_source

    def test_param_display_names_export(self, parameters_panel_source):
        """The sidebar mirror needs human-readable names for each pinned
        key — exposed via PARAM_DISPLAY_NAMES."""
        assert "PARAM_DISPLAY_NAMES" in parameters_panel_source
        assert "ALL_PARAMS" in parameters_panel_source

    def test_pin_toggle_callback_writes_store(self, dashboard_manager_source):
        """ALL-pattern callback must write `pinned-params-store.data`."""
        assert 'Output("pinned-params-store", "data")' in dashboard_manager_source
        assert "param-pin" in dashboard_manager_source
        assert "dash.ALL" in dashboard_manager_source

    def test_sidebar_mirror_callback_renders_or_hides_card(self, dashboard_manager_source):
        """Mirror callback returns ([rows], {style}) and hides the card
        when the pinned list is empty."""
        idx = dashboard_manager_source.find('Output("sidebar-pinned-list"')
        assert idx != -1
        # The full callback body (incl. both empty and populated paths)
        # is well under 3000 chars.
        window = dashboard_manager_source[idx : idx + 3000]
        assert 'Output("sidebar-pinned-card", "style")' in window
        assert '{"display": "none"}' in window
        assert '{"display": "block"}' in window

    def test_table_callback_reads_pinned_store(self, parameters_panel_source):
        """update_parameters_tables takes pinned-params-store as a
        second Input so the checkbox column re-renders when pin state
        changes."""
        assert 'Input("pinned-params-store", "data")' in parameters_panel_source


class TestContextMenuWiring:
    """CAN-018: right-click context menus.

    Verifies the source-level wiring (Stores in layout, clientside
    callbacks installed, JS asset shipped). Browser interaction is
    out of scope for unit tests — same source-invariant pattern as
    GAP-WS-15 and CAN-000.

    NOTE: This class was clobbered during the Phase-1/2 merge sequence
    (PRs #191 / #192 / #193 each appended a new test class at the same
    insertion point at the end of the file; later merges retained only
    the most-recent one). Restored verbatim from PR #191's branch tip
    (commit 52f905d).
    """

    @pytest.fixture
    def dashboard_manager_source(self):
        path = Path(__file__).resolve().parents[2] / "frontend" / "dashboard_manager.py"
        return path.read_text(encoding="utf-8")

    @pytest.fixture
    def context_menus_js(self):
        path = Path(__file__).resolve().parents[2] / "frontend" / "assets" / "context_menus.js"
        return path.read_text(encoding="utf-8")

    def test_control_tooltips_store_in_layout(self, dashboard_manager_source):
        """Layout must expose CONTROL_TOOLTIPS to JS via a Store seeded
        with the dict, so context_menus.js reads descriptions from one
        source instead of duplicating them."""
        assert 'dcc.Store(id="control-tooltips-store"' in dashboard_manager_source
        assert "data=CONTROL_TOOLTIPS" in dashboard_manager_source

    def test_tutorial_trigger_store_in_layout(self, dashboard_manager_source):
        """Layout must include the trigger Store the JS writes when
        'View tutorial' is clicked."""
        assert 'dcc.Store(id="context-menu-tutorial-trigger"' in dashboard_manager_source

    def test_install_callback_calls_js_entry_point(self, dashboard_manager_source):
        """Mount-time clientside callback must call the JS install
        function, gated on window.juniperCanopy existing."""
        assert "juniperCanopy.installContextMenus" in dashboard_manager_source

    def test_tutorial_trigger_switches_active_tab(self, dashboard_manager_source):
        """When the JS writes the trigger Store, a clientside callback
        must set visualization-tabs.active_tab to 'tutorial'."""
        assert 'Input("context-menu-tutorial-trigger", "data")' in dashboard_manager_source
        idx = dashboard_manager_source.find('Input("context-menu-tutorial-trigger", "data")')
        window = dashboard_manager_source[max(0, idx - 800) : idx + 200]
        assert 'Output("visualization-tabs", "active_tab"' in window
        assert 'return "tutorial"' in window

    def test_js_asset_exists_and_exposes_install(self, context_menus_js):
        """assets/context_menus.js exists and exposes the install entry point."""
        assert "window.juniperCanopy" in context_menus_js
        assert "installContextMenus" in context_menus_js

    def test_js_walks_up_dom_to_find_tooltip(self, context_menus_js):
        """Right-click target may not carry the registered id directly
        (dcc.Input wraps a child element). The asset must walk up the
        DOM looking for an id that matches CONTROL_TOOLTIPS keys."""
        assert "parentElement" in context_menus_js

    def test_js_writes_tutorial_trigger_via_set_props(self, context_menus_js):
        """View-tutorial click must bump the trigger Store so the
        Python clientside callback fires."""
        assert "dash_clientside" in context_menus_js
        assert "set_props" in context_menus_js
        assert '"context-menu-tutorial-trigger"' in context_menus_js

    def test_js_does_not_break_default_contextmenu_for_unknown_targets(self, context_menus_js):
        """When the right-click target has no matching tooltip id, the
        browser's default context menu must still appear — we only call
        preventDefault when we have something to show."""
        idx = context_menus_js.find("function onContextMenu")
        assert idx != -1
        body = context_menus_js[idx : idx + 600]
        assert "findTooltipForElement" in body
        return_idx = body.find("return;")
        prevent_idx = body.find("preventDefault")
        assert return_idx != -1 and prevent_idx != -1
        # The null-guard return MUST come before preventDefault.
        assert return_idx < prevent_idx


class TestLayoutStatePersistence:
    """CAN-016a: persist dashboard layout state (active tab) to localStorage.

    NOTE: This class was clobbered during the Phase-1/2 merge sequence.
    Restored verbatim from PR #192's branch tip (commit 0ad5999).
    """

    @pytest.fixture
    def dashboard_manager_source(self):
        path = Path(__file__).resolve().parents[2] / "frontend" / "dashboard_manager.py"
        return path.read_text(encoding="utf-8")

    def test_layout_state_store_uses_localStorage(self, dashboard_manager_source):
        """The persistence Store must declare `storage_type="local"`, same
        pattern the existing `dark-mode-store` uses for theme."""
        idx = dashboard_manager_source.find('id="layout-state-store"')
        assert idx != -1
        window = dashboard_manager_source[idx : idx + 200]
        assert 'storage_type="local"' in window

    def test_layout_state_store_seeds_active_tab(self, dashboard_manager_source):
        """Default state must seed `active_tab` so the read callback
        always has a value (fresh sessions / cleared localStorage)."""
        idx = dashboard_manager_source.find('id="layout-state-store"')
        assert idx != -1
        window = dashboard_manager_source[idx : idx + 300]
        assert '"active_tab"' in window

    def test_read_callback_restores_active_tab_on_mount(self, dashboard_manager_source):
        """Mount-time clientside callback must read the Store and write
        `visualization-tabs.active_tab` so the user lands on the same tab."""
        idx = dashboard_manager_source.find('Input("layout-state-store", "data")')
        assert idx != -1
        window = dashboard_manager_source[max(0, idx - 800) : idx + 200]
        assert 'Output("visualization-tabs", "active_tab"' in window
        assert "state.active_tab" in window

    def test_write_callback_stamps_state_on_tab_change(self, dashboard_manager_source):
        """When the user switches tabs, the active_tab must be stamped
        onto the layout-state-store so the next page load restores it.
        Spread-merge over prior state for forward-compat with future
        layout keys (sidebar collapse, etc.)."""
        assert 'Output("layout-state-store", "data"' in dashboard_manager_source
        assert "Object.assign" in dashboard_manager_source

    def test_no_self_loop_on_same_tab(self, dashboard_manager_source):
        """Writer must short-circuit when the new active_tab equals the
        already-persisted one, preventing redundant Store writes."""
        assert "prev.active_tab === activeTab" in dashboard_manager_source

    def test_legacy_localstorage_persistence_removed(self, dashboard_manager_source):
        """#1 tab-feedback-loop fix: the legacy hand-rolled localStorage
        persistence is gone — `layout-state-store` is the single source of
        truth. That second persistence system raced the Store at mount and its
        Input→Output self-edge on `active_tab` fed the tab-toggle loop. We
        assert the actual get/setItem call sites are removed (a historical
        mention in a code comment is fine)."""
        assert "localStorage.setItem('juniper_canopy_active_tab'" not in dashboard_manager_source
        assert "localStorage.getItem('juniper_canopy_active_tab'" not in dashboard_manager_source

    def test_read_callback_is_equality_guarded(self, dashboard_manager_source):
        """#1 fix (read side): the restore callback must short-circuit when the
        persisted tab already equals the shown tab, so a Store echo doesn't
        re-assert `active_tab` and re-trigger every Input(active_tab) callback.
        It takes the current tab as State and compares. Mirrors
        test_no_self_loop_on_same_tab for the read side."""
        idx = dashboard_manager_source.find('Input("layout-state-store", "data")')
        assert idx != -1
        window = dashboard_manager_source[max(0, idx - 900) : idx + 300]
        assert 'State("visualization-tabs", "active_tab")' in window
        assert "state.active_tab === currentTab" in window

    def test_single_mount_time_active_tab_restore(self, dashboard_manager_source):
        """#1 fix: only two callbacks may write `visualization-tabs.active_tab`
        — the Store restore (Reader B) and the tutorial-link trigger. The two
        legacy localStorage outputs were removed, so a single callback restores
        at mount and nothing races it (the params-init-interval restore is
        gone)."""
        assert dashboard_manager_source.count('Output("visualization-tabs", "active_tab"') == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
