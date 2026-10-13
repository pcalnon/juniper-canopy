"""F-CANOPY-003 regression: a control button must be released by its success ack,
not only by the interval-driven timeout sweep.

Found live in the canopy E2E arc (juniper-ml evidence note): Reset's WS frame
was acked in ~1 s, the optimistic ``loading`` state rendered at +4 s, and the
button re-enabled at **+32 s**; Start's stuck window after a successful ack ran
minutes. The Phase-D clientside success path only ``console.log``'d, the REST
path did nothing on 2xx, and the sweep ``handle_button_timeout_and_acks`` -- the
SOLE recovery -- compared against ``DASHBOARD_TIMEOUT_THRESHOLD`` on
``fast-update-interval``, which lands 30 s to minutes late under callback
congestion. Its registration comment promised "or on control acknowledgment";
no ack path existed.

Two halves, both pinned here: the JS reports the ack (and clears the button's
loading state directly) on WS and REST success, and the sweep handler honours a
fresh success ack immediately while ignoring stale ones.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import dash
import pytest

SRC_DIR = Path(__file__).resolve().parent.parent.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

os.environ.setdefault("JUNIPER_CANOPY_DEMO_MODE", "1")


@pytest.fixture
def dashboard_manager():
    from frontend.dashboard_manager import DashboardManager

    return DashboardManager({"metrics_panel": {}, "network_visualizer": {}, "dataset_plotter": {}, "decision_boundary": {}})


@pytest.mark.unit
class TestClientsideAckContract:
    """The JS string is the contract (same idiom as test_phase_d_button_clientside)."""

    def test_success_ack_is_reported_and_clears_the_button(self):
        from frontend.dashboard_manager import PHASE_D_TRAINING_BUTTONS_CLIENTSIDE_JS as js

        assert "function reportSuccess" in js
        # The ack rides the same store as failures, with the command named...
        assert "success: true, command: command" in js
        # ...and the button's loading state is cleared directly, not left to the sweep.
        assert "dc.set_props('button-states'" in js
        assert "loading: false, timestamp: 0" in js

    def test_both_transports_report_the_ack(self):
        from frontend.dashboard_manager import PHASE_D_TRAINING_BUTTONS_CLIENTSIDE_JS as js

        assert "reportSuccess('ws'" in js
        assert "reportSuccess('rest'" in js
        assert js.count("reportSuccess(") >= 3  # 1 definition + the two call sites


@pytest.mark.unit
class TestSweepHonoursTheAck:
    def _loading(self, ts: float) -> dict:
        return {"disabled": True, "loading": True, "timestamp": ts}

    def test_fresh_success_ack_releases_the_button_before_the_timeout(self, dashboard_manager):
        clicked = time.time() - 0.2  # well inside DASHBOARD_TIMEOUT_THRESHOLD (2 s)
        states = {"start": self._loading(clicked), "pause": {"disabled": False, "loading": False, "timestamp": 0}}
        ack = {"last": "start-button", "ts": clicked + 0.05, "success": True, "command": "start", "transport": "ws"}
        result = dashboard_manager._handle_button_timeout_and_acks_handler(action=ack, n_intervals=1, button_states=states)
        assert result["start"] == {"disabled": False, "loading": False, "timestamp": 0}
        assert result["pause"] == states["pause"]

    def test_ack_only_releases_its_own_command(self, dashboard_manager):
        now = time.time()
        states = {"start": self._loading(now - 0.2), "reset": self._loading(now - 0.3)}
        ack = {"ts": now, "success": True, "command": "reset"}
        result = dashboard_manager._handle_button_timeout_and_acks_handler(action=ack, n_intervals=1, button_states=states)
        assert result["reset"]["loading"] is False
        assert result["start"]["loading"] is True

    def test_stale_ack_from_an_earlier_click_does_not_release_a_newer_one(self, dashboard_manager):
        now = time.time()
        states = {"start": self._loading(now - 0.1)}  # the NEW click
        stale = {"ts": now - 5.0, "success": True, "command": "start"}  # an ack of the previous click
        assert dashboard_manager._handle_button_timeout_and_acks_handler(action=stale, n_intervals=1, button_states=states) is dash.no_update

    @pytest.mark.parametrize(
        "action",
        [None, {"ts": time.time(), "success": False, "command": "start"}, {"ts": time.time(), "success": True}, {"success": True, "command": "start"}, {"last": "start-button", "ts": time.time(), "success": True, "transport": "ws"}],
        ids=["no-action", "failure", "no-command", "no-ts", "click-time-optimistic-write"],
    )
    def test_non_acks_leave_the_timeout_semantics_alone(self, dashboard_manager, action):
        states = {"start": self._loading(time.time() - 0.2)}
        assert dashboard_manager._handle_button_timeout_and_acks_handler(action=action, n_intervals=1, button_states=states) is dash.no_update

    def test_timeout_backstop_still_releases(self, dashboard_manager):
        states = {"start": self._loading(time.time() - 3.0)}
        result = dashboard_manager._handle_button_timeout_and_acks_handler(action=None, n_intervals=1, button_states=states)
        assert result["start"]["loading"] is False
