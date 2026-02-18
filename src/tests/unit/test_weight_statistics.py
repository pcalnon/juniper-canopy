#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     test_weight_statistics.py
# Author:        Paul Calnon
# Version:       0.1.0
#
# Date:          2025-11-16
# Last Modified: 2025-11-16
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2025 Paul Calnon
#
# Description:
#    Unit tests for weight statistics computation module.
#
#####################################################################################################################################################################################################
import numpy as np
import pytest

from backend.statistics import compute_weight_statistics


class TestWeightStatisticsBasics:
    """Test basic weight statistics computation."""

    def test_normal_weights(self):
        """Test statistics computation with normal distribution of weights."""
        np.random.seed(42)
        weights = np.random.randn(100)

        stats = compute_weight_statistics(weights)

        assert stats["total_weights"] == 100
        assert isinstance(stats["mean"], float)
        assert isinstance(stats["std_dev"], float)
        assert isinstance(stats["variance"], float)
        assert stats["positive_weights"] + stats["negative_weights"] + stats["zero_weights"] == 100

    def test_positive_negative_zero_counts(self):
        """Test correct counting of positive, negative, and zero weights."""
        weights = np.array([1.0, 2.0, -1.0, -2.0, 0.0, 3.0, -3.0, 0.0])

        stats = compute_weight_statistics(weights)

        assert stats["positive_weights"] == 3
        assert stats["negative_weights"] == 3
        assert stats["zero_weights"] == 2
        assert stats["total_weights"] == 8

    def test_mean_computation(self):
        """Test mean computation."""
        weights = np.array([1.0, 2.0, 3.0, 4.0, 5.0])

        stats = compute_weight_statistics(weights)

        assert abs(stats["mean"] - 3.0) < 1e-6

    def test_std_dev_computation(self):
        """Test standard deviation computation."""
        weights = np.array([1.0, 2.0, 3.0, 4.0, 5.0])

        stats = compute_weight_statistics(weights)

        expected_std = np.std(weights, ddof=1)
        assert abs(stats["std_dev"] - expected_std) < 1e-6

    def test_median_computation(self):
        """Test median computation."""
        weights = np.array([1.0, 2.0, 3.0, 4.0, 5.0])

        stats = compute_weight_statistics(weights)

        assert stats["median"] == 3.0


class TestWeightStatisticsEdgeCases:
    """Test edge cases for weight statistics computation."""

    def test_empty_weights(self):
        """Test handling of empty weights array."""
        weights = np.array([])

        stats = compute_weight_statistics(weights)

        assert stats["total_weights"] == 0
        assert stats["mean"] == 0.0
        assert stats["std_dev"] == 0.0
        assert stats["positive_weights"] == 0
        assert stats["negative_weights"] == 0
        assert stats["zero_weights"] == 0

    def test_single_value(self):
        """Test handling of single weight value."""
        weights = np.array([5.0])

        stats = compute_weight_statistics(weights)

        assert stats["total_weights"] == 1
        assert stats["mean"] == 5.0
        assert stats["std_dev"] == 0.0
        assert stats["variance"] == 0.0
        assert stats["median"] == 5.0
        assert stats["positive_weights"] == 1
        assert stats["negative_weights"] == 0

    def test_all_zeros(self):
        """Test handling of all zero weights."""
        weights = np.array([0.0, 0.0, 0.0, 0.0])

        stats = compute_weight_statistics(weights)

        assert stats["total_weights"] == 4
        assert stats["mean"] == 0.0
        assert stats["std_dev"] == 0.0
        assert stats["zero_weights"] == 4
        assert stats["positive_weights"] == 0
        assert stats["negative_weights"] == 0

    def test_all_same_value(self):
        """Test handling of all same non-zero values."""
        weights = np.array([3.5, 3.5, 3.5, 3.5, 3.5])

        stats = compute_weight_statistics(weights)

        assert stats["total_weights"] == 5
        assert stats["mean"] == 3.5
        assert stats["std_dev"] == 0.0
        assert stats["variance"] == 0.0
        assert stats["positive_weights"] == 5

    def test_negative_single_value(self):
        """Test handling of single negative value."""
        weights = np.array([-2.5])

        stats = compute_weight_statistics(weights)

        assert stats["total_weights"] == 1
        assert stats["mean"] == -2.5
        assert stats["negative_weights"] == 1
        assert stats["positive_weights"] == 0


class TestAdvancedStatistics:
    """Test advanced statistical measures."""

    def test_skewness_computation(self):
        """Test skewness computation."""
        np.random.seed(42)
        weights = np.random.randn(100)

        stats = compute_weight_statistics(weights)

        assert "skewness" in stats
        assert isinstance(stats["skewness"], float)

    def test_kurtosis_computation(self):
        """Test kurtosis computation."""
        np.random.seed(42)
        weights = np.random.randn(100)

        stats = compute_weight_statistics(weights)

        assert "kurtosis" in stats
        assert isinstance(stats["kurtosis"], float)

    def test_mad_computation(self):
        """Test median absolute deviation computation."""
        weights = np.array([1.0, 2.0, 3.0, 4.0, 5.0])

        stats = compute_weight_statistics(weights)

        assert "mad" in stats
        assert stats["mad"] > 0

    def test_iqr_computation(self):
        """Test interquartile range computation."""
        weights = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])

        stats = compute_weight_statistics(weights)

        assert "iqr" in stats
        assert stats["iqr"] > 0
        assert stats["q1"] < stats["q3"]

    def test_z_score_distribution(self):
        """Test z-score distribution computation."""
        np.random.seed(42)
        weights = np.random.randn(1000)

        stats = compute_weight_statistics(weights)

        z_dist = stats["z_score_distribution"]
        assert "within_1_sigma" in z_dist
        assert "within_2_sigma" in z_dist
        assert "within_3_sigma" in z_dist
        assert "beyond_3_sigma" in z_dist

        # For normal distribution, ~68% within 1 sigma, ~95% within 2 sigma
        assert z_dist["within_1_sigma"] > 600
        assert z_dist["within_2_sigma"] > 900
        assert z_dist["within_3_sigma"] > 990


class TestInputValidation:
    """Test input validation and error handling."""

    def test_none_input(self):
        """Test handling of None input."""
        with pytest.raises(ValueError):
            compute_weight_statistics(None)

    def test_list_input(self):
        """Test handling of list input (should convert to numpy array)."""
        weights = [1.0, 2.0, 3.0, 4.0, 5.0]

        stats = compute_weight_statistics(weights)

        assert stats["total_weights"] == 5
        assert abs(stats["mean"] - 3.0) < 1e-6

    def test_multidimensional_array(self):
        """Test handling of multidimensional array (should flatten)."""
        weights = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])

        stats = compute_weight_statistics(weights)

        assert stats["total_weights"] == 6
        assert abs(stats["mean"] - 3.5) < 1e-6


class TestExceptionHandling:
    """Test exception handling in statistics computation."""

    def test_skewness_exception_handling(self, monkeypatch):
        """Test that skewness exception is caught and returns 0.0."""
        from scipy import stats as scipy_stats

        def mock_skew(*args, **kwargs):
            raise RuntimeError("Simulated skewness failure")

        monkeypatch.setattr(scipy_stats, "skew", mock_skew)

        weights = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        result = compute_weight_statistics(weights)

        assert result["skewness"] == 0.0

    def test_kurtosis_exception_handling(self, monkeypatch):
        """Test that kurtosis exception is caught and returns 0.0."""
        from scipy import stats as scipy_stats

        def mock_kurtosis(*args, **kwargs):
            raise RuntimeError("Simulated kurtosis failure")

        monkeypatch.setattr(scipy_stats, "kurtosis", mock_kurtosis)

        weights = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        result = compute_weight_statistics(weights)

        assert result["kurtosis"] == 0.0

    def test_both_skewness_and_kurtosis_exceptions(self, monkeypatch):
        """Test that both exceptions can occur and be handled."""
        from scipy import stats as scipy_stats

        def mock_skew(*args, **kwargs):
            raise ValueError("Skew computation error")

        def mock_kurtosis(*args, **kwargs):
            raise ValueError("Kurtosis computation error")

        monkeypatch.setattr(scipy_stats, "skew", mock_skew)
        monkeypatch.setattr(scipy_stats, "kurtosis", mock_kurtosis)

        weights = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        result = compute_weight_statistics(weights)

        assert result["skewness"] == 0.0
        assert result["kurtosis"] == 0.0
        assert result["mean"] == 3.0

    def test_zero_std_dev_z_score_fallback(self, monkeypatch):
        """Test z-score fallback when std_dev is 0 (bypasses constant check)."""
        weights = np.array([1.0, 2.0, 3.0])

        def mock_std(arr, ddof=0):
            return 0.0

        monkeypatch.setattr(np, "std", mock_std)

        result = compute_weight_statistics(weights)

        z_dist = result["z_score_distribution"]
        assert z_dist["within_1_sigma"] == 3
        assert z_dist["within_2_sigma"] == 3
        assert z_dist["within_3_sigma"] == 3
        assert z_dist["beyond_3_sigma"] == 0


class TestStatisticalAccuracy:
    """Test accuracy of statistical computations."""

    def test_min_max_values(self):
        """Test min and max value computation."""
        weights = np.array([-10.0, -5.0, 0.0, 5.0, 10.0])

        stats = compute_weight_statistics(weights)

        assert stats["min"] == -10.0
        assert stats["max"] == 10.0

    def test_variance_computation(self):
        """Test variance computation."""
        weights = np.array([1.0, 2.0, 3.0, 4.0, 5.0])

        stats = compute_weight_statistics(weights)

        expected_var = np.var(weights, ddof=1)
        assert abs(stats["variance"] - expected_var) < 1e-6

    def test_percentiles(self):
        """Test quartile computations."""
        weights = np.linspace(0, 100, 101)

        stats = compute_weight_statistics(weights)

        assert abs(stats["q1"] - 25.0) < 2.0
        assert abs(stats["q3"] - 75.0) < 2.0
