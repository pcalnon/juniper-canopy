#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_recurrence_routing.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-06-22
# Last Modified: 2026-06-22
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   Unit tests for create_backend() recurrence provider routing
#                (A1-ii / D5) and the model_registry get_model_spec() lookup.
#####################################################################
"""Unit tests for the recurrence provider routing in ``backend.create_backend`` (A1-ii).

``create_backend(nn_model=...)`` routes a recurrence-provider model to ``RecurrenceBackend``
only when ``recurrence_service_url`` is configured; every other case (non-recurrence model,
unconfigured URL, ``nn_model=None``) falls through to the unchanged demo/cascor selection.
Settings are stubbed so the routing decision is tested in isolation (no ``.env``, no
network).
"""

from types import SimpleNamespace

import pytest

from backend.recurrence_backend import RecurrenceBackend
from model_registry import RECURRENCE_PROVIDER, get_model_spec


def _stub_settings(**overrides):
    base = {
        "recurrence_service_url": None,
        "recurrence_api_key": None,
        "demo_mode": False,
        "cascor_service_url": None,
        "cascor_ws_origin": "",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _create(monkeypatch, *, nn_model, **settings_overrides):
    """Call create_backend(nn_model=...) with a stubbed Settings object."""
    import settings as settings_module

    monkeypatch.setattr(settings_module, "get_settings", lambda: _stub_settings(**settings_overrides))
    from backend import create_backend

    return create_backend(nn_model=nn_model)


@pytest.mark.unit
class TestGetModelSpec:
    def test_recurrence_resolves_with_recurrence_provider(self):
        spec = get_model_spec("recurrence")
        assert spec is not None
        assert spec.provider == RECURRENCE_PROVIDER

    def test_cascor_resolves_in_process(self):
        spec = get_model_spec("cascor")
        assert spec is not None
        assert spec.provider == "in-process"

    def test_unknown_key_returns_none(self):
        assert get_model_spec("does-not-exist") is None


@pytest.mark.unit
class TestRecurrenceRouting:
    def test_recurrence_with_url_routes_to_recurrence_backend(self, monkeypatch):
        backend = _create(monkeypatch, nn_model="recurrence", recurrence_service_url="http://rec:8210", recurrence_api_key="k")
        assert isinstance(backend, RecurrenceBackend)
        assert backend.backend_type == "recurrence"

    def test_recurrence_without_url_falls_through(self, monkeypatch):
        # Recurrence requested but not configured → must NOT route to recurrence.
        backend = _create(monkeypatch, nn_model="recurrence", demo_mode=True)
        assert not isinstance(backend, RecurrenceBackend)

    def test_cascor_model_does_not_route_to_recurrence(self, monkeypatch):
        # Even with a recurrence URL set, a non-recurrence model falls through.
        backend = _create(monkeypatch, nn_model="cascor", recurrence_service_url="http://rec:8210", demo_mode=True)
        assert not isinstance(backend, RecurrenceBackend)

    def test_unknown_model_falls_through(self, monkeypatch):
        backend = _create(monkeypatch, nn_model="does-not-exist", recurrence_service_url="http://rec:8210", demo_mode=True)
        assert not isinstance(backend, RecurrenceBackend)

    def test_none_model_preserves_default_path(self, monkeypatch):
        # The startup default (nn_model=None) must never trigger recurrence routing,
        # even when a recurrence URL happens to be configured.
        backend = _create(monkeypatch, nn_model=None, recurrence_service_url="http://rec:8210", demo_mode=True)
        assert not isinstance(backend, RecurrenceBackend)
