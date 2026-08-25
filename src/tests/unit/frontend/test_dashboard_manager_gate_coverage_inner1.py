#!/usr/bin/env python
"""Per-file coverage gate: inner-callback bodies of dashboard_manager.py (part 1).

Many Dash callbacks are registered as inner functions inside ``_setup_*_callbacks``.
Their bodies are only reachable by invoking the registered callback, which the
existing suite (handler-focused) never does. Dash preserves the raw inner
function under ``callback_map[<key>]["callback"].__wrapped__`` with its original
``__name__``, so ``raw_cb(dm, name)`` fetches it and it is callable directly with
the callback's positional Input/State args.

This file exercises the sidebar / model-class / model-selection / theme / status /
network / datastore / button-action / backend-toggle inner callbacks
(source regions ~2081-3842). Every test asserts real return behaviour.
"""

from unittest.mock import MagicMock, patch

import dash
import pytest

import frontend.dashboard_manager as dmmod
from frontend.callback_context import CallbackContextAdapter
from frontend.dashboard_manager import DashboardManager


@pytest.fixture
def dm():
    return DashboardManager({})


def raw_cb(dm, name):
    """Return the raw (unwrapped) inner callback function registered under ``name``."""
    matches = []
    for entry in dm.app.callback_map.values():
        cb = entry.get("callback")
        if cb is None:
            continue
        raw = getattr(cb, "__wrapped__", cb)
        if getattr(raw, "__name__", None) == name:
            matches.append(raw)
    if not matches:
        raise KeyError(f"callback {name!r} not registered")
    if len(matches) > 1:
        raise AssertionError(f"ambiguous callback name {name!r}: {len(matches)} matches")
    return matches[0]


def _resp(*, ok=True, status=200, json_value=None):
    r = MagicMock()
    r.ok = ok
    r.status_code = status
    r.json.return_value = json_value if json_value is not None else {}
    return r


# ---------------------------------------------------------------------------
# _setup_sidebar_visibility_callback (2083-2090, 2103-2104)
# ---------------------------------------------------------------------------
class TestSidebarVisibilityInner:
    def test_update_sidebar_visibility_metrics(self, dm):
        cb = raw_cb(dm, "update_sidebar_visibility")
        result = cb("metrics")
        # styles for every section + [nn_open, cn_open, header_text]
        assert len(result) == len(dmmod.SIDEBAR_SECTION_IDS) + 3
        assert result[-1] == "Network Parameters"  # TAB_HEADER_MAP["metrics"]
        # metrics shows the NN section -> nn_open True
        assert result[-3] is True

    def test_update_sidebar_visibility_unknown_tab_defaults(self, dm):
        cb = raw_cb(dm, "update_sidebar_visibility")
        result = cb("about")
        # unmapped header falls back to "Meta Parameters"
        assert result[-1] == "Meta Parameters"

    def test_resize_sidebar_for_tab(self, dm):
        cb = raw_cb(dm, "resize_sidebar_for_tab")
        sidebar, content = cb("metrics")
        assert isinstance(sidebar, int)
        assert sidebar + content == dmmod.ui_standards.GRID_COLUMNS


# ---------------------------------------------------------------------------
# _setup_model_class_callbacks (2122-2133, 2142, 2151-2152)
# ---------------------------------------------------------------------------
class TestModelClassInner:
    # F-CANOPY-027: hydrate_model_class now takes the store's CURRENT value as State and
    # returns ``no_update`` when the resolved class already matches it. A no-op write
    # re-triggered ``suppress_cascade_tabs`` and rebuilt the whole 15-tab bar for nothing,
    # which also reset the ``disabled`` prop of every poller interval living inside it.
    # These three cases pass ``None`` as the current value, so the resolved class is
    # always written and their original intent is preserved exactly.
    @patch("requests.get")
    def test_hydrate_model_class_one_shot(self, mock_get, dm):
        mock_get.return_value = _resp(ok=True, json_value={"execution": "one_shot"})
        cb = raw_cb(dm, "hydrate_model_class")
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            assert cb(1, None) == "one_shot"

    @patch("requests.get")
    def test_hydrate_model_class_live_when_not_one_shot(self, mock_get, dm):
        mock_get.return_value = _resp(ok=True, json_value={"execution": "live"})
        cb = raw_cb(dm, "hydrate_model_class")
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            assert cb(1, None) == "live"

    @patch("requests.get", side_effect=Exception("down"))
    def test_hydrate_model_class_exception_defaults_live(self, _mock_get, dm):
        cb = raw_cb(dm, "hydrate_model_class")
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            assert cb(1, None) == "live"

    @patch("requests.get")
    def test_hydrate_model_class_suppresses_noop_rewrite(self, mock_get, dm):
        """F-CANOPY-027: the common path — store already "live" and the backend says
        "live" — must NOT write, so the tab bar is never rebuilt for no change."""
        mock_get.return_value = _resp(ok=True, json_value={"execution": "live"})
        cb = raw_cb(dm, "hydrate_model_class")
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            assert cb(1, "live") is dash.no_update

    @patch("requests.get")
    def test_hydrate_model_class_writes_on_genuine_transition(self, mock_get, dm):
        """A real live → one_shot transition still writes, and so still rebuilds."""
        mock_get.return_value = _resp(ok=True, json_value={"execution": "one_shot"})
        cb = raw_cb(dm, "hydrate_model_class")
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            assert cb(1, "live") == "one_shot"

    def test_suppress_cascade_tabs_one_shot_fewer(self, dm):
        cb = raw_cb(dm, "suppress_cascade_tabs")
        live = cb("live")
        one_shot = cb("one_shot")
        assert isinstance(live, list) and isinstance(one_shot, list)
        assert len(one_shot) < len(live)

    def test_toggle_iteration_segment(self, dm):
        cb = raw_cb(dm, "toggle_iteration_segment")
        assert cb("one_shot").get("display") == "none"
        assert "display" not in cb("live")


# ---------------------------------------------------------------------------
# _setup_model_selection_callbacks (2183, 2201, 2211, 2223, 2235, 2246)
# ---------------------------------------------------------------------------
class TestModelSelectionInner:
    def test_toggle_model_modal_open(self, dm):
        cb = raw_cb(dm, "toggle_model_modal")
        fake_ctx = MagicMock()
        fake_ctx.triggered_id = "nn-model-change-button"
        with patch.object(dmmod.dash, "callback_context", fake_ctx):
            is_open, table = cb(1, None, "", dmmod.DEFAULT_DATASET_TYPE, dmmod.DEFAULT_MODEL_KEY)
        assert is_open is True
        assert table is not None

    def test_toggle_model_modal_close(self, dm):
        cb = raw_cb(dm, "toggle_model_modal")
        fake_ctx = MagicMock()
        fake_ctx.triggered_id = "model-selection-modal-close"
        with patch.object(dmmod.dash, "callback_context", fake_ctx):
            is_open, table = cb(None, 1, "", dmmod.DEFAULT_DATASET_TYPE, dmmod.DEFAULT_MODEL_KEY)
        assert is_open is False
        assert table is dash.no_update

    def test_select_model_no_click(self, dm):
        cb = raw_cb(dm, "select_model")
        fake_ctx = MagicMock()
        fake_ctx.triggered_id = None
        with patch.object(dmmod.dash, "callback_context", fake_ctx):
            result = cb([None])
        assert result == (dash.no_update, dash.no_update, dash.no_update, dash.no_update)

    def test_gate_dataset_options(self, dm):
        cb = raw_cb(dm, "gate_dataset_options")
        # N7: gate_dataset_options gained a params-init-interval Input (fires the availability gate
        # on mount too) — the middle positional is the interval count.
        options, value = cb(dmmod.DEFAULT_MODEL_KEY, None, dmmod.DEFAULT_DATASET_TYPE)
        assert isinstance(options, list)

    def test_resolve_oneshot_start_body_live(self, dm):
        cb = raw_cb(dm, "resolve_oneshot_start_body")
        assert cb("live", dmmod.DEFAULT_DATASET_TYPE) is None

    def test_resolve_oneshot_start_body_one_shot(self, dm):
        cb = raw_cb(dm, "resolve_oneshot_start_body")
        result = cb("one_shot", dmmod.DEFAULT_DATASET_TYPE)
        assert isinstance(result, dict)
        assert "dataset" in result

    def test_annotate_model_hint(self, dm):
        cb = raw_cb(dm, "annotate_model_hint")
        # returns a string (possibly empty) — never raises
        assert isinstance(cb(dmmod.DEFAULT_DATASET_TYPE), str)

    def test_annotate_train_gate_trainable(self, dm):
        cb = raw_cb(dm, "annotate_train_gate")
        # DEFAULT_MODEL_KEY ("cascor") is live/trainable -> None (hidden)
        assert cb(dmmod.DEFAULT_MODEL_KEY) is None


# ---------------------------------------------------------------------------
# _setup_theme_callbacks (2505, 2517)
# ---------------------------------------------------------------------------
class TestThemeInner:
    def test_toggle_dark_mode(self, dm):
        cb = raw_cb(dm, "toggle_dark_mode")
        is_dark, icon = cb(1, False)
        assert is_dark is True and icon == "☀️"

    def test_update_theme_state(self, dm):
        cb = raw_cb(dm, "update_theme_state")
        assert cb(True) == "dark"
        assert cb(False) == "light"


# ---------------------------------------------------------------------------
# _setup_status_bar_callbacks / _setup_network_callbacks
# (2693, 2707, 2717, 2730-2732, 2743)
# ---------------------------------------------------------------------------
class TestStatusAndNetworkInner:
    @patch("requests.get")
    def test_update_unified_status_bar(self, mock_get, dm):
        # Stage 2 (design §13 row 1) + F-CANOPY-025: the bar callback owns
        # training-status-store AND the Live Switch gate, so the tuple is 11;
        # the store element carries {is_running, phase}, the gate element the
        # button's disabled state (idle + no flag -> disabled True).
        mock_get.return_value = _resp(ok=True, status=200, json_value={"is_running": False, "phase": "idle", "current_epoch": 0, "hidden_units": 0})
        cb = raw_cb(dm, "update_unified_status_bar")
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            result = cb(1, None, None, None)
        assert len(result) == 11
        assert result[9] == {"is_running": False, "phase": "idle"}
        assert result[10] is True

    @patch("requests.get")
    def test_update_unified_status_bar_suppresses_unchanged_training_status(self, mock_get, dm):
        # Stage 2 (design §13 row 1): unchanged {is_running, phase} -> the store
        # element is no_update; F-CANOPY-025: unchanged gate value likewise.
        mock_get.return_value = _resp(ok=True, status=200, json_value={"is_running": True, "phase": "output"})
        cb = raw_cb(dm, "update_unified_status_bar")
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            result = cb(1, {"is_running": True, "phase": "output"}, None, True)
        assert result[9] is dash.no_update
        assert result[10] is dash.no_update

    @patch("requests.get")
    def test_update_unified_status_bar_opens_the_live_switch_gate(self, mock_get, dm):
        # F-CANOPY-025 allow arm: flag ON + running -> the gate element writes
        # disabled=False. The standalone gate callback could NEVER execute
        # during a run (its Input store is claimed by this very feeder while in
        # flight every fast tick), which hid this arm for the whole arc.
        mock_get.return_value = _resp(ok=True, status=200, json_value={"is_running": True, "phase": "output"})
        cb = raw_cb(dm, "update_unified_status_bar")
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            result = cb(1, None, {"experimental_functions": True}, True)
        assert result[10] is False

    @patch("requests.get")
    def test_update_network_info(self, mock_get, dm):
        # Stage 2 (design §13 row 2): the panel is now element [0] of the merged
        # update_system_panels callback (network info / details / stream health / banner).
        mock_get.return_value = _resp(ok=True, json_value={"input_size": 2, "hidden_units": 1, "output_size": 1})
        cb = raw_cb(dm, "update_system_panels")
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            info, details, health, banner = cb(1)
        assert info is not None
        assert details is not None

    def test_toggle_network_info(self, dm):
        cb = raw_cb(dm, "toggle_network_info")
        assert cb(1, False) is True
        assert cb(1, True) is False

    def test_toggle_network_info_details(self, dm):
        cb = raw_cb(dm, "toggle_network_info_details")
        state, icon = cb(1, False)
        assert state is True and icon == "▼"
        state, icon = cb(1, True)
        assert state is False and icon == "▶"

    @patch("requests.get")
    def test_update_network_info_details(self, mock_get, dm):
        # Stage 2 (design §13 row 2): details is element [1] of update_system_panels.
        mock_get.return_value = _resp(ok=True, json_value={"total_weights": 5})
        cb = raw_cb(dm, "update_system_panels")
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            _info, details, _health, _banner = cb(1)
        assert details is not None


# ---------------------------------------------------------------------------
# _setup_datastore_callbacks (3159-3470)
# ---------------------------------------------------------------------------
class TestDatastoreInner:
    def test_update_parameters_panel_store_strips_prefixes(self, dm):
        cb = raw_cb(dm, "update_parameters_panel_store")
        result = cb({"nn_learning_rate": 0.01, "cn_pool_size": 100, "other": 5}, "parameters")
        assert result["learning_rate"] == 0.01
        assert result["pool_size"] == 100
        assert result["other"] == 5

    def test_update_parameters_panel_store_empty(self, dm):
        cb = raw_cb(dm, "update_parameters_panel_store")
        assert cb(None, "parameters") == {}

    @patch("requests.get")
    def test_update_metrics_store_delegates(self, mock_get, dm):
        # Called outside a Dash callback context: the wrapper's
        # MissingCallbackContextException branch maps that to trigger="" (a
        # mount/mode-switch-style fetch). N8 args: (n, display_mode_state,
        # ws_liveness, current_metrics). ws_liveness=None → stale → the REST poll
        # runs (the liveness-gated O1 fallback); current_metrics=None (empty-guard).
        mock_get.return_value = _resp(ok=True, json_value={"history": [{"epoch": 1}]})
        cb = raw_cb(dm, "update_metrics_store")
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            result = cb(1, {"mode": "window", "window_size": 100}, None, None)
        assert result == [{"epoch": 1}]

    @patch("requests.get")
    def test_update_metrics_store_interval_trigger_in_callback_context(self, mock_get, dm):
        # N8: exercise the wrapper's happy ctx path — an interval-tick trigger
        # inside a (mocked) callback context reaches the handler with the interval
        # prop_id; with the WS stream stale (ws_liveness=None) window mode fetches on
        # every tick (the O1 fallback).
        mock_get.return_value = _resp(ok=True, json_value={"history": [{"epoch": 2}]})
        cb = raw_cb(dm, "update_metrics_store")
        fake_ctx = MagicMock()
        fake_ctx.triggered = [{"prop_id": "fast-update-interval.n_intervals"}]
        with patch.object(dmmod.dash, "callback_context", fake_ctx):
            with dm.app.server.test_request_context(base_url="http://localhost:8050"):
                result = cb(1, {"mode": "window", "window_size": 100}, None, None)
        assert result == [{"epoch": 2}]

    def test_update_topology_store_ws_complete(self, dm):
        cb = raw_cb(dm, "update_topology_store")
        fake_ctx = MagicMock()
        fake_ctx.triggered = [{"prop_id": "ws-topology-buffer.data"}]
        with patch.object(dmmod.dash, "callback_context", fake_ctx), patch("backend.cascor_service_adapter.CascorServiceAdapter._is_complete_topology", return_value=True), patch("backend.cascor_service_adapter.CascorServiceAdapter._transform_topology", return_value={"transformed": True}):
            result = cb(1, {"hidden_units": [1, 2]}, "topology")
        assert result == {"transformed": True}

    def test_update_topology_store_ws_stub_falls_back_to_rest(self, dm):
        # Weight-format REST payload so the fallback exercises the transform
        # (graph-format now passes through untransformed — see
        # test_update_topology_store_graph_format_passthrough).
        cb = raw_cb(dm, "update_topology_store")
        fake_ctx = MagicMock()
        fake_ctx.triggered = [{"prop_id": "ws-topology-buffer.data"}]
        with patch.object(dmmod.dash, "callback_context", fake_ctx), patch("backend.cascor_service_adapter.CascorServiceAdapter._is_complete_topology", return_value=False), patch("backend.cascor_service_adapter.CascorServiceAdapter._transform_topology", return_value={"rest": True}), patch("requests.get") as mock_get:
            mock_get.return_value = _resp(ok=True, json_value={"data": {"input_size": 2, "output_size": 1, "hidden_units": []}})
            with dm.app.server.test_request_context(base_url="http://localhost:8050"):
                result = cb(1, {"hidden_units": 5}, "topology")
        assert result == {"rest": True}

    def test_update_topology_store_polls_rest_even_with_ws_connected(self, dm):
        # N1: the sticky topologyReceived gate is gone — an interval tick on the
        # active topology tab polls REST regardless of WS connection state
        # (the gate pinned here pre-N1 returned no_update and starved the view).
        # Weight-format payload (no input_units key) so the adapter transform
        # still runs — graph-format payloads now pass through untransformed
        # (see test_update_topology_store_graph_format_passthrough).
        cb = raw_cb(dm, "update_topology_store")
        fake_ctx = MagicMock()
        fake_ctx.triggered = [{"prop_id": "slow-update-interval.n_intervals"}]
        with patch.object(dmmod.dash, "callback_context", fake_ctx), patch("backend.cascor_service_adapter.CascorServiceAdapter._transform_topology", return_value={"rest": True}), patch("requests.get") as mock_get:
            mock_get.return_value = _resp(ok=True, json_value={"data": {"input_size": 2, "output_size": 1, "hidden_units": []}})
            with dm.app.server.test_request_context(base_url="http://localhost:8050"):
                result = cb(1, None, "topology")
        assert result == {"rest": True}
        mock_get.assert_called_once()

    def test_update_topology_store_rest_fallback(self, dm):
        cb = raw_cb(dm, "update_topology_store")
        fake_ctx = MagicMock()
        fake_ctx.triggered = [{"prop_id": "slow-update-interval.n_intervals"}]
        with patch.object(dmmod.dash, "callback_context", fake_ctx), patch("backend.cascor_service_adapter.CascorServiceAdapter._transform_topology", return_value={"rest": True}), patch("requests.get") as mock_get:
            mock_get.return_value = _resp(ok=True, json_value={"data": {"input_size": 2, "output_size": 1, "hidden_units": []}})
            with dm.app.server.test_request_context(base_url="http://localhost:8050"):
                result = cb(1, None, "topology")
        assert result == {"rest": True}

    def test_update_topology_store_graph_format_passthrough(self, dm):
        # Demo-mode seam (2026-07-14, canopy#449): a graph-format payload
        # (has ``input_units``) is returned UNTRANSFORMED and the service
        # adapter is never consulted — its module hard-imports
        # juniper_cascor_client (the optional [juniper-cascor] extra), which
        # is legitimately absent in demo-only installs; importing it here
        # turned every dispatch into a silent no_update (empty topology
        # panel). The patched transform's sentinel must NOT come back.
        cb = raw_cb(dm, "update_topology_store")
        fake_ctx = MagicMock()
        fake_ctx.triggered = [{"prop_id": "slow-update-interval.n_intervals"}]
        graph_payload = {"input_units": 2, "output_units": 1, "hidden_units": 0, "nodes": [{"id": "input_0"}], "connections": []}
        with patch.object(dmmod.dash, "callback_context", fake_ctx), patch("backend.cascor_service_adapter.CascorServiceAdapter._transform_topology", return_value={"rest": True}) as mock_transform, patch("requests.get") as mock_get:
            mock_get.return_value = _resp(ok=True, json_value={"data": graph_payload})
            with dm.app.server.test_request_context(base_url="http://localhost:8050"):
                result = cb(1, None, "topology")
        assert result == graph_payload
        mock_transform.assert_not_called()

    @patch("requests.get")
    def test_update_raw_topology_store_delegates(self, mock_get, dm):
        mock_get.return_value = _resp(ok=True, json_value={"weights": []})
        cb = raw_cb(dm, "update_raw_topology_store")
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            result = cb(1, "topology", "weight_matrix")
        assert result == {"weights": []}

    @patch("requests.get")
    def test_update_dataset_store_delegates(self, mock_get, dm):
        mock_get.return_value = _resp(ok=True, json_value={"num_samples": 100})
        cb = raw_cb(dm, "update_dataset_store")
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            result = cb(1, "dataset")
        assert result == {"num_samples": 100}

    @patch("requests.get")
    def test_update_boundary_store_delegates(self, mock_get, dm):
        # Stage 2 (design §13 row 5): the feeder holds its own store as State so
        # an identical fetch suppresses to no_update; a changed one still lands.
        mock_get.return_value = _resp(ok=True, json_value={"grid": []})
        cb = raw_cb(dm, "update_boundary_store")
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            result = cb(1, "boundaries", None, 50, None)
        assert result == {"grid": []}

    @patch("requests.get")
    def test_update_boundary_dataset_store_delegates(self, mock_get, dm):
        mock_get.return_value = _resp(ok=True, json_value={"inputs": []})
        cb = raw_cb(dm, "update_boundary_dataset_store")
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            result = cb(1, "boundaries", None)
        assert result == {"inputs": []}

    # F-CANOPY-029: these two fakes MUST be spec'd to CallbackContextAdapter.
    # They previously used a bare MagicMock() and set ``fake_ctx.triggered_id`` --
    # an attribute the adapter has never had. A bare MagicMock fabricates any
    # attribute on demand, so both tests passed green while every real click
    # raised AttributeError and Dash returned 500, leaving the dataset generate
    # modal permanently unopenable. With spec= the mock rejects the wrong name,
    # so this class of drift fails the test instead of shipping.
    def test_toggle_generate_modal_open(self, dm):
        cb = raw_cb(dm, "toggle_generate_modal")
        fake_ctx = MagicMock(spec=CallbackContextAdapter)
        fake_ctx.get_triggered_id.return_value = "dataset-plotter-generate-btn"
        with patch.object(dmmod, "get_callback_context", return_value=fake_ctx):
            assert cb(1, None, None, None, None, False) is True

    def test_toggle_generate_modal_close(self, dm):
        cb = raw_cb(dm, "toggle_generate_modal")
        fake_ctx = MagicMock(spec=CallbackContextAdapter)
        fake_ctx.get_triggered_id.return_value = "dataset-plotter-gen-cancel"
        with patch.object(dmmod, "get_callback_context", return_value=fake_ctx):
            assert cb(None, 1, None, None, None, True) is False

    def test_toggle_generate_modal_rejects_raw_dash_attribute(self, dm):
        """Anti-regression for F-CANOPY-029 itself.

        The adapter exposes get_triggered_id() and NOT dash's ``.triggered_id``.
        Pin that so a future edit cannot reintroduce the raw-dash attribute read
        on the adapter object without a test failing.
        """
        assert hasattr(CallbackContextAdapter, "get_triggered_id")
        assert not hasattr(CallbackContextAdapter, "triggered_id")
        with pytest.raises(AttributeError):
            MagicMock(spec=CallbackContextAdapter).triggered_id

    @patch("requests.post")
    def test_generate_dataset_delegates(self, mock_post, dm):
        mock_post.return_value = _resp(ok=True, json_value={"num_samples": 200})
        cb = raw_cb(dm, "generate_dataset")
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            status, data = cb(1, 200, 2, 1.5, 0.1)
        assert data == {"num_samples": 200}

    def test_load_selected_dataset_delegates_no_click(self, dm):
        cb = raw_cb(dm, "load_selected_dataset")
        assert cb(None, "xor") == (dash.no_update, dash.no_update)

    def test_update_import_file_label(self, dm):
        cb = raw_cb(dm, "update_import_file_label")
        assert cb(None) == ("", True)
        label, disabled = cb("data.csv")
        assert "data.csv" in label and disabled is False

    def test_import_dataset_file_delegates_no_contents(self, dm):
        cb = raw_cb(dm, "import_dataset_file")
        status, data = cb(1, None, "x.csv")
        assert data is dash.no_update

    def test_import_dataset_url_delegates_empty(self, dm):
        cb = raw_cb(dm, "import_dataset_url")
        status, data = cb(1, "")
        assert data is dash.no_update

    def test_update_pinned_params_store(self, dm):
        cb = raw_cb(dm, "update_pinned_params_store")
        values = [True, None, False]
        ids = [{"type": "param-pin", "key": "a"}, {"type": "param-pin", "key": "b"}, {"type": "param-pin", "key": "c"}]
        assert cb(values, ids) == ["a"]

    def test_render_sidebar_pinned_mirror_empty(self, dm):
        cb = raw_cb(dm, "render_sidebar_pinned_mirror")
        rows, style = cb([], {})
        assert rows == [] and style == {"display": "none"}

    def test_render_sidebar_pinned_mirror_populated(self, dm):
        cb = raw_cb(dm, "render_sidebar_pinned_mirror")
        pinned = ["a", "b", "c"]
        params = {"a": True, "b": ["enabled"], "c": 0.5}
        rows, style = cb(pinned, params)
        assert len(rows) == 3
        assert style == {"display": "block"}


# ---------------------------------------------------------------------------
# _setup_button_action_callbacks inner delegations (3659, 3674, 3705, 3718)
# ---------------------------------------------------------------------------
class TestButtonActionInner:
    def test_update_last_click_delegates(self, dm):
        cb = raw_cb(dm, "update_last_click")
        result = cb({"last": "start-button", "ts": 123.0})
        assert result == {"button": "start-button", "timestamp": 123.0}

    def test_surface_training_control_outcome_success_clears(self, dm):
        cb = raw_cb(dm, "surface_training_control_outcome")
        assert cb({"success": True}) is None

    def test_surface_training_control_outcome_failure_alert(self, dm):
        cb = raw_cb(dm, "surface_training_control_outcome")
        alert = cb({"success": False, "command": "start", "detail": "no data"})
        assert alert is not None
        assert "no data" in str(alert)

    def test_update_button_appearance_delegates(self, dm):
        cb = raw_cb(dm, "update_button_appearance")
        result = cb({"start": {"disabled": False, "loading": False, "timestamp": 0}}, dmmod.DEFAULT_MODEL_KEY)
        assert len(result) == 10

    def test_handle_button_timeout_and_acks_delegates(self, dm):
        cb = raw_cb(dm, "handle_button_timeout_and_acks")
        assert cb(None, 1, None) is dash.no_update


# ---------------------------------------------------------------------------
# _setup_backend_callbacks toggles (3732-3842)
# ---------------------------------------------------------------------------
class TestBackendToggleInner:
    @pytest.mark.parametrize(
        "name",
        [
            "toggle_nn_subsection",
            "toggle_cn_subsection",
            "toggle_ctx_growth_triggers",
            "toggle_ctx_multi_node",
            "toggle_ctx_spiral_dataset",
            "toggle_ctx_pool_training",
        ],
    )
    def test_collapse_toggles(self, dm, name):
        cb = raw_cb(dm, name)
        is_open, icon = cb(1, False)
        assert is_open is True and icon == "▼"
        is_open, icon = cb(1, True)
        assert is_open is False and icon == "▶"

    def test_toggle_nn_growth_inputs(self, dm):
        cb = raw_cb(dm, "toggle_nn_growth_inputs")
        assert cb("preset_epochs") == (False, True)
        assert cb("convergence") == (True, False)

    def test_toggle_cn_training_inputs(self, dm):
        cb = raw_cb(dm, "toggle_cn_training_inputs")
        assert cb("preset_epochs") == (False, True)
        assert cb("convergence") == (True, False)

    def test_toggle_cn_selection_inputs(self, dm):
        cb = raw_cb(dm, "toggle_cn_selection_inputs")
        assert cb("top_tier") == (False, True)

    def test_toggle_cn_multi_candidate_subgroup(self, dm):
        cb = raw_cb(dm, "toggle_cn_multi_candidate_subgroup")
        style, top_disabled, rand_disabled = cb([])
        assert top_disabled is True and rand_disabled is True

    def test_sync_multi_node_checkboxes(self, dm):
        cb = raw_cb(dm, "sync_multi_node_checkboxes")
        fake_ctx = MagicMock()
        fake_ctx.triggered = [{"prop_id": "cn-multi-candidate-checkbox.value"}]
        with patch.object(dmmod.dash, "callback_context", fake_ctx):
            result = cb([], ["enabled"])
        assert result[0] == ["enabled"]


# ---------------------------------------------------------------------------
# Server-side handle_training_buttons inner callback (line 3637)
#
# Only registered when ``enable_ws_control_buttons`` is False; the default is
# True (Phase D), which registers the clientside JS transport instead. Flip the
# flag for one construction so the server-side inner callback exists, then invoke
# it (with a start-button trigger) to exercise the delegation line.
# ---------------------------------------------------------------------------
class TestServerSideTrainingButtonsInner:
    def test_handle_training_buttons_server_side_start(self):
        real = dmmod.get_settings()
        flipped = real.model_copy(update={"enable_ws_control_buttons": False})
        with patch.object(dmmod, "get_settings", return_value=flipped):
            dm = DashboardManager({})
        cb = raw_cb(dm, "handle_training_buttons")
        # spec'd for the same reason as the toggle_generate_modal fakes (F-CANOPY-029)
        fake_ctx = MagicMock(spec=CallbackContextAdapter)
        fake_ctx.get_triggered_id.return_value = "start-button"
        button_states = {"start": {"disabled": False, "loading": False, "timestamp": 0}}
        with patch.object(dmmod, "get_callback_context", return_value=fake_ctx), patch("requests.post") as mock_post:
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            mock_post.return_value = resp
            with dm.app.server.test_request_context(base_url="http://localhost:8050"):
                action, states = cb(1, None, None, None, None, None, button_states, None)
        assert action["success"] is True
        assert action["last"] == "start-button"
        assert states["start"]["loading"] is True
