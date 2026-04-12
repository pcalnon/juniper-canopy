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
from typing import Any, Callable, List, Optional, cast

from backend.cascor_service_adapter import CascorServiceAdapter, _first_defined
from backend.protocol import (
    ApplyParamsResult,
    ControlResult,
    DatasetResult,
    DecisionBoundaryResult,
    MetricsResult,
    NetworkStatsResult,
    RawTopologyResult,
    StatusResult,
    TopologyResult,
)
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

    def start_training(self, reset: bool = True, **kwargs: Any) -> ControlResult:
        if self._adapter.network is None:
            return ControlResult(ok=False, error="No network created")
        if self._adapter.is_training_in_progress():
            return ControlResult(ok=False, error="Training already in progress")
        success = self._adapter.start_training_background(**kwargs)
        return ControlResult(ok=success, is_training=success)

    def stop_training(self) -> ControlResult:
        success = self._adapter.request_training_stop()
        return ControlResult(ok=success)

    def pause_training(self) -> ControlResult:
        return cast(ControlResult, self._adapter.pause_training())

    def resume_training(self) -> ControlResult:
        return cast(ControlResult, self._adapter.resume_training())

    def reset_training(self) -> ControlResult:
        return cast(ControlResult, self._adapter.reset_training())

    def is_training_active(self) -> bool:
        return self._adapter.is_training_in_progress()

    # --- Status and metrics ---

    def get_status(self) -> StatusResult:
        raw = self._adapter.get_training_status()
        if not isinstance(raw, dict) or not CascorServiceAdapter.is_cascor_nested(raw):
            return cast(StatusResult, raw)
        sm = raw.get("state_machine", {}) if isinstance(raw.get("state_machine"), dict) else {}
        monitor = raw.get("monitor", {}) if isinstance(raw.get("monitor"), dict) else {}
        ts = raw.get("training_state", {}) if isinstance(raw.get("training_state"), dict) else {}
        fsm_status = sm.get("status", sm.get("current_state", "Stopped"))
        status_upper = fsm_status.upper() if isinstance(fsm_status, str) else "STOPPED"
        phase_raw = sm.get("phase") or ts.get("phase", "idle")
        return cast(
            StatusResult,
            {
                "is_training": raw.get("training_active", False),
                "is_running": status_upper in ("STARTED", "RUNNING", "TRAINING"),
                "is_paused": status_upper == "PAUSED",
                "completed": status_upper in ("COMPLETED", "CONVERGED"),
                "failed": status_upper == "FAILED",
                "fsm_status": fsm_status,
                "phase": phase_raw.lower() if isinstance(phase_raw, str) else "idle",
                "current_epoch": _first_defined(
                    monitor.get("current_epoch"),
                    monitor.get("epoch"),
                    ts.get("current_epoch"),
                    default=0,
                ),
                "hidden_units": _first_defined(
                    monitor.get("current_hidden_units"),
                    monitor.get("hidden_units"),
                    default=0,
                ),
                "network_connected": raw.get("network_loaded", False),
                "monitoring_active": status_upper in ("STARTED", "RUNNING", "TRAINING"),
                "input_size": ts.get("input_size", 0),
                "output_size": ts.get("output_size", 0),
                "learning_rate": ts.get("learning_rate", 0.0),
                "max_hidden_units": ts.get("max_hidden_units", 0),
                "max_epochs": ts.get("max_epochs", 0),
            },
        )

    def get_metrics(self) -> MetricsResult:
        return cast(MetricsResult, self._adapter.training_monitor.get_current_metrics())

    def get_metrics_history(self, count: int = 100) -> List[MetricsResult]:
        return self._adapter.training_monitor.get_recent_metrics(count)

    # --- Network and data ---

    def has_network(self) -> bool:
        return self._adapter.network is not None

    def get_network_topology(self) -> Optional[TopologyResult]:
        result = cast(Optional[TopologyResult], self._adapter.extract_network_topology())
        # OI-5: Fall back to synced topology if live fetch fails (e.g. during startup)
        if result is None and self._synced_state and self._synced_state.topology:
            return cast(TopologyResult, self._synced_state.topology)
        return result

    def get_raw_topology(self) -> Optional[RawTopologyResult]:
        return cast(Optional[RawTopologyResult], self._adapter.get_raw_topology())

    def get_network_stats(self) -> NetworkStatsResult:
        return cast(NetworkStatsResult, self._adapter.get_network_data())

    def get_dataset(self) -> Optional[DatasetResult]:
        raw = self._adapter.get_dataset_info()
        if not raw:
            return None
        if "train_samples" in raw or "input_features" in raw:
            result = {
                "num_samples": raw.get("train_samples", 0) + raw.get("test_samples", 0),
                "num_features": raw.get("input_features", 0),
                "num_classes": raw.get("output_features", 0),
                "loaded": raw.get("loaded", True),
                "train_samples": raw.get("train_samples", 0),
                "test_samples": raw.get("test_samples", 0),
            }
            if "inputs" in raw:
                result["inputs"] = raw["inputs"]
            if "targets" in raw:
                result["targets"] = raw["targets"]
            # Fetch actual arrays if metadata-only
            if "inputs" not in result:
                data = self._adapter.get_dataset_data()
                if data:
                    result["inputs"] = data["inputs"]
                    result["targets"] = data["targets"]
            return cast(DatasetResult, result)
        return cast(DatasetResult, raw)

    def get_decision_boundary(self, resolution: int = 50) -> Optional[DecisionBoundaryResult]:
        return cast(Optional[DecisionBoundaryResult], self._adapter.get_decision_boundary(resolution))

    # --- Parameters ---

    def apply_params(self, **params: Any) -> ApplyParamsResult:
        return cast(ApplyParamsResult, self._adapter.apply_params(**params))

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
                self._synced_state = CascorStateSync(self._adapter.client).sync()
                logger.info(f"ServiceBackend: state synced — status={self._synced_state.status}, epoch={self._synced_state.current_epoch}, params={len(self._synced_state.params)} keys")
            else:
                logger.info("ServiceBackend: no existing cascor network found (will create on start)")
            await self._adapter.start_metrics_relay()
            logger.info(f"ServiceBackend connected to {self._adapter.service_url}")
        else:
            logger.error(f"ServiceBackend failed to connect to {self._adapter.service_url}")
        return connected

    def get_synced_state(self) -> Optional[SyncedState]:
        """Return the state snapshot from the most recent sync, or None."""
        return self._synced_state

    async def shutdown(self) -> None:
        """Disconnect from cascor gracefully. Does NOT stop training on cascor."""
        await self._adapter.stop_metrics_relay()
        self._adapter.shutdown()
        logger.info("ServiceBackend disconnected — cascor continues running independently")
