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
#     Training control operations (pause, resume, reset) and apply_params
#     delegate to CascorServiceAdapter, which forwards to the CasCor service.
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
from typing import Any, Callable, Dict, List, Optional

from backend.cascor_service_adapter import CascorServiceAdapter
from backend.state_sync import CascorStateSync, SyncedState

logger = logging.getLogger("juniper_canopy.backend.service_backend")


class ServiceBackend:
    """BackendProtocol implementation wrapping CascorServiceAdapter."""

    def __init__(self, adapter: CascorServiceAdapter):
        self._adapter = adapter
        self._synced_state: Optional[SyncedState] = None
        self._state_update_callback: Optional[Callable] = None

    def set_state_update_callback(self, callback: Callable) -> None:
        """Register a callback invoked when cascor broadcasts state changes.

        The callback receives keyword arguments (status, phase, etc.) and is
        expected to update the application-level TrainingState.
        """
        self._state_update_callback = callback
        self._adapter.set_state_update_callback(callback)

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
        return self._adapter.pause_training()

    def resume_training(self) -> Dict[str, Any]:
        return self._adapter.resume_training()

    def reset_training(self) -> Dict[str, Any]:
        return self._adapter.reset_training()

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
        return self._adapter.get_decision_boundary(resolution)

    # --- Parameters ---

    def apply_params(self, **params: Any) -> Dict[str, Any]:
        return self._adapter.apply_params(**params)

    # --- Lifecycle ---

    async def initialize(self) -> bool:
        """Connect to cascor service, attach non-destructively, sync state, and start metrics relay."""
        connected = await self._adapter.connect()
        if connected:
            # Non-destructive attach: check for existing network without creating/resetting
            has_network = self._adapter.attach_to_existing()
            if has_network:
                logger.info("ServiceBackend: attached to existing cascor network")
                # Sync current cascor state into canopy
                self._synced_state = CascorStateSync(self._adapter._client).sync()
                logger.info(f"ServiceBackend: state synced — status={self._synced_state.status}, epoch={self._synced_state.current_epoch}, params={len(self._synced_state.params)} keys")
            else:
                logger.info("ServiceBackend: no existing cascor network found (will create on start)")
            await self._adapter.start_metrics_relay()
            logger.info(f"ServiceBackend connected to {self._adapter._service_url}")
        else:
            logger.error(f"ServiceBackend failed to connect to {self._adapter._service_url}")
        return connected

    def get_synced_state(self) -> Optional[SyncedState]:
        """Return the state snapshot from the most recent sync, or None."""
        return self._synced_state

    async def shutdown(self) -> None:
        """Disconnect from cascor gracefully. Does NOT stop training on cascor."""
        await self._adapter.stop_metrics_relay()
        self._adapter.shutdown()
        logger.info("ServiceBackend disconnected — cascor continues running independently")
