"""N3 / N3b (canopy training-runtime defects plan, I-6) — restart-orchestration handlers.

Direct-invocation tests for the ``_*_handler`` methods extracted from
``_setup_restart_orchestration_callbacks`` — the cold-swap confirm modal (Q3/Q4)
and the ``POST /api/train/restart`` outcome rendering. Mirrors the P2-6 live-switch
handler test pattern: ``DashboardManager.__new__`` skips ``__init__`` so we exercise
the branch logic without the full Dash app; ``requests`` is patched at the module.

N3b makes the modal's granular section MODIFY-capable: the open handler seeds the
editable dataset / param fields + a baseline, the summary reflects edits, and Confirm
re-stages the (edited) dataset and applies (edited) params through N5's machinery
BEFORE the stop→await→start orchestration. These tests pin the N3b contract that
supersedes N3's read-only open-handler shape.

The route-level orchestration contract lives in
``tests/integration/test_restart_orchestration_route.py``; the N3b confirm-sequence
integration lives in ``tests/integration/test_n3b_restart_modal_modify.py``.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import dash
import pytest
import requests

from frontend.dashboard_manager import DashboardManager


@pytest.fixture
def dm():
    manager = DashboardManager.__new__(DashboardManager)
    manager.logger = MagicMock()
    manager._api_base_url = "http://test.local"
    return manager


def _text(component):
    """Flatten a Dash/dbc component tree to its concatenated text."""
    if component is None:
        return ""
    if isinstance(component, str):
        return component
    if isinstance(component, (list, tuple)):
        return "".join(_text(c) for c in component)
    return _text(getattr(component, "children", None))


# ---------------------------------------------------------------------------
# _open_restart_confirm_modal_handler
# ---------------------------------------------------------------------------


# N3b: the open handler now returns a 17-tuple wiring the modal-open,
# summary, toggle/collapse resets, context, the 5 editable dataset field
# values, the 6 editable param field values, and the baseline store.
OPEN = {
    "modal": 0,
    "summary": 1,
    "start_fresh": 2,
    "granular_open": 3,
    "context": 4,
    # X2: ``restart-ds-type.options`` is written on open now (it previously had no writer at all
    # and stayed frozen on the cascor gate), so everything from ds_type down shifts by one.
    "ds_options": 5,
    "ds_type": 6,
    "ds_samples": 7,
    "ds_noise": 8,
    "ds_rotations": 9,
    "ds_spirals": 10,
    "p_lr": 11,
    "p_hu": 12,
    "p_patience": 13,
    "p_pool": 14,
    "p_selected": 15,
    "p_corr": 16,
    "baseline": 17,
}

_STATE_JSON = {
    "current_epoch": 12,
    "hidden_units": 5,
    "nn_learning_rate": 0.01,
    "nn_max_hidden_units": 100,
    "nn_patience": 50,
    "cn_pool_size": 8,
    "cn_selected_candidates": 1,
    "cn_correlation_threshold": 0.5,
}


class TestOpenRestartConfirmModalHandler:
    def test_no_clicks_is_all_no_update(self, dm):
        result = dm._open_restart_confirm_modal_handler(n_clicks=None)
        assert result == (dash.no_update,) * 18

    def test_opens_seeds_dataset_params_and_baseline(self, dm):
        with patch("frontend.dashboard_manager.requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = dict(_STATE_JSON)
            result = dm._open_restart_confirm_modal_handler(n_clicks=1, dataset_type="xor", n_samples=300, noise=0.1, rotations=None, n_spirals=None)
        assert len(result) == 18
        assert result[OPEN["modal"]] is True
        # Q4: start-fresh resets OFF and the granular section collapses on open.
        assert result[OPEN["start_fresh"]] is False
        assert result[OPEN["granular_open"]] is False
        # Dataset fields seeded from the sidebar (the currently staged / current config).
        assert result[OPEN["ds_type"]] == "xor"
        assert result[OPEN["ds_samples"]] == 300
        assert result[OPEN["ds_noise"]] == 0.1
        # Param fields seeded (clamped) from /api/state.
        assert result[OPEN["p_lr"]] == 0.01
        assert result[OPEN["p_hu"]] == 100
        assert result[OPEN["p_pool"]] == 8
        # Baseline captures both for the Confirm-time diff.
        baseline = result[OPEN["baseline"]]
        assert baseline["dataset"]["dataset_type"] == "xor"
        assert baseline["params"]["nn_learning_rate"] == 0.01
        # Summary + context reflect the plan.
        assert "xor" in _text(result[OPEN["summary"]])
        assert "12" in _text(result[OPEN["context"]])

    def test_open_clamps_out_of_range_seeded_param(self, dm):
        """N5 delegation: a backend-echoed out-of-range default seeds the
        admissible (clamped) value in BOTH the visible field and the baseline."""
        state = dict(_STATE_JSON, nn_learning_rate=50.0, nn_max_hidden_units=999999)
        with patch("frontend.dashboard_manager.requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = state
            result = dm._open_restart_confirm_modal_handler(n_clicks=1, dataset_type="xor", n_samples=300)
        assert result[OPEN["p_lr"]] == 10.0  # cascor le=10.0
        assert result[OPEN["p_hu"]] == 10000  # cascor le=10_000
        assert result[OPEN["baseline"]]["params"]["nn_learning_rate"] == 10.0

    def test_open_degrades_when_state_unreachable(self, dm):
        with patch("frontend.dashboard_manager.requests.get", side_effect=requests.RequestException("boom")):
            result = dm._open_restart_confirm_modal_handler(n_clicks=1, dataset_type="moons", n_samples=200)
        # Still opens; params blank; context notes unavailable.
        assert result[OPEN["modal"]] is True
        assert result[OPEN["p_lr"]] is None
        assert result[OPEN["baseline"]]["params"]["nn_learning_rate"] is None
        assert "unavailable" in _text(result[OPEN["context"]]).lower()

    def test_empty_dataset_selection_still_opens(self, dm):
        with patch("frontend.dashboard_manager.requests.get", side_effect=requests.RequestException("boom")):
            result = dm._open_restart_confirm_modal_handler(n_clicks=1)
        assert result[OPEN["modal"]] is True
        assert "staged change will be applied" in _text(result[OPEN["summary"]])
        # X2: the modal must not INVENT a dataset the operator never chose; ⊥ survives the open,
        # and Confirm's re-stage guard is what refuses it.
        assert result[OPEN["ds_type"]] is None
        # ...but the list is now regated rather than frozen, so it is populated either way.
        assert result[OPEN["ds_options"]] is not dash.no_update
        assert len(result[OPEN["ds_options"]]) > 0


# ---------------------------------------------------------------------------
# _execute_restart_handler
# ---------------------------------------------------------------------------


class TestExecuteRestartHandler:
    def test_no_clicks_is_all_no_update(self, dm):
        result = dm._execute_restart_handler(n_clicks=None, start_fresh=False)
        assert result == (dash.no_update, dash.no_update, dash.no_update, dash.no_update)

    def test_success_closes_modal_and_banner(self, dm):
        with patch("frontend.dashboard_manager.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"success": True, "was_active": True, "start_fresh": False, "steps": [{"step": "start", "ok": True}]}
            modal, progress, outcome, banner = dm._execute_restart_handler(n_clicks=1, start_fresh=False)
        assert modal is False
        assert progress is False
        assert banner is False  # closed on success
        assert outcome.color == "success"
        assert "Restart succeeded" in _text(outcome)

    def test_forwards_start_fresh_true(self, dm):
        with patch("frontend.dashboard_manager.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"success": True, "was_active": False, "start_fresh": True, "steps": []}
            dm._execute_restart_handler(n_clicks=1, start_fresh=True)
        args, kwargs = mock_post.call_args
        assert args[0].endswith("/api/train/restart")
        assert kwargs["json"] == {"start_fresh": True, "reset": True}

    def test_failure_keeps_banner_open_and_surfaces_detail(self, dm):
        with patch("frontend.dashboard_manager.requests.post") as mock_post:
            mock_post.return_value.status_code = 409
            mock_post.return_value.json.return_value = {"success": False, "message": "Training already in progress"}
            mock_post.return_value.text = "Training already in progress"
            modal, progress, outcome, banner = dm._execute_restart_handler(n_clicks=1, start_fresh=False)
        assert modal is False
        assert progress is False
        assert banner is dash.no_update  # banner stays open on failure
        assert outcome.color == "danger"
        assert "Training already in progress" in _text(outcome)

    def test_timeout_504_marks_retriable(self, dm):
        with patch("frontend.dashboard_manager.requests.post") as mock_post:
            mock_post.return_value.status_code = 504
            mock_post.return_value.json.return_value = {"success": False, "message": "Timed out waiting for the current run to stop", "retriable": True}
            mock_post.return_value.text = ""
            _, _, outcome, banner = dm._execute_restart_handler(n_clicks=1, start_fresh=False)
        assert banner is dash.no_update
        assert outcome.color == "danger"
        assert "retry" in _text(outcome).lower()

    def test_request_exception_surfaces_unreachable(self, dm):
        with patch("frontend.dashboard_manager.requests.post", side_effect=requests.RequestException("connection refused")):
            modal, progress, outcome, banner = dm._execute_restart_handler(n_clicks=1, start_fresh=False)
        assert modal is False
        assert banner is dash.no_update
        assert outcome.color == "danger"
        assert "unreachable" in _text(outcome).lower()


# ---------------------------------------------------------------------------
# _render_restart_outcome
# ---------------------------------------------------------------------------


class TestRenderRestartOutcome:
    def test_success_continue_mentions_continued_model(self):
        alert = DashboardManager._render_restart_outcome({"success": True, "was_active": True, "start_fresh": False}, ok=True)
        assert alert.color == "success"
        text = _text(alert)
        assert "Stopped the running model" in text
        assert "continued the current model" in text

    def test_success_start_fresh_mentions_fresh_model(self):
        alert = DashboardManager._render_restart_outcome({"success": True, "was_active": False, "start_fresh": True}, ok=True)
        assert alert.color == "success"
        assert "fresh model" in _text(alert)

    def test_success_instant_complete_is_truthful(self):
        # Folded finding 2 — an epoch-0 run must read as "converged immediately",
        # not as a frozen dashboard.
        alert = DashboardManager._render_restart_outcome({"success": True, "was_active": False, "start_fresh": True, "instant_complete": True}, ok=True)
        assert "converged immediately" in _text(alert)

    def test_failure_carries_message(self):
        alert = DashboardManager._render_restart_outcome({"message": "boom"}, ok=False)
        assert alert.color == "danger"
        assert "boom" in _text(alert)

    def test_failure_retriable_notes_staged_change(self):
        alert = DashboardManager._render_restart_outcome({"message": "timed out", "retriable": True}, ok=False)
        assert "still staged" in _text(alert)

    # N3b: the outcome reports what the modal re-staged / applied (item 4).
    def test_success_prepends_restage_and_apply_notes(self):
        alert = DashboardManager._render_restart_outcome(
            {"success": True, "was_active": False, "start_fresh": False},
            ok=True,
            restage_note="circles (500 samples)",
            apply_note="Parameters applied",
        )
        text = _text(alert)
        assert "Re-staged dataset to circles (500 samples)" in text
        assert "Parameters applied" in text
        assert "continued the current model" in text

    def test_failure_still_prepends_restage_note(self):
        alert = DashboardManager._render_restart_outcome({"message": "boom"}, ok=False, restage_note="moons")
        text = _text(alert)
        assert "Re-staged dataset to moons" in text
        assert "boom" in text


# ---------------------------------------------------------------------------
# N3b helpers: diff, summary, seed, re-stage, shared apply core
# ---------------------------------------------------------------------------


def _resp(status=200, json_body=None, text=""):
    r = MagicMock(status_code=status)
    r.text = text
    if json_body is None:
        r.json.side_effect = ValueError("no json")
    else:
        r.json.return_value = json_body
    return r


def _post_router(routes):
    """``side_effect`` routing a POST to the mapped response by URL substring."""

    def _post(url, *args, **kwargs):
        for frag, resp in routes.items():
            if frag in url:
                return resp
        raise AssertionError(f"unexpected POST url: {url}")

    return _post


def _baseline():
    return {
        "dataset": {"dataset_type": "xor", "n_samples": 300, "noise": 0.1, "rotations": None, "n_spirals": None},
        "params": {"nn_learning_rate": 0.01, "nn_max_hidden_units": 100, "nn_patience": 50, "cn_pool_size": 8, "cn_selected_candidates": 1, "cn_correlation_threshold": 0.5},
    }


class TestRestartDiffHelpers:
    def test_values_differ_numeric_tolerant(self):
        assert DashboardManager._values_differ(300, 300.0) is False
        assert DashboardManager._values_differ(300, 301) is True
        assert DashboardManager._values_differ("xor", "moons") is True
        assert DashboardManager._values_differ(None, None) is False
        assert DashboardManager._values_differ(None, 3) is True

    def test_dataset_changed(self):
        base = _baseline()["dataset"]
        assert DashboardManager._restart_dataset_changed(dict(base), base) is False
        assert DashboardManager._restart_dataset_changed(dict(base, dataset_type="circles"), base) is True
        assert DashboardManager._restart_dataset_changed(dict(base, n_samples=999), base) is True

    def test_param_updates_only_edited_nonnull(self):
        base = _baseline()["params"]
        updates = DashboardManager._restart_param_updates({"nn_learning_rate": 0.5, "cn_pool_size": 8, "nn_patience": None}, base)
        # only the changed, non-None key is applied
        assert updates == {"nn_learning_rate": 0.5}

    def test_param_updates_empty_when_unchanged(self):
        base = _baseline()["params"]
        assert DashboardManager._restart_param_updates(dict(base), base) == {}


class TestBuildRestartSummary:
    def test_dataset_rows_present(self):
        rows = DashboardManager._build_restart_summary({"dataset_type": "xor", "n_samples": 300}, {}, {})
        text = _text(rows)
        assert "xor" in text and "300" in text

    def test_param_change_reflected(self):
        baseline = {"params": {"nn_learning_rate": 0.01}}
        rows = DashboardManager._build_restart_summary({"dataset_type": "xor"}, {"nn_learning_rate": 0.5}, baseline)
        text = _text(rows)
        assert "Parameter changes" in text
        assert "0.01 → 0.5" in text

    def test_unchanged_param_not_listed(self):
        baseline = {"params": {"nn_learning_rate": 0.01}}
        rows = DashboardManager._build_restart_summary({"dataset_type": "xor"}, {"nn_learning_rate": 0.01}, baseline)
        assert "Parameter changes" not in _text(rows)

    def test_empty_dataset_warns(self):
        rows = DashboardManager._build_restart_summary({}, {}, {})
        assert "staged change will be applied" in _text(rows)


class TestReadRestartParamSeed:
    def test_reads_and_clamps(self, dm):
        with patch("frontend.dashboard_manager.requests.get") as mg:
            mg.return_value.status_code = 200
            mg.return_value.json.return_value = dict(_STATE_JSON, nn_learning_rate=50.0)
            param_vals, context = dm._read_restart_param_seed()
        assert param_vals["nn_learning_rate"] == 10.0  # clamped to cascor le=10.0
        assert param_vals["cn_pool_size"] == 8
        assert "12" in _text(context)  # current_epoch surfaced

    def test_degrades_on_error(self, dm):
        with patch("frontend.dashboard_manager.requests.get", side_effect=requests.RequestException("boom")):
            param_vals, context = dm._read_restart_param_seed()
        assert all(v is None for v in param_vals.values())
        assert "unavailable" in _text(context).lower()


class TestRestageDataset:
    def test_posts_stage_payload_omitting_none(self, dm):
        with patch("frontend.dashboard_manager.requests.post") as mp:
            mp.return_value.status_code = 200
            mp.return_value.text = ""
            ok, detail = dm._restage_dataset({"dataset_type": "circles", "n_samples": 500, "noise": 0.2, "rotations": None, "n_spirals": None})
        assert ok is True
        payload = mp.call_args.kwargs["json"]
        assert payload["nn_dataset_type"] == "circles"
        assert payload["nn_dataset_elements"] == 500
        assert payload["nn_dataset_noise"] == 0.2
        assert "nn_spiral_rotations" not in payload  # None omitted (apply_dataset parity)

    def test_failure_returns_detail(self, dm):
        with patch("frontend.dashboard_manager.requests.post") as mp:
            mp.return_value.status_code = 502
            mp.return_value.text = "Backend rejected dataset: unknown"
            ok, detail = dm._restage_dataset({"dataset_type": "bogus"})
        assert ok is False
        assert "unknown" in detail


class TestApplyParamsViaBackend:
    """The shared N5 apply core the restart modal delegates into."""

    def test_clamps_and_applies(self, dm):
        post = _resp(200, {"status": "success"})
        with patch("frontend.dashboard_manager.requests.post", return_value=post) as mp, patch("frontend.dashboard_manager.requests.get", return_value=_resp(200, {})):
            applied, toast = dm._apply_params_via_backend({"nn_learning_rate": 50.0})
        assert mp.call_args.kwargs["json"]["nn_learning_rate"] == 10.0  # CascorPatchBounds clamp
        assert applied["nn_learning_rate"] == 10.0
        assert "clamped to bounds" in toast

    def test_failure_returns_no_update_and_verbatim_detail(self, dm):
        post = _resp(502, {"error": "Backend rejected parameters: [x]"})
        with patch("frontend.dashboard_manager.requests.post", return_value=post):
            applied, toast = dm._apply_params_via_backend({"nn_learning_rate": 0.5})
        assert applied is dash.no_update
        assert "Backend rejected parameters" in toast


# ---------------------------------------------------------------------------
# N3b confirm sequence: re-stage → apply → restart
# ---------------------------------------------------------------------------


class TestExecuteRestartHandlerN3b:
    def test_dataset_edit_restages_before_restart(self, dm):
        baseline = _baseline()
        dataset_vals = dict(baseline["dataset"], dataset_type="circles")
        routes = {"/api/stage_dataset": _resp(200, {"status": "success"}), "/api/train/restart": _resp(200, {"success": True, "was_active": False, "start_fresh": False, "steps": []})}
        with patch("frontend.dashboard_manager.requests.post", side_effect=_post_router(routes)) as mp, patch("frontend.dashboard_manager.requests.get", return_value=_resp(200, {})):
            modal, progress, outcome, banner = dm._execute_restart_handler(n_clicks=1, start_fresh=False, dataset_vals=dataset_vals, param_vals=dict(baseline["params"]), baseline=baseline)
        urls = [c.args[0] for c in mp.call_args_list]
        assert any("/api/stage_dataset" in u for u in urls)
        stage_i = next(i for i, u in enumerate(urls) if "/api/stage_dataset" in u)
        restart_i = next(i for i, u in enumerate(urls) if "/api/train/restart" in u)
        assert stage_i < restart_i  # re-stage BEFORE the orchestration
        assert banner is False  # success closes the banner
        assert "Re-staged dataset to circles" in _text(outcome)

    def test_param_edit_applies_via_n5_before_restart(self, dm):
        baseline = _baseline()
        param_vals = dict(baseline["params"], nn_learning_rate=0.5)
        routes = {"/api/set_params": _resp(200, {"status": "success", "applied": ["nn_learning_rate"]}), "/api/train/restart": _resp(200, {"success": True, "was_active": False, "start_fresh": False, "steps": []})}
        with patch("frontend.dashboard_manager.requests.post", side_effect=_post_router(routes)) as mp, patch("frontend.dashboard_manager.requests.get", return_value=_resp(200, {})):
            modal, progress, outcome, banner = dm._execute_restart_handler(n_clicks=1, start_fresh=False, dataset_vals=dict(baseline["dataset"]), param_vals=param_vals, baseline=baseline)
        posts = [(c.args[0], c.kwargs.get("json")) for c in mp.call_args_list]
        setp = [j for u, j in posts if "/api/set_params" in u]
        assert setp == [{"nn_learning_rate": 0.5}]  # only the edited key, via the N5 core
        urls = [u for u, _ in posts]
        assert next(i for i, u in enumerate(urls) if "/api/set_params" in u) < next(i for i, u in enumerate(urls) if "/api/train/restart" in u)
        assert banner is False

    def test_both_edited_restages_and_applies(self, dm):
        baseline = _baseline()
        dataset_vals = dict(baseline["dataset"], dataset_type="circles")
        param_vals = dict(baseline["params"], nn_learning_rate=0.5)
        routes = {"/api/stage_dataset": _resp(200, {"status": "success"}), "/api/set_params": _resp(200, {"status": "success"}), "/api/train/restart": _resp(200, {"success": True, "was_active": False, "start_fresh": False, "steps": []})}
        with patch("frontend.dashboard_manager.requests.post", side_effect=_post_router(routes)) as mp, patch("frontend.dashboard_manager.requests.get", return_value=_resp(200, {})):
            _, _, outcome, banner = dm._execute_restart_handler(n_clicks=1, start_fresh=False, dataset_vals=dataset_vals, param_vals=param_vals, baseline=baseline)
        urls = [c.args[0] for c in mp.call_args_list]
        assert any("/api/stage_dataset" in u for u in urls)
        assert any("/api/set_params" in u for u in urls)
        text = _text(outcome)
        assert "Re-staged dataset to circles" in text
        assert "Parameters applied" in text
        assert banner is False

    def test_staging_failure_aborts_before_restart(self, dm):
        baseline = _baseline()
        dataset_vals = dict(baseline["dataset"], dataset_type="circles")
        routes = {"/api/stage_dataset": _resp(502, None, text="Backend rejected dataset: unknown"), "/api/train/restart": _resp(200, {"success": True})}
        with patch("frontend.dashboard_manager.requests.post", side_effect=_post_router(routes)) as mp, patch("frontend.dashboard_manager.requests.get", return_value=_resp(200, {})):
            _, _, outcome, banner = dm._execute_restart_handler(n_clicks=1, start_fresh=False, dataset_vals=dataset_vals, param_vals=dict(baseline["params"]), baseline=baseline)
        urls = [c.args[0] for c in mp.call_args_list]
        assert not any("/api/train/restart" in u for u in urls)  # aborted — never restart on a stale dataset
        assert banner is dash.no_update
        assert outcome.color == "danger"
        assert "re-stage" in _text(outcome).lower()

    def test_param_apply_failure_aborts_before_restart(self, dm):
        baseline = _baseline()
        param_vals = dict(baseline["params"], nn_learning_rate=0.5)
        routes = {"/api/set_params": _resp(502, {"error": "Backend rejected parameters: [bad]"}), "/api/train/restart": _resp(200, {"success": True})}
        with patch("frontend.dashboard_manager.requests.post", side_effect=_post_router(routes)) as mp, patch("frontend.dashboard_manager.requests.get", return_value=_resp(200, {})):
            _, _, outcome, banner = dm._execute_restart_handler(n_clicks=1, start_fresh=False, dataset_vals=dict(baseline["dataset"]), param_vals=param_vals, baseline=baseline)
        urls = [c.args[0] for c in mp.call_args_list]
        assert not any("/api/train/restart" in u for u in urls)  # aborted
        assert banner is dash.no_update
        assert outcome.color == "danger"
        assert "could not apply parameters" in _text(outcome).lower()

    def test_no_edits_skips_restage_and_apply(self, dm):
        baseline = _baseline()
        routes = {"/api/train/restart": _resp(200, {"success": True, "was_active": False, "start_fresh": False, "steps": []})}
        with patch("frontend.dashboard_manager.requests.post", side_effect=_post_router(routes)) as mp, patch("frontend.dashboard_manager.requests.get", return_value=_resp(200, {})):
            _, _, outcome, banner = dm._execute_restart_handler(n_clicks=1, start_fresh=False, dataset_vals=dict(baseline["dataset"]), param_vals=dict(baseline["params"]), baseline=baseline)
        urls = [c.args[0] for c in mp.call_args_list]
        assert not any("/api/stage_dataset" in u for u in urls)  # simple-confirm default
        assert not any("/api/set_params" in u for u in urls)
        assert banner is False
