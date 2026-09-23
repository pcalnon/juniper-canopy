#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_y8_disabled_derives_from_compatible.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-09-22
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   Y8 — every greyed control in the selection UI is
#                ``not compatible()``, and carries a reason iff greyed.
#####################################################################
"""Y8: the ``disabled`` decision is ``compatible()``'s, never a reason-string helper's.

Before Y8, ``gated_dataset_options`` disabled an option when ``dataset_reason`` returned a string,
and the model table disabled a Select when ``model_reason`` did. Both helpers re-implemented all
three compatibility axes inline, so the load-bearing predicate had three independent expressions:
``compatible()`` and two phrase builders. They agreed only because nobody had changed one of them.

The properties pinned here, over EVERY (model, dataset) pair of two registries:

* ``disabled == not compatible(dataset, model)`` — on the sidebar dataset options and on the model
  table's Select buttons;
* a reason is shown **iff** the control is disabled.

**Two registries, because the production one cannot catch an axis mistake.** Every shipped rank-3
model is Δt-aware, so no production pair fails the temporal axis alone — drop that axis from the
gate and the production registry stays green. ``PER_AXIS_*`` fails each axis ALONE at least once,
and ``test_the_per_axis_registry_fails_each_axis_alone`` guards that premise so the fixture cannot
quietly stop testing what it exists for.
"""

import pytest

import frontend.dashboard_manager as dashboard_manager
import model_registry
from frontend.dashboard_manager import DashboardManager
from model_registry import DATASET_TYPES, MODELS, DatasetTypeSpec, ModelSpec, compatible, dataset_reason, gated_dataset_options, model_reason, temporal_ok

PER_AXIS_MODELS = (
    ModelSpec(key="clf2d", label="2-D classifier", category="feedforward", input_ndim=frozenset({2}), supported_task_types=frozenset({"classification"})),
    ModelSpec(key="reg3d", label="3-D regressor", category="ts_established", input_ndim=frozenset({3}), supported_task_types=frozenset({"regression"})),
    ModelSpec(key="dtreg3d", label="3-D Δt regressor", category="ts_established", input_ndim=frozenset({3}), supported_task_types=frozenset({"regression"}), requires_dt=True),
)
PER_AXIS_DATASETS = (
    DatasetTypeSpec(value="tab_clf", label="Tabular classes", task_type="classification", ndim=2),
    DatasetTypeSpec(value="tab_reg", label="Tabular values", task_type="regression", ndim=2),
    DatasetTypeSpec(value="seq_clf", label="Sequence classes", task_type="classification", ndim=3),
    DatasetTypeSpec(value="seq_reg", label="Sequence (regular)", task_type="regression", ndim=3, temporal="regular"),
    DatasetTypeSpec(value="seq_irr", label="Sequence (irregular)", task_type="regression", ndim=3, temporal="irregular"),
)

REGISTRIES = {
    "production": (MODELS, DATASET_TYPES),
    "per-axis": (PER_AXIS_MODELS, PER_AXIS_DATASETS),
}

COMPATIBLE_CELL = "✓ compatible"


def _failing_axes(dataset, model):
    """Which named axes a pair fails. Used ONLY to prove the fixture's coverage, never as an oracle."""
    axes = set()
    if dataset.ndim not in model.input_ndim:
        axes.add("ndim")
    if dataset.task_type not in model.supported_task_types:
        axes.add("task_type")
    if not temporal_ok(dataset, model):
        axes.add("temporal")
    return frozenset(axes)


def _walk(node):
    yield node
    children = getattr(node, "children", None)
    if isinstance(children, (list, tuple)):
        for child in children:
            yield from _walk(child)
    elif children is not None and not isinstance(children, (str, int, float, bool)):
        yield from _walk(children)


def _table_rows(table):
    """``{model_key: (select_button, compatibility_cell)}`` for every body row of the model table."""
    rows = {}
    for node in _walk(table):
        if type(node).__name__ != "Tr" or not isinstance(node.children, list) or len(node.children) != 5:
            continue
        compat_td, select_td = node.children[3], node.children[4]
        button = select_td.children
        if isinstance(getattr(button, "id", None), dict) and button.id.get("type") == "model-select-btn":
            rows[button.id["index"]] = (button, compat_td.children)
    return rows


@pytest.mark.regression
@pytest.mark.unit
class TestY8FixturePremise:
    def test_the_per_axis_registry_fails_each_axis_alone(self):
        seen = {_failing_axes(dataset, model) for model in PER_AXIS_MODELS for dataset in PER_AXIS_DATASETS}
        for axis in ("ndim", "task_type", "temporal"):
            assert frozenset({axis}) in seen, f"no per-axis pair fails {axis} ALONE, so a gate that ignores {axis} would pass"
        assert frozenset() in seen, "the per-axis registry must also contain compatible pairs"


@pytest.mark.regression
@pytest.mark.unit
@pytest.mark.parametrize("registry", sorted(REGISTRIES))
class TestY8DatasetOptions:
    """The sidebar dataset dropdown (``gated_dataset_options``)."""

    def test_disabled_is_exactly_not_compatible(self, registry):
        models, datasets = REGISTRIES[registry]
        for model in models:
            options = gated_dataset_options(model.key, models=models, dataset_types=datasets)
            assert [option["value"] for option in options] == [dataset.value for dataset in datasets]
            for dataset, option in zip(datasets, options):
                disabled = option.get("disabled", False)
                assert disabled is (not compatible(dataset, model)), (registry, model.key, dataset.value, option)

    def test_a_reason_is_shown_iff_disabled(self, registry):
        models, datasets = REGISTRIES[registry]
        for model in models:
            for dataset, option in zip(datasets, gated_dataset_options(model.key, models=models, dataset_types=datasets)):
                where = (registry, model.key, dataset.value, option)
                if option.get("disabled"):
                    prefix = f"{dataset.label} — "
                    assert option["label"].startswith(prefix), where
                    reason = option["label"][len(prefix) :]
                    assert reason and reason != "None", where
                    assert reason == dataset_reason(dataset, model), where
                else:
                    assert "disabled" not in option, where
                    assert option["label"] == dataset.label, where
                    assert dataset_reason(dataset, model) is None, where


@pytest.mark.regression
@pytest.mark.unit
@pytest.mark.parametrize("registry", sorted(REGISTRIES))
class TestY8ModelTable:
    """The model-selection table (``_build_model_selection_table``), against every dataset."""

    def test_disabled_is_exactly_not_compatible(self, registry):
        models, datasets = REGISTRIES[registry]
        for dataset in datasets:
            rows = _table_rows(DashboardManager._build_model_selection_table(dataset.value, None, models=models, dataset_types=datasets))
            assert set(rows) == {model.key for model in models}, (registry, dataset.value)
            for model in models:
                button, _cell = rows[model.key]
                assert button.disabled is (not compatible(dataset, model)), (registry, dataset.value, model.key)

    def test_a_reason_is_shown_iff_disabled(self, registry):
        models, datasets = REGISTRIES[registry]
        for dataset in datasets:
            rows = _table_rows(DashboardManager._build_model_selection_table(dataset.value, None, models=models, dataset_types=datasets))
            for model in models:
                button, cell = rows[model.key]
                where = (registry, dataset.value, model.key)
                if button.disabled:
                    assert isinstance(cell.children, str) and cell.children and cell.children != COMPATIBLE_CELL, where
                    assert cell.children == model_reason(model, dataset), where
                else:
                    assert cell.children == COMPATIBLE_CELL, where
                    assert model_reason(model, dataset) is None, where


@pytest.mark.regression
@pytest.mark.unit
class TestY8AnAxisTheWordingDoesNotKnow:
    """``compatible()`` gaining an axis must move every control with it, and never leave a greyed
    control without a reason. Simulated by patching the predicate for one pair whose three NAMED
    axes all pass — exactly the pair a new, unnamed axis would reject."""

    @pytest.fixture
    def rejected_pair(self, monkeypatch):
        spirals = next(dataset for dataset in DATASET_TYPES if dataset.value == "spirals")
        cascor = next(model for model in MODELS if model.key == "cascor")
        assert _failing_axes(spirals, cascor) == frozenset(), "premise: every named axis passes for this pair"
        real = model_registry.compatible

        def with_a_new_axis(dataset, model):
            return False if (dataset.value, model.key) == ("spirals", "cascor") else real(dataset, model)

        monkeypatch.setattr(model_registry, "compatible", with_a_new_axis)
        monkeypatch.setattr(dashboard_manager, "compatible", with_a_new_axis)
        return spirals, cascor

    def test_the_dataset_option_is_greyed_with_a_reason(self, rejected_pair):
        options = {option["value"]: option for option in gated_dataset_options("cascor")}
        assert options["spirals"]["disabled"] is True
        assert options["spirals"]["label"] == "Spirals — not compatible with this model"
        # Every other option still follows the real predicate.
        assert "disabled" not in options["xor"]

    def test_the_model_select_is_greyed_with_a_reason(self, rejected_pair):
        button, cell = _table_rows(DashboardManager._build_model_selection_table("spirals", None))["cascor"]
        assert button.disabled is True
        assert cell.children == "not compatible with this dataset"

    def test_neither_helper_returns_none_for_the_rejected_pair(self, rejected_pair):
        spirals, cascor = rejected_pair
        assert dataset_reason(spirals, cascor) == "not compatible with this model"
        assert model_reason(cascor, spirals) == "not compatible with this dataset"
