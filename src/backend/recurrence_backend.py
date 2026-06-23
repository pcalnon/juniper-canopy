#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       BackendProtocol adapter wrapping RecurrenceServiceAdapter (one-shot fit)
#
# Author:        Paul Calnon
# Version:       0.1.0
# File Name:     recurrence_backend.py
# File Path:     JuniperCanopy/juniper_canopy/src/backend/
#
# Date Created:  2026-06-22
# Last Modified: 2026-06-22
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#     A1-ii of the model-selection A1 enabler (design-of-record: juniper-ml
#     notes/JUNIPER_CANOPY_MODEL_SELECTION_A1_ENABLER_SCOPE_2026-06-18.md, decisions D1-A /
#     D5 / D6). ``RecurrenceBackend`` adapts ``RecurrenceServiceAdapter`` to
#     ``BackendProtocol`` so the dashboard can drive a recurrence (LMU) fit through the
#     same interface it uses for cascor — without canopy's poll-and-chart machinery
#     fabricating per-epoch progress the model does not have.
#
#     The recurrence service's ``POST /v1/train`` is a SYNCHRONOUS one-shot fit (it blocks
#     until the LMU is solved). ``BackendProtocol.start_training`` must return immediately
#     (it runs on a Dash callback), so this backend runs the blocking ``adapter.train`` on
#     a daemon thread and reports a BINARY status — idle -> training -> trained|failed — via
#     ``get_status`` / ``is_training_active``. There are no per-epoch metrics to stream and
#     none are invented (D1-A: honest one-shot, not a faked feed). The cascade-only surface
#     (network topology, decision boundary, candidate metrics) returns ``None`` / empty
#     because LMU has no growing topology and no 2-D decision boundary (D6).
#
#     Scope (A1-ii, per the ratified slice cadence): this backend + its routing through
#     ``create_backend`` only. Wiring it into ``main.py``'s route layer (which branches on
#     ``backend_type``) and the one-shot result view / panel suppression are A1-iii.
#
#####################################################################################################################################################################################################
# Notes:
#     - Concurrency: a ``threading.Lock`` guards the small state machine; the blocking
#       ``adapter.train`` call runs OUTSIDE the lock so ``get_status`` can be polled while a
#       fit is in flight. The worker is a daemon thread (never blocks process exit).
#     - Regression-generic: recurrence metrics are mse / rmse / mae / r2 / loss — never
#       accuracy. ``get_metrics`` returns the raw final-metrics dict; the metrics-panel
#       accuracy->regression switch is A1-iii.
#     - ``completion_reason`` (an existing ``StatusResult`` field) carries the failure
#       message on failure and the service's ``stopped_reason`` on success.
#
#####################################################################################################################################################################################################
# References:
#     - backend/service_backend.py (the cascor ServiceBackend, the delegation template).
#     - backend/recurrence_service_adapter.py (the REST client wrapped here, A1-i).
#     - backend/protocol.py (BackendProtocol + the total=False TypedDict return types).
#
#####################################################################################################################################################################################################
# TODO :
#     - A1-iii: handle ``backend_type == "recurrence"`` in main.py's route branches; the
#       one-shot result view; cascade-panel suppression driven by model-class metadata.
#
#####################################################################################################################################################################################################
# COMPLETED:
#
#####################################################################################################################################################################################################
"""``BackendProtocol`` wrapper for the juniper-recurrence one-shot fit (A1-ii, D1-A/D5/D6).

Runs the adapter's blocking ``train`` on a daemon thread and reports a binary
idle/training/trained/failed status; stubs the cascade-only surface to ``None``/empty.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List, Optional, cast

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
from backend.recurrence_service_adapter import RecurrenceServiceAdapter, RecurrenceServiceError, RecurrenceTrainResult

logger = logging.getLogger("juniper_canopy.backend.recurrence_backend")

# Keys extracted from ``start_training(**kwargs)`` and forwarded to ``adapter.train``.
_DATASET_REF_KEYS = ("dataset_id", "name", "generator", "params", "split")
_HYPERPARAM_KEYS = ("d", "theta", "ridge")
# Internal fit state -> the dashboard "phase" label.
_PHASE_BY_STATE = {"idle": "idle", "training": "fitting", "trained": "complete", "failed": "error"}


class RecurrenceBackend:
    """``BackendProtocol`` implementation wrapping :class:`RecurrenceServiceAdapter`.

    A one-shot execution paradigm: ``start_training`` backgrounds the blocking
    ``POST /v1/train`` and the backend reports a binary status until the fit completes.
    The cascade-specific protocol methods (topology / decision boundary) return ``None``.
    """

    def __init__(self, adapter: RecurrenceServiceAdapter) -> None:
        self._adapter = adapter
        self._lock = threading.Lock()
        self._state = "idle"  # "idle" | "training" | "trained" | "failed"
        self._thread: Optional[threading.Thread] = None
        self._result: Optional[RecurrenceTrainResult] = None
        self._error: Optional[str] = None
        self._pending_hyperparams: Dict[str, Any] = {}

    @property
    def backend_type(self) -> str:
        # A distinct type (not "service") so A1-iii can drive one-shot rendering + panel
        # suppression off it; main.py's backend_type branches are audited in A1-iii.
        return "recurrence"

    @property
    def execution(self) -> str:
        """One-shot fit paradigm — drives A1-iii cascade-panel suppression + regression metrics."""
        return "one_shot"

    # --- Training control ---

    def start_training(self, reset: bool = True, **kwargs: Any) -> ControlResult:
        """Background a one-shot ``POST /v1/train``; return immediately.

        Dataset reference (``dataset_id`` / ``name`` / ``generator`` / ``params`` /
        ``split``) and LMU hyperparameters (``d`` / ``theta`` / ``ridge``) are read from
        ``kwargs``; hyperparameters fall back to any previously :meth:`apply_params`-staged
        values. ``reset`` is accepted for protocol parity (each fit is independent).
        """
        dataset_ref = {k: kwargs[k] for k in _DATASET_REF_KEYS if kwargs.get(k) is not None}
        if not any(dataset_ref.get(k) for k in ("dataset_id", "name", "generator")):
            return ControlResult(ok=False, error="no dataset reference (need one of dataset_id / name / generator)")

        hyperparams = dict(self._pending_hyperparams)
        for key in _HYPERPARAM_KEYS:
            if kwargs.get(key) is not None:
                hyperparams[key] = kwargs[key]

        with self._lock:
            if self._state == "training":
                return ControlResult(ok=False, error="a recurrence fit is already in progress", is_training=True)
            self._result = None
            self._error = None
            self._state = "training"
            thread = threading.Thread(target=self._run_fit, args=(dataset_ref, hyperparams), name="recurrence-fit", daemon=True)
            self._thread = thread
        thread.start()  # outside the lock — never hold it across thread start / the blocking call
        return ControlResult(ok=True, is_training=True, message="recurrence fit started")

    def _run_fit(self, dataset_ref: Dict[str, Any], hyperparams: Dict[str, Any]) -> None:
        """Daemon-thread target: run the blocking fit, then record terminal state."""
        try:
            result = self._adapter.train(**dataset_ref, **hyperparams)
        except RecurrenceServiceError as exc:
            with self._lock:
                self._error = str(exc)
                self._state = "failed"
            logger.warning("recurrence fit failed: %s", exc)
            return
        except Exception as exc:  # defensive: never leave the state stuck in "training"
            with self._lock:
                self._error = f"unexpected error during recurrence fit: {exc}"
                self._state = "failed"
            logger.exception("recurrence fit crashed")
            return
        with self._lock:
            self._result = result
            self._state = "trained"
        logger.info("recurrence fit complete (final_metrics=%s)", result.final_metrics)

    def stop_training(self) -> ControlResult:
        # A one-shot ridge/lstsq solve is not interruptible.
        return ControlResult(ok=False, message="a recurrence fit is a non-interruptible one-shot solve and cannot be stopped")

    def pause_training(self) -> ControlResult:
        return ControlResult(ok=False, message="pause is not supported for one-shot (recurrence) models")

    def resume_training(self) -> ControlResult:
        return ControlResult(ok=False, message="resume is not supported for one-shot (recurrence) models")

    def reset_training(self) -> ControlResult:
        with self._lock:
            if self._state == "training":
                return ControlResult(ok=False, error="cannot reset while a recurrence fit is in progress")
            self._state = "idle"
            self._result = None
            self._error = None
        return ControlResult(ok=True, is_training=False)

    def is_training_active(self) -> bool:
        with self._lock:
            return self._state == "training"

    # --- Status and metrics ---

    def get_status(self) -> StatusResult:
        with self._lock:
            state = self._state
            result = self._result
            error = self._error
        status: Dict[str, Any] = {
            "is_training": state == "training",
            "is_running": state == "training",
            "is_paused": False,
            "completed": state == "trained",
            "failed": state == "failed",
            "fsm_status": state,
            "phase": _PHASE_BY_STATE[state],
            "network_connected": state == "trained",
            "monitoring_active": state == "training",
        }
        if state == "failed" and error is not None:
            status["completion_reason"] = error
        elif result is not None:
            status["current_epoch"] = result.n_epochs
            if result.stopped_reason:
                status["completion_reason"] = result.stopped_reason
        return cast(StatusResult, status)

    def get_metrics(self) -> MetricsResult:
        with self._lock:
            result = self._result
        if result is None:
            return cast(MetricsResult, {})
        # Regression metric set (mse / rmse / mae / r2 / loss) carried through verbatim;
        # the panel renders these as regression metrics in A1-iii. ``loss`` is surfaced so
        # the generic loss readout has a value even if the service omits an explicit key.
        metrics: Dict[str, Any] = dict(result.final_metrics)
        metrics["epoch"] = result.n_epochs
        if "loss" not in metrics:
            metrics["loss"] = result.final_metrics.get("mse", result.final_metrics.get("rmse", 0.0))
        return cast(MetricsResult, metrics)

    def get_metrics_history(self, count: int = 100) -> List[MetricsResult]:
        # A one-shot fit has no per-epoch history: a single terminal point, or nothing yet.
        metrics = self.get_metrics()
        return [metrics] if metrics else []

    # --- Network and data ---

    def has_network(self) -> bool:
        with self._lock:
            return self._state == "trained"

    def get_network_topology(self) -> Optional[TopologyResult]:
        return None  # LMU has no growing cascade topology (D6)

    def get_raw_topology(self) -> Optional[RawTopologyResult]:
        return None

    def get_network_stats(self) -> NetworkStatsResult:
        with self._lock:
            return cast(NetworkStatsResult, {"network_loaded": self._state == "trained", "training_active": self._state == "training"})

    def get_dataset(self) -> Optional[DatasetResult]:
        with self._lock:
            result = self._result
        if result is None or not result.dataset:
            return None
        descriptor = result.dataset
        return cast(
            DatasetResult,
            {
                "num_samples": descriptor.get("n_windows", 0),
                "num_features": descriptor.get("n_features", 0),
                "num_classes": descriptor.get("output_dim", 0),
                "loaded": True,
                "dataset_name": descriptor.get("name") or descriptor.get("dataset_id") or "",
            },
        )

    def get_decision_boundary(self, resolution: int = 50) -> Optional[DecisionBoundaryResult]:
        return None  # 2-D-classification only; meaningless for an LMU sequence regressor (D6)

    # --- Parameters ---

    def apply_params(self, **params: Any) -> ApplyParamsResult:
        """Stage recognised LMU hyperparameters (``d`` / ``theta`` / ``ridge``) for the next fit.

        Recurrence hyperparameters apply at fit time (not live), so they are stored and
        consumed by the next :meth:`start_training`. Unrecognised params are ignored.
        """
        applied: Dict[str, Any] = {}
        with self._lock:
            for key in _HYPERPARAM_KEYS:
                if params.get(key) is not None:
                    self._pending_hyperparams[key] = params[key]
                    applied[key] = params[key]
        return cast(ApplyParamsResult, {"ok": True, "data": applied})

    # --- Lifecycle ---

    async def initialize(self) -> bool:
        """No eager connection — the adapter surfaces connection errors at fit time."""
        logger.info("RecurrenceBackend ready (lazy connect) for %s", self._adapter.service_url)
        return True

    async def shutdown(self) -> None:
        """Join an in-flight fit thread (bounded) so shutdown does not race the worker."""
        with self._lock:
            thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=5.0)
        logger.info("RecurrenceBackend shut down")
