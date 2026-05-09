"""
Tests for CascorServiceAdapter — Phase 4 Canopy/CasCor decoupling.

Verifies that the adapter:
1. Exposes all methods/attributes required by main.py
2. Delegates REST calls to JuniperCascorClient
3. Returns graceful fallbacks on connection errors
4. _ServiceTrainingMonitor works correctly
5. Async WS relay broadcasts messages
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_jcc = pytest.importorskip("juniper_cascor_client", reason="juniper-cascor-client not installed")
if getattr(_jcc, "_is_stub", False):
    pytest.skip("juniper-cascor-client is a test stub, not the real package", allow_module_level=True)

from backend.cascor_service_adapter import CascorServiceAdapter, _ServiceTrainingMonitor

# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def mock_client():
    """Create a mock JuniperCascorClient."""
    client = MagicMock()
    client.is_ready.return_value = True
    client.is_alive.return_value = True
    client.get_training_status.return_value = {"is_training": False, "status": "idle"}
    client.get_metrics.return_value = {"loss": 0.5, "accuracy": 0.8}
    client.get_metrics_history.return_value = {"history": [{"epoch": 1, "loss": 0.5}]}
    client.get_network.return_value = {"input_size": 2, "output_size": 1}
    client.get_topology.return_value = {"input_units": 2, "hidden_units": 0, "output_units": 1}
    client.get_statistics.return_value = {"total_weights": 3}
    client.get_dataset.return_value = {"num_samples": 100}
    client.create_network.return_value = {"status": "created"}
    client.start_training.return_value = {"status": "started"}
    client.stop_training.return_value = {"status": "stopped"}
    client.close.return_value = None
    return client


@pytest.fixture
def adapter(mock_client):
    """Create a CascorServiceAdapter with a mocked client."""
    a = CascorServiceAdapter(service_url="http://localhost:8200")
    a._client = mock_client
    a.training_monitor = _ServiceTrainingMonitor(mock_client)
    return a


# =========================================================================
# Interface compatibility — verify all required attributes/methods exist
# =========================================================================


class TestInterfaceCompatibility:
    """Verify the adapter exposes all methods and attributes used by main.py."""

    def test_has_network_property(self, adapter):
        assert hasattr(adapter, "network")

    def test_has_training_monitor(self, adapter):
        assert hasattr(adapter, "training_monitor")

    def test_has_training_stop_requested(self, adapter):
        assert hasattr(adapter, "_training_stop_requested")

    @pytest.mark.parametrize(
        "method_name",
        [
            "create_network",
            "start_training_background",
            "is_training_in_progress",
            "request_training_stop",
            "get_training_status",
            "get_network_data",
            "extract_network_topology",
            "get_network_topology",
            "get_dataset_info",
            "get_prediction_function",
            "install_monitoring_hooks",
            "start_monitoring_thread",
            "stop_monitoring",
            "restore_original_methods",
            "create_monitoring_callback",
            "get_remote_worker_status",
            "connect_remote_workers",
            "start_remote_workers",
            "stop_remote_workers",
            "disconnect_remote_workers",
            "shutdown",
        ],
    )
    def test_has_required_method(self, adapter, method_name):
        assert hasattr(adapter, method_name), f"Missing method: {method_name}"
        assert callable(getattr(adapter, method_name))


# =========================================================================
# REST delegation — verify methods call the client correctly
# =========================================================================


class TestRESTDelegation:
    """Verify adapter methods delegate to JuniperCascorClient."""

    def test_create_network(self, adapter, mock_client):
        config = {"input_size": 2, "output_size": 1}
        result = adapter.create_network(config)
        mock_client.create_network.assert_called_once_with(input_size=2, output_size=1)
        assert result == {"status": "created"}

    def test_create_network_none_config(self, adapter, mock_client):
        adapter.create_network(None)
        mock_client.create_network.assert_called_once_with()

    def test_start_training_background(self, adapter, mock_client):
        result = adapter.start_training_background()
        assert result is True
        mock_client.start_training.assert_called_once()

    def test_is_training_in_progress(self, adapter, mock_client):
        assert adapter.is_training_in_progress() is False
        mock_client.get_training_status.assert_called()

    def test_is_training_in_progress_when_training(self, adapter, mock_client):
        mock_client.get_training_status.return_value = {"is_training": True}
        assert adapter.is_training_in_progress() is True

    def test_request_training_stop(self, adapter, mock_client):
        assert adapter.request_training_stop() is True
        mock_client.stop_training.assert_called_once()

    def test_get_training_status(self, adapter, mock_client):
        result = adapter.get_training_status()
        assert result == {"is_training": False, "status": "idle"}

    def test_get_network_data(self, adapter, mock_client):
        result = adapter.get_network_data()
        mock_client.get_statistics.assert_called_once()
        assert result == {"total_weights": 3}

    def test_extract_network_topology(self, adapter, mock_client):
        result = adapter.extract_network_topology()
        mock_client.get_topology.assert_called_once()
        assert result["input_units"] == 2

    def test_get_network_topology_alias(self, adapter, mock_client):
        result = adapter.get_network_topology()
        assert result == adapter.extract_network_topology()

    def test_get_dataset_info(self, adapter, mock_client):
        result = adapter.get_dataset_info()
        mock_client.get_dataset.assert_called_once()
        assert result == {"num_samples": 100}

    def test_get_prediction_function_returns_none(self, adapter):
        assert adapter.get_prediction_function() is None


# =========================================================================
# Parameter normalization for canopy namespace
# =========================================================================


class TestCanopyParamsMapping:
    """Verify get_canopy_params() handles both nested and flat payloads."""

    def test_get_canopy_params_prefers_nested_params(self, adapter, mock_client):
        mock_client.get_training_params.return_value = {
            "data": {
                "params": {
                    "learning_rate": 0.02,
                    "max_hidden_units": 11,
                    "epochs_max": 250,
                },
                "learning_rate": 0.99,  # Should be ignored because nested params exist
            }
        }

        result = adapter.get_canopy_params()

        assert result["nn_learning_rate"] == 0.02
        assert result["nn_max_hidden_units"] == 11
        assert result["nn_max_total_epochs"] == 250

    def test_get_canopy_params_supports_flat_data_payload(self, adapter, mock_client):
        mock_client.get_training_params.return_value = {
            "data": {
                "learning_rate": 0.03,
                "max_hidden_units": 7,
                "epochs_max": 100,
                "status": "started",
                "meta": {"source": "test"},
                "timestamp": "2026-03-29T00:00:00Z",
                "dataset": "two_spiral",
            }
        }

        result = adapter.get_canopy_params()

        assert result == {
            "nn_learning_rate": 0.03,
            "nn_max_hidden_units": 7,
            "nn_max_total_epochs": 100,
        }

    def test_apply_params_maps_candidate_namespace_keys(self, adapter, mock_client):
        """cn_* candidate params should map to candidate_* cascor keys."""
        mock_client.update_params.return_value = {"updated": True}

        result = adapter.apply_params(
            cn_patience=13,
            cn_training_convergence_threshold=0.0005,
        )

        assert result["ok"] is True
        mock_client.update_params.assert_called_once_with(
            {
                "candidate_patience": 13,
                "candidate_convergence_threshold": 0.0005,
            }
        )

    def test_get_canopy_params_maps_candidate_namespace_keys(self, adapter, mock_client):
        """Reverse mapping should expose candidate_* params as canopy cn_* keys."""
        mock_client.get_training_params.return_value = {
            "data": {
                "params": {
                    "candidate_patience": 21,
                    "candidate_convergence_threshold": 0.00025,
                }
            }
        }

        result = adapter.get_canopy_params()

        assert result["cn_patience"] == 21
        assert result["cn_training_convergence_threshold"] == 0.00025

    def test_get_canopy_params_returns_empty_dict_on_client_error(self, adapter, mock_client):
        from juniper_cascor_client.exceptions import JuniperCascorConnectionError

        mock_client.get_training_params.side_effect = JuniperCascorConnectionError("connection down")

        assert adapter.get_canopy_params() == {}

    def test_get_canopy_params_maps_candidate_fields(self, adapter, mock_client):
        """Candidate parameters should map from cascor names to canopy cn_* names."""
        mock_client.get_training_params.return_value = {
            "data": {
                "params": {
                    "candidate_patience": 31,
                    "candidate_convergence_threshold": 0.0002,
                    "candidate_pool_size": 12,
                }
            }
        }

        result = adapter.get_canopy_params()

        assert result["cn_patience"] == 31
        assert result["cn_training_convergence_threshold"] == 0.0002
        assert result["cn_pool_size"] == 12

    def test_apply_params_maps_candidate_fields_and_skips_unmapped(self, adapter, mock_client):
        """apply_params() should forward mapped candidate fields only."""
        mock_client.update_params.return_value = {"ok": True}

        result = adapter.apply_params(
            cn_patience=25,
            cn_training_convergence_threshold=0.001,
            cn_pool_size=9,
            canopy_only_param=True,
        )

        mock_client.update_params.assert_called_once_with(
            {
                "candidate_patience": 25,
                "candidate_convergence_threshold": 0.001,
                "candidate_pool_size": 9,
            }
        )
        assert result == {"ok": True, "data": {"ok": True}}

    def test_param_map_values_are_unique(self):
        """Forward map values must be unique to avoid reverse-map collisions."""
        cascor_param_names = list(CascorServiceAdapter._CANOPY_TO_CASCOR_PARAM_MAP.values())
        assert len(cascor_param_names) == len(set(cascor_param_names))


# =========================================================================
# Network property
# =========================================================================


class TestNetworkProperty:
    """Verify the network property returns sentinel or None."""

    def test_network_truthy_when_exists(self, adapter, mock_client):
        network = adapter.network
        assert network is not None
        assert bool(network) is True

    def test_network_none_when_error(self, adapter, mock_client):
        from juniper_cascor_client.exceptions import JuniperCascorConnectionError

        mock_client.get_network.side_effect = JuniperCascorConnectionError("no conn")
        assert adapter.network is None

    def test_network_none_when_empty_response(self, adapter, mock_client):
        mock_client.get_network.return_value = {}
        # Empty dict is falsy so should return None
        assert adapter.network is None


# =========================================================================
# _training_stop_requested
# =========================================================================


class TestTrainingStopRequested:
    """Tests for training stop request flag in CascorServiceAdapter."""

    def test_always_false(self, adapter):
        assert adapter._training_stop_requested is False


# =========================================================================
# No-op methods
# =========================================================================


class TestNoOpMethods:
    """Verify monitoring/worker stubs return expected values."""

    def test_install_monitoring_hooks(self, adapter):
        assert adapter.install_monitoring_hooks() is True

    def test_start_monitoring_thread(self, adapter):
        assert adapter.start_monitoring_thread(interval=2.0) is None

    def test_stop_monitoring(self, adapter):
        assert adapter.stop_monitoring() is None

    def test_restore_original_methods(self, adapter):
        assert adapter.restore_original_methods() is None

    def test_create_monitoring_callback(self, adapter):
        assert adapter.create_monitoring_callback("epoch_end", lambda: None) is None

    def test_get_remote_worker_status(self, adapter):
        status = adapter.get_remote_worker_status()
        assert status["available"] is False
        assert status["connected"] is False

    def test_connect_remote_workers(self, adapter):
        assert adapter.connect_remote_workers(("host", 5000), "key") is False

    def test_start_remote_workers(self, adapter):
        assert adapter.start_remote_workers(2) is False

    def test_stop_remote_workers(self, adapter):
        assert adapter.stop_remote_workers(10) is False

    def test_disconnect_remote_workers(self, adapter):
        assert adapter.disconnect_remote_workers() is False


# =========================================================================
# _ServiceTrainingMonitor
# =========================================================================


class TestServiceTrainingMonitor:
    """Verify the training monitor delegates to the client."""

    def test_is_training_false(self, mock_client):
        monitor = _ServiceTrainingMonitor(mock_client)
        assert monitor.is_training is False

    def test_is_training_true(self, mock_client):
        mock_client.get_training_status.return_value = {"is_training": True}
        monitor = _ServiceTrainingMonitor(mock_client)
        assert monitor.is_training is True

    def test_is_training_on_connection_error(self, mock_client):
        from juniper_cascor_client.exceptions import JuniperCascorConnectionError

        mock_client.get_training_status.side_effect = JuniperCascorConnectionError("fail")
        monitor = _ServiceTrainingMonitor(mock_client)
        assert monitor.is_training is False

    def test_get_current_metrics(self, mock_client):
        monitor = _ServiceTrainingMonitor(mock_client)
        metrics = monitor.get_current_metrics()
        assert metrics == {"loss": 0.5, "accuracy": 0.8}

    def test_get_current_metrics_on_error(self, mock_client):
        from juniper_cascor_client.exceptions import JuniperCascorConnectionError

        mock_client.get_metrics.side_effect = JuniperCascorConnectionError("fail")
        monitor = _ServiceTrainingMonitor(mock_client)
        assert monitor.get_current_metrics() == {}

    def test_get_recent_metrics(self, mock_client):
        monitor = _ServiceTrainingMonitor(mock_client)
        metrics = monitor.get_recent_metrics(50)
        mock_client.get_metrics_history.assert_called_with(count=50)
        assert isinstance(metrics, list)
        assert len(metrics) == 1

    def test_get_recent_metrics_on_error(self, mock_client):
        from juniper_cascor_client.exceptions import JuniperCascorConnectionError

        mock_client.get_metrics_history.side_effect = JuniperCascorConnectionError("fail")
        monitor = _ServiceTrainingMonitor(mock_client)
        assert monitor.get_recent_metrics(100) == []


# =========================================================================
# Error handling
# =========================================================================


class TestErrorHandling:
    """Verify graceful fallbacks when client raises exceptions."""

    def test_create_network_on_error(self, adapter, mock_client):
        from juniper_cascor_client.exceptions import JuniperCascorConnectionError

        mock_client.create_network.side_effect = JuniperCascorConnectionError("fail")
        result = adapter.create_network({"input_size": 2})
        assert "error" in result

    def test_start_training_on_error(self, adapter, mock_client):
        from juniper_cascor_client.exceptions import JuniperCascorConnectionError

        mock_client.start_training.side_effect = JuniperCascorConnectionError("fail")
        assert adapter.start_training_background() is False

    def test_is_training_on_error(self, adapter, mock_client):
        from juniper_cascor_client.exceptions import JuniperCascorConnectionError

        mock_client.get_training_status.side_effect = JuniperCascorConnectionError("fail")
        assert adapter.is_training_in_progress() is False

    def test_request_stop_on_error(self, adapter, mock_client):
        from juniper_cascor_client.exceptions import JuniperCascorConnectionError

        mock_client.stop_training.side_effect = JuniperCascorConnectionError("fail")
        assert adapter.request_training_stop() is False

    def test_get_training_status_on_error(self, adapter, mock_client):
        from juniper_cascor_client.exceptions import JuniperCascorConnectionError

        mock_client.get_training_status.side_effect = JuniperCascorConnectionError("fail")
        result = adapter.get_training_status()
        assert result["is_training"] is False
        assert "error" in result

    def test_extract_topology_on_error(self, adapter, mock_client):
        from juniper_cascor_client.exceptions import JuniperCascorConnectionError

        mock_client.get_topology.side_effect = JuniperCascorConnectionError("fail")
        assert adapter.extract_network_topology() is None

    def test_get_dataset_info_on_error(self, adapter, mock_client):
        from juniper_cascor_client.exceptions import JuniperCascorConnectionError

        mock_client.get_dataset.side_effect = JuniperCascorConnectionError("fail")
        assert adapter.get_dataset_info() is None

    def test_get_network_data_on_error(self, adapter, mock_client):
        from juniper_cascor_client.exceptions import JuniperCascorConnectionError

        mock_client.get_statistics.side_effect = JuniperCascorConnectionError("fail")
        assert adapter.get_network_data() == {}


# =========================================================================
# Async connect
# =========================================================================


class TestAsyncConnect:
    """Verify async connection lifecycle."""

    @pytest.mark.asyncio
    async def test_connect_success(self, adapter, mock_client):
        result = await adapter.connect()
        assert result is True
        mock_client.is_alive.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_not_alive(self, adapter, mock_client):
        mock_client.is_alive.return_value = False
        result = await adapter.connect()
        assert result is False

    @pytest.mark.asyncio
    async def test_connect_on_error(self, adapter, mock_client):
        mock_client.is_alive.side_effect = ConnectionError("refused")
        result = await adapter.connect()
        assert result is False


# =========================================================================
# Shutdown
# =========================================================================


class TestShutdown:
    """Verify shutdown closes the client."""

    def test_shutdown_closes_client(self, adapter, mock_client):
        adapter.shutdown()
        mock_client.close.assert_called_once()

    def test_shutdown_handles_error(self, adapter, mock_client):
        mock_client.close.side_effect = Exception("close failed")
        # Should not raise
        adapter.shutdown()


# =========================================================================
# WebSocket URL derivation
# =========================================================================


class TestWebSocketURL:
    """Tests for WebSocket URL construction from service URL."""

    def test_ws_url_from_http(self):
        adapter = CascorServiceAdapter(service_url="http://localhost:8200")
        assert adapter._ws_url == "ws://localhost:8200"

    def test_ws_url_from_https(self):
        adapter = CascorServiceAdapter(service_url="https://cascor.example.com")
        assert adapter._ws_url == "wss://cascor.example.com"


# =========================================================================
# Phase 6E Sprint B (B-5): snapshot operation endpoints
# =========================================================================


class TestSnapshotOperationsB5:
    """Verify replay/resume/retrain adapter methods proxy through ``_post``."""

    def test_replay_snapshot_calls_replay_endpoint(self, adapter, mock_client):
        mock_client._post.return_value = {"snapshot_id": "demo_001", "operation": "replay"}
        result = adapter.replay_snapshot("demo_001")
        mock_client._post.assert_called_once_with("/v1/snapshots/demo_001/replay")
        assert result["operation"] == "replay"

    def test_replay_control_passes_action_and_params(self, adapter, mock_client):
        mock_client._post.return_value = {"action": "seek", "time_index": 42}
        adapter.replay_control("demo_001", "seek", time_index=42)
        mock_client._post.assert_called_once()
        args, kwargs = mock_client._post.call_args
        assert args[0] == "/v1/snapshots/demo_001/replay/control"
        assert kwargs["json"] == {"action": "seek", "time_index": 42}

    def test_replay_control_drops_none_params(self, adapter, mock_client):
        mock_client._post.return_value = {}
        adapter.replay_control("demo_001", "play", time_index=None, value=None)
        kwargs = mock_client._post.call_args.kwargs
        assert kwargs["json"] == {"action": "play"}

    def test_resume_snapshot_calls_resume_endpoint(self, adapter, mock_client):
        mock_client._post.return_value = {"snapshot_id": "demo_001", "operation": "resume"}
        adapter.resume_snapshot("demo_001")
        mock_client._post.assert_called_once_with("/v1/snapshots/demo_001/resume")

    def test_retrain_snapshot_calls_retrain_endpoint(self, adapter, mock_client):
        mock_client._post.return_value = {"snapshot_id": "demo_001", "operation": "retrain"}
        adapter.retrain_snapshot("demo_001")
        mock_client._post.assert_called_once_with("/v1/snapshots/demo_001/retrain")

    def test_replay_snapshot_propagates_client_error(self, adapter, mock_client):
        from juniper_cascor_client import JuniperCascorClientError

        mock_client._post.side_effect = JuniperCascorClientError("boom")
        with pytest.raises(JuniperCascorClientError):
            adapter.replay_snapshot("demo_001")


# =========================================================================
# Phase 6E CAN-015h-4: network mutation endpoints
# =========================================================================


class TestNetworkMutationsH4:
    """Verify patch_weights / add_hidden_unit / remove_hidden_unit adapter
    methods proxy through ``_patch`` / ``_post`` / ``_delete``."""

    def test_patch_weights_output_target(self, adapter, mock_client):
        mock_client._patch.return_value = {"operation": "patch_weights", "fsm_state": "INVESTIGATING"}
        result = adapter.patch_weights(target="output", field="weights", values=[[0.1], [0.2]])
        mock_client._patch.assert_called_once()
        args, kwargs = mock_client._patch.call_args
        assert args[0] == "/v1/network/weights"
        assert kwargs["json"] == {
            "target": "output",
            "field": "weights",
            "values": [[0.1], [0.2]],
            "dtype": "float32",
        }
        assert result["operation"] == "patch_weights"

    def test_patch_weights_hidden_unit_target_includes_index(self, adapter, mock_client):
        mock_client._patch.return_value = {"operation": "patch_weights"}
        adapter.patch_weights(
            target="hidden_unit",
            field="bias",
            values=[0.5],
            hidden_unit_index=2,
        )
        kwargs = mock_client._patch.call_args.kwargs
        assert kwargs["json"]["hidden_unit_index"] == 2
        assert kwargs["json"]["target"] == "hidden_unit"
        assert kwargs["json"]["field"] == "bias"

    def test_patch_weights_hidden_unit_index_omitted_for_output(self, adapter, mock_client):
        # When target is "output", hidden_unit_index must not appear
        # in the body — the cascor route's Pydantic body has it as
        # Optional and the validation requires it to be None for
        # output-target patches.
        mock_client._patch.return_value = {}
        adapter.patch_weights(target="output", field="bias", values=[0.0])
        kwargs = mock_client._patch.call_args.kwargs
        assert "hidden_unit_index" not in kwargs["json"]

    def test_patch_weights_propagates_client_error(self, adapter, mock_client):
        from juniper_cascor_client import JuniperCascorClientError

        mock_client._patch.side_effect = JuniperCascorClientError("422 NaN")
        with pytest.raises(JuniperCascorClientError):
            adapter.patch_weights(target="output", field="weights", values=[[float("nan")]])

    def test_add_hidden_unit_calls_post_with_tail_position(self, adapter, mock_client):
        mock_client._post.return_value = {"operation": "add_hidden_unit", "unit_index": 3}
        result = adapter.add_hidden_unit(weights=[0.1, 0.2, 0.3], bias=0.0, activation="Tanh")
        mock_client._post.assert_called_once()
        args, kwargs = mock_client._post.call_args
        assert args[0] == "/v1/network/hidden-units"
        assert kwargs["json"] == {
            "weights": [0.1, 0.2, 0.3],
            "bias": 0.0,
            "activation": "Tanh",
            "position": "tail",
        }
        assert result["unit_index"] == 3

    def test_add_hidden_unit_default_activation_and_bias(self, adapter, mock_client):
        mock_client._post.return_value = {}
        adapter.add_hidden_unit(weights=[0.0, 0.0])
        kwargs = mock_client._post.call_args.kwargs
        assert kwargs["json"]["bias"] == 0.0
        assert kwargs["json"]["activation"] == "Tanh"

    def test_add_hidden_unit_propagates_client_error(self, adapter, mock_client):
        from juniper_cascor_client import JuniperCascorClientError

        mock_client._post.side_effect = JuniperCascorClientError("409 at cap")
        with pytest.raises(JuniperCascorClientError):
            adapter.add_hidden_unit(weights=[0.0, 0.0])

    def test_remove_hidden_unit_calls_delete(self, adapter, mock_client):
        mock_client._delete.return_value = {"operation": "remove_hidden_unit", "removed_index": 1, "num_hidden_units": 2}
        result = adapter.remove_hidden_unit(idx=1)
        mock_client._delete.assert_called_once_with("/v1/network/hidden-units/1")
        assert result["removed_index"] == 1
        assert result["num_hidden_units"] == 2

    def test_remove_hidden_unit_propagates_client_error(self, adapter, mock_client):
        from juniper_cascor_client import JuniperCascorClientError

        mock_client._delete.side_effect = JuniperCascorClientError("404 out of range")
        with pytest.raises(JuniperCascorClientError):
            adapter.remove_hidden_unit(idx=99)


# =========================================================================
# Topology completeness — defense against count-only WS stubs
# =========================================================================


class TestIsCompleteTopology:
    """Regression for the cascade_add stub-payload bug.

    Pre-fix cascor servers broadcast a count-only stub on cascade_add
    (``hidden_units`` as an int). Passing such a payload to
    ``_transform_topology`` collapses the topology to inputs+outputs only —
    the transform's ``isinstance(int, list) is False`` path drops every
    hidden node and every cascade connection. ``_is_complete_topology``
    is the gate the dashboard callback uses to fall through to REST when
    a stub is detected.
    """

    def test_cascor_format_with_list_hidden_units_is_complete(self):
        raw = {
            "input_size": 2,
            "output_size": 2,
            "hidden_units": [{"id": 0, "weights": [0.1, 0.2, 0.3], "bias": 0.0, "activation": "sigmoid"}],
            "output_weights": [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]],
            "output_bias": [0.0, 0.0],
        }
        assert CascorServiceAdapter._is_complete_topology(raw) is True

    def test_cascor_format_with_empty_list_hidden_units_is_complete(self):
        # Untrained network — list is empty, but still structurally complete.
        raw = {
            "input_size": 2,
            "output_size": 2,
            "hidden_units": [],
            "output_weights": [[0.1, 0.2], [0.3, 0.4]],
            "output_bias": [0.0, 0.0],
        }
        assert CascorServiceAdapter._is_complete_topology(raw) is True

    def test_graph_format_with_nodes_is_complete(self):
        raw = {
            "input_units": 2,
            "output_units": 2,
            "hidden_units": 1,  # Graph format uses an int count here, by design.
            "nodes": [{"id": "input_0", "type": "input", "layer": 0}],
            "connections": [],
        }
        assert CascorServiceAdapter._is_complete_topology(raw) is True

    def test_count_only_stub_is_incomplete(self):
        # The exact stub shape pre-fix cascor was broadcasting on cascade_add.
        stub = {
            "hidden_units": 1,
            "input_size": 2,
            "output_size": 2,
            "event": "cascade_add",
        }
        assert CascorServiceAdapter._is_complete_topology(stub) is False

    def test_graph_format_without_nodes_is_incomplete(self):
        # input_units present but nodes missing/non-list → cannot trust as graph format.
        raw = {"input_units": 2, "output_units": 2, "hidden_units": 1}
        assert CascorServiceAdapter._is_complete_topology(raw) is False

    def test_non_dict_payload_is_incomplete(self):
        assert CascorServiceAdapter._is_complete_topology(None) is False
        assert CascorServiceAdapter._is_complete_topology([]) is False
        assert CascorServiceAdapter._is_complete_topology("topology") is False
        assert CascorServiceAdapter._is_complete_topology(42) is False

    def test_empty_dict_is_incomplete(self):
        assert CascorServiceAdapter._is_complete_topology({}) is False


class TestTransformTopologyHiddenUnits:
    """Verify ``_transform_topology`` produces non-zero hidden nodes when the
    cascor payload carries a list-shaped ``hidden_units``. Regression
    for the canopy-side symptom of the cascade_add stub bug.
    """

    def test_transform_produces_hidden_nodes_and_cascade_connections(self):
        # 2 inputs, 2 outputs, 1 hidden unit. Cascade-correlation weights for
        # the hidden unit cover [bias_proxy, input_0, input_1] = 3 values.
        # output_weights is shape (input_size + num_hidden, output_size) =
        # (3, 2), so 3 rows × 2 cols.
        raw = {
            "input_size": 2,
            "output_size": 2,
            "hidden_units": [
                {"id": 0, "weights": [0.1, 0.2, 0.3], "bias": 0.0, "activation": "sigmoid"},
            ],
            "output_weights": [
                [0.5, 0.6],  # row for input_0
                [0.7, 0.8],  # row for input_1
                [0.9, 1.0],  # row for hidden_0
            ],
            "output_bias": [0.0, 0.0],
        }

        out = CascorServiceAdapter._transform_topology(raw)

        assert out["input_units"] == 2
        assert out["output_units"] == 2
        assert out["hidden_units"] == 1
        # Node accounting: 2 input + 1 hidden + 2 output = 5
        node_types = [n["type"] for n in out["nodes"]]
        assert node_types.count("input") == 2
        assert node_types.count("hidden") == 1
        assert node_types.count("output") == 2
        # Connection accounting:
        # - 2 input→hidden_0 (from hidden unit's input weights)
        # - 2 input→output_X (per output) × 2 outputs = 4
        # - 1 hidden_0→output_X × 2 outputs = 2
        # Total = 8
        connections = out["connections"]
        assert any(c["from"] == "input_0" and c["to"] == "hidden_0" for c in connections)
        assert any(c["from"] == "input_1" and c["to"] == "hidden_0" for c in connections)
        assert any(c["from"] == "hidden_0" and c["to"] == "output_0" for c in connections)
        assert any(c["from"] == "hidden_0" and c["to"] == "output_1" for c in connections)
        assert len(connections) == 8

    def test_transform_count_only_stub_collapses_to_zero_hidden(self):
        """Documents the silent corruption the new gate guards against.

        This is the failure mode without ``_is_complete_topology`` upstream:
        the transform produces a structurally-valid but semantically-wrong
        topology with 0 hidden nodes and only input→output connections.
        """
        stub = {
            "hidden_units": 1,
            "input_size": 2,
            "output_size": 2,
            "event": "cascade_add",
        }
        out = CascorServiceAdapter._transform_topology(stub)
        # Demonstrate the collapse: hidden_units becomes 0 despite the stub
        # claiming 1. Callers must use ``_is_complete_topology`` to refuse
        # this payload before it reaches the transform.
        assert out["hidden_units"] == 0
        assert all(n["type"] != "hidden" for n in out["nodes"])
        assert all("hidden" not in c["from"] and "hidden" not in c["to"] for c in out["connections"])
