"""Tests for the Network Evolution component.

Covers the static helpers (delta, epoch label, mini-diagram) directly
since they're pure-functional, plus source-level invariants on the grid
layout, the dashboard store wiring, and the capture/clear clientside
callbacks. The capture callback is exercised in source rather than via
a real Dash app — Dash 3.x's clientside callbacks aren't trivially
testable without a browser, so we assert the JS source has the right
shape (de-dupe, ring bound, auto-clear) and rely on manual smoke for
runtime behavior.
"""

from pathlib import Path

import plotly.graph_objects as go
import pytest

pytestmark = pytest.mark.unit

_SRC = Path(__file__).resolve().parents[2]


@pytest.fixture
def evolution():
    from frontend.components.network_evolution import NetworkEvolution

    return NetworkEvolution({}, component_id="network-evolution")


@pytest.fixture
def NetworkEvolutionCls():
    from frontend.components.network_evolution import NetworkEvolution

    return NetworkEvolution


@pytest.fixture
def MAX_SNAPSHOTS():
    from frontend.components.network_evolution import MAX_SNAPSHOTS as cap

    return cap


@pytest.fixture
def dashboard_manager_source():
    return (_SRC / "frontend" / "dashboard_manager.py").read_text(encoding="utf-8")


@pytest.fixture
def evolution_source():
    return (_SRC / "frontend" / "components" / "network_evolution.py").read_text(encoding="utf-8")


class TestComponentInit:
    def test_component_id_default(self, evolution):
        assert evolution.component_id == "network-evolution"

    def test_layout_returns_div(self, evolution):
        layout = evolution.get_layout()
        assert layout.id == "network-evolution"

    def test_layout_has_grid_container(self, evolution_source):
        # IDs are built via f-string: f"{self.component_id}-grid-container"
        assert "-grid-container" in evolution_source

    def test_layout_has_clear_button(self, evolution_source):
        assert "-clear-btn" in evolution_source


class TestComputeDelta:
    """``_compute_delta`` is pure — drive directly."""

    def test_no_prior_returns_empty(self, NetworkEvolutionCls):
        assert NetworkEvolutionCls._compute_delta({"hidden_units": 5}, None) == ""

    def test_growth_returns_plus_n_units(self, NetworkEvolutionCls):
        assert NetworkEvolutionCls._compute_delta({"hidden_units": 5}, {"hidden_units": 3}) == "+2 units"

    def test_unchanged_returns_empty(self, NetworkEvolutionCls):
        assert NetworkEvolutionCls._compute_delta({"hidden_units": 4}, {"hidden_units": 4}) == ""

    def test_shrink_returns_negative_n_units(self, NetworkEvolutionCls):
        """Shouldn't normally happen during training, but the renderer
        shouldn't crash if it does — show the shrink as a negative delta."""
        assert NetworkEvolutionCls._compute_delta({"hidden_units": 3}, {"hidden_units": 5}) == "-2 units"

    def test_non_numeric_values_return_empty(self, NetworkEvolutionCls):
        assert NetworkEvolutionCls._compute_delta({"hidden_units": "x"}, {"hidden_units": 3}) == ""


class TestFormatEpochLabel:
    def test_integer_epoch(self, NetworkEvolutionCls):
        assert NetworkEvolutionCls._format_epoch_label({"epoch": 42}) == "Epoch 42"

    def test_zero_epoch_is_valid(self, NetworkEvolutionCls):
        assert NetworkEvolutionCls._format_epoch_label({"epoch": 0}) == "Epoch 0"

    def test_negative_epoch_falls_back(self, NetworkEvolutionCls):
        # Sentinel for "no epoch yet".
        out = NetworkEvolutionCls._format_epoch_label({"epoch": -1, "timestamp": 12345})
        assert out == "Captured"

    def test_no_epoch_with_timestamp(self, NetworkEvolutionCls):
        assert NetworkEvolutionCls._format_epoch_label({"timestamp": 12345}) == "Captured"

    def test_no_epoch_no_timestamp(self, NetworkEvolutionCls):
        assert NetworkEvolutionCls._format_epoch_label({}) == "—"


class TestMiniDiagram:
    """``_build_mini_diagram`` returns a Plotly Figure. We don't assert on
    pixel-perfect layout, just that it produces a valid figure with the
    expected high-level structure (markers + lines, hidden den/output
    dot rows present)."""

    def test_returns_figure(self, NetworkEvolutionCls):
        fig = NetworkEvolutionCls._build_mini_diagram({"input_units": 2, "hidden_units": 0, "output_units": 2}, "light")
        assert isinstance(fig, go.Figure)

    def test_zero_hidden_still_renders(self, NetworkEvolutionCls):
        """Initial snapshot has 0 hidden units — must still produce valid output."""
        fig = NetworkEvolutionCls._build_mini_diagram({"input_units": 2, "hidden_units": 0, "output_units": 2}, "light")
        # No exception, axes hidden, at least input + output marker traces.
        assert fig.layout.xaxis.visible is False
        assert fig.layout.yaxis.visible is False

    def test_with_hidden_units_adds_more_traces(self, NetworkEvolutionCls):
        no_hidden = NetworkEvolutionCls._build_mini_diagram({"input_units": 2, "hidden_units": 0, "output_units": 2}, "light")
        with_hidden = NetworkEvolutionCls._build_mini_diagram({"input_units": 2, "hidden_units": 5, "output_units": 2}, "light")
        # More hidden units → more connection lines + the hidden marker trace.
        assert len(with_hidden.data) > len(no_hidden.data)

    def test_caps_dot_count_for_legibility(self, NetworkEvolutionCls):
        """A network with 100 hidden units shouldn't try to draw 100 dots
        in a 120px-tall thumbnail. The component caps the visible dots
        and surfaces the real count via the text label below the card."""
        fig = NetworkEvolutionCls._build_mini_diagram({"input_units": 2, "hidden_units": 100, "output_units": 2}, "light")
        # Should not crash, should not produce thousands of traces.
        assert len(fig.data) < 500

    def test_dark_theme_uses_dark_background(self, NetworkEvolutionCls):
        fig = NetworkEvolutionCls._build_mini_diagram({"input_units": 2, "hidden_units": 1, "output_units": 2}, "dark")
        # paper_bgcolor is set as a string; dark theme chooses #2d2d2d.
        assert "2d2d2d" in str(fig.layout.paper_bgcolor).lower()


class TestRenderGridIntegration:
    """Drive ``_render_grid`` end-to-end. Returns (cards, stats_str)."""

    def test_empty_returns_empty_state(self, evolution):
        cards, stats = evolution._render_grid([], "light")
        assert stats == "No snapshots yet"
        assert cards.id == "network-evolution-empty-state"

    def test_with_snapshots_returns_cards_and_stat_count(self, evolution, MAX_SNAPSHOTS):
        snaps = [
            {"timestamp": 3, "epoch": 30, "input_units": 2, "hidden_units": 3, "output_units": 2},
            {"timestamp": 2, "epoch": 20, "input_units": 2, "hidden_units": 2, "output_units": 2},
            {"timestamp": 1, "epoch": 10, "input_units": 2, "hidden_units": 1, "output_units": 2},
        ]
        cards, stats = evolution._render_grid(snaps, "light")
        assert isinstance(cards, list)
        assert len(cards) == 3
        assert stats == f"Snapshots: 3 of {MAX_SNAPSHOTS} max"

    def test_dark_theme_propagates(self, evolution):
        snaps = [{"timestamp": 1, "epoch": 5, "input_units": 2, "hidden_units": 1, "output_units": 2}]
        cards, _ = evolution._render_grid(snaps, "dark")
        # First card's outer Div carries the dark background color.
        first = cards[0]
        assert "2d2d2d" in first.style.get("background", "").lower()


class TestDashboardManagerWiring:
    """Source-level invariants on the dashboard manager's stores and callbacks."""

    def test_evolution_tab_added(self, dashboard_manager_source):
        assert 'tab_id="evolution"' in dashboard_manager_source
        assert "Network Evolution" in dashboard_manager_source

    def test_snapshots_store_present(self, dashboard_manager_source):
        assert "evolution-snapshots-store" in dashboard_manager_source

    def test_capture_callback_dedupes_unchanged_snapshots(self, dashboard_manager_source):
        """The capture callback must skip when the head snapshot already has
        the same (input, hidden, output) tuple — otherwise every topology-
        store update would push a duplicate."""
        # Look for the de-dupe guard.
        assert "no_update" in dashboard_manager_source
        # The callback compares head's hidden_units with the incoming.
        assert "hidden_units|0" in dashboard_manager_source

    def test_capture_callback_bounds_to_max_snapshots(self, dashboard_manager_source, MAX_SNAPSHOTS):
        """The bound must come from MAX_SNAPSHOTS, not a magic number, so
        future tweaks stay in one place."""
        assert str(MAX_SNAPSHOTS) in dashboard_manager_source
        assert "slice(0, " in dashboard_manager_source

    def test_capture_callback_auto_clears_on_reset(self, dashboard_manager_source):
        """Auto-clear when input_units changes or hidden_units shrinks."""
        assert "input_units" in dashboard_manager_source
        # The literal "snaps = []" in the auto-clear branch.
        assert "snaps = []" in dashboard_manager_source

    def test_clear_button_callback_registered(self, dashboard_manager_source):
        assert "network-evolution-clear-btn" in dashboard_manager_source

    def test_component_imported_and_instantiated(self, dashboard_manager_source):
        assert "from .components.network_evolution import" in dashboard_manager_source
        assert "self.network_evolution = NetworkEvolution(" in dashboard_manager_source

    def test_component_registered(self, dashboard_manager_source):
        assert "self.register_component(self.network_evolution)" in dashboard_manager_source
