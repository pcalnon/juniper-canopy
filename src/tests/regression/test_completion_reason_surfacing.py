"""
Pin that a run's completion reason reaches the operator, for BOTH producers and BOTH outcomes.

`completion_reason` is written by two backends with disjoint meanings, and canopy implemented
only one reading of it:

* **cascor** writes a ``grow_network`` completion OUTCOME (one of five tokens).
* **recurrence** writes ``TrainResult.stopped_reason`` on success — ``max_epochs`` /
  ``early_stopping`` / ``converged`` from juniper-recurrence-model — and on failure writes the
  **raw adapter error string** into the same field (``recurrence_backend.py:274``).

Two independent losses followed, and they are not the same defect:

1. **The failed run's reason was never read.** The only consumer was gated on
   ``status == "Completed"``; there was no ``Failed`` branch anywhere in the file. The mapper
   was not even reached. The operator saw a bare "Failed".
2. **The successful recurrence run's reason was dropped by the mapper**, whose table held only
   cascor's five tokens and returns ``None`` for anything else.

The distinction matters because fixing (2) alone — the obvious reading, and the one the
handoff originally recorded — leaves (1) untouched, which is the case that loses the most.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

REPO = Path(__file__).resolve().parents[3]
SRC = REPO / "src"
if str(SRC) not in sys.path:  # pragma: no cover - import side effect
    sys.path.insert(0, str(SRC))

from frontend.dashboard_manager import DashboardManager  # noqa: E402

# The vocabulary juniper-recurrence-model actually emits. Kept as a literal rather than an
# import: canopy does not depend on that package, and the point of the test is that canopy's
# table matches what the wire carries.
RECURRENCE_STOP_REASONS = ("max_epochs", "early_stopping", "converged")

CASCOR_STOP_REASONS = ("residual_collapsed", "below_threshold", "no_candidate", "early_stopped", "max_iterations")


@pytest.mark.regression
@pytest.mark.unit
class TestBothVocabulariesRender:
    """One table, two producers, no collisions."""

    @pytest.mark.parametrize("reason", RECURRENCE_STOP_REASONS)
    def test_every_recurrence_stop_reason_has_a_label(self, reason):
        label = DashboardManager._completion_reason_label(reason)
        assert label, f"recurrence emits stopped_reason={reason!r} and canopy renders nothing for it"

    @pytest.mark.parametrize("reason", CASCOR_STOP_REASONS)
    def test_every_cascor_reason_still_has_a_label(self, reason):
        """The recurrence rows must not have displaced cascor's."""
        assert DashboardManager._completion_reason_label(reason), f"cascor reason {reason!r} lost its label"

    def test_the_two_vocabularies_do_not_collide(self):
        """If a token ever appeared in both, one producer's meaning would silently win."""
        overlap = set(RECURRENCE_STOP_REASONS) & set(CASCOR_STOP_REASONS)
        assert not overlap, f"{sorted(overlap)} is emitted by both producers with possibly different meanings; a single table can no longer serve both"

    def test_the_near_misses_are_distinct_tokens(self):
        """cascor `early_stopped` vs recurrence `early_stopping` — same meaning, different wire token.

        This is why the implementation is a table and not a normaliser: a normaliser that
        stemmed these together would also fold `max_iterations` into `max_epochs`, which are
        different quantities (cascade iterations vs readout epochs).
        """
        assert DashboardManager._completion_reason_label("early_stopped") == DashboardManager._completion_reason_label("early_stopping")
        assert DashboardManager._completion_reason_label("max_iterations") != DashboardManager._completion_reason_label("max_epochs")

    def test_an_unknown_reason_still_degrades_to_no_suffix(self):
        """A future fourth stop reason must render nothing, not crash or print a raw token."""
        assert DashboardManager._completion_reason_label("some_future_reason") is None
        assert DashboardManager._completion_reason_label(None) is None


@pytest.mark.regression
@pytest.mark.unit
class TestAFailureReasonSurvives:
    """The failed path is free text, and was never read at all."""

    def test_a_plain_error_is_rendered(self):
        label = DashboardManager._failure_reason_label("LMU service unreachable at http://localhost:8300")
        assert label == "LMU service unreachable at http://localhost:8300"

    def test_a_long_error_is_bounded(self):
        """A status bar cannot carry a traceback."""
        label = DashboardManager._failure_reason_label("x" * 500)
        assert len(label) <= DashboardManager._COMPLETION_REASON_MAX_CHARS
        assert label.endswith("…"), "a truncated reason must show that it was truncated"

    def test_newlines_are_flattened(self):
        """A multi-line exception must not break the status line."""
        assert DashboardManager._failure_reason_label("line one\n  line two\n\nline three") == "line one line two line three"

    def test_empty_and_non_string_reasons_render_nothing(self):
        for value in ("", "   ", None, 42, {"error": "x"}):
            assert DashboardManager._failure_reason_label(value) is None, f"{value!r} should produce no suffix"

    def test_the_failure_path_does_not_use_the_vocabulary_table(self):
        """Routing free text through the mapper returns None for every real error.

        This is the fix that looks right and reinstates the defect, so it is pinned: a real
        adapter error is not a vocabulary token, and the mapper must not be the thing that
        judges it.
        """
        real_error = "HTTPConnectionPool(host='localhost', port=8300): Max retries exceeded"
        assert DashboardManager._completion_reason_label(real_error) is None
        assert DashboardManager._failure_reason_label(real_error) is not None


def _status_bar_status(**status_fields):
    """Drive the real status-bar builder and return the status string it renders.

    Element 3 of the returned tuple is the status string (the shape
    ``tests/unit/test_phase0_fixes.py`` already relies on).
    """
    response = Mock()
    response.json.return_value = {"is_running": False, "is_paused": False, "phase": "output", "current_epoch": 1, "hidden_units": 0, **status_fields}
    return DashboardManager({})._build_unified_status_bar_content(response, latency_ms=50)[3]


@pytest.mark.regression
@pytest.mark.unit
class TestTheStatusBarActuallyWiresBothBranches:
    """The helpers above are useless if nothing calls them.

    Tested through ``_build_unified_status_bar_content`` rather than the helpers, because the
    original defect was NOT in a helper — it was a missing ``elif``. A suite that exercised
    only the mapper would have stayed green through the entire outage, and the first draft of
    this file did exactly that.
    """

    def test_a_completed_recurrence_run_shows_its_stop_reason(self):
        assert _status_bar_status(completed=True, failed=False, completion_reason="early_stopping") == "Completed — early stopped"

    def test_a_completed_cascor_run_still_shows_its_reason(self):
        assert _status_bar_status(completed=True, failed=False, completion_reason="no_candidate") == "Completed — stalled (0 new units)"

    def test_a_failed_run_shows_its_error(self):
        """The branch that did not exist."""
        assert _status_bar_status(completed=False, failed=True, completion_reason="LMU service unreachable") == "Failed — LMU service unreachable"

    def test_a_failed_run_without_a_reason_stays_bare(self):
        """A cascor failure carries no reason; it must not gain an empty suffix or an em dash."""
        assert _status_bar_status(completed=False, failed=True) == "Failed"

    def test_a_completed_run_does_not_render_a_raw_error(self):
        """Cross-wiring guard: free text must not leak into the COMPLETED suffix.

        If the failure renderer were called from the completed branch, an unmapped token would
        print verbatim instead of being dropped.
        """
        assert _status_bar_status(completed=True, failed=False, completion_reason="HTTPConnectionPool(host='x'): Max retries exceeded") == "Completed"
