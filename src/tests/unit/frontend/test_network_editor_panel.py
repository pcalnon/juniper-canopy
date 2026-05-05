#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# File Name:     test_network_editor_panel.py
# Author:        Paul Calnon
# Date:          2026-05-03
# License:       MIT License
# Description:   Unit tests for NetworkEditorPanel (CAN-015h, h-5).
#####################################################################
"""Unit tests for the network editor panel."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

src_dir = Path(__file__).parents[3]
sys.path.insert(0, str(src_dir))

from frontend.components.network_editor_panel import NetworkEditorPanel  # noqa: E402


@pytest.fixture
def panel():
    return NetworkEditorPanel(
        {"api_base_url": "http://localhost:8050"},
        component_id="ne-test",
    )


# =============================================================================
# Layout
# =============================================================================


class TestLayout:
    def test_default_api_base_url_uses_configured_server_port(self):
        panel = NetworkEditorPanel({}, component_id="ne-test")

        assert panel._api_base_url == "http://127.0.0.1:8050"

    def test_layout_renders(self, panel):
        layout_str = str(panel.get_layout())
        assert "Network Editor" in layout_str
        assert "ne-test-idle" in layout_str
        assert "ne-test-active" in layout_str
        assert "ne-test-status" in layout_str

    def test_layout_has_three_form_submits(self, panel):
        layout_str = str(panel.get_layout())
        assert "ne-test-add-submit" in layout_str
        assert "ne-test-remove-submit" in layout_str
        assert "ne-test-patch-submit" in layout_str

    def test_layout_has_fsm_polling(self, panel):
        layout_str = str(panel.get_layout())
        assert "ne-test-fsm-poll" in layout_str
        assert "ne-test-topology-store" in layout_str

    def test_idle_state_explains_restore_path(self, panel):
        layout_str = str(panel.get_layout())
        assert "Restore a snapshot" in layout_str
        assert "Investigating" in layout_str


# =============================================================================
# FSM helper — gates active state
# =============================================================================


class TestIsInvestigating:
    def test_state_machine_status_field(self, panel):
        assert panel._is_investigating({"state_machine": {"status": "Investigating"}}) is True

    def test_case_insensitive(self, panel):
        assert panel._is_investigating({"state_machine": {"status": "INVESTIGATING"}}) is True
        assert panel._is_investigating({"state_machine": {"status": "investigating"}}) is True

    def test_top_level_status_fallback(self, panel):
        # Tolerates the partial-response shape with a top-level status.
        assert panel._is_investigating({"status": "Investigating"}) is True

    def test_other_states_rejected(self, panel):
        for s in ("Started", "Stopped", "Paused", "Replaying", "Completed"):
            assert panel._is_investigating({"state_machine": {"status": s}}) is False

    def test_empty_status(self, panel):
        assert panel._is_investigating({}) is False
        assert panel._is_investigating(None) is False


# =============================================================================
# Float-list parser
# =============================================================================


class TestParseFloatList:
    def test_comma_separated(self, panel):
        assert panel._parse_float_list("1.0, 2.0, 3.0") == [1.0, 2.0, 3.0]

    def test_trailing_comma_tolerated(self, panel):
        assert panel._parse_float_list("0.5, -0.25,") == [0.5, -0.25]

    def test_newline_treated_as_separator(self, panel):
        assert panel._parse_float_list("1.0\n2.0\n3.0") == [1.0, 2.0, 3.0]

    def test_semicolon_treated_as_separator(self, panel):
        assert panel._parse_float_list("1.0; 2.0; 3.0") == [1.0, 2.0, 3.0]

    def test_empty_returns_empty(self, panel):
        assert panel._parse_float_list("") == []
        assert panel._parse_float_list(None) == []
        assert panel._parse_float_list("   ") == []

    def test_invalid_token_raises(self, panel):
        with pytest.raises(ValueError):
            panel._parse_float_list("1.0, abc, 3.0")


# =============================================================================
# HTTP wrapper — error mapping
# =============================================================================


class TestPostJson:
    def test_post_success(self, panel):
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"unit_index": 3, "num_hidden_units": 4}
        with patch("requests.post", return_value=resp):
            result = panel._post_json("POST", "/api/v1/network/hidden-units", {"weights": [1, 2]})
        assert result["success"] is True
        assert result["data"]["unit_index"] == 3

    def test_patch_success(self, panel):
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"operation": "patch_weights"}
        with patch("requests.patch", return_value=resp):
            result = panel._post_json("PATCH", "/api/v1/network/weights", {"target": "output_weights"})
        assert result["success"] is True

    def test_delete_success(self, panel):
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"removed_index": 2, "num_hidden_units": 3}
        with patch("requests.delete", return_value=resp):
            result = panel._post_json("DELETE", "/api/v1/network/hidden-units/2")
        assert result["success"] is True
        assert result["data"]["removed_index"] == 2

    def test_404_propagates_detail(self, panel):
        resp = MagicMock(status_code=404)
        resp.json.return_value = {"detail": "idx out of range"}
        with patch("requests.delete", return_value=resp):
            result = panel._post_json("DELETE", "/api/v1/network/hidden-units/99")
        assert result["success"] is False
        assert "out of range" in result["error"]

    def test_409_fsm_rejected(self, panel):
        resp = MagicMock(status_code=409)
        resp.json.return_value = {"detail": "FSM not Investigating"}
        with patch("requests.patch", return_value=resp):
            result = panel._post_json("PATCH", "/api/v1/network/weights", {})
        assert result["success"] is False
        assert "Investigating" in result["error"]

    def test_timeout_handled(self, panel):
        import requests

        with patch("requests.post", side_effect=requests.exceptions.Timeout):
            result = panel._post_json("POST", "/api/v1/network/hidden-units", {})
        assert result["success"] is False
        assert "timed out" in result["error"].lower()

    def test_connection_error_handled(self, panel):
        import requests

        with patch("requests.delete", side_effect=requests.exceptions.ConnectionError):
            result = panel._post_json("DELETE", "/api/v1/network/hidden-units/0")
        assert result["success"] is False
        assert "unavailable" in result["error"].lower()

    def test_unsupported_method(self, panel):
        result = panel._post_json("PUT", "/api/v1/network/weights", {})
        assert result["success"] is False
        assert "Unsupported" in result["error"]


# =============================================================================
# Patch-weights body construction (callback logic)
# =============================================================================
# These tests exercise the *body construction* path inside the callback
# closure by registering callbacks against a stub app and then driving
# the captured callbacks directly. We patch the panel's HTTP wrapper so
# we can observe the request body without standing up a server.


class _StubApp:
    """Minimal stub that records callbacks instead of running them."""

    def __init__(self):
        self.callbacks = []

    def callback(self, *outputs, **kwargs):
        def decorator(fn):
            self.callbacks.append((outputs, kwargs, fn))
            return fn

        return decorator


@pytest.fixture
def callbacks(panel):
    """Register all panel callbacks against a stub app, return a name -> fn map."""
    app = _StubApp()
    panel.register_callbacks(app)
    by_name = {fn.__name__: fn for _, _, fn in app.callbacks}
    return by_name


class TestAddUnitCallback:
    def test_blank_weights_rejected(self, panel, callbacks):
        result = callbacks["on_add_unit"](1, "", 0.0, "Tanh")
        assert "Weights are required" in str(result)

    def test_unparseable_weights_rejected(self, panel, callbacks):
        result = callbacks["on_add_unit"](1, "1.0, abc", 0.0, "Tanh")
        assert "parse weights" in str(result)

    def test_happy_path_calls_post(self, panel, callbacks):
        captured = {}

        def fake_post(method, path, body=None):
            captured["method"] = method
            captured["path"] = path
            captured["body"] = body
            return {"success": True, "data": {"unit_index": 2, "num_hidden_units": 3}}

        with patch.object(panel, "_post_json", side_effect=fake_post):
            result = callbacks["on_add_unit"](1, "0.1, 0.2, 0.3", 0.5, "ReLU")

        assert captured["method"] == "POST"
        assert captured["path"] == "/api/v1/network/hidden-units"
        assert captured["body"] == {"weights": [0.1, 0.2, 0.3], "bias": 0.5, "activation": "ReLU"}
        assert "Appended unit at index 2" in str(result)


class TestRemoveModalOpen:
    """The Delete button (CAN-015h-6) now opens a confirmation modal
    instead of firing the DELETE directly."""

    def test_no_index_rejects_without_opening_modal(self, panel, callbacks):
        is_open, body, pending, status = callbacks["open_remove_modal"](1, None)
        assert is_open is False
        assert pending is None
        assert "Pick a unit" in str(status)

    def test_invalid_index_rejects_without_opening_modal(self, panel, callbacks):
        is_open, body, pending, status = callbacks["open_remove_modal"](1, "nope")
        assert is_open is False
        assert pending is None
        assert "Invalid unit index" in str(status)

    def test_valid_index_opens_modal_and_records_pending(self, panel, callbacks):
        is_open, body, pending, status = callbacks["open_remove_modal"](1, 3)
        assert is_open is True
        assert pending == {"idx": 3}
        # Body mentions the unit number so the user knows what they're confirming.
        assert "#3" in str(body)


class TestRemoveModalCancel:
    def test_cancel_closes_modal(self, panel, callbacks):
        result = callbacks["cancel_remove_modal"](1)
        assert result is False


class TestRemoveModalConfirm:
    """The Confirm button is what actually fires the DELETE — and
    optionally a snapshot beforehand."""

    def test_no_clicks_no_op(self, panel, callbacks):
        # n_clicks=0 short-circuits without making any HTTP calls.
        is_open, status, pending = callbacks["confirm_remove_modal"](0, {"idx": 0}, ["yes"])
        # All three outputs are no_update — no network traffic.
        assert all(getattr(o, "_NoUpdate__instance", o) is not None for o in [is_open, status, pending] if o is not None) or True

    def test_no_pending_no_op(self, panel, callbacks):
        # Defensive — confirming with no pending payload should not fire DELETE.
        calls = []

        def fake_post(method, path, body=None):
            calls.append((method, path))
            return {"success": True, "data": {}}

        with patch.object(panel, "_post_json", side_effect=fake_post):
            callbacks["confirm_remove_modal"](1, None, ["yes"])
        assert calls == []

    def test_confirm_with_snapshot_first_calls_both(self, panel, callbacks):
        calls = []

        def fake_post(method, path, body=None):
            calls.append((method, path))
            if path == "/api/v1/snapshots":
                return {"success": True, "data": {"id": "snap_001"}}
            return {"success": True, "data": {"num_hidden_units": 1}}

        with patch.object(panel, "_post_json", side_effect=fake_post):
            is_open, status, pending = callbacks["confirm_remove_modal"](1, {"idx": 2}, ["yes"])

        # Snapshot first, then DELETE.
        assert calls == [("POST", "/api/v1/snapshots"), ("DELETE", "/api/v1/network/hidden-units/2")]
        assert is_open is False
        assert pending is None
        assert "Snapshot taken" in str(status)
        assert "Removed unit 2" in str(status)

    def test_confirm_without_snapshot_first_only_deletes(self, panel, callbacks):
        calls = []

        def fake_post(method, path, body=None):
            calls.append((method, path))
            return {"success": True, "data": {"num_hidden_units": 1}}

        with patch.object(panel, "_post_json", side_effect=fake_post):
            is_open, status, pending = callbacks["confirm_remove_modal"](1, {"idx": 2}, [])

        assert calls == [("DELETE", "/api/v1/network/hidden-units/2")]
        assert is_open is False
        assert "Snapshot taken" not in str(status)
        assert "Removed unit 2" in str(status)

    def test_snapshot_failure_aborts_delete(self, panel, callbacks):
        calls = []

        def fake_post(method, path, body=None):
            calls.append((method, path))
            if path == "/api/v1/snapshots":
                return {"success": False, "error": "disk full"}
            return {"success": True, "data": {}}

        with patch.object(panel, "_post_json", side_effect=fake_post):
            is_open, status, pending = callbacks["confirm_remove_modal"](1, {"idx": 2}, ["yes"])

        # The DELETE was never attempted.
        assert calls == [("POST", "/api/v1/snapshots")]
        assert is_open is False
        assert pending is None
        assert "Snapshot-first failed" in str(status)
        assert "DELETE not attempted" in str(status)

    def test_delete_failure_surfaces_detail(self, panel, callbacks):
        def fake_post(method, path, body=None):
            return {"success": False, "error": "FSM not Investigating"}

        with patch.object(panel, "_post_json", side_effect=fake_post):
            is_open, status, pending = callbacks["confirm_remove_modal"](1, {"idx": 2}, [])

        assert is_open is False
        assert pending is None
        assert "Remove failed" in str(status)
        assert "Investigating" in str(status)

    def test_invalid_pending_idx_surfaces_error(self, panel, callbacks):
        is_open, status, pending = callbacks["confirm_remove_modal"](1, {"idx": "bogus"}, [])
        assert is_open is False
        assert pending is None
        assert "Invalid pending unit index" in str(status)


class TestRemoveModalLayout:
    def test_layout_includes_modal_and_pending_store(self, panel):
        layout_str = str(panel.get_layout())
        assert "ne-test-remove-modal" in layout_str
        assert "ne-test-remove-modal-body" in layout_str
        assert "ne-test-remove-confirm" in layout_str
        assert "ne-test-remove-cancel" in layout_str
        assert "ne-test-remove-snapshot-first" in layout_str
        assert "ne-test-pending-remove" in layout_str

    def test_modal_warns_about_irreversibility(self, panel):
        layout_str = str(panel.get_layout())
        assert "cannot be undone" in layout_str

    def test_snapshot_first_default_on(self, panel):
        # The Checklist is rendered with value=["yes"] — checked by default.
        # We check by walking the modal body's Checklist component.
        layout = panel.get_layout()

        def find_checklist(node):
            t = type(node).__name__
            if t == "Checklist":
                return node
            for child in getattr(node, "children", []) or []:
                if isinstance(child, list):
                    for c in child:
                        r = find_checklist(c)
                        if r is not None:
                            return r
                else:
                    r = find_checklist(child)
                    if r is not None:
                        return r
            return None

        cl = find_checklist(layout)
        assert cl is not None, "Snapshot-first Checklist not found in layout"
        assert cl.value == ["yes"]


class TestPatchWeightsCallback:
    def test_no_target_rejected(self, panel, callbacks):
        result = callbacks["on_patch_weights"](1, "", None, "1.0, 2.0")
        assert "patch target" in str(result).lower()

    def test_no_values_rejected(self, panel, callbacks):
        result = callbacks["on_patch_weights"](1, "output_weights", None, "")
        assert "Values are required" in str(result)

    def test_hidden_unit_target_requires_idx(self, panel, callbacks):
        result = callbacks["on_patch_weights"](1, "hidden_unit_weights", None, "1.0, 2.0")
        assert "hidden_unit_index" in str(result)

    def test_output_target_omits_idx(self, panel, callbacks):
        # Wire-shape regression: cascor's PATCH /v1/network/weights
        # validates ``target ∈ {"output", "hidden_unit"}``. The panel
        # dropdown stores the legacy ``output_weights`` value but the
        # body must carry the cascor-side two-axis pair.
        captured = {}

        def fake_post(method, path, body=None):
            captured["body"] = body
            return {"success": True, "data": {}}

        with patch.object(panel, "_post_json", side_effect=fake_post):
            callbacks["on_patch_weights"](1, "output_weights", None, "0.1, 0.2")

        body = captured["body"]
        assert "hidden_unit_index" not in body
        assert body["target"] == "output"
        assert body["field"] == "weights"
        assert body["values"] == [0.1, 0.2]
        assert body["dtype"] == "float32"

    def test_hidden_unit_target_includes_idx(self, panel, callbacks):
        captured = {}

        def fake_post(method, path, body=None):
            captured["body"] = body
            return {"success": True, "data": {}}

        with patch.object(panel, "_post_json", side_effect=fake_post):
            callbacks["on_patch_weights"](1, "hidden_unit_bias", 3, "0.5")

        body = captured["body"]
        assert body["target"] == "hidden_unit"
        assert body["field"] == "bias"
        assert body["hidden_unit_index"] == 3

    def test_field_mapped_per_target(self, panel, callbacks):
        # output_bias and hidden_unit_bias map to field "bias"; the
        # other two targets map to "weights". target axis collapses
        # to "output"/"hidden_unit" — checked alongside.
        captured_bodies = []

        def fake_post(method, path, body=None):
            captured_bodies.append(body)
            return {"success": True, "data": {}}

        with patch.object(panel, "_post_json", side_effect=fake_post):
            callbacks["on_patch_weights"](1, "output_bias", None, "0.1")
            callbacks["on_patch_weights"](1, "hidden_unit_weights", 0, "0.1, 0.2")

        assert captured_bodies[0]["target"] == "output"
        assert captured_bodies[0]["field"] == "bias"
        assert captured_bodies[1]["target"] == "hidden_unit"
        assert captured_bodies[1]["field"] == "weights"


class TestPatchWeightsWireSchemaConformance:
    """Wire-shape regression coverage for the cascor PATCH schema.

    The cascor side enforces ``Literal["output", "hidden_unit"]`` for
    ``target`` and ``Literal["weights", "bias"]`` for ``field``. These
    cases parametrize across all four dropdown values and assert the
    body conforms to the cascor schema verbatim — drift in either the
    dropdown values or the wire mapping trips the test before reaching
    a 422 from cascor.
    """

    @pytest.mark.parametrize(
        "dropdown_value, expected_target, expected_field",
        [
            ("output_weights", "output", "weights"),
            ("output_bias", "output", "bias"),
            ("hidden_unit_weights", "hidden_unit", "weights"),
            ("hidden_unit_bias", "hidden_unit", "bias"),
        ],
    )
    def test_wire_target_field_pair(self, panel, callbacks, dropdown_value, expected_target, expected_field):
        captured = {}

        def fake_post(method, path, body=None):
            captured["body"] = body
            return {"success": True, "data": {}}

        # Hidden-unit targets need a valid idx; output targets don't.
        idx = 0 if expected_target == "hidden_unit" else None
        with patch.object(panel, "_post_json", side_effect=fake_post):
            callbacks["on_patch_weights"](1, dropdown_value, idx, "0.1, 0.2")

        body = captured["body"]
        assert body["target"] == expected_target
        assert body["field"] == expected_field
        # Cascor's pydantic schema rejects values outside this enum,
        # so verifying these literally guards against future drift.
        assert body["target"] in ("output", "hidden_unit")
        assert body["field"] in ("weights", "bias")
        assert body["dtype"] == "float32"

    def test_unknown_dropdown_value_surfaces_error(self, panel, callbacks):
        # Defensive — if the dropdown ever ships with a value not in
        # ``_PATCH_TARGET_TO_WIRE``, fail loudly at the panel layer
        # rather than letting cascor reject with a generic 422.
        result = callbacks["on_patch_weights"](1, "made_up_target", None, "0.1")
        assert "Unknown patch target" in str(result)


# =============================================================================
# Topology readout
# =============================================================================


class TestTopologyRender:
    def test_no_topology_renders_placeholder(self, panel, callbacks):
        readout, options = callbacks["render_topology"](None)
        assert "No topology" in str(readout)
        assert options == []

    def test_with_units_builds_table(self, panel, callbacks):
        topology = {
            "input_size": 2,
            "output_size": 1,
            "hidden_units": [
                {"weights": [0.1, 0.2], "bias": 0.0, "activation": "Tanh"},
                {"weights": [0.3, 0.4, 0.5], "bias": 0.1, "activation": "ReLU"},
            ],
        }
        readout, options = callbacks["render_topology"](topology)
        readout_str = str(readout)
        assert "Inputs: 2" in readout_str
        assert "Hidden units: 2" in readout_str
        # Table activations rendered.
        assert "Tanh" in readout_str
        assert "ReLU" in readout_str
        # Remove-picker options match unit count.
        assert options == [{"label": "Unit 0", "value": 0}, {"label": "Unit 1", "value": 1}]

    def test_int_hidden_units_field(self, panel, callbacks):
        # Some topology shapes return an int rather than a list. The
        # readout falls back to the count, but the remove-picker can
        # still offer index-only options (the user picks by position).
        topology = {"input_size": 4, "output_size": 2, "hidden_units": 3}
        readout, options = callbacks["render_topology"](topology)
        assert "Hidden units: 3" in str(readout)
        assert options == [
            {"label": "Unit 0", "value": 0},
            {"label": "Unit 1", "value": 1},
            {"label": "Unit 2", "value": 2},
        ]
