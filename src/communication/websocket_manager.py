#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     websocket_manager.py
# Author:        Paul Calnon
# Version:       2.0.0
#
# Date:          2025-10-11
# Last Modified: 2025-12-03
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2025 Paul Calnon
#
# Description:
#    This module manages WebSocket connections for real-time communication between
#    the backend training system and frontend dashboard. Includes standardized
#    message schema and builder functions.
#
#####################################################################################################################################################################################################
# Notes:
#
# WebSocket Manager Module
#
# Manages WebSocket connections for real-time communication between
# the backend training system and frontend dashboard.
#
# Features:
# - Connection management (connect, disconnect, track metadata)
# - Broadcasting messages to all connected clients
# - Synchronous broadcasting for non-async code
# - Connection health monitoring
# - Automatic cleanup of broken connections
# - Standardized message schema
#
# WebSocket Message Schema:
# All messages follow this format:
# {
#     "type": "state | metrics | topology | event | control_ack",
#     "timestamp": <float>,  # Unix timestamp with milliseconds
#     "data": {
#         # Type-specific payload
#     }
# }
#
# Message Types:
# - state: Training state updates (status, phase, learning_rate, etc.)
# - metrics: Training metrics (loss, accuracy, validation metrics)
# - topology: Network topology changes (nodes, connections, architecture)
# - event: Training events (cascade_add, phase_change, etc.)
# - control_ack: Control command acknowledgments
#
# Example Messages:
#
# State Message:
# {
#     "type": "state",
#     "timestamp": 1700000000.123,
#     "data": {
#         "status": "Started",
#         "phase": "Output",
#         "learning_rate": 0.01,
#         "current_epoch": 42,
#         ...
#     }
# }
#
# Metrics Message:
# {
#     "type": "metrics",
#     "timestamp": 1700000000.456,
#     "data": {
#         "epoch": 42,
#         "metrics": {
#             "loss": 0.23,
#             "accuracy": 0.91,
#             "val_loss": 0.25,
#             "val_accuracy": 0.89
#         }
#     }
# }
#
# Topology Message:
# {
#     "type": "topology",
#     "timestamp": 1700000000.789,
#     "data": {
#         "input_units": 2,
#         "hidden_units": 3,
#         "output_units": 1,
#         "nodes": [...],
#         "connections": [...]
#     }
# }
#
# Event Message:
# {
#     "type": "event",
#     "timestamp": 1700000000.999,
#     "data": {
#         "event_type": "cascade_add",
#         "details": {
#             "unit_index": 2,
#             "total_hidden_units": 3,
#             "epoch": 42
#         }
#     }
# }
#
# Control Acknowledgment Message:
# {
#     "type": "control_ack",
#     "timestamp": 1700000001.123,
#     "data": {
#         "command": "start",
#         "success": true,
#         "message": "Training started successfully"
#     }
# }
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
import asyncio
import contextlib

# import json
import logging
import time
from datetime import datetime

# from typing import Set, Dict, Any, Optional
from typing import Any, Dict, Optional, Set

# from fastapi import WebSocket, WebSocketDisconnect
from fastapi import WebSocket


class WebSocketManager:
    """
    - Active WebSocket connections with metadata

    - Message broadcasting (async and sync)
    - Connection lifecycle (connect, disconnect, cleanup)
    - Message serialization and error handling

    Usage:
        # In FastAPI endpoint
        @app.websocket("/ws/training")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket_manager.connect(websocket)
            try:
                while True:
                    await websocket.receive_text()
            except WebSocketDisconnect:
                websocket_manager.disconnect(websocket)

        # Broadcasting from training code
        websocket_manager.broadcast_sync({'type': 'metrics', 'loss': 0.5})
    """

    def __init__(self):
        """Initialize WebSocket manager with config-driven settings."""
        import os

        from canopy_constants import WebSocketConstants
        from config_manager import ConfigManager

        self.active_connections: Set[WebSocket] = set()
        self.connection_metadata: Dict[WebSocket, dict] = {}
        self.logger = self._setup_logger()
        self.message_count = 0
        self.event_loop: Optional[asyncio.AbstractEventLoop] = None

        # Initialize ConfigManager
        config_mgr = ConfigManager()
        ws_config = config_mgr.config.get("backend", {}).get("communication", {}).get("websocket", {})

        if max_conn_env := os.getenv("CASCOR_WEBSOCKET_MAX_CONNECTIONS"):
            try:
                self.max_connections = int(max_conn_env)
                self.logger.info(f"Max connections from env: {self.max_connections}")
            except ValueError:
                self.logger.warning(f"Invalid CASCOR_WEBSOCKET_MAX_CONNECTIONS: {max_conn_env}")
                self.max_connections = ws_config.get("max_connections", WebSocketConstants.MAX_CONNECTIONS)
        else:
            self.max_connections = ws_config.get("max_connections", WebSocketConstants.MAX_CONNECTIONS)

        if heartbeat_env := os.getenv("CASCOR_WEBSOCKET_HEARTBEAT_INTERVAL"):
            try:
                self.heartbeat_interval = int(heartbeat_env)
                self.logger.info(f"Heartbeat interval from env: {self.heartbeat_interval}s")
            except ValueError:
                self.logger.warning(f"Invalid CASCOR_WEBSOCKET_HEARTBEAT_INTERVAL: {heartbeat_env}")
                self.heartbeat_interval = ws_config.get("heartbeat_interval", WebSocketConstants.HEARTBEAT_INTERVAL_SEC)
        else:
            self.heartbeat_interval = ws_config.get("heartbeat_interval", WebSocketConstants.HEARTBEAT_INTERVAL_SEC)

        if reconnect_attempts_env := os.getenv("CASCOR_WEBSOCKET_RECONNECT_ATTEMPTS"):
            try:
                self.reconnect_attempts = int(reconnect_attempts_env)
                self.logger.info(f"Reconnect attempts from env: {self.reconnect_attempts}")
            except ValueError:
                self.logger.warning(f"Invalid CASCOR_WEBSOCKET_RECONNECT_ATTEMPTS: {reconnect_attempts_env}")
                self.reconnect_attempts = ws_config.get("reconnect_attempts", WebSocketConstants.RECONNECT_ATTEMPTS)
        else:
            self.reconnect_attempts = ws_config.get("reconnect_attempts", WebSocketConstants.RECONNECT_ATTEMPTS)

        if reconnect_delay_env := os.getenv("CASCOR_WEBSOCKET_RECONNECT_DELAY"):
            try:
                self.reconnect_delay = int(reconnect_delay_env)
                self.logger.info(f"Reconnect delay from env: {self.reconnect_delay}s")
            except ValueError:
                self.logger.warning(f"Invalid CASCOR_WEBSOCKET_RECONNECT_DELAY: {reconnect_delay_env}")
                self.reconnect_delay = ws_config.get("reconnect_delay", WebSocketConstants.RECONNECT_DELAY_SEC)
        else:
            self.reconnect_delay = ws_config.get("reconnect_delay", WebSocketConstants.RECONNECT_DELAY_SEC)

        self.logger.info(f"WebSocketManager initialized: " f"max_connections={self.max_connections}, " f"heartbeat_interval={self.heartbeat_interval}s, " f"reconnect_attempts={self.reconnect_attempts}, " f"reconnect_delay={self.reconnect_delay}s")

    def set_event_loop(self, loop: asyncio.AbstractEventLoop):
        """
        Set the event loop for thread-safe broadcasting.

        Args:
            loop: The asyncio event loop to use for broadcasting
        """
        self.event_loop = loop
        self.logger.debug("Event loop set for WebSocketManager")

    def _setup_logger(self) -> logging.Logger:
        """
        Setup logger for WebSocket manager.

        Returns:
            Logger instance
        """
        try:
            # Try to use project logger
            from logger.logger import get_system_logger

            return get_system_logger()
        except ImportError:
            # Fallback to standard logging
            logger = logging.getLogger(__name__)
            if not logger.handlers:
                handler = logging.StreamHandler()
                formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
                handler.setFormatter(formatter)
                logger.addHandler(handler)
                logger.setLevel(logging.INFO)
            return logger

    async def connect(self, websocket: WebSocket, client_id: Optional[str] = None):
        """
        Accept new WebSocket connection.

        Args:
            websocket: WebSocket connection to accept
            client_id: Optional client identifier (default: auto-generated)

        Example:
            await websocket_manager.connect(websocket, client_id='dashboard-1')
        """
        await websocket.accept()

        # Add to active connections
        self.active_connections.add(websocket)

        # Store metadata
        self.connection_metadata[websocket] = {
            "client_id": client_id or f"client-{id(websocket)}",
            "connected_at": datetime.now().isoformat(),
            "messages_sent": 0,
            "last_message_at": None,
        }

        self.logger.info(f"Client connected: {self.connection_metadata[websocket]['client_id']} " f"(Total: {len(self.active_connections)})")

        # Send initial connection acknowledgment
        await self.send_personal_message(
            {
                "type": "connection_established",
                "client_id": self.connection_metadata[websocket]["client_id"],
                "server_time": datetime.now().isoformat(),
            },
            websocket,
        )

    def disconnect(self, websocket: WebSocket):
        """
        Remove WebSocket connection.

        Args:
            websocket: WebSocket connection to remove

        Example:
            websocket_manager.disconnect(websocket)
        """
        if websocket in self.active_connections:
            client_info = self.connection_metadata.get(websocket, {})
            client_id = client_info.get("client_id", "unknown")

            self.active_connections.discard(websocket)
            self.connection_metadata.pop(websocket, None)

            self.logger.info(f"Client disconnected: {client_id} " f"(Remaining: {len(self.active_connections)})")

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """
        Send message to specific WebSocket connection.

        Args:
            message: Message dictionary to send
            websocket: Target WebSocket connection

        Example:
            await websocket_manager.send_personal_message(
                {'type': 'error', 'message': 'Invalid request'},
                websocket
            )
        """
        try:
            # Add timestamp if not present
            if "timestamp" not in message:
                message["timestamp"] = datetime.now().isoformat()

            # Send as JSON
            await websocket.send_json(message)

            # Update metadata
            if websocket in self.connection_metadata:
                self.connection_metadata[websocket]["messages_sent"] += 1
                self.connection_metadata[websocket]["last_message_at"] = datetime.now().isoformat()

        except Exception as e:
            self.logger.warning(f"Failed to send message to client: {e}")
            # Connection broken, remove it
            self.disconnect(websocket)

    async def broadcast(self, message: dict, exclude: Optional[Set[WebSocket]] = None):
        """
        Broadcast message to all active connections (async).

        Args:
            message: Message dictionary to broadcast
            exclude: Optional set of connections to exclude

        Example:
            await websocket_manager.broadcast({
                'type': 'training_update',
                'epoch': 10,
                'loss': 0.5
            })
        """
        if not self.active_connections:
            self.logger.debug("No active connections for broadcast")
            return

        # Add timestamp if not present
        if "timestamp" not in message:
            message["timestamp"] = datetime.now().isoformat()

        # Track message
        self.message_count += 1

        # Send to all connections (excluding specified ones)
        disconnected = set()
        connections = self.active_connections - (exclude or set())

        for connection in connections:
            try:
                await connection.send_json(message)

                # Update metadata
                if connection in self.connection_metadata:
                    self.connection_metadata[connection]["messages_sent"] += 1
                    self.connection_metadata[connection]["last_message_at"] = datetime.now().isoformat()

            except Exception as e:
                self.logger.warning(f"Failed to broadcast to client: {e}")
                disconnected.add(connection)

        # Remove disconnected clients
        for connection in disconnected:
            self.disconnect(connection)

        self.logger.debug(f"Broadcast message #{self.message_count} to {len(connections)} clients " f"(type: {message.get('type', 'unknown')})")

    def broadcast_sync(self, message: dict):
        """
        Synchronous broadcast for use from non-async code.

        This method allows broadcasting from regular Python code
        (e.g., training callbacks) without async/await syntax.
        Uses only the stored event loop set during application startup.

        Args:
            message: Message dictionary to broadcast

        Example:
            # From training callback (non-async)
            websocket_manager.broadcast_sync({
                'type': 'epoch_end',
                'epoch': 10,
                'loss': 0.5
            })
        """
        try:
            # Use only the stored event loop (set during app startup)
            if self.event_loop and self.event_loop.is_running():
                asyncio.run_coroutine_threadsafe(self.broadcast(message), self.event_loop)
            else:
                self.logger.debug("Event loop not set or not running; dropping sync broadcast")
        except Exception as e:
            self.logger.error(f"Sync broadcast failed: {type(e).__name__}: {e}")

    def broadcast_from_thread(self, message: dict):
        """
        Thread-safe broadcast for use from background threads.

        This method allows broadcasting from non-async background threads
        (e.g., demo mode training loop) by scheduling the coroutine on the
        main event loop using run_coroutine_threadsafe.

        Args:
            message: Message dictionary to broadcast

        Example:
            # From background thread
            websocket_manager.broadcast_from_thread({
                'type': 'training_metrics',
                'data': {...}
            })
        """
        if not self.active_connections:
            # No clients connected, skip broadcast to avoid logging spam
            return

        try:
            # Use the stored event loop
            if self.event_loop and not self.event_loop.is_closed():
                # Schedule the coroutine on the main event loop from this thread
                asyncio.run_coroutine_threadsafe(self.broadcast(message), self.event_loop)
            else:
                # No event loop available
                self.logger.debug("No running event loop available for broadcast_from_thread")

        except Exception as e:
            self.logger.warning(f"Failed to broadcast from thread: {type(e).__name__}: {e}")

    def broadcast_state_change(self, state_data: dict):
        """
        Broadcast training state change to all connected clients.

        Uses standardized state message format.

        Args:
            state_data: TrainingState dictionary to broadcast

        Example:
            websocket_manager.broadcast_state_change({
                'status': 'Started',
                'phase': 'Output',
                'learning_rate': 0.01,
                ...
            })
        """
        # Use standardized message format
        message = {"type": "state", "timestamp": time.time(), "data": state_data}
        self.broadcast_from_thread(message)

    async def send_ping(self, websocket: WebSocket):
        """
        Send ping message to check connection health.

        Args:
            websocket: WebSocket connection to ping

        Returns:
            bool: True if ping successful, False otherwise
        """
        try:
            await self.send_personal_message({"type": "ping"}, websocket)
            return True
        except Exception:
            return False

    async def broadcast_ping(self):
        """
        Send ping to all active connections.

        Useful for connection health monitoring.

        Example:
            # Periodic health check
            while True:
                await websocket_manager.broadcast_ping()
                await asyncio.sleep(30)
        """
        await self.broadcast({"type": "ping"})

    def get_connection_count(self) -> int:
        """
        Get number of active connections.

        Returns:
            Number of active WebSocket connections

        Example:
            count = websocket_manager.get_connection_count()
            print(f"{count} clients connected")
        """
        return len(self.active_connections)

    def get_connection_info(self) -> list:
        """
        Get information about all active connections.

        Returns:
            List of connection metadata dictionaries

        Example:
            connections = websocket_manager.get_connection_info()
            for conn in connections:
                print(f"{conn['client_id']}: {conn['messages_sent']} messages")
        """
        return [
            {
                "client_id": meta["client_id"],
                "connected_at": meta["connected_at"],
                "messages_sent": meta["messages_sent"],
                "last_message_at": meta["last_message_at"],
            }
            for meta in self.connection_metadata.values()
        ]

    def get_statistics(self) -> dict:
        """
        Get WebSocket manager statistics.

        Returns:
            Dictionary with statistics:
            {
                'active_connections': int,
                'total_messages_broadcast': int,
                'uptime_seconds': float
            }

        Example:
            stats = websocket_manager.get_statistics()
            print(f"Broadcast {stats['total_messages_broadcast']} messages")
        """
        return {
            "active_connections": len(self.active_connections),
            "total_messages_broadcast": self.message_count,
            "connections_info": self.get_connection_info(),
        }

    async def shutdown(self):
        """
        Gracefully shutdown all connections.

        Sends shutdown notice and closes all active connections.

        Example:
            await websocket_manager.shutdown()
        """
        self.logger.info("Shutting down WebSocket manager")

        # Send shutdown notice
        await self.broadcast({"type": "server_shutdown", "message": "Server is shutting down"})

        # Close all connections (suppress errors for already-closed connections)
        for websocket in list(self.active_connections):
            with contextlib.suppress(Exception):  # Connection may already be closed
                await websocket.close()
            self.disconnect(websocket)

        self.logger.info("WebSocket manager shutdown complete")


# Message Builder Helper Functions
def create_state_message(training_state) -> Dict[str, Any]:
    """
    Create a standardized state message.

    Args:
        training_state: TrainingState instance or dict with state data

    Returns:
        Standardized message dictionary

    Example:
        >>> from backend.training_monitor import TrainingState
        >>> state = TrainingState()
        >>> msg = create_state_message(state)
        >>> msg["type"]
        'state'
    """
    if hasattr(training_state, "get_state"):
        state_data = training_state.get_state()
    else:
        state_data = training_state

    return {"type": "state", "timestamp": time.time(), "data": state_data}


def create_metrics_message(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a standardized metrics message.

    Args:
        metrics: Dictionary containing training metrics

    Returns:
        Standardized message dictionary

    Example:
        >>> metrics = {
        ...     "epoch": 42,
        ...     "metrics": {
        ...         "loss": 0.23,
        ...         "accuracy": 0.91
        ...     }
        ... }
        >>> msg = create_metrics_message(metrics)
        >>> msg["type"]
        'metrics'
    """
    return {"type": "metrics", "timestamp": time.time(), "data": metrics}


def create_topology_message(topology: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a standardized topology message.

    Args:
        topology: Dictionary containing network topology data

    Returns:
        Standardized message dictionary

    Example:
        >>> topology = {
        ...     "input_units": 2,
        ...     "hidden_units": 3,
        ...     "output_units": 1,
        ...     "nodes": [],
        ...     "connections": []
        ... }
        >>> msg = create_topology_message(topology)
        >>> msg["type"]
        'topology'
    """
    return {"type": "topology", "timestamp": time.time(), "data": topology}


def create_event_message(event_type: str, details: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a standardized event message.

    Args:
        event_type: Type of event (e.g., 'cascade_add', 'phase_change')
        details: Event-specific details

    Returns:
        Standardized message dictionary

    Example:
        >>> msg = create_event_message(
        ...     "cascade_add",
        ...     {"unit_index": 2, "total_hidden_units": 3, "epoch": 42}
        ... )
        >>> msg["type"]
        'event'
        >>> msg["data"]["event_type"]
        'cascade_add'
    """
    return {"type": "event", "timestamp": time.time(), "data": {"event_type": event_type, "details": details}}


def create_control_ack_message(command: str, success: bool, message: str = "") -> Dict[str, Any]:
    """
    Create a standardized control acknowledgment message.

    Args:
        command: Command that was executed
        success: Whether command succeeded
        message: Optional message with details

    Returns:
        Standardized message dictionary

    Example:
        >>> msg = create_control_ack_message(
        ...     "start",
        ...     True,
        ...     "Training started successfully"
        ... )
        >>> msg["type"]
        'control_ack'
        >>> msg["data"]["success"]
        True
    """
    return {
        "type": "control_ack",
        "timestamp": time.time(),
        "data": {"command": command, "success": success, "message": message},
    }


def create_stats_message(stats: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a standardized network statistics message.

    Args:
        stats: Network statistics dictionary containing weight stats and metadata

    Returns:
        Standardized message dictionary

    Example:
        >>> stats = {
        ...     "threshold_function": "sigmoid",
        ...     "optimizer": "sgd",
        ...     "total_nodes": 10,
        ...     "weight_statistics": {...}
        ... }
        >>> msg = create_stats_message(stats)
        >>> msg["type"]
        'network_stats'
    """
    return {
        "type": "network_stats",
        "timestamp": time.time(),
        "data": stats,
    }


# Global singleton instance
websocket_manager = WebSocketManager()
