"""
Regression tests for CascorServiceAdapter parameter mappings.

These tests protect candidate-training parameter round-trips:
- canopy `cn_*` keys forwarded via apply_params()
- cascor `candidate_*` keys mapped back via get_canopy_params()
"""

from unittest.mock import MagicMock

import pytest

from backend.cascor_service_adapter import CascorServiceAdapter


@pytest.mark.unit
class TestCandidateParameterMappingRegression:
    """Guard critical candidate parameter mapping behavior."""

    def _make_adapter(self) -> CascorServiceAdapter:
        adapter = CascorServiceAdapter.__new__(CascorServiceAdapter)
        adapter._client = MagicMock()
        return adapter

    def test_forward_map_contains_candidate_parameter_keys(self):
        """Canopy candidate keys must be present in forward map."""
        assert CascorServiceAdapter._CANOPY_TO_CASCOR_PARAM_MAP["cn_patience"] == "candidate_patience"
        assert (
            CascorServiceAdapter._CANOPY_TO_CASCOR_PARAM_MAP["cn_training_convergence_threshold"]
            == "candidate_convergence_threshold"
        )

    def test_reverse_map_contains_candidate_parameter_keys(self):
        """Cascor candidate keys must map back to canopy keys."""
        assert CascorServiceAdapter._CASCOR_TO_CANOPY_PARAM_MAP["candidate_patience"] == "cn_patience"
        assert (
            CascorServiceAdapter._CASCOR_TO_CANOPY_PARAM_MAP["candidate_convergence_threshold"]
            == "cn_training_convergence_threshold"
        )

    def test_apply_params_forwards_candidate_parameters(self):
        """apply_params() should forward candidate controls to cascor names."""
        adapter = self._make_adapter()
        adapter._client.update_params.return_value = {"ok": True}

        result = adapter.apply_params(cn_patience=33, cn_training_convergence_threshold=0.0005)

        adapter._client.update_params.assert_called_once_with(
            {
                "candidate_patience": 33,
                "candidate_convergence_threshold": 0.0005,
            }
        )
        assert result["ok"] is True

    def test_get_canopy_params_maps_candidate_parameters_from_nested_payload(self):
        """get_canopy_params() should return canopy candidate keys from nested payload."""
        adapter = self._make_adapter()
        adapter._client.get_training_params.return_value = {
            "data": {
                "params": {
                    "candidate_patience": 25,
                    "candidate_convergence_threshold": 0.0012,
                }
            }
        }

        result = adapter.get_canopy_params()

        assert result["cn_patience"] == 25
        assert result["cn_training_convergence_threshold"] == 0.0012
