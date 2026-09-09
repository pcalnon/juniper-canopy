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
from typing import Any, Dict, List, Mapping, Optional, cast

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

# Canopy-dialect staging keys that translate to juniper-data generator params. The spiral-only
# typed fields (``nn_spiral_rotations`` / ``nn_spiral_number``) are deliberately absent: a spiral is
# rank-2 and can never be staged into this backend, and forwarding them to a sequence generator
# would 422 at juniper-data.
_STAGED_PARAM_KEYS = {"nn_dataset_elements": "n_samples", "nn_dataset_noise": "noise"}


def dataset_ref_from_staged(cfg: Mapping[str, Any]) -> Dict[str, Any]:
    """Translate a canopy-dialect staged dataset config into a recurrence ``DatasetRef``.

    The staging channel speaks canopy's dialect (``nn_dataset_type`` + typed fields +
    ``nn_dataset_params``) because ``/api/stage_dataset`` was built for cascor, whose
    ``StageDatasetRequest`` is the authoritative validator there. The recurrence service takes the
    one-shot ``DatasetRef`` -- ``generator`` in juniper-data's vocabulary plus ``params`` forwarded
    verbatim -- so the alias map is applied HERE (``spirals`` -> ``spiral``), exactly where the
    one-shot Start body applies it (X3 / design §4.6), and never on the cascor-bound payload.

    The registry's ``default_params`` for the dataset seed ``params`` (bounded + stationary, the
    same seed the one-shot Start body carries); the typed fields override them; the schema-driven
    ``nn_dataset_params`` override both. A staged fit and an un-staged fit of the same dataset
    therefore differ only by what the operator actually edited.
    """
    from dataset_schema import generator_name_for_type
    from model_registry import dataset_default_params

    dataset_type = cfg.get("nn_dataset_type")
    params: Dict[str, Any] = dict(dataset_default_params(dataset_type or ""))
    for canopy_key, param_key in _STAGED_PARAM_KEYS.items():
        if cfg.get(canopy_key) is not None:
            params[param_key] = cfg[canopy_key]
    params.update(cfg.get("nn_dataset_params") or {})
    return {"generator": generator_name_for_type(dataset_type), "params": params, "split": "train"}


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
        # X6 / §4.9: the canopy-dialect dataset config staged for the NEXT fit (see the
        # "Dataset staging" section). Consumed by ``start_training``; surfaced on ``get_status``
        # as ``pending_dataset`` for the banner.
        self._pending_dataset_config: Optional[Dict[str, Any]] = None

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

        **A staged dataset config is the dataset of the next fit** (X6 / §4.9), and it takes
        precedence over a dataset reference in ``kwargs``. That is cascor's contract for
        ``POST /v1/training/dataset`` too, and it is the only honest order here: the one-shot
        Start body carries the registry's *defaults* for the dropdown value and knows nothing of
        what the operator edited and applied, so preferring it would discard the applied change
        while reporting success. Start consumes the staged config, as cascor's does, so the
        pending-dataset banner closes.
        """
        explicit_ref = {k: kwargs[k] for k in _DATASET_REF_KEYS if kwargs.get(k) is not None}

        hyperparams = dict(self._pending_hyperparams)
        for key in _HYPERPARAM_KEYS:
            if kwargs.get(key) is not None:
                hyperparams[key] = kwargs[key]

        with self._lock:
            if self._state == "training":
                return ControlResult(ok=False, error="a recurrence fit is already in progress", is_training=True)
            staged = self._pending_dataset_config
            dataset_ref = dataset_ref_from_staged(staged) if staged else explicit_ref
            if not any(dataset_ref.get(k) for k in ("dataset_id", "name", "generator")):
                return ControlResult(ok=False, error="no dataset reference (need one of dataset_id / name / generator, or a staged dataset)")
            if staged and explicit_ref.get("generator") not in (None, dataset_ref["generator"]):
                logger.info("recurrence fit uses the staged dataset %r over the start body's %r", dataset_ref["generator"], explicit_ref.get("generator"))
            self._pending_dataset_config = None  # consumed by this start (cascor parity)
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
            pending = self._pending_dataset_config
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
            # X6 / §4.9: the pending-dataset banner reconciles off this field for every backend
            # (cascor carries it through from /v1/training/status; demo reads its simulator).
            "pending_dataset": dict(pending) if pending else None,
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

    # --- Dataset staging (X6 / design §4.9) ---
    #
    # ``/api/stage_dataset`` / ``/api/cancel_pending_dataset`` and the pending-dataset banner were
    # built for cascor's server-side staging surface (cascor #242), and DemoMode mirrors them
    # in-process. This backend does the same. The recurrence service is one-shot -- the dataset
    # reference travels in ``POST /v1/train`` -- so "staged for the next start" is a canopy-side
    # fact: held here, consumed by ``start_training``, no service endpoint involved. Before this,
    # the pair the selection arc made reachable could be selected but not staged (the route
    # answered 501), and the restart modal's bare start had nothing to fit.

    def stage_dataset(self, **canopy_params: Any) -> Dict[str, Any]:
        """Record a canopy-dialect dataset config for the next fit; an empty body clears it."""
        cfg = {k: v for k, v in canopy_params.items() if v is not None}
        with self._lock:
            if not cfg:
                # cascor documents an empty body as "clears any prior staging"; keep the contract.
                self._pending_dataset_config = None
                return {"ok": True, "data": {"status": "cleared", "config": None}}
            if not cfg.get("nn_dataset_type"):
                return {"ok": False, "error": "a staged dataset needs nn_dataset_type"}
            self._pending_dataset_config = dict(cfg)
            return {"ok": True, "data": {"status": "staged", "config": dict(cfg), "dataset_ref": dataset_ref_from_staged(cfg)}}

    def cancel_pending_dataset(self) -> Dict[str, Any]:
        with self._lock:
            prior = self._pending_dataset_config
            self._pending_dataset_config = None
        return {"ok": True, "data": {"status": "cleared", "discarded": dict(prior) if prior else None}}

    def get_pending_dataset(self) -> Dict[str, Any]:
        with self._lock:
            cfg = self._pending_dataset_config
        return {"ok": True, "pending": dict(cfg) if cfg else None}

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
