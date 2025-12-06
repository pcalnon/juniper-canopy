#!/usr/bin/env python
"""
Integration tests for parameter persistence (Issue #4).

Tests verify that learning rate and max hidden units parameters:
1. Persist after being changed
2. Don't reset to defaults after several seconds
3. Are respected by the training system
4. Don't cause echo loops or oscillation
"""
import asyncio
import time

import pytest

from backend.training_monitor import TrainingState
from demo_mode import DemoMode


class TestParameterPersistence:
    """Test suite for parameter persistence across system components."""

    def test_training_state_persists_learning_rate(self):
        """Test that TrainingState persists learning_rate updates."""
        state = TrainingState()

        # Set learning rate
        state.update_state(learning_rate=0.05)

        # Verify it persists
        assert state.get_state()["learning_rate"] == 0.05

        # Wait and verify it hasn't changed
        time.sleep(1)
        assert state.get_state()["learning_rate"] == 0.05

    def test_training_state_persists_max_hidden_units(self):
        """Test that TrainingState persists max_hidden_units updates."""
        state = TrainingState()

        # Set max hidden units
        state.update_state(max_hidden_units=15)

        # Verify it persists
        assert state.get_state()["max_hidden_units"] == 15

        # Wait and verify it hasn't changed
        time.sleep(1)
        assert state.get_state()["max_hidden_units"] == 15

    def test_training_state_no_oscillation(self):
        """Test that rapid parameter changes don't cause oscillation."""
        state = TrainingState()

        # Rapidly change learning rate
        for lr in [0.01, 0.02, 0.03, 0.04, 0.05]:
            state.update_state(learning_rate=lr)
            time.sleep(0.1)

        # Final value should be last one set
        assert state.get_state()["learning_rate"] == 0.05

        # Wait and verify stability
        time.sleep(2)
        assert state.get_state()["learning_rate"] == 0.05

    def test_demo_mode_applies_learning_rate(self):
        """Test that DemoMode applies learning_rate parameter."""
        demo = DemoMode(update_interval=1.0)

        # Apply learning rate
        demo.apply_params(learning_rate=0.025)

        # Verify it's applied to network
        assert demo.network.learning_rate == 0.025

        # Wait and verify it persists
        time.sleep(1)
        assert demo.network.learning_rate == 0.025

    def test_demo_mode_applies_max_hidden_units(self):
        """Test that DemoMode applies max_hidden_units parameter."""
        demo = DemoMode(update_interval=1.0)

        # Apply max hidden units
        demo.apply_params(max_hidden_units=5)

        # Verify it's applied
        assert demo.max_hidden_units == 5

        # Wait and verify it persists
        time.sleep(1)
        assert demo.max_hidden_units == 5

    def test_demo_mode_respects_max_hidden_units_constraint(self):
        """Test that DemoMode respects max_hidden_units when adding cascade units."""
        demo = DemoMode(update_interval=0.1)

        # Set low max hidden units
        demo.apply_params(max_hidden_units=2)

        # Manually add hidden units up to limit
        demo.network.add_hidden_unit()
        demo.network.add_hidden_unit()

        # Should not allow more units
        with demo._lock:
            current_units = len(demo.network.hidden_units)
        assert current_units == 2

        # _should_add_cascade_unit should return False
        assert not demo._should_add_cascade_unit()

    def test_parameter_persistence_during_training(self):
        """Test that parameters persist during active training simulation."""
        demo = DemoMode(update_interval=0.2)

        # Set parameters before starting
        demo.apply_params(learning_rate=0.03, max_hidden_units=3)

        # Start training
        demo.start(reset=True)

        # Let it run for a few epochs
        time.sleep(1)

        # Verify parameters haven't changed
        assert demo.network.learning_rate == 0.03
        assert demo.max_hidden_units == 3

        # Stop training
        demo.stop()

    def test_parameter_changes_while_training(self):
        """Test that parameters can be changed while training is active."""
        demo = DemoMode(update_interval=0.2)

        # Start training
        demo.start(reset=True)

        # Let it run
        time.sleep(0.5)

        # Change parameters mid-training
        demo.apply_params(learning_rate=0.07, max_hidden_units=4)

        # Verify changes applied immediately
        assert demo.network.learning_rate == 0.07
        assert demo.max_hidden_units == 4

        # Let training continue
        time.sleep(1)

        # Verify parameters still correct
        assert demo.network.learning_rate == 0.07
        assert demo.max_hidden_units == 4

        # Stop training
        demo.stop()

    def test_no_reset_to_defaults_after_10_seconds(self):
        """Test that parameters don't reset to defaults after 10+ seconds (Issue #4 core test)."""
        demo = DemoMode(update_interval=0.5)

        # Set non-default parameters
        demo.apply_params(learning_rate=0.0123, max_hidden_units=7)

        # Start training
        demo.start(reset=True)

        # Wait 11 seconds (longer than the reported reset time)
        time.sleep(11)

        # Verify parameters haven't reset to defaults
        assert demo.network.learning_rate == 0.0123, "Learning rate reset to default!"
        assert demo.max_hidden_units == 7, "Max hidden units reset to default!"

        # Stop training
        demo.stop()

    def test_training_state_echo_prevention(self):
        """Test that TrainingState updates don't cause echo loops."""
        state = TrainingState()

        # Track all state changes
        updates = []
        original_update = state.update_state

        def tracked_update(**kwargs):
            updates.append(kwargs.copy())
            original_update(**kwargs)

        state.update_state = tracked_update

        # Update learning rate
        state.update_state(learning_rate=0.04)

        # Wait a bit
        time.sleep(1)

        # Should only have one update, no echoes
        assert len(updates) == 1
        assert updates[0]["learning_rate"] == 0.04

    def test_multiple_parameters_update_atomically(self):
        # sourcery skip: extract-duplicate-method
        """Test that multiple parameters update together atomically."""
        state = TrainingState()

        # Update both parameters at once
        state.update_state(learning_rate=0.06, max_hidden_units=12)

        # Both should be updated
        current_state = state.get_state()
        assert current_state["learning_rate"] == 0.06
        assert current_state["max_hidden_units"] == 12

        # Wait and verify both persist
        time.sleep(1)
        current_state = state.get_state()
        assert current_state["learning_rate"] == 0.06
        assert current_state["max_hidden_units"] == 12


@pytest.mark.asyncio
async def test_api_set_params_integration():
    """Integration test for /api/set_params endpoint (requires running server)."""
    # This test requires a running server instance
    # Skip if server not available
    pytest.skip("Requires running server - run manually for full integration test")

    import httpx

    async with httpx.AsyncClient() as client:
        # Set parameters via API
        response = await client.post(
            "http://localhost:8050/api/set_params", json={"learning_rate": 0.08, "max_hidden_units": 6}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

        # Verify parameters persisted
        await asyncio.sleep(1)

        state_response = await client.get("http://localhost:8050/api/state")
        state_data = state_response.json()

        assert state_data["learning_rate"] == 0.08
        assert state_data["max_hidden_units"] == 6


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
