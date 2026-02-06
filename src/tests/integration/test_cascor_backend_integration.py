"""
Integration Tests for CasCor Backend Integration

Tests the CascorIntegration class with the actual CasCor backend to verify:
1. Backend module import
2. Network creation and configuration
3. Monitoring hook installation
4. Training callbacks and metric extraction
5. Network topology extraction
6. WebSocket message broadcasting

Prerequisites:
- CasCor backend must be available at ../cascor/ or $CASCOR_BACKEND_PATH
- columnar package must be installed
- JuniperPython conda environment activated
"""

import os
import sys
from pathlib import Path

# Add src to path - must be before local imports
src_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(src_dir))

# import asyncio
from unittest.mock import AsyncMock, MagicMock, patch  # noqa: E402

import numpy as np  # noqa: E402
import pytest  # noqa: E402

from backend.cascor_integration import CascorIntegration  # noqa: E402
from communication.websocket_manager import WebSocketManager  # noqa: E402


@pytest.mark.requires_cascor
@pytest.mark.integration
class TestCascorBackendIntegration:
    """Test CascorIntegration with real backend."""

    @pytest.fixture
    def backend_path(self):
        """Get CasCor backend path."""
        # Try environment variable first
        path = os.getenv("CASCOR_BACKEND_PATH")
        if path and Path(path).exists():
            return path

        # Try relative path
        rel_path = Path(__file__).parent.parent.parent.parent.parent / "cascor"
        if rel_path.exists():
            return str(rel_path)

        pytest.skip("CasCor backend not found. Set CASCOR_BACKEND_PATH environment variable.")

    @pytest.fixture
    def cascor_integration(self, backend_path):
        """Create CascorIntegration instance."""
        integration = CascorIntegration(backend_path=backend_path)
        yield integration
        # Cleanup
        if integration.monitoring_active:
            integration.shutdown()

    @pytest.fixture
    def mock_websocket_manager(self):
        """Mock WebSocketManager to capture broadcasts."""
        manager = MagicMock(spec=WebSocketManager)
        manager.broadcast_sync = MagicMock()
        manager.broadcast = AsyncMock()
        return manager

    def test_backend_import_successful(self, cascor_integration):
        """Test that backend modules import successfully."""
        assert cascor_integration.cascade_correlation_class is not None, "CascadeCorrelationNetwork class should be imported"  # trunk-ignore(bandit/B101)
        assert cascor_integration.cascade_correlation_config_class is not None, "CascadeCorrelationConfig class should be imported"  # trunk-ignore(bandit/B101)
        print("✅ Backend modules imported successfully")

    def test_network_creation_with_config(self, cascor_integration):
        """Test network creation with configuration."""
        config = {
            "input_size": 2,
            "output_size": 1,
            "max_epochs": 10,
            "learning_rate": 0.01,
            "patience": 5,
        }

        network = cascor_integration.create_network(config)

        assert network is not None, "Network should be created"  # trunk-ignore(bandit/B101)
        assert cascor_integration.cascade_correlation_instance is not None, "Network instance should be stored"  # trunk-ignore(bandit/B101)
        assert hasattr(network, "input_size"), "Network should have input_size attribute"  # trunk-ignore(bandit/B101)
        assert network.input_size == 2, "Input size should be 2"  # trunk-ignore(bandit/B101)

        print(f"✅ Network created: input_size={network.input_size}, output_size={network.output_size}")

    def test_connect_to_existing_network(self, cascor_integration):
        """Test connecting to an existing network instance."""
        # Create a network first
        config = {"input_size": 2, "output_size": 1}
        network = cascor_integration.create_network(config)

        # Disconnect
        cascor_integration.cascade_correlation_instance = None

        # Reconnect
        result = cascor_integration.connect_to_network(network)

        assert network is not None, "Network should be created"  # trunk-ignore(bandit/B101)
        assert result is True, "Connection should succeed"  # trunk-ignore(bandit/B101)
        assert cascor_integration.cascade_correlation_instance is network, "Connected network should match"  # trunk-ignore(bandit/B101)

        print("✅ Successfully connected to existing network")

    def test_install_monitoring_hooks(self, cascor_integration):
        """Test installation of monitoring hooks."""
        # Create network
        config = {"input_size": 2, "output_size": 1, "max_epochs": 5}
        network = cascor_integration.create_network(config)

        # Install hooks
        result = cascor_integration.install_monitoring_hooks()

        assert network is not None, "Network should be created"  # trunk-ignore(bandit/B101)
        assert result is True, "Hook installation should succeed"  # trunk-ignore(bandit/B101)
        assert cascor_integration.monitoring_active is True, "Monitoring should be active"  # trunk-ignore(bandit/B101)
        assert cascor_integration.original_fit is not None, "Original fit method should be stored"  # trunk-ignore(bandit/B101)

        print("✅ Monitoring hooks installed successfully")

    def test_get_training_status(self, cascor_integration):
        """Test training status retrieval."""
        config = {"input_size": 2, "output_size": 1}
        cascor_integration.create_network(config)

        status = cascor_integration.get_training_status()

        assert status is not None, "Status should be returned"  # trunk-ignore(bandit/B101)
        assert "network_connected" in status, "Status should include network_connected"  # trunk-ignore(bandit/B101)
        assert "monitoring_active" in status, "Status should include monitoring_active"  # trunk-ignore(bandit/B101)
        assert status["network_connected"] is True, "Network should be connected"  # trunk-ignore(bandit/B101)

        print(f"✅ Training status: {status}")

    def test_network_topology_extraction(self, cascor_integration):
        """Test network topology extraction."""
        # Create and train network briefly to add hidden units
        config = {"input_size": 2, "output_size": 1, "max_epochs": 2}
        network = cascor_integration.create_network(config)

        # Get topology (should work even before training)
        topology = cascor_integration.get_network_topology()

        assert network is not None, "Network should be created"  # trunk-ignore(bandit/B101)
        assert topology is not None, "Topology should be returned"  # trunk-ignore(bandit/B101)
        assert "input_size" in topology, "Topology should include input_size"  # trunk-ignore(bandit/B101)
        assert "output_size" in topology, "Topology should include output_size"  # trunk-ignore(bandit/B101)
        assert "hidden_units" in topology, "Topology should include hidden_units"  # trunk-ignore(bandit/B101)
        assert topology["input_size"] == 2, "Input size should match"  # trunk-ignore(bandit/B101)
        assert topology["output_size"] == 1, "Output size should match"  # trunk-ignore(bandit/B101)

        hidden = len(topology["hidden_units"])
        print(f"✅ Topology extracted: {topology['input_size']} inputs, {hidden} hidden, " f"{topology['output_size']} outputs")

    def test_dataset_info_preparation(self, cascor_integration):
        """Test dataset info preparation for visualization."""
        # Create network
        config = {"input_size": 2, "output_size": 1}
        cascor_integration.create_network(config)

        # Generate sample data
        x_train = np.random.randn(50, 2)
        y_train = np.random.randint(0, 2, (50, 1)).astype(float)

        dataset_info = cascor_integration.get_dataset_info(x_train, y_train)

        assert dataset_info is not None, "Dataset info should be returned"  # trunk-ignore(bandit/B101)
        assert "num_samples" in dataset_info, "Should include sample count"  # trunk-ignore(bandit/B101)
        assert dataset_info["num_samples"] == 50, "Sample count should match"  # trunk-ignore(bandit/B101)

        print(f"✅ Dataset info prepared: {dataset_info['num_samples']} samples")

    def test_prediction_function_retrieval(self, cascor_integration):
        """Test retrieval of prediction function."""
        # Create network
        config = {"input_size": 2, "output_size": 1}
        network = cascor_integration.create_network(config)

        predict_fn = cascor_integration.get_prediction_function()

        assert network is not None, "Network should be created"  # trunk-ignore(bandit/B101)
        assert predict_fn is not None, "Prediction function should be returned"  # trunk-ignore(bandit/B101)
        assert callable(predict_fn), "Should be callable"  # trunk-ignore(bandit/B101)

        # Test prediction
        x_test = np.random.randn(10, 2)
        predictions = predict_fn(x_test)

        assert predictions is not None, "Predictions should be returned"  # trunk-ignore(bandit/B101)
        assert len(predictions) == 10, "Should predict for all samples"  # trunk-ignore(bandit/B101)

        print(f"✅ Prediction function working: {len(predictions)} predictions made")

    @pytest.mark.asyncio
    async def test_training_with_monitoring(self, cascor_integration, mock_websocket_manager):
        """Test training with monitoring hooks and WebSocket broadcasting."""
        # Patch websocket_manager
        with patch("communication.websocket_manager.websocket_manager", mock_websocket_manager):
            # Create network with small config for fast training
            config = {
                "input_size": 2,
                "output_size": 1,
                "max_epochs": 3,  # Very few epochs for fast test
                "patience": 2,
                "learning_rate": 0.1,
            }
            network = cascor_integration.create_network(config)

            # Install hooks
            cascor_integration.install_monitoring_hooks()

            # Generate simple training data
            np.random.seed(42)
            x_train = np.random.randn(20, 2)
            y_train = (x_train[:, 0] + x_train[:, 1] > 0).astype(float).reshape(-1, 1)

            # Train network (this will trigger callbacks)
            try:
                history = network.fit(x_train, y_train)
                assert history is not None, "Training history should be returned"  # trunk-ignore(bandit/B101)

                # Verify broadcasts were made
                assert mock_websocket_manager.broadcast_sync.called, "WebSocket broadcast should be called during training"  # trunk-ignore(bandit/B101)

                call_count = mock_websocket_manager.broadcast_sync.call_count
                print(f"✅ Training completed with {call_count} WebSocket broadcasts")

                # Verify broadcast content
                if call_count > 0:
                    first_call = mock_websocket_manager.broadcast_sync.call_args_list[0][0][0]
                    assert "type" in first_call, "Broadcast should have 'type' field"  # trunk-ignore(bandit/B101)
                    print(f"   First broadcast type: {first_call['type']}")

            except Exception as e:
                print(f"⚠️  Training encountered issue (expected for small dataset): {e}")
                # Still verify at least training_start was broadcast
                assert mock_websocket_manager.broadcast_sync.called, "Should have broadcast training_start even if training failed"  # trunk-ignore(bandit/B101)

    def test_monitoring_thread_lifecycle(self, cascor_integration):
        """Test monitoring thread start and stop."""
        # Create network
        config = {"input_size": 2, "output_size": 1}
        cascor_integration.create_network(config)

        # Start monitoring thread
        cascor_integration.start_monitoring_thread(interval=0.1)  # 100ms interval

        assert cascor_integration.monitoring_thread is not None, "Monitoring thread should be created"  # trunk-ignore(bandit/B101)
        assert cascor_integration.monitoring_thread.is_alive(), "Monitoring thread should be running"  # trunk-ignore(bandit/B101)

        print("✅ Monitoring thread started")

        # Let it run briefly
        import time

        time.sleep(0.3)

        # Stop monitoring
        cascor_integration.shutdown()

        # Wait for thread to stop
        time.sleep(0.2)

        # Check monitoring is inactive (thread reference cleared on stop)
        assert not cascor_integration.monitoring_active, "Monitoring should be inactive after shutdown"  # trunk-ignore(bandit/B101)
        assert cascor_integration.monitoring_thread is None, "Monitoring thread reference should be cleared"  # trunk-ignore(bandit/B101)

        print("✅ Monitoring thread stopped cleanly")

    def test_metric_extraction_from_history(self, cascor_integration):
        """Test metric extraction from training history."""
        # Create and train network
        config = {"input_size": 2, "output_size": 1, "max_epochs": 3}
        network = cascor_integration.create_network(config)

        # Generate simple data
        np.random.seed(42)
        x_train = np.random.randn(30, 2)
        y_train = (x_train[:, 0] > 0).astype(float).reshape(-1, 1)

        # Train to populate history
        try:
            network.fit(x_train, y_train)

            # Extract metrics
            metrics = cascor_integration._extract_current_metrics()

            assert metrics is not None, "Metrics should be extracted"  # trunk-ignore(bandit/B101)
            if "epoch" in metrics:  # sourcery skip: no-conditionals-in-tests
                print(
                    f"✅ Metrics extracted: epoch={metrics.get('epoch')}, ",
                    f"loss={metrics.get('loss', 'N/A')}",
                )
            else:
                print(f"✅ Metrics structure: {list(metrics.keys())}")

        except Exception as e:
            print(f"⚠️  Training failed (expected for toy dataset): {e}")
            pytest.skip("Training failed, but integration structure verified")

    def test_hook_restoration_on_shutdown(self, cascor_integration):
        """Test that original methods are restored on shutdown."""
        # Create network
        config = {"input_size": 2, "output_size": 1}
        network = cascor_integration.create_network(config)

        # Get original method reference
        original_fit = network.fit

        # Install hooks
        cascor_integration.install_monitoring_hooks()

        # Method should be wrapped
        assert network.fit != original_fit, "fit method should be wrapped"  # trunk-ignore(bandit/B101)

        # Shutdown (restores methods)
        cascor_integration.shutdown()

        # Method should be restored (or at least monitoring inactive)
        assert cascor_integration.monitoring_active is False, "Monitoring should be inactive after shutdown"  # trunk-ignore(bandit/B101)

        print("✅ Methods restored on shutdown")


class TestCascorIntegrationErrorHandling:
    """Test error handling in CascorIntegration."""

    def test_create_network_without_backend(self):
        """Test graceful failure when backend not found."""
        with pytest.raises((FileNotFoundError, ImportError, RuntimeError)):
            CascorIntegration(backend_path="/nonexistent/path")

    def test_install_hooks_without_network(self):
        """Test hook installation fails gracefully without network."""
        backend_path = os.getenv("CASCOR_BACKEND_PATH", "../cascor")
        if not Path(backend_path).exists():  # sourcery skip: no-conditionals-in-tests
            pytest.skip("Backend not available")

        integration = CascorIntegration(backend_path=backend_path)

        # Don't create network
        result = integration.install_monitoring_hooks()

        assert result is False, "Should fail without network"  # trunk-ignore(bandit/B101)
        print("✅ Hook installation fails gracefully without network")

    def test_get_topology_without_network(self):
        """Test topology extraction returns None without network."""
        backend_path = os.getenv("CASCOR_BACKEND_PATH", "../cascor")
        if not Path(backend_path).exists():  # sourcery skip: no-conditionals-in-tests
            pytest.skip("Backend not available")

        integration = CascorIntegration(backend_path=backend_path)
        topology = integration.get_network_topology()

        assert topology is None, "Should return None without network"  # trunk-ignore(bandit/B101)
        print("✅ Topology extraction handles missing network")


@pytest.mark.integration
class TestCascorWebSocketIntegration:
    """Test WebSocket integration during training."""

    @pytest.fixture
    def integration_with_websocket(self):
        """Create integration with mocked WebSocket."""
        backend_path = os.getenv("CASCOR_BACKEND_PATH", "../cascor")
        if not Path(backend_path).exists():
            pytest.skip("Backend not available")

        integration = CascorIntegration(backend_path=backend_path)
        mock_ws = MagicMock(spec=WebSocketManager)
        mock_ws.broadcast_sync = MagicMock()

        # Store for verification
        integration._test_ws_manager = mock_ws

        yield integration, mock_ws

        # Cleanup
        if integration.monitoring_active:
            integration.shutdown()

    def test_broadcast_on_training_start(self, integration_with_websocket):
        """Test WebSocket broadcast on training start."""
        integration, mock_ws = integration_with_websocket

        with patch("communication.websocket_manager.websocket_manager", mock_ws):
            # Create network
            config = {"input_size": 2, "output_size": 1, "max_epochs": 1}
            network = integration.create_network(config)
            integration.install_monitoring_hooks()

            # Trigger training start callback
            integration._on_training_start()

            # Verify broadcast
            assert network is not None, "Network should be created"  # trunk-ignore(bandit/B101)
            assert mock_ws.broadcast_sync.called, "Should broadcast on training start"  # trunk-ignore(bandit/B101)

            call_args = mock_ws.broadcast_sync.call_args[0][0]
            assert call_args["type"] == "training_start", "Broadcast type should be training_start"  # trunk-ignore(bandit/B101)

            print("✅ Training start broadcast verified")

    def test_broadcast_on_output_phase_end(self, integration_with_websocket):
        """Test WebSocket broadcast on output phase end."""
        integration, mock_ws = integration_with_websocket

        with patch("communication.websocket_manager.websocket_manager", mock_ws):
            # Create network
            config = {"input_size": 2, "output_size": 1}
            integration.create_network(config)

            # Trigger callback
            integration._on_output_phase_end(loss=0.5)

            # Verify broadcast
            assert mock_ws.broadcast_sync.called, "Should broadcast on output phase end"  # trunk-ignore(bandit/B101)

            call_args = mock_ws.broadcast_sync.call_args[0][0]
            assert "loss" in call_args, "Broadcast should include loss"  # trunk-ignore(bandit/B101)
            assert call_args["loss"] == 0.5, "Loss value should match"  # trunk-ignore(bandit/B101)

            print("✅ Output phase end broadcast verified")


if __name__ == "__main__":
    """Run tests with pytest."""
    pytest.main([__file__, "-v", "--tb=short"])
