#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       0.8.0
# File Name:     main.py
# File Path:     ${HOME}/Development/python/Juniper/juniper-canopy/src/
#
# Date Created:  2025-10-11
# Last Modified: 2026-01-09
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#     This file contains the Main function to monitor the current Cascade Correlation Neural Network prototype
#     including training, state, and architecture with the Juniper prototype Frontend for monitoring and diagnostics.
#
#####################################################################################################################################################################################################
# Notes:
#     Main Application Entry Point
#     FastAPI application with Dash integration for Juniper Canopy monitoring.
#
#####################################################################################################################################################################################################
# References:
#
#####################################################################################################################################################################################################
# TODO :
#     Force pre-commit checks to run
#
#####################################################################################################################################################################################################
# COMPLETED:
#
#####################################################################################################################################################################################################
import asyncio
import importlib.metadata
import ipaddress
import json
import os
import re
import secrets
import socket

# import sys
import time
import uuid
from collections import deque
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlsplit

import uvicorn
from a2wsgi import WSGIMiddleware

# from fastapi.staticfiles import StaticFiles
from fastapi import Depends, FastAPI, File, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.requests import Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field, SecretStr

# from backend.data_adapter import DataAdapter  trunk-ignore(ruff/E402)
# from backend.training_monitor import TrainingMonitor  trunk-ignore(ruff/E402)
from backend.training_monitor import TrainingState  # trunk-ignore(ruff/E402)
from canopy_constants import BackendConstants, TrainingConstants  # trunk-ignore(ruff/E402)
from communication.websocket_manager import create_command_response_message, websocket_manager
from frontend.dashboard_manager import DashboardManager
from health import DependencyStatus, ErrorResponse, ReadinessResponse, probe_dependency

# import logging
from logger.logger import (  # LogContext,; Alert,; ColoredFormatter,; JsonFormatter,; CascorLogger,; TrainingLogger,
    get_system_logger,
    get_training_logger,
    get_ui_logger,
)
from observability import (
    RequestIdMiddleware,
    configure_logging,
    configure_sentry,
    get_prometheus_app,
    set_build_info,
    set_demo_mode_active,
)
from provenance import build_date as provenance_build_date
from provenance import git_sha as provenance_git_sha
from secrets_util import get_secret
from settings import get_settings

# import dash
# from dash import html, dcc


# Initialize configuration
settings = get_settings()

# SEC-F27: overlay any uvicorn CLI --host/--port onto settings so the SEC-F22 bind
# guard (in lifespan) evaluates the real bind even when canopy is launched via
# `uvicorn main:app --host ...` rather than `python main.py` (no-op for the latter).
# juniper-ml notes/JUNIPER_2026-07-06_JUNIPER-ECOSYSTEM_LAUNCH-PATH-BIND-AUDIT.md (SEC-F27).
from security import settings_with_uvicorn_cli_bind

settings = settings_with_uvicorn_cli_bind(settings)

# Application version from package metadata
try:
    APP_VERSION = importlib.metadata.version("juniper-canopy")
except importlib.metadata.PackageNotFoundError:
    APP_VERSION = "0.5.0"

# Initialize loggers
system_logger = get_system_logger()
training_logger = get_training_logger()
ui_logger = get_ui_logger()

# Event loop holder for thread-safe async scheduling from training callbacks
loop_holder = {"loop": None}

# Global state tracking
juniper_data_available = False
training_state = TrainingState()  # Global TrainingState instance

# Phase D §S10.1: per-command budgets for /ws/control. Seeded from the
# pydantic settings at import time but kept as a plain dict so tests can
# monkeypatch individual entries without fighting BaseModel's __setattr__.
_PHASE_D_CONTROL_TIMEOUTS: dict[str, float] = {
    "start": settings.ws_control_start_timeout,
    "stop": settings.ws_control_stop_timeout,
    "pause": settings.ws_control_stop_timeout,
    "resume": settings.ws_control_stop_timeout,
    "reset": settings.ws_control_stop_timeout,
    "set_params": settings.ws_control_set_params_timeout,
}


async def _websocket_keepalive_loop(interval: float, channel: str = "training") -> None:
    """Server side of the Phase F WebSocket heartbeat.

    The browser client already replies to ``{"type": "ping"}`` with a pong
    (``assets/websocket_client.js``), and the ``/ws/training`` receive loop
    resets its idle timer on *any* inbound frame. Nothing, however, ever sent
    the server ping, so a quiet-but-healthy training stream idled out after
    ``idle_timeout_seconds`` and the client flapped Connected→Reconnecting.

    This loop pings every ``interval`` seconds (< the idle timeout), scoped to
    ``channel="training"`` because ``/ws/control`` has no idle timeout, so it
    needs no keepalive. (``/ws/control`` now also accepts an inbound pong as a
    no-op, so extending the heartbeat to it later would be safe.)
    """
    while True:
        await asyncio.sleep(interval)
        try:
            await websocket_manager.broadcast_ping(channel=channel)
        except Exception as exc:  # a transient send error must not kill the heartbeat
            system_logger.debug("WebSocket keepalive ping failed: %s", exc)


def _seed_training_state(backend: Any) -> None:
    """Seed the global ``training_state`` from a freshly-initialized backend.

    The per-backend-type seeding shared by application startup (``lifespan``) and the A1-iv-2
    runtime model swap (``_swap_backend``), kept in one place so the two never drift:

    - demo: copy the demo simulation's current state.
    - service (cascor): pull ``get_synced_state()`` and register the relay state-update
      callback so live per-epoch updates keep ``training_state`` current.
    - recurrence (one-shot LMU): seed the binary idle/phase baseline from ``get_status()``
      (no live stream, no callback).
    """
    if backend.backend_type == "demo" and hasattr(backend, "_demo"):
        demo = backend._demo
        if demo.training_state:
            demo_state = demo.training_state.get_state()
            training_state.update_state(**demo_state)
            system_logger.info(
                "Global training_state synced with demo defaults: LR=%s, MaxHidden=%s, Epochs=%s",
                demo_state.get("learning_rate"),
                demo_state.get("max_hidden_units"),
                demo_state.get("max_epochs"),
            )
    elif backend.backend_type == "service":
        synced = backend.get_synced_state()
        if synced:
            training_state.update_state(
                status=synced.status,
                phase=synced.phase,
                current_epoch=synced.current_epoch,
                max_epochs=synced.max_epochs,
                learning_rate=synced.params.get("learning_rate", training_state.get_state().get("learning_rate")),
                max_hidden_units=synced.params.get("max_hidden_units", training_state.get_state().get("max_hidden_units")),
                **synced.progress_fields,
            )
            system_logger.info(
                "Global training_state synced with cascor: status=%s, epoch=%s, params=%s keys",
                synced.status,
                synced.current_epoch,
                len(synced.params),
            )
        # Register callback so relay-driven state updates keep training_state current
        backend.set_state_update_callback(training_state.update_state)
    elif backend.backend_type == "recurrence":
        # Recurrence (one-shot LMU) has no live training stream and no
        # ``set_state_update_callback`` — the dashboard reads its binary status by
        # polling ``get_status()``. Seed ``training_state`` from the backend's initial
        # status so the dashboard boots to a consistent idle baseline (A1-iii-a).
        initial_status = backend.get_status()
        training_state.update_state(
            status=initial_status.get("fsm_status", "idle"),
            phase=initial_status.get("phase", "idle"),
        )
        system_logger.info("Global training_state seeded for recurrence (one-shot) backend: %s", initial_status.get("fsm_status", "idle"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup — observability
    configure_logging(settings.log_level, settings.log_format, "juniper-canopy")
    configure_sentry(settings.sentry_dsn, "juniper-canopy", APP_VERSION, settings.sentry_traces_sample_rate)
    if settings.metrics_enabled:
        set_build_info("juniper_canopy", APP_VERSION, git_sha=provenance_git_sha(), build_date=provenance_build_date())

    # E-8: boot-time dependency-floor self-check. Fail loud here -- before backend
    # init / binding -- if any installed juniper-* wheel is below canopy's declared
    # floor, instead of serving on a stale wheel (the "green tests / dead app" class
    # from the canopy incident). Reads canopy's own Requires-Dist floors from the
    # installed distribution metadata; raises DependencyFloorError (uvicorn startup
    # fails) on a violation. Bypass with JUNIPER_SKIP_DEP_FLOOR_CHECK=1 (logged
    # loudly). The automatic prevention companion to ``make check-env`` (E-2).
    from juniper_service_core import enforce_dependency_floors

    enforce_dependency_floors(distribution="juniper-canopy", logger=system_logger)

    # SEC-F01 (HO-2): boot-time auth-posture self-check, the security companion to
    # the floor check above. An empty/placeholder CANOPY_API_KEY secret silently
    # disables APIKeyAuth (security.py computes ``[api_key] if api_key else None``)
    # and canopy serves its control surface OPEN behind a healthy health check.
    # Surface that posture loudly at boot. The intended posture comes from
    # JUNIPER_CANOPY_REQUIRE_AUTH (settings.require_auth; default false): false =
    # loud WARNING only (bare/dev profile), true = a missing/placeholder key is a
    # boot FAILURE (CRITICAL + AuthPostureError) — set true wherever secrets are
    # provisioned (the composed juniper-deploy stack). Bypass with
    # JUNIPER_SKIP_AUTH_POSTURE_CHECK=1 (logged loudly).
    from juniper_service_core import enforce_auth_posture

    from secrets_util import get_secret

    _canopy_api_key = get_secret("CANOPY_API_KEY")
    enforce_auth_posture(
        [_canopy_api_key] if _canopy_api_key else [],
        require_auth=settings.require_auth,
        service_name="juniper-canopy",
        logger=system_logger,
    )

    # D2 (SEC-F22): loopback bind-guard. Fail loud + closed here -- before
    # backend init / serving -- when canopy is configured to bind a non-loopback
    # interface with NEITHER bind-posture attestation set, instead of silently
    # exposing the in-network-bypassable browser training-control surface (audit
    # HO-6). Either attestation (loopback-publish OR auth-proxy) permits the bind;
    # loopback binds (the default) start regardless. Implemented inline in canopy
    # (no new dependency). Design-of-record: juniper-ml
    # notes/JUNIPER_CANOPY_CONTROL_SURFACE_AUTH_AND_NAT_DESIGN_2026-07-03.md §4 / §8 D2.
    from security import enforce_loopback_bind_guard

    enforce_loopback_bind_guard(
        settings.server.host,
        loopback_publish_attested=settings.loopback_publish_attested,
        auth_proxy_attested=settings.auth_proxy_attested,
        logger=system_logger,
    )

    system_logger.info("Starting Juniper Canopy application")
    system_logger.info("Settings: server=%s:%s, demo=%s", settings.server.host, settings.server.port, settings.demo_mode)

    # Capture the running event loop for thread-safe async scheduling
    loop_holder["loop"] = asyncio.get_running_loop()
    system_logger.info("Event loop captured for thread-safe broadcasting")

    # Set event loop on websocket_manager for thread-safe broadcasting
    websocket_manager.set_event_loop(loop_holder["loop"])

    # Initialize backend via factory
    global backend, training_state

    from backend import create_backend
    from discovery import discover_cascor

    # Auto-discover a running cascor instance if no URL is explicitly configured
    # and demo mode is not forced.
    discovered_url = None
    if not settings.demo_mode and not settings.cascor_service_url:
        if settings.cascor_discovery.enabled:
            discovered_url = await discover_cascor(
                host=settings.cascor_discovery.host,
                ports=settings.cascor_discovery.ports,
                timeout=settings.cascor_discovery.timeout_seconds,
            )
            if discovered_url:
                system_logger.info("Auto-discovered cascor at %s — activating service mode", discovered_url)

    backend = create_backend(service_url=discovered_url)

    # Validate JuniperData URL — mandatory for both demo and real backend (CAN-INT-002).
    juniper_data_url = settings.juniper_data_url
    # Propagate to env so downstream code (backend factory, etc.) can read it
    os.environ.setdefault("JUNIPER_DATA_URL", juniper_data_url)

    # CAN-HIGH-001: Probe upstream services at startup using standardized probe.
    global juniper_data_available
    data_probe = await probe_dependency("JuniperData", f"{juniper_data_url.rstrip('/')}/v1/health/live")
    if data_probe.status == "healthy":
        juniper_data_available = True
        system_logger.info("JuniperData reachable at %s (%.1fms)", juniper_data_url, data_probe.latency_ms)
    else:
        system_logger.warning("JuniperData unreachable at %s: %s", juniper_data_url, data_probe.message)

    # Probe JuniperCascor at startup (service mode only) — fallback to demo on failure.
    backend_initialized = False
    cascor_url = settings.cascor_service_url
    if cascor_url and backend.backend_type == "service":
        cascor_probe = await probe_dependency("JuniperCascor", f"{cascor_url.rstrip('/')}/v1/health/live")
        if cascor_probe.status == "healthy":
            system_logger.info("JuniperCascor reachable at %s (%.1fms)", cascor_url, cascor_probe.latency_ms)
        else:
            system_logger.warning("JuniperCascor unreachable at %s — falling back to demo mode", cascor_url)
            await backend.shutdown()
            from backend import create_backend

            backend = create_backend(demo_mode=True)
            await backend.initialize()
            backend_initialized = True

    # Initialize the backend (demo: starts simulation; service: connects to CasCor)
    if not backend_initialized:
        await backend.initialize()

    # A1-iv-2: remember the service URL the default backend resolved to (auto-discovered or
    # configured) so a later swap back from the recurrence model re-creates the SAME cascor
    # backend instead of silently falling to demo when the URL was discovered, not in settings.
    global _resolved_service_url
    _resolved_service_url = (discovered_url or settings.cascor_service_url) if backend.backend_type == "service" else None

    # Sync global training_state from the freshly-initialized backend. Shared with the A1-iv-2
    # runtime model swap (``_swap_backend``) so the per-backend-type seeding logic lives in
    # exactly one place and cannot drift between startup and a live model switch.
    _seed_training_state(backend)

    system_logger.info("Backend initialized: %s", backend.backend_type)
    # METRICS-MON R3.2 / seed-11: reflect the post-fallback backend type in
    # the ``juniper_canopy_demo_mode_active`` gauge. This is the single
    # source of truth — the cascor-unreachable fallback above may flip the
    # backend from "service" to "demo" before we get here, so reading
    # ``settings.demo_mode`` directly would lie about the live state.
    set_demo_mode_active(backend.backend_type == "demo")

    # Phase F heartbeat (server side): the browser client already pongs to
    # server pings, but nothing was sending them, so a quiet but healthy
    # /ws/training stream idled out after idle_timeout_seconds and the client
    # flapped Connected→Reconnecting. Start the keepalive pinger now and cancel
    # it on shutdown. Scoped to the training channel (control has no idle
    # timeout). Interval comes from the existing (previously dormant)
    # websocket.heartbeat_interval setting.
    keepalive_interval = websocket_manager.heartbeat_interval
    keepalive_task: Optional[asyncio.Task] = None
    if keepalive_interval and keepalive_interval > 0:
        keepalive_task = asyncio.create_task(_websocket_keepalive_loop(keepalive_interval), name="ws-keepalive")
        system_logger.info("WebSocket keepalive heartbeat started (interval=%ss, channel=training)", keepalive_interval)
    else:
        system_logger.info("WebSocket keepalive heartbeat disabled (heartbeat_interval=%s)", keepalive_interval)

    system_logger.info("Application startup complete")

    yield

    # Shutdown
    system_logger.info("Shutting down Juniper Canopy application")

    # Stop the keepalive heartbeat before tearing down connections.
    if keepalive_task is not None:
        keepalive_task.cancel()
        with suppress(asyncio.CancelledError):
            await keepalive_task

    await backend.shutdown()

    # Shutdown WebSocket connections
    await websocket_manager.shutdown()

    system_logger.info("Application shutdown complete")


# Disable interactive API docs when authentication is enabled (production).
_docs_enabled = not get_secret("CANOPY_API_KEY")
# Initialize FastAPI
app = FastAPI(
    title="Juniper Canopy",
    version=APP_VERSION,
    description="Real-time monitoring for CasCor networks",
    lifespan=lifespan,
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    openapi_url="/openapi.json" if _docs_enabled else None,
)

# CORS: only enable when origins are explicitly configured.
if settings.cors_origins:
    allow_credentials = bool(settings.cors_origins) and "*" not in settings.cors_origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=allow_credentials,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["X-API-Key", "Content-Type", "Accept"],
    )

# Security headers (outermost — runs on every response)
from middleware import RequestBodyLimitMiddleware, SecurityHeadersMiddleware, SecurityMiddleware
from security import browser_origin_allowed, get_api_key_auth, get_rate_limiter, require_browser_control_auth

app.add_middleware(RequestBodyLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

api_key_auth = get_api_key_auth()
rate_limiter = get_rate_limiter()
app.add_middleware(SecurityMiddleware, api_key_auth=api_key_auth, rate_limiter=rate_limiter)

# Phase B-pre-b: SessionMiddleware for CSRF token management (M-SEC-02)
from starlette.middleware.sessions import SessionMiddleware

_session_secret = settings.session_secret_key or secrets.token_urlsafe(32)
app.add_middleware(
    SessionMiddleware,
    secret_key=_session_secret,
    session_cookie="canopy_session",
    max_age=settings.csrf_token_ttl_seconds,
    same_site="strict",
    https_only=False,  # Allow HTTP in dev; HTTPS enforced by reverse proxy in prod
    path="/",
)

# Observability middleware (LIFO: last added runs OUTERMOST).
#
# OBS-WIRE C.1: order matters — starlette is LIFO, so whatever is added
# LAST runs OUTERMOST. ``RequestIdMiddleware`` MUST be added LAST so it
# runs OUTERMOST and the ``request_id`` contextvar is set BEFORE
# ``PrometheusMiddleware`` records the request (otherwise structured
# logs emitted from inside the metrics path see request_id=None).
# Matches the canonical pattern in juniper-data
# (juniper_data/api/app.py) and juniper-cascor (src/api/app.py).
if settings.metrics_enabled:
    from juniper_observability import MetricsAuthMiddleware

    from observability import PrometheusMiddleware

    app.add_middleware(PrometheusMiddleware, service_name="juniper-canopy", namespace="juniper_canopy")
    # SEC-16 parity with juniper-data + juniper-cascor: wrap the
    # Prometheus ASGI sub-app in ``MetricsAuthMiddleware`` so untrusted
    # IPs get 403 instead of an open ``/metrics`` surface. The exempt
    # path prefix in ``SecurityConstants.EXEMPT_PATH_PREFIXES`` already
    # bypasses canopy's ``SecurityMiddleware`` for ``/metrics`` — the
    # allowlist is the only gate, so ``settings.metrics_trusted_ips``
    # is the source of truth.
    app.mount("/metrics", MetricsAuthMiddleware(get_prometheus_app(), settings.metrics_trusted_ips))
app.add_middleware(RequestIdMiddleware)


# Global exception handler for unhandled errors — returns standardized ErrorResponse.
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all handler returning a consistent JSON error shape."""
    system_logger.error("Unhandled exception on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    body = ErrorResponse(error="Internal server error", detail="An unexpected error occurred.", status_code=500)
    return JSONResponse(body.model_dump(), status_code=500)


# Backend is initialized in lifespan via create_backend() factory
backend = None
# A1-iv-2: the currently-selected model key driving the live ``backend`` (None = the
# cascor/demo startup default) and the service URL that default resolved to. Both are set by
# the lifespan + ``_swap_backend`` so a runtime model switch can faithfully re-create either
# backend (D5: re-create, not multiplex).
current_nn_model: Optional[str] = None
_resolved_service_url: Optional[str] = None

# Initialize Dash dashboard (standalone with its own Flask server)
dashboard_manager = DashboardManager({})

# Mount Dash's Flask server to FastAPI using WSGIMiddleware
# This allows ASGI FastAPI to serve WSGI Dash application
app.mount("/dashboard", WSGIMiddleware(dashboard_manager.app.server))

# Get Dash app instance for reference
dash_app = dashboard_manager.app


def schedule_broadcast(coroutine):
    """
    Schedule coroutine on FastAPI's event loop from any thread.
    This allows synchronous training code to trigger async broadcasts
    without blocking or requiring async/await syntax.

    Args:
        coroutine: Async coroutine to schedule
    """
    if loop_holder["loop"] and not loop_holder["loop"].is_closed():
        try:
            asyncio.run_coroutine_threadsafe(coroutine, loop_holder["loop"])
        except Exception as e:
            system_logger.error("Failed to schedule broadcast: %s", e)
    else:
        coroutine.close()
        system_logger.warning("Event loop not available for broadcasting")


@app.get("/")
async def root():
    """
    Root endpoint - redirects to dashboard.
    Returns:
        Redirect response to /dashboard/
    """
    return RedirectResponse(url="/dashboard/")


# ── Phase B-pre-b: CSRF token endpoint (M-SEC-02) ────────────────────

from csrf import get_csrf_store


@app.get("/api/csrf")
async def api_csrf_token(request: Request):
    """Mint a CSRF token for WebSocket control-path authentication.

    The token is stored server-side with a 1h sliding TTL and must be
    sent as the first frame after /ws/control connection is accepted.

    PR-1 hardening (§6): the route is key-exempt (``KEY_EXEMPT_PATHS``) so the
    same-origin browser can fetch a token. Minting is refused only for an
    explicit **disallowed** ``Origin`` (a cross-origin page) when auth is enabled;
    a *missing* Origin is the normal same-origin GET — browsers omit the Origin
    header on same-origin GETs (they send ``sec-fetch-site: same-origin`` instead)
    — and is allowed, as are keyed callers. In open/dev mode (no key configured)
    it stays anonymously mintable. This blocks an off-origin browser token oracle
    without breaking the same-origin bootstrap.
    """
    from fastapi import HTTPException

    _key = request.headers.get("X-API-Key")
    _keyed = bool(_key is not None and api_key_auth.validate(_key))
    # Reject only an Origin that is PRESENT and not allowlisted (an explicit
    # cross-origin request). A MISSING Origin is the same-origin browser bootstrap
    # (the dashboard's page-load GET /api/csrf) and must be allowed, else
    # window.__canopy_csrf never populates and the whole browser control surface
    # 403s. The state-changing /api/train/* POSTs stay fail-closed on Origin
    # (browsers do send Origin on POST), so this relaxation is scoped to minting.
    _origin = request.headers.get("origin")
    if api_key_auth.enabled and not _keyed and _origin is not None and not browser_origin_allowed(request):
        raise HTTPException(status_code=403, detail="Origin not allowed.")

    if not settings.csrf_enabled:
        return {"csrf_token": "", "enabled": False}  # nosec B105 — empty token when CSRF disabled
    store = get_csrf_store(ttl_seconds=settings.csrf_token_ttl_seconds)
    token = store.mint()
    return {"csrf_token": token, "enabled": True}


async def _authenticate_websocket(websocket: WebSocket, allow_browser_auth: bool = False) -> bool:
    """Authenticate WebSocket connection using X-API-Key header.

    BaseHTTPMiddleware does not intercept WebSocket upgrades, so
    authentication must be performed explicitly at connection accept.

    PR-1 (Start-Training 401 fix): when ``allow_browser_auth`` is True, an
    *absent* key is accepted so the downstream Origin gate (and, on
    ``/ws/control``, the CSRF first-frame) becomes the real authn for the
    same-origin browser, which cannot hold the server key. A *present* key is
    still validated, so keyed callers — and a bad key — are unaffected (no
    regression). When ``allow_browser_auth`` is False the legacy behaviour
    holds: any keyless connection is closed 4001.

    Returns True if authenticated (or auth disabled), False otherwise.
    """
    if api_key_auth.enabled:
        key = websocket.headers.get("X-API-Key") or websocket.query_params.get("api_key")
        if allow_browser_auth and key is None:
            return True
        if not api_key_auth.validate(key):
            await websocket.close(code=4001, reason="Authentication required")
            return False
    return True


WS_BEARER_SUBPROTOCOL = "bearer"


async def _authenticate_websocket_token(websocket: WebSocket) -> tuple[bool, str | None]:
    """SEC-06 opt-in bearer-token auth over ``Sec-WebSocket-Protocol``.

    When ``settings.ws_auth_enabled`` is False, this is a no-op that returns
    ``(True, None)`` so the caller proceeds with the legacy header-based
    ``_authenticate_websocket`` flow. When enabled, the client must send
    ``Sec-WebSocket-Protocol: bearer, <token>``; the token is validated
    against ``api_key_auth`` using constant-time comparison. On success the
    caller must echo ``"bearer"`` as the accepted subprotocol. On failure
    the WebSocket is closed with code 1008 and the caller should return.

    Returns:
        (authenticated, subprotocol_to_echo). ``subprotocol_to_echo`` is
        ``"bearer"`` on success when auth is enabled, ``None`` when disabled
        (preserves prior unauthenticated default for legacy clients).
    """
    if not getattr(settings, "ws_auth_enabled", False):
        return True, None

    header = websocket.headers.get("sec-websocket-protocol", "")
    parts = [p.strip() for p in header.split(",") if p.strip()]
    if len(parts) < 2 or parts[0].lower() != WS_BEARER_SUBPROTOCOL:
        await websocket.close(code=1008, reason="Authentication required")
        return False, None

    token = parts[1]
    if not api_key_auth.validate(token):
        await websocket.close(code=1008, reason="Invalid authentication token")
        return False, None

    return True, WS_BEARER_SUBPROTOCOL


@app.websocket("/ws/training")
async def websocket_training_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time training metrics.
    Handles:
    - Training progress updates
    - Metrics broadcasting
    - Phase notifications
    - Real-time data streaming
    Example client connection:
        ws = new WebSocket('ws://localhost:8050/ws/training');
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log('Received:', data.type);
        };
    """
    # PR-1 (C5): read-only metric stream — relax the key gate so the keyless
    # same-origin browser is admitted by the Origin gate below (no state to
    # forge, no CSRF frame). A present key is still validated.
    if not await _authenticate_websocket(websocket, allow_browser_auth=True):
        return

    # SEC-06: opt-in bearer-token auth over Sec-WebSocket-Protocol
    ws_auth_ok, ws_subprotocol = await _authenticate_websocket_token(websocket)
    if not ws_auth_ok:
        return

    # Phase B-pre-a: Origin validation (M-SEC-01b)
    from ws_security import validate_origin

    ws_settings = settings.websocket
    if ws_settings.allowed_origins:
        if not validate_origin(websocket, ws_settings.allowed_origins):
            from audit_log import log_ws_origin_rejected

            origin = websocket.headers.get("origin", "")
            client_ip = websocket.client[0] if websocket.client else "unknown"
            log_ws_origin_rejected("/ws/training", client_ip, origin)
            await websocket.close(code=4003, reason="Origin not allowed")
            return

    # SEC-F19 / D4: per-IP cap (M-SEC-04; DoS-dampening, INERT BEHIND NAT --
    # every client behind Docker NAT shares the bridge-gateway IP) + per-session
    # cap keyed on the anonymous canopy_session cookie (restores per-client
    # fairness under a shared NAT IP). The global cap
    # (websocket_manager.max_connections, enforced in connect()) bounds total
    # load + backstops cookieless connections. Over-cap -> close 1013.
    if not websocket_manager.check_connection_limits(
        websocket,
        max_per_ip=ws_settings.max_connections_per_ip,
        max_per_session=ws_settings.max_connections_per_session,
    ):
        await websocket.close(code=1013, reason="Per-IP connection limit reached")
        return

    client_id = f"training-client-{id(websocket)}"
    # OBS-WIRE A.4: pass channel="training" so connect/disconnect updates
    # juniper_canopy_websocket_connections_active{channel="training"} and
    # outbound dispatch labels juniper_canopy_websocket_messages_total{...}.
    try:
        connected = await websocket_manager.connect(websocket, client_id=client_id, subprotocol=ws_subprotocol, channel="training")
    except Exception:
        websocket_manager.release_connection_limits(websocket)
        raise
    if not connected:
        websocket_manager.release_connection_limits(websocket)
        return

    idle_timeout = ws_settings.idle_timeout_seconds
    max_msg_size = ws_settings.max_message_size_training

    try:
        # Send initial status
        status = backend.get_status()

        await websocket_manager.send_personal_message({"type": "initial_status", "data": status}, websocket)

        # Send a properly formatted state message so clients receive current state immediately
        # Use TrainingState.get_state() for standardized field names (status, phase, learning_rate, etc.)
        state_data = training_state.get_state() if training_state else status
        await websocket_manager.send_personal_message({"type": "state", "timestamp": time.time(), "data": state_data}, websocket)

        # Message handling loop (with idle timeout)
        while True:
            try:
                if idle_timeout and idle_timeout > 0:
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=idle_timeout)
                else:
                    data = await websocket.receive_text()

                if len(data) > max_msg_size:
                    await websocket_manager.send_personal_message({"ok": False, "error": "Message too large"}, websocket)
                    continue

                message = json.loads(data) if isinstance(data, str) else data

                # Handle ping/pong
                if message.get("type") == "ping":
                    await websocket_manager.send_personal_message({"type": "pong"}, websocket)
                # Handle other messages as needed
                else:
                    system_logger.debug("Received message: %s", message.get("type"))

            except asyncio.TimeoutError:
                system_logger.info("WebSocket idle timeout (%ss), closing: %s", idle_timeout, client_id)
                await websocket.close(code=1000, reason="Idle timeout")
                break
            except WebSocketDisconnect:
                system_logger.info("Client disconnected: %s", client_id)
                break
            except Exception as e:
                system_logger.error("WebSocket error: %s", e)
                break

    finally:
        websocket_manager.disconnect(websocket)


def _recurrence_start_kwargs(payload: "dict | None") -> dict:
    """Extract a recurrence dataset-ref + LMU hyperparameters from a start payload (A1-iii-a).

    The one-shot recurrence ``start_training`` needs a dataset reference
    (``generator``/``name``/``dataset_id`` + ``params``/``split``) and optional
    ``d``/``theta``/``ridge``. ``payload`` is the REST ``/api/train/start`` body (as a dict)
    or the WS ``/ws/control`` ``start`` ``params`` dict. Returns ONLY the keys actually
    present, so cascor/demo (which never supply a payload) keep their bare
    ``start_training(reset=...)`` call unchanged.
    """
    kwargs: dict = {}
    if not payload:
        return kwargs
    dataset = payload.get("dataset") or {}
    for key in ("dataset_id", "name", "generator", "split"):
        if dataset.get(key) is not None:
            kwargs[key] = dataset[key]
    if dataset.get("params") is not None:
        kwargs["params"] = dataset["params"]
    for key in ("d", "theta", "ridge"):
        if payload.get(key) is not None:
            kwargs[key] = payload[key]
    return kwargs


@app.websocket("/ws/control")
async def websocket_control_endpoint(websocket: WebSocket):
    """WebSocket endpoint for training control commands.

    Phase B-pre-b security gates:
    1. API key authentication
    2. Origin validation (M-SEC-01b)
    3. Per-IP connection cap (M-SEC-04)
    4. CSRF first-frame auth (M-SEC-02) — 5s timeout → close 1008
    """
    # PR-1: relax the key gate for the same-origin browser — a keyless
    # connection defers to the Origin + CSRF first-frame gates below; a
    # present key is still validated (keyed callers unaffected).
    if not await _authenticate_websocket(websocket, allow_browser_auth=True):
        return

    # SEC-06: opt-in bearer-token auth over Sec-WebSocket-Protocol
    ws_auth_ok, ws_subprotocol = await _authenticate_websocket_token(websocket)
    if not ws_auth_ok:
        return

    # Phase B-pre-a: Origin validation (M-SEC-01b)
    from ws_security import validate_origin

    ws_settings = settings.websocket
    if ws_settings.allowed_origins:
        if not validate_origin(websocket, ws_settings.allowed_origins):
            from audit_log import log_ws_origin_rejected

            origin = websocket.headers.get("origin", "")
            client_ip = websocket.client[0] if websocket.client else "unknown"
            log_ws_origin_rejected("/ws/control", client_ip, origin)
            await websocket.close(code=4003, reason="Policy violation")  # M-SEC-06: opaque
            return

    # SEC-F19 / D4: per-IP cap (M-SEC-04; DoS-dampening, INERT BEHIND NAT) +
    # per-session cap keyed on the anonymous canopy_session cookie (per-client
    # fairness under a shared NAT IP); the global cap (connect()) backstops the
    # cookieless case. Over-cap -> close 1013 (opaque per M-SEC-06).
    if not websocket_manager.check_connection_limits(
        websocket,
        max_per_ip=ws_settings.max_connections_per_ip,
        max_per_session=ws_settings.max_connections_per_session,
    ):
        await websocket.close(code=1013, reason="Policy violation")  # M-SEC-06: opaque
        return

    client_id = f"control-client-{id(websocket)}"
    # OBS-WIRE A.4: pass channel="control" so connect/disconnect updates
    # juniper_canopy_websocket_connections_active{channel="control"} and
    # outbound dispatch labels juniper_canopy_websocket_messages_total{...}.
    try:
        connected = await websocket_manager.connect(websocket, client_id=client_id, subprotocol=ws_subprotocol, channel="control")
    except Exception:
        websocket_manager.release_connection_limits(websocket)
        raise
    if not connected:
        websocket_manager.release_connection_limits(websocket)
        return

    # Phase B-pre-b: CSRF first-frame authentication (M-SEC-02)
    if settings.csrf_enabled:
        from audit_log import log_ws_csrf_rejected

        client_ip = websocket.client[0] if websocket.client else "unknown"
        try:
            raw_auth = await asyncio.wait_for(
                websocket.receive_text(),
                timeout=settings.ws_control_auth_timeout,
            )
            auth_msg = json.loads(raw_auth)
            if auth_msg.get("type") != "auth" or not auth_msg.get("csrf_token"):
                log_ws_csrf_rejected("/ws/control", client_ip, "missing_or_invalid_frame")
                await websocket.close(code=1008, reason="Policy violation")
                return
            csrf_store = get_csrf_store()
            if not csrf_store.validate(auth_msg["csrf_token"]):
                log_ws_csrf_rejected("/ws/control", client_ip, "invalid_token")
                await websocket.close(code=1008, reason="Policy violation")
                return
        except asyncio.TimeoutError:
            log_ws_csrf_rejected("/ws/control", client_ip, "auth_timeout")
            await websocket.close(code=1008, reason="Policy violation")
            return
        except (json.JSONDecodeError, Exception):
            log_ws_csrf_rejected("/ws/control", client_ip, "malformed_auth")
            await websocket.close(code=1008, reason="Policy violation")
            return

    _valid_commands = {"start", "stop", "pause", "resume", "reset", "set_params"}
    max_msg_size = ws_settings.max_message_size_control

    # Phase D §S10.1: per-command timeouts — reads _PHASE_D_CONTROL_TIMEOUTS
    # each iteration so tests can patch the module-level dict to force
    # asyncio.wait_for to trip without mutating the pydantic Settings model.
    def _command_timeout(cmd: str) -> float:
        return _PHASE_D_CONTROL_TIMEOUTS.get(cmd, _PHASE_D_CONTROL_TIMEOUTS["stop"])

    def _execute_command(cmd: str, params: dict | None, reset: bool):  # noqa: ANN202
        """Blocking dispatch to the backend; runs in the thread pool.

        Return type is intentionally unannotated: backend methods have
        ``Any`` return types and the caller treats the result as "maybe a
        dict" when building the command_response envelope.
        """
        if cmd == "start":
            # A1-iii-a: forward a one-shot dataset-ref + hyperparameters for recurrence
            # (carried in the WS ``params``); cascor/demo keep the bare reset-only call.
            start_kwargs = _recurrence_start_kwargs(params) if backend.backend_type == "recurrence" else {}
            return backend.start_training(reset=reset, **start_kwargs)
        if cmd == "stop":
            return backend.stop_training()
        if cmd == "pause":
            return backend.pause_training()
        if cmd == "resume":
            return backend.resume_training()
        if cmd == "reset":
            return backend.reset_training()
        if cmd == "set_params":
            if not params:
                raise ValueError("set_params requires a 'params' dict")
            return backend.apply_params(**params)
        raise ValueError(f"Unhandled command: {cmd}")

    try:
        while True:
            data = await websocket.receive_text()

            if len(data) > max_msg_size:
                await websocket_manager.send_personal_message(
                    create_command_response_message("unknown", "error", error="Message too large"),
                    websocket,
                )
                continue

            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                await websocket_manager.send_personal_message(
                    create_command_response_message("unknown", "error", error="Invalid JSON"),
                    websocket,
                )
                continue

            # Phase F: respond to server heartbeat pings with pong
            if message.get("type") == "ping":
                await websocket_manager.send_personal_message({"type": "pong"}, websocket)
                continue

            # A client may send an unsolicited heartbeat pong (e.g. if the
            # server heartbeat is later extended to this channel — today it
            # only pings /ws/training). Accept it as a no-op instead of
            # mis-parsing it as an "Unknown command: " — a pong frame carries
            # no ``command`` key, so it would otherwise fall through to the
            # command dispatch below and return an error. Mirrors /ws/training,
            # which silently ignores non-ping frames.
            if message.get("type") == "pong":
                system_logger.debug("Received heartbeat pong on /ws/control")
                continue

            command = message.get("command", "")
            command_id = message.get("command_id")

            if command not in _valid_commands:
                await websocket_manager.send_personal_message(
                    create_command_response_message(
                        command,
                        "error",
                        command_id=command_id,
                        error=f"Unknown command: {command}",
                        code="unknown_command",
                    ),
                    websocket,
                )
                continue

            system_logger.info("Control command received: %s (backend=%s, id=%s)", command, backend.backend_type, command_id)

            timeout = _command_timeout(command)
            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(
                        _execute_command,
                        command,
                        message.get("params"),
                        message.get("reset", True),
                    ),
                    timeout=timeout,
                )
                failure = _control_result_failure(result)
                if failure is not None:
                    system_logger.warning("Command '%s' failed: %s", command, failure)
                    await websocket_manager.send_personal_message(
                        create_command_response_message(
                            command,
                            "error",
                            command_id=command_id,
                            data=result if isinstance(result, dict) else None,
                            error=failure,
                            code="command_failed",
                        ),
                        websocket,
                    )
                else:
                    await websocket_manager.send_personal_message(
                        create_command_response_message(
                            command,
                            "success",
                            command_id=command_id,
                            data=result if isinstance(result, dict) else None,
                        ),
                        websocket,
                    )
            except asyncio.TimeoutError:
                system_logger.error("Command '%s' timed out after %ss", command, timeout)
                await websocket_manager.send_personal_message(
                    create_command_response_message(
                        command,
                        "error",
                        command_id=command_id,
                        error=f"Command timed out after {timeout}s",
                    ),
                    websocket,
                )
            except Exception as e:
                system_logger.error("Command execution error: %s", e)
                await websocket_manager.send_personal_message(
                    create_command_response_message(
                        command,
                        "error",
                        command_id=command_id,
                        error="Command execution failed",
                    ),
                    websocket,
                )

    except WebSocketDisconnect:
        system_logger.info("Control client disconnected: %s", client_id)
    finally:
        websocket_manager.disconnect(websocket)


@app.get("/health", deprecated=True)
@app.get("/api/health", deprecated=True)
async def health_check_deprecated(request: Request):
    """Health check endpoint (deprecated — use /v1/health instead)."""
    system_logger.warning("Deprecated health endpoint %s called — use /v1/health, /v1/health/live, or /v1/health/ready instead", request.url.path)
    return {
        # API-01: align with cascor + juniper-data ("ok"). Canopy was the
        # only service returning "healthy"; the field is still present so
        # legacy clients see a non-empty status, just with the
        # ecosystem-standard value.
        "status": "ok",
        # API-02: shared {status, version, service} base across the three
        # Juniper services so cross-service monitoring tools can tell
        # health responses apart without inspecting the URL. The canopy-
        # specific fields below (timestamp, active_connections,
        # training_active, demo_mode, juniper_data_available) are
        # documented optional extras per Approach A guardrails and
        # remain unchanged for backward compat.
        "service": "juniper-canopy",
        "timestamp": time.time(),
        "version": APP_VERSION,
        "active_connections": websocket_manager.get_connection_count(),
        "training_active": backend.is_training_active(),
        "demo_mode": backend.backend_type == "demo",
        "juniper_data_available": juniper_data_available,
    }


@app.get("/v1/health")
async def health_check():
    """Combined health check endpoint.

    Response schema:

    - Shared API-02 base: ``status``, ``version``, ``service``
      (``"juniper-canopy"``) — matches juniper-data and juniper-cascor.
    - Canopy-specific optional extras (Approach A guardrails): ``timestamp``,
      ``active_connections``, ``training_active``, ``demo_mode``,
      ``juniper_data_available``.
    """
    return {
        # API-01: align with cascor + juniper-data ("ok").
        "status": "ok",
        # API-02: shared {status, version, service} base across services.
        "service": "juniper-canopy",
        "timestamp": time.time(),
        "version": APP_VERSION,
        "active_connections": websocket_manager.get_connection_count(),
        "training_active": backend.is_training_active(),
        "demo_mode": backend.backend_type == "demo",
        "juniper_data_available": juniper_data_available,
        # Build provenance (juniper-ml notes/BUILD_PROVENANCE_DESIGN_2026-06-14.md):
        # source git SHA + ISO-8601 build date baked into the image. ``None``
        # outside a provenance-stamped image; lets ``make doctor`` detect drift.
        "git_sha": provenance_git_sha(),
        "build_date": provenance_build_date(),
    }


@app.get("/v1/health/live")
async def liveness_probe():
    """Liveness probe — confirms the process is running."""
    return {"status": "alive"}


@app.get("/v1/health/ready", response_model=ReadinessResponse)
async def readiness_probe() -> ReadinessResponse:
    """Readiness probe with dependency health status.

    Probes JuniperData and JuniperCascor health endpoints and reports
    overall readiness with per-dependency status.
    """
    # Probe JuniperData
    data_url = settings.juniper_data_url
    data_dep = await probe_dependency("JuniperData Service", f"{data_url.rstrip('/')}/v1/health/live")

    # Probe JuniperCascor
    ready_cascor_url = settings.cascor_service_url
    if ready_cascor_url:
        cascor_dep = await probe_dependency("JuniperCascor Service", f"{ready_cascor_url.rstrip('/')}/v1/health/live")
    else:
        cascor_dep = DependencyStatus(
            name="JuniperCascor Service",
            status="not_configured",
            message="JUNIPER_CANOPY_CASCOR_SERVICE_URL not set (demo mode)",
        )

    dependencies = {"juniper_data": data_dep, "juniper_cascor": cascor_dep}

    overall = "ready"
    for dep in dependencies.values():
        if dep.status == "unhealthy":
            overall = "degraded"
            break

    return ReadinessResponse(
        status=overall,
        version=APP_VERSION,
        service="juniper-canopy",
        git_sha=provenance_git_sha(),
        build_date=provenance_build_date(),
        dependencies=dependencies,
        details={
            "mode": backend.backend_type,
            "active_connections": websocket_manager.get_connection_count(),
            "training_active": backend.is_training_active(),
        },
    )


@app.get("/api/state")
async def get_state():
    """
    Get current training state.
    Returns:
        TrainingState as JSON (includes convergence params from DemoMode when available)
    """
    # Return demo mode's live training state if available, otherwise global
    if backend.backend_type == "demo" and hasattr(backend, "_demo"):
        demo = backend._demo
        if demo.training_state:
            state = demo.training_state.get_state()
        else:
            state = training_state.get_state()
        # Merge demo-specific params from DemoMode (not stored in TrainingState)
        state["convergence_enabled"] = getattr(demo, "convergence_enabled", True)
        state["convergence_threshold"] = getattr(demo, "convergence_threshold", 0.001)
        state["spiral_rotations"] = getattr(demo, "spiral_rotations", 3.0)

        # ── Neural Network meta-parameters ──
        state["nn_max_iterations"] = getattr(demo, "nn_max_iterations", TrainingConstants.DEFAULT_MAX_GROWTH_ITERATIONS)
        state["nn_max_total_epochs"] = getattr(demo, "nn_max_total_epochs", TrainingConstants.DEFAULT_TRAINING_EPOCHS)
        state["nn_init_output_weights"] = getattr(demo, "nn_init_output_weights", TrainingConstants.DEFAULT_INIT_OUTPUT_WEIGHTS)
        state["nn_learning_rate"] = getattr(demo, "nn_learning_rate", TrainingConstants.DEFAULT_LEARNING_RATE)
        state["nn_max_hidden_units"] = getattr(demo, "nn_max_hidden_units", TrainingConstants.DEFAULT_MAX_HIDDEN_UNITS)
        state["nn_multi_node_layers"] = getattr(demo, "nn_multi_node_layers", TrainingConstants.DEFAULT_MULTI_NODE_LAYERS)
        state["nn_growth_trigger"] = getattr(demo, "nn_growth_trigger", TrainingConstants.DEFAULT_GROWTH_TRIGGER)
        state["nn_growth_preset_epochs"] = getattr(demo, "nn_growth_preset_epochs", TrainingConstants.DEFAULT_PRESET_EPOCHS)
        state["nn_growth_convergence_threshold"] = getattr(demo, "nn_growth_convergence_threshold", TrainingConstants.DEFAULT_CONVERGENCE_THRESHOLD)
        state["nn_patience"] = getattr(demo, "nn_patience", TrainingConstants.DEFAULT_PATIENCE)
        state["nn_spiral_rotations"] = getattr(demo, "nn_spiral_rotations", TrainingConstants.DEFAULT_SPIRAL_ROTATIONS)
        state["nn_spiral_number"] = getattr(demo, "nn_spiral_number", TrainingConstants.DEFAULT_SPIRAL_NUMBER)
        state["nn_dataset_elements"] = getattr(demo, "nn_dataset_elements", TrainingConstants.DEFAULT_DATASET_ELEMENTS)
        state["nn_dataset_noise"] = getattr(demo, "nn_dataset_noise", TrainingConstants.DEFAULT_DATASET_NOISE)

        # ── Candidate Node meta-parameters ──
        state["cn_pool_size"] = getattr(demo, "cn_pool_size", TrainingConstants.DEFAULT_CANDIDATE_POOL_SIZE)
        state["cn_correlation_threshold"] = getattr(demo, "cn_correlation_threshold", TrainingConstants.DEFAULT_CANDIDATE_CORRELATION_THRESHOLD)
        state["cn_selected_candidates"] = getattr(demo, "cn_selected_candidates", TrainingConstants.DEFAULT_SELECTED_CANDIDATES)
        state["cn_patience"] = getattr(demo, "cn_patience", TrainingConstants.DEFAULT_CN_PATIENCE)
        state["cn_training_complete"] = getattr(demo, "cn_training_complete", TrainingConstants.DEFAULT_CN_TRAINING_COMPLETE)
        state["cn_training_iterations"] = getattr(demo, "cn_training_iterations", TrainingConstants.DEFAULT_CANDIDATE_TRAINING_ITERATIONS)
        state["cn_training_convergence_threshold"] = getattr(demo, "cn_training_convergence_threshold", TrainingConstants.DEFAULT_CANDIDATE_CONVERGENCE_THRESHOLD)
        state["cn_multi_candidate"] = getattr(demo, "cn_multi_candidate", TrainingConstants.DEFAULT_MULTI_CANDIDATE_ENABLED)
        state["cn_candidate_selection"] = getattr(demo, "cn_candidate_selection", "top")
        state["cn_top_candidates"] = getattr(demo, "cn_top_candidates", TrainingConstants.DEFAULT_TOP_CANDIDATES_COUNT)
        state["cn_random_candidates"] = getattr(demo, "cn_random_candidates", TrainingConstants.DEFAULT_RANDOM_CANDIDATES_COUNT)

        return state

    # Service mode: provide all nn_*/cn_* keys the dashboard expects.
    # Keys that cascor exposes are fetched live; the rest get defaults.
    #
    # N2 (training-runtime defects plan §4 I-1): the BASE fields
    # (status/phase/current_epoch/timestamp) are now LIVE-FIRST. This route
    # already paid a live cascor call per GET for the parameter keys
    # (``get_canopy_params``) while serving base fields solely from the
    # relay-fed ``training_state`` global — which went ~8 h stale in the
    # 2026-07-10 session when the WS relay silently died. The base fields now
    # ride the same live-fetch posture (one consolidated ``get_status()``
    # call), and the relay-fed global is only the fallback on upstream error,
    # explicitly marked ``stale: true`` with an age. The global itself stays
    # relay-updated for demo mode and WS-push granularity.
    if backend.backend_type == "service" and hasattr(backend, "_adapter"):
        # Both fetches are synchronous HTTP calls — keep them off the event
        # loop so a slow cascor cannot stall every other canopy route.
        def _fetch_live_status_and_params():
            return backend.get_status(), backend._adapter.get_canopy_params()

        live_status, canopy_params = await asyncio.to_thread(_fetch_live_status_and_params)

        state = training_state.get_state()

        live_ok = isinstance(live_status, dict) and not live_status.get("error") and "fsm_status" in live_status
        if live_ok:
            from backend.state_sync import CascorStateSync

            if live_status.get("failed"):
                state["status"] = "Failed"
            elif live_status.get("is_paused"):
                state["status"] = "Paused"
            elif live_status.get("is_running") or live_status.get("is_training"):
                state["status"] = "Started"
            elif live_status.get("completed"):
                state["status"] = "Completed"
            else:
                state["status"] = CascorStateSync._normalize_status(str(live_status.get("fsm_status", "")))
            live_phase = live_status.get("phase")
            if isinstance(live_phase, str) and live_phase:
                state["phase"] = live_phase
            live_epoch = live_status.get("current_epoch")
            if live_epoch is not None:
                state["current_epoch"] = live_epoch
            state["timestamp"] = time.time()
            state["stale"] = False
        else:
            # Upstream error: serve the last-known relay-fed global, honestly
            # marked. The 8-hour-stale-base-fields class is impossible while
            # cascor is reachable; when it is NOT, the staleness is declared.
            state["stale"] = True
            try:
                state["stale_age_seconds"] = round(max(0.0, time.time() - float(state.get("timestamp") or 0.0)), 1)
            except (TypeError, ValueError):
                state["stale_age_seconds"] = None

        # Populate all nn_*/cn_* keys with defaults first (dashboard reads all 22)
        state.setdefault("nn_max_iterations", TrainingConstants.DEFAULT_MAX_GROWTH_ITERATIONS)
        state.setdefault("nn_max_total_epochs", TrainingConstants.DEFAULT_TRAINING_EPOCHS)
        state.setdefault("nn_init_output_weights", TrainingConstants.DEFAULT_INIT_OUTPUT_WEIGHTS)
        state.setdefault("nn_learning_rate", TrainingConstants.DEFAULT_LEARNING_RATE)
        state.setdefault("nn_max_hidden_units", TrainingConstants.DEFAULT_MAX_HIDDEN_UNITS)
        state.setdefault("nn_multi_node_layers", TrainingConstants.DEFAULT_MULTI_NODE_LAYERS)
        state.setdefault("nn_growth_trigger", TrainingConstants.DEFAULT_GROWTH_TRIGGER)
        state.setdefault("nn_growth_preset_epochs", TrainingConstants.DEFAULT_PRESET_EPOCHS)
        state.setdefault("nn_growth_convergence_threshold", TrainingConstants.DEFAULT_CONVERGENCE_THRESHOLD)
        state.setdefault("nn_patience", TrainingConstants.DEFAULT_PATIENCE)
        state.setdefault("nn_spiral_rotations", TrainingConstants.DEFAULT_SPIRAL_ROTATIONS)
        state.setdefault("nn_spiral_number", TrainingConstants.DEFAULT_SPIRAL_NUMBER)
        state.setdefault("nn_dataset_elements", TrainingConstants.DEFAULT_DATASET_ELEMENTS)
        state.setdefault("nn_dataset_noise", TrainingConstants.DEFAULT_DATASET_NOISE)
        state.setdefault("cn_pool_size", TrainingConstants.DEFAULT_CANDIDATE_POOL_SIZE)
        state.setdefault("cn_correlation_threshold", TrainingConstants.DEFAULT_CANDIDATE_CORRELATION_THRESHOLD)
        state.setdefault("cn_selected_candidates", TrainingConstants.DEFAULT_SELECTED_CANDIDATES)
        state.setdefault("cn_patience", TrainingConstants.DEFAULT_CN_PATIENCE)
        state.setdefault("cn_training_complete", TrainingConstants.DEFAULT_CN_TRAINING_COMPLETE)
        state.setdefault("cn_training_iterations", TrainingConstants.DEFAULT_CANDIDATE_TRAINING_ITERATIONS)
        state.setdefault("cn_training_convergence_threshold", TrainingConstants.DEFAULT_CANDIDATE_CONVERGENCE_THRESHOLD)
        state.setdefault("cn_multi_candidate", TrainingConstants.DEFAULT_MULTI_CANDIDATE_ENABLED)
        state.setdefault("cn_candidate_selection", "top")
        state.setdefault("cn_top_candidates", TrainingConstants.DEFAULT_TOP_CANDIDATES_COUNT)
        state.setdefault("cn_random_candidates", TrainingConstants.DEFAULT_RANDOM_CANDIDATES_COUNT)

        # Override with live values from cascor (keys it actually exposes).
        # Fetched above in the same off-loop thread hop as the status call.
        state.update(canopy_params)
        return state

    return training_state.get_state()


@app.get("/api/status")
async def get_status():
    """
    Get current training status.
    Returns:
        Training status dictionary with FSM-based status and phase
    """
    return backend.get_status()


@app.get("/api/stream_health")
async def get_stream_health():
    """
    N2 (training-runtime defects plan §4 I-1 / §5 T2): canopy→cascor stream
    health for the dashboard's degraded-mode indicator.

    Returns ``{"overall": "healthy"|"degraded"|"reconnecting"|"n/a", "relay":
    {...}, "control": {...}}`` in service mode — a pure in-memory snapshot of
    the metrics-relay / control-stream supervisor liveness state (no upstream
    call). Non-service backends (demo/recurrence) have no upstream stream, so
    ``overall`` is ``"n/a"`` and the badge ignores it.
    """
    if backend.backend_type == "service" and hasattr(backend, "_adapter"):
        return backend._adapter.get_stream_health()
    return {"overall": "n/a", "mode": backend.backend_type, "relay": None, "control": None}


@app.get("/api/metrics")
async def get_metrics():
    """
    Get current training metrics.
    Returns:
        Current metrics dictionary
    """
    return backend.get_metrics()


@app.get("/api/metrics/history")
async def get_metrics_history(limit: int = 100):
    """
    Get metrics history.
    Args:
        limit: Maximum number of history entries to return (default: 100, 0 = all)
    Returns:
        Dictionary with history list
    """
    count = limit if limit > 0 else 10000
    # N1 event-loop guard: the backend call is a synchronous cascor-client call;
    # run it in a thread so a slow cascor cannot stall canopy's event loop under
    # the un-gated 1 Hz dashboard poll.
    return {"history": await asyncio.to_thread(backend.get_metrics_history, count)}


@app.get("/api/network/stats")
async def get_network_stats():
    """
    Get comprehensive network statistics including weight statistics and metadata.
    Returns:
        Dictionary with threshold function, optimizer, node/edge counts, and weight statistics
    """
    from backend.data_adapter import DataAdapter

    adapter = DataAdapter()

    # Demo mode: direct access to weight tensors for detailed statistics
    if backend.backend_type == "demo" and hasattr(backend, "_demo"):
        network = backend._demo.get_network()
        state = backend._demo.get_current_state()
        threshold_function = state.get("activation_fn", "sigmoid")
        optimizer_name = state.get("optimizer", "sgd")

        # Collect weights from ALL hidden units (not just the first)
        if network.hidden_units:
            import torch

            all_hidden_weights = torch.cat([hu["weights"] for hu in network.hidden_units])
        else:
            all_hidden_weights = None

        return adapter.get_network_statistics(
            input_weights=network.input_weights,
            hidden_weights=all_hidden_weights,
            output_weights=network.output_weights,
            hidden_biases=None,
            output_biases=network.output_bias,
            threshold_function=threshold_function,
            optimizer_name=optimizer_name,
        )

    # Service mode: get network data from adapter
    if backend.backend_type == "service" and hasattr(backend, "_adapter"):
        network_data = backend._adapter.get_network_data()
        return adapter.get_network_statistics(
            input_weights=network_data.get("input_weights"),
            hidden_weights=network_data.get("hidden_weights"),
            output_weights=network_data.get("output_weights"),
            hidden_biases=network_data.get("hidden_biases"),
            output_biases=network_data.get("output_biases"),
            threshold_function=network_data.get("threshold_function", "sigmoid"),
            optimizer_name=network_data.get("optimizer", "sgd"),
        )
    return JSONResponse({"error": "No network data available"}, status_code=503)


@app.get("/api/topology")
async def get_topology():
    """
    Get current network topology.
    Returns:
        Network topology dictionary with nodes and connections
    """
    # N1 event-loop guard: same sync-in-async pattern as /api/metrics/history —
    # the un-gated topology poll exercises this route on every slow tick.
    topology = await asyncio.to_thread(backend.get_network_topology)
    if topology is None:
        return JSONResponse({"error": "No topology available"}, status_code=503)
    return topology


@app.get("/api/topology/raw")
async def get_raw_topology():
    """
    Get raw weight-oriented network topology (pre-transformation).
    Returns CasCor's native format with weight arrays for heatmap visualization.
    """
    # N1 event-loop guard (trivially co-located with /api/topology).
    raw = await asyncio.to_thread(backend.get_raw_topology)
    if raw is None:
        return JSONResponse({"error": "No raw topology available"}, status_code=503)
    return raw


@app.get("/api/dataset")
async def get_dataset():
    """
    Get dataset information.
    Returns:
        Dataset dictionary
    """
    dataset = backend.get_dataset()
    if dataset is None:
        return JSONResponse({"error": "No dataset available"}, status_code=503)
    return dataset


@app.post("/api/dataset/generate")
async def generate_dataset(request: Request):
    """Generate a new dataset with custom parameters (demo mode only)."""
    if backend.backend_type != "demo":
        return JSONResponse({"error": "Dataset generation only available in demo mode"}, status_code=400)

    if not hasattr(backend, "regenerate_dataset"):
        return JSONResponse({"error": "Backend does not support dataset regeneration"}, status_code=501)

    try:
        body = await request.json()
    except Exception:
        body = {}

    n_samples = int(body.get("n_samples", 200))
    n_spirals = int(body.get("n_spirals", 2))
    noise = float(body.get("noise", 0.1))
    n_rotations = float(body.get("n_rotations", 1.5))

    n_samples = max(20, min(2000, n_samples))
    n_rotations = max(0.1, min(10.0, n_rotations))
    noise = max(0.0, min(1.0, noise))

    # Generator selection (dataset-plotter "Dataset:" picker). Spiral is the
    # demo's local generator; every other generator (xor, circles, moon, …) is
    # synthesized by the JuniperData service, so it requires that service to be
    # reachable and surfaces a clean 503 otherwise.
    generator = str(body.get("generator", "spiral")).strip().lower() or "spiral"
    if generator not in ("spiral", "spirals"):
        if not juniper_data_available:
            return JSONResponse({"error": f"Generator '{generator}' requires the JuniperData service"}, status_code=503)
        if not hasattr(backend, "regenerate_dataset_from_generator"):
            return JSONResponse({"error": "Backend does not support generator selection"}, status_code=501)
        try:
            dataset = backend.regenerate_dataset_from_generator(generator=generator, n_samples=n_samples)
            return dataset or {"status": "generated"}
        except Exception as exc:
            error_id = uuid.uuid4().hex[:12]
            system_logger.error("Generator '%s' dataset load failed [error_id=%s]", generator, error_id, exception=exc)
            return JSONResponse({"error": "Internal server error", "error_id": error_id}, status_code=500)

    try:
        dataset = backend.regenerate_dataset(n_samples=n_samples, n_spirals=n_spirals, noise=noise, n_rotations=n_rotations)
        return dataset or {"status": "generated"}
    except Exception as exc:
        # SEC-14: never leak internal exception messages to clients; log the
        # full traceback server-side and return an opaque error_id so the
        # operator can correlate the client report with server logs.
        error_id = uuid.uuid4().hex[:12]
        system_logger.error("Dataset generation failed [error_id=%s]", error_id, exception=exc)
        return JSONResponse(
            {"error": "Internal server error", "error_id": error_id},
            status_code=500,
        )


@app.post("/api/dataset/import-file")
async def import_dataset_file(file: UploadFile = File(...)):  # noqa: B008 — FastAPI canonical pattern for multipart parameters
    """CAN-016b: import a dataset from an uploaded CSV file (demo mode only).

    Format: see ``dataset_import.parse_csv_bytes`` — CSV, last column is the
    integer class label, optional header auto-detected. 10 MB / 50k rows /
    100 features cap.
    """
    if backend.backend_type != "demo":
        return JSONResponse(
            {"error": "Dataset import only available in demo mode (cascor backend doesn't accept inline datasets yet)"},
            status_code=400,
        )
    if not hasattr(backend, "import_dataset"):
        return JSONResponse({"error": "Backend does not support dataset import"}, status_code=501)

    from dataset_import import DatasetImportError, parse_csv_bytes

    raw = await file.read()
    try:
        inputs, targets = parse_csv_bytes(raw)
    except DatasetImportError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)

    try:
        dataset = backend.import_dataset(inputs, targets, source_label=f"upload:{file.filename or 'unnamed.csv'}")
        return dataset or {"status": "imported"}
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except Exception as exc:
        # SEC-14: opaque server-side error with correlation id (matches the
        # ``/api/dataset/generate`` pattern). Don't leak exception details.
        error_id = uuid.uuid4().hex[:12]
        system_logger.error("Dataset import (file) failed [error_id=%s]", error_id, exception=exc)
        return JSONResponse({"error": "Internal server error", "error_id": error_id}, status_code=500)


# SEC-F08: SSRF egress guard for POST /api/dataset/import-url. The URL-fetch
# import makes the canopy server issue an outbound request to a caller-supplied
# address; unguarded, that address can be a loopback / RFC-1918 / link-local host
# (including the cloud-metadata endpoint 169.254.169.254). These helpers resolve
# the target and refuse it when the RESOLVED IP is non-public — validating the
# resolved address rather than the URL string, so a hostname that resolves to an
# internal address (DNS rebind) is caught too. Audit: SEC-F08 (HO-1/HO-7),
# juniper-ml notes/JUNIPER_STACK_SECURITY_AUDIT_PLAN_2026-07-02.md §4.3 / §5.2.
def _import_url_ip_is_blocked(ip_text: str) -> bool:
    """True when ``ip_text`` is a non-routable / internal address the SSRF guard
    must refuse: loopback (127.0.0.0/8, ::1), RFC-1918 private (10/8, 172.16/12,
    192.168/16), link-local (169.254/16 incl. the metadata IP, fe80::/10),
    unique-local IPv6 (fc00::/7), unspecified (0.0.0.0, ::), multicast, and
    reserved ranges. An unparseable value fails closed (blocked)."""
    try:
        addr = ipaddress.ip_address(ip_text)
    except ValueError:
        return True
    return bool(addr.is_loopback or addr.is_private or addr.is_link_local or addr.is_reserved or addr.is_multicast or addr.is_unspecified)


def _classify_import_url_target(url: str) -> Optional[str]:
    """Resolve ``url``'s host and return a human-readable rejection reason when it
    maps to any non-public address, else ``None`` (safe to fetch).

    Every resolved A/AAAA record is checked — a host that resolves to a mix of
    public and internal addresses is rejected. Uses a blocking ``getaddrinfo``,
    so callers must invoke it off the event loop (``asyncio.to_thread``)."""
    host = urlsplit(url).hostname
    if not host:
        return "URL has no host to resolve"
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return f"Could not resolve host: {host}"
    resolved = {str(info[4][0]) for info in infos}
    if not resolved:
        return f"Could not resolve host: {host}"
    for ip_text in sorted(resolved):
        if _import_url_ip_is_blocked(ip_text):
            return "Refusing to fetch a URL that resolves to a non-public address"
    return None


class _ImportUrlRequest(BaseModel):
    """Body for ``POST /api/dataset/import-url``."""

    url: str = Field(..., min_length=1, max_length=2048)


@app.post("/api/dataset/import-url")
async def import_dataset_url(request: _ImportUrlRequest):
    """CAN-016b: fetch a CSV from a URL and import it (demo mode only).

    Network access is gated by ``settings.dataset_import_url_enabled`` — a real
    ``Settings`` field that defaults **off** (SEC-F08): URL-based import lets the
    server issue arbitrary outbound requests, so it is opt-in. When enabled, the
    fetch is hardened against SSRF — the resolved target IP is refused if it is
    loopback / private / link-local / reserved (``_classify_import_url_target``),
    redirects are **not** followed (a public→internal 302 cannot bypass the
    egress guard), and the 10 MB cap is enforced *during* the streamed download.
    10s fetch timeout.
    """
    if backend.backend_type != "demo":
        return JSONResponse(
            {"error": "Dataset import only available in demo mode (cascor backend doesn't accept inline datasets yet)"},
            status_code=400,
        )
    if not settings.dataset_import_url_enabled:
        return JSONResponse({"error": "URL-based dataset import is disabled by configuration"}, status_code=403)
    if not hasattr(backend, "import_dataset"):
        return JSONResponse({"error": "Backend does not support dataset import"}, status_code=501)

    url = request.url.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        return JSONResponse({"error": "URL must use http:// or https:// scheme"}, status_code=400)

    # SEC-F08: SSRF egress guard. Resolve the host and refuse the fetch when the
    # RESOLVED IP is loopback / private / link-local / reserved — validating the
    # resolved address (not just the URL string) defeats DNS-rebind. Blocking DNS
    # runs off the event loop so the single uvicorn worker never stalls (SEC-F20).
    ssrf_rejection = await asyncio.to_thread(_classify_import_url_target, url)
    if ssrf_rejection is not None:
        return JSONResponse({"error": ssrf_rejection}, status_code=400)

    try:
        import httpx
    except ImportError:
        return JSONResponse({"error": "URL import requires httpx — not available in this build"}, status_code=501)

    from dataset_import import MAX_FILE_BYTES, DatasetImportError, parse_csv_bytes

    # SEC-F08: redirects disabled (a 302 to an internal host must not slip past
    # the egress guard, which only validated the original URL) and the size cap
    # enforced while streaming — abort as soon as the running byte count exceeds
    # MAX_FILE_BYTES instead of buffering the whole body first.
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
            async with client.stream("GET", url) as resp:
                if resp.status_code != 200:
                    return JSONResponse({"error": f"Fetch failed: HTTP {resp.status_code}"}, status_code=400)
                chunks: list[bytes] = []
                total = 0
                async for chunk in resp.aiter_bytes():
                    total += len(chunk)
                    if total > MAX_FILE_BYTES:
                        return JSONResponse(
                            {"error": f"Remote file too large: exceeds {MAX_FILE_BYTES} bytes"},
                            status_code=413,
                        )
                    chunks.append(chunk)
        raw = b"".join(chunks)
    except httpx.TimeoutException:
        return JSONResponse({"error": "Fetch timed out (10s limit)"}, status_code=504)
    except httpx.HTTPError as exc:
        return JSONResponse({"error": f"Fetch failed: {type(exc).__name__}"}, status_code=400)

    try:
        inputs, targets = parse_csv_bytes(raw)
    except DatasetImportError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)

    try:
        dataset = backend.import_dataset(inputs, targets, source_label=f"url:{url}")
        return dataset or {"status": "imported"}
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except Exception as exc:
        error_id = uuid.uuid4().hex[:12]
        system_logger.error("Dataset import (url) failed [error_id=%s]", error_id, exception=exc)
        return JSONResponse({"error": "Internal server error", "error_id": error_id}, status_code=500)


@app.get("/api/dataset/generators")
async def list_dataset_generators():
    """
    List available dataset generators from JuniperData service.
    Returns a list of generator names available for dataset creation.
    Falls back to built-in demo generators when JuniperData is unavailable.
    """
    generators = []

    # Try JuniperData service first
    if juniper_data_available:
        try:
            import httpx

            data_url = settings.juniper_data_url.rstrip("/")
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{data_url}/v1/generators")
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list):
                        generators = data
                    elif isinstance(data, dict) and "generators" in data:
                        generators = data["generators"]
        except Exception as e:
            system_logger.debug("Failed to fetch generators from JuniperData: %s", e)

    # Fallback to built-in demo generators
    if not generators:
        generators = [
            # XREPO-01 / DC-01 (2026-04-24): generator ``name`` values
            # must match the juniper-data server registry keys. The
            # concentric-circles generator is ``"circles"`` (plural).
            {"name": "spiral", "display_name": "Spiral", "description": "N-arm spiral classification"},
            {"name": "xor", "display_name": "XOR", "description": "XOR gate classification"},
            {"name": "circles", "display_name": "Circles", "description": "Concentric circles classification"},
            {"name": "moon", "display_name": "Moon", "description": "Two interleaving half-moon classification"},
        ]

    return {"generators": generators}


@app.get("/api/decision_boundary")
async def get_decision_boundary(resolution: int = 100):
    """
    Get decision boundary data for visualization.
    Args:
        resolution: Grid resolution per axis (5-200, default 100)
    Returns:
        Decision boundary dictionary with grid and predictions
    """
    resolution = max(5, min(200, resolution))
    boundary = backend.get_decision_boundary(resolution)
    if boundary is None:
        return JSONResponse({"error": "No decision boundary data available"}, status_code=503)
    return boundary


@app.get("/api/statistics")
async def get_statistics():
    """
    Get connection statistics.
    Returns:
        Statistics dictionary
    """
    return websocket_manager.get_statistics()


# =============================================================================
# HDF5 Snapshot API Endpoints (P2-4, P2-5)
# =============================================================================

# Snapshot configuration
SNAPSHOT_EXTENSIONS = (".h5", ".hdf5")
_snapshots_dir = os.getenv("JUNIPER_CANOPY_SNAPSHOT_DIR")
if _snapshots_dir is None:
    _legacy_snapshot_dir = os.getenv("CASCOR_SNAPSHOT_DIR")
    if _legacy_snapshot_dir is not None:
        import warnings as _snapshot_warnings

        _snapshot_warnings.warn(
            "CASCOR_SNAPSHOT_DIR is deprecated. Use JUNIPER_CANOPY_SNAPSHOT_DIR instead.",
            DeprecationWarning,
            stacklevel=1,
        )
        _snapshots_dir = _legacy_snapshot_dir
    else:
        _snapshots_dir = "./snapshots"

# Snapshot name validation pattern: alphanumeric, hyphens, underscores, dots (no path separators)
_SNAPSHOT_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$")


# ─────────────────────────────────────────────────────────────────────────────
# Filesystem helpers — synchronous, called via ``asyncio.to_thread`` from
# async route handlers so the FastAPI event loop stays responsive while disk
# operations are in flight (Phase 3 of the async-route audit; see
# juniper-ml notes/ASYNC_ROUTE_AUDIT_HOOK_MIGRATION_PLAN.md).
# ─────────────────────────────────────────────────────────────────────────────


def _load_snapshot_history(history_file: "Path") -> list[dict]:
    """Read ``snapshot_history.jsonl`` and return parsed entries.

    Returns an empty list when the file is absent or unreadable; logs
    individual JSON-parse failures at WARNING and a top-level read
    failure at WARNING. Always returns; the caller treats an empty
    list as "no history" rather than as an error.
    """
    entries: list[dict] = []
    if not history_file.exists():
        return entries
    try:
        with open(history_file, "r") as f:
            for line in f:
                if line := line.strip():
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        system_logger.warning("Invalid JSON in history file: %s...", line[:50])
    except Exception as e:  # noqa: BLE001 — best-effort read; log and return what we have
        system_logger.warning("Failed to read snapshot history: %s", e)
    return entries


def _find_snapshot_file(snapshots_dir: str, snapshot_id: str) -> tuple["Path | None", "os.stat_result | None", bool]:
    """Find a snapshot file by stem and stat it.

    Returns ``(snapshot_file, stat_result, directory_missing)``. The first two
    elements are ``None`` when no file matches; ``directory_missing`` is
    ``True`` only when the snapshots directory itself does not exist, so the
    route handler can surface a more specific 404 message to API consumers.
    Bundles the filesystem walk + ``stat`` syscall so callers take one
    ``asyncio.to_thread`` hop instead of three.
    """
    from pathlib import Path

    path = Path(snapshots_dir)
    if not path.exists():
        return None, None, True
    snapshot_file = next(
        (f for f in path.iterdir() if f.is_file() and f.suffix.lower() in SNAPSHOT_EXTENSIONS and f.stem == snapshot_id),
        None,
    )
    if snapshot_file is None:
        return None, None, False
    return snapshot_file, snapshot_file.stat(), False


def _sanitize_snapshot_name(name: str) -> str:
    """Validate and sanitize a snapshot name to prevent path traversal.

    Args:
        name: The snapshot name or ID to validate.

    Returns:
        The validated name.

    Raises:
        HTTPException: 400 if the name contains invalid characters or path traversal sequences.
    """
    from fastapi import HTTPException

    if not name or not _SNAPSHOT_NAME_PATTERN.match(name):
        raise HTTPException(status_code=400, detail="Invalid snapshot name. Use only alphanumeric characters, hyphens, underscores, and dots.")

    # Path confinement: resolve and verify the resulting path stays inside _snapshots_dir
    base = Path(_snapshots_dir).resolve()
    # Verify with normalised version of path
    # candidate = (base / name).resolve()  ## This line is the borked version
    candidate = os.path.normpath(os.path.join(base, name))

    if not str(candidate).startswith(str(base) + os.sep) and candidate != base:
        raise HTTPException(status_code=400, detail="Invalid snapshot name.")

    return name


def _generate_mock_snapshots():
    """Generate mock snapshot metadata for demo mode or missing backend."""
    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)
    snapshots = []
    for i in range(3):
        ts = now - timedelta(hours=i * 24 + i * 2, minutes=i * 15)
        ts = ts.replace(microsecond=0)
        snapshots.append(
            {
                "id": f"demo_snapshot_{i + 1}",
                "name": f"Demo Snapshot {i + 1}",
                "timestamp": f"{ts.isoformat()}Z",
                "size_bytes": (i + 1) * 1024 * 1024 + i * 512 * 1024,
                "description": f"Demo training snapshot #{i + 1} (simulated)",
            }
        )
    return snapshots


def _list_snapshot_files():
    """
    Return list of snapshot metadata dicts from snapshots directory.

    Each item:
        - id: file stem (no extension)
        - name: file name
        - timestamp: ISO8601 from mtime (UTC)
        - size_bytes: file size
    """
    from datetime import UTC, datetime
    from pathlib import Path

    path = Path(_snapshots_dir)
    if not path.exists() or not path.is_dir():
        return []

    snapshots = []
    for f in sorted(path.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not f.is_file() or f.suffix.lower() not in SNAPSHOT_EXTENSIONS:
            continue

        stat = f.stat()
        ts = datetime.fromtimestamp(stat.st_mtime, tz=UTC).replace(microsecond=0)
        snapshots.append(
            {
                "id": f.stem,
                "name": f.name,
                "timestamp": f"{ts.isoformat()}Z",
                "size_bytes": stat.st_size,
                "path": str(f.absolute()),
            }
        )
    return snapshots


@app.get("/api/v1/snapshots")
async def get_snapshots():
    """
    List available HDF5 snapshots.

    Returns:
        JSON object with:
            - snapshots: list of snapshot metadata objects
            - message: optional status message
    """
    try:
        snapshots = _list_snapshot_files()
    except Exception as e:
        system_logger.error("Failed to list snapshots: %s", e)
        snapshots = []

    # Demo mode → return mock data. (A1-iii-a: gate on ``== "demo"`` rather than
    # ``!= "service"`` so a non-cascor, non-demo backend — e.g. recurrence — does NOT
    # fall into the "no real snapshots" branch and serve fabricated demo snapshots.)
    if backend.backend_type == "demo":
        # Combine session-created demo snapshots with mock snapshots
        mock_snapshots = _generate_mock_snapshots()

        # Merge: session snapshots first, then mock snapshots (avoid duplicates by ID)
        existing_ids = {s["id"] for s in _demo_snapshots}
        combined = list(_demo_snapshots)
        for mock in mock_snapshots:
            if mock["id"] not in existing_ids:
                combined.append(mock)

        return {"snapshots": combined, "message": "Demo mode: showing simulated snapshots"}

    if not snapshots:
        return {"snapshots": [], "message": "No snapshots available"}

    return {"snapshots": snapshots}


@app.get("/api/v1/snapshots/history")
async def get_snapshot_history(limit: int = 50):
    """
    Get snapshot activity history (P3-3).

    Reads from snapshot_history.jsonl and returns entries in reverse chronological order.

    Args:
        limit: Maximum number of entries to return (default 50)

    Returns:
        JSON object with history entries array
    """
    from pathlib import Path

    history_file = Path(_snapshots_dir) / "snapshot_history.jsonl"

    # Read off the event loop. The history file can grow large (one line
    # per snapshot op, no rotation today) and disk I/O on a slow volume
    # blocks the loop. ``_load_snapshot_history`` returns the parsed
    # entries; warnings are still routed through the logger inside the
    # helper so the route stays simple.
    entries = await asyncio.to_thread(_load_snapshot_history, history_file)

    # Return in reverse chronological order (newest first)
    entries.reverse()

    # Apply limit
    if limit and limit > 0:
        entries = entries[:limit]

    return {
        "history": entries,
        "total": len(entries),
        "message": "Demo mode history" if backend.backend_type == "demo" else None,
    }


@app.get("/api/v1/snapshots/{snapshot_id}")
async def get_snapshot_detail(snapshot_id: str):
    """
    Get details for a specific snapshot.

    Args:
        snapshot_id: The snapshot ID (file stem) to look up

    Returns:
        JSON object with snapshot metadata and optional HDF5 attributes
    """
    from datetime import UTC, datetime

    from fastapi import HTTPException

    snapshot_id = _sanitize_snapshot_name(snapshot_id)

    # Demo mode: return synthetic details
    if backend.backend_type == "demo":
        # Check session-created demo snapshots first
        for s in _demo_snapshots:
            if s["id"] == snapshot_id:
                s_copy = dict(s)
                s_copy["attributes"] = {
                    "mode": "demo",
                    "description": s.get("description", "Demo snapshot (no real HDF5 file)"),
                    "epochs_trained": 0,
                    "hidden_units": 0,
                    "created_in_session": True,
                }
                if "meta_params" in s:
                    s_copy["meta_params"] = s["meta_params"]
                return s_copy

        # Then check mock snapshots
        for s in _generate_mock_snapshots():
            if s["id"] == snapshot_id:
                s["attributes"] = {
                    "mode": "demo",
                    "description": "Demo snapshot (no real HDF5 file)",
                    "epochs_trained": 100 + int(snapshot_id.split("_")[-1]) * 50,
                    "hidden_units": 3 + int(snapshot_id.split("_")[-1]),
                }
                return s

        raise HTTPException(status_code=404, detail="Snapshot not found")

    # Real mode: find file in snapshots directory. The directory walk and
    # ``stat`` syscall are bundled into ``_find_snapshot_file`` and run on a
    # worker thread so the FastAPI event loop stays responsive on slow disks.
    snapshot_file, stat, directory_missing = await asyncio.to_thread(_find_snapshot_file, _snapshots_dir, snapshot_id)

    if directory_missing:
        raise HTTPException(status_code=404, detail="Snapshot directory not found")
    if snapshot_file is None or stat is None:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    ts = datetime.fromtimestamp(stat.st_mtime, tz=UTC).replace(microsecond=0)

    detail = {
        "id": snapshot_file.stem,
        "name": snapshot_file.name,
        "timestamp": f"{ts.isoformat()}Z",
        "size_bytes": stat.st_size,
        "path": str(snapshot_file.absolute()),
        "attributes": None,
    }

    # Optional: if h5py is available, read HDF5 root attributes
    try:
        import h5py

        with h5py.File(snapshot_file, "r") as f:
            detail["attributes"] = {k: str(v) for k, v in f.attrs.items()}
            if "meta_params" in f:
                mp_group = f["meta_params"]
                detail["meta_params"] = {k: mp_group.attrs[k] for k in mp_group.attrs.keys()}
    except ImportError:
        system_logger.debug("h5py not available, skipping HDF5 attribute extraction")
    except Exception as e:
        system_logger.warning("Failed to read HDF5 attributes for %s: %s", snapshot_file, e)

    return detail


# Session-persistent storage for demo mode snapshots (P3-1).
# BUG-CN-08: bounded by ``maxlen`` so the list can't grow unbounded across
# a long demo session — older snapshots fall off the tail LRU-style. 100
# is enough for any realistic demo run; existing callers iterate the
# whole collection and don't depend on list-specific methods beyond
# ``insert(0, ...)`` (now ``.appendleft(...)``).
_DEMO_SNAPSHOTS_MAX = 100
_demo_snapshots: deque = deque(maxlen=_DEMO_SNAPSHOTS_MAX)

# Meta parameter key prefixes captured in snapshots
_META_PARAM_PREFIXES = ("nn_", "cn_")


def _extract_meta_params() -> dict:
    """Extract current nn_*/cn_* meta parameters from the backend status."""
    status = backend.get_status()
    return {k: v for k, v in status.items() if any(k.startswith(p) for p in _META_PARAM_PREFIXES)}


def _log_snapshot_activity(action: str, snapshot_id: str, details: dict = None, message: str = None):
    """
    Log snapshot activity to history file for P3-3.

    Args:
        action: The action type ('create', 'restore', 'delete')
        snapshot_id: The snapshot ID
        details: Additional details about the action
        message: Human-readable message
    """
    import json
    from datetime import UTC, datetime
    from pathlib import Path

    history_file = Path(_snapshots_dir) / "snapshot_history.jsonl"

    entry = {
        "timestamp": f"{datetime.now(UTC).isoformat()}Z",
        "action": action,
        "snapshot_id": snapshot_id,
        "details": details or {},
        "message": message or f"Snapshot {action} completed",
    }

    try:
        # Ensure directory exists
        Path(_snapshots_dir).mkdir(parents=True, exist_ok=True)

        with open(history_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

        system_logger.debug("Logged snapshot activity: %s for %s", action, snapshot_id)
    except Exception as e:
        system_logger.warning("Failed to log snapshot activity: %s", e)


@app.post("/api/v1/snapshots", status_code=201)
async def create_snapshot(
    name: str = None,
    description: str = "",
):
    """
    Create a new HDF5 snapshot of the current training state.

    Args:
        name: Optional custom name for the snapshot (auto-generated if not provided)
        description: Optional description for the snapshot. Defaults to "" (never
            ``None``) — cascor's ``SnapshotCreateRequest.description: str`` accepts an
            omitted/blank string but 422s an explicit ``null``, so a blank description
            must never be forwarded as ``None`` (plan N4 / incident I-3).

    Returns:
        JSON object with the created snapshot metadata
    """
    from datetime import UTC, datetime
    from pathlib import Path

    from fastapi import HTTPException

    now = datetime.now(UTC)
    timestamp_str = now.strftime("%Y%m%d_%H%M%S")

    # Generate snapshot ID and name
    snapshot_id = name or f"snapshot_{timestamp_str}"
    snapshot_id = _sanitize_snapshot_name(snapshot_id)
    snapshot_name = f"{snapshot_id}.h5"

    # Demo mode: create mock snapshot entry
    if backend.backend_type == "demo":
        size_bytes = 1024 * 1024 + int(now.timestamp()) % (512 * 1024)  # ~1-1.5 MB mock size
        meta_params = _extract_meta_params()

        snapshot = {
            "id": snapshot_id,
            "name": snapshot_name,
            "timestamp": f"{now.replace(microsecond=0).isoformat()}Z",
            "size_bytes": size_bytes,
            "description": description or "Demo snapshot (no real HDF5 file)",
            "path": f"{_snapshots_dir}/{snapshot_name}",
            "meta_params": meta_params,
        }

        # Include dataset versioning metadata for reproducibility
        status = backend.get_status()
        if "dataset_name" in status:
            snapshot["dataset_name"] = status["dataset_name"]
        if "dataset_version" in status:
            snapshot["dataset_version"] = status["dataset_version"]

        # Add to session-persistent demo snapshots list (deque appendleft is
        # the O(1) equivalent of list.insert(0, ...); maxlen drops the oldest
        # entry when the cap is reached — see BUG-CN-08).
        _demo_snapshots.appendleft(snapshot)

        # Log the activity
        _log_snapshot_activity(
            action="create",
            snapshot_id=snapshot_id,
            details={"name": snapshot_name, "size_bytes": size_bytes, "mode": "demo"},
            message="Demo snapshot created successfully",
        )

        system_logger.info("Created demo snapshot: %s", snapshot_id)

        return {
            **snapshot,
            "message": "Demo snapshot created successfully",
        }

    # Real mode: create actual HDF5 file via backend
    try:
        snapshot_path = Path(_snapshots_dir) / snapshot_name
        # Path-containment guard: defense-in-depth over
        # ``_sanitize_snapshot_name`` (which already 400s traversal
        # sequences), and the explicit taint barrier CodeQL's
        # py/path-injection query recognizes — the resolved target must stay
        # inside the snapshots directory.
        snapshots_base = await asyncio.to_thread(Path(_snapshots_dir).resolve)
        snapshot_path = await asyncio.to_thread(snapshot_path.resolve)
        if not snapshot_path.is_relative_to(snapshots_base):
            raise HTTPException(status_code=400, detail="Invalid snapshot name")
        # ``mkdir`` is a sync syscall — push to a worker thread so a slow
        # disk doesn't stall the event loop. ``exist_ok=True`` keeps the
        # call idempotent on a hot path that may run frequently.
        await asyncio.to_thread(Path(_snapshots_dir).mkdir, parents=True, exist_ok=True)

        # Attempt to create HDF5 snapshot via CasCor integration. (A1-iii-a: gate on
        # ``backend_type == "service"`` — recurrence also exposes ``_adapter`` but it is a
        # ``RecurrenceServiceAdapter`` with cascor-incompatible semantics, so it must use
        # the h5py state-dump fallback below, never the cascor adapter's ``save_snapshot``.)
        if backend.backend_type == "service" and hasattr(backend, "_adapter") and hasattr(backend._adapter, "save_snapshot"):
            # N4 (plan I-3): normalize a ``None`` description to "" at the seam — the
            # adapter defaults to "" and the cascor-client would otherwise POST
            # ``{"description": null}``, which cascor rejects with a 422.
            #
            # Wave-1 E2E finding (2026-07-18): the local ``snapshot_path`` is a
            # hint the adapter deliberately IGNORES — cascor names and stores
            # the snapshot server-side, and canopy shares no filesystem with it
            # (the deploy stack mounts no snapshot volume into canopy). The
            # former post-save ``snapshot_path.stat()`` therefore raised ENOENT
            # and turned every SUCCESSFUL service-mode save into a 500. Build
            # the response from cascor's own metadata instead; the local stat
            # now lives only in the h5py fallback branch, which really writes
            # the file it stats.
            result = backend._adapter.save_snapshot(str(snapshot_path), description=description or "")
            data = result.get("data", result) if isinstance(result, dict) else {}
            if not isinstance(data, dict):
                data = {}
            server_id = data.get("id") or snapshot_id
            snapshot = {
                "id": server_id,
                "name": f"{server_id}.h5",
                "timestamp": data.get("timestamp") or f"{now.replace(microsecond=0).isoformat()}Z",
                "size_bytes": data.get("size_bytes", 0),
                "description": data.get("description", description),
                "path": data.get("path", ""),
            }
        else:
            # Fallback: create a minimal HDF5 file with current state
            try:
                import h5py

                with h5py.File(snapshot_path, "w") as f:
                    f.attrs["created"] = now.isoformat()
                    f.attrs["description"] = description or ""
                    f.attrs["mode"] = "manual"

                    # Try to store current training state if available
                    if training_state:
                        state_group = f.create_group("training_state")
                        for key, value in training_state.__dict__.items():
                            if not key.startswith("_") and isinstance(value, (int, float, str, bool)):
                                state_group.attrs[key] = value

                    # Store nn_*/cn_* meta parameters
                    meta_params = _extract_meta_params()
                    if meta_params:
                        mp_group = f.create_group("meta_params")
                        for key, value in meta_params.items():
                            if isinstance(value, (int, float, str, bool)):
                                mp_group.attrs[key] = value

            except ImportError as e:
                raise HTTPException(
                    status_code=500,
                    detail="h5py not available for creating HDF5 snapshots",
                ) from e

            # Get file stats after creation (the fallback genuinely wrote this
            # file locally, so the stat is valid here — the service branch
            # above never reaches this).
            stat = snapshot_path.stat()
            ts = datetime.fromtimestamp(stat.st_mtime, tz=UTC).replace(microsecond=0)

            snapshot = {
                "id": snapshot_id,
                "name": snapshot_name,
                "timestamp": f"{ts.isoformat()}Z",
                "size_bytes": stat.st_size,
                "description": description,
                "path": str(snapshot_path.absolute()),
            }

        # Include dataset versioning metadata for reproducibility
        status = backend.get_status()
        if "dataset_name" in status:
            snapshot["dataset_name"] = status["dataset_name"]
        if "dataset_version" in status:
            snapshot["dataset_version"] = status["dataset_version"]

        # Log the activity
        _log_snapshot_activity(
            action="create",
            snapshot_id=snapshot["id"],
            details={"name": snapshot["name"], "size_bytes": snapshot["size_bytes"], "mode": "real"},
            message="Snapshot created successfully",
        )

        system_logger.info("Created snapshot: %s at %s", snapshot["id"], snapshot["path"] or snapshot_path)

        return {
            **snapshot,
            "message": "Snapshot created successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        system_logger.error("Failed to create snapshot: %s", e)
        # N4 (plan I-3): carry the upstream failure reason in the HTTP detail
        # (truncated for display) so the frontend toast shows the actual cause
        # instead of doubling a generic constant with zero diagnostic content.
        reason = str(e) or e.__class__.__name__
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create snapshot: {reason[:300]}",
        ) from e


@app.post("/api/v1/snapshots/{snapshot_id}/restore")
async def restore_snapshot(snapshot_id: str):
    """
    Restore training state from an HDF5 snapshot (P3-2).

    Args:
        snapshot_id: The snapshot ID to restore from

    Returns:
        JSON object with restore status and restored state info

    Raises:
        HTTPException 404: Snapshot not found
        HTTPException 409: Training is currently running (must be paused/stopped)
        HTTPException 500: Restore failed
    """
    from datetime import UTC, datetime
    from pathlib import Path

    from fastapi import HTTPException

    snapshot_id = _sanitize_snapshot_name(snapshot_id)

    global training_state

    # Check if training is running - only allow restore when paused/stopped
    if backend.is_training_active():
        raise HTTPException(
            status_code=409,
            detail="Cannot restore while training is running. Please pause or stop training first.",
        )

    # Find the snapshot
    snapshot_data = next(
        (s for s in _demo_snapshots if s["id"] == snapshot_id),
        None,
    )

    # Check mock demo snapshots if not found
    if not snapshot_data and backend.backend_type == "demo":
        # Check against generated mock snapshots
        for s in _generate_mock_snapshots():
            if s["id"] == snapshot_id:
                snapshot_data = {
                    "id": snapshot_id,
                    "name": f"{snapshot_id}.h5",
                    "mode": "demo",
                }
                break

    # Check real file system if in service mode
    if not snapshot_data and backend.backend_type == "service":
        snapshot_path = Path(_snapshots_dir) / f"{snapshot_id}.h5"
        if not snapshot_path.exists():
            snapshot_path = Path(_snapshots_dir) / f"{snapshot_id}.hdf5"
        if snapshot_path.exists():
            snapshot_data = {
                "id": snapshot_id,
                "name": snapshot_path.name,
                "path": str(snapshot_path),
                "mode": "real",
            }

    if not snapshot_data:
        raise HTTPException(
            status_code=404,
            detail=f"Snapshot '{snapshot_id}' not found",
        )

    try:
        now = datetime.now(UTC)

        # Demo mode: simulate restore by resetting training state
        if backend.backend_type == "demo":
            # Reset demo mode state
            backend.reset_training()

            # Update training state with simulated restored values
            if training_state:
                training_state.update_state(
                    status="Stopped",
                    phase="Idle",
                    current_epoch=0,
                    current_step=0,
                )

            # Restore meta parameters if the snapshot captured them
            meta_params = snapshot_data.get("meta_params")
            if meta_params:
                backend.apply_params(**meta_params)

            restored_state = {
                "snapshot_id": snapshot_id,
                "restored_at": f"{now.isoformat()}Z",
                "mode": "demo",
                "current_epoch": 0,
                "training_status": "Stopped",
            }
            if meta_params:
                restored_state["meta_params"] = meta_params

            # Log the activity
            _log_snapshot_activity(
                action="restore",
                snapshot_id=snapshot_id,
                details={"mode": "demo", "restored_at": restored_state["restored_at"]},
                message=f"Restored from demo snapshot {snapshot_id}",
            )

            # Broadcast state change via WebSocket
            await websocket_manager.broadcast(
                {
                    "type": "state",
                    "data": {
                        "action": "snapshot_restored",
                        "snapshot_id": snapshot_id,
                        "training_state": training_state.get_state() if training_state else {},
                    },
                }
            )

            system_logger.info("Restored from demo snapshot: %s", snapshot_id)

            return {
                "status": "success",
                "message": f"Restored from snapshot '{snapshot_id}'",
                **restored_state,
            }

        # Real mode: load from HDF5 file
        snapshot_path = Path(snapshot_data.get("path", f"{_snapshots_dir}/{snapshot_id}.h5"))
        meta_params = None

        # A1-iii-a: gate on ``backend_type == "service"`` — recurrence's ``_adapter`` is a
        # different type, so it falls to the h5py fallback rather than cascor's load path.
        if backend.backend_type == "service" and hasattr(backend, "_adapter") and hasattr(backend._adapter, "load_snapshot"):
            backend._adapter.load_snapshot(str(snapshot_path))
        else:
            # Fallback: read HDF5 file and restore state
            try:
                import h5py

                with h5py.File(snapshot_path, "r") as f:
                    if "training_state" in f:
                        state_group = f["training_state"]
                        restored_attrs = {key: state_group.attrs[key] for key in state_group.attrs.keys()}
                        if training_state and restored_attrs:
                            training_state.update_state(**restored_attrs)

                    if "meta_params" in f:
                        mp_group = f["meta_params"]
                        meta_params = {k: mp_group.attrs[k] for k in mp_group.attrs.keys()}

            except ImportError as e:
                raise HTTPException(
                    status_code=500,
                    detail="h5py not available for reading HDF5 snapshots",
                ) from e

        # Also try reading meta_params when adapter handled the load
        if meta_params is None:
            try:
                import h5py

                with h5py.File(snapshot_path, "r") as f:
                    if "meta_params" in f:
                        mp_group = f["meta_params"]
                        meta_params = {k: mp_group.attrs[k] for k in mp_group.attrs.keys()}
            except Exception:  # nosec B110 — best-effort meta_params extraction
                pass

        if meta_params:
            backend.apply_params(**meta_params)

        restored_state = {
            "snapshot_id": snapshot_id,
            "restored_at": f"{now.isoformat()}Z",
            "mode": "real",
            "path": str(snapshot_path),
        }
        if meta_params:
            restored_state["meta_params"] = meta_params

        # Log the activity
        _log_snapshot_activity(
            action="restore",
            snapshot_id=snapshot_id,
            details={"mode": "real", "path": str(snapshot_path)},
            message=f"Restored from snapshot {snapshot_id}",
        )

        # Broadcast state change
        await websocket_manager.broadcast(
            {
                "type": "state",
                "data": {
                    "action": "snapshot_restored",
                    "snapshot_id": snapshot_id,
                    "training_state": training_state.get_state() if training_state else {},
                },
            }
        )

        system_logger.info("Restored from snapshot: %s at %s", snapshot_id, snapshot_path)

        return {
            "status": "success",
            "message": f"Restored from snapshot '{snapshot_id}'",
            **restored_state,
        }

    except HTTPException:
        raise
    except Exception as e:
        system_logger.error("Failed to restore snapshot: %s", e)
        raise HTTPException(
            status_code=500,
            detail="Failed to restore snapshot",
        ) from e


# ============================================================================
# CAN-015 (Phase 6E Sprint B B-5): Replay / Resume / Retrain proxy routes
# ============================================================================
# These three endpoints proxy to the cascor /v1/snapshots/{id}/{op} endpoints
# added in Sprint B B-1 (retrain), B-2 (resume), and B-3 (replay). Unlike
# the existing /restore route which carries significant demo-mode +
# legacy-mode compatibility logic, these new endpoints are thin proxies:
# they delegate to the cascor adapter, surface the unified response shape,
# and broadcast a state-change event for canopy clients on the WS stream.
#
# In demo mode the operations are not supported (cascor isn't running) —
# the proxies return 501 Not Implemented with a helpful message rather
# than silently no-op'ing. Demo-mode coverage is a follow-up if the
# product wants Replay/Resume/Retrain available without a live backend.


def _broadcast_snapshot_op(action: str, snapshot_id: str, payload: dict | None = None) -> None:
    """Broadcast a snapshot-operation state event to all WS subscribers.
    Mirrors the pre-existing snapshot_restored broadcast in
    ``restore_snapshot`` but parameterized over the operation name."""
    import asyncio as _asyncio
    from typing import Any as _Any

    data: dict[str, _Any] = {
        "action": f"snapshot_{action}",
        "snapshot_id": snapshot_id,
        "training_state": training_state.get_state() if training_state else {},
    }
    if payload is not None:
        data["payload"] = payload
    msg: dict[str, _Any] = {"type": "state", "data": data}
    # Fire-and-forget — broadcast is best-effort.
    try:
        loop = _asyncio.get_event_loop()
        loop.create_task(websocket_manager.broadcast(msg))
    except Exception as exc:
        system_logger.debug("snapshot_op broadcast skipped: %s", exc)


def _require_service_adapter():
    """Snapshot operations beyond /restore require a live cascor backend.
    Returns the adapter; raises HTTPException(501) when unavailable."""
    from fastapi import HTTPException

    if backend.backend_type != "service" or not hasattr(backend, "_adapter"):
        raise HTTPException(
            status_code=501,
            detail="Snapshot replay/resume/retrain operations require a live cascor backend (service mode). Demo mode is not supported.",
        )
    return backend._adapter


@app.post("/api/v1/snapshots/{snapshot_id}/replay")
async def replay_snapshot_route(snapshot_id: str):
    """Start a read-only replay session for a snapshot (CAN-015c).

    Proxies to cascor's ``POST /v1/snapshots/{id}/replay``. Returns the
    unified payload from cascor including ``operation``, ``fsm_state``,
    ``time_index``, and a ``session`` block describing the playback
    state. Canopy uses the ``session.length`` to wire the replay
    player UI scrubber.
    """
    from fastapi import HTTPException

    snapshot_id = _sanitize_snapshot_name(snapshot_id)
    if backend.is_training_active():
        raise HTTPException(status_code=409, detail="Cannot start replay while training is running. Pause or stop training first.")
    adapter = _require_service_adapter()
    try:
        result = adapter.replay_snapshot(snapshot_id)
        _log_snapshot_activity(action="replay", snapshot_id=snapshot_id, details={"mode": "service"}, message=f"Started replay of snapshot {snapshot_id}")
        _broadcast_snapshot_op("replay_started", snapshot_id, payload=result)
        return result
    except Exception as e:
        system_logger.error("Failed to start replay for %s: %s", snapshot_id, e)
        raise HTTPException(status_code=500, detail=f"Failed to start replay: {e}") from e


class _ReplayControlBody(BaseModel):
    """Body schema for /replay/control. Mirrors the cascor route's
    ReplayControlRequest — ``action`` discriminator + per-action params."""

    action: str
    time_index: int | None = None
    value: float | None = None
    start: int | None = None
    end: int | None = None


@app.post("/api/v1/snapshots/{snapshot_id}/replay/control")
async def replay_control_route(snapshot_id: str, body: _ReplayControlBody):
    """Send a playback control command to the active replay session
    (CAN-015c). Proxies to cascor's ``/replay/control`` endpoint."""
    from fastapi import HTTPException

    snapshot_id = _sanitize_snapshot_name(snapshot_id)
    adapter = _require_service_adapter()
    params = body.model_dump(exclude_none=True, exclude={"action"})
    try:
        result = adapter.replay_control(snapshot_id, body.action, **params)
        # Don't log/broadcast every play/pause/seek tick — too noisy. The
        # ``stop`` action is the meaningful one to surface.
        if body.action.lower() == "stop":
            _log_snapshot_activity(action="replay_stopped", snapshot_id=snapshot_id, details={"mode": "service"}, message=f"Stopped replay of snapshot {snapshot_id}")
            _broadcast_snapshot_op("replay_stopped", snapshot_id, payload=result)
        return result
    except Exception as e:
        system_logger.error("Replay control failed for %s (action=%s): %s", snapshot_id, body.action, e)
        # The cascor side maps bad params to 400 and missing-session to 409;
        # we don't get to see the underlying status here without parsing
        # JuniperCascorClientError. Map all to 500 for now and let the
        # message carry the cascor detail.
        raise HTTPException(status_code=500, detail=f"Replay control failed: {e}") from e


@app.post("/api/v1/snapshots/{snapshot_id}/resume")
async def resume_snapshot_route(snapshot_id: str):
    """Continue training from a snapshot (CAN-015b).

    Proxies to cascor's ``POST /v1/snapshots/{id}/resume``. Returns the
    unified payload including ``resume_point_epoch`` so canopy can
    render the visual boundary in the metrics-curve component.
    """
    from fastapi import HTTPException

    snapshot_id = _sanitize_snapshot_name(snapshot_id)
    if backend.is_training_active():
        raise HTTPException(status_code=409, detail="Cannot resume while training is running. Pause or stop training first.")
    adapter = _require_service_adapter()
    try:
        result = adapter.resume_snapshot(snapshot_id)
        _log_snapshot_activity(action="resume", snapshot_id=snapshot_id, details={"mode": "service"}, message=f"Resumed snapshot {snapshot_id}")
        _broadcast_snapshot_op("resumed", snapshot_id, payload=result)
        return result
    except Exception as e:
        system_logger.error("Failed to resume %s: %s", snapshot_id, e)
        raise HTTPException(status_code=500, detail=f"Failed to resume: {e}") from e


@app.post("/api/v1/snapshots/{snapshot_id}/retrain")
async def retrain_snapshot_route(snapshot_id: str):
    """Reset training history and prepare a fresh run from a snapshot (CAN-015a).

    Proxies to cascor's ``POST /v1/snapshots/{id}/retrain``."""
    from fastapi import HTTPException

    snapshot_id = _sanitize_snapshot_name(snapshot_id)
    if backend.is_training_active():
        raise HTTPException(status_code=409, detail="Cannot retrain while training is running. Pause or stop training first.")
    adapter = _require_service_adapter()
    try:
        result = adapter.retrain_snapshot(snapshot_id)
        _log_snapshot_activity(action="retrain", snapshot_id=snapshot_id, details={"mode": "service"}, message=f"Retrain prepared from snapshot {snapshot_id}")
        _broadcast_snapshot_op("retrain_ready", snapshot_id, payload=result)
        return result
    except Exception as e:
        system_logger.error("Failed to retrain from %s: %s", snapshot_id, e)
        raise HTTPException(status_code=500, detail=f"Failed to retrain: {e}") from e


# ============================================================================
# Network mutation proxies (Phase 6E CAN-015h, h-5)
# ----------------------------------------------------------------------------
# Forward the canopy Network Editor's submit actions to the cascor
# mutation endpoints landed in CAN-015h-1/h-2/h-3. The cascor side is
# the source of truth for FSM gating (rejects with 409 unless
# Investigating), shape/NaN validation (400/422), and out-of-range
# index handling (404). We surface the cascor detail verbatim.
# ============================================================================


class _PatchWeightsBody(BaseModel):
    """Body schema for PATCH /api/v1/network/weights. Mirrors the
    cascor-side ``PatchWeightsRequest`` — see juniper-cascor
    ``src/api/models/network.py``.
    """

    target: str
    field: str
    values: Any
    hidden_unit_index: int | None = None
    dtype: str = "float32"


@app.patch("/api/v1/network/weights")
async def patch_weights_route(body: _PatchWeightsBody):
    """Surgical weight rewrite — forwards to cascor's PATCH route."""
    from fastapi import HTTPException

    adapter = _require_service_adapter()
    try:
        return adapter.patch_weights(
            target=body.target,
            field=body.field,
            values=body.values,
            hidden_unit_index=body.hidden_unit_index,
            dtype=body.dtype,
        )
    except Exception as e:
        system_logger.error("patch_weights failed (target=%s, field=%s): %s", body.target, body.field, e)
        raise HTTPException(status_code=500, detail=f"patch_weights failed: {e}") from e


class _AddHiddenUnitBody(BaseModel):
    """Body schema for POST /api/v1/network/hidden-units. Mirrors the
    cascor-side ``AddHiddenUnitRequest`` — see juniper-cascor
    ``src/api/models/network.py``.
    """

    weights: Any
    bias: float = 0.0
    activation: str = "Tanh"


@app.post("/api/v1/network/hidden-units")
async def add_hidden_unit_route(body: _AddHiddenUnitBody):
    """Append a hidden unit at the cascade tail — forwards to cascor."""
    from fastapi import HTTPException

    adapter = _require_service_adapter()
    try:
        return adapter.add_hidden_unit(
            weights=body.weights,
            bias=body.bias,
            activation=body.activation,
        )
    except Exception as e:
        system_logger.error("add_hidden_unit failed (activation=%s): %s", body.activation, e)
        raise HTTPException(status_code=500, detail=f"add_hidden_unit failed: {e}") from e


@app.delete("/api/v1/network/hidden-units/{idx}")
async def remove_hidden_unit_route(idx: int):
    """Delete the hidden unit at ``idx`` — forwards to cascor."""
    from fastapi import HTTPException

    adapter = _require_service_adapter()
    try:
        return adapter.remove_hidden_unit(idx=idx)
    except Exception as e:
        system_logger.error("remove_hidden_unit(idx=%d) failed: %s", idx, e)
        raise HTTPException(status_code=500, detail=f"remove_hidden_unit failed: {e}") from e


# ============================================================================
# Metrics Layouts API (P3-4)
# ============================================================================

# Directory for storing metric layout presets
_layouts_dir = os.path.join(os.path.dirname(__file__), "..", "conf", "layouts")


def _get_layouts_file() -> "Path":
    """Get the path to the layouts JSON file."""
    from pathlib import Path

    layouts_path = Path(_layouts_dir)
    layouts_path.mkdir(parents=True, exist_ok=True)
    return layouts_path / "metrics_layouts.json"


def _load_layouts() -> dict:
    """Load all saved layouts from disk."""
    import json

    layouts_file = _get_layouts_file()
    if layouts_file.exists():
        try:
            with open(layouts_file) as f:
                return dict(json.load(f))
        except Exception as e:
            system_logger.warning("Failed to load layouts file: %s", e)
    return {}


def _save_layouts(layouts: dict) -> None:
    """Save all layouts to disk."""
    import json

    layouts_file = _get_layouts_file()
    try:
        with open(layouts_file, "w") as f:
            json.dump(layouts, f, indent=2)
            f.write("\n")
    except Exception as e:
        system_logger.error("Failed to save layouts file: %s", e)
        raise


@app.get("/api/v1/metrics/layouts")
async def list_metrics_layouts():
    """
    List all saved metrics layouts (P3-4).

    Returns:
        JSON object with list of layout names and metadata
    """
    layouts = _load_layouts()

    layout_list = [
        {
            "name": name,
            "created": data.get("created"),
            "description": data.get("description", ""),
        }
        for name, data in layouts.items()
    ]

    return {
        "layouts": sorted(layout_list, key=lambda x: x.get("created", ""), reverse=True),
        "total": len(layout_list),
    }


@app.get("/api/v1/metrics/layouts/{name}")
async def get_metrics_layout(name: str):
    """
    Get a specific metrics layout by name (P3-4).

    Args:
        name: The layout name to retrieve

    Returns:
        JSON object with layout configuration
    """
    from fastapi import HTTPException

    layouts = _load_layouts()

    if name not in layouts:
        raise HTTPException(status_code=404, detail=f"Layout '{name}' not found")

    return layouts[name]


@app.post("/api/v1/metrics/layouts", status_code=201)
async def save_metrics_layout(
    name: str,
    selected_metrics: list = None,
    zoom_ranges: dict = None,
    smoothing_window: int = None,
    hyperparameters: dict = None,
    description: str = None,
):
    """
    Save a new metrics layout preset (P3-4).

    Args:
        name: Unique name for the layout
        selected_metrics: List of metric names to display
        zoom_ranges: Dict of axis ranges for plots
        smoothing_window: Smoothing window size
        hyperparameters: Training hyperparameters (learning_rate, max_hidden_units, max_epochs)
        description: Optional description

    Returns:
        JSON object confirming save with layout metadata
    """
    from datetime import UTC, datetime

    from fastapi import HTTPException

    if not name or not name.strip():
        raise HTTPException(status_code=400, detail="Layout name is required")

    name = name.strip()

    layouts = _load_layouts()

    now = datetime.now(UTC)

    layout_data = {
        "name": name,
        "created": f"{now.isoformat()}Z",
        "description": description or "",
        "selected_metrics": selected_metrics or ["loss", "accuracy"],
        "zoom_ranges": zoom_ranges or {},
        "smoothing_window": smoothing_window or 10,
        "hyperparameters": hyperparameters or {},
    }

    layouts[name] = layout_data

    try:
        _save_layouts(layouts)
    except Exception as e:
        system_logger.debug("Failed to save layout: %s", e)
        raise HTTPException(status_code=500, detail="Failed to save layout") from e

    system_logger.info("Saved metrics layout: %s", name)

    return {
        "name": name,
        "created": layout_data["created"],
        "message": "Layout saved successfully",
    }


@app.delete("/api/v1/metrics/layouts/{name}")
async def delete_metrics_layout(name: str):
    """
    Delete a metrics layout by name (P3-4).

    Args:
        name: The layout name to delete

    Returns:
        JSON object confirming deletion
    """
    from fastapi import HTTPException

    layouts = _load_layouts()

    if name not in layouts:
        raise HTTPException(status_code=404, detail=f"Layout '{name}' not found")

    del layouts[name]

    try:
        _save_layouts(layouts)
    except Exception as e:
        system_logger.debug("Failed to delete layout: %s", e)
        raise HTTPException(status_code=500, detail="Failed to delete layout") from e

    system_logger.info("Deleted metrics layout: %s", name)

    return {
        "name": name,
        "message": "Layout deleted successfully",
    }


# ============================================================================
# Redis Monitoring API (P3-6)
# ============================================================================


@app.get("/api/v1/redis/status")
async def get_redis_status():
    """
    Get Redis health and availability status (P3-6).

    Always returns HTTP 200 with a 'status' field:
    - DISABLED: Feature disabled via config or missing driver
    - UNAVAILABLE: Enabled but cannot connect
    - UP: Redis connection is healthy
    - DOWN: Redis connection failed

    Returns:
        JSON object with status, mode, message, and details
    """
    from backend.redis_client import get_redis_client

    client = get_redis_client()
    return client.get_status()


@app.get("/api/v1/redis/metrics")
async def get_redis_metrics():
    """
    Get Redis usage metrics (P3-6).

    Returns metrics including memory usage, connection stats,
    keyspace info, and hit rates.

    Returns:
        JSON object with status, mode, message, and metrics
    """
    from backend.redis_client import get_redis_client

    client = get_redis_client()
    return client.get_metrics()


# ============================================================================
# Cassandra Monitoring API (P3-7)
# ============================================================================


@app.get("/api/v1/cassandra/status")
async def get_cassandra_status():
    """
    Get Cassandra cluster health and availability status (P3-7).

    Always returns HTTP 200 with a 'status' field:
    - DISABLED: Feature disabled via config or missing driver
    - UNAVAILABLE: Enabled but cannot connect
    - UP: Cluster connection is healthy
    - DOWN: Cluster connection failed

    Returns:
        JSON object with status, mode, message, and details (hosts, keyspace, etc.)
    """
    from backend.cassandra_client import get_cassandra_client

    client = get_cassandra_client()
    return client.get_status()


@app.get("/api/v1/cassandra/metrics")
async def get_cassandra_metrics():
    """
    Get Cassandra keyspace and table metrics (P3-7).

    Returns metrics including keyspace counts, table information,
    and cluster statistics.

    Returns:
        JSON object with status, mode, message, and metrics
    """
    from backend.cassandra_client import get_cassandra_client

    client = get_cassandra_client()
    return client.get_metrics()


# ============================================================================
# Remote Worker Monitoring API (CAN-HIGH-005)
# ============================================================================


@app.get("/api/v1/workers/stats")
async def get_worker_stats():
    """
    Get aggregate remote worker statistics (CAN-HIGH-005).

    In service mode, delegates to JuniperCascor /v1/workers/stats endpoint.
    In demo mode, returns synthetic worker statistics.
    """
    if backend.backend_type == "service" and hasattr(backend, "_adapter"):
        try:
            result = backend._adapter._client.get_worker_stats()
            return result.get("data", result)
        except Exception:
            # SEC-14: return an opaque error_id instead of the exception message.
            error_id = uuid.uuid4().hex[:12]
            system_logger.warning("Failed to fetch worker stats from CasCor [error_id=%s]", error_id)
            return {
                "total": 0,
                "idle": 0,
                "busy": 0,
                "stale": 0,
                "total_tasks_completed": 0,
                "total_tasks_failed": 0,
                "average_health_score": 0,
                "error": "Upstream error",
                "error_id": error_id,
            }

    # A1-iii-a: a one-shot LMU regressor has no distributed worker pool — return an
    # empty pool rather than the synthetic demo fixtures below (which are demo-only).
    if backend.backend_type == "recurrence":
        return {"total": 0, "idle": 0, "busy": 0, "stale": 0, "total_tasks_completed": 0, "total_tasks_failed": 0, "average_health_score": 0}

    import time

    return {"total": 2, "idle": 1, "busy": 1, "stale": 0, "total_tasks_completed": 42, "total_tasks_failed": 1, "average_health_score": 0.9767, "timestamp": time.time()}


@app.get("/api/v1/workers/list")
async def get_worker_list():
    """
    List all registered remote workers with status (CAN-HIGH-005).

    In service mode, delegates to JuniperCascor /v1/workers endpoint.
    In demo mode, returns synthetic worker data.
    """
    if backend.backend_type == "service" and hasattr(backend, "_adapter"):
        try:
            result = backend._adapter._client.list_workers()
            return result.get("data", result)
        except Exception:
            # SEC-14: return an opaque error_id instead of the exception message.
            error_id = uuid.uuid4().hex[:12]
            system_logger.warning("Failed to fetch worker list from CasCor [error_id=%s]", error_id)
            return {"workers": [], "count": 0, "error": "Upstream error", "error_id": error_id}

    # A1-iii-a: recurrence (one-shot LMU) has no worker pool — empty list, not demo fixtures.
    if backend.backend_type == "recurrence":
        return {"workers": [], "count": 0}

    import time

    return {
        "workers": [
            {
                "worker_id": "worker-demo-01",
                "capabilities": {"cpu_cores": 8, "gpu": False, "python": "3.13"},
                "connected_at": time.time() - 600,
                "last_heartbeat": time.time() - 2,
                "tasks_completed": 25,
                "tasks_failed": 0,
                "active_task_id": None,
                "health_score": 1.0,
                "idle": True,
            },
            {
                "worker_id": "worker-demo-02",
                "capabilities": {"cpu_cores": 4, "gpu": True, "python": "3.13"},
                "connected_at": time.time() - 300,
                "last_heartbeat": time.time() - 1,
                "tasks_completed": 17,
                "tasks_failed": 1,
                "active_task_id": "task-cn-round-7-cand-3",
                "health_score": 0.9444,
                "idle": False,
            },
        ],
        "count": 2,
    }


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    """
    General WebSocket endpoint for compatibility.

    Security gates (SEC-05, SEC-06, SEC-12) mirror /ws/training and
    /ws/control so every WebSocket route enforces the same policy:
    1. API-key header auth (legacy)
    2. Opt-in Sec-WebSocket-Protocol bearer-token auth
    3. Origin allowlist (CSWSH defense)
    4. Per-IP connection cap

    Handles both text and non-text frames gracefully.
    """
    # PR-1 (C5): read-only compat stream — relax the key gate so the keyless
    # same-origin browser is admitted by the Origin gate below (no state to
    # forge, no CSRF frame). A present key is still validated.
    if not await _authenticate_websocket(websocket, allow_browser_auth=True):
        return

    # SEC-06: opt-in bearer-token auth over Sec-WebSocket-Protocol
    ws_auth_ok, ws_subprotocol = await _authenticate_websocket_token(websocket)
    if not ws_auth_ok:
        return

    # SEC-05 / SEC-12: Origin validation (parity with /ws/training, /ws/control)
    from ws_security import validate_origin

    ws_settings = settings.websocket
    if ws_settings.allowed_origins:
        if not validate_origin(websocket, ws_settings.allowed_origins):
            from audit_log import log_ws_origin_rejected

            origin = websocket.headers.get("origin", "")
            client_ip = websocket.client[0] if websocket.client else "unknown"
            log_ws_origin_rejected("/ws", client_ip, origin)
            await websocket.close(code=4003, reason="Origin not allowed")
            return

    # SEC-F19 / D4: per-IP cap (DoS-dampening, INERT BEHIND NAT) + per-session
    # cap keyed on the anonymous canopy_session cookie; the global cap
    # (connect()) backstops cookieless connections. Parity with /ws/training,
    # /ws/control. Over-cap -> close 1013.
    if not websocket_manager.check_connection_limits(
        websocket,
        max_per_ip=ws_settings.max_connections_per_ip,
        max_per_session=ws_settings.max_connections_per_session,
    ):
        await websocket.close(code=1013, reason="Per-IP connection limit reached")
        return

    try:
        connected = await websocket_manager.connect(websocket, subprotocol=ws_subprotocol)
    except Exception:
        websocket_manager.release_connection_limits(websocket)
        raise
    if not connected:
        websocket_manager.release_connection_limits(websocket)
        return
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        system_logger.error("Unexpected error on /ws endpoint", exc_info=True)
    finally:
        websocket_manager.disconnect(websocket)


def _control_result_failure(result: Any) -> Optional[str]:
    """Return the backend failure message when a control result signals failure, else None.

    Backends return ``ControlResult`` (TypedDict, total=False): only an explicit
    ``ok=False`` is a failure. An absent ``ok`` (demo-state dicts) or a non-dict
    result keeps the legacy success interpretation, so demo and pre-ControlResult
    shapes are unaffected. Phase D §S10 error surfacing keys off error envelopes
    and non-2xx responses — wrapping an ``ok=False`` result in a success envelope
    is the "dead button" class (training-start diagnosis 2026-07-09 §4.2).
    """
    if isinstance(result, dict) and result.get("ok") is False:
        return str(result.get("error") or "command failed")
    return None


class _TrainStartBody(BaseModel):
    """Optional body for ``POST /api/train/start`` (A1-iii-a).

    Lets a one-shot (recurrence) fit carry its dataset reference + LMU hyperparameters.
    Ignored for cascor/demo (which start from a separately-staged/pending dataset). Every
    field is optional so the existing no-body ``?reset=`` callers are unaffected.
    """

    dataset: dict | None = None  # {generator | name | dataset_id, params, split}
    d: int | None = None
    theta: float | None = None
    ridge: float | None = None


@app.post("/api/train/start", dependencies=[Depends(require_browser_control_auth)])
async def api_train_start(reset: bool = False, body: _TrainStartBody | None = None):
    """
    Start training.
    Args:
        reset: Whether to reset network before starting
        body: Optional one-shot dataset ref + LMU hyperparameters (recurrence only)
    Returns:
        Training status
    """
    from fastapi import HTTPException

    from communication.websocket_manager import create_control_ack_message

    # A1-iii-a: forward a one-shot dataset-ref + hyperparameters for recurrence; cascor/demo
    # keep the bare reset-only call (no extra kwargs reach their start_training).
    # N3 note: the start-fresh toggle (Q4) is driven exclusively through the
    # dedicated POST /api/train/restart orchestration route, which calls
    # ``backend.start_training(reset=..., start_fresh=...)`` directly — the plain
    # Start route keeps its existing signature (start_fresh defaults to False).
    start_kwargs = _recurrence_start_kwargs(body.model_dump()) if (backend.backend_type == "recurrence" and body is not None) else {}
    result = backend.start_training(reset=reset, **start_kwargs)
    failure = _control_result_failure(result)
    if failure is not None:
        system_logger.warning("Training start rejected: %s", failure)
        schedule_broadcast(websocket_manager.broadcast(create_control_ack_message("start", False, failure)))
        raise HTTPException(status_code=409, detail=f"Training could not be started: {failure}")
    message = "Training started successfully"
    schedule_broadcast(websocket_manager.broadcast(create_control_ack_message("start", True, message)))
    return {"status": "started", **result}


@app.post("/api/train/pause", dependencies=[Depends(require_browser_control_auth)])
async def api_train_pause():
    """
    Pause training.
    Returns:
        Training status
    """
    from fastapi import HTTPException

    from communication.websocket_manager import create_control_ack_message

    result = backend.pause_training()
    failure = _control_result_failure(result)
    if failure is not None:
        system_logger.warning("Training pause rejected: %s", failure)
        schedule_broadcast(websocket_manager.broadcast(create_control_ack_message("pause", False, failure)))
        raise HTTPException(status_code=409, detail=f"Training could not be paused: {failure}")
    schedule_broadcast(websocket_manager.broadcast(create_control_ack_message("pause", True, "Training paused")))
    return {"status": "paused"}


@app.post("/api/train/resume", dependencies=[Depends(require_browser_control_auth)])
async def api_train_resume():
    """
    Resume training.
    Returns:
        Training status
    """
    from fastapi import HTTPException

    from communication.websocket_manager import create_control_ack_message

    result = backend.resume_training()
    failure = _control_result_failure(result)
    if failure is not None:
        system_logger.warning("Training resume rejected: %s", failure)
        schedule_broadcast(websocket_manager.broadcast(create_control_ack_message("resume", False, failure)))
        raise HTTPException(status_code=409, detail=f"Training could not be resumed: {failure}")
    schedule_broadcast(websocket_manager.broadcast(create_control_ack_message("resume", True, "Training resumed")))
    return {"status": "running"}


@app.post("/api/train/stop", dependencies=[Depends(require_browser_control_auth)])
async def api_train_stop():
    """
    Stop training.
    Returns:
        Training status
    """
    from fastapi import HTTPException

    from communication.websocket_manager import create_control_ack_message

    result = backend.stop_training()
    failure = _control_result_failure(result)
    if failure is not None:
        system_logger.warning("Training stop rejected: %s", failure)
        schedule_broadcast(websocket_manager.broadcast(create_control_ack_message("stop", False, failure)))
        raise HTTPException(status_code=409, detail=f"Training could not be stopped: {failure}")
    schedule_broadcast(websocket_manager.broadcast(create_control_ack_message("stop", True, "Training stopped")))
    return {"status": "stopped"}


@app.post("/api/train/reset", dependencies=[Depends(require_browser_control_auth)])
async def api_train_reset():
    """
    Reset training.
    Returns:
        Training status with reset state
    """
    from fastapi import HTTPException

    from communication.websocket_manager import create_control_ack_message

    result = backend.reset_training()
    failure = _control_result_failure(result)
    if failure is not None:
        system_logger.warning("Training reset rejected: %s", failure)
        schedule_broadcast(websocket_manager.broadcast(create_control_ack_message("reset", False, failure)))
        raise HTTPException(status_code=409, detail=f"Training could not be reset: {failure}")
    schedule_broadcast(websocket_manager.broadcast(create_control_ack_message("reset", True, "Training reset")))
    return {"status": "reset", **result}


@app.get("/api/train/status", dependencies=[Depends(require_browser_control_auth)])
async def api_train_status():
    """
    Get current training status (P1-NEW-003).
    Returns:
        Training status dictionary with network info and training state.
    """
    return {"backend": backend.backend_type, "execution": backend.execution, **backend.get_status()}


class _TrainRestartBody(BaseModel):
    """Body for ``POST /api/train/restart`` (N3 cold-swap restart orchestration)."""

    # N3 / Q4 / cascor C5: start-fresh toggle (default off) — see _TrainStartBody.
    start_fresh: bool = False
    # Legacy network-reset flag, forwarded to the backend for demo parity (cascor
    # consumes the staged dataset + rebuilds regardless; start_fresh carries the
    # explicit model-discard semantics for the service path).
    reset: bool = True


async def _await_training_stopped(timeout_s: float, poll: float) -> bool:
    """Poll (bounded) until the backend reports training is no longer active.

    Returns True once stopped, False on timeout. Status reads run off the event
    loop (``asyncio.to_thread``) so a slow cascor cannot stall the single uvicorn
    worker while we wait out the current run (plan §8 stop→start race).
    """
    deadline = asyncio.get_running_loop().time() + timeout_s
    while True:
        if not await asyncio.to_thread(backend.is_training_active):
            return True
        if asyncio.get_running_loop().time() >= deadline:
            return False
        await asyncio.sleep(poll)


async def _peek_training_completed(budget: float, poll: float) -> bool:
    """Best-effort: did the just-started run already reach a terminal state?

    Folded finding 2 (2026-07-19 live pass): a ``start_fresh`` rebuild on a tiny
    dataset can converge at epoch 0 with empty history. This bounded peek lets the
    restart outcome read truthfully ("converged immediately") instead of looking
    frozen — it exits fast once the run is genuinely progressing (``is_running``
    with ``current_epoch > 0``) and swallows every error so it can NEVER turn a
    successful restart into a failure. Live status polling (N1/N2) remains the
    real source of truth.
    """
    try:
        deadline = asyncio.get_running_loop().time() + budget
        while True:
            status = await asyncio.to_thread(backend.get_status)
            if isinstance(status, dict):
                if status.get("completed") or status.get("failed"):
                    return True
                if status.get("is_running") and (status.get("current_epoch") or 0) > 0:
                    return False
            if asyncio.get_running_loop().time() >= deadline:
                return False
            await asyncio.sleep(poll)
    except Exception:  # pragma: no cover - the peek must never break a restart
        return False


@app.post("/api/train/restart", dependencies=[Depends(require_browser_control_auth)])
async def api_train_restart(body: _TrainRestartBody | None = None):
    """N3 (canopy training-runtime defects plan, I-6): cold-swap restart with the
    staged dataset, surfacing every step's outcome.

    Sequence (E-2 pin — a start against an ACTIVE run 409s immediately while the
    staged dataset config survives): stop (if a run is active) → await stopped
    (bounded) → start(start_fresh). Idle / completed / failed runs skip straight
    to start (cascor's engine FSM and the demo FSM both auto-reset from a terminal
    state on start), so no stop step is issued there.

    Replaces the pre-N3 fire-and-forget ``POST /api/train/start?reset=true``
    callback that returned only the banner ``is_open`` — three cold-swaps trained
    to completion invisibly in the 2026-07-11 incident. Returns a structured,
    per-step result so the dashboard renders a truthful outcome::

        {"success": bool, "steps": [{"step","ok","detail"}, ...], "was_active": bool,
         "start_fresh": bool, "instant_complete": bool, "status": "restarted"}

    A stop-await timeout returns 504 with ``retriable: True`` and leaves the staged
    dataset intact so the caller keeps the pending banner open and can retry.
    """
    from communication.websocket_manager import create_control_ack_message

    start_fresh = bool(body.start_fresh) if body is not None else False
    reset = bool(body.reset) if body is not None else True
    steps: list[dict] = []

    was_active = await asyncio.to_thread(backend.is_training_active)
    if was_active:
        stop_result = backend.stop_training()
        stop_failure = _control_result_failure(stop_result)
        if stop_failure is not None:
            steps.append({"step": "stop", "ok": False, "detail": stop_failure})
            system_logger.warning("Restart: stop rejected: %s", stop_failure)
            schedule_broadcast(websocket_manager.broadcast(create_control_ack_message("stop", False, stop_failure)))
            return JSONResponse({"success": False, "steps": steps, "was_active": True, "start_fresh": start_fresh, "message": f"Could not stop the current run: {stop_failure}"}, status_code=409)
        steps.append({"step": "stop", "ok": True, "detail": "Training stop requested"})
        schedule_broadcast(websocket_manager.broadcast(create_control_ack_message("stop", True, "Training stopped")))

        stopped = await _await_training_stopped(BackendConstants.RESTART_STOP_WAIT_TIMEOUT_SECONDS, BackendConstants.RESTART_STOP_WAIT_POLL_SECONDS)
        if not stopped:
            steps.append({"step": "await_stopped", "ok": False, "detail": f"still running after {BackendConstants.RESTART_STOP_WAIT_TIMEOUT_SECONDS:.0f}s"})
            system_logger.warning("Restart: timed out waiting for training to stop")
            return JSONResponse(
                {"success": False, "steps": steps, "was_active": True, "start_fresh": start_fresh, "retriable": True, "message": "Timed out waiting for the current run to stop — the dataset change is still staged; try Restart again."},
                status_code=504,
            )
        steps.append({"step": "await_stopped", "ok": True, "detail": "Training stopped"})

    # Start consumes the staged dataset; start_fresh discards the model when set.
    start_result = backend.start_training(reset=reset, start_fresh=start_fresh)
    start_failure = _control_result_failure(start_result)
    if start_failure is not None:
        steps.append({"step": "start", "ok": False, "detail": start_failure})
        system_logger.warning("Restart: start rejected: %s", start_failure)
        schedule_broadcast(websocket_manager.broadcast(create_control_ack_message("start", False, start_failure)))
        return JSONResponse({"success": False, "steps": steps, "was_active": was_active, "start_fresh": start_fresh, "message": f"Could not start the new run: {start_failure}"}, status_code=409)
    steps.append({"step": "start", "ok": True, "detail": "Training started (start-fresh)" if start_fresh else "Training started"})
    schedule_broadcast(websocket_manager.broadcast(create_control_ack_message("start", True, "Training started")))

    instant_complete = await _peek_training_completed(BackendConstants.RESTART_INSTANT_COMPLETE_PEEK_SECONDS, BackendConstants.RESTART_STOP_WAIT_POLL_SECONDS)

    return {"success": True, "steps": steps, "was_active": was_active, "start_fresh": start_fresh, "instant_complete": instant_complete, "status": "restarted"}


class _ModelSelectBody(BaseModel):
    """Request body for ``POST /api/model/select`` (A1-iv-2)."""

    nn_model: str


def _selection_targets_recurrence(nn_model: str) -> bool:
    """True when selecting ``nn_model`` should route to the recurrence service backend.

    Mirrors ``create_backend``'s routing: a model targets the recurrence backend iff it is a
    recurrence-provider model AND ``recurrence_service_url`` is configured. Every other
    selection (cascor, or recurrence without a configured URL) resolves to the default
    cascor/demo backend — so this single predicate decides whether a swap is a no-op (target
    backend type unchanged) or a real re-create.
    """
    from model_registry import RECURRENCE_PROVIDER, get_model_spec

    spec = get_model_spec(nn_model)
    return spec is not None and spec.provider == RECURRENCE_PROVIDER and bool(settings.recurrence_service_url)


def _model_state_response(nn_model: str, *, swapped: bool) -> dict:
    """Describe the live backend + current selection for the ``/api/model/*`` responses."""
    from model_registry import get_model_spec

    spec = get_model_spec(nn_model)
    return {
        "nn_model": nn_model,
        "backend": backend.backend_type,
        "execution": backend.execution,
        "status": spec.status if spec is not None else "unknown",
        "swapped": swapped,
    }


async def _swap_backend(nn_model: str) -> dict:
    """Re-create the process-global ``backend`` for a newly-selected model (A1-iv-2).

    Toggles between the recurrence (one-shot LMU) service backend and the default cascor/demo
    backend. **No-ops** when the selection would not change the live backend type, so
    re-selecting the active model never tears down a working connection. **Refuses** to swap
    while training is active (409). The new backend is created + initialized BEFORE the global
    is reassigned and the old one is shut down only AFTER — so concurrent requests always see a
    live backend, and a failed ``initialize()`` leaves the current backend untouched (502).
    D5: re-create, not multiplex (sufficient for the two-model population).
    """
    from fastapi import HTTPException

    from backend import create_backend

    global backend, current_nn_model

    if _selection_targets_recurrence(nn_model) == (backend.backend_type == "recurrence"):
        # Target backend type is unchanged — record the selection and skip the re-create.
        current_nn_model = nn_model
        return _model_state_response(nn_model, swapped=False)

    if backend.is_training_active():
        raise HTTPException(
            status_code=409,
            detail="Cannot switch models while training is active. Pause or stop training first.",
        )

    old_backend = backend
    new_backend = create_backend(nn_model=nn_model, service_url=_resolved_service_url)
    if not await new_backend.initialize():
        await new_backend.shutdown()
        raise HTTPException(status_code=502, detail=f"Failed to initialize the backend for model {nn_model!r}.")

    backend = new_backend
    current_nn_model = nn_model
    _seed_training_state(new_backend)
    set_demo_mode_active(new_backend.backend_type == "demo")
    await old_backend.shutdown()
    system_logger.info("Backend swapped for model %r -> %s", nn_model, new_backend.backend_type)
    return _model_state_response(nn_model, swapped=True)


@app.post("/api/model/select")
async def api_model_select(body: _ModelSelectBody):
    """Select the active NN model, re-creating the backend if the target changes (A1-iv-2).

    The A1 model picker (A1-iv-3/iv-4) POSTs the chosen model key here. Validates the key
    against the registry, then swaps the process-global backend (a no-op when the live backend
    type is unchanged). Lifecycle ``status`` gating (``coming_soon`` etc.) is the picker's job;
    this endpoint is the mechanism and returns the model ``status`` so the UI can reflect it.
    """
    from fastapi import HTTPException

    from model_registry import get_model_spec

    if get_model_spec(body.nn_model) is None:
        raise HTTPException(status_code=422, detail=f"Unknown model: {body.nn_model!r}")
    return await _swap_backend(body.nn_model)


class SetParamsRequest(BaseModel):
    """Validated request body for the set_params endpoint."""

    # Neural network parameters
    nn_max_iterations: int | None = None
    nn_max_total_epochs: int | None = None
    nn_learning_rate: float | None = None
    nn_max_hidden_units: int | None = None
    nn_multi_node_layers: bool | None = None
    nn_growth_trigger: str | None = None
    nn_growth_preset_epochs: int | None = None
    nn_growth_convergence_threshold: float | None = None
    nn_patience: int | None = None
    nn_spiral_rotations: float | None = None
    nn_spiral_number: int | None = None
    nn_dataset_elements: int | None = None
    nn_dataset_noise: float | None = None
    # #2b: previously omitted here, so these three were silently dropped before
    # reaching the adapter (which DOES map them). The dashboard already sends them.
    nn_output_epochs: int | None = None
    nn_optimizer_type: str | None = None
    nn_activation_function_name: str | None = None
    # init_output_weights is consumed by the set_params handler (nn_keys) and
    # surfaced on /api/state, but was missing from this request model — so the
    # dashboard's dropdown value was silently dropped at parse time
    # (Pydantic extra="ignore") and never reached the backend. Declared now.
    nn_init_output_weights: str | None = None

    # Candidate parameters
    cn_pool_size: int | None = None
    cn_correlation_threshold: float | None = None
    cn_candidate_learning_rate: float | None = None
    cn_patience: int | None = None
    cn_selected_candidates: int | None = None
    cn_training_complete: str | None = None
    cn_training_iterations: int | None = None
    cn_training_convergence_threshold: float | None = None
    cn_multi_candidate: bool | None = None
    cn_candidate_selection: str | None = None
    cn_top_candidates: int | None = None
    cn_random_candidates: int | None = None

    # Backward-compatible keys
    learning_rate: float | None = None
    max_hidden_units: int | None = None
    max_epochs: int | None = None
    convergence_enabled: bool | None = None
    convergence_threshold: float | None = None
    patience: int | None = None
    spiral_rotations: float | None = None


@app.post("/api/set_params")
async def api_set_params(body: SetParamsRequest):
    """
    Set training parameters with nn_* and cn_* prefixed keys.
    Also accepts old-style keys for backward compatibility.
    Args:
        body: Validated SetParamsRequest containing parameters to update
    Returns:
        Updated training state
    """
    try:
        params = body.model_dump(exclude_none=True)
        # Backward-compatible mapping: old-style keys -> new prefixed keys
        compat_map = {
            "learning_rate": "nn_learning_rate",
            "max_hidden_units": "nn_max_hidden_units",
            "max_epochs": "nn_max_total_epochs",
            "convergence_enabled": "convergence_enabled",
            "convergence_threshold": "nn_growth_convergence_threshold",
            "patience": "nn_patience",
            "spiral_rotations": "nn_spiral_rotations",
        }
        # Normalize old-style keys into prefixed keys (prefixed keys take precedence)
        for old_key, new_key in compat_map.items():
            if old_key in params and new_key not in params:
                params[new_key] = params.pop(old_key)

        # All recognized nn_* and cn_* parameter keys
        nn_keys = [
            "nn_max_iterations",
            "nn_max_total_epochs",
            "nn_init_output_weights",
            "nn_learning_rate",
            "nn_max_hidden_units",
            "nn_multi_node_layers",
            "nn_growth_trigger",
            "nn_growth_preset_epochs",
            "nn_growth_convergence_threshold",
            "nn_patience",
            "nn_spiral_rotations",
            "nn_spiral_number",
            "nn_dataset_elements",
            "nn_dataset_noise",
            "nn_output_epochs",
            "nn_optimizer_type",
            "nn_activation_function_name",
        ]
        cn_keys = [
            "cn_pool_size",
            "cn_correlation_threshold",
            "cn_candidate_learning_rate",
            "cn_patience",
            "cn_selected_candidates",
            "cn_training_complete",
            "cn_training_iterations",
            "cn_training_convergence_threshold",
            "cn_multi_candidate",
            "cn_candidate_selection",
            "cn_top_candidates",
            "cn_random_candidates",
        ]

        # Collect all recognized params
        backend_updates = {}
        for key in nn_keys + cn_keys:
            if key in params and params[key] is not None:
                backend_updates[key] = params[key]

        # Also pass through convergence_enabled if present (backward compat, no prefix)
        if "convergence_enabled" in params and params["convergence_enabled"] is not None:
            backend_updates["convergence_enabled"] = bool(params["convergence_enabled"])

        if not backend_updates:
            return JSONResponse({"error": "No parameters provided"}, status_code=400)

        # Update TrainingState with backward-compatible keys it understands
        ts_updates = {}
        if "nn_learning_rate" in backend_updates:
            ts_updates["learning_rate"] = float(backend_updates["nn_learning_rate"])
        if "nn_max_hidden_units" in backend_updates:
            ts_updates["max_hidden_units"] = int(backend_updates["nn_max_hidden_units"])
        if "nn_max_total_epochs" in backend_updates:
            ts_updates["max_epochs"] = int(backend_updates["nn_max_total_epochs"])
        if "nn_max_iterations" in backend_updates:
            ts_updates["max_iterations"] = int(backend_updates["nn_max_iterations"])
        if "nn_init_output_weights" in backend_updates:
            ts_updates["init_output_weights"] = str(backend_updates["nn_init_output_weights"])
        if "cn_pool_size" in backend_updates:
            ts_updates["candidate_pool_size"] = int(backend_updates["cn_pool_size"])
        if "nn_growth_convergence_threshold" in backend_updates:
            ts_updates["convergence_threshold"] = float(backend_updates["nn_growth_convergence_threshold"])
        if "nn_patience" in backend_updates:
            ts_updates["patience"] = int(backend_updates["nn_patience"])
        if "cn_correlation_threshold" in backend_updates:
            ts_updates["correlation_threshold"] = float(backend_updates["cn_correlation_threshold"])
        if "cn_candidate_learning_rate" in backend_updates:
            ts_updates["candidate_learning_rate"] = float(backend_updates["cn_candidate_learning_rate"])
        # Forward all params to backend FIRST (offloaded to thread for sync backends)
        result = await asyncio.to_thread(backend.apply_params, **backend_updates)
        skipped: list = []
        # N5 (I-4 / T3): cascor's C2a applied/skipped(reason) partition — which
        # submitted keys the live network actually took vs. declined (with the
        # reason). Distinct from ``skipped`` above (canopy keys with no cascor
        # mapping, never sent). Threaded into the response so the dashboard toast
        # can render both. Absent on a pre-C2a backend → empty lists.
        applied_detail: list = []
        skipped_detail: list = []
        if isinstance(result, dict):
            if not result.get("ok", True):
                error_msg = result.get("error", "unknown")
                system_logger.warning("Backend parameter application failed: %s", error_msg)
                # FRONTEND_ISSUES_PLAN_2026-05-09 §1.5 C1a: even on failure, surface
                # which keys never made it through the adapter map so the user can
                # tell "backend rejected my values" from "canopy never asked the
                # backend in the first place".
                err_payload = {"error": f"Backend rejected parameters: {error_msg}"}
                if result.get("skipped"):
                    err_payload["skipped"] = result["skipped"]
                return JSONResponse(err_payload, status_code=502)
            skipped = list(result.get("skipped") or [])  # type: ignore[call-overload]  # pre-existing: dict.get() is object-typed, runtime value is a list (surfaced by the A1-iv-2 main.py mypy re-check)
            applied_detail = list(result.get("applied") or [])  # type: ignore[call-overload]  # runtime value is list[str] (C2a applied, canopy-keyed)
            skipped_detail = list(result.get("skipped_detail") or [])  # type: ignore[call-overload]  # runtime value is list[{key, reason}] (C2a skipped, canopy-keyed)

        # Only update TrainingState AFTER backend confirms success
        if ts_updates:
            training_state.update_state(**ts_updates)
        system_logger.info("Parameters updated: %s", backend_updates)

        # Broadcast params update with applied parameters
        broadcast_data = {**training_state.get_state(), "applied_params": backend_updates}
        await websocket_manager.broadcast({"type": "params_updated", "data": broadcast_data})

        # FRONTEND_ISSUES_PLAN_2026-05-09 §1.5 C1a: thread the adapter's `skipped`
        # list into the response so the dashboard handler can show
        # "Applied X of Y; Z not yet supported by the backend: …" instead of the
        # misleading "Parameters applied" toast for every call.
        response: dict = {"status": "success", "state": training_state.get_state()}
        if skipped:
            response["skipped"] = skipped
        # N5: additive C2a partition (both empty on a pre-C2a backend).
        if applied_detail:
            response["applied"] = applied_detail
        if skipped_detail:
            response["skipped_detail"] = skipped_detail
        return response
    except Exception as exc:
        # SEC-14: return an opaque error_id; full traceback goes to logs only.
        error_id = uuid.uuid4().hex[:12]
        system_logger.error("Failed to set parameters [error_id=%s]", error_id, exception=exc)
        return JSONResponse(
            {"error": "Internal server error", "error_id": error_id},
            status_code=500,
        )


# =========================================================================
# FRONTEND_ISSUES_PLAN_2026-05-09 §3.5.1 + §3.5.2 Phase 1 — Issue #3
# Pending dataset stage / cancel endpoints. Mirrors cascor #242.
# =========================================================================


class StageDatasetRequest(BaseModel):
    """Body for POST /api/stage_dataset.

    All fields optional so the dashboard can build the body from whatever
    subset of dataset inputs the user touched. The cascor side
    (StageDatasetRequest) is the authoritative validator; we forward
    blindly via the adapter.
    """

    nn_dataset_type: Optional[str] = None
    nn_dataset_elements: Optional[int] = None
    nn_dataset_noise: Optional[float] = None
    nn_spiral_rotations: Optional[float] = None
    nn_spiral_number: Optional[int] = None
    # N7 (I-7): generic generator params for non-spiral generators whose inputs are not covered by
    # the typed convenience fields above (e.g. mnist: dataset/flatten; equities: regression_target).
    # Forwarded verbatim to cascor's StageDatasetRequest.params channel (the adapter maps the canopy
    # key -> cascor ``params``), which cascor merges into its create_dataset call. Keeps the legacy
    # spiral/xor bodies unchanged (no key present) while letting schema-driven generators pass
    # arbitrary params without widening the typed fields.
    nn_dataset_params: Optional[dict[str, Any]] = None


@app.post("/api/stage_dataset")
async def api_stage_dataset(body: StageDatasetRequest):
    """Stage a dataset-config change for the next start_training.

    Returns the staged config + the adapter's ``ok`` flag. On backend
    rejection (e.g. unknown dataset_type) returns 502 with the cascor
    error string.
    """
    try:
        params = body.model_dump(exclude_none=True)
        result = await asyncio.to_thread(backend.stage_dataset, **params)
        if isinstance(result, dict) and not result.get("ok", True):
            error_msg = result.get("error", "unknown")
            system_logger.warning("Backend rejected dataset staging: %s", error_msg)
            return JSONResponse({"error": f"Backend rejected dataset: {error_msg}"}, status_code=502)
        return {"status": "success", "data": (result or {}).get("data", {})}
    except Exception as exc:
        # SEC-14: opaque error_id; full traceback to logs only.
        error_id = uuid.uuid4().hex[:12]
        system_logger.error("Failed to stage dataset [error_id=%s]", error_id, exception=exc)
        return JSONResponse({"error": "Internal server error", "error_id": error_id}, status_code=500)


@app.delete("/api/cancel_pending_dataset")
async def api_cancel_pending_dataset():
    """Cancel any staged dataset change — Phase 1 Cancel button target."""
    try:
        result = await asyncio.to_thread(backend.cancel_pending_dataset)
        if isinstance(result, dict) and not result.get("ok", True):
            error_msg = result.get("error", "unknown")
            system_logger.warning("Backend rejected dataset cancel: %s", error_msg)
            return JSONResponse({"error": f"Backend rejected cancel: {error_msg}"}, status_code=502)
        return {"status": "success", "data": (result or {}).get("data", {})}
    except Exception as exc:
        error_id = uuid.uuid4().hex[:12]
        system_logger.error("Failed to cancel pending dataset [error_id=%s]", error_id, exception=exc)
        return JSONResponse({"error": "Internal server error", "error_id": error_id}, status_code=500)


# =========================================================================
# Phase 2 P2-4 (Issue #3): Experimental Functions gate proxy.
# Canopy proxies cascor's /v1/admin/experimental_functions through its own
# backend so the Dash callback layer keeps a single HTTP target convention
# and inherits canopy's X-API-Key auth boundary. F2.10 in
# ISSUE_3_PHASE_2_LIVE_DATASET_SWAP_2026-05-09 makes the cascor side the
# authoritative source of truth — these routes faithfully forward whatever
# state cascor reports back.
# =========================================================================


class ExperimentalFunctionsRequest(BaseModel):
    """Body for POST /api/admin/experimental_functions."""

    enabled: bool


@app.get("/api/admin/experimental_functions")
async def api_get_experimental_functions():
    """Read the server-side experimental-functions gate state.

    Returns ``{"status": "success", "data": {"enabled": bool}}`` on success.
    On backend rejection / cascor unreachable: 502 with the error string,
    and the dash callback layer treats that as "gate is closed" (F2.10
    safe default — no Live Switch affordance until we can confirm).
    """
    try:
        result = await asyncio.to_thread(backend.get_experimental_functions)
        if isinstance(result, dict) and not result.get("ok", True):
            error_msg = result.get("error", "unknown")
            system_logger.warning("Backend rejected experimental_functions read: %s", error_msg)
            return JSONResponse({"error": f"Backend rejected: {error_msg}"}, status_code=502)
        return {"status": "success", "data": {"enabled": bool((result or {}).get("enabled", False))}}
    except Exception as exc:
        error_id = uuid.uuid4().hex[:12]
        system_logger.error("Failed to read experimental_functions [error_id=%s]", error_id, exception=exc)
        return JSONResponse({"error": "Internal server error", "error_id": error_id}, status_code=500)


@app.post("/api/admin/experimental_functions")
async def api_set_experimental_functions(body: ExperimentalFunctionsRequest):
    """Toggle the server-side experimental-functions gate.

    Returns the gate state AFTER cascor's write completed. F2.10: the
    returned ``enabled`` may differ from the request body if cascor's
    policy overrides (e.g., env-var lockdown). The Dash callback layer
    must trust the returned value and reconcile UI state to it.
    """
    try:
        result = await asyncio.to_thread(backend.set_experimental_functions, body.enabled)
        if isinstance(result, dict) and not result.get("ok", True):
            error_msg = result.get("error", "unknown")
            system_logger.warning("Backend rejected experimental_functions write: %s", error_msg)
            return JSONResponse({"error": f"Backend rejected: {error_msg}"}, status_code=502)
        return {"status": "success", "data": {"enabled": bool((result or {}).get("enabled", False))}}
    except Exception as exc:
        error_id = uuid.uuid4().hex[:12]
        system_logger.error("Failed to set experimental_functions [error_id=%s]", error_id, exception=exc)
        return JSONResponse({"error": "Internal server error", "error_id": error_id}, status_code=500)


# =========================================================================
# Phase 2 P2-5 (Issue #3): Live Dataset Switch proxy.
# POST /api/live_dataset_swap → backend.swap_dataset_live → cascor's
# /v1/training/dataset/live (the P2-1a/P2-1d/P2-2/P2-3 endpoint).
# DELETE /api/live_dataset_swap → backend.cancel_swap_dataset_live →
# cascor's DELETE (P2-1b cancel mechanism). The Dash callback fires
# the POST on Dash's worker pool, so the Cancel button (a separate
# callback) can fire the DELETE concurrently while the POST is still
# in flight — cascor's swap aborts at its next checkpoint and the
# POST returns with ``{"status": "cancelled"}``.
# =========================================================================


@app.post("/api/live_dataset_swap")
async def api_live_dataset_swap(body: StageDatasetRequest):
    """Initiate an in-flight live dataset swap.

    Reuses ``StageDatasetRequest`` body shape — same canopy keys cascor
    accepts for both ``POST /v1/training/dataset`` (cold swap) and
    ``POST /v1/training/dataset/live`` (live swap). All fields optional;
    cascor is the authoritative validator.

    Response on success: ``{"status": "success", "data": {<§3.3 dict>}}``
    carrying ``status`` (``"swapped"`` or ``"cancelled"``), ``arch_changes``,
    ``pre_swap_snapshot_id``, ``post_swap_snapshot_id``, ``mode``, etc.

    Cascor rejection codes (403 gate, 409 in-flight, 422 validation,
    504 pause-timeout, 502 fetch failure) all collapse to canopy 502
    here; the Dash callback layer surfaces the error string in a toast.
    """
    try:
        params = body.model_dump(exclude_none=True)
        result = await asyncio.to_thread(backend.swap_dataset_live, **params)
        if isinstance(result, dict) and not result.get("ok", True):
            error_msg = result.get("error", "unknown")
            system_logger.warning("Backend rejected live dataset swap: %s", error_msg)
            return JSONResponse({"error": f"Backend rejected live swap: {error_msg}"}, status_code=502)
        return {"status": "success", "data": (result or {}).get("data", {})}
    except Exception as exc:
        error_id = uuid.uuid4().hex[:12]
        system_logger.error("Failed to swap dataset live [error_id=%s]", error_id, exception=exc)
        return JSONResponse({"error": "Internal server error", "error_id": error_id}, status_code=500)


@app.delete("/api/live_dataset_swap")
async def api_cancel_live_dataset_swap():
    """Cancel an in-flight live dataset swap.

    Fires cascor's ``DELETE /v1/training/dataset/live`` (P2-1b). Cascor
    sets its internal cancel flag; the in-flight swap aborts at the
    next checkpoint and the originating POST returns with
    ``{"status": "cancelled"}``.

    Returns 502 when cascor returns 404 (no swap in flight) — the Dash
    callback layer treats that as "Cancel had no effect, swap already
    finished" and leaves the UI alone.
    """
    try:
        result = await asyncio.to_thread(backend.cancel_swap_dataset_live)
        if isinstance(result, dict) and not result.get("ok", True):
            error_msg = result.get("error", "unknown")
            system_logger.warning("Backend rejected live swap cancel: %s", error_msg)
            return JSONResponse({"error": f"Backend rejected cancel: {error_msg}"}, status_code=502)
        return {"status": "success", "data": (result or {}).get("data", {})}
    except Exception as exc:
        error_id = uuid.uuid4().hex[:12]
        system_logger.error("Failed to cancel live dataset swap [error_id=%s]", error_id, exception=exc)
        return JSONResponse({"error": "Internal server error", "error_id": error_id}, status_code=500)


# =========================================================================
# Phase 2 P2-7 (Issue #3): dataset_swap event feed for canopy timeline /
# paired-diff / snapshot-badge consumers. Proxies cascor's follow-up B
# (#255) — ``GET /v1/history/dataset_swaps`` — so the canopy callback
# layer keeps its single-HTTP-target convention.
#
# ``since`` query param is forwarded verbatim so a poller can pass its
# last-seen timestamp and get only strictly-newer events on subsequent
# ticks. Empty-list response is normal (no swaps yet) and not an error.
# =========================================================================


@app.get("/api/history/dataset_swaps")
async def api_get_dataset_swap_events(since: Optional[str] = None):
    """Read the canopy session's live dataset_swap event list.

    Returns ``{"status": "success", "data": {"events": [...]}}`` on
    success. Each event has the §3.9 schema (``timestamp``, ``before_cfg``,
    ``after_cfg``, ``arch_changes``, ``pre_swap_snapshot_id``,
    ``post_swap_snapshot_id``).

    Cascor / backend failure → 502 with the error string. The canopy
    panels treat a 502 as "no events known yet" and render empty state.
    """
    try:
        result = await asyncio.to_thread(backend.get_dataset_swap_events, since=since)
        if isinstance(result, dict) and not result.get("ok", True):
            error_msg = result.get("error", "unknown")
            system_logger.warning("Backend rejected dataset_swap events fetch: %s", error_msg)
            return JSONResponse({"error": f"Backend rejected: {error_msg}"}, status_code=502)
        events = (result or {}).get("events", []) or []
        return {"status": "success", "data": {"events": events}}
    except Exception as exc:
        error_id = uuid.uuid4().hex[:12]
        system_logger.error("Failed to fetch dataset_swap events [error_id=%s]", error_id, exception=exc)
        return JSONResponse({"error": "Internal server error", "error_id": error_id}, status_code=500)


@app.get("/api/snapshots/{snapshot_id}/history/dataset_swaps")
async def api_get_snapshot_dataset_swaps(snapshot_id: str):
    """Read a stored snapshot's own dataset_swap event list.

    P2-7 follow-up (Issue #3) — proxies cascor's
    ``GET /v1/snapshots/{id}/history/dataset_swaps`` (cascor #259). The
    Replay timeline reads this when a snapshot is loaded so markers
    reflect the snapshot's own history (parent spec §4.4 full flavor)
    rather than the live event feed.

    Backend failure (including cascor 404 for a missing snapshot) → 502
    with the error string. The timeline treats a 502 as "no markers for
    this snapshot" and degrades to the live-event-only render so a
    missing or unreadable snapshot never produces a hard UI error.
    """
    try:
        result = await asyncio.to_thread(backend.get_snapshot_dataset_swaps, snapshot_id=snapshot_id)
        if isinstance(result, dict) and not result.get("ok", True):
            error_msg = result.get("error", "unknown")
            system_logger.warning("Backend rejected snapshot dataset_swap events fetch (%s): %s", snapshot_id, error_msg)
            return JSONResponse({"error": f"Backend rejected: {error_msg}"}, status_code=502)
        events = (result or {}).get("events", []) or []
        return {"status": "success", "data": {"events": events}}
    except Exception as exc:
        error_id = uuid.uuid4().hex[:12]
        system_logger.error("Failed to fetch snapshot dataset_swap events [error_id=%s, snapshot_id=%s]", error_id, snapshot_id, exception=exc)
        return JSONResponse({"error": "Internal server error", "error_id": error_id}, status_code=500)


# =========================================================================
# P1-NEW-002: Remote Worker Management Endpoints
# =========================================================================


@app.get("/api/remote/status")
async def api_remote_status():
    """
    Get remote worker connection status (P1-NEW-002).
    Returns:
        Dictionary with remote worker status information.
    """
    if backend.backend_type == "service" and hasattr(backend, "_adapter"):
        return backend._adapter.get_remote_worker_status()
    return {"available": False, "connected": False, "workers_active": False, "error": "Not available in demo mode"}


class RemoteConnectRequest(BaseModel):
    """Request body for ``POST /api/remote/connect`` (SEC-13).

    The authkey was previously a query parameter and therefore leaked into
    web-server access logs, browser history, and Referer headers. It now
    travels in the POST body as a ``SecretStr`` so it is redacted in
    Pydantic logs/reprs and never appears in URLs.
    """

    host: str = Field(..., min_length=1)
    port: int = Field(..., ge=1, le=65535)
    authkey: SecretStr


@app.post("/api/remote/connect")
async def api_remote_connect(request: RemoteConnectRequest):
    """
    Connect to a remote CandidateTrainingManager (P1-NEW-002).

    Request body (SEC-13): ``{"host": str, "port": int, "authkey": str}``.
    Callers that still send ``authkey`` as a query parameter will receive a
    422 from FastAPI because the body is now required.
    """
    if backend.backend_type != "service" or not hasattr(backend, "_adapter"):
        return JSONResponse({"error": "Not available in demo mode"}, status_code=503)

    try:
        success = backend._adapter.connect_remote_workers((request.host, request.port), request.authkey.get_secret_value())
        if success:
            return {"status": "connected", "address": f"{request.host}:{request.port}"}
        return JSONResponse({"error": "Connection failed"}, status_code=500)
    except Exception as exc:
        error_id = uuid.uuid4().hex[:12]
        system_logger.error(
            f"Remote connect failed [error_id={error_id} host={request.host} port={request.port}]",
            exception=exc,
        )
        return JSONResponse(
            {"error": "Internal server error", "error_id": error_id},
            status_code=500,
        )


@app.post("/api/remote/start_workers")
async def api_remote_start_workers(num_workers: int = 1):
    """
    Start remote worker processes (P1-NEW-002).
    Args:
        num_workers: Number of workers to start (default: 1).
    Returns:
        Worker start status.
    """
    if backend.backend_type != "service" or not hasattr(backend, "_adapter"):
        return JSONResponse({"error": "Not available in demo mode"}, status_code=503)

    success = backend._adapter.start_remote_workers(num_workers)
    if success:
        return {"status": "started", "num_workers": num_workers}
    return JSONResponse({"error": "Failed to start workers"}, status_code=500)


@app.post("/api/remote/stop_workers")
# ``timeout`` is a passthrough query/body parameter consumed by the adapter's
# ``stop_remote_workers`` call, not a deadline for this handler. ASYNC109
# wants ``asyncio.timeout`` instead, but the parameter never bounds awaitable
# work in this function — silencing is the correct call.
async def api_remote_stop_workers(timeout: int = 10):  # noqa: ASYNC109
    """
    Stop remote worker processes (P1-NEW-002).
    Args:
        timeout: Timeout for graceful shutdown (default: 10s).
    Returns:
        Worker stop status.
    """
    if backend.backend_type != "service" or not hasattr(backend, "_adapter"):
        return JSONResponse({"error": "Not available in demo mode"}, status_code=503)

    success = backend._adapter.stop_remote_workers(timeout)
    if success:
        return {"status": "stopped"}
    return JSONResponse({"error": "Failed to stop workers"}, status_code=500)


@app.post("/api/remote/disconnect")
async def api_remote_disconnect():
    """
    Disconnect from remote manager (P1-NEW-002).
    Returns:
        Disconnection status.
    """
    if backend.backend_type != "service" or not hasattr(backend, "_adapter"):
        return JSONResponse({"error": "Not available in demo mode"}, status_code=503)

    success = backend._adapter.disconnect_remote_workers()
    if success:
        return {"status": "disconnected"}
    return JSONResponse({"error": "Failed to disconnect"}, status_code=500)


# ── Phase B: Browser WebSocket observability endpoints ────────────────

# Prometheus metrics singletons (created once, reused)
_ws_latency_hist = None
_ws_error_counter = None

try:
    from juniper_observability import register_or_reuse as _register_or_reuse
    from prometheus_client import Counter as _PromCounter
    from prometheus_client import Histogram as _PromHistogram

    # METRICS-MON R4.1: bucket layout is **tentative pending R5.1**.
    # Per-boundary SLO rationale lives in
    # ``notes/observability/HISTOGRAM_BUCKETS_RATIONALE_2026-05-02.md``.
    # R5.1's SLO catalog will ratify or reshape; re-bucketing is a
    # metric-version event but not a public-API break.
    _ws_latency_hist = _register_or_reuse(
        _PromHistogram,
        "canopy_ws_browser_latency_ms",
        "Browser-reported WebSocket round-trip latency (R4.1 buckets tentative pending R5.1)",
        ["endpoint"],
        buckets=[5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000],
    )
    _ws_error_counter = _register_or_reuse(
        _PromCounter,
        "canopy_ws_browser_errors_total",
        "Browser-reported WebSocket errors",
        ["endpoint"],
    )
except Exception:  # nosec B110 — graceful degradation when prometheus_client not installed
    pass


class WsLatencyReport(BaseModel):
    """Browser-reported WebSocket round-trip latency sample."""

    latency_ms: float
    endpoint: str = "/ws/training"


class WsBrowserErrorReport(BaseModel):
    """Browser-reported WebSocket error."""

    error: str
    endpoint: str = "/ws/training"
    user_agent: str = ""


@app.post("/api/ws_latency")
async def api_ws_latency(report: WsLatencyReport):
    """Accept browser-reported WS latency and feed Prometheus histogram."""
    if _ws_latency_hist:
        _ws_latency_hist.labels(endpoint=report.endpoint).observe(report.latency_ms)
    return {"status": "ok"}


@app.post("/api/ws_browser_errors")
async def api_ws_browser_errors(report: WsBrowserErrorReport):
    """Accept browser-reported WS errors and feed Prometheus counter."""
    if _ws_error_counter:
        _ws_error_counter.labels(endpoint=report.endpoint).inc()
    system_logger.warning("Browser WS error on %s: %s", report.endpoint, report.error)
    return {"status": "ok"}


# Dash app is automatically mounted at /dashboard/ via DashboardManager


def main():
    """Main entry point."""
    host = settings.server.host
    port = settings.server.port
    debug = settings.server.debug

    system_logger.info("Starting server on %s:%s", host, port)
    system_logger.info("Debug mode: %s", debug)
    system_logger.info("Dashboard available at: http://%s:%s/dashboard/", host, port)
    system_logger.info("WebSocket endpoint: ws://%s:%s/ws", host, port)
    system_logger.info("API documentation: http://%s:%s/docs", host, port)

    # Run server
    uvicorn.run(app, host=host, port=port, log_level="info" if debug else "warning")


if __name__ == "__main__":
    main()
