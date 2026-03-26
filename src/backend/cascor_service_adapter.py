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
import logging
from typing import Any, Callable, Dict, Optional, Tuple, Union

from juniper_cascor_client import CascorTrainingStream, JuniperCascorClient
from juniper_cascor_client.exceptions import JuniperCascorClientError

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
            # Check top-level first (FakeCascorClient), with explicit None guard
            # so that is_training=False doesn't fall through
            is_training_top = status.get("is_training")
            if is_training_top is not None:
                return is_training_top
            # Unwrap envelope and check nested (real server)
            data = status.get("data", {})
            if isinstance(data, dict):
                return data.get("training_active", False)
            return False
        except JuniperCascorClientError:
            return False

    def get_current_metrics(self) -> Dict[str, Any]:
        try:
            result = self._client.get_metrics()
            if isinstance(result, dict) and "data" in result:
                data = result["data"]
                return CascorServiceAdapter._normalize_metric(data) if isinstance(data, dict) else result
            return result if isinstance(result, dict) else {}
        except JuniperCascorClientError:
            return {}

    def get_recent_metrics(self, count: int = 100) -> list:
        try:
            result = self._client.get_metrics_history(count=count)
            if isinstance(result, dict):
                data = result.get("data", result)
                if isinstance(data, list):
                    return [CascorServiceAdapter._normalize_metric(m) for m in data]
                if isinstance(data, dict):
                    history = data.get("history", [])
                    return [CascorServiceAdapter._normalize_metric(m) for m in history]
            return result if isinstance(result, list) else []
        except JuniperCascorClientError:
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
            return self._client.is_alive()
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
                                self._state_update_callback(status=status, phase=data.get("phase", ""))
                            except Exception as se:  # nosec B110
                                logger.debug(f"State update callback error: {se}")

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
            try:
                await self._relay_task
            except asyncio.CancelledError:
                pass
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
        except JuniperCascorClientError:
            pass
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
            return self._client.create_network(**(config or {}))
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
                return is_training_top
            data = status.get("data", {})
            if isinstance(data, dict):
                return data.get("training_active", False)
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
        "cn_training_iterations": "candidate_epochs",
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
                # Real server: params are flat fields in data, filter non-param keys
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
        """Detect whether the data dict uses cascor's nested structure
        (state_machine/monitor/training_state) vs the flat demo format.

        Uses positive detection of nested structure rather than checking
        for flat keys, which could misfire if cascor ever adds a flat field.
        """
        return "state_machine" in data or "training_active" in data

    @staticmethod
    def _normalize_metric(entry: dict) -> dict:
        """Normalize a single metric entry to canopy's canonical field names.

        Handles both real cascor names (loss, accuracy, validation_loss,
        validation_accuracy) and canopy names (train_loss, train_accuracy,
        val_loss, val_accuracy). Uses _first_defined to preserve 0.0 values.
        """
        return {
            "epoch": entry.get("epoch", 0),
            "train_loss": _first_defined(
                entry.get("train_loss") if "train_loss" in entry else None,
                entry.get("loss") if "loss" in entry else None,
            ),
            "train_accuracy": _first_defined(
                entry.get("train_accuracy") if "train_accuracy" in entry else None,
                entry.get("accuracy") if "accuracy" in entry else None,
            ),
            "val_loss": _first_defined(
                entry.get("val_loss") if "val_loss" in entry else None,
                entry.get("validation_loss") if "validation_loss" in entry else None,
            ),
            "val_accuracy": _first_defined(
                entry.get("val_accuracy") if "val_accuracy" in entry else None,
                entry.get("validation_accuracy") if "validation_accuracy" in entry else None,
            ),
            "hidden_units": entry.get("hidden_units", 0),
            "phase": entry.get("phase"),
            "timestamp": entry.get("timestamp"),
        }

    # ------------------------------------------------------------------
    # Status & metrics
    # ------------------------------------------------------------------

    def get_training_status(self) -> Dict[str, Any]:
        try:
            return self._unwrap_response(self._client.get_training_status())
        except JuniperCascorClientError as e:
            logger.error(f"Failed to get training status: {e}")
            return {"is_training": False, "error": str(e)}

    def get_network_data(self) -> Dict[str, Any]:
        try:
            return self._unwrap_response(self._client.get_statistics())
        except JuniperCascorClientError as e:
            logger.error(f"Failed to get network data: {e}")
            return {}

    def extract_network_topology(self) -> Optional[Dict[str, Any]]:
        try:
            data = self._unwrap_response(self._client.get_topology())
            if not isinstance(data, dict):
                return data
            # Already in canopy format (has input_units key)
            if "input_units" in data:
                return data
            # Cascor format: input_size/output_size, hidden_units as list of dicts
            if "input_size" in data:
                n_input = data.get("input_size", 0)
                n_output = data.get("output_size", 0)
                hidden_list = data.get("hidden_units", [])
                n_hidden = len(hidden_list) if isinstance(hidden_list, list) else 0
                # Build nodes and connections from cascor weight-oriented format
                nodes = []
                connections = []
                for i in range(n_input):
                    nodes.append({"id": f"input_{i}", "type": "input", "label": f"I{i}"})
                for h_idx, hu in enumerate(hidden_list if isinstance(hidden_list, list) else []):
                    nodes.append({"id": f"hidden_{h_idx}", "type": "hidden", "label": f"H{h_idx}"})
                    # Connections from inputs and prior hidden units to this hidden unit
                    conn_indices = hu.get("connections", []) if isinstance(hu, dict) else []
                    for src_idx in conn_indices:
                        src_id = f"input_{src_idx}" if src_idx < n_input else f"hidden_{src_idx - n_input}"
                        connections.append({"from": src_id, "to": f"hidden_{h_idx}", "weight": 0.0})
                for i in range(n_output):
                    nodes.append({"id": f"output_{i}", "type": "output", "label": f"O{i}"})
                    # Output weights from all inputs + hidden to this output
                    output_weights = data.get("output_weights", [])
                    if isinstance(output_weights, list):
                        for h_idx in range(n_hidden):
                            w = output_weights[h_idx][i] if h_idx < len(output_weights) and i < len(output_weights[h_idx]) else 0.0
                            connections.append({"from": f"hidden_{h_idx}", "to": f"output_{i}", "weight": w})
                return {
                    "nodes": nodes,
                    "connections": connections,
                    "input_units": n_input,
                    "output_units": n_output,
                    "hidden_units": n_hidden,
                }
            return data
        except JuniperCascorClientError:
            return None

    def get_network_topology(self) -> Optional[Dict[str, Any]]:
        return self.extract_network_topology()

    def get_dataset_info(self, x=None, y=None) -> Optional[Dict[str, Any]]:
        try:
            return self._unwrap_response(self._client.get_dataset())
        except JuniperCascorClientError:
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
