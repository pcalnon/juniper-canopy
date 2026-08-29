"""F-CANOPY-035 regression: the candidate loss plot must be fed by the producer
that actually emits per-epoch candidate losses.

Found during the 2026-08-24 live re-drive (juniper-ml evidence note): the figure
read ``epochs`` / ``losses`` / ``phases`` off the training-state store, keys
``/api/state`` never provides in any lane (``TrainingState._STATE_FIELDS`` has
none of them), so the only reachable render was the "No candidate data available"
placeholder -- while cascor's metrics history held 4,106 candidate-phase per-epoch
loss entries for the same run and canopy already proxied them at
``/api/metrics/history``. The panel was wired to the wrong producer, not
starved. The fix consumes the dashboard's existing shared metrics-history store
(no new poller -- the F-CANOPY-027 rule) and derives the three series from it.
"""

import plotly.graph_objects as go
import pytest
from dash.dependencies import Input

from frontend.components.candidate_metrics_panel import SHARED_METRICS_STORE_ID, CandidateMetricsPanel


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
    return CandidateMetricsPanel({}, component_id="cmp-f035")


@pytest.fixture
def app(panel):
    stub = _StubApp()
    panel.register_callbacks(stub)
    return stub


@pytest.fixture
def callbacks(app):
    return {fn.__name__: fn for _, _, fn in app.callbacks}


def _entry(epoch, loss, phase):
    """The dashboard's nested history shape (demo backend and the cascor adapter's
    ``_to_dashboard_metric`` both produce it)."""
    return {"epoch": epoch, "metrics": {"loss": loss, "accuracy": 0.5}, "network_topology": {"hidden_units": 1}, "phase": phase, "timestamp": "t"}


# What /api/state really carries mid-candidate-phase (2026-08-24 live capture):
# pool telemetry, and none of epochs / losses / phases.
REAL_STATE = {"candidate_pool_size": 40, "candidate_epoch": 201, "candidates_trained": 40, "current_epoch": 7, "phase": "candidate", "is_training": True}
HISTORY = [_entry(1, 0.9, "output"), _entry(2, 0.7, "candidate"), _entry(3, 0.6, "candidate"), _entry(4, 0.5, "output"), _entry(5, 0.4, "candidate")]


@pytest.mark.unit
class TestF035ProducerContract:
    def test_api_state_never_carries_the_three_keys(self):
        """The ledger's proof: the old producer cannot feed the figure in any lane."""
        from backend.training_monitor import TrainingState

        fields = set(TrainingState._STATE_FIELDS)
        assert not fields & {"epochs", "losses", "phases"}

    def test_loss_plot_consumes_the_shared_metrics_history_store(self, app):
        registered = {fn.__name__: outputs for outputs, _, fn in app.callbacks}
        outputs = registered["update_loss_plot"]
        inputs = [dep for group in outputs for dep in (group if isinstance(group, (list, tuple)) else [group]) if isinstance(dep, Input)]
        assert any(dep.component_id == SHARED_METRICS_STORE_ID and dep.component_property == "data" for dep in inputs)
        assert SHARED_METRICS_STORE_ID == "metrics-panel-metrics-store"


@pytest.mark.unit
class TestCandidateSeriesFromHistory:
    def test_nested_entries_yield_candidate_series(self, panel):
        series = panel._candidate_series_from_history(HISTORY)
        assert series == {"epochs": [2, 3, 5], "losses": [0.7, 0.6, 0.4], "phases": ["candidate", "candidate", "candidate"]}

    def test_flat_entries_are_tolerated(self, panel):
        flat = [{"epoch": 1, "loss": 0.3, "cascade_phase": "candidate"}, {"epoch": 2, "train_loss": 0.2, "cascade_phase": "Candidate"}]
        series = panel._candidate_series_from_history(flat)
        assert series["epochs"] == [1, 2]
        assert series["losses"] == [0.3, 0.2]

    @pytest.mark.parametrize("history", [None, [], {}, "nope", [{"epoch": 1, "metrics": {"loss": 0.1}, "phase": "output"}], [{"epoch": None, "metrics": {"loss": 0.1}, "phase": "candidate"}], [{"epoch": 1, "metrics": {"loss": None}, "phase": "candidate"}], [{"epoch": 1, "metrics": {"loss": True}, "phase": "candidate"}]])
    def test_nothing_to_plot_is_an_empty_dict(self, panel, history):
        assert panel._candidate_series_from_history(history) == {}


@pytest.mark.unit
class TestLossPlotCallback:
    def test_real_state_plus_history_renders_the_candidate_trace(self, callbacks):
        fig = callbacks["update_loss_plot"](REAL_STATE, "light", HISTORY)
        assert isinstance(fig, go.Figure)
        assert len(fig.data) == 1
        assert fig.data[0].name == "Candidate Training"
        assert list(fig.data[0].x) == [2, 3, 5]
        assert list(fig.data[0].y) == [0.7, 0.6, 0.4]

    def test_real_state_without_history_is_still_the_placeholder(self, callbacks):
        # The parent's behaviour, kept as the fallback: /api/state alone has nothing to plot.
        fig = callbacks["update_loss_plot"](REAL_STATE, "light", None)
        assert len(fig.data) == 0

    def test_state_shape_fallback_still_works(self, callbacks):
        state = {"epochs": [1, 2], "losses": [0.5, 0.4], "phases": ["candidate", "candidate"]}
        fig = callbacks["update_loss_plot"](state, "dark", [])
        assert len(fig.data) == 1

    def test_history_wins_over_state_when_both_present(self, callbacks):
        state = {"epochs": [9], "losses": [9.9], "phases": ["candidate"]}
        fig = callbacks["update_loss_plot"](state, "light", HISTORY)
        assert list(fig.data[0].x) == [2, 3, 5]
