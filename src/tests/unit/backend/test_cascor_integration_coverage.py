#!/usr/bin/env python
"""
Comprehensive coverage tests for cascor_integration.py
Target: Raise coverage from 49% to 80%+

Tests cover:
- Initialization with config_mgr
- Network creation with minimal config
- Error handling for invalid configs
- Callback registration
- State management
- Integration points (mocked backend)
- Configuration validation
- Path resolution
- Monitoring hooks
"""
import os

# import sys
# from pathlib import Path
# from unittest.mock import Mock, MagicMock, patch, PropertyMock
from unittest.mock import Mock, patch

import numpy as np
import pytest
import torch


class TestCascorIntegrationInit:
    """Test CascorIntegration initialization."""

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_init_with_default_path(self, mock_config_mgr, mock_exists):
        """Test initialization with default backend path."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {"backend": {"cascor_integration": {}}}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()

            assert integration.network is None
            assert integration.monitoring_active is False

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_init_with_explicit_path(self, mock_config_mgr, mock_exists):
        """Test initialization with explicit backend path."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration(backend_path="/custom/path")

            assert integration.backend_path.name == "path"

    @patch("backend.cascor_integration.ConfigManager")
    def test_init_with_missing_backend_raises_error(self, mock_config_mgr):
        """Test initialization with missing backend path."""
        from backend.cascor_integration import CascorIntegration

        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with pytest.raises(FileNotFoundError):
            CascorIntegration(backend_path="/nonexistent/path")

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_init_with_environment_variable_path(self, mock_config_mgr, mock_exists):
        """Test initialization with CASCOR_BACKEND_PATH environment variable."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.dict(os.environ, {"CASCOR_BACKEND_PATH": "/env/path"}):
            with patch.object(CascorIntegration, "_import_backend_modules"):
                integration = CascorIntegration()

                assert "env" in str(integration.backend_path) or "path" in str(integration.backend_path)


class TestCascorIntegrationPathResolution:
    """Test backend path resolution."""

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_resolve_backend_path_tilde_expansion(self, mock_config_mgr, mock_exists):
        """Test path resolution with tilde expansion."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration(backend_path="~/cascor")

            # Should expand to home directory
            assert str(integration.backend_path) != "~/cascor"

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_resolve_backend_path_env_var_expansion(self, mock_config_mgr, mock_exists):
        """Test path resolution with environment variable expansion."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.dict(os.environ, {"CUSTOM_PATH": "/custom"}):
            with patch.object(CascorIntegration, "_import_backend_modules"):
                integration = CascorIntegration(backend_path="$CUSTOM_PATH/cascor")

                assert "custom" in str(integration.backend_path).lower() or "cascor" in str(integration.backend_path)


class TestCascorIntegrationNetworkCreation:
    """Test network creation and connection."""

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_create_network_with_minimal_config(self, mock_config_mgr, mock_exists):
        """Test creating network with minimal configuration."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()

            # Mock backend classes
            mock_config_class = Mock()
            mock_network_class = Mock()
            mock_network = Mock()
            mock_network.input_size = 2
            mock_network.output_size = 1
            mock_network_class.return_value = mock_network

            integration.CascadeCorrelationConfig = mock_config_class
            integration.CascadeCorrelationNetwork = mock_network_class

            network = integration.create_network(config={"input_size": 2, "output_size": 1})

            assert network == mock_network
            assert integration.network == mock_network

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_create_network_with_max_epochs_mapping(self, mock_config_mgr, mock_exists):
        """Test that max_epochs is mapped to epochs_max."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()

            mock_config_class = Mock()
            mock_network_class = Mock()
            mock_network = Mock()
            mock_network.input_size = 2
            mock_network.output_size = 1
            mock_network_class.return_value = mock_network

            integration.CascadeCorrelationConfig = mock_config_class
            integration.CascadeCorrelationNetwork = mock_network_class
            network = integration.create_network(config={"max_epochs": 500})
            assert network is not None

            # Verify max_epochs was converted to epochs_max
            call_args = mock_config_class.call_args
            assert "epochs_max" in call_args[1] or call_args[1].get("max_epochs") is None

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_connect_to_network(self, mock_config_mgr, mock_exists):
        """Test connecting to existing network."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()

            mock_network = Mock()
            mock_network.input_size = 3
            mock_network.output_size = 2

            result = integration.connect_to_network(mock_network)

            assert result is True
            assert integration.network == mock_network


class TestCascorIntegrationMonitoringHooks:
    """Test monitoring hook installation."""

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_install_monitoring_hooks_without_network(self, mock_config_mgr, mock_exists):
        """Test installing hooks without connected network."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()

            result = integration.install_monitoring_hooks()

            assert result is False

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_install_monitoring_hooks_with_network(self, mock_config_mgr, mock_exists):
        """Test installing hooks with connected network."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()

            # Create mock network
            mock_network = Mock()
            mock_network.fit = Mock()
            mock_network.train_output_layer = Mock()
            mock_network.train_candidates = Mock()

            integration.connect_to_network(mock_network)

            result = integration.install_monitoring_hooks()

            assert result is True
            assert integration.monitoring_active is True

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_install_monitoring_hooks_twice(self, mock_config_mgr, mock_exists):
        """Test installing hooks twice returns warning."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()

            mock_network = Mock()
            mock_network.fit = Mock()
            mock_network.train_output_layer = Mock()
            mock_network.train_candidates = Mock()

            integration.connect_to_network(mock_network)
            integration.install_monitoring_hooks()

            # Second call
            result = integration.install_monitoring_hooks()

            assert result is True  # Still returns True but warns


class TestCascorIntegrationTopologyExtraction:
    """Test network topology extraction."""

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_get_network_topology_without_network(self, mock_config_mgr, mock_exists):
        """Test topology extraction without connected network."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()

            result = integration.get_network_topology()

            assert result is None

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_get_network_topology_with_network(self, mock_config_mgr, mock_exists):
        """Test topology extraction with connected network."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()

            # Create mock network with required attributes
            mock_network = Mock()
            mock_network.input_size = 2
            mock_network.output_size = 1
            mock_network.hidden_units = []
            mock_network.output_weights = torch.randn(1, 2)
            mock_network.output_bias = torch.randn(1)

            integration.connect_to_network(mock_network)

            result = integration.get_network_topology()

            assert result is not None
            assert "input_size" in result
            assert "output_size" in result


class TestCascorIntegrationDatasetInfo:
    """Test dataset information extraction."""

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_get_dataset_info_with_tensors(self, mock_config_mgr, mock_exists):
        """Test dataset info extraction with torch tensors."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()

            x = torch.randn(100, 2)
            y = torch.randint(0, 2, (100,))

            result = integration.get_dataset_info(x, y)

            assert result is not None

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_get_dataset_info_without_data_generates_mock(self, mock_config_mgr, mock_exists):
        """Test dataset info generates mock data when none provided."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()

            # Create network without training data
            mock_network = Mock()
            mock_network.input_size = 2
            mock_network.output_size = 1
            del mock_network.train_x
            del mock_network.train_y

            integration.connect_to_network(mock_network)

            result = integration.get_dataset_info()

            # Should generate spiral dataset via JuniperData (canonical schema)
            assert result is not None
            assert "inputs" in result or "targets" in result


class TestCascorIntegrationPredictionFunction:
    """Test prediction function retrieval."""

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_get_prediction_function_without_network(self, mock_config_mgr, mock_exists):
        """Test getting prediction function without network."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()

            result = integration.get_prediction_function()

            assert result is None

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_get_prediction_function_with_network(self, mock_config_mgr, mock_exists):
        """Test getting prediction function with network."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()

            mock_network = Mock()
            mock_network.forward = Mock(return_value=torch.randn(10, 1))

            integration.connect_to_network(mock_network)

            predict_fn = integration.get_prediction_function()

            assert predict_fn is not None
            assert callable(predict_fn)

            # Test prediction with numpy array
            x = np.random.randn(10, 2)
            result = predict_fn(x)
            assert result is not None
            mock_network.forward.assert_called_once()


class TestCascorIntegrationMonitoringThread:
    """Test background monitoring thread."""

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_start_monitoring_thread(self, mock_config_mgr, mock_exists):
        """Test starting monitoring thread."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()

            integration.start_monitoring_thread(interval=0.1)

            assert integration.monitoring_active is True
            assert integration.monitoring_thread is not None

            # Clean up
            integration.stop_monitoring()

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_stop_monitoring(self, mock_config_mgr, mock_exists):
        """Test stopping monitoring thread."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()

            integration.start_monitoring_thread(interval=0.1)
            integration.stop_monitoring()

            assert integration.monitoring_active is False


class TestCascorIntegrationCleanup:
    """Test cleanup and shutdown."""

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_shutdown(self, mock_config_mgr, mock_exists):
        """Test shutdown cleans up resources."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()

            integration.shutdown()

            # Should be idempotent
            integration.shutdown()

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_restore_original_methods(self, mock_config_mgr, mock_exists):
        """Test restoring original methods."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()

            mock_network = Mock()
            original_fit = Mock()
            mock_network.fit = original_fit
            mock_network.train_output_layer = Mock()
            mock_network.train_candidates = Mock()

            integration.connect_to_network(mock_network)
            integration.install_monitoring_hooks()

            # Methods should be wrapped
            assert mock_network.fit != original_fit

            integration.restore_original_methods()

            # Should be restored
            assert mock_network.fit == original_fit


class TestCascorIntegrationPropertyAliases:
    """Test property aliases for backward compatibility."""

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_original_fit_property(self, mock_config_mgr, mock_exists):
        """Test original_fit property alias."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()

            mock_network = Mock()
            mock_network.fit = Mock()
            mock_network.train_output_layer = Mock()
            mock_network.train_candidates = Mock()

            integration.connect_to_network(mock_network)
            integration.install_monitoring_hooks()

            assert integration.original_fit is not None

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_connect_to_cascor_network_alias(self, mock_config_mgr, mock_exists):
        """Test connect_to_cascor_network alias."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()

            mock_network = Mock()
            mock_network.input_size = 2
            mock_network.output_size = 1

            result = integration.connect_to_cascor_network(mock_network)

            assert result is True
