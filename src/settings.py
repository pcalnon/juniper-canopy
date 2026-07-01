#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Pydantic BaseSettings configuration for Juniper Canopy
#
# Author:        Paul Calnon
# Version:       0.1.0
# File Name:     settings.py
#
# Created Date:  2026-03-02
# Last Modified: 2026-03-02
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
#
# Description:
#    Pydantic v2 BaseSettings configuration for JuniperCanopy application.
#    Replaces YAML-based ConfigManager with typed, validated settings using
#    the JUNIPER_CANOPY_ environment variable prefix. Maintains backward
#    compatibility with legacy CASCOR_* environment variables during the
#    transition period.
#
#####################################################################################################################################################################################################
# Notes:
#
#    Environment variable access:
#      - New prefix: JUNIPER_CANOPY_*  (primary)
#      - Legacy prefix: CASCOR_*       (fallback with deprecation warnings)
#      - Shared: JUNIPER_DATA_URL      (cross-service, no prefix change)
#
#    Nested settings via double-underscore delimiter:
#      JUNIPER_CANOPY_SERVER__HOST=0.0.0.0
#      JUNIPER_CANOPY_TRAINING__EPOCHS__DEFAULT=300
#
#####################################################################################################################################################################################################
import os
import socket
import warnings
from functools import lru_cache
from typing import Optional

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from secrets_util import get_secret

# Canopy's canonical bind port. Hardcoded because ``cascor_ws_origin``'s
# factory needs a port at module-evaluation time, before
# ``ServerSettings.port`` (the runtime authority) is constructed.
# Operators who bind canopy on a different port must additionally set
# ``JUNIPER_CANOPY_CASCOR_WS_ORIGIN`` to the matching value (and add it
# to cascor's ``JUNIPER_CASCOR_WS_CONTROL_ALLOWED_ORIGINS``).
_CASCOR_WS_ORIGIN_DEFAULT_PORT = 8050


def _default_cascor_ws_origin() -> str:
    """Derive a sensible default ``cascor_ws_origin`` from the runtime host.

    Returns ``http://{socket.gethostname()}:8050``. ``gethostname()`` resolves to:

    - The compose service name in docker compose (``juniper-canopy``,
      ``juniper-canopy-demo``, …) — automatically tracks demo / dev /
      future-profile renames.
    - The pod name in kubernetes.
    - The dev box hostname under host-mode dev — wrong for connecting
      to a cascor on ``localhost:8200``. Set
      ``JUNIPER_CANOPY_CASCOR_WS_ORIGIN=http://localhost:8050`` in that
      case (same override that the previous hardcoded default required
      for host-mode dev).

    Pre-this-commit default was a hardcoded ``http://juniper-canopy:8050``
    — correct only for the canonical full-profile compose service name;
    every other topology (demo profile, k8s, …) needed an explicit
    operator override. The factory removes that need for the common
    case while keeping the override hook for the dev / unusual-name
    case.

    Cascor's matching allowlist (``JUNIPER_CASCOR_WS_CONTROL_ALLOWED_ORIGINS``)
    must contain the value canopy ends up sending. juniper-deploy ships
    the canonical full-profile compose with both ends pre-aligned;
    the demo-profile override (juniper-deploy#110) is now redundant for
    the canopy half but stays as belt-and-suspenders.
    """
    return f"http://{socket.gethostname()}:{_CASCOR_WS_ORIGIN_DEFAULT_PORT}"


class TrainingParamConfig(BaseModel):
    """Nested model for a single training parameter with validation constraints."""

    min: float
    max: float
    default: float
    modifiable_during_training: bool = False

    @field_validator("default")
    @classmethod
    def default_in_range(cls, v, info):
        data = info.data
        if "min" in data and "max" in data:
            if not data["min"] <= v <= data["max"]:
                raise ValueError(f"default {v} not in [{data['min']}, {data['max']}]")
        return v


class TrainingSettings(BaseModel):
    """Training parameter configuration (replaces YAML training section)."""

    # epochs.max raised to 1e11, max_iterations.max raised to 1e6 per requirements 2026-04-10
    epochs: TrainingParamConfig = TrainingParamConfig(min=10, max=100000000000, default=1000000)
    learning_rate: TrainingParamConfig = TrainingParamConfig(min=0.0001, max=1.0, default=0.01)
    hidden_units: TrainingParamConfig = TrainingParamConfig(min=0, max=10000, default=1000)
    max_iterations: TrainingParamConfig = TrainingParamConfig(min=1, max=1000000, default=1000)
    preset_epochs: TrainingParamConfig = TrainingParamConfig(min=1, max=10000, default=50)


class ServerSettings(BaseModel):
    """Server configuration (replaces YAML application.server section)."""

    host: str = "127.0.0.1"
    port: int = 8050
    debug: bool = False


class WebSocketSettings(BaseModel):
    """WebSocket configuration (replaces YAML backend.communication section)."""

    max_connections: int = 50
    heartbeat_interval: int = 30
    reconnect_attempts: int = 5
    reconnect_delay: int = 2

    # Phase B-pre-a: WebSocket security (M-SEC-01b, M-SEC-03, M-SEC-04)
    allowed_origins: list[str] = [
        "http://localhost:8050",
        "http://127.0.0.1:8050",
        "https://localhost:8050",
        "https://127.0.0.1:8050",
    ]
    max_connections_per_ip: int = 5
    idle_timeout_seconds: int = 120
    max_message_size_training: int = 4096
    max_message_size_control: int = 65536


class CascorDiscoverySettings(BaseModel):
    """Settings for auto-discovery of running cascor instances."""

    enabled: bool = True
    host: str = "localhost"
    ports: list[int] = [8200]
    timeout_seconds: float = 2.0


class Settings(BaseSettings):
    """JuniperCanopy application settings.

    Primary configuration source for the Juniper Canopy application. Uses
    Pydantic BaseSettings with JUNIPER_CANOPY_ prefix for environment variables.
    Supports nested settings via double-underscore delimiter and .env file loading.
    """

    model_config = SettingsConfigDict(
        env_prefix="JUNIPER_CANOPY_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_nested_delimiter="__",
    )

    # Server
    server: ServerSettings = ServerSettings()

    # Training
    training: TrainingSettings = TrainingSettings()

    # WebSocket
    websocket: WebSocketSettings = WebSocketSettings()

    # Backend
    demo_mode: bool = False
    backend_path: str = "../juniper-cascor"
    juniper_data_url: str = "http://localhost:8100"
    # Outbound API key canopy sends as ``X-API-Key`` on every juniper-data
    # request. Resolved by ``_check_juniper_data_api_key`` via ``get_secret``,
    # which honors ``<NAME>_FILE`` indirection so Docker-secrets / k8s-secrets
    # mounts work without leaking the value through ``docker inspect`` /
    # env dumps. Resolution order: prefixed canonical
    # (``JUNIPER_CANOPY_JUNIPER_DATA_API_KEY[_FILE]``) → cross-service shared
    # (``JUNIPER_DATA_API_KEY[_FILE]``) → ``None`` (auth omitted). When
    # ``None`` and juniper-data has auth enabled, calls 401 — by design so
    # the failure is loud rather than silent.
    juniper_data_api_key: Optional[str] = None
    cascor_service_url: Optional[str] = None
    # E.2 PR-2-C: explicit Origin header for canopy → cascor /ws/control
    # connections (juniper-cascor-client>=0.5.0 forwards this to
    # ``websockets.connect(..., origin=…)``). Required because cascor's
    # ``/ws/control`` is fail-closed against missing Origin
    # (juniper-cascor#129); inside docker compose the Python
    # ``websockets`` client emits no Origin by default and the upgrade
    # is rejected with 403. Cascor's matching allowlist
    # ``JUNIPER_CASCOR_WS_CONTROL_ALLOWED_ORIGINS`` must contain the
    # value sent here.
    #
    # Default is derived from ``socket.gethostname()`` so the right
    # Origin tracks the actual runtime topology:
    #
    #   - docker compose full profile  → "http://juniper-canopy:8050"
    #   - docker compose demo profile  → "http://juniper-canopy-demo:8050"
    #   - kubernetes                   → "http://<pod-name>:8050"
    #   - host-mode dev                → "http://<dev-host>:8050"  ← wrong;
    #                                    set JUNIPER_CANOPY_CASCOR_WS_ORIGIN=
    #                                    http://localhost:8050 explicitly.
    #
    # Pre-this-change default was a hardcoded ``http://juniper-canopy:8050``;
    # every non-canonical topology (demo, k8s, …) needed an explicit
    # override. The factory removes that for the common case.
    #
    # Set to empty string to opt out (preserves the pre-0.5.0
    # juniper-cascor-client behaviour of sending no Origin — only
    # safe when cascor is configured to accept missing-Origin upgrades).
    cascor_ws_origin: str = Field(default_factory=_default_cascor_ws_origin)
    cascor_discovery: CascorDiscoverySettings = CascorDiscoverySettings()

    # Recurrence (LMU) model service — model-selection A1 enabler (D3). When set,
    # canopy routes a ``recurrence``-provider model to ``RecurrenceServiceAdapter``,
    # which speaks the service's synchronous one-shot ``POST /v1/train`` contract.
    #
    # ``recurrence_service_url`` resolution (``_check_recurrence_service_url``):
    # prefixed canonical ``JUNIPER_CANOPY_RECURRENCE_SERVICE_URL`` → shared cross-
    # service ``RECURRENCE_SERVICE_URL`` (the var juniper-deploy sets, mirroring
    # ``JUNIPER_DATA_URL``) → ``None``. ``None`` leaves recurrence unconfigured (the
    # model stays non-routable); inside docker compose the canonical value is
    # ``http://juniper-recurrence:8210``.
    recurrence_service_url: Optional[str] = None
    # Outbound API key canopy sends as ``X-API-Key`` on every recurrence request.
    # The recurrence service runs ``SecurityMiddleware``, so a missing key 401s — by
    # design, so the failure is loud rather than silent. Resolved by
    # ``_check_recurrence_api_key`` via ``get_secret`` (honors ``<NAME>_FILE``
    # indirection for Docker/k8s secret mounts): prefixed
    # ``JUNIPER_CANOPY_RECURRENCE_API_KEY[_FILE]`` → shared
    # ``JUNIPER_RECURRENCE_API_KEY[_FILE]`` (the var the recurrence service itself
    # reads) → ``None``. Mirrors ``juniper_data_api_key``.
    recurrence_api_key: Optional[str] = None

    # Demo
    demo_update_interval: float = 1.0
    demo_cascade_every: int = 30

    # Logging
    log_level: str = "INFO"
    log_format: str = "text"
    sentry_dsn: Optional[str] = None
    sentry_traces_sample_rate: float = 0.1

    # Metrics / observability
    metrics_enabled: bool = False
    # SEC-16 parity with juniper-data + juniper-cascor: loopback-only IP
    # allowlist for the Prometheus ``/metrics`` mount. Set
    # ``JUNIPER_CANOPY_METRICS_TRUSTED_IPS='["10.0.0.5","172.18.0.0/16"]'``
    # (JSON list) or a comma-separated string. Accepts bare IP literals
    # and CIDR ranges; ``juniper_observability.MetricsAuthMiddleware``
    # normalises IPv6 zone-ids and IPv4-mapped IPv6 client addresses
    # before membership check, so a Docker container appearing as
    # ``::ffff:172.18.0.5`` matches an IPv4 ``172.18.0.0/16`` allowlist
    # entry. Mirrors
    # ``juniper-data.api.settings.metrics_trusted_ips`` (SEC-16 promoted
    # to juniper-observability 0.3.0).
    metrics_trusted_ips: list[str] = ["127.0.0.1", "::1"]

    @field_validator("metrics_trusted_ips")
    @classmethod
    def _validate_metrics_trusted_ips(cls, v: list[str]) -> list[str]:
        """Fail loud at startup if any allowlist entry is unparseable.

        Without this guard a typo like ``172.18.0.0/164`` would silently
        compile to a working-but-empty allowlist that 403s every scrape.
        Delegates to the same ``parse_trusted_networks`` helper that
        ``MetricsAuthMiddleware`` calls so the failure surfaces at
        ``Settings()`` construction (before the FastAPI app boots).
        """
        from juniper_observability import parse_trusted_networks

        parse_trusted_networks(v)
        return v

    # CORS
    cors_origins: list[str] = []

    # Rate limiting
    rate_limit_enabled: bool = False
    rate_limit_requests_per_minute: int = 60

    # Smoothing
    metrics_smoothing_window: int = 10

    # Phase B-pre-a: Audit logging (M-SEC-07)
    audit_log_enabled: bool = True
    # CFG-09 (v7 roadmap §13896): default was previously
    # ``/var/log/canopy/audit.log`` which requires root to create the
    # parent dir and crashes non-root deployments at startup
    # (``audit_log.py:51`` mkdir or :53 ``TimedRotatingFileHandler`` open).
    # Switched to a CWD-relative default that works out-of-the-box on a
    # fresh non-root install. Production deployments continue to override
    # via the ``JUNIPER_CANOPY_AUDIT_LOG_PATH`` env var (pydantic
    # auto-derives via ``env_prefix='JUNIPER_CANOPY_'``); a deferred
    # follow-up may switch to ``$XDG_STATE_HOME/canopy/audit.log`` for
    # XDG-spec correctness once an XDG helper exists in canopy.
    audit_log_path: str = "logs/audit.log"
    audit_log_retention_days: int = 90

    # Phase B: Browser WebSocket bridge (D-17, D-18, D-04)
    enable_browser_ws_bridge: bool = True  # D-17: P7 flag-flip — 72h staging soak passed
    disable_ws_bridge: bool = False  # D-18: permanent kill switch
    enable_raf_coalescer: bool = False  # D-04: rAF coalescer scaffolded but disabled
    enable_ws_latency_beacon: bool = True  # Latency beacon enabled by default

    # Phase C: set_params over WebSocket (D-47, C-28)
    use_websocket_set_params: bool = True  # C-28: default off, 6 hard flip gates (D-48)
    ws_set_params_timeout: float = 1.0  # C-03: per-request timeout in seconds

    # Phase D: control buttons over WebSocket (D-49, §S10)
    enable_ws_control_buttons: bool = True  # D-49: P12b flag-flip — production soak passed, browser buttons via /ws/control
    ws_control_start_timeout: float = 10.0  # §S10.1 per-command start timeout
    ws_control_stop_timeout: float = 2.0  # §S10.1 per-command stop/pause/resume/reset timeout
    ws_control_set_params_timeout: float = 1.0  # §S10.1 per-command set_params timeout (mirrors ws_set_params_timeout)

    # Phase B-pre-b: CSRF + control-path security (M-SEC-02)
    csrf_enabled: bool = True  # CSRF protection on /ws/control
    csrf_token_ttl_seconds: int = 3600  # 1h sliding TTL
    session_secret_key: str = ""  # SessionMiddleware secret (auto-generated if empty)
    ws_control_auth_timeout: float = 5.0  # Seconds to wait for CSRF first-frame
    # PR-1 (Start-Training 401 fix): authenticate the same-origin browser control
    # surface (/api/train/*, /api/csrf, /ws/control) by Origin + CSRF + session
    # instead of the X-API-Key the browser cannot hold. Default ON so the fix is
    # active on rebuild; set JUNIPER_CANOPY_BROWSER_CONTROL_AUTH_ENABLED=false to
    # restore pre-fix behaviour (key required even for the browser surface). See
    # notes/JUNIPER_CANOPY_TRAINING-CONTROL-AUTH_DESIGN_2026-06-30.md §8.
    browser_control_auth_enabled: bool = True

    # Phase 1B Track 1 (SEC-06): opt-in Sec-WebSocket-Protocol bearer auth for
    # all WS endpoints. Defaults to False until every downstream client
    # (cascor-client, dashboard JS) is updated to negotiate the subprotocol.
    # When enabled, clients must send `Sec-WebSocket-Protocol: bearer, <key>`
    # and the server validates <key> against `api_keys` before accepting.
    ws_auth_enabled: bool = False

    @property
    def ws_bridge_enabled(self) -> bool:
        """Runtime check: bridge is active only when dev-flipped ON and not kill-switched."""
        return self.enable_browser_ws_bridge and not self.disable_ws_bridge

    # ── Legacy CASCOR_* fallback validators ────────────────────────────

    @field_validator("demo_mode", mode="before")
    @classmethod
    def _check_legacy_demo_mode(cls, v):
        if os.getenv("JUNIPER_CANOPY_DEMO_MODE") is not None:
            return v
        legacy = os.getenv("CASCOR_DEMO_MODE")
        if legacy is not None:
            warnings.warn(
                "CASCOR_DEMO_MODE is deprecated. Use JUNIPER_CANOPY_DEMO_MODE instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            return legacy.lower() in ("1", "true", "yes")
        return v

    @field_validator("juniper_data_url", mode="before")
    @classmethod
    def _check_juniper_data_url(cls, v):
        if os.getenv("JUNIPER_CANOPY_JUNIPER_DATA_URL") is not None:
            return v
        shared = os.getenv("JUNIPER_DATA_URL")
        if shared is not None:
            return shared
        return v

    @field_validator("juniper_data_api_key", mode="before")
    @classmethod
    def _check_juniper_data_api_key(cls, v):
        """Resolve the outbound juniper-data API key, ``_FILE`` form first.

        Order:

          1. ``JUNIPER_CANOPY_JUNIPER_DATA_API_KEY_FILE`` → file content,
             or ``JUNIPER_CANOPY_JUNIPER_DATA_API_KEY`` direct (prefixed,
             canopy-specific override — wins so deploy can route a
             canopy-only key separately from cascor's).
          2. ``JUNIPER_DATA_API_KEY_FILE`` → file content, or
             ``JUNIPER_DATA_API_KEY`` direct (shared cross-service env
             var that cascor / juniper-data-client / canopy all read).
          3. ``v`` (whatever pydantic-settings already populated; usually
             ``None`` once we've reached this branch).
        """
        prefixed = get_secret("JUNIPER_CANOPY_JUNIPER_DATA_API_KEY")
        if prefixed:
            return prefixed
        shared = get_secret("JUNIPER_DATA_API_KEY")
        if shared:
            return shared
        return v

    @field_validator("cascor_service_url", mode="before")
    @classmethod
    def _check_cascor_service_url(cls, v):
        if os.getenv("JUNIPER_CANOPY_CASCOR_SERVICE_URL") is not None:
            return v
        legacy = os.getenv("CASCOR_SERVICE_URL")
        if legacy is not None:
            warnings.warn(
                "CASCOR_SERVICE_URL is deprecated. Use JUNIPER_CANOPY_CASCOR_SERVICE_URL instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            return legacy
        return v

    @field_validator("recurrence_service_url", mode="before")
    @classmethod
    def _check_recurrence_service_url(cls, v):
        """Honor a shared unprefixed ``RECURRENCE_SERVICE_URL`` fallback.

        Precedence: the prefixed ``JUNIPER_CANOPY_RECURRENCE_SERVICE_URL`` is
        handled natively by pydantic-settings (so if set it already arrives as
        ``v``); otherwise fall back to the shared cross-service
        ``RECURRENCE_SERVICE_URL`` that juniper-deploy sets (mirroring the
        ``JUNIPER_DATA_URL`` shared-var pattern in ``_check_juniper_data_url``).
        """
        if os.getenv("JUNIPER_CANOPY_RECURRENCE_SERVICE_URL") is not None:
            return v
        shared = os.getenv("RECURRENCE_SERVICE_URL")
        if shared is not None:
            return shared
        return v

    @field_validator("recurrence_api_key", mode="before")
    @classmethod
    def _check_recurrence_api_key(cls, v):
        """Resolve the outbound recurrence API key, ``_FILE`` form first.

        Order (mirrors ``_check_juniper_data_api_key`` so Docker-secrets /
        k8s-secrets mounts work without leaking the value through env dumps):

          1. ``JUNIPER_CANOPY_RECURRENCE_API_KEY_FILE`` → file content, or
             ``JUNIPER_CANOPY_RECURRENCE_API_KEY`` direct (prefixed canonical —
             a canopy-specific override deploy can route separately).
          2. ``JUNIPER_RECURRENCE_API_KEY_FILE`` → file content, or
             ``JUNIPER_RECURRENCE_API_KEY`` direct (shared cross-service var the
             recurrence service itself reads).
          3. ``v`` (whatever pydantic-settings already populated; usually
             ``None`` once we've reached this branch).
        """
        prefixed = get_secret("JUNIPER_CANOPY_RECURRENCE_API_KEY")
        if prefixed:
            return prefixed
        shared = get_secret("JUNIPER_RECURRENCE_API_KEY")
        if shared:
            return shared
        return v

    @field_validator("backend_path", mode="before")
    @classmethod
    def _check_legacy_backend_path(cls, v):
        if os.getenv("JUNIPER_CANOPY_BACKEND_PATH") is not None:
            return v
        legacy = os.getenv("CASCOR_BACKEND_PATH")
        if legacy is not None:
            warnings.warn(
                "CASCOR_BACKEND_PATH is deprecated. Use JUNIPER_CANOPY_BACKEND_PATH instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            return legacy
        return v

    @field_validator("log_level", mode="before")
    @classmethod
    def _check_legacy_log_level(cls, v):
        if os.getenv("JUNIPER_CANOPY_LOG_LEVEL") is not None:
            return v
        legacy = os.getenv("CASCOR_LOG_LEVEL")
        if legacy is not None:
            warnings.warn(
                "CASCOR_LOG_LEVEL is deprecated. Use JUNIPER_CANOPY_LOG_LEVEL instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            return legacy
        return v

    @field_validator("demo_update_interval", mode="before")
    @classmethod
    def _check_legacy_demo_update_interval(cls, v):
        if os.getenv("JUNIPER_CANOPY_DEMO_UPDATE_INTERVAL") is not None:
            return v
        legacy = os.getenv("CASCOR_DEMO_UPDATE_INTERVAL")
        if legacy is not None:
            warnings.warn(
                "CASCOR_DEMO_UPDATE_INTERVAL is deprecated. Use JUNIPER_CANOPY_DEMO_UPDATE_INTERVAL instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            try:
                return float(legacy)
            except (ValueError, TypeError):
                warnings.warn(
                    f"Invalid CASCOR_DEMO_UPDATE_INTERVAL value: {legacy!r}, using default.",
                    UserWarning,
                    stacklevel=2,
                )
                return v
        return v

    @field_validator("demo_cascade_every", mode="before")
    @classmethod
    def _check_legacy_demo_cascade_every(cls, v):
        if os.getenv("JUNIPER_CANOPY_DEMO_CASCADE_EVERY") is not None:
            return v
        legacy = os.getenv("CASCOR_DEMO_CASCADE_EVERY")
        if legacy is not None:
            warnings.warn(
                "CASCOR_DEMO_CASCADE_EVERY is deprecated. Use JUNIPER_CANOPY_DEMO_CASCADE_EVERY instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            try:
                return int(legacy)
            except (ValueError, TypeError):
                warnings.warn(
                    f"Invalid CASCOR_DEMO_CASCADE_EVERY value: {legacy!r}, using default.",
                    UserWarning,
                    stacklevel=2,
                )
                return v
        return v

    @field_validator("log_format", mode="before")
    @classmethod
    def _check_legacy_log_format(cls, v):
        if os.getenv("JUNIPER_CANOPY_LOG_FORMAT") is not None:
            return v
        legacy = os.getenv("CANOPY_LOG_FORMAT")
        if legacy is not None:
            warnings.warn(
                "CANOPY_LOG_FORMAT is deprecated. Use JUNIPER_CANOPY_LOG_FORMAT instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            return legacy
        return v

    @field_validator("sentry_dsn", mode="before")
    @classmethod
    def _check_legacy_sentry_dsn(cls, v):
        if os.getenv("JUNIPER_CANOPY_SENTRY_DSN") is not None:
            return v
        legacy = os.getenv("CANOPY_SENTRY_DSN")
        if legacy is not None:
            warnings.warn(
                "CANOPY_SENTRY_DSN is deprecated. Use JUNIPER_CANOPY_SENTRY_DSN instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            return legacy
        return v

    # ── Backward-compatible methods ────────────────────────────────────

    def get_training_defaults(self) -> dict:
        """Backward-compatible method matching ConfigManager.get_training_defaults()."""
        return {
            "epochs": self.training.epochs.default,
            "learning_rate": self.training.learning_rate.default,
            "hidden_units": self.training.hidden_units.default,
            "max_iterations": self.training.max_iterations.default,
            "preset_epochs": self.training.preset_epochs.default,
        }

    def validate_training_param(self, param: str, value: float) -> bool:
        """Backward-compatible validation matching ConfigManager.validate_training_param_value()."""
        config = getattr(self.training, param, None)
        if config is None:
            return False
        return bool(config.min <= value <= config.max)

    def get_training_param_config(self, param: str) -> dict:
        """Get training parameter config as dict (backward-compatible)."""
        config = getattr(self.training, param, None)
        if config is None:
            raise KeyError(f"Training parameter {param!r} not found")
        return {
            "min": config.min,
            "max": config.max,
            "default": config.default,
            "modifiable_during_training": config.modifiable_during_training,
        }


@lru_cache
def get_settings() -> Settings:
    """Get cached Settings instance. Call get_settings.cache_clear() to reset."""
    return Settings()
