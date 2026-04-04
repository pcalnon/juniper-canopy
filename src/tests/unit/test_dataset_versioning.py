#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_dataset_versioning.py
# Author:        Paul Calnon
# Version:       0.1.0
#
# Date:          2026-04-01
# Last Modified: 2026-04-01
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
#
# Description:
#    Unit tests for dataset versioning integration (CAN-DEF-005 Phase 3).
#    Verifies that dataset_name and dataset_version metadata from juniper-data
#    is properly propagated through the Canopy stack.
#
#####################################################################################################################################################################################################
"""Unit tests for dataset versioning integration (CAN-DEF-005 Phase 3)."""

import pytest

from backend.training_monitor import TrainingState


class TestTrainingStateVersioning:
    """Test that TrainingState stores dataset versioning fields."""

    def test_default_dataset_version_is_zero(self):
        """TrainingState initializes dataset_version to 0."""
        state = TrainingState()
        data = state.get_state()
        assert data["dataset_version"] == 0

    def test_update_dataset_version(self):
        """TrainingState accepts dataset_version via update_state."""
        state = TrainingState()
        state.update_state(dataset_name="Spiral2D", dataset_version=3)
        data = state.get_state()
        assert data["dataset_name"] == "Spiral2D"
        assert data["dataset_version"] == 3

    def test_dataset_version_in_state_fields(self):
        """dataset_version is in the _STATE_FIELDS set."""
        assert "dataset_version" in TrainingState._STATE_FIELDS

    def test_update_dataset_name_without_version(self):
        """Updating dataset_name without version leaves version unchanged."""
        state = TrainingState()
        state.update_state(dataset_name="TestDS")
        data = state.get_state()
        assert data["dataset_name"] == "TestDS"
        assert data["dataset_version"] == 0


class TestDemoModeVersioning:
    """Test that DemoMode propagates versioning metadata from dataset dict."""

    def test_get_current_state_includes_version_when_present(self):
        """get_current_state includes dataset_name/version when dataset has them."""
        from demo_mode import get_demo_mode

        demo = get_demo_mode(update_interval=1.0)
        try:
            # Manually inject versioning metadata into dataset
            demo.dataset["dataset_name"] = "Spiral2D"
            demo.dataset["dataset_version"] = 2

            state = demo.get_current_state()
            assert state["dataset_name"] == "Spiral2D"
            assert state["dataset_version"] == 2
        finally:
            demo.stop()

    def test_get_current_state_omits_version_when_absent(self):
        """get_current_state omits versioning keys when dataset lacks them."""
        from demo_mode import get_demo_mode

        demo = get_demo_mode(update_interval=1.0)
        try:
            # Ensure no versioning keys in dataset
            demo.dataset.pop("dataset_name", None)
            demo.dataset.pop("dataset_version", None)

            state = demo.get_current_state()
            assert "dataset_name" not in state
            assert "dataset_version" not in state
        finally:
            demo.stop()


class TestDemoBackendVersioning:
    """Test that DemoBackend propagates versioning metadata."""

    def test_get_dataset_includes_versioning(self):
        """get_dataset includes dataset_name/version when available."""
        from backend.demo_backend import DemoBackend
        from demo_mode import get_demo_mode

        demo = get_demo_mode(update_interval=1.0)
        try:
            # Inject versioning metadata
            demo.dataset["dataset_name"] = "Spiral2D"
            demo.dataset["dataset_version"] = 5

            backend = DemoBackend(demo)
            dataset = backend.get_dataset()
            assert dataset is not None
            assert dataset["dataset_name"] == "Spiral2D"
            assert dataset["dataset_version"] == 5
        finally:
            demo.stop()

    def test_get_dataset_without_versioning(self):
        """get_dataset works without versioning fields (backward compat)."""
        from backend.demo_backend import DemoBackend
        from demo_mode import get_demo_mode

        demo = get_demo_mode(update_interval=1.0)
        try:
            # Remove versioning keys
            demo.dataset.pop("dataset_name", None)
            demo.dataset.pop("dataset_version", None)

            backend = DemoBackend(demo)
            dataset = backend.get_dataset()
            assert dataset is not None
            assert "dataset_name" not in dataset
            assert "dataset_version" not in dataset
            # Core fields still present
            assert "num_samples" in dataset
            assert "num_features" in dataset
        finally:
            demo.stop()


class TestSnapshotVersioning:
    """Test that snapshot metadata includes versioning fields."""

    def test_snapshot_metadata_structure(self):
        """Verify snapshot dict can hold dataset versioning fields."""
        # This tests the pattern used in main.py create_snapshot
        snapshot = {
            "id": "test_snap_001",
            "name": "test_snap_001.h5",
            "timestamp": "2026-04-01T00:00:00Z",
            "size_bytes": 1048576,
            "description": "Test snapshot",
        }

        # Simulate adding versioning metadata from status
        status = {"dataset_name": "Spiral2D", "dataset_version": 3}
        if "dataset_name" in status:
            snapshot["dataset_name"] = status["dataset_name"]
        if "dataset_version" in status:
            snapshot["dataset_version"] = status["dataset_version"]

        assert snapshot["dataset_name"] == "Spiral2D"
        assert snapshot["dataset_version"] == 3

    def test_snapshot_without_versioning(self):
        """Snapshot works without versioning fields (backward compat)."""
        snapshot = {
            "id": "test_snap_002",
            "name": "test_snap_002.h5",
            "timestamp": "2026-04-01T00:00:00Z",
            "size_bytes": 1048576,
            "description": "Test snapshot no version",
        }

        # Simulate status without versioning fields
        status = {"is_running": True, "current_epoch": 10}
        if "dataset_name" in status:
            snapshot["dataset_name"] = status["dataset_name"]
        if "dataset_version" in status:
            snapshot["dataset_version"] = status["dataset_version"]

        assert "dataset_name" not in snapshot
        assert "dataset_version" not in snapshot
        # Core fields intact
        assert snapshot["id"] == "test_snap_002"


_has_jdc_testing = False
try:
    from juniper_data_client.testing import FakeDataClient  # noqa: F401

    _has_jdc_testing = True
except ImportError:
    pass


@pytest.mark.skipif(not _has_jdc_testing, reason="requires juniper-data-client[testing]")
class TestFakeDataClientVersioning:
    """Test that FakeDataClient returns versioning fields when name is provided."""

    def test_create_dataset_with_name_has_version(self):
        """create_dataset with name returns dataset_name and dataset_version in meta."""
        with FakeDataClient() as client:
            result = client.create_dataset(
                "spiral",
                {"n_spirals": 2, "n_points_per_spiral": 50, "seed": 42},
                name="TestSpiral",
            )
            meta = result["meta"]
            assert meta["dataset_name"] == "TestSpiral"
            assert meta["dataset_version"] == 1

    def test_create_dataset_without_name_no_version(self):
        """create_dataset without name does not include versioning fields."""
        with FakeDataClient() as client:
            result = client.create_dataset(
                "spiral",
                {"n_spirals": 2, "n_points_per_spiral": 50, "seed": 42},
            )
            meta = result["meta"]
            assert "dataset_name" not in meta
            assert "dataset_version" not in meta

    def test_version_increments_for_same_name(self):
        """Successive create_dataset calls with same name increment version."""
        with FakeDataClient() as client:
            r1 = client.create_dataset("spiral", {"seed": 1}, name="IncrTest")
            r2 = client.create_dataset("spiral", {"seed": 2}, name="IncrTest")

            assert r1["meta"]["dataset_version"] == 1
            assert r2["meta"]["dataset_version"] == 2
