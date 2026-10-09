#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_recurrence_request.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-10-08
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   W1.2 / ruling R7 -- the recurrence POST /v1/train
#                request shaping (backend/recurrence_request.py) and
#                the declaration it filters by
#                (dataset_schema.DECLARED_PARAM_DEFAULTS), pinned
#                against juniper-data's own parameter schemas.
#####################################################################
"""The recurrence request: what canopy forwards, and the declaration that decides it (W1.2 / R7).

juniper-ml plan ``notes/JUNIPER_2026-10-03_JUNIPER-RECURRENCE_EQUITIES-END-TO-END-AUDIT-AND-DEVELOPMENT-PLAN.md``,
W1.2 (findings F-C2, F-C3), and its risk row: "Canopy schema filtering drops a legitimately staged
param because ``dataset_schema.py`` is incomplete ... Test enumerates ``equities_seq/params.py``
fields against the schema." canopy does not depend on juniper-data (the copy in the test env is
0.6.0, which predates ``equities_seq``), so the enumeration runs against a capture of exactly what
juniper-data serves -- ``tests/fixtures/juniper_data_sequence_generator_schemas.json`` -- and, when a
juniper-data checkout is named by ``JUNIPER_DATA_SRC``, against its source as well (parsed, not imported).

The end-to-end acceptance tests (rendered form -> Apply -> Start -> the JSON on the wire) are in
``tests/regression/test_recurrence_staging.py``.
"""

import ast
import json
import logging
import os
import re
import threading
from pathlib import Path

import httpx
import pytest

import dataset_schema
from backend import recurrence_request
from backend.recurrence_backend import RecurrenceBackend
from backend.recurrence_request import (
    GENERIC_FIELD_PARAMS,
    NO_DATASET_REF_ERROR,
    SOURCE_STAGED,
    SOURCE_START_BODY,
    FitRequest,
    ShapedRef,
    resolve_fit_request,
    same_value,
    shape_staged_ref,
    shape_start_body_ref,
    train_request_body,
)
from backend.recurrence_service_adapter import RecurrenceServiceAdapter, RecurrenceTrainResult
from dataset_schema import DECLARED_PARAM_DEFAULTS, DECLARED_PARAMS_SOURCE, FORM_EXCLUDED_FIELDS, PARTIAL_DATA_POLICY_FIELDS, declared_param_defaults, generator_name_for_type
from frontend.dashboard_manager import DashboardManager
from model_registry import DATASET_TYPES, compatible, dataset_default_params, get_model_spec

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_PATH = REPO_ROOT / "src" / "tests" / "fixtures" / "juniper_data_sequence_generator_schemas.json"
FIXTURE = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
CAPTURED = {entry["name"]: entry for entry in FIXTURE["generators"]}
RECAPTURE = "re-capture with util/ad-hoc/2026-10-08_capture_sequence_generator_schemas.py and update dataset_schema.DECLARED_PARAM_DEFAULTS from its output"
LOGGER = "juniper_canopy.backend.recurrence_request"


def _recurrence_seeds():
    recurrence = get_model_spec("recurrence")
    seeds = [spec for spec in DATASET_TYPES if compatible(spec, recurrence)]
    assert seeds, "no dataset is compatible with the recurrence model -- every check over this list would be vacuous"
    return seeds


@pytest.fixture(scope="module")
def manager():
    return DashboardManager({})


def _untouched_form(manager, dataset_value):
    """The rendered schema-driven form as ``{name: value}``, as Apply's collector would post it."""
    _title, _style, children = manager._render_dataset_params_handler(dataset_value, generators=FIXTURE["generators"])
    controls = [child for child in children if isinstance(getattr(child, "id", None), dict) and child.id.get("type") == "nn-gen-param"]
    assert controls, f"the {dataset_value!r} form rendered no controls -- this check would be vacuous"
    return DashboardManager._collect_generator_params([c.value for c in controls], [c.id for c in controls], exclude=FORM_EXCLUDED_FIELDS)


# ------------------------------------------------------------------------------ the declaration


@pytest.mark.unit
class TestTheDeclarationMatchesJuniperData:
    """``DECLARED_PARAM_DEFAULTS`` against juniper-data's captured ``GET /v1/generators`` schemas."""

    def test_the_capture_and_the_declaration_name_the_same_generators(self):
        assert set(CAPTURED) == set(DECLARED_PARAM_DEFAULTS), RECAPTURE

    def test_equities_seq_declares_every_field_juniper_data_has(self):
        # THE risk row. A field juniper-data's EquitiesSeqParams has and canopy does not declare would
        # be dropped from every request that set it -- the filter would discard operator intent.
        upstream = list(CAPTURED["equities_seq"]["schema"]["properties"])
        assert len(upstream) == 18, f"the capture holds {len(upstream)} equities_seq fields; 18 at juniper-data 462da218 -- {RECAPTURE}"
        missing = [name for name in upstream if name not in DECLARED_PARAM_DEFAULTS["equities_seq"]]
        assert not missing, f"juniper-data's equities_seq declares {missing} and canopy does not; the filter would drop them -- {RECAPTURE}"

    @pytest.mark.parametrize("generator", sorted(DECLARED_PARAM_DEFAULTS))
    def test_names_match_in_both_directions(self, generator):
        upstream = set(CAPTURED[generator]["schema"]["properties"])
        declared = set(DECLARED_PARAM_DEFAULTS[generator])
        assert upstream == declared, f"{generator}: upstream-only {sorted(upstream - declared)}, canopy-only {sorted(declared - upstream)} -- {RECAPTURE}"

    @pytest.mark.parametrize("generator", sorted(DECLARED_PARAM_DEFAULTS))
    def test_every_default_matches(self, generator):
        # A wrong default makes an untouched field read as an edit, which puts it in the request.
        properties = CAPTURED[generator]["schema"]["properties"]
        wrong = {name: (DECLARED_PARAM_DEFAULTS[generator][name], prop.get("default")) for name, prop in properties.items() if not same_value(DECLARED_PARAM_DEFAULTS[generator][name], prop.get("default"))}
        assert not wrong, f"{generator}: (canopy, juniper-data) defaults differ for {wrong} -- {RECAPTURE}"

    def test_the_capture_says_where_it_came_from(self):
        provenance = FIXTURE["_provenance"]
        assert re.fullmatch(r"[0-9a-f]{40}", provenance["commit"]), provenance
        assert provenance["dirty"] is False
        assert (REPO_ROOT / provenance["tool"]).is_file(), f"{provenance['tool']} is not in the repository"
        assert provenance["commit"][:8] in DECLARED_PARAMS_SOURCE, "the declaration and the capture name different juniper-data commits"

    def test_the_live_source_still_matches_the_capture(self):
        """Opt-in drift check against a juniper-data checkout: ``JUNIPER_DATA_SRC=/path/to/juniper-data``.

        Parses ``EquitiesSeqParams`` and its base ``EquitiesParams`` (no import -- canopy does not
        depend on juniper-data) and compares their annotated fields with the capture. Skipped when
        the variable is unset, which is every CI run: there the capture above is the whole check.
        """
        root = os.environ.get("JUNIPER_DATA_SRC")
        if not root:
            pytest.skip("JUNIPER_DATA_SRC is not set: no juniper-data source to compare the capture against")
        generators = Path(root) / "juniper_data" / "generators"
        fields = _annotated_fields(generators / "equities" / "params.py", "EquitiesParams") + _annotated_fields(generators / "equities_seq" / "params.py", "EquitiesSeqParams")
        assert set(fields) == set(CAPTURED["equities_seq"]["schema"]["properties"]), f"juniper-data at {root} has moved: {RECAPTURE}"


def _annotated_fields(path: Path, class_name: str) -> list:
    """Names of the annotated class-body fields of ``class_name`` in ``path`` (pydantic model fields)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return [item.target.id for item in node.body if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name)]
    raise AssertionError(f"{class_name} not found in {path}")


@pytest.mark.unit
class TestEveryRecurrenceSeedIsDeclared:
    """A rank-3 seed with no declaration would be forwarded unfiltered -- the pre-W1.2 behaviour."""

    @pytest.mark.parametrize("spec", _recurrence_seeds(), ids=lambda spec: spec.value)
    def test_the_seed_s_generator_is_declared(self, spec):
        assert generator_name_for_type(spec.value) in DECLARED_PARAM_DEFAULTS, f"{spec.value!r} can be staged for the recurrence model but declares no params -- {RECAPTURE}"

    @pytest.mark.parametrize("spec", _recurrence_seeds(), ids=lambda spec: spec.value)
    def test_every_seed_key_is_a_declared_parameter(self, spec):
        # The Start-body path filters by the declaration, so an undeclared seed key would reach the
        # service when staged and vanish when not -- the two paths would send different requests.
        undeclared = set(spec.default_params) - set(DECLARED_PARAM_DEFAULTS[generator_name_for_type(spec.value)])
        assert not undeclared, f"{spec.value!r} seeds {sorted(undeclared)}, which its generator does not declare"

    @pytest.mark.parametrize("spec", _recurrence_seeds(), ids=lambda spec: spec.value)
    def test_an_untouched_form_stages_nothing_but_the_seed(self, spec, manager):
        cfg = {"nn_dataset_type": spec.value, "nn_dataset_params": {**dataset_default_params(spec.value), **_untouched_form(manager, spec.value)}}
        shaped = shape_staged_ref(cfg)
        assert shaped.dataset_ref["params"] == dataset_default_params(spec.value)
        assert shaped.edited == () and shaped.not_forwarded == ()

    def test_declared_param_defaults_hands_out_copies(self):
        first = declared_param_defaults("ar_p")
        first["coefficients"].append(9.9)
        assert declared_param_defaults("ar_p")["coefficients"] == [0.5, -0.3]
        assert declared_param_defaults("no_such_generator") is None
        assert declared_param_defaults(None) is None


# ------------------------------------------------------------------------------ the shaping rules


@pytest.mark.unit
class TestSameValue:
    def test_numbers_compare_by_value_across_int_and_float(self):
        # The browser returns a rendered 1.0 as 1: JSON has one number type.
        assert same_value(1, 1.0) and same_value(0.0, 0)
        assert not same_value(1, 1.5)

    def test_a_checkbox_is_not_a_count(self):
        assert not same_value(True, 1) and not same_value(0, False)
        assert same_value(False, False) and not same_value(True, False)

    def test_sequences_and_mappings_compare_by_content(self):
        assert same_value([0.5, -0.3], (0.5, -0.3))
        assert not same_value([1, 2], [1, 2, 3])
        assert same_value({"a": [1, 2]}, {"a": (1.0, 2)})
        assert not same_value({"a": 1}, {"b": 1})
        assert not same_value([1], {"a": 1})

    def test_strings_and_none(self):
        assert same_value("drop", "drop") and not same_value("drop", "nan")
        assert same_value(None, None) and not same_value(None, 0) and not same_value("", None)


@pytest.mark.unit
class TestShapeStagedRef:
    """R7 over the staged config, one rule per test."""

    def test_an_edit_to_a_seeded_key_wins_over_the_seed(self):
        shaped = shape_staged_ref({"nn_dataset_type": "equities_seq", "nn_dataset_params": {**dataset_default_params("equities_seq"), "regression_target": "next_close"}})
        assert shaped.dataset_ref["params"]["regression_target"] == "next_close"
        assert shaped.edited == ("regression_target",)

    def test_an_edit_to_an_unseeded_key_is_forwarded(self):
        shaped = shape_staged_ref({"nn_dataset_type": "equities_seq", "nn_dataset_params": {"lookback": 32, "start_date": "2000-01-01"}})
        assert shaped.dataset_ref["params"] == {**dataset_default_params("equities_seq"), "lookback": 32}
        assert shaped.edited == ("lookback",)

    def test_a_parameter_the_generator_does_not_declare_is_withheld_and_named(self):
        shaped = shape_staged_ref({"nn_dataset_type": "equities_seq", "nn_dataset_params": {"interval": "1h"}})
        assert "interval" not in shaped.dataset_ref["params"]
        assert shaped.not_forwarded == ("interval",) and shaped.undeclared == ("interval",)

    def test_generic_fields_are_withheld_from_every_recurrence_generator(self):
        for spec in _recurrence_seeds():
            shaped = shape_staged_ref({"nn_dataset_type": spec.value, "nn_dataset_elements": 40, "nn_dataset_noise": 0.25})
            assert shaped.dataset_ref["params"] == dataset_default_params(spec.value), spec.value
            assert shaped.not_forwarded == ("nn_dataset_elements", "nn_dataset_noise"), spec.value
            assert shaped.undeclared == (), "a generic field is not snapshot drift"

    def test_spiral_only_fields_are_named_not_silently_dropped(self):
        shaped = shape_staged_ref({"nn_dataset_type": "equities_seq", "nn_spiral_rotations": 2.0, "nn_spiral_number": 3})
        assert shaped.not_forwarded == ("nn_spiral_rotations", "nn_spiral_number")
        assert shaped.dataset_ref["params"] == dataset_default_params("equities_seq")

    def test_a_generic_field_is_forwarded_where_declared_and_edited(self, monkeypatch):
        # No shipped rank-3 generator declares n_samples or noise; a fake one exercises the rule.
        monkeypatch.setitem(dataset_schema.DECLARED_PARAM_DEFAULTS, "fake_gen", {"n_samples": 100, "noise": 0.0})
        at_default = shape_staged_ref({"nn_dataset_type": "fake_gen", "nn_dataset_elements": 100, "nn_dataset_noise": 0})
        assert at_default.dataset_ref["params"] == {} and at_default.edited == ()
        edited = shape_staged_ref({"nn_dataset_type": "fake_gen", "nn_dataset_elements": 40, "nn_dataset_noise": 0.3})
        assert edited.dataset_ref["params"] == {"n_samples": 40, "noise": 0.3}
        assert edited.edited == ("n_samples", "noise")

    def test_a_generic_field_never_overrides_the_seed(self, monkeypatch):
        monkeypatch.setitem(dataset_schema.DECLARED_PARAM_DEFAULTS, "fake_gen", {"noise": 0.0})
        monkeypatch.setattr(recurrence_request, "dataset_default_params", lambda value: {"noise": 0.05})
        shaped = shape_staged_ref({"nn_dataset_type": "fake_gen", "nn_dataset_noise": 0.3})
        assert shaped.dataset_ref["params"] == {"noise": 0.05}
        assert shaped.not_forwarded == ("nn_dataset_noise",)

    def test_an_undeclared_generator_is_forwarded_as_staged_except_against_the_seed(self, monkeypatch):
        # The pre-W1.2 behaviour, minus what R7 forbids without needing a declaration: a generic
        # field over a seeded key, and an untouched seeded key read as an edit.
        monkeypatch.setattr(recurrence_request, "dataset_default_params", lambda value: {"a": 1, "noise": 0.05})
        shaped = shape_staged_ref({"nn_dataset_type": "brand_new", "nn_dataset_elements": 40, "nn_dataset_noise": 0.3, "nn_dataset_params": {"a": 1, "b": 2}})
        assert shaped.declared is False
        assert shaped.dataset_ref == {"generator": "brand_new", "params": {"a": 1, "noise": 0.05, "n_samples": 40, "b": 2}, "split": "train"}
        assert shaped.not_forwarded == ("nn_dataset_noise",)
        assert shaped.edited == ("n_samples",)
        assert shape_staged_ref({"nn_dataset_type": "brand_new", "nn_dataset_params": {"a": 2}}).edited == ("a",)

    def test_the_alias_is_applied_to_the_generator_name(self):
        assert shape_staged_ref({"nn_dataset_type": "spirals"}).dataset_ref["generator"] == "spiral"

    def test_the_browser_number_round_trip_is_not_an_edit(self, manager):
        # A rendered float with an integral value (sample_dt=1.0, noise_std=0.0) comes back from the
        # browser as an int. That must not read as an operator edit.
        form = {name: (int(value) if isinstance(value, float) and value.is_integer() else value) for name, value in _untouched_form(manager, "multi_sine").items()}
        assert any(isinstance(DECLARED_PARAM_DEFAULTS["multi_sine"][name], float) and isinstance(value, int) for name, value in form.items()), "no float was rounded -- this test would be vacuous"
        shaped = shape_staged_ref({"nn_dataset_type": "multi_sine", "nn_dataset_params": form})
        assert shaped.dataset_ref["params"] == {} and shaped.edited == ()

    def test_shaping_never_adds_a_partial_data_stance(self):
        # TestNoPathSendsAPartialDataStance (test_dataset_generator_contract.py) pins canopy's senders;
        # the shaping must not become one.
        shaped = shape_staged_ref({"nn_dataset_type": "equities_seq", "nn_dataset_elements": 1, "nn_dataset_params": dataset_default_params("equities_seq")})
        assert not PARTIAL_DATA_POLICY_FIELDS & set(shaped.dataset_ref["params"])


@pytest.mark.unit
class TestShapeStartBodyRef:
    def test_the_seed_passes_unchanged(self):
        ref = {"generator": "equities_seq", "params": dataset_default_params("equities_seq")}
        shaped = shape_start_body_ref(ref)
        assert shaped.dataset_ref == ref and shaped.not_forwarded == ()

    def test_an_undeclared_parameter_is_withheld(self):
        shaped = shape_start_body_ref({"generator": "equities_seq", "params": {"max_symbols": 1, "n_samples": 5}, "split": "val"})
        assert shaped.dataset_ref == {"generator": "equities_seq", "params": {"max_symbols": 1}, "split": "val"}
        assert shaped.not_forwarded == ("n_samples",) == shaped.undeclared

    def test_a_reference_by_name_or_an_undeclared_generator_passes_through(self):
        assert shape_start_body_ref({"name": "equities_seq", "params": {"n": 128}}).dataset_ref == {"name": "equities_seq", "params": {"n": 128}}
        undeclared = shape_start_body_ref({"generator": "brand_new", "params": {"n": 1}})
        assert undeclared.dataset_ref == {"generator": "brand_new", "params": {"n": 1}} and undeclared.declared is False
        assert shape_start_body_ref({"generator": "equities_seq"}).dataset_ref == {"generator": "equities_seq"}


# ------------------------------------------------------------------------------ the body on the wire


def _wire_body(dataset_ref, hyperparams):
    """The JSON the REAL adapter POSTs for ``train(**dataset_ref, **hyperparams)``."""
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"final_metrics": {}, "n_epochs": 1})

    RecurrenceServiceAdapter("http://rec.test:8210", transport=httpx.MockTransport(handler)).train(**dataset_ref, **hyperparams)
    return seen[0]


@pytest.mark.unit
class TestTrainRequestBodyMatchesTheAdapter:
    """``train_request_body`` mirrors ``RecurrenceServiceAdapter.train``; this fails the day they part."""

    @pytest.mark.parametrize(
        "dataset_ref,hyperparams",
        [
            ({"generator": "equities_seq", "params": {"symbols": ["AAPL"]}, "split": "train"}, {}),
            ({"generator": "multi_sine"}, {"d": 8, "theta": 1.5, "ridge": 0.1}),
            ({"name": "equities_seq", "params": {"n": 128}, "split": "full"}, {"d": 4}),
            ({"dataset_id": "equities_seq-6.0.0-abc", "split": "val"}, {"theta": None, "ridge": 0.0}),
            ({"generator": "ar_p", "params": {}}, {}),
        ],
    )
    def test_the_same_json_as_the_adapter(self, dataset_ref, hyperparams):
        assert train_request_body(dataset_ref, hyperparams) == _wire_body(dataset_ref, {k: v for k, v in hyperparams.items() if v is not None})


@pytest.mark.unit
class TestFitRequest:
    def _request(self, **shaped):
        return FitRequest(source=SOURCE_STAGED, shaped=ShapedRef(**shaped), hyperparams={"d": 8})

    def test_describe_carries_the_body_and_the_account(self):
        request = self._request(dataset_ref={"generator": "equities_seq", "params": {"a": 1}, "split": "train"}, not_forwarded=("nn_dataset_elements",), edited=("a",))
        assert request.describe() == {
            "ok": True,
            "source": SOURCE_STAGED,
            "request": {"dataset": {"split": "train", "generator": "equities_seq", "params": {"a": 1}}, "d": 8},
            "not_forwarded": ["nn_dataset_elements"],
            "edited": ["a"],
            "declared_params_source": DECLARED_PARAMS_SOURCE,
        }

    def test_without_a_reference_there_is_no_body_and_start_s_own_error(self):
        request = self._request(dataset_ref={})
        assert request.body is None
        assert request.describe()["ok"] is False and request.describe()["error"] == NO_DATASET_REF_ERROR

    def test_the_preview_logs_info_only(self, caplog):
        caplog.set_level(logging.INFO, logger=LOGGER)
        self._request(dataset_ref={"generator": "equities_seq", "params": {}}, not_forwarded=("x",), undeclared=("x",), declared=False).log("preview")
        records = [record for record in caplog.records if record.name == LOGGER]
        assert [record.levelno for record in records] == [logging.INFO]
        assert "(preview, source=staged)" in records[0].getMessage() and "not forwarded: x" in records[0].getMessage()

    def test_the_start_warns_about_drift_and_about_an_undeclared_generator(self, caplog):
        caplog.set_level(logging.INFO, logger=LOGGER)
        self._request(dataset_ref={"generator": "equities_seq", "params": {}}, not_forwarded=("interval",), undeclared=("interval",)).log("start")
        self._request(dataset_ref={"generator": "brand_new", "params": {}}, declared=False).log("start")
        warnings = [record.getMessage() for record in caplog.records if record.name == LOGGER and record.levelno == logging.WARNING]
        assert len(warnings) == 2
        assert "withheld interval" in warnings[0] and "re-capture" in warnings[0]
        assert "'brand_new' is forwarded unfiltered" in warnings[1]

    def test_no_reference_is_logged_as_such(self, caplog):
        caplog.set_level(logging.INFO, logger=LOGGER)
        self._request(dataset_ref={}).log("start")
        assert any("none -- no dataset reference" in record.getMessage() for record in caplog.records if record.name == LOGGER)

    def test_resolve_prefers_the_staged_dataset(self):
        staged = resolve_fit_request(explicit_ref={"generator": "multi_sine"}, staged_cfg={"nn_dataset_type": "equities_seq"}, hyperparams={})
        assert staged.source == SOURCE_STAGED and staged.dataset_ref["generator"] == "equities_seq" and staged.start_body_generator == "multi_sine"
        body = resolve_fit_request(explicit_ref={"generator": "multi_sine"}, staged_cfg=None, hyperparams={"d": 2})
        assert body.source == SOURCE_START_BODY and body.dataset_ref == {"generator": "multi_sine"} and body.hyperparams == {"d": 2}


# ------------------------------------------------------------------------------ the backend's preview


class _GatedAdapter:
    """Records ``train`` calls; blocks in ``train`` until released, so a fit can be held in flight."""

    def __init__(self):
        self.service_url = "http://rec.test:8210"
        self.calls = []
        self.release = threading.Event()

    def train(self, **kwargs):
        self.calls.append(kwargs)
        self.release.wait(5.0)
        return RecurrenceTrainResult(final_metrics={"r2": 0.0}, n_epochs=1, stopped_reason="fit_complete", dataset={})


@pytest.mark.unit
class TestBackendPreview:
    def test_the_preview_is_the_request_start_sends(self):
        adapter = _GatedAdapter()
        adapter.release.set()
        backend = RecurrenceBackend(adapter)
        backend.apply_params(d=6)
        backend.stage_dataset(nn_dataset_type="equities_seq", nn_dataset_elements=40, nn_dataset_params={"regression_target": "log_return"})
        preview = backend.preview_train_request(generator="multi_sine", theta=2.0)
        assert backend.get_pending_dataset()["pending"] is not None, "the preview consumed the staged dataset"
        assert backend.start_training(generator="multi_sine", theta=2.0)["ok"] is True
        for thread in threading.enumerate():
            if thread.name == "recurrence-fit":
                thread.join(5.0)
        call = adapter.calls[0]
        assert preview["request"] == train_request_body({k: call[k] for k in ("generator", "params", "split")}, {k: call[k] for k in ("d", "theta")})
        assert preview["request"]["dataset"]["params"] == {**dataset_default_params("equities_seq"), "regression_target": "log_return"}
        assert preview["request"]["d"] == 6 and preview["request"]["theta"] == 2.0
        assert preview["not_forwarded"] == ["nn_dataset_elements"] and preview["edited"] == ["regression_target"]

    def test_the_preview_says_when_a_start_would_be_refused_for_a_running_fit(self):
        adapter = _GatedAdapter()
        backend = RecurrenceBackend(adapter)
        try:
            assert backend.start_training(generator="multi_sine")["ok"] is True
            assert backend.preview_train_request(generator="multi_sine")["fit_in_progress"] is True
        finally:
            adapter.release.set()
            for thread in threading.enumerate():
                if thread.name == "recurrence-fit":
                    thread.join(5.0)
        assert backend.preview_train_request(generator="multi_sine")["fit_in_progress"] is False

    def test_a_bare_start_refuses_with_the_shared_text(self):
        result = RecurrenceBackend(_GatedAdapter()).start_training()
        assert result["ok"] is False and result["error"] == NO_DATASET_REF_ERROR

    def test_the_generic_field_map_is_the_one_documented(self):
        assert GENERIC_FIELD_PARAMS == {"nn_dataset_elements": "n_samples", "nn_dataset_noise": "noise"}
