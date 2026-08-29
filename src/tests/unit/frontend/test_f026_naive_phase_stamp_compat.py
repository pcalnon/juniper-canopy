#!/usr/bin/env python
"""F-CANOPY-026 (canopy half): a naive ``phase_started_at`` is LOCAL, not UTC.

Ledger: juniper-ml notes/JUNIPER_2026-08-09_JUNIPER-CANOPY_E2E-VALIDATION-EVIDENCE.md

cascor used to emit ``phase_started_at`` as ``datetime.now().isoformat()`` — naive
local. This handler stamped a naive value as UTC and subtracted it from ``now(UTC)``,
so the readout was off by the whole host offset: **"Phase Duration: 300m 37s" on a run
37 seconds old** on a CDT box (18000 s = -0500). The counter ticked correctly at 1 s/s,
so it was a pure constant offset.

The real fix is upstream (juniper-cascor emits tz-aware UTC, which makes the naive
branch unreachable). This is the compat half, for a dashboard pointed at an un-upgraded
cascor.

**These tests only discriminate off UTC-0**, which is why they force
``TZ=America/Chicago`` — on a UTC-0 host local *is* UTC and the two readings coincide.
That is exactly why fourteen segments of dashboard testing, and every CI runner, missed
this. ``test_the_bug_is_invisible_at_utc0`` pins that property directly so the suite
states its own blind spot rather than hiding it.
"""

import os
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[3]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from frontend.components.metrics_panel import MetricsPanel  # noqa: E402


@pytest.fixture
def panel():
    return MetricsPanel({})


def _set_tz(name):
    previous = os.environ.get("TZ")
    os.environ["TZ"] = name
    time.tzset()
    return previous


def _restore_tz(previous):
    if previous is None:
        os.environ.pop("TZ", None)
    else:
        os.environ["TZ"] = previous
    time.tzset()


@pytest.fixture
def cdt():
    previous = _set_tz("America/Chicago")
    yield
    _restore_tz(previous)


@pytest.fixture
def kolkata():
    """UTC+0530 — east of UTC, where the same bug blanks the readout instead."""
    previous = _set_tz("Asia/Kolkata")
    yield
    _restore_tz(previous)


def _state(started):
    return {"status": "RUNNING", "phase_started_at": started}


@pytest.mark.unit
class TestNaivePhaseStampIsTreatedAsLocal:
    def test_naive_local_stamp_reads_as_seconds_not_hours(self, panel, cdt):
        """THE regression: a phase 30 s old must not render as ~5 hours."""
        naive_now = datetime.now().replace(microsecond=0).isoformat()
        text = panel._update_phase_duration_handler(state=_state(naive_now))
        assert text.startswith("Phase Duration: 0m"), f"a just-started phase rendered as {text!r} — the host offset is still being added"

    def test_a_real_elapsed_interval_is_preserved(self, panel, cdt):
        """The fix must not flatten the duration to zero — it must still measure."""
        started = (datetime.now() - timedelta(seconds=125)).replace(microsecond=0).isoformat()
        text = panel._update_phase_duration_handler(state=_state(started))
        assert text == "Phase Duration: 2m 5s", f"expected 2m 5s elapsed, got {text!r}"

    def test_east_of_utc_no_longer_blanks_the_readout(self, panel, kolkata):
        """The mirror symptom.

        Stamped as UTC, a naive local time east of Greenwich lands in the FUTURE, the
        handler's ``total_seconds < 0`` guard fires, and the user sees nothing at all —
        the same defect presenting as a missing readout rather than a wrong one.
        """
        naive_now = datetime.now().replace(microsecond=0).isoformat()
        text = panel._update_phase_duration_handler(state=_state(naive_now))
        assert text != "", "the readout is still blank east of UTC — the naive stamp is being read as UTC and lands in the future"
        assert text.startswith("Phase Duration: 0m")

    def test_an_aware_utc_stamp_is_unchanged(self, panel, cdt):
        """Forward guard: the fixed cascor emits aware UTC, which must be untouched."""
        started = (datetime.now(UTC) - timedelta(seconds=65)).isoformat()
        assert panel._update_phase_duration_handler(state=_state(started)) == "Phase Duration: 1m 5s"

    def test_an_aware_offset_stamp_is_unchanged(self, panel, cdt):
        """A stamp carrying a non-UTC offset is already unambiguous."""
        started = (datetime.now().astimezone() - timedelta(seconds=5)).isoformat()
        assert panel._update_phase_duration_handler(state=_state(started)) == "Phase Duration: 0m 5s"

    def test_the_bug_is_invisible_at_utc0(self, panel):
        """Pins the suite's OWN blind spot.

        At UTC-0, naive-as-local and naive-as-UTC agree, so none of the tests above can
        discriminate. If this ever fails, the TZ fixtures have stopped taking effect and
        the rest of this module has quietly gone vacuous.
        """
        previous = _set_tz("UTC")
        try:
            naive_now = datetime.now().replace(microsecond=0).isoformat()
            assert panel._update_phase_duration_handler(state=_state(naive_now)).startswith("Phase Duration: 0m")
        finally:
            _restore_tz(previous)

    @pytest.mark.parametrize("bad", ["", None, "not-a-timestamp"])
    def test_unusable_stamps_still_render_empty(self, panel, cdt, bad):
        assert panel._update_phase_duration_handler(state=_state(bad)) == ""

    @pytest.mark.parametrize("status", ["STOPPED", "IDLE", ""])
    def test_non_running_statuses_still_render_empty(self, panel, cdt, status):
        state = {"status": status, "phase_started_at": datetime.now().isoformat()}
        assert panel._update_phase_duration_handler(state=state) == ""
