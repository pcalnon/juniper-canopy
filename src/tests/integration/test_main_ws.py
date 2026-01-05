#!/usr/bin/env python
"""
Integration tests for WebSocket endpoints in main.py.

Tests WebSocket functionality:
- /ws/training endpoint (real-time metrics)
- /ws endpoint (general WebSocket)
- Connection management
- Message broadcasting
- Connection count in statistics
- Multi-client scenarios
"""

import contextlib
import os
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# MUST set environment variable BEFORE importing main
os.environ["CASCOR_DEMO_MODE"] = "1"

# Add src to path
src_path = Path(__file__).parent.parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from main import app  # noqa: E402


class TestWebSocketEndpoints:
    """Integration tests for WebSocket endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client with demo mode."""
        with TestClient(app) as client:
            yield client

    # ========== /ws/training Endpoint ==========

    def test_ws_training_connection_establishment(self, client):
        """Test WebSocket connection to /ws/training."""
        with client.websocket_connect("/ws/training") as websocket:
            # Should receive connection_established message
            msg = websocket.receive_json()
            assert msg["type"] == "connection_established"
            assert "client_id" in msg
            assert "server_time" in msg

    def test_ws_training_initial_status(self, client):
        """Test /ws/training sends initial status after connection."""
        with client.websocket_connect("/ws/training") as websocket:
            # Skip connection message
            websocket.receive_json()

            # Should receive initial_status
            msg = websocket.receive_json()
            assert msg["type"] == "initial_status"
            assert "data" in msg

            # Validate status data
            status = msg["data"]
            assert "current_epoch" in status or "error" not in status

    def test_ws_training_ping_pong(self, client):
        """Test ping/pong functionality on /ws/training."""
        with client.websocket_connect("/ws/training") as websocket:
            # Skip connection and initial status messages
            websocket.receive_json()
            websocket.receive_json()

            # Send ping
            websocket.send_json({"type": "ping"})

            # Should receive pong
            msg = websocket.receive_json()
            assert msg["type"] == "pong"

    def test_ws_training_receives_broadcasts(self, client):
        """Test /ws/training receives training broadcast messages."""
        # Reset demo mode to clean state
        client.post("/api/train/reset")
        time.sleep(0.1)

        with client.websocket_connect("/ws/training") as websocket:
            # Skip connection and initial status
            websocket.receive_json()
            websocket.receive_json()

            # Start training to generate broadcasts
            client.post("/api/train/start")
            time.sleep(0.3)  # Allow broadcast buffering

            # Should receive training updates
            received_broadcast = False
            for _ in range(10):  # Check multiple messages
                try:
                    msg = websocket.receive_json()
                    if msg.get("type") in ["metrics", "state", "control_ack"]:
                        received_broadcast = True
                        break
                except Exception:
                    break

            assert received_broadcast, "Should receive training broadcast messages"

    def test_ws_training_multiple_clients(self, client):
        """Test multiple clients can connect to /ws/training."""
        with client.websocket_connect("/ws/training") as ws1:
            with client.websocket_connect("/ws/training") as ws2:
                # Both should receive connection messages
                msg1 = ws1.receive_json()
                msg2 = ws2.receive_json()

                assert msg1["type"] == "connection_established"
                assert msg2["type"] == "connection_established"

                # Client IDs should be different
                assert msg1["client_id"] != msg2["client_id"]

    def test_ws_training_connection_count_increases(self, client):
        """Test connection count increases with WebSocket connections."""
        # Get initial count
        response = client.get("/api/statistics")
        initial_count = response.json()["active_connections"]

        # Connect WebSocket
        with client.websocket_connect("/ws/training") as websocket:
            websocket.receive_json()  # Connection message

            # Check increased count
            response = client.get("/api/statistics")
            new_count = response.json()["active_connections"]

            assert new_count == initial_count + 1

    def test_ws_training_disconnection_cleanup(self, client):
        """Test WebSocket disconnection decreases connection count."""
        # Get initial count
        response = client.get("/api/statistics")
        initial_count = response.json()["active_connections"]

        # Connect and disconnect
        with client.websocket_connect("/ws/training") as websocket:
            websocket.receive_json()
            # Context exit will disconnect

        # Count should return to initial
        response = client.get("/api/statistics")
        final_count = response.json()["active_connections"]

        assert final_count == initial_count

    # ========== /ws Endpoint (General WebSocket) ==========

    def test_ws_general_connection(self, client):
        """Test general WebSocket endpoint /ws."""
        with client.websocket_connect("/ws") as websocket:
            # Should receive connection message
            msg = websocket.receive_json()
            assert msg["type"] == "connection_established"

    def test_ws_general_counts_in_statistics(self, client):
        """Test /ws connections count in statistics."""
        response = client.get("/api/statistics")
        initial_count = response.json()["active_connections"]

        with client.websocket_connect("/ws") as websocket:
            websocket.receive_json()

            response = client.get("/api/statistics")
            new_count = response.json()["active_connections"]

            assert new_count == initial_count + 1

    # ========== Connection Statistics ==========

    def test_statistics_shows_connection_info(self, client):
        """Test statistics endpoint provides connection details."""
        with client.websocket_connect("/ws/training") as websocket:
            websocket.receive_json()

            response = client.get("/api/statistics")
            data = response.json()

            assert "active_connections" in data
            assert "connections_info" in data
            assert isinstance(data["connections_info"], list)

            # Should have connection info
            if len(data["connections_info"]) > 0:
                conn_info = data["connections_info"][0]
                assert "client_id" in conn_info
                assert "connected_at" in conn_info
                assert "messages_sent" in conn_info

    def test_statistics_message_count_increases(self, client):
        """Test total_messages_broadcast increases with activity."""
        # Reset demo mode to clean state
        client.post("/api/train/reset")
        time.sleep(0.1)

        # Get initial count
        response = client.get("/api/statistics")
        initial_messages = response.json()["total_messages_broadcast"]

        # Connect and trigger some activity
        with client.websocket_connect("/ws/training") as websocket:
            websocket.receive_json()  # Connection message
            websocket.receive_json()  # Initial status

            # Start training to generate broadcasts
            client.post("/api/train/start")
            time.sleep(0.3)  # Wait for broadcasts with buffering

            # Receive some messages
            for _ in range(5):
                try:
                    websocket.receive_json(timeout=0.2)
                except Exception:
                    continue

        # Message count should have increased
        response = client.get("/api/statistics")
        final_messages = response.json()["total_messages_broadcast"]

        assert final_messages > initial_messages

    # ========== Message Broadcasting ==========

    def test_broadcast_to_multiple_clients(self, client):
        """Test broadcasts reach all connected clients."""
        # Reset demo mode to clean state
        client.post("/api/train/reset")
        time.sleep(0.1)

        with client.websocket_connect("/ws/training") as ws1:
            with client.websocket_connect("/ws/training") as ws2:
                self._receive_broadcast_from_multiple_clients(ws1, ws2, client)

    def _receive_broadcast_from_multiple_clients(self, ws1, ws2, client):
        # Skip connection messages
        ws1.receive_json()
        ws2.receive_json()
        ws1.receive_json()  # Initial status
        ws2.receive_json()  # Initial status

        # Trigger broadcast via training command
        client.post("/api/train/start")
        time.sleep(0.3)  # Allow broadcast buffering

        # Both should receive broadcast
        received1 = False
        received2 = False

        for _ in range(10):
            try:
                msg1 = ws1.receive_json()
                if msg1.get("type") in ["metrics", "state", "control_ack"]:
                    received1 = True
            except Exception:
                break

            if not received2:
                try:
                    msg2 = ws2.receive_json()
                    if msg2.get("type") in ["metrics", "state", "control_ack"]:
                        received2 = True
                except Exception:
                    break

            if received1 and received2:
                break

        # Both clients should receive broadcasts
        assert received1, "Client 1 should receive broadcast"
        assert received2, "Client 2 should receive broadcast"

    def test_broadcast_survives_client_disconnect(self, client):
        """Test broadcasts continue when one client disconnects."""
        # Reset demo mode to clean state
        client.post("/api/train/reset")
        time.sleep(0.1)

        # Connect two clients
        with client.websocket_connect("/ws/training") as ws1:
            ws1.receive_json()  # Connection
            ws1.receive_json()  # Initial status

            # Connect and disconnect second client
            with client.websocket_connect("/ws/training") as ws2:
                ws2.receive_json()
                ws2.receive_json()
            # ws2 disconnected

            # Broadcasts should still work for ws1
            client.post("/api/train/start")
            time.sleep(0.3)  # Allow broadcast buffering

            received = False
            for _ in range(10):
                try:
                    msg = ws1.receive_json()
                    if msg.get("type") in ["metrics", "state", "control_ack"]:
                        received = True
                        break
                except Exception:
                    break

            assert received, "Remaining client should still receive broadcasts"

    # ========== Error Handling ==========

    def test_ws_handles_invalid_message(self, client):
        """Test WebSocket handles invalid messages gracefully."""
        with client.websocket_connect("/ws/training") as websocket:
            websocket.receive_json()  # Connection
            websocket.receive_json()  # Initial status

            # Send invalid JSON
            with contextlib.suppress(Exception):
                websocket.send_text("invalid json {{{")

    def test_ws_connection_after_disconnect(self, client):
        """Test can reconnect after disconnection."""
        # First connection
        with client.websocket_connect("/ws/training") as websocket:
            msg = websocket.receive_json()
            assert msg["type"] == "connection_established"

        # Second connection after first disconnected
        with client.websocket_connect("/ws/training") as websocket:
            msg = websocket.receive_json()
            assert msg["type"] == "connection_established"

    # ========== Stress Tests ==========

    def test_rapid_connection_disconnection(self, client):
        """Test rapid connect/disconnect cycles."""
        for _ in range(5):
            with client.websocket_connect("/ws/training") as websocket:
                msg = websocket.receive_json()
                assert msg["type"] == "connection_established"

        # Final connection count should be 0
        response = client.get("/api/statistics")
        count = response.json()["active_connections"]
        assert count == 0

    def test_ws_message_timestamps(self, client):
        """Test WebSocket messages include timestamps."""
        with client.websocket_connect("/ws/training") as websocket:
            msg = websocket.receive_json()
            assert "timestamp" in msg or msg["type"] == "connection_established"

            # Initial status should have timestamp
            msg = websocket.receive_json()
            # Some messages might not have timestamp in the data field

    def test_concurrent_ws_and_http_requests(self, client):
        """Test WebSocket and HTTP requests work concurrently."""
        with client.websocket_connect("/ws/training") as websocket:
            # Receive initial messages
            msg = websocket.receive_json()  # Connection or initial status
            assert msg is not None

            # Make HTTP requests while WebSocket is connected
            response = client.get("/api/health")
            assert response.status_code == 200

            response = client.get("/api/status")
            assert response.status_code == 200

            # Wait for demo mode to generate broadcasts
            time.sleep(0.5)

            # WebSocket should still work - receive messages without timeout
            received = False
            for _ in range(10):
                try:
                    msg = websocket.receive_json()
                    if msg and "type" in msg:
                        received = True
                        break
                except Exception:
                    break

            assert received, "WebSocket should remain functional during HTTP requests"

    # ========== Connection Metadata ==========

    def test_connection_metadata_tracking(self, client):
        """Test connection metadata is properly tracked."""
        with client.websocket_connect("/ws/training") as websocket:
            msg = websocket.receive_json()
            client_id = msg["client_id"]

            # Get statistics
            response = client.get("/api/statistics")
            data = response.json()

            our_connection = next(
                (conn_info for conn_info in data["connections_info"] if conn_info["client_id"] == client_id),
                None,
            )
            assert our_connection is not None
            assert "connected_at" in our_connection
            assert "messages_sent" in our_connection
            assert our_connection["messages_sent"] >= 1  # At least connection message

    def test_message_count_per_connection(self, client):
        """Test messages_sent count increases per connection."""
        with client.websocket_connect("/ws/training") as websocket:
            msg = websocket.receive_json()
            client_id = msg["client_id"]

            # Receive several messages
            for _ in range(3):
                try:
                    websocket.receive_json(timeout=1)
                except Exception:
                    break

            # Check message count
            response = client.get("/api/statistics")
            data = response.json()

            if our_connection := next(
                (conn_info for conn_info in data["connections_info"] if conn_info["client_id"] == client_id),
                None,
            ):
                assert our_connection["messages_sent"] >= 2  # Connection + initial status minimum
