#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       BackendProtocol adapter wrapping CascorServiceAdapter for real CasCor service communication
#
# Author:        Paul Calnon
# Version:       0.1.0
# File Name:     service_backend.py
# File Path:     JuniperCanopy/juniper_canopy/src/backend/
#
# Date Created:  2026-02-26
# Last Modified: 2026-02-26
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#     ServiceBackend wraps the existing CascorServiceAdapter, adapting its interface
#     to BackendProtocol. Handles async lifecycle (connect, metrics relay) and
#     delegates all training operations to the CasCor service over REST/WebSocket.
#
#####################################################################################################################################################################################################
# Notes:
#     Phase 5 of the Microservices Architecture Development Roadmap.
#     Operations not yet supported by the CasCor service (pause, resume, reset,
#     apply_params) return {"ok": False, "error": "..."} rather than raising.
#
#####################################################################################################################################################################################################
# References:
#     - juniper-ml/notes/MICROSERVICES-ARCHITECTURE_DEVELOPMENT-ROADMAP.md §5.6
#
#####################################################################################################################################################################################################
# TODO :
#
#####################################################################################################################################################################################################
# COMPLETED:
#
#####################################################################################################################################################################################################

import logging
from typing import Any, Dict, List, Optional

from backend.cascor_service_adapter import CascorServiceAdapter

logger = logging.getLogger("juniper_canopy.backend.service_backend")


class ServiceBackend:
    """BackendProtocol implementation wrapping CascorServiceAdapter."""

    def __init__(self, adapter: CascorServiceAdapter):
        self._adapter = adapter

    @property
    def backend_type(self) -> str:
        return "service"

    # --- Training control ---

    def start_training(self, reset: bool = True, **kwargs: Any) -> Dict[str, Any]:
        if self._adapter.network is None:
            return {"ok": False, "error": "No network created"}
        if self._adapter.is_training_in_progress():
            return {"ok": False, "error": "Training already in progress"}
        success = self._adapter.start_training_background(**kwargs)
        return {"ok": success, "is_training": success}

    def stop_training(self) -> Dict[str, Any]:
        success = self._adapter.request_training_stop()
        return {"ok": success}

    def pause_training(self) -> Dict[str, Any]:
        return {"ok": False, "error": "Pause not yet supported in service mode"}

    def resume_training(self) -> Dict[str, Any]:
        return {"ok": False, "error": "Resume not yet supported in service mode"}

    def reset_training(self) -> Dict[str, Any]:
        return {"ok": False, "error": "Reset not yet supported in service mode"}

    def is_training_active(self) -> bool:
        return self._adapter.is_training_in_progress()

    # --- Status and metrics ---

    def get_status(self) -> Dict[str, Any]:
        return self._adapter.get_training_status()

    def get_metrics(self) -> Dict[str, Any]:
        return self._adapter.training_monitor.get_current_metrics()

    def get_metrics_history(self, count: int = 100) -> List[Dict[str, Any]]:
        return self._adapter.training_monitor.get_recent_metrics(count)

    # --- Network and data ---

    def has_network(self) -> bool:
        return self._adapter.network is not None

    def get_network_topology(self) -> Optional[Dict[str, Any]]:
        return self._adapter.extract_network_topology()

    def get_network_stats(self) -> Dict[str, Any]:
        return self._adapter.get_network_data()

    def get_dataset(self) -> Optional[Dict[str, Any]]:
        return self._adapter.get_dataset_info()

    def get_decision_boundary(self, resolution: int = 50) -> Optional[Dict[str, Any]]:
        # Decision boundary computation requires in-process network access.
        # Not available over REST — returns None.
        return None

    # --- Parameters ---

    def apply_params(self, **params: Any) -> Dict[str, Any]:
        return {"ok": False, "error": "Parameter changes not yet supported in service mode"}

    # --- Lifecycle ---

    async def initialize(self) -> bool:
        connected = await self._adapter.connect()
        if connected:
            await self._adapter.start_metrics_relay()
            logger.info(f"ServiceBackend connected to {self._adapter._service_url}")
        else:
            logger.error(f"ServiceBackend failed to connect to {self._adapter._service_url}")
        return connected

    async def shutdown(self) -> None:
        await self._adapter.stop_metrics_relay()
        self._adapter.shutdown()
        logger.info("ServiceBackend shut down")
