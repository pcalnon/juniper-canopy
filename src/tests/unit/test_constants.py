#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     test_constants.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2025-11-17
# Last Modified: 2025-11-17
# License:       MIT License
# Copyright:     Copyright (c) 2024-2025 Paul Calnon
# Description:   Unit tests for constants module
#####################################################################
"""Unit tests for constants module — training, dashboard, and server constants."""

import pytest  # noqa: F401 - needed for test fixtures

from canopy_constants import DashboardConstants, ServerConstants, TrainingConstants


class TestTrainingConstants:
    """Test training constants validity and relationships."""

    def test_epoch_constraints(self):
        """Test epoch min/max/default relationships.

        Updated 2026-04-10: MAX_TRAINING_EPOCHS raised from 1e7 to 1e11 per
        canopy requirements — the cap should not silently surprise users with
        long-running jobs by clipping at an artificially low value.
        """
        assert TrainingConstants.MIN_TRAINING_EPOCHS < TrainingConstants.DEFAULT_TRAINING_EPOCHS
        assert TrainingConstants.DEFAULT_TRAINING_EPOCHS < TrainingConstants.MAX_TRAINING_EPOCHS
        assert TrainingConstants.MIN_TRAINING_EPOCHS == 10
        assert TrainingConstants.MAX_TRAINING_EPOCHS == 100000000000
        assert TrainingConstants.DEFAULT_TRAINING_EPOCHS == 1000000

    def test_learning_rate_constraints(self):
        """Test learning rate min/max/default relationships."""
        assert TrainingConstants.MIN_LEARNING_RATE < TrainingConstants.DEFAULT_LEARNING_RATE
        assert TrainingConstants.DEFAULT_LEARNING_RATE < TrainingConstants.MAX_LEARNING_RATE
        assert TrainingConstants.MIN_LEARNING_RATE == 0.0001
        assert TrainingConstants.MAX_LEARNING_RATE == 1.0
        assert TrainingConstants.DEFAULT_LEARNING_RATE == 0.01

    def test_hidden_units_constraints(self):
        """Test hidden units min/max/default relationships."""
        assert TrainingConstants.MIN_HIDDEN_UNITS <= TrainingConstants.DEFAULT_MAX_HIDDEN_UNITS
        assert TrainingConstants.DEFAULT_MAX_HIDDEN_UNITS <= TrainingConstants.MAX_HIDDEN_UNITS
        assert TrainingConstants.MIN_HIDDEN_UNITS == 0
        assert TrainingConstants.MAX_HIDDEN_UNITS == 10000
        assert TrainingConstants.DEFAULT_MAX_HIDDEN_UNITS == 1000

    def test_constants_are_integers(self):
        """Test that integer constants are actually integers."""
        assert isinstance(TrainingConstants.MIN_TRAINING_EPOCHS, int)
        assert isinstance(TrainingConstants.MAX_TRAINING_EPOCHS, int)
        assert isinstance(TrainingConstants.DEFAULT_TRAINING_EPOCHS, int)
        assert isinstance(TrainingConstants.DEFAULT_MAX_HIDDEN_UNITS, int)
        assert isinstance(TrainingConstants.MIN_HIDDEN_UNITS, int)
        assert isinstance(TrainingConstants.MAX_HIDDEN_UNITS, int)

    def test_constants_are_floats(self):
        """Test that float constants are actually floats."""
        assert isinstance(TrainingConstants.DEFAULT_LEARNING_RATE, float)
        assert isinstance(TrainingConstants.MIN_LEARNING_RATE, float)
        assert isinstance(TrainingConstants.MAX_LEARNING_RATE, float)

    def test_positive_values(self):
        """Test that all training constants are positive."""
        assert TrainingConstants.MIN_TRAINING_EPOCHS > 0
        assert TrainingConstants.MAX_TRAINING_EPOCHS > 0
        assert TrainingConstants.DEFAULT_TRAINING_EPOCHS > 0
        assert TrainingConstants.DEFAULT_LEARNING_RATE > 0
        assert TrainingConstants.MIN_LEARNING_RATE > 0
        assert TrainingConstants.MAX_LEARNING_RATE > 0
        assert TrainingConstants.MIN_HIDDEN_UNITS >= 0
        assert TrainingConstants.MAX_HIDDEN_UNITS > 0
        assert TrainingConstants.DEFAULT_MAX_HIDDEN_UNITS > 0


class TestDashboardConstants:
    """Test dashboard constants."""

    def test_update_intervals(self):
        """Test update interval values and relationships."""
        assert DashboardConstants.FAST_UPDATE_INTERVAL_MS == 1000
        assert DashboardConstants.SLOW_UPDATE_INTERVAL_MS == 5000
        assert DashboardConstants.FAST_UPDATE_INTERVAL_MS < DashboardConstants.SLOW_UPDATE_INTERVAL_MS

    def test_api_timeout(self):
        """Test API timeout value."""
        assert DashboardConstants.API_TIMEOUT_SECONDS == 2
        assert isinstance(DashboardConstants.API_TIMEOUT_SECONDS, int)
        assert DashboardConstants.API_TIMEOUT_SECONDS > 0

    def test_data_limits(self):
        """Test data limit values and relationships."""
        assert DashboardConstants.MAX_METRICS_HISTORY == 100
        assert DashboardConstants.MAX_DATA_POINTS == 10000
        assert DashboardConstants.MAX_METRICS_HISTORY < DashboardConstants.MAX_DATA_POINTS
        assert isinstance(DashboardConstants.MAX_METRICS_HISTORY, int)
        assert isinstance(DashboardConstants.MAX_DATA_POINTS, int)

    def test_positive_values(self):
        """Test that all dashboard constants are positive."""
        assert DashboardConstants.FAST_UPDATE_INTERVAL_MS > 0
        assert DashboardConstants.SLOW_UPDATE_INTERVAL_MS > 0
        assert DashboardConstants.API_TIMEOUT_SECONDS > 0
        assert DashboardConstants.MAX_METRICS_HISTORY > 0
        assert DashboardConstants.MAX_DATA_POINTS > 0


class TestServerConstants:
    """Test server configuration constants."""

    def test_default_host(self):
        """Test default host value."""
        assert ServerConstants.DEFAULT_HOST == "127.0.0.1"
        assert isinstance(ServerConstants.DEFAULT_HOST, str)

    def test_default_port(self):
        """Test default port value."""
        assert ServerConstants.DEFAULT_PORT == 8050
        assert isinstance(ServerConstants.DEFAULT_PORT, int)
        assert 1024 <= ServerConstants.DEFAULT_PORT <= 65535

    def test_websocket_paths(self):
        """Test WebSocket path values."""
        assert ServerConstants.WS_TRAINING_PATH == "/ws/training"
        assert ServerConstants.WS_CONTROL_PATH == "/ws/control"
        assert isinstance(ServerConstants.WS_TRAINING_PATH, str)
        assert isinstance(ServerConstants.WS_CONTROL_PATH, str)
        assert ServerConstants.WS_TRAINING_PATH.startswith("/")
        assert ServerConstants.WS_CONTROL_PATH.startswith("/")
        assert ServerConstants.WS_TRAINING_PATH != ServerConstants.WS_CONTROL_PATH


class TestModuleLevelConvenience:
    """Test module-level convenience imports."""

    def test_convenience_imports(self):
        """Test that convenience imports match class constants."""
        from canopy_constants import DEFAULT_TRAINING_EPOCHS, MAX_TRAINING_EPOCHS, MIN_TRAINING_EPOCHS

        assert MIN_TRAINING_EPOCHS == TrainingConstants.MIN_TRAINING_EPOCHS
        assert MAX_TRAINING_EPOCHS == TrainingConstants.MAX_TRAINING_EPOCHS
        assert DEFAULT_TRAINING_EPOCHS == TrainingConstants.DEFAULT_TRAINING_EPOCHS


def _validate_candidate_pool_triple(s, t, r, p):
    """Local mirror of cascor's post-merge (S, T, R, P) invariant.

    Byte-for-byte the branch order of
    ``juniper-cascor/src/api/lifecycle/manager.py:225`` (``_validate_candidate_
    pool_triple``). canopy cannot import cascor, so the invariant is restated
    here; the clientside ``cn-pool-triple-feedback`` validator mirrors the same
    truth table, and live driving confirmed canopy's message text is identical
    to cascor's rejection string.

    Returns ``None`` when valid, else a human-readable violation.
    """
    if not (1 <= s <= p):
        return f"selected_candidates {s} not in [1, candidate_pool_size={p}]"
    if t < 0 or r < 0:
        return f"top_candidates and random_candidates must be >= 0 (got T={t}, R={r})"
    if t > s or r > s:
        return f"each component must be <= selected_candidates (S={s}, T={t}, R={r})"
    if t == 0 and r == 0:
        return "top_candidates and random_candidates cannot both be 0"
    if t == 0 and r != s:
        return f"with top_candidates=0, random_candidates must equal S={s} (got R={r})"
    if r == 0 and t != s:
        return f"with random_candidates=0, top_candidates must equal S={s} (got T={t})"
    if t > 0 and r > 0 and t + r != s:
        return f"top_candidates+random_candidates must equal S={s} (got {t}+{r}={t + r})"
    return None


class TestShippedCandidateTripleIsValid:
    """F-CANOPY-024 — the shipped (S, T, R) default must satisfy the invariant.

    canopy shipped S=1, T=1, R=1, so T+R=2 != S=1 and the FIRST ``Apply
    Parameters`` on a fresh dashboard always failed validation — client-side
    and again at cascor, with the same sentence. The operator could not correct
    it in place because T and R both ship ``disabled=True`` behind
    ``cn-multi-candidate-checkbox``.
    """

    def test_shipped_defaults_satisfy_the_invariant(self):
        violation = _validate_candidate_pool_triple(
            TrainingConstants.DEFAULT_SELECTED_CANDIDATES,
            TrainingConstants.DEFAULT_TOP_CANDIDATES_COUNT,
            TrainingConstants.DEFAULT_RANDOM_CANDIDATES_COUNT,
            TrainingConstants.DEFAULT_CANDIDATE_POOL_SIZE,
        )
        assert violation is None, f"shipped candidate triple is invalid: {violation}"

    def test_the_pre_fix_triple_is_what_this_guards_against(self):
        """Negative control — the shipped-before values must fail the mirror.

        Without this, a mirror that silently accepted everything would make the
        test above vacuous.
        """
        assert _validate_candidate_pool_triple(1, 1, 1, 100) is not None

    def test_count_floors_match_cascor_field_bounds(self):
        """cascor declares T and R as ``ge=0``.

        (``juniper-cascor/src/api/models/training.py:161-162``, ``:329-330``.)
        A canopy floor of 1 is stricter than the backend and makes the valid
        single-strategy config (T=S, R=0) unreachable from the UI.
        """
        assert TrainingConstants.MIN_TOP_CANDIDATES_COUNT == 0
        assert TrainingConstants.MIN_RANDOM_CANDIDATES_COUNT == 0

    def test_defaults_are_within_their_own_bounds(self):
        assert TrainingConstants.MIN_TOP_CANDIDATES_COUNT <= TrainingConstants.DEFAULT_TOP_CANDIDATES_COUNT <= TrainingConstants.MAX_TOP_CANDIDATES_COUNT
        assert TrainingConstants.MIN_RANDOM_CANDIDATES_COUNT <= TrainingConstants.DEFAULT_RANDOM_CANDIDATES_COUNT <= TrainingConstants.MAX_RANDOM_CANDIDATES_COUNT
        assert TrainingConstants.MIN_SELECTED_CANDIDATES <= TrainingConstants.DEFAULT_SELECTED_CANDIDATES <= TrainingConstants.MAX_SELECTED_CANDIDATES
