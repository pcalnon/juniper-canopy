"""§6.6 (Issue #6, PR-9.5) — markdown table in UI_STANDARDS.md matches code.

Parses the "Sidebar widths per tab class" table in
``notes/UI_STANDARDS.md`` and asserts every (class, width, tabs) row
agrees with ``frontend.ui_standards.TAB_SIDEBAR_WIDTH``. Catches the
common drift mode where a developer updates the constants but forgets
to update the human-readable doc.

If this test fails, fix one of three things in a single PR:

  1. The constants module (``src/frontend/ui_standards.py``).
  2. The markdown table (``notes/UI_STANDARDS.md``).
  3. This test (if the table format changed deliberately).

Don't update one without the others.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

import pytest

from frontend import ui_standards

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DOC_PATH = _REPO_ROOT / "notes" / "UI_STANDARDS.md"


def _parse_sidebar_widths_table(text: str) -> dict[int, set[str]]:
    """Extract ``{width: {tabs}}`` from the markdown table.

    Looks for the "Sidebar widths per tab class" section heading, then
    scans table rows of the form ``| class | width | tabs, list |``
    until a non-table line interrupts the block.
    """
    section_idx = text.find("## Sidebar widths per tab class")
    assert section_idx != -1, "section heading 'Sidebar widths per tab class' not found in UI_STANDARDS.md"
    table_text = text[section_idx:]
    by_width: dict[int, set[str]] = defaultdict(set)
    # | class | width | tabs |  — three pipes plus content. Skip header
    # row (alphabetic width) and divider row (only -/: chars).
    row_re = re.compile(r"^\|\s*([a-z]+)\s*\|\s*(\d+)\s*\|\s*(.+?)\s*\|\s*$", re.M)
    for match in row_re.finditer(table_text):
        _cls, width_str, tabs_str = match.groups()
        width = int(width_str)
        for tab in tabs_str.split(","):
            by_width[width].add(tab.strip())
    assert by_width, "no width rows parsed from the markdown table — check the table syntax"
    return dict(by_width)


@pytest.mark.regression
def test_ui_standards_doc_table_matches_constants():
    """Doc table and ``TAB_SIDEBAR_WIDTH`` agree on every (tab, width) entry."""
    doc_table = _parse_sidebar_widths_table(_DOC_PATH.read_text())

    # Build the same {width: {tabs}} shape from the code's authoritative dict.
    code_by_width: dict[int, set[str]] = defaultdict(set)
    for tab, width in ui_standards.TAB_SIDEBAR_WIDTH.items():
        code_by_width[width].add(tab)

    # Symmetric-difference per width. Reporting both directions catches
    # "new tab in code but missing from doc" and "stale tab in doc".
    diffs: list[str] = []
    all_widths = set(doc_table) | set(code_by_width)
    for width in sorted(all_widths):
        doc_tabs = doc_table.get(width, set())
        code_tabs = code_by_width.get(width, set())
        only_doc = doc_tabs - code_tabs
        only_code = code_tabs - doc_tabs
        if only_doc:
            diffs.append(f"width={width}: only in doc: {sorted(only_doc)}")
        if only_code:
            diffs.append(f"width={width}: only in code: {sorted(only_code)}")

    assert not diffs, "UI_STANDARDS.md and ui_standards.TAB_SIDEBAR_WIDTH disagree:\n  " + "\n  ".join(diffs) + "\n\nFix: update notes/UI_STANDARDS.md, src/frontend/ui_standards.py, or both — in the same PR."


@pytest.mark.regression
def test_ui_standards_doc_references_source_of_truth():
    """The doc must point at the constants module so readers know where the
    authoritative values live."""
    text = _DOC_PATH.read_text()
    assert "src/frontend/ui_standards.py" in text, "UI_STANDARDS.md must reference src/frontend/ui_standards.py as the source of truth"
