"""Cheap layout-structure regression net (Option C of FRONTEND_ISSUES_PLAN §5).

Each panel's ``get_layout()`` ``repr`` is hashed and pinned to a baseline
file under ``snapshots/``. Drift fails the test, prompting an explicit
review of the layout change.

Baselines are written on the first run for any new panel and the test
``skip``s — commit the generated file under ``snapshots/`` and the next
run becomes a hard assertion.

PR-3 ships two representative panels; PR-10 will expand the parameter
list to the full set of dashboard panels.
"""

from __future__ import annotations

import pathlib

import pytest

from frontend.dashboard_manager import DashboardManager

SNAP_DIR = pathlib.Path(__file__).parent / "snapshots"
SNAP_DIR.mkdir(exist_ok=True)


@pytest.fixture(scope="module")
def dashboard_manager() -> DashboardManager:
    return DashboardManager({})


@pytest.mark.regression
@pytest.mark.parametrize(
    "panel_attr",
    [
        "metrics_panel",
        "dataset_plotter",
    ],
)
def test_panel_layout_snapshot(dashboard_manager: DashboardManager, panel_attr: str) -> None:
    panel = getattr(dashboard_manager, panel_attr)
    serialised = repr(panel.get_layout())

    baseline = SNAP_DIR / f"{panel_attr}.txt"
    if not baseline.exists():
        # Always write with a trailing newline so the pre-commit
        # ``end-of-file-fixer`` hook is a no-op on the freshly-seeded baseline.
        baseline.write_text(serialised + "\n")
        pytest.skip(f"baseline written for {panel_attr}; commit and re-run")

    # Newline-tolerant compare: the pre-commit ``end-of-file-fixer`` hook will
    # always append a trailing newline to the committed baseline file, but
    # ``repr(panel.get_layout())`` never produces one. Strip both ends so the
    # test pins layout structure, not file-trailer punctuation.
    expected = baseline.read_text().rstrip("\n")
    assert expected == serialised.rstrip("\n"), f"layout drift for {panel_attr}; review the diff and regenerate the " f"baseline at {baseline} if intentional."
