"""
Regression tests for CascorServiceAdapter parameter mapping.

These tests intentionally avoid real juniper-cascor-client behavior so they run
in CI environments where the package may be stubbed.
"""

from unittest.mock import MagicMock

import pytest

from backend.cascor_service_adapter import CascorServiceAdapter


@pytest.fixture
def mock_client():
    """Mock client with only the methods needed for mapping tests."""
    client = MagicMock()
    client.update_params.return_value = {"ok": True}
    return client


@pytest.mark.unit
def test_apply_params_maps_candidate_specific_keys(mock_client):
    """cn_* candidate keys should translate to candidate_* cascor names."""
    adapter = CascorServiceAdapter(client=mock_client)

    result = adapter.apply_params(
        cn_patience=25,
        cn_training_convergence_threshold=0.0001,
        cn_training_iterations=300,
    )

    assert result["ok"] is True
    mock_client.update_params.assert_called_once_with(
        {
            "candidate_patience": 25,
            "candidate_convergence_threshold": 0.0001,
            "candidate_epochs": 300,
        }
    )


@pytest.mark.unit
def test_get_canopy_params_maps_candidate_specific_keys(mock_client):
    """candidate_* cascor response keys should map back to canopy cn_* keys."""
    mock_client.get_training_params.return_value = {
        "data": {
            "params": {
                "candidate_patience": 12,
                "candidate_convergence_threshold": 0.0005,
                "candidate_epochs": 150,
            }
        }
    }
    adapter = CascorServiceAdapter(client=mock_client)

    result = adapter.get_canopy_params()

    assert result["cn_patience"] == 12
    assert result["cn_training_convergence_threshold"] == 0.0005
    assert result["cn_training_iterations"] == 150


# ---------------------------------------------------------------------------
# F-CANOPY-022 — candidate_selection VALUE vocabulary
#
# The key rename alone shipped canopy's ``top_tier`` to cascor, whose schema is
# ``Literal["top", "random", "mixed"]`` (juniper-cascor
# ``src/api/models/training.py:159``, ``:327``). Applying with "Add Top Tier
# Candidates" selected returned a pydantic ``literal_error`` that the dashboard
# surfaced as HTTP 502, so that option could never be applied — while its
# sibling ``random`` worked, because that value happened to match on both sides.
# ---------------------------------------------------------------------------


def _sent_payload(mock_client):
    """The dict actually PATCHed to cascor."""
    mock_client.update_params.assert_called_once()
    return mock_client.update_params.call_args[0][0]


@pytest.mark.unit
def test_legacy_top_tier_is_translated_to_cascor_literal(mock_client):
    """A persisted/legacy ``top_tier`` must reach cascor as ``top``."""
    adapter = CascorServiceAdapter(client=mock_client)

    result = adapter.apply_params(cn_candidate_selection="top_tier")

    assert result["ok"] is True
    assert _sent_payload(mock_client)["candidate_selection"] == "top"


@pytest.mark.unit
def test_shipped_top_value_passes_through(mock_client):
    """The post-fix radio value is already a cascor literal."""
    adapter = CascorServiceAdapter(client=mock_client)

    adapter.apply_params(cn_candidate_selection="top")

    assert _sent_payload(mock_client)["candidate_selection"] == "top"


@pytest.mark.unit
def test_random_is_untouched(mock_client):
    """``random`` matched on both sides before the fix and must still."""
    adapter = CascorServiceAdapter(client=mock_client)

    adapter.apply_params(cn_candidate_selection="random")

    assert _sent_payload(mock_client)["candidate_selection"] == "random"


@pytest.mark.unit
def test_unknown_value_is_forwarded_verbatim(mock_client):
    """Only the known legacy token is rewritten — cascor stays authoritative.

    Silently coercing an unrecognised value would hide a real client error
    behind a guess; forwarding it lets cascor's schema reject it by name.
    """
    adapter = CascorServiceAdapter(client=mock_client)

    adapter.apply_params(cn_candidate_selection="not_a_strategy")

    assert _sent_payload(mock_client)["candidate_selection"] == "not_a_strategy"


@pytest.mark.unit
def test_value_map_targets_only_cascor_literals():
    """Every translation output must be something cascor actually accepts."""
    cascor_literals = {"top", "random", "mixed"}
    for cascor_key, value_map in CascorServiceAdapter._CANOPY_TO_CASCOR_VALUE_MAP.items():
        if cascor_key == "candidate_selection":
            assert set(value_map.values()) <= cascor_literals, f"{cascor_key} maps to non-literals: {sorted(set(value_map.values()) - cascor_literals)}"
