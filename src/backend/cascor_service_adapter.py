#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Service adapter wrapping juniper-cascor-client for REST/WebSocket communication with CasCor service
#
# Author:        Paul Calnon
# Version:       0.1.0
# File Name:     cascor_service_adapter.py
# File Path:     Juniper/juniper-canopy/src/backend/
#
# Date Created:  2026-02-21
# Last Modified: 2026-02-27
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#     CascorServiceAdapter wraps the juniper-cascor-client package to provide
#     a backward-compatible interface matching CascorIntegration's public API.
#     This enables Canopy to communicate with CasCor as an independent service
#     over REST/WebSocket instead of in-process sys.path injection.
#
#####################################################################################################################################################################################################
# Notes:
#     Phase 4 of the Juniper polyrepo migration — Decouple Canopy from CasCor.
#     All methods match the CascorIntegration interface used by main.py.
#
#####################################################################################################################################################################################################
# References:
#     - juniper-cascor-client v0.1.0 API
#     - notes/DECOUPLE_CANOPY_FROM_CASCOR_PLAN.md
#
#####################################################################################################################################################################################################

import asyncio
import contextlib
import json
import logging
import time
from typing import Any, Callable, Dict, Optional, Tuple, Union, cast

from juniper_cascor_client import CascorControlStream, CascorTrainingStream, JuniperCascorClient, JuniperCascorClientError
from juniper_cascor_client.exceptions import JuniperCascorConnectionError

from backend.circuit_breaker import CircuitBreaker
from canopy_constants import BackendConstants

# from juniper_cascor_client.juniper_cascor_client.client import CascorTrainingStream, JuniperCascorClient
# from juniper_cascor_client.client import CascorTrainingStream, JuniperCascorClient


# from juniper_cascor_client.juniper_cascor_client.exceptions import JuniperCascorClientError
# from juniper_cascor_client.exceptions import JuniperCascorClientError

logger = logging.getLogger("juniper_canopy.backend.cascor_service_adapter")


def _first_defined(*values, default=None):
    """Return the first value that is not None, or default.

    Unlike ``or`` chains, this correctly preserves falsy-but-valid values
    like 0, 0.0, False, and empty strings.
    """
    for v in values:
        if v is not None:
            return v
    return default


class ControlStreamSupervisor:
    """Phase C: persistent /ws/control connection to cascor for set_params.

    Maintains a background ``CascorControlStream`` with auto-reconnect.
    Exposes ``set_params()`` that delegates to the stream's correlated
    command/response mechanism. Bounded pending map (256 max, C-01).

    The supervisor runs on the event loop passed at construction time.
    ``apply_params`` calls it via ``asyncio.run_coroutine_threadsafe``.
    """

    _BACKOFF = [1, 2, 5, 10, 30]

    def __init__(self, ws_url: str, api_key: Optional[str] = None, ws_origin: Optional[str] = None) -> None:
        self._ws_url = ws_url
        self._api_key = api_key
        # E.2 PR-2-C: forward Origin to ``CascorControlStream(origin=…)``
        # so cascor's fail-closed ``/ws/control`` allowlist
        # (juniper-cascor#129) accepts canopy's docker-compose upgrade.
        # None → preserve pre-0.5.0 behaviour (no Origin header sent).
        self._ws_origin = ws_origin
        self._stream: Optional[CascorControlStream] = None
        self._connect_task: Optional[asyncio.Task] = None
        self._shutdown = False
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    @property
    def is_connected(self) -> bool:
        return self._stream is not None and self._stream._ws is not None

    async def start(self) -> None:
        """Start the supervisor background connect loop."""
        self.loop = asyncio.get_running_loop()
        self._shutdown = False
        self._connect_task = asyncio.create_task(self._connect_loop())

    async def stop(self) -> None:
        """Shut down the supervisor and close the stream."""
        self._shutdown = True
        if self._connect_task:
            self._connect_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._connect_task
        if self._stream:
            await self._stream.disconnect()
            self._stream = None

    async def set_params(self, params: dict, *, timeout: float = 1.0) -> dict:
        """Send set_params via the persistent control stream."""
        if not self.is_connected or self._stream is None:
            raise JuniperCascorConnectionError("Control stream not connected")
        result = await self._stream.set_params(params, timeout=timeout)
        return result if isinstance(result, dict) else {}

    async def _connect_loop(self) -> None:
        """Auto-reconnect loop with backoff."""
        attempt = 0
        while not self._shutdown:
            try:
                self._stream = CascorControlStream(
                    base_url=self._ws_url,
                    api_key=self._api_key,
                    origin=self._ws_origin,
                )
                await self._stream.connect()
                logger.info("Control stream supervisor connected to %s", self._ws_url)
                attempt = 0
                # Stay connected until disconnect. ASYNC110 prefers an
                # ``asyncio.Event`` here; for this supervisor a 1-second
                # poll is fine because (a) ``self.is_connected`` is updated
                # by callbacks we don't own, so wiring an Event around it
                # would require touching the stream class, and (b) the
                # one-second granularity is well below any reconnect
                # latency we care about.
                while not self._shutdown and self.is_connected:  # noqa: ASYNC110
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                return
            except Exception as e:
                delay = self._BACKOFF[min(attempt, len(self._BACKOFF) - 1)]
                logger.warning("Control stream supervisor disconnected (%s), reconnecting in %ds", e, delay)
                attempt += 1
                try:
                    await asyncio.sleep(delay)
                except asyncio.CancelledError:
                    return


class _ServiceTrainingMonitor:
    """
    Lightweight training monitor that delegates to the CasCor service via REST.

    Satisfies the subset of TrainingMonitor's interface used by main.py:
        - .is_training (property)
        - .get_current_metrics()
        - .get_recent_metrics(count)
    """

    def __init__(self, client: JuniperCascorClient):
        self._client = client

    @property
    def is_training(self) -> bool:
        try:
            status = self._client.get_training_status()
            is_training_top = status.get("is_training")
            if is_training_top is not None:
                return bool(is_training_top)
            data = status.get("data", {})
            if isinstance(data, dict):
                return bool(data.get("training_active", False))
            return False
        except Exception:
            return False

    def get_current_metrics(self) -> Dict[str, Any]:
        try:
            result = self._client.get_metrics()
            if isinstance(result, dict) and "data" in result:
                data = result["data"]
                if isinstance(data, dict):
                    flat = CascorServiceAdapter._normalize_metric(data)
                    return CascorServiceAdapter._to_dashboard_metric(flat)
                return result
            return result if isinstance(result, dict) else {}
        except Exception:
            return {}

    def get_recent_metrics(self, count: int = 100) -> list:
        try:
            result = self._client.get_metrics_history(count=count)
            if isinstance(result, dict):
                data = result.get("data", result)
                if isinstance(data, list):
                    return [CascorServiceAdapter._to_dashboard_metric(CascorServiceAdapter._normalize_metric(m)) for m in data]
                if isinstance(data, dict):
                    history = data.get("history", [])
                    return [CascorServiceAdapter._to_dashboard_metric(CascorServiceAdapter._normalize_metric(m)) for m in history]
            return result if isinstance(result, list) else []
        except Exception:
            return []


class _NetworkSentinel:
    """Truthy sentinel representing a remote network exists."""

    def __bool__(self):
        return True

    def __repr__(self):
        return "<RemoteNetwork>"


class CascorServiceAdapter:
    """
    Adapter wrapping juniper-cascor-client to provide a CascorIntegration-compatible
    interface for main.py. Communicates with CasCor over REST/WebSocket.
    """

    _is_service_adapter = True

    def __init__(
        self,
        service_url: str = BackendConstants.DEFAULT_CASCOR_SERVICE_URL,
        api_key: Optional[str] = None,
        client: Optional[JuniperCascorClient] = None,
        ws_origin: Optional[str] = None,
    ):
        self._service_url = service_url
        self._api_key = api_key
        # E.2 PR-2-C: store + forward to the control-stream supervisor.
        # See ``settings.cascor_ws_origin`` for the env-binding contract.
        self._ws_origin = ws_origin
        self._client = client or JuniperCascorClient(base_url=service_url, api_key=api_key)
        self.training_monitor = _ServiceTrainingMonitor(self._client)
        self._training_stream: Optional[CascorTrainingStream] = None
        self._relay_task: Optional[asyncio.Task] = None
        self._attached_to_existing: bool = False
        self._state_update_callback: Optional[Callable] = None
        self._circuit = CircuitBreaker(name=BackendConstants.CIRCUIT_BREAKER_NAME, failure_threshold=BackendConstants.CIRCUIT_BREAKER_FAILURE_THRESHOLD, recovery_timeout=BackendConstants.CIRCUIT_BREAKER_RECOVERY_TIMEOUT)

        # Network property TTL cache
        self._network_cache = None
        self._network_cache_time = 0

        # Derive WebSocket URL from HTTP URL
        ws_url = service_url.replace("http://", "ws://").replace("https://", "wss://")
        self._ws_url = ws_url

        # Phase C: control stream supervisor for hot-param WS routing
        self._control_supervisor = ControlStreamSupervisor(ws_url=ws_url, api_key=api_key, ws_origin=ws_origin)

    @property
    def service_url(self) -> str:
        """Return the CasCor service URL."""
        return self._service_url

    @property
    def client(self) -> JuniperCascorClient:
        """Return the underlying JuniperCascorClient instance."""
        return self._client

    @staticmethod
    def is_cascor_nested(data: dict) -> bool:
        """Detect whether data uses cascor's nested structure.

        Uses positive detection of nested structure (state_machine/monitor/
        training_state) rather than checking for flat keys, which could
        misfire if cascor ever adds a flat field.

        Public wrapper around ``_is_cascor_nested`` for use by external callers.
        """
        return CascorServiceAdapter._is_cascor_nested(data)

    def set_state_update_callback(self, callback: Callable) -> None:
        """Register a callback invoked when cascor broadcasts state changes."""
        self._state_update_callback = callback

    # ------------------------------------------------------------------
    # Connection lifecycle (async)
    # ------------------------------------------------------------------

    async def connect(self) -> bool:
        """Connect to the CasCor service and verify it is reachable."""
        try:
            return bool(self._client.is_alive())
        except Exception:
            logger.error(f"Failed to connect to CasCor service at {self._service_url}")
            return False

    def attach_to_existing(self) -> bool:
        """
        Attempt to attach to an already-running cascor session non-destructively.

        Calls get_network() to confirm a network exists. Does NOT create a new
        network or modify any cascor state. The network property queries the
        client on each access, so there is no local state to cache.

        Returns:
            True if an existing network was found; False otherwise.
        """
        try:
            result = self._client.get_network()
            if result and not result.get("error"):
                self._attached_to_existing = True
                logger.info("Attached to existing cascor network (non-destructive)")
                return True
        except Exception as e:
            logger.debug(f"No existing cascor network found: {e}")
        self._attached_to_existing = False
        return False

    async def start_metrics_relay(self) -> None:
        """
        Open a WebSocket training stream and relay messages to Canopy's
        websocket_manager for broadcast to dashboard clients.
        """

        async def _relay_loop():
            import random

            from communication.websocket_manager import websocket_manager

            attempt = 0
            relay_enabled = True
            # OBS-WIRE-02 / Q1 (option a): per-connection sequence
            # tracker for client-side gap detection on the training
            # channel. Reset to ``None`` whenever the relay reconnects
            # (the cascor-side counter restarts at 1 on each new
            # connection — see juniper-cascor websocket_manager seq
            # assignment), so a "gap" is only meaningful within one
            # connected session. Gap detection is inherently client-
            # side truth (cascor cannot observe whether a frame
            # actually arrived); see juniper-ml#197 state-analysis.
            last_training_seq: Optional[int] = None
            while relay_enabled:
                try:
                    stream = CascorTrainingStream(base_url=self._ws_url, api_key=self._api_key)
                    await stream.connect()
                    attempt = 0
                    last_training_seq = None
                    async for message in stream.stream():
                        # METRICS-MON R2.2.5 / seed-05: validate the inbound
                        # frame against juniper-cascor-protocol's canonical
                        # envelope schemas. Validation is observational —
                        # never raises, never modifies ``message`` — so the
                        # downstream dispatch logic stays byte-compatible.
                        # On UnknownEnvelope (unknown type OR known type with
                        # invalid payload) increments
                        # juniper_canopy_unrecognized_ws_frames_total with
                        # the cardinality-bounded type label.
                        try:
                            from juniper_cascor_protocol.envelope import UnknownEnvelope, validate_envelope

                            from observability import inc_unrecognized_ws_frame

                            _envelope = validate_envelope(message)
                            if isinstance(_envelope, UnknownEnvelope):
                                inc_unrecognized_ws_frame(_envelope.type, "training")
                        except Exception:  # noqa: BLE001 — observability MUST NOT break the relay loop
                            logger.debug("Inbound-frame validation hook errored; relay continues", exc_info=True)

                        # OBS-WIRE-02 / Q1 (option a): client-side WS
                        # sequence-gap detection. Compares each frame's
                        # ``seq`` against ``last_training_seq + 1``;
                        # mismatches bump the new
                        # ``juniper_canopy_ws_seq_gap_detected_total``
                        # counter (replaces the deleted cascor-side
                        # counter, which had no semantically valid
                        # server-side wire-site). Frames without a
                        # ``seq`` field — e.g. /ws/control responses
                        # (D-03) — are skipped. Wrapped in a broad
                        # try/except so observability NEVER breaks the
                        # relay loop.
                        try:
                            incoming_seq = message.get("seq") if isinstance(message, dict) else None
                            if isinstance(incoming_seq, int):
                                if last_training_seq is not None and incoming_seq != last_training_seq + 1:
                                    from observability import inc_ws_seq_gap_detected

                                    inc_ws_seq_gap_detected("training")
                                last_training_seq = incoming_seq
                        except Exception:  # noqa: BLE001 — observability MUST NOT break the relay loop
                            logger.debug("Inbound-frame seq-gap hook errored; relay continues", exc_info=True)

                        msg_type = message.get("type", "")

                        # Phase F: respond to cascor heartbeat pings with pong
                        if msg_type == "ping":
                            if stream._ws:
                                await stream._ws.send(json.dumps({"type": "pong"}))
                            continue

                        data = message.get("data", message)

                        # Normalize metrics payloads to dashboard format (P5-RC-14)
                        if msg_type == "metrics" and isinstance(data, dict):
                            data = CascorServiceAdapter._to_dashboard_metric(CascorServiceAdapter._normalize_metric(data))

                        await websocket_manager.broadcast({"type": msg_type, "data": data})

                        # On cascade_add, fetch fresh topology and broadcast
                        if msg_type == "cascade_add":
                            try:
                                topology = self.extract_network_topology()
                                if topology:
                                    await websocket_manager.broadcast({"type": "topology", "data": topology})
                            except Exception as te:
                                logger.debug(f"Failed to fetch topology after cascade_add: {te}")

                        # Update local training_state from cascor state messages
                        if msg_type == "state" and self._state_update_callback and isinstance(data, dict):
                            try:
                                from backend.state_sync import CascorStateSync

                                status = CascorStateSync._normalize_status(data.get("status", data.get("state", "")))
                                phase_detail = data.get("phase_detail", "")
                                if phase_detail in ("training_candidates", "candidate_training"):
                                    candidate_pool_status = "Training"
                                    candidate_pool_phase = "Training"
                                elif phase_detail == "adding_candidate":
                                    candidate_pool_status = "Selecting Best"
                                    candidate_pool_phase = "Selecting"
                                else:
                                    candidate_pool_status = "Inactive"
                                    candidate_pool_phase = "Idle"
                                # Map top candidate identity from CasCor state.
                                # Field-name bridge (NEW-02): cascor emits ``best_candidate_id`` /
                                # ``best_candidate_uuid`` on its TrainingState while canopy's
                                # TrainingState uses ``top_candidate_id`` / ``top_candidate_uuid``.
                                # Both names refer to the same concept (highest-correlation candidate
                                # in the current pool). Rather than rename either side, we bridge
                                # the names at this single adapter seam and document it here.
                                best_cand_id = data.get("best_candidate_id")
                                second_cand_id = data.get("second_candidate_id")
                                second_cand_corr = data.get("second_candidate_correlation", 0.0)
                                self._state_update_callback(
                                    status=status,
                                    phase=data.get("phase", ""),
                                    current_epoch=data.get("current_epoch"),
                                    current_step=data.get("current_step"),
                                    learning_rate=data.get("learning_rate"),
                                    max_hidden_units=data.get("max_hidden_units"),
                                    max_epochs=data.get("max_epochs"),
                                    phase_detail=phase_detail,
                                    grow_iteration=data.get("grow_iteration"),
                                    grow_max=data.get("grow_max"),
                                    best_correlation=data.get("best_correlation"),
                                    candidates_trained=data.get("candidates_trained"),
                                    candidates_total=data.get("candidates_total"),
                                    phase_started_at=data.get("phase_started_at"),
                                    candidate_epoch=data.get("candidate_epoch"),
                                    candidate_total_epochs=data.get("candidate_total_epochs"),
                                    candidate_pool_status=candidate_pool_status,
                                    candidate_pool_phase=candidate_pool_phase,
                                    candidate_pool_size=data.get("candidates_total"),
                                    top_candidate_id=str(best_cand_id) if best_cand_id is not None and best_cand_id != -1 else "",
                                    top_candidate_score=data.get("best_correlation", 0.0),
                                    second_candidate_id=str(second_cand_id) if second_cand_id is not None else "",
                                    second_candidate_score=second_cand_corr,
                                    all_correlations=data.get("all_correlations", []),
                                )
                            except Exception as se:  # nosec B110
                                logger.debug(f"State update callback error: {se}")

                        # Update local training_state from candidate progress messages
                        if msg_type == "candidate_progress" and self._state_update_callback and isinstance(data, dict):
                            try:
                                self._state_update_callback(
                                    phase_detail="training_candidates",
                                    candidate_epoch=data.get("epoch"),
                                    candidate_total_epochs=data.get("total_epochs"),
                                    best_correlation=data.get("correlation"),
                                    candidate_pool_status="Training",
                                )
                            except Exception as cpe:  # nosec B110
                                logger.debug(f"Candidate progress callback error: {cpe}")

                        # Handle event messages (e.g. training_complete) to keep training_state aligned
                        if msg_type == "event" and self._state_update_callback and isinstance(data, dict):
                            event_name = data.get("event", "")
                            if event_name == "training_complete":
                                try:
                                    self._state_update_callback(status="Completed", phase="Idle")
                                    logger.info("Training complete event received from cascor")
                                except Exception as ee:  # nosec B110
                                    logger.debug(f"Event callback error: {ee}")

                    await stream.disconnect()
                except asyncio.CancelledError:
                    relay_enabled = False
                except OSError as e:
                    # Phase F: jitter backoff — matches JS formula (GAP-WS-30/31)
                    delay = random.random() * min(60, 0.5 * (2 ** min(attempt, 7)))
                    delay = max(delay, 0.5)  # Floor at 500ms
                    logger.warning(f"Cascor metrics stream disconnected ({e}). Reconnecting in {delay:.1f}s")
                    attempt += 1
                    try:
                        await asyncio.sleep(delay)
                    except asyncio.CancelledError:
                        relay_enabled = False
                except Exception as e:
                    logger.error("Unexpected error in relay loop: %s", e, exc_info=True)
                    break

        self._relay_task = asyncio.create_task(_relay_loop())
        logger.info("Metrics relay started")

        # Phase C: start control stream supervisor for hot-param WS routing
        from settings import get_settings

        app_settings = get_settings()
        if getattr(app_settings, "use_websocket_set_params", False):
            await self._control_supervisor.start()
            logger.info("Control stream supervisor started (use_websocket_set_params=True)")
            assert len(self._HOT_CASCOR_PARAMS) > 0, "HOT_CASCOR_PARAMS must be non-empty when WS set_params enabled"
        else:
            logger.info("Control stream supervisor skipped (use_websocket_set_params=False)")

    async def stop_metrics_relay(self) -> None:
        """Cancel the WebSocket relay task and control stream supervisor."""
        # Phase C: stop control supervisor
        await self._control_supervisor.stop()

        if self._relay_task and not self._relay_task.done():
            self._relay_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._relay_task
        self._relay_task = None
        logger.info("Metrics relay stopped")

    # ------------------------------------------------------------------
    # Network property (lines 491, 1803 in main.py)
    # ------------------------------------------------------------------

    @property
    def network(self) -> Optional[_NetworkSentinel]:
        """Return a truthy sentinel if the service has a network, else None.

        Results are cached for 30 seconds to avoid redundant HTTP calls.
        """
        now = time.monotonic()
        if self._network_cache is not None and now - self._network_cache_time < 30:
            return self._network_cache
        try:
            result = self._client.get_network()
            if result and not result.get("error"):
                self._network_cache = _NetworkSentinel()
                self._network_cache_time = now
                return self._network_cache
        except Exception as e:
            logger.debug("Failed to query network: %s", e)
        self._network_cache = None
        self._network_cache_time = now
        return None

    # ------------------------------------------------------------------
    # _training_stop_requested (line 1920 in main.py)
    # ------------------------------------------------------------------

    @property
    def _training_stop_requested(self) -> bool:
        """Service manages stop requests internally."""
        return False

    # ------------------------------------------------------------------
    # Network creation & management
    # ------------------------------------------------------------------

    def create_network(self, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        try:
            result: Dict[str, Any] = self._client.create_network(**(config or {}))
            return result
        except JuniperCascorClientError as e:
            logger.error(f"Failed to create network: {e}")
            return {"error": str(e)}

    # ------------------------------------------------------------------
    # Training control
    # ------------------------------------------------------------------

    def start_training_background(self, *args, **kwargs) -> "Tuple[bool, Optional[str]]":
        """Kick off training via REST. Returns ``(started, error_message)``.

        PR-B2 (training-start diagnosis 2026-07-09): the cascor 409 detail
        (e.g. "Training cannot be started: Training data not provided") used to
        be flattened to a bare ``False`` here, so the §S10 surfacing could only
        show a generic failure. The message now rides back to ServiceBackend's
        ControlResult.
        """
        try:
            self._client.start_training(**kwargs)
            return True, None
        except JuniperCascorClientError as e:
            logger.error(f"Failed to start training: {e}")
            return False, str(e)

    def is_training_in_progress(self) -> bool:
        try:
            status = self._client.get_training_status()
            is_training_top = status.get("is_training")
            if is_training_top is not None:
                return bool(is_training_top)
            data = status.get("data", {})
            if isinstance(data, dict):
                return bool(data.get("training_active", False))
            return False
        except JuniperCascorClientError:
            return False

    def request_training_stop(self) -> bool:
        try:
            self._client.stop_training()
            return True
        except JuniperCascorClientError as e:
            logger.error(f"Failed to stop training: {e}")
            return False

    def pause_training(self) -> Dict[str, Any]:
        try:
            result = self._client.pause_training()
            return {"ok": True, "data": result}
        except JuniperCascorClientError as e:
            logger.error(f"Failed to pause training: {e}")
            return {"ok": False, "error": str(e)}

    def resume_training(self) -> Dict[str, Any]:
        try:
            result = self._client.resume_training()
            return {"ok": True, "data": result}
        except JuniperCascorClientError as e:
            logger.error(f"Failed to resume training: {e}")
            return {"ok": False, "error": str(e)}

    def reset_training(self) -> Dict[str, Any]:
        try:
            result = self._client.reset_training()
            self._attached_to_existing = False
            return {"ok": True, "data": result}
        except JuniperCascorClientError as e:
            logger.error(f"Failed to reset training: {e}")
            return {"ok": False, "error": str(e)}

    # Parameter mapping: canopy nn_*/cn_* names -> cascor API parameter names
    _CANOPY_TO_CASCOR_PARAM_MAP = {
        "nn_learning_rate": "learning_rate",
        "nn_max_hidden_units": "max_hidden_units",
        "nn_max_total_epochs": "epochs_max",
        "nn_max_iterations": "max_iterations",
        "nn_output_epochs": "output_epochs",
        "nn_init_output_weights": "init_output_weights",
        "nn_optimizer_type": "optimizer_type",
        "nn_activation_function_name": "activation_function_name",
        "nn_growth_convergence_threshold": "convergence_threshold",
        "nn_patience": "patience",
        "cn_patience": "candidate_patience",
        "cn_training_convergence_threshold": "candidate_convergence_threshold",
        "cn_training_iterations": "candidate_epochs",
        "cn_pool_size": "candidate_pool_size",
        "cn_correlation_threshold": "correlation_threshold",
        "cn_candidate_learning_rate": "candidate_learning_rate",
        # FRONTEND_ISSUES_PLAN_2026-05-09 §1.5 C1b / Issue #1 — candidate-pool
        # selection knobs. Schema landed in cascor #241 (PR-4a) with the
        # post-merge invariant validator (_validate_candidate_pool_triple).
        # Canopy adds a clientside C2.2 fast-feedback validator (see
        # dashboard_manager); the server remains authoritative.
        "cn_multi_candidate": "multi_candidate",
        "cn_candidate_selection": "candidate_selection",
        "cn_selected_candidates": "selected_candidates",
        "cn_top_candidates": "top_candidates",
        "cn_random_candidates": "random_candidates",
    }

    # FRONTEND_ISSUES_PLAN_2026-05-09 §1.6 — params that are conceptually
    # canopy-only (drive demo-side dataset generation, UI behavior, etc.) and
    # should never be reported as "skipped" in the toast. Used by the
    # test_param_map_completeness contract test to allow-list intentionally-
    # local fields without weakening the check.
    _CANOPY_LOCAL_PARAMS: frozenset = frozenset(
        {
            "nn_spiral_rotations",
            "nn_spiral_number",
            "nn_dataset_elements",
            "nn_dataset_noise",
            "nn_multi_node_layers",
            "nn_growth_trigger",
            "nn_growth_preset_epochs",
            "cn_training_complete",
        }
    )

    _CASCOR_TO_CANOPY_PARAM_MAP = {v: k for k, v in _CANOPY_TO_CASCOR_PARAM_MAP.items()}

    # Phase C: hot params route over /ws/control; cold stay on REST PATCH (§S9)
    _HOT_CASCOR_PARAMS: frozenset = frozenset(
        {
            "learning_rate",
            "candidate_learning_rate",
            "correlation_threshold",
            "candidate_pool_size",
            "max_hidden_units",
            "epochs_max",
            "max_iterations",
            "output_epochs",
            "patience",
            "convergence_threshold",
            "candidate_convergence_threshold",
            "candidate_patience",
            # FRONTEND_ISSUES_PLAN_2026-05-09 §1.5 C1b — pool resize knobs are
            # safe mid-training; the cascade-correlation outer loop reads them
            # at the next growth iteration boundary (PR-4b will wire the
            # selection logic; today they're storage-only but still hot since
            # the read is fully snapshot at iteration start).
            "selected_candidates",
            "top_candidates",
            "random_candidates",
        }
    )

    _COLD_CASCOR_PARAMS: frozenset = frozenset(
        {
            "init_output_weights",
            "candidate_epochs",
            # Phase 6E A-2: optimizer swap takes effect at next output-training
            # pass. Mid-pass changes are not supported (cascor lifecycle uses a
            # special-cased _write_optimizer_type setter that mutates the nested
            # config; the running optimizer instance keeps its momentum).
            "optimizer_type",
            # Phase 6E A-3: activation function swap takes effect at next
            # cascade growth pass; existing cascaded units keep whatever
            # activation they were trained with. cascor's lifecycle re-runs
            # _init_activation_function on PATCH so activation_fn /
            # activation_fn_no_diff actually refresh from the registry.
            "activation_function_name",
            # FRONTEND_ISSUES_PLAN_2026-05-09 §1.5 C1b — selection-strategy
            # changes (multi-candidate flag + top/random/mixed mode) need a
            # next-iteration boundary to take effect cleanly; classifying as
            # cold avoids racing the in-flight candidate-training pass.
            "multi_candidate",
            "candidate_selection",
        }
    )

    # FRONTEND_ISSUES_PLAN_2026-05-09 §1.5 C3 — params whose verify step uses
    # math.isclose(rel_tol=1e-6) instead of equality. Float round-trips through
    # JSON / pydantic / numpy lose enough precision that exact equality is the
    # wrong test for these.
    _FLOAT_TOLERANT_PARAMS: frozenset = frozenset(
        {
            "learning_rate",
            "candidate_learning_rate",
            "correlation_threshold",
            "convergence_threshold",
            "candidate_convergence_threshold",
        }
    )

    def apply_params(self, **params: Any) -> Dict[str, Any]:
        """Forward parameter updates to the running cascor instance.

        Maps canopy's nn_*/cn_* parameter namespace to cascor API parameter names.
        Keys not in the mapping are skipped (canopy-only parameters
        such as nn_spiral_rotations have no cascor service equivalent).

        Phase C: when ``use_websocket_set_params=True``, hot params are
        routed over /ws/control via ``set_params`` command with ``command_id``
        correlation (D-01). Cold params always use REST PATCH. On WS failure,
        hot params fall back to REST unconditionally.
        """
        mapped = {self._CANOPY_TO_CASCOR_PARAM_MAP[k]: v for k, v in params.items() if k in self._CANOPY_TO_CASCOR_PARAM_MAP}
        # FRONTEND_ISSUES_PLAN_2026-05-09 §1.5 C1a (Issue #1) + #2b: surface
        # GENUINELY-unsupported keys (neither cascor-mappable nor known
        # canopy-local) so they aren't silently dropped — but exclude
        # ``_CANOPY_LOCAL_PARAMS``, which are handled canopy-side and must never
        # be reported as "skipped" in the apply toast (they were the bogus
        # "N not supported" entries). Sorted for deterministic toast + warn log.
        skipped = sorted(k for k in params if k not in self._CANOPY_TO_CASCOR_PARAM_MAP and k not in self._CANOPY_LOCAL_PARAMS)
        if skipped:
            logger.warning(
                "apply_params dropped %d unmapped key(s) — add to _CANOPY_TO_CASCOR_PARAM_MAP " "or document as canopy-only: %s",
                len(skipped),
                skipped,
            )
        if not mapped:
            return {"ok": True, "data": {}, "skipped": skipped, "message": "No cascor-mappable params provided"}

        from settings import get_settings

        app_settings = get_settings()
        use_ws = getattr(app_settings, "use_websocket_set_params", False)

        hot = {k: v for k, v in mapped.items() if k in self._HOT_CASCOR_PARAMS}
        cold = {k: v for k, v in mapped.items() if k in self._COLD_CASCOR_PARAMS}
        unclassified = {k: v for k, v in mapped.items() if k not in self._HOT_CASCOR_PARAMS and k not in self._COLD_CASCOR_PARAMS}

        if unclassified:
            logger.warning(f"Unclassified params defaulting to REST (C-09): {list(unclassified.keys())}")
            cold.update(unclassified)

        result_data: Dict[str, Any] = {}

        # Hot path: WS with REST fallback
        if hot and use_ws:
            ws_result = self._apply_params_hot(hot)
            if ws_result is not None:
                result_data.update(ws_result)
            else:
                # WS failed — fallback to REST
                logger.warning("WS set_params failed, falling back to REST for hot params")
                cold.update(hot)

        elif hot:
            # Feature flag off — hot params go through REST
            cold.update(hot)

        # Cold path: always REST
        if cold:
            try:
                rest_result = self._client.update_params(cold)
                result_data.update(rest_result if isinstance(rest_result, dict) else {})
                logger.info(f"Cascor params updated via REST: {list(cold.keys())}")
            except JuniperCascorClientError as e:
                logger.error(f"Failed to update cascor params via REST: {e}")
                return {"ok": False, "error": str(e), "skipped": skipped}

        # FRONTEND_ISSUES_PLAN_2026-05-09 §1.5 C3 — roundtrip verify. Confirm
        # the running cascor config moved to the requested values; surface any
        # divergence via ``mismatches`` so the canopy toast can route it
        # through the same machinery as ``skipped``. Failures of the verify
        # call itself are logged but never silently swallow the original
        # write — the PATCH already returned 200; if cascor's GET broke we
        # still want the user to see "applied", just without the second-line
        # confirmation.
        verify = self._verify_apply_roundtrip(mapped)
        if verify is not None:
            logger.warning("apply_params verify mismatch: %s", verify)
            return {
                "ok": False,
                "error": "verification_failed",
                "mismatches": verify,
                "skipped": skipped,
            }

        logger.info(f"Cascor params updated: {list(mapped.keys())}")
        return {"ok": True, "data": result_data, "skipped": skipped}

    def _verify_apply_roundtrip(self, mapped: Dict[str, Any]) -> Optional[Dict[str, Dict[str, Any]]]:
        """Confirm the cascor running config matches the values just PATCHed.

        Returns ``None`` on full match (or when the verify call itself fails —
        we don't want a flaky GET to invalidate a successful PATCH). Returns
        a ``{cascor_key: {requested, applied}}`` dict on real divergence.

        Float-tolerant comparison (``math.isclose(rel_tol=1e-6)``) for the
        params in ``_FLOAT_TOLERANT_PARAMS``; everything else uses ``!=``.
        """
        try:
            # juniper-cascor-client returns ``{"data": {...}}``; the inner
            # dict is the same shape ``get_canopy_params`` consumes above.
            response = self._client.get_training_params() or {}
        except JuniperCascorClientError as exc:
            logger.warning("apply_params verify call failed (continuing): %s", exc)
            return None
        applied_raw = response.get("data") if isinstance(response, dict) else None
        if not isinstance(applied_raw, dict):
            return None

        import math

        mismatches: Dict[str, Dict[str, Any]] = {}
        for key, requested in mapped.items():
            if key not in applied_raw:
                # Not all PATCH targets are echoed by GET; absence means the
                # server didn't surface it, not that it was rejected. Skip.
                continue
            applied = applied_raw[key]
            if key in self._FLOAT_TOLERANT_PARAMS:
                try:
                    if math.isclose(float(requested), float(applied), rel_tol=1e-6, abs_tol=1e-9):
                        continue
                except (TypeError, ValueError):
                    pass  # fall through to strict compare on coercion failure
            if applied != requested:
                mismatches[key] = {"requested": requested, "applied": applied}
        return mismatches or None

    # FRONTEND_ISSUES_PLAN_2026-05-09 §3.5.1 + §3.5.2 P1 — Issue #3 Phase 1
    # dataset staging. Three pass-through methods that hit the cascor PR-6
    # endpoints. juniper-cascor-client doesn't yet expose dedicated methods
    # for these (see cascor #242), so we use the public-but-private ``_request``
    # escape hatch — a follow-up will lift these into the client when it ships
    # 0.4.0+ with first-class methods.

    # Maps canopy nn_* dataset-form keys → cascor StageDatasetRequest keys.
    # Keys not in this map are silently dropped from the staging payload.
    _DATASET_PARAM_MAP = {
        "nn_dataset_type": "dataset_type",
        "nn_dataset_elements": "n_samples",
        "nn_dataset_noise": "noise",
        "nn_spiral_rotations": "rotations",
        "nn_spiral_number": "n_spirals",
    }

    def stage_dataset(self, **canopy_params: Any) -> Dict[str, Any]:
        """POST /v1/training/dataset — stage a dataset change for next start_training."""
        cascor_cfg = {self._DATASET_PARAM_MAP[k]: v for k, v in canopy_params.items() if k in self._DATASET_PARAM_MAP and v is not None}
        try:
            result = self._client._request("POST", "/training/dataset", json=cascor_cfg)
            return {"ok": True, "data": (result or {}).get("data", {}), "config": cascor_cfg}
        except JuniperCascorClientError as e:
            logger.error("stage_dataset failed: %s", e)
            return {"ok": False, "error": str(e)}

    def cancel_pending_dataset(self) -> Dict[str, Any]:
        """DELETE /v1/training/dataset — Phase 1 Cancel button target."""
        try:
            result = self._client._request("DELETE", "/training/dataset")
            return {"ok": True, "data": (result or {}).get("data", {})}
        except JuniperCascorClientError as e:
            logger.error("cancel_pending_dataset failed: %s", e)
            return {"ok": False, "error": str(e)}

    def get_pending_dataset(self) -> Dict[str, Any]:
        """GET /v1/training/dataset/pending — peek for the canopy banner."""
        try:
            result = self._client._request("GET", "/training/dataset/pending")
            return {"ok": True, "pending": ((result or {}).get("data", {}) or {}).get("pending")}
        except JuniperCascorClientError as e:
            logger.error("get_pending_dataset failed: %s", e)
            return {"ok": False, "error": str(e), "pending": None}

    # ------------------------------------------------------------------
    # Phase 2 P2-4 (Issue #3): Experimental Functions gate.
    #
    # Cascor exposes ``GET / POST /v1/admin/experimental_functions`` to
    # read/write the server-side gate that authorises ``swap_dataset_live``
    # (cascor shipped P2-1a — see ISSUE_3_PHASE_2_LIVE_DATASET_SWAP_2026-05-09
    # §3.1 / §3.3). Canopy P2-4 proxies these through its own backend so
    # the Dash callback layer keeps its single HTTP target convention
    # (Dash → canopy backend → cascor) and inherits the existing
    # X-API-Key auth boundary.
    #
    # F2.10: the server is authoritative. ``set_experimental_functions``
    # returns the gate state *after* the cascor write completed — callers
    # must trust this value rather than the requested value. On any
    # failure both methods return ``{"ok": False, "error": ...}`` and the
    # callback layer surfaces a toast + reverts the toggle.
    # ------------------------------------------------------------------

    def get_experimental_functions(self) -> Dict[str, Any]:
        """GET /v1/admin/experimental_functions — read the server gate state.

        Returns ``{"ok": True, "enabled": bool}`` on success, or
        ``{"ok": False, "error": <str>}`` on failure. A failure is treated
        as "gate is closed" by the callback layer (F2.10 safe default —
        no Live Switch button if we can't confirm cascor's state).
        """
        try:
            result = self._client._request("GET", "/admin/experimental_functions")
            data = (result or {}).get("data", {}) or {}
            return {"ok": True, "enabled": bool(data.get("enabled", False))}
        except JuniperCascorClientError as e:
            logger.error("get_experimental_functions failed: %s", e)
            return {"ok": False, "error": str(e), "enabled": False}

    def set_experimental_functions(self, enabled: bool) -> Dict[str, Any]:
        """POST /v1/admin/experimental_functions — write the server gate state.

        Returns ``{"ok": True, "enabled": <authoritative bool>}`` on
        success. The authoritative ``enabled`` may differ from the
        request if cascor's policy overrides the write (e.g., env-var
        lockdown); F2.10 makes that ambiguity a feature, not a bug.

        Returns ``{"ok": False, "error": <str>}`` on cascor failure. The
        callback layer treats this as "revert the toggle to last-known-good".
        """
        try:
            result = self._client._request("POST", "/admin/experimental_functions", json={"enabled": bool(enabled)})
            data = (result or {}).get("data", {}) or {}
            return {"ok": True, "enabled": bool(data.get("experimental_functions_enabled", data.get("enabled", enabled)))}
        except JuniperCascorClientError as e:
            logger.error("set_experimental_functions failed: %s", e)
            return {"ok": False, "error": str(e), "enabled": False}

    # ------------------------------------------------------------------
    # Phase 2 P2-5 (Issue #3): Live Dataset Switch.
    #
    # ``swap_dataset_live`` POSTs the new dataset config to cascor's
    # ``/v1/training/dataset/live`` (shipped P2-1a + P2-1d + P2-2 + P2-3).
    # Cascor performs the in-flight swap (stop → reload → resize → restart)
    # and returns the §3.3 response: ``arch_changes``, ``pre/post_swap_snapshot_id``,
    # ``mode``, etc. The HTTP request can block for 5–30s for real
    # juniper-data fetches; the canopy callback layer runs the request on
    # Dash's worker pool so the Cancel button (a separate callback) can
    # fire ``cancel_swap_dataset_live`` concurrently.
    #
    # ``cancel_swap_dataset_live`` DELETEs the live-swap endpoint (cascor
    # P2-1b). Cascor sets its internal cancel flag; the in-flight swap
    # aborts at the next checkpoint and returns ``{"status": "cancelled"}``
    # to the originating POST. A DELETE with no swap in flight gets 404
    # from cascor — surfaced here as ``{"ok": False}``.
    # ------------------------------------------------------------------

    def swap_dataset_live(self, **canopy_params: Any) -> Dict[str, Any]:
        """POST /v1/training/dataset/live — initiate an in-flight dataset swap.

        Maps canopy keys to cascor keys via ``_DATASET_PARAM_MAP`` so the
        same sidebar inputs that drive ``stage_dataset`` (cold swap) can
        drive the live swap with no UI duplication.

        Returns:
            ``{"ok": True, "data": <§3.3 response dict>}`` on success. The
            ``data`` carries ``status`` (``"swapped"`` or ``"cancelled"``),
            ``arch_changes``, ``pre_swap_snapshot_id``,
            ``post_swap_snapshot_id``, ``mode``, and the before/after configs
            — everything the canopy UI needs to render the outcome and the
            P2-7 timeline marker.

            ``{"ok": False, "error": <str>}`` on cascor failure. Distinct
            cascor status codes (403/409/422/504/502) all collapse to
            ``ok=False`` here; the callback layer can inspect the
            ``error`` string for the user-facing message.
        """
        cascor_cfg = {self._DATASET_PARAM_MAP[k]: v for k, v in canopy_params.items() if k in self._DATASET_PARAM_MAP and v is not None}
        try:
            result = self._client._request("POST", "/training/dataset/live", json=cascor_cfg)
            return {"ok": True, "data": (result or {}).get("data", {}), "config": cascor_cfg}
        except JuniperCascorClientError as e:
            logger.error("swap_dataset_live failed: %s", e)
            return {"ok": False, "error": str(e)}

    def cancel_swap_dataset_live(self) -> Dict[str, Any]:
        """DELETE /v1/training/dataset/live — cancel an in-flight live swap.

        Returns ``{"ok": True, "data": {...}}`` on cascor accepting the
        cancel signal (HTTP 200). Returns ``{"ok": False, "error": ...}``
        when cascor returns 404 (no swap in flight) or any other error —
        the callback layer treats both as "Cancel had no effect" without
        distinguishing.
        """
        try:
            result = self._client._request("DELETE", "/training/dataset/live")
            return {"ok": True, "data": (result or {}).get("data", {})}
        except JuniperCascorClientError as e:
            logger.error("cancel_swap_dataset_live failed: %s", e)
            return {"ok": False, "error": str(e)}

    # ------------------------------------------------------------------
    # Phase 2 P2-7 (Issue #3): live ``dataset_swap`` event feed.
    #
    # Cascor's follow-up B (#255) ships ``GET /v1/history/dataset_swaps``
    # which returns the LIVE network's recorded swap events
    # (``network.history["dataset_swaps"]`` — P2-2 #253 storage). Canopy
    # P2-7's three UI deliverables (replay timeline marker, History
    # paired-diff, Snapshots tab badges) all consume this list. Polled
    # every ``slow-update-interval`` tick into a single
    # ``dataset-swap-events-store`` so the three panels share state.
    #
    # The ``since`` filter lets the canopy poller pass its last-seen
    # timestamp and pull only new events on subsequent ticks — useful
    # when the list grows large.
    # ------------------------------------------------------------------

    def get_dataset_swap_events(self, since: Optional[str] = None) -> Dict[str, Any]:
        """GET /v1/history/dataset_swaps — read the dataset_swap event list.

        Returns ``{"ok": True, "events": [<event_dict>, ...]}`` on success.
        Each event has the §3.9 schema:
        ``{timestamp, before_cfg, after_cfg, arch_changes,
           pre_swap_snapshot_id, post_swap_snapshot_id}``.

        Returns ``{"ok": False, "error": <str>}`` on cascor failure. The
        callback layer treats a failure as "no events known" (empty list)
        rather than as a UI error — the three panels degrade gracefully.
        """
        params = {"since": since} if since else None
        try:
            result = self._client._request("GET", "/history/dataset_swaps", params=params)
            data = (result or {}).get("data", {}) or {}
            events = data.get("events", []) or []
            return {"ok": True, "events": list(events)}
        except JuniperCascorClientError as e:
            logger.error("get_dataset_swap_events failed: %s", e)
            return {"ok": False, "error": str(e), "events": []}

    def get_snapshot_dataset_swaps(self, snapshot_id: str) -> Dict[str, Any]:
        """GET /v1/snapshots/{id}/history/dataset_swaps — read a stored
        snapshot's own dataset_swap event list (cascor P2-7 follow-up).

        Used by the Replay timeline to render markers tied to the *loaded
        snapshot's* history (spec §4.4 full flavor), separate from the
        live event feed surfaced by :meth:`get_dataset_swap_events`.

        Returns ``{"ok": True, "events": [...]}`` on success. Events have
        the same §3.9 schema as the live feed; an empty list is a
        legitimate response (pre-P2-2 snapshot or training run with no
        live swaps).

        Returns ``{"ok": False, "error": <str>, "events": []}`` on cascor
        failure — including 404 (snapshot not present). Callers treat
        this as "no markers for this snapshot" rather than a UI error
        so the timeline degrades to the live-event-only behaviour.
        """
        try:
            result = self._client._request("GET", f"/snapshots/{snapshot_id}/history/dataset_swaps")
            data = (result or {}).get("data", {}) or {}
            events = data.get("events", []) or []
            return {"ok": True, "events": list(events)}
        except JuniperCascorClientError as e:
            logger.error("get_snapshot_dataset_swaps(%s) failed: %s", snapshot_id, e)
            return {"ok": False, "error": str(e), "events": []}

    def _apply_params_hot(self, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Send hot params via /ws/control set_params with command_id.

        Returns result dict on success, None on failure (caller falls back to REST).
        Uses ``asyncio.run_coroutine_threadsafe`` since apply_params is called
        from a thread (via asyncio.to_thread in the route handler).
        """
        supervisor = getattr(self, "_control_supervisor", None)
        if supervisor is None or not supervisor.is_connected:
            logger.debug("Control stream not connected, hot params will use REST fallback")
            return None

        from settings import get_settings

        app_settings = get_settings()
        timeout = getattr(app_settings, "ws_set_params_timeout", 1.0)

        try:
            loop = supervisor.loop
            future = asyncio.run_coroutine_threadsafe(
                supervisor.set_params(params, timeout=timeout),
                loop,
            )
            result = future.result(timeout=timeout + 1.0)  # Extra 1s for scheduling overhead
            logger.info(f"Cascor params updated via WS: {list(params.keys())}")
            return result if isinstance(result, dict) else {}
        except Exception as e:
            logger.warning(f"WS set_params failed ({type(e).__name__}: {e}), will use REST fallback")
            return None

    def get_canopy_params(self) -> Dict[str, Any]:
        """Fetch training params from cascor and map to canopy nn_*/cn_* namespace."""
        try:
            result = self._client.get_training_params()
            # Unwrap the response: try FakeCascorClient nested format first
            params = result.get("data", {}).get("params", {})
            if not params and isinstance(result.get("data"), dict):
                params = {k: v for k, v in result.get("data", {}).items() if k not in ("epochs", "dataset", "status", "meta", "timestamp")}
            # Map to canopy namespace
            canopy_params = {}
            for cascor_key, canopy_key in self._CASCOR_TO_CANOPY_PARAM_MAP.items():
                if cascor_key in params:
                    canopy_params[canopy_key] = params[cascor_key]
            return canopy_params
        except JuniperCascorClientError as e:
            logger.warning(f"Failed to fetch canopy params: {e}")
            return {}

    # ------------------------------------------------------------------
    # Response normalization
    # ------------------------------------------------------------------

    @staticmethod
    def _unwrap_response(response: Any) -> Any:
        """Unwrap cascor API success_response envelope.

        The cascor API wraps successful responses in ``{"data": ...}``.
        This helper extracts the inner payload so that adapter methods
        return consistent shapes regardless of envelope presence.
        """
        if isinstance(response, dict) and "data" in response:
            return response["data"]
        return response

    @staticmethod
    def _is_cascor_nested(data: dict) -> bool:
        """Detect whether data uses cascor's nested structure.

        Uses positive detection of nested structure (state_machine/monitor/
        training_state) rather than checking for flat keys, which could
        misfire if cascor ever adds a flat field.
        """
        return isinstance(data, dict) and ("state_machine" in data or "training_active" in data)

    @staticmethod
    def _normalize_metric(entry: dict) -> dict:
        """Normalize a single metric entry to canopy's canonical field names.

        Handles both real cascor names (loss, accuracy, validation_loss,
        validation_accuracy) and canopy names (train_loss, train_accuracy,
        val_loss, val_accuracy).  Uses ``"key" in entry`` checks instead of
        ``or`` chains so that valid 0.0 values are preserved.
        """
        train_loss = _first_defined(
            entry.get("train_loss") if "train_loss" in entry else None,
            entry.get("loss") if "loss" in entry else None,
        )
        train_accuracy = _first_defined(
            entry.get("train_accuracy") if "train_accuracy" in entry else None,
            entry.get("accuracy") if "accuracy" in entry else None,
        )
        val_loss = _first_defined(
            entry.get("val_loss") if "val_loss" in entry else None,
            entry.get("validation_loss") if "validation_loss" in entry else None,
        )
        val_accuracy = _first_defined(
            entry.get("val_accuracy") if "val_accuracy" in entry else None,
            entry.get("validation_accuracy") if "validation_accuracy" in entry else None,
        )
        hidden_units = entry.get("hidden_units", 0)
        epoch = entry.get("epoch", 0)

        return {
            # Legacy dashboard shape used by metrics panel rendering.
            "epoch": epoch,
            "metrics": {
                "loss": train_loss,
                "accuracy": train_accuracy,
                "val_loss": val_loss,
                "val_accuracy": val_accuracy,
            },
            "network_topology": {"hidden_units": hidden_units},
            # Canonical normalized names retained for API/client compatibility.
            "train_loss": train_loss,
            "train_accuracy": train_accuracy,
            "val_loss": val_loss,
            "val_accuracy": val_accuracy,
            "hidden_units": hidden_units,
            "phase": entry.get("phase"),
            "timestamp": entry.get("timestamp"),
        }

    @staticmethod
    def _to_dashboard_metric(flat: dict) -> dict:
        """Transform flat normalized metric to dashboard's nested format.

        Matches the format produced by DemoMode._emit_training_metrics().
        The dashboard (metrics_panel.py) reads metrics using nested access:
          m.get("metrics", {}).get("loss", 0)
          m.get("network_topology", {}).get("hidden_units", 0)
        """
        return {
            "epoch": flat.get("epoch", 0),
            "metrics": {
                "loss": flat.get("train_loss"),
                "accuracy": flat.get("train_accuracy"),
                "val_loss": flat.get("val_loss"),
                "val_accuracy": flat.get("val_accuracy"),
            },
            "network_topology": {
                "hidden_units": flat.get("hidden_units", 0),
            },
            "phase": flat.get("phase"),
            "timestamp": flat.get("timestamp"),
        }

    # ------------------------------------------------------------------
    # Status & metrics
    # ------------------------------------------------------------------

    def get_training_status(self) -> Dict[str, Any]:
        try:
            return self._cb.call(
                lambda: self._unwrap_response(self._client.get_training_status()),
                fallback=lambda: {"is_training": False, "error": "circuit open"},
            )
        except JuniperCascorClientError as e:
            logger.error(f"Failed to get training status: {e}")
            return {"is_training": False, "error": str(e)}

    def get_network_data(self) -> Dict[str, Any]:
        try:
            return self._cb.call(
                lambda: self._unwrap_response(self._client.get_statistics()),
                fallback=lambda: {},
            )
        except JuniperCascorClientError as e:
            logger.error(f"Failed to get network data: {e}")
            return {}

    @staticmethod
    def _is_complete_topology(raw: Any) -> bool:
        """Return True iff ``raw`` is a structurally-complete topology snapshot.

        A complete payload is one of:
        - Graph-format: a dict with ``input_units`` AND ``nodes`` already
          populated (the post-transform shape).
        - Cascor-format: a dict with ``input_size``/``output_size`` AND a
          list-shaped ``hidden_units`` (the get_topology() shape; the list may
          legitimately be empty for an untrained network).

        Returns False for count-only stubs (e.g., a pre-fix cascade_add WS
        broadcast where ``hidden_units`` was an integer count). Such payloads
        must not be passed to :meth:`_transform_topology` — the transform
        coerces ``isinstance(int, list) is False`` into ``num_hidden = 0``,
        producing a topology that drops every hidden node and every cascade
        connection.
        """
        if not isinstance(raw, dict):
            return False
        # Graph-format passthrough: must have nodes too, not just input_units.
        if "input_units" in raw and isinstance(raw.get("nodes"), list):
            return True
        # Cascor-format: hidden_units must be a list (possibly empty).
        return isinstance(raw.get("hidden_units"), list)

    @staticmethod
    def _transform_topology(raw: dict) -> dict:
        """Transform CasCor weight-oriented topology to graph-oriented format.

        CasCor returns: {input_size, output_size, hidden_units: [{weights, bias, activation}], output_weights, output_bias}
        Dashboard expects: {input_units, output_units, hidden_units: int, nodes: [...], connections: [...]}

        Cascade correlation architecture: each hidden unit connects to all inputs
        AND all prior hidden units (cascaded connections).
        """
        if "input_units" in raw:
            return raw  # Already in graph format

        input_size = raw.get("input_size", 0)
        output_size = raw.get("output_size", 0)
        hidden_units_data = raw.get("hidden_units", [])
        num_hidden = len(hidden_units_data) if isinstance(hidden_units_data, list) else 0

        nodes = []
        connections = []

        # Input nodes
        for i in range(input_size):
            nodes.append({"id": f"input_{i}", "type": "input", "layer": 0})

        # Hidden nodes with cascade connections
        for h, unit in enumerate(hidden_units_data if isinstance(hidden_units_data, list) else []):
            nodes.append({"id": f"hidden_{h}", "type": "hidden", "layer": 1})
            weights = unit.get("weights", [])
            w_idx = 0
            # Connections from inputs
            for i in range(input_size):
                if w_idx < len(weights):
                    connections.append({"from": f"input_{i}", "to": f"hidden_{h}", "weight": float(weights[w_idx])})
                    w_idx += 1
            # Cascade connections from prior hidden units
            for prior_h in range(h):
                if w_idx < len(weights):
                    connections.append({"from": f"hidden_{prior_h}", "to": f"hidden_{h}", "weight": float(weights[w_idx])})
                    w_idx += 1

        # Output nodes and connections
        # CasCor output_weights is shape (input_size + num_hidden, output_size),
        # stored row-per-input-feature. Transpose to row-per-output-neuron.
        raw_output_weights = raw.get("output_weights", [])
        if raw_output_weights and isinstance(raw_output_weights[0], list):
            n_cols = len(raw_output_weights[0])
            output_weights_t = [[raw_output_weights[r][c] for r in range(len(raw_output_weights))] for c in range(n_cols)]
        else:
            # 1D fallback (single output, already flat)
            output_weights_t = [raw_output_weights] if raw_output_weights else []

        for o in range(output_size):
            nodes.append({"id": f"output_{o}", "type": "output", "layer": 2})
            if o < len(output_weights_t):
                row = output_weights_t[o]
                w_idx = 0
                for i in range(input_size):
                    if w_idx < len(row):
                        connections.append({"from": f"input_{i}", "to": f"output_{o}", "weight": float(row[w_idx])})
                        w_idx += 1
                for h in range(num_hidden):
                    if w_idx < len(row):
                        connections.append({"from": f"hidden_{h}", "to": f"output_{o}", "weight": float(row[w_idx])})
                        w_idx += 1

        return {
            "input_units": input_size,
            "output_units": output_size,
            "hidden_units": num_hidden,
            "nodes": nodes,
            "connections": connections,
        }

    @property
    def _cb(self) -> CircuitBreaker:
        """Lazy circuit breaker accessor (safe for __new__-created instances)."""
        try:
            return self._circuit
        except AttributeError:
            self._circuit = CircuitBreaker(name=BackendConstants.CIRCUIT_BREAKER_NAME, failure_threshold=BackendConstants.CIRCUIT_BREAKER_FAILURE_THRESHOLD, recovery_timeout=BackendConstants.CIRCUIT_BREAKER_RECOVERY_TIMEOUT)
            return self._circuit

    def extract_network_topology(self) -> Optional[Dict[str, Any]]:
        try:
            raw = self._cb.call(
                lambda: self._unwrap_response(self._client.get_topology()),
                fallback=lambda: None,
            )
            if isinstance(raw, dict):
                return self._transform_topology(raw)
            result: Optional[Dict[str, Any]] = raw
            return result
        except Exception as e:
            logger.warning("Failed to extract network topology: %s: %s", type(e).__name__, e)
            return None

    def get_network_topology(self) -> Optional[Dict[str, Any]]:
        return self.extract_network_topology()

    def get_raw_topology(self) -> Optional[Dict[str, Any]]:
        """Get raw weight-oriented topology from CasCor without graph transformation."""
        try:
            raw = self._cb.call(
                lambda: self._unwrap_response(self._client.get_topology()),
                fallback=lambda: None,
            )
            if isinstance(raw, dict):
                return raw
            return None
        except Exception as e:
            logger.warning("Failed to get raw topology: %s: %s", type(e).__name__, e)
            return None

    def get_dataset_info(self, x=None, y=None) -> Optional[Dict[str, Any]]:
        try:
            result: Optional[Dict[str, Any]] = self._cb.call(
                lambda: self._unwrap_response(self._client.get_dataset()),
                fallback=lambda: None,
            )
            return result
        except Exception:
            return None

    @staticmethod
    def _coerce_scalar_target(value: Any) -> int:
        """Convert scalar target/probability value to integer class label."""
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return 0

        if numeric.is_integer():
            return int(numeric)
        if 0.0 <= numeric <= 1.0:
            return int(numeric >= 0.5)
        return int(round(numeric))

    def get_dataset_data(self) -> Optional[Dict[str, Any]]:
        """Fetch dataset arrays from CasCor for scatter plot visualization."""
        if not hasattr(self._client, "get_dataset_data"):
            logger.warning("Client does not support get_dataset_data (version mismatch?)")
            return None
        try:
            result = self._unwrap_response(self._client.get_dataset_data())
            if not result:
                return None
            inputs = result.get("train_x", [])
            targets_raw = result.get("train_y", [])
            targets = []
            if targets_raw:
                first = targets_raw[0]
                # Binary (output_size=1): threshold scalar values at 0.5 — NOT argmax.
                if isinstance(first, list):
                    if len(first) == 1:
                        targets = [self._coerce_scalar_target(row[0] if isinstance(row, list) and row else 0) for row in targets_raw]
                    else:
                        for row in targets_raw:
                            if isinstance(row, list) and row:
                                targets.append(max(range(len(row)), key=lambda i: row[i]))
                            else:
                                targets.append(0)
                else:
                    # Some services emit scalar labels directly (e.g., [0, 1, 0]).
                    targets = [self._coerce_scalar_target(value) for value in targets_raw]
            return {"inputs": inputs, "targets": targets}
        except Exception as e:
            logger.warning("Failed to fetch dataset data: %s: %s", type(e).__name__, e)
            return None

    def get_decision_boundary(self, resolution: int = 50) -> Optional[Dict[str, Any]]:
        """Fetch decision boundary from CasCor service and transform to frontend format.

        The CasCor service returns 2D meshgrid arrays (``grid_x``, ``grid_y``)
        and a 2D predictions array of integer class indices.  This method
        renames the keys to ``xx``, ``yy``, ``Z`` as expected by the
        DecisionBoundary frontend component.

        Args:
            resolution: Grid resolution per axis (5-200).

        Returns:
            Dict with xx, yy (2D meshgrids), Z (2D predictions), bounds, and resolution,
            or None if unavailable.
        """
        try:
            import numpy as np

            response = self._client.get_decision_boundary(resolution)
            data = response.get("data", {}) if isinstance(response, dict) else {}
            if not data:
                return None

            # The real CasCor API returns 2D meshgrid arrays with keys
            # grid_x / grid_y and a 2D predictions array.
            grid_x = np.array(data["grid_x"])
            grid_y = np.array(data["grid_y"])
            predictions = np.array(data["predictions"])
            res = data.get("resolution", resolution)

            x_range = data.get("x_range", [float(grid_x[0][0]), float(grid_x[0][-1])])
            y_range = data.get("y_range", [float(grid_y[0][0]), float(grid_y[-1][0])])

            return {
                "xx": grid_x.tolist(),
                "yy": grid_y.tolist(),
                "Z": predictions.tolist(),
                "x_min": x_range[0],
                "x_max": x_range[1],
                "y_min": y_range[0],
                "y_max": y_range[1],
                "resolution": res,
            }
        except Exception as e:
            logger.warning("Failed to get decision boundary: %s: %s", type(e).__name__, e)
            return None

    def get_prediction_function(self) -> Optional[Callable]:
        """Not available over REST — returns None."""
        return None

    # ------------------------------------------------------------------
    # Snapshot REST delegation
    # ------------------------------------------------------------------

    def save_snapshot(self, path: str, description: str = "") -> None:
        """Save current network state via CasCor /v1/snapshots endpoint.

        Args:
            path: Local path hint (ignored — CasCor manages storage server-side).
            description: Optional description for the snapshot.
        """
        try:
            self._client.save_snapshot(description=description)
            logger.info("Snapshot saved via CasCor service (description=%r)", description)
        except JuniperCascorClientError as e:
            logger.error("Failed to save snapshot: %s", e)
            raise

    def load_snapshot(self, path: str) -> None:
        """Restore network state via CasCor /v1/snapshots/{id}/restore endpoint.

        Args:
            path: Snapshot path or ID. The file stem is used as the snapshot ID.
        """
        from pathlib import Path as _Path

        snapshot_id = _Path(path).stem
        try:
            self._client.load_snapshot(snapshot_id)
            logger.info("Snapshot restored via CasCor service (id=%s)", snapshot_id)
        except JuniperCascorClientError as e:
            logger.error("Failed to load snapshot %s: %s", snapshot_id, e)
            raise

    # ──────────────────────────────────────────────────────────────────
    # CAN-015 (Phase 6E Sprint B) snapshot operation endpoints
    # ──────────────────────────────────────────────────────────────────
    # Restore (above) is the original snapshot operation. B-1..B-4 added
    # three more semantically-distinct operations on the cascor side:
    # ``replay`` (read-only playback), ``resume`` (continue training),
    # and ``retrain`` (fresh training using snapshot weights). The
    # cascor client wrapper hasn't been extended for these yet — when
    # it is (cross-repo follow-up tracked separately), these adapter
    # methods can switch to the typed wrappers. Until then we drive
    # the underlying ``_post`` directly, which is what
    # ``client.load_snapshot`` does internally anyway.

    def replay_snapshot(self, snapshot_id: str) -> Dict[str, Any]:
        """Start a read-only replay session via /v1/snapshots/{id}/replay.

        Returns the unified response payload from cascor including the
        ``operation``, ``fsm_state``, ``time_index``, and a ``session``
        block describing the playback state. The caller (canopy
        backend route) forwards this to the frontend so canopy can
        wire the replay player UI to the returned ``length`` and
        initial ``time_index``.

        Raises ``JuniperCascorClientError`` on HTTP failure.
        """
        try:
            data = self._client._post(f"/snapshots/{snapshot_id}/replay")
            logger.info("Snapshot replay started via CasCor service (id=%s)", snapshot_id)
            return cast(Dict[str, Any], data)
        except JuniperCascorClientError as e:
            logger.error("Failed to start replay for %s: %s", snapshot_id, e)
            raise

    def replay_control(self, snapshot_id: str, action: str, **params: Any) -> Dict[str, Any]:
        """Send a playback control command to /v1/snapshots/{id}/replay/control.

        ``action`` is one of ``play`` / ``pause`` / ``seek`` / ``speed``
        / ``range`` / ``stop``. Per-action parameters (``time_index``
        for seek, ``value`` for speed, ``start`` and ``end`` for range)
        are passed through unchanged via ``**params``.
        """
        body: Dict[str, Any] = {"action": action}
        body.update({k: v for k, v in params.items() if v is not None})
        try:
            data = self._client._post(f"/snapshots/{snapshot_id}/replay/control", json=body)
            logger.info("Snapshot replay control via CasCor service (id=%s, action=%s)", snapshot_id, action)
            return cast(Dict[str, Any], data)
        except JuniperCascorClientError as e:
            logger.error("Failed replay control for %s (action=%s): %s", snapshot_id, action, e)
            raise

    def resume_snapshot(self, snapshot_id: str) -> Dict[str, Any]:
        """Continue training from a snapshot via /v1/snapshots/{id}/resume.

        Returns the unified response payload including
        ``resume_point_epoch`` so canopy can render the visual boundary
        in the metrics-curve component.
        """
        try:
            data = self._client._post(f"/snapshots/{snapshot_id}/resume")
            logger.info("Snapshot resume started via CasCor service (id=%s)", snapshot_id)
            return cast(Dict[str, Any], data)
        except JuniperCascorClientError as e:
            logger.error("Failed to resume snapshot %s: %s", snapshot_id, e)
            raise

    def retrain_snapshot(self, snapshot_id: str) -> Dict[str, Any]:
        """Reset training history and prepare a fresh run via /v1/snapshots/{id}/retrain."""
        try:
            data = self._client._post(f"/snapshots/{snapshot_id}/retrain")
            logger.info("Snapshot retrain started via CasCor service (id=%s)", snapshot_id)
            return cast(Dict[str, Any], data)
        except JuniperCascorClientError as e:
            logger.error("Failed to retrain snapshot %s: %s", snapshot_id, e)
            raise

    # ------------------------------------------------------------------
    # CAN-015h: network mutation endpoints (h-1 / h-2 / h-3)
    # ------------------------------------------------------------------
    # All three are FSM-gated to ``Investigating`` on the cascor side
    # — the service returns 409 from any other state. The adapter is
    # transport-only: validation and shape checks live in the cascor
    # lifecycle, surfaced as JuniperCascorClientError → re-raise so
    # canopy callers can map to UI feedback. Demo mode handling
    # follows the B-5 pattern: the canopy backend route layer
    # short-circuits to 501 before reaching the adapter.

    def patch_weights(
        self,
        target: str,
        field: str,
        values: Any,
        hidden_unit_index: Optional[int] = None,
        dtype: str = "float32",
    ) -> Dict[str, Any]:
        """CAN-015h-1: surgical weight rewrite via PATCH /v1/network/weights.

        ``target`` ∈ {"output", "hidden_unit"}, ``field`` ∈ {"weights", "bias"}.
        ``hidden_unit_index`` is required iff ``target == "hidden_unit"``.
        Mirrors the Pydantic model on the cascor side; the body is
        passed through as-is so the cascor route's exact-shape /
        NaN-Inf / FSM-gate validation runs unchanged.
        """
        body: Dict[str, Any] = {
            "target": target,
            "field": field,
            "values": values,
            "dtype": dtype,
        }
        if hidden_unit_index is not None:
            body["hidden_unit_index"] = hidden_unit_index
        try:
            data = self._client._patch("/network/weights", json=body)
            logger.info("Weights patched via CasCor service (target=%s, field=%s)", target, field)
            return cast(Dict[str, Any], data)
        except JuniperCascorClientError as e:
            logger.error("patch_weights failed (target=%s, field=%s): %s", target, field, e)
            raise

    def add_hidden_unit(
        self,
        weights: Any,
        bias: float = 0.0,
        activation: str = "Tanh",
    ) -> Dict[str, Any]:
        """CAN-015h-2: append a hidden unit at the cascade tail.

        V1 is tail-only — the cascor route's Pydantic body forces
        ``position="tail"``. New unit's output column is initialized
        to zero by the cascor side regardless of the network's
        ``init_output_weights`` config.
        """
        body: Dict[str, Any] = {
            "weights": weights,
            "bias": bias,
            "activation": activation,
            "position": "tail",
        }
        try:
            data = self._client._post("/network/hidden-units", json=body)
            logger.info("Hidden unit appended via CasCor service (activation=%s)", activation)
            return cast(Dict[str, Any], data)
        except JuniperCascorClientError as e:
            logger.error("add_hidden_unit failed: %s", e)
            raise

    def remove_hidden_unit(self, idx: int) -> Dict[str, Any]:
        """CAN-015h-3: remove the hidden unit at ``idx`` with cascade rebuild.

        Cascade-rebuild semantics live in cascor's lifecycle —
        subsequent units' weights at the deleted column are dropped
        so the forward-pass shape invariant holds. The adapter is
        purely transport.
        """
        try:
            data = self._client._delete(f"/network/hidden-units/{idx}")
            logger.info("Hidden unit removed via CasCor service (idx=%d)", idx)
            return cast(Dict[str, Any], data)
        except JuniperCascorClientError as e:
            logger.error("remove_hidden_unit(idx=%d) failed: %s", idx, e)
            raise

    # ------------------------------------------------------------------
    # Monitoring no-ops (hooks are in-process CascorIntegration only)
    # ------------------------------------------------------------------

    def install_monitoring_hooks(self) -> bool:
        return True

    def start_monitoring_thread(self, interval: float = 1.0) -> None:
        pass

    def stop_monitoring(self) -> None:
        pass

    def restore_original_methods(self) -> None:
        pass

    def create_monitoring_callback(self, event_type: str, callback: Callable) -> None:
        pass

    # ------------------------------------------------------------------
    # Remote worker no-ops (workers managed by the CasCor service)
    # ------------------------------------------------------------------

    def get_remote_worker_status(self) -> Dict[str, Any]:
        return {"available": False, "connected": False, "workers_active": False, "error": "Managed by CasCor service"}

    def connect_remote_workers(self, address: Tuple[str, int], authkey: Union[str, bytes]) -> bool:
        return False

    def start_remote_workers(self, num_workers: int = 1) -> bool:
        return False

    def stop_remote_workers(self, timeout: int = 10) -> bool:
        return False

    def disconnect_remote_workers(self) -> bool:
        return False

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def shutdown(self) -> None:
        """Close the HTTP session. Does NOT stop training on the cascor service."""
        logger.info("CascorServiceAdapter shutting down — cascor continues running")
        try:
            self._client.close()
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
