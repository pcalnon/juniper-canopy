"""
Unit tests for Meta Parameters layout verification.

Validates that the Meta Parameters card (replacing Training Parameters) contains
all expected component IDs with correct default values, types, and structure.
"""

import pytest
from dash import Dash

from canopy_constants import TrainingConstants
from frontend.dashboard_manager import DashboardManager


def _find_component_by_id(layout, component_id):
    """Recursively search layout tree for a component with the given ID."""
    if hasattr(layout, "id") and layout.id == component_id:
        return layout
    children = getattr(layout, "children", None)
    if children is None:
        return None
    if not isinstance(children, (list, tuple)):
        children = [children]
    for child in children:
        if child is not None:
            result = _find_component_by_id(child, component_id)
            if result is not None:
                return result
    return None


def _find_text_in_layout(layout, text):
    """Recursively search layout tree for text content."""
    if isinstance(layout, str) and text in layout:
        return True
    children = getattr(layout, "children", None)
    if children is None:
        return False
    if isinstance(children, str) and text in children:
        return True
    if not isinstance(children, (list, tuple)):
        children = [children]
    for child in children:
        if child is not None and _find_text_in_layout(child, text):
            return True
    return False


@pytest.fixture
def dashboard():
    dm = DashboardManager.__new__(DashboardManager)
    dm.logger = __import__("logging").getLogger("test")
    dm._settings = __import__("settings").get_settings()
    dm.training_defaults = dm._settings.get_training_defaults()
    dm.app = Dash(__name__, suppress_callback_exceptions=True)
    dm.components = []
    dm.metrics_panel = type("Mock", (), {"get_layout": lambda self: None})()
    dm.candidate_metrics_panel = type("Mock", (), {"get_layout": lambda self: None})()
    dm.network_visualizer = type("Mock", (), {"get_layout": lambda self: None})()
    dm.network_evolution = type("Mock", (), {"get_layout": lambda self: None})()
    dm.decision_boundary = type("Mock", (), {"get_layout": lambda self: None})()
    dm.dataset_plotter = type("Mock", (), {"get_layout": lambda self: None})()
    dm.hdf5_snapshots_panel = type("Mock", (), {"get_layout": lambda self: None})()
    # Phase 6E Sprint B B-6 (CAN-015f): replay player panel.
    dm.replay_player_panel = type("Mock", (), {"get_layout": lambda self: None})()
    dm.redis_panel = type("Mock", (), {"get_layout": lambda self: None})()
    dm.cassandra_panel = type("Mock", (), {"get_layout": lambda self: None})()
    dm.about_panel = type("Mock", (), {"get_layout": lambda self: None})()
    dm.parameters_panel = type("Mock", (), {"get_layout": lambda self: None})()
    dm.tutorial_panel = type("Mock", (), {"get_layout": lambda self: None})()
    dm.worker_panel = type("Mock", (), {"get_layout": lambda self: None})()
    # Phase 6E CAN-015h-5: surgical network-editor panel for restored snapshots.
    dm.network_editor_panel = type("Mock", (), {"get_layout": lambda self: None})()
    dm._setup_layout()
    return dm


class TestMetaParametersCardStructure:
    """Test the top-level Meta Parameters card structure."""

    def test_card_header_says_meta_parameters(self, dashboard):
        assert _find_text_in_layout(dashboard.app.layout, "Meta Parameters")

    def test_no_training_parameters_label(self, dashboard):
        assert not _find_text_in_layout(dashboard.app.layout, "Training Parameters")

    def test_nn_subsection_header_exists(self, dashboard):
        component = _find_component_by_id(dashboard.app.layout, "nn-subsection-header")
        assert component is not None

    def test_cn_subsection_header_exists(self, dashboard):
        component = _find_component_by_id(dashboard.app.layout, "cn-subsection-header")
        assert component is not None

    def test_nn_subsection_collapse_exists(self, dashboard):
        component = _find_component_by_id(dashboard.app.layout, "nn-subsection-collapse")
        assert component is not None
        assert component.is_open is True

    def test_cn_subsection_collapse_exists(self, dashboard):
        component = _find_component_by_id(dashboard.app.layout, "cn-subsection-collapse")
        assert component is not None
        assert component.is_open is False

    def test_apply_button_exists(self, dashboard):
        component = _find_component_by_id(dashboard.app.layout, "apply-params-button")
        assert component is not None
        assert component.disabled is True

    def test_params_status_exists(self, dashboard):
        component = _find_component_by_id(dashboard.app.layout, "params-status")
        assert component is not None


class TestNeuralNetworkInputs:
    """Test all Neural Network subsection inputs exist with correct defaults."""

    def test_max_iterations_input(self, dashboard):
        c = _find_component_by_id(dashboard.app.layout, "nn-max-iterations-input")
        assert c is not None
        assert c.type == "number"

    def test_max_total_epochs_input(self, dashboard):
        c = _find_component_by_id(dashboard.app.layout, "nn-max-total-epochs-input")
        assert c is not None
        assert c.type == "number"

    def test_learning_rate_input(self, dashboard):
        c = _find_component_by_id(dashboard.app.layout, "nn-learning-rate-input")
        assert c is not None
        assert c.type == "number"

    def test_max_hidden_units_input(self, dashboard):
        c = _find_component_by_id(dashboard.app.layout, "nn-max-hidden-units-input")
        assert c is not None
        assert c.type == "number"

    def test_multi_node_layers_checkbox(self, dashboard):
        c = _find_component_by_id(dashboard.app.layout, "nn-multi-node-layers-checkbox")
        assert c is not None
        assert c.value == []

    def test_growth_trigger_radio(self, dashboard):
        c = _find_component_by_id(dashboard.app.layout, "nn-growth-trigger-radio")
        assert c is not None
        assert c.value == "convergence"
        assert len(c.options) == 2

    def test_growth_preset_epochs_input(self, dashboard):
        c = _find_component_by_id(dashboard.app.layout, "nn-growth-preset-epochs-input")
        assert c is not None
        assert c.disabled is True

    def test_growth_convergence_threshold_input(self, dashboard):
        c = _find_component_by_id(dashboard.app.layout, "nn-growth-convergence-threshold-input")
        assert c is not None
        assert c.disabled is False

    def test_spiral_rotations_input(self, dashboard):
        c = _find_component_by_id(dashboard.app.layout, "nn-spiral-rotations-input")
        assert c is not None
        assert c.value == TrainingConstants.DEFAULT_SPIRAL_ROTATIONS

    def test_spiral_number_input(self, dashboard):
        c = _find_component_by_id(dashboard.app.layout, "nn-spiral-number-input")
        assert c is not None
        assert c.value == TrainingConstants.DEFAULT_SPIRAL_NUMBER

    def test_dataset_elements_input(self, dashboard):
        c = _find_component_by_id(dashboard.app.layout, "nn-dataset-elements-input")
        assert c is not None
        assert c.value == TrainingConstants.DEFAULT_DATASET_ELEMENTS

    def test_dataset_noise_input(self, dashboard):
        c = _find_component_by_id(dashboard.app.layout, "nn-dataset-noise-input")
        assert c is not None
        assert c.value == TrainingConstants.DEFAULT_DATASET_NOISE


class TestCandidateNodesInputs:
    """Test all Candidate Nodes subsection inputs exist with correct defaults."""

    def test_pool_size_input(self, dashboard):
        c = _find_component_by_id(dashboard.app.layout, "cn-pool-size-input")
        assert c is not None
        assert c.value == TrainingConstants.DEFAULT_CANDIDATE_POOL_SIZE

    def test_correlation_threshold_input(self, dashboard):
        c = _find_component_by_id(dashboard.app.layout, "cn-correlation-threshold-input")
        assert c is not None
        assert c.value == TrainingConstants.DEFAULT_CANDIDATE_CORRELATION_THRESHOLD

    def test_selected_candidates_input(self, dashboard):
        c = _find_component_by_id(dashboard.app.layout, "cn-selected-candidates-input")
        assert c is not None
        assert c.value == TrainingConstants.DEFAULT_SELECTED_CANDIDATES

    def test_training_complete_radio(self, dashboard):
        c = _find_component_by_id(dashboard.app.layout, "cn-training-complete-radio")
        assert c is not None
        assert c.value == "preset_epochs"

    def test_training_iterations_input(self, dashboard):
        c = _find_component_by_id(dashboard.app.layout, "cn-training-iterations-input")
        assert c is not None
        assert c.disabled is False

    def test_training_convergence_threshold_input(self, dashboard):
        c = _find_component_by_id(dashboard.app.layout, "cn-training-convergence-threshold-input")
        assert c is not None
        assert c.disabled is True

    def test_multi_candidate_checkbox(self, dashboard):
        c = _find_component_by_id(dashboard.app.layout, "cn-multi-candidate-checkbox")
        assert c is not None
        assert c.value == []

    def test_candidate_selection_radio(self, dashboard):
        c = _find_component_by_id(dashboard.app.layout, "cn-candidate-selection-radio")
        assert c is not None
        assert c.value is None

    def test_top_candidates_input(self, dashboard):
        c = _find_component_by_id(dashboard.app.layout, "cn-top-candidates-input")
        assert c is not None
        assert c.disabled is True

    def test_random_candidates_input(self, dashboard):
        c = _find_component_by_id(dashboard.app.layout, "cn-random-candidates-input")
        assert c is not None
        assert c.disabled is True


class TestOldComponentIDsRemoved:
    """Verify that old component IDs no longer exist in the layout."""

    @pytest.mark.parametrize(
        "old_id",
        [
            "learning-rate-input",
            "max-hidden-units-input",
            "max-epochs-input",
            "convergence-enabled-checkbox",
            "convergence-threshold-input",
            "spiral-rotations-input",
        ],
    )
    def test_old_id_removed(self, dashboard, old_id):
        assert _find_component_by_id(dashboard.app.layout, old_id) is None
