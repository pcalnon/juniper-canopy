"""N5 (I-4) — ``CascorPatchBounds`` clamp + PATCH-bounds mirror.

Behavior 1 of the apply-params UX unit: the Apply Parameters form seeds itself
from the backend and submits the full form to ``PATCH /v1/training/params``. A
backend-echoed out-of-range value would wholesale-422 the form (the evening-502
class the plan diagnosed). ``CascorPatchBounds`` mirrors cascor's
``TrainingParamUpdateRequest`` bounds and clamps/flags such values before apply.

These tests pin (a) the clamp behavior and (b) the mirrored bound values so a
future edit to either the map or the clamp is deliberate — there is no cross-repo
import to catch drift automatically.
"""

from __future__ import annotations

import pytest

from canopy_constants import CascorPatchBounds, TrainingConstants


@pytest.mark.unit
class TestClampBehavior:
    def test_upper_bound_clamped_down_with_violation(self):
        clamped, violations = CascorPatchBounds.clamp_params({"nn_learning_rate": 50.0})
        assert clamped["nn_learning_rate"] == 10.0  # cascor le=10.0
        assert len(violations) == 1
        v = violations[0]
        assert v["key"] == "nn_learning_rate"
        assert v["requested"] == 50.0
        assert v["clamped"] == 10.0
        assert "10.0" in v["bound"]

    def test_epochs_max_1e11_no_upper_bound_post_c2b(self):
        """The historical 1e11 root cause: epochs_max is now ge=1 with NO upper
        bound (C2b made it derived/read-only), so a large value is NOT clamped —
        the C2a skipped(not-updatable) toast handles it, not the clamp."""
        clamped, violations = CascorPatchBounds.clamp_params({"nn_max_total_epochs": 100_000_000_000})
        assert clamped["nn_max_total_epochs"] == 100_000_000_000
        assert violations == []
        assert CascorPatchBounds.BOUNDS["nn_max_total_epochs"].get("deprecated") is True

    def test_integer_bound_keeps_int_type(self):
        clamped, violations = CascorPatchBounds.clamp_params({"nn_max_hidden_units": 999_999, "cn_pool_size": 400})
        assert clamped["nn_max_hidden_units"] == 10_000 and isinstance(clamped["nn_max_hidden_units"], int)
        assert clamped["cn_pool_size"] == 256 and isinstance(clamped["cn_pool_size"], int)
        assert {v["key"] for v in violations} == {"nn_max_hidden_units", "cn_pool_size"}

    def test_lower_bound_ge_clamped_up(self):
        clamped, violations = CascorPatchBounds.clamp_params({"nn_patience": 0})
        assert clamped["nn_patience"] == 1  # cascor ge=1
        assert violations and violations[0]["clamped"] == 1

    def test_gt_zero_float_clamped_to_positive_floor(self):
        """A ``gt=0`` field seeded 0 clamps to canopy's strictly-positive MIN
        floor (which satisfies cascor's ``gt=0``), never to 0 (which would 422)."""
        clamped, violations = CascorPatchBounds.clamp_params({"nn_learning_rate": 0.0})
        assert clamped["nn_learning_rate"] == TrainingConstants.MIN_LEARNING_RATE
        assert clamped["nn_learning_rate"] > 0
        assert violations

    def test_in_range_values_are_no_ops(self):
        payload = {"nn_learning_rate": 0.05, "nn_max_hidden_units": 64, "cn_pool_size": 8, "nn_patience": 50}
        clamped, violations = CascorPatchBounds.clamp_params(payload)
        assert violations == []
        assert clamped == payload

    def test_none_bool_and_nonnumeric_left_untouched(self):
        payload = {"nn_learning_rate": None, "nn_max_hidden_units": True, "nn_growth_trigger": "convergence"}
        clamped, violations = CascorPatchBounds.clamp_params(payload)
        assert violations == []
        assert clamped == payload

    def test_unbounded_and_canopy_local_keys_pass_through(self):
        payload = {"nn_spiral_rotations": 3.0, "nn_dataset_elements": 200, "cn_candidate_selection": "top"}
        clamped, violations = CascorPatchBounds.clamp_params(payload)
        assert violations == []
        assert clamped == payload

    def test_clamp_returns_shallow_copy_not_mutating_input(self):
        payload = {"nn_learning_rate": 99.0}
        clamped, _ = CascorPatchBounds.clamp_params(payload)
        assert payload["nn_learning_rate"] == 99.0  # original untouched
        assert clamped["nn_learning_rate"] == 10.0


@pytest.mark.unit
class TestBoundsMirrorPin:
    """Pin the mirrored bounds so any edit is deliberate and stays aligned with
    cascor ``src/api/models/training.py`` ``TrainingParamUpdateRequest``."""

    EXPECTED = {
        "nn_learning_rate": (TrainingConstants.MIN_LEARNING_RATE, 10.0),  # gt=0, le=10.0
        "nn_max_hidden_units": (1, 10_000),  # ge=1, le=10_000
        "nn_max_total_epochs": (1, None),  # ge=1 (deprecated)
        "nn_max_iterations": (1, None),  # ge=1
        "nn_output_epochs": (1, 1_000_000),  # ge=1, le=1_000_000
        "nn_growth_convergence_threshold": (TrainingConstants.MIN_CONVERGENCE_THRESHOLD, None),  # gt=0
        "nn_patience": (1, 100_000),  # ge=1, le=100_000
        "cn_pool_size": (1, 256),  # ge=1, le=256
        "cn_correlation_threshold": (TrainingConstants.MIN_CANDIDATE_CORRELATION_THRESHOLD, 1.0),  # gt=0, le=1.0
        "cn_candidate_learning_rate": (TrainingConstants.MIN_LEARNING_RATE, 10.0),  # gt=0, le=10.0
        "cn_selected_candidates": (1, 256),  # ge=1, le=256
        "cn_training_iterations": (1, 1_000_000),  # ge=1, le=1_000_000
        "cn_training_convergence_threshold": (TrainingConstants.MIN_CANDIDATE_CONVERGENCE_THRESHOLD, None),  # gt=0
        "cn_patience": (1, 100_000),  # ge=1, le=100_000
        "cn_top_candidates": (0, 256),  # ge=0, le=256
        "cn_random_candidates": (0, 256),  # ge=0, le=256
    }

    def test_bounds_map_matches_expected(self):
        assert set(CascorPatchBounds.BOUNDS) == set(self.EXPECTED)
        for key, (lo, hi) in self.EXPECTED.items():
            bound = CascorPatchBounds.BOUNDS[key]
            assert bound["lo"] == lo, key
            assert bound["hi"] == hi, key

    def test_every_bounded_key_is_a_real_canopy_to_cascor_param(self):
        """Guard against a bound keyed on a non-existent form field: every
        bounded key must be a canopy key the adapter maps to cascor."""
        pytest.importorskip("juniper_cascor_client", reason="adapter requires the [juniper-cascor] extra")
        from backend.cascor_service_adapter import CascorServiceAdapter

        mapped = set(CascorServiceAdapter._CANOPY_TO_CASCOR_PARAM_MAP)
        assert set(CascorPatchBounds.BOUNDS).issubset(mapped)
