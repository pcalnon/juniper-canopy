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
import json
import os

# import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

# import dash
import uvicorn

# from fastapi.staticfiles import StaticFiles
from a2wsgi import WSGIMiddleware

# from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

# from dash import html, dcc
# Add src directory to Python path
# src_dir = Path(__file__).parent
# sys.path.insert(0, str(src_dir))
# from backend.training_monitor import TrainingMonitor  trunk-ignore(ruff/E402)
# from backend.data_adapter import DataAdapter  trunk-ignore(ruff/E402)
from backend.training_monitor import TrainingState  # trunk-ignore(ruff/E402)
from communication.websocket_manager import websocket_manager
from frontend.dashboard_manager import DashboardManager
from health import DependencyStatus, ReadinessResponse, probe_dependency
from logger.logger import (
    get_system_logger,
    get_training_logger,
    get_ui_logger,
)
from observability import (
    RequestIdMiddleware,
    configure_logging,
    configure_sentry,
    get_prometheus_app,
)
from settings import get_settings

# import logging

# from logger.logger import (
#     LogContext,
#     Alert,
#     ColoredFormatter,
#     JsonFormatter,
#     CascorLogger,
#     TrainingLogger,
# )

# Initialize configuration
settings = get_settings()

# Initialize loggers
system_logger = get_system_logger()
training_logger = get_training_logger()
ui_logger = get_ui_logger()

# Event loop holder for thread-safe async scheduling from training callbacks
loop_holder = {"loop": None}

# Global state tracking
juniper_data_available = False
training_state = TrainingState()  # Global TrainingState instance


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup — observability
    configure_logging(settings.log_level, settings.log_format, "juniper-canopy")
    configure_sentry(settings.sentry_dsn, "juniper-canopy", "0.3.0")

    system_logger.info("Starting Juniper Canopy application")
    system_logger.info(f"Settings: server={settings.server.host}:{settings.server.port}, demo={settings.demo_mode}")

    # Capture the running event loop for thread-safe async scheduling
    loop_holder["loop"] = asyncio.get_running_loop()
    system_logger.info("Event loop captured for thread-safe broadcasting")

    # Set event loop on websocket_manager for thread-safe broadcasting
    websocket_manager.set_event_loop(loop_holder["loop"])

    # Initialize backend via factory
    global backend, training_state

    from backend import create_backend

    backend = create_backend()

    # Validate JuniperData URL — mandatory for both demo and real backend (CAN-INT-002).
    juniper_data_url = settings.juniper_data_url
    # Propagate to env so downstream code (backend factory, etc.) can read it
    os.environ.setdefault("JUNIPER_DATA_URL", juniper_data_url)

    # CAN-HIGH-001: Probe upstream services at startup using standardized probe.
    global juniper_data_available
    data_probe = probe_dependency("JuniperData", f"{juniper_data_url.rstrip('/')}/v1/health/live")
    if data_probe.status == "healthy":
        juniper_data_available = True
        system_logger.info(f"JuniperData reachable at {juniper_data_url} ({data_probe.latency_ms:.1f}ms)")
    else:
        system_logger.warning(f"JuniperData unreachable at {juniper_data_url}: {data_probe.message}")

    # Probe JuniperCascor at startup (service mode only) — fallback to demo on failure.
    cascor_url = settings.cascor_service_url
    if cascor_url and backend.backend_type == "service":
        cascor_probe = probe_dependency("JuniperCascor", f"{cascor_url.rstrip('/')}/v1/health/live")
        if cascor_probe.status == "healthy":
            system_logger.info(f"JuniperCascor reachable at {cascor_url} ({cascor_probe.latency_ms:.1f}ms)")
        else:
            system_logger.warning(f"JuniperCascor unreachable at {cascor_url} — falling back to demo mode")
            await backend.shutdown()
            from backend import create_backend

            os.environ["CASCOR_DEMO_MODE"] = "1"
            backend = create_backend()
            await backend.initialize()

    # Initialize the backend (demo: starts simulation; service: connects to CasCor)
    await backend.initialize()

    # Sync global training_state with demo defaults if applicable
    if backend.backend_type == "demo" and hasattr(backend, "_demo"):
        demo = backend._demo
        if demo.training_state:
            demo_state = demo.training_state.get_state()
            training_state.update_state(**demo_state)
            system_logger.info(f"Global training_state synced with demo defaults: LR={demo_state.get('learning_rate')}, " f"MaxHidden={demo_state.get('max_hidden_units')}, Epochs={demo_state.get('max_epochs')}")

    system_logger.info(f"Backend initialized: {backend.backend_type}")
    system_logger.info("Application startup complete")

    yield

    # Shutdown
    system_logger.info("Shutting down Juniper Canopy application")

    await backend.shutdown()

    # Shutdown WebSocket connections
    await websocket_manager.shutdown()

    system_logger.info("Application shutdown complete")


# Disable interactive API docs when authentication is enabled (production).
_docs_enabled = not os.environ.get("CANOPY_API_KEY")
# Initialize FastAPI
app = FastAPI(
    title="Juniper Canopy",
    version="0.3.0",
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
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Security headers (outermost — runs on every response)
from middleware import RequestBodyLimitMiddleware, SecurityHeadersMiddleware, SecurityMiddleware
from security import get_api_key_auth, get_rate_limiter

app.add_middleware(RequestBodyLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

api_key_auth = get_api_key_auth()
rate_limiter = get_rate_limiter()
app.add_middleware(SecurityMiddleware, api_key_auth=api_key_auth, rate_limiter=rate_limiter)

# Observability middleware (LIFO: last added runs first)
app.add_middleware(RequestIdMiddleware)
if settings.metrics_enabled:
    from observability import PrometheusMiddleware

    app.add_middleware(PrometheusMiddleware, service_name="juniper-canopy")
    app.mount("/metrics", get_prometheus_app())

# Backend is initialized in lifespan via create_backend() factory
backend = None

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
            system_logger.error(f"Failed to schedule broadcast: {e}")
    else:
        system_logger.warning("Event loop not available for broadcasting")


@app.get("/")
async def root():
    """
    Root endpoint - redirects to dashboard.
    Returns:
        Redirect response to /dashboard/
    """
    return RedirectResponse(url="/dashboard/")


_WS_MAX_MESSAGE_SIZE = 65536  # 64KB max message size for WebSocket


async def _authenticate_websocket(websocket: WebSocket) -> bool:
    """Authenticate WebSocket connection using X-API-Key header.

    BaseHTTPMiddleware does not intercept WebSocket upgrades, so
    authentication must be performed explicitly at connection accept.

    Returns True if authenticated (or auth disabled), False otherwise.
    """
    if api_key_auth.enabled:
        key = websocket.headers.get("X-API-Key")
        if not api_key_auth.validate(key):
            await websocket.close(code=4001, reason="Authentication required")
            return False
    return True


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
    if not await _authenticate_websocket(websocket):
        return

    client_id = f"training-client-{id(websocket)}"
    await websocket_manager.connect(websocket, client_id=client_id)
    try:
        # Send initial status
        status = backend.get_status()

        await websocket_manager.send_personal_message({"type": "initial_status", "data": status}, websocket)

        # Send a properly formatted state message so clients receive current state immediately
        # Use TrainingState.get_state() for standardized field names (status, phase, learning_rate, etc.)
        state_data = training_state.get_state() if training_state else status
        await websocket_manager.send_personal_message({"type": "state", "timestamp": time.time(), "data": state_data}, websocket)

        # Message handling loop
        while True:
            try:
                # Receive message from client
                data = await websocket.receive_text()
                message = json.loads(data) if isinstance(data, str) else data

                # Handle ping/pong
                if message.get("type") == "ping":
                    await websocket_manager.send_personal_message({"type": "pong"}, websocket)
                # Handle other messages as needed
                else:
                    system_logger.debug(f"Received message: {message.get('type')}")

            except WebSocketDisconnect:
                system_logger.info(f"Client disconnected: {client_id}")
                break
            except Exception as e:
                system_logger.error(f"WebSocket error: {e}")
                break

    finally:
        websocket_manager.disconnect(websocket)


@app.websocket("/ws/control")
async def websocket_control_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for training control commands.
    Handles:
    - Start/stop training
    - Pause/resume
    - Reset
    - Configuration updates
    Commands:
        {'command': 'start', 'reset': true/false}
        {'command': 'stop'}
        {'command': 'pause'}
        {'command': 'resume'}
        {'command': 'reset'}
    """
    if not await _authenticate_websocket(websocket):
        return

    client_id = f"control-client-{id(websocket)}"
    await websocket_manager.connect(websocket, client_id=client_id)
    # Connection confirmation is sent automatically by websocket_manager.connect()

    _valid_commands = {"start", "stop", "pause", "resume", "reset"}

    try:
        while True:
            data = await websocket.receive_text()

            if len(data) > _WS_MAX_MESSAGE_SIZE:
                await websocket_manager.send_personal_message({"ok": False, "error": "Message too large"}, websocket)
                continue

            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                await websocket_manager.send_personal_message({"ok": False, "error": "Invalid JSON"}, websocket)
                continue

            command = message.get("command", "")

            if command not in _valid_commands:
                await websocket_manager.send_personal_message({"ok": False, "error": f"Unknown command: {command}"}, websocket)
                continue

            system_logger.info(f"Control command received: {command} (backend={backend.backend_type})")

            try:
                if command == "start":
                    reset = message.get("reset", True)
                    result = backend.start_training(reset=reset)
                    response = {"ok": True, "command": command, "state": result}
                elif command == "stop":
                    result = backend.stop_training()
                    response = {"ok": True, "command": command, "state": result}
                elif command == "pause":
                    result = backend.pause_training()
                    response = {"ok": True, "command": command, "state": result}
                elif command == "resume":
                    result = backend.resume_training()
                    response = {"ok": True, "command": command, "state": result}
                elif command == "reset":
                    result = backend.reset_training()
                    response = {"ok": True, "command": command, "state": result}

                await websocket_manager.send_personal_message(response, websocket)
            except Exception as e:
                system_logger.error(f"Command execution error: {e}")
                await websocket_manager.send_personal_message({"ok": False, "error": "Command execution failed"}, websocket)

    except WebSocketDisconnect:
        system_logger.info(f"Control client disconnected: {client_id}")
    finally:
        websocket_manager.disconnect(websocket)


@app.get("/health", deprecated=True)
@app.get("/api/health", deprecated=True)
async def health_check_deprecated():
    """Health check endpoint (deprecated — use /v1/health instead)."""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "version": "0.3.0",
        "active_connections": websocket_manager.get_connection_count(),
        "training_active": backend.is_training_active(),
        "demo_mode": backend.backend_type == "demo",
        "juniper_data_available": juniper_data_available,
    }


@app.get("/v1/health")
async def health_check():
    """Combined health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "version": "0.3.0",
        "active_connections": websocket_manager.get_connection_count(),
        "training_active": backend.is_training_active(),
        "demo_mode": backend.backend_type == "demo",
        "juniper_data_available": juniper_data_available,
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
    data_dep = probe_dependency("JuniperData Service", f"{data_url.rstrip('/')}/v1/health/live")

    # Probe JuniperCascor
    ready_cascor_url = settings.cascor_service_url
    if ready_cascor_url:
        cascor_dep = probe_dependency("JuniperCascor Service", f"{ready_cascor_url.rstrip('/')}/v1/health/live")
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
        version="0.3.0",
        service="juniper-canopy",
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
        TrainingState as JSON
    """
    # Return demo mode's live training state if available, otherwise global
    if backend.backend_type == "demo" and hasattr(backend, "_demo") and backend._demo.training_state:
        return backend._demo.training_state.get_state()

    return training_state.get_state()


@app.get("/api/status")
async def get_status():
    """
    Get current training status.
    Returns:
        Training status dictionary with FSM-based status and phase
    """
    return backend.get_status()


@app.get("/api/metrics")
async def get_metrics():
    """
    Get current training metrics.
    Returns:
        Current metrics dictionary
    """
    return backend.get_metrics()


@app.get("/api/metrics/history")
async def get_metrics_history():
    """
    Get metrics history.
    Returns:
        Dictionary with history list
    """
    return {"history": backend.get_metrics_history(100)}


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

        return adapter.get_network_statistics(
            input_weights=network.input_weights,
            hidden_weights=(network.hidden_units[0]["weights"] if network.hidden_units else None),
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
    topology = backend.get_network_topology()
    if topology is None:
        return JSONResponse({"error": "No topology available"}, status_code=503)
    return topology


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


@app.get("/api/decision_boundary")
async def get_decision_boundary():
    """
    Get decision boundary data for visualization.
    Returns:
        Decision boundary dictionary with grid and predictions
    """
    boundary = backend.get_decision_boundary(100)
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
_snapshots_dir = os.getenv("CASCOR_SNAPSHOT_DIR", "./snapshots")


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
        system_logger.error(f"Failed to list snapshots: {e}")
        snapshots = []

    # Demo mode or no real snapshots available → return mock data
    if (backend.backend_type == "demo" or not snapshots) and backend.backend_type != "service":
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

    entries = []

    if history_file.exists():
        try:
            with open(history_file, "r") as f:
                for line in f:
                    if line := line.strip():
                        try:
                            entry = json.loads(line)
                            entries.append(entry)
                        except json.JSONDecodeError:
                            system_logger.warning(f"Invalid JSON in history file: {line[:50]}...")
        except Exception as e:
            system_logger.warning(f"Failed to read snapshot history: {e}")

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
    from pathlib import Path

    from fastapi import HTTPException

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

    # Real mode: find file in snapshots directory
    path = Path(_snapshots_dir)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Snapshot directory not found")

    # Search by file stem
    snapshot_file = next(
        (f for f in path.iterdir() if f.is_file() and f.suffix.lower() in SNAPSHOT_EXTENSIONS and f.stem == snapshot_id),
        None,
    )

    if not snapshot_file:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    stat = snapshot_file.stat()
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
    except ImportError:
        system_logger.debug("h5py not available, skipping HDF5 attribute extraction")
    except Exception as e:
        system_logger.warning(f"Failed to read HDF5 attributes for {snapshot_file}: {e}")

    return detail


# Session-persistent storage for demo mode snapshots (P3-1)
_demo_snapshots: list = []


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

        system_logger.debug(f"Logged snapshot activity: {action} for {snapshot_id}")
    except Exception as e:
        system_logger.warning(f"Failed to log snapshot activity: {e}")


@app.post("/api/v1/snapshots", status_code=201)
async def create_snapshot(
    name: str = None,
    description: str = None,
):
    """
    Create a new HDF5 snapshot of the current training state.

    Args:
        name: Optional custom name for the snapshot (auto-generated if not provided)
        description: Optional description for the snapshot

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
    snapshot_name = f"{snapshot_id}.h5"

    # Demo mode: create mock snapshot entry
    if backend.backend_type == "demo":
        size_bytes = 1024 * 1024 + int(now.timestamp()) % (512 * 1024)  # ~1-1.5 MB mock size

        snapshot = {
            "id": snapshot_id,
            "name": snapshot_name,
            "timestamp": f"{now.replace(microsecond=0).isoformat()}Z",
            "size_bytes": size_bytes,
            "description": description or "Demo snapshot (no real HDF5 file)",
            "path": f"{_snapshots_dir}/{snapshot_name}",
        }

        # Add to session-persistent demo snapshots list
        _demo_snapshots.insert(0, snapshot)

        # Log the activity
        _log_snapshot_activity(
            action="create",
            snapshot_id=snapshot_id,
            details={"name": snapshot_name, "size_bytes": size_bytes, "mode": "demo"},
            message="Demo snapshot created successfully",
        )

        system_logger.info(f"Created demo snapshot: {snapshot_id}")

        return {
            **snapshot,
            "message": "Demo snapshot created successfully",
        }

    # Real mode: create actual HDF5 file via backend
    try:
        snapshot_path = Path(_snapshots_dir) / snapshot_name
        Path(_snapshots_dir).mkdir(parents=True, exist_ok=True)

        # Attempt to create HDF5 snapshot via CasCor integration
        if hasattr(backend, "_adapter") and hasattr(backend._adapter, "save_snapshot"):
            backend._adapter.save_snapshot(str(snapshot_path), description=description)
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

            except ImportError as e:
                raise HTTPException(
                    status_code=500,
                    detail="h5py not available for creating HDF5 snapshots",
                ) from e

        # Get file stats after creation
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

        # Log the activity
        _log_snapshot_activity(
            action="create",
            snapshot_id=snapshot_id,
            details={"name": snapshot_name, "size_bytes": stat.st_size, "mode": "real"},
            message="Snapshot created successfully",
        )

        system_logger.info(f"Created snapshot: {snapshot_id} at {snapshot_path}")

        return {
            **snapshot,
            "message": "Snapshot created successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        system_logger.error(f"Failed to create snapshot: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to create snapshot",
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

            restored_state = {
                "snapshot_id": snapshot_id,
                "restored_at": f"{now.isoformat()}Z",
                "mode": "demo",
                "current_epoch": 0,
                "training_status": "Stopped",
            }

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

            system_logger.info(f"Restored from demo snapshot: {snapshot_id}")

            return {
                "status": "success",
                "message": f"Restored from snapshot '{snapshot_id}'",
                **restored_state,
            }

        # Real mode: load from HDF5 file
        snapshot_path = Path(snapshot_data.get("path", f"{_snapshots_dir}/{snapshot_id}.h5"))

        if hasattr(backend, "_adapter") and hasattr(backend._adapter, "load_snapshot"):
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

            except ImportError as e:
                raise HTTPException(
                    status_code=500,
                    detail="h5py not available for reading HDF5 snapshots",
                ) from e

        restored_state = {
            "snapshot_id": snapshot_id,
            "restored_at": f"{now.isoformat()}Z",
            "mode": "real",
            "path": str(snapshot_path),
        }

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

        system_logger.info(f"Restored from snapshot: {snapshot_id} at {snapshot_path}")

        return {
            "status": "success",
            "message": f"Restored from snapshot '{snapshot_id}'",
            **restored_state,
        }

    except HTTPException:
        raise
    except Exception as e:
        system_logger.error(f"Failed to restore snapshot: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to restore snapshot",
        ) from e


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
                return json.load(f)
        except Exception as e:
            system_logger.warning(f"Failed to load layouts file: {e}")
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
        system_logger.error(f"Failed to save layouts file: {e}")
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
        system_logger.debug(f"Failed to save layout: {e}")
        raise HTTPException(status_code=500, detail="Failed to save layout") from e

    system_logger.info(f"Saved metrics layout: {name}")

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
        system_logger.debug(f"Failed to delete layout: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete layout") from e

    system_logger.info(f"Deleted metrics layout: {name}")

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


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    """
    General WebSocket endpoint for compatibility.
    Handles both text and non-text frames gracefully.
    """
    if not await _authenticate_websocket(websocket):
        return

    await websocket_manager.connect(websocket)
    try:
        while True:
            try:
                await websocket.receive_text()
            except Exception:
                # Ignore non-text frames (pings, pongs, binary)
                await asyncio.sleep(10)
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket)


@app.post("/api/train/start")
async def api_train_start(reset: bool = False):
    """
    Start training.
    Args:
        reset: Whether to reset network before starting
    Returns:
        Training status
    """
    from communication.websocket_manager import create_control_ack_message

    result = backend.start_training(reset=reset)
    message = "Training started successfully"
    schedule_broadcast(websocket_manager.broadcast(create_control_ack_message("start", True, message)))
    return {"status": "started", **result}


@app.post("/api/train/pause")
async def api_train_pause():
    """
    Pause training.
    Returns:
        Training status
    """
    from communication.websocket_manager import create_control_ack_message

    backend.pause_training()
    schedule_broadcast(websocket_manager.broadcast(create_control_ack_message("pause", True, "Training paused")))
    return {"status": "paused"}


@app.post("/api/train/resume")
async def api_train_resume():
    """
    Resume training.
    Returns:
        Training status
    """
    from communication.websocket_manager import create_control_ack_message

    backend.resume_training()
    schedule_broadcast(websocket_manager.broadcast(create_control_ack_message("resume", True, "Training resumed")))
    return {"status": "running"}


@app.post("/api/train/stop")
async def api_train_stop():
    """
    Stop training.
    Returns:
        Training status
    """
    from communication.websocket_manager import create_control_ack_message

    backend.stop_training()
    schedule_broadcast(websocket_manager.broadcast(create_control_ack_message("stop", True, "Training stopped")))
    return {"status": "stopped"}


@app.post("/api/train/reset")
async def api_train_reset():
    """
    Reset training.
    Returns:
        Training status with reset state
    """
    from communication.websocket_manager import create_control_ack_message

    result = backend.reset_training()
    schedule_broadcast(websocket_manager.broadcast(create_control_ack_message("reset", True, "Training reset")))
    return {"status": "reset", **result}


@app.get("/api/train/status")
async def api_train_status():
    """
    Get current training status (P1-NEW-003).
    Returns:
        Training status dictionary with network info and training state.
    """
    return {"backend": backend.backend_type, **backend.get_status()}


@app.post("/api/set_params")
async def api_set_params(params: dict):
    """
    Set training parameters (learning rate, max hidden units).
    Args:
        params: Dictionary containing parameters to update
    Returns:
        Updated training state
    """
    try:
        learning_rate = params.get("learning_rate")
        max_hidden_units = params.get("max_hidden_units")
        max_epochs = params.get("max_epochs")

        # Update TrainingState with all provided parameters
        updates = {}
        if learning_rate is not None:
            updates["learning_rate"] = float(learning_rate)
        if max_hidden_units is not None:
            updates["max_hidden_units"] = int(max_hidden_units)
        if max_epochs is not None:
            updates["max_epochs"] = int(max_epochs)

        if not updates:
            return JSONResponse({"error": "No parameters provided"}, status_code=400)

        training_state.update_state(**updates)
        backend.apply_params(**updates)
        system_logger.info(f"Parameters updated: {updates}")

        # Broadcast state change
        await websocket_manager.broadcast({"type": "state_change", "data": training_state.get_state()})

        return {"status": "success", "state": training_state.get_state()}
    except Exception as e:
        system_logger.error(f"Failed to set parameters: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


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


@app.post("/api/remote/connect")
async def api_remote_connect(host: str, port: int, authkey: str):
    """
    Connect to a remote CandidateTrainingManager (P1-NEW-002).
    Args:
        host: Remote manager host address.
        port: Remote manager port.
        authkey: Authentication key for secure connection.
    Returns:
        Connection status.
    """
    if backend.backend_type != "service" or not hasattr(backend, "_adapter"):
        return JSONResponse({"error": "Not available in demo mode"}, status_code=503)

    try:
        success = backend._adapter.connect_remote_workers((host, port), authkey)
        if success:
            return {"status": "connected", "address": f"{host}:{port}"}
        return JSONResponse({"error": "Connection failed"}, status_code=500)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


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
async def api_remote_stop_workers(timeout: int = 10):
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


# Dash app is automatically mounted at /dashboard/ via DashboardManager


def main():
    """Main entry point."""
    host = settings.server.host
    port = settings.server.port
    debug = settings.server.debug

    system_logger.info(f"Starting server on {host}:{port}")
    system_logger.info(f"Debug mode: {debug}")
    system_logger.info(f"Dashboard available at: http://{host}:{port}/dashboard/")
    system_logger.info(f"WebSocket endpoint: ws://{host}:{port}/ws")
    system_logger.info(f"API documentation: http://{host}:{port}/docs")

    # Run server
    uvicorn.run(app, host=host, port=port, log_level="info" if debug else "warning")


if __name__ == "__main__":
    main()
