#!/usr/bin/env python
"""Per-file coverage gate: inner-callback bodies of dashboard_manager.py (part 2).

Covers the dataset-apply / experimental-functions / live-dataset-switch /
dataset-swap-observer inner callbacks (source regions ~4126-4536), invoked via
the raw registered callback function (see raw_cb docstring in inner1). Every
test asserts real return behaviour.
"""

from unittest.mock import MagicMock, patch

import dash
import pytest
import requests

from frontend.dashboard_manager import DashboardManager


@pytest.fixture
def dm():
    return DashboardManager({})


def raw_cb(dm, name):
    matches = []
    for entry in dm.app.callback_map.values():
        cb = entry.get("callback")
        if cb is None:
            continue
        raw = getattr(cb, "__wrapped__", cb)
        if getattr(raw, "__name__", None) == name:
            matches.append(raw)
    if not matches:
        raise KeyError(f"callback {name!r} not registered")
    if len(matches) > 1:
        raise AssertionError(f"ambiguous callback name {name!r}: {len(matches)} matches")
    return matches[0]


def _resp(*, status=200, json_value=None, text=""):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = json_value if json_value is not None else {}
    r.text = text
    return r


# ---------------------------------------------------------------------------
# apply_dataset (4128-4161)
# ---------------------------------------------------------------------------
class TestApplyDatasetInner:
    # N3 (T4): apply_dataset now returns ``(banner_is_open, stage_outcome_alert)``
    # — a staging failure that used to be silent (``return dash.no_update``) now
    # also surfaces a danger alert. Every branch asserts both outputs.
    def test_no_click(self, dm):
        cb = raw_cb(dm, "apply_dataset")
        # N7: apply_dataset gained the pattern-matching gen-param (values, ids) — empty for spiral.
        assert cb(None, "spirals", 100, 0.1, 1.5, 2, [], []) == (dash.no_update, dash.no_update)

    @patch("requests.post")
    def test_success_opens_banner(self, mock_post, dm):
        mock_post.return_value = _resp(status=200)
        cb = raw_cb(dm, "apply_dataset")
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            banner, alert = cb(1, "spirals", 100, 0.1, 1.5, 2, [], [])
        assert banner is True
        assert alert is None  # success clears any prior staging error
        # dataset_type + all four optional numeric/spiral fields were forwarded
        payload = mock_post.call_args.kwargs["json"]
        assert payload["nn_dataset_type"] == "spirals"
        assert payload["nn_dataset_elements"] == 100

    @patch("requests.post")
    def test_non_200_surfaces_alert(self, mock_post, dm):
        mock_post.return_value = _resp(status=500, text="err")
        cb = raw_cb(dm, "apply_dataset")
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            banner, alert = cb(1, "spirals", None, None, None, None, [], [])
        assert banner is dash.no_update
        assert alert is not None and alert.color == "danger"

    @patch("requests.post", side_effect=requests.ConnectionError("down"))
    def test_exception_surfaces_alert(self, _mock_post, dm):
        cb = raw_cb(dm, "apply_dataset")
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            banner, alert = cb(1, "spirals", 100, 0.1, 1.5, 2, [], [])
        assert banner is dash.no_update
        assert alert is not None and alert.color == "danger"


# ---------------------------------------------------------------------------
# cancel_pending_dataset (4170-4185)
# ---------------------------------------------------------------------------
class TestCancelPendingDatasetInner:
    def test_no_click(self, dm):
        cb = raw_cb(dm, "cancel_pending_dataset")
        assert cb(None) is dash.no_update

    @patch("requests.delete")
    def test_success_closes_banner(self, mock_delete, dm):
        mock_delete.return_value = _resp(status=200)
        cb = raw_cb(dm, "cancel_pending_dataset")
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            assert cb(1) is False

    @patch("requests.delete")
    def test_non_200_no_update(self, mock_delete, dm):
        mock_delete.return_value = _resp(status=404, text="nope")
        cb = raw_cb(dm, "cancel_pending_dataset")
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            assert cb(1) is dash.no_update

    @patch("requests.delete", side_effect=requests.ConnectionError("down"))
    def test_exception_no_update(self, _mock_delete, dm):
        cb = raw_cb(dm, "cancel_pending_dataset")
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            assert cb(1) is dash.no_update


# ---------------------------------------------------------------------------
# open_restart_confirm_modal (N3 — replaced the feedback-free
# ``restart_with_new_dataset`` closure: the "Stop & Restart" button now opens
# the confirm modal (Q3/Q4) instead of POSTing ``/api/train/start?reset=true``).
# N3b: the open handler now returns a 17-tuple — modal-open, summary, toggle/
# collapse resets, context, the 5 editable dataset field values, the 6 editable
# param field values, and the baseline store.
# ---------------------------------------------------------------------------
class TestOpenRestartConfirmModalInner:
    def test_no_click(self, dm):
        cb = raw_cb(dm, "open_restart_confirm_modal")
        assert cb(None, "spirals", 100, 0.1, 1.5, 2) == (dash.no_update,) * 17

    @patch("requests.get")
    def test_click_opens_modal_with_defaults_off(self, mock_get, dm):
        mock_get.return_value = _resp(status=200, json_value={"current_epoch": 5})
        cb = raw_cb(dm, "open_restart_confirm_modal")
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            result = cb(1, "spirals", 100, 0.1, 1.5, 2)
        assert len(result) == 17
        assert result[0] is True  # modal open
        # Q4 default OFF (index 2) + Q3 verify/modify section collapsed (index 3).
        assert result[2] is False
        assert result[3] is False
        assert result[1] is not None  # summary
        assert result[16] and "dataset" in result[16] and "params" in result[16]  # baseline

    @patch("requests.get", side_effect=requests.ConnectionError("down"))
    def test_click_opens_even_when_status_unreachable(self, _mock_get, dm):
        cb = raw_cb(dm, "open_restart_confirm_modal")
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            is_open = cb(1, "moons", None, None, None, None)[0]
        assert is_open is True


# ---------------------------------------------------------------------------
# pending-dataset banner reconciliation — Stage 2 (design §13 row 2): merged
# into ``update_system_panels``; the banner is element [3] of its 4-tuple.
# Same contract as the old ``reconcile_pending_dataset_banner``: bool(pending)
# on 200, ``no_update`` on non-200 / network error.
# ---------------------------------------------------------------------------
class TestReconcilePendingDatasetBannerInner:
    @staticmethod
    def _banner(dm, cb_result):
        return cb_result[3]

    @patch("requests.get")
    def test_pending_true(self, mock_get, dm):
        mock_get.return_value = _resp(status=200, json_value={"pending_dataset": {"nn_dataset_type": "xor"}})
        cb = raw_cb(dm, "update_system_panels")
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            assert self._banner(dm, cb(1)) is True

    @patch("requests.get")
    def test_pending_false(self, mock_get, dm):
        mock_get.return_value = _resp(status=200, json_value={"pending_dataset": None})
        cb = raw_cb(dm, "update_system_panels")
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            assert self._banner(dm, cb(1)) is False

    @patch("requests.get")
    def test_non_200_no_update(self, mock_get, dm):
        mock_get.return_value = _resp(status=500)
        cb = raw_cb(dm, "update_system_panels")
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            assert self._banner(dm, cb(1)) is dash.no_update

    @patch("requests.get", side_effect=requests.ConnectionError("down"))
    def test_exception_no_update(self, _mock_get, dm):
        cb = raw_cb(dm, "update_system_panels")
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            assert self._banner(dm, cb(1)) is dash.no_update


# ---------------------------------------------------------------------------
# _setup_experimental_functions_callbacks (4282-4298, 4316-4348)
# ---------------------------------------------------------------------------
class TestExperimentalFunctionsInner:
    @patch("requests.get")
    def test_load_reconcile_success(self, mock_get, dm):
        mock_get.return_value = _resp(status=200, json_value={"data": {"enabled": True}})
        cb = raw_cb(dm, "load_reconcile_experimental_functions")
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            value, store, alert = cb(1, None)
        assert value is True
        assert store == {"experimental_functions": True}
        assert alert is None

    @patch("requests.get")
    def test_load_reconcile_unchanged_value_suppresses_toggle_write(self, mock_get, dm):
        # F-CANOPY-025 (echo clobber): when the authoritative value already
        # matches the toggle, DON'T rewrite it — an unchanged write fires the
        # toggle handler, which used to POST the mount-time value back to
        # cascor on every page load, clobbering operator changes.
        mock_get.return_value = _resp(status=200, json_value={"data": {"enabled": True}})
        cb = raw_cb(dm, "load_reconcile_experimental_functions")
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            value, store, alert = cb(1, True)
        assert value is dash.no_update
        assert store == {"experimental_functions": True}

    @patch("requests.get")
    def test_load_reconcile_non_200_warns(self, mock_get, dm):
        mock_get.return_value = _resp(status=503, text="down")
        cb = raw_cb(dm, "load_reconcile_experimental_functions")
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            value, store, alert = cb(1, None)
        # F-CANOPY-025: the toggle already ships False, so the safe-default
        # arm suppresses the (unchanged) write instead of echoing it.
        assert value is dash.no_update
        assert store == {"experimental_functions": False}
        assert alert is not None

    @patch("requests.get", side_effect=requests.ConnectionError("down"))
    def test_load_reconcile_exception(self, _mock_get, dm):
        cb = raw_cb(dm, "load_reconcile_experimental_functions")
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            value, store, alert = cb(1, None)
        assert value is dash.no_update  # F-CANOPY-025: unchanged-write suppression
        assert alert is not None

    @patch("requests.post")
    def test_toggle_success_authoritative_matches(self, mock_post, dm):
        mock_post.return_value = _resp(status=200, json_value={"data": {"enabled": True}})
        cb = raw_cb(dm, "handle_experimental_functions_toggle")
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            value, store, alert = cb(True, {"experimental_functions": False})
        assert value is True
        assert store == {"experimental_functions": True}
        assert alert is None

    @patch("requests.post")
    def test_toggle_success_authoritative_differs_warns(self, mock_post, dm):
        # requested True but backend authoritative False -> warning alert
        mock_post.return_value = _resp(status=200, json_value={"data": {"enabled": False}})
        cb = raw_cb(dm, "handle_experimental_functions_toggle")
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            value, store, alert = cb(True, {"experimental_functions": False})
        assert value is False
        assert alert is not None

    @patch("requests.post")
    def test_toggle_non_200_reverts(self, mock_post, dm):
        mock_post.return_value = _resp(status=500, text="rejected")
        cb = raw_cb(dm, "handle_experimental_functions_toggle")
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            value, store, alert = cb(True, {"experimental_functions": False})
        assert value is False  # reverted to last-known-good
        assert alert is not None

    def test_toggle_echo_is_not_posted(self, dm):
        # F-CANOPY-025 (echo guard): value == store means a programmatic
        # write (reconcile / revert), not a user flip — no POST, no rewrite.
        cb = raw_cb(dm, "handle_experimental_functions_toggle")
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            value, store, alert = cb(True, {"experimental_functions": True})
        assert value is dash.no_update
        assert store is dash.no_update
        assert alert is dash.no_update

    @patch("requests.post", side_effect=requests.ConnectionError("down"))
    def test_toggle_exception_reverts(self, _mock_post, dm):
        # A REAL user flip (value != store) whose POST dies reverts to the
        # store's last-known-good value.
        cb = raw_cb(dm, "handle_experimental_functions_toggle")
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            value, store, alert = cb(True, {"experimental_functions": False})
        assert value is False  # reverted to last-known-good
        assert alert is not None


# ---------------------------------------------------------------------------
# _setup_live_dataset_switch_callbacks inner delegations (4382-4483)
# ---------------------------------------------------------------------------
class TestLiveDatasetSwitchInner:
    @patch("requests.get")
    def test_update_training_status_store(self, mock_get, dm):
        # Stage 2 (design §13 row 1): the store's dedicated poller merged into
        # update_unified_status_bar; the store payload is element [9] of its tuple.
        mock_get.return_value = _resp(status=200, json_value={"is_running": True, "phase": "output"})
        cb = raw_cb(dm, "update_unified_status_bar")
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            result = cb(1, None, None, None)
        assert result[9] == {"is_running": True, "phase": "output"}

    def test_gate_live_switch_button(self, dm):
        # F-CANOPY-025: the standalone gate callback merged into
        # update_unified_status_bar (it lost the promotion race against that
        # feeder's in-flight claim on training-status-store during every run —
        # the only time its allow arm is reachable). The truth table lives on
        # in the directly invocable handler the merged path calls.
        assert dm._gate_live_switch_button_handler(flags={"experimental_functions": True}, status={"is_running": True}) is False
        assert dm._gate_live_switch_button_handler(flags={"experimental_functions": True}, status={"is_running": False}) is True

    def test_open_live_switch_modal(self, dm):
        cb = raw_cb(dm, "open_live_switch_modal")
        is_open, rows = cb(1, "spirals", 100, 0.1, 2, 1.5)
        assert is_open is True
        assert isinstance(rows, list) and rows

    def test_close_live_switch_modal_on_fallback(self, dm):
        cb = raw_cb(dm, "close_live_switch_modal_on_fallback")
        assert cb(1) is False
        assert cb(None) is dash.no_update

    @patch("requests.post")
    def test_accept_live_switch_success(self, mock_post, dm):
        mock_post.return_value = _resp(status=200, json_value={"data": {"status": "swapped", "pre_swap_snapshot_id": "snap1"}})
        cb = raw_cb(dm, "accept_live_switch")
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            modal, progress, outcome, in_flight = cb(1, "spirals", 100, 0.1, 2, 1.5)
        assert modal is False and progress is False
        assert in_flight == {"in_flight": False}
        assert outcome is not None

    def test_open_progress_alert_on_accept(self, dm):
        cb = raw_cb(dm, "open_progress_alert_on_accept")
        progress, in_flight = cb(1)
        assert progress is True and in_flight == {"in_flight": True}

    @patch("requests.delete")
    def test_cancel_live_switch_success(self, mock_delete, dm):
        mock_delete.return_value = _resp(status=200)
        cb = raw_cb(dm, "cancel_live_switch")
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            assert cb(1) is dash.no_update


# ---------------------------------------------------------------------------
# _setup_dataset_swap_observers_callbacks inner delegations (4504, 4518, 4536)
# ---------------------------------------------------------------------------
class TestDatasetSwapObserversInner:
    @patch("requests.get")
    def test_poll_dataset_swap_events(self, mock_get, dm):
        # Stage 2 (design §13 row 3): the poller holds its own store as State.
        mock_get.return_value = _resp(status=200, json_value={"data": {"events": [{"timestamp": "t1"}]}})
        cb = raw_cb(dm, "poll_dataset_swap_events")
        with dm.app.server.test_request_context(base_url="http://localhost:8050"):
            result = cb(1, None)
        assert result == {"events": [{"timestamp": "t1"}]}

    def test_hydrate_loaded_snapshot_swap_events_no_session(self, dm):
        cb = raw_cb(dm, "hydrate_loaded_snapshot_swap_events")
        # no session and no prior snapshot -> no_update
        assert cb(None, {}) is dash.no_update

    def test_merge_ws_dataset_swap_events_empty_buffer(self, dm):
        cb = raw_cb(dm, "merge_ws_dataset_swap_events")
        # non-dict buffer -> no_update
        assert cb(None, None) is dash.no_update
