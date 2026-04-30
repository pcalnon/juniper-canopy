"""Observability surface for juniper-canopy.

METRICS-MON R2.1.5 / seed-06: the cross-cutting machinery
(:class:`JuniperJsonFormatter`, :class:`RequestIdMiddleware`,
:class:`PrometheusMiddleware`, :data:`UNMATCHED_ENDPOINT_LABEL`,
:data:`request_id_var`, :func:`configure_logging`,
:func:`get_prometheus_app`, :func:`set_build_info`) lives in the shared
:mod:`juniper_observability` package and is re-exported here for
backwards compatibility with existing imports across ``main.py`` and
the test suites.

What stays in this module:

- :func:`configure_sentry` — thin wrapper that delegates to the shared
  implementation but accepts ``traces_sample_rate`` as a positional
  argument (canopy's existing call site in ``main.py`` passes it
  positionally as the fourth argument). The shared signature requires
  it as keyword-only.
- The canopy-specific Prometheus metrics
  (:func:`set_websocket_connections`, :func:`inc_websocket_messages`,
  :func:`set_demo_mode_active`) and the lazy-init helper that backs
  them.

New code should prefer ``from juniper_observability import …`` for the
re-exported symbols to make the dependency on the shared lib explicit.

The migration also closes a security gap: canopy's local
:func:`configure_sentry` did **not** install the SEC-15
``before_send`` hook. The shared implementation does (defense in depth
against future Sentry SDK changes that may re-attach request headers).

See: notes/code-review/METRICS_MONITORING_R2.1_SHARED_OBSERVABILITY_DESIGN_2026-04-28.md
in juniper-ml.
"""

# Cross-service primitives — re-exported from juniper-observability.
from juniper_observability import (  # noqa: F401 — re-exported for backwards compat
    DEFAULT_LOG_FORMAT_PLAIN,
    DEFAULT_SENTRY_TRACES_SAMPLE_RATE,
    LOG_FORMAT_JSON,
    UNMATCHED_ENDPOINT_LABEL,
    JuniperJsonFormatter,
    PrometheusMiddleware,
    RequestIdMiddleware,
    configure_logging,
)
from juniper_observability import configure_sentry as _shared_configure_sentry
from juniper_observability import (  # noqa: F401 — re-exported for backwards compat
    get_prometheus_app,
    request_id_var,
    set_build_info,
)

_SERVICE_NAME_DEFAULT: str = "juniper-canopy"
_NAMESPACE_DEFAULT: str = "juniper_canopy"


def configure_sentry(dsn: str | None, service_name: str, version: str, traces_sample_rate: float = 0.1) -> None:
    """Initialize Sentry via the shared :func:`juniper_observability.configure_sentry`.

    Canopy's historical signature accepts ``traces_sample_rate`` as a
    positional fourth argument (see ``main.py``); the shared signature
    requires it keyword-only. This wrapper preserves the canopy call
    convention while delegating to the shared implementation, which
    additionally installs the SEC-15 ``before_send`` hook (canopy's
    previous local implementation did not).

    Args:
        dsn: Sentry DSN URL. Pass None or empty string to skip initialization.
        service_name: Service name for Sentry environment tag.
        version: Application version string.
        traces_sample_rate: Fraction of transactions to send to Sentry
            (0.0-1.0, default 0.1 — preserves canopy's prior default).
    """
    _shared_configure_sentry(
        dsn,
        service_name,
        version,
        traces_sample_rate=traces_sample_rate,
    )


# ---------------------------------------------------------------------------
# Custom application metrics — lazily initialized to avoid requiring
# prometheus_client at import time (it is an optional dependency).
# ---------------------------------------------------------------------------

_canopy_metrics: dict | None = None


def _ensure_canopy_metrics() -> dict:
    """Create canopy-related Prometheus metrics on first access."""
    global _canopy_metrics
    if _canopy_metrics is None:
        from prometheus_client import Counter, Gauge

        _canopy_metrics = {
            "websocket_connections_active": Gauge(
                "juniper_canopy_websocket_connections_active",
                "Number of active WebSocket connections",
                ["channel"],
            ),
            "websocket_messages_total": Counter(
                "juniper_canopy_websocket_messages_total",
                "Total WebSocket messages sent",
                ["channel", "type"],
            ),
            "demo_mode_active": Gauge(
                "juniper_canopy_demo_mode_active",
                "Whether demo mode is currently active (0 or 1)",
            ),
            # METRICS-MON R2.2.5 / seed-05: inbound-frame validation counter.
            # Bumped from cascor_service_adapter._relay_loop when an inbound
            # frame fails validation against the canonical envelope schemas
            # in juniper_cascor_protocol.envelope. The ``type`` label is
            # cardinality-bounded by the protocol package (collapses to
            # ``"_unmatched"`` after UNKNOWN_TYPE_BUDGET=16 distinct unknowns
            # per process), mirroring the R1.1 HTTP cardinality discipline.
            "unrecognized_ws_frames_total": Counter(
                "juniper_canopy_unrecognized_ws_frames_total",
                "WS frames that failed envelope validation, by reported type and endpoint.",
                ["type", "endpoint"],
            ),
        }
    return _canopy_metrics


def set_websocket_connections(channel: str, count: int) -> None:
    """Update the active WebSocket connections gauge.

    Args:
        channel: WebSocket channel — "training" or "control".
        count: Current number of active connections.
    """
    _ensure_canopy_metrics()["websocket_connections_active"].labels(channel=channel).set(count)


def inc_websocket_messages(channel: str, msg_type: str) -> None:
    """Increment the WebSocket messages counter.

    Args:
        channel: WebSocket channel — "training" or "control".
        msg_type: Message type — "metrics", "state", "topology", "event", "control_ack", etc.
    """
    _ensure_canopy_metrics()["websocket_messages_total"].labels(channel=channel, type=msg_type).inc()


def set_demo_mode_active(active: bool) -> None:
    """Update the demo mode active gauge.

    Args:
        active: Whether demo mode is currently active.
    """
    _ensure_canopy_metrics()["demo_mode_active"].set(1 if active else 0)


def inc_unrecognized_ws_frame(type_label: str, endpoint: str) -> None:
    """Record an inbound WS frame that failed envelope validation.

    METRICS-MON R2.2.5 / seed-05: increments
    ``juniper_canopy_unrecognized_ws_frames_total{type, endpoint}`` and
    emits a structured WARNING log line so operators see the unrecognized
    type even on stacks without Prometheus scraping.

    Args:
        type_label: The cardinality-bounded type string from the
            ``UnknownEnvelope`` returned by
            :func:`juniper_cascor_protocol.envelope.validate_envelope`.
            Already collapsed to ``"_unmatched"`` if the per-process
            distinct-unknown-type budget is exhausted.
        endpoint: ``"training"`` or ``"control"`` — which WS endpoint
            the frame arrived on.
    """
    import logging

    logging.getLogger("juniper_canopy.observability").warning(
        "juniper_canopy_unrecognized_ws_frame",
        extra={"type": type_label, "endpoint": endpoint},
    )
    _ensure_canopy_metrics()["unrecognized_ws_frames_total"].labels(type=type_label, endpoint=endpoint).inc()
