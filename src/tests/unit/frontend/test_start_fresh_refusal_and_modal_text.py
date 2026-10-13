#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_start_fresh_refusal_and_modal_text.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-09-24
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   F1 -- a Start refused because the staged dataset
#                is wider than the network points at Start fresh.
#                F2 -- the restart modal says the parameters carry
#                over a start-fresh.
#####################################################################
"""The canopy half of two owner rulings of 2026-09-24 on the A-N2 findings.

juniper-ml ``reports/2026-09-23_canopy-a-n2-generate-stage-train-render/README.md`` records both.

**F1.** A plain Start continues the current network, and cascor cannot widen one on a Start. It
used to consume the staged dataset and THEN refuse it, so every route named the new dataset beside
the previous run's results. cascor now refuses first, and it opens the message with
``[start_fresh_required]``. The dataset stays staged, and so the pending-dataset banner stays up.
This alert recognises the marker and names the two controls that apply the remedy. It is a
dismissable danger alert that is not auto-dismissed, because it carries an instruction.

**F2.** cascor now carries the applied params onto the network a start-fresh rebuilds. The
modal's own text said a start-fresh was "functionally a clean stack launch", which is no longer
true, so it now says the parameters carry over.
"""

from __future__ import annotations

import dash
import pytest

from frontend.dashboard_manager import START_FRESH_REQUIRED_MARKER, DashboardManager

pytestmark = pytest.mark.unit

#: cascor's refusal after the marker, verbatim from juniper-cascor's ``_refuse_dataset_wider_than_network``.
CASCOR_SENTENCE = "The staged dataset {name!r} ({features} features, {outputs} outputs) is wider than the current network (2 inputs, 2 outputs). A start continues the current network, and only a live dataset swap can widen one, so this start needs start_fresh, which builds a new network from the dataset. Nothing was loaded: the dataset is still staged, and the current network and its results are unchanged."


def _refusal(name, features, outputs):
    """The refusal as it reaches the dashboard: canopy's 409 wrapping cascor's 409."""
    sentence = CASCOR_SENTENCE.format(name=name, features=features, outputs=outputs)
    return f"HTTP 409: Training could not be started: Training cannot be started: {START_FRESH_REQUIRED_MARKER} {sentence}"


def _text(node) -> str:
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, (list, tuple)):
        return "".join(_text(child) for child in node)
    return _text(getattr(node, "children", None))


def _components(tree):
    out, stack = [], [tree]
    while stack:
        node = stack.pop()
        if node is None or isinstance(node, (str, int, float, bool)):
            continue
        if isinstance(node, (list, tuple)):
            stack.extend(node)
            continue
        out.append(node)
        stack.append(getattr(node, "children", None))
    return out


@pytest.fixture(scope="module")
def manager():
    return DashboardManager({})


@pytest.fixture(scope="module")
def layout(manager):
    return _components(manager.app.layout)


def _by_id(layout, component_id):
    (component,) = [c for c in layout if getattr(c, "id", None) == component_id]
    return component


class TestF1TheRefusalPointsAtStartFresh:
    def test_the_marker_is_cascor_s_literal(self):
        # cascor pins the same literal (``_PROJECT_API_START_FRESH_REQUIRED_MARKER``); the two
        # are one contract, and a rename on either side silently drops canopy back to the
        # generic alert.
        assert START_FRESH_REQUIRED_MARKER == "[start_fresh_required]"

    @pytest.mark.parametrize(("name", "features", "outputs"), [("equities", 15, 2), ("mnist", 784, 10)], ids=["equities", "mnist"])
    def test_the_refusal_names_the_remedy_and_what_did_not_change(self, manager, name, features, outputs):
        full = _refusal(name, features, outputs)
        alert = manager._surface_training_control_outcome_handler(action={"success": False, "command": "start", "detail": full[:300], "detail_full": full})
        text = _text(alert)
        assert "Stop & Restart with new dataset" in text and "Start fresh" in text
        assert "the dataset is still staged" in text
        assert "still the previous run's" in text
        # cascor's own sentence, naming both shapes, rides along.
        assert f"The staged dataset '{name}' ({features} features, {outputs} outputs) is wider than the current network (2 inputs, 2 outputs)." in text
        assert alert.color == "danger" and alert.dismissable is True
        assert getattr(alert, "duration", None) is None  # an instruction is not auto-dismissed

    def test_the_300_char_slice_alone_is_enough(self, manager):
        # The REST path may carry only ``detail``. The marker sits near the front of the message,
        # so the alert's slice keeps it.
        full = _refusal("equities", 15, 2)
        assert full.index(START_FRESH_REQUIRED_MARKER) < 300
        alert = manager._surface_training_control_outcome_handler(action={"success": False, "command": "start", "detail": full[:300]})
        assert "Start fresh" in _text(alert)

    def test_any_other_start_failure_keeps_the_generic_alert(self, manager):
        alert = manager._surface_training_control_outcome_handler(action={"success": False, "command": "start", "detail": "HTTP 409: Training data not provided"})
        assert _text(alert.children[0]) == "Start failed. "
        assert alert.duration == 8000

    def test_the_marker_on_another_command_is_not_this_alert(self, manager):
        alert = manager._surface_training_control_outcome_handler(action={"success": False, "command": "stop", "detail": _refusal("equities", 15, 2)})
        assert _text(alert.children[0]) == "Stop failed. "

    def test_the_partial_data_prompt_does_not_open_for_it(self, manager):
        full = _refusal("equities", 15, 2)
        assert manager._open_dataset_shortfall_prompt_handler({"success": False, "command": "start", "detail": full[:300], "detail_full": full}) == (dash.no_update,) * 3


class TestF1TheAlertNamesControlsThatExist:
    """The alert names two controls. If either is renamed, the instruction points at nothing."""

    def test_the_pending_banner_button_carries_the_named_label(self, layout):
        assert _text(_by_id(layout, "restart-with-new-dataset-button")) == "Stop & Restart with new dataset"

    def test_the_modal_toggle_carries_the_named_label(self, layout):
        assert _by_id(layout, "restart-start-fresh-toggle").label.startswith("Start fresh")


class TestF2TheModalSaysTheParametersCarryOver:
    def test_the_toggle_label_says_parameters_are_kept(self, layout):
        assert "parameters and snapshots kept" in _by_id(layout, "restart-start-fresh-toggle").label

    def test_no_modal_text_still_calls_it_a_clean_stack_launch(self, layout):
        # A clean launch would reset the params to the engine defaults, which is what F2 fixed.
        modal = _components(_by_id(layout, "restart-confirm-modal"))
        text = " ".join(_text(c) for c in modal if isinstance(getattr(c, "children", None), str))
        assert "clean stack launch" not in text
        assert "The applied parameters carry over" in text
