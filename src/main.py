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
# File Path:     ${HOME}/Development/python/JuniperCanopy/juniper_canopy/src/
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

# import dash
import uvicorn

# from pathlib import Path
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
from backend.cascor_integration import CascorIntegration

# from backend.training_monitor import TrainingMonitor  trunk-ignore(ruff/E402)
# from backend.data_adapter import DataAdapter  trunk-ignore(ruff/E402)
from backend.training_monitor import TrainingState
from canopy_constants import ServerConstants
from communication.websocket_manager import websocket_manager
from config_manager import get_config
from frontend.dashboard_manager import DashboardManager
from logger.logger import get_system_logger, get_training_logger, get_ui_logger

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
config = get_config()

# Initialize loggers
system_logger = get_system_logger()
training_logger = get_training_logger()
ui_logger = get_ui_logger()

# Event loop holder for thread-safe async scheduling from training callbacks
loop_holder = {"loop": None}

# Demo mode tracking (global variables for startup/shutdown).
# ***IMPORTANT NOTE: demo_mode_active is set in the CascorIntegration initialization above.***  ????
demo_mode_active = False

# ***IMPORTANT NOTE: Do NOT reset it here or demo mode will not start!!!***
demo_mode_instance = None
training_state = TrainingState()  # Global TrainingState instance


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    system_logger.info("Starting Juniper Canopy application")
    system_logger.info(f"Configuration loaded from: {config.config_path}")
    system_logger.info(f"Environment: {config.get('application.environment', 'unknown')}")

    # Capture the running event loop for thread-safe async scheduling
    loop_holder["loop"] = asyncio.get_running_loop()
    system_logger.info("Event loop captured for thread-safe broadcasting")

    # Set event loop on websocket_manager for thread-safe broadcasting
    websocket_manager.set_event_loop(loop_holder["loop"])

    # Initialize demo mode or real backend
    global demo_mode_active, demo_mode_instance, cascor_integration, training_state

    if demo_mode_active:
        system_logger.info("Initializing demo mode")
        from demo_mode import get_demo_mode

        demo_mode_instance = get_demo_mode(update_interval=1.0)

        # Create minimal integration wrapper for demo mode. Don't need full CascorIntegration,
        # just basic structure for APIs
        system_logger.info("Demo mode network created")

        # Initialize global training_state with demo mode defaults
        if demo_mode_instance.training_state:
            demo_state = demo_mode_instance.training_state.get_state()
            training_state.update_state(**demo_state)
            system_logger.info(
                f"Global training_state initialized with demo defaults: LR={demo_state.get('learning_rate')}, "
                f"MaxHidden={demo_state.get('max_hidden_units')}, Epochs={demo_state.get('max_epochs')}"
            )

        # Start demo training simulation
        demo_mode_instance.start()
        system_logger.info("Demo mode started with simulated training")
    else:
        system_logger.info("CasCor backend mode active")
        demo_mode_instance = None

        # Initialize monitoring callbacks for real backend
        if cascor_integration:
            setup_monitoring_callbacks()

    system_logger.info("Application startup complete")

    yield

    # Shutdown
    system_logger.info("Shutting down Juniper Canopy application")

    # Stop demo mode if active
    if demo_mode_instance:
        demo_mode_instance.stop()
        system_logger.info("Demo mode stopped")

    # Shutdown WebSocket connections
    await websocket_manager.shutdown()

    # Shutdown CasCor integration
    if cascor_integration:
        cascor_integration.shutdown()

    system_logger.info("Application shutdown complete")


# Initialize FastAPI
app = FastAPI(
    title=config.get("application.name", "Juniper Canopy"),
    version=config.get("application.version", "1.0.0"),
    description=config.get("application.description", "Real-time monitoring for CasCor networks"),
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize backend integration
cascor_backend_path = config.get(
    "backend.cascor_integration.backend_path",
    os.getenv("CASCOR_BACKEND_PATH", "../cascor"),
)

# Check if demo mode is explicitly requested via environment variable
force_demo_mode = os.getenv("CASCOR_DEMO_MODE", "0") in ("1", "true", "True", "yes", "Yes")

if force_demo_mode:
    system_logger.info("Demo mode explicitly enabled via CASCOR_DEMO_MODE environment variable")
    cascor_integration = None
    demo_mode_active = True
else:
    # Try to initialize CasCor integration, fallback to demo mode
    try:
        cascor_integration = CascorIntegration(cascor_backend_path)
        demo_mode_active = False
        system_logger.info("CasCor backend integration initialized successfully")
    except FileNotFoundError as e:
        system_logger.warning(f"CasCor backend not found: {e}")
        system_logger.info("Falling back to demo mode for frontend development")
        cascor_integration = None
        demo_mode_active = True
    except Exception as e:
        system_logger.error(f"Failed to initialize CasCor backend: {e}")
        system_logger.info("Falling back to demo mode")
        cascor_integration = None
        demo_mode_active = True

# Initialize Dash dashboard (standalone with its own Flask server)
dashboard_manager = DashboardManager(config.get_section("frontend"))

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


def setup_monitoring_callbacks():
    """
    Set up monitoring callbacks for training events.
    These callbacks are invoked from training threads (non-async context).
    They schedule broadcasts onto FastAPI's event loop using run_coroutine_threadsafe.
    """

    def on_metrics_update(**kwargs):
        """Handle training metrics update (synchronous callback)."""
        from communication.websocket_manager import create_metrics_message

        metrics = kwargs.get("metrics")
        if metrics:
            metrics_data = metrics.to_dict() if hasattr(metrics, "to_dict") else metrics
            schedule_broadcast(websocket_manager.broadcast(create_metrics_message(metrics_data)))

    def on_topology_change(**kwargs):
        """Handle network topology change (synchronous callback)."""
        from communication.websocket_manager import create_topology_message

        topology = kwargs.get("topology")
        if topology:
            topology_data = topology.to_dict() if hasattr(topology, "to_dict") else topology
            schedule_broadcast(websocket_manager.broadcast(create_topology_message(topology_data)))

    def on_cascade_add(**kwargs):
        """Handle cascade unit addition (synchronous callback)."""
        from communication.websocket_manager import create_event_message

        event = kwargs.get("event")
        if event:
            # Extract event details from the event dict
            details = event if isinstance(event, dict) else {}
            schedule_broadcast(websocket_manager.broadcast(create_event_message("cascade_add", details)))

    # Register synchronous callbacks
    cascor_integration.create_monitoring_callback("epoch_end", on_metrics_update)
    cascor_integration.create_monitoring_callback("topology_change", on_topology_change)
    cascor_integration.create_monitoring_callback("cascade_add", on_cascade_add)

    system_logger.info("Monitoring callbacks registered (thread-safe)")


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
    client_id = f"training-client-{id(websocket)}"
    await websocket_manager.connect(websocket, client_id=client_id)
    try:
        # Send initial status
        global demo_mode_instance, demo_mode_active
        if demo_mode_active and demo_mode_instance:
            status = demo_mode_instance.get_current_state()
        elif cascor_integration:
            status = cascor_integration.get_training_status()
        else:
            status = {"error": "No backend available"}

        await websocket_manager.send_personal_message({"type": "initial_status", "data": status}, websocket)

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
    # from datetime import datetime

    client_id = f"control-client-{id(websocket)}"
    await websocket_manager.connect(websocket, client_id=client_id)
    # Connection confirmation is sent automatically by websocket_manager.connect()

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            command = message.get("command")
            system_logger.info(f"Control command received: {command}")

            # Handle demo mode commands
            global demo_mode_instance, demo_mode_active

            # Initialize demo_mode_instance if needed (for testing)
            if demo_mode_active and demo_mode_instance is None:
                from demo_mode import get_demo_mode

                demo_mode_instance = get_demo_mode(update_interval=1.0)
                demo_mode_instance.start()
                system_logger.info("Demo mode initialized in WebSocket handler")

            # Debug logging
            system_logger.info(
                f"demo_mode_active={demo_mode_active}, demo_mode_instance={demo_mode_instance is not None}"
            )

            if demo_mode_instance:
                try:
                    if command == "start":
                        reset = message.get("reset", True)
                        # start() returns state snapshot after reset
                        state = demo_mode_instance.start(reset=reset)
                        response = {"ok": True, "command": command, "state": state}
                    elif command == "stop":
                        demo_mode_instance.stop()
                        response = {"ok": True, "command": command, "state": demo_mode_instance.get_current_state()}
                    elif command == "pause":
                        demo_mode_instance.pause()
                        response = {"ok": True, "command": command, "state": demo_mode_instance.get_current_state()}
                    elif command == "resume":
                        demo_mode_instance.resume()
                        response = {"ok": True, "command": command, "state": demo_mode_instance.get_current_state()}
                    elif command == "reset":
                        # reset() returns state snapshot after reset
                        state = demo_mode_instance.reset()
                        response = {"ok": True, "command": command, "state": state}
                    else:
                        response = {"ok": False, "error": f"Unknown command: {command}"}

                    await websocket_manager.send_personal_message(response, websocket)
                except Exception as e:
                    system_logger.error(f"Command execution error: {e}")
                    await websocket_manager.send_personal_message({"ok": False, "error": str(e)}, websocket)

            # Handle real CasCor backend commands
            elif cascor_integration:
                # TODO: Implement real backend control
                await websocket_manager.send_personal_message(
                    {
                        "ok": False,
                        "error": "Real backend control not yet implemented",
                    },
                    websocket,
                )
            else:
                await websocket_manager.send_personal_message(
                    {"ok": False, "error": "No backend available"},
                    websocket,
                )

    except WebSocketDisconnect:
        system_logger.info(f"Control client disconnected: {client_id}")
    finally:
        websocket_manager.disconnect(websocket)


@app.get("/health")
@app.get("/api/health")
async def health_check():
    """
    Health check endpoint.
    Returns:
        Health status information
    """
    global demo_mode_instance

    # Check training status
    training_active = False
    if demo_mode_instance:
        training_active = demo_mode_instance.get_current_state()["is_running"]
    elif cascor_integration and hasattr(cascor_integration, "training_monitor"):
        training_active = cascor_integration.training_monitor.is_training

    return {
        "status": "healthy",
        "timestamp": time.time(),
        "version": config.get("application.version", "1.0.0"),
        "active_connections": websocket_manager.get_connection_count(),
        "training_active": training_active,
        "demo_mode": demo_mode_active,
    }


@app.get("/api/state")
async def get_state():
    """
    Get current training state.
    Returns:
        TrainingState as JSON
    """
    global training_state, demo_mode_instance

    # Return demo mode's training state if active
    if demo_mode_instance and demo_mode_instance.training_state:
        return demo_mode_instance.training_state.get_state()

    return training_state.get_state()


@app.get("/api/status")
async def get_status():
    """
    Get current training status.
    Returns:
        Training status dictionary with FSM-based status and phase
    """
    global demo_mode_instance

    # Demo mode status - get proper FSM-based status and phase
    if demo_mode_instance:
        state = demo_mode_instance.get_current_state()
        network = demo_mode_instance.get_network()

        # Get FSM state for accurate status and phase
        fsm_state = demo_mode_instance.state_machine.get_state_summary()
        status_name = fsm_state["status"]  # "STARTED", "PAUSED", "STOPPED", "COMPLETED", "FAILED"

        # Map FSM status to flags
        is_running = status_name == "STARTED"
        is_paused = status_name == "PAUSED"
        is_completed = status_name == "COMPLETED"
        is_failed = status_name == "FAILED"

        return {
            "is_training": is_running and not is_paused,
            "is_running": is_running,
            "is_paused": is_paused,
            "completed": is_completed,
            "failed": is_failed,
            "fsm_status": status_name,
            "current_epoch": state["current_epoch"],
            "current_loss": state["current_loss"],
            "current_accuracy": state["current_accuracy"],
            "network_connected": True,
            "monitoring_active": is_running,
            "input_size": network.input_size,
            "output_size": network.output_size,
            "hidden_units": len(network.hidden_units),
            "phase": fsm_state["phase"].lower(),  # 'output', 'candidate', 'idle'
        }

    # Real cascor status
    if cascor_integration:
        return cascor_integration.get_training_status()

    return {
        "is_training": False,
        "is_running": False,
        "is_paused": False,
        "completed": False,
        "failed": False,
        "fsm_status": "STOPPED",
        "network_connected": False,
        "monitoring_active": False,
        "phase": "idle",
    }


@app.get("/api/metrics")
async def get_metrics():
    """
    Get current training metrics.
    Returns:
        Current metrics dictionary
    """
    global demo_mode_instance

    # Try demo mode first
    if demo_mode_instance:
        return demo_mode_instance.get_current_state()
    # Fall back to cascor integration
    if cascor_integration and hasattr(cascor_integration, "training_monitor"):
        metrics = cascor_integration.training_monitor.get_current_metrics()
        return metrics.to_dict() if hasattr(metrics, "to_dict") else metrics

    return {}


@app.get("/api/metrics/history")
async def get_metrics_history():
    """
    Get metrics history.
    Returns:
        Dictionary with history list
    """
    global demo_mode_instance

    if demo_mode_instance:
        history = demo_mode_instance.get_metrics_history()
        return {"history": history}
    if cascor_integration and hasattr(cascor_integration, "training_monitor"):
        metrics = cascor_integration.training_monitor.get_recent_metrics(100)
        return {"history": [m.to_dict() for m in metrics]}
    return JSONResponse({"error": "No backend available"}, status_code=503)


@app.get("/api/network/stats")
async def get_network_stats():
    """
    Get comprehensive network statistics including weight statistics and metadata.
    Returns:
        Dictionary with threshold function, optimizer, node/edge counts, and weight statistics
    """
    global demo_mode_instance
    from backend.data_adapter import DataAdapter

    adapter = DataAdapter()

    # Get from demo mode or real cascor
    if demo_mode_instance:
        network = demo_mode_instance.get_network()

        # Get current state for optimizer and threshold function
        state = demo_mode_instance.get_current_state()
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
    if cascor_integration:
        # Get network parameters from cascor integration
        network_data = cascor_integration.get_network_data()
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
    global demo_mode_instance

    # Extract from demo mode or real cascor
    if demo_mode_instance:
        network = demo_mode_instance.get_network()
        connections = []

        # Create connections list for network visualizer
        # Input -> Output connections
        for i in range(network.input_size):
            for o in range(network.output_size):
                weight = float(network.input_weights[i, o].item())
                connections.append({"from": f"input_{i}", "to": f"output_{o}", "weight": weight})

        # Hidden -> Output connections (if hidden units exist)
        for h_idx, _ in enumerate(network.hidden_units):
            for o in range(network.output_size):
                # Output weights include contributions from hidden units
                # They are stored in output_weights matrix
                weight = float(network.output_weights[o, network.input_size + h_idx].item())
                connections.append({"from": f"hidden_{h_idx}", "to": f"output_{o}", "weight": weight})

        # Input -> Hidden (cascade correlation input connections)
        for h_idx, unit in enumerate(network.hidden_units):
            for i in range(network.input_size):
                weight = float(unit["weights"][i].item())
                connections.append({"from": f"input_{i}", "to": f"hidden_{h_idx}", "weight": weight})

        # Hidden -> Hidden (cascade connections from previous hidden units)
        for h_idx, unit in enumerate(network.hidden_units):
            for prev in range(h_idx):
                weight = float(unit["weights"][network.input_size + prev].item())
                connections.append({"from": f"hidden_{prev}", "to": f"hidden_{h_idx}", "weight": weight})

        # Manually construct topology for demo mode
        nodes = []
        # Input nodes
        nodes.extend({"id": f"input_{i}", "type": "input", "layer": 0} for i in range(network.input_size))
        # Hidden nodes
        nodes.extend(
            {"id": f"hidden_{h_idx}", "type": "hidden", "layer": 1} for h_idx in range(len(network.hidden_units))
        )
        # Output nodes
        nodes.extend({"id": f"output_{o}", "type": "output", "layer": 2} for o in range(network.output_size))

        return {
            "input_units": network.input_size,
            "hidden_units": len(network.hidden_units),
            "output_units": network.output_size,
            "nodes": nodes,
            "connections": connections,
            "total_connections": len(connections),
        }

    if cascor_integration:
        topology = cascor_integration.extract_network_topology()
        return topology.to_dict() if topology else JSONResponse({"error": "No topology available"}, status_code=503)

    return JSONResponse({"error": "No topology available"}, status_code=503)


@app.get("/api/dataset")
async def get_dataset():
    """
    Get dataset information.
    Returns:
        Dataset dictionary
    """
    global demo_mode_instance

    # Try demo mode first if active
    if demo_mode_instance:
        dataset = demo_mode_instance.get_dataset()
        return {
            "inputs": dataset["inputs"].tolist(),
            "targets": dataset["targets"].tolist(),
            "num_samples": dataset["num_samples"],
            "num_features": dataset["num_features"],
            "num_classes": dataset["num_classes"],
        }

    # Fall back to cascor integration
    if cascor_integration:
        dataset = cascor_integration.get_dataset_info()
        return dataset or JSONResponse({"error": "No dataset available"}, status_code=503)

    return JSONResponse({"error": "No dataset available"}, status_code=503)


@app.get("/api/decision_boundary")
async def get_decision_boundary():
    """
    Get decision boundary data for visualization.
    Returns:
        Decision boundary dictionary with grid and predictions
    """
    global demo_mode_instance

    # Try demo mode first
    if demo_mode_instance:
        import numpy as np
        import torch

        network = demo_mode_instance.get_network()
        dataset = demo_mode_instance.get_dataset()

        # Get data bounds
        inputs = dataset["inputs"]
        x_min, x_max = inputs[:, 0].min() - 0.5, inputs[:, 0].max() + 0.5
        y_min, y_max = inputs[:, 1].min() - 0.5, inputs[:, 1].max() + 0.5

        # Create meshgrid for decision boundary
        resolution = 100
        xx, yy = np.meshgrid(np.linspace(x_min, x_max, resolution), np.linspace(y_min, y_max, resolution))

        # Predict on grid
        grid_points = np.c_[xx.ravel(), yy.ravel()]
        with torch.no_grad():
            grid_tensor = torch.from_numpy(grid_points).float()
            predictions = network.forward(grid_tensor)
            Z = predictions.cpu().numpy().reshape(xx.shape)

        return {
            "xx": xx.tolist(),
            "yy": yy.tolist(),
            "Z": Z.tolist(),
            "bounds": {
                "x_min": float(x_min),
                "x_max": float(x_max),
                "y_min": float(y_min),
                "y_max": float(y_max),
            },
        }

    # Fall back to cascor integration
    if cascor_integration:
        # if predict_fn:
        if predict_fn := cascor_integration.get_prediction_function():
            # TODO: Add Similar logic for real cascor network
            system_logger = get_system_logger()
            system_logger.info(
                f"main.py: get_decision_boundary: Decision boundary data available: Predict Function: {predict_fn}"
            )
            # pass

    return JSONResponse({"error": "No decision boundary data available"}, status_code=503)


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
_snapshots_dir = os.getenv("CASCOR_SNAPSHOT_DIR", config.get("backend.snapshots.directory", "./snapshots"))


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
    global demo_mode_active

    try:
        snapshots = _list_snapshot_files()
    except Exception as e:
        system_logger.error(f"Failed to list snapshots: {e}")
        snapshots = []

    # Demo mode or no real snapshots available → return mock data
    if (demo_mode_active or not snapshots) and not cascor_integration:
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
        "message": "Demo mode history" if demo_mode_active else None,
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

    global demo_mode_active

    # Demo mode: return synthetic details
    if demo_mode_active or not cascor_integration:
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
        (
            f
            for f in path.iterdir()
            if f.is_file() and f.suffix.lower() in SNAPSHOT_EXTENSIONS and f.stem == snapshot_id
        ),
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

    global demo_mode_active

    now = datetime.now(UTC)
    timestamp_str = now.strftime("%Y%m%d_%H%M%S")

    # Generate snapshot ID and name
    snapshot_id = name or f"snapshot_{timestamp_str}"
    snapshot_name = f"{snapshot_id}.h5"

    # Demo mode: create mock snapshot entry
    if demo_mode_active or not cascor_integration:
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

    # Real mode: create actual HDF5 file via cascor_integration
    try:
        snapshot_path = Path(_snapshots_dir) / snapshot_name
        Path(_snapshots_dir).mkdir(parents=True, exist_ok=True)

        # Attempt to create HDF5 snapshot via CasCor integration
        if hasattr(cascor_integration, "save_snapshot"):
            cascor_integration.save_snapshot(str(snapshot_path), description=description)
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
                            if isinstance(value, (int, float, str, bool)):
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
            detail=f"Failed to create snapshot: {str(e)}",
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

    global demo_mode_active, demo_mode_instance, training_state

    # Check if training is running - only allow restore when paused/stopped
    if demo_mode_instance:
        fsm = demo_mode_instance.state_machine
        if fsm.is_started():
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
    if not snapshot_data and (demo_mode_active or not cascor_integration):
        # Check against generated mock snapshots
        for s in _generate_mock_snapshots():
            if s["id"] == snapshot_id:
                snapshot_data = {
                    "id": snapshot_id,
                    "name": f"{snapshot_id}.h5",
                    "mode": "demo",
                }
                break

    # Check real file system if in real mode
    if not snapshot_data and not demo_mode_active and cascor_integration:
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
        if demo_mode_active or not cascor_integration:
            # Reset demo mode state
            if demo_mode_instance:
                demo_mode_instance.reset()

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

        if hasattr(cascor_integration, "load_snapshot"):
            cascor_integration.load_snapshot(str(snapshot_path))
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
            detail=f"Failed to restore snapshot: {str(e)}",
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
    from pathlib import Path

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
        raise HTTPException(status_code=500, detail=f"Failed to save layout: {e}") from e

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
        raise HTTPException(status_code=500, detail=f"Failed to delete layout: {e}") from e

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

    success = False
    message = ""

    if demo_mode_instance:
        state = demo_mode_instance.start(reset=reset)
        success = True
        message = "Training started successfully"
        # Send control acknowledgment via WebSocket
        schedule_broadcast(websocket_manager.broadcast(create_control_ack_message("start", success, message)))
        return {"status": "started", **state}
    if cascor_integration:
        # P1-NEW-003: Use async training to avoid blocking event loop
        if cascor_integration.is_training_in_progress():
            message = "Training already in progress"
            schedule_broadcast(websocket_manager.broadcast(create_control_ack_message("start", False, message)))
            return {"status": "busy", "message": message}

        if cascor_integration.network is None:
            message = "No network configured. Create or load a network first."
            schedule_broadcast(websocket_manager.broadcast(create_control_ack_message("start", False, message)))
            return JSONResponse({"error": message}, status_code=400)

        # Start training in background (fire-and-forget)
        # Actual training uses monitoring hooks for WebSocket updates
        started = cascor_integration.start_training_background()
        if started:
            success = True
            message = "Training started successfully"
            schedule_broadcast(websocket_manager.broadcast(create_control_ack_message("start", success, message)))
            return {"status": "started", "message": message}
        else:
            message = "Failed to start training"
            schedule_broadcast(websocket_manager.broadcast(create_control_ack_message("start", False, message)))
            return JSONResponse({"error": message}, status_code=500)

    schedule_broadcast(websocket_manager.broadcast(create_control_ack_message("start", False, "No backend available")))
    return JSONResponse({"error": "No backend available"}, status_code=503)


@app.post("/api/train/pause")
async def api_train_pause():
    """
    Pause training.
    Returns:
        Training status
    """
    from communication.websocket_manager import create_control_ack_message

    if demo_mode_instance:
        demo_mode_instance.pause()
        schedule_broadcast(websocket_manager.broadcast(create_control_ack_message("pause", True, "Training paused")))
        return {"status": "paused"}

    schedule_broadcast(websocket_manager.broadcast(create_control_ack_message("pause", False, "No backend available")))
    return JSONResponse({"error": "No backend available"}, status_code=503)


@app.post("/api/train/resume")
async def api_train_resume():
    """
    Resume training.
    Returns:
        Training status
    """
    from communication.websocket_manager import create_control_ack_message

    if demo_mode_instance:
        demo_mode_instance.resume()
        schedule_broadcast(websocket_manager.broadcast(create_control_ack_message("resume", True, "Training resumed")))
        return {"status": "running"}

    schedule_broadcast(websocket_manager.broadcast(create_control_ack_message("resume", False, "No backend available")))
    return JSONResponse({"error": "No backend available"}, status_code=503)


@app.post("/api/train/stop")
async def api_train_stop():
    """
    Stop training.
    Returns:
        Training status
    """
    from communication.websocket_manager import create_control_ack_message

    if demo_mode_instance:
        demo_mode_instance.stop()
        schedule_broadcast(websocket_manager.broadcast(create_control_ack_message("stop", True, "Training stopped")))
        return {"status": "stopped"}

    # P1-NEW-003: Support stop for cascor_integration (best-effort)
    if cascor_integration:
        if cascor_integration.is_training_in_progress():
            requested = cascor_integration.request_training_stop()
            if requested:
                message = "Training stop requested (best-effort)"
                schedule_broadcast(websocket_manager.broadcast(create_control_ack_message("stop", True, message)))
                return {"status": "stop_requested", "message": message}
        else:
            message = "No training in progress"
            schedule_broadcast(websocket_manager.broadcast(create_control_ack_message("stop", True, message)))
            return {"status": "stopped", "message": message}

    schedule_broadcast(websocket_manager.broadcast(create_control_ack_message("stop", False, "No backend available")))
    return JSONResponse({"error": "No backend available"}, status_code=503)


@app.post("/api/train/reset")
async def api_train_reset():
    """
    Reset training.
    Returns:
        Training status with reset state
    """
    from communication.websocket_manager import create_control_ack_message

    if demo_mode_instance:
        state = demo_mode_instance.reset()
        schedule_broadcast(websocket_manager.broadcast(create_control_ack_message("reset", True, "Training reset")))
        return {"status": "reset", **state}

    schedule_broadcast(websocket_manager.broadcast(create_control_ack_message("reset", False, "No backend available")))
    return JSONResponse({"error": "No backend available"}, status_code=503)


@app.get("/api/train/status")
async def api_train_status():
    """
    Get current training status (P1-NEW-003).
    Returns:
        Training status dictionary with network info and training state.
    """
    if demo_mode_instance:
        return {"backend": "demo", **demo_mode_instance.get_state()}

    if cascor_integration:
        status = cascor_integration.get_training_status()
        status["backend"] = "cascor"
        status["training_in_progress"] = cascor_integration.is_training_in_progress()
        status["stop_requested"] = cascor_integration._training_stop_requested
        return status

    return {"backend": None, "status": "no_backend"}


@app.post("/api/set_params")
async def api_set_params(params: dict):
    """
    Set training parameters (learning rate, max hidden units).
    Args:
        params: Dictionary containing parameters to update
    Returns:
        Updated training state
    """
    global demo_mode_instance, training_state

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

        # Check if any parameter was provided
        has_params = bool(updates)

        if has_params:
            training_state.update_state(**updates)
            system_logger.info(f"Parameters updated: {updates}")

            # Apply to demo mode instance if active
            if demo_mode_instance:
                demo_mode_instance.apply_params(
                    learning_rate=updates.get("learning_rate"),
                    max_hidden_units=updates.get("max_hidden_units"),
                    max_epochs=updates.get("max_epochs"),
                )

            # Broadcast state change
            await websocket_manager.broadcast({"type": "state_change", "data": training_state.get_state()})

            return {"status": "success", "state": training_state.get_state()}
        else:
            return JSONResponse({"error": "No parameters provided"}, status_code=400)
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
    if cascor_integration:
        return cascor_integration.get_remote_worker_status()
    return {"available": False, "connected": False, "workers_active": False, "error": "No backend"}


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
    if not cascor_integration:
        return JSONResponse({"error": "No backend available"}, status_code=503)

    try:
        success = cascor_integration.connect_remote_workers((host, port), authkey)
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
    if not cascor_integration:
        return JSONResponse({"error": "No backend available"}, status_code=503)

    success = cascor_integration.start_remote_workers(num_workers)
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
    if not cascor_integration:
        return JSONResponse({"error": "No backend available"}, status_code=503)

    success = cascor_integration.stop_remote_workers(timeout)
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
    if not cascor_integration:
        return JSONResponse({"error": "No backend available"}, status_code=503)

    success = cascor_integration.disconnect_remote_workers()
    if success:
        return {"status": "disconnected"}
    return JSONResponse({"error": "Failed to disconnect"}, status_code=500)


# Dash app is automatically mounted at /dashboard/ via DashboardManager


def main():
    """Main entry point."""
    # Get server configuration with proper fallback hierarchy:
    # 1. Environment variable (CASCOR_SERVER_*)
    # 2. YAML configuration (conf/app_config.yaml)
    # 3. Constants module (ServerConstants)

    host_config = config.get("application.server.host")
    host = os.getenv("CASCOR_SERVER_HOST") or host_config or ServerConstants.DEFAULT_HOST

    port_config = config.get("application.server.port")
    port_env = os.getenv("CASCOR_SERVER_PORT")
    port = int(port_env) if port_env else (port_config or ServerConstants.DEFAULT_PORT)

    debug_config = config.get("application.server.debug")
    debug_env = os.getenv("CASCOR_SERVER_DEBUG")
    if debug_env:
        debug = debug_env.lower() in ("1", "true", "yes")
    else:
        debug = debug_config if debug_config is not None else False

    # Log configuration sources for transparency
    host_source = "env" if os.getenv("CASCOR_SERVER_HOST") else ("config" if host_config else "constant")
    port_source = "env" if port_env else ("config" if port_config else "constant")
    debug_source = "env" if debug_env else ("config" if debug_config is not None else "default")

    system_logger.info(f"Starting server on {host}:{port} (host source: {host_source}, port source: {port_source})")
    system_logger.info(f"Debug mode: {debug} (source: {debug_source})")
    system_logger.info(f"Dashboard available at: http://{host}:{port}/dashboard/")
    system_logger.info(f"WebSocket endpoint: ws://{host}:{port}/ws")
    system_logger.info(f"API documentation: http://{host}:{port}/docs")

    # Run server
    uvicorn.run(app, host=host, port=port, log_level="info" if debug else "warning")


if __name__ == "__main__":
    main()
