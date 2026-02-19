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

from unittest.mock import MagicMock, patch

import pytest
from juniper_data_client.exceptions import JuniperDataConfigurationError

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

    def test_demo_mode_init_without_juniper_data_url_raises(self, monkeypatch):
        """ST-2: DemoMode raises JuniperDataConfigurationError when URL is missing."""
        monkeypatch.delenv("JUNIPER_DATA_URL", raising=False)

        mock_cm = MagicMock()
        mock_cm.config = {}
        mock_cm.get_training_defaults.return_value = {}

        with patch("demo_mode.ConfigManager", return_value=mock_cm):
            with pytest.raises(JuniperDataConfigurationError, match="JUNIPER_DATA_URL"):
                DemoMode(update_interval=1.0)

    def test_demo_mode_init_with_config_fallback(self, monkeypatch):
        """ST-3: DemoMode uses config fallback when env var is absent."""
        monkeypatch.delenv("JUNIPER_DATA_URL", raising=False)

        mock_cm = MagicMock()
        mock_cm.config = {"backend": {"juniper_data": {"url": "http://localhost:8100"}}}
        mock_cm.get_training_defaults.return_value = {}

        with patch("demo_mode.ConfigManager", return_value=mock_cm):
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
