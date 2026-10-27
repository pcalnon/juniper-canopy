#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_cascor_staging_declared_params.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-10-26
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   juniper-canopy#736 -- the cascor staging body for flat
#                ``equities`` carries the registry seed plus what the
#                operator edited, and nothing the generator does not
#                declare, on all three paths that stage it.
#####################################################################
"""The cascor tier gets W1.2's declared-param filter and R7 rule (juniper-canopy#736).

W1.2 (juniper-canopy#733) gave the recurrence request a declared-param filter and R7's "send only what
the operator edited". The cascor path for flat ``equities`` had neither. Sidebar Apply and the live swap
posted every rendered form value, the restart modal added ``n_samples`` / ``noise``, and the route
forwarded all of it to cascor. juniper-data 0.17.x's flat ``EquitiesParams`` declares neither of those
two, and it ignores unknown keys, so they were dropped without a word (F-C3). The untouched fields went
out at canopy's displayed defaults, as overrides nobody chose (F-C2).

Every test runs the path an operator runs. The form is RENDERED from the published juniper-data 0.17.1
wheel's own schema (``tests/fixtures/juniper_data_tabular_generator_schemas.json``), the dashboard builds
the body it really posts, the real canopy route receives it, and the real ``ServiceBackend`` and
``CascorServiceAdapter`` turn it into the JSON cascor would receive, which is read off a stub client.
The route coroutines are awaited directly: a ``TestClient`` lifespan would shut the stub backend down.
"""

import asyncio
import json
import logging
from pathlib import Path
from unittest import mock

import pytest

import main
from backend.cascor_service_adapter import CascorServiceAdapter
from backend.service_backend import ServiceBackend
from frontend.dashboard_manager import DashboardManager
from model_registry import dataset_default_params

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "juniper_data_tabular_generator_schemas.json"
GENERATORS = json.loads(_FIXTURE.read_text(encoding="utf-8"))["generators"]
EQUITIES_SEED = dataset_default_params("equities")
LOGGER = "juniper_canopy.backend.recurrence_request"


class _RecordingClient:
    """Stands in for juniper-cascor-client: records what the adapter would send to cascor."""

    def __init__(self):
        self.calls = []

    def _request(self, method, path, json=None):
        self.calls.append({"method": method, "path": path, "json": json})
        return {"data": {"status": "staged"}}


@pytest.fixture(scope="module")
def manager():
    return DashboardManager({})


@pytest.fixture
def cascor(monkeypatch):
    """A live cascor selection over the real ServiceBackend + adapter; returns the recording client."""
    adapter = CascorServiceAdapter.__new__(CascorServiceAdapter)
    adapter._client = _RecordingClient()
    monkeypatch.setattr(main, "backend", ServiceBackend(adapter), raising=False)
    monkeypatch.setattr(main, "current_nn_model", "cascor", raising=False)
    return adapter._client


def _stage(payload):
    """POST ``payload`` to canopy's ``/api/stage_dataset`` route; return the route's answer."""
    return asyncio.run(main.api_stage_dataset(main.StageDatasetRequest(**payload)))


def _swap(payload):
    return asyncio.run(main.api_live_dataset_swap(main.StageDatasetRequest(**payload)))


def _wire(client, path="/training/dataset"):
    """The single JSON body the adapter sent cascor on ``path``."""
    bodies = [call["json"] for call in client.calls if call["path"] == path]
    assert len(bodies) == 1, client.calls
    return bodies[0]


def _rendered_form(manager, dataset_value="equities"):
    """The schema-driven form as the browser posts it untouched: ``(values, ids)``."""
    _title, _style, children = manager._render_dataset_params_handler(dataset_value, generators=GENERATORS)
    controls = [child for child in children if isinstance(getattr(child, "id", None), dict) and child.id.get("type") == "nn-gen-param"]
    assert controls, f"the {dataset_value!r} form rendered no controls -- every check below would be vacuous"
    return [control.value for control in controls], [control.id for control in controls]


def _apply_payload(manager, edits=None):
    """What Apply Dataset posts for equities: the rendered form, with ``edits`` made in it."""
    values, ids = _rendered_form(manager)
    names = [control_id["name"] for control_id in ids]
    for name, value in (edits or {}).items():
        values[names.index(name)] = value
    return DashboardManager._dataset_stage_payload("equities", n_samples=200, noise=0.1, rotations=1.5, n_spirals=2, gen_values=values, gen_ids=ids, nn_model="cascor")


@pytest.mark.regression
@pytest.mark.unit
class TestTheCascorTierSendsTheSeedPlusWhatWasEdited:
    def test_an_untouched_apply_sends_exactly_the_seed(self, cascor, manager):
        payload = _apply_payload(manager)
        # Non-vacuity: Apply really does post every rendered field's default beside the seed. Before
        # juniper-canopy#736 all of it reached cascor.
        assert set(payload["nn_dataset_params"]) > set(EQUITIES_SEED), payload
        assert _stage(payload)["status"] == "success"
        assert _wire(cascor) == {"dataset_type": "equities", "params": EQUITIES_SEED}

    def test_an_edit_wins_over_the_seed(self, cascor, manager):
        # "Form overrides seed" survives the filter (TestTheCascorPathCarriesRegistryDefaults pins the body).
        _stage(_apply_payload(manager, {"fundamentals_fill": "zero"}))
        assert _wire(cascor)["params"] == {**EQUITIES_SEED, "fundamentals_fill": "zero"}

    def test_an_edited_unseeded_field_reaches_cascor_and_its_untouched_neighbours_do_not(self, cascor, manager):
        _stage(_apply_payload(manager, {"start_date": "2010-01-04"}))
        params = _wire(cascor)["params"]
        assert params == {**EQUITIES_SEED, "start_date": "2010-01-04"}
        assert "purchase_date" not in params and "max_symbols" not in params

    def test_the_live_swap_sends_what_apply_sends(self, monkeypatch, manager):
        bodies = {}
        for route, path in ((_stage, "/training/dataset"), (_swap, "/training/dataset/live")):
            adapter = CascorServiceAdapter.__new__(CascorServiceAdapter)
            adapter._client = _RecordingClient()
            monkeypatch.setattr(main, "backend", ServiceBackend(adapter), raising=False)
            monkeypatch.setattr(main, "current_nn_model", "cascor", raising=False)
            route(_apply_payload(manager, {"fundamentals_fill": "zero"}))
            bodies[path] = _wire(adapter._client, path)
        assert bodies["/training/dataset/live"] == bodies["/training/dataset"] == {"dataset_type": "equities", "params": {**EQUITIES_SEED, "fundamentals_fill": "zero"}}

    def test_the_restart_modal_restage_sends_the_seed_and_no_generic_fields(self, cascor, manager):
        with mock.patch("frontend.dashboard_manager.requests.post") as post:
            post.return_value = mock.MagicMock(status_code=200, text="{}")
            ok, _detail = manager._restage_dataset({"dataset_type": "equities", "n_samples": 500, "noise": 0.1, "rotations": 1.5, "n_spirals": 2}, nn_model="cascor")
        assert ok is True
        payload = post.call_args.kwargs["json"]
        assert payload == {"nn_dataset_type": "equities", "nn_dataset_params": EQUITIES_SEED, "nn_model": "cascor"}
        _stage(payload)
        assert _wire(cascor) == {"dataset_type": "equities", "params": EQUITIES_SEED}

    def test_a_stale_tab_s_generic_fields_are_withheld_by_the_backend_and_named(self, cascor, caplog):
        # A tab rendered before juniper-canopy#735 still re-stages n_samples / noise for every type. The
        # backend is the line that holds whatever the client sends.
        caplog.set_level(logging.INFO, logger=LOGGER)
        _stage({"nn_dataset_type": "equities", "nn_dataset_elements": 500, "nn_dataset_noise": 0.1, "nn_dataset_params": EQUITIES_SEED, "nn_model": "cascor"})
        assert _wire(cascor) == {"dataset_type": "equities", "params": EQUITIES_SEED}
        lines = [record.getMessage() for record in caplog.records if record.name == LOGGER and record.levelno == logging.INFO]
        assert any("(stage) for 'equities'" in line and "not forwarded: nn_dataset_elements, nn_dataset_noise" in line for line in lines), lines

    def test_an_untouched_apply_is_logged_with_what_was_held_back(self, cascor, manager, caplog):
        caplog.set_level(logging.INFO, logger=LOGGER)
        _stage(_apply_payload(manager))
        lines = [record.getMessage() for record in caplog.records if record.name == LOGGER and record.levelno == logging.INFO]
        assert len(lines) == 1, lines
        assert json.dumps(EQUITIES_SEED, sort_keys=True) in lines[0] and "untouched (juniper-data's default): " in lines[0] and "start_date" in lines[0]


@pytest.mark.regression
@pytest.mark.unit
class TestEveryOtherGeneratorIsForwardedAsStaged:
    """Only a generator ``DECLARED_PARAM_DEFAULTS`` covers is shaped; the spiral-era bodies are byte-for-byte unchanged."""

    def test_spiral_keeps_its_typed_fields(self, cascor):
        _stage({"nn_dataset_type": "spirals", "nn_dataset_elements": 200, "nn_dataset_noise": 0.1, "nn_spiral_rotations": 1.5, "nn_spiral_number": 2, "nn_model": "cascor"})
        assert _wire(cascor) == {"dataset_type": "spirals", "n_samples": 200, "noise": 0.1, "rotations": 1.5, "n_spirals": 2}

    def test_circles_keeps_its_schema_params_and_its_typed_fields(self, cascor):
        _stage({"nn_dataset_type": "circles", "nn_dataset_elements": 500, "nn_dataset_params": {"n_samples": 100, "noise": 0.05, "factor": 0.5}})
        assert _wire(cascor) == {"dataset_type": "circles", "n_samples": 500, "params": {"n_samples": 100, "noise": 0.05, "factor": 0.5}}

    def test_mnist_keeps_its_seed(self, cascor):
        _stage({"nn_dataset_type": "mnist", "nn_dataset_params": {"flatten": True, "n_samples": 5000}})
        assert _wire(cascor) == {"dataset_type": "mnist", "params": {"flatten": True, "n_samples": 5000}}
