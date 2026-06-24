#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_model_picker.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-06-24
# Last Modified: 2026-06-24
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   A1-iv-3a sidebar model-picker regression tests: the
#                _select_model_handler POSTs to /api/model/select and
#                mirrors the result into the selection + model-class
#                stores, with a no-op fallback on any failure.
#####################################################################
"""Regression tests for the A1-iv-3a model picker (juniper-canopy #368).

Exercises ``DashboardManager._select_model_handler`` (the testable body behind the
``nn-model-dropdown`` callback) with a mocked ``/api/model/select`` round-trip — no server.
On success it returns the swap response + the execution paradigm (mirrored to
``model-class-store``) + a compact summary; on an empty selection or any transport/HTTP failure
it returns ``dash.no_update`` for all three outputs so the UI stays on its prior model.

Constructing the ``DashboardManager`` here also validates that the new picker layout and the
``allow_duplicate`` model-class-store callback register cleanly.
"""

from unittest.mock import MagicMock

import dash
import pytest
import requests

from frontend.dashboard_manager import DashboardManager


@pytest.fixture(scope="module")
def manager():
    """A DashboardManager instance (also validates the layout + callbacks register cleanly)."""
    return DashboardManager({})


def _resp(*, ok, json_body=None, status_code=200, text=""):
    resp = MagicMock(ok=ok, status_code=status_code, text=text)
    resp.json.return_value = json_body or {}
    return resp


def test_select_model_handler_success_mirrors_swap(manager, monkeypatch):
    body = {"nn_model": "recurrence", "backend": "recurrence", "execution": "one_shot", "status": "coming_soon", "swapped": True}
    monkeypatch.setattr(requests, "post", lambda *a, **k: _resp(ok=True, json_body=body))
    store, model_class, summary = manager._select_model_handler("recurrence")
    assert store == body
    assert model_class == "one_shot"  # mirrored to model-class-store -> drives cascade suppression
    assert summary.startswith("Active: Recurrence (LMU)")
    assert "coming soon" in summary


def test_select_model_handler_empty_is_noop(manager):
    assert manager._select_model_handler("") == (dash.no_update, dash.no_update, dash.no_update)
    assert manager._select_model_handler(None) == (dash.no_update, dash.no_update, dash.no_update)


def test_select_model_handler_http_error_is_noop(manager, monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *a, **k: _resp(ok=False, status_code=502, text="init failed"))
    assert manager._select_model_handler("recurrence") == (dash.no_update, dash.no_update, dash.no_update)


def test_select_model_handler_transport_error_is_noop(manager, monkeypatch):
    def _boom(*args, **kwargs):
        raise requests.ConnectionError("down")

    monkeypatch.setattr(requests, "post", _boom)
    assert manager._select_model_handler("recurrence") == (dash.no_update, dash.no_update, dash.no_update)


def test_model_summary_text_live_vs_coming_soon():
    assert DashboardManager._model_summary_text({"nn_model": "cascor", "status": "live"}) == "Active: CasCor (Cascade-Correlation)"
    soon = DashboardManager._model_summary_text({"nn_model": "recurrence", "status": "coming_soon"})
    assert soon.startswith("Active: Recurrence (LMU)")
    assert "coming soon" in soon
