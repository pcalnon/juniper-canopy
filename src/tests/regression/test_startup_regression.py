#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       1.0.0
# File Name:     test_startup_regression.py
# File Path:     src/tests/regression/
#
# Created Date:  2026-02-09
# Last Modified: 2026-02-09
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#     Regression tests for the JuniperCanopy startup failure caused by the
#     JuniperData integration refactor.
#
#####################################################################################################################################################################################################
# Notes:
#     ST-1, ST-5, ST-6 rely on conftest.py which sets JUNIPER_DATA_URL and
#     mocks JuniperDataClient globally. Only ST-2 and ST-3 need to
#     monkeypatch away the env var and mock ConfigManager.
#
#####################################################################################################################################################################################################
# References:
#     CAN-INT-002: Mandatory JUNIPER_DATA_URL enforcement
#
#####################################################################################################################################################################################################
# TODO :
#
#####################################################################################################################################################################################################
# COMPLETED:
#     ST-1 through ST-6 initial implementation
#
#####################################################################################################################################################################################################
"""Regression tests for JuniperCanopy startup failure caused by JuniperData integration refactor."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from demo_mode import DemoMode


@pytest.mark.regression
@pytest.mark.unit
class TestStartupRegression:
    """Regression tests for startup failure caused by JuniperData integration refactor."""

    def test_demo_mode_init_with_juniper_data_url_set(self):
        """ST-1: DemoMode initialises when JUNIPER_DATA_URL is set (via conftest)."""
        demo = DemoMode(update_interval=1.0)
        assert demo.dataset is not None
        assert "inputs_tensor" in demo.dataset
        assert "targets_tensor" in demo.dataset

    def test_demo_mode_init_without_juniper_data_url_falls_back_to_local(self, monkeypatch):
        """ST-2: DemoMode falls back to local dataset generation when JUNIPER_DATA_URL is missing."""
        monkeypatch.delenv("JUNIPER_DATA_URL", raising=False)

        mock_settings = MagicMock()
        mock_settings.juniper_data_url = ""
        mock_settings.demo_update_interval = 1.0
        mock_settings.demo_cascade_every = 30
        mock_settings.get_training_defaults.return_value = {}

        with patch("demo_mode.get_settings", return_value=mock_settings):
            demo = DemoMode(update_interval=1.0)
            # Should succeed via local fallback instead of raising
            assert demo.dataset is not None
            assert "inputs_tensor" in demo.dataset
            assert "targets_tensor" in demo.dataset

    def test_demo_mode_init_with_settings_default(self, monkeypatch):
        """ST-3: DemoMode uses Settings default juniper_data_url when env var is absent."""
        monkeypatch.delenv("JUNIPER_DATA_URL", raising=False)

        # Settings always provides a default juniper_data_url, so DemoMode should init fine
        demo = DemoMode(update_interval=1.0)
        assert demo.dataset is not None

    def test_app_startup_with_mocked_juniper_data(self):
        """ST-5: FastAPI app starts and /health returns 200."""
        from fastapi.testclient import TestClient

        from main import app

        with TestClient(app) as client:
            assert client.get("/health").status_code == 200

    def test_demo_mode_dataset_has_correct_schema(self):
        """ST-6: DemoMode dataset contains all required keys."""
        demo = DemoMode(update_interval=1.0)
        expected_keys = {
            "inputs",
            "targets",
            "inputs_tensor",
            "targets_tensor",
            "num_samples",
            "num_features",
            "num_classes",
        }
        assert expected_keys.issubset(demo.dataset.keys())

    def test_regenerate_dataset_falls_back_to_local_on_juniper_data_error(self):
        """ST-7: regenerate_dataset() falls back to local generation when JuniperData fails."""
        demo = DemoMode(update_interval=1.0)
        fallback_dataset = demo.dataset

        # Seed non-default state to verify reset behavior still occurs on fallback.
        demo.current_epoch = 12
        demo.current_loss = 0.25
        demo.current_accuracy = 0.85
        with demo._lock:
            demo.metrics_history.append({"epoch": 12, "loss": 0.25})

        with patch.object(demo, "_generate_spiral_dataset", side_effect=RuntimeError("service unavailable")) as mock_remote:
            with patch.object(demo, "_generate_spiral_dataset_local", return_value=fallback_dataset) as mock_local:
                result = demo.regenerate_dataset(n_samples=50, n_rotations=2.5)

        mock_remote.assert_called_once_with(n_samples=50, n_rotations=2.5)
        mock_local.assert_called_once_with(n_samples=50)
        assert result is fallback_dataset
        assert demo.network.train_x is fallback_dataset["inputs_tensor"]
        assert demo.network.train_y is fallback_dataset["targets_tensor"]
        assert demo.current_epoch == 0
        assert demo.current_loss == 1.0
        assert demo.current_accuracy == 0.5
        assert len(demo.metrics_history) == 0

    def test_apply_params_spiral_rotations_falls_back_to_local(self):
        """ST-8: apply_params() local fallback is used when spiral rotation regeneration fails."""
        demo = DemoMode(update_interval=1.0)
        fallback_dataset = demo.dataset

        # Add state/history that should be reset when dataset regeneration runs.
        demo.network.add_hidden_unit()
        demo.current_epoch = 7
        with demo._lock:
            demo.metrics_history.append({"epoch": 7, "loss": 0.4})

        with patch.object(demo, "_generate_spiral_dataset", side_effect=RuntimeError("timeout")) as mock_remote:
            with patch.object(demo, "_generate_spiral_dataset_local", return_value=fallback_dataset) as mock_local:
                demo.apply_params(spiral_rotations=3.0)

        mock_remote.assert_called_once_with(n_samples=200, n_rotations=3.0)
        mock_local.assert_called_once_with(n_samples=200)
        assert demo.spiral_rotations == 3.0
        assert demo.network.train_x is fallback_dataset["inputs_tensor"]
        assert demo.network.train_y is fallback_dataset["targets_tensor"]
        assert demo.current_epoch == 0
        assert len(demo.metrics_history) == 0
        assert len(demo.network.hidden_units) == 0

    def test_juniper_data_create_dataset_call_uses_compatible_kwargs(self):
        """ST-9: JuniperData create_dataset() call avoids unsupported legacy kwargs."""
        demo = DemoMode.__new__(DemoMode)
        demo.logger = MagicMock()

        npz_data = {
            "X_full": np.zeros((20, 2), dtype=np.float32),
            "y_full": np.eye(2, dtype=np.float32)[np.arange(20) % 2],
            "X_train": np.zeros((16, 2), dtype=np.float32),
            "y_train": np.eye(2, dtype=np.float32)[np.arange(16) % 2],
            "X_test": np.zeros((4, 2), dtype=np.float32),
            "y_test": np.eye(2, dtype=np.float32)[np.arange(4) % 2],
        }

        mock_client_instance = MagicMock()
        mock_client_instance.create_dataset.return_value = {"dataset_id": "smoke-dataset-001"}
        mock_client_instance.download_artifact_npz.return_value = npz_data

        with patch("juniper_data_client.JuniperDataClient", return_value=mock_client_instance):
            result = demo._generate_spiral_dataset_from_juniper_data(
                n_samples=20,
                juniper_data_url="http://localhost:8100",
                n_rotations=2.0,
            )

        assert result["num_samples"] == 20
        assert mock_client_instance.create_dataset.call_count == 1
        _, kwargs = mock_client_instance.create_dataset.call_args
        assert kwargs["generator"] == "spiral"
        assert kwargs["persist"] is True
        assert "name" not in kwargs
        assert "created_by" not in kwargs
