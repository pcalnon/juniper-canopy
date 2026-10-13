"""§1.5 C3 (Issue #1) — adapter detects post-PATCH config divergence.

After ``CascorServiceAdapter.apply_params`` PATCHes the cascor service it
GETs ``/v1/training/params`` and compares applied vs requested values.
Mismatches surface as ``{ok: False, error: "verification_failed",
mismatches: {...}}``. Float-tolerant params allow ~1e-6 relative drift to
absorb JSON / pydantic / numpy precision loss.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

pytest.importorskip("juniper_cascor_client.testing", reason="juniper-cascor-client[testing] not installed")

from juniper_cascor_client.testing import FakeCascorClient  # noqa: E402

from backend.cascor_service_adapter import CascorServiceAdapter  # noqa: E402


@pytest.fixture
def adapter():
    client = FakeCascorClient(scenario="two_spiral_training")
    yield CascorServiceAdapter(client=client)
    client.close()


# ---------------------------------------------------------------------------
# Successful roundtrip — no mismatches
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_roundtrip_returns_ok_when_applied_matches_requested(adapter):
    """When cascor echoes the values we PATCHed, no mismatches surface."""
    requested = {"max_hidden_units": 64, "max_iterations": 5}
    with patch.object(adapter._client, "update_params", return_value={"data": requested}), patch.object(adapter._client, "get_training_params", return_value={"data": requested}):
        result = adapter.apply_params(nn_max_hidden_units=64, nn_max_iterations=5)
    assert result["ok"] is True
    assert "mismatches" not in result, result


@pytest.mark.integration
def test_roundtrip_tolerates_float_precision_loss(adapter):
    """learning_rate is in _FLOAT_TOLERANT_PARAMS — sub-1e-6 drift is fine."""
    requested = {"learning_rate": 0.05}
    applied = {"learning_rate": 0.05 + 1e-9}  # well within rel_tol=1e-6
    with patch.object(adapter._client, "update_params", return_value={"data": requested}), patch.object(adapter._client, "get_training_params", return_value={"data": applied}):
        result = adapter.apply_params(nn_learning_rate=0.05)
    assert result["ok"] is True, result


# ---------------------------------------------------------------------------
# Detected divergence
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_roundtrip_detects_int_mismatch(adapter):
    requested = {"max_hidden_units": 64}
    applied = {"max_hidden_units": 32}  # cascor silently kept the old value
    with patch.object(adapter._client, "update_params", return_value={"data": requested}), patch.object(adapter._client, "get_training_params", return_value={"data": applied}):
        result = adapter.apply_params(nn_max_hidden_units=64)
    assert result["ok"] is False
    assert result["error"] == "verification_failed"
    assert result["mismatches"] == {"max_hidden_units": {"requested": 64, "applied": 32}}, result


@pytest.mark.integration
def test_roundtrip_detects_float_mismatch_outside_tolerance(adapter):
    """Drift larger than rel_tol=1e-6 surfaces as a real mismatch."""
    requested = {"learning_rate": 0.05}
    applied = {"learning_rate": 0.07}  # ~40% off — well outside tolerance
    with patch.object(adapter._client, "update_params", return_value={"data": requested}), patch.object(adapter._client, "get_training_params", return_value={"data": applied}):
        result = adapter.apply_params(nn_learning_rate=0.05)
    assert result["ok"] is False
    assert result["error"] == "verification_failed"
    assert "learning_rate" in result["mismatches"]


# ---------------------------------------------------------------------------
# Defensive: verify call failures must not invalidate a successful PATCH
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_failed_verify_call_does_not_invalidate_successful_patch(adapter):
    """If GET /v1/training/params raises, we keep the PATCH success — a
    flaky GET shouldn't be promoted to a fake mismatch."""
    from juniper_cascor_client import JuniperCascorClientError

    with patch.object(adapter._client, "update_params", return_value={"data": {"max_hidden_units": 64}}), patch.object(adapter._client, "get_training_params", side_effect=JuniperCascorClientError("network blip")):
        result = adapter.apply_params(nn_max_hidden_units=64)
    assert result["ok"] is True, result
    assert "mismatches" not in result


@pytest.mark.integration
def test_unexpected_verify_response_shape_does_not_invalidate_patch(adapter):
    """If GET returns something we can't parse (wrong type, missing data),
    treat it as ``no mismatches`` rather than fabricating one."""
    with patch.object(adapter._client, "update_params", return_value={"data": {"max_hidden_units": 64}}), patch.object(adapter._client, "get_training_params", return_value="not a dict"):
        result = adapter.apply_params(nn_max_hidden_units=64)
    assert result["ok"] is True, result


# ---------------------------------------------------------------------------
# F-CANOPY-023 — a key the live network DECLINED is not a verification failure
#
# ``epochs_max`` is derived read-only in cascor (C2b / Q1 outcome (c)): it is
# accepted at the request boundary so a full-form canopy apply keeps working,
# then reported as ``skipped(not-updatable)`` instead of being stored. Its
# post-PATCH value is therefore EXPECTED to differ from what was sent.
#
# Before the fix the verify ran BEFORE ``_extract_cascor_partition``, so that
# expected divergence failed the WHOLE apply — the operator was told the apply
# failed while every edit they made had actually landed.
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_cascor_declined_key_does_not_fail_the_apply(adapter):
    """cascor reports epochs_max skipped(not-updatable) -> apply still OK."""
    c2a_envelope = {
        "data": {
            "applied": ["patience"],
            "skipped": [{"key": "epochs_max", "reason": "not-updatable"}],
        }
    }
    # cascor derived its own epochs_max; the sidebar sent a stale 115000.
    applied = {"epochs_max": 140795, "patience": 88}
    with patch.object(adapter._client, "update_params", return_value=c2a_envelope), patch.object(adapter._client, "get_training_params", return_value={"data": applied}):
        result = adapter.apply_params(nn_max_total_epochs=115000, nn_patience=88)
    assert result["ok"] is True, result
    assert "mismatches" not in result
    # the decline is still surfaced to the operator, in the right channel
    assert {"key": "nn_max_total_epochs", "reason": "not-updatable"} in result["skipped_detail"]


@pytest.mark.integration
def test_derived_readonly_key_excluded_without_a_partition(adapter):
    """Static backstop: a backend that reports NO C2a partition still passes.

    The data-driven rule has nothing to read here, so only
    ``_DERIVED_READONLY_CASCOR_PARAMS`` prevents the false failure.
    """
    applied = {"epochs_max": 140795, "patience": 88}
    with patch.object(adapter._client, "update_params", return_value={"data": {}}), patch.object(adapter._client, "get_training_params", return_value={"data": applied}):
        result = adapter.apply_params(nn_max_total_epochs=115000, nn_patience=88)
    assert result["ok"] is True, result


@pytest.mark.integration
def test_a_genuine_divergence_still_fails(adapter):
    """The exclusion must not blunt the check it was carved out of.

    ``max_hidden_units`` is neither declined nor derived, so a real divergence
    on it must still surface — even alongside a declined ``epochs_max``.
    """
    c2a_envelope = {"data": {"skipped": [{"key": "epochs_max", "reason": "not-updatable"}]}}
    applied = {"epochs_max": 140795, "max_hidden_units": 32}
    with patch.object(adapter._client, "update_params", return_value=c2a_envelope), patch.object(adapter._client, "get_training_params", return_value={"data": applied}):
        result = adapter.apply_params(nn_max_total_epochs=115000, nn_max_hidden_units=64)
    assert result["ok"] is False
    assert result["error"] == "verification_failed"
    assert "max_hidden_units" in result["mismatches"]
    assert "epochs_max" not in result["mismatches"], "declined key leaked into mismatches"


@pytest.mark.integration
def test_any_declined_key_is_excluded_not_just_epochs_max(adapter):
    """The primary rule is data-driven, so a future not-updatable key works
    with no code change."""
    c2a_envelope = {"data": {"skipped": [{"key": "max_iterations", "reason": "not-updatable"}]}}
    applied = {"max_iterations": 7}
    with patch.object(adapter._client, "update_params", return_value=c2a_envelope), patch.object(adapter._client, "get_training_params", return_value={"data": applied}):
        result = adapter.apply_params(nn_max_iterations=5)
    assert result["ok"] is True, result


@pytest.mark.integration
def test_verify_helper_keeps_its_single_argument_contract(adapter):
    """``skipped_detail`` is optional — existing callers/tests are unaffected."""
    with patch.object(adapter._client, "get_training_params", return_value={"data": {"max_hidden_units": 32}}):
        assert adapter._verify_apply_roundtrip({"max_hidden_units": 64}) == {"max_hidden_units": {"requested": 64, "applied": 32}}
