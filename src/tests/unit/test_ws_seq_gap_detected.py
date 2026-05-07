"""Regression tests for the canopy-side WS sequence-gap counter.

OBS-WIRE-02 / Q1 (option a): replaces the deleted cascor-side
``cascor_ws_seq_gap_detected_total`` counter with a canopy-side
client-truth counter
``juniper_canopy_ws_seq_gap_detected_total{service, channel}``.

These tests pin:

* The metric is registered on the canonical Prometheus name with the
  expected closed-set labels.
* The helper :func:`observability.inc_ws_seq_gap_detected` validates
  ``channel`` against :data:`observability._SEQ_GAP_CHANNELS` and raises
  :class:`ValueError` on an unknown value (instrumentation-drift early-
  warning, mirrors cascor's ``inc_training_session_completed`` pattern).
* The ``service`` label is hardcoded to ``"juniper-cascor"`` (only
  upstream today; reserves room for future multi-cascor topologies).
* A structured WARNING log line is emitted alongside the metric
  increment so operators see gaps on stacks without Prometheus
  scraping (R4.7 / R2.2 pattern).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

src_dir = Path(__file__).parents[2]
sys.path.insert(0, str(src_dir))

import observability as obs  # noqa: E402


def _counter_value(metric, **labels) -> float:
    """Read a labelset's accumulated counter value via the public
    ``collect()`` API (see ``test_data_client_request_hook.py`` for
    rationale).
    """
    samples = list(metric.collect())[0].samples
    for s in samples:
        if not s.name.endswith("_total"):
            continue
        if all(s.labels.get(k) == v for k, v in labels.items()):
            return s.value
    return 0.0


@pytest.fixture(autouse=True)
def _reset_canopy_metrics():
    """Null the lazy-cached metrics dict AND scrub the global Prometheus
    REGISTRY of the seq-gap collector so each test starts fresh.
    """
    obs._canopy_metrics = None
    try:
        from prometheus_client import REGISTRY

        collector = REGISTRY._names_to_collectors.get("juniper_canopy_ws_seq_gap_detected_total")
        if collector is not None:
            try:
                REGISTRY.unregister(collector)
            except (KeyError, ValueError):
                pass
    except ImportError:
        pass
    yield
    obs._canopy_metrics = None


class TestSeqGapMetricRegistration:
    """The new Q1 metric is registered on the canonical name + labels."""

    def test_metric_present_with_expected_labels(self):
        metrics = obs._ensure_canopy_metrics()
        assert "ws_seq_gap_detected_total" in metrics
        # The collected sample's labelnames are the closed-set
        # cross-service correlation labels documented in
        # ``A9_AND_3_2_STATE_ANALYSIS_2026-05-03.md``.
        descriptor = metrics["ws_seq_gap_detected_total"]
        # _labelnames is a tuple set at construction time.
        assert tuple(descriptor._labelnames) == ("service", "channel")

    def test_metric_full_name_is_canonical(self):
        metrics = obs._ensure_canopy_metrics()
        descriptor = metrics["ws_seq_gap_detected_total"]
        # The Counter object's ``_name`` attribute is the metric name
        # (without the implicit ``_total`` suffix on samples).
        assert descriptor._name == "juniper_canopy_ws_seq_gap_detected"


class TestIncWsSeqGapDetected:
    """Helper validates the channel and emits both metric + log."""

    def test_training_channel_increments_with_correct_labels(self):
        obs.inc_ws_seq_gap_detected("training")
        metrics = obs._ensure_canopy_metrics()
        assert _counter_value(metrics["ws_seq_gap_detected_total"], service="juniper-cascor", channel="training") == 1.0

    def test_control_channel_increments_with_correct_labels(self):
        obs.inc_ws_seq_gap_detected("control")
        metrics = obs._ensure_canopy_metrics()
        assert _counter_value(metrics["ws_seq_gap_detected_total"], service="juniper-cascor", channel="control") == 1.0

    def test_repeated_calls_accumulate(self):
        for _ in range(4):
            obs.inc_ws_seq_gap_detected("training")
        metrics = obs._ensure_canopy_metrics()
        assert _counter_value(metrics["ws_seq_gap_detected_total"], service="juniper-cascor", channel="training") == 4.0

    def test_unknown_channel_raises_value_error(self):
        """Closed-set discipline: unknown channel must raise so
        instrumentation drift surfaces early rather than silently
        emitting high-cardinality labels.
        """
        with pytest.raises(ValueError, match="invalid ws seq gap channel"):
            obs.inc_ws_seq_gap_detected("garbage_channel")

    def test_emits_structured_warning_log(self, caplog):
        caplog.clear()
        with caplog.at_level("WARNING", logger="juniper_canopy.observability"):
            obs.inc_ws_seq_gap_detected("training")
        assert any(rec.levelname == "WARNING" and "juniper_canopy_ws_seq_gap_detected" in rec.message for rec in caplog.records), f"expected WARNING line; got: {[(r.levelname, r.message) for r in caplog.records]}"

    def test_channels_frozenset_membership(self):
        """Pin the closed-set membership so adding/removing a channel
        without updating tests is loud rather than silent.
        """
        assert obs._SEQ_GAP_CHANNELS == frozenset({"training", "control"})

    def test_service_label_is_hardcoded_to_juniper_cascor(self):
        """Only one upstream cascor today; static service label
        keeps the labelset cardinality at the minimum.
        """
        assert obs._SEQ_GAP_UPSTREAM_SERVICE == "juniper-cascor"
