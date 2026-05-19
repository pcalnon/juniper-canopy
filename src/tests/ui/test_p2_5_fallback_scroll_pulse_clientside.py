"""P2-5 follow-ups A+B (Issue #3) — fallback-button clientside JS contract.

When the user dismisses the Live Switch modal via "Return to Stop &
Restart" (``live-switch-fallback-button``), a clientside callback
should:

  * **A** — smooth-scroll the Apply Dataset button into view.
  * **B** — briefly pulse it via the ``attention-pulse`` class.

Mirrors the pattern in ``test_apply_blur_clientside.py``: we can't
drive the full DOM interaction under headless tests, so we verify the
JS contract two ways:

  1. The clientside_callback is registered with
     ``live-switch-fallback-sink.data`` as Output, keyed by
     ``live-switch-fallback-button.n_clicks``.
  2. The JS body actually contains the operative DOM mutations —
     ``scrollIntoView`` (A) and ``attention-pulse`` (B).

The CSS rule itself is asserted to exist so the className isn't a
dangling reference.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from frontend.dashboard_manager import DashboardManager


@pytest.fixture(scope="module")
def manager() -> DashboardManager:
    return DashboardManager({})


@pytest.mark.ui
def test_fallback_pulse_clientside_callback_is_registered(manager: DashboardManager):
    """The callback's Output is ``live-switch-fallback-sink.data``; its
    sole Input is ``live-switch-fallback-button.n_clicks``."""
    cb_keys = list(manager.app.callback_map.keys())
    matching = [k for k in cb_keys if "live-switch-fallback-sink.data" in k]
    assert matching, f"expected a callback writing to live-switch-fallback-sink.data; found keys: {cb_keys[:10]}…"


@pytest.mark.ui
def test_fallback_pulse_clientside_scrolls_apply_dataset_button(manager: DashboardManager):
    """Walk registered clientside callbacks and confirm one matches the
    P2-5 follow-up A contract: scrollIntoView on Apply Dataset."""
    blobs = list(getattr(manager.app, "_inline_scripts", []))
    assert blobs, "Dash app exposes no clientside callback bodies"

    scroll_blob = next((b for b in blobs if "apply-dataset-button" in b and "scrollIntoView" in b), None)
    assert scroll_blob is not None, "no clientside callback found with the P2-5 follow-up A contract; " "expected document.getElementById('apply-dataset-button') + .scrollIntoView() in some _inline_scripts entry"


@pytest.mark.ui
def test_fallback_pulse_clientside_applies_attention_pulse_class(manager: DashboardManager):
    """P2-5 follow-up B contract: the same callback adds the
    ``attention-pulse`` className to the Apply Dataset button so the
    CSS keyframes animation fires."""
    blobs = list(getattr(manager.app, "_inline_scripts", []))
    pulse_blob = next((b for b in blobs if "apply-dataset-button" in b and "attention-pulse" in b), None)
    assert pulse_blob is not None, "no clientside callback found with the P2-5 follow-up B contract; " "expected classList.add('attention-pulse') against apply-dataset-button"


@pytest.mark.ui
def test_attention_pulse_css_class_is_defined():
    """The ``attention-pulse`` className referenced by the clientside
    callback must resolve to a CSS rule, otherwise adding the class
    has no visible effect."""
    css_path = Path(__file__).resolve().parents[2] / "frontend" / "assets" / "controls.css"
    assert css_path.exists(), f"controls.css not found at {css_path}"
    css = css_path.read_text(encoding="utf-8")
    assert ".attention-pulse" in css, "expected .attention-pulse class definition in controls.css"
    # The class must reference the existing pulse keyframes (otherwise
    # nothing visibly happens when the class is added).
    assert "animation:" in css and "pulse" in css, "expected .attention-pulse to apply the 'pulse' keyframes animation"


@pytest.mark.ui
def test_fallback_pulse_callback_removes_class_for_re_trigger(manager: DashboardManager):
    """The callback must reset the className before adding it so a
    rapid second click within the animation window re-triggers cleanly
    rather than appearing to "stick" because the class is already
    present from the first click."""
    blobs = list(getattr(manager.app, "_inline_scripts", []))
    retrigger_blob = next((b for b in blobs if "attention-pulse" in b and "classList.remove" in b), None)
    assert retrigger_blob is not None, "expected classList.remove('attention-pulse') in the callback so re-clicks retrigger the animation"
