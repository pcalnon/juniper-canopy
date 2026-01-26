"""
Unit Tests for Architectural Fixes

Tests for critical fixes implemented to resolve MVP blockers:
1. Thread-safe async broadcasting
2. Thread-safe topology extraction
3. Thread lifecycle management
4. Idempotent shutdown
"""

import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor

# from unittest.mock import Mock, MagicMock, patch
from unittest.mock import Mock, patch

import pytest
import torch


def create_mock_cascor_integration(network=None, with_training_monitor=False):
    """
    Create a CascorIntegration instance without calling __init__.

    This helper properly initializes all required attributes that __init__
    would set, avoiding AttributeError in tests that use __new__.

    Args:
        network: Optional network instance to attach
        with_training_monitor: If True, attach a mock TrainingMonitor

    Returns:
        CascorIntegration instance with minimal required attributes
    """
    from src.backend.cascor_integration import CascorIntegration

    integration = CascorIntegration.__new__(CascorIntegration)
    integration.logger = Mock()
    integration.network = network
    integration.monitoring_thread = None
    integration.monitoring_active = False
    integration.metrics_lock = threading.Lock()  # CANOPY-P1-003 thread safety
    integration.topology_lock = threading.Lock()
    integration._shutdown_called = False
    integration._original_methods = {}
    # P1-NEW-003: Async training support attributes
    integration._training_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="TestFit")
    integration._training_lock = threading.Lock()
    integration._training_future = None
    integration._training_stop_requested = False
    if with_training_monitor:
        integration.training_monitor = Mock()
    return integration


class TestThreadSafeAsyncBroadcasting:
    """Test thread-safe async callback scheduling."""

    def test_schedule_broadcast_from_thread(self):
        """Test that broadcasts can be scheduled from non-async threads."""
        messages = []

        async def mock_broadcast(msg):
            """Mock broadcast function."""
            messages.append(msg)

        async def test_runner():
            """Main test runner in async context."""
            loop = asyncio.get_running_loop()
            loop_holder = {"loop": loop}

            def schedule_broadcast(coro):
                """Helper to schedule broadcasts."""
                if (
                    loop_holder["loop"] and not loop_holder["loop"].is_closed()
                ):  # sourcery skip: no-conditionals-in-tests
                    asyncio.run_coroutine_threadsafe(coro, loop_holder["loop"])

            def callback_from_thread():
                """Simulate callback from training thread."""
                schedule_broadcast(mock_broadcast({"type": "test", "data": 42}))

            # Run callback in separate thread
            thread = threading.Thread(target=callback_from_thread)
            thread.start()
            thread.join()

            # Give time for scheduled coroutine to execute
            await asyncio.sleep(0.1)

            # Verify message was broadcasted
            assert len(messages) == 1  # trunk-ignore(bandit/B101)
            assert messages[0]["type"] == "test"  # trunk-ignore(bandit/B101)
            assert messages[0]["data"] == 42  # trunk-ignore(bandit/B101)

        # Run the async test
        asyncio.run(test_runner())

    def test_schedule_broadcast_with_closed_loop(self):
        """Test graceful handling when event loop is closed."""
        messages = []
        warnings = []

        def mock_warning(msg):
            warnings.append(msg)

        loop_holder = {"loop": None}

        def schedule_broadcast(coro):
            """Helper that should warn when loop unavailable."""
            if loop_holder["loop"] and not loop_holder["loop"].is_closed():  # sourcery skip: no-conditionals-in-tests
                asyncio.run_coroutine_threadsafe(coro, loop_holder["loop"])
            else:
                mock_warning("Event loop not available")

        async def mock_broadcast(msg):
            messages.append(msg)

        # Try to schedule without loop
        coro = mock_broadcast({"type": "test"})
        schedule_broadcast(coro)
        # Close the unawaited coroutine to prevent warning
        coro.close()

        # Should have warning, no messages
        assert len(warnings) == 1  # trunk-ignore(bandit/B101)
        assert not messages  # trunk-ignore(bandit/B101)

    def test_concurrent_broadcasts_from_multiple_threads(self):
        """Test that multiple threads can schedule broadcasts concurrently."""
        messages = []
        lock = threading.Lock()

        async def mock_broadcast(msg):
            """Thread-safe mock broadcast."""
            with lock:
                messages.append(msg)

        async def test_runner():
            """Main test runner."""
            loop = asyncio.get_running_loop()
            loop_holder = {"loop": loop}

            def schedule_broadcast(coro):
                if (
                    loop_holder["loop"] and not loop_holder["loop"].is_closed()
                ):  # sourcery skip: no-conditionals-in-tests
                    asyncio.run_coroutine_threadsafe(coro, loop_holder["loop"])

            def worker(worker_id):
                """Worker thread."""
                for i in range(5):  # sourcery skip: no-loop-in-tests
                    schedule_broadcast(mock_broadcast({"worker": worker_id, "iteration": i}))
                    time.sleep(0.01)

            # Start multiple worker threads
            threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]

            for thread in threads:  # sourcery skip: no-loop-in-tests
                thread.start()

            for thread in threads:  # sourcery skip: no-loop-in-tests
                thread.join()

            # Wait for all scheduled broadcasts
            await asyncio.sleep(0.5)

            # Should have received 5 workers * 5 messages each = 25 messages
            assert len(messages) == 25  # trunk-ignore(bandit/B101)

            # Verify all workers contributed
            worker_ids = {msg["worker"] for msg in messages}
            assert worker_ids == {0, 1, 2, 3, 4}  # trunk-ignore(bandit/B101)

        asyncio.run(test_runner())


class TestThreadSafeTopologyExtraction:
    """Test thread-safe network topology extraction."""

    @pytest.fixture
    def mock_network(self):
        """Create mock network for testing."""
        network = Mock()
        network.input_size = 2
        network.output_size = 1
        network.output_weights = torch.randn(1, 3)
        network.output_bias = torch.randn(1)
        network.hidden_units = [{"weights": torch.randn(3), "bias": torch.tensor(0.1), "activation_fn": torch.sigmoid}]
        return network

    def test_topology_extraction_with_lock(self, mock_network):
        """Test that topology extraction uses lock."""
        integration = create_mock_cascor_integration(network=mock_network)

        # Extract topology
        topology = integration.get_network_topology()

        # Verify structure
        assert topology is not None  # trunk-ignore(bandit/B101)
        assert topology["input_size"] == 2  # trunk-ignore(bandit/B101)
        assert topology["output_size"] == 1  # trunk-ignore(bandit/B101)
        assert len(topology["hidden_units"]) == 1  # trunk-ignore(bandit/B101)

    def test_concurrent_topology_extraction(self, mock_network):
        """Test that concurrent extractions don't cause errors."""
        integration = create_mock_cascor_integration(network=mock_network)

        results = []
        errors = []

        def extract():
            """Worker to extract topology."""
            try:
                result = integration.get_network_topology()
                results.append(result)
            except Exception as e:
                errors.append(e)

        # Run multiple extractions concurrently
        threads = [threading.Thread(target=extract) for _ in range(10)]

        for thread in threads:  # sourcery skip: no-loop-in-tests
            thread.start()

        for thread in threads:  # sourcery skip: no-loop-in-tests
            thread.join()

        # No errors should occur
        assert not errors  # trunk-ignore(bandit/B101)
        assert len(results) == 10  # trunk-ignore(bandit/B101)

        # All results should be valid
        assert all(r is not None for r in results)  # trunk-ignore(bandit/B101)
        assert all(r["input_size"] == 2 for r in results)  # trunk-ignore(bandit/B101)


class TestThreadLifecycle:
    """Test monitoring thread lifecycle management."""

    def test_stop_monitoring_idempotent(self):
        """Test that stop_monitoring can be called multiple times."""
        integration = create_mock_cascor_integration()

        # Should be safe to call multiple times
        integration.stop_monitoring()
        integration.stop_monitoring()
        integration.stop_monitoring()

        # Should not raise any exceptions

    def test_stop_monitoring_waits_for_thread(self):
        """Test that stop_monitoring waits for thread to finish."""
        integration = create_mock_cascor_integration()
        integration.monitoring_active = True

        # Create mock thread
        mock_thread = Mock()
        mock_thread.is_alive.return_value = False
        integration.monitoring_thread = mock_thread

        # Stop monitoring
        integration.stop_monitoring()

        # Verify thread.join was called with timeout
        mock_thread.join.assert_called_once_with(timeout=5.0)
        mock_thread.is_alive.assert_called_once()

        # Verify flags set correctly
        assert not integration.monitoring_active  # trunk-ignore(bandit/B101)
        assert integration.monitoring_thread is None  # trunk-ignore(bandit/B101)

    def test_shutdown_idempotent(self):
        """Test that shutdown can be called multiple times."""
        integration = create_mock_cascor_integration(with_training_monitor=True)

        # First call should execute
        integration.shutdown()
        assert integration._shutdown_called  # trunk-ignore(bandit/B101)

        # Second call should skip
        integration.shutdown()
        integration.shutdown()

        # training_monitor.on_training_end should only be called once
        integration.training_monitor.on_training_end.assert_called_once()


class TestDashMounting:
    """Test Dash app mounting configuration."""

    def test_dash_uses_requests_pathname_prefix(self):
        """Test that Dash app uses requests_pathname_prefix instead of url_base_pathname."""
        with patch("src.frontend.dashboard_manager.dash.Dash") as mock_dash:
            from src.frontend.dashboard_manager import DashboardManager

            config = {}
            # Dash app is initialized in __init__, not a separate method
            manager = DashboardManager(config)
            assert manager is not None  # trunk-ignore(bandit/B101)
            assert manager.app is not None  # trunk-ignore(bandit/B101)

            # Verify Dash was initialized with requests_pathname_prefix
            call_kwargs = mock_dash.call_args[1]
            assert "requests_pathname_prefix" in call_kwargs  # trunk-ignore(bandit/B101)
            assert call_kwargs["requests_pathname_prefix"] == "/dashboard/"  # trunk-ignore(bandit/B101)

            # Verify url_base_pathname is NOT used
            assert "url_base_pathname" not in call_kwargs  # trunk-ignore(bandit/B101)


class TestAPIURLDynamicResolution:
    """Test that API URLs are resolved dynamically from Flask request."""

    def test_callbacks_use_request_host_url(self):
        """Test that callbacks use dynamic request-based URLs instead of hardcoded URLs."""
        import inspect

        from src.frontend.dashboard_manager import DashboardManager

        config = {}
        manager = DashboardManager(config)

        # Get source code of _api_url helper
        api_url_source = inspect.getsource(manager._api_url)

        # Verify dynamic URL building using request.scheme and request.host (in _api_url helper)
        assert "request.scheme" in api_url_source  # trunk-ignore(bandit/B101)
        assert "request.host" in api_url_source  # trunk-ignore(bandit/B101)

        # Verify handler methods use the _api_url helper (check a sample handler)
        # _update_unified_status_bar_handler uses _api_url for API calls
        handler_source = inspect.getsource(manager._update_unified_status_bar_handler)
        assert "_api_url" in handler_source  # trunk-ignore(bandit/B101)

        # Verify no hardcoded URLs in handler methods
        assert "http://127.0.0.1:8050" not in handler_source  # trunk-ignore(bandit/B101)


class TestConfigurationManagement:
    """Test configuration management robustness."""

    def test_config_manager_handles_missing_file(self):
        """Test that ConfigManager handles missing config file gracefully."""
        import os

        from src.config_manager import ConfigManager

        # Save and clear any CASCOR environment variables
        cascor_env_backup = {k: v for k, v in os.environ.items() if k.startswith("CASCOR_")}
        for key in cascor_env_backup:  # sourcery skip: no-loop-in-tests
            del os.environ[key]

        try:
            with patch("pathlib.Path.exists", return_value=False):
                config = ConfigManager("/nonexistent/config.yaml")

                # Should return default values
                assert config.get("application.name", "default") == "default"  # trunk-ignore(bandit/B101)
                # Config should have defaults applied when no file exists
                assert config.config is not None  # trunk-ignore(bandit/B101)
                assert config.get("application.server.port") == 8050  # trunk-ignore(bandit/B101)
        finally:
            # Restore environment variables
            for key, value in cascor_env_backup.items():  # sourcery skip: no-loop-in-tests
                os.environ[key] = value

    def test_environment_variable_overrides(self):
        """Test that environment variables override config values."""
        import os

        from src.config_manager import ConfigManager

        # Save and clear any CASCOR environment variables
        cascor_env_backup = {k: v for k, v in os.environ.items() if k.startswith("CASCOR_")}
        for key in cascor_env_backup:  # sourcery skip: no-loop-in-tests
            del os.environ[key]

        try:
            with patch("pathlib.Path.exists", return_value=False):
                # Set environment variable
                os.environ["CASCOR_SERVER_PORT"] = "9000"

                config = ConfigManager("/nonexistent/config.yaml")

                # Should apply environment override
                assert config.get("server.port", 8050) == 9000  # trunk-ignore(bandit/B101)

        finally:
            # Clean up - restore all original env vars
            for key in [k for k in os.environ if k.startswith("CASCOR_")]:  # sourcery skip: no-loop-in-tests
                if key not in cascor_env_backup:
                    del os.environ[key]
            for key, value in cascor_env_backup.items():  # sourcery skip: no-loop-in-tests
                os.environ[key] = value


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
