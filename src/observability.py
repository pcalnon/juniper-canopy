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
    """Create canopy-related Prometheus metrics on first access.

    In production this runs exactly once per process. In test contexts the
    module-level ``_canopy_metrics`` cache may be reset (e.g. by a fixture
    nulling it for re-init coverage) while the underlying Prometheus REGISTRY
    still holds the prior collectors. We catch the resulting
    ``Duplicated timeseries`` ``ValueError`` and adopt the already-registered
    collectors instead of rebuilding them, which keeps test isolation cheap
    without forcing every fixture to scrub REGISTRY by hand.
    """
    global _canopy_metrics
    if _canopy_metrics is None:
        from juniper_observability import register_or_reuse
        from prometheus_client import Counter, Gauge, Histogram

        _canopy_metrics = {
            "websocket_connections_active": register_or_reuse(
                Gauge,
                "juniper_canopy_websocket_connections_active",
                "Number of active WebSocket connections",
                ["channel"],
            ),
            "websocket_messages_total": register_or_reuse(
                Counter,
                "juniper_canopy_websocket_messages_total",
                "Total WebSocket messages sent",
                ["channel", "type"],
            ),
            "demo_mode_active": register_or_reuse(
                Gauge,
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
            "unrecognized_ws_frames_total": register_or_reuse(
                Counter,
                "juniper_canopy_unrecognized_ws_frames_total",
                "WS frames that failed envelope validation, by reported type and endpoint.",
                ["type", "endpoint"],
            ),
            # METRICS-MON R4.3 / seed-13: outbound juniper-data-client
            # request observability. Populated by the on_request hook
            # closure built in :func:`build_data_client_request_hook`,
            # which is passed to ``JuniperDataClient(on_request=...)``
            # at construction time. Labels:
            # * ``method`` — HTTP method ("GET" / "POST" / ...).
            # * ``status_class`` — closed bucket: "2xx" / "4xx" / "5xx"
            #   / "transport_error". Closed-set labels keep cardinality
            #   bounded vs. raw status codes (R1.1 discipline).
            # * ``error_type`` — exception class name on failure paths,
            #   ``"none"`` on success. Closed by the typed-exception
            #   surface of juniper-data-client (5 known classes + "none").
            "data_client_requests_total": register_or_reuse(
                Counter,
                "juniper_canopy_data_client_requests_total",
                "Outbound juniper-data-client HTTP requests, by method, status class, and error type",
                ["method", "status_class", "error_type"],
            ),
            "data_client_request_duration_ms": register_or_reuse(
                Histogram,
                "juniper_canopy_data_client_request_duration_ms",
                # METRICS-MON R4.1 / R4.3: bucket layout is **tentative
                # pending R5.1**. Same human-UX-anchored decade pattern
                # as ``canopy_ws_browser_latency_ms`` (covered in
                # ``notes/observability/HISTOGRAM_BUCKETS_RATIONALE_2026-05-02.md``).
                "Outbound juniper-data-client HTTP request duration in milliseconds (R4.1 buckets tentative pending R5.1)",
                ["method", "status_class"],
                buckets=[1, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000],
            ),
            # OBS-WIRE-02 / Q1 (option a): client-side WS sequence-gap
            # counter. Replaces the cascor-side
            # ``cascor_ws_seq_gap_detected_total`` (which had no
            # semantically valid server-side wire-site — gap detection
            # is inherently client-side truth). Cross-service
            # correlation labels:
            # * ``service`` — upstream cascor identity (closed: just
            #   ``"juniper-cascor"`` today, reserves room for future
            #   multi-cascor topologies).
            # * ``channel`` — ``"training"`` or ``"control"`` (mirrors
            #   the A.4 ``websocket_messages_total`` channel labelset).
            # See ``notes/observability/A9_AND_3_2_STATE_ANALYSIS_2026-05-03.md``
            # in juniper-ml (Q1 resolution).
            "ws_seq_gap_detected_total": register_or_reuse(
                Counter,
                "juniper_canopy_ws_seq_gap_detected_total",
                "Client-side WS sequence-number gaps detected on inbound frames, by upstream service and channel.",
                ["service", "channel"],
            ),
        }
    return _canopy_metrics


def _classify_status(status: int | None) -> str:
    """METRICS-MON R4.3: bucket an HTTP status code (or ``None`` on
    transport failure) into a closed-set ``status_class`` label.

    Returning closed-set strings instead of raw status codes keeps the
    Counter cardinality bounded — a misbehaving server returning
    arbitrary 4xx/5xx codes can't blow up the label space.
    """
    if status is None:
        return "transport_error"
    if 200 <= status < 300:
        return "2xx"
    if 400 <= status < 500:
        return "4xx"
    if 500 <= status < 600:
        return "5xx"
    # 1xx / 3xx are not expected on this surface (data-client follows
    # redirects via requests' default; 1xx never reaches user code).
    # Bucket as transport_error so anomalies show up.
    return "transport_error"


def build_data_client_request_hook():
    """METRICS-MON R4.3: Prometheus-emitting closure for
    :class:`juniper_data_client.JuniperDataClient`'s ``on_request``
    instrumentation hook.

    Returned closure matches the :data:`juniper_data_client.RequestHook`
    signature ``(method, url, status, duration_ms, error)``. It bumps:

    * ``juniper_canopy_data_client_requests_total{method, status_class,
      error_type}`` — once per call.
    * ``juniper_canopy_data_client_request_duration_ms{method,
      status_class}`` — once per call (timing).

    The hook is built once and passed to ``JuniperDataClient(on_request=
    build_data_client_request_hook())`` at construction time. Building
    it lazily (rather than as a module-level singleton) means tests
    that null ``_canopy_metrics`` see a fresh closure on the next
    construction.
    """

    def _hook(
        method: str,
        url: str,  # noqa: ARG001 — accepted to match RequestHook signature; not labeled (cardinality)
        status: int | None,
        duration_ms: float,
        error: BaseException | None,
    ) -> None:
        metrics = _ensure_canopy_metrics()
        status_class = _classify_status(status)
        raw_error_type = type(error).__name__ if error is not None else "none"
        # OBS-WIRE-02 / A.8: closed-set validation. juniper-data-client
        # publishes a known set of typed exceptions (see
        # ``_KNOWN_DATA_CLIENT_ERROR_TYPES``); anything else collapses to
        # ``"_other"`` to keep cardinality bounded if the client ever
        # adds a new exception class. Production must NOT crash on the
        # unknown class — log a structured WARNING so the next allowlist
        # update gets flagged, but emit the metric either way.
        if raw_error_type in _KNOWN_DATA_CLIENT_ERROR_TYPES:
            error_type = raw_error_type
        else:
            error_type = "_other"
            import logging

            logging.getLogger("juniper_canopy.observability").warning(
                "juniper_canopy_data_client_unknown_error_type",
                extra={"raw_error_type": raw_error_type, "method": method, "status_class": status_class},
            )
        metrics["data_client_requests_total"].labels(
            method=method,
            status_class=status_class,
            error_type=error_type,
        ).inc()
        metrics["data_client_request_duration_ms"].labels(
            method=method,
            status_class=status_class,
        ).observe(duration_ms)

    return _hook


def set_websocket_connections(channel: str, count: int) -> None:
    """Update the active WebSocket connections gauge.

    Args:
        channel: WebSocket channel — "training" or "control".
        count: Current number of active connections.
    """
    _ensure_canopy_metrics()["websocket_connections_active"].labels(channel=channel).set(count)


# OBS-WIRE A.4 / messages_total: closed-set allowlist for the ``type`` label
# on ``juniper_canopy_websocket_messages_total``. Production message types
# emitted by the WebSocketManager dispatch sites and the create_*_message()
# helpers in :mod:`communication.websocket_manager`. Anything outside this
# set collapses to ``"_other"`` so a misbehaving caller — or a future code
# path that introduces a new type without thinking about cardinality —
# cannot blow up the timeseries label space (R1.1 closed-set discipline,
# same posture as ``unrecognized_ws_frames_total``).
_WS_MESSAGE_TYPE_ALLOWLIST: frozenset[str] = frozenset(
    {
        "state",
        "metrics",
        "topology",
        "event",
        "control_ack",
        "command_response",
        "ping",
        "pong",
        "connection_established",
        "server_shutdown",
        "initial_status",
        "initial_metrics",
        "params_updated",
        "candidate_progress",
        "network_stats",
        "state_change",
        "error",
    }
)


def inc_websocket_messages(channel: str, msg_type: str) -> None:
    """Increment the WebSocket messages counter.

    Args:
        channel: WebSocket channel — "training" or "control".
        msg_type: Message type — collapsed to ``"_other"`` when outside the
            closed allowlist :data:`_WS_MESSAGE_TYPE_ALLOWLIST` to keep the
            counter cardinality bounded (R1.1).
    """
    bucketed = msg_type if msg_type in _WS_MESSAGE_TYPE_ALLOWLIST else "_other"
    _ensure_canopy_metrics()["websocket_messages_total"].labels(channel=channel, type=bucketed).inc()


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


# OBS-WIRE-02 / Q1 (option a): closed-set allowlist for the ``error_type``
# label on ``juniper_canopy_data_client_requests_total``. Mirrors the typed
# exception surface published by juniper-data-client (see
# ``juniper_data_client/exceptions.py``). Anything outside this set
# collapses to ``"_other"`` so a future juniper-data-client release that
# adds a new exception class can't blow up the timeseries label space
# (R1.1 closed-set discipline).
#
# When juniper-data-client adds a new typed exception, the WARNING log
# line emitted by ``build_data_client_request_hook`` flags it for an
# allowlist update here; production must not crash on the unknown class
# (audit doc A.8).
_KNOWN_DATA_CLIENT_ERROR_TYPES: frozenset[str] = frozenset(
    {
        "none",
        "JuniperDataClientError",
        "JuniperDataConfigurationError",
        "JuniperDataConnectionError",
        "JuniperDataTimeoutError",
        "JuniperDataNotFoundError",
        "JuniperDataValidationError",
    }
)


# OBS-WIRE-02 / Q1 (option a): closed-set allowlist for the ``channel``
# label on ``juniper_canopy_ws_seq_gap_detected_total``. Mirrors the A.4
# wire-up choice for ``juniper_canopy_websocket_messages_total``.
_SEQ_GAP_CHANNELS: frozenset[str] = frozenset({"training", "control"})

# Static value for the ``service`` label — only one upstream cascor for
# now; reserves room for future multi-cascor topologies (would become a
# parameter on the helper at that point).
_SEQ_GAP_UPSTREAM_SERVICE: str = "juniper-cascor"


def inc_ws_seq_gap_detected(channel: str) -> None:
    """Record a client-side WS sequence gap detected on an inbound frame.

    OBS-WIRE-02 / Q1 (option a): replaces the cascor-side
    ``cascor_ws_seq_gap_detected_total`` counter, which had no
    semantically valid server-side wire-site (gap detection is
    inherently client-side truth). The replacement lives here on canopy
    with cross-service correlation labels:

    * ``service`` — the upstream cascor service the gap was detected
      against. Static ``"juniper-cascor"`` for now (one upstream);
      reserves room for future multi-cascor topologies.
    * ``channel`` — the WS channel the gap was detected on. Closed
      set: ``{"training", "control"}``.

    The helper validates ``channel`` against
    :data:`_SEQ_GAP_CHANNELS` and raises :class:`ValueError` on an
    unknown value (mirrors the
    :func:`juniper-cascor.api.observability.inc_training_session_completed`
    pattern — instrumentation drift surfaces early rather than silently
    blowing up cardinality).

    Also emits a structured WARNING log line per the R4.7 / R2.2 pattern
    so operators see the gap on stacks without Prometheus scraping.

    Args:
        channel: WS channel — must be one of ``"training"`` or
            ``"control"``.

    Raises:
        ValueError: If ``channel`` is not in :data:`_SEQ_GAP_CHANNELS`.
    """
    if channel not in _SEQ_GAP_CHANNELS:
        raise ValueError(f"invalid ws seq gap channel {channel!r}; expected one of {sorted(_SEQ_GAP_CHANNELS)!r}")

    import logging

    logging.getLogger("juniper_canopy.observability").warning(
        "juniper_canopy_ws_seq_gap_detected",
        extra={"service": _SEQ_GAP_UPSTREAM_SERVICE, "channel": channel},
    )
    _ensure_canopy_metrics()["ws_seq_gap_detected_total"].labels(
        service=_SEQ_GAP_UPSTREAM_SERVICE,
        channel=channel,
    ).inc()
