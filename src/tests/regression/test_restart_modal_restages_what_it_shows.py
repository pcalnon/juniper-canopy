#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_restart_modal_restages_what_it_shows.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-10-26
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   juniper-canopy#735 -- the restart modal renders its
#                dataset fields per type, and Confirm re-stages exactly
#                what the modal displays (owner ruling 2026-09-22).
#####################################################################
"""The restart modal renders its dataset fields per type and re-stages exactly what it shows (juniper-canopy#735).

**The ruling this enforces.** The owner ruled on 2026-09-22 that the modal keeps its ``enabled[0]`` swap of a
stranded dataset, where the sidebar clears to ``⊥``. The reason: "the modal is a confirmation dialog, and it
shows the operator the swapped value before anything is re-staged: Confirm re-stages exactly what the modal
displays, and refuses ``⊥``". Sources: point 4 of §5.6.1 of juniper-ml's
``JUNIPER_2026-06-17_JUNIPER-CANOPY_MODEL-DATASET-SELECTION-DESIGN.md``, and the §4.5 note of
``JUNIPER_2026-09-02_JUNIPER-CANOPY_SELECTION-REACHABILITY-DESIGN.md``. Only the parameter fields go per type
here. The type behaviour (the swap, the ``⊥`` refusal, the gate against the selected model) is unchanged, and
``TestX2RestartModalIsGatedAgainstTheSelectedModel`` still pins it.

**What #735 found.** The modal showed the spiral-era fields (Samples, Noise, Spiral rotations, Spirals) for
every type, sequence generators included, and Confirm re-staged all four. For a sequence generator, W1.2's
filter then dropped them at Start while the modal had "planned" them; for flat ``equities``, juniper-data
dropped them silently. Separately, the swap stored the swapped value as the baseline, so an untouched Confirm
after a swap re-staged nothing and restarted on the very dataset the modal had replaced.

**The invariant, pinned directly.** For every type, the keys Confirm re-stages are the fields the modal
rendered for that type, plus the two documented riders a re-stage carries without a field of its own -- the
registry seed (canopy#668) and the FR9 ``nn_model`` mirror (canopy#674) -- and the plan names every one of
them, and every value it does not send.
"""

from unittest import mock

import pytest
import requests

from frontend.dashboard_manager import RESTART_MODAL_STAGE_KEYS, RESTART_MODAL_TYPED_FIELDS, DashboardManager
from model_registry import DATASET_TYPES, MODELS, compatible, dataset_default_params, get_dataset_spec, get_model_spec

# Payload key -> modal key, for reading a re-stage back as the fields it came from.
_MODAL_KEY_OF = {"nn_dataset_type": "dataset_type", **{stage_key: modal_key for modal_key, stage_key in RESTART_MODAL_STAGE_KEYS.items()}}
_RIDERS = {"nn_dataset_params", "nn_model"}
# What the sidebar's typed inputs hold whichever dataset is picked: they prefill the modal for every type.
PREFILL = {"n_samples": 200, "noise": 0.1, "rotations": 1.5, "n_spirals": 2}
EXPECTED_FIELDS = {
    "spirals": ("n_samples", "noise", "rotations", "n_spirals"),
    "xor": ("n_samples", "noise"),
    "mnist": ("n_samples", "noise"),
    "circles": ("n_samples", "noise"),
    "moons": ("n_samples", "noise"),
    "gaussian": ("n_samples", "noise"),
    "checkerboard": ("n_samples", "noise"),
    "equities": (),
    "multi_sine": (),
    "mackey_glass": (),
    "irregular_sine": (),
    "ar_p": (),
    "delay_product": (),
    "equities_seq": (),
}
_OK = mock.MagicMock(status_code=200, text="")
_OK.json.return_value = {"success": True, "was_active": False, "start_fresh": False, "steps": []}


def _model_for(dataset_value):
    """A model that can train ``dataset_value``: the one the modal would be opened under."""
    spec = get_dataset_spec(dataset_value)
    return next(model.key for model in MODELS if compatible(spec, model))


def _text(component):
    if component is None:
        return ""
    if isinstance(component, str):
        return component
    if isinstance(component, (list, tuple)):
        return " ".join(_text(child) for child in component)
    return _text(getattr(component, "children", None))


@pytest.fixture(scope="module")
def manager():
    return DashboardManager({})


def _rendered(manager, dataset_type):
    """The dataset fields the modal RENDERS for ``dataset_type``, read off the visibility callback's styles."""
    styles = manager._restart_dataset_field_styles(dataset_type)
    shown = {key for (_id, key, _label), style in zip(RESTART_MODAL_TYPED_FIELDS, styles, strict=False) if style.get("display") != "none"}
    return ({"dataset_type"} | shown) if dataset_type else shown


def _confirm(manager, dataset_vals, baseline_dataset, model_key):
    """Click Confirm; return the body POSTed to /api/stage_dataset, or None when nothing was re-staged."""
    baseline = {"dataset": baseline_dataset, "params": {}}
    with mock.patch("frontend.dashboard_manager.requests.post", return_value=_OK) as post, mock.patch("frontend.dashboard_manager.requests.get", side_effect=requests.RequestException("no backend")):
        manager._execute_restart_handler(n_clicks=1, start_fresh=False, dataset_vals=dataset_vals, param_vals={}, baseline=baseline, nn_model=model_key)
    stages = [call.kwargs["json"] for call in post.call_args_list if call.args[0].endswith("/api/stage_dataset")]
    assert len(stages) <= 1, stages
    return stages[0] if stages else None


def _open(manager, sidebar_type, model_key):
    """Open the modal as the banner's button does, with every generator available and no backend to read params from."""
    with mock.patch.object(manager, "_fetch_generators", return_value=[]), mock.patch("frontend.dashboard_manager.requests.get", side_effect=requests.RequestException("no backend")):
        result = manager._open_restart_confirm_modal_handler(n_clicks=1, dataset_type=sidebar_type, model_key=model_key, **PREFILL)
    displayed = {"dataset_type": result[6], "n_samples": result[7], "noise": result[8], "rotations": result[9], "n_spirals": result[10]}
    # ``result[17]`` is the whole ``restart-modal-baseline`` store; Confirm diffs against its dataset half.
    return displayed, result[17]["dataset"], result[1]


def _assert_restages_what_it_shows(manager, payload, dataset_type, model_key):
    assert payload is not None, f"Confirm re-staged nothing for {dataset_type!r} -- the check would be vacuous"
    assert {_MODAL_KEY_OF[key] for key in payload if key not in _RIDERS} == _rendered(manager, dataset_type), f"{dataset_type}: re-staged {payload}"
    assert payload.get("nn_dataset_params") == (dataset_default_params(dataset_type) or None), f"{dataset_type}: the registry seed rider changed: {payload}"
    assert payload.get("nn_model") == model_key, f"{dataset_type}: the FR9 mirror rider changed: {payload}"


@pytest.mark.regression
@pytest.mark.unit
class TestTheModalRendersItsFieldsPerType:
    def test_every_dataset_type_has_an_expectation(self):
        assert set(EXPECTED_FIELDS) == {spec.value for spec in DATASET_TYPES}

    @pytest.mark.parametrize("dataset_type", sorted(EXPECTED_FIELDS))
    def test_a_type_renders_the_fields_its_generator_has_a_parameter_for(self, manager, dataset_type):
        assert _rendered(manager, dataset_type) == {"dataset_type", *EXPECTED_FIELDS[dataset_type]}

    def test_the_note_explains_a_type_with_no_fields_and_nothing_shows_at_bottom(self, manager):
        assert manager._restart_dataset_field_styles("equities")[-1] == {"display": "block"}
        assert manager._restart_dataset_field_styles("circles")[-1] == {"display": "none"}
        assert all(style == {"display": "none"} for style in manager._restart_dataset_field_styles(None))

    def test_the_fields_follow_the_type_through_one_callback(self, manager):
        found = []
        for output, entry in manager.app.callback_map.items():
            fn = entry.get("callback")
            if getattr(getattr(fn, "__wrapped__", fn), "__name__", None) == "show_restart_dataset_fields":
                found.append((output, [f"{item['id']}.{item['property']}" for item in entry.get("inputs", [])]))
        assert len(found) == 1, found
        output, inputs = found[0]
        # Driven by the type alone, so it fires on every way the type changes: the open (swap included) and the operator.
        assert inputs == ["restart-ds-type.value"]
        for field_id, _key, _label in RESTART_MODAL_TYPED_FIELDS:
            assert f"{field_id}-group.style" in output
        assert "restart-ds-no-fields-note.style" in output


@pytest.mark.regression
@pytest.mark.unit
class TestConfirmReStagesExactlyWhatTheModalDisplays:
    """The WYSIWYG invariant of the 2026-09-22 ruling, for every type and through the ``enabled[0]`` swap."""

    @pytest.mark.parametrize("dataset_type", sorted(EXPECTED_FIELDS))
    def test_picking_a_type_in_the_modal(self, manager, dataset_type):
        # Every typed field holds a value (the sidebar prefilled it); only the rendered ones may travel.
        model_key = _model_for(dataset_type)
        other = "multi_sine" if dataset_type != "multi_sine" else "ar_p"
        payload = _confirm(manager, {"dataset_type": dataset_type, **PREFILL}, {"dataset_type": other, **PREFILL}, model_key)
        _assert_restages_what_it_shows(manager, payload, dataset_type, model_key)

    def test_after_the_swap_onto_spiral_confirm_re_stages_the_swapped_dataset(self, manager):
        # A rank-3 dataset stranded under CasCor: the modal swaps to ``enabled[0]``, which is spirals.
        displayed, baseline_dataset, _summary = _open(manager, "equities_seq", "cascor")
        assert displayed["dataset_type"] == "spirals", "the swap moved: this test pins the spiral case"
        payload = _confirm(manager, displayed, baseline_dataset, "cascor")
        _assert_restages_what_it_shows(manager, payload, "spirals", "cascor")

    def test_after_the_swap_onto_a_sequence_generator_confirm_re_stages_the_type_alone(self, manager):
        # A spiral carried over from a CasCor session, under the LMU: swapped to the first rank-3 seed.
        displayed, baseline_dataset, _summary = _open(manager, "spirals", "recurrence")
        assert displayed["dataset_type"] != "spirals" and _rendered(manager, displayed["dataset_type"]) == {"dataset_type"}
        payload = _confirm(manager, displayed, baseline_dataset, "recurrence")
        _assert_restages_what_it_shows(manager, payload, displayed["dataset_type"], "recurrence")
        assert not {"nn_dataset_elements", "nn_dataset_noise", "nn_spiral_rotations", "nn_spiral_number"} & payload.keys()

    def test_after_the_swap_the_operator_can_still_pick_another_type(self, manager):
        displayed, baseline_dataset, _summary = _open(manager, "equities_seq", "cascor")
        payload = _confirm(manager, dict(displayed, dataset_type="equities"), baseline_dataset, "cascor")
        _assert_restages_what_it_shows(manager, payload, "equities", "cascor")

    def test_an_untouched_confirm_without_a_swap_still_re_stages_nothing(self, manager):
        # The simple-confirm default is kept: no swap, no edit, nothing re-staged.
        displayed, baseline_dataset, _summary = _open(manager, "circles", "cascor")
        assert displayed["dataset_type"] == "circles"
        assert _confirm(manager, displayed, baseline_dataset, "cascor") is None

    def test_a_field_edited_and_then_hidden_is_not_re_staged(self, manager):
        # Samples edited under circles, then the type moved to equities, which renders no Samples.
        payload = _confirm(manager, {"dataset_type": "equities", **PREFILL, "n_samples": 900}, {"dataset_type": "circles", **PREFILL}, "cascor")
        assert "nn_dataset_elements" not in payload
        _assert_restages_what_it_shows(manager, payload, "equities", "cascor")

    def test_bottom_is_still_refused(self, manager):
        # The ruling's second half: Confirm refuses ``⊥`` and posts nothing (canopy#593's guard, unchanged).
        with mock.patch("frontend.dashboard_manager.requests.post") as post:
            ok, detail = manager._restage_dataset({"dataset_type": None, **PREFILL}, nn_model="cascor")
        post.assert_not_called()
        assert ok is False and "No dataset" in detail


@pytest.mark.regression
@pytest.mark.unit
class TestThePlanShowsWhatConfirmSends:
    @pytest.mark.parametrize("dataset_type", sorted(EXPECTED_FIELDS))
    def test_every_value_a_re_stage_carries_is_in_the_plan_and_every_withheld_one_is_named(self, manager, dataset_type):
        model_key = _model_for(dataset_type)
        dataset_vals = {"dataset_type": dataset_type, **PREFILL}
        text = _text(manager._build_restart_summary(dataset_vals, {}, {"dataset": {"dataset_type": "multi_sine" if dataset_type != "multi_sine" else "ar_p"}}, model_key=model_key))
        payload = manager._restart_restage_payload(dataset_vals, nn_model=model_key)
        assert "Confirm re-stages this dataset" in text
        assert str(payload["nn_dataset_type"]) in text
        for stage_key, modal_key in _MODAL_KEY_OF.items():
            if stage_key in payload and modal_key != "dataset_type":
                assert str(payload[stage_key]) in text, f"{dataset_type}: {modal_key} is sent but not shown"
        for name in payload.get("nn_dataset_params") or {}:
            assert f"{name}=" in text, f"{dataset_type}: the seed key {name} is sent but not shown"
        assert get_model_spec(model_key).label in text, f"{dataset_type}: the model mirror is sent but not shown"
        hidden = [label for _id, key, label in RESTART_MODAL_TYPED_FIELDS if key not in EXPECTED_FIELDS[dataset_type]]
        if hidden:
            assert f"Not sent: {', '.join(hidden)}." in text, f"{dataset_type}: the plan does not name what it withholds"

    def test_an_unchanged_dataset_says_nothing_is_re_staged(self, manager):
        dataset_vals = {"dataset_type": "circles", **PREFILL}
        text = _text(manager._build_restart_summary(dataset_vals, {}, {"dataset": dict(dataset_vals)}, model_key="cascor"))
        assert "nothing is re-staged" in text and "Confirm re-stages" not in text

    def test_the_swap_s_plan_announces_the_re_stage(self, manager):
        _displayed, _baseline, summary = _open(manager, "equities_seq", "cascor")
        assert "Confirm re-stages this dataset" in _text(summary)

    def test_a_shown_value_the_filter_would_withhold_is_named(self, manager, monkeypatch):
        # No shipped declaration lets this happen: a rendered generic field is one the generator declares.
        # A future entry that declares n_samples would render Samples, and R7 holds a value equal to the
        # generator's own default. The plan must then say so rather than drop a visible value silently.
        from dataset_schema import DECLARED_PARAM_DEFAULTS

        monkeypatch.setitem(DECLARED_PARAM_DEFAULTS, "fake_gen", {"n_samples": 100})
        assert _rendered(manager, "fake_gen") == {"dataset_type", "n_samples"}
        at_default = _text(manager._build_restart_summary({"dataset_type": "fake_gen", "n_samples": 100}, {}, {}))
        assert "Shown but not sent: Samples" in at_default
        edited = _text(manager._build_restart_summary({"dataset_type": "fake_gen", "n_samples": 40}, {}, {}))
        assert "Shown but not sent" not in edited
