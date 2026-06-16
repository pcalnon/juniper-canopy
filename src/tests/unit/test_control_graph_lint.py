"""Harness L1 — control-graph lint gate (the "dead button" regression net).

Fails CI when any actionable control becomes unreachable by every callback
(the regression class that shipped ``restart-with-new-dataset-button``,
``nn-init-output-weights-dropdown`` and ``dataset-plotter-dataset-selector``).

Known, intentionally-deferred orphans live in ``KNOWN_ORPHANS`` with a reason +
tracking ref. The anti-rot test forces an entry to be removed once its control is
wired, so the baseline can only shrink.

See ``util/ui_control_graph.py`` and the juniper-ml audit doc
``JUNIPER_CANOPY_AUDIT_REGRESSIONS_AND_MODEL_SELECTION_2026-06-15.md``.
"""

from __future__ import annotations

import os
import sys

import pytest

_UTIL = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "util"))
if _UTIL not in sys.path:
    sys.path.insert(0, _UTIL)

from ui_control_graph import build_app, id_key, lint  # noqa: E402

# id -> reason + tracking ref. This baseline may only SHRINK.
KNOWN_ORPHANS: dict[str, str] = {
    "restart-with-new-dataset-button": ("Cold-swap 'Stop & Restart with new dataset' button has no callback " "(dashboard_manager.py:1409). Fix stacked in PR fix/orphan-dataset-restart-button."),
    "nn-init-output-weights-dropdown": ("NN 'Init Output Weights' selector reaches no callback (dashboard_manager.py:880); " "wiring needs backend set_params + demo mirror. Deferred to its own PR."),
    "dataset-plotter-dataset-selector": ("Dataset-Visualization dataset picker: options are populated by populate_dataset_selector " "(frontend/components/dataset_plotter.py:386), but the selected value reaches no callback Input/State. Incomplete feature; deferred to its own PR."),
}


@pytest.fixture(scope="module")
def dash_app():
    return build_app()


def _current_orphan_ids(app) -> set[str]:
    return {str(id_key(v.id)) for v in lint(app)}


@pytest.mark.unit
def test_no_new_orphan_controls(dash_app):
    """No actionable control may be unreachable by every callback (dead-button gate)."""
    current = _current_orphan_ids(dash_app)
    new = current - set(KNOWN_ORPHANS)
    assert not new, "New orphan control(s) — actionable but unreachable by any callback:\n  " + "\n  ".join(sorted(new)) + "\n\nWire a callback Input (buttons/uploads) or Input/State (value controls) for each. " "Only if a control is intentionally deferred, add it to KNOWN_ORPHANS with a reason + tracking ref."


@pytest.mark.unit
def test_known_orphans_not_stale(dash_app):
    """KNOWN_ORPHANS must not list controls that are already wired (forces trimming)."""
    current = _current_orphan_ids(dash_app)
    stale = set(KNOWN_ORPHANS) - current
    assert not stale, "KNOWN_ORPHANS lists control(s) that are no longer orphaned — remove them:\n  " + "\n  ".join(sorted(stale))
