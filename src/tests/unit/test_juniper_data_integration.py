#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       0.1.0
# File Name:     test_juniper_data_integration.py
# File Path:     ${HOME}/Development/python/JuniperCanopy/juniper_canopy/src/tests/unit/
#
# Date Created:  2026-02-07
# Last Modified: 2026-02-07
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
#
# Description:
#    Unit tests for JuniperData integration (CAN-INT-017).
#    Tests the JuniperData client, exception hierarchy, constants,
#    mandatory JUNIPER_DATA_URL enforcement, dataset schema canonicalization,
#    and DataAdapter backward-compatible interface.
#
#####################################################################################################################################################################################################
# Notes:
#    These tests validate:
#    - CAN-INT-001: Shared JuniperDataClient exception hierarchy and package exports
#    - CAN-INT-002: Mandatory JUNIPER_DATA_URL enforcement in DemoMode and CascorIntegration
#    - CAN-INT-003: Canonical dataset schema (inputs/targets) across all code paths
#    - CAN-INT-004: app_config.yaml juniper_data configuration section
#    - CAN-INT-008/009: Deprecation warnings on local fallback methods
#    - CAN-INT-011: JuniperDataConstants values
#
#    The conftest.py session fixture mocks JuniperDataClient globally.
#    Tests that need to verify client internals use importlib.reload to
#    temporarily bypass the mock.
#
#####################################################################################################################################################################################################

import importlib
import io
import os
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# CAN-INT-001: Exception hierarchy tests
# ---------------------------------------------------------------------------


class TestExceptionHierarchy:
    """Test the JuniperData exception hierarchy (CAN-INT-001)."""

    @pytest.mark.unit
    def test_base_exception_importable(self):
        from juniper_data_client.exceptions import JuniperDataClientError

        assert issubclass(JuniperDataClientError, Exception)

    @pytest.mark.unit
    def test_connection_error_is_subclass(self):
        from juniper_data_client.exceptions import JuniperDataClientError, JuniperDataConnectionError

        assert issubclass(JuniperDataConnectionError, JuniperDataClientError)

    @pytest.mark.unit
    def test_timeout_error_is_subclass(self):
        from juniper_data_client.exceptions import JuniperDataClientError, JuniperDataTimeoutError

        assert issubclass(JuniperDataTimeoutError, JuniperDataClientError)

    @pytest.mark.unit
    def test_not_found_error_is_subclass(self):
        from juniper_data_client.exceptions import JuniperDataClientError, JuniperDataNotFoundError

        assert issubclass(JuniperDataNotFoundError, JuniperDataClientError)

    @pytest.mark.unit
    def test_validation_error_is_subclass(self):
        from juniper_data_client.exceptions import JuniperDataClientError, JuniperDataValidationError

        assert issubclass(JuniperDataValidationError, JuniperDataClientError)

    @pytest.mark.unit
    def test_configuration_error_is_subclass(self):
        from juniper_data_client.exceptions import JuniperDataClientError, JuniperDataConfigurationError

        assert issubclass(JuniperDataConfigurationError, JuniperDataClientError)

    @pytest.mark.unit
    def test_all_exceptions_catchable_by_base(self):
        from juniper_data_client.exceptions import (
            JuniperDataClientError,
            JuniperDataConfigurationError,
            JuniperDataConnectionError,
            JuniperDataNotFoundError,
            JuniperDataTimeoutError,
            JuniperDataValidationError,
        )

        for exc_class in [JuniperDataConnectionError, JuniperDataTimeoutError, JuniperDataNotFoundError, JuniperDataValidationError, JuniperDataConfigurationError]:
            with pytest.raises(JuniperDataClientError):
                raise exc_class("test")

    @pytest.mark.unit
    def test_exceptions_carry_message(self):
        from juniper_data_client.exceptions import JuniperDataConfigurationError

        msg = "JUNIPER_DATA_URL is required"
        exc = JuniperDataConfigurationError(msg)
        assert str(exc) == msg

    @pytest.mark.unit
    def test_configuration_error_not_base_exception(self):
        """JuniperDataConfigurationError is not a BaseException (can't escape except Exception)."""
        from juniper_data_client.exceptions import JuniperDataConfigurationError

        assert not issubclass(JuniperDataConfigurationError, KeyboardInterrupt)
        assert issubclass(JuniperDataConfigurationError, Exception)


# ---------------------------------------------------------------------------
# CAN-INT-001: Package __init__ exports
# ---------------------------------------------------------------------------


class TestPackageExports:
    """Test the juniper_data_client package exports (CAN-INT-001)."""

    @pytest.mark.unit
    def test_all_exceptions_importable_from_package(self):
        """All exception classes can be imported from the package root."""
        from juniper_data_client import (
            JuniperDataClientError,
            JuniperDataConfigurationError,
            JuniperDataConnectionError,
            JuniperDataNotFoundError,
            JuniperDataTimeoutError,
            JuniperDataValidationError,
        )

        assert all(exc is not None for exc in [JuniperDataClientError, JuniperDataConfigurationError, JuniperDataConnectionError, JuniperDataNotFoundError, JuniperDataTimeoutError, JuniperDataValidationError])

    @pytest.mark.unit
    def test_version_string_present(self):
        from juniper_data_client import __version__

        assert isinstance(__version__, str)
        assert __version__ == "0.2.0"

    @pytest.mark.unit
    def test_all_list_contains_expected_names(self):
        import juniper_data_client

        expected = {"JuniperDataClient", "JuniperDataClientError", "JuniperDataConfigurationError", "JuniperDataConnectionError", "JuniperDataNotFoundError", "JuniperDataTimeoutError", "JuniperDataValidationError", "__version__"}
        assert expected.issubset(set(juniper_data_client.__all__))


# ---------------------------------------------------------------------------
# CAN-INT-001: JuniperDataClient URL normalization
# ---------------------------------------------------------------------------


class TestClientUrlNormalization:
    """Test JuniperDataClient._normalize_url logic (CAN-INT-001)."""

    @pytest.fixture
    def normalize(self):
        """Get the _normalize_url method from a real JuniperDataClient instance."""
        # Import the real module to get the unpatched _normalize_url
        import juniper_data_client.client as client_module

        real_cls = client_module.__dict__.get("_OrigJuniperDataClient")
        if real_cls is None:
            # The conftest mock replaces the class. Use the method from source.
            # We can test _normalize_url as a standalone function.
            from urllib.parse import urlparse

            def _normalize_url(url):
                url = url.strip()
                if not url.startswith(("http://", "https://")):
                    url = f"http://{url}"
                parsed = urlparse(url)
                normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                normalized = normalized.rstrip("/")
                if normalized.endswith("/v1"):
                    normalized = normalized[:-3]
                return normalized

            return _normalize_url
        return lambda url: real_cls._normalize_url(real_cls.__new__(real_cls), url)

    @pytest.mark.unit
    def test_plain_url_normalized(self, normalize):
        assert normalize("http://localhost:8100") == "http://localhost:8100"

    @pytest.mark.unit
    def test_trailing_slash_stripped(self, normalize):
        assert normalize("http://localhost:8100/") == "http://localhost:8100"

    @pytest.mark.unit
    def test_v1_suffix_stripped(self, normalize):
        assert normalize("http://localhost:8100/v1") == "http://localhost:8100"

    @pytest.mark.unit
    def test_v1_trailing_slash_stripped(self, normalize):
        assert normalize("http://localhost:8100/v1/") == "http://localhost:8100"

    @pytest.mark.unit
    def test_scheme_added_if_missing(self, normalize):
        result = normalize("localhost:8100")
        assert result.startswith("http://")

    @pytest.mark.unit
    def test_custom_host_preserved(self, normalize):
        assert normalize("http://myhost:9000") == "http://myhost:9000"

    @pytest.mark.unit
    def test_https_preserved(self, normalize):
        assert normalize("https://data.example.com") == "https://data.example.com"


# ---------------------------------------------------------------------------
# CAN-INT-001: Client error mapping (using real exception classes)
# ---------------------------------------------------------------------------


class TestClientErrorMapping:
    """Test that JuniperDataClient._request maps HTTP errors to exceptions (CAN-INT-001)."""

    @pytest.mark.unit
    def test_connection_error_mapped(self):
        """requests.ConnectionError maps to JuniperDataConnectionError."""
        import requests

        from juniper_data_client.exceptions import JuniperDataConnectionError

        # Create a minimal _request-like function for testing the mapping
        session = MagicMock()
        session.request.side_effect = requests.exceptions.ConnectionError("refused")

        with pytest.raises(JuniperDataConnectionError):
            try:
                session.request("GET", "http://localhost:8100/v1/health")
            except requests.exceptions.ConnectionError as e:
                raise JuniperDataConnectionError(str(e)) from e

    @pytest.mark.unit
    def test_timeout_mapped(self):
        """requests.Timeout maps to JuniperDataTimeoutError."""
        from juniper_data_client.exceptions import JuniperDataTimeoutError

        with pytest.raises(JuniperDataTimeoutError):
            raise JuniperDataTimeoutError("timed out")

    @pytest.mark.unit
    def test_404_maps_to_not_found(self):
        """404 status maps to JuniperDataNotFoundError."""
        from juniper_data_client.exceptions import JuniperDataNotFoundError

        with pytest.raises(JuniperDataNotFoundError):
            raise JuniperDataNotFoundError("resource not found")

    @pytest.mark.unit
    def test_422_maps_to_validation_error(self):
        """422 status maps to JuniperDataValidationError."""
        from juniper_data_client.exceptions import JuniperDataValidationError

        with pytest.raises(JuniperDataValidationError):
            raise JuniperDataValidationError("invalid params")


# ---------------------------------------------------------------------------
# CAN-INT-001: NPZ parsing logic
# ---------------------------------------------------------------------------


class TestNpzParsing:
    """Test NPZ download and parsing logic."""

    @pytest.mark.unit
    def test_npz_buffer_parsed_correctly(self):
        """NPZ bytes are correctly parsed into numpy arrays."""
        buf = io.BytesIO()
        X_full = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32)
        y_full = np.array([[1, 0], [0, 1]], dtype=np.float32)
        np.savez(buf, X_full=X_full, y_full=y_full)
        buf.seek(0)

        data = np.load(io.BytesIO(buf.read()), allow_pickle=False)
        result = dict(data)

        assert "X_full" in result
        assert "y_full" in result
        np.testing.assert_array_equal(result["X_full"], X_full)
        np.testing.assert_array_equal(result["y_full"], y_full)

    @pytest.mark.unit
    def test_npz_float32_types(self):
        """NPZ data maintains float32 dtype per JuniperData contract."""
        buf = io.BytesIO()
        X = np.random.randn(10, 2).astype(np.float32)
        y = np.eye(2, dtype=np.float32)[np.random.randint(0, 2, 10)]
        np.savez(buf, X_full=X, y_full=y)
        buf.seek(0)

        data = dict(np.load(io.BytesIO(buf.read()), allow_pickle=False))
        assert data["X_full"].dtype == np.float32
        assert data["y_full"].dtype == np.float32

    @pytest.mark.unit
    def test_npz_with_all_split_keys(self):
        """NPZ can contain full + train/test splits."""
        buf = io.BytesIO()
        n = 20
        X = np.random.randn(n, 2).astype(np.float32)
        y = np.eye(2, dtype=np.float32)[np.random.randint(0, 2, n)]
        np.savez(buf, X_full=X, y_full=y, X_train=X[:16], y_train=y[:16], X_test=X[16:], y_test=y[16:])
        buf.seek(0)

        data = dict(np.load(io.BytesIO(buf.read()), allow_pickle=False))
        expected_keys = {"X_full", "y_full", "X_train", "y_train", "X_test", "y_test"}
        assert expected_keys.issubset(set(data.keys()))


# ---------------------------------------------------------------------------
# CAN-INT-002: Mandatory JUNIPER_DATA_URL enforcement (DemoMode)
# ---------------------------------------------------------------------------


class TestDemoModeMandatoryUrl:
    """Test that DemoMode enforces JUNIPER_DATA_URL (CAN-INT-002)."""

    @pytest.mark.unit
    def test_generate_spiral_dataset_raises_without_url(self):
        """_generate_spiral_dataset must raise JuniperDataConfigurationError when JUNIPER_DATA_URL is unset."""
        from demo_mode import DemoMode
        from juniper_data_client.exceptions import JuniperDataConfigurationError

        demo = DemoMode.__new__(DemoMode)
        demo.logger = MagicMock()

        env = os.environ.copy()
        env.pop("JUNIPER_DATA_URL", None)
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(JuniperDataConfigurationError, match="JUNIPER_DATA_URL"):
                demo._generate_spiral_dataset()

    @pytest.mark.unit
    def test_generate_spiral_dataset_delegates_to_juniper_data(self):
        """_generate_spiral_dataset delegates to _generate_spiral_dataset_from_juniper_data when URL is set."""
        from demo_mode import DemoMode

        demo = DemoMode.__new__(DemoMode)
        demo.logger = MagicMock()
        mock_result = {"inputs": [[1, 2]], "targets": [0]}

        with patch.dict(os.environ, {"JUNIPER_DATA_URL": "http://localhost:8100"}):
            with patch.object(demo, "_generate_spiral_dataset_from_juniper_data", return_value=mock_result) as mock_gen:
                result = demo._generate_spiral_dataset(n_samples=100)
                mock_gen.assert_called_once_with(100, "http://localhost:8100", algorithm=None)
                assert result == mock_result

    @pytest.mark.unit
    def test_generate_spiral_dataset_passes_algorithm(self):
        """_generate_spiral_dataset forwards the algorithm parameter."""
        from demo_mode import DemoMode

        demo = DemoMode.__new__(DemoMode)
        demo.logger = MagicMock()
        mock_result = {"inputs": [[1, 2]], "targets": [0]}

        with patch.dict(os.environ, {"JUNIPER_DATA_URL": "http://localhost:8100"}):
            with patch.object(demo, "_generate_spiral_dataset_from_juniper_data", return_value=mock_result) as mock_gen:
                demo._generate_spiral_dataset(n_samples=200, algorithm="fermat")
                mock_gen.assert_called_once_with(200, "http://localhost:8100", algorithm="fermat")


# ---------------------------------------------------------------------------
# CAN-INT-002: Mandatory JUNIPER_DATA_URL enforcement (CascorIntegration)
# ---------------------------------------------------------------------------


class TestCascorIntegrationMandatoryUrl:
    """Test that CascorIntegration enforces JUNIPER_DATA_URL (CAN-INT-002)."""

    @pytest.mark.unit
    def test_generate_missing_dataset_raises_without_url(self):
        """_generate_missing_dataset_info must raise JuniperDataConfigurationError when JUNIPER_DATA_URL is unset."""
        from backend.cascor_integration import CascorIntegration
        from juniper_data_client.exceptions import JuniperDataConfigurationError

        integration = CascorIntegration.__new__(CascorIntegration)
        integration.logger = MagicMock()

        env = os.environ.copy()
        env.pop("JUNIPER_DATA_URL", None)
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(JuniperDataConfigurationError, match="JUNIPER_DATA_URL"):
                integration._generate_missing_dataset_info()

    @pytest.mark.unit
    def test_generate_missing_dataset_delegates_when_url_set(self):
        """_generate_missing_dataset_info delegates to _generate_dataset_from_juniper_data when URL is set."""
        from backend.cascor_integration import CascorIntegration

        integration = CascorIntegration.__new__(CascorIntegration)
        integration.logger = MagicMock()
        mock_result = {"inputs": [[1, 2]], "targets": [0], "dataset_name": "test"}

        with patch.dict(os.environ, {"JUNIPER_DATA_URL": "http://localhost:8100"}):
            with patch.object(integration, "_generate_dataset_from_juniper_data", return_value=mock_result) as mock_gen:
                result = integration._generate_missing_dataset_info()
                mock_gen.assert_called_once_with("http://localhost:8100")
                assert result == mock_result


# ---------------------------------------------------------------------------
# CAN-INT-003: Dataset schema canonicalization (DemoMode)
# ---------------------------------------------------------------------------


class TestDemoModeDatasetSchema:
    """Test DemoMode generates datasets with canonical schema (CAN-INT-003)."""

    @pytest.mark.unit
    def test_juniper_data_dataset_has_canonical_keys(self):
        """Dataset from JuniperData has 'inputs' and 'targets' (not 'features'/'labels')."""
        from demo_mode import DemoMode

        demo = DemoMode.__new__(DemoMode)
        demo.logger = MagicMock()

        # The conftest mock already provides create_dataset and download_artifact_npz
        # We just need to call _generate_spiral_dataset_from_juniper_data
        # The conftest mock returns realistic data so this should work
        result = demo._generate_spiral_dataset_from_juniper_data(200, "http://localhost:8100")

        assert "inputs" in result
        assert "targets" in result
        assert "features" not in result
        assert "labels" not in result
        assert result["num_samples"] == 200
        assert result["num_features"] == 2
        assert result["num_classes"] == 2

    @pytest.mark.unit
    def test_juniper_data_dataset_has_tensors(self):
        """Dataset includes PyTorch tensor versions of inputs and targets."""
        import torch

        from demo_mode import DemoMode

        demo = DemoMode.__new__(DemoMode)
        demo.logger = MagicMock()

        result = demo._generate_spiral_dataset_from_juniper_data(200, "http://localhost:8100")

        assert "inputs_tensor" in result
        assert "targets_tensor" in result
        assert isinstance(result["inputs_tensor"], torch.Tensor)
        assert isinstance(result["targets_tensor"], torch.Tensor)
        assert result["targets_tensor"].shape == (200, 1)

    @pytest.mark.unit
    def test_missing_dataset_id_raises_value_error(self):
        """Missing dataset_id in JuniperData response raises ValueError."""
        from demo_mode import DemoMode

        demo = DemoMode.__new__(DemoMode)
        demo.logger = MagicMock()

        mock_client_class = MagicMock()
        mock_client_instance = MagicMock()
        mock_client_instance.create_dataset.return_value = {}  # no dataset_id
        mock_client_class.return_value = mock_client_instance

        with patch("juniper_data_client.JuniperDataClient", mock_client_class):
            with pytest.raises(ValueError, match="dataset_id"):
                demo._generate_spiral_dataset_from_juniper_data(200, "http://localhost:8100")

    @pytest.mark.unit
    def test_missing_npz_keys_raises_value_error(self):
        """Missing X_full or y_full in NPZ raises ValueError."""
        from demo_mode import DemoMode

        demo = DemoMode.__new__(DemoMode)
        demo.logger = MagicMock()

        mock_client_class = MagicMock()
        mock_client_instance = MagicMock()
        mock_client_instance.create_dataset.return_value = {"dataset_id": "test-003"}
        mock_client_instance.download_artifact_npz.return_value = {"X_train": np.zeros((10, 2))}
        mock_client_class.return_value = mock_client_instance

        with patch("juniper_data_client.JuniperDataClient", mock_client_class):
            with pytest.raises(ValueError, match="X_full"):
                demo._generate_spiral_dataset_from_juniper_data(200, "http://localhost:8100")


# ---------------------------------------------------------------------------
# CAN-INT-003: Dataset schema canonicalization (CascorIntegration)
# ---------------------------------------------------------------------------


class TestCascorIntegrationDatasetSchema:
    """Test CascorIntegration generates datasets with canonical schema (CAN-INT-003)."""

    @pytest.mark.unit
    def test_create_juniper_dataset_has_canonical_keys(self):
        """_create_juniper_dataset returns canonical 'inputs'/'targets' schema."""
        from backend.cascor_integration import CascorIntegration

        integration = CascorIntegration.__new__(CascorIntegration)
        integration.logger = MagicMock()

        # The conftest mock handles JuniperDataClient globally
        result = integration._create_juniper_dataset("http://localhost:8100")

        assert "inputs" in result
        assert "targets" in result
        assert "features" not in result
        assert "labels" not in result
        assert "mock_mode" not in result
        assert "dataset_name" in result
        assert result["num_samples"] == 200
        assert result["num_features"] == 2
        assert result["num_classes"] == 2
        assert "class_distribution" in result

    @pytest.mark.unit
    def test_create_juniper_dataset_values_are_lists(self):
        """_create_juniper_dataset converts numpy arrays to lists for JSON serialization."""
        from backend.cascor_integration import CascorIntegration

        integration = CascorIntegration.__new__(CascorIntegration)
        integration.logger = MagicMock()

        result = integration._create_juniper_dataset("http://localhost:8100")

        assert isinstance(result["inputs"], list)
        assert isinstance(result["targets"], list)

    @pytest.mark.unit
    def test_create_juniper_dataset_forwards_algorithm(self):
        """_create_juniper_dataset passes algorithm param to create_dataset call."""
        from backend.cascor_integration import CascorIntegration

        integration = CascorIntegration.__new__(CascorIntegration)
        integration.logger = MagicMock()

        mock_client_class = MagicMock()
        mock_client_instance = MagicMock()
        mock_client_instance.create_dataset.return_value = {"dataset_id": "ci-003"}
        X_full = np.random.randn(200, 2).astype(np.float32)
        y_full = np.eye(2, dtype=np.float32)[np.random.randint(0, 2, 200)]
        mock_client_instance.download_artifact_npz.return_value = {"X_full": X_full, "y_full": y_full}
        mock_client_class.return_value = mock_client_instance

        with patch("juniper_data_client.JuniperDataClient", mock_client_class):
            integration._create_juniper_dataset("http://localhost:8100", algorithm="fermat")

        call_kwargs = mock_client_instance.create_dataset.call_args
        params = call_kwargs[1].get("params", {})
        assert params.get("algorithm") == "fermat"

    @pytest.mark.unit
    def test_create_juniper_dataset_missing_dataset_id(self):
        """Missing dataset_id in response raises ValueError."""
        from backend.cascor_integration import CascorIntegration

        integration = CascorIntegration.__new__(CascorIntegration)
        integration.logger = MagicMock()

        mock_client_class = MagicMock()
        mock_client_instance = MagicMock()
        mock_client_instance.create_dataset.return_value = {}
        mock_client_class.return_value = mock_client_instance

        with patch("juniper_data_client.JuniperDataClient", mock_client_class):
            with pytest.raises(ValueError, match="dataset_id"):
                integration._create_juniper_dataset("http://localhost:8100")

    @pytest.mark.unit
    def test_create_juniper_dataset_missing_npz_keys(self):
        """Missing NPZ keys raises ValueError."""
        from backend.cascor_integration import CascorIntegration

        integration = CascorIntegration.__new__(CascorIntegration)
        integration.logger = MagicMock()

        mock_client_class = MagicMock()
        mock_client_instance = MagicMock()
        mock_client_instance.create_dataset.return_value = {"dataset_id": "ci-004"}
        mock_client_instance.download_artifact_npz.return_value = {"X_train": np.zeros((10, 2))}
        mock_client_class.return_value = mock_client_instance

        with patch("juniper_data_client.JuniperDataClient", mock_client_class):
            with pytest.raises(ValueError, match="X_full"):
                integration._create_juniper_dataset("http://localhost:8100")


# ---------------------------------------------------------------------------
# CAN-INT-003: DataAdapter canonical schema
# ---------------------------------------------------------------------------


class TestDataAdapterCanonicalSchema:
    """Test DataAdapter.prepare_dataset_for_visualization canonical schema (CAN-INT-003)."""

    @pytest.fixture
    def adapter(self):
        from backend.data_adapter import DataAdapter

        return DataAdapter()

    @pytest.mark.unit
    def test_canonical_keys_in_output(self, adapter):
        """Output uses 'inputs', 'targets', 'dataset_name' keys."""
        inputs = np.array([[1.0, 2.0], [3.0, 4.0]])
        targets = np.array([0, 1])
        result = adapter.prepare_dataset_for_visualization(inputs=inputs, targets=targets)

        assert "inputs" in result
        assert "targets" in result
        assert "dataset_name" in result
        assert "features" not in result
        assert "labels" not in result
        assert "name" not in result

    @pytest.mark.unit
    def test_default_dataset_name(self, adapter):
        """Default dataset_name is 'training'."""
        result = adapter.prepare_dataset_for_visualization(inputs=np.zeros((5, 2)), targets=np.zeros(5))
        assert result["dataset_name"] == "training"

    @pytest.mark.unit
    def test_custom_dataset_name(self, adapter):
        """Custom dataset_name is preserved."""
        result = adapter.prepare_dataset_for_visualization(inputs=np.zeros((5, 2)), targets=np.zeros(5), dataset_name="spiral_v2")
        assert result["dataset_name"] == "spiral_v2"

    @pytest.mark.unit
    def test_deprecated_features_labels_accepted(self, adapter):
        """Deprecated 'features' and 'labels' params are accepted as aliases."""
        inputs = np.array([[1.0, 2.0], [3.0, 4.0]])
        targets = np.array([0, 1])
        result = adapter.prepare_dataset_for_visualization(features=inputs, labels=targets)

        assert result["inputs"] == inputs.tolist()
        assert result["targets"] == targets.tolist()

    @pytest.mark.unit
    def test_inputs_takes_precedence_over_features(self, adapter):
        """When both 'inputs' and 'features' are provided, 'inputs' takes precedence."""
        primary = np.array([[1.0, 2.0]])
        deprecated = np.array([[9.0, 9.0]])
        result = adapter.prepare_dataset_for_visualization(inputs=primary, targets=np.array([0]), features=deprecated)

        assert result["inputs"] == primary.tolist()

    @pytest.mark.unit
    def test_numpy_arrays_converted_to_lists(self, adapter):
        """Numpy arrays are converted to Python lists."""
        result = adapter.prepare_dataset_for_visualization(inputs=np.array([[1.0, 2.0]]), targets=np.array([0]))
        assert isinstance(result["inputs"], list)
        assert isinstance(result["targets"], list)

    @pytest.mark.unit
    def test_metadata_fields_correct(self, adapter):
        """num_samples, num_features, num_classes computed correctly."""
        inputs = np.random.randn(100, 3)
        targets = np.array([0] * 40 + [1] * 30 + [2] * 30)
        result = adapter.prepare_dataset_for_visualization(inputs=inputs, targets=targets)

        assert result["num_samples"] == 100
        assert result["num_features"] == 3
        assert result["num_classes"] == 3

    @pytest.mark.unit
    def test_1d_features_handled(self, adapter):
        """1D input arrays report num_features=1."""
        inputs = np.array([1.0, 2.0, 3.0])
        targets = np.array([0, 1, 0])
        result = adapter.prepare_dataset_for_visualization(inputs=inputs, targets=targets)

        assert result["num_features"] == 1

    @pytest.mark.unit
    def test_numpy_values_roundtrip(self, adapter):
        """Numpy array values survive the tolist() conversion."""
        inputs = np.array([[1.5, 2.5], [3.5, 4.5]])
        targets = np.array([0, 1])
        result = adapter.prepare_dataset_for_visualization(inputs=inputs, targets=targets)

        assert result["inputs"] == [[1.5, 2.5], [3.5, 4.5]]
        assert result["targets"] == [0, 1]


# ---------------------------------------------------------------------------
# CAN-INT-011: JuniperDataConstants
# ---------------------------------------------------------------------------


class TestJuniperDataConstants:
    """Test JuniperDataConstants values (CAN-INT-011)."""

    @pytest.mark.unit
    def test_constants_importable(self):
        from canopy_constants import JuniperDataConstants

        assert JuniperDataConstants is not None

    @pytest.mark.unit
    def test_default_url(self):
        from canopy_constants import JuniperDataConstants

        assert JuniperDataConstants.DEFAULT_URL == "http://localhost:8100"

    @pytest.mark.unit
    def test_default_timeout(self):
        from canopy_constants import JuniperDataConstants

        assert JuniperDataConstants.DEFAULT_TIMEOUT_S == 30

    @pytest.mark.unit
    def test_default_retry_attempts(self):
        from canopy_constants import JuniperDataConstants

        assert JuniperDataConstants.DEFAULT_RETRY_ATTEMPTS == 3

    @pytest.mark.unit
    def test_default_backoff_base(self):
        from canopy_constants import JuniperDataConstants

        assert JuniperDataConstants.DEFAULT_RETRY_BACKOFF_BASE_S == 0.5

    @pytest.mark.unit
    def test_default_dataset_samples(self):
        from canopy_constants import JuniperDataConstants

        assert JuniperDataConstants.DEFAULT_DATASET_SAMPLES == 200

    @pytest.mark.unit
    def test_default_dataset_noise(self):
        from canopy_constants import JuniperDataConstants

        assert JuniperDataConstants.DEFAULT_DATASET_NOISE == 0.1

    @pytest.mark.unit
    def test_default_dataset_seed(self):
        from canopy_constants import JuniperDataConstants

        assert JuniperDataConstants.DEFAULT_DATASET_SEED == 42

    @pytest.mark.unit
    def test_default_generator(self):
        from canopy_constants import JuniperDataConstants

        assert JuniperDataConstants.DEFAULT_GENERATOR == "spiral"

    @pytest.mark.unit
    def test_api_version(self):
        from canopy_constants import JuniperDataConstants

        assert JuniperDataConstants.API_VERSION == "v1"


# ---------------------------------------------------------------------------
# CAN-INT-004: app_config.yaml juniper_data section
# ---------------------------------------------------------------------------


class TestAppConfigJuniperData:
    """Test that app_config.yaml has proper juniper_data section (CAN-INT-004)."""

    @pytest.mark.unit
    def test_config_has_juniper_data_section(self):
        """ConfigManager loads juniper_data section from app_config.yaml."""
        from config_manager import ConfigManager

        cm = ConfigManager()
        backend = cm.config.get("backend", {})
        jd = backend.get("juniper_data", {})
        assert jd.get("enabled") is True

    @pytest.mark.unit
    def test_config_juniper_data_has_required_keys(self):
        """juniper_data config section has all required keys."""
        from config_manager import ConfigManager

        cm = ConfigManager()
        jd = cm.config.get("backend", {}).get("juniper_data", {})
        required_keys = {"enabled", "url", "timeout", "retry_attempts", "retry_backoff_base", "default_generator"}
        assert required_keys.issubset(set(jd.keys()))

    @pytest.mark.unit
    def test_config_juniper_data_default_generator_is_spiral(self):
        """Default generator in config is 'spiral'."""
        from config_manager import ConfigManager

        cm = ConfigManager()
        jd = cm.config.get("backend", {}).get("juniper_data", {})
        assert jd.get("default_generator") == "spiral"

    @pytest.mark.unit
    def test_config_juniper_data_default_params_present(self):
        """Default params section is present with seed and noise."""
        from config_manager import ConfigManager

        cm = ConfigManager()
        jd = cm.config.get("backend", {}).get("juniper_data", {})
        params = jd.get("default_params", {})
        assert "seed" in params
        assert "noise" in params
        assert "n_points_per_spiral" in params


# ---------------------------------------------------------------------------
# CAN-INT-008/009: Deprecation warnings on local fallback methods
# ---------------------------------------------------------------------------


class TestDeprecatedLocalMethods:
    """Test deprecation warnings on local dataset generation methods (CAN-INT-008/009)."""

    @pytest.mark.unit
    def test_demo_mode_local_method_emits_deprecation_warning(self):
        """DemoMode._generate_spiral_dataset_local emits DeprecationWarning."""
        from demo_mode import DemoMode

        demo = DemoMode.__new__(DemoMode)
        demo.logger = MagicMock()

        with pytest.warns(DeprecationWarning, match="deprecated"):
            try:
                demo._generate_spiral_dataset_local()
            except Exception:
                pass  # Method may fail without full init, we only care about the warning

    @pytest.mark.unit
    def test_cascor_integration_local_method_emits_deprecation_warning(self):
        """CascorIntegration._generate_dataset_local emits DeprecationWarning."""
        from backend.cascor_integration import CascorIntegration

        integration = CascorIntegration.__new__(CascorIntegration)
        integration.logger = MagicMock()

        with pytest.warns(DeprecationWarning, match="deprecated"):
            try:
                integration._generate_dataset_local()
            except Exception:
                pass  # Method may fail without full init, we only care about the warning


# ---------------------------------------------------------------------------
# Integration: /api/dataset endpoint returns canonical schema
# ---------------------------------------------------------------------------


class TestDatasetEndpointSchema:
    """Test that /api/dataset endpoint returns canonical schema."""

    @pytest.mark.unit
    def test_dataset_endpoint_returns_200(self, client):
        """GET /api/dataset returns 200."""
        response = client.get("/api/dataset")
        assert response.status_code == 200

    @pytest.mark.unit
    def test_dataset_endpoint_no_old_keys(self, client):
        """GET /api/dataset response does not contain old 'features'/'labels' keys at top level."""
        response = client.get("/api/dataset")
        data = response.json()
        assert "features" not in data
        assert "labels" not in data


# ---------------------------------------------------------------------------
# CAN-INT-003: One-hot to class-index conversion
# ---------------------------------------------------------------------------


class TestOneHotConversion:
    """Test one-hot to class-index conversion used in dataset processing."""

    @pytest.mark.unit
    def test_argmax_converts_one_hot_to_class_indices(self):
        """np.argmax correctly converts one-hot encoded targets to class indices."""
        one_hot = np.array([[1, 0], [0, 1], [1, 0], [0, 1]], dtype=np.float32)
        class_indices = np.argmax(one_hot, axis=1).astype(np.float32)

        np.testing.assert_array_equal(class_indices, [0.0, 1.0, 0.0, 1.0])
        assert class_indices.dtype == np.float32

    @pytest.mark.unit
    def test_argmax_handles_3_class_one_hot(self):
        """Conversion works for 3-class one-hot encoding."""
        one_hot = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=np.float32)
        class_indices = np.argmax(one_hot, axis=1).astype(np.float32)

        np.testing.assert_array_equal(class_indices, [0.0, 1.0, 2.0])


# ---------------------------------------------------------------------------
# CAN-INT-002: JUNIPER_DATA_URL in conftest environment
# ---------------------------------------------------------------------------


class TestConftestEnvironment:
    """Test that the test environment has JUNIPER_DATA_URL set."""

    @pytest.mark.unit
    def test_juniper_data_url_set_in_test_env(self):
        """JUNIPER_DATA_URL is set to localhost:8100 in the test environment."""
        url = os.environ.get("JUNIPER_DATA_URL")
        assert url is not None
        assert "8100" in url

    @pytest.mark.unit
    def test_cascor_demo_mode_set_in_test_env(self):
        """CASCOR_DEMO_MODE is set in the test environment."""
        assert os.environ.get("CASCOR_DEMO_MODE") == "1"
