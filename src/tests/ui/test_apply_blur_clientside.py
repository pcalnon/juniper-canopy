"""§5.6 (Issue #2, PR-10) — apply-blur clientside JS is wired correctly.

PR-8 §2.5 C added a clientside callback that blurs the focused element
on Apply-button click so any pending debounced numeric value commits
*before* the server-side ``State()`` reads. We can't drive the full
type+click+verify flow under headless Playwright (see
``test_apply_button_flow.py`` xfail — Dash dbc.Input doesn't see
Playwright's value-set), so this test verifies the JS contract two
ways:

  1. The clientside_callback writing to ``apply-blur-sink.data`` is
     registered against ``apply-params-button.n_clicks``.
  2. The JS body actually calls ``document.activeElement.blur()`` —
     the operative line.

Pre-PR-8 the callback didn't exist, so this test would fail. Post-PR-8
both assertions hold.
"""

from __future__ import annotations

import pytest

from frontend.dashboard_manager import DashboardManager


@pytest.fixture(scope="module")
def manager() -> DashboardManager:
    return DashboardManager({})


@pytest.mark.ui
def test_apply_blur_clientside_callback_is_registered(manager: DashboardManager):
    """The clientside callback's Output is keyed by ``apply-blur-sink.data``;
    its Inputs are ``apply-params-button.n_clicks`` AND
    ``apply-dataset-button.n_clicks`` — Issue #4 extended the force-blur to the
    Apply-Dataset button so its numeric inputs commit before the State() read."""
    cb_keys = list(manager.app.callback_map.keys())
    matching = [k for k in cb_keys if "apply-blur-sink.data" in k]
    assert matching, f"expected a callback writing to apply-blur-sink.data; found keys: {cb_keys[:10]}…"
    inputs = manager.app.callback_map[matching[0]]["inputs"]
    input_ids = {f"{i['id']}.{i['property']}" for i in inputs}
    assert "apply-params-button.n_clicks" in input_ids, input_ids
    assert "apply-dataset-button.n_clicks" in input_ids, input_ids


@pytest.mark.ui
def test_apply_blur_clientside_calls_active_element_blur(manager: DashboardManager):
    """Walk every registered clientside callback JS blob and confirm one
    matches the §2.5 C contract: blur the active element on Apply click.

    Dash 3 stores clientside callback bodies on ``app._inline_scripts``
    (a private list of pre-wrapped IIFE strings); ``callback_map`` only
    holds the input/output graph, not the JS itself. The private name
    is sad but stable across recent Dash releases.
    """
    blobs = list(getattr(manager.app, "_inline_scripts", []))
    assert blobs, "Dash app exposes no clientside callback bodies; private API may have moved"

    blur_blob = next((b for b in blobs if "activeElement" in b and ".blur()" in b), None)
    assert blur_blob is not None, "no clientside callback found with the §2.5 C blur-on-Apply contract; " "expected document.activeElement.blur() in some _inline_scripts entry"
    # The Output id (``apply-blur-sink``) doesn't appear in the wrapped JS
    # body — Dash 3 stores Output ids in callback_map's graph, not in the
    # wrapper IIFE. The first test above checks the Output binding; this
    # test verifies the contract of the JS itself (must blur on click).
