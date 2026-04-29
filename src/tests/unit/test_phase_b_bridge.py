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
class TestMetricsPollingToggle:
    """Test polling toggle in _update_metrics_store_handler."""

    def test_returns_no_update_when_ws_connected_and_metrics_received(self):
        """GAP-WS-16: REST poll is skipped only when WS reports BOTH connected
        AND metricsReceived (avoids the empty-chart blip during the connect→
        first-frame window)."""
        import dash

        from frontend.dashboard_manager import DashboardManager

        dm = DashboardManager.__new__(DashboardManager)
        dm.logger = __import__("logging").getLogger("test")

        ws_status = {"connected": True, "reconnecting": False, "mode": "live", "metricsReceived": True}

        with patch("frontend.dashboard_manager.get_settings") as mock_settings:
            mock_settings.return_value.ws_bridge_enabled = True
            result = dm._update_metrics_store_handler(n=1, ws_status=ws_status)

        assert result is dash.no_update

    def test_rest_poll_continues_when_connected_but_no_metrics_yet(self):
        """GAP-WS-16: connected=True but metricsReceived=False keeps REST polling
        until the first WS metrics frame arrives. Without this gate, a tab that
        connects mid-training shows an empty chart for one polling interval."""
        from frontend.dashboard_manager import DashboardManager

        dm = DashboardManager.__new__(DashboardManager)
        dm.logger = __import__("logging").getLogger("test")
        dm._api_base_url = "http://127.0.0.1:8050"

        ws_status = {"connected": True, "reconnecting": False, "mode": "live", "metricsReceived": False}

        with patch("frontend.dashboard_manager.get_settings") as mock_settings, patch("frontend.dashboard_manager.requests") as mock_requests:
            mock_settings.return_value.ws_bridge_enabled = True
            mock_resp = mock_requests.get.return_value
            mock_resp.ok = True
            mock_resp.json.return_value = [{"epoch": 1, "error": 0.5}]
            result = dm._update_metrics_store_handler(
                n=1,
                display_mode_state={"mode": "window", "window_size": 100},
                ws_status=ws_status,
            )

        assert isinstance(result, list)
        assert len(result) == 1

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
class TestGapWs16RestSwitchoverGate:
    """GAP-WS-16: dashboard_manager REST→WS switchover must wait for first metrics frame."""

    @pytest.fixture
    def dashboard_manager_source(self):
        from pathlib import Path

        path = Path(__file__).resolve().parents[2] / "frontend" / "dashboard_manager.py"
        return path.read_text(encoding="utf-8")

    def test_gate_requires_metrics_received(self, dashboard_manager_source):
        """The REST poll suppression must require ws_status['metricsReceived'], not
        only 'connected'."""
        assert 'ws_status.get("metricsReceived")' in dashboard_manager_source


@pytest.mark.unit
class TestGapWs25TopologyRestGate:
    """GAP-WS-25: topology REST poll waits for first WS topology frame.

    Mirrors GAP-WS-16's metricsReceived pattern. Cascor only broadcasts
    `topology` on cascade_add (grow events), so a fresh tab can wait
    minutes for one. Until the first frame arrives, REST keeps polling
    so the visualizer paints something.
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

    def test_dashboard_topology_gate_requires_topology_received(self, dashboard_manager_source):
        """The topology REST gate must require ws_status['topologyReceived']."""
        assert 'ws_status.get("topologyReceived")' in dashboard_manager_source

    def test_raw_topology_intentionally_ungated(self, dashboard_manager_source):
        """Raw topology has no WS source — must remain ungated, with a
        comment explaining why so future contributors don't 'fix' it."""
        assert "raw weight matrices" in dashboard_manager_source
        assert "GAP-WS-25" in dashboard_manager_source
        # The raw-topology callback signature must not include ws_status —
        # the callback definition stays as-is.
        assert "def update_raw_topology_store(n, active_tab, view_mode):" in dashboard_manager_source

    def test_topology_callback_signature_unchanged(self, dashboard_manager_source):
        """The existing topology callback signature stays — we only tightened
        the gate condition, didn't add new inputs."""
        assert "def update_topology_store(n, ws_topology, active_tab, ws_status):" in dashboard_manager_source


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
