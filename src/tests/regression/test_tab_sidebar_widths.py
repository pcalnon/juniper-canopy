"""§6.6 (Issue #6) — pin the per-tab sidebar-width contract.

Two assertions:

  1. Every entry in ``TAB_SIDEBAR_WIDTH`` plus its complement sums to
     ``GRID_COLUMNS`` (12). If a future edit to the constants module
     forgets to keep the sum invariant, the dashboard renders broken.

  2. ``dashboard_manager.py`` does not contain raw ``width=2`` /
     ``width=3`` literals on a ``dbc.Col`` — the only sidebar/visualisation
     widths must flow through ``frontend.ui_standards`` so a single edit
     there is the only thing needed to retune the layout.

The companion Playwright test that verifies the rendered DOM widths
matches ``TAB_SIDEBAR_WIDTH`` lands in PR-9.5 alongside the human-readable
``notes/UI_STANDARDS.md``.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from frontend import ui_standards

_DASHBOARD_PATH = Path(__file__).resolve().parents[2] / "frontend" / "dashboard_manager.py"


@pytest.mark.regression
def test_every_tab_width_sums_to_grid_columns():
    """Sidebar + visualization width must always sum to GRID_COLUMNS."""
    grid = ui_standards.GRID_COLUMNS
    bad: list[str] = []
    for tab, sidebar in ui_standards.TAB_SIDEBAR_WIDTH.items():
        viz = ui_standards.visualization_width_for(tab)
        if sidebar + viz != grid:
            bad.append(f"  {tab!r}: sidebar={sidebar} + viz={viz} = {sidebar + viz} (want {grid})")
    assert not bad, "TAB_SIDEBAR_WIDTH entries violate the sum-to-GRID_COLUMNS invariant:\n" + "\n".join(bad)


@pytest.mark.regression
def test_visualization_width_for_unknown_tab_defaults_to_wide_complement():
    """Unknown tabs default to WIDE_SIDEBAR — the complement must match."""
    expected = ui_standards.GRID_COLUMNS - ui_standards.WIDE_SIDEBAR
    assert ui_standards.visualization_width_for("never-heard-of-it") == expected


@pytest.mark.regression
def test_dashboard_manager_uses_ui_standards_for_col_widths():
    """No raw ``width=2`` or ``width=3`` literals on ``dbc.Col(...)`` widgets.

    The two ``dbc.Col`` widgets in the layout (sidebar + visualization) plus
    every callback Output(width) must source their numeric width from
    ``frontend.ui_standards`` so retuning is a one-place change.

    We allow ``width=N`` in non-``dbc.Col`` contexts (e.g. dropdown ``style``
    dicts) by anchoring the regex to a ``dbc.Col(...)`` window.
    """
    text = _DASHBOARD_PATH.read_text()
    # Find each dbc.Col(...) call and check its body for raw width=2|3 ints.
    offenders: list[str] = []
    pattern = re.compile(r"dbc\.Col\((.*?)\)\s*,?\s*\n", re.S)
    for match in pattern.finditer(text):
        body = match.group(1)
        # Only ``width=`` integer literals in [2, 3] — leave width=12 (full
        # row) and other Bootstrap utility values alone.
        for raw in re.finditer(r"\bwidth\s*=\s*([23])\b(?!\s*\.)", body):
            line_no = text.count("\n", 0, match.start() + raw.start()) + 1
            offenders.append(f"dashboard_manager.py:{line_no}: raw width={raw.group(1)} on dbc.Col — import from frontend.ui_standards instead")

    assert not offenders, "Raw sidebar-class numeric widths found on dbc.Col widgets:\n  " + "\n  ".join(offenders)
