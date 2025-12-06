#!/usr/bin/env python
"""
Integration tests for WebSocket control endpoint and demo mode integration.
"""
import pytest

# import asyncio
# import json
# from fastapi.testclient import TestClient
# from fastapi.websockets import WebSocket


class TestWebSocketControlIntegration:
    """Integration tests for /ws/control endpoint."""

    @pytest.fixture
    def demo_app(self):
        """Create FastAPI app with demo mode for testing."""
        import os
        import sys
        from pathlib import Path

        # MUST set environment variable BEFORE importing main
        os.environ["CASCOR_DEMO_MODE"] = "1"  # Force demo mode

        # Add src to path
        src_path = Path(__file__).parent.parent.parent
        if str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))

        # Import and return app (demo_mode_active will be True)
        from main import app

        return app

    def _skip_connection_message(self, websocket):
        """Helper to consume the initial connection message."""
        conn_msg = websocket.receive_json()
        assert conn_msg.get("type") == "connection_established"
        return conn_msg

    def _receive_command_response(self, websocket, timeout_messages=10):
        """
        Helper to receive command response, skipping any broadcast messages.

        Args:
            websocket: WebSocket connection
            timeout_messages: Max messages to check before giving up

        Returns:
            Command response dict with 'ok' key
        """
        for _ in range(timeout_messages):
            msg = websocket.receive_json()
            # Skip training broadcasts (these don't have 'ok' field)
            msg_type = msg.get("type", "")
            if msg_type in ["metrics", "state", "event", "cascade_add", "status"]:
                continue  # Skip broadcast, check next message
            # Return command responses (should have 'ok' field)
            if "ok" in msg:
                return msg
            # Skip other broadcast types
            continue
        raise TimeoutError(f"Did not receive command response within {timeout_messages} messages")

    def test_control_websocket_connection(self, demo_app):
        """Test basic WebSocket connection to /ws/control."""
        from fastapi.testclient import TestClient

        with TestClient(demo_app) as client:
            with client.websocket_connect("/ws/control") as websocket:
                self._skip_connection_message(websocket)
                websocket.send_json({"command": "start", "reset": True})
                response = self._receive_command_response(websocket)
                assert response.get("ok") is True
                assert "state" in response
                assert response["state"]["is_running"]

    def test_control_start_command(self, demo_app):
        """Test start command functionality."""
        from fastapi.testclient import TestClient

        with TestClient(demo_app) as client:
            with client.websocket_connect("/ws/control") as websocket:
                self._skip_connection_message(websocket)
                websocket.send_json({"command": "start", "reset": True})
                response = self._receive_command_response(websocket)
                assert response["ok"]
                assert response["command"] == "start"
                state = response["state"]
                assert state["is_running"]
                assert state["current_epoch"] == 0  # Reset should clear epoch

    def test_control_pause_resume(self, demo_app):
        """Test pause and resume commands."""
        import time

        from fastapi.testclient import TestClient

        with TestClient(demo_app) as client:
            with client.websocket_connect("/ws/control") as websocket:
                self._skip_connection_message(websocket)
                self._validate_pause_resume_commands(websocket, time)

    def _validate_pause_resume_commands(self, websocket, time):
        self._command_and_response(websocket, time)
        pause_response = self._validate_pause_command(websocket, "pause")
        assert pause_response["state"]["is_paused"]
        resume_response = self._validate_pause_command(websocket, "resume")
        assert not resume_response["state"]["is_paused"]
        websocket.send_json({"command": "stop"})  # Stop
        websocket.receive_json()

    def _validate_pause_command(self, websocket, arg1):
        import time

        websocket.send_json({"command": arg1})  # Pause
        time.sleep(0.1)  # Allow message delivery
        result = self._receive_command_response(websocket)
        assert result["ok"]
        return result

    def test_control_stop_command(self, demo_app):
        # sourcery skip: extract-method
        """Test stop command functionality."""
        import time

        from fastapi.testclient import TestClient

        with TestClient(demo_app) as client:
            with client.websocket_connect("/ws/control") as websocket:
                self._skip_connection_message(websocket)
                websocket.send_json({"command": "start"})  # Start first
                time.sleep(0.1)  # Allow message delivery
                self._receive_command_response(websocket)
                websocket.send_json({"command": "stop"})  # Stop
                time.sleep(0.1)  # Allow message delivery
                stop_response = self._receive_command_response(websocket)
                assert stop_response["ok"]
                assert not stop_response["state"]["is_running"]

    def test_control_reset_command(self, demo_app):
        """Test reset command functionality."""
        import time

        from fastapi.testclient import TestClient

        with TestClient(demo_app) as client:
            with client.websocket_connect("/ws/control") as websocket:
                self._skip_connection_message(websocket)
                self._validate_reset_command(websocket, time)

    def _validate_reset_command(self, websocket, time):
        self._command_and_response(websocket, time)
        websocket.send_json({"command": "reset"})  # Reset
        reset_response = self._receive_command_response(websocket)
        assert reset_response["ok"]
        state = reset_response["state"]
        assert state["current_epoch"] == 0
        assert state["metrics_count"] == 0

    def _command_and_response(self, websocket, time):
        websocket.send_json({"command": "start"})
        self._receive_command_response(websocket)
        time.sleep(0.5)

    def test_control_unknown_command(self, demo_app):
        """Test handling of unknown command."""
        from fastapi.testclient import TestClient

        with TestClient(demo_app) as client:
            with client.websocket_connect("/ws/control") as websocket:
                self._skip_connection_message(websocket)
                websocket.send_json({"command": "invalid_command"})
                response = self._receive_command_response(websocket)
                assert not response["ok"]
                assert "error" in response


class TestWebSocketTrainingIntegration:
    """Integration tests for /ws/training endpoint."""

    @pytest.fixture
    def demo_app(self):
        """Create FastAPI app with demo mode for testing."""
        import os
        import sys
        from pathlib import Path

        # MUST set environment variable BEFORE importing main
        os.environ["CASCOR_DEMO_MODE"] = "1"

        src_path = Path(__file__).parent.parent.parent
        if str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))

        from main import app

        return app

    def _skip_connection_message(self, websocket):
        """Helper to consume the initial connection message."""
        conn_msg = websocket.receive_json()
        assert conn_msg.get("type") in ["connection_established", "initial_status"]
        return conn_msg

    def test_training_websocket_connection(self, demo_app):
        """Test basic WebSocket connection to /ws/training."""
        from fastapi.testclient import TestClient

        with TestClient(demo_app) as client:
            with client.websocket_connect("/ws/training") as websocket:
                # Consume initial status message
                self._skip_connection_message(websocket)

                # Send ping
                websocket.send_json({"type": "ping"})

                # Should receive pong or initial status
                response = websocket.receive_json()
                assert response.get("type") in ["pong", "initial_status"]

    def test_training_metrics_broadcast(self, demo_app):
        # sourcery skip: extract-method
        """Test receiving training metrics via WebSocket."""
        import time

        from fastapi.testclient import TestClient

        with TestClient(demo_app) as client:
            # Connect to training websocket to receive broadcasts
            with client.websocket_connect("/ws/training") as training_ws:
                # Skip initial messages (connection, initial_status)
                self._skip_connection_message(training_ws)

                # Wait for demo mode to generate metrics (it runs continuously)
                time.sleep(1.0)

                # Collect messages - demo mode should be broadcasting metrics
                messages_checked = 0
                received_metrics = False

                # Check multiple messages for metrics type
                for _ in range(20):
                    try:
                        message = training_ws.receive_json()
                        messages_checked += 1
                        msg_type = message.get("type", "")
                        # Accept "metrics", "training_metrics", or "state" as valid broadcasts
                        if msg_type in ["metrics", "training_metrics"]:
                            received_metrics = True
                            break
                        # Also accept state updates as proof broadcasting works
                        if msg_type == "state":
                            received_metrics = True
                            break
                    except Exception:
                        break

                assert received_metrics, f"Did not receive broadcast after checking {messages_checked} messages"


class TestEndToEndFlow:
    """End-to-end integration tests for complete workflows."""

    @pytest.fixture
    def demo_app(self):
        """Create FastAPI app with demo mode for testing."""
        import os
        import sys
        from pathlib import Path

        # MUST set environment variable BEFORE importing main
        os.environ["CASCOR_DEMO_MODE"] = "1"

        src_path = Path(__file__).parent.parent.parent
        if str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))

        from main import app

        return app

    def _skip_connection_message(self, websocket):
        """Helper to consume the initial connection message."""
        conn_msg = websocket.receive_json()
        assert conn_msg.get("type") in ["connection_established", "initial_status"]
        return conn_msg

    def test_complete_training_lifecycle(self, demo_app):
        """Test complete training lifecycle: start -> pause -> resume -> stop."""
        import time

        from fastapi.testclient import TestClient

        with TestClient(demo_app) as client:
            with client.websocket_connect("/ws/control") as websocket:
                self._skip_connection_message(websocket)
                self._test_client_training_commands(websocket, time)

    def _test_client_training_commands(self, websocket, time):
        # sourcery skip: extract-duplicate-method
        # Start training
        start_resp = self._send_command_with_retry(websocket, "start", timeout_messages=15)
        assert start_resp["ok"]
        assert start_resp["state"]["is_running"]
        time.sleep(0.5)  # Let it run

        # Pause
        pause_resp = self._send_command_with_retry(websocket, "pause", timeout_messages=15)
        assert pause_resp["ok"]
        assert pause_resp["state"]["is_paused"]
        time.sleep(0.3)

        # Resume
        resume_resp = self._send_command_with_retry(websocket, "resume", timeout_messages=15)
        assert resume_resp["ok"]
        assert not resume_resp["state"]["is_paused"]
        time.sleep(0.3)

        # Stop
        stop_resp = self._send_command_with_retry(websocket, "stop", timeout_messages=15)
        assert stop_resp["ok"]
        assert not stop_resp["state"]["is_running"]

    def _send_command_with_retry(self, websocket, command: str, timeout_messages: int = 10):
        """Send command and wait for response, skipping broadcasts."""
        websocket.send_json({"command": command})

        for _ in range(timeout_messages):
            msg = websocket.receive_json()
            # Skip training broadcasts (these don't have 'ok' field)
            msg_type = msg.get("type", "")
            if msg_type in ["metrics", "state", "event", "cascade_add", "status"]:
                continue  # Skip broadcast, check next message
            # Return command responses (should have 'ok' field)
            if "ok" in msg:
                return msg
            # Skip other broadcast types
            continue
        raise TimeoutError(f"Did not receive response for command {command!r} within {timeout_messages} messages")

    def test_api_endpoints_during_training(self, demo_app):
        """Test API endpoints return correct data during training."""
        import time

        from fastapi.testclient import TestClient

        with TestClient(demo_app) as client:
            # Demo mode is already running, just wait for data to accumulate
            time.sleep(1.0)  # Let demo mode generate some data

            # Check status endpoint
            status_data = self._validate_status_response(client, "/api/status")
            # Demo mode should be running or have valid state
            assert "is_training" in status_data or "current_epoch" in status_data

            # Check metrics/history endpoint - may be empty if just started
            metrics_resp = client.get("/api/metrics/history?limit=10")
            assert metrics_resp.status_code == 200
            metrics_result = metrics_resp.json()
            # API returns dict with 'history' key
            if isinstance(metrics_result, dict):
                metrics_data = metrics_result.get("history", [])
            else:
                metrics_data = metrics_result
            assert isinstance(metrics_data, list)
            # Note: history may be empty early in demo mode, just verify structure

            # Check topology endpoint
            topology_data = self._validate_status_response(client, "/api/topology")
            assert "nodes" in topology_data
            assert "connections" in topology_data

    def _validate_status_response(self, client, arg1):
        # Test /api/status
        status_resp = client.get(arg1)
        assert status_resp.status_code == 200
        return status_resp.json()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
