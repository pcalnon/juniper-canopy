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
from __future__ import annotations

import asyncio
import contextlib

# import json
import logging
import threading
import time
from datetime import datetime

# from typing import Set, Dict, Any, Optional
from typing import TYPE_CHECKING, Any, Dict, Optional, Set

# from fastapi import WebSocket, WebSocketDisconnect
from fastapi import WebSocket

if TYPE_CHECKING:
    from logger.logger import SystemLogger


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
        from settings import get_settings

        self.active_connections: Set[WebSocket] = set()
        self.connection_metadata: Dict[WebSocket, dict] = {}
        self.logger = self._setup_logger()
        self.message_count = 0
        self.event_loop: Optional[asyncio.AbstractEventLoop] = None
        # BUG-CN-09 / BUG-CN-10 (Phase 3C): `active_connections`,
        # `connection_metadata`, and `message_count` are touched from at least
        # three execution contexts: the asyncio event loop (FastAPI websocket
        # endpoints), background threads via `broadcast_from_thread →
        # broadcast` (which currently re-enters the event loop but used to
        # iterate directly), and `disconnect()` which can fire from
        # `send_personal_message` after a send error. Iterating a bare `set()`
        # while another thread mutates it raises
        # `RuntimeError: Set changed size during iteration` (BUG-CN-09); the
        # `self.message_count += 1` increment is also a non-atomic
        # read-modify-write (BUG-CN-10). Guard every mutation site and the
        # read-then-iterate snapshot with a single `threading.Lock` so the
        # protection composes regardless of the calling context.
        self._connections_lock = threading.Lock()

        _settings = get_settings()
        self.max_connections = _settings.websocket.max_connections
        self.heartbeat_interval = _settings.websocket.heartbeat_interval
        self.reconnect_attempts = _settings.websocket.reconnect_attempts
        self.reconnect_delay = _settings.websocket.reconnect_delay

        # Phase B-pre-a: Per-IP connection tracking (M-SEC-04)
        self._per_ip_counts: Dict[str, int] = {}
        # CONC-01 (Phase 3B): The check_per_ip_limit / _decrement_ip_count pair
        # is a non-atomic read-modify-write on _per_ip_counts. While both methods
        # are sync (no await between get and assign, so async tasks on a single
        # event loop cannot interleave with themselves), disconnect() can also
        # be called from background-thread send paths. Use a threading.Lock so
        # the protection holds for any caller — sync, async, or BG thread —
        # without forcing the public API to become async.
        self._ip_lock = threading.Lock()

        self.logger.info(f"WebSocketManager initialized: " f"max_connections={self.max_connections}, " f"heartbeat_interval={self.heartbeat_interval}s, " f"reconnect_attempts={self.reconnect_attempts}, " f"reconnect_delay={self.reconnect_delay}s")

    def set_event_loop(self, loop: asyncio.AbstractEventLoop):
        """
        Set the event loop for thread-safe broadcasting.

        Args:
            loop: The asyncio event loop to use for broadcasting
        """
        self.event_loop = loop
        self.logger.debug("Event loop set for WebSocketManager")

    def _setup_logger(self) -> logging.Logger | SystemLogger:
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

    async def connect(
        self,
        websocket: WebSocket,
        client_id: Optional[str] = None,
        subprotocol: Optional[str] = None,
    ):
        """
        Accept new WebSocket connection.

        Args:
            websocket: WebSocket connection to accept
            client_id: Optional client identifier (default: auto-generated)
            subprotocol: Optional subprotocol to echo back. Set when the
                endpoint negotiated a bearer token via the
                ``Sec-WebSocket-Protocol`` header (SEC-06) so the server
                response acknowledges the chosen subprotocol.

        Example:
            await websocket_manager.connect(websocket, client_id='dashboard-1')
        """
        # BUG-CN-09 (Phase 3C): hold _connections_lock for the cap-check +
        # add so a concurrent `connect()` cannot also pass `len(...) <
        # max_connections` and overshoot, and so the set mutation cannot race
        # with a broadcast snapshot.
        with self._connections_lock:
            if len(self.active_connections) >= self.max_connections:
                self.logger.warning(f"Max connections ({self.max_connections}) reached, rejecting client")
                # Release the lock before the (suspending) close — we already
                # rejected the slot.
                close_ws = True
            else:
                close_ws = False
        if close_ws:
            await websocket.close(code=1013, reason="Max connections reached")
            return

        await websocket.accept(subprotocol=subprotocol)

        with self._connections_lock:
            self.active_connections.add(websocket)
            self.connection_metadata[websocket] = {
                "client_id": client_id or f"client-{id(websocket)}",
                "connected_at": datetime.now().isoformat(),
                "messages_sent": 0,
                "last_message_at": None,
            }
            client_label = self.connection_metadata[websocket]["client_id"]
            total_after = len(self.active_connections)

        self.logger.info(f"Client connected: {client_label} " f"(Total: {total_after})")

        # Send initial connection acknowledgment
        await self.send_personal_message(
            {
                "type": "connection_established",
                "client_id": self.connection_metadata[websocket]["client_id"],
                "server_time": datetime.now().isoformat(),
            },
            websocket,
        )

    def check_per_ip_limit(self, websocket: WebSocket, max_per_ip: int) -> bool:
        """Check if the source IP has room for another connection (M-SEC-04).

        Increments the counter if allowed. Counter is decremented in disconnect().

        Returns:
            True if the connection is allowed, False if limit reached.
        """
        source_ip = websocket.client[0] if websocket.client else "unknown"
        # CONC-01 (Phase 3B): atomic check-then-increment under self._ip_lock —
        # before this guard two near-simultaneous connections from the same IP
        # could both read `current = max_per_ip - 1`, both pass the check, and
        # both write `max_per_ip`, exceeding the configured per-IP cap.
        with self._ip_lock:
            current = self._per_ip_counts.get(source_ip, 0)
            if current >= max_per_ip:
                self.logger.warning(f"Per-IP limit reached for {source_ip} ({current}/{max_per_ip})")
                return False
            self._per_ip_counts[source_ip] = current + 1
        return True

    def _decrement_ip_count(self, websocket: WebSocket) -> None:
        """Decrement per-IP counter on disconnect."""
        source_ip = websocket.client[0] if websocket.client else "unknown"
        # CONC-01 (Phase 3B): symmetric atomic decrement so a concurrent
        # disconnect cannot lose a count and underflow the limiter.
        with self._ip_lock:
            count = self._per_ip_counts.get(source_ip, 0)
            if count <= 1:
                self._per_ip_counts.pop(source_ip, None)
            else:
                self._per_ip_counts[source_ip] = count - 1

    def disconnect(self, websocket: WebSocket):
        """
        Remove WebSocket connection.

        Args:
            websocket: WebSocket connection to remove

        Example:
            websocket_manager.disconnect(websocket)
        """
        # BUG-CN-09 (Phase 3C): membership probe + set/dict mutation must be
        # atomic relative to broadcast snapshots and concurrent disconnects.
        # _decrement_ip_count is intentionally invoked outside this lock so
        # we don't nest _ip_lock under _connections_lock (lock-order rule).
        with self._connections_lock:
            if websocket not in self.active_connections:
                return
            client_info = self.connection_metadata.get(websocket, {})
            client_id = client_info.get("client_id", "unknown")
            self.active_connections.discard(websocket)
            self.connection_metadata.pop(websocket, None)
            remaining = len(self.active_connections)

        self._decrement_ip_count(websocket)
        self.logger.info(f"Client disconnected: {client_id} " f"(Remaining: {remaining})")

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
            # Add timestamp if not present (copy to avoid mutating caller's dict).
            # Schema contract (module docstring lines 40, 58, …): timestamp is a
            # Unix float matching `time.time()`, which is what create_*_message()
            # emits. Stay consistent so test_websocket_message_schema assertions
            # against `isinstance(ts, (int, float))` hold for every path.
            if "timestamp" not in message:
                message = {**message, "timestamp": time.time()}

            # Send as JSON
            await websocket.send_json(message)

            # BUG-CN-09 / BUG-CN-10 (Phase 3C): per-connection metadata is
            # mutated from any context that calls send_personal_message —
            # protect under _connections_lock so the increment composes with
            # broadcast() and disconnect().
            now_iso = datetime.now().isoformat()
            with self._connections_lock:
                meta = self.connection_metadata.get(websocket)
                if meta is not None:
                    meta["messages_sent"] += 1
                    meta["last_message_at"] = now_iso

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
        # BUG-CN-09 / BUG-CN-10 (Phase 3C): snapshot the connection set under
        # the lock and increment the message counter inside the same critical
        # section, then iterate the snapshot outside the lock so a slow
        # `await connection.send_json(message)` cannot block other connect /
        # disconnect operations or other broadcasts.
        excluded = exclude or set()
        with self._connections_lock:
            if not self.active_connections:
                self.logger.debug("No active connections for broadcast")
                return
            self.message_count += 1
            current_count = self.message_count
            connections = self.active_connections - excluded

        # Add timestamp if not present (copy to avoid mutating caller's dict).
        # Match the Unix-float schema used by create_*_message() helpers.
        if "timestamp" not in message:
            message = {**message, "timestamp": time.time()}

        # Send to all connections in the snapshot.
        disconnected = set()
        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                self.logger.warning(f"Failed to broadcast to client: {e}")
                disconnected.add(connection)
                continue

            # Per-connection metadata bookkeeping under the same lock so the
            # counter can't race with disconnect() removing the entry.
            now_iso = datetime.now().isoformat()
            with self._connections_lock:
                meta = self.connection_metadata.get(connection)
                if meta is not None:
                    meta["messages_sent"] += 1
                    meta["last_message_at"] = now_iso

        # Remove disconnected clients (disconnect() reacquires the lock).
        for connection in disconnected:
            self.disconnect(connection)

        self.logger.debug(f"Broadcast message #{current_count} to {len(connections)} clients " f"(type: {message.get('type', 'unknown')})")

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
        # BUG-CN-09 (Phase 3C): the early-out used to read len(set) from a
        # background thread without the lock. Snapshot the size under the
        # lock and decide based on that to avoid racing against connect().
        with self._connections_lock:
            has_connections = bool(self.active_connections)
        if not has_connections:
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
        with self._connections_lock:
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
        # BUG-CN-09 (Phase 3C): snapshot the metadata dict under the lock so
        # iteration cannot race with connect/disconnect mutating it.
        with self._connections_lock:
            metas = list(self.connection_metadata.values())
        return [
            {
                "client_id": meta["client_id"],
                "connected_at": meta["connected_at"],
                "messages_sent": meta["messages_sent"],
                "last_message_at": meta["last_message_at"],
            }
            for meta in metas
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
        # BUG-CN-09 / BUG-CN-10 (Phase 3C): atomic snapshot of count + counter
        # so external observers don't see a torn read.
        with self._connections_lock:
            active_count = len(self.active_connections)
            total_messages = self.message_count
        return {
            "active_connections": active_count,
            "total_messages_broadcast": total_messages,
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

        # BUG-CN-09 (Phase 3C): snapshot the set under the lock before
        # iterating so a late-arriving connect() cannot trigger a "set
        # changed size during iteration" RuntimeError mid-shutdown.
        with self._connections_lock:
            to_close = list(self.active_connections)
        for websocket in to_close:
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


def create_command_response_message(
    command: str,
    status: str,
    *,
    command_id: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
    code: Optional[str] = None,
) -> Dict[str, Any]:
    """Phase D §S10: canonical command_response envelope for /ws/control.

    Mirrors ``juniper_cascor.api.websocket.messages.create_control_ack_message``
    so browsers can correlate async responses by ``command_id`` regardless of
    whether the command was served by canopy or cascor. ``code`` carries
    machine-readable error categories such as ``"unknown_command"``.

    The envelope intentionally omits ``seq`` (D-03): the /ws/control channel
    has no replay buffer.

    Backward-compat fields (``ok``, top-level ``command``, ``state``, ``error``)
    are duplicated alongside the nested ``data`` block so existing integration
    tests and pre-Phase-D clients keep working until the next round of tests
    is migrated. Remove once §S10 adoption is complete.
    """
    is_success = status == "success"
    msg: Dict[str, Any] = {
        "type": "command_response",
        "timestamp": time.time(),
        "data": {
            "command": command,
            "status": status,
        },
        # Legacy compat (pre-Phase-D callers read these top-level fields)
        "ok": is_success,
        "command": command,
    }
    if command_id is not None:
        msg["data"]["command_id"] = command_id
    if data:
        msg["data"]["result"] = data
        msg["state"] = data  # legacy compat
    if error:
        msg["data"]["error"] = error
        msg["error"] = error  # legacy compat
    if code is not None:
        msg["data"]["code"] = code
    return msg


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
