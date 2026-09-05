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
#     - juniper-ml/notes/JUNIPER_2026-04-20_JUNIPER-ECOSYSTEM_MICROSERVICES-ARCHITECTURE-DEVELOPMENT-ROADMAP.md §5.6
#
#####################################################################################################################################################################################################
# TODO :
#
#####################################################################################################################################################################################################
# COMPLETED:
#
#####################################################################################################################################################################################################

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional, cast

import validation_gate
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
from canopy_constants import TrainingConstants

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

    @property
    def execution(self) -> str:
        """Execution paradigm — cascor streams live per-epoch training (A1-iii)."""
        return "live"

    # --- Training control ---

    # Default dataset staged on a first start against a fresh cascor (no network,
    # nothing staged, nothing loaded) — the "trivial case" of the training-start
    # diagnosis 2026-07-09 (PR-B2). Values are the Dataset-panel defaults from
    # TrainingConstants, in the canopy staging dialect that cascor's
    # StageDatasetRequest speaks (cascor translates to juniper-data's schema at
    # its fetch boundary since PR-B1).
    _DEFAULT_FIRST_START_DATASET: Dict[str, Any] = {
        "nn_dataset_type": "spirals",
        "nn_dataset_elements": TrainingConstants.DEFAULT_DATASET_ELEMENTS,
        "nn_dataset_noise": TrainingConstants.DEFAULT_DATASET_NOISE,
        "nn_spiral_rotations": TrainingConstants.DEFAULT_SPIRAL_ROTATIONS,
        "nn_spiral_number": TrainingConstants.DEFAULT_SPIRAL_NUMBER,
    }

    def start_training(self, reset: bool = True, start_fresh: bool = False, accept_missing_validation_split: bool = False, **kwargs: Any) -> ControlResult:
        """Start training, refusing first if the dataset has no validation split.

        Design §6.4: an interactive run must not proceed silently when ``X_val`` is
        absent. cascor refuses at ingress (§6.1 rule 1) and that refusal is what
        ultimately protects the metric, but by then the user has clicked Start and gets
        a service error rather than a choice. Refusing HERE, before the request, is what
        lets canopy explain the problem and offer §6.4's options.

        ``accept_missing_validation_split`` is the user's choice arriving back -- §6.4
        option 1. It is a parameter rather than a setting on purpose: the decision
        belongs to one run, and a persisted flag would silently apply to the next one.

        Args:
            reset: legacy query flag, not forwarded (see below).
            start_fresh: discard the current model rather than continuing it.
            accept_missing_validation_split: proceed despite a missing validation split,
                having been told what that costs. The caller is responsible for
                recording the warning for the run's lifetime.
        """
        if self._adapter.is_training_in_progress():
            return ControlResult(ok=False, error="Training already in progress")
        gate = self._validation_split_refusal(accept_missing_validation_split)
        if gate is not None:
            return gate
        if self._adapter.network is None:
            # PR-B2: cascor creates the network from the dataset dims on start
            # (PR-B1), honoring this class's long-standing "will create on
            # start" startup log — canopy's job is only to guarantee there IS
            # a dataset for cascor to size from.
            failure = self._ensure_first_start_dataset()
            if failure is not None:
                return ControlResult(ok=False, error=failure)
        # N3 / Q4 / cascor C5: forward ``start_fresh`` to cascor's POST
        # /v1/training/start body field (default False = continue the current
        # model, retaining metrics/history). The legacy ``reset`` query flag is
        # not forwarded — cascor's start consumes any staged dataset and rebuilds
        # the network from its dims regardless, and start_fresh now carries the
        # explicit model-discard semantics.
        started, error = self._adapter.start_training_background(start_fresh=start_fresh, **kwargs)
        if not started:
            return ControlResult(ok=False, error=error or "Failed to start training")
        return ControlResult(ok=True, is_training=True)

    def _validation_split_refusal(self, accepted: bool) -> Optional[ControlResult]:
        """Return a refusal when the staged dataset is KNOWN to have no validation split.

        ``None`` means "nothing to refuse", which covers three different situations and
        deliberately does not distinguish them here: the split exists, the user has
        already accepted its absence, or this cascor is too old to say. The third is
        surfaced as a warning by :func:`validation_gate.decide`, not as a refusal --
        gating on "cannot tell" would block every run against an older cascor and teach
        the user to click past the gate, which is worse than the thing being guarded.
        """
        if accepted:
            return None
        decision = validation_gate.decide(self._adapter.get_dataset_info())
        if not decision.show_gate:
            return None
        return ControlResult(
            ok=False,
            error=validation_gate.CONTINUE_WITH_WARNING_NOTE,
            data={
                "validation_gate": True,
                "options": [
                    {
                        "id": option.option_id,
                        "label": option.label,
                        "description": option.description,
                        "enabled": option.enabled,
                        "disabled_reason": option.disabled_reason,
                    }
                    for option in decision.options
                ],
            },
        )

    def _ensure_first_start_dataset(self) -> Optional[str]:
        """Trivial-case first start: make sure cascor has data to size the network from.

        Startable already (returns None) when a staged dataset is pending or a
        dataset is loaded; otherwise stages the Dataset-panel defaults
        (``_DEFAULT_FIRST_START_DATASET``). Returns an error message on staging
        failure.
        """
        pending = self._adapter.get_pending_dataset()
        if pending.get("pending"):
            return None
        info = self._adapter.get_dataset_info() or {}
        if info.get("loaded"):
            return None
        logger.info("First start on a fresh cascor: staging default dataset %s", self._DEFAULT_FIRST_START_DATASET)
        result = self._adapter.stage_dataset(**self._DEFAULT_FIRST_START_DATASET)
        if not result.get("ok"):
            return f"Failed to stage default dataset: {result.get('error', 'unknown error')}"
        return None

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
        """Live status fetch, normalized. Unchanged behaviour — see ``normalize_status``."""
        return self.normalize_status(self._adapter.get_training_status())

    @staticmethod
    def normalize_status(raw: Any) -> StatusResult:
        """Map cascor's raw training status onto canopy's ``StatusResult`` shape.

        Split out of ``get_status`` for the X7 slice-1c status cache, which needs the two
        halves separately: it classifies the **raw** response — the nested check below is
        the classifier's discriminator too — and then serves the **normalized** one to
        readers. Composing them as ``get_status`` does would force the cache to choose one.

        Pure and static; the body moved verbatim, so ``get_status`` is exactly this
        function applied to a live fetch.
        """
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
                # N6 / C2b (training-runtime-defects plan §4 I-1c / §5 S12):
                # carry through the reconciled counter surface so the header +
                # network-info panels can render each counter against its
                # correct denominator. Field meanings are the C2b contract
                # documented in juniper-cascor
                # ``docs/api/JUNIPER_CASCOR_API_REFERENCE.md`` ("Counter
                # semantics"): ``current_step`` aliases ``current_epoch``
                # (completed training steps); ``grow_iteration``/``grow_max`` is
                # the cascade growth-iteration counter vs ``max_iterations`` (the
                # true "Iteration", distinct from the hidden-unit count);
                # ``output_epoch``/``candidate_epoch`` (+ their ``*_total_epochs``)
                # are the live within-pass inner-epoch progress that resets to 0
                # at each phase entry by design. Nested under ``training_state``
                # in the cascor payload (``grow_iteration`` etc.), so read from
                # ``ts``. Absent on a pre-C2b cascor → ``None`` → the consumer
                # renders a graceful placeholder.
                "current_step": _first_defined(
                    ts.get("current_step"),
                    monitor.get("current_step"),
                    monitor.get("current_epoch"),
                    ts.get("current_epoch"),
                    default=0,
                ),
                "grow_iteration": ts.get("grow_iteration"),
                "grow_max": ts.get("grow_max"),
                "output_epoch": ts.get("output_epoch"),
                "output_total_epochs": ts.get("output_total_epochs"),
                "candidate_epoch": ts.get("candidate_epoch"),
                "candidate_total_epochs": ts.get("candidate_total_epochs"),
                # FRONTEND_ISSUES_PLAN_2026-05-09 §3.5.1 / Issue #3 Phase 1 —
                # surface the cascor-side staged dataset config so the canopy
                # banner can react without a separate poll. Cascor #242 added
                # this field to the /v1/training/status payload; carry it
                # through unchanged.
                "pending_dataset": raw.get("pending_dataset"),
                # cascor #320 (Issue #3 follow-up): which grow_network exit fired
                # (converged vs a 0-unit stall, etc.). Carried through unchanged
                # so the status bar can render "Completed — <reason>". None when
                # the connected cascor predates the field.
                "completion_reason": raw.get("completion_reason"),
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
            # THREE partitions. ``num_samples`` summed train + test, which was the whole
            # dataset only while there were two; with a val split it under-counts by the
            # validation rows and the dashboard reports a dataset smaller than the one
            # cascor is training on.
            #
            # ``val_samples`` is absent from a pre-#623 cascor, and ``.get(..., 0)`` is the
            # right reading of that: a producer that does not report a validation split has
            # none to report. It is NOT a claim that the split is empty -- see
            # ``has_validation_split`` below, which distinguishes "no val" from "cascor too
            # old to say".
            result = {
                "num_samples": raw.get("train_samples", 0) + raw.get("val_samples", 0) + raw.get("test_samples", 0),
                "num_features": raw.get("input_features", 0),
                "num_classes": raw.get("output_features", 0),
                "loaded": raw.get("loaded", True),
                "train_samples": raw.get("train_samples", 0),
                "val_samples": raw.get("val_samples", 0),
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

    # FRONTEND_ISSUES_PLAN_2026-05-09 §3.5.1 / Issue #3 Phase 1 — pass-through
    # to the cascor pending-dataset surface (cascor #242).

    def stage_dataset(self, **canopy_params: Any) -> Dict[str, Any]:
        return self._adapter.stage_dataset(**canopy_params)

    def cancel_pending_dataset(self) -> Dict[str, Any]:
        return self._adapter.cancel_pending_dataset()

    def get_pending_dataset(self) -> Dict[str, Any]:
        return self._adapter.get_pending_dataset()

    # Phase 2 P2-4 (Issue #3): pass-through to cascor's experimental-functions
    # gate (cascor #245 P2-1a — see ISSUE_3_PHASE_2_LIVE_DATASET_SWAP_2026-05-09 §3.1).

    def get_experimental_functions(self) -> Dict[str, Any]:
        return self._adapter.get_experimental_functions()

    def set_experimental_functions(self, enabled: bool) -> Dict[str, Any]:
        return self._adapter.set_experimental_functions(enabled)

    # Phase 2 P2-5 (Issue #3): Live Dataset Switch — passthroughs to
    # cascor's /v1/training/dataset/live (POST + DELETE).

    def swap_dataset_live(self, **canopy_params: Any) -> Dict[str, Any]:
        return self._adapter.swap_dataset_live(**canopy_params)

    def cancel_swap_dataset_live(self) -> Dict[str, Any]:
        return self._adapter.cancel_swap_dataset_live()

    # Phase 2 P2-7 (Issue #3): dataset_swap event feed (cascor follow-up
    # B / #255). Polled by canopy's three swap-aware panels.

    def get_dataset_swap_events(self, since: Optional[str] = None) -> Dict[str, Any]:
        return self._adapter.get_dataset_swap_events(since=since)

    def get_snapshot_dataset_swaps(self, snapshot_id: str) -> Dict[str, Any]:
        """P2-7 follow-up: per-snapshot swap history (cascor #259)."""
        return self._adapter.get_snapshot_dataset_swaps(snapshot_id=snapshot_id)

    # --- Lifecycle ---

    async def initialize(self) -> bool:
        """Connect to cascor service, attach non-destructively, sync state, and start metrics relay."""
        connected = await self._adapter.connect()
        if connected:
            # Non-destructive attach: check for existing network without creating/resetting.
            # X7: both calls below are synchronous cascor HTTP — ``attach_to_existing``
            # issues a ``get_network()`` and ``sync()`` issues several more. This runs on
            # the request path, not just at startup: ``_swap_backend`` (main.py) awaits
            # ``initialize()`` when the operator changes model at runtime.
            has_network = await asyncio.to_thread(self._adapter.attach_to_existing)
            if has_network:
                logger.info("ServiceBackend: attached to existing cascor network")
                # Sync current cascor state into canopy
                self._synced_state = await asyncio.to_thread(CascorStateSync(self._adapter.client).sync)
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
