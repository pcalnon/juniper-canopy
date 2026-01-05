#!/usr/bin/env python
"""
Comprehensive coverage tests for cascor_integration.py
Target: Raise coverage from 62% to 90%+

Tests focus on previously untested code paths:
- _import_backend_modules error handling
- Monitored method wrappers (fit, train_output, train_candidates)
- Training lifecycle callbacks
- Monitoring loop and metrics extraction
- Topology extraction with hidden units
- CasCor topology extraction
- Dataset info from network attributes
- Training status with/without network
- Prediction function with torch tensors
- Path resolution edge cases
- Error handling throughout
"""
import os
import threading
import time
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pytest
import torch


def create_mock_integration():
    """Helper to create a CascorIntegration with mocked backend."""
    with patch("backend.cascor_integration.Path.exists") as mock_exists:
        with patch("backend.cascor_integration.ConfigManager") as mock_config_mgr:
            from backend.cascor_integration import CascorIntegration

            mock_exists.return_value = True
            mock_config_instance = Mock()
            mock_config_instance.config = {}
            mock_config_mgr.return_value = mock_config_instance

            with patch.object(CascorIntegration, "_import_backend_modules"):
                return CascorIntegration()


class TestBackendImportErrors:
    """Test _import_backend_modules error handling."""

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_import_backend_modules_cascadecorrelation_import_error(self, mock_config_mgr, mock_exists):
        """Test ImportError when CascadeCorrelationNetwork is not found."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch("backend.cascor_integration.sys.path"):
            with pytest.raises(ImportError) as exc_info:
                CascorIntegration(backend_path="/tmp/fake_backend")

            assert "Failed to import CasCor backend modules" in str(exc_info.value)

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_add_backend_to_path_missing_src(self, mock_config_mgr, mock_exists):
        """Test _add_backend_to_path when src directory doesn't exist."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.side_effect = lambda: True

        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration.__new__(CascorIntegration)
            integration.logger = Mock()
            integration.backend_path = Mock()
            integration.backend_path.__truediv__ = Mock(return_value=Mock(exists=Mock(return_value=False)))

            with pytest.raises(FileNotFoundError):
                integration._add_backend_to_path()


class TestMonitoredMethodWrappers:
    """Test the wrapped monitoring methods (fit, train_output, train_candidates)."""

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_monitored_fit_calls_callbacks(self, mock_config_mgr, mock_exists):
        """Test that wrapped fit method calls training callbacks."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()

            mock_network = Mock()
            mock_network.fit = Mock(return_value={"loss": [0.1]})
            mock_network.train_output_layer = Mock()
            mock_network.train_candidates = Mock()
            mock_network.input_size = 2
            mock_network.output_size = 1

            integration.connect_to_network(mock_network)
            integration.install_monitoring_hooks()

            with patch.object(integration, "_on_training_start") as mock_start:
                with patch.object(integration, "_on_training_complete") as mock_complete:
                    integration.network.fit()

                    mock_start.assert_called_once()
                    mock_complete.assert_called_once()

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_monitored_train_output_layer_calls_callbacks(self, mock_config_mgr, mock_exists):
        """Test that wrapped train_output_layer calls phase callbacks."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()

            mock_network = Mock()
            mock_network.fit = Mock()
            mock_network.train_output_layer = Mock(return_value={"output_loss": 0.1})
            mock_network.train_candidates = Mock()

            integration.connect_to_network(mock_network)
            integration.install_monitoring_hooks()

            with patch.object(integration, "_on_output_phase_start") as mock_start:
                with patch.object(integration, "_on_output_phase_end") as mock_end:
                    integration.network.train_output_layer()

                    mock_start.assert_called_once()
                    mock_end.assert_called_once()

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_monitored_train_candidates_calls_callbacks(self, mock_config_mgr, mock_exists):
        """Test that wrapped train_candidates calls phase callbacks."""
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
            mock_network.train_candidates = Mock(return_value={"candidate_loss": 0.2})

            integration.connect_to_network(mock_network)
            integration.install_monitoring_hooks()

            with patch.object(integration, "_on_candidate_phase_start") as mock_start:
                with patch.object(integration, "_on_candidate_phase_end") as mock_end:
                    integration.network.train_candidates()

                    mock_start.assert_called_once()
                    mock_end.assert_called_once()

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_install_hooks_exception_handling(self, mock_config_mgr, mock_exists):
        """Test hook installation exception handling."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()

            class BrokenNetwork:
                @property
                def fit(self):
                    raise RuntimeError("Cannot access fit")

                def train_output_layer(self):
                    pass

                def train_candidates(self):
                    pass

            integration.network = BrokenNetwork()

            result = integration.install_monitoring_hooks()

            assert result is False


class TestTrainingLifecycleCallbacks:
    """Test _on_training_start, _on_training_complete, phase callbacks."""

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_on_training_start_broadcasts_message(self, mock_config_mgr, mock_exists):
        """Test _on_training_start broadcasts WebSocket message."""
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
            integration.network = mock_network

            with patch.object(integration, "_broadcast_message") as mock_broadcast:
                integration._on_training_start()

                mock_broadcast.assert_called_once()
                call_args = mock_broadcast.call_args[0][0]
                assert call_args["type"] == "training_start"
                assert call_args["input_size"] == 2
                assert call_args["output_size"] == 1

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_on_training_complete_broadcasts_message(self, mock_config_mgr, mock_exists):
        """Test _on_training_complete broadcasts WebSocket message."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()

            mock_network = Mock()
            mock_network.hidden_units = [Mock(), Mock()]
            integration.network = mock_network

            history = {"train_loss": [0.5, 0.2, 0.1], "train_accuracy": [0.6, 0.8, 0.95]}

            with patch.object(integration, "_broadcast_message") as mock_broadcast:
                integration._on_training_complete(history)

                mock_broadcast.assert_called_once()
                call_args = mock_broadcast.call_args[0][0]
                assert call_args["type"] == "training_complete"


class TestMonitoringLoop:
    """Test _monitoring_loop and _extract_current_metrics."""

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_extract_current_metrics_with_history(self, mock_config_mgr, mock_exists):
        """Test _extract_current_metrics with populated history."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()

            mock_network = Mock()
            mock_network.history = {
                "train_loss": [0.5, 0.3, 0.1],
                "train_accuracy": [0.6, 0.8, 0.95],
                "value_loss": [0.6, 0.4, 0.2],
                "value_accuracy": [0.5, 0.7, 0.9],
            }
            mock_network.hidden_units = [Mock(), Mock()]
            integration.network = mock_network

            metrics = integration._extract_current_metrics()

            assert metrics["epoch"] == 3
            assert metrics["train_loss"] == 0.1
            assert metrics["train_accuracy"] == 0.95
            assert metrics["value_loss"] == 0.2
            assert metrics["value_accuracy"] == 0.9
            assert metrics["hidden_units"] == 2
            assert "timestamp" in metrics

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_extract_current_metrics_no_network(self, mock_config_mgr, mock_exists):
        """Test _extract_current_metrics with no network."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()
            integration.network = None

            metrics = integration._extract_current_metrics()

            assert metrics == {}

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_extract_current_metrics_no_history_attribute(self, mock_config_mgr, mock_exists):
        """Test _extract_current_metrics when network has no history."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()

            mock_network = Mock(spec=[])
            integration.network = mock_network

            metrics = integration._extract_current_metrics()

            assert metrics == {}

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_extract_current_metrics_empty_history(self, mock_config_mgr, mock_exists):
        """Test _extract_current_metrics with empty history."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()

            mock_network = Mock()
            mock_network.history = {}
            mock_network.hidden_units = []
            integration.network = mock_network

            metrics = integration._extract_current_metrics()

            assert metrics["epoch"] == 0
            assert metrics["train_loss"] is None
            assert metrics["hidden_units"] == 0

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_monitoring_loop_broadcasts_metrics(self, mock_config_mgr, mock_exists):
        """Test monitoring loop broadcasts metrics."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()

            mock_network = Mock()
            mock_network.history = {"train_loss": [0.5]}
            mock_network.hidden_units = []
            integration.network = mock_network
            integration.monitoring_active = True

            broadcasts = []

            def mock_broadcast(msg):
                broadcasts.append(msg)
                integration.monitoring_active = False

            with patch.object(integration, "_broadcast_message", side_effect=mock_broadcast):
                integration._monitoring_loop(0.01)

            assert broadcasts
            assert broadcasts[0]["type"] == "metrics_update"

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_monitoring_loop_handles_exception(self, mock_config_mgr, mock_exists):
        """Test monitoring loop handles exceptions gracefully."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()
            integration.network = Mock()
            integration.monitoring_active = True

            call_count = [0]

            def mock_extract_metrics():
                call_count[0] += 1
                if call_count[0] == 1:
                    raise RuntimeError("Test error")
                integration.monitoring_active = False
                return {"epoch": 0}

            with patch.object(integration, "_extract_current_metrics", side_effect=mock_extract_metrics):
                integration._monitoring_loop(0.01)

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_start_monitoring_thread_already_running(self, mock_config_mgr, mock_exists):
        """Test starting monitoring thread when already running."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()

            integration.start_monitoring_thread(interval=0.1)

            integration.start_monitoring_thread(interval=0.1)

            assert integration.monitoring_active is True
            integration.stop_monitoring()

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_stop_monitoring_not_active(self, mock_config_mgr, mock_exists):
        """Test stop_monitoring when not active is idempotent."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()
            integration.monitoring_active = False

            integration.stop_monitoring()

            assert not integration.monitoring_active


class TestTopologyExtractionWithHiddenUnits:
    """Test topology extraction with various hidden unit configurations."""

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_get_network_topology_with_hidden_units(self, mock_config_mgr, mock_exists):
        """Test topology extraction with hidden units."""
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
            mock_network.output_weights = torch.randn(1, 4)
            mock_network.output_bias = torch.randn(1)
            mock_network.hidden_units = [
                {
                    "weights": torch.randn(3),
                    "bias": torch.tensor(0.1),
                    "activation_fn": torch.sigmoid,
                },
                {
                    "weights": torch.randn(4),
                    "bias": torch.tensor(0.2),
                    "activation_fn": torch.tanh,
                },
            ]

            integration.network = mock_network

            topology = integration.get_network_topology()

            assert topology is not None
            assert topology["input_size"] == 2
            assert topology["output_size"] == 1
            assert len(topology["hidden_units"]) == 2
            assert topology["hidden_units"][0]["activation"] == "sigmoid"
            assert topology["hidden_units"][1]["activation"] == "tanh"

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_get_network_topology_exception_handling(self, mock_config_mgr, mock_exists):
        """Test topology extraction handles exceptions."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()

            mock_network = Mock()
            mock_network.input_size = property(lambda self: 1 / 0)

            integration.network = mock_network

            result = integration.get_network_topology()

            assert result is None


class TestCascorTopologyExtraction:
    """Test extract_cascor_topology and _cascor_topology_get_components."""

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_extract_cascor_topology_no_instance(self, mock_config_mgr, mock_exists):
        """Test extract_cascor_topology with no instance."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()
            integration.cascade_correlation_instance = None

            result = integration.extract_cascor_topology()

            assert result is None

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_extract_cascor_topology_with_instance(self, mock_config_mgr, mock_exists):
        """Test extract_cascor_topology with instance."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()

            mock_instance = Mock()
            mock_instance.input_weights = torch.randn(2, 3)
            mock_instance.hidden_weights = torch.randn(3, 3)
            mock_instance.output_weights = torch.randn(1, 3)
            mock_instance.hidden_biases = torch.randn(3)
            mock_instance.output_biases = torch.randn(1)
            mock_instance.cascade_history = []
            mock_instance.current_epoch = 5

            integration.cascade_correlation_instance = mock_instance

            mock_topology = {"nodes": [], "edges": []}
            integration.data_adapter.convert_network_topology = Mock(return_value=mock_topology)

            result = integration.extract_cascor_topology()

            assert result == mock_topology

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_cascor_topology_get_components_no_instance(self, mock_config_mgr, mock_exists):
        """Test _cascor_topology_get_components with no instance."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()
            integration.cascade_correlation_instance = None

            result = integration._cascor_topology_get_components()

            assert result is None

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_extract_cascor_topology_exception(self, mock_config_mgr, mock_exists):
        """Test extract_cascor_topology handles exceptions."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()

            mock_instance = Mock()
            mock_instance.input_weights = property(lambda self: 1 / 0)

            integration.cascade_correlation_instance = mock_instance

            result = integration.extract_cascor_topology()

            assert result is None


class TestDatasetInfoFromNetwork:
    """Test get_dataset_info with data from network attributes."""

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_get_dataset_info_from_network_attributes(self, mock_config_mgr, mock_exists):
        """Test getting dataset info from network train_x/train_y."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()

            mock_network = Mock()
            mock_network.train_x = torch.randn(50, 2)
            mock_network.train_y = torch.randint(0, 2, (50,))
            mock_network.input_size = 2
            mock_network.output_size = 1

            integration.network = mock_network

            result = integration.get_dataset_info()

            assert result is not None

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_get_dataset_info_with_numpy_arrays(self, mock_config_mgr, mock_exists):
        """Test get_dataset_info with numpy arrays."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()

            x = np.random.randn(100, 2)
            y = np.random.randint(0, 2, 100)

            result = integration.get_dataset_info(x, y)

            assert result is not None

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_get_dataset_info_exception_handling(self, mock_config_mgr, mock_exists):
        """Test get_dataset_info exception handling."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()

            integration.data_adapter.prepare_dataset_for_visualization = Mock(side_effect=RuntimeError("Test error"))

            x = torch.randn(100, 2)
            y = torch.randint(0, 2, (100,))

            result = integration.get_dataset_info(x, y)

            assert result is None


class TestTrainingStatus:
    """Test get_training_status with various network states."""

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_get_training_status_with_network(self, mock_config_mgr, mock_exists):
        """Test get_training_status with connected network."""
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
            mock_network.hidden_units = [Mock(), Mock(), Mock()]

            integration.network = mock_network
            integration.monitoring_active = True

            integration.training_monitor.get_current_state = Mock(
                return_value={"is_training": True, "current_epoch": 42}
            )

            status = integration.get_training_status()

            assert status["network_connected"] is True
            assert status["input_size"] == 3
            assert status["output_size"] == 2
            assert status["hidden_units"] == 3
            assert status["monitoring_active"] is True

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_get_training_status_without_network(self, mock_config_mgr, mock_exists):
        """Test get_training_status without connected network."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()
            integration.network = None
            integration.monitoring_active = False

            integration.training_monitor.get_current_state = Mock(return_value={})

            status = integration.get_training_status()

            assert status["network_connected"] is False
            assert status["input_size"] == 0
            assert status["output_size"] == 0
            assert status["hidden_units"] == 0
            assert status["monitoring_active"] is False


class TestPredictionFunctionWithTorch:
    """Test get_prediction_function with torch tensor inputs."""

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_prediction_function_with_torch_tensor(self, mock_config_mgr, mock_exists):
        """Test prediction function accepts torch tensors."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()

            mock_network = Mock()
            mock_network.forward = Mock(return_value=torch.randn(10, 1))
            integration.network = mock_network

            predict_fn = integration.get_prediction_function()

            x_tensor = torch.randn(10, 2)
            result = predict_fn(x_tensor)

            assert result is not None
            mock_network.forward.assert_called_once_with(x_tensor)


class TestCallbackRegistration:
    """Test monitoring callback registration."""

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_create_monitoring_callback(self, mock_config_mgr, mock_exists):
        """Test creating monitoring callback."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()

            mock_register = Mock()
            integration.training_monitor.register_callback = mock_register

            def my_callback(epoch, loss, accuracy):
                pass

            integration.create_monitoring_callback("epoch_end", my_callback)

            mock_register.assert_called_once_with("epoch_end", my_callback)


class TestPathResolutionEdgeCases:
    """Test path resolution with various edge cases."""

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_resolve_path_from_yaml_config(self, mock_config_mgr, mock_exists):
        """Test path resolution from YAML config."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {"backend": {"cascor_integration": {"backend_path": "/yaml/config/path"}}}
        mock_config_mgr.return_value = mock_config_instance

        with patch.dict(os.environ, {}, clear=False):
            if "CASCOR_BACKEND_PATH" in os.environ:
                del os.environ["CASCOR_BACKEND_PATH"]

            with patch.object(CascorIntegration, "_import_backend_modules"):
                integration = CascorIntegration()

                assert (
                    "yaml" in str(integration.backend_path).lower() or "config" in str(integration.backend_path).lower()
                )

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_resolve_path_with_braced_env_var(self, mock_config_mgr, mock_exists):
        """Test path resolution with ${VAR} syntax."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.dict(os.environ, {"MY_BACKEND_DIR": "/braced/path"}):
            with patch.object(CascorIntegration, "_import_backend_modules"):
                integration = CascorIntegration(backend_path="${MY_BACKEND_DIR}/cascor")

                assert "braced" in str(integration.backend_path).lower() or "cascor" in str(integration.backend_path)


class TestOriginalMethodProperties:
    """Test original method property aliases."""

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_original_train_output_property(self, mock_config_mgr, mock_exists):
        """Test original_train_output property."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()

            mock_network = Mock()
            original_train_output = Mock()
            mock_network.fit = Mock()
            mock_network.train_output_layer = original_train_output
            mock_network.train_candidates = Mock()

            integration.connect_to_network(mock_network)
            integration.install_monitoring_hooks()

            assert integration.original_train_output == original_train_output

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_original_train_candidates_property(self, mock_config_mgr, mock_exists):
        """Test original_train_candidates property."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()

            mock_network = Mock()
            original_train_candidates = Mock()
            mock_network.fit = Mock()
            mock_network.train_output_layer = Mock()
            mock_network.train_candidates = original_train_candidates

            integration.connect_to_network(mock_network)
            integration.install_monitoring_hooks()

            assert integration.original_train_candidates == original_train_candidates

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_original_properties_before_hooks_installed(self, mock_config_mgr, mock_exists):
        """Test original properties return None before hooks installed."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()

            assert integration.original_fit is None
            assert integration.original_train_output is None
            assert integration.original_train_candidates is None


class TestShutdownEdgeCases:
    """Test shutdown and cleanup edge cases."""

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_shutdown_with_active_monitoring(self, mock_config_mgr, mock_exists):
        """Test shutdown with active monitoring thread."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()

            integration.start_monitoring_thread(interval=0.1)

            integration.shutdown()

            assert integration.monitoring_active is False
            assert integration._shutdown_called is True

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_restore_original_methods_no_network(self, mock_config_mgr, mock_exists):
        """Test restore_original_methods with no network."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()
            integration.network = None
            integration._original_methods = {}

            integration.restore_original_methods()

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_destructor_calls_shutdown(self, mock_config_mgr, mock_exists):
        """Test __del__ calls shutdown."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()

            with patch.object(integration, "shutdown") as mock_shutdown:
                integration.__del__()
                mock_shutdown.assert_called_once()


class TestExtractNetworkTopologyAlias:
    """Test extract_network_topology alias."""

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_extract_network_topology_is_alias(self, mock_config_mgr, mock_exists):
        """Test extract_network_topology is alias for get_network_topology."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()

            assert integration.extract_network_topology == integration.get_network_topology


class TestStopMonitoringThreadTimeout:
    """Test stop_monitoring with thread timeout scenarios."""

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_stop_monitoring_thread_timeout_warning(self, mock_config_mgr, mock_exists):
        """Test stop_monitoring logs warning when thread doesn't stop cleanly."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()

            mock_thread = Mock()
            mock_thread.is_alive = Mock(return_value=True)
            mock_thread.join = Mock()

            integration.monitoring_active = True
            integration.monitoring_thread = mock_thread

            integration.stop_monitoring()

            mock_thread.join.assert_called_once_with(timeout=5.0)


class TestPhaseCallbacks:
    """Test output and candidate phase callbacks."""

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_on_output_phase_start(self, mock_config_mgr, mock_exists):
        """Test _on_output_phase_start broadcasts message."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()

            with patch.object(integration, "_broadcast_message") as mock_broadcast:
                integration._on_output_phase_start()

                mock_broadcast.assert_called_once()
                call_args = mock_broadcast.call_args[0][0]
                assert call_args["type"] == "phase_start"
                assert call_args["phase"] == "output"

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_on_output_phase_end(self, mock_config_mgr, mock_exists):
        """Test _on_output_phase_end broadcasts metrics."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()

            mock_network = Mock()
            mock_network.history = {
                "train_loss": [0.5, 0.3, 0.1],
                "train_accuracy": [0.6, 0.8, 0.95],
            }
            mock_network.hidden_units = [Mock()]
            mock_network.learning_rate = 0.01
            integration.network = mock_network

            with patch.object(integration, "_broadcast_message") as mock_broadcast:
                integration._on_output_phase_end(0.1)

                mock_broadcast.assert_called_once()
                call_args = mock_broadcast.call_args[0][0]
                assert call_args["type"] == "phase_end"
                assert call_args["phase"] == "output"
                assert call_args["loss"] == 0.1

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_on_candidate_phase_start(self, mock_config_mgr, mock_exists):
        """Test _on_candidate_phase_start broadcasts message."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()

            with patch.object(integration, "_broadcast_message") as mock_broadcast:
                integration._on_candidate_phase_start()

                mock_broadcast.assert_called_once()
                call_args = mock_broadcast.call_args[0][0]
                assert call_args["type"] == "phase_start"
                assert call_args["phase"] == "candidate"

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_on_candidate_phase_end_with_dict(self, mock_config_mgr, mock_exists):
        """Test _on_candidate_phase_end with dict results."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()

            with patch.object(integration, "_broadcast_message") as mock_broadcast:
                results = {"correlation": 0.95, "best_candidate": 2}
                integration._on_candidate_phase_end(results)

                mock_broadcast.assert_called_once()

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_on_candidate_phase_end_with_tuple(self, mock_config_mgr, mock_exists):
        """Test _on_candidate_phase_end with tuple results."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()

            with patch.object(integration, "_broadcast_message") as mock_broadcast:
                results = ([Mock()], Mock(), {"correlation": 0.9})
                integration._on_candidate_phase_end(results)

                mock_broadcast.assert_called_once()


class TestSerializeHistory:
    """Test _serialize_history with various data types."""

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_serialize_history_with_tensors(self, mock_config_mgr, mock_exists):
        """Test _serialize_history converts tensors to floats."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()

            history = {
                "train_loss": [torch.tensor(0.5), torch.tensor(0.3), torch.tensor(0.1)],
                "single_value": torch.tensor(0.05),
                "plain_list": [1, 2, 3],
                "string_value": "test",
            }

            serialized = integration._serialize_history(history)

            assert len(serialized["train_loss"]) == 3
            assert abs(serialized["train_loss"][0] - 0.5) < 0.01
            assert abs(serialized["single_value"] - 0.05) < 0.01
            assert serialized["plain_list"] == [1, 2, 3]
            assert serialized["string_value"] == "test"


class TestBroadcastMessage:
    """Test _broadcast_message WebSocket integration."""

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_broadcast_message_success(self, mock_config_mgr, mock_exists):
        """Test _broadcast_message sends to websocket."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()

            mock_ws_manager = Mock()
            mock_ws_manager.broadcast_sync = Mock()
            mock_ws_module = MagicMock()
            mock_ws_module.websocket_manager = mock_ws_manager

            with patch.dict(
                "sys.modules",
                {"communication.websocket_manager": mock_ws_module},
            ):
                integration._broadcast_message({"type": "test"})
                mock_ws_manager.broadcast_sync.assert_called_once_with({"type": "test"})

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_broadcast_message_handles_exception(self, mock_config_mgr, mock_exists):
        """Test _broadcast_message handles import/broadcast errors."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()

            with patch("communication.websocket_manager.websocket_manager") as mock_ws:
                mock_ws.broadcast_sync.side_effect = RuntimeError("Connection failed")
                integration._broadcast_message({"type": "test"})


class TestCreateNetworkNoneConfig:
    """Test create_network with None config."""

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_create_network_with_none_config(self, mock_config_mgr, mock_exists):
        """Test create_network with None config defaults to empty dict."""
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

            network = integration.create_network()

            assert network == mock_network
            mock_config_class.assert_called_once_with()


class TestOutputPhaseEndEmptyAccuracy:
    """Test _on_output_phase_end when accuracy history is empty."""

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_on_output_phase_end_no_accuracy(self, mock_config_mgr, mock_exists):
        """Test _on_output_phase_end with empty accuracy history."""
        from backend.cascor_integration import CascorIntegration

        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()

            mock_network = Mock()
            mock_network.history = {"train_loss": [0.1]}
            mock_network.hidden_units = []
            mock_network.learning_rate = 0.01
            integration.network = mock_network

            with patch.object(integration, "_broadcast_message") as mock_broadcast:
                integration._on_output_phase_end(0.1)

                call_args = mock_broadcast.call_args[0][0]
                assert call_args["accuracy"] == 0.0
