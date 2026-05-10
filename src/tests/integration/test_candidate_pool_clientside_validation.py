"""§1.5 C2.2 (Issue #1) — clientside JS validator string is registered.

The clientside callback runs in the user's browser; we don't need a real
Playwright session to verify its truth-table fidelity (the truth table is
already pinned by cascor's test_param_validation_helper.py + 17 cases).
What we DO need is to confirm:

  1. The callback was actually registered (the string lives on
     ``app.config['external_scripts']`` or in the index, but pragmatically
     dash exposes registered callbacks via ``app.callback_map`` — for
     clientside callbacks the ``clientside_function`` field is populated).
  2. The truth-table cases that match cascor's invariant are present in
     the JS source — guards against accidental drift if either side is
     edited without the other.
"""

from __future__ import annotations

import pytest

from frontend.dashboard_manager import DashboardManager


@pytest.fixture(scope="module")
def manager() -> DashboardManager:
    return DashboardManager({})


@pytest.mark.unit
def test_clientside_callback_registered_for_pool_triple(manager: DashboardManager):
    """The callback is keyed by the (joined) Output ids; dash stores it on
    ``app.callback_map``. We look for the cn-pool-triple-feedback Output
    which is unique to this validator."""
    cb_keys = list(manager.app.callback_map.keys())
    matching = [k for k in cb_keys if "cn-pool-triple-feedback.children" in k]
    assert matching, "expected a clientside callback writing to cn-pool-triple-feedback.children, " f"found callback keys: {cb_keys[:10]}…"


@pytest.mark.unit
def test_clientside_validator_includes_full_truth_table(manager: DashboardManager):
    """Walks every clientside callback registered on the app and looks for
    the one whose JS body covers the §1.5 C2.1 truth table. Failure here
    means either the callback was renamed or someone trimmed the cases —
    either way, server and client would drift."""
    # Dash stores clientside JS strings in app.clientside_callback_map (Dash 2+)
    # OR inside the registered callback's ``clientside_function`` attribute.
    js_blobs: list[str] = []
    for entry in manager.app.callback_map.values():
        cs = entry.get("clientside_function") if isinstance(entry, dict) else getattr(entry, "clientside_function", None)
        if cs is not None:
            js_blobs.append(str(cs))
    # Fallback: dash also tracks raw strings on the inline cs registry.
    inline = getattr(manager.app, "_inline_scripts", None)
    if inline:
        js_blobs.extend(str(b) for b in inline)

    triple_blob = next((b for b in js_blobs if "cn-pool-triple-feedback" in b or "candidate_pool_size=" in b or "selected_candidates" in b and "top_candidates" in b and "random_candidates" in b), None)
    assert triple_blob is not None, "could not locate the candidate-pool clientside validator JS — search the dashboard_manager registration"

    # Truth-table fragments — each maps 1:1 to a case in
    # cascor's _validate_candidate_pool_triple.
    expected_fragments = [
        "selected_candidates",  # Case 1 (S out of [1, P])
        "must be >= 0",  # Case 2 (T or R negative)
        "each component",  # Case 3 (T > S or R > S)
        "cannot both be 0",  # Case 6 (T == 0 == R with S > 0)
        "with top_candidates=0",  # Case 4a (T == 0, R != S)
        "with random_candidates=0",  # Case 4b (R == 0, T != S)
        "must equal S=",  # Case 5 (T+R != S when both nonzero)
    ]
    missing = [f for f in expected_fragments if f not in triple_blob]
    assert not missing, f"clientside validator JS is missing cases from the §1.5 C2.1 truth table: {missing}"
