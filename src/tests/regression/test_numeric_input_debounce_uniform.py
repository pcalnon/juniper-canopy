"""§2.5 B (Issue #2) — pin the convention: no boolean ``debounce=`` on
numeric ``dbc.Input``s.

Pre-PR-8, every numeric input used ``debounce=True`` which only commits
on blur/Enter — producing the "type into a numeric input, click Apply
with the mouse without leaving the field, get the OLD value POSTed"
race. PR-8 swept the codebase to ``debounce=NUMERIC_INPUT_DEBOUNCE_MS``
(integer ms — commits ~350 ms after the last keystroke without
requiring blur). This test forecloses regressions: any new numeric
input that uses the boolean form will fail loudly.
"""

import re
from pathlib import Path

import pytest

_FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"

# Match dbc.Input(...) blocks containing ``debounce=True`` or ``debounce=False``.
# DOTALL so multi-line component definitions are caught; non-greedy so we don't
# bleed into the next sibling component.
_BOOLEAN_DEBOUNCE_RE = re.compile(r"dbc\.Input\([^)]*?debounce\s*=\s*(True|False)", re.S)


@pytest.mark.regression
def test_no_boolean_debounce_on_numeric_inputs():
    offenders: list[str] = []
    for path in _FRONTEND_DIR.rglob("*.py"):
        text = path.read_text()
        for match in _BOOLEAN_DEBOUNCE_RE.finditer(text):
            line_no = text.count("\n", 0, match.start()) + 1
            snippet = match.group(0).replace("\n", " ")[:80]
            offenders.append(f"{path.relative_to(_FRONTEND_DIR.parent)}:{line_no}: {snippet}")

    assert not offenders, "Numeric ``dbc.Input`` widgets must use ``debounce=DashboardConstants.NUMERIC_INPUT_DEBOUNCE_MS`` " "(integer ms), not the boolean form. Boolean ``debounce=True`` only commits on blur/Enter — see " "FRONTEND_ISSUES_PLAN_2026-05-09 §2.5 B / Issue #2 for the bug class. Offenders:\n  " + "\n  ".join(offenders)
