#!/usr/bin/env python
"""Per-file coverage-gate tests for ``frontend.components.network_editor_panel``.

Covers the baseline-missing branches: ``_post_json`` non-JSON responses,
the ``poll_fsm_and_topology`` FSM/topology poll callback (idle, active,
exception paths), and the guard/error rails inside the add / remove /
patch callbacks (no-click short-circuits, numeric-parse failures, and
backend-failure surfacing).
"""

from unittest.mock import MagicMock, patch

import dash
import pytest

from frontend.components.network_editor_panel import NetworkEditorPanel


class _StubApp:
    def __init__(self):
        self.callbacks = []

    def callback(self, *outputs, **kwargs):
        def decorator(fn):
            self.callbacks.append((outputs, kwargs, fn))
            return fn

        return decorator


@pytest.fixture
def panel():
    return NetworkEditorPanel({"api_base_url": "http://localhost:8050"}, component_id="ne-gate")


@pytest.fixture
def callbacks(panel):
    app = _StubApp()
    panel.register_callbacks(app)
    return {fn.__name__: fn for _, _, fn in app.callbacks}


class TestPostJsonNonJsonResponses:
    def test_2xx_non_json_returns_empty_data(self, panel):
        resp = MagicMock(status_code=200)
        resp.json.side_effect = ValueError
        with patch("requests.post", return_value=resp):
            result = panel._post_json("POST", "/api/v1/network/hidden-units", {})
        assert result == {"success": True, "data": {}}

    def test_error_status_non_json_falls_back_to_http_code(self, panel):
        resp = MagicMock(status_code=500)
        resp.json.side_effect = ValueError
        with patch("requests.delete", return_value=resp):
            result = panel._post_json("DELETE", "/api/v1/network/hidden-units/1")
        assert result["success"] is False
        assert result["error"] == "HTTP 500"


class TestPollFsmAndTopology:
    def test_not_investigating_shows_idle(self, callbacks):
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"state_machine": {"status": "Stopped"}}
        with patch("requests.get", return_value=resp):
            idle_style, active_style, badge, topology = callbacks["poll_fsm_and_topology"](1)
        assert idle_style == {"display": "block"}
        assert active_style == {"display": "none"}
        assert badge == "FSM: Stopped"
        assert topology is None

    def test_status_request_exception_defaults_idle(self, callbacks):
        with patch("requests.get", side_effect=RuntimeError("net down")):
            idle_style, active_style, badge, topology = callbacks["poll_fsm_and_topology"](1)
        assert idle_style == {"display": "block"}
        assert badge == "FSM: Unknown"
        assert topology is None

    def test_investigating_fetches_topology(self, callbacks):
        status_resp = MagicMock(status_code=200)
        status_resp.json.return_value = {"state_machine": {"status": "Investigating"}}
        topo_resp = MagicMock(status_code=200)
        topo_resp.json.return_value = {"input_size": 2, "output_size": 1, "hidden_units": []}
        with patch("requests.get", side_effect=[status_resp, topo_resp]):
            idle_style, active_style, badge, topology = callbacks["poll_fsm_and_topology"](1)
        assert idle_style == {"display": "none"}
        assert active_style == {"display": "block"}
        assert badge == "FSM: Investigating"
        assert topology == {"input_size": 2, "output_size": 1, "hidden_units": []}

    def test_investigating_topology_exception_yields_none(self, callbacks):
        status_resp = MagicMock(status_code=200)
        status_resp.json.return_value = {"state_machine": {"status": "Investigating"}}
        with patch("requests.get", side_effect=[status_resp, RuntimeError("topo down")]):
            _idle, active_style, _badge, topology = callbacks["poll_fsm_and_topology"](1)
        assert active_style == {"display": "block"}
        assert topology is None

    def test_investigating_topology_non_200_yields_none(self, callbacks):
        status_resp = MagicMock(status_code=200)
        status_resp.json.return_value = {"state_machine": {"status": "Investigating"}}
        topo_resp = MagicMock(status_code=404)
        with patch("requests.get", side_effect=[status_resp, topo_resp]):
            _idle, _active, _badge, topology = callbacks["poll_fsm_and_topology"](1)
        assert topology is None


class TestAddUnitGuards:
    def test_no_click_no_update(self, callbacks):
        assert callbacks["on_add_unit"](0, "1.0", 0.0, "Tanh") is dash.no_update

    def test_non_numeric_bias_rejected(self, callbacks):
        result = callbacks["on_add_unit"](1, "1.0, 2.0", "abc", "Tanh")
        assert "Bias must be numeric" in str(result)

    def test_backend_failure_surfaced(self, panel, callbacks):
        with patch.object(panel, "_post_json", return_value={"success": False, "error": "boom"}):
            result = callbacks["on_add_unit"](1, "1.0, 2.0", 0.0, "Tanh")
        assert "Add failed" in str(result)
        assert "boom" in str(result)


class TestRemoveModalGuards:
    def test_open_modal_no_click_no_update(self, callbacks):
        result = callbacks["open_remove_modal"](0, 3)
        assert all(r is dash.no_update for r in result)

    def test_cancel_no_click_no_update(self, callbacks):
        assert callbacks["cancel_remove_modal"](0) is dash.no_update


class TestPatchWeightsGuards:
    def test_no_click_no_update(self, callbacks):
        assert callbacks["on_patch_weights"](0, "output_weights", None, "1.0") is dash.no_update

    def test_unparseable_values_rejected(self, callbacks):
        result = callbacks["on_patch_weights"](1, "output_weights", None, "1.0, abc")
        assert "Could not parse values" in str(result)

    def test_non_integer_hidden_idx_rejected(self, callbacks):
        result = callbacks["on_patch_weights"](1, "hidden_unit_weights", "abc", "1.0, 2.0")
        assert "hidden_unit_index must be an integer" in str(result)

    def test_backend_failure_surfaced(self, panel, callbacks):
        with patch.object(panel, "_post_json", return_value={"success": False, "error": "shape mismatch"}):
            result = callbacks["on_patch_weights"](1, "output_weights", None, "1.0, 2.0")
        assert "Patch failed" in str(result)
        assert "shape mismatch" in str(result)
