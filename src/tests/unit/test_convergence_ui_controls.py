"""
Tests for convergence-based cascade addition UI controls (Phase 5).

Verifies that:
- Convergence params have correct defaults
- apply_params() sets convergence params
- _should_add_cascade_unit() respects convergence_enabled toggle
- _should_add_cascade_unit() respects convergence_threshold
- Reset restores convergence defaults
"""

import threading
from collections import deque
from unittest.mock import MagicMock

import pytest
import torch

from canopy_constants import TrainingConstants
from demo_mode import DemoMode, MockCascorNetwork


def _make_demo():
    """Create a DemoMode-like object with minimal attributes for unit testing."""
    demo = DemoMode.__new__(DemoMode)
    demo.logger = MagicMock()
    demo._lock = threading.Lock()
    demo.network = MockCascorNetwork(input_size=2, output_size=1)
    demo.max_hidden_units = 10
    demo.cascade_every = 30
    demo.current_epoch = 15  # not at fixed interval
    demo.convergence_enabled = True
    demo.convergence_threshold = 0.001
    demo._cascade_cooldown_remaining = 0
    return demo


class TestConvergenceDefaults:
    """Verify convergence parameters have correct default values."""

    def test_convergence_enabled_by_default(self):
        """DemoMode initializes with convergence_enabled=True."""
        demo = DemoMode(update_interval=0.01)
        assert demo.convergence_enabled is True
        demo.stop()

    def test_convergence_threshold_default_value(self):
        """DemoMode initializes with convergence_threshold=0.001."""
        demo = DemoMode(update_interval=0.01)
        assert demo.convergence_threshold == TrainingConstants.DEFAULT_CONVERGENCE_THRESHOLD
        assert demo.convergence_threshold == 0.001
        demo.stop()

    def test_constants_defined(self):
        """TrainingConstants has convergence constants."""
        assert hasattr(TrainingConstants, "DEFAULT_CONVERGENCE_ENABLED")
        assert hasattr(TrainingConstants, "DEFAULT_CONVERGENCE_THRESHOLD")
        assert hasattr(TrainingConstants, "MIN_CONVERGENCE_THRESHOLD")
        assert hasattr(TrainingConstants, "MAX_CONVERGENCE_THRESHOLD")


class TestConvergenceApplyParams:
    """Verify apply_params() sets convergence parameters."""

    def test_apply_params_sets_convergence_enabled_false(self):
        """apply_params(convergence_enabled=False) disables convergence."""
        demo = DemoMode(update_interval=0.01)
        demo.apply_params(convergence_enabled=False)
        assert demo.convergence_enabled is False
        demo.stop()

    def test_apply_params_sets_convergence_enabled_true(self):
        """apply_params(convergence_enabled=True) enables convergence."""
        demo = DemoMode(update_interval=0.01)
        demo.apply_params(convergence_enabled=False)
        demo.apply_params(convergence_enabled=True)
        assert demo.convergence_enabled is True
        demo.stop()

    def test_apply_params_sets_convergence_threshold(self):
        """apply_params(convergence_threshold=0.01) updates threshold."""
        demo = DemoMode(update_interval=0.01)
        demo.apply_params(convergence_threshold=0.01)
        assert demo.convergence_threshold == 0.01
        demo.stop()

    def test_apply_params_clamps_threshold_high(self):
        """Threshold above MAX is clamped."""
        demo = DemoMode(update_interval=0.01)
        demo.apply_params(convergence_threshold=1.0)
        assert demo.convergence_threshold == TrainingConstants.MAX_CONVERGENCE_THRESHOLD
        demo.stop()

    def test_apply_params_clamps_threshold_low(self):
        """Threshold below MIN is clamped."""
        demo = DemoMode(update_interval=0.01)
        demo.apply_params(convergence_threshold=0.0)
        assert demo.convergence_threshold == TrainingConstants.MIN_CONVERGENCE_THRESHOLD
        demo.stop()

    def test_apply_params_none_does_not_change(self):
        """apply_params with None convergence params leaves defaults."""
        demo = DemoMode(update_interval=0.01)
        demo.apply_params(convergence_enabled=None, convergence_threshold=None)
        assert demo.convergence_enabled is True
        assert demo.convergence_threshold == 0.001
        demo.stop()


class TestConvergenceBehavior:
    """Verify _should_add_cascade_unit() respects convergence settings."""

    def test_disabled_convergence_uses_fixed_schedule_only(self):
        """With convergence disabled, only fixed schedule triggers addition."""
        demo = _make_demo()
        demo.convergence_enabled = False
        # Populate with stagnant loss (would trigger if enabled)
        for _ in range(15):
            demo.network.history["train_loss"].append(0.25)
        demo.current_epoch = 15  # not at fixed interval
        assert demo._should_add_cascade_unit() is False

    def test_disabled_convergence_ignores_plateau(self):
        """With convergence disabled, loss plateau does NOT trigger addition."""
        demo = _make_demo()
        demo.convergence_enabled = False
        for _ in range(15):
            demo.network.history["train_loss"].append(0.25)
        # Not at fixed interval
        demo.current_epoch = 7
        assert demo._should_add_cascade_unit() is False

    def test_enabled_convergence_fires_on_plateau(self):
        """With convergence enabled and loss plateau, unit is added."""
        demo = _make_demo()
        demo.convergence_enabled = True
        for _ in range(15):
            demo.network.history["train_loss"].append(0.25)
        demo.current_epoch = 15  # not at fixed interval
        assert demo._should_add_cascade_unit() is True

    def test_threshold_affects_sensitivity(self):
        """Higher threshold triggers earlier; lower threshold requires more stagnation."""
        demo = _make_demo()
        # Loss with small improvement (0.005 over 10 entries)
        for i in range(10):
            demo.network.history["train_loss"].append(0.255 - i * 0.0005)

        # With threshold 0.01, improvement 0.005 < 0.01 → triggers
        demo.convergence_threshold = 0.01
        assert demo._should_add_cascade_unit() is True

        # With threshold 0.001, improvement 0.005 > 0.001 → does not trigger
        demo.convergence_threshold = 0.001
        assert demo._should_add_cascade_unit() is False

    def test_convergence_requires_10_history_entries(self):
        """Convergence check requires at least 10 loss history entries."""
        demo = _make_demo()
        demo.convergence_enabled = True
        # Only 9 entries — not enough
        for _ in range(9):
            demo.network.history["train_loss"].append(0.25)
        demo.current_epoch = 7  # not at fixed interval
        assert demo._should_add_cascade_unit() is False

    def test_fixed_schedule_still_works_when_convergence_disabled(self):
        """Fixed schedule fallback works regardless of convergence setting."""
        demo = _make_demo()
        demo.convergence_enabled = False
        demo.current_epoch = 30  # at fixed interval
        assert demo._should_add_cascade_unit() is True


class TestConvergenceReset:
    """Verify reset restores convergence defaults."""

    def test_reset_restores_convergence_defaults(self):
        """_reset_state_and_history() restores convergence params to defaults."""
        demo = DemoMode(update_interval=0.01)
        demo.apply_params(convergence_enabled=False, convergence_threshold=0.05)
        assert demo.convergence_enabled is False
        assert demo.convergence_threshold == 0.05

        demo._reset_state_and_history()
        assert demo.convergence_enabled is True
        assert demo.convergence_threshold == TrainingConstants.DEFAULT_CONVERGENCE_THRESHOLD
        demo.stop()


class TestConvergenceState:
    """Verify convergence params appear in state output."""

    def test_get_current_state_includes_convergence(self):
        """get_current_state() includes convergence_enabled and convergence_threshold."""
        demo = DemoMode(update_interval=0.01)
        state = demo.get_current_state()
        assert "convergence_enabled" in state
        assert "convergence_threshold" in state
        assert state["convergence_enabled"] is True
        assert state["convergence_threshold"] == 0.001
        demo.stop()

    def test_get_current_state_reflects_changes(self):
        """get_current_state() reflects apply_params changes."""
        demo = DemoMode(update_interval=0.01)
        demo.apply_params(convergence_enabled=False, convergence_threshold=0.02)
        state = demo.get_current_state()
        assert state["convergence_enabled"] is False
        assert state["convergence_threshold"] == 0.02
        demo.stop()
