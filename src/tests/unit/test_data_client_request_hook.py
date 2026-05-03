"""Regression tests for the data-client request-hook adoption.

METRICS-MON R4.3 / seed-13.

Canopy supplies a Prometheus-emitting closure to
:class:`juniper_data_client.JuniperDataClient`'s ``on_request``
instrumentation kwarg. The closure bumps:

* ``juniper_canopy_data_client_requests_total{method, status_class,
  error_type}`` — once per call.
* ``juniper_canopy_data_client_request_duration_ms{method,
  status_class}`` — once per call (timing).

These tests pin the closure shape (matches
:data:`juniper_data_client.RequestHook`), the status-class bucketing
(closed-set labels keep cardinality bounded), and the error-type
mapping ("none" on success / class name on failure).
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
    ``collect()`` API (vs. ``.labels(...)._value.get()`` which returns
    a freshly-zeroed child counter when the labelset hasn't been
    exercised yet — a pytest-fixture-reset interaction we're robust to
    by going through ``collect()``).
    """
    samples = list(metric.collect())[0].samples
    for s in samples:
        # Counter exposition emits ``_total`` and ``_created`` per
        # labelset; we want the cumulative ``_total``.
        if not s.name.endswith("_total"):
            continue
        if all(s.labels.get(k) == v for k, v in labels.items()):
            return s.value
    return 0.0


def _histogram_count(metric, **labels) -> float:
    """Read a labelset's histogram observation count via ``collect()``."""
    samples = list(metric.collect())[0].samples
    for s in samples:
        if not s.name.endswith("_count"):
            continue
        if all(s.labels.get(k) == v for k, v in labels.items()):
            return s.value
    return 0.0


@pytest.fixture(autouse=True)
def _reset_canopy_metrics():
    """Null the lazy-cached metrics dict AND scrub the global Prometheus
    REGISTRY of the data-client collectors so each test starts with
    fresh, zero-valued counters.

    Without scrubbing REGISTRY, ``_get_or_create`` in
    ``_ensure_canopy_metrics`` adopts the previously-registered
    collector (still holding accumulated counter values from prior
    tests) and the increment-by-one assertions below would see
    inflated baselines. Mirrors the scrub pattern in
    ``juniper_data/tests/integration/test_dataset_post_total_metric.py``.
    """
    obs._canopy_metrics = None
    try:
        from prometheus_client import REGISTRY

        for metric_name in (
            "juniper_canopy_data_client_requests_total",
            "juniper_canopy_data_client_request_duration_ms",
        ):
            collector = REGISTRY._names_to_collectors.get(metric_name)
            if collector is not None:
                try:
                    REGISTRY.unregister(collector)
                except (KeyError, ValueError):
                    pass
    except ImportError:
        pass
    yield
    obs._canopy_metrics = None


class TestClassifyStatus:
    """Status code → closed-set ``status_class`` label."""

    @pytest.mark.parametrize(
        ("status", "expected"),
        [
            (200, "2xx"),
            (201, "2xx"),
            (299, "2xx"),
            (400, "4xx"),
            (404, "4xx"),
            (422, "4xx"),
            (499, "4xx"),
            (500, "5xx"),
            (503, "5xx"),
            (599, "5xx"),
            (None, "transport_error"),
            # 1xx and 3xx are unexpected on this surface; they bucket
            # to ``transport_error`` so anomalies surface.
            (100, "transport_error"),
            (301, "transport_error"),
            (399, "transport_error"),
        ],
    )
    def test_classify_status(self, status, expected):
        assert obs._classify_status(status) == expected


class TestBuildDataClientRequestHook:
    """The Prometheus-emitting closure bumps the right metrics."""

    def test_hook_is_callable_with_request_hook_signature(self):
        """Closure matches ``juniper_data_client.RequestHook``."""
        hook = obs.build_data_client_request_hook()
        # No-op call with the documented signature; raises if the
        # closure shape doesn't accept all 5 positional args.
        hook("GET", "http://localhost:8100/v1/health", 200, 1.5, None)

    def test_success_increments_2xx_none_buckets(self):
        hook = obs.build_data_client_request_hook()
        hook("GET", "http://localhost:8100/v1/health", 200, 5.0, None)
        metrics = obs._ensure_canopy_metrics()
        assert _counter_value(metrics["data_client_requests_total"], method="GET", status_class="2xx", error_type="none") == 1.0
        # Histogram registers exactly one observation under the same
        # (method, status_class) labelset.
        assert _histogram_count(metrics["data_client_request_duration_ms"], method="GET", status_class="2xx") == 1.0

    def test_404_increments_4xx_with_typed_error(self):
        # NOTE: canopy's ``src/tests/conftest.py`` injects stub
        # juniper_data_client.exceptions classes with ``_``-prefixed
        # names (e.g. ``_JuniperDataNotFoundError``) so canopy tests
        # don't need the real data-client installed. We derive the
        # expected ``error_type`` label from the stub's actual
        # ``type(err).__name__`` rather than hardcoding the production
        # class name — this way the test exercises the production
        # ``type(error).__name__`` extraction path against whatever
        # class identity the test environment provides.
        from juniper_data_client.exceptions import JuniperDataNotFoundError

        err = JuniperDataNotFoundError("not found")
        expected_error_type = type(err).__name__
        hook = obs.build_data_client_request_hook()
        hook("GET", "http://localhost:8100/v1/datasets/missing", 404, 12.0, err)
        metrics = obs._ensure_canopy_metrics()
        assert _counter_value(metrics["data_client_requests_total"], method="GET", status_class="4xx", error_type=expected_error_type) == 1.0

    def test_422_increments_4xx_with_validation_error(self):
        from juniper_data_client.exceptions import JuniperDataValidationError

        err = JuniperDataValidationError("bad params")
        expected_error_type = type(err).__name__
        hook = obs.build_data_client_request_hook()
        hook("POST", "http://localhost:8100/v1/datasets", 422, 8.0, err)
        metrics = obs._ensure_canopy_metrics()
        assert _counter_value(metrics["data_client_requests_total"], method="POST", status_class="4xx", error_type=expected_error_type) == 1.0

    def test_500_increments_5xx_with_client_error(self):
        from juniper_data_client.exceptions import JuniperDataClientError

        err = JuniperDataClientError("server boom")
        expected_error_type = type(err).__name__
        hook = obs.build_data_client_request_hook()
        hook("GET", "http://localhost:8100/v1/health", 500, 25.0, err)
        metrics = obs._ensure_canopy_metrics()
        assert _counter_value(metrics["data_client_requests_total"], method="GET", status_class="5xx", error_type=expected_error_type) == 1.0

    def test_transport_error_increments_with_status_none(self):
        from juniper_data_client.exceptions import JuniperDataConnectionError

        err = JuniperDataConnectionError("refused")
        expected_error_type = type(err).__name__
        hook = obs.build_data_client_request_hook()
        hook("POST", "http://localhost:8100/v1/datasets", None, 3000.0, err)
        metrics = obs._ensure_canopy_metrics()
        assert _counter_value(metrics["data_client_requests_total"], method="POST", status_class="transport_error", error_type=expected_error_type) == 1.0

    def test_repeated_calls_accumulate(self):
        """Multiple calls under the same labels accumulate (vs. reset)."""
        hook = obs.build_data_client_request_hook()
        for _ in range(3):
            hook("GET", "http://localhost:8100/v1/health", 200, 1.0, None)
        metrics = obs._ensure_canopy_metrics()
        assert _counter_value(metrics["data_client_requests_total"], method="GET", status_class="2xx", error_type="none") == 3.0

    def test_url_label_is_not_emitted_to_keep_cardinality_bounded(self):
        """METRICS-MON R1.1 discipline: ``url`` (high-cardinality) is
        NOT a Counter label. Only ``method`` / ``status_class`` /
        ``error_type`` (all closed-set) should appear in the labelset.
        """
        hook = obs.build_data_client_request_hook()
        # Two URLs, identical otherwise — both must collapse to one
        # counter sample (no per-URL bucket explosion).
        hook("GET", "http://localhost:8100/v1/datasets/aaaa", 200, 1.0, None)
        hook("GET", "http://localhost:8100/v1/datasets/bbbb", 200, 1.0, None)
        metrics = obs._ensure_canopy_metrics()
        # Both URLs collapse to a single (GET, 2xx, none) labelset
        # incremented to 2.0 (no per-URL bucket explosion).
        assert _counter_value(metrics["data_client_requests_total"], method="GET", status_class="2xx", error_type="none") == 2.0
        # And there's only one distinct (GET, 2xx, none) labelset.
        samples = list(metrics["data_client_requests_total"].collect())[0].samples
        labelsets = [(s.labels.get("method"), s.labels.get("status_class"), s.labels.get("error_type")) for s in samples if s.name.endswith("_total")]
        target = [ls for ls in labelsets if ls == ("GET", "2xx", "none")]
        assert len(target) == 1, f"expected 1 (GET, 2xx, none) labelset, got {labelsets}"
