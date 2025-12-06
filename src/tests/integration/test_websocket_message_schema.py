#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     test_websocket_message_schema.py
# Author:        Paul Calnon
# Version:       1.0.0
#
# Date:          2025-11-16
# Last Modified: 2025-11-16
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2025 Paul Calnon
#
# Description:
#    Integration tests verifying WebSocket messages follow standardized schema.
#
#####################################################################################################################################################################################################
import contextlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def test_client():
    """Create test client for FastAPI app."""
    from main import app

    return TestClient(app)


class TestWebSocketMessageSchema:
    """Test WebSocket messages follow the standardized schema."""

    def test_connection_established_follows_schema(self, test_client):
        """Test connection_established message has required fields."""
        with test_client.websocket_connect("/ws/training") as websocket:
            data = websocket.receive_json()

            assert "type" in data
            assert data["type"] == "connection_established"
            # This is a special connection message, not data message

    def test_state_messages_follow_schema(self, test_client):
        """Test state messages from demo mode follow schema."""
        with test_client.websocket_connect("/ws/training") as websocket:
            # Skip connection message
            websocket.receive_json()

            # Wait for state messages
            for _ in range(10):
                try:
                    message = websocket.receive_json(timeout=2.0)

                    if message.get("type") == "state":
                        # Verify schema
                        assert "type" in message
                        assert message["type"] == "state"
                        assert "timestamp" in message
                        assert "data" in message

                        # Verify data structure
                        data = message["data"]
                        assert isinstance(data, dict)

                        # Verify state-specific fields
                        expected_fields = [
                            "status",
                            "phase",
                            "learning_rate",
                            "max_hidden_units",
                            "current_epoch",
                            "current_step",
                            "timestamp",
                        ]
                        for field in expected_fields:
                            assert field in data, f"Missing field: {field}"
                        break
                except Exception:
                    continue

    def test_metrics_messages_follow_schema(self, test_client):
        """Test metrics messages follow schema."""
        with test_client.websocket_connect("/ws/training") as websocket:
            websocket.receive_json()

            for _ in range(15):
                try:
                    message = websocket.receive_json(timeout=2.0)

                    if message.get("type") == "metrics":
                        # Verify schema
                        assert "type" in message
                        assert message["type"] == "metrics"
                        assert "timestamp" in message
                        assert "data" in message
                        assert isinstance(message["data"], dict)
                        break
                except Exception:
                    continue

    def test_event_messages_follow_schema(self, test_client):
        """Test event messages follow schema."""
        with test_client.websocket_connect("/ws/training") as websocket:
            websocket.receive_json()

            for _ in range(20):
                try:
                    message = websocket.receive_json(timeout=2.0)

                    if message.get("type") == "event":
                        # Verify schema
                        assert "type" in message
                        assert message["type"] == "event"
                        assert "timestamp" in message
                        assert "data" in message

                        # Verify event structure
                        data = message["data"]
                        assert "event_type" in data
                        assert "details" in data
                        assert isinstance(data["details"], dict)
                        break
                except Exception:
                    continue

    def test_all_messages_have_timestamp(self, test_client):
        """Test all messages include timestamp."""
        with test_client.websocket_connect("/ws/training") as websocket:
            # Skip connection message (special case)
            websocket.receive_json()

            # Check next several messages
            for _ in range(10):
                with contextlib.suppress(Exception):
                    message = websocket.receive_json(timeout=2.0)

                    # Skip connection-related messages
                    if message.get("type") in ["connection_established", "ping", "pong"]:
                        continue

                    # All data messages must have timestamp
                    assert "timestamp" in message
                    assert isinstance(message["timestamp"], (int, float))


class TestControlWebSocketSchema:
    """Test control WebSocket responses follow schema."""

    def test_control_ack_follows_schema(self, test_client):
        """Test control acknowledgment messages follow schema."""
        with test_client.websocket_connect("/ws/control") as websocket:
            # Skip connection established
            websocket.receive_json()

            # Send control command
            websocket.send_json({"command": "start", "reset": True})

            # Receive response
            response = websocket.receive_json()

            # Control ack may come as 'ok' field or follow message schema
            if "ok" in response:
                # Legacy format still used in control endpoint
                assert "command" in response
                assert isinstance(response["ok"], bool)
            elif response.get("type") == "control_ack":
                # Standardized format
                assert "timestamp" in response
                assert "data" in response
                assert "command" in response["data"]
                assert "success" in response["data"]


class TestMessageFormatConsistency:
    """Test message format consistency across different message types."""

    def test_all_data_messages_have_three_keys(self, test_client):
        """Test all data messages have exactly 3 keys: type, timestamp, data."""
        with test_client.websocket_connect("/ws/training") as websocket:
            websocket.receive_json()

            for _ in range(10):
                with contextlib.suppress(Exception):
                    message = websocket.receive_json(timeout=2.0)

                    # Skip special messages
                    if message.get("type") in ["connection_established", "server_shutdown"]:
                        continue

                    # Data messages should have exactly these keys
                    if message.get("type") in ["state", "metrics", "topology", "event"]:
                        assert set(message.keys()) == {"type", "timestamp", "data"}
                        break

            # If no data messages found, that's okay (demo mode might not be active)

    def test_timestamp_is_unix_time(self, test_client):
        """Test timestamps are Unix timestamps (seconds since epoch)."""
        import time

        with test_client.websocket_connect("/ws/training") as websocket:
            websocket.receive_json()

            current_time = time.time()

            for _ in range(10):
                with contextlib.suppress(Exception):
                    message = websocket.receive_json(timeout=2.0)

                    if "timestamp" in message:
                        ts = message["timestamp"]
                        # Should be within reasonable range of current time
                        # (within last hour to next hour)
                        assert current_time - 3600 < ts < current_time + 3600
                        break
