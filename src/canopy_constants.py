#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     canopy_constants.py
# Author:        Paul Calnon
# Version:       0.1.1
#
# Date:          2025-10-22
# Last Modified: 2025-12-13
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2025 Paul Calnon
#
# Description:
#    Centralized constants for juniper_canopy application
#
#####################################################################################################################################################################################################
# Notes:
#
#####################################################################################################################################################################################################
# References:
#
#####################################################################################################################################################################################################
# TODO :
#
#####################################################################################################################################################################################################
# COMPLETED:
#
#####################################################################################################################################################################################################
from typing import Final


class TrainingConstants:
    """Training-related constants.

    Defines default values, minimum and maximum constraints for training
    parameters including epochs, learning rates, and hidden units.
    """

    # ── Neural Network: Epoch limits ──
    # MAX_TRAINING_EPOCHS raised to 1e11 (100 billion) per requirements 2026-04-10
    MIN_TRAINING_EPOCHS: Final[int] = 10
    MAX_TRAINING_EPOCHS: Final[int] = 100000000000
    DEFAULT_TRAINING_EPOCHS: Final[int] = 1000000

    # ── Neural Network: Maximum growth iterations (hidden unit additions) ──
    # MAX_MAX_GROWTH_ITERATIONS raised to 1e6 (1 million) per requirements 2026-04-10
    DEFAULT_MAX_GROWTH_ITERATIONS: Final[int] = 1000
    MIN_MAX_GROWTH_ITERATIONS: Final[int] = 1
    MAX_MAX_GROWTH_ITERATIONS: Final[int] = 1000000

    # ── Neural Network: Per-output-training-pass epoch budget (Phase 6E A-1) ──
    # Distinct from MAX_TRAINING_EPOCHS (global ceiling). Surfaced by cascor PR #157.
    DEFAULT_OUTPUT_EPOCHS: Final[int] = 25
    MIN_OUTPUT_EPOCHS: Final[int] = 1
    MAX_OUTPUT_EPOCHS: Final[int] = 1000000

    # ── Neural Network: Output weight initialization method ──
    DEFAULT_INIT_OUTPUT_WEIGHTS: Final[str] = "zero"
    INIT_OUTPUT_WEIGHTS_OPTIONS: Final[list] = ["zero", "random"]

    # ── Neural Network: Output-layer optimizer (Phase 6E A-2 — cascor PR #158) ──
    # Mirrors the Literal in cascor's NetworkCreateRequest / TrainingParams /
    # TrainingParamUpdateRequest. Live changes take effect at the next
    # output-training pass (the running optimizer keeps its momentum mid-pass).
    DEFAULT_OPTIMIZER_TYPE: Final[str] = "Adam"
    OPTIMIZER_TYPE_OPTIONS: Final[list] = [
        "Adam",
        "AdamW",
        "SGD",
        "RMSprop",
        "NAdam",
        "RAdam",
        "Adamax",
        "Adagrad",
        "Adadelta",
        "Adafactor",
        "ASGD",
        "LBFGS",
        "Rprop",
        "Muon",
    ]

    # ── Neural Network: Hidden-unit activation function (Phase 6E A-3 — cascor PR #162) ──
    # Mirrors the Literal in cascor's NetworkCreateRequest / TrainingParams /
    # TrainingParamUpdateRequest. Live changes take effect at the next
    # cascade growth pass (existing units retain whatever activation they
    # were trained with).
    DEFAULT_ACTIVATION_FUNCTION: Final[str] = "Tanh"
    ACTIVATION_FUNCTION_OPTIONS: Final[list] = [
        "Identity",
        "Tanh",
        "Sigmoid",
        "ReLU",
        "LeakyReLU",
        "ELU",
        "SELU",
        "GELU",
        "Softmax",
        "Softplus",
        "Hardtanh",
        "Softshrink",
        "Tanhshrink",
        "tanh",
        "sigmoid",
        "relu",
    ]

    # ── Neural Network: Learning rate ──
    DEFAULT_LEARNING_RATE: Final[float] = 0.01
    MIN_LEARNING_RATE: Final[float] = 0.0001
    MAX_LEARNING_RATE: Final[float] = 1.0

    # ── Neural Network: Hidden units ──
    DEFAULT_MAX_HIDDEN_UNITS: Final[int] = 1000
    MIN_HIDDEN_UNITS: Final[int] = 0
    MAX_HIDDEN_UNITS: Final[int] = 10000

    # ── Neural Network: Multi-node layers ──
    DEFAULT_MULTI_NODE_LAYERS: Final[bool] = False

    # ── Neural Network: Growth trigger ──
    DEFAULT_GROWTH_TRIGGER: Final[str] = "convergence"
    DEFAULT_PRESET_EPOCHS: Final[int] = 50
    MIN_PRESET_EPOCHS: Final[int] = 1
    MAX_PRESET_EPOCHS: Final[int] = 10000

    # ── Neural Network: Convergence detection (used by growth trigger) ──
    DEFAULT_CONVERGENCE_ENABLED: Final[bool] = True
    DEFAULT_CONVERGENCE_THRESHOLD: Final[float] = 0.001
    MIN_CONVERGENCE_THRESHOLD: Final[float] = 0.0001
    MAX_CONVERGENCE_THRESHOLD: Final[float] = 0.1

    # ── Neural Network: Patience ──
    DEFAULT_PATIENCE: Final[int] = 50
    MIN_PATIENCE: Final[int] = 1
    MAX_PATIENCE: Final[int] = 500

    # ── Neural Network: Spiral dataset ──
    DEFAULT_SPIRAL_ROTATIONS: Final[float] = 1.5
    MIN_SPIRAL_ROTATIONS: Final[float] = 0.5
    MAX_SPIRAL_ROTATIONS: Final[float] = 5.0
    DEFAULT_SPIRAL_NUMBER: Final[int] = 2
    MIN_SPIRAL_NUMBER: Final[int] = 1
    MAX_SPIRAL_NUMBER: Final[int] = 10
    DEFAULT_DATASET_ELEMENTS: Final[int] = 1000
    MIN_DATASET_ELEMENTS: Final[int] = 50
    MAX_DATASET_ELEMENTS: Final[int] = 50000
    DEFAULT_DATASET_NOISE: Final[float] = 0.25
    MIN_DATASET_NOISE: Final[float] = 0.0
    MAX_DATASET_NOISE: Final[float] = 1.0

    # ── Candidate Nodes: Pool size ──
    DEFAULT_CANDIDATE_POOL_SIZE: Final[int] = 100
    MIN_CANDIDATE_POOL_SIZE: Final[int] = 1
    MAX_CANDIDATE_POOL_SIZE: Final[int] = 500

    # ── Candidate Nodes: Correlation threshold ──
    DEFAULT_CANDIDATE_CORRELATION_THRESHOLD: Final[float] = 0.001
    MIN_CANDIDATE_CORRELATION_THRESHOLD: Final[float] = 0.00001
    MAX_CANDIDATE_CORRELATION_THRESHOLD: Final[float] = 0.1

    # ── Candidate Nodes: Selected candidates ──
    DEFAULT_SELECTED_CANDIDATES: Final[int] = 1
    MIN_SELECTED_CANDIDATES: Final[int] = 1
    MAX_SELECTED_CANDIDATES: Final[int] = 50

    # ── Candidate Nodes: Patience ──
    DEFAULT_CN_PATIENCE: Final[int] = 30
    MIN_CN_PATIENCE: Final[int] = 1
    MAX_CN_PATIENCE: Final[int] = 500

    # ── Candidate Nodes: Pool training complete ──
    DEFAULT_CN_TRAINING_COMPLETE: Final[str] = "preset_epochs"
    DEFAULT_CANDIDATE_TRAINING_ITERATIONS: Final[int] = 500
    MIN_CANDIDATE_TRAINING_ITERATIONS: Final[int] = 10
    MAX_CANDIDATE_TRAINING_ITERATIONS: Final[int] = 5000
    DEFAULT_CANDIDATE_CONVERGENCE_THRESHOLD: Final[float] = 0.0001
    MIN_CANDIDATE_CONVERGENCE_THRESHOLD: Final[float] = 0.000001
    MAX_CANDIDATE_CONVERGENCE_THRESHOLD: Final[float] = 0.01

    # ── Candidate Nodes: Multi candidate selection ──
    DEFAULT_MULTI_CANDIDATE_ENABLED: Final[bool] = False
    DEFAULT_TOP_CANDIDATES_COUNT: Final[int] = 1
    MIN_TOP_CANDIDATES_COUNT: Final[int] = 1
    MAX_TOP_CANDIDATES_COUNT: Final[int] = 20
    DEFAULT_RANDOM_CANDIDATES_COUNT: Final[int] = 1
    MIN_RANDOM_CANDIDATES_COUNT: Final[int] = 1
    MAX_RANDOM_CANDIDATES_COUNT: Final[int] = 20

    # ── Cascade correlation internal constants (Phase 6 — matches CasCor reference) ──
    CASCADE_COOLDOWN_EPOCHS: Final[int] = 50  # DEPRECATED: only used by _should_add_cascade_unit (not production loop)
    CANDIDATE_POOL_SIZE: Final[int] = 32  # internal CasCor constant, distinct from UI DEFAULT_CANDIDATE_POOL_SIZE
    CANDIDATE_TRAINING_STEPS: Final[int] = 600
    CANDIDATE_PATIENCE: Final[int] = 30
    OUTPUT_RETRAIN_STEPS: Final[int] = 1000
    OUTPUT_RETRAIN_EMIT_EVERY: Final[int] = 50
    OUTPUT_WEIGHT_INIT_STD: Final[float] = 0.1
    MIN_CANDIDATE_CORRELATION: Final[float] = 0.01
    METRICS_HISTORY_MAXLEN: Final[int] = 10000


class DashboardConstants:
    """Dashboard UI constants.

    Defines update intervals, timeouts, and data limits for the dashboard
    components and API interactions.
    """

    # Update intervals (milliseconds)
    FAST_UPDATE_INTERVAL_MS: Final[int] = 1000  # 1 second
    SLOW_UPDATE_INTERVAL_MS: Final[int] = 5000  # 5 seconds

    # API timeouts (seconds)
    API_TIMEOUT_SECONDS: Final[int] = 2
    FAST_API_TIMEOUT_SECONDS: Final[float] = 1.0  # For fast-interval polling callbacks

    # Data limits
    MAX_METRICS_HISTORY: Final[int] = 100
    MAX_DATA_POINTS: Final[int] = 10000

    # N1 (training-runtime defects plan §4 I-1): bound the full-history metrics
    # fetch. In ``full`` / ``hidden_units`` display modes the metrics-store poll
    # fetches the complete history (``limit=0`` → up to 10k rows); refetching
    # that every fast-interval tick (1 s) is an unconditional 10k-rows-per-second
    # steady state. Interval-driven full fetches therefore only run every Nth
    # fast tick (N = this modulus → one full fetch per ~5 s at the 1 s fast
    # interval); a display-mode switch still triggers an immediate fetch.
    FULL_HISTORY_POLL_TICK_MODULUS: Final[int] = 5

    DEFAULT_METRICS_HISTORY: Final[int] = 50
    DEFAULT_DATA_POINTS: Final[int] = 1000
    DEFAULT_SLIDING_WINDOW_SIZE: Final[int] = 500

    # Display Constants
    DEFAULT_SCALE: Final[float] = 10.0
    DEFAULT_ZOOM: Final[int] = 1
    DEFAULT_ZOOM_INCREMENT: Final[int] = 1
    DEFAULT_ZOOM_DECREMENT: Final[int] = 1
    DEFAULT_ZOOM_MIN: Final[int] = 1
    DEFAULT_ZOOM_MAX: Final[int] = 10

    # ── HTTP request timeouts for dashboard manager (seconds) ──
    # POST timeout for short-lived training control commands
    # (start/pause/stop/resume/reset).
    DASHBOARD_POST_TIMEOUT: Final[int] = 2
    # Threshold (seconds) after which a loading button is force-reset.
    DASHBOARD_TIMEOUT_THRESHOLD: Final[float] = 2.0
    # Long POST timeout for set_params with retry. Higher because the backend
    # may need to reconfigure the cascor session.
    DASHBOARD_LONG_POST_TIMEOUT: Final[int] = 10
    # GET timeout for state verification reads.
    DASHBOARD_GET_TIMEOUT: Final[int] = 5
    # Maximum retries for set_params operations.
    DASHBOARD_SET_PARAMS_MAX_RETRIES: Final[int] = 3
    # ── #2a Retry-After backoff (PROVISIONAL — revisit) ──────────────────
    # On HTTP 429 from set_params, the handler backs off and retries within
    # the budget above instead of bailing immediately. The sleep runs on a
    # Dash callback thread, so the server-advertised ``Retry-After`` (which can
    # be the limiter's full window, tens of seconds) is *capped* — we never
    # block the callback on the raw value. A missing/non-numeric header (e.g.
    # the rare RFC 9110 HTTP-date form) uses the fallback delay below.
    # NOTE: both values are first-cut tuning and should be revisited once
    # there is real 429-frequency data from the deployed stack.
    DASHBOARD_RETRY_AFTER_MAX_SLEEP_S: Final[float] = 2.0
    DASHBOARD_RETRY_AFTER_FALLBACK_S: Final[float] = 0.5

    # FRONTEND_ISSUES_PLAN_2026-05-09 §2.5 B / Issue #2 — common debounce for
    # numeric ``dbc.Input`` widgets. 350 ms balances typing latency against
    # callback churn — typed values commit ~350 ms after the last keystroke
    # without requiring blur. Spinner clicks commit immediately regardless.
    # Pre-PR-8 every numeric input used ``debounce=True`` which only commits
    # on blur/Enter, producing the "type then click Apply with mouse =
    # stale value" UX bug.
    NUMERIC_INPUT_DEBOUNCE_MS: Final[int] = 350

    # ── E-3 (training-runtime defects plan §9): apply-in-flight watchdog ──
    # A failed Apply used to leave the CAN-000 `apply-in-flight` clamp stuck
    # true (every non-200 path returned `dash.no_update` for
    # `applied-params-store`, the store whose update released the clamp),
    # permanently disabling BOTH update intervals — the pre-refresh total
    # freeze of I-1 root cause 4. The server callback now always releases the
    # clamp; this clientside watchdog is the safety net for the class no
    # server response can fix (the `/_dash-update-component` POST itself
    # failing at the network level). Limit must exceed the worst-case legit
    # apply: 3 retries × DASHBOARD_LONG_POST_TIMEOUT (10 s) + 2 ×
    # DASHBOARD_RETRY_AFTER_MAX_SLEEP_S (2 s) + DASHBOARD_GET_TIMEOUT (5 s)
    # verify ≈ 39 s.
    APPLY_WATCHDOG_INTERVAL_MS: Final[int] = 5000
    APPLY_IN_FLIGHT_MAX_MS: Final[int] = 60000


class ServerConstants:
    """Server configuration constants.

    Defines default server configuration including host, port, and
    WebSocket endpoint paths.
    """

    DEFAULT_HOST: Final[str] = "127.0.0.1"
    DEFAULT_PORT: Final[int] = 8050

    # WebSocket paths
    WS_TRAINING_PATH: Final[str] = "/ws/training"
    WS_CONTROL_PATH: Final[str] = "/ws/control"

    # ── Service discovery (cascor auto-discovery) ──
    DEFAULT_DISCOVERY_PORTS: Final[tuple[int, ...]] = (8200,)
    DEFAULT_DISCOVERY_HOST: Final[str] = "localhost"
    DEFAULT_DISCOVERY_TIMEOUT: Final[float] = 2.0

    # ── Health check endpoints (cascor side, used by discovery) ──
    HEALTH_LIVE_ENDPOINT: Final[str] = "/v1/health/live"
    HEALTH_LIVE_OK_VALUE: Final[str] = "alive"
    HEALTH_STATUS_KEY: Final[str] = "status"

    # ── Example WebSocket URLs (for documentation) ──
    WS_TRAINING_URL_EXAMPLE: Final[str] = "ws://localhost:8050/ws/training"


class WebSocketConstants:
    """WebSocket configuration constants.

    Defines WebSocket connection limits, heartbeat intervals, and
    reconnection parameters.
    """

    MAX_CONNECTIONS: Final[int] = 50
    HEARTBEAT_INTERVAL_SEC: Final[int] = 30
    RECONNECT_ATTEMPTS: Final[int] = 5
    RECONNECT_DELAY_SEC: Final[int] = 2


class JuniperDataConstants:
    """JuniperData service integration constants.

    Defines default values for connecting to and interacting with the
    JuniperData dataset generation service.
    """

    DEFAULT_URL: Final[str] = "http://localhost:8100"
    DEFAULT_TIMEOUT_S: Final[int] = 30
    DEFAULT_RETRY_ATTEMPTS: Final[int] = 3
    DEFAULT_RETRY_BACKOFF_BASE_S: Final[float] = 0.5
    DEFAULT_DATASET_SAMPLES: Final[int] = 200
    DEFAULT_DATASET_NOISE: Final[float] = 0.1
    DEFAULT_DATASET_SEED: Final[int] = 42
    DEFAULT_GENERATOR: Final[str] = "spiral"
    API_VERSION: Final[str] = "v1"


class SecurityConstants:
    """Security middleware and request hardening constants.

    Centralizes the security headers, exempt paths, request limits, CORS
    origin defaults, and Content-Security-Policy used by the canopy
    middleware stack.
    """

    # ── Request body size limits (bytes) ──
    MAX_REQUEST_BODY_BYTES: Final[int] = 10 * 1024 * 1024  # 10 MB

    # ── Path-based exemption from API key + rate limiter middleware ──
    # Prefix-based exemptions (Dash app + its static assets, Prometheus
    # /metrics sub-app). /metrics is mounted as an ASGI sub-app via
    # ``app.mount("/metrics", get_prometheus_app())``; FastAPI's mount
    # behaviour issues a 307 from ``/metrics`` -> ``/metrics/`` (and
    # any sub-paths under the sub-app would be ``/metrics/...``), so a
    # prefix-form exemption is required to keep the whole sub-app
    # anonymously scrape-able. This matches the convention in
    # juniper-cascor (no auth on /metrics) and complements
    # juniper-data's IP-allowlisted variant. The trailing-slash form
    # is intentional: ``startswith("/metrics")`` covers ``/metrics``,
    # ``/metrics/``, and any future sub-paths the prometheus_client
    # ASGI app may add.
    EXEMPT_PATH_PREFIXES: Final[tuple[str, ...]] = ("/dashboard", "/metrics")
    # Exact path exemptions (health checks, OpenAPI docs).
    EXEMPT_PATHS: Final[frozenset[str]] = frozenset(
        {
            "/",
            "/health",
            "/api/health",
            "/v1/health",
            "/v1/health/live",
            "/v1/health/ready",
            "/docs",
            "/openapi.json",
            "/redoc",
        }
    )

    # ── Key-exempt tier (PR-1, Start-Training 401 fix) ──
    # Paths that skip the API-key gate but REMAIN rate-limited — distinct from
    # the fully-exempt sets above, which short-circuit before BOTH the key gate
    # and the limiter. This is the same-origin browser control surface:
    # ``/api/csrf`` must be anonymously mintable so the browser can fetch a
    # token, and ``/api/train/*`` is authenticated by the per-route
    # ``require_browser_control_auth`` dependency (Origin + CSRF) instead of the
    # X-API-Key the browser cannot hold. ``/v1/*`` and every other route stay
    # key-gated (C5). The ``/api/train/`` prefix carries a trailing slash so it
    # matches only the training-control routes, never a future ``/api/train…``
    # sibling. See JUNIPER_CANOPY_TRAINING-CONTROL-AUTH_DESIGN_2026-06-30.md §8.1.
    KEY_EXEMPT_PATH_PREFIXES: Final[tuple[str, ...]] = ("/api/train/",)
    KEY_EXEMPT_PATHS: Final[frozenset[str]] = frozenset({"/api/csrf"})

    # ── Default Content-Security-Policy ──
    # - Dash requires 'unsafe-inline' for styles and scripts.
    # - cdn.jsdelivr.net serves Bootstrap CSS via dash-bootstrap-components.
    # - data: in img-src is needed for Bootstrap inline SVG data URIs.
    DEFAULT_CSP_POLICY: Final[str] = "default-src 'self'; " "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; " "script-src 'self' 'unsafe-inline'; " "img-src 'self' data:; " "frame-ancestors 'none'"

    # ── Standard security response headers ──
    HEADER_X_CONTENT_TYPE_OPTIONS: Final[str] = "X-Content-Type-Options"
    HEADER_X_FRAME_OPTIONS: Final[str] = "X-Frame-Options"
    HEADER_REFERRER_POLICY: Final[str] = "Referrer-Policy"
    HEADER_PERMISSIONS_POLICY: Final[str] = "Permissions-Policy"
    HEADER_CONTENT_SECURITY_POLICY: Final[str] = "Content-Security-Policy"
    HEADER_X_FORWARDED_PROTO: Final[str] = "X-Forwarded-Proto"
    HEADER_STRICT_TRANSPORT_SECURITY: Final[str] = "Strict-Transport-Security"

    # Header values
    NOSNIFF_VALUE: Final[str] = "nosniff"
    FRAME_OPTIONS_DENY: Final[str] = "DENY"
    REFERRER_POLICY_VALUE: Final[str] = "strict-origin-when-cross-origin"
    PERMISSIONS_POLICY_VALUE: Final[str] = "camera=(), microphone=(), geolocation=()"
    HSTS_VALUE: Final[str] = "max-age=31536000; includeSubDomains"
    HTTPS_SCHEME: Final[str] = "https"

    # ── Rate limit response headers ──
    HEADER_RATE_LIMIT: Final[str] = "X-RateLimit-Limit"
    HEADER_RATE_LIMIT_REMAINING: Final[str] = "X-RateLimit-Remaining"
    HEADER_RATE_LIMIT_RESET: Final[str] = "X-RateLimit-Reset"

    # ── HTTP error responses raised by the request body limiter ──
    HTTP_PAYLOAD_TOO_LARGE: Final[int] = 413
    HTTP_BAD_REQUEST: Final[int] = 400
    ERROR_BODY_TOO_LARGE: Final[str] = "Request body too large"
    ERROR_INVALID_CONTENT_LENGTH: Final[str] = "Invalid Content-Length header"

    # ── Content-Length header name (lowercased per RFC 9110 § 6.6.1) ──
    HEADER_CONTENT_LENGTH: Final[str] = "content-length"

    # ── Local CORS origin (Dash dev/preview) ──
    CORS_LOCAL_ORIGIN: Final[str] = "http://127.0.0.1:8050"


class BackendConstants:
    """Backend service adapter and resilience constants.

    Centralizes circuit breaker settings, Redis/Cassandra timeouts, default
    CasCor service URL, and metrics buffer sizing for backend integration.
    """

    # ── Default CasCor service base URL ──
    DEFAULT_CASCOR_SERVICE_URL: Final[str] = "http://localhost:8200"

    # ── Circuit breaker (cascor service adapter) ──
    CIRCUIT_BREAKER_NAME: Final[str] = "cascor"
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: Final[int] = 5
    CIRCUIT_BREAKER_RECOVERY_TIMEOUT: Final[float] = 60.0

    # ── Redis client timeouts (seconds) ──
    REDIS_SOCKET_TIMEOUT: Final[float] = 5.0
    REDIS_CONNECT_TIMEOUT: Final[float] = 5.0
    REDIS_DEFAULT_HOST: Final[str] = "localhost"
    REDIS_DEFAULT_PORT: Final[int] = 6379
    REDIS_DEFAULT_DB: Final[int] = 0
    REDIS_DEFAULT_TTL_SECONDS: Final[int] = 3600
    REDIS_DEFAULT_MAX_MEMORY_MB: Final[int] = 100
    REDIS_URL_ENV_VAR: Final[str] = "REDIS_URL"

    # ── Cassandra client ──
    CASSANDRA_CONNECT_TIMEOUT: Final[int] = 10
    CASSANDRA_DEFAULT_PORT: Final[int] = 9042
    CASSANDRA_DEFAULT_KEYSPACE: Final[str] = "juniper_canopy"
    CASSANDRA_DEFAULT_CONTACT_POINT: Final[str] = "127.0.0.1"
    CASSANDRA_STATUS_CACHE_TTL_SECONDS: Final[int] = 5

    # ── Training metrics buffer ──
    MAX_METRICS_BUFFER_SIZE: Final[int] = 10000

    # ── N2: canopy→cascor stream liveness (cascor_service_adapter) ──
    # Age of the last inbound frame beyond which a *connected* relay stream is
    # classified "degraded" (cascor pings every 30 s, so 60 s = two missed
    # pings). Full liveness expiry (close + reconnect) is governed separately
    # by ``settings.ws_stream_liveness_timeout_seconds``.
    RELAY_STALE_AFTER_SECONDS: Final[float] = 60.0
    # Pong deadline for the control-stream protocol-level keepalive probe.
    CONTROL_PROBE_PONG_TIMEOUT_SECONDS: Final[float] = 10.0

    # ── Demo mode timing ──
    DEMO_THREAD_JOIN_TIMEOUT: Final[float] = 5.0
    DEMO_MAIN_LOOP_SLEEP: Final[int] = 30


# Convenience imports at module level for commonly used constants
MIN_TRAINING_EPOCHS = TrainingConstants.MIN_TRAINING_EPOCHS
MAX_TRAINING_EPOCHS = TrainingConstants.MAX_TRAINING_EPOCHS
DEFAULT_TRAINING_EPOCHS = TrainingConstants.DEFAULT_TRAINING_EPOCHS
