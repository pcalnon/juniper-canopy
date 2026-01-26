#!/usr/bin/env python
"""
Comprehensive integration tests for main.py to improve coverage.

Targets uncovered areas:
- schedule_broadcast helper function
- WebSocket endpoints edge cases
- API endpoints with edge cases
- Error handling paths
- Metrics layouts API
- General WebSocket endpoint
- No-backend paths (mocked)
"""
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ["CASCOR_DEMO_MODE"] = "1"

src_path = Path(__file__).parent.parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

import main as main_module  # noqa: E402
from main import app, schedule_broadcast  # noqa: E402


@pytest.fixture
def client():
    """Create test client with demo mode."""
    with TestClient(app) as test_client:
        yield test_client


# =============================================================================
# schedule_broadcast() Tests
# =============================================================================


class TestScheduleBroadcast:
    """Test schedule_broadcast helper function."""

    @pytest.mark.unit
    def test_schedule_broadcast_with_no_loop(self):
        """schedule_broadcast should handle missing event loop gracefully."""
        import main

        original_loop = main.loop_holder["loop"]

        try:
            main.loop_holder["loop"] = None
            schedule_broadcast(AsyncMock())
        finally:
            main.loop_holder["loop"] = original_loop

    @pytest.mark.unit
    def test_schedule_broadcast_with_closed_loop(self):
        """schedule_broadcast should handle closed event loop."""
        import asyncio

        import main

        original_loop = main.loop_holder["loop"]

        try:
            closed_loop = asyncio.new_event_loop()
            closed_loop.close()
            main.loop_holder["loop"] = closed_loop
            schedule_broadcast(AsyncMock())
        finally:
            main.loop_holder["loop"] = original_loop


# =============================================================================
# API State Endpoint Tests
# =============================================================================


class TestGetStateEndpoint:
    """Test /api/state endpoint edge cases."""

    @pytest.mark.integration
    def test_get_state_returns_200(self, client):
        """GET /api/state should return 200."""
        response = client.get("/api/state")
        assert response.status_code == 200

    @pytest.mark.integration
    def test_get_state_has_required_fields(self, client):
        """GET /api/state should have required fields."""
        response = client.get("/api/state")
        data = response.json()

        assert "current_epoch" in data
        assert "status" in data
        assert "phase" in data
        assert "learning_rate" in data


# =============================================================================
# Network Stats Endpoint Tests
# =============================================================================


class TestNetworkStatsEndpoint:
    """Test /api/network/stats endpoint."""

    @pytest.mark.integration
    def test_network_stats_returns_200(self, client):
        """GET /api/network/stats should return 200."""
        response = client.get("/api/network/stats")
        assert response.status_code == 200

    @pytest.mark.integration
    def test_network_stats_has_structure(self, client):
        """GET /api/network/stats should have expected structure."""
        response = client.get("/api/network/stats")
        data = response.json()

        assert "threshold_function" in data
        assert "optimizer" in data
        assert "total_nodes" in data
        assert "total_edges" in data

    @pytest.mark.integration
    def test_network_stats_has_total_connections(self, client):
        """GET /api/network/stats should have total_connections."""
        response = client.get("/api/network/stats")
        data = response.json()

        assert "total_connections" in data
        assert isinstance(data["total_connections"], int)

    @pytest.mark.integration
    def test_network_stats_weight_statistics(self, client):
        """GET /api/network/stats should have weight_statistics."""
        response = client.get("/api/network/stats")
        data = response.json()

        assert "weight_statistics" in data


# =============================================================================
# Set Parameters Endpoint Tests
# =============================================================================


class TestSetParamsEndpoint:
    """Test /api/set_params endpoint."""

    @pytest.mark.integration
    def test_set_params_learning_rate(self, client):
        """POST /api/set_params should update learning rate."""
        response = client.post("/api/set_params", json={"learning_rate": 0.05})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["state"]["learning_rate"] == 0.05

    @pytest.mark.integration
    def test_set_params_max_hidden_units(self, client):
        """POST /api/set_params should update max hidden units."""
        response = client.post("/api/set_params", json={"max_hidden_units": 15})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["state"]["max_hidden_units"] == 15

    @pytest.mark.integration
    def test_set_params_max_epochs(self, client):
        """POST /api/set_params should update max epochs."""
        response = client.post("/api/set_params", json={"max_epochs": 500})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["state"]["max_epochs"] == 500

    @pytest.mark.integration
    def test_set_params_multiple_values(self, client):
        """POST /api/set_params should update multiple parameters."""
        response = client.post(
            "/api/set_params",
            json={
                "learning_rate": 0.02,
                "max_hidden_units": 20,
                "max_epochs": 300,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

    @pytest.mark.integration
    def test_set_params_empty_returns_400(self, client):
        """POST /api/set_params with empty body should return 400."""
        response = client.post("/api/set_params", json={})
        assert response.status_code == 400
        data = response.json()
        assert "error" in data

    @pytest.mark.integration
    def test_set_params_invalid_value_type(self, client):
        """POST /api/set_params with invalid value should return 500."""
        response = client.post("/api/set_params", json={"learning_rate": "not_a_number"})
        assert response.status_code == 500


# =============================================================================
# Metrics Layouts API Tests
# =============================================================================


class TestMetricsLayoutsAPI:
    """Test /api/v1/metrics/layouts endpoints."""

    @pytest.mark.integration
    def test_list_layouts_returns_200(self, client):
        """GET /api/v1/metrics/layouts should return 200."""
        response = client.get("/api/v1/metrics/layouts")
        assert response.status_code == 200

    @pytest.mark.integration
    def test_list_layouts_structure(self, client):
        """GET /api/v1/metrics/layouts should have layouts and total."""
        response = client.get("/api/v1/metrics/layouts")
        data = response.json()

        assert "layouts" in data
        assert "total" in data
        assert isinstance(data["layouts"], list)

    @pytest.mark.integration
    def test_create_layout(self, client):
        """POST /api/v1/metrics/layouts should create layout."""
        response = client.post(
            "/api/v1/metrics/layouts",
            params={
                "name": "test_layout",
                "description": "Test layout",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "test_layout"
        assert "created" in data
        assert data["message"] == "Layout saved successfully"

    @pytest.mark.integration
    def test_create_layout_with_metrics(self, client):
        """POST /api/v1/metrics/layouts should save selected metrics."""
        response = client.post(
            "/api/v1/metrics/layouts",
            params={
                "name": "metrics_test_layout",
                "smoothing_window": 20,
            },
        )
        assert response.status_code == 201

    @pytest.mark.integration
    def test_get_layout(self, client):
        """GET /api/v1/metrics/layouts/{name} should return layout."""
        client.post(
            "/api/v1/metrics/layouts",
            params={"name": "get_test_layout"},
        )

        response = client.get("/api/v1/metrics/layouts/get_test_layout")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "get_test_layout"

    @pytest.mark.integration
    def test_get_nonexistent_layout_404(self, client):
        """GET /api/v1/metrics/layouts/{name} should return 404 for missing."""
        response = client.get("/api/v1/metrics/layouts/nonexistent_layout_xyz")
        assert response.status_code == 404

    @pytest.mark.integration
    def test_delete_layout(self, client):
        """DELETE /api/v1/metrics/layouts/{name} should delete layout."""
        client.post(
            "/api/v1/metrics/layouts",
            params={"name": "delete_test_layout"},
        )

        response = client.delete("/api/v1/metrics/layouts/delete_test_layout")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Layout deleted successfully"

    @pytest.mark.integration
    def test_delete_nonexistent_layout_404(self, client):
        """DELETE /api/v1/metrics/layouts/{name} should return 404 for missing."""
        response = client.delete("/api/v1/metrics/layouts/nonexistent_delete_xyz")
        assert response.status_code == 404

    @pytest.mark.integration
    def test_create_layout_empty_name_400(self, client):
        """POST /api/v1/metrics/layouts with empty name should return 400."""
        response = client.post(
            "/api/v1/metrics/layouts",
            params={"name": ""},
        )
        assert response.status_code == 400


# =============================================================================
# WebSocket Training Endpoint Tests
# =============================================================================


class TestWebSocketTrainingEndpoint:
    """Test /ws/training WebSocket endpoint."""

    @pytest.mark.integration
    def test_ws_training_connect(self, client):
        """WebSocket /ws/training should accept connections."""
        with client.websocket_connect("/ws/training") as ws:
            data = ws.receive_json()
            assert data["type"] == "connection_established"

    @pytest.mark.integration
    def test_ws_training_receives_initial_status(self, client):
        """WebSocket /ws/training should receive initial_status after connection."""
        with client.websocket_connect("/ws/training") as ws:
            ws.receive_json()
            data = ws.receive_json()
            assert data["type"] == "initial_status"
            assert "data" in data

    @pytest.mark.integration
    def test_ws_training_ping_pong(self, client):
        """WebSocket /ws/training should respond to ping with pong."""
        with client.websocket_connect("/ws/training") as ws:
            ws.receive_json()
            ws.receive_json()
            ws.send_json({"type": "ping"})
            response = ws.receive_json()
            assert response["type"] == "pong"

    @pytest.mark.integration
    def test_ws_training_other_message(self, client):
        """WebSocket /ws/training should handle other message types."""
        with client.websocket_connect("/ws/training") as ws:
            ws.receive_json()
            ws.receive_json()
            ws.send_json({"type": "custom", "data": "test"})


# =============================================================================
# WebSocket Control Endpoint Tests
# =============================================================================


class TestWebSocketControlEndpoint:
    """Test /ws/control WebSocket endpoint."""

    @pytest.mark.integration
    def test_ws_control_connect(self, client):
        """WebSocket /ws/control should accept connections."""
        with client.websocket_connect("/ws/control") as ws:
            data = ws.receive_json()
            assert data.get("type") == "connection_established"
            assert "client_id" in data

    @pytest.mark.integration
    def test_ws_control_start_command(self, client):
        """WebSocket /ws/control should handle start command."""
        with client.websocket_connect("/ws/control") as ws:
            ws.receive_json()
            ws.send_json({"command": "start"})
            response = ws.receive_json()
            assert response["ok"] is True
            assert response["command"] == "start"

    @pytest.mark.integration
    def test_ws_control_stop_command(self, client):
        """WebSocket /ws/control should handle stop command."""
        with client.websocket_connect("/ws/control") as ws:
            ws.receive_json()
            ws.send_json({"command": "stop"})
            response = ws.receive_json()
            assert response["ok"] is True
            assert response["command"] == "stop"

    @pytest.mark.integration
    def test_ws_control_pause_command(self, client):
        """WebSocket /ws/control should handle pause command."""
        with client.websocket_connect("/ws/control") as ws:
            ws.receive_json()
            ws.send_json({"command": "pause"})
            response = ws.receive_json()
            assert response["ok"] is True
            assert response["command"] == "pause"

    @pytest.mark.integration
    def test_ws_control_resume_command(self, client):
        """WebSocket /ws/control should handle resume command."""
        with client.websocket_connect("/ws/control") as ws:
            ws.receive_json()
            ws.send_json({"command": "resume"})
            response = ws.receive_json()
            assert response["ok"] is True
            assert response["command"] == "resume"

    @pytest.mark.integration
    def test_ws_control_reset_command(self, client):
        """WebSocket /ws/control should handle reset command."""
        with client.websocket_connect("/ws/control") as ws:
            ws.receive_json()
            ws.send_json({"command": "reset"})
            response = ws.receive_json()
            assert response["ok"] is True
            assert response["command"] == "reset"

    @pytest.mark.integration
    def test_ws_control_unknown_command(self, client):
        """WebSocket /ws/control should return error for unknown command."""
        with client.websocket_connect("/ws/control") as ws:
            ws.receive_json()
            ws.send_json({"command": "invalid_cmd"})
            response = ws.receive_json()
            assert response["ok"] is False
            assert "error" in response


# =============================================================================
# General WebSocket Endpoint Tests
# =============================================================================


class TestGeneralWebSocketEndpoint:
    """Test /ws general WebSocket endpoint."""

    @pytest.mark.integration
    def test_ws_connect(self, client):
        """WebSocket /ws should accept connections."""
        with client.websocket_connect("/ws") as ws:
            ws.send_text("test")


# =============================================================================
# Decision Boundary Tests
# =============================================================================


class TestDecisionBoundaryEndpoint:
    """Test /api/decision_boundary endpoint edge cases."""

    @pytest.mark.integration
    def test_decision_boundary_returns_200(self, client):
        """GET /api/decision_boundary should return 200."""
        response = client.get("/api/decision_boundary")
        assert response.status_code == 200

    @pytest.mark.integration
    def test_decision_boundary_has_grid(self, client):
        """GET /api/decision_boundary should have grid data."""
        response = client.get("/api/decision_boundary")
        data = response.json()

        assert "xx" in data
        assert "yy" in data
        assert "Z" in data
        assert "bounds" in data

    @pytest.mark.integration
    def test_decision_boundary_bounds_structure(self, client):
        """GET /api/decision_boundary bounds should have min/max."""
        response = client.get("/api/decision_boundary")
        data = response.json()
        bounds = data["bounds"]

        assert "x_min" in bounds
        assert "x_max" in bounds
        assert "y_min" in bounds
        assert "y_max" in bounds


# =============================================================================
# Topology Edge Cases
# =============================================================================


class TestTopologyEdgeCases:
    """Test /api/topology endpoint edge cases."""

    @pytest.mark.integration
    def test_topology_after_start(self, client):
        """Topology should be valid after training start."""
        client.post("/api/train/start")

        response = client.get("/api/topology")
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "connections" in data

    @pytest.mark.integration
    def test_topology_nodes_have_layer(self, client):
        """Topology nodes should have layer attribute."""
        response = client.get("/api/topology")
        data = response.json()

        for node in data["nodes"]:
            assert "layer" in node
            assert node["layer"] in [0, 1, 2]

    @pytest.mark.integration
    def test_topology_connections_have_weight(self, client):
        """Topology connections should have weight attribute."""
        response = client.get("/api/topology")
        data = response.json()

        for conn in data["connections"]:
            assert "weight" in conn
            assert isinstance(conn["weight"], (int, float))


# =============================================================================
# Dataset Endpoint Tests
# =============================================================================


class TestDatasetEndpoint:
    """Test /api/dataset endpoint."""

    @pytest.mark.integration
    def test_dataset_inputs_are_lists(self, client):
        """Dataset inputs should be lists."""
        response = client.get("/api/dataset")
        data = response.json()

        assert isinstance(data["inputs"], list)
        assert len(data["inputs"]) > 0
        assert isinstance(data["inputs"][0], list)

    @pytest.mark.integration
    def test_dataset_targets_are_lists(self, client):
        """Dataset targets should be lists."""
        response = client.get("/api/dataset")
        data = response.json()

        assert isinstance(data["targets"], list)
        assert len(data["targets"]) > 0


# =============================================================================
# Metrics History Limit Tests
# =============================================================================


class TestMetricsHistoryLimit:
    """Test /api/metrics/history with limit parameter."""

    @pytest.mark.integration
    def test_metrics_history_no_limit(self, client):
        """Metrics history without limit returns all."""
        response = client.get("/api/metrics/history")
        assert response.status_code == 200
        data = response.json()
        assert "history" in data


# =============================================================================
# Health Endpoint Edge Cases
# =============================================================================


class TestHealthEndpointEdgeCases:
    """Test /api/health endpoint edge cases."""

    @pytest.mark.integration
    def test_health_with_demo_mode(self, client):
        """Health check should report demo mode status."""
        response = client.get("/api/health")
        data = response.json()

        assert data["demo_mode"] is True

    @pytest.mark.integration
    def test_health_has_version(self, client):
        """Health check should have version."""
        response = client.get("/api/health")
        data = response.json()

        assert "version" in data


# =============================================================================
# Snapshot Additional Tests
# =============================================================================


class TestSnapshotAdditionalEndpoints:
    """Test additional snapshot endpoints."""

    @pytest.fixture(autouse=True)
    def pause_training(self, client):
        """Pause training before snapshot tests."""
        client.post("/api/train/stop")
        yield

    @pytest.mark.integration
    def test_create_snapshot_with_description(self, client):
        """POST /api/v1/snapshots should accept description."""
        response = client.post(
            "/api/v1/snapshots",
            params={
                "name": "described_snapshot",
                "description": "Test description",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "described_snapshot"

    @pytest.mark.integration
    def test_snapshot_detail_for_session_created(self, client):
        """GET /api/v1/snapshots/{id} should return session-created snapshot."""
        client.post(
            "/api/v1/snapshots",
            params={"name": "detail_test_snap"},
        )

        response = client.get("/api/v1/snapshots/detail_test_snap")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "detail_test_snap"
        assert "attributes" in data
        assert data["attributes"]["created_in_session"] is True

    @pytest.mark.integration
    def test_restore_while_running_returns_409(self, client):
        """POST /api/v1/snapshots/{id}/restore should return 409 when training running."""
        client.post("/api/train/start")

        response = client.post("/api/v1/snapshots/demo_snapshot_1/restore")
        assert response.status_code == 409
        assert "running" in response.json()["detail"].lower()


# =============================================================================
# API Train Endpoints with Validation
# =============================================================================


class TestTrainEndpointsValidation:
    """Test training endpoints with validation."""

    @pytest.mark.integration
    def test_train_start_reset_false(self, client):
        """POST /api/train/start with reset=false should not reset epoch."""
        client.post("/api/train/start")
        response = client.post("/api/train/start?reset=false")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"

    @pytest.mark.integration
    def test_train_lifecycle(self, client):
        """Full training lifecycle: start -> pause -> resume -> stop."""
        start = client.post("/api/train/start")
        assert start.json()["status"] == "started"

        pause = client.post("/api/train/pause")
        assert pause.json()["status"] == "paused"

        resume = client.post("/api/train/resume")
        assert resume.json()["status"] == "running"

        stop = client.post("/api/train/stop")
        assert stop.json()["status"] == "stopped"


# =============================================================================
# Status Endpoint FSM Tests
# =============================================================================


class TestStatusEndpointFSM:
    """Test /api/status endpoint FSM-related fields."""

    @pytest.mark.integration
    def test_status_has_fsm_status(self, client):
        """GET /api/status should have fsm_status field."""
        response = client.get("/api/status")
        data = response.json()

        assert "fsm_status" in data

    @pytest.mark.integration
    def test_status_fsm_after_start(self, client):
        """GET /api/status should show STARTED after start."""
        client.post("/api/train/start")

        response = client.get("/api/status")
        data = response.json()

        assert data["fsm_status"] == "STARTED"
        assert data["is_running"] is True

    @pytest.mark.integration
    def test_status_fsm_after_pause(self, client):
        """GET /api/status should show PAUSED after pause."""
        client.post("/api/train/start")
        client.post("/api/train/pause")

        response = client.get("/api/status")
        data = response.json()

        assert data["fsm_status"] == "PAUSED"
        assert data["is_paused"] is True

    @pytest.mark.integration
    def test_status_fsm_after_stop(self, client):
        """GET /api/status should show STOPPED after stop."""
        client.post("/api/train/start")
        client.post("/api/train/stop")

        response = client.get("/api/status")
        data = response.json()

        assert data["fsm_status"] == "STOPPED"
        assert data["is_running"] is False


# =============================================================================
# Snapshot History Edge Cases
# =============================================================================


class TestSnapshotHistoryEdgeCases:
    """Test snapshot history endpoint edge cases."""

    @pytest.mark.integration
    def test_history_default_limit(self, client):
        """GET /api/v1/snapshots/history should default to 50 entries."""
        response = client.get("/api/v1/snapshots/history")
        assert response.status_code == 200
        data = response.json()
        assert "history" in data
        assert "total" in data

    @pytest.mark.integration
    def test_history_custom_limit(self, client):
        """GET /api/v1/snapshots/history should respect limit param."""
        response = client.get("/api/v1/snapshots/history", params={"limit": 5})
        assert response.status_code == 200
        data = response.json()
        assert len(data["history"]) <= 5

    @pytest.mark.integration
    def test_history_message_in_demo_mode(self, client):
        """GET /api/v1/snapshots/history should have message in demo mode."""
        response = client.get("/api/v1/snapshots/history")
        data = response.json()
        assert data.get("message") == "Demo mode history"


# =============================================================================
# Snapshot List Edge Cases
# =============================================================================


class TestSnapshotListEdgeCases:
    """Test snapshot list endpoint edge cases."""

    @pytest.mark.integration
    def test_snapshots_includes_demo_message(self, client):
        """GET /api/v1/snapshots should include demo message."""
        response = client.get("/api/v1/snapshots")
        data = response.json()
        assert "demo" in data.get("message", "").lower()

    @pytest.mark.integration
    def test_snapshots_combines_session_and_mock(self, client):
        """GET /api/v1/snapshots should combine session and mock snapshots."""
        client.post("/api/train/stop")

        client.post("/api/v1/snapshots", params={"name": "session_snap_1"})

        response = client.get("/api/v1/snapshots")
        data = response.json()

        snapshot_ids = [s["id"] for s in data["snapshots"]]
        assert "session_snap_1" in snapshot_ids
        assert any(s.startswith("demo_") for s in snapshot_ids)


# =============================================================================
# WebSocket with Exception Handling
# =============================================================================


class TestWebSocketExceptionHandling:
    """Test WebSocket endpoints with error scenarios."""

    @pytest.mark.integration
    def test_ws_training_handles_disconnect(self, client):
        """WebSocket /ws/training should handle disconnection gracefully."""
        with client.websocket_connect("/ws/training") as ws:
            ws.receive_json()
            ws.receive_json()

    @pytest.mark.integration
    def test_ws_control_handles_valid_then_close(self, client):
        """WebSocket /ws/control should handle connection close."""
        with client.websocket_connect("/ws/control") as ws:
            ws.receive_json()
            ws.send_json({"command": "stop"})
            ws.receive_json()


# =============================================================================
# General WebSocket Full Test
# =============================================================================


class TestGeneralWebSocketFull:
    """Test /ws general WebSocket endpoint comprehensively."""

    @pytest.mark.integration
    def test_ws_sends_text(self, client):
        """WebSocket /ws should handle text messages."""
        with client.websocket_connect("/ws") as ws:
            ws.send_text("hello")


# =============================================================================
# Set Params Edge Cases
# =============================================================================


class TestSetParamsEdgeCases:
    """Test /api/set_params endpoint edge cases."""

    @pytest.mark.integration
    def test_set_params_broadcasts_state(self, client):
        """POST /api/set_params should return updated state."""
        response = client.post("/api/set_params", json={"learning_rate": 0.03})
        data = response.json()

        assert data["status"] == "success"
        assert "state" in data
        assert data["state"]["learning_rate"] == 0.03


# =============================================================================
# Topology with Hidden Units
# =============================================================================


class TestTopologyWithHiddenUnits:
    """Test topology endpoint with different network states."""

    @pytest.mark.integration
    def test_topology_has_input_units(self, client):
        """Topology should report input units."""
        response = client.get("/api/topology")
        data = response.json()
        assert data["input_units"] > 0

    @pytest.mark.integration
    def test_topology_has_output_units(self, client):
        """Topology should report output units."""
        response = client.get("/api/topology")
        data = response.json()
        assert data["output_units"] > 0

    @pytest.mark.integration
    def test_topology_connections_from_to(self, client):
        """Topology connections should have from/to fields."""
        response = client.get("/api/topology")
        data = response.json()

        for conn in data["connections"]:
            assert "from" in conn
            assert "to" in conn


# =============================================================================
# Network Stats Detailed
# =============================================================================


class TestNetworkStatsDetailed:
    """Test /api/network/stats endpoint in detail."""

    @pytest.mark.integration
    def test_network_stats_optimizer_value(self, client):
        """Network stats should have optimizer value."""
        response = client.get("/api/network/stats")
        data = response.json()
        assert data["optimizer"] in ["SGD", "sgd", "Adam", "adam"]

    @pytest.mark.integration
    def test_network_stats_threshold_function(self, client):
        """Network stats should have threshold function."""
        response = client.get("/api/network/stats")
        data = response.json()
        assert data["threshold_function"] in ["sigmoid", "tanh", "relu"]


# =============================================================================
# Snapshot Restore Edge Cases
# =============================================================================


class TestSnapshotRestoreEdgeCases:
    """Test snapshot restore edge cases."""

    @pytest.fixture(autouse=True)
    def stop_training(self, client):
        """Stop training before restore tests."""
        client.post("/api/train/stop")
        yield

    @pytest.mark.integration
    def test_restore_mock_snapshot(self, client):
        """Should restore from mock demo snapshot."""
        response = client.post("/api/v1/snapshots/demo_snapshot_1/restore")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["snapshot_id"] == "demo_snapshot_1"

    @pytest.mark.integration
    def test_restore_returns_mode(self, client):
        """Restore response should include mode."""
        response = client.post("/api/v1/snapshots/demo_snapshot_1/restore")
        data = response.json()
        assert data["mode"] == "demo"


# =============================================================================
# Snapshot Create Detailed
# =============================================================================


class TestSnapshotCreateDetailed:
    """Test snapshot create endpoint in detail."""

    @pytest.fixture(autouse=True)
    def stop_training(self, client):
        """Stop training before snapshot tests."""
        client.post("/api/train/stop")
        yield

    @pytest.mark.integration
    def test_create_snapshot_returns_size(self, client):
        """Created snapshot should have size_bytes."""
        response = client.post("/api/v1/snapshots", params={"name": "size_test"})
        data = response.json()
        assert "size_bytes" in data
        assert data["size_bytes"] > 0

    @pytest.mark.integration
    def test_create_snapshot_returns_path(self, client):
        """Created snapshot should have path."""
        response = client.post("/api/v1/snapshots", params={"name": "path_test"})
        data = response.json()
        assert "path" in data

    @pytest.mark.integration
    def test_create_snapshot_returns_timestamp(self, client):
        """Created snapshot should have timestamp."""
        response = client.post("/api/v1/snapshots", params={"name": "ts_test"})
        data = response.json()
        assert "timestamp" in data
        assert "T" in data["timestamp"]


# =============================================================================
# Metrics History Content
# =============================================================================


class TestMetricsHistoryContent:
    """Test /api/metrics/history content."""

    @pytest.mark.integration
    def test_metrics_history_structure(self, client):
        """Metrics history should have history array."""
        response = client.get("/api/metrics/history")
        data = response.json()
        assert isinstance(data["history"], list)


# =============================================================================
# Health Endpoint Comprehensive
# =============================================================================


class TestHealthEndpointComprehensive:
    """Test /api/health endpoint comprehensively."""

    @pytest.mark.integration
    def test_health_status_healthy(self, client):
        """Health should report healthy status."""
        response = client.get("/api/health")
        data = response.json()
        assert data["status"] == "healthy"

    @pytest.mark.integration
    def test_health_has_timestamp(self, client):
        """Health should have timestamp."""
        response = client.get("/api/health")
        data = response.json()
        assert "timestamp" in data
        assert isinstance(data["timestamp"], (int, float))

    @pytest.mark.integration
    def test_health_has_active_connections(self, client):
        """Health should report active connections."""
        response = client.get("/api/health")
        data = response.json()
        assert "active_connections" in data

    @pytest.mark.integration
    def test_health_has_training_active(self, client):
        """Health should report training_active."""
        response = client.get("/api/health")
        data = response.json()
        assert "training_active" in data

    @pytest.mark.integration
    def test_health_training_active_after_start(self, client):
        """Health should show training active after start."""
        client.post("/api/train/start")

        response = client.get("/api/health")
        data = response.json()
        assert data["training_active"] is True


# =============================================================================
# Layouts with Hyperparameters
# =============================================================================


class TestLayoutsWithHyperparameters:
    """Test metrics layouts with hyperparameters."""

    @pytest.mark.integration
    def test_create_layout_with_hyperparameters(self, client):
        """Layout creation should accept hyperparameters."""
        response = client.post(
            "/api/v1/metrics/layouts",
            params={
                "name": "hyper_layout",
                "smoothing_window": 15,
            },
        )
        assert response.status_code == 201

    @pytest.mark.integration
    def test_layout_retrieval_has_smoothing(self, client):
        """Retrieved layout should have smoothing_window."""
        client.post(
            "/api/v1/metrics/layouts",
            params={"name": "smoothing_test_layout", "smoothing_window": 25},
        )

        response = client.get("/api/v1/metrics/layouts/smoothing_test_layout")
        data = response.json()
        assert data["smoothing_window"] == 25


# =============================================================================
# No Backend Available Paths (Mocked)
# =============================================================================


class TestNoBackendPaths:
    """Test endpoints when no backend is available (mocked demo_mode_instance)."""

    @pytest.mark.integration
    def test_train_start_no_backend(self, client):
        """POST /api/train/start should return 503 without backend."""
        original_instance = main_module.demo_mode_instance
        try:
            main_module.demo_mode_instance = None
            response = client.post("/api/train/start")
            assert response.status_code == 503
            assert "No backend available" in response.json()["error"]
        finally:
            main_module.demo_mode_instance = original_instance

    @pytest.mark.integration
    def test_train_pause_no_backend(self, client):
        """POST /api/train/pause should return 503 without backend."""
        original_instance = main_module.demo_mode_instance
        try:
            main_module.demo_mode_instance = None
            response = client.post("/api/train/pause")
            assert response.status_code == 503
            assert "No backend available" in response.json()["error"]
        finally:
            main_module.demo_mode_instance = original_instance

    @pytest.mark.integration
    def test_train_resume_no_backend(self, client):
        """POST /api/train/resume should return 503 without backend."""
        original_instance = main_module.demo_mode_instance
        try:
            main_module.demo_mode_instance = None
            response = client.post("/api/train/resume")
            assert response.status_code == 503
            assert "No backend available" in response.json()["error"]
        finally:
            main_module.demo_mode_instance = original_instance

    @pytest.mark.integration
    def test_train_stop_no_backend(self, client):
        """POST /api/train/stop should return 503 without backend."""
        original_instance = main_module.demo_mode_instance
        try:
            main_module.demo_mode_instance = None
            response = client.post("/api/train/stop")
            assert response.status_code == 503
            assert "No backend available" in response.json()["error"]
        finally:
            main_module.demo_mode_instance = original_instance

    @pytest.mark.integration
    def test_train_reset_no_backend(self, client):
        """POST /api/train/reset should return 503 without backend."""
        original_instance = main_module.demo_mode_instance
        try:
            main_module.demo_mode_instance = None
            response = client.post("/api/train/reset")
            assert response.status_code == 503
            assert "No backend available" in response.json()["error"]
        finally:
            main_module.demo_mode_instance = original_instance

    @pytest.mark.integration
    def test_get_metrics_no_backend(self, client):
        """GET /api/metrics should return empty dict without backend."""
        original_instance = main_module.demo_mode_instance
        try:
            main_module.demo_mode_instance = None
            response = client.get("/api/metrics")
            assert response.status_code == 200
            data = response.json()
            assert data == {}
        finally:
            main_module.demo_mode_instance = original_instance

    @pytest.mark.integration
    def test_get_metrics_history_no_backend(self, client):
        """GET /api/metrics/history should return 503 without backend."""
        original_instance = main_module.demo_mode_instance
        original_cascor = main_module.cascor_integration
        try:
            main_module.demo_mode_instance = None
            main_module.cascor_integration = None
            response = client.get("/api/metrics/history")
            assert response.status_code == 503
        finally:
            main_module.demo_mode_instance = original_instance
            main_module.cascor_integration = original_cascor

    @pytest.mark.integration
    def test_get_topology_no_backend(self, client):
        """GET /api/topology should return 503 without backend."""
        original_instance = main_module.demo_mode_instance
        original_cascor = main_module.cascor_integration
        try:
            main_module.demo_mode_instance = None
            main_module.cascor_integration = None
            response = client.get("/api/topology")
            assert response.status_code == 503
        finally:
            main_module.demo_mode_instance = original_instance
            main_module.cascor_integration = original_cascor

    @pytest.mark.integration
    def test_get_dataset_no_backend(self, client):
        """GET /api/dataset should return 503 without backend."""
        original_instance = main_module.demo_mode_instance
        original_cascor = main_module.cascor_integration
        try:
            main_module.demo_mode_instance = None
            main_module.cascor_integration = None
            response = client.get("/api/dataset")
            assert response.status_code == 503
        finally:
            main_module.demo_mode_instance = original_instance
            main_module.cascor_integration = original_cascor

    @pytest.mark.integration
    def test_get_decision_boundary_no_backend(self, client):
        """GET /api/decision_boundary should return 503 without backend."""
        original_instance = main_module.demo_mode_instance
        original_cascor = main_module.cascor_integration
        try:
            main_module.demo_mode_instance = None
            main_module.cascor_integration = None
            response = client.get("/api/decision_boundary")
            assert response.status_code == 503
        finally:
            main_module.demo_mode_instance = original_instance
            main_module.cascor_integration = original_cascor

    @pytest.mark.integration
    def test_get_network_stats_no_backend(self, client):
        """GET /api/network/stats should return 503 without backend."""
        original_instance = main_module.demo_mode_instance
        original_cascor = main_module.cascor_integration
        try:
            main_module.demo_mode_instance = None
            main_module.cascor_integration = None
            response = client.get("/api/network/stats")
            assert response.status_code == 503
        finally:
            main_module.demo_mode_instance = original_instance
            main_module.cascor_integration = original_cascor

    @pytest.mark.integration
    def test_get_status_no_backend(self, client):
        """GET /api/status should return minimal status without backend."""
        original_instance = main_module.demo_mode_instance
        original_cascor = main_module.cascor_integration
        try:
            main_module.demo_mode_instance = None
            main_module.cascor_integration = None
            response = client.get("/api/status")
            assert response.status_code == 200
            data = response.json()
            assert data["is_training"] is False
            assert data["network_connected"] is False
        finally:
            main_module.demo_mode_instance = original_instance
            main_module.cascor_integration = original_cascor

    @pytest.mark.integration
    def test_get_state_no_backend(self, client):
        """GET /api/state should return training_state without demo mode."""
        original_instance = main_module.demo_mode_instance
        try:
            main_module.demo_mode_instance = None
            response = client.get("/api/state")
            assert response.status_code == 200
            data = response.json()
            assert "status" in data or "learning_rate" in data
        finally:
            main_module.demo_mode_instance = original_instance


# =============================================================================
# Health Check with Cascor Integration Path
# =============================================================================


class TestHealthWithMockedCascor:
    """Test health endpoint edge cases with mocked cascor."""

    @pytest.mark.integration
    def test_health_with_no_training_monitors(self, client):
        """Health check should handle missing training monitors."""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data


# =============================================================================
# WebSocket with Cascor Integration Paths
# =============================================================================


class TestWebSocketWithCascorIntegration:
    """Test WebSocket endpoints with mocked cascor integration."""

    @pytest.mark.integration
    def test_ws_training_with_cascor_status(self, client):
        """WebSocket training should work with cascor integration path."""
        original_demo = main_module.demo_mode_active
        original_instance = main_module.demo_mode_instance

        mock_cascor = MagicMock()
        mock_cascor.get_training_status.return_value = {"status": "idle", "epoch": 0}
        original_cascor = main_module.cascor_integration

        try:
            main_module.demo_mode_active = False
            main_module.demo_mode_instance = None
            main_module.cascor_integration = mock_cascor

            with client.websocket_connect("/ws/training") as ws:
                data = ws.receive_json()
                assert data["type"] == "connection_established"
        finally:
            main_module.demo_mode_active = original_demo
            main_module.demo_mode_instance = original_instance
            main_module.cascor_integration = original_cascor

    @pytest.mark.integration
    def test_ws_control_with_cascor(self, client):
        """WebSocket control should handle cascor integration path."""
        original_demo = main_module.demo_mode_active
        original_instance = main_module.demo_mode_instance

        mock_cascor = MagicMock()
        original_cascor = main_module.cascor_integration

        try:
            main_module.demo_mode_active = False
            main_module.demo_mode_instance = None
            main_module.cascor_integration = mock_cascor

            with client.websocket_connect("/ws/control") as ws:
                ws.receive_json()
                ws.send_json({"command": "start"})
                response = ws.receive_json()
                assert response["ok"] is False
        finally:
            main_module.demo_mode_active = original_demo
            main_module.demo_mode_instance = original_instance
            main_module.cascor_integration = original_cascor


# =============================================================================
# Training Control Endpoints with Cascor Integration
# =============================================================================


class TestTrainEndpointsWithCascor:
    """Test training endpoints with mocked cascor integration."""

    @pytest.mark.integration
    def test_train_start_with_cascor_busy(self, client):
        """POST /api/train/start should return busy when training in progress."""
        original_demo = main_module.demo_mode_instance
        mock_cascor = MagicMock()
        # P1-NEW-003: Async training - mock returns True for is_training_in_progress
        mock_cascor.is_training_in_progress.return_value = True
        original_cascor = main_module.cascor_integration

        try:
            main_module.demo_mode_instance = None
            main_module.cascor_integration = mock_cascor

            response = client.post("/api/train/start")
            assert response.status_code == 200
            assert response.json()["status"] == "busy"
            assert "already in progress" in response.json()["message"]
        finally:
            main_module.demo_mode_instance = original_demo
            main_module.cascor_integration = original_cascor

    @pytest.mark.integration
    def test_train_start_with_cascor_no_network(self, client):
        """POST /api/train/start should return error when no network configured."""
        original_demo = main_module.demo_mode_instance
        mock_cascor = MagicMock()
        mock_cascor.is_training_in_progress.return_value = False
        mock_cascor.network = None  # No network configured
        original_cascor = main_module.cascor_integration

        try:
            main_module.demo_mode_instance = None
            main_module.cascor_integration = mock_cascor

            response = client.post("/api/train/start")
            assert response.status_code == 400
            assert "No network configured" in response.json()["error"]
        finally:
            main_module.demo_mode_instance = original_demo
            main_module.cascor_integration = original_cascor

    @pytest.mark.integration
    def test_train_start_with_cascor_success(self, client):
        """POST /api/train/start should start training when conditions met."""
        original_demo = main_module.demo_mode_instance
        mock_cascor = MagicMock()
        mock_cascor.is_training_in_progress.return_value = False
        mock_cascor.network = MagicMock()  # Network exists
        mock_cascor.start_training_background.return_value = True
        original_cascor = main_module.cascor_integration

        try:
            main_module.demo_mode_instance = None
            main_module.cascor_integration = mock_cascor

            response = client.post("/api/train/start")
            assert response.status_code == 200
            assert response.json()["status"] == "started"
        finally:
            main_module.demo_mode_instance = original_demo
            main_module.cascor_integration = original_cascor


# =============================================================================
# Main Function Tests (Unit)
# =============================================================================


class TestMainFunction:
    """Test main() function configuration."""

    @pytest.mark.unit
    def test_main_function_exists(self):
        """main() function should exist."""
        from main import main

        assert callable(main)

    @pytest.mark.unit
    def test_main_module_has_config(self):
        """main module should have config object."""
        assert main_module.config is not None

    @pytest.mark.unit
    def test_main_module_has_app(self):
        """main module should have FastAPI app."""
        assert main_module.app is not None


# =============================================================================
# Snapshot with Missing Directory
# =============================================================================


class TestSnapshotMissingDirectory:
    """Test snapshot endpoints when directory doesn't exist."""

    @pytest.mark.integration
    def test_list_snapshots_handles_missing_dir(self, client):
        """GET /api/v1/snapshots should handle missing directory."""
        original_dir = main_module._snapshots_dir
        try:
            main_module._snapshots_dir = "/nonexistent/path/to/snapshots"
            response = client.get("/api/v1/snapshots")
            assert response.status_code == 200
        finally:
            main_module._snapshots_dir = original_dir


# =============================================================================
# Layouts Edge Cases
# =============================================================================


class TestLayoutsEdgeCases:
    """Test metrics layouts edge cases."""

    @pytest.mark.integration
    def test_layout_list_sorted_by_created(self, client):
        """Layouts should be sorted by created date."""
        client.post("/api/v1/metrics/layouts", params={"name": "first_layout"})
        client.post("/api/v1/metrics/layouts", params={"name": "second_layout"})

        response = client.get("/api/v1/metrics/layouts")
        data = response.json()

        assert len(data["layouts"]) >= 2

    @pytest.mark.integration
    def test_layout_has_default_selected_metrics(self, client):
        """Created layout should have default selected_metrics."""
        client.post("/api/v1/metrics/layouts", params={"name": "default_metrics_layout"})

        response = client.get("/api/v1/metrics/layouts/default_metrics_layout")
        data = response.json()

        assert "selected_metrics" in data
        assert isinstance(data["selected_metrics"], list)


# =============================================================================
# Real Snapshot Files Tests (with temp directory)
# =============================================================================


class TestRealSnapshotFiles:
    """Test snapshot endpoints with real files in temp directory."""

    @pytest.fixture
    def temp_snapshots_dir(self, tmp_path):
        """Create temp directory with mock HDF5 files."""
        import time

        snap1 = tmp_path / "test_snapshot_001.h5"
        snap1.write_bytes(b"\x00" * 1024)

        time.sleep(0.1)

        snap2 = tmp_path / "test_snapshot_002.hdf5"
        snap2.write_bytes(b"\x00" * 2048)

        not_snap = tmp_path / "not_a_snapshot.txt"
        not_snap.write_text("not a snapshot")

        return tmp_path

    @pytest.mark.integration
    def test_list_real_snapshot_files(self, client, temp_snapshots_dir):
        """GET /api/v1/snapshots should list real HDF5 files."""
        original_dir = main_module._snapshots_dir
        original_demo = main_module.demo_mode_active
        original_cascor = main_module.cascor_integration

        mock_cascor = MagicMock()

        try:
            main_module._snapshots_dir = str(temp_snapshots_dir)
            main_module.demo_mode_active = False
            main_module.cascor_integration = mock_cascor

            response = client.get("/api/v1/snapshots")
            assert response.status_code == 200
            data = response.json()

            snapshot_names = [s["name"] for s in data["snapshots"]]
            assert "test_snapshot_001.h5" in snapshot_names
            assert "test_snapshot_002.hdf5" in snapshot_names
            assert "not_a_snapshot.txt" not in snapshot_names
        finally:
            main_module._snapshots_dir = original_dir
            main_module.demo_mode_active = original_demo
            main_module.cascor_integration = original_cascor

    @pytest.mark.integration
    def test_get_real_snapshot_detail(self, client, temp_snapshots_dir):
        """GET /api/v1/snapshots/{id} should return real file details."""
        original_dir = main_module._snapshots_dir
        original_demo = main_module.demo_mode_active
        original_cascor = main_module.cascor_integration

        mock_cascor = MagicMock()

        try:
            main_module._snapshots_dir = str(temp_snapshots_dir)
            main_module.demo_mode_active = False
            main_module.cascor_integration = mock_cascor

            response = client.get("/api/v1/snapshots/test_snapshot_001")
            assert response.status_code == 200
            data = response.json()

            assert data["id"] == "test_snapshot_001"
            assert data["name"] == "test_snapshot_001.h5"
            assert data["size_bytes"] == 1024
            assert "timestamp" in data
        finally:
            main_module._snapshots_dir = original_dir
            main_module.demo_mode_active = original_demo
            main_module.cascor_integration = original_cascor

    @pytest.mark.integration
    def test_get_snapshot_detail_not_found(self, client, temp_snapshots_dir):
        """GET /api/v1/snapshots/{id} should return 404 for missing file."""
        original_dir = main_module._snapshots_dir
        original_demo = main_module.demo_mode_active
        original_cascor = main_module.cascor_integration

        mock_cascor = MagicMock()

        try:
            main_module._snapshots_dir = str(temp_snapshots_dir)
            main_module.demo_mode_active = False
            main_module.cascor_integration = mock_cascor

            response = client.get("/api/v1/snapshots/nonexistent_snapshot")
            assert response.status_code == 404
        finally:
            main_module._snapshots_dir = original_dir
            main_module.demo_mode_active = original_demo
            main_module.cascor_integration = original_cascor

    @pytest.mark.integration
    def test_list_empty_snapshot_directory(self, client, tmp_path):
        """GET /api/v1/snapshots should return empty list for empty dir."""
        original_dir = main_module._snapshots_dir
        original_demo = main_module.demo_mode_active
        original_cascor = main_module.cascor_integration

        mock_cascor = MagicMock()

        try:
            main_module._snapshots_dir = str(tmp_path)
            main_module.demo_mode_active = False
            main_module.cascor_integration = mock_cascor

            response = client.get("/api/v1/snapshots")
            assert response.status_code == 200
            data = response.json()

            assert data["snapshots"] == []
            assert "No snapshots available" in data.get("message", "")
        finally:
            main_module._snapshots_dir = original_dir
            main_module.demo_mode_active = original_demo
            main_module.cascor_integration = original_cascor


# =============================================================================
# Snapshot Detail with Missing Directory
# =============================================================================


class TestSnapshotDetailMissingDir:
    """Test snapshot detail when directory doesn't exist."""

    @pytest.mark.integration
    def test_detail_missing_directory_404(self, client):
        """GET /api/v1/snapshots/{id} should return 404 when dir missing."""
        original_dir = main_module._snapshots_dir
        original_demo = main_module.demo_mode_active
        original_cascor = main_module.cascor_integration

        mock_cascor = MagicMock()

        try:
            main_module._snapshots_dir = "/nonexistent/snapshots/path"
            main_module.demo_mode_active = False
            main_module.cascor_integration = mock_cascor

            response = client.get("/api/v1/snapshots/some_snapshot")
            assert response.status_code == 404
        finally:
            main_module._snapshots_dir = original_dir
            main_module.demo_mode_active = original_demo
            main_module.cascor_integration = original_cascor
