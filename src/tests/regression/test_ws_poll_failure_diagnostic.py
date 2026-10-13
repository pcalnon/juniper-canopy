"""
Pin that the WS-silent poll suite's failure messages stay diagnostic — canopy#637.

`test_ws_silent_poll_liveness.py`'s assertions rendered every drained payload as
`type(p).__name__`, and `drain()` produces a `str` from two places that mean OPPOSITE
things:

* ``"<no_update>"`` — the callback WAS dispatched and deliberately wrote nothing. A real
  starvation signal.
* ``"<body-unavailable:…>"`` — the collector could not read the response body. An artefact
  of the test's own plumbing, which says nothing about the poll.

Both rendered as ``'str'``, so a CI failure could not be root-caused and the only move was
a re-run. It happened three times in one day — canopy#636 (a two-line CHANGELOG deletion),
canopy#651 (a status-bar string change), canopy#653 (an availability-state change) — none
of which can plausibly starve a metrics poll, and none of which taught anything.

**This test lives in `regression/`, not `ui/`, deliberately.** The UI lane needs Playwright
and a live app, and the default addopts carry ``--ignore=src/tests/ui``; the helper itself
is pure. Putting the guard here means it runs on every PR rather than only where the
flake appears.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
SRC = REPO / "src"
if str(SRC) not in sys.path:  # pragma: no cover - import side effect
    sys.path.insert(0, str(SRC))

from tests.ui.test_ws_silent_poll_liveness import _render_payload  # noqa: E402

NO_UPDATE = "<no_update>"
BODY_UNAVAILABLE = "<body-unavailable:JSONDecodeError>"


@pytest.mark.regression
@pytest.mark.unit
class TestTheTwoStrSentinelsStayDistinguishable:
    """The whole point of canopy#637: these two must never render the same."""

    def test_the_two_sentinels_render_differently(self):
        assert _render_payload(NO_UPDATE) != _render_payload(BODY_UNAVAILABLE)

    def test_each_sentinel_renders_as_itself(self):
        """Not a type name, not a truncation — the sentinel text IS the diagnosis."""
        assert _render_payload(NO_UPDATE) == NO_UPDATE
        assert _render_payload(BODY_UNAVAILABLE) == BODY_UNAVAILABLE

    def test_neither_sentinel_renders_as_the_bare_type(self):
        """The regression this file exists for."""
        assert _render_payload(NO_UPDATE) != "str"
        assert _render_payload(BODY_UNAVAILABLE) != "str"


@pytest.mark.regression
@pytest.mark.unit
class TestAListCarriesItsLength:
    """The assertions require a NON-EMPTY list, so `list[0]` and `list[3]` differ."""

    def test_an_empty_list_is_distinguishable_from_a_full_one(self):
        assert _render_payload([]) != _render_payload([{"epoch": 1}])

    def test_the_length_is_reported(self):
        assert _render_payload([{"epoch": 1}, {"epoch": 2}]) == "list[2]"
        assert _render_payload([]) == "list[0]"


@pytest.mark.regression
@pytest.mark.unit
class TestEveryAssertionSiteUsesTheHelper:
    """The idiom existed at ONE of five sites before canopy#637 — that is the defect class.

    A helper nothing calls is the same as no helper, and this module's history is precisely
    a correct rendering applied to one member of a five-member set.
    """

    SUITE = Path(__file__).resolve().parents[1] / "ui" / "test_ws_silent_poll_liveness.py"

    def _code_lines(self) -> list[str]:
        """Source lines with docstring prose excluded, crudely but adequately.

        The helper's own docstring quotes the old idiom, so a naive grep over the whole
        file would match the explanation of the defect and report it as the defect.
        """
        lines = self.SUITE.read_text(encoding="utf-8").splitlines()
        return [ln for ln in lines if not ln.lstrip().startswith(("*", "#")) and "``" not in ln]

    def test_no_assertion_still_renders_a_bare_type_name(self):
        offenders = [ln.strip() for ln in self._code_lines() if "type(p).__name__" in ln]
        assert not offenders, "these sites bypass _render_payload and will print 'str' for both sentinels again: " + "; ".join(offenders)

    def test_the_helper_is_actually_used(self):
        """Guard the instrument: if the helper were unreferenced, the test above passes vacuously."""
        uses = [ln for ln in self._code_lines() if "_render_payload(" in ln and "def _render_payload" not in ln]
        assert len(uses) >= 5, f"expected the helper at all five assertion sites, found {len(uses)}"
