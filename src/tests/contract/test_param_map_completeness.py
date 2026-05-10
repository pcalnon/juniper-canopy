"""§1.6 (Issue #1) — every Apply-button input has a backend mapping.

Walks the Apply-button callback declaration in dashboard_manager.py and
confirms each ``State("nn-…-input"|"cn-…-input"|"-dropdown"|"-radio"|
"-checkbox", "value")`` has a corresponding ``nn_*``/``cn_*`` key that is
either:

  - in ``CascorServiceAdapter._CANOPY_TO_CASCOR_PARAM_MAP`` (will be sent
    to cascor on Apply), **or**
  - in ``CascorServiceAdapter._CANOPY_LOCAL_PARAMS`` (intentionally
    canopy-only — drives demo dataset generation, UI behaviour, etc.).

Any new Apply-button input that doesn't appear in either set will fail
this test, forcing the author to either add a cascor mapping or document
the canopy-local intent in ``_CANOPY_LOCAL_PARAMS``. This is the contract
that Issue #1's silent-drop bug violated.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from backend.cascor_service_adapter import CascorServiceAdapter

_DASHBOARD = Path(__file__).resolve().parents[3] / "src" / "frontend" / "dashboard_manager.py"

# Match ``State("nn-…-input"|"-dropdown"|"-radio"|"-checkbox", "value")`` —
# captures the full element id; the widget-type suffix is stripped in Python.
# Anchored on "value" so non-State references and Output()-only ids don't leak in.
_ID_TO_PARAM_RE = re.compile(r'State\("((?:nn|cn)-[a-z0-9-]+?-(?:input|dropdown|radio|checkbox))", "value"\)')

_WIDGET_SUFFIXES = ("-input", "-dropdown", "-radio", "-checkbox")

# Apply-handler-internal renames between the input element id and the param
# key actually placed in the POST payload. Historical naming-debt — every
# entry should ideally be retired by renaming the underlying element id.
# Adding to this map is allowed but should come with a comment justifying
# why the rename can't (or shouldn't) be done now.
_ID_KEY_RENAMES = {
    # ``nn-activation-function-dropdown`` (id) → ``nn_activation_function_name``
    # (payload). Cascor's TrainingParamUpdateRequest expects the ``_name``
    # suffix, but the dropdown id was set without it. Renaming the id touches
    # ~half a dozen callbacks/tests; deferred.
    "nn_activation_function": "nn_activation_function_name",
}


def _enumerate_apply_button_inputs() -> list[str]:
    """Parse the Apply-button callback's State() list out of the dashboard.

    The dashboard registers two callbacks against ``apply-params-button``: a
    tiny clientside in-flight clamp (no State) and the main params-handler
    callback (28+ States). We want the latter — the one with the actual
    State() list — and the simplest tell is to scan **all** occurrences and
    return the union of ids found in the next ~6KB after each.
    """
    text = _DASHBOARD.read_text()
    needle = 'Input("apply-params-button", "n_clicks"),'
    found: list[str] = []
    start = 0
    while True:
        idx = text.find(needle, start)
        if idx == -1:
            break
        window = text[idx : idx + 6000]
        found.extend(_ID_TO_PARAM_RE.findall(window))
        start = idx + len(needle)
    assert found, "no State()s found near any apply-params-button callback — dashboard structure changed; update the test"
    return found


def _id_to_param_key(element_id: str) -> str:
    """``nn-learning-rate-input`` → ``nn_learning_rate``.

    Strips the widget-type suffix, folds remaining hyphens to underscores,
    then applies ``_ID_KEY_RENAMES`` for the historical naming-debt cases.
    """
    base = element_id
    for suffix in _WIDGET_SUFFIXES:
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    raw = base.replace("-", "_")
    return _ID_KEY_RENAMES.get(raw, raw)


@pytest.mark.unit
def test_every_apply_button_input_has_map_entry_or_is_local():
    """Hard contract: a new Apply-button param MUST be classified as either
    backend-mapped or canopy-local. Silent-drop is the bug, not the policy."""
    cascor_keys = set(CascorServiceAdapter._CANOPY_TO_CASCOR_PARAM_MAP.keys())
    local_keys = set(CascorServiceAdapter._CANOPY_LOCAL_PARAMS)
    classified = cascor_keys | local_keys

    inputs = _enumerate_apply_button_inputs()
    assert inputs, "regex matched no inputs — dashboard structure changed; update the test"

    unclassified = []
    for element_id in inputs:
        key = _id_to_param_key(element_id)
        if key not in classified:
            unclassified.append((element_id, key))

    assert not unclassified, "Apply-button inputs missing from both _CANOPY_TO_CASCOR_PARAM_MAP and _CANOPY_LOCAL_PARAMS:\n" + "\n".join(f"  {eid:40s} → {key}" for eid, key in unclassified) + "\n\nFix: add the mapping to _CANOPY_TO_CASCOR_PARAM_MAP (if cascor accepts it)\n     or add the key to _CANOPY_LOCAL_PARAMS (if it's intentionally local)."


@pytest.mark.unit
def test_canopy_local_keys_are_disjoint_from_cascor_map():
    """A key can be one or the other, never both — catches accidental dual-classification."""
    cascor_keys = set(CascorServiceAdapter._CANOPY_TO_CASCOR_PARAM_MAP.keys())
    local_keys = set(CascorServiceAdapter._CANOPY_LOCAL_PARAMS)
    overlap = cascor_keys & local_keys
    assert not overlap, f"keys present in both _CANOPY_TO_CASCOR_PARAM_MAP and _CANOPY_LOCAL_PARAMS: {overlap}"


@pytest.mark.unit
def test_candidate_pool_quintet_is_mapped():
    """The 5 keys whose absence prompted PR-5 are present in the adapter map."""
    expected = {
        "cn_multi_candidate",
        "cn_candidate_selection",
        "cn_selected_candidates",
        "cn_top_candidates",
        "cn_random_candidates",
    }
    assert expected <= set(CascorServiceAdapter._CANOPY_TO_CASCOR_PARAM_MAP.keys())
