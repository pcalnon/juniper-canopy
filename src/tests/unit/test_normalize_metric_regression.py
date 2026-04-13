"""Phase H: Regression gate tests for _normalize_metric dual-format contract.

§S14 — Locks in the dual metric format (flat + nested keys both present)
with regression tests and golden shape hash. NO removal of either format
is permitted (C-22). Changes to the output shape require explicit review
via CODEOWNERS hard merge gate (D-27).

Golden shape file: tests/fixtures/normalize_metric_shape.golden.json
"""

import json
import os

import pytest

from backend.cascor_service_adapter import CascorServiceAdapter

# ===================================================================
# Fixtures
# ===================================================================

_FIXTURES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fixtures")
_GOLDEN_PATH = os.path.join(_FIXTURES_DIR, "normalize_metric_shape.golden.json")


@pytest.fixture
def sample_cascor_metric():
    """Representative metric entry from cascor with all fields."""
    return {
        "epoch": 42,
        "loss": 0.123,
        "accuracy": 0.876,
        "validation_loss": 0.234,
        "validation_accuracy": 0.765,
        "hidden_units": 3,
        "phase": "output_training",
        "timestamp": "2026-04-13T17:00:00Z",
    }


@pytest.fixture
def normalized(sample_cascor_metric):
    """Normalized output from _normalize_metric."""
    return CascorServiceAdapter._normalize_metric(sample_cascor_metric)


@pytest.fixture
def golden_shape():
    """Load the golden shape file."""
    with open(_GOLDEN_PATH) as f:
        return json.load(f)


# ===================================================================
# Tests — Phase H (§S14)
# ===================================================================


@pytest.mark.unit
class TestNormalizeMetricRegression:
    """Regression gate for _normalize_metric dual-format contract."""

    # ------------------------------------------------------------------
    # 1. Dual format: both flat AND nested keys present
    # ------------------------------------------------------------------

    def test_normalize_metric_produces_dual_format(self, normalized):
        """Output contains BOTH flat keys AND nested dicts (C-22 contract).

        The flat keys (train_loss, train_accuracy, etc.) are used by
        API/client consumers. The nested keys (metrics.loss, etc.) are
        used by the dashboard metrics_panel.py rendering.

        Neither format may be removed without an RFC per D-21.
        """
        # Flat keys present
        assert "train_loss" in normalized
        assert "train_accuracy" in normalized
        assert "val_loss" in normalized
        assert "val_accuracy" in normalized
        assert "hidden_units" in normalized
        assert "epoch" in normalized

        # Nested keys present
        assert "metrics" in normalized
        assert isinstance(normalized["metrics"], dict)
        assert "loss" in normalized["metrics"]
        assert "accuracy" in normalized["metrics"]
        assert "val_loss" in normalized["metrics"]
        assert "val_accuracy" in normalized["metrics"]

        # Values consistent between flat and nested
        assert normalized["train_loss"] == normalized["metrics"]["loss"]
        assert normalized["train_accuracy"] == normalized["metrics"]["accuracy"]
        assert normalized["val_loss"] == normalized["metrics"]["val_loss"]
        assert normalized["val_accuracy"] == normalized["metrics"]["val_accuracy"]

        # Verify actual values from cascor input
        assert normalized["train_loss"] == pytest.approx(0.123)
        assert normalized["train_accuracy"] == pytest.approx(0.876)
        assert normalized["val_loss"] == pytest.approx(0.234)
        assert normalized["val_accuracy"] == pytest.approx(0.765)

    # ------------------------------------------------------------------
    # 2. Nested topology present
    # ------------------------------------------------------------------

    def test_normalize_metric_nested_topology_present(self, normalized):
        """Output contains network_topology dict with hidden_units.

        The metrics_panel.py reads topology via:
            m.get("network_topology", {}).get("hidden_units", 0)
        """
        assert "network_topology" in normalized
        assert isinstance(normalized["network_topology"], dict)
        assert "hidden_units" in normalized["network_topology"]
        assert normalized["network_topology"]["hidden_units"] == 3

        # Flat hidden_units also present and consistent
        assert normalized["hidden_units"] == 3
        assert normalized["hidden_units"] == normalized["network_topology"]["hidden_units"]

    # ------------------------------------------------------------------
    # 3. Legacy timestamp field preserved
    # ------------------------------------------------------------------

    def test_normalize_metric_preserves_legacy_timestamp_field(self, normalized):
        """timestamp field is preserved from input (not dropped or renamed).

        Legacy consumers rely on the timestamp being present at the top
        level of the normalized output.
        """
        assert "timestamp" in normalized
        assert normalized["timestamp"] == "2026-04-13T17:00:00Z"

        # phase also preserved
        assert "phase" in normalized
        assert normalized["phase"] == "output_training"

    def test_normalize_metric_preserves_none_timestamp(self):
        """timestamp is None when not in input (not KeyError)."""
        result = CascorServiceAdapter._normalize_metric({"epoch": 1})
        assert "timestamp" in result
        assert result["timestamp"] is None

    # ------------------------------------------------------------------
    # 4. Shape hash matches golden file
    # ------------------------------------------------------------------

    def test_normalize_metric_shape_hash_matches_golden_file(self, normalized, golden_shape):
        """Output key structure matches the golden shape file.

        Any change to the key set (additions OK, removals BLOCKED)
        will fail this test, flagging the change for review. The golden
        file lives at tests/fixtures/normalize_metric_shape.golden.json.
        """
        # Verify top-level keys are a superset of golden (additions OK, removals BLOCKED)
        actual_top_keys = sorted(normalized.keys())
        golden_top_keys = golden_shape["top_level_keys"]
        missing = set(golden_top_keys) - set(actual_top_keys)
        assert not missing, f"Keys removed from _normalize_metric output (C-22 violation): {missing}"

        # Verify nested keys are a superset of golden
        for nested_key, expected_subkeys in golden_shape["nested_keys"].items():
            assert nested_key in normalized, f"Nested dict '{nested_key}' removed (C-22 violation)"
            assert isinstance(normalized[nested_key], dict), f"'{nested_key}' is no longer a dict"
            actual_subkeys = sorted(normalized[nested_key].keys())
            missing_sub = set(expected_subkeys) - set(actual_subkeys)
            assert not missing_sub, f"Keys removed from '{nested_key}' (C-22 violation): {missing_sub}"

    # ------------------------------------------------------------------
    # 5. Zero-value preservation (regression for _first_defined)
    # ------------------------------------------------------------------

    def test_normalize_metric_preserves_zero_values(self):
        """Zero values (0.0) are preserved, not treated as None.

        This is the critical _first_defined() behavior — using 'in' checks
        rather than truthiness so that loss=0.0 at training end is kept.
        """
        entry = {
            "train_loss": 0.0,
            "train_accuracy": 0.0,
            "val_loss": 0.0,
            "val_accuracy": 0.0,
            "hidden_units": 0,
            "epoch": 0,
        }
        result = CascorServiceAdapter._normalize_metric(entry)
        assert result["train_loss"] == 0.0
        assert result["train_accuracy"] == 0.0
        assert result["val_loss"] == 0.0
        assert result["val_accuracy"] == 0.0
        assert result["metrics"]["loss"] == 0.0
        assert result["metrics"]["accuracy"] == 0.0

    # ------------------------------------------------------------------
    # 6. Canopy-name input passthrough
    # ------------------------------------------------------------------

    def test_normalize_metric_accepts_canopy_names(self):
        """Input using canopy names (train_loss, val_loss) works directly."""
        entry = {
            "train_loss": 0.5,
            "train_accuracy": 0.8,
            "val_loss": 0.6,
            "val_accuracy": 0.7,
            "epoch": 10,
        }
        result = CascorServiceAdapter._normalize_metric(entry)
        assert result["train_loss"] == pytest.approx(0.5)
        assert result["val_loss"] == pytest.approx(0.6)
        assert result["metrics"]["loss"] == pytest.approx(0.5)
        assert result["metrics"]["val_loss"] == pytest.approx(0.6)
