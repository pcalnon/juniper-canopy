#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_recurrence_staging.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-09-08
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   X6 / design §4.9 -- the (recurrence, equities_seq) pair
#                can be STAGED: RecurrenceBackend stages in-process and
#                the next fit consumes it; staging toward a backend the
#                selection does not target is refused (N5), so cascor's
#                by-design refusal of a rank-3 artifact is never reached.
#####################################################################
"""Staging the pair (X6 / design §4.9), and why neither half of it is cross-repo.

Design of record: ``JUNIPER_2026-09-02_JUNIPER-CANOPY_SELECTION-REACHABILITY-DESIGN.md`` §4.9.
Handoff ``HANDOFF_2026-09-07_canopy-selection-deadlock-fixed-generator-gap-open.md`` item 2 filed
both branches as cross-repo work -- ``equities_seq`` into cascor's ``Literal``, and a staging
endpoint on juniper-recurrence. Both premises were wrong, and this module pins the corrections:

* cascor refuses 3-D artifacts **by design** at the tier boundary (``api/lifecycle/manager.py``,
  W-2). The only way canopy sent one there was the inactive-selection state N5 names, and
  ``/api/stage_dataset`` now refuses that state before anything leaves canopy.
* the recurrence service is one-shot -- the dataset reference travels in ``POST /v1/train`` -- so
  "staged for the next start" is a canopy-side fact, exactly as ``DemoMode`` already holds it.
  ``RecurrenceBackend`` stages in-process and ``start_training`` consumes it.
"""

import json
import logging
import time
from pathlib import Path
from unittest import mock

import httpx
import pytest
from fastapi.testclient import TestClient

import main
from backend.recurrence_backend import RecurrenceBackend, dataset_ref_from_staged
from backend.recurrence_service_adapter import RecurrenceServiceAdapter, RecurrenceTrainResult
from dataset_schema import DECLARED_PARAM_DEFAULTS
from frontend.dashboard_manager import DashboardManager
from model_registry import dataset_default_params


class _RecordingAdapter:
    """Stand-in for RecurrenceServiceAdapter that records ``train`` calls (no network)."""

    def __init__(self):
        self.service_url = "http://rec.test:8210"
        self.calls = []

    def train(self, **kwargs):
        self.calls.append(kwargs)
        return RecurrenceTrainResult(
            final_metrics={"r2": 0.5, "mse": 0.1, "loss": 0.1},
            n_epochs=1,
            stopped_reason="fit_complete",
            dataset={"name": "equities_seq", "n_windows": 3, "n_features": 2, "output_dim": 1},
        )


def _wait_until(predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.005)
    return predicate()


def _text_of(component):
    if component is None:
        return ""
    if isinstance(component, str):
        return component
    if isinstance(component, (list, tuple)):
        return "".join(_text_of(child) for child in component)
    return _text_of(getattr(component, "children", None))


# Recurrence recorded over the demo backend: the D-8 / X1 state, ``swapped`` False.
INACTIVE_STATE = {"nn_model": "recurrence", "backend": "demo", "execution": "continuous", "status": "live", "swapped": False}
LIVE_STATE = {"nn_model": "recurrence", "backend": "recurrence", "execution": "one_shot", "status": "live", "swapped": True}
# The operator's applied edit. It overrides the seed's ``symbols`` with a SHORTER list, which is
# what narrowing an equities universe actually looks like. It deliberately does not override
# ``max_symbols``: that key is a cap juniper-data refuses against, so pairing a cap of 2 with the
# seed's five names would make this fixture encode a config that 422s in production -- invisible
# here, because the adapter is a recorder, and wrong everywhere else.
STAGED = {"nn_dataset_type": "equities_seq", "nn_dataset_params": {"symbols": ["AAPL", "MSFT"]}}


@pytest.fixture
def backend():
    return RecurrenceBackend(_RecordingAdapter())


@pytest.fixture(scope="module")
def manager():
    return DashboardManager({})


@pytest.mark.regression
@pytest.mark.unit
class TestTheStagedConfigTranslation:
    """Canopy's staging dialect -> the recurrence service's ``DatasetRef``."""

    def test_registry_defaults_seed_the_params(self):
        ref = dataset_ref_from_staged({"nn_dataset_type": "equities_seq"})
        assert ref == {"generator": "equities_seq", "params": dataset_default_params("equities_seq"), "split": "train"}
        # The two keys without which this seed cannot train at all ride along. ``symbols`` pins the
        # universe (``max_symbols`` is a cap juniper-data REFUSES against, not a truncator, so the
        # former seed generated nothing); ``fundamentals_fill`` keeps X_train finite (at the "nan"
        # default the LMU rejects it outright). Both are measured in the registry's own comment and
        # pinned by TestEquitiesSeedIsGenerableAndFinite in test_dataset_generator_contract.py.
        assert ref["params"]["symbols"] == ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]
        assert ref["params"]["fundamentals_fill"] == "drop"
        assert "max_symbols" not in ref["params"]

    def test_the_alias_map_is_applied_here_and_only_here(self):
        # The staging PAYLOAD stays in canopy's dialect (``test_the_STAGING_payload_must_NOT_be_translated``);
        # the translation to juniper-data's vocabulary happens where the ref is built for the
        # recurrence service, exactly as the one-shot Start body does (X3 / §4.6).
        assert dataset_ref_from_staged({"nn_dataset_type": "spirals"})["generator"] == "spiral"

    def test_operator_edits_override_the_seed(self):
        ref = dataset_ref_from_staged({"nn_dataset_type": "equities_seq", "nn_dataset_elements": 40, "nn_dataset_params": {"symbols": ["AAPL"], "fundamentals_fill": "zero"}})
        # Registry defaults seeded and BOTH overridden keys replaced -- including ``fundamentals_fill``,
        # so an operator who wants the zero-filled variant gets it.
        #
        # W1.2 (plan finding F-C3) corrected the rest of this assertion. It used to expect
        # ``"n_samples": 40`` as well: the generic typed field, translated into a generator that
        # declares no ``n_samples``. juniper-data did not refuse it -- its params model drops unknown
        # keys -- so the operator's 40 vanished downstream while canopy reported it staged.
        assert ref["params"] == {"symbols": ["AAPL"], "regression_target": "return", "fundamentals_fill": "zero"}
        assert "n_samples" not in ref["params"]

    def test_spiral_only_typed_fields_never_reach_a_sequence_generator(self):
        ref = dataset_ref_from_staged({"nn_dataset_type": "equities_seq", "nn_spiral_rotations": 2.0, "nn_spiral_number": 3})
        assert "rotations" not in ref["params"]
        assert "n_spirals" not in ref["params"]


@pytest.mark.regression
@pytest.mark.unit
class TestRecurrenceBackendStagesInProcess:
    """The DemoMode contract, on the recurrence backend: stage / peek / status / cancel / consume."""

    def test_stage_then_status_then_cancel(self, backend):
        assert backend.get_pending_dataset() == {"ok": True, "pending": None}
        assert backend.get_status().get("pending_dataset") is None
        result = backend.stage_dataset(nn_dataset_type="equities_seq", nn_dataset_params={"symbols": ["AAPL", "MSFT"]}, nn_dataset_noise=None)
        assert result["ok"] is True
        assert result["data"]["status"] == "staged"
        assert result["data"]["config"] == STAGED
        assert result["data"]["dataset_ref"]["generator"] == "equities_seq"
        assert backend.get_pending_dataset()["pending"] == STAGED
        # The banner reconciles off status, as it does for cascor and demo.
        assert backend.get_status()["pending_dataset"] == STAGED
        cancelled = backend.cancel_pending_dataset()
        assert cancelled["ok"] is True
        assert cancelled["data"]["discarded"] == STAGED
        assert backend.get_pending_dataset()["pending"] is None
        assert backend.get_status()["pending_dataset"] is None

    def test_an_empty_body_clears_as_cascor_documents(self, backend):
        backend.stage_dataset(nn_dataset_type="equities_seq")
        assert backend.stage_dataset()["data"]["status"] == "cleared"
        assert backend.get_pending_dataset()["pending"] is None

    def test_a_config_without_a_type_is_refused_and_stages_nothing(self, backend):
        result = backend.stage_dataset(nn_dataset_params={"max_symbols": 2})
        assert result["ok"] is False
        assert "nn_dataset_type" in result["error"]
        assert backend.get_pending_dataset()["pending"] is None

    def test_the_next_fit_consumes_the_staged_dataset(self, backend):
        backend.stage_dataset(**STAGED)
        result = backend.start_training(reset=True)  # the restart route's bare call: no ref at all
        assert result["ok"] is True, result
        assert _wait_until(lambda: not backend.is_training_active())
        call = backend._adapter.calls[0]
        assert call["generator"] == "equities_seq"
        assert call["params"] == {"symbols": ["AAPL", "MSFT"], "regression_target": "return", "fundamentals_fill": "drop"}
        assert call["split"] == "train"
        # Consumed: the banner closes, as it does when cascor clears ``pending_dataset``.
        assert backend.get_pending_dataset()["pending"] is None
        assert backend.get_status().get("pending_dataset") is None

    def test_the_staged_dataset_wins_over_the_one_shot_body(self, backend):
        # The one-shot Start body carries only the registry's defaults for the dropdown value; it
        # knows nothing of what the operator edited and APPLIED. Preferring it would discard the
        # applied change while reporting success -- the class this arc exists to close.
        backend.stage_dataset(**STAGED)
        result = backend.start_training(reset=True, generator="equities_seq", params=dataset_default_params("equities_seq"))
        assert result["ok"] is True, result
        assert _wait_until(lambda: not backend.is_training_active())
        assert backend._adapter.calls[0]["params"]["symbols"] == ["AAPL", "MSFT"]

    def test_without_a_staged_dataset_the_body_is_used_unchanged(self, backend):
        result = backend.start_training(reset=True, generator="equities_seq", params={"max_symbols": 1}, d=4)
        assert result["ok"] is True, result
        assert _wait_until(lambda: not backend.is_training_active())
        call = backend._adapter.calls[0]
        assert call["generator"] == "equities_seq"
        assert call["params"] == {"max_symbols": 1}
        assert call["d"] == 4

    def test_a_bare_start_with_nothing_staged_still_fails_closed(self, backend):
        result = backend.start_training(reset=True)
        assert result["ok"] is False
        assert "no dataset reference" in result["error"]
        assert backend._adapter.calls == []

    def test_the_hyperparameters_still_ride_along(self, backend):
        backend.apply_params(d=6, theta=2.0)
        backend.stage_dataset(**STAGED)
        assert backend.start_training(reset=True)["ok"] is True
        assert _wait_until(lambda: not backend.is_training_active())
        call = backend._adapter.calls[0]
        assert call["d"] == 6
        assert call["theta"] == 2.0


@pytest.mark.regression
@pytest.mark.unit
class TestTheRoutesStageThePair:
    """End to end through the routes the dashboard actually calls."""

    @pytest.fixture
    def client(self):
        with TestClient(main.app) as client:
            yield client

    @pytest.fixture
    def recurrence(self, monkeypatch):
        rb = RecurrenceBackend(_RecordingAdapter())
        monkeypatch.setattr(main, "backend", rb, raising=False)
        monkeypatch.setattr(main, "current_nn_model", "recurrence", raising=False)
        return rb

    def test_stage_dataset_reaches_the_recurrence_backend(self, client, recurrence):
        # Before: 501 "does not support staging" (the #599 guard, which still covers a backend
        # without the capability -- see test_dataset_generator_contract.py).
        resp = client.post("/api/stage_dataset", json=STAGED)
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["status"] == "staged"
        assert recurrence.get_pending_dataset()["pending"] == STAGED

    def test_the_restart_route_fits_the_staged_dataset(self, client, recurrence):
        # The dataset modal's path: stage, then POST /api/train/restart -- a bare start.
        assert client.post("/api/stage_dataset", json=STAGED).status_code == 200
        resp = client.post("/api/train/restart", json={"start_fresh": False, "reset": True})
        assert resp.status_code == 200, resp.text
        assert resp.json()["success"] is True
        assert _wait_until(lambda: not recurrence.is_training_active())
        assert recurrence._adapter.calls[0]["generator"] == "equities_seq"
        assert recurrence._adapter.calls[0]["params"]["symbols"] == ["AAPL", "MSFT"]
        assert recurrence.get_pending_dataset()["pending"] is None

    def test_cancel_pending_reaches_the_recurrence_backend(self, client, recurrence):
        assert client.post("/api/stage_dataset", json=STAGED).status_code == 200
        resp = client.delete("/api/cancel_pending_dataset")
        assert resp.status_code == 200, resp.text
        assert recurrence.get_pending_dataset()["pending"] is None

    def test_train_status_carries_pending_dataset_for_the_banner(self, client, recurrence):
        assert client.post("/api/stage_dataset", json=STAGED).status_code == 200
        resp = client.get("/api/train/status")
        assert resp.status_code == 200, resp.text
        assert resp.json().get("pending_dataset") == STAGED

    def test_staging_is_refused_for_an_inactive_selection_before_anything_leaves_canopy(self, client, monkeypatch):
        # X6's cascor branch, at its cause: Recurrence recorded over the demo backend. Nothing
        # reaches the backend, so nothing reaches cascor -- whose refusal of a rank-3 artifact is
        # correct and stays exactly where it is.
        fake = mock.MagicMock()
        fake.backend_type = "demo"
        fake.stage_dataset.return_value = {"ok": True, "data": {}}
        monkeypatch.setattr(main, "backend", fake, raising=False)
        monkeypatch.setattr(main, "current_nn_model", "recurrence", raising=False)
        resp = client.post("/api/stage_dataset", json={"nn_dataset_type": "equities_seq"})
        assert resp.status_code == 409, resp.text
        error = resp.json()["error"]
        assert "Recurrence (LMU)" in error
        assert "demo" in error
        fake.stage_dataset.assert_not_called()

    def test_a_live_cascor_selection_still_stages_normally(self, client, monkeypatch):
        fake = mock.MagicMock()
        fake.backend_type = "demo"
        fake.stage_dataset.return_value = {"ok": True, "data": {"status": "staged"}}
        monkeypatch.setattr(main, "backend", fake, raising=False)
        monkeypatch.setattr(main, "current_nn_model", "cascor", raising=False)
        resp = client.post("/api/stage_dataset", json={"nn_dataset_type": "spirals", "nn_dataset_elements": 100})
        assert resp.status_code == 200, resp.text
        fake.stage_dataset.assert_called_once_with(nn_dataset_type="spirals", nn_dataset_elements=100)


@pytest.mark.regression
@pytest.mark.unit
class TestApplyDatasetIsGatedLikeStart:
    """The control-side half of the refusal, in the callback that owns both buttons."""

    @staticmethod
    def _appearance(manager, model_state):
        states = {"start": {"disabled": False, "loading": False, "timestamp": 0}}
        return manager._update_button_appearance_handler(button_states=states, model_key="recurrence", dataset_value="equities_seq", model_state=model_state)

    def test_apply_is_disabled_for_an_inactive_selection(self, manager):
        out = self._appearance(manager, INACTIVE_STATE)
        assert out[0] is True  # Start (N5)
        assert out[-1] is True  # Apply Dataset

    def test_apply_stays_enabled_when_the_selection_is_live(self, manager):
        out = self._appearance(manager, LIVE_STATE)
        assert out[0] is False
        assert out[-1] is False

    def test_apply_is_unknown_safe_at_first_paint(self, manager):
        assert self._appearance(manager, None)[-1] is False

    def test_the_notice_names_both_controls(self):
        text = _text_of(DashboardManager._train_gate_notice_handler("recurrence", model_state=INACTIVE_STATE))
        assert "Start and Apply Dataset are disabled" in text
        assert "demo" in text


# --------------------------------------------------------------------------------------------------
# W1.2 / ruling R7 -- juniper-ml plan
# notes/JUNIPER_2026-10-03_JUNIPER-RECURRENCE_EQUITIES-END-TO-END-AUDIT-AND-DEVELOPMENT-PLAN.md, W1.2
# (findings F-C2, F-C3). R7's recommended default, applied pending the owner's ruling: generic-form
# defaults never override the registry seed; an explicitly edited recurrence-aware field wins over
# it; the effective request is previewed before Start and logged at INFO.
#
# Every test below runs the whole path an operator runs. The form is RENDERED from juniper-data's own
# schema for the generator (the captured ``GET /v1/generators`` entries in
# ``tests/fixtures/juniper_data_sequence_generator_schemas.json``), Apply's real payload builder posts
# it to the real ``/api/stage_dataset`` route, Start goes through ``/api/train/start``, and the
# request is read off the wire: the backend runs the REAL ``RecurrenceServiceAdapter``, whose httpx
# transport records the JSON it POSTs to ``/v1/train``. "Body" below means that JSON.
# --------------------------------------------------------------------------------------------------

_SCHEMA_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "juniper_data_sequence_generator_schemas.json"
GENERATORS = json.loads(_SCHEMA_FIXTURE.read_text(encoding="utf-8"))["generators"]
EQUITIES_SEQ_SEED = dataset_default_params("equities_seq")
_TRAIN_OK = {"final_metrics": {"r2": 0.1, "mse": 1.0, "loss": 1.0}, "n_epochs": 1, "stopped_reason": "fit_complete", "dataset": {"name": "equities_seq", "n_windows": 3, "n_features": 15, "output_dim": 1}}


def _rendered_form(manager, dataset_value):
    """The schema-driven form for ``dataset_value`` as the browser would post it untouched: ``(values, ids)``."""
    _title, _style, children = manager._render_dataset_params_handler(dataset_value, generators=GENERATORS)
    controls = [child for child in children if isinstance(getattr(child, "id", None), dict) and child.id.get("type") == "nn-gen-param"]
    assert controls, f"the {dataset_value!r} form rendered no controls -- every check below would be vacuous"
    return [control.value for control in controls], [control.id for control in controls]


@pytest.fixture
def wire(monkeypatch):
    """A live recurrence selection over the REAL adapter; returns ``(backend, sent)``, ``sent`` = POSTed JSON bodies."""
    sent = []

    def handler(request):
        sent.append({"method": request.method, "path": request.url.path, "json": json.loads(request.content or b"null")})
        return httpx.Response(200, json=_TRAIN_OK)

    rb = RecurrenceBackend(RecurrenceServiceAdapter("http://rec.test:8210", transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(main, "backend", rb, raising=False)
    monkeypatch.setattr(main, "current_nn_model", "recurrence", raising=False)
    return rb, sent


@pytest.fixture
def client():
    with TestClient(main.app) as test_client:
        yield test_client


def _start_and_read_the_wire(client, rb, sent):
    """Click Start with the body the sidebar resolves for equities_seq; return the JSON POSTed to /v1/train."""
    start_body = DashboardManager._resolve_oneshot_start_body_handler("one_shot", "equities_seq")
    resp = client.post("/api/train/start", json=start_body)
    assert resp.status_code == 200, resp.text
    assert _wait_until(lambda: bool(sent) and not rb.is_training_active()), "the fit never reached the adapter"
    assert len(sent) == 1 and sent[0]["method"] == "POST" and sent[0]["path"] == "/v1/train", sent
    return sent[0]["json"]


@pytest.mark.regression
@pytest.mark.unit
class TestR7RequestPrecedence:
    """The plan's three acceptance tests for W1.2, kept separate as the plan asks."""

    def test_an_untouched_form_sends_exactly_the_seed(self, client, wire, manager):
        # (1) Untouched generic form -> the body equals the seed exactly.
        rb, sent = wire
        values, ids = _rendered_form(manager, "equities_seq")
        payload = DashboardManager._dataset_stage_payload("equities_seq", gen_values=values, gen_ids=ids, nn_model="recurrence")
        # Non-vacuity: Apply really does post more than the seed -- every rendered field's default.
        # That surplus is F-C2: before W1.2 all of it reached the service.
        assert set(payload["nn_dataset_params"]) > set(EQUITIES_SEQ_SEED), payload
        assert client.post("/api/stage_dataset", json=payload).status_code == 200
        body = _start_and_read_the_wire(client, rb, sent)
        assert body == {"dataset": {"split": "train", "generator": "equities_seq", "params": EQUITIES_SEQ_SEED}}

    def test_a_staged_n_samples_beside_untouched_equities_fields_sends_schema_keys_only(self, client, wire, manager):
        # (2) Staged ``n_samples`` (with ``noise``) + untouched equities fields -> schema keys only,
        # still the seed. The generic fields are the ones the restart modal re-stages for every type.
        rb, sent = wire
        values, ids = _rendered_form(manager, "equities_seq")
        payload = DashboardManager._dataset_stage_payload("equities_seq", gen_values=values, gen_ids=ids, nn_model="recurrence")
        payload.update(nn_dataset_elements=40, nn_dataset_noise=0.25)
        assert client.post("/api/stage_dataset", json=payload).status_code == 200
        preview = client.post("/api/recurrence/effective_request", json={}).json()
        assert {"nn_dataset_elements", "nn_dataset_noise"} <= set(preview["not_forwarded"]), preview
        body = _start_and_read_the_wire(client, rb, sent)
        params = body["dataset"]["params"]
        assert set(params) <= set(DECLARED_PARAM_DEFAULTS["equities_seq"]), f"keys equities_seq does not declare: {sorted(set(params) - set(DECLARED_PARAM_DEFAULTS['equities_seq']))}"
        assert "n_samples" not in params and "noise" not in params
        assert params == EQUITIES_SEQ_SEED

    def test_an_edited_regression_target_is_sent_and_the_preview_matches(self, client, wire, manager):
        # (3) Explicitly edited ``regression_target: next_close`` -> the body carries it and the preview matches.
        rb, sent = wire
        values, ids = _rendered_form(manager, "equities_seq")
        position = [control_id["name"] for control_id in ids].index("regression_target")
        # The form rendered the SEED's value (``apply_seeded_defaults``), not juniper-data's ``next_close``
        # default -- so choosing ``next_close`` is an edit the operator made, not a default they left.
        assert values[position] == EQUITIES_SEQ_SEED["regression_target"] == "return"
        values[position] = "next_close"
        payload = DashboardManager._dataset_stage_payload("equities_seq", gen_values=values, gen_ids=ids, nn_model="recurrence")
        assert client.post("/api/stage_dataset", json=payload).status_code == 200
        start_body = DashboardManager._resolve_oneshot_start_body_handler("one_shot", "equities_seq")
        preview = client.post("/api/recurrence/effective_request", json=start_body).json()
        assert preview["ok"] is True and preview["source"] == "staged" and preview["edited"] == ["regression_target"], preview
        body = _start_and_read_the_wire(client, rb, sent)
        assert body["dataset"]["params"] == {**EQUITIES_SEQ_SEED, "regression_target": "next_close"}
        assert preview["request"] == body, "the preview shown before Start is not the request Start sent"


@pytest.mark.regression
@pytest.mark.unit
class TestTheEffectiveRequestRoute:
    """``POST /api/recurrence/effective_request``: read-only, logged, and refused where Start would be."""

    def test_the_start_body_is_previewed_when_nothing_is_staged(self, client, wire):
        start_body = DashboardManager._resolve_oneshot_start_body_handler("one_shot", "equities_seq")
        preview = client.post("/api/recurrence/effective_request", json=start_body).json()
        assert preview["source"] == "start_body"
        assert preview["request"] == {"dataset": {"split": "train", "generator": "equities_seq", "params": EQUITIES_SEQ_SEED}}
        assert preview["not_forwarded"] == [] and preview["edited"] == [] and preview["fit_in_progress"] is False

    def test_a_preview_consumes_nothing(self, client, wire):
        rb, sent = wire
        assert client.post("/api/stage_dataset", json=STAGED).status_code == 200
        assert client.post("/api/recurrence/effective_request", json={}).status_code == 200
        assert rb.get_pending_dataset()["pending"] == STAGED
        assert sent == [] and rb.is_training_active() is False

    def test_no_reference_at_all_says_what_start_would_say(self, client, wire):
        preview = client.post("/api/recurrence/effective_request").json()
        assert preview["ok"] is False and preview["request"] is None
        assert "no dataset reference" in preview["error"]

    def test_the_preview_and_the_start_are_both_logged_at_info(self, client, wire, caplog):
        rb, sent = wire
        caplog.set_level(logging.INFO, logger="juniper_canopy.backend.recurrence_request")
        start_body = DashboardManager._resolve_oneshot_start_body_handler("one_shot", "equities_seq")
        client.post("/api/recurrence/effective_request", json=start_body)
        body = _start_and_read_the_wire(client, rb, sent)
        lines = [record.getMessage() for record in caplog.records if record.name == "juniper_canopy.backend.recurrence_request" and record.levelno == logging.INFO]
        expected = json.dumps(body, sort_keys=True)
        assert any("(preview, source=start_body)" in line and expected in line for line in lines), lines
        assert any("(start, source=start_body)" in line and expected in line for line in lines), lines

    def test_a_non_recurrence_backend_has_nothing_to_preview(self, client, monkeypatch):
        fake = mock.MagicMock()
        fake.backend_type = "demo"
        monkeypatch.setattr(main, "backend", fake, raising=False)
        monkeypatch.setattr(main, "current_nn_model", "cascor", raising=False)
        resp = client.post("/api/recurrence/effective_request", json={})
        assert resp.status_code == 409
        assert "not the recurrence backend" in resp.json()["error"]
        fake.preview_train_request.assert_not_called()

    def test_an_inactive_selection_is_refused_as_start_refuses_it(self, client, monkeypatch):
        # Recurrence recorded over the demo backend (N5): Start answers 409, so the preview does too.
        fake = mock.MagicMock()
        fake.backend_type = "demo"
        monkeypatch.setattr(main, "backend", fake, raising=False)
        monkeypatch.setattr(main, "current_nn_model", "recurrence", raising=False)
        resp = client.post("/api/recurrence/effective_request", json={})
        assert resp.status_code == 409
        assert resp.json()["error"].startswith("Training could not be started: ")
        fake.preview_train_request.assert_not_called()

    def test_the_restart_modal_restage_reaches_the_service_as_the_seed(self, client, wire, manager):
        # F-C3 on the path that actually carries the generic fields: the restart modal re-stages
        # ``n_samples`` / ``noise`` for every dataset type (``_restage_dataset``).
        rb, sent = wire
        with mock.patch("frontend.dashboard_manager.requests.post") as post:
            post.return_value = mock.MagicMock(status_code=200, text="{}")
            ok, _detail = manager._restage_dataset({"dataset_type": "equities_seq", "n_samples": 100, "noise": 0.1}, nn_model="recurrence")
        assert ok is True
        payload = post.call_args.kwargs["json"]
        assert payload["nn_dataset_elements"] == 100 and payload["nn_dataset_noise"] == 0.1, "the modal no longer sends the generic fields -- this test would be vacuous"
        assert client.post("/api/stage_dataset", json=payload).status_code == 200
        body = _start_and_read_the_wire(client, rb, sent)
        assert body["dataset"]["params"] == EQUITIES_SEQ_SEED
