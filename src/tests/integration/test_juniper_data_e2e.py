#!/usr/bin/env python
"""E2E integration tests for the JuniperData dataset pipeline (CAN-MED-010).

Tests the full data lifecycle: dataset creation -> NPZ download -> tensor
conversion -> training consumption -> metric verification.

Default tests use FakeDataClient and always run. Live service tests are gated
behind the JUNIPER_DATA_E2E_TEST=1 environment variable and require a running
JuniperData service at JUNIPER_DATA_URL (default: http://localhost:8100).

Run (fake only):
    pytest tests/integration/test_juniper_data_e2e.py -v

Run (with live service):
    JUNIPER_DATA_E2E_TEST=1 JUNIPER_DATA_URL=http://localhost:8100 \
        pytest tests/integration/test_juniper_data_e2e.py -v
"""
import math
import os
import sys
import uuid
from pathlib import Path

import numpy as np
import pytest

src_path = Path(__file__).parent.parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

JUNIPER_DATA_E2E = os.environ.get("JUNIPER_DATA_E2E_TEST", "0") == "1"
JUNIPER_DATA_URL = os.environ.get("JUNIPER_DATA_URL", "http://localhost:8100")

pytestmark = [pytest.mark.integration]

# ---------------------------------------------------------------------------
# Standard NPZ data contract keys and validation helpers
# ---------------------------------------------------------------------------

NPZ_REQUIRED_KEYS = {"X_train", "y_train", "X_test", "y_test", "X_full", "y_full"}


def _validate_npz_arrays(arrays, *, expected_n_features=None, expected_n_classes=None, expected_n_full=None, expected_train_ratio=None):
    """Assert that NPZ arrays satisfy the Juniper data contract.

    Checks:
    - All six required keys are present
    - All arrays are float32
    - Feature/label dimensions are consistent across splits
    - Train + test = full (sample counts)
    - Optional shape constraints when provided
    """
    # All required keys present
    assert NPZ_REQUIRED_KEYS.issubset(set(arrays.keys())), f"Missing NPZ keys: {NPZ_REQUIRED_KEYS - set(arrays.keys())}"

    # All float32
    for key in NPZ_REQUIRED_KEYS:
        assert arrays[key].dtype == np.float32, f"{key} dtype is {arrays[key].dtype}, expected float32"

    # Feature dimensions consistent
    n_features = arrays["X_train"].shape[1]
    assert arrays["X_test"].shape[1] == n_features
    assert arrays["X_full"].shape[1] == n_features

    # Label dimensions consistent
    n_classes = arrays["y_train"].shape[1]
    assert arrays["y_test"].shape[1] == n_classes
    assert arrays["y_full"].shape[1] == n_classes

    # Sample counts: train + test == full
    n_train = arrays["X_train"].shape[0]
    n_test = arrays["X_test"].shape[0]
    n_full = arrays["X_full"].shape[0]
    assert n_train + n_test == n_full, f"train({n_train}) + test({n_test}) != full({n_full})"

    # y dimensions match X dimensions
    assert arrays["y_train"].shape[0] == n_train
    assert arrays["y_test"].shape[0] == n_test
    assert arrays["y_full"].shape[0] == n_full

    # Optional constraints
    if expected_n_features is not None:
        assert n_features == expected_n_features, f"n_features={n_features}, expected {expected_n_features}"
    if expected_n_classes is not None:
        assert n_classes == expected_n_classes, f"n_classes={n_classes}, expected {expected_n_classes}"
    if expected_n_full is not None:
        assert n_full == expected_n_full, f"n_full={n_full}, expected {expected_n_full}"
    if expected_train_ratio is not None:
        actual_ratio = n_train / n_full
        assert abs(actual_ratio - expected_train_ratio) < 0.05, f"train_ratio={actual_ratio:.3f}, expected ~{expected_train_ratio}"


def _run_training_step(arrays):
    """Convert NPZ arrays to PyTorch tensors, run a forward pass through a
    linear layer, compute loss, and return the loss value.

    Simulates the minimal training consumption path that juniper-canopy would
    perform when forwarding data to a CasCor-compatible network.
    """
    import torch
    import torch.nn as nn

    X_train = torch.from_numpy(arrays["X_train"])
    y_train = torch.from_numpy(arrays["y_train"])

    n_features = X_train.shape[1]
    n_classes = y_train.shape[1]

    # Minimal linear model (single layer, no hidden units)
    model = nn.Linear(n_features, n_classes)

    # Forward pass
    logits = model(X_train)

    # MSE loss (CasCor uses sum-of-squared-errors; MSE is the mean variant)
    loss = nn.functional.mse_loss(logits, y_train)

    return loss.item()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def fake_client():
    """Create a FakeDataClient for offline testing."""
    pytest.importorskip("juniper_data_client.testing", reason="juniper-data-client[testing] not installed")
    from juniper_data_client.testing import FakeDataClient

    with FakeDataClient() as client:
        yield client


@pytest.fixture()
def live_client():
    """Create a real JuniperDataClient for live service testing."""
    from juniper_data_client.client import JuniperDataClient

    with JuniperDataClient(base_url=JUNIPER_DATA_URL) as client:
        yield client


# ===================================================================
# TestDatasetCreationE2E -- create + validate response structure
# ===================================================================


class TestDatasetCreationE2E:
    """Tests for dataset creation using FakeDataClient."""

    def test_create_spiral_dataset(self, fake_client):
        """Create a spiral dataset and validate response structure."""
        result = fake_client.create_dataset("spiral", {"n_spirals": 2, "n_points_per_spiral": 50, "seed": 42})

        assert "dataset_id" in result
        assert result["generator"] == "spiral"
        assert "meta" in result
        assert "artifact_url" in result
        assert result["meta"]["n_features"] == 2
        assert result["meta"]["n_classes"] == 2
        assert result["meta"]["dtype"] == "float32"

    def test_create_xor_dataset(self, fake_client):
        """Create an XOR dataset and validate response structure."""
        result = fake_client.create_dataset("xor", {"n_points": 100, "noise": 0.15, "seed": 7})

        assert "dataset_id" in result
        assert result["generator"] == "xor"
        assert result["meta"]["n_features"] == 2
        assert result["meta"]["n_classes"] == 2

    def test_create_spiral_convenience_method(self, fake_client):
        """create_spiral_dataset convenience method produces valid response."""
        result = fake_client.create_spiral_dataset(n_spirals=3, n_points_per_spiral=40, noise=0.05, seed=99)

        assert "dataset_id" in result
        assert result["generator"] == "spiral"
        assert result["meta"]["n_classes"] == 3
        assert result["meta"]["n_full"] == 3 * 40

    def test_create_circle_dataset(self, fake_client):
        """Create a circle dataset and validate response structure."""
        result = fake_client.create_dataset("circle", {"n_points": 80, "noise": 0.08, "factor": 0.4, "seed": 11})

        assert "dataset_id" in result
        assert result["generator"] == "circle"
        assert result["meta"]["n_features"] == 2
        assert result["meta"]["n_classes"] == 2

    def test_create_moon_dataset(self, fake_client):
        """Create a moon dataset and validate response structure."""
        result = fake_client.create_dataset("moon", {"n_points": 120, "noise": 0.12, "seed": 33})

        assert "dataset_id" in result
        assert result["generator"] == "moon"
        assert result["meta"]["n_features"] == 2
        assert result["meta"]["n_classes"] == 2

    def test_create_dataset_metadata_has_timestamps(self, fake_client):
        """Dataset metadata contains created_at timestamp."""
        result = fake_client.create_dataset("spiral", {"seed": 1})

        assert "created_at" in result
        assert "T" in result["created_at"]  # ISO 8601

    def test_create_dataset_with_custom_train_ratio(self, fake_client):
        """Custom train_ratio is honored in the split."""
        result = fake_client.create_dataset("xor", {"n_points": 100, "train_ratio": 0.7, "seed": 5})

        n_train = result["meta"]["n_train"]
        n_full = result["meta"]["n_full"]
        actual_ratio = n_train / n_full
        assert abs(actual_ratio - 0.7) < 0.05

    def test_create_dataset_ids_are_unique(self, fake_client):
        """Each creation returns a unique dataset_id."""
        id1 = fake_client.create_dataset("spiral", {"seed": 1})["dataset_id"]
        id2 = fake_client.create_dataset("spiral", {"seed": 2})["dataset_id"]
        id3 = fake_client.create_dataset("xor", {"seed": 1})["dataset_id"]

        assert len({id1, id2, id3}) == 3


# ===================================================================
# TestArtifactDownloadE2E -- download NPZ + validate arrays
# ===================================================================


class TestArtifactDownloadE2E:
    """Tests for artifact download and NPZ array validation."""

    def test_download_spiral_npz(self, fake_client):
        """Download spiral NPZ artifact and validate all arrays."""
        result = fake_client.create_dataset("spiral", {"n_spirals": 2, "n_points_per_spiral": 50, "seed": 42})
        arrays = fake_client.download_artifact_npz(result["dataset_id"])

        _validate_npz_arrays(arrays, expected_n_features=2, expected_n_classes=2, expected_n_full=100, expected_train_ratio=0.8)

    def test_download_xor_npz(self, fake_client):
        """Download XOR NPZ artifact and validate all arrays."""
        result = fake_client.create_dataset("xor", {"n_points": 80, "noise": 0.1, "seed": 7})
        arrays = fake_client.download_artifact_npz(result["dataset_id"])

        _validate_npz_arrays(arrays, expected_n_features=2, expected_n_classes=2, expected_n_full=80, expected_train_ratio=0.8)

    def test_download_spiral_three_arms(self, fake_client):
        """Three-arm spiral produces 3-class one-hot labels."""
        result = fake_client.create_dataset("spiral", {"n_spirals": 3, "n_points_per_spiral": 30, "seed": 10})
        arrays = fake_client.download_artifact_npz(result["dataset_id"])

        _validate_npz_arrays(arrays, expected_n_features=2, expected_n_classes=3, expected_n_full=90)

    def test_download_artifact_bytes_roundtrip(self, fake_client):
        """download_artifact_bytes produces valid NPZ that np.load can parse."""
        result = fake_client.create_dataset("xor", {"n_points": 40, "seed": 55})
        raw_bytes = fake_client.download_artifact_bytes(result["dataset_id"])

        assert isinstance(raw_bytes, bytes)
        assert len(raw_bytes) > 0

        # Round-trip: load bytes back into arrays
        import io

        loaded = np.load(io.BytesIO(raw_bytes))
        assert NPZ_REQUIRED_KEYS.issubset(set(loaded.files))
        for key in NPZ_REQUIRED_KEYS:
            assert loaded[key].dtype == np.float32

    def test_download_circle_npz(self, fake_client):
        """Download circle NPZ and validate arrays."""
        result = fake_client.create_dataset("circle", {"n_points": 100, "factor": 0.5, "seed": 22})
        arrays = fake_client.download_artifact_npz(result["dataset_id"])

        _validate_npz_arrays(arrays, expected_n_features=2, expected_n_classes=2, expected_n_full=100)

    def test_download_moon_npz(self, fake_client):
        """Download moon NPZ and validate arrays."""
        result = fake_client.create_dataset("moon", {"n_points": 60, "noise": 0.05, "seed": 44})
        arrays = fake_client.download_artifact_npz(result["dataset_id"])

        _validate_npz_arrays(arrays, expected_n_features=2, expected_n_classes=2, expected_n_full=60)

    def test_different_train_ratios(self, fake_client):
        """Train ratio parameter correctly affects split sizes."""
        for ratio in [0.5, 0.7, 0.9]:
            result = fake_client.create_dataset("xor", {"n_points": 100, "train_ratio": ratio, "seed": 42})
            arrays = fake_client.download_artifact_npz(result["dataset_id"])
            _validate_npz_arrays(arrays, expected_train_ratio=ratio)

    def test_one_hot_labels_are_valid(self, fake_client):
        """One-hot label rows each sum to 1.0 (exactly one class active)."""
        result = fake_client.create_dataset("spiral", {"n_spirals": 4, "n_points_per_spiral": 25, "seed": 8})
        arrays = fake_client.download_artifact_npz(result["dataset_id"])

        for split in ["y_train", "y_test", "y_full"]:
            row_sums = arrays[split].sum(axis=1)
            np.testing.assert_allclose(row_sums, 1.0, atol=1e-6, err_msg=f"{split} rows do not sum to 1.0")

    def test_seed_reproducibility(self, fake_client):
        """Same generator + seed produces identical arrays."""
        params = {"n_spirals": 2, "n_points_per_spiral": 30, "seed": 123}

        r1 = fake_client.create_dataset("spiral", params)
        arrays1 = fake_client.download_artifact_npz(r1["dataset_id"])

        r2 = fake_client.create_dataset("spiral", params)
        arrays2 = fake_client.download_artifact_npz(r2["dataset_id"])

        for key in NPZ_REQUIRED_KEYS:
            np.testing.assert_array_equal(arrays1[key], arrays2[key], err_msg=f"{key} differs between runs with same seed")


# ===================================================================
# TestTrainingConsumptionE2E -- tensor conversion + training step
# ===================================================================


class TestTrainingConsumptionE2E:
    """Tests that simulate canopy's training consumption of downloaded data."""

    def test_spiral_training_step(self, fake_client):
        """Spiral dataset converts to tensors and produces finite loss."""
        result = fake_client.create_dataset("spiral", {"n_spirals": 2, "n_points_per_spiral": 50, "seed": 42})
        arrays = fake_client.download_artifact_npz(result["dataset_id"])

        loss = _run_training_step(arrays)

        assert isinstance(loss, float)
        assert math.isfinite(loss), f"Loss is not finite: {loss}"
        assert loss >= 0.0, f"Loss is negative: {loss}"

    def test_xor_training_step(self, fake_client):
        """XOR dataset converts to tensors and produces finite loss."""
        result = fake_client.create_dataset("xor", {"n_points": 80, "noise": 0.1, "seed": 7})
        arrays = fake_client.download_artifact_npz(result["dataset_id"])

        loss = _run_training_step(arrays)

        assert isinstance(loss, float)
        assert math.isfinite(loss)
        assert loss >= 0.0

    def test_circle_training_step(self, fake_client):
        """Circle dataset converts to tensors and produces finite loss."""
        result = fake_client.create_dataset("circle", {"n_points": 100, "seed": 12})
        arrays = fake_client.download_artifact_npz(result["dataset_id"])

        loss = _run_training_step(arrays)

        assert isinstance(loss, float)
        assert math.isfinite(loss)
        assert loss >= 0.0

    def test_moon_training_step(self, fake_client):
        """Moon dataset converts to tensors and produces finite loss."""
        result = fake_client.create_dataset("moon", {"n_points": 80, "seed": 77})
        arrays = fake_client.download_artifact_npz(result["dataset_id"])

        loss = _run_training_step(arrays)

        assert isinstance(loss, float)
        assert math.isfinite(loss)
        assert loss >= 0.0

    def test_three_class_spiral_training_step(self, fake_client):
        """Three-class spiral trains through a linear layer without error."""
        result = fake_client.create_dataset("spiral", {"n_spirals": 3, "n_points_per_spiral": 40, "seed": 99})
        arrays = fake_client.download_artifact_npz(result["dataset_id"])

        loss = _run_training_step(arrays)

        assert math.isfinite(loss)
        assert loss >= 0.0

    def test_tensor_dtypes_match(self, fake_client):
        """PyTorch tensors inherit float32 dtype from numpy arrays."""
        import torch

        result = fake_client.create_dataset("spiral", {"n_spirals": 2, "n_points_per_spiral": 20, "seed": 1})
        arrays = fake_client.download_artifact_npz(result["dataset_id"])

        for key in NPZ_REQUIRED_KEYS:
            tensor = torch.from_numpy(arrays[key])
            assert tensor.dtype == torch.float32, f"{key} tensor dtype is {tensor.dtype}, expected float32"

    def test_full_pipeline_create_download_train(self, fake_client):
        """Full pipeline: create -> download -> validate -> train -> verify loss."""
        # Step 1: Create
        result = fake_client.create_dataset("spiral", {"n_spirals": 2, "n_points_per_spiral": 100, "noise": 0.1, "seed": 42})
        dataset_id = result["dataset_id"]
        assert dataset_id is not None

        # Step 2: Download
        arrays = fake_client.download_artifact_npz(dataset_id)

        # Step 3: Validate contract
        _validate_npz_arrays(arrays, expected_n_features=2, expected_n_classes=2, expected_n_full=200, expected_train_ratio=0.8)

        # Step 4: Train
        loss = _run_training_step(arrays)

        # Step 5: Verify
        assert math.isfinite(loss)
        assert loss >= 0.0


# ===================================================================
# TestDatasetLifecycleE2E -- create -> use -> delete -> recreate
# ===================================================================


class TestDatasetLifecycleE2E:
    """Tests for the full dataset lifecycle including deletion and recreation."""

    def test_create_then_delete(self, fake_client):
        """Created dataset can be deleted successfully."""
        result = fake_client.create_dataset("spiral", {"n_spirals": 2, "seed": 1})
        dataset_id = result["dataset_id"]

        assert fake_client.delete_dataset(dataset_id) is True

    def test_delete_removes_from_list(self, fake_client):
        """Deleted dataset no longer appears in list_datasets."""
        result = fake_client.create_dataset("xor", {"n_points": 40, "seed": 2})
        dataset_id = result["dataset_id"]

        assert dataset_id in fake_client.list_datasets()
        fake_client.delete_dataset(dataset_id)
        assert dataset_id not in fake_client.list_datasets()

    def test_regenerate_dataset_flow(self, fake_client):
        """Create -> delete -> create with different params (regenerate flow)."""
        # Create original spiral
        r1 = fake_client.create_dataset("spiral", {"n_spirals": 2, "n_points_per_spiral": 30, "seed": 10})
        id1 = r1["dataset_id"]
        arrays1 = fake_client.download_artifact_npz(id1)

        # Delete original
        fake_client.delete_dataset(id1)

        # Recreate with different parameters (more spirals, different seed)
        r2 = fake_client.create_dataset("spiral", {"n_spirals": 3, "n_points_per_spiral": 40, "seed": 20})
        id2 = r2["dataset_id"]
        arrays2 = fake_client.download_artifact_npz(id2)

        # IDs differ
        assert id1 != id2

        # New dataset has different shape (3 classes instead of 2)
        assert arrays1["y_train"].shape[1] == 2
        assert arrays2["y_train"].shape[1] == 3

        # Both are valid NPZ artifacts
        _validate_npz_arrays(arrays1, expected_n_classes=2)
        _validate_npz_arrays(arrays2, expected_n_classes=3)

    def test_regenerate_with_different_generator(self, fake_client):
        """Regenerate flow: create spiral -> delete -> create xor."""
        r1 = fake_client.create_dataset("spiral", {"n_spirals": 2, "seed": 1})
        id1 = r1["dataset_id"]
        fake_client.delete_dataset(id1)

        r2 = fake_client.create_dataset("xor", {"n_points": 60, "seed": 2})
        id2 = r2["dataset_id"]
        arrays2 = fake_client.download_artifact_npz(id2)

        _validate_npz_arrays(arrays2, expected_n_features=2, expected_n_classes=2)
        assert r2["generator"] == "xor"

    def test_list_datasets_reflects_state(self, fake_client):
        """list_datasets accurately reflects current dataset count."""
        assert len(fake_client.list_datasets()) == 0

        ids = []
        for i in range(3):
            result = fake_client.create_dataset("xor", {"n_points": 20, "seed": i})
            ids.append(result["dataset_id"])

        assert len(fake_client.list_datasets()) == 3

        fake_client.delete_dataset(ids[1])
        listed = fake_client.list_datasets()
        assert len(listed) == 2
        assert ids[1] not in listed

    def test_get_metadata_after_creation(self, fake_client):
        """get_dataset_metadata returns correct info for a created dataset."""
        result = fake_client.create_dataset("spiral", {"n_spirals": 2, "n_points_per_spiral": 50, "seed": 42})
        dataset_id = result["dataset_id"]

        metadata = fake_client.get_dataset_metadata(dataset_id)
        assert metadata["dataset_id"] == dataset_id
        assert metadata["generator"] == "spiral"
        assert metadata["meta"]["n_features"] == 2
        assert metadata["meta"]["n_classes"] == 2


# ===================================================================
# TestErrorHandlingE2E -- invalid generators, missing datasets
# ===================================================================


class TestErrorHandlingE2E:
    """Tests for error handling: invalid inputs and missing resources."""

    def test_invalid_generator_raises(self, fake_client):
        """Creating a dataset with an unknown generator raises JuniperDataValidationError."""
        from juniper_data_client.exceptions import JuniperDataValidationError

        with pytest.raises(JuniperDataValidationError, match="Unknown generator"):
            fake_client.create_dataset("nonexistent_generator", {"seed": 1})

    def test_download_nonexistent_dataset_raises(self, fake_client):
        """Downloading an artifact for a nonexistent dataset_id raises JuniperDataNotFoundError."""
        from juniper_data_client.exceptions import JuniperDataNotFoundError

        fake_id = str(uuid.uuid4())
        with pytest.raises(JuniperDataNotFoundError, match="Dataset not found"):
            fake_client.download_artifact_npz(fake_id)

    def test_download_bytes_nonexistent_raises(self, fake_client):
        """download_artifact_bytes for a nonexistent dataset_id raises JuniperDataNotFoundError."""
        from juniper_data_client.exceptions import JuniperDataNotFoundError

        fake_id = str(uuid.uuid4())
        with pytest.raises(JuniperDataNotFoundError, match="Dataset not found"):
            fake_client.download_artifact_bytes(fake_id)

    def test_delete_nonexistent_dataset_raises(self, fake_client):
        """Deleting a nonexistent dataset raises JuniperDataNotFoundError."""
        from juniper_data_client.exceptions import JuniperDataNotFoundError

        fake_id = str(uuid.uuid4())
        with pytest.raises(JuniperDataNotFoundError, match="Dataset not found"):
            fake_client.delete_dataset(fake_id)

    def test_get_metadata_nonexistent_raises(self, fake_client):
        """Getting metadata for a nonexistent dataset raises JuniperDataNotFoundError."""
        from juniper_data_client.exceptions import JuniperDataNotFoundError

        fake_id = str(uuid.uuid4())
        with pytest.raises(JuniperDataNotFoundError, match="Dataset not found"):
            fake_client.get_dataset_metadata(fake_id)

    def test_get_generator_schema_nonexistent_raises(self, fake_client):
        """Requesting schema for an unknown generator raises JuniperDataNotFoundError."""
        from juniper_data_client.exceptions import JuniperDataNotFoundError

        with pytest.raises(JuniperDataNotFoundError, match="Generator not found"):
            fake_client.get_generator_schema("totally_fake_generator")

    def test_download_after_delete_raises(self, fake_client):
        """Downloading an artifact after deletion raises JuniperDataNotFoundError."""
        from juniper_data_client.exceptions import JuniperDataNotFoundError

        result = fake_client.create_dataset("spiral", {"n_spirals": 2, "seed": 1})
        dataset_id = result["dataset_id"]

        # Download succeeds before deletion
        arrays = fake_client.download_artifact_npz(dataset_id)
        assert "X_train" in arrays

        # Delete
        fake_client.delete_dataset(dataset_id)

        # Download fails after deletion
        with pytest.raises(JuniperDataNotFoundError):
            fake_client.download_artifact_npz(dataset_id)

    def test_double_delete_raises(self, fake_client):
        """Deleting the same dataset twice raises JuniperDataNotFoundError on second call."""
        from juniper_data_client.exceptions import JuniperDataNotFoundError

        result = fake_client.create_dataset("xor", {"n_points": 20, "seed": 1})
        dataset_id = result["dataset_id"]

        fake_client.delete_dataset(dataset_id)

        with pytest.raises(JuniperDataNotFoundError):
            fake_client.delete_dataset(dataset_id)


# ===================================================================
# TestLiveServiceE2E -- gated real service tests (JUNIPER_DATA_E2E_TEST=1)
# ===================================================================


@pytest.mark.skipif(not JUNIPER_DATA_E2E, reason="Set JUNIPER_DATA_E2E_TEST=1 and ensure JuniperData is running at JUNIPER_DATA_URL")
class TestLiveServiceE2E:
    """Tests that run against a real JuniperData service.

    Gated behind JUNIPER_DATA_E2E_TEST=1. Requires a running JuniperData
    service at JUNIPER_DATA_URL (default: http://localhost:8100).
    """

    def test_health_check(self, live_client):
        """Live service health check returns healthy status."""
        health = live_client.health_check()
        assert health["status"] == "healthy"

    def test_list_generators(self, live_client):
        """Live service lists available generators including spiral and xor."""
        generators = live_client.list_generators()
        generator_names = {g["name"] for g in generators}
        assert "spiral" in generator_names
        assert "xor" in generator_names

    def test_create_spiral_live(self, live_client):
        """Create a spiral dataset on the live service."""
        result = live_client.create_dataset("spiral", {"n_spirals": 2, "n_points_per_spiral": 50, "seed": 42})

        assert "dataset_id" in result
        assert result["generator"] == "spiral"

        # Cleanup
        live_client.delete_dataset(result["dataset_id"])

    def test_create_xor_live(self, live_client):
        """Create an XOR dataset on the live service."""
        result = live_client.create_dataset("xor", {"n_points": 80, "noise": 0.1, "seed": 7})

        assert "dataset_id" in result
        assert result["generator"] == "xor"

        # Cleanup
        live_client.delete_dataset(result["dataset_id"])

    def test_full_pipeline_spiral_live(self, live_client):
        """Full pipeline on live service: create -> download -> validate -> train."""
        result = live_client.create_dataset("spiral", {"n_spirals": 2, "n_points_per_spiral": 100, "noise": 0.1, "seed": 42})
        dataset_id = result["dataset_id"]

        try:
            arrays = live_client.download_artifact_npz(dataset_id)
            _validate_npz_arrays(arrays, expected_n_features=2, expected_n_classes=2, expected_n_full=200, expected_train_ratio=0.8)

            loss = _run_training_step(arrays)
            assert math.isfinite(loss)
            assert loss >= 0.0
        finally:
            live_client.delete_dataset(dataset_id)

    def test_full_pipeline_xor_live(self, live_client):
        """Full pipeline on live service: create -> download -> validate -> train (XOR)."""
        result = live_client.create_dataset("xor", {"n_points": 100, "noise": 0.15, "seed": 7})
        dataset_id = result["dataset_id"]

        try:
            arrays = live_client.download_artifact_npz(dataset_id)
            _validate_npz_arrays(arrays, expected_n_features=2, expected_n_classes=2, expected_n_full=100, expected_train_ratio=0.8)

            loss = _run_training_step(arrays)
            assert math.isfinite(loss)
            assert loss >= 0.0
        finally:
            live_client.delete_dataset(dataset_id)

    def test_regenerate_dataset_live(self, live_client):
        """Regenerate flow on live service: create -> delete -> create with different params."""
        r1 = live_client.create_dataset("spiral", {"n_spirals": 2, "n_points_per_spiral": 30, "seed": 10})
        id1 = r1["dataset_id"]

        live_client.delete_dataset(id1)

        r2 = live_client.create_dataset("spiral", {"n_spirals": 3, "n_points_per_spiral": 40, "seed": 20})
        id2 = r2["dataset_id"]

        try:
            arrays = live_client.download_artifact_npz(id2)
            _validate_npz_arrays(arrays, expected_n_classes=3)
        finally:
            live_client.delete_dataset(id2)

    def test_invalid_generator_live(self, live_client):
        """Live service rejects unknown generator with appropriate error."""
        from juniper_data_client.exceptions import JuniperDataClientError

        with pytest.raises(JuniperDataClientError):
            live_client.create_dataset("nonexistent_generator", {"seed": 1})

    def test_nonexistent_dataset_live(self, live_client):
        """Live service returns 404 for nonexistent dataset_id."""
        from juniper_data_client.exceptions import JuniperDataNotFoundError

        fake_id = str(uuid.uuid4())
        with pytest.raises(JuniperDataNotFoundError):
            live_client.download_artifact_npz(fake_id)

    def test_artifact_bytes_roundtrip_live(self, live_client):
        """download_artifact_bytes from live service can be parsed back to NPZ."""
        import io

        result = live_client.create_dataset("xor", {"n_points": 40, "seed": 55})
        dataset_id = result["dataset_id"]

        try:
            raw_bytes = live_client.download_artifact_bytes(dataset_id)
            assert isinstance(raw_bytes, bytes)
            assert len(raw_bytes) > 0

            loaded = np.load(io.BytesIO(raw_bytes))
            assert NPZ_REQUIRED_KEYS.issubset(set(loaded.files))
        finally:
            live_client.delete_dataset(dataset_id)
