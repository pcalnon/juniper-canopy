"""
Integration tests for Meta Parameters API endpoints.

Tests the /api/set_params and /api/state endpoints with the expanded
meta-parameter payload (nn_* and cn_* prefixed keys).
"""

import pytest

from backend.training_monitor import TrainingState
from demo_mode import DemoMode


@pytest.fixture
def training_state():
    return TrainingState()


@pytest.fixture
def demo_mode():
    demo = DemoMode(update_interval=0.1)
    yield demo
    if demo.is_running:
        demo.stop()


class TestSetParamsNewPayload:
    """Test /api/set_params with new nn_/cn_ prefixed keys."""

    @pytest.mark.asyncio
    async def test_set_params_with_nn_keys(self, client):
        response = client.post(
            "/api/set_params",
            json={
                "nn_learning_rate": 0.05,
                "nn_max_hidden_units": 500,
                "nn_max_total_epochs": 500000,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

    @pytest.mark.asyncio
    async def test_set_params_with_cn_keys(self, client):
        response = client.post(
            "/api/set_params",
            json={
                "cn_pool_size": 200,
                "cn_correlation_threshold": 0.01,
                "cn_selected_candidates": 3,
            },
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_set_params_accepts_previously_dropped_params(self, client):
        """#2b: nn_output_epochs / nn_optimizer_type / nn_activation_function_name
        were silently dropped by SetParamsRequest before reaching the adapter
        (which maps them). They're now accepted and forwarded — a payload of only
        these three is recognized (200), not rejected as 'no parameters'."""
        response = client.post(
            "/api/set_params",
            json={
                "nn_output_epochs": 7,
                "nn_optimizer_type": "adam",
                "nn_activation_function_name": "relu",
            },
        )
        assert response.status_code == 200
        assert response.json()["status"] == "success"

    @pytest.mark.asyncio
    async def test_set_params_full_payload(self, client):
        response = client.post(
            "/api/set_params",
            json={
                "nn_max_iterations": 2000,
                "nn_max_total_epochs": 500000,
                "nn_learning_rate": 0.05,
                "nn_max_hidden_units": 500,
                "nn_multi_node_layers": True,
                "nn_growth_trigger": "preset_epochs",
                "nn_growth_preset_epochs": 100,
                "nn_growth_convergence_threshold": 0.01,
                "nn_spiral_rotations": 2.0,
                "nn_spiral_number": 3,
                "nn_dataset_elements": 2000,
                "nn_dataset_noise": 0.5,
                "cn_pool_size": 200,
                "cn_correlation_threshold": 0.01,
                "cn_selected_candidates": 3,
                "cn_training_complete": "convergence",
                "cn_training_iterations": 1000,
                "cn_training_convergence_threshold": 0.001,
                "cn_multi_candidate": True,
                "cn_candidate_selection": "top_tier",
                "cn_top_candidates": 5,
                "cn_random_candidates": 3,
            },
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_set_params_rejects_empty(self, client):
        response = client.post("/api/set_params", json={})
        assert response.status_code == 400


class TestSetParamsBackwardCompat:
    """Test /api/set_params accepts old-style keys."""

    @pytest.mark.asyncio
    async def test_old_style_learning_rate(self, client):
        response = client.post(
            "/api/set_params",
            json={"learning_rate": 0.025},
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_old_style_max_epochs(self, client):
        response = client.post(
            "/api/set_params",
            json={"max_epochs": 5000},
        )
        assert response.status_code == 200


class TestDemoModeApplyParams:
    """Test DemoMode.apply_params() accepts new parameters."""

    def test_apply_nn_params(self, demo_mode):
        demo_mode.apply_params(
            nn_max_iterations=2000,
            nn_learning_rate=0.05,
            nn_max_hidden_units=500,
        )

    def test_apply_cn_params(self, demo_mode):
        demo_mode.apply_params(
            cn_pool_size=200,
            cn_correlation_threshold=0.01,
        )

    def test_apply_mixed_params(self, demo_mode):
        demo_mode.apply_params(
            nn_learning_rate=0.05,
            cn_pool_size=200,
            nn_growth_trigger="preset_epochs",
        )
