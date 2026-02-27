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
            return status.get("is_training", False)
        except JuniperCascorClientError:
            return False

    def get_current_metrics(self) -> Dict[str, Any]:
        try:
            return self._client.get_metrics()
        except JuniperCascorClientError:
            return {}

    def get_recent_metrics(self, count: int = 100) -> list:
        try:
            result = self._client.get_metrics_history(count=count)
            return result.get("history", []) if isinstance(result, dict) else result
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

        # Derive WebSocket URL from HTTP URL
        ws_url = service_url.replace("http://", "ws://").replace("https://", "wss://")
        self._ws_url = ws_url

    # ------------------------------------------------------------------
    # Connection lifecycle (async)
    # ------------------------------------------------------------------

    async def connect(self) -> bool:
        """Connect to the CasCor service and verify it is ready."""
        try:
            return self._client.is_ready()
        except JuniperCascorClientError:
            logger.error(f"Failed to connect to CasCor service at {self._service_url}")
            return False

    async def start_metrics_relay(self) -> None:
        """
        Open a WebSocket training stream and relay messages to Canopy's
        websocket_manager for broadcast to dashboard clients.
        """
        from communication.websocket_manager import websocket_manager

        self._training_stream = CascorTrainingStream(base_url=self._ws_url, api_key=self._api_key)

        async def _relay_loop():
            try:
                await self._training_stream.connect()
                async for message in self._training_stream.stream():
                    msg_type = message.get("type", "")
                    data = message.get("data", message)
                    await websocket_manager.broadcast({"type": msg_type, "data": data})
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"Metrics relay error: {e}")
            finally:
                await self._training_stream.disconnect()

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
            return status.get("is_training", False)
        except JuniperCascorClientError:
            return False

    def request_training_stop(self) -> bool:
        try:
            self._client.stop_training()
            return True
        except JuniperCascorClientError as e:
            logger.error(f"Failed to stop training: {e}")
            return False

    # ------------------------------------------------------------------
    # Status & metrics
    # ------------------------------------------------------------------

    def get_training_status(self) -> Dict[str, Any]:
        try:
            return self._client.get_training_status()
        except JuniperCascorClientError as e:
            logger.error(f"Failed to get training status: {e}")
            return {"is_training": False, "error": str(e)}

    def get_network_data(self) -> Dict[str, Any]:
        try:
            return self._client.get_statistics()
        except JuniperCascorClientError as e:
            logger.error(f"Failed to get network data: {e}")
            return {}

    def extract_network_topology(self) -> Optional[Dict[str, Any]]:
        try:
            return self._client.get_topology()
        except JuniperCascorClientError:
            return None

    def get_network_topology(self) -> Optional[Dict[str, Any]]:
        return self.extract_network_topology()

    def get_dataset_info(self, x=None, y=None) -> Optional[Dict[str, Any]]:
        try:
            return self._client.get_dataset()
        except JuniperCascorClientError:
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
        try:
            self._client.close()
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
