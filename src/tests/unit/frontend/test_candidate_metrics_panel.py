#!/usr/bin/env python
"""Tests for CandidateMetricsPanel component layout and helpers."""

import pytest
from dash import html

from frontend.components.candidate_metrics_panel import MAX_POOL_HISTORY_ENTRIES, CandidateMetricsPanel


@pytest.fixture
def panel():
    """Create a CandidateMetricsPanel instance for testing."""
    return CandidateMetricsPanel({}, component_id="candidate-metrics-panel")


class TestCandidateMetricsPanelInit:
    """Test component initialization."""

    def test_default_component_id(self):
        """Default component_id should be 'candidate-metrics-panel'."""
        panel = CandidateMetricsPanel({})
        assert panel.get_component_id() == "candidate-metrics-panel"

    def test_custom_component_id(self):
        """Should accept custom component_id."""
        panel = CandidateMetricsPanel({}, component_id="custom-id")
        assert panel.get_component_id() == "custom-id"

    def test_default_update_interval(self):
        """Default update interval should be 1000ms."""
        panel = CandidateMetricsPanel({})
        assert panel.update_interval == 1000

    def test_custom_update_interval(self):
        """Should accept update_interval from config."""
        panel = CandidateMetricsPanel({"update_interval": 2000})
        assert panel.update_interval == 2000

    def test_max_pool_history_entries_constant(self):
        """MAX_POOL_HISTORY_ENTRIES should be 20."""
        assert MAX_POOL_HISTORY_ENTRIES == 20


class TestCandidateMetricsPanelLayout:
    """Test get_layout() output."""

    def test_layout_returns_div(self, panel):
        """get_layout() should return an html.Div."""
        layout = panel.get_layout()
        assert isinstance(layout, html.Div)

    def test_layout_contains_status_badge(self, panel):
        """Layout should contain status badge component."""
        layout_str = str(panel.get_layout())
        assert "candidate-metrics-panel-status-badge" in layout_str

    def test_layout_contains_phase(self, panel):
        """Layout should contain phase display."""
        layout_str = str(panel.get_layout())
        assert "candidate-metrics-panel-phase" in layout_str

    def test_layout_contains_pool_size(self, panel):
        """Layout should contain pool size display."""
        layout_str = str(panel.get_layout())
        assert "candidate-metrics-panel-pool-size" in layout_str

    def test_layout_contains_epoch_progress(self, panel):
        """Layout should contain epoch progress bar."""
        layout_str = str(panel.get_layout())
        assert "candidate-metrics-panel-epoch-progress" in layout_str

    def test_layout_contains_loss_plot(self, panel):
        """Layout should contain loss plot."""
        layout_str = str(panel.get_layout())
        assert "candidate-metrics-panel-loss-plot" in layout_str

    def test_layout_contains_pool_info(self, panel):
        """Layout should contain pool info container."""
        layout_str = str(panel.get_layout())
        assert "candidate-metrics-panel-pool-info" in layout_str

    def test_layout_contains_history_section(self, panel):
        """Layout should contain history section."""
        layout_str = str(panel.get_layout())
        assert "candidate-metrics-panel-history-section" in layout_str

    def test_layout_contains_history_collapse(self, panel):
        """Layout should contain history collapse."""
        layout_str = str(panel.get_layout())
        assert "candidate-metrics-panel-history-collapse" in layout_str

    def test_layout_contains_training_state_store(self, panel):
        """Layout should contain training state store."""
        layout_str = str(panel.get_layout())
        assert "candidate-metrics-panel-training-state-store" in layout_str

    def test_layout_contains_pool_history_store(self, panel):
        """Layout should contain pool history store."""
        layout_str = str(panel.get_layout())
        assert "candidate-metrics-panel-pool-history-store" in layout_str

    def test_layout_contains_update_interval(self, panel):
        """Layout should contain update interval."""
        layout_str = str(panel.get_layout())
        assert "candidate-metrics-panel-update-interval" in layout_str


class TestCandidatePoolDisplay:
    """Test _create_candidate_pool_display method."""

    def test_creates_display_with_candidates(self, panel):
        """Should create display with top candidates and metrics."""
        state = {
            "candidate_pool_status": "Active",
            "candidate_pool_phase": "Training",
            "candidate_pool_size": 8,
            "top_candidate_id": "cand_001",
            "top_candidate_score": 0.85,
            "second_candidate_id": "cand_002",
            "second_candidate_score": 0.72,
            "pool_metrics": {
                "avg_loss": 0.3,
                "avg_accuracy": 0.85,
                "avg_precision": 0.82,
                "avg_recall": 0.88,
                "avg_f1_score": 0.85,
            },
        }
        display = panel._create_candidate_pool_display(state)
        assert isinstance(display, html.Div)

    def test_creates_display_without_candidates(self, panel):
        """Should handle state with no candidates."""
        state = {
            "candidate_pool_status": "Active",
            "candidate_pool_phase": "Idle",
            "candidate_pool_size": 0,
            "pool_metrics": {},
        }
        display = panel._create_candidate_pool_display(state)
        assert isinstance(display, html.Div)


class TestStatusStyle:
    """Test _get_status_style method."""

    def test_candidate_phase_yellow(self, panel):
        """Candidate phase should use yellow background."""
        style = panel._get_status_style("candidate_training")
        assert style["backgroundColor"] == "#ffc107"

    def test_output_phase_blue(self, panel):
        """Output phase should use blue background."""
        style = panel._get_status_style("output_training")
        assert style["backgroundColor"] == "#007bff"

    def test_complete_phase_green(self, panel):
        """Complete phase should use green background."""
        style = panel._get_status_style("complete")
        assert style["backgroundColor"] == "#28a745"

    def test_idle_phase_gray(self, panel):
        """Idle/unknown phase should use gray background."""
        style = panel._get_status_style("idle")
        assert style["backgroundColor"] == "#6c757d"


class TestEmptyPlot:
    """Test _create_empty_plot method."""

    def test_creates_figure(self, panel):
        """Should return a Plotly figure."""
        import plotly.graph_objects as go

        fig = panel._create_empty_plot()
        assert isinstance(fig, go.Figure)

    def test_has_annotation(self, panel):
        """Should have 'No candidate data available' annotation."""
        fig = panel._create_empty_plot()
        assert len(fig.layout.annotations) == 1
        assert "No candidate data" in fig.layout.annotations[0].text


class TestPoolHistory:
    """Test _render_pool_history method."""

    def test_empty_history_shows_message(self, panel):
        """Empty history should show placeholder message."""
        result = panel._render_pool_history([])
        assert len(result) == 1

    def test_none_history_shows_message(self, panel):
        """None history should show placeholder message."""
        result = panel._render_pool_history(None)
        assert len(result) == 1

    def test_renders_pool_cards(self, panel):
        """Should render a card for each historical pool."""
        history = [
            {
                "epoch": 100,
                "status": "Active",
                "phase": "Training",
                "size": 8,
                "top_candidate_id": "cand_001",
                "top_candidate_score": 0.85,
                "pool_metrics": {"avg_loss": 0.3, "avg_accuracy": 0.8},
            },
            {
                "epoch": 200,
                "status": "Active",
                "phase": "Complete",
                "size": 8,
                "top_candidate_id": "cand_003",
                "top_candidate_score": 0.92,
                "pool_metrics": {},
            },
        ]
        result = panel._render_pool_history(history)
        assert len(result) == 2


class TestCandidateLossFigure:
    """Test _create_candidate_loss_figure method."""

    def test_empty_state_returns_empty_plot(self, panel):
        """No state should return empty plot."""
        fig = panel._create_candidate_loss_figure(None)
        assert len(fig.data) == 0

    def test_no_candidate_data_returns_empty_plot(self, panel):
        """State without candidate phases should return empty plot."""
        state = {
            "epochs": [1, 2, 3],
            "losses": [0.5, 0.4, 0.3],
            "phases": ["output", "output", "output"],
        }
        fig = panel._create_candidate_loss_figure(state)
        assert len(fig.data) == 0

    def test_candidate_data_creates_trace(self, panel):
        """State with candidate phases should create orange trace."""
        state = {
            "epochs": [1, 2, 3, 4],
            "losses": [0.5, 0.4, 0.3, 0.35],
            "phases": ["output", "output", "candidate", "candidate"],
        }
        fig = panel._create_candidate_loss_figure(state)
        assert len(fig.data) == 1
        assert fig.data[0].name == "Candidate Training"
        assert fig.data[0].line.color == "#ff7f0e"
