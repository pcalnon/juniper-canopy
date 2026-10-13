"""Canonical UI layout constants for juniper-canopy.

Single source of truth for layout values referenced by both the production
code and the tests, so a future spec edit is a one-place change. PR-9.5
will land the human-readable companion at ``notes/UI_STANDARDS.md`` and a
regression test that pins the markdown table to ``TAB_SIDEBAR_WIDTH``.

Values here are referenced by:
  * ``frontend.dashboard_manager`` — sets initial sidebar/visualization
    column widths and drives the per-tab resize callback.
  * ``tests/regression/test_tab_sidebar_widths.py`` — sum-to-12 check +
    no-raw-widths grep against ``dashboard_manager.py``.
  * (PR-9.5) ``tests/ui/test_sidebar_width.py`` — Playwright width verify.
  * (PR-9.5) ``notes/UI_STANDARDS.md`` — human-readable spec.

Do not introduce raw numeric widths in ``dashboard_manager.py`` — import
from here so the regression test stays meaningful.

FRONTEND_ISSUES_PLAN_2026-05-09 §6.4 + §6.4.1 / Issue #6.
"""

from __future__ import annotations

from typing import Dict, Final

# Bootstrap 12-column grid; sidebar + visualization widths must sum to this.
GRID_COLUMNS: Final[int] = 12

# The two width classes we ship in PR-9. PR-9.5's Training-Metrics narrowing
# experiment may add intermediate sizes once the empirical break-point is known.
WIDE_SIDEBAR: Final[int] = 3
NARROW_SIDEBAR: Final[int] = 2

# Per-tab sidebar widths. Tabs not listed default to ``WIDE_SIDEBAR`` at the
# call site so the dashboard always renders something sensible even if a new
# tab is added before its entry lands here.
TAB_SIDEBAR_WIDTH: Final[Dict[str, int]] = {
    # Wide — need Training Controls + Network Parameters (+ Network Info).
    "metrics": WIDE_SIDEBAR,
    "candidates": WIDE_SIDEBAR,
    "network-editor": WIDE_SIDEBAR,
    "topology": WIDE_SIDEBAR,
    "dataset": WIDE_SIDEBAR,
    # Narrow — Network Info only (or no params); reclaim viewport for viz.
    "boundaries": NARROW_SIDEBAR,
    "evolution": NARROW_SIDEBAR,
    "parameters": NARROW_SIDEBAR,
    "snapshots": NARROW_SIDEBAR,
    "replay": NARROW_SIDEBAR,
    "workers": NARROW_SIDEBAR,
    # Minimal — mostly static / log content.
    "about": NARROW_SIDEBAR,
    "tutorial": NARROW_SIDEBAR,
    "redis": NARROW_SIDEBAR,
    "cassandra": NARROW_SIDEBAR,
}


def visualization_width_for(tab: str) -> int:
    """Return the right-column width that complements ``TAB_SIDEBAR_WIDTH[tab]``.

    Defaults to the wide-sidebar pairing for unknown tabs so a new tab still
    renders correctly until its entry is added.
    """
    sidebar = TAB_SIDEBAR_WIDTH.get(tab, WIDE_SIDEBAR)
    return GRID_COLUMNS - sidebar
