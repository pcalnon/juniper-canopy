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
import logging
from typing import Any, Callable, Dict, Optional, Tuple, Union

from juniper_cascor_client import CascorTrainingStream, JuniperCascorClient, JuniperCascorClientError

from backend.circuit_breaker import CircuitBreaker

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
        service_url: str = "http://localhost:8200",
        api_key: Optional[str] = None,
        client: Optional[JuniperCascorClient] = None,
    ):
        self._service_url = service_url
        self._api_key = api_key
        self._client = client or JuniperCascorClient(base_url=service_url, api_key=api_key)
        self.training_monitor = _ServiceTrainingMonitor(self._client)
        self._training_stream: Optional[CascorTrainingStream] = None
        self._relay_task: Optional[asyncio.Task] = None
        self._attached_to_existing: bool = False
        self._state_update_callback: Optional[Callable] = None
        self._circuit = CircuitBreaker(name="cascor", failure_threshold=5, recovery_timeout=60.0)

        # Derive WebSocket URL from HTTP URL
        ws_url = service_url.replace("http://", "ws://").replace("https://", "wss://")
        self._ws_url = ws_url

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
            from communication.websocket_manager import websocket_manager

            backoff = [1, 2, 5, 10, 30]
            attempt = 0
            relay_enabled = True
            while relay_enabled:
                try:
                    stream = CascorTrainingStream(base_url=self._ws_url, api_key=self._api_key)
                    await stream.connect()
                    attempt = 0
                    async for message in stream.stream():
                        msg_type = message.get("type", "")
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
                                # Map top candidate identity from CasCor state
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
                except Exception as e:
                    delay = backoff[min(attempt, len(backoff) - 1)]
                    logger.warning(f"Cascor metrics stream disconnected ({e}). Reconnecting in {delay}s")
                    attempt += 1
                    try:
                        await asyncio.sleep(delay)
                    except asyncio.CancelledError:
                        relay_enabled = False

        self._relay_task = asyncio.create_task(_relay_loop())
        logger.info("Metrics relay started")

    async def stop_metrics_relay(self) -> None:
        """Cancel the WebSocket relay task."""
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
        """Return a truthy sentinel if the service has a network, else None."""
        try:
            result = self._client.get_network()
            if result and not result.get("error"):
                return _NetworkSentinel()
        except Exception as e:
            logger.debug("Failed to query network: %s", e)
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

    def start_training_background(self, *args, **kwargs) -> bool:
        try:
            self._client.start_training(**kwargs)
            return True
        except JuniperCascorClientError as e:
            logger.error(f"Failed to start training: {e}")
            return False

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
        "nn_growth_convergence_threshold": "patience",
        "cn_pool_size": "candidate_pool_size",
        "cn_correlation_threshold": "correlation_threshold",
        "cn_candidate_learning_rate": "candidate_learning_rate",
    }

    _CASCOR_TO_CANOPY_PARAM_MAP = {v: k for k, v in _CANOPY_TO_CASCOR_PARAM_MAP.items()}

    def apply_params(self, **params: Any) -> Dict[str, Any]:
        """Forward parameter updates to the running cascor instance.

        Maps canopy's nn_*/cn_* parameter namespace to cascor API parameter names.
        Keys not in the mapping are silently skipped (canopy-only parameters
        such as nn_spiral_rotations have no cascor service equivalent).
        """
        mapped = {self._CANOPY_TO_CASCOR_PARAM_MAP[k]: v for k, v in params.items() if k in self._CANOPY_TO_CASCOR_PARAM_MAP}
        if not mapped:
            return {"ok": True, "data": {}, "message": "No cascor-mappable params provided"}
        try:
            result = self._client.update_params(mapped)
            return {"ok": True, "data": result}
        except JuniperCascorClientError as e:
            logger.error(f"Failed to update cascor params: {e}")
            return {"ok": False, "error": str(e)}

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
            self._circuit = CircuitBreaker(name="cascor", failure_threshold=5, recovery_timeout=60.0)
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
        except JuniperCascorClientError as e:
            logger.warning(f"Failed to get decision boundary: {e}")
            return None
        except (KeyError, ValueError, IndexError) as e:
            logger.warning(f"Failed to transform decision boundary data: {e}")
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
