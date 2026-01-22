#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     test_data_adapter_normalization.py
# Author:        Paul Calnon
# Version:       0.1.0 (0.7.3)
#
# Date:          2026-01-22
# Last Modified: 2026-01-22
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
#
# Description:
#    Unit tests for DataAdapter.normalize_metrics() and denormalize_metrics() methods.
#    These methods handle key naming differences between Cascor backend and Canopy frontend.
#
#####################################################################################################################################################################################################
# Notes:
#
# Integration Issue 4.3: Data Format Alignment
# - Cascor uses 'value_loss'/'value_accuracy'
# - Canopy expects 'val_loss'/'val_accuracy'
#
#####################################################################################################################################################################################################
import pytest

from backend.data_adapter import DataAdapter


class TestNormalizeMetrics:
    """Tests for DataAdapter.normalize_metrics() method."""

    @pytest.fixture
    def adapter(self):
        """Create DataAdapter instance."""
        return DataAdapter()

    @pytest.mark.unit
    def test_normalize_none_input(self, adapter):
        """Test that None input returns empty dict."""
        result = adapter.normalize_metrics(None)
        assert result == {}

    @pytest.mark.unit
    def test_normalize_empty_dict(self, adapter):
        """Test that empty dict returns empty dict."""
        result = adapter.normalize_metrics({})
        assert result == {}

    @pytest.mark.unit
    def test_normalize_value_loss_to_val_loss(self, adapter):
        """Test value_loss → val_loss conversion."""
        raw = {"epoch": 5, "value_loss": 0.3}
        result = adapter.normalize_metrics(raw)
        assert "val_loss" in result
        assert result["val_loss"] == 0.3
        assert "value_loss" not in result

    @pytest.mark.unit
    def test_normalize_value_accuracy_to_val_accuracy(self, adapter):
        """Test value_accuracy → val_accuracy conversion."""
        raw = {"epoch": 5, "value_accuracy": 0.9}
        result = adapter.normalize_metrics(raw)
        assert "val_accuracy" in result
        assert result["val_accuracy"] == 0.9
        assert "value_accuracy" not in result

    @pytest.mark.unit
    def test_normalize_legacy_loss_to_train_loss(self, adapter):
        """Test legacy 'loss' → 'train_loss' conversion."""
        raw = {"epoch": 5, "loss": 0.25}
        result = adapter.normalize_metrics(raw)
        assert "train_loss" in result
        assert result["train_loss"] == 0.25
        assert "loss" not in result

    @pytest.mark.unit
    def test_normalize_legacy_accuracy_to_train_accuracy(self, adapter):
        """Test legacy 'accuracy' → 'train_accuracy' conversion."""
        raw = {"epoch": 5, "accuracy": 0.85}
        result = adapter.normalize_metrics(raw)
        assert "train_accuracy" in result
        assert result["train_accuracy"] == 0.85
        assert "accuracy" not in result

    @pytest.mark.unit
    def test_normalize_full_cascor_output(self, adapter):
        """Test full Cascor output normalization."""
        raw = {
            "epoch": 10,
            "train_loss": 0.15,
            "train_accuracy": 0.92,
            "value_loss": 0.2,
            "value_accuracy": 0.88,
            "hidden_units": 3,
            "phase": "output",
            "correlation": 0.75,
        }
        result = adapter.normalize_metrics(raw)

        # Check normalized keys
        assert result["epoch"] == 10
        assert result["train_loss"] == 0.15
        assert result["train_accuracy"] == 0.92
        assert result["val_loss"] == 0.2
        assert result["val_accuracy"] == 0.88
        assert result["hidden_units"] == 3
        assert result["phase"] == "output"
        assert result["correlation"] == 0.75

        # Check old keys removed
        assert "value_loss" not in result
        assert "value_accuracy" not in result

    @pytest.mark.unit
    def test_normalize_passthrough_keys(self, adapter):
        """Test that unknown keys pass through unchanged."""
        raw = {"epoch": 5, "custom_metric": 42, "another_key": "value"}
        result = adapter.normalize_metrics(raw)
        assert result["epoch"] == 5
        assert result["custom_metric"] == 42
        assert result["another_key"] == "value"

    @pytest.mark.unit
    def test_normalize_preserves_train_loss_over_legacy_loss(self, adapter):
        """Test that train_loss is preserved if both train_loss and loss are present."""
        raw = {"train_loss": 0.1, "loss": 0.5}
        result = adapter.normalize_metrics(raw)
        # train_loss should be preserved (not overwritten by loss)
        assert result["train_loss"] == 0.1

    @pytest.mark.unit
    def test_normalize_already_normalized_input(self, adapter):
        """Test that already-normalized input passes through."""
        raw = {
            "epoch": 5,
            "train_loss": 0.2,
            "train_accuracy": 0.9,
            "val_loss": 0.25,
            "val_accuracy": 0.85,
        }
        result = adapter.normalize_metrics(raw)
        assert result == raw

    @pytest.mark.unit
    def test_normalize_handles_none_values(self, adapter):
        """Test that None values are preserved."""
        raw = {"epoch": 5, "value_loss": None, "value_accuracy": None}
        result = adapter.normalize_metrics(raw)
        assert result["val_loss"] is None
        assert result["val_accuracy"] is None


class TestDenormalizeMetrics:
    """Tests for DataAdapter.denormalize_metrics() method."""

    @pytest.fixture
    def adapter(self):
        """Create DataAdapter instance."""
        return DataAdapter()

    @pytest.mark.unit
    def test_denormalize_none_input(self, adapter):
        """Test that None input returns empty dict."""
        result = adapter.denormalize_metrics(None)
        assert result == {}

    @pytest.mark.unit
    def test_denormalize_empty_dict(self, adapter):
        """Test that empty dict returns empty dict."""
        result = adapter.denormalize_metrics({})
        assert result == {}

    @pytest.mark.unit
    def test_denormalize_val_loss_to_value_loss(self, adapter):
        """Test val_loss → value_loss conversion."""
        normalized = {"epoch": 5, "val_loss": 0.3}
        result = adapter.denormalize_metrics(normalized)
        assert "value_loss" in result
        assert result["value_loss"] == 0.3
        assert "val_loss" not in result

    @pytest.mark.unit
    def test_denormalize_val_accuracy_to_value_accuracy(self, adapter):
        """Test val_accuracy → value_accuracy conversion."""
        normalized = {"epoch": 5, "val_accuracy": 0.9}
        result = adapter.denormalize_metrics(normalized)
        assert "value_accuracy" in result
        assert result["value_accuracy"] == 0.9
        assert "val_accuracy" not in result

    @pytest.mark.unit
    def test_denormalize_full_canopy_metrics(self, adapter):
        """Test full Canopy metrics denormalization."""
        normalized = {
            "epoch": 10,
            "train_loss": 0.15,
            "train_accuracy": 0.92,
            "val_loss": 0.2,
            "val_accuracy": 0.88,
            "hidden_units": 3,
        }
        result = adapter.denormalize_metrics(normalized)

        assert result["epoch"] == 10
        assert result["train_loss"] == 0.15
        assert result["train_accuracy"] == 0.92
        assert result["value_loss"] == 0.2
        assert result["value_accuracy"] == 0.88
        assert result["hidden_units"] == 3

    @pytest.mark.unit
    def test_denormalize_passthrough_keys(self, adapter):
        """Test that unknown keys pass through unchanged."""
        normalized = {"epoch": 5, "custom_metric": 42}
        result = adapter.denormalize_metrics(normalized)
        assert result["epoch"] == 5
        assert result["custom_metric"] == 42


class TestNormalizeDenormalizeRoundTrip:
    """Tests for round-trip normalization/denormalization."""

    @pytest.fixture
    def adapter(self):
        """Create DataAdapter instance."""
        return DataAdapter()

    @pytest.mark.unit
    def test_round_trip_cascor_to_canopy_to_cascor(self, adapter):
        """Test Cascor → Canopy → Cascor round trip."""
        cascor_original = {
            "epoch": 10,
            "train_loss": 0.15,
            "train_accuracy": 0.92,
            "value_loss": 0.2,
            "value_accuracy": 0.88,
            "hidden_units": 3,
        }

        # Normalize (Cascor → Canopy)
        canopy_format = adapter.normalize_metrics(cascor_original)
        assert "val_loss" in canopy_format
        assert "val_accuracy" in canopy_format

        # Denormalize (Canopy → Cascor)
        cascor_restored = adapter.denormalize_metrics(canopy_format)
        assert "value_loss" in cascor_restored
        assert "value_accuracy" in cascor_restored

        # Values should match
        assert cascor_restored["value_loss"] == cascor_original["value_loss"]
        assert cascor_restored["value_accuracy"] == cascor_original["value_accuracy"]
        assert cascor_restored["train_loss"] == cascor_original["train_loss"]
        assert cascor_restored["train_accuracy"] == cascor_original["train_accuracy"]

    @pytest.mark.unit
    def test_idempotent_normalization(self, adapter):
        """Test that normalizing already-normalized data is idempotent."""
        normalized = {
            "epoch": 5,
            "train_loss": 0.2,
            "val_loss": 0.25,
        }
        result = adapter.normalize_metrics(normalized)
        # Should be unchanged
        assert result == normalized

    @pytest.mark.unit
    def test_idempotent_denormalization(self, adapter):
        """Test that denormalizing already-denormalized data is idempotent."""
        denormalized = {
            "epoch": 5,
            "train_loss": 0.2,
            "value_loss": 0.25,
        }
        result = adapter.denormalize_metrics(denormalized)
        # Should be unchanged
        assert result == denormalized
