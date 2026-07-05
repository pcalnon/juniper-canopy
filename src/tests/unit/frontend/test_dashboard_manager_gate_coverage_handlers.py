#!/usr/bin/env python
"""Per-file coverage gate: direct handler-method tests for dashboard_manager.py.

Targets the still-uncovered branches inside the ``_*_handler`` methods that the
existing suite exercises only on their happy paths:

* dataset generate / load / import-file / import-url handlers (error + edge branches)
* store handlers (metrics / topology / raw-topology / dataset / boundary) non-OK branches
* ``_classify_exception_failure`` generic-exception fallback
* ``_extract_training_error_detail`` message-without-status branch
* ``_sync_multi_node_checkboxes_handler`` no-trigger fallback
* ``_apply_parameters_handler`` verification-mismatch / skipped-keys / timeout-retry paths
* ``_parse_retry_after`` non-numeric / negative fallbacks
* ``_merge_ws_dataset_swap_events_handler`` non-dict existing-event skip

Every test asserts real handler behaviour — never ``assert True``. Handlers are
invoked directly (the established pattern in test_dashboard_manager_handlers.py).
"""

from unittest.mock import MagicMock, patch

import dash
import pytest
import requests

import frontend.dashboard_manager as dmmod
from canopy_constants import DashboardConstants
from frontend.dashboard_manager import DashboardManager


@pytest.fixture
def dm():
    return DashboardManager({})


def _resp(*, ok=True, status=200, json_value=None, raises_json=None, text="", content=b""):
    r = MagicMock()
    r.ok = ok
    r.status_code = status
    if raises_json is not None:
        r.json.side_effect = raises_json
    else:
        r.json.return_value = json_value if json_value is not None else {}
    r.text = text
    r.content = content
    return r


# ---------------------------------------------------------------------------
# _generate_dataset_handler (lines 3474-3488)
# ---------------------------------------------------------------------------
class TestGenerateDatasetHandler:
    @patch("requests.post")
    def test_success_returns_payload(self, mock_post, dm):
        mock_post.return_value = _resp(ok=True, json_value={"num_samples": 200})
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            status, data = dm._generate_dataset_handler(200, 2, 1.5, 0.1)
        assert "generated" in status.lower()
        assert data == {"num_samples": 200}

    @patch("requests.post")
    def test_non_ok_returns_error_and_no_update(self, mock_post, dm):
        mock_post.return_value = _resp(ok=False, json_value={"error": "boom"})
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            status, data = dm._generate_dataset_handler(None, None, None, None)
        assert "boom" in status
        assert data is dash.no_update

    @patch("requests.post", side_effect=Exception("net down"))
    def test_exception_returns_error_and_no_update(self, _mock_post, dm):
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            status, data = dm._generate_dataset_handler(200, 2, 1.5, 0.1)
        assert "net down" in status
        assert data is dash.no_update


# ---------------------------------------------------------------------------
# _load_selected_dataset_handler (lines 3498-3516)
# ---------------------------------------------------------------------------
class TestLoadSelectedDatasetHandler:
    def test_no_click_or_generator_no_update(self, dm):
        assert dm._load_selected_dataset_handler(None, "xor") == (dash.no_update, dash.no_update)
        assert dm._load_selected_dataset_handler(1, None) == (dash.no_update, dash.no_update)

    @patch("requests.post")
    def test_success(self, mock_post, dm):
        mock_post.return_value = _resp(ok=True, json_value={"num_samples": 100})
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            status, data = dm._load_selected_dataset_handler(1, "xor")
        assert "xor" in status and status.startswith("✅")
        assert data == {"num_samples": 100}

    @patch("requests.post")
    def test_non_ok_with_json_error(self, mock_post, dm):
        mock_post.return_value = _resp(ok=False, status=503, json_value={"error": "service down"})
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            status, data = dm._load_selected_dataset_handler(1, "moon")
        assert "service down" in status
        assert data is dash.no_update

    @patch("requests.post")
    def test_non_ok_json_raises_uses_http_code(self, mock_post, dm):
        mock_post.return_value = _resp(ok=False, status=500, raises_json=ValueError("bad json"))
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            status, data = dm._load_selected_dataset_handler(1, "circles")
        assert "HTTP 500" in status
        assert data is dash.no_update

    @patch("requests.post", side_effect=Exception("connreset"))
    def test_exception(self, _mock_post, dm):
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            status, data = dm._load_selected_dataset_handler(1, "xor")
        assert "connreset" in status
        assert data is dash.no_update


# ---------------------------------------------------------------------------
# _import_dataset_file_handler (lines 3526-3551)
# ---------------------------------------------------------------------------
class TestImportDatasetFileHandler:
    def test_no_contents(self, dm):
        status, data = dm._import_dataset_file_handler(None, "x.csv")
        assert "No file selected" in status
        assert data is dash.no_update

    def test_missing_data_url_header(self, dm):
        status, data = dm._import_dataset_file_handler("rawbytesnocomma", "x.csv")
        assert "missing data-URL header" in status
        assert data is dash.no_update

    def test_bad_base64_body(self, dm):
        # A data-URL with an undecodable base64 body (validate=False still raises
        # on certain malformed input lengths/chars via binascii.Error subclassing ValueError).
        status, data = dm._import_dataset_file_handler("data:text/csv;base64,!!!!not*base64", "x.csv")
        # Either decodes to garbage (then POST path) or fails to decode; both are
        # acceptable, but with no requests patch the POST would raise -> Error path.
        assert data is dash.no_update
        assert status.startswith("❌")

    @patch("requests.post")
    def test_success(self, mock_post, dm):
        mock_post.return_value = _resp(ok=True, json_value={"num_samples": 50})
        contents = "data:text/csv;base64,YSxiCjEsMg=="  # "a,b\n1,2"
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            status, data = dm._import_dataset_file_handler(contents, "data.csv")
        assert "Imported data.csv" in status
        assert data == {"num_samples": 50}

    @patch("requests.post")
    def test_non_ok_json_raises_uses_http_code(self, mock_post, dm):
        mock_post.return_value = _resp(ok=False, status=422, raises_json=ValueError("x"))
        contents = "data:text/csv;base64,YSxiCjEsMg=="
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            status, data = dm._import_dataset_file_handler(contents, "data.csv")
        assert "HTTP 422" in status
        assert data is dash.no_update

    @patch("requests.post", side_effect=Exception("boom"))
    def test_exception(self, _mock_post, dm):
        contents = "data:text/csv;base64,YSxiCjEsMg=="
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            status, data = dm._import_dataset_file_handler(contents, "data.csv")
        assert "boom" in status
        assert data is dash.no_update


# ---------------------------------------------------------------------------
# _import_dataset_url_handler (lines 3561-3575)
# ---------------------------------------------------------------------------
class TestImportDatasetUrlHandler:
    def test_empty_url(self, dm):
        status, data = dm._import_dataset_url_handler("   ")
        assert "Enter a URL" in status
        assert data is dash.no_update

    @patch("requests.post")
    def test_success(self, mock_post, dm):
        mock_post.return_value = _resp(ok=True, json_value={"num_samples": 30})
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            status, data = dm._import_dataset_url_handler("https://x/y.csv")
        assert "Imported from https://x/y.csv" in status
        assert data == {"num_samples": 30}

    @patch("requests.post")
    def test_non_ok_json_raises(self, mock_post, dm):
        mock_post.return_value = _resp(ok=False, status=404, raises_json=ValueError("x"))
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            status, data = dm._import_dataset_url_handler("https://x/y.csv")
        assert "HTTP 404" in status
        assert data is dash.no_update

    @patch("requests.post", side_effect=Exception("timeout"))
    def test_exception(self, _mock_post, dm):
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            status, data = dm._import_dataset_url_handler("https://x/y.csv")
        assert "timeout" in status
        assert data is dash.no_update


# ---------------------------------------------------------------------------
# _classify_exception_failure generic branch (line 4873)
# ---------------------------------------------------------------------------
class TestClassifyExceptionFailure:
    def test_timeout(self, dm):
        assert dm._classify_exception_failure(requests.Timeout())[0] == "Backend Timeout"

    def test_connection_error(self, dm):
        assert dm._classify_exception_failure(requests.ConnectionError())[0] == "Unreachable"

    def test_generic_exception_names_type(self, dm):
        label, detail = dm._classify_exception_failure(ValueError("nope"))
        assert label == "Error"
        assert "ValueError" in detail


# ---------------------------------------------------------------------------
# Store handlers: non-OK branches + mode/guard branches
# ---------------------------------------------------------------------------
class TestStoreHandlerBranches:
    @patch("requests.get")
    def test_metrics_full_mode_and_non_ok(self, mock_get, dm):
        # mode == "full" -> limit=0 branch (line 5208), then non-OK -> [] (5214-5215)
        mock_get.return_value = _resp(ok=False, status=500)
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dm._update_metrics_store_handler(n=1, display_mode_state={"mode": "full"}, ws_status=None)
        assert result == []

    @patch("requests.get")
    def test_metrics_gauge_registration_failure_swallowed(self, mock_get, dm):
        # Force the observability import path to raise so the gauge except: branch
        # (lines 5245-5246 -> self._rest_bytes_gauge = None) is taken, and the
        # handler still returns the metrics list.
        mock_get.return_value = _resp(ok=True, json_value={"history": [{"epoch": 1}]})
        with patch("juniper_observability.register_or_reuse", side_effect=RuntimeError("no registry")):
            with dm.app.server.test_request_context(base_url="http://localhost:8050"):
                result = dm._update_metrics_store_handler(n=1, display_mode_state={"mode": "full"}, ws_status=None)
        assert result == [{"epoch": 1}]
        assert dm._rest_bytes_gauge is None

    @patch("requests.get")
    def test_topology_non_ok(self, mock_get, dm):
        mock_get.return_value = _resp(ok=False, status=502)
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dm._update_topology_store_handler(n=1, active_tab="topology")
        assert result is dash.no_update

    def test_raw_topology_guard_wrong_tab(self, dm):
        assert dm._update_raw_topology_store_handler(n=1, active_tab="metrics", view_mode="weight_matrix") is dash.no_update

    def test_raw_topology_guard_wrong_view(self, dm):
        assert dm._update_raw_topology_store_handler(n=1, active_tab="topology", view_mode="graph") is dash.no_update

    @patch("requests.get")
    def test_raw_topology_success(self, mock_get, dm):
        mock_get.return_value = _resp(ok=True, json_value={"weights": [[1, 2]]})
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dm._update_raw_topology_store_handler(n=1, active_tab="topology", view_mode="weight_matrix")
        assert result == {"weights": [[1, 2]]}

    @patch("requests.get")
    def test_raw_topology_non_ok(self, mock_get, dm):
        mock_get.return_value = _resp(ok=False, status=500)
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dm._update_raw_topology_store_handler(n=1, active_tab="topology", view_mode="weight_matrix")
        assert result is dash.no_update

    @patch("requests.get", side_effect=Exception("boom"))
    def test_raw_topology_exception(self, _mock_get, dm):
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dm._update_raw_topology_store_handler(n=1, active_tab="topology", view_mode="weight_matrix")
        assert result is dash.no_update

    @patch("requests.get")
    def test_dataset_non_ok(self, mock_get, dm):
        mock_get.return_value = _resp(ok=False, status=503)
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dm._update_dataset_store_handler(n=1, active_tab="dataset")
        assert result is dash.no_update

    @patch("requests.get")
    def test_boundary_non_ok(self, mock_get, dm):
        mock_get.return_value = _resp(ok=False, status=500)
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dm._update_boundary_store_handler(n=1, active_tab="boundaries", resolution=50)
        assert result is dash.no_update

    @patch("requests.get")
    def test_boundary_dataset_non_ok(self, mock_get, dm):
        mock_get.return_value = _resp(ok=False, status=500)
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dm._update_boundary_dataset_store_handler(n=1, active_tab="boundaries")
        assert result is dash.no_update


# ---------------------------------------------------------------------------
# _extract_training_error_detail message-without-status (line 5458)
# ---------------------------------------------------------------------------
class TestExtractTrainingErrorDetail:
    def test_message_without_status(self, dm):
        exc = Exception("outer")
        resp = MagicMock()
        resp.status_code = None
        resp.json.return_value = {"message": "specific reason"}
        exc.response = resp
        assert dm._extract_training_error_detail(exc) == "specific reason"

    def test_status_and_message(self, dm):
        exc = Exception("outer")
        resp = MagicMock()
        resp.status_code = 400
        resp.json.return_value = {"error": {"message": "bad start"}}
        exc.response = resp
        assert dm._extract_training_error_detail(exc) == "HTTP 400: bad start"

    def test_no_response_falls_back_to_exc_string(self, dm):
        exc = ValueError("plain")
        # no .response attribute
        assert "ValueError" in dm._extract_training_error_detail(exc)


# ---------------------------------------------------------------------------
# _sync_multi_node_checkboxes_handler no-trigger fallback (line 5600)
# ---------------------------------------------------------------------------
class TestSyncMultiNodeCheckboxesFallback:
    def test_no_trigger_returns_double_no_update(self, dm):
        fake_ctx = MagicMock()
        fake_ctx.triggered = []
        with patch.object(dmmod.dash, "callback_context", fake_ctx):
            result = dm._sync_multi_node_checkboxes_handler([], [])
        assert result == (dash.no_update, dash.no_update)

    def test_cn_trigger_enabled_syncs_nn(self, dm):
        fake_ctx = MagicMock()
        fake_ctx.triggered = [{"prop_id": "cn-multi-candidate-checkbox.value"}]
        with patch.object(dmmod.dash, "callback_context", fake_ctx):
            result = dm._sync_multi_node_checkboxes_handler([], ["enabled"])
        assert result[0] == ["enabled"]

    def test_nn_trigger_returns_no_update(self, dm):
        fake_ctx = MagicMock()
        fake_ctx.triggered = [{"prop_id": "nn-multi-node-layers-checkbox.value"}]
        with patch.object(dmmod.dash, "callback_context", fake_ctx):
            result = dm._sync_multi_node_checkboxes_handler(["enabled"], [])
        assert result == (dash.no_update, dash.no_update)


# ---------------------------------------------------------------------------
# _apply_parameters_handler verification / skipped / timeout paths
# ---------------------------------------------------------------------------
_APPLY_ARGS = (
    1,  # n_clicks
    1000,  # nn_max_iter
    300,  # nn_max_epochs
    0.02,  # nn_lr
    15,  # nn_max_hu
    [],  # nn_multi_node
    "convergence",
    50,
    0.001,
    50,  # nn_patience
    1.5,
    2,
    1000,
    0.25,
    100,
    0.001,
    1,
    "preset_epochs",
    500,
    0.0001,
    30,  # cn_patience
    [],
    None,
    1,
    1,
)


class TestApplyParametersHandlerBranches:
    @patch("requests.get")
    @patch("requests.post")
    def test_verification_mismatch_and_skipped_list(self, mock_post, mock_get, dm):
        # POST 200 with a skipped list; GET /api/state (verify) 200 with a
        # mismatched value -> both the verification-mismatch branch (5783-5786)
        # and the skipped-keys message branch (5806-5810) execute.
        mock_post.return_value = _resp(ok=True, status=200, json_value={"skipped": ["cn_patience", "nn_patience"]})
        mock_get.return_value = _resp(ok=True, status=200, json_value={"nn_learning_rate": 999.0})
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            result, msg = dm._apply_parameters_handler(*_APPLY_ARGS)
        assert isinstance(result, dict)
        assert "not yet supported" in msg
        assert "cn_patience" in msg

    @patch("requests.get")
    @patch("requests.post")
    def test_body_json_error_defaults_to_applied(self, mock_post, mock_get, dm):
        # POST 200 whose .json() raises -> body=None branch (5800-5801); no skipped
        # -> plain "Parameters applied".
        post_resp = _resp(ok=True, status=200)
        post_resp.json.side_effect = ValueError("bad")
        mock_post.return_value = post_resp
        mock_get.return_value = _resp(ok=True, status=200, json_value={})
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            result, msg = dm._apply_parameters_handler(*_APPLY_ARGS)
        assert isinstance(result, dict)
        assert msg == "Parameters applied"

    @patch("frontend.dashboard_manager.time.sleep")
    @patch("requests.post", side_effect=requests.exceptions.Timeout())
    def test_timeout_retries_then_errors(self, _mock_post, _mock_sleep, dm):
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            result, msg = dm._apply_parameters_handler(*_APPLY_ARGS)
        assert result is dash.no_update
        assert msg.startswith("Error:")


# ---------------------------------------------------------------------------
# _parse_retry_after non-numeric / negative fallbacks (lines 5861-5862)
# ---------------------------------------------------------------------------
class TestParseRetryAfter:
    def test_non_numeric_uses_fallback(self, dm):
        assert dm._parse_retry_after("Wed, 21 Oct 2099 07:28:00 GMT") == DashboardConstants.DASHBOARD_RETRY_AFTER_FALLBACK_S

    def test_none_uses_fallback(self, dm):
        assert dm._parse_retry_after(None) == DashboardConstants.DASHBOARD_RETRY_AFTER_FALLBACK_S

    def test_negative_uses_fallback(self, dm):
        assert dm._parse_retry_after("-5") == DashboardConstants.DASHBOARD_RETRY_AFTER_FALLBACK_S

    def test_valid_seconds_returned(self, dm):
        assert dm._parse_retry_after("7") == 7.0


# ---------------------------------------------------------------------------
# _merge_ws_dataset_swap_events_handler: non-dict WS event skip (lines 4611-4612)
#
# NOTE: the sibling non-dict *existing*-event skip (source line 4603) is NOT
# unit-tested here: reaching it requires a non-dict entry already in
# current_store["events"], but the handler then copies existing verbatim into
# ``merged`` (line 4609) and its own ``merged.sort(key=lambda e: e.get(...))``
# (line 4624) raises AttributeError on that same non-dict. The path is only
# reachable via input that crashes the handler downstream (a latent source
# bug), so it cannot be exercised with a meaningful assertion.
# ---------------------------------------------------------------------------
class TestMergeWsDatasetSwapEventsNonDict:
    def test_non_dict_ws_event_skipped(self, dm):
        ws_buffer = {"events": ["not-a-dict", {"timestamp": "t3"}]}
        result = dm._merge_ws_dataset_swap_events_handler(ws_buffer=ws_buffer, current_store={"events": []})
        timestamps = [e.get("timestamp") for e in result["events"] if isinstance(e, dict)]
        assert "t3" in timestamps
        assert "not-a-dict" not in result["events"]
