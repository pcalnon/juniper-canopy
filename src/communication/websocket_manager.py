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
import hashlib
import hmac

# import json
import logging
import secrets
import threading
import time
from datetime import datetime

# from typing import Set, Dict, Any, Optional
from typing import TYPE_CHECKING, Any, Dict, Optional, Set

# from fastapi import WebSocket, WebSocketDisconnect
from fastapi import WebSocket

if TYPE_CHECKING:
    from logger.logger import SystemLogger


# SEC-F19 / D4: name of the anonymous browser-session cookie set by canopy's
# SessionMiddleware (see ``main.py`` -> ``session_cookie="canopy_session"``). The
# per-session WS cap keys on this cookie value. Duplicated as a module constant
# (rather than imported from main) to avoid a circular import; keep in sync with
# the SessionMiddleware ``session_cookie`` in main.py.
_SESSION_COOKIE_NAME = "canopy_session"


# SEC-F19 log hygiene (PR #420 independent-review follow-up): never log the raw
# ``canopy_session`` cookie value. That cookie is a signed Starlette session
# token (``main.py`` -> ``SessionMiddleware(session_cookie="canopy_session")``);
# even a short raw prefix in a log line is an avoidable identifier leak that aids
# cross-log correlation of a browser session. ``_hash_session_key_for_log``
# returns a short, non-reversible tag instead -- keyed HMAC-SHA256 over the raw
# cookie with a per-process random secret, so the digest is NOT an offline-
# computable function of the cookie (an attacker who obtains the logs cannot
# confirm a stolen/guessed cookie by re-hashing it) and does not correlate across
# process restarts. Mirrors the cascor sibling, which hashes its identity before
# logging (juniper-cascor ``src/api/workers/security.py``).
_LOG_HASH_KEY = secrets.token_bytes(32)


def _hash_session_key_for_log(session_key: str) -> str:
    """Return a short, non-reversible tag for ``session_key`` that is safe to log.

    Keyed HMAC-SHA256 over the raw ``canopy_session`` cookie value with a
    per-process secret (:data:`_LOG_HASH_KEY`); only the first 12 hex characters
    are returned -- enough to correlate log lines within one process lifetime
    without being reversible. Guarantees the raw cookie value never reaches a log
    line (SEC-F19 log hygiene).
    """
    digest = hmac.new(_LOG_HASH_KEY, session_key.encode("utf-8"), hashlib.sha256).hexdigest()
    return digest[:12]


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
        # OBS-WIRE A.4: per-channel active-connection counts driving the
        # ``juniper_canopy_websocket_connections_active{channel=...}`` Gauge
        # via :func:`observability.set_websocket_connections`. Mutated under
        # ``_connections_lock`` so the count cannot race with connect /
        # disconnect on a different channel. Channel set is closed: only
        # ``"training"`` and ``"control"`` are emitted; the legacy ``/ws``
        # compat endpoint passes ``channel=None`` and skips the gauge to
        # preserve closed-set label discipline (R1.1).
        self._channel_counts: Dict[str, int] = {}
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

        # SEC-F19 / D4: Per-session connection tracking keyed on the anonymous
        # ``canopy_session`` cookie. Restores per-client fairness where the
        # per-IP cap above is inert (a shared NAT gateway IP collapses every
        # client to one key, audit HO-3). Same atomic check-then-increment /
        # decrement-on-disconnect discipline as the per-IP counter, under its
        # own lock so the two caps never contend.
        self._per_session_counts: Dict[str, int] = {}
        self._session_lock = threading.Lock()

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
        channel: Optional[str] = None,
        limits_reserved: bool = False,
    ) -> bool:
        """
        Accept new WebSocket connection.

        Args:
            websocket: WebSocket connection to accept
            client_id: Optional client identifier (default: auto-generated)
            subprotocol: Optional subprotocol to echo back. Set when the
                endpoint negotiated a bearer token via the
                ``Sec-WebSocket-Protocol`` header (SEC-06) so the server
                response acknowledges the chosen subprotocol.
            channel: OBS-WIRE A.4: closed-set channel label (``"training"``
                or ``"control"``). When provided, the
                ``juniper_canopy_websocket_connections_active{channel}``
                Gauge is updated with the post-connect count for that
                channel, and outbound ``send_personal_message`` /
                ``broadcast`` calls bump
                ``juniper_canopy_websocket_messages_total{channel, type}``.
                Pass ``None`` (default) on the legacy ``/ws`` compat route
                to skip metric emission and preserve closed-set discipline.
            limits_reserved: True when the caller has already incremented the
                per-IP/per-session counters via ``check_connection_limits``.
                When the global cap rejects here, those reservations must be
                released because ``disconnect()`` only decrements counters for
                websockets that were added to ``active_connections``.

        Returns:
            True when the websocket was accepted and tracked; False when the
            global cap rejected the connection.

        Example:
            await websocket_manager.connect(websocket, client_id='dashboard-1')
        """
        # SEC-F19 / D4: this ``max_connections`` check is the stack-absolute
        # GLOBAL connection cap. Every WS endpoint (/ws/training, /ws/control,
        # /ws) admits through this single ``connect()`` choke point, so it
        # bounds total server resource across all endpoints and backstops the
        # cookieless per-session case (design §5 Option B / §9 R2). Over-cap ->
        # close 1013 (same code as the per-IP / per-session paths).
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
            if limits_reserved:
                self._decrement_ip_count(websocket)
                self._decrement_session_count(websocket)
            await websocket.close(code=1013, reason="Max connections reached")
            return False

        await websocket.accept(subprotocol=subprotocol)

        # OBS-WIRE A.4: snapshot the post-connect per-channel count under the
        # same critical section that mutates active_connections so the gauge
        # update below sees a self-consistent value (no torn reads if a
        # concurrent disconnect removes the next connection on the same
        # channel before we publish).
        channel_count_after: Optional[int] = None
        with self._connections_lock:
            self.active_connections.add(websocket)
            self.connection_metadata[websocket] = {
                "client_id": client_id or f"client-{id(websocket)}",
                "connected_at": datetime.now().isoformat(),
                "messages_sent": 0,
                "last_message_at": None,
                # OBS-WIRE A.4 / messages_total: stash the channel so
                # outbound dispatch sites (send_personal_message, broadcast)
                # can label per-channel message counters without plumbing
                # the channel through every call site.
                "channel": channel,
            }
            client_label = self.connection_metadata[websocket]["client_id"]
            total_after = len(self.active_connections)
            if channel is not None:
                self._channel_counts[channel] = self._channel_counts.get(channel, 0) + 1
                channel_count_after = self._channel_counts[channel]

        self.logger.info(f"Client connected: {client_label} " f"(Total: {total_after})")

        # OBS-WIRE A.4: publish gauge OUTSIDE the lock — observability is a
        # best-effort side effect; we never want a Prometheus client error
        # to surface as a WS connect failure or hold _connections_lock
        # across an arbitrary collector call. Failures are logged and
        # swallowed so connect() remains semantically pure.
        if channel is not None and channel_count_after is not None:
            try:
                from observability import set_websocket_connections

                set_websocket_connections(channel, channel_count_after)
            except Exception as exc:  # pragma: no cover — defensive
                self.logger.debug(f"set_websocket_connections({channel}) failed: {exc}")

        # Send initial connection acknowledgment
        await self.send_personal_message(
            {
                "type": "connection_established",
                "client_id": self.connection_metadata[websocket]["client_id"],
                "server_time": datetime.now().isoformat(),
            },
            websocket,
        )
        return True

    def check_per_ip_limit(self, websocket: WebSocket, max_per_ip: int) -> bool:
        """Check if the source IP has room for another connection (M-SEC-04).

        Increments the counter if allowed. Counter is decremented in disconnect().

        SEC-F19 / D4: this cap is DoS-dampening only and is **inert behind
        NAT** -- inside Docker every client presents as the bridge-gateway IP
        (audit HO-3), so the cap is shared across all users and is NOT a
        per-client authenticator. :meth:`check_per_session_limit` restores
        per-client fairness under a shared NAT IP; :meth:`check_connection_limits`
        composes the two. Genuine per-client identity needs the deferred
        fronting-proxy X-Forwarded-For work (Phase 4).

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

    def _session_key(self, websocket: WebSocket) -> Optional[str]:
        """Return the anonymous ``canopy_session`` cookie value from the WS
        handshake, or ``None`` when the client sent no session cookie (SEC-F19/D4).

        A ``None`` key marks a cookieless (first) connection: it is exempt from
        the per-session cap and left to the global ``max_connections`` cap as the
        backstop (design §9 R2). Defensive against a malformed Cookie header
        (returns ``None``).
        """
        try:
            value = websocket.cookies.get(_SESSION_COOKIE_NAME)
        except Exception:  # pragma: no cover - defensive against a malformed Cookie header
            return None
        return value if isinstance(value, str) else None

    def check_per_session_limit(self, websocket: WebSocket, max_per_session: int) -> bool:
        """Check if the browser session has room for another connection (SEC-F19/D4).

        Keyed on the anonymous ``canopy_session`` cookie so per-client fairness
        survives Docker NAT, where every client shares the bridge-gateway IP and
        the per-IP cap is inert. A cookieless connection (no session cookie) is
        allowed and left to the global cap as the backstop (design §9 R2).
        Increments the per-session counter when allowed (atomic check-then-
        increment under ``_session_lock``); decremented in :meth:`disconnect`.

        Returns:
            True if the connection is allowed, False if the per-session limit is
            reached.
        """
        session_key = self._session_key(websocket)
        if session_key is None:
            # Cookieless first connection -- global cap backstops (R2).
            return True
        with self._session_lock:
            current = self._per_session_counts.get(session_key, 0)
            if current >= max_per_session:
                self.logger.warning(f"Per-session limit reached for session hash={_hash_session_key_for_log(session_key)} ({current}/{max_per_session})")
                return False
            self._per_session_counts[session_key] = current + 1
        return True

    def _decrement_session_count(self, websocket: WebSocket) -> None:
        """Decrement the per-session counter on disconnect (SEC-F19 / D4).

        Symmetric to :meth:`check_per_session_limit`: a cookieless connection was
        never counted, so a ``None`` key is a no-op.
        """
        session_key = self._session_key(websocket)
        if session_key is None:
            return
        with self._session_lock:
            count = self._per_session_counts.get(session_key, 0)
            if count <= 1:
                self._per_session_counts.pop(session_key, None)
            else:
                self._per_session_counts[session_key] = count - 1

    def check_connection_limits(self, websocket: WebSocket, *, max_per_ip: int, max_per_session: int) -> bool:
        """Composite admission gate for a new WS connection (SEC-F19 / D4).

        Applies the per-IP cap (DoS-dampening, inert behind NAT) and then the
        per-session cap (per-client fairness under a shared NAT IP). Returns True
        only when BOTH pass. On a per-session rejection the per-IP slot just
        taken is released, so a rejected attempt cannot leak the per-IP counter.
        The stack-absolute GLOBAL cap (``max_connections``) is enforced
        separately and authoritatively inside :meth:`connect` and also backstops
        the cookieless case. Callers reject an over-cap connection with close
        code 1013.

        Returns:
            True if the connection is within both the per-IP and per-session
            caps, False otherwise.
        """
        if not self.check_per_ip_limit(websocket, max_per_ip):
            return False
        if not self.check_per_session_limit(websocket, max_per_session):
            # Roll back the per-IP increment taken above so a per-session
            # rejection does not leak the per-IP counter.
            self._decrement_ip_count(websocket)
            return False
        return True

    def release_connection_limits(self, websocket: WebSocket) -> None:
        """Release cap counters reserved by :meth:`check_connection_limits`.

        Endpoint handlers reserve per-IP/per-session slots before awaiting the
        WebSocket accept/register path. If the later global cap rejects in
        :meth:`connect`, or the accept fails before the socket enters
        ``active_connections``, ``disconnect`` intentionally no-ops because the
        socket was never active. This helper lets callers roll back only the
        endpoint-level reservations in that pre-registration failure window.
        """
        self._decrement_ip_count(websocket)
        self._decrement_session_count(websocket)

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
        # OBS-WIRE A.4: snapshot post-disconnect channel count under the
        # same critical section so the gauge update below cannot be reordered
        # behind a racing connect().
        channel: Optional[str] = None
        channel_count_after: Optional[int] = None
        with self._connections_lock:
            if websocket not in self.active_connections:
                return
            client_info = self.connection_metadata.get(websocket, {})
            client_id = client_info.get("client_id", "unknown")
            channel = client_info.get("channel")
            self.active_connections.discard(websocket)
            self.connection_metadata.pop(websocket, None)
            remaining = len(self.active_connections)
            if channel is not None:
                # Floor at 0 — defensive against double-disconnect; we
                # already early-returned if websocket wasn't in the set,
                # but the dict.get default keeps us safe even if the
                # metadata entry was somehow missing.
                current = self._channel_counts.get(channel, 0)
                new_count = max(current - 1, 0)
                if new_count == 0:
                    self._channel_counts.pop(channel, None)
                else:
                    self._channel_counts[channel] = new_count
                channel_count_after = new_count

        self._decrement_ip_count(websocket)
        # SEC-F19 / D4: release the per-session slot symmetrically (also outside
        # _connections_lock; a no-op for a cookieless connection).
        self._decrement_session_count(websocket)
        self.logger.info(f"Client disconnected: {client_id} " f"(Remaining: {remaining})")

        # OBS-WIRE A.4: publish gauge outside the lock (same rationale as
        # connect()). When the channel drains to zero we still publish 0
        # rather than deleting the timeseries — Prometheus/Grafana panels
        # behave better with an explicit "0" than with a vanishing series.
        if channel is not None and channel_count_after is not None:
            try:
                from observability import set_websocket_connections

                set_websocket_connections(channel, channel_count_after)
            except Exception as exc:  # pragma: no cover — defensive
                self.logger.debug(f"set_websocket_connections({channel}) failed: {exc}")

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
            # OBS-WIRE A.4 / messages_total: snapshot the channel under the
            # same lock so we can label the Counter outside the critical
            # section without racing disconnect().
            now_iso = datetime.now().isoformat()
            channel: Optional[str] = None
            with self._connections_lock:
                meta = self.connection_metadata.get(websocket)
                if meta is not None:
                    meta["messages_sent"] += 1
                    meta["last_message_at"] = now_iso
                    channel = meta.get("channel")

            # OBS-WIRE A.4 / messages_total: bump
            # ``juniper_canopy_websocket_messages_total{channel, type}``.
            # Skipped when the connection has no channel (legacy ``/ws``
            # compat route) to preserve closed-set discipline.
            if channel is not None:
                try:
                    from observability import inc_websocket_messages

                    inc_websocket_messages(channel, message.get("type", "_other"))
                except Exception as exc:  # pragma: no cover — defensive
                    self.logger.debug(f"inc_websocket_messages({channel}) failed: {exc}")

        except Exception as e:
            self.logger.warning(f"Failed to send message to client: {e}")
            # Connection broken, remove it
            self.disconnect(websocket)

    async def broadcast(self, message: dict, exclude: Optional[Set[WebSocket]] = None, channel: Optional[str] = None):
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
            # Channel scoping (keepalive heartbeat): when ``channel`` is given,
            # send only to connections on that channel. ``/ws/control`` has no
            # idle timeout and treats an inbound pong as an unknown command, so
            # the heartbeat ping must never reach it — only ``channel="training"``.
            if channel is not None:
                connections = {c for c in connections if self.connection_metadata.get(c, {}).get("channel") == channel}

        # Add timestamp if not present (copy to avoid mutating caller's dict).
        # Match the Unix-float schema used by create_*_message() helpers.
        if "timestamp" not in message:
            message = {**message, "timestamp": time.time()}

        # Send to all connections in the snapshot.
        disconnected = set()
        # OBS-WIRE A.4 / messages_total: aggregate per-channel counts for a
        # single bulk emit after the loop. Doing one Counter.inc() per
        # successful delivery is correct, but accumulating per-channel and
        # emitting once at the end keeps the prometheus_client overhead off
        # the per-connection hot path during large fan-outs.
        per_channel_delivered: Dict[str, int] = {}
        msg_type = message.get("type", "_other")
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
                    ch = meta.get("channel")
                    if ch is not None:
                        per_channel_delivered[ch] = per_channel_delivered.get(ch, 0) + 1

        # OBS-WIRE A.4 / messages_total: emit one Counter increment per
        # (channel, type) bucket touched, with the aggregated count.
        if per_channel_delivered:
            try:
                from observability import inc_websocket_messages

                for ch, n in per_channel_delivered.items():
                    for _ in range(n):
                        inc_websocket_messages(ch, msg_type)
            except Exception as exc:  # pragma: no cover — defensive
                self.logger.debug(f"inc_websocket_messages (broadcast) failed: {exc}")

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

    async def broadcast_ping(self, channel: Optional[str] = None):
        """
        Send a heartbeat ping to active connections.

        Useful for connection health monitoring. When ``channel`` is given the
        ping is scoped to connections on that channel only — the server-side
        keepalive heartbeat passes ``channel="training"`` so it never reaches
        ``/ws/control`` (which has no idle timeout and treats an inbound pong
        as an unknown command).

        Args:
            channel: Optional channel label (e.g. ``"training"``) to scope the
                ping to. ``None`` pings every active connection.

        Example:
            # Periodic health check (server-side keepalive loop)
            while True:
                await asyncio.sleep(websocket_manager.heartbeat_interval)
                await websocket_manager.broadcast_ping(channel="training")
        """
        await self.broadcast({"type": "ping"}, channel=channel)

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
