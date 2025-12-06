#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     test_training_state.py
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
#    Unit tests for TrainingState class.
#
#####################################################################################################################################################################################################
import json
import threading
import time

import pytest  # noqa: F401 - needed for fixtures

from backend.training_monitor import TrainingState


class TestTrainingStateInitialization:
    """Test TrainingState initialization."""

    def test_default_initialization(self):
        """Test TrainingState initializes with default values."""
        state = TrainingState()
        data = state.get_state()

        assert data["status"] == "Stopped"
        assert data["phase"] == "Idle"
        assert data["learning_rate"] == 0.0
        assert data["max_hidden_units"] == 0
        assert data["current_epoch"] == 0
        assert data["current_step"] == 0
        assert data["network_name"] == ""
        assert data["dataset_name"] == ""
        assert data["threshold_function"] == ""
        assert data["optimizer_name"] == ""
        assert "timestamp" in data
        assert isinstance(data["timestamp"], float)


class TestTrainingStateSerialization:
    """Test TrainingState serialization."""

    def test_to_json_returns_valid_json(self):
        """Test to_json() returns valid JSON string."""
        state = TrainingState()
        json_str = state.to_json()

        # Should parse without error
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)

    def test_to_json_contains_all_fields(self):
        """Test to_json() contains all required fields."""
        state = TrainingState()
        state.update_state(
            status="Started", phase="Output", learning_rate=0.01, max_hidden_units=10, current_epoch=5, current_step=100
        )

        json_str = state.to_json()
        parsed = json.loads(json_str)

        assert parsed["status"] == "Started"
        assert parsed["phase"] == "Output"
        assert parsed["learning_rate"] == 0.01
        assert parsed["max_hidden_units"] == 10
        assert parsed["current_epoch"] == 5
        assert parsed["current_step"] == 100

    def test_get_state_returns_dict(self):
        """Test get_state() returns dictionary."""
        state = TrainingState()
        data = state.get_state()

        assert isinstance(data, dict)
        assert len(data) == 19  # 11 original + 8 candidate fields


class TestTrainingStateUpdate:
    """Test TrainingState update methods."""

    def test_update_state_single_field(self):
        """Test updating single field."""
        state = TrainingState()
        state.update_state(status="Started")

        data = state.get_state()
        assert data["status"] == "Started"

    def test_update_state_multiple_fields(self):
        """Test updating multiple fields."""
        state = TrainingState()
        state.update_state(status="Started", phase="Candidate", learning_rate=0.001, current_epoch=42)

        data = state.get_state()
        assert data["status"] == "Started"
        assert data["phase"] == "Candidate"
        assert data["learning_rate"] == 0.001
        assert data["current_epoch"] == 42

    def test_update_state_all_fields(self):
        """Test updating all fields."""
        state = TrainingState()
        state.update_state(
            status="Started",
            phase="Output",
            learning_rate=0.01,
            max_hidden_units=5,
            current_epoch=10,
            current_step=50,
            network_name="TestNet",
            dataset_name="TestDataset",
            threshold_function="sigmoid",
            optimizer_name="Adam",
        )

        data = state.get_state()
        assert data["status"] == "Started"
        assert data["phase"] == "Output"
        assert data["learning_rate"] == 0.01
        assert data["max_hidden_units"] == 5
        assert data["current_epoch"] == 10
        assert data["current_step"] == 50
        assert data["network_name"] == "TestNet"
        assert data["dataset_name"] == "TestDataset"
        assert data["threshold_function"] == "sigmoid"
        assert data["optimizer_name"] == "Adam"

    def test_update_state_updates_timestamp(self):
        """Test update_state() updates timestamp."""
        state = TrainingState()
        old_timestamp = state.get_state()["timestamp"]

        time.sleep(0.01)
        state.update_state(status="Started")

        new_timestamp = state.get_state()["timestamp"]
        assert new_timestamp > old_timestamp

    def test_update_state_preserves_other_fields(self):
        """Test partial update preserves other fields."""
        state = TrainingState()
        state.update_state(status="Started", phase="Output", learning_rate=0.01)

        state.update_state(current_epoch=5)

        data = state.get_state()
        assert data["status"] == "Started"
        assert data["phase"] == "Output"
        assert data["learning_rate"] == 0.01
        assert data["current_epoch"] == 5


class TestTrainingStateThreadSafety:
    """Test TrainingState thread safety."""

    def test_concurrent_reads(self):
        """Test concurrent reads are thread-safe."""
        state = TrainingState()
        state.update_state(status="Started", current_epoch=10)

        results = []

        def read_state():
            for _ in range(100):
                data = state.get_state()
                results.append(data["current_epoch"])

        threads = [threading.Thread(target=read_state) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All reads should succeed and return consistent value
        assert all(epoch == 10 for epoch in results)

    def test_concurrent_writes(self):
        """Test concurrent writes are thread-safe."""
        state = TrainingState()

        def update_state(epoch):
            for i in range(10):
                state.update_state(current_epoch=epoch * 10 + i)

        threads = [threading.Thread(target=update_state, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should complete without errors (value will be from last writer)
        data = state.get_state()
        assert isinstance(data["current_epoch"], int)
        assert data["current_epoch"] >= 0

    def test_concurrent_read_write(self):
        """Test concurrent reads and writes are thread-safe."""
        state = TrainingState()
        errors = []

        def reader():
            try:
                for _ in range(50):
                    state.get_state()
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        def writer():
            try:
                for i in range(50):
                    state.update_state(current_epoch=i)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        threads = []
        threads.extend([threading.Thread(target=reader) for _ in range(5)])
        threads.extend([threading.Thread(target=writer) for _ in range(5)])

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
