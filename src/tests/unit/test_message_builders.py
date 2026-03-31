#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     test_message_builders.py
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
#    Unit tests for WebSocket message builder functions.
#
#####################################################################################################################################################################################################
"""Unit tests for WebSocket message builder functions."""

import time

import pytest  # noqa: F401

from communication.websocket_manager import (
    create_control_ack_message,
    create_event_message,
    create_metrics_message,
    create_state_message,
    create_topology_message,
)


class TestCreateStateMessage:
    """Test create_state_message function."""

    def test_create_state_message_with_dict(self):
        """Test creating state message from dictionary."""
        state_data = {
            "status": "Started",
            "phase": "Output",
            "learning_rate": 0.01,
            "current_epoch": 42,
        }

        msg = create_state_message(state_data)

        assert msg["type"] == "state"
        assert "timestamp" in msg
        assert msg["data"] == state_data

    def test_create_state_message_with_training_state(self):
        """Test creating state message from TrainingState instance."""
        from backend.training_monitor import TrainingState

        state = TrainingState()
        state.update_state(status="Started", phase="Output", learning_rate=0.01)

        msg = create_state_message(state)

        assert msg["type"] == "state"
        assert msg["data"]["status"] == "Started"
        assert msg["data"]["phase"] == "Output"
        assert msg["data"]["learning_rate"] == 0.01

    def test_create_state_message_has_timestamp(self):
        """Test that state message includes timestamp."""
        state_data = {"status": "Stopped"}
        msg = create_state_message(state_data)

        assert "timestamp" in msg
        assert isinstance(msg["timestamp"], float)
        assert abs(msg["timestamp"] - time.time()) < 1.0


class TestCreateMetricsMessage:
    """Test create_metrics_message function."""

    def test_create_metrics_message(self):
        """Test creating metrics message."""
        metrics_data = {"epoch": 42, "metrics": {"loss": 0.23, "accuracy": 0.91}}

        msg = create_metrics_message(metrics_data)

        assert msg["type"] == "metrics"
        assert "timestamp" in msg
        assert msg["data"] == metrics_data

    def test_create_metrics_message_with_validation(self):
        """Test creating metrics message with validation data."""
        metrics_data = {
            "epoch": 10,
            "metrics": {"loss": 0.5, "accuracy": 0.75, "val_loss": 0.6, "val_accuracy": 0.70},
        }

        msg = create_metrics_message(metrics_data)

        assert msg["data"]["metrics"]["val_loss"] == 0.6
        assert msg["data"]["metrics"]["val_accuracy"] == 0.70

    def test_create_metrics_message_timestamp(self):
        """Test that metrics message has recent timestamp."""
        msg = create_metrics_message({"epoch": 1})

        assert abs(msg["timestamp"] - time.time()) < 1.0


class TestCreateTopologyMessage:
    """Test create_topology_message function."""

    def test_create_topology_message(self):
        """Test creating topology message."""
        topology_data = {
            "input_units": 2,
            "hidden_units": 3,
            "output_units": 1,
            "nodes": [],
            "connections": [],
        }

        msg = create_topology_message(topology_data)

        assert msg["type"] == "topology"
        assert "timestamp" in msg
        assert msg["data"] == topology_data

    def test_create_topology_message_with_connections(self):
        """Test creating topology message with node and connection data."""
        topology_data = {
            "input_units": 2,
            "hidden_units": 1,
            "output_units": 1,
            "nodes": [
                {"id": "input_0", "type": "input"},
                {"id": "hidden_0", "type": "hidden"},
                {"id": "output_0", "type": "output"},
            ],
            "connections": [{"from": "input_0", "to": "hidden_0", "weight": 0.5}],
        }

        msg = create_topology_message(topology_data)

        assert len(msg["data"]["nodes"]) == 3
        assert len(msg["data"]["connections"]) == 1


class TestCreateEventMessage:
    """Test create_event_message function."""

    def test_create_event_message(self):
        """Test creating event message."""
        event_type = "cascade_add"
        details = {"unit_index": 2, "total_hidden_units": 3, "epoch": 42}

        msg = create_event_message(event_type, details)

        assert msg["type"] == "event"
        assert "timestamp" in msg
        assert msg["data"]["event_type"] == event_type
        assert msg["data"]["details"] == details

    def test_create_event_message_different_types(self):
        """Test creating different event types."""
        events = [
            ("cascade_add", {"unit_index": 1}),
            ("status_change", {"status": "paused"}),
            ("phase_change", {"new_phase": "candidate"}),
        ]

        for event_type, details in events:
            msg = create_event_message(event_type, details)
            assert msg["data"]["event_type"] == event_type
            assert msg["data"]["details"] == details

    def test_create_event_message_empty_details(self):
        """Test creating event message with empty details."""
        msg = create_event_message("test_event", {})

        assert msg["data"]["event_type"] == "test_event"
        assert msg["data"]["details"] == {}


class TestCreateControlAckMessage:
    """Test create_control_ack_message function."""

    def test_create_control_ack_success(self):
        """Test creating successful control acknowledgment."""
        msg = create_control_ack_message("start", True, "Training started")

        assert msg["type"] == "control_ack"
        assert "timestamp" in msg
        assert msg["data"]["command"] == "start"
        assert msg["data"]["success"] is True
        assert msg["data"]["message"] == "Training started"

    def test_create_control_ack_failure(self):
        """Test creating failed control acknowledgment."""
        msg = create_control_ack_message("stop", False, "Failed to stop training")

        assert msg["data"]["command"] == "stop"
        assert msg["data"]["success"] is False
        assert msg["data"]["message"] == "Failed to stop training"

    def test_create_control_ack_no_message(self):
        """Test creating control ack without message."""
        msg = create_control_ack_message("pause", True)

        assert msg["data"]["command"] == "pause"
        assert msg["data"]["success"] is True
        assert msg["data"]["message"] == ""

    def test_create_control_ack_different_commands(self):
        """Test different control commands."""
        commands = ["start", "stop", "pause", "resume", "reset"]

        for cmd in commands:
            msg = create_control_ack_message(cmd, True, f"{cmd} successful")
            assert msg["data"]["command"] == cmd


class TestMessageSchema:
    """Test that all messages follow the standardized schema."""

    def test_all_messages_have_type(self):
        """Test all message builders include 'type' field."""
        from backend.training_monitor import TrainingState

        state = TrainingState()
        messages = [
            create_state_message(state),
            create_metrics_message({"epoch": 1}),
            create_topology_message({"input_units": 2}),
            create_event_message("test", {}),
            create_control_ack_message("test", True),
        ]

        for msg in messages:
            assert "type" in msg
            assert isinstance(msg["type"], str)

    def test_all_messages_have_timestamp(self):
        """Test all message builders include 'timestamp' field."""
        from backend.training_monitor import TrainingState

        state = TrainingState()
        messages = [
            create_state_message(state),
            create_metrics_message({"epoch": 1}),
            create_topology_message({"input_units": 2}),
            create_event_message("test", {}),
            create_control_ack_message("test", True),
        ]

        for msg in messages:
            assert "timestamp" in msg
            assert isinstance(msg["timestamp"], float)
            assert abs(msg["timestamp"] - time.time()) < 1.0

    def test_all_messages_have_data(self):
        """Test all message builders include 'data' field."""
        from backend.training_monitor import TrainingState

        state = TrainingState()
        messages = [
            create_state_message(state),
            create_metrics_message({"epoch": 1}),
            create_topology_message({"input_units": 2}),
            create_event_message("test", {}),
            create_control_ack_message("test", True),
        ]

        for msg in messages:
            assert "data" in msg
            assert isinstance(msg["data"], dict)

    def test_message_types_are_unique(self):
        """Test each builder creates distinct message types."""
        from backend.training_monitor import TrainingState

        state = TrainingState()
        messages = [
            create_state_message(state),
            create_metrics_message({"epoch": 1}),
            create_topology_message({"input_units": 2}),
            create_event_message("test", {}),
            create_control_ack_message("test", True),
        ]

        types = [msg["type"] for msg in messages]
        assert len(types) == len(set(types))
