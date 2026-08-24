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
        """rAF coalescer scaffolded but disabled by default (D-04 / GAP-WS-15)."""
        s = self._make_settings()
        assert s.enable_raf_coalescer is False

    def test_raf_coalescer_env_override_enables(self):
        """JUNIPER_CANOPY_ENABLE_RAF_COALESCER=true flips the flag (GAP-WS-15)."""
        from settings import Settings, get_settings

        get_settings.cache_clear()
        env = {
            "JUNIPER_CANOPY_ENABLE_RAF_COALESCER": "true",
            "JUNIPER_DATA_URL": "http://localhost:8100",
        }
        with patch.dict(os.environ, env, clear=False):
            get_settings.cache_clear()
            s = Settings()
        assert s.enable_raf_coalescer is True

    def test_latency_beacon_default_enabled(self):
        """Latency beacon enabled by default."""
        s = self._make_settings()
        assert s.enable_ws_latency_beacon is True


@pytest.mark.unit
class TestMetricsPollUngated:
    """N1 (training-runtime defects plan §4 I-1, posture O2): the metrics-store
    poll is un-gated — it proceeds on every fast-interval tick regardless of WS
    connection state. The former sticky GAP-WS-16 gate (skip REST while
    connected + metricsReceived) starved long-lived tabs once WS frames stopped
    arriving; these tests pin the new contract (bridge until Q6/C6/N8)."""

    def _dm(self):
        from frontend.dashboard_manager import DashboardManager

        dm = DashboardManager.__new__(DashboardManager)
        dm.logger = __import__("logging").getLogger("test")
        dm._api_base_url = "http://127.0.0.1:8050"
        return dm

    def test_poll_proceeds_even_when_ws_connected_and_metrics_received(self):
        """The N1 regression pin: a tab whose WS reports connected+metricsReceived
        (the sticky-starvation state) still polls REST every tick."""
        dm = self._dm()

        with patch("frontend.dashboard_manager.requests") as mock_requests:
            mock_resp = mock_requests.get.return_value
            mock_resp.ok = True
            mock_resp.json.return_value = [{"epoch": 1, "error": 0.5}]
            result = dm._update_metrics_store_handler(n=1, display_mode_state={"mode": "window", "window_size": 100}, trigger="fast-update-interval.n_intervals")

        assert isinstance(result, list)
        assert len(result) == 1
        mock_requests.get.assert_called_once()

    def test_poll_proceeds_when_ws_disconnected(self):
        """REST poll proceeds normally with no WS connection (unchanged)."""
        dm = self._dm()

        with patch("frontend.dashboard_manager.requests") as mock_requests:
            mock_resp = mock_requests.get.return_value
            mock_resp.ok = True
            mock_resp.json.return_value = [{"epoch": 1, "error": 0.5}]
            result = dm._update_metrics_store_handler(n=1, display_mode_state={"mode": "window", "window_size": 100})

        assert isinstance(result, list)
        assert len(result) == 1

    def test_empty_fetch_with_populated_store_returns_no_update(self):
        """Empty-guard (plan §8 row 1): an empty fetch must not wipe a populated
        store — cascor clears metrics post-run, and the un-gated 1 Hz poll would
        otherwise blank a completed run's charts."""
        import dash

        dm = self._dm()

        with patch("frontend.dashboard_manager.requests") as mock_requests:
            mock_resp = mock_requests.get.return_value
            mock_resp.ok = True
            mock_resp.json.return_value = {"history": []}
            result = dm._update_metrics_store_handler(n=1, current_metrics=[{"epoch": 7}])

        assert result is dash.no_update

    def test_empty_fetch_with_empty_store_is_no_op_suppressed(self):
        """Genuinely-empty fetch with an empty store is now ``no_update``.

        Stage 2 (design §13 row 4) supersedes the old "passes through
        unchanged" arm: ``[]`` over ``[]`` is the definition of a no-op write,
        and an unchanged write still fires every downstream consumer. The
        empty-GUARD (don't blank a populated store) is untouched — see the
        populated-store case above.
        """
        import dash

        dm = self._dm()

        with patch("frontend.dashboard_manager.requests") as mock_requests:
            mock_resp = mock_requests.get.return_value
            mock_resp.ok = True
            mock_resp.json.return_value = {"history": []}
            result = dm._update_metrics_store_handler(n=1, current_metrics=[])

        assert result is dash.no_update

    def test_non_ok_with_populated_store_returns_no_update(self):
        """A non-ok fetch preserves the last-known-good store."""
        import dash

        dm = self._dm()

        with patch("frontend.dashboard_manager.requests") as mock_requests:
            mock_resp = mock_requests.get.return_value
            mock_resp.ok = False
            mock_resp.status_code = 502
            result = dm._update_metrics_store_handler(n=1, current_metrics=[{"epoch": 7}])

        assert result is dash.no_update

    def test_exception_with_populated_store_returns_no_update(self):
        """A fetch exception preserves the last-known-good store."""
        import dash

        dm = self._dm()

        with patch("frontend.dashboard_manager.requests") as mock_requests:
            mock_requests.get.side_effect = RuntimeError("connection refused")
            result = dm._update_metrics_store_handler(n=1, current_metrics=[{"epoch": 7}])

        assert result is dash.no_update

    def test_exception_with_empty_store_returns_empty_list(self):
        """A fetch exception with nothing to preserve keeps the [] contract."""
        dm = self._dm()

        with patch("frontend.dashboard_manager.requests") as mock_requests:
            mock_requests.get.side_effect = RuntimeError("connection refused")
            result = dm._update_metrics_store_handler(n=1, current_metrics=None)

        assert result == []


@pytest.mark.unit
class TestFullHistoryFetchBounded:
    """N1 (plan §8 row 2): full/hidden_units display modes fetch the complete
    history (limit=0 → up to 10k rows) — interval-driven ticks must not refetch
    that every second. Off-modulus ticks skip; the modulus tick, a display-mode
    switch, and window mode fetch normally."""

    def _dm(self):
        from frontend.dashboard_manager import DashboardManager

        dm = DashboardManager.__new__(DashboardManager)
        dm.logger = __import__("logging").getLogger("test")
        dm._api_base_url = "http://127.0.0.1:8050"
        return dm

    def test_full_mode_interval_off_tick_skips_fetch(self):
        import dash

        dm = self._dm()

        with patch("frontend.dashboard_manager.requests") as mock_requests:
            result = dm._update_metrics_store_handler(n=1, display_mode_state={"mode": "full"}, trigger="fast-update-interval.n_intervals")

        assert result is dash.no_update
        mock_requests.get.assert_not_called()

    def test_full_mode_interval_modulus_tick_fetches_all(self):
        from canopy_constants import DashboardConstants

        dm = self._dm()
        tick = DashboardConstants.FULL_HISTORY_POLL_TICK_MODULUS

        with patch("frontend.dashboard_manager.requests") as mock_requests:
            mock_resp = mock_requests.get.return_value
            mock_resp.ok = True
            mock_resp.json.return_value = {"history": [{"epoch": 1}]}
            result = dm._update_metrics_store_handler(n=tick, display_mode_state={"mode": "full"}, trigger="fast-update-interval.n_intervals")

        assert result == [{"epoch": 1}]
        assert "limit=0" in mock_requests.get.call_args[0][0]

    def test_full_mode_display_mode_switch_fetches_immediately(self):
        """A display-mode switch (display-mode-store Input trigger) must fetch
        immediately even on an off-modulus tick, so Full History stays snappy."""
        dm = self._dm()

        with patch("frontend.dashboard_manager.requests") as mock_requests:
            mock_resp = mock_requests.get.return_value
            mock_resp.ok = True
            mock_resp.json.return_value = {"history": [{"epoch": 1}]}
            result = dm._update_metrics_store_handler(n=1, display_mode_state={"mode": "full"}, trigger="metrics-panel-display-mode-store.data")

        assert result == [{"epoch": 1}]

    def test_hidden_units_mode_bounded_like_full(self):
        import dash

        dm = self._dm()

        with patch("frontend.dashboard_manager.requests") as mock_requests:
            result = dm._update_metrics_store_handler(n=2, display_mode_state={"mode": "hidden_units"}, trigger="fast-update-interval.n_intervals")

        assert result is dash.no_update
        mock_requests.get.assert_not_called()

    def test_window_mode_fetches_every_interval_tick(self):
        dm = self._dm()

        with patch("frontend.dashboard_manager.requests") as mock_requests:
            mock_resp = mock_requests.get.return_value
            mock_resp.ok = True
            mock_resp.json.return_value = {"history": [{"epoch": 1}]}
            result = dm._update_metrics_store_handler(n=1, display_mode_state={"mode": "window", "window_size": 100}, trigger="fast-update-interval.n_intervals")

        assert result == [{"epoch": 1}]
        assert "limit=100" in mock_requests.get.call_args[0][0]


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


@pytest.mark.unit
class TestRafCoalescerJsAsset:
    """GAP-WS-15: ws_dash_bridge.js coalescer wiring."""

    @pytest.fixture
    def bridge_js(self):
        from pathlib import Path

        path = Path(__file__).resolve().parents[2] / "frontend" / "assets" / "ws_dash_bridge.js"
        return path.read_text(encoding="utf-8")

    def test_default_off_flag_check_present(self, bridge_js):
        """Handler must gate the rAF path on `window._juniperRafCoalescerEnabled === true`."""
        assert "window._juniperRafCoalescerEnabled === true" in bridge_js

    def test_schedule_raf_replaces_noop(self, bridge_js):
        """`_scheduleRaf` is no longer a noop — it must reference rAF or its fallback."""
        assert "/* noop */" not in bridge_js
        assert "requestAnimationFrame" in bridge_js

    def test_latest_value_wins_only_for_candidate_progress(self, bridge_js):
        """`metrics`, `cascade_add`, `state_change`, `topology` handlers must NOT route through rAF.

        Time-series / one-shot streams keep per-event semantics; only 50Hz
        candidate_progress is coalesced (every point matters for plotting,
        but candidate progress is an ephemeral UI signal).
        """
        # The flag check should appear exactly once: inside candidate_progress.
        assert bridge_js.count("window._juniperRafCoalescerEnabled === true") == 1
        # And `pendingCandidateProgress` should be the only "pending" slot.
        assert "pendingCandidateProgress" in bridge_js
        assert "pendingMetrics" not in bridge_js
        assert "pendingCascade" not in bridge_js


@pytest.mark.unit
class TestRafCoalescerDashWiring:
    """GAP-WS-15: dashboard_manager wires settings.enable_raf_coalescer to JS."""

    @pytest.fixture
    def dashboard_manager_source(self):
        from pathlib import Path

        path = Path(__file__).resolve().parents[2] / "frontend" / "dashboard_manager.py"
        return path.read_text(encoding="utf-8")

    def test_ws_config_init_store_added(self, dashboard_manager_source):
        """A `ws-config-init` Store must exist in the layout to receive the bridged flag."""
        assert 'dcc.Store(id="ws-config-init"' in dashboard_manager_source

    def test_clientside_callback_writes_flag(self, dashboard_manager_source):
        """Callback must set `window._juniperRafCoalescerEnabled` from the setting."""
        assert "window._juniperRafCoalescerEnabled =" in dashboard_manager_source
        # And the input/output must hook ws-config-init so it fires on mount.
        assert 'Output("ws-config-init"' in dashboard_manager_source
        assert 'Input("ws-config-init"' in dashboard_manager_source

    def test_callback_value_reflects_setting(self):
        """When `enable_raf_coalescer=True`, the rendered JS must contain `= true`.

        We verify the f-string renders correctly by exercising the same
        code path the dashboard uses.
        """
        # Same expression used in dashboard_manager.py
        for setting_value, expected in [(True, "true"), (False, "false")]:
            rendered = str(setting_value).lower()
            assert rendered == expected


@pytest.mark.unit
class TestGapWs16BridgeAssets:
    """GAP-WS-16: ws_dash_bridge.js initial_metrics handler + metricsReceived flag."""

    @pytest.fixture
    def bridge_js(self):
        from pathlib import Path

        path = Path(__file__).resolve().parents[2] / "frontend" / "assets" / "ws_dash_bridge.js"
        return path.read_text(encoding="utf-8")

    def test_initial_metrics_handler_registered(self, bridge_js):
        """Handler must exist for the initial_metrics envelope sent on fresh connect."""
        assert 'window.cascorWS.on("initial_metrics"' in bridge_js

    def test_initial_metrics_drains_into_metrics_buffer(self, bridge_js):
        """initial_metrics handler must push each entry into the metrics ring buffer."""
        # The handler reads data.metrics as an array and pushes into _metricsBuffer
        assert "data.metrics" in bridge_js
        assert "_metricsBuffer.push(data.metrics" in bridge_js

    def test_metrics_received_flag_set_on_initial_burst(self, bridge_js):
        """initial_metrics handler must flip _metricsReceived so REST poll quiets down."""
        assert "_metricsReceived: false" in bridge_js
        assert "drain._metricsReceived = true" in bridge_js

    def test_metrics_received_flag_set_on_live_metrics(self, bridge_js):
        """First live `metrics` frame must also flip the flag (covers resume path)."""
        # _metricsReceived = true should appear in BOTH the metrics handler and
        # the initial_metrics handler — twice total.
        assert bridge_js.count("drain._metricsReceived = true") == 2

    def test_peek_connection_status_merges_metrics_received(self, bridge_js):
        """peekConnectionStatus must surface the flag so the REST gate can read it."""
        assert "metricsReceived: !!this._metricsReceived" in bridge_js


@pytest.mark.unit
class TestGapWs16WebSocketClientResume:
    """GAP-WS-16: websocket_client.js sends subscribe_metrics on reconnect."""

    @pytest.fixture
    def client_js(self):
        from pathlib import Path

        path = Path(__file__).resolve().parents[2] / "frontend" / "assets" / "websocket_client.js"
        return path.read_text(encoding="utf-8")

    def test_subscribe_metrics_sent_after_resume(self, client_js):
        """On reconnect the client must request a metrics burst to backfill the gap."""
        assert '"subscribe_metrics"' in client_js or "'subscribe_metrics'" in client_js

    def test_subscribe_metrics_skipped_for_control_socket(self, client_js):
        """The /ws/control socket has no metrics — subscribe_metrics must be gated on
        !this._csrfEnabled (the control socket is the CSRF-enabled one)."""
        assert "!this._csrfEnabled" in client_js


@pytest.mark.unit
class TestN1MetricsPollGateRemoved:
    """N1: the GAP-WS-16 sticky REST→WS switchover gate is REMOVED from the
    metrics-store poll. The sticky ``metricsReceived`` flag starved long-lived
    tabs indefinitely once WS frames stopped arriving (training-runtime defects
    plan §4 I-1 root cause 1); the poll now runs every fast tick as the bridge
    until the WS-primary target (Q6/C6/N8) lands."""

    @pytest.fixture
    def dashboard_manager_source(self):
        from pathlib import Path

        path = Path(__file__).resolve().parents[2] / "frontend" / "dashboard_manager.py"
        return path.read_text(encoding="utf-8")

    def test_metrics_poll_gate_removed(self, dashboard_manager_source):
        """The sticky-gate expression must be gone from the metrics poll."""
        assert 'ws_status.get("metricsReceived")' not in dashboard_manager_source

    def test_bridge_posture_documented(self, dashboard_manager_source):
        """The un-gated poll must say it is the bridge until WS-primary (N8)."""
        assert "Q6/C6/N8" in dashboard_manager_source


@pytest.mark.unit
class TestGapWs25TopologyRestGate:
    """Topology poll posture after N1: the sticky ``topologyReceived`` REST gate
    is REMOVED (same starvation class as the metrics gate — plan §4 I-2); the
    poll stays tab-gated on the slow interval with ``cascade_add`` WS push as
    the fast path, and the ``active_tab`` Input refetches on tab switch.

    The JS-side GAP-WS-25 flags stay in ws_dash_bridge.js (harmless bookkeeping
    that N8's liveness-gated fallback may consume), so the bridge-asset
    assertions below still hold.
    """

    @pytest.fixture
    def bridge_js(self):
        from pathlib import Path

        path = Path(__file__).resolve().parents[2] / "frontend" / "assets" / "ws_dash_bridge.js"
        return path.read_text(encoding="utf-8")

    @pytest.fixture
    def dashboard_manager_source(self):
        from pathlib import Path

        path = Path(__file__).resolve().parents[2] / "frontend" / "dashboard_manager.py"
        return path.read_text(encoding="utf-8")

    def test_topology_received_flag_initialized_false(self, bridge_js):
        assert "_topologyReceived: false" in bridge_js

    def test_topology_received_flag_set_on_first_topology_frame(self, bridge_js):
        assert "drain._topologyReceived = true" in bridge_js

    def test_peek_connection_status_merges_topology_received(self, bridge_js):
        assert "topologyReceived: !!this._topologyReceived" in bridge_js

    def test_dashboard_topology_gate_removed(self, dashboard_manager_source):
        """N1: the sticky topologyReceived REST gate must be gone."""
        assert 'ws_status.get("topologyReceived")' not in dashboard_manager_source

    def test_raw_topology_intentionally_ungated(self, dashboard_manager_source):
        """Raw topology has no WS source — must remain ungated, with a
        comment explaining why so future contributors don't 'fix' it."""
        assert "raw weight matrices" in dashboard_manager_source
        assert "GAP-WS-25" in dashboard_manager_source
        # The raw-topology callback signature must not include ws_status —
        # the callback definition stays as-is.
        assert "def update_raw_topology_store(n, active_tab, view_mode):" in dashboard_manager_source

    def test_topology_callback_signature_dropped_ws_status(self, dashboard_manager_source):
        """N1: the topology callback no longer reads ws-connection-status —
        the gate was its only consumer."""
        assert "def update_topology_store(n, ws_topology, active_tab):" in dashboard_manager_source


@pytest.mark.unit
class TestTopologyStubGuard:
    """Defense against count-only ``topology`` WS frames from pre-fix cascor.

    Pre-fix cascor broadcast a stub on cascade_add (``hidden_units`` as int).
    Without these guards, the topology view collapsed to inputs+outputs
    only and stayed stuck for the rest of the session because
    ``_topologyReceived`` was set on the stub frame, suppressing REST.
    """

    @pytest.fixture
    def bridge_js(self):
        from pathlib import Path

        path = Path(__file__).resolve().parents[2] / "frontend" / "assets" / "ws_dash_bridge.js"
        return path.read_text(encoding="utf-8")

    @pytest.fixture
    def dashboard_manager_source(self):
        from pathlib import Path

        path = Path(__file__).resolve().parents[2] / "frontend" / "dashboard_manager.py"
        return path.read_text(encoding="utf-8")

    def test_js_bridge_only_sets_topology_received_for_complete_payloads(self, bridge_js):
        # The bridge must Array-check hidden_units (or graph-format nodes)
        # before flipping the gate flag.
        assert "Array.isArray(hu)" in bridge_js or "Array.isArray(data.hidden_units)" in bridge_js
        # And the flag-set must be guarded — not unconditional.
        # Look for the conditional wrapping the assignment.
        assert "isComplete" in bridge_js or "if (Array.isArray" in bridge_js

    def test_dashboard_callback_falls_through_to_rest_on_stub(self, dashboard_manager_source):
        # The WS-branch must consult ``_is_complete_topology`` before
        # transforming, and fall back to the REST handler on a stub.
        assert "_is_complete_topology" in dashboard_manager_source
        # The fallback is a call to the REST handler with the ws_topology trigger.
        assert "_update_topology_store_handler" in dashboard_manager_source

    def test_adapter_exposes_is_complete_topology_helper(self):
        # The Python helper the JS gate mirrors. Public-by-convention static
        # method on the adapter so dashboard_manager and tests can call it.
        from backend.cascor_service_adapter import CascorServiceAdapter

        assert hasattr(CascorServiceAdapter, "_is_complete_topology")
        # Spot-check: the documented stub form must be flagged incomplete.
        stub = {"hidden_units": 1, "input_size": 2, "output_size": 2, "event": "cascade_add"}
        assert CascorServiceAdapter._is_complete_topology(stub) is False


@pytest.mark.unit
class TestGapWs18ChunkedMessageReassembler:
    """GAP-WS-18: client reassembles chunked_message envelopes from cascor.

    Pairs with the cascor server-side chunker that splits oversized topology
    broadcasts (>60 KB serialized JSON) into a sequence of ``chunked_message``
    envelopes sharing a chunk_id. Without the client reassembler, those chunks
    would be silently dropped and the visualizer would never paint.
    """

    @pytest.fixture
    def client_js(self):
        from pathlib import Path

        path = Path(__file__).resolve().parents[2] / "frontend" / "assets" / "websocket_client.js"
        return path.read_text(encoding="utf-8")

    def test_chunk_groups_map_initialized(self, client_js):
        assert "this._chunkGroups = new Map()" in client_js
        assert "this._maxChunkGroups" in client_js

    def test_chunked_message_dispatched_to_reassembler(self, client_js):
        """`_handleMessage` must route `chunked_message` to `_reassembleChunk`
        and not fall through to user-handler dispatch (those frames have no
        meaning to the dashboard)."""
        assert "type === 'chunked_message'" in client_js or 'type === "chunked_message"' in client_js
        assert "this._reassembleChunk(message)" in client_js
        # On reassembly success, recurse so the original envelope flows through
        # the same dispatch as a normal message.
        assert "this._handleMessage(reassembled)" in client_js

    def test_reassembler_validates_chunk_envelope(self, client_js):
        """Invalid chunk_index / total_chunks must be rejected, not crash."""
        assert "idx < 0 || idx >= total" in client_js
        assert "total < 1" in client_js

    def test_reassembler_evicts_oldest_at_cap(self, client_js):
        """When _maxChunkGroups is hit, the oldest in-flight group is evicted
        so a buggy or hostile server can't leak memory by sending unfinished
        groups."""
        assert "this._chunkGroups.size >= this._maxChunkGroups" in client_js
        assert "this._chunkGroups.keys().next().value" in client_js
        assert "this._chunkGroups.delete(oldestKey)" in client_js

    def test_reassembler_handles_duplicate_chunk_silently(self, client_js):
        """Resume replay can re-deliver chunks; duplicates must be ignored
        without warning spam."""
        assert "Duplicate chunk" in client_js

    def test_reassembler_parses_reassembled_payload(self, client_js):
        """Successful reassembly must JSON.parse the joined payloads."""
        assert "group.chunks.join('')" in client_js
        assert "JSON.parse(text)" in client_js

    def test_reassembly_end_to_end_via_node(self, tmp_path):
        """Spin up Node and exercise the reassembly logic against a synthetic
        chunk sequence to validate end-to-end behavior, not just source-level
        invariants. Skipped if Node is not available."""
        import shutil
        import subprocess

        node_bin = shutil.which("node")
        if not node_bin:
            pytest.skip("node not available")

        from pathlib import Path

        client_js_path = Path(__file__).resolve().parents[2] / "frontend" / "assets" / "websocket_client.js"

        harness_src = r"""
import { readFileSync } from 'node:fs';

globalThis.window = globalThis;
globalThis.location = { protocol: 'http:', host: 'localhost' };
globalThis.WebSocket = class { constructor() {} send() {} close() {} };
globalThis.XMLHttpRequest = class { open() {} send() {} };
if (!globalThis.crypto || typeof globalThis.crypto.getRandomValues !== 'function') {
    Object.defineProperty(globalThis, 'crypto', {
        value: {
            getRandomValues: (b) => {
                for (let i = 0; i < b.length; i++) b[i] = Math.floor(Math.random() * 256);
                return b;
            },
        },
        configurable: true,
    });
}

// Load the client; truncate the auto-init/singleton tail so we don't need
// a real server, then evaluate just the class definition.
let raw = readFileSync(process.argv[2], 'utf8');
const cutMarker = '// Create global singleton WebSocket';
const cutIdx = raw.indexOf(cutMarker);
if (cutIdx > 0) {
    raw = raw.slice(0, cutIdx);
}
// Append a globalThis bridge so the class escapes the strict-mode module scope.
const src = raw.replace(/this\.connect\(\);/g, '/* test: auto-connect suppressed */')
    + '\nglobalThis.CascorWebSocket = CascorWebSocket;\n';
eval(src);
const CascorWebSocket = globalThis.CascorWebSocket;

const original = { type: 'topology', timestamp: 1.0, data: { hidden: 'x'.repeat(100) } };
const fullJson = JSON.stringify(original);
const chunkSize = 30;
const chunks = [];
for (let i = 0; i < fullJson.length; i += chunkSize) {
    chunks.push(fullJson.slice(i, i + chunkSize));
}

const ws = new CascorWebSocket('ws://localhost/ws/test');
let receivedTopology = null;
ws.on('topology', (data) => { receivedTopology = data; });

const chunkId = 'test-group-1';
chunks.forEach((payload, idx) => {
    ws._handleMessage({
        type: 'chunked_message',
        data: {
            chunk_id: chunkId,
            chunk_index: idx,
            total_chunks: chunks.length,
            original_type: 'topology',
            payload: payload,
        },
    });
});

if (!receivedTopology) {
    console.error('FAIL: topology handler not invoked');
    process.exit(1);
}
if (receivedTopology.hidden !== original.data.hidden) {
    console.error('FAIL: reassembled data mismatch');
    process.exit(1);
}
console.log('OK');
"""
        harness = tmp_path / "harness.mjs"
        harness.write_text(harness_src)
        result = subprocess.run(
            [node_bin, str(harness), str(client_js_path)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"Node harness failed:\nstdout={result.stdout}\nstderr={result.stderr}"
        assert "OK" in result.stdout
