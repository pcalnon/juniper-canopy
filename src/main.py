#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     main.py
# Author:        Paul Calnon
# Version:       1.7.0
#
# Date:          2025-10-11
# Last Modified: 2025-12-03
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2025 Paul Calnon
#
# Description:
#    This file contains the Main function to monitor the current Cascade Correlation Neural Network prototype
#       including training, state, and architecture with the Juniper prototype Frontend for monitoring and diagnostics.
#
#####################################################################################################################################################################################################
# Notes:
#
# Main Application Entry Point
#
# FastAPI application with Dash integration for Juniper Canopy monitoring.
#
#####################################################################################################################################################################################################
# References:
#
#####################################################################################################################################################################################################
# TODO :
#     Force pre-compile checks to run
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
from communication.websocket_manager import websocket_manager
from config_manager import get_config
from constants import ServerConstants
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
        Training status dictionary
    """
    global demo_mode_instance

    # Demo mode status
    if demo_mode_instance:
        state = demo_mode_instance.get_current_state()
        network = demo_mode_instance.get_network()
        return {
            "is_training": state["is_running"],
            "current_epoch": state["current_epoch"],
            "current_loss": state["current_loss"],
            "current_accuracy": state["current_accuracy"],
            "network_connected": True,
            "monitoring_active": state["is_running"],
            "input_size": network.input_size,
            "output_size": network.output_size,
            "hidden_units": len(network.hidden_units),
            "current_phase": "demo_mode",
        }

    # Real cascor status
    if cascor_integration:
        return cascor_integration.get_training_status()

    return {
        "is_training": False,
        "network_connected": False,
        "monitoring_active": False,
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
        success = False
        message = "Start command not implemented for cascor"
        schedule_broadcast(websocket_manager.broadcast(create_control_ack_message("start", success, message)))
        return {"status": "unimplemented"}

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

        # Update TrainingState
        updates = {}
        if learning_rate is not None:
            updates["learning_rate"] = float(learning_rate)
        if max_hidden_units is not None:
            updates["max_hidden_units"] = int(max_hidden_units)
        # Note: max_epochs is not stored in TrainingState, only applied to demo mode

        # Check if any parameter was provided
        has_params = updates or max_epochs is not None

        if has_params:
            if updates:
                training_state.update_state(**updates)
                system_logger.info(f"Parameters updated: {updates}")

            # Apply to demo mode instance if active
            if demo_mode_instance:
                demo_mode_instance.apply_params(
                    learning_rate=updates.get("learning_rate"),
                    max_hidden_units=updates.get("max_hidden_units"),
                    max_epochs=max_epochs,
                )

            # Broadcast state change
            await websocket_manager.broadcast({"type": "state_change", "data": training_state.get_state()})

            return {"status": "success", "state": training_state.get_state()}
        else:
            return JSONResponse({"error": "No parameters provided"}, status_code=400)
    except Exception as e:
        system_logger.error(f"Failed to set parameters: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


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
