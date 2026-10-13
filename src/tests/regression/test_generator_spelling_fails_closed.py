#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_generator_spelling_fails_closed.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-10-05
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   The juniper-data spelling of a rank-2 dataset is
#                refused for the LMU, and the selection read keeps
#                pending and loaded from collapsing into each other.
#####################################################################
"""Edges the mirror suite and the G7 seam tests do not reach.

``test_request_nn_model_mirror.py`` proves two halves of the alias and neither of the
pair that matters together: ``spiral`` is *allowed* on CasCor, and ``spirals`` (canopy's
own spelling) is *refused* for the LMU. A resolver that special-cases the string
``spirals`` and never calls ``dataset_type_for_generator_name`` still passes that file,
and ``POST /api/stage_dataset`` with ``nn_dataset_type: "spiral"`` while Recurrence is
live stages a rank-2 dataset into the LMU. The same hole is on ``/api/live_dataset_swap``.
``moon`` / ``moons`` is the other alias and is not in that file at all.

``_backend_dataset_selection`` is pinned for the shapes cascor and the demo simulator
actually emit. It is not pinned for an empty pending type (which must not hide the
loaded dataset), for the two dialects disagreeing, or for an unnameable pending sitting
on top of a loaded dataset the dropdown *can* show.
"""

from __future__ import annotations

from unittest import mock

import pytest
from fastapi.testclient import TestClient

import main
from backend.recurrence_backend import RecurrenceBackend

_LOADED_XOR = {"value": "xor", "source": "loaded", "generator": "xor"}


class _NoFitAdapter:
    """Stand-in for ``RecurrenceServiceAdapter``. These tests must not start a fit."""

    service_url = "http://rec.test:8210"

    def train(self, **_kwargs):  # pragma: no cover - a refusal returns before any fit
        raise AssertionError("no fit expected")


def _fake_backend(backend_type="demo"):
    fake = mock.MagicMock()
    fake.backend_type = backend_type
    fake.execution = "continuous"
    fake.is_training_active.return_value = False
    fake.stage_dataset.return_value = {"ok": True, "data": {"status": "staged"}}
    return fake


@pytest.fixture
def client():
    with TestClient(main.app) as test_client:
        yield test_client


@pytest.fixture
def recurrence_live(client, monkeypatch):
    backend = RecurrenceBackend(_NoFitAdapter())
    monkeypatch.setattr(main, "backend", backend, raising=False)
    monkeypatch.setattr(main, "current_nn_model", "recurrence", raising=False)
    return client, backend


@pytest.mark.regression
@pytest.mark.unit
class TestGeneratorSpellingFailsClosedForTheLmu:
    @pytest.mark.parametrize("generator, label", [("spiral", "Spirals"), ("moon", "Moons")])
    @pytest.mark.parametrize("path", ["/api/stage_dataset", "/api/live_dataset_swap"])
    def test_the_juniper_data_name_is_judged_as_the_canopy_dataset(self, recurrence_live, generator, label, path):
        client, backend = recurrence_live
        response = client.post(path, json={"nn_dataset_type": generator, "nn_model": "recurrence"})
        assert response.status_code == 422, response.text
        error = response.json()["error"]
        assert label in error
        assert "needs a 2-D model" in error
        assert backend.get_pending_dataset()["pending"] is None

    def test_moon_stages_on_cascor_and_the_wire_name_is_forwarded(self, client, monkeypatch):
        fake = _fake_backend("demo")
        monkeypatch.setattr(main, "backend", fake, raising=False)
        monkeypatch.setattr(main, "current_nn_model", "cascor", raising=False)
        assert client.post("/api/stage_dataset", json={"nn_dataset_type": "moon", "nn_model": "cascor"}).status_code == 200
        fake.stage_dataset.assert_called_once_with(nn_dataset_type="moon")


@pytest.mark.regression
@pytest.mark.unit
class TestSelectionReadDoesNotCollapsePendingAndLoaded:
    def test_an_empty_pending_type_falls_through_to_the_loaded_dataset(self):
        status = {"pending_dataset": {"nn_dataset_type": "", "dataset_type": None}, "current_dataset": {"dataset_type": "xor"}}
        assert main._backend_dataset_selection(status) == _LOADED_XOR

    def test_a_non_dict_pending_falls_through_to_the_loaded_dataset(self):
        status = {"pending_dataset": ["spiral"], "current_dataset": {"dataset_type": "xor"}}
        assert main._backend_dataset_selection(status) == _LOADED_XOR

    def test_pending_prefers_canopy_s_field_when_the_two_dialects_disagree(self):
        status = {
            "pending_dataset": {"nn_dataset_type": "xor", "dataset_type": "spiral"},
            "current_dataset": {"dataset_type": "circles"},
        }
        assert main._backend_dataset_selection(status) == {"value": "xor", "source": "pending", "generator": "xor"}

    def test_loaded_prefers_cascor_s_field_when_the_two_dialects_disagree(self):
        status = {"current_dataset": {"dataset_type": "spiral", "nn_dataset_type": "xor"}}
        assert main._backend_dataset_selection(status) == {"value": "spirals", "source": "loaded", "generator": "spiral"}

    def test_an_unnameable_pending_does_not_reveal_the_loaded_dataset(self):
        # The next Start trains the pending generator. Falling through to xor would
        # mount a dataset the backend is not about to run.
        status = {"pending_dataset": {"dataset_type": "arc_agi"}, "current_dataset": {"dataset_type": "xor"}}
        assert main._backend_dataset_selection(status) == {"value": None, "source": "pending", "generator": "arc_agi"}

    @pytest.mark.parametrize("status", [None, "idle", []], ids=["none", "string", "list"])
    def test_a_non_dict_status_is_unknown(self, status):
        assert main._backend_dataset_selection(status) == {"value": None, "source": "unknown", "generator": None}
