"""
Layout structure tests for convergence UI controls.

Verifies that the required UI components exist in the dashboard layout
with correct default values, IDs, and configuration.
"""

import pytest

from canopy_constants import TrainingConstants


def _find_component_by_id(layout, target_id):
    """Recursively search layout for a component with the given id."""
    if hasattr(layout, "id") and layout.id == target_id:
        return layout
    children = getattr(layout, "children", None)
    if children is None:
        return None
    if not isinstance(children, (list, tuple)):
        children = [children]
    for child in children:
        if child is None:
            continue
        result = _find_component_by_id(child, target_id)
        if result is not None:
            return result
    return None


@pytest.mark.unit
class TestConvergenceLayoutComponents:
    """Verify convergence UI components exist with correct configuration."""

    def test_growth_trigger_radio_exists(self, reset_singletons):
        """Growth trigger radio exists with correct ID."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})
        radio = _find_component_by_id(manager.app.layout, "nn-growth-trigger-radio")
        assert radio is not None, "nn-growth-trigger-radio not found"

    def test_convergence_threshold_input_exists(self, reset_singletons):
        """Convergence threshold input exists with correct min/max/step/default."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})
        inp = _find_component_by_id(manager.app.layout, "nn-growth-convergence-threshold-input")
        assert inp is not None, "nn-growth-convergence-threshold-input not found"
        assert inp.value == TrainingConstants.DEFAULT_CONVERGENCE_THRESHOLD
        assert inp.min == TrainingConstants.MIN_CONVERGENCE_THRESHOLD
        assert inp.max == TrainingConstants.MAX_CONVERGENCE_THRESHOLD
        assert inp.step == 0.0001

    def test_apply_button_exists(self, reset_singletons):
        """Apply button exists with correct ID."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})
        btn = _find_component_by_id(manager.app.layout, "apply-params-button")
        assert btn is not None, "apply-params-button not found"

    def test_applied_params_store_exists(self, reset_singletons):
        """applied-params-store exists with empty initial data."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})
        store = _find_component_by_id(manager.app.layout, "applied-params-store")
        assert store is not None, "applied-params-store not found"
        assert store.data == {}, f"Expected empty dict, got {store.data}"

    def test_params_init_interval_exists_with_max_intervals_1(self, reset_singletons):
        """params-init-interval exists with max_intervals=1."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})
        interval = _find_component_by_id(manager.app.layout, "params-init-interval")
        assert interval is not None, "params-init-interval not found"
        assert interval.max_intervals == 1

    def test_spiral_rotations_input_exists(self, reset_singletons):
        """Spiral rotations input exists with correct defaults."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})
        inp = _find_component_by_id(manager.app.layout, "nn-spiral-rotations-input")
        assert inp is not None, "nn-spiral-rotations-input not found"
        assert inp.value == TrainingConstants.DEFAULT_SPIRAL_ROTATIONS
        assert inp.min == TrainingConstants.MIN_SPIRAL_ROTATIONS
        assert inp.max == TrainingConstants.MAX_SPIRAL_ROTATIONS

    def test_params_status_div_exists(self, reset_singletons):
        """params-status div exists for status messages."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})
        div = _find_component_by_id(manager.app.layout, "params-status")
        assert div is not None, "params-status not found"

    def test_learning_rate_input_exists(self, reset_singletons):
        """Learning rate input exists with correct ID."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})
        inp = _find_component_by_id(manager.app.layout, "nn-learning-rate-input")
        assert inp is not None, "nn-learning-rate-input not found"
