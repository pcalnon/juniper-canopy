#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_model_table.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-06-25
# Last Modified: 2026-06-25
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   A1b-1 model-selection modal/table regression tests: the
#                custom dbc.Table builder (compatibility cells, status
#                badges, per-row Select disabled for incompatible models,
#                active-row highlight), the open/close modal handler, and
#                the table-Select -> store-mirror + modal-close handler.
#####################################################################
"""Regression tests for the A1b-1 model-selection surface (juniper-canopy #368).

A1b-1 replaces the sidebar ``nn-model-dropdown`` with a compact summary + a "▸ change" button
that opens a dedicated ``dbc.Modal`` holding a custom ``dbc.Table`` of models. Selection happens
via a per-row, pattern-matching Select button that reuses the iv-3a ``_select_model_handler``
(POST /api/model/select + store mirror) and then closes the modal.

These exercise the testable bodies behind those callbacks — no server, no browser:

* ``_build_model_selection_table`` — rows = the registry; the compatibility cell + Select-disabled
  state are computed against the current dataset; per ratified option (a) a ``coming_soon`` model
  stays selectable (only *incompatible* is disabled); the active row is highlighted.
* ``_status_badge`` — the lifecycle badge (D8), distinct from incompatibility.
* ``_toggle_model_modal_handler`` — open (rebuild table vs current dataset) / close.
* ``_select_model_from_table_handler`` — resolve the clicked key, apply, close; guard the
  dynamic-insertion no-click fire; keep the modal open on a failed apply.
* ``_initial_model_summary`` — the at-rest summary seed.

Constructing ``DashboardManager({})`` here also validates that the new modal + the rewired
pattern-matching select callback + the toggle callback register cleanly (no ``allow_duplicate``
duplicate-output conflicts).
"""

from unittest.mock import MagicMock

import dash
import pytest
import requests

from frontend.dashboard_manager import DashboardManager
from model_registry import MODELS


@pytest.fixture(scope="module")
def manager():
    """A DashboardManager instance (also validates the layout + callbacks register cleanly)."""
    return DashboardManager({})


def _resp(*, ok, json_body=None, status_code=200, text=""):
    resp = MagicMock(ok=ok, status_code=status_code, text=text)
    resp.json.return_value = json_body or {}
    return resp


# --------------------------------------------------------------------------- tree-walk helpers


def _walk(node):
    """Yield ``node`` and every descendant component in its children tree."""
    yield node
    children = getattr(node, "children", None)
    if isinstance(children, (list, tuple)):
        for child in children:
            yield from _walk(child)
    elif children is not None and not isinstance(children, (str, int, float, bool)):
        yield from _walk(children)


def _select_buttons(table):
    """Every per-row Select button (its id is the pattern-matching dict)."""
    return [n for n in _walk(table) if isinstance(getattr(n, "id", None), dict) and n.id.get("type") == "model-select-btn"]


def _button_for(table, key):
    for button in _select_buttons(table):
        if button.id.get("index") == key:
            return button
    raise AssertionError(f"no Select button for model {key!r}")


def _all_text(node):
    """All string content anywhere under ``node`` (for reason-cell assertions)."""
    texts = []

    def rec(n):
        if isinstance(n, str):
            texts.append(n)
            return
        child = getattr(n, "children", None)
        if isinstance(child, str):
            texts.append(child)
        elif isinstance(child, (list, tuple)):
            for grandchild in child:
                rec(grandchild)
        elif child is not None and not isinstance(child, (int, float, bool)):
            rec(child)

    rec(node)
    return " | ".join(texts)


def _rows(table):
    """Every ``html.Tr`` in the table (header + body); callers filter by className."""
    return [n for n in _walk(table) if type(n).__name__ == "Tr"]


def _has_id(node, target):
    """True when any component under ``node`` carries ``id == target``."""
    return any(getattr(n, "id", None) == target for n in _walk(node))


# --------------------------------------------------------------------------- table builder


def test_table_has_one_row_per_registry_model_with_select_buttons():
    table = DashboardManager._build_model_selection_table("spirals", "cascor")
    buttons = _select_buttons(table)
    assert {button.id["index"] for button in buttons} == {model.key for model in MODELS}
    # Every Select button is a pattern-matching id (so one ALL callback observes them all).
    assert all(button.id["type"] == "model-select-btn" for button in buttons)


def test_table_greys_incompatible_models_against_2d_dataset():
    # spirals = 2-D classification: cascor compatible, the 3-D recurrence model is not.
    table = DashboardManager._build_model_selection_table("spirals", "cascor")
    assert _button_for(table, "cascor").disabled is False
    assert _button_for(table, "recurrence").disabled is True
    # The model-perspective reason sits in the row (what data the model needs).
    assert "needs 3-D data" in _all_text(table)


def test_table_greys_incompatible_models_against_3d_dataset():
    # equities_seq = 3-D irregular regression: recurrence compatible, the 2-D cascor model is not.
    table = DashboardManager._build_model_selection_table("equities_seq", "recurrence")
    assert _button_for(table, "recurrence").disabled is False
    assert _button_for(table, "cascor").disabled is True
    assert "needs 2-D data" in _all_text(table)


def test_table_option_a_coming_soon_stays_selectable_when_compatible():
    """Ratified option (a): a coming_soon model is NOT disabled — only *incompatible* is (D8 -> iv-5)."""
    table = DashboardManager._build_model_selection_table("equities_seq", "recurrence")
    recurrence = next(model for model in MODELS if model.key == "recurrence")
    assert recurrence.status == "coming_soon"  # guard the premise
    assert _button_for(table, "recurrence").disabled is False  # selectable despite coming_soon


def test_table_highlights_the_active_row_and_labels_its_button():
    table = DashboardManager._build_model_selection_table("spirals", "cascor")
    assert _button_for(table, "cascor").children == "Selected"
    assert _button_for(table, "recurrence").children == "Select"
    active_rows = [row for row in _rows(table) if getattr(row, "className", "") == "table-active"]
    assert len(active_rows) == 1
    assert "CasCor" in _all_text(active_rows[0])


def test_table_without_a_dataset_treats_all_models_as_compatible():
    # No dataset selected (e.g. cleared) -> no model is greyed (compatibility is best-effort).
    table = DashboardManager._build_model_selection_table(None, "cascor")
    assert all(button.disabled is False for button in _select_buttons(table))


def test_table_unknown_dataset_value_treats_all_models_as_compatible():
    # An unknown/stale dataset value resolves to no spec -> never grey every model.
    table = DashboardManager._build_model_selection_table("does-not-exist", "cascor")
    assert all(button.disabled is False for button in _select_buttons(table))


# --------------------------------------------------------------------------- status badge


def test_status_badge_colors_by_lifecycle():
    assert DashboardManager._status_badge("live").color == "success"
    assert DashboardManager._status_badge("coming_soon").color == "info"
    assert DashboardManager._status_badge("coming_soon").children == "coming soon"
    # Unknown status falls back to a neutral badge rather than raising.
    assert DashboardManager._status_badge("nonsense").color == "secondary"


# --------------------------------------------------------------------------- open/close modal


def test_toggle_opens_and_builds_table_against_current_dataset(manager):
    is_open, children = manager._toggle_model_modal_handler("nn-model-change-button", "equities_seq", "recurrence")
    assert is_open is True
    # The container children is the freshly-built table, gated against the passed dataset.
    assert type(children).__name__ == "Table"
    assert _button_for(children, "cascor").disabled is True  # 2-D model vs the 3-D dataset


def test_toggle_close_leaves_table_untouched(manager):
    is_open, children = manager._toggle_model_modal_handler("model-selection-modal-close", "spirals", "cascor")
    assert is_open is False
    assert children is dash.no_update


# --------------------------------------------------------------------------- select from table


def test_select_from_table_applies_and_closes_modal(manager, monkeypatch):
    body = {"nn_model": "recurrence", "backend": "recurrence", "execution": "one_shot", "status": "coming_soon", "swapped": True}
    monkeypatch.setattr(requests, "post", lambda *a, **k: _resp(ok=True, json_body=body))
    store, model_class, summary, is_open = manager._select_model_from_table_handler([None, 1], {"type": "model-select-btn", "index": "recurrence"})
    assert store == "recurrence"
    assert model_class == "one_shot"
    assert summary.startswith("Active: Recurrence (LMU)")
    assert is_open is False  # a successful apply closes the modal


def test_select_from_table_noop_on_dynamic_insertion_fire(manager):
    # The pattern-matching callback fires once when the buttons are first inserted (all n_clicks None).
    result = manager._select_model_from_table_handler([None, None], {"type": "model-select-btn", "index": "cascor"})
    assert result == (dash.no_update, dash.no_update, dash.no_update, dash.no_update)
    # A missing/None triggered id is likewise a no-op.
    assert manager._select_model_from_table_handler([None, None], None) == (dash.no_update, dash.no_update, dash.no_update, dash.no_update)


def test_select_from_table_keeps_modal_open_on_failed_apply(manager, monkeypatch):
    # A transient apply failure -> handler no-ops all three -> the modal must NOT close.
    monkeypatch.setattr(requests, "post", lambda *a, **k: _resp(ok=False, status_code=502, text="init failed"))
    store, model_class, summary, is_open = manager._select_model_from_table_handler([1, None], {"type": "model-select-btn", "index": "cascor"})
    assert store is dash.no_update
    assert is_open is dash.no_update  # modal stays open on the prior model


# --------------------------------------------------------------------------- sidebar summary seed


def test_initial_model_summary_seeds_the_default_model(manager):
    # cascor is the DEFAULT_MODEL_KEY and is live -> "Active: CasCor ..." with no status note.
    assert manager._initial_model_summary() == "Active: CasCor (Cascade-Correlation)"


# --------------------------------------------------------------------------- degenerate state (A1b-2, §5.8)


def test_table_degenerate_empty_set_shows_recovery_alert():
    # Inject a model population with nothing compatible with the 3-D dataset (cascor is 2-D only)
    # -> a recovery message wraps the (all-greyed) table, not a bare Table (§5.8).
    cascor_only = tuple(model for model in MODELS if model.key == "cascor")
    result = DashboardManager._build_model_selection_table("equities_seq", "recurrence", models=cascor_only)
    assert type(result).__name__ == "Div"  # alert + table wrapper
    assert _has_id(result, "model-selection-empty-alert")
    assert "No compatible model" in _all_text(result)
    assert any(type(n).__name__ == "Table" for n in _walk(result))  # the greyed table is still shown below


def test_table_non_degenerate_returns_bare_table():
    # >=1 compatible model -> a bare Table, no recovery wrapper.
    result = DashboardManager._build_model_selection_table("equities_seq", "recurrence")
    assert type(result).__name__ == "Table"
    assert not _has_id(result, "model-selection-empty-alert")


# --------------------------------------------------------------------------- reverse-gate sidebar hint (A1b-2, §5.3)


def test_dataset_model_hint_handler_text_and_clear(manager):
    assert manager._dataset_model_hint_handler("equities_seq") == "3-D Δt-aware models only"
    assert manager._dataset_model_hint_handler("spirals") == "2-D models only"
    # no / unknown dataset -> "" so the annotation clears (never renders "None")
    assert manager._dataset_model_hint_handler("") == ""
    assert manager._dataset_model_hint_handler("does-not-exist") == ""


def test_initial_dataset_model_hint_seeds_default_dataset(manager):
    # DEFAULT_DATASET_TYPE = spirals (2-D) -> "2-D models only" at first paint.
    assert manager._initial_dataset_model_hint() == "2-D models only"


def test_dataset_hint_callback_is_registered(manager):
    """Wiring guard: the reverse-gate annotation Output (a Div, so invisible to the control-graph
    lint) is connected to a callback. Catches accidental removal/miswiring of annotate_model_hint."""
    assert any(key.startswith("nn-model-dataset-hint.children") for key in manager.app.callback_map)
