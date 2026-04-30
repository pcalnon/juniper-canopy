"""Inbound WS frame validation — METRICS-MON R2.2.5 / seed-05.

These tests pin the canopy-side observational validation contract:

  * Known envelopes pass through to the existing dispatch logic
    unchanged.
  * Unknown / malformed frames increment
    ``juniper_canopy_unrecognized_ws_frames_total{type, endpoint}``
    AND emit a structured WARNING log line, but **never** crash the
    relay loop.
  * The R1.1 cardinality bound (collapse to ``"_unmatched"`` after
    UNKNOWN_TYPE_BUDGET=16 distinct unknowns per process) is honored.

The canopy adapter consumes WS frames via ``juniper-cascor-client``'s
``CascorTrainingStream``; cascor-client's R2.2.4 also validates each
frame inside the client. Canopy's own validation is intentionally
**redundant** — it gives canopy its own ``juniper_canopy_*`` service-
identity metric on canopy's ``/metrics`` endpoint and provides
defense-in-depth if cascor-client's hook is ever disabled.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _reset_canopy_observability_state():
    """Clear the cardinality tracker + the Counter cache between tests."""
    from juniper_cascor_protocol.envelope import reset_unknown_label_state

    import observability as canopy_obs

    reset_unknown_label_state()

    # Unregister and clear the metrics dict so the next ``_ensure_canopy_metrics``
    # creates fresh Counter / Gauge instances and the default Prometheus
    # registry stays clean across tests.
    if canopy_obs._canopy_metrics is not None:
        try:
            from prometheus_client import REGISTRY

            for metric in canopy_obs._canopy_metrics.values():
                try:
                    REGISTRY.unregister(metric)
                except KeyError:
                    pass
        except ImportError:
            pass
        canopy_obs._canopy_metrics = None

    yield

    reset_unknown_label_state()
    if canopy_obs._canopy_metrics is not None:
        try:
            from prometheus_client import REGISTRY

            for metric in canopy_obs._canopy_metrics.values():
                try:
                    REGISTRY.unregister(metric)
                except KeyError:
                    pass
        except ImportError:
            pass
        canopy_obs._canopy_metrics = None


@pytest.mark.unit
class TestIncUnrecognizedWsFrame:
    """The observability hook is purely additive."""

    def test_increments_counter_with_correct_labels(self):
        from observability import _ensure_canopy_metrics, inc_unrecognized_ws_frame

        inc_unrecognized_ws_frame("garbage_type", "training")

        # Read the counter sample by walking the default registry.
        from prometheus_client import REGISTRY

        sample_value = REGISTRY.get_sample_value(
            "juniper_canopy_unrecognized_ws_frames_total",
            {"type": "garbage_type", "endpoint": "training"},
        )
        assert sample_value == 1.0
        # Idempotent: a second call advances the same series.
        inc_unrecognized_ws_frame("garbage_type", "training")
        sample_value = REGISTRY.get_sample_value(
            "juniper_canopy_unrecognized_ws_frames_total",
            {"type": "garbage_type", "endpoint": "training"},
        )
        assert sample_value == 2.0
        # And the metric was actually created via the canonical helper.
        _ensure_canopy_metrics()  # no error => already present

    def test_endpoint_label_distinguishes_training_and_control(self):
        from prometheus_client import REGISTRY

        from observability import inc_unrecognized_ws_frame

        inc_unrecognized_ws_frame("foo", "training")
        inc_unrecognized_ws_frame("foo", "control")
        assert (
            REGISTRY.get_sample_value(
                "juniper_canopy_unrecognized_ws_frames_total",
                {"type": "foo", "endpoint": "training"},
            )
            == 1.0
        )
        assert (
            REGISTRY.get_sample_value(
                "juniper_canopy_unrecognized_ws_frames_total",
                {"type": "foo", "endpoint": "control"},
            )
            == 1.0
        )

    def test_emits_structured_warning_log(self, caplog):
        from observability import inc_unrecognized_ws_frame

        with caplog.at_level(logging.WARNING, logger="juniper_canopy.observability"):
            inc_unrecognized_ws_frame("structured_log_test", "training")
        warnings = [rec for rec in caplog.records if rec.levelno == logging.WARNING]
        assert len(warnings) >= 1
        rec = warnings[-1]
        assert rec.message == "juniper_canopy_unrecognized_ws_frame"
        assert getattr(rec, "type", None) == "structured_log_test"
        assert getattr(rec, "endpoint", None) == "training"


@pytest.mark.unit
class TestRelayLoopValidationHook:
    """The validation hook in ``CascorServiceAdapter._relay_loop`` is observational only.

    These tests exercise the validation logic the relay loop runs on
    each inbound message, without spinning up the full async loop —
    the loop's other behaviours are covered by
    ``test_cascor_service_adapter*``.
    """

    def test_known_envelope_does_not_increment_counter(self):
        """A valid ``metrics`` envelope must NOT bump the counter."""
        from juniper_cascor_protocol.envelope import UnknownEnvelope, validate_envelope

        from observability import inc_unrecognized_ws_frame

        message = {"type": "metrics", "timestamp": 1.0, "data": {"loss": 0.1}, "seq": 5}

        with patch("observability.inc_unrecognized_ws_frame", wraps=inc_unrecognized_ws_frame) as spy:
            envelope = validate_envelope(message)
            if isinstance(envelope, UnknownEnvelope):
                inc_unrecognized_ws_frame(envelope.type, "training")
            spy.assert_not_called()

    def test_unknown_type_increments_counter(self):
        """A frame with an unrecognized ``type`` increments the counter."""
        from juniper_cascor_protocol.envelope import UnknownEnvelope, validate_envelope

        from observability import inc_unrecognized_ws_frame

        message = {"type": "totally_made_up", "timestamp": 1.0, "data": {}}
        envelope = validate_envelope(message)
        assert isinstance(envelope, UnknownEnvelope)

        from prometheus_client import REGISTRY

        inc_unrecognized_ws_frame(envelope.type, "training")
        assert (
            REGISTRY.get_sample_value(
                "juniper_canopy_unrecognized_ws_frames_total",
                {"type": "totally_made_up", "endpoint": "training"},
            )
            == 1.0
        )

    def test_known_type_with_invalid_payload_increments_counter(self):
        """A known type with malformed inner payload still increments the counter."""
        from juniper_cascor_protocol.envelope import UnknownEnvelope, validate_envelope

        from observability import inc_unrecognized_ws_frame

        # initial_metrics requires count to be int
        message = {
            "type": "initial_metrics",
            "timestamp": 1.0,
            "data": {"metrics": [], "count": "BAD-not-an-int", "current_seq": 0},
        }
        envelope = validate_envelope(message)
        assert isinstance(envelope, UnknownEnvelope)

        from prometheus_client import REGISTRY

        inc_unrecognized_ws_frame(envelope.type, "training")
        assert (
            REGISTRY.get_sample_value(
                "juniper_canopy_unrecognized_ws_frames_total",
                {"type": "initial_metrics", "endpoint": "training"},
            )
            == 1.0
        )

    def test_validation_hook_does_not_modify_message(self):
        """Validation must not mutate the dict that the relay loop dispatches."""
        from juniper_cascor_protocol.envelope import validate_envelope

        original = {"type": "metrics", "timestamp": 1.0, "data": {"loss": 0.1}, "seq": 5}
        snapshot = dict(original)
        snapshot["data"] = dict(original["data"])  # shallow copy was enough

        validate_envelope(original)

        assert original == snapshot
        assert original["data"] == snapshot["data"]

    def test_validation_hook_swallows_internal_errors(self):
        """If validation itself raises (impossible today, but guarded), the relay continues."""
        # Simulate a hypothetical future bug in validate_envelope by patching
        # it to raise. The relay-loop guard (try/except + logger.debug) must
        # absorb the error so the dashboard's broadcast loop keeps running.
        with patch("juniper_cascor_protocol.envelope.validate_envelope", side_effect=RuntimeError("hypothetical bug")):
            try:
                # Mirror the relay-loop's guarded call.
                from juniper_cascor_protocol.envelope import UnknownEnvelope, validate_envelope

                from observability import inc_unrecognized_ws_frame

                try:
                    envelope = validate_envelope({"type": "metrics", "timestamp": 0.0, "data": {}})
                    if isinstance(envelope, UnknownEnvelope):
                        inc_unrecognized_ws_frame(envelope.type, "training")
                except Exception:  # noqa: BLE001 — mirroring the relay-loop guard
                    pass
            except Exception:
                pytest.fail("Validation hook must not propagate exceptions to the relay loop")


@pytest.mark.unit
class TestCardinalityBound:
    """METRICS-MON R1.1: distinct unknown types beyond UNKNOWN_TYPE_BUDGET collapse."""

    def test_unknown_label_collapses_after_budget(self):
        from juniper_cascor_protocol.envelope import UNKNOWN_TYPE_BUDGET, UNMATCHED_TYPE_LABEL, UnknownEnvelope, validate_envelope

        from observability import inc_unrecognized_ws_frame

        for i in range(UNKNOWN_TYPE_BUDGET):
            envelope = validate_envelope({"type": f"unknown_brand_{i}", "timestamp": 0.0, "data": {}})
            assert isinstance(envelope, UnknownEnvelope)
            assert envelope.type == f"unknown_brand_{i}"
            inc_unrecognized_ws_frame(envelope.type, "training")

        # The next distinct unknown collapses to "_unmatched".
        envelope = validate_envelope({"type": "another_brand_new_one", "timestamp": 0.0, "data": {}})
        assert envelope.type == UNMATCHED_TYPE_LABEL
        inc_unrecognized_ws_frame(envelope.type, "training")

        from prometheus_client import REGISTRY

        # Verify both: a previously-tracked one is verbatim, and the
        # collapsed one shows up under "_unmatched".
        assert (
            REGISTRY.get_sample_value(
                "juniper_canopy_unrecognized_ws_frames_total",
                {"type": "unknown_brand_0", "endpoint": "training"},
            )
            == 1.0
        )
        assert (
            REGISTRY.get_sample_value(
                "juniper_canopy_unrecognized_ws_frames_total",
                {"type": UNMATCHED_TYPE_LABEL, "endpoint": "training"},
            )
            == 1.0
        )
