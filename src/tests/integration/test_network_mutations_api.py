#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# File Name:     test_network_mutations_api.py
# Author:        Paul Calnon
# Date:          2026-05-03
# License:       MIT License
# Description:   Integration tests for the canopy network-mutation
#                proxy routes (Phase 6E CAN-015h, h-5).
#####################################################################
"""Integration tests for the canopy network-mutation proxy routes.

The routes themselves are thin pass-throughs to the cascor service
adapter — these tests verify:

- Body schemas accept the documented shape.
- Demo mode (no service adapter wired) returns 501 with a clear
  message, mirroring the snapshot-replay/resume/retrain pattern.
- The DELETE route accepts an integer index in the path.
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

src_dir = Path(__file__).parents[2]
sys.path.insert(0, str(src_dir))

os.environ["JUNIPER_CANOPY_DEMO_MODE"] = "1"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def service_client(monkeypatch):
    """TestClient with the global backend mocked as a live service adapter."""
    import main

    adapter = MagicMock()
    backend = MagicMock()
    backend.backend_type = "service"
    backend._adapter = adapter

    with TestClient(app) as test_client:
        monkeypatch.setattr(main, "backend", backend)
        yield test_client, adapter


# =============================================================================
# Body validation — fires before the demo-mode adapter check
# =============================================================================


class TestBodyValidation:
    @pytest.mark.integration
    def test_patch_weights_missing_target_is_422(self, client):
        response = client.patch(
            "/api/v1/network/weights",
            json={"field": "weights", "values": [0.1, 0.2]},
        )
        assert response.status_code == 422

    @pytest.mark.integration
    def test_patch_weights_missing_field_is_422(self, client):
        response = client.patch(
            "/api/v1/network/weights",
            json={"target": "output_weights", "values": [0.1, 0.2]},
        )
        assert response.status_code == 422

    @pytest.mark.integration
    def test_patch_weights_missing_values_is_422(self, client):
        response = client.patch(
            "/api/v1/network/weights",
            json={"target": "output_weights", "field": "weights"},
        )
        assert response.status_code == 422

    @pytest.mark.integration
    def test_add_hidden_unit_missing_weights_is_422(self, client):
        response = client.post("/api/v1/network/hidden-units", json={"bias": 0.0})
        assert response.status_code == 422

    @pytest.mark.integration
    def test_remove_hidden_unit_non_integer_idx_is_422(self, client):
        response = client.delete("/api/v1/network/hidden-units/not-an-int")
        assert response.status_code == 422


# =============================================================================
# Demo mode — well-formed body, no live cascor backend
# =============================================================================


class TestDemoModeReturns501:
    @pytest.mark.integration
    def test_patch_weights_demo_mode_returns_501(self, client):
        response = client.patch(
            "/api/v1/network/weights",
            json={
                "target": "output_weights",
                "field": "weights",
                "values": [0.1, 0.2, 0.3],
            },
        )
        assert response.status_code == 501
        detail = response.json().get("detail", "")
        assert "cascor" in detail.lower()

    @pytest.mark.integration
    def test_add_hidden_unit_demo_mode_returns_501(self, client):
        response = client.post(
            "/api/v1/network/hidden-units",
            json={"weights": [0.1, 0.2], "bias": 0.0, "activation": "Tanh"},
        )
        assert response.status_code == 501
        detail = response.json().get("detail", "")
        assert "cascor" in detail.lower()

    @pytest.mark.integration
    def test_remove_hidden_unit_demo_mode_returns_501(self, client):
        response = client.delete("/api/v1/network/hidden-units/0")
        assert response.status_code == 501
        detail = response.json().get("detail", "")
        assert "cascor" in detail.lower()


# =============================================================================
# Defaults applied by the body schema
# =============================================================================


class TestSchemaDefaults:
    """Verify the BaseModel defaults make optional fields actually optional."""

    @pytest.mark.integration
    def test_patch_weights_dtype_defaults(self, client):
        # No dtype field — body should still validate (defaults to float32).
        response = client.patch(
            "/api/v1/network/weights",
            json={"target": "output_weights", "field": "weights", "values": [0.1]},
        )
        # Body validates; demo mode then returns 501 from
        # _require_service_adapter rather than 422.
        assert response.status_code == 501

    @pytest.mark.integration
    def test_add_hidden_unit_bias_and_activation_default(self, client):
        response = client.post("/api/v1/network/hidden-units", json={"weights": [0.1, 0.2]})
        assert response.status_code == 501


# =============================================================================
# Service-mode proxying — exact adapter contract
# =============================================================================


class TestServiceModeProxying:
    """Verify live service-mode routes forward the exact editor payload."""

    @pytest.mark.integration
    def test_patch_weights_forwards_all_fields_to_adapter(self, service_client):
        client, adapter = service_client
        adapter.patch_weights.return_value = {
            "operation": "patch_weights",
            "target": "hidden_unit_weights",
            "updated": True,
        }

        response = client.patch(
            "/api/v1/network/weights",
            json={
                "target": "hidden_unit_weights",
                "field": "weights",
                "values": [0.1, -0.2, 0.3],
                "hidden_unit_index": 2,
            },
        )

        assert response.status_code == 200
        assert response.json()["operation"] == "patch_weights"
        adapter.patch_weights.assert_called_once_with(
            target="hidden_unit_weights",
            field="weights",
            values=[0.1, -0.2, 0.3],
            hidden_unit_index=2,
            dtype="float32",
        )

    @pytest.mark.integration
    def test_add_hidden_unit_defaults_forward_to_adapter(self, service_client):
        client, adapter = service_client
        adapter.add_hidden_unit.return_value = {"unit_index": 0, "num_hidden_units": 1}

        response = client.post("/api/v1/network/hidden-units", json={"weights": [0.25, 0.5]})

        assert response.status_code == 200
        assert response.json()["num_hidden_units"] == 1
        adapter.add_hidden_unit.assert_called_once_with(
            weights=[0.25, 0.5],
            bias=0.0,
            activation="Tanh",
        )

    @pytest.mark.integration
    def test_remove_hidden_unit_forwards_path_index(self, service_client):
        client, adapter = service_client
        adapter.remove_hidden_unit.return_value = {"removed_index": 4, "num_hidden_units": 4}

        response = client.delete("/api/v1/network/hidden-units/4")

        assert response.status_code == 200
        assert response.json()["removed_index"] == 4
        adapter.remove_hidden_unit.assert_called_once_with(idx=4)

    @pytest.mark.integration
    def test_adapter_failure_returns_route_specific_500(self, service_client):
        client, adapter = service_client
        adapter.patch_weights.side_effect = RuntimeError("cascor rejected invalid shape")

        response = client.patch(
            "/api/v1/network/weights",
            json={"target": "output_weights", "field": "weights", "values": [0.1]},
        )

        assert response.status_code == 500
        assert "patch_weights failed" in response.json()["detail"]
        assert "invalid shape" in response.json()["detail"]
