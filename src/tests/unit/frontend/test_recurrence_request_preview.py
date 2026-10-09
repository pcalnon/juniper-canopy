#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_recurrence_request_preview.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-10-08
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   W1.2 / ruling R7 -- the read-only "effective request"
#                preview above Start (frontend/components/
#                recurrence_request_preview.py).
#####################################################################
"""The effective-request preview panel (W1.2 / ruling R7).

juniper-ml plan ``notes/JUNIPER_2026-10-03_JUNIPER-RECURRENCE_EQUITIES-END-TO-END-AUDIT-AND-DEVELOPMENT-PLAN.md``,
finding F-C2: "No preview of the effective request before Start". That the panel shows exactly what
Start sends is pinned end to end in ``tests/regression/test_recurrence_staging.py``
(``test_an_edited_regression_target_is_sent_and_the_preview_matches``); this module pins the panel.
"""

import json
from unittest import mock

import dash
import pytest
import requests

from frontend.components import recurrence_request_preview as module
from frontend.components.recurrence_request_preview import BANNER_EDGE_JS, EFFECTIVE_REQUEST_PATH, RecurrenceRequestPreview
from frontend.dashboard_manager import DashboardManager

CID = "recurrence-request-preview"
REQUEST = {"dataset": {"split": "train", "generator": "equities_seq", "params": {"symbols": ["AAPL"], "regression_target": "next_close"}}}
START_BODY = {"dataset": {"generator": "equities_seq", "params": {"symbols": ["AAPL"]}}}


def _ok_payload(**extra):
    return {"ok": True, "source": "staged", "request": REQUEST, "not_forwarded": [], "edited": [], "fit_in_progress": False, **extra}


def _response(status_code=200, payload=None, json_error=False):
    resp = mock.MagicMock(status_code=status_code)
    if json_error:
        resp.json.side_effect = ValueError("no json")
    else:
        resp.json.return_value = payload
    return resp


def _text(component):
    if component is None:
        return ""
    if isinstance(component, str):
        return component
    if isinstance(component, (list, tuple)):
        return " ".join(_text(child) for child in component)
    return _text(getattr(component, "children", None))


def _ids_in_order(node, found=None):
    """Every component id in the tree, depth-first in render order (a ``dcc.Store`` has no children)."""
    found = [] if found is None else found
    if isinstance(node, (list, tuple)):
        for child in node:
            _ids_in_order(child, found)
    elif node is not None and not isinstance(node, (str, int, float)):
        if getattr(node, "id", None) is not None:
            found.append(node.id)
        _ids_in_order(getattr(node, "children", None), found)
    return found


@pytest.fixture
def preview():
    return RecurrenceRequestPreview({"api_base_url": "http://canopy.test:8050", "api_timeout": 3}, component_id=CID)


@pytest.mark.unit
class TestLayout:
    def test_hidden_until_a_one_shot_model_is_selected(self, preview):
        layout = preview.get_layout()
        assert layout.id == CID and layout.style == {"display": "none"}

    def test_it_carries_a_body_notes_refresh_and_its_edge_store(self, preview):
        ids = set(_ids_in_order(preview.get_layout()))
        assert {f"{CID}-body", f"{CID}-notes", f"{CID}-refresh", f"{CID}-banner-edge"} <= ids

    def test_the_defaults_come_from_settings_and_constants(self):
        panel = RecurrenceRequestPreview({})
        assert panel._api_base_url.startswith("http://127.0.0.1:")
        assert panel.api_timeout > 0 and panel.component_id == CID


@pytest.mark.unit
class TestRefreshHandler:
    def test_a_live_model_shows_nothing_and_asks_nothing(self, preview):
        with mock.patch.object(module.requests, "post") as post:
            assert preview._refresh_handler(model_class="live", start_body=None) == ({"display": "none"}, "", "")
        post.assert_not_called()

    def test_the_request_is_rendered_as_json(self, preview):
        with mock.patch.object(module.requests, "post", return_value=_response(payload=_ok_payload())) as post:
            style, body, notes = preview._refresh_handler(model_class="one_shot", start_body=START_BODY)
        assert style == {"display": "block"}
        assert json.loads(body) == REQUEST
        assert "the staged dataset (Apply)" in _text(notes)
        args, kwargs = post.call_args
        assert args[0] == f"http://canopy.test:8050{EFFECTIVE_REQUEST_PATH}"
        assert kwargs["json"] == START_BODY and kwargs["timeout"] == 3.0 and "headers" in kwargs

    def test_no_start_body_posts_an_empty_one(self, preview):
        with mock.patch.object(module.requests, "post", return_value=_response(payload=_ok_payload(source="start_body"))) as post:
            _style, _body, notes = preview._refresh_handler(model_class="one_shot", start_body=None)
        assert post.call_args.kwargs["json"] == {}
        assert "the Start body" in _text(notes)

    def test_the_notes_name_edits_withheld_keys_and_a_running_fit(self, preview):
        payload = _ok_payload(edited=["regression_target"], not_forwarded=["nn_dataset_elements", "nn_dataset_noise"], fit_in_progress=True)
        with mock.patch.object(module.requests, "post", return_value=_response(payload=payload)):
            _style, _body, notes = preview._refresh_handler(model_class="one_shot", start_body=START_BODY)
        text = _text(notes)
        assert "Edited in the form, so sent over the registry defaults: regression_target." in text
        assert "Staged but not sent" in text and "nn_dataset_elements, nn_dataset_noise" in text
        assert "A fit is in progress" in text

    def test_a_refusal_is_shown_in_place_of_the_body(self, preview):
        refused = _response(status_code=409, payload={"ok": False, "error": "Training could not be started: recurrence is not active"})
        with mock.patch.object(module.requests, "post", return_value=refused):
            style, body, notes = preview._refresh_handler(model_class="one_shot", start_body=START_BODY)
        assert style == {"display": "block"} and body == ""
        assert notes == "No request to preview: Training could not be started: recurrence is not active"

    def test_no_reference_is_shown_with_the_backend_s_reason(self, preview):
        with mock.patch.object(module.requests, "post", return_value=_response(payload={"ok": False, "error": "no dataset reference"})):
            _style, body, notes = preview._refresh_handler(model_class="one_shot", start_body=None)
        assert body == "" and notes == "No request to preview: no dataset reference"

    def test_an_error_without_a_reason_falls_back_to_the_status(self, preview):
        with mock.patch.object(module.requests, "post", return_value=_response(status_code=502, payload={})):
            _style, _body, notes = preview._refresh_handler(model_class="one_shot", start_body=None)
        assert notes == "No request to preview: HTTP 502"

    def test_a_body_that_is_not_json_is_named(self, preview):
        with mock.patch.object(module.requests, "post", return_value=_response(status_code=500, json_error=True)):
            _style, body, notes = preview._refresh_handler(model_class="one_shot", start_body=None)
        assert body == "" and notes == "Could not compute the effective request: HTTP 500 without a JSON body."

    def test_an_unreachable_canopy_is_named_not_raised(self, preview):
        with mock.patch.object(module.requests, "post", side_effect=requests.ConnectionError("refused")):
            style, body, notes = preview._refresh_handler(model_class="one_shot", start_body=None)
        assert style == {"display": "block"} and body == ""
        assert notes == "Could not compute the effective request: canopy did not answer (ConnectionError)."


@pytest.mark.unit
class TestCallbacks:
    @pytest.fixture
    def app(self, preview):
        app = dash.Dash(__name__, suppress_callback_exceptions=True)
        preview.register_callbacks(app)
        return app

    def test_the_server_callback_is_driven_by_events_never_an_interval(self, app):
        entry = next(entry for key, entry in app.callback_map.items() if f"{CID}.style" in key)
        inputs = {(i["id"], i["property"]) for i in entry["inputs"]}
        assert inputs == {("oneshot-start-params-store", "data"), ("dataset-stage-outcome-alert", "children"), (f"{CID}-banner-edge", "data"), (f"{CID}-refresh", "n_clicks")}
        assert not any("interval" in i["id"] for i in entry["inputs"])
        assert [(s["id"], s["property"]) for s in entry["state"]] == [("model-class-store", "data")]

    def test_the_registered_callback_runs_the_handler(self, app, preview):
        entry = next(entry for key, entry in app.callback_map.items() if f"{CID}.style" in key)
        fn = entry["callback"]
        inner = getattr(fn, "__wrapped__", fn)
        with mock.patch.object(module.requests, "post") as post:
            assert inner(None, None, None, None, "live") == ({"display": "none"}, "", "")
        post.assert_not_called()

    def test_the_banner_edge_detector_is_clientside_and_writes_only_its_store(self, app):
        clientside = [entry for key, entry in app.callback_map.items() if key == f"{CID}-banner-edge.data"]
        assert len(clientside) == 1
        assert [(i["id"], i["property"]) for i in clientside[0]["inputs"]] == [("pending-dataset-banner", "is_open")]

    def test_the_edge_detector_idles_unless_the_banner_changed(self):
        # The banner is rewritten every 5 s by the slow-lane poll; only a CHANGE may reach the server.
        assert "previous.open === open" in BANNER_EDGE_JS
        assert "return window.dash_clientside.no_update;" in BANNER_EDGE_JS
        assert "return {open: open};" in BANNER_EDGE_JS


@pytest.mark.unit
class TestTheDashboardCarriesIt:
    @pytest.fixture(scope="class")
    def manager(self):
        return DashboardManager({})

    def test_the_panel_sits_above_the_start_button(self, manager):
        order = [found for found in _ids_in_order(manager.app.layout) if found in (CID, "start-button")]
        assert order == [CID, "start-button"], order

    def test_it_is_a_registered_component(self, manager):
        assert manager.get_component(CID) is manager.recurrence_request_preview
