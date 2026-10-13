#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_y7_model_table_describedby.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-09-22
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   Y7 (model-table half) — each Select button is described
#                by its row's rendered compatibility cell.
#####################################################################
"""Y7, model-table half: the reason a model cannot be selected is the button's accessible description.

Design §4.3 (``JUNIPER_2026-09-02_JUNIPER-CANOPY_SELECTION-REACHABILITY-DESIGN.md``): *"Give the
reason cell an id and point the row's control at it with ``aria-describedby``"*. Before this, the
reason cell was an id-less ``html.Span`` and the Select button carried the reason only in
``title=``. Measured in headless chromium, that ``title`` was the disabled button's accessible
description — but it could never show as a tooltip, because Bootstrap gives ``.btn:disabled``
``pointer-events: none``, and design N4 rules ``title=`` out as the channel for a consequence.

``dbc.Button`` 2.0.4 declares no ``aria-*`` wildcard and raises ``TypeError`` on
``aria-describedby``, so the control is an ``html.Button`` carrying the class string dbc rendered.
The dataset dropdown's half of Y7 shipped separately (a ``role="status"`` notice) and is not
covered here.
"""

import re

import pytest

from frontend.dashboard_manager import DashboardManager
from model_registry import DATASET_TYPES, MODELS, DatasetTypeSpec, ModelSpec

#: A key that is not a valid id as-is (whitespace splits an IDREF list; Dash refuses ``.``), next
#: to one that collides with a naive escape of it. Both must still get valid, distinct ids.
AWKWARD_MODELS = (
    ModelSpec(key="lmu growth.v3", label="LMU growth", category="ts_growth", input_ndim=frozenset({3}), supported_task_types=frozenset({"regression"}), requires_dt=True),
    ModelSpec(key="lmu-growth-v3", label="LMU growth (dashed)", category="ts_growth", input_ndim=frozenset({3}), supported_task_types=frozenset({"regression"}), requires_dt=True),
    ModelSpec(key="flat_clf", label="Flat classifier", category="feedforward", input_ndim=frozenset({2}), supported_task_types=frozenset({"classification"})),
)
AWKWARD_DATASETS = (
    DatasetTypeSpec(value="tab_clf", label="Tabular classes", task_type="classification", ndim=2),
    DatasetTypeSpec(value="seq_irr", label="Sequence (irregular)", task_type="regression", ndim=3, temporal="irregular"),
)

#: ``None`` is ``⊥`` — no dataset — where every row is enabled and states its requirement.
SCENARIOS = [(MODELS, DATASET_TYPES, dataset.value) for dataset in DATASET_TYPES] + [(MODELS, DATASET_TYPES, None)]
SCENARIOS += [(AWKWARD_MODELS, AWKWARD_DATASETS, dataset.value) for dataset in AWKWARD_DATASETS] + [(AWKWARD_MODELS, AWKWARD_DATASETS, None)]

#: HTML: no ASCII whitespace. Stricter here: also a CSS-safe, Dash-safe token.
VALID_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")


def _walk(node):
    yield node
    children = getattr(node, "children", None)
    if isinstance(children, (list, tuple)):
        for child in children:
            yield from _walk(child)
    elif children is not None and not isinstance(children, (str, int, float, bool)):
        yield from _walk(children)


def _the_table(result):
    tables = [node for node in _walk(result) if type(node).__name__ == "Table"]
    assert len(tables) == 1, f"expected one table, found {len(tables)}"
    return tables[0]


def _props(component):
    return component.to_plotly_json()["props"]


def _rows(table):
    """``[(model_key, select_button, compatibility_cell)]`` for every body row."""
    rows = []
    for node in _walk(table):
        if type(node).__name__ == "Tr" and isinstance(node.children, list) and len(node.children) == 5:
            button = node.children[4].children
            if isinstance(getattr(button, "id", None), dict) and button.id.get("type") == "model-select-btn":
                rows.append((button.id["index"], button, node.children[3].children))
    return rows


def _by_id(table, target):
    return [node for node in _walk(table) if getattr(node, "id", None) == target]


def _scenario_id(scenario):
    models, _datasets, dataset_value = scenario
    return f"{'production' if models is MODELS else 'awkward'}:{dataset_value or 'bottom'}"


@pytest.mark.regression
@pytest.mark.unit
@pytest.mark.parametrize("scenario", SCENARIOS, ids=[_scenario_id(s) for s in SCENARIOS])
class TestY7SelectIsDescribedByItsRow:
    def test_every_reason_row_is_described_by_that_reason(self, scenario):
        """The brief's property: a row with a non-empty reason has a Select whose
        ``aria-describedby`` names an element in the SAME table whose text is that reason."""
        models, datasets, dataset_value = scenario
        table = _the_table(DashboardManager._build_model_selection_table(dataset_value, None, models=models, dataset_types=datasets))
        for key, button, cell in _rows(table):
            if not button.disabled:
                continue
            reason = cell.children
            assert isinstance(reason, str) and reason, key
            target = _props(button).get("aria-describedby")
            assert target, f"{key}: a greyed Select with no aria-describedby"
            referenced = _by_id(table, target)
            assert len(referenced) == 1, f"{key}: aria-describedby={target!r} resolves to {len(referenced)} elements in the table"
            assert referenced[0].children == reason, key

    def test_every_row_is_described_by_its_own_compatibility_cell(self, scenario):
        """Enabled rows too — including ``⊥``, where the cell states what the model would need."""
        models, datasets, dataset_value = scenario
        table = _the_table(DashboardManager._build_model_selection_table(dataset_value, None, models=models, dataset_types=datasets))
        rows = _rows(table)
        assert {key for key, _b, _c in rows} == {model.key for model in models}
        for key, button, cell in rows:
            target = _props(button).get("aria-describedby")
            assert target == DashboardManager._model_compat_cell_id(key), key
            assert getattr(cell, "id", None) == target, key
            assert VALID_ID.match(target), target

    def test_describedby_targets_are_unique_in_the_table(self, scenario):
        models, datasets, dataset_value = scenario
        table = _the_table(DashboardManager._build_model_selection_table(dataset_value, None, models=models, dataset_types=datasets))
        targets = [_props(button)["aria-describedby"] for _key, button, _cell in _rows(table)]
        assert len(targets) == len(set(targets)), targets

    def test_a_greyed_select_does_not_repeat_the_reason_in_title(self, scenario):
        """The kept-or-dropped ``title=`` decision. Dropped where it only carried the reason: a
        disabled ``.btn`` never shows a tooltip, and the description now comes from the cell.
        Kept on enabled buttons, where it is a live hover hint."""
        models, datasets, dataset_value = scenario
        table = _the_table(DashboardManager._build_model_selection_table(dataset_value, models[0].key, models=models, dataset_types=datasets))
        for key, button, _cell in _rows(table):
            title = _props(button).get("title")
            if button.disabled:
                assert title is None, f"{key}: title={title!r} on a disabled Select"
            else:
                assert title in ("Currently active", "Select this model"), key


@pytest.mark.regression
@pytest.mark.unit
class TestY7ControlShape:
    def test_the_select_renders_the_classes_dbc_rendered(self):
        """The switch to ``html.Button`` must not change the look. These are the class strings read
        off the dbc-rendered DOM (``btn btn-success btn-sm`` / ``btn btn-outline-primary btn-sm``)."""
        table = _the_table(DashboardManager._build_model_selection_table("spirals", "cascor"))
        classes = {key: _props(button).get("className") for key, button, _cell in _rows(table)}
        assert classes == {"cascor": "btn btn-success btn-sm", "recurrence": "btn btn-outline-primary btn-sm"}

    def test_the_cell_id_is_deterministic_valid_and_injective(self):
        keys = ["cascor", "recurrence", "lmu-growth-v3", "lmu growth.v3", "lmu_growth_v3", "a.b", "a_2e_b", "a{b}", "tab\tkey", "Δt-model", ""]
        ids = [DashboardManager._model_compat_cell_id(key) for key in keys]
        assert ids == [DashboardManager._model_compat_cell_id(key) for key in keys], "not deterministic"
        assert len(set(ids)) == len(keys), dict(zip(keys, ids))
        for key, cell_id in zip(keys, ids):
            assert VALID_ID.match(cell_id), (key, cell_id)
        # Plain keys stay readable.
        assert DashboardManager._model_compat_cell_id("cascor") == "model-compat-cascor"
        assert DashboardManager._model_compat_cell_id("lmu-growth-v3") == "model-compat-lmu-growth-v3"
