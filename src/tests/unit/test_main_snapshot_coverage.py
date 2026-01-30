#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     test_main_snapshot_coverage.py
# Author:        Paul Calnon (via Amp AI)
# Version:       1.0.0
# Date:          2025-01-29
# Last Modified: 2025-01-29
# License:       MIT License
# Copyright:     Copyright (c) 2024-2025 Paul Calnon
# Description:   Tests for main.py snapshot endpoints in real mode
#####################################################################
"""Tests for snapshot endpoints in real mode (lines 1146-1208, 1266-1270, 1338-1399)."""
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure demo mode for initial import
os.environ["CASCOR_DEMO_MODE"] = "1"

# Add src to path
src_dir = Path(__file__).parents[2]
sys.path.insert(0, str(src_dir))


class FakeIntegration:
    """Fake CasCor integration for testing real mode snapshot operations."""

    def __init__(self):
        self.save_snapshot_called = False
        self.load_snapshot_called = False
        self.saved_path = None
        self.saved_description = None
        self.loaded_path = None

    def save_snapshot(self, path: str, description: str = None):
        """Simulate saving a snapshot."""
        self.save_snapshot_called = True
        self.saved_path = path
        self.saved_description = description
        Path(path).touch()

    def load_snapshot(self, path: str):
        """Simulate loading a snapshot."""
        self.load_snapshot_called = True
        self.loaded_path = path

    def shutdown(self):
        """Simulate shutdown."""
        pass


class FakeIntegrationNoMethods:
    """Fake integration without save_snapshot/load_snapshot methods."""

    def shutdown(self):
        pass


@pytest.fixture
def snapshot_dir(tmp_path):
    """Create isolated snapshot directory."""
    snapshot_path = tmp_path / "snapshots"
    snapshot_path.mkdir(parents=True, exist_ok=True)
    return snapshot_path


@pytest.fixture
def h5py_available():
    """Check if h5py is available."""
    try:
        import h5py

        return True
    except ImportError:
        return False


@pytest.fixture
def create_test_hdf5(snapshot_dir, h5py_available):
    """Factory fixture to create test HDF5 files."""

    def _create(name="test_snapshot.h5", with_training_state=True):
        if not h5py_available:
            pytest.skip("h5py not available")

        import h5py

        snapshot_path = snapshot_dir / name
        with h5py.File(snapshot_path, "w") as f:
            f.attrs["created"] = "2025-01-01T00:00:00"
            f.attrs["description"] = "Test snapshot"
            f.attrs["mode"] = "manual"

            if with_training_state:
                state_group = f.create_group("training_state")
                state_group.attrs["current_epoch"] = 50
                state_group.attrs["learning_rate"] = 0.01
                state_group.attrs["status"] = "Stopped"

        return snapshot_path

    return _create


@pytest.fixture(scope="module")
def app_client():
    """Create test client with demo mode (initial setup)."""
    from fastapi.testclient import TestClient

    from main import app

    with TestClient(app) as client:
        yield client


class TestCreateSnapshotRealMode:
    """Tests for create_snapshot in real mode (lines 1146-1208)."""

    @pytest.mark.unit
    def test_create_snapshot_with_cascor_integration(self, app_client, snapshot_dir):
        """Test creating snapshot when cascor_integration.save_snapshot is available."""
        import main

        fake_integration = FakeIntegration()

        with (
            patch.object(main, "demo_mode_active", False),
            patch.object(main, "cascor_integration", fake_integration),
            patch.object(main, "_snapshots_dir", str(snapshot_dir)),
        ):
            response = app_client.post("/api/v1/snapshots?name=test_snapshot&description=Test%20description")

            assert response.status_code == 201
            data = response.json()
            assert data["id"] == "test_snapshot"
            assert data["name"] == "test_snapshot.h5"
            assert "timestamp" in data
            assert "size_bytes" in data
            assert data["description"] == "Test description"
            assert data["message"] == "Snapshot created successfully"

            assert fake_integration.save_snapshot_called
            assert "test_snapshot.h5" in fake_integration.saved_path
            assert fake_integration.saved_description == "Test description"

    @pytest.mark.unit
    def test_create_snapshot_auto_generated_name(self, app_client, snapshot_dir):
        """Test creating snapshot without providing name (auto-generated)."""
        import main

        fake_integration = FakeIntegration()

        with (
            patch.object(main, "demo_mode_active", False),
            patch.object(main, "cascor_integration", fake_integration),
            patch.object(main, "_snapshots_dir", str(snapshot_dir)),
        ):
            response = app_client.post("/api/v1/snapshots")

            assert response.status_code == 201
            data = response.json()
            assert data["id"].startswith("snapshot_")
            assert data["name"].endswith(".h5")
            assert fake_integration.save_snapshot_called

    @pytest.mark.unit
    def test_create_snapshot_h5py_fallback(self, app_client, snapshot_dir, h5py_available):
        """Test creating snapshot with h5py when integration lacks save_snapshot method."""
        if not h5py_available:
            pytest.skip("h5py not available")

        import main

        with (
            patch.object(main, "demo_mode_active", False),
            patch.object(main, "cascor_integration", FakeIntegrationNoMethods()),
            patch.object(main, "_snapshots_dir", str(snapshot_dir)),
        ):
            response = app_client.post("/api/v1/snapshots?name=h5py_test&description=H5py%20fallback%20test")

            assert response.status_code == 201
            data = response.json()
            assert data["id"] == "h5py_test"
            assert data["name"] == "h5py_test.h5"

            snapshot_path = snapshot_dir / "h5py_test.h5"
            assert snapshot_path.exists()

            import h5py

            with h5py.File(snapshot_path, "r") as f:
                assert "created" in f.attrs
                assert f.attrs["description"] == "H5py fallback test"
                assert f.attrs["mode"] == "manual"

    @pytest.mark.unit
    def test_create_snapshot_h5py_not_available(self, app_client, snapshot_dir):
        """Test creating snapshot when h5py is not available (ImportError path)."""
        import builtins

        import main

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "h5py":
                raise ImportError("No module named 'h5py'")
            return original_import(name, *args, **kwargs)

        with (
            patch.object(main, "demo_mode_active", False),
            patch.object(main, "cascor_integration", FakeIntegrationNoMethods()),
            patch.object(main, "_snapshots_dir", str(snapshot_dir)),
            patch.object(builtins, "__import__", side_effect=mock_import),
        ):
            response = app_client.post("/api/v1/snapshots?name=no_h5py_test")

            assert response.status_code == 500
            assert "h5py not available" in response.json()["detail"]

    @pytest.mark.unit
    def test_create_snapshot_directory_creation(self, app_client, tmp_path):
        """Test that snapshot directory is created if it doesn't exist."""
        import main

        non_existent_dir = tmp_path / "new_snapshots_dir"
        assert not non_existent_dir.exists()

        fake_integration = FakeIntegration()

        with (
            patch.object(main, "demo_mode_active", False),
            patch.object(main, "cascor_integration", fake_integration),
            patch.object(main, "_snapshots_dir", str(non_existent_dir)),
        ):
            response = app_client.post("/api/v1/snapshots?name=dir_test")

            assert response.status_code == 201
            assert non_existent_dir.exists()

    @pytest.mark.unit
    def test_create_snapshot_error_handling(self, app_client, snapshot_dir):
        """Test error handling when snapshot creation fails."""
        import main

        class FailingIntegration:
            def save_snapshot(self, path, description=None):
                raise RuntimeError("Simulated save failure")

            def shutdown(self):
                pass

        with (
            patch.object(main, "demo_mode_active", False),
            patch.object(main, "cascor_integration", FailingIntegration()),
            patch.object(main, "_snapshots_dir", str(snapshot_dir)),
        ):
            response = app_client.post("/api/v1/snapshots?name=fail_test")

            assert response.status_code == 500
            assert "Failed to create snapshot" in response.json()["detail"]


class TestRestoreSnapshotRealMode:
    """Tests for restore_snapshot in real mode (lines 1266-1270, 1338-1399)."""

    @pytest.mark.unit
    def test_restore_snapshot_with_cascor_integration(self, app_client, snapshot_dir, create_test_hdf5):
        """Test restoring snapshot when cascor_integration.load_snapshot is available."""
        snapshot_path = create_test_hdf5("restore_test.h5")

        import main

        fake_integration = FakeIntegration()

        with (
            patch.object(main, "demo_mode_active", False),
            patch.object(main, "cascor_integration", fake_integration),
            patch.object(main, "_snapshots_dir", str(snapshot_dir)),
            patch.object(main, "demo_mode_instance", None),
        ):
            response = app_client.post("/api/v1/snapshots/restore_test/restore")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert data["snapshot_id"] == "restore_test"
            assert data["mode"] == "real"
            assert "restored_at" in data

            assert fake_integration.load_snapshot_called
            assert "restore_test" in fake_integration.loaded_path

    @pytest.mark.unit
    def test_restore_snapshot_h5_extension(self, app_client, snapshot_dir, create_test_hdf5):
        """Test restoring snapshot with .h5 extension found on filesystem."""
        snapshot_path = create_test_hdf5("test_h5_ext.h5")

        import main

        fake_integration = FakeIntegration()

        with (
            patch.object(main, "demo_mode_active", False),
            patch.object(main, "cascor_integration", fake_integration),
            patch.object(main, "_snapshots_dir", str(snapshot_dir)),
            patch.object(main, "demo_mode_instance", None),
        ):
            response = app_client.post("/api/v1/snapshots/test_h5_ext/restore")

            assert response.status_code == 200
            assert fake_integration.load_snapshot_called

    @pytest.mark.unit
    def test_restore_snapshot_hdf5_extension(self, app_client, snapshot_dir, h5py_available):
        """Test restoring snapshot with .hdf5 extension fallback."""
        if not h5py_available:
            pytest.skip("h5py not available")

        import h5py

        import main

        snapshot_path = snapshot_dir / "test_hdf5_ext.hdf5"
        with h5py.File(snapshot_path, "w") as f:
            f.attrs["created"] = "2025-01-01T00:00:00"

        fake_integration = FakeIntegration()

        with (
            patch.object(main, "demo_mode_active", False),
            patch.object(main, "cascor_integration", fake_integration),
            patch.object(main, "_snapshots_dir", str(snapshot_dir)),
            patch.object(main, "demo_mode_instance", None),
        ):
            response = app_client.post("/api/v1/snapshots/test_hdf5_ext/restore")

            assert response.status_code == 200
            assert fake_integration.load_snapshot_called

    @pytest.mark.unit
    def test_restore_snapshot_h5py_fallback(self, app_client, snapshot_dir, h5py_available):
        """Test restoring snapshot with h5py when integration lacks load_snapshot method."""
        if not h5py_available:
            pytest.skip("h5py not available")

        import h5py

        import main

        snapshot_path = snapshot_dir / "h5py_restore_test.h5"
        with h5py.File(snapshot_path, "w") as f:
            f.attrs["created"] = "2025-01-01T00:00:00"
            state_group = f.create_group("training_state")
            state_group.attrs["current_epoch"] = 75
            state_group.attrs["learning_rate"] = 0.005

        with (
            patch.object(main, "demo_mode_active", False),
            patch.object(main, "cascor_integration", FakeIntegrationNoMethods()),
            patch.object(main, "_snapshots_dir", str(snapshot_dir)),
            patch.object(main, "demo_mode_instance", None),
        ):
            response = app_client.post("/api/v1/snapshots/h5py_restore_test/restore")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert data["mode"] == "real"

    @pytest.mark.unit
    def test_restore_snapshot_h5py_no_training_state(self, app_client, snapshot_dir, h5py_available):
        """Test restoring snapshot when HDF5 file has no training_state group."""
        if not h5py_available:
            pytest.skip("h5py not available")

        import h5py

        import main

        snapshot_path = snapshot_dir / "no_state_test.h5"
        with h5py.File(snapshot_path, "w") as f:
            f.attrs["created"] = "2025-01-01T00:00:00"
            f.attrs["description"] = "No training state"

        with (
            patch.object(main, "demo_mode_active", False),
            patch.object(main, "cascor_integration", FakeIntegrationNoMethods()),
            patch.object(main, "_snapshots_dir", str(snapshot_dir)),
            patch.object(main, "demo_mode_instance", None),
        ):
            response = app_client.post("/api/v1/snapshots/no_state_test/restore")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"

    @pytest.mark.unit
    def test_restore_snapshot_h5py_not_available(self, app_client, snapshot_dir):
        """Test restoring snapshot when h5py is not available (ImportError path)."""
        import builtins

        import main

        dummy_snapshot = snapshot_dir / "no_h5py_restore.h5"
        dummy_snapshot.touch()

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "h5py":
                raise ImportError("No module named 'h5py'")
            return original_import(name, *args, **kwargs)

        with (
            patch.object(main, "demo_mode_active", False),
            patch.object(main, "cascor_integration", FakeIntegrationNoMethods()),
            patch.object(main, "_snapshots_dir", str(snapshot_dir)),
            patch.object(main, "demo_mode_instance", None),
            patch.object(builtins, "__import__", side_effect=mock_import),
        ):
            response = app_client.post("/api/v1/snapshots/no_h5py_restore/restore")

            assert response.status_code == 500
            assert "h5py not available" in response.json()["detail"]

    @pytest.mark.unit
    def test_restore_snapshot_not_found(self, app_client, snapshot_dir):
        """Test restoring non-existent snapshot returns 404."""
        import main

        with (
            patch.object(main, "demo_mode_active", False),
            patch.object(main, "cascor_integration", FakeIntegration()),
            patch.object(main, "_snapshots_dir", str(snapshot_dir)),
            patch.object(main, "demo_mode_instance", None),
        ):
            response = app_client.post("/api/v1/snapshots/nonexistent_snapshot/restore")

            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()

    @pytest.mark.unit
    def test_restore_snapshot_error_handling(self, app_client, snapshot_dir, h5py_available):
        """Test error handling when snapshot restoration fails."""
        if not h5py_available:
            pytest.skip("h5py not available")

        import h5py

        import main

        class FailingLoadIntegration:
            def load_snapshot(self, path):
                raise RuntimeError("Simulated load failure")

            def shutdown(self):
                pass

        snapshot_path = snapshot_dir / "fail_restore.h5"
        with h5py.File(snapshot_path, "w") as f:
            f.attrs["created"] = "2025-01-01T00:00:00"

        with (
            patch.object(main, "demo_mode_active", False),
            patch.object(main, "cascor_integration", FailingLoadIntegration()),
            patch.object(main, "_snapshots_dir", str(snapshot_dir)),
            patch.object(main, "demo_mode_instance", None),
        ):
            response = app_client.post("/api/v1/snapshots/fail_restore/restore")

            assert response.status_code == 500
            assert "Failed to restore" in response.json()["detail"]


class TestSnapshotActivityLogging:
    """Tests for _log_snapshot_activity function."""

    @pytest.mark.unit
    def test_log_snapshot_activity_create(self, app_client, snapshot_dir):
        """Test that snapshot creation logs activity."""
        import main

        fake_integration = FakeIntegration()

        with (
            patch.object(main, "demo_mode_active", False),
            patch.object(main, "cascor_integration", fake_integration),
            patch.object(main, "_snapshots_dir", str(snapshot_dir)),
        ):
            response = app_client.post("/api/v1/snapshots?name=log_test")

            assert response.status_code == 201

            history_file = snapshot_dir / "snapshot_history.jsonl"
            assert history_file.exists()

            with open(history_file) as f:
                lines = f.readlines()
                assert len(lines) >= 1
                entry = json.loads(lines[-1])
                assert entry["action"] == "create"
                assert entry["snapshot_id"] == "log_test"
                assert "mode" in entry["details"]
                assert entry["message"] == "Snapshot created successfully"

    @pytest.mark.unit
    def test_log_snapshot_activity_restore(self, app_client, snapshot_dir, create_test_hdf5):
        """Test that snapshot restoration logs activity."""
        snapshot_path = create_test_hdf5("restore_log_test.h5")

        import main

        fake_integration = FakeIntegration()

        with (
            patch.object(main, "demo_mode_active", False),
            patch.object(main, "cascor_integration", fake_integration),
            patch.object(main, "_snapshots_dir", str(snapshot_dir)),
            patch.object(main, "demo_mode_instance", None),
        ):
            response = app_client.post("/api/v1/snapshots/restore_log_test/restore")

            assert response.status_code == 200

            history_file = snapshot_dir / "snapshot_history.jsonl"
            assert history_file.exists()

            with open(history_file) as f:
                lines = f.readlines()
                restore_entries = [json.loads(line) for line in lines if "restore" in line]
                assert len(restore_entries) >= 1
                entry = restore_entries[-1]
                assert entry["action"] == "restore"
                assert entry["snapshot_id"] == "restore_log_test"

    @pytest.mark.unit
    def test_log_snapshot_activity_directory_creation(self, tmp_path):
        """Test that _log_snapshot_activity creates directory if needed."""
        import main

        new_dir = tmp_path / "new_log_dir"
        assert not new_dir.exists()

        original_snapshots_dir = main._snapshots_dir

        try:
            main._snapshots_dir = str(new_dir)

            main._log_snapshot_activity(
                action="test",
                snapshot_id="test_id",
                details={"test": True},
                message="Test message",
            )

            assert new_dir.exists()
            history_file = new_dir / "snapshot_history.jsonl"
            assert history_file.exists()
        finally:
            main._snapshots_dir = original_snapshots_dir

    @pytest.mark.unit
    def test_log_snapshot_activity_handles_errors(self, tmp_path):
        """Test that _log_snapshot_activity handles write errors gracefully."""
        import main

        invalid_path = tmp_path / "invalid_file"
        invalid_path.touch()

        original_snapshots_dir = main._snapshots_dir

        try:
            main._snapshots_dir = str(invalid_path / "cannot_create")

            main._log_snapshot_activity(
                action="test",
                snapshot_id="test_id",
                details={},
                message="Test",
            )
        finally:
            main._snapshots_dir = original_snapshots_dir


class TestCreateSnapshotWithTrainingState:
    """Tests for snapshot creation with training state serialization."""

    @pytest.mark.unit
    def test_create_snapshot_stores_training_state(self, app_client, snapshot_dir, h5py_available):
        """Test that h5py fallback stores training state attributes."""
        if not h5py_available:
            pytest.skip("h5py not available")

        import main

        class MockTrainingState:
            def __init__(self):
                self.current_epoch = 100
                self.learning_rate = 0.01
                self.status = "Training"
                self.hidden_units = 5
                self._private = "should_be_ignored"
                self.complex_data = {"nested": True}

        original_training_state = main.training_state

        try:
            main.training_state = MockTrainingState()

            with (
                patch.object(main, "demo_mode_active", False),
                patch.object(main, "cascor_integration", FakeIntegrationNoMethods()),
                patch.object(main, "_snapshots_dir", str(snapshot_dir)),
            ):
                response = app_client.post("/api/v1/snapshots?name=state_test")

                assert response.status_code == 201

                import h5py

                snapshot_path = snapshot_dir / "state_test.h5"
                with h5py.File(snapshot_path, "r") as f:
                    assert "training_state" in f
                    state_group = f["training_state"]
                    assert state_group.attrs["current_epoch"] == 100
                    assert state_group.attrs["learning_rate"] == 0.01
                    assert state_group.attrs["status"] == "Training"
                    assert state_group.attrs["hidden_units"] == 5
                    assert "_private" not in state_group.attrs
                    assert "complex_data" not in state_group.attrs
        finally:
            main.training_state = original_training_state
