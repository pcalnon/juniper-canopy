#!/usr/bin/env python
"""Per-file coverage-gate tests for ``frontend.components.candidate_metrics_panel``.

Drives the panel's callback closures (via a stub app that records the raw
callback functions) plus the display-builder branches the baseline suite
misses: the ``_fetch_training_state`` HTTP path, the empty-epochs branch of
``_create_candidate_loss_figure``, and the second-candidate rows of
``_render_pool_history``.
"""

from unittest.mock import MagicMock, patch

import dash
import plotly.graph_objects as go
import pytest
from dash import html

from frontend.components.candidate_metrics_panel import CandidateMetricsPanel


class _StubApp:
    def __init__(self):
        self.callbacks = []

    def callback(self, *outputs, **kwargs):
        def decorator(fn):
            self.callbacks.append((outputs, kwargs, fn))
            return fn

        return decorator


@pytest.fixture
def panel():
    return CandidateMetricsPanel({}, component_id="cmp-gate")


@pytest.fixture
def callbacks(panel):
    app = _StubApp()
    panel.register_callbacks(app)
    return {fn.__name__: fn for _, _, fn in app.callbacks}


class TestApiUrl:
    def test_api_url_concatenates_base_and_path(self, panel):
        url = panel._api_url("/api/state")
        assert url.endswith("/api/state")
        assert url.startswith("http")


class TestFetchTrainingStateCallback:
    """F-CANOPY-036: this callback now carries the pool history too, so it returns a
    (state, history) pair. The history half rides here rather than on a poller of its
    own -- no new interval, no new renderer slot."""

    def test_non_candidate_tab_returns_no_update(self, callbacks):
        state, history = callbacks["fetch_training_state"](3, "metrics", [])
        assert state is dash.no_update
        assert history is dash.no_update

    def test_candidate_tab_fetches_state_on_200(self, panel, callbacks):
        def fake_get(url, **kwargs):
            resp = MagicMock(status_code=200)
            resp.json.return_value = {"history": [{"epoch": 1}]} if "pool-history" in url else {"candidate_pool_status": "Active"}
            return resp

        with patch("requests.get", side_effect=fake_get):
            state, history = callbacks["fetch_training_state"](1, "candidates", [])
        assert state == {"candidate_pool_status": "Active"}
        assert history == [{"epoch": 1}]

    def test_identical_history_is_not_rewritten(self, panel, callbacks):
        """Stage 2's no-op-write rule: an unchanged history must not re-fire its
        consumers every tick."""

        def fake_get(url, **kwargs):
            resp = MagicMock(status_code=200)
            resp.json.return_value = {"history": [{"epoch": 1}]} if "pool-history" in url else {}
            return resp

        with patch("requests.get", side_effect=fake_get):
            _state, history = callbacks["fetch_training_state"](1, "candidates", [{"epoch": 1}])
        assert history is dash.no_update

    def test_fetch_swallows_exception_and_returns_empty(self, panel, callbacks):
        """F-CANOPY-053: a failed fetch HOLDS the last good state for both stores.

        The name predates that change. This test used to assert ``state == {}``, and
        ``{}`` is what the status badge renders as ``Inactive``, so one transient hiccup
        blanked a live candidate phase. The state store now follows the history store's
        last-known-good contract.
        """
        with patch("requests.get", side_effect=RuntimeError("boom")):
            state, history = callbacks["fetch_training_state"](1, "candidates", [{"epoch": 1}], {"candidate_pool_status": "Training"})
        assert state is dash.no_update
        # Last-known-good: an unreachable server must not blank a populated history.
        assert history is dash.no_update

    def test_fetch_non_200_returns_empty(self, panel):
        """F-CANOPY-053: a non-200 is ``None`` now, not ``{}`` (the name predates the
        change), which is ``_fetch_pool_history``'s contract."""
        resp = MagicMock(status_code=503)
        with patch("requests.get", return_value=resp):
            assert panel._fetch_training_state() is None


class TestF053StateStoreWritesOnlyRealChanges:
    """F-CANOPY-053 (provisional id): the state store is written only when the state
    actually changed, and never blanked by a failed fetch.

    ``/api/state`` stamps a fresh ``timestamp`` on every call, so the store used to
    change on every tick and re-fire its three Input consumers; and a failed fetch wrote
    ``{}``, which the badge renders as ``Inactive``. The callback now compares against
    the store (riding as its own State, pinned in ``test_stage2_global_lane.py``) with
    the volatile keys stripped, and maps a failed fetch to ``no_update``.
    """

    STATE = {
        "status": "Started",
        "candidate_pool_status": "Training",
        "candidate_pool_phase": "Training",
        "candidate_pool_size": 8,
        "candidate_epoch": 501,
        "pool_metrics": {"avg_loss": 0.25},
        "timestamp": 1790106936.63,
    }

    @staticmethod
    def _serve(state):
        def fake_get(url, **kwargs):
            resp = MagicMock(status_code=200)
            resp.json.return_value = {"history": []} if "pool-history" in url else state
            return resp

        return fake_get

    def _run(self, callbacks, served, current):
        with patch("requests.get", side_effect=self._serve(served)):
            return callbacks["fetch_training_state"](1, "candidates", [], current)

    def test_timestamp_only_change_is_no_update(self, callbacks):
        fresh = dict(self.STATE, timestamp=self.STATE["timestamp"] + 10.0)
        state, history = self._run(callbacks, fresh, dict(self.STATE))
        assert state is dash.no_update, "a per-call timestamp alone must not rewrite the store"
        assert history is dash.no_update

    def test_stale_age_only_change_is_no_update(self, callbacks):
        """``stale_age_seconds`` is recomputed on every call while the upstream is down
        (main.py ``get_state``), so ignoring only ``timestamp`` would still rewrite the
        store on every tick of an outage."""
        current = dict(self.STATE, stale=True, stale_age_seconds=12.3)
        fresh = dict(current, stale_age_seconds=22.3, timestamp=self.STATE["timestamp"] + 10.0)
        state, _history = self._run(callbacks, fresh, current)
        assert state is dash.no_update

    def test_real_change_still_writes(self, callbacks):
        fresh = dict(self.STATE, candidate_pool_status="Inactive", timestamp=self.STATE["timestamp"] + 10.0)
        state, _history = self._run(callbacks, fresh, dict(self.STATE))
        assert state == fresh

    def test_nested_change_still_writes(self, callbacks):
        fresh = dict(self.STATE, pool_metrics={"avg_loss": 0.2})
        state, _history = self._run(callbacks, fresh, dict(self.STATE))
        assert state == fresh

    def test_staleness_flip_is_a_real_change(self, callbacks):
        """``stale`` itself is NOT volatile: the flip into an outage must be written."""
        fresh = dict(self.STATE, stale=True, stale_age_seconds=0.4)
        state, _history = self._run(callbacks, fresh, dict(self.STATE, stale=False))
        assert state == fresh

    def test_mount_with_empty_store_still_writes(self, callbacks):
        """The store mounts as ``{}``; the first fetch must land."""
        state, _history = self._run(callbacks, dict(self.STATE), {})
        assert state == self.STATE

    def test_no_current_value_never_suppresses(self, callbacks):
        """``None`` means "no previous value", which is also every 3-argument call."""
        state, _history = self._run(callbacks, dict(self.STATE), None)
        assert state == self.STATE

    def test_a_comparison_that_fails_still_writes(self, callbacks):
        """Fail toward the write. A payload that cannot be compared cannot be PROVEN
        unchanged, and a suppressed real update is worse than a redundant one."""
        fresh = dict(self.STATE)
        fresh[1] = "a non-string key makes the sorted-key comparison raise"
        state, _history = self._run(callbacks, fresh, dict(self.STATE))
        assert state == fresh

    def test_non_200_holds_the_last_good_state(self, callbacks):
        with patch("requests.get", return_value=MagicMock(status_code=503)):
            state, history = callbacks["fetch_training_state"](1, "candidates", [], dict(self.STATE))
        assert state is dash.no_update
        assert history is dash.no_update

    def test_a_payload_that_is_not_an_object_is_a_failure(self, panel):
        resp = MagicMock(status_code=200)
        resp.json.return_value = ["not", "a", "state"]
        with patch("requests.get", return_value=resp):
            assert panel._fetch_training_state() is None


class TestStatusDisplayCallback:
    def test_empty_state_defaults(self, callbacks):
        badge, style, phase, size = callbacks["update_status_display"](None)
        assert badge == "Inactive"
        assert phase == "Idle"
        assert size == "0"
        assert isinstance(style, dict)

    def test_populated_state(self, callbacks):
        state = {"candidate_pool_status": "Active", "candidate_pool_phase": "candidate_training", "candidate_pool_size": 6}
        badge, style, phase, size = callbacks["update_status_display"](state)
        assert badge == "Active"
        assert phase == "candidate_training"
        assert size == "6"


class TestEpochProgressCallback:
    def test_empty_state_hidden(self, callbacks):
        style, value, label = callbacks["update_epoch_progress"](None)
        assert style == {"display": "none"}
        assert value == 0
        assert label == ""

    def test_active_progress_computes_percent(self, callbacks):
        style, value, label = callbacks["update_epoch_progress"]({"candidate_epoch": 5, "candidate_total_epochs": 10})
        assert style == {"display": "block"}
        assert value == 50
        assert label == "5/10"

    def test_state_without_epoch_hidden(self, callbacks):
        style, value, label = callbacks["update_epoch_progress"]({"candidate_pool_status": "Active"})
        assert style == {"display": "none"}
        assert value == 0


class TestPoolInfoCallback:
    def test_empty_state_placeholder(self, callbacks):
        result = callbacks["update_pool_info"](None)
        assert isinstance(result, html.Div)
        assert "No active candidate pool" in str(result)

    def test_inactive_pool_placeholder(self, callbacks):
        result = callbacks["update_pool_info"]({"candidate_pool_status": "Inactive"})
        assert "No active candidate pool" in str(result)

    def test_active_pool_builds_display(self, callbacks):
        state = {
            "candidate_pool_status": "Active",
            "top_candidate_id": "cand_1",
            "top_candidate_score": 0.9,
            "pool_metrics": {"avg_loss": 0.1},
        }
        result = callbacks["update_pool_info"](state)
        assert isinstance(result, html.Div)
        assert "Top 2 Candidates" in str(result)


class TestLossPlotCallback:
    def test_returns_figure(self, callbacks):
        state = {"epochs": [1, 2, 3], "losses": [0.5, 0.4, 0.3], "phases": ["candidate", "candidate", "candidate"]}
        fig = callbacks["update_loss_plot"](state, "dark")
        assert isinstance(fig, go.Figure)

    def test_none_theme_defaults_light(self, callbacks):
        fig = callbacks["update_loss_plot"](None, None)
        assert isinstance(fig, go.Figure)


class TestTogglePoolDetailsCallback:
    def test_click_toggles_open(self, callbacks):
        is_open, icon = callbacks["toggle_pool_details"](1, True)
        assert is_open is False
        assert icon == "▶"

    def test_click_toggles_closed_to_open(self, callbacks):
        is_open, icon = callbacks["toggle_pool_details"](1, False)
        assert is_open is True
        assert icon == "▼"

    def test_no_click_keeps_state(self, callbacks):
        is_open, icon = callbacks["toggle_pool_details"](0, True)
        assert is_open is True
        assert icon == "▼"


class TestPoolHistoryIsNoLongerBuiltInTheBrowser:
    """F-CANOPY-036: ``update_pool_history`` was removed.

    It appended in the browser from an Input fed by a ~1 Hz store, so dash-renderer
    ran it against the store's CURRENT value whenever the feeder won the race -- any
    pool state shorter-lived than the promotion delay was unrecordable, and the panel
    rendered zero cards across five training runs. The accumulation now happens in
    ``TrainingState.update_state`` under the state lock; see
    ``src/tests/unit/test_f036_server_side_pool_history.py`` for its coverage.
    """

    def test_the_client_side_append_callback_is_gone(self, callbacks):
        assert "update_pool_history" not in callbacks, "the client-side append is back; it cannot see short-lived pool states"

    def test_the_history_store_has_exactly_one_writer(self, panel):
        """And it is the tab-gated fetch, not a second racing appender."""
        import dash as _dash
        from dash import html as _html

        app = _dash.Dash(__name__)
        app.layout = _html.Div([panel.get_layout()])
        panel.register_callbacks(app)
        target = f"{panel.component_id}-pool-history-store.data"
        writers = [e for e in app._callback_list if target in str(e["output"])]
        assert len(writers) == 1, f"expected exactly one writer of the pool-history store, found {len(writers)}"


class TestRenderPoolHistoryCallback:
    def test_callback_delegates_to_helper(self, callbacks):
        result = callbacks["render_pool_history"]([])
        assert len(result) == 1  # placeholder message


class TestToggleHistoryCallback:
    def test_toggles(self, callbacks):
        is_open, icon = callbacks["toggle_history"](1, False)
        assert is_open is True
        assert icon == "▼"
        is_open2, icon2 = callbacks["toggle_history"](1, True)
        assert is_open2 is False
        assert icon2 == "▶"


class TestLossFigureEmptyEpochs:
    def test_empty_epochs_returns_empty_plot(self, panel):
        # state is truthy but epochs/losses/phases are empty -> empty plot branch.
        fig = panel._create_candidate_loss_figure({"epochs": [], "losses": [], "phases": []})
        assert isinstance(fig, go.Figure)
        assert len(fig.data) == 0


class TestRenderPoolHistorySecondCandidate:
    def test_second_candidate_rows_rendered(self, panel):
        history = [
            {
                "epoch": 12,
                "status": "Active",
                "phase": "Training",
                "size": 8,
                "top_candidate_id": "c1",
                "top_candidate_score": 0.9,
                "second_candidate_id": "c2",
                "second_candidate_score": 0.7,
                "pool_metrics": {"avg_loss": 0.2, "avg_accuracy": 0.8},
            }
        ]
        result = panel._render_pool_history(history)
        assert len(result) == 1
        assert "2nd Candidate" in str(result)
