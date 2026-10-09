#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Shape the recurrence POST /v1/train request: schema-filtered params + R7 precedence + preview
#
# Author:        Paul Calnon
# Version:       0.1.0
# File Name:     recurrence_request.py
# File Path:     JuniperCanopy/juniper_canopy/src/backend/
#
# Date Created:  2026-10-08
# Last Modified: 2026-10-08
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#     W1.2 of juniper-ml's plan notes/JUNIPER_2026-10-03_JUNIPER-RECURRENCE_EQUITIES-END-TO-END-AUDIT-AND-DEVELOPMENT-PLAN.md
#     (findings F-C2 and F-C3; owner ruling R7, whose recommended default this applies PENDING the
#     owner's ruling). The one place canopy decides what the recurrence service's ``POST /v1/train``
#     carries, so that the fit, the INFO log line and the dashboard's "effective request" preview are
#     the same computation and cannot disagree.
#
#####################################################################################################################################################################################################
# Notes:
#     - Pure: no Dash, no network, no backend state. ``RecurrenceBackend`` calls it under its own lock.
#     - ``train_request_body`` mirrors ``RecurrenceServiceAdapter.train``'s body key for key. That file
#       is not touched here; ``tests/regression/test_recurrence_staging.py`` drives the REAL adapter
#       through an ``httpx.MockTransport`` and fails if the two ever disagree.
#
#####################################################################################################################################################################################################
# References:
#     - dataset_schema.DECLARED_PARAM_DEFAULTS (what each generator declares, and its defaults).
#     - model_registry.dataset_default_params (the registry seed).
#     - backend/recurrence_backend.py (start_training / preview_train_request / dataset_ref_from_staged).
#
#####################################################################################################################################################################################################
"""The recurrence ``POST /v1/train`` request: what canopy forwards, and in what order (W1.2 / R7).

Two defects, one rule (juniper-ml plan ``notes/JUNIPER_2026-10-03_JUNIPER-RECURRENCE_EQUITIES-END-TO-END-AUDIT-AND-DEVELOPMENT-PLAN.md``):

* **F-C3** -- canopy translated its generic ``nn_dataset_elements`` / ``nn_dataset_noise`` into
  ``n_samples`` / ``noise`` for every generator, and no rank-3 generator declares either. Contrary to
  the plan's expectation of a 422, juniper-data did not refuse them: its params models keep
  pydantic's default ``extra`` handling and drop unknown keys, at ``main`` and at v0.16.0 alike. So
  the generic value vanished downstream while canopy reported it staged.
* **F-C2** -- the schema-driven form renders every field and Apply posts every rendered value, so an
  untouched ``equities_seq`` form staged its defaults beside the registry seed, and the request
  carried ``start_date``, ``max_symbols: 14`` and the rest. Nothing showed the request before Start.

**R7, as the plan recommends it (applied pending the owner's ruling):**

1. The registry seed is the base.
2. A GENERIC form field (``nn_dataset_elements`` / ``nn_dataset_noise``) is forwarded only when the
   generator declares the parameter it names, never over a key the seed sets, and not at the
   generator's own default.
3. A recurrence-aware (schema-driven) field is forwarded only when the generator declares it, and
   only when the operator EDITED it -- its value differs from what the form rendered for it, which
   is the seed's value where the seed sets the key and juniper-data's default otherwise
   (``dataset_schema.apply_seeded_defaults``). An edited field wins over the seed.
4. The result is previewed before Start (``POST /api/recurrence/effective_request``) and logged at
   INFO, at the preview and again at Start.

"Edited" is read from the value, because nothing else records it: Dash inputs carry no dirty flag,
and the form posts every rendered value. A value set back to its rendered default therefore reads as
untouched and is not sent -- which asks juniper-data for exactly the value the form showed.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Tuple

from dataset_schema import DECLARED_PARAMS_SOURCE, declared_param_defaults, generator_name_for_type
from model_registry import dataset_default_params

logger = logging.getLogger("juniper_canopy.backend.recurrence_request")

# canopy's GENERIC dataset-form fields -> the juniper-data parameter each one names. These are the
# spiral-era typed inputs: the sidebar sends them only for spiral, but the restart modal re-stages them
# for every dataset type (``DashboardManager._restage_dataset``), which is how they reach a sequence
# generator. No rank-3 generator declares either parameter (``dataset_schema.DECLARED_PARAM_DEFAULTS``).
GENERIC_FIELD_PARAMS: Dict[str, str] = {"nn_dataset_elements": "n_samples", "nn_dataset_noise": "noise"}

# Spiral-only typed fields. A spiral is rank-2 and cannot be staged into the recurrence backend, so
# these never have a parameter to become; they are reported, not silently dropped.
SPIRAL_ONLY_FIELDS: Tuple[str, ...] = ("nn_spiral_rotations", "nn_spiral_number")

# Where the request came from: a dataset staged with Apply (it wins, X6 / design §4.9) or the
# one-shot Start body (the dropdown value and the registry seed).
SOURCE_STAGED = "staged"
SOURCE_START_BODY = "start_body"

# ``start_training`` refuses with exactly this text, and the preview reports it, so the two agree.
NO_DATASET_REF_ERROR = "no dataset reference (need one of dataset_id / name / generator, or a staged dataset)"

_REF_IDENTITY_KEYS: Tuple[str, ...] = ("dataset_id", "name", "generator")
_TRAIN_HYPERPARAM_KEYS: Tuple[str, ...] = ("d", "theta", "ridge")


def same_value(left: Any, right: Any) -> bool:
    """Whether a value posted by the form equals the value the form rendered for it.

    Python equality with two corrections. Numbers compare by value, because JSON has one number type
    and a rendered ``1.0`` comes back from the browser as ``1``. Booleans compare only with booleans,
    because ``True == 1`` and ``False == 0`` hold in Python and a checkbox is not a count. Sequences
    compare element-wise whatever their container, and mappings key-wise.
    """
    if isinstance(left, bool) or isinstance(right, bool):
        return isinstance(left, bool) and isinstance(right, bool) and left == right
    if isinstance(left, (list, tuple)) and isinstance(right, (list, tuple)):
        return len(left) == len(right) and all(same_value(a, b) for a, b in zip(left, right, strict=True))
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        return set(left) == set(right) and all(same_value(left[key], right[key]) for key in left)
    return bool(left == right)


@dataclass(frozen=True)
class ShapedRef:
    """A dataset reference shaped for ``POST /v1/train``, and an account of what the shaping did.

    ``not_forwarded`` names every staged key the reference does not carry, by the name it was staged
    under. ``undeclared`` is the subset that arrived as a juniper-data parameter name -- from the
    schema-driven form or a Start body's ``params`` -- that ``DECLARED_PARAM_DEFAULTS`` lacks: a
    juniper-data addition the snapshot has not caught up with, or a caller's mistake. canopy's generic
    fields are never in it. ``edited`` names the parameters forwarded because they differ from what
    the form rendered. ``declared`` is False when the generator has no entry at all, in which case
    nothing was filtered.
    """

    dataset_ref: Dict[str, Any]
    not_forwarded: Tuple[str, ...] = ()
    undeclared: Tuple[str, ...] = ()
    edited: Tuple[str, ...] = ()
    declared: bool = True


def shape_staged_ref(cfg: Mapping[str, Any]) -> ShapedRef:
    """Translate a canopy-dialect staged dataset config into the recurrence ``DatasetRef`` (R7).

    ``cfg`` is what ``RecurrenceBackend.stage_dataset`` holds: ``nn_dataset_type``, the optional typed
    fields, and ``nn_dataset_params`` (the schema-driven form, seed first). The generator name is
    juniper-data's (``spirals`` -> ``spiral``); the seed is looked up under canopy's value, which is
    what the registry is keyed on. See the module docstring for the four rules.
    """
    dataset_type = cfg.get("nn_dataset_type") or ""
    generator = generator_name_for_type(dataset_type)
    seed = dataset_default_params(dataset_type)
    declared = declared_param_defaults(generator)
    params: Dict[str, Any] = dict(seed)
    not_forwarded: List[str] = [key for key in SPIRAL_ONLY_FIELDS if cfg.get(key) is not None]
    undeclared: List[str] = []
    edited: List[str] = []

    for canopy_key, param in GENERIC_FIELD_PARAMS.items():
        value = cfg.get(canopy_key)
        if value is None:
            continue
        if (declared is not None and param not in declared) or param in seed:
            not_forwarded.append(canopy_key)  # F-C3: nothing to become; R7: never over the seed
        elif declared is None or not same_value(value, declared[param]):
            params[param] = value
            edited.append(param)

    for key, value in (cfg.get("nn_dataset_params") or {}).items():
        if declared is not None and key not in declared:
            not_forwarded.append(key)
            undeclared.append(key)
            continue
        if key in seed:
            rendered: Any = seed[key]
        elif declared is not None:
            rendered = declared[key]
        else:
            # No declaration to read a rendered default from: forward as staged (the pre-W1.2 behaviour).
            params[key] = value
            continue
        if not same_value(value, rendered):
            params[key] = value
            edited.append(key)

    return ShapedRef(
        dataset_ref={"generator": generator, "params": params, "split": "train"},
        not_forwarded=tuple(not_forwarded),
        undeclared=tuple(undeclared),
        edited=tuple(edited),
        declared=declared is not None,
    )


def shape_start_body_ref(ref: Mapping[str, Any]) -> ShapedRef:
    """Filter a Start body's dataset reference to the parameters its generator declares (F-C3).

    The one-shot Start body carries the registry seed for the dropdown value, or whatever an API
    caller sent; both are explicit, so nothing is compared against a rendered default -- only a
    parameter the generator does not declare is withheld. A reference by ``dataset_id`` / ``name``
    names no generator, and one whose generator canopy declares nothing for is passed through.
    """
    out = dict(ref)
    generator = out.get("generator")
    declared = declared_param_defaults(generator) if generator else None
    params = out.get("params")
    if declared is None or not isinstance(params, Mapping):
        return ShapedRef(dataset_ref=out, declared=declared is not None)
    withheld = tuple(key for key in params if key not in declared)
    out["params"] = {key: value for key, value in params.items() if key in declared}
    return ShapedRef(dataset_ref=out, not_forwarded=withheld, undeclared=withheld)


def train_request_body(dataset_ref: Mapping[str, Any], hyperparams: Mapping[str, Any]) -> Dict[str, Any]:
    """The JSON body ``RecurrenceServiceAdapter.train(**dataset_ref, **hyperparams)`` POSTs.

    Built the way the adapter builds it: ``split`` always (``"train"`` when the reference has none,
    the adapter's default), each identity key and ``params`` only when present, and each LMU
    hyperparameter only when set.
    """
    dataset: Dict[str, Any] = {"split": dataset_ref.get("split", "train")}
    for key in _REF_IDENTITY_KEYS:
        if dataset_ref.get(key) is not None:
            dataset[key] = dataset_ref[key]
    if dataset_ref.get("params") is not None:
        dataset["params"] = dict(dataset_ref["params"])
    body: Dict[str, Any] = {"dataset": dataset}
    for key in _TRAIN_HYPERPARAM_KEYS:
        if hyperparams.get(key) is not None:
            body[key] = hyperparams[key]
    return body


@dataclass(frozen=True)
class FitRequest:
    """The next fit's request, resolved exactly as ``RecurrenceBackend.start_training`` resolves it."""

    source: str
    shaped: ShapedRef
    hyperparams: Dict[str, Any]
    start_body_generator: Optional[str] = None

    @property
    def dataset_ref(self) -> Dict[str, Any]:
        return self.shaped.dataset_ref

    @property
    def has_dataset_ref(self) -> bool:
        return any(self.dataset_ref.get(key) for key in _REF_IDENTITY_KEYS)

    @property
    def body(self) -> Optional[Dict[str, Any]]:
        """The ``POST /v1/train`` body, or None when there is no dataset reference to send."""
        return train_request_body(self.dataset_ref, self.hyperparams) if self.has_dataset_ref else None

    def describe(self) -> Dict[str, Any]:
        """The read-only preview payload served by ``POST /api/recurrence/effective_request``."""
        preview: Dict[str, Any] = {
            "ok": self.has_dataset_ref,
            "source": self.source,
            "request": self.body,
            "not_forwarded": list(self.shaped.not_forwarded),
            "edited": list(self.shaped.edited),
            "declared_params_source": DECLARED_PARAMS_SOURCE,
        }
        if not self.has_dataset_ref:
            preview["error"] = NO_DATASET_REF_ERROR
        return preview

    def log(self, phase: str) -> None:
        """Log the effective request at INFO (R7); at Start, also WARN about anything filtered blind.

        ``phase`` is ``"preview"`` or ``"start"``. The body is serialised with sorted keys so two log
        lines for the same request compare equal as text. The WARNINGs fire at Start only: the preview
        is refreshed on every selection change and Apply, and already shows the same list on screen.
        """
        body = self.body
        if body is None:
            logger.info("recurrence effective request (%s): none -- %s", phase, NO_DATASET_REF_ERROR)
            return
        withheld = f"; not forwarded: {', '.join(self.shaped.not_forwarded)}" if self.shaped.not_forwarded else ""
        logger.info("recurrence effective request (%s, source=%s): %s%s", phase, self.source, json.dumps(body, sort_keys=True, default=str), withheld)
        if phase != "start":
            return
        if self.shaped.undeclared:
            logger.warning(
                "recurrence request for %r withheld %s: not declared in dataset_schema.DECLARED_PARAM_DEFAULTS (%s). If juniper-data added them, re-capture with util/ad-hoc/2026-10-08_capture_sequence_generator_schemas.py",
                self.dataset_ref.get("generator"),
                ", ".join(self.shaped.undeclared),
                DECLARED_PARAMS_SOURCE,
            )
        if not self.shaped.declared and self.dataset_ref.get("generator"):
            logger.warning("recurrence request for %r is forwarded unfiltered: dataset_schema.DECLARED_PARAM_DEFAULTS has no entry for it", self.dataset_ref.get("generator"))


def resolve_fit_request(*, explicit_ref: Mapping[str, Any], staged_cfg: Optional[Mapping[str, Any]], hyperparams: Mapping[str, Any]) -> FitRequest:
    """Resolve the next fit's request. A staged dataset wins over the Start body's reference.

    That order is X6 / design §4.9 and cascor's contract for its staged dataset: the one-shot Start
    body carries only the registry's defaults for the dropdown value and knows nothing of what the
    operator edited and applied. The Start body's generator is kept on the result so the backend can
    say when the staged dataset overrode it.
    """
    start_body_generator = explicit_ref.get("generator")
    if staged_cfg:
        return FitRequest(source=SOURCE_STAGED, shaped=shape_staged_ref(staged_cfg), hyperparams=dict(hyperparams), start_body_generator=start_body_generator)
    return FitRequest(source=SOURCE_START_BODY, shaped=shape_start_body_ref(explicit_ref), hyperparams=dict(hyperparams), start_body_generator=start_body_generator)
