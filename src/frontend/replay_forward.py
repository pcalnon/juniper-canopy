#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     replay_forward.py
# Author:        Paul Calnon
# Date:          2026-05-03
# License:       MIT License
# Description:   Replay V2 weight-payload decoding + cascade-correlation
#                forward pass for canopy-side decision-boundary rendering.
#                Phase 6E CAN-015g g-7.
#####################################################################
"""Decode and apply replay V2 weight payloads for canopy rendering.

The cascor backend's g-3 emitter produces sample-boundary
``epoch_end`` events with a base64-encoded weight payload (see
``juniper-cascor/notes/development/SNAPSHOT_SCHEMA_V2.md``). This
module:

- Decodes the base64 envelopes into numpy arrays.
- Implements a pure-numpy cascade-correlation forward pass so
  ``decision_boundary.py`` can render the network as it was at a
  given sample without round-tripping through cascor.

The forward pass is **not** a full reimplementation of
``CascadeCorrelationNetwork.forward`` — it covers exactly the
output-prediction surface canopy needs, with the activation set the
serializer ships (tanh, sigmoid, relu, linear). Anything more exotic
than these falls back to identity with a logged warning so a
production-pretty plot is still produced.
"""

from __future__ import annotations

import base64
import logging
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


# Activation registry. Keys match the ``activation`` strings the
# cascor recorder emits via ``_unit_activation_name`` (g-6) — the
# names are the Python class names of the activation functions.
# Unknown activations fall back to identity with a WARNING.
_ACTIVATIONS = {
    "tanh": np.tanh,
    "Tanh": np.tanh,
    "sigmoid": lambda x: 1.0 / (1.0 + np.exp(-np.clip(x, -50.0, 50.0))),
    "Sigmoid": lambda x: 1.0 / (1.0 + np.exp(-np.clip(x, -50.0, 50.0))),
    "relu": lambda x: np.maximum(0.0, x),
    "ReLU": lambda x: np.maximum(0.0, x),
    "linear": lambda x: x,
    "Linear": lambda x: x,
    "identity": lambda x: x,
    "": lambda x: x,  # empty string from g-6 when the unit's activation
    # name couldn't be resolved — forgive silently
}


def _activation_for(name: Optional[str]):
    if name is None or name not in _ACTIVATIONS:
        if name:
            logger.warning("replay_forward: unknown activation %r — falling back to identity", name)
        return _ACTIVATIONS[""]
    return _ACTIVATIONS[name]


# ---------------------------------------------------------------------
# Base64 → numpy decoding
# ---------------------------------------------------------------------


def decode_tensor(envelope: Optional[Dict[str, Any]]) -> Optional[np.ndarray]:
    """Decode a single ``{dtype, shape, data: base64}`` envelope.

    Returns ``None`` if the input is missing or malformed — callers
    treat absent tensors as "skip this field" rather than crashing
    a render path.
    """
    if not envelope or not isinstance(envelope, dict):
        return None
    data = envelope.get("data")
    shape = envelope.get("shape")
    dtype = envelope.get("dtype", "float32")
    if not isinstance(data, str) or not isinstance(shape, list):
        return None
    try:
        raw = base64.b64decode(data)
        arr = np.frombuffer(raw, dtype=np.dtype(dtype)).reshape(shape)
        # ``np.frombuffer`` returns a non-writable view; copy so callers
        # can compose / cast without surprises.
        return np.array(arr, copy=True)
    except (ValueError, TypeError) as e:
        logger.warning("replay_forward: tensor decode failed: %s", e)
        return None


def decode_weight_payload(payload: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Decode a full V2 weight payload into numpy form.

    Returns a dict with the same shape as the wire payload but with
    ``output_weights`` / ``output_bias`` / hidden-unit ``weights``
    fields replaced by numpy arrays. ``None`` propagation is
    preserved for any missing tensor.
    """
    if not payload:
        return None
    decoded: Dict[str, Any] = {
        "sample_index": int(payload.get("sample_index", 0)),
        "epoch": int(payload.get("epoch", 0)),
        "output_weights": decode_tensor(payload.get("output_weights")),
        "output_bias": decode_tensor(payload.get("output_bias")),
        "hidden_units": [],
    }
    for unit in payload.get("hidden_units", []) or []:
        if not isinstance(unit, dict):
            continue
        decoded["hidden_units"].append(
            {
                "first_sample_index": int(unit.get("first_sample_index", 0)),
                "activation": str(unit.get("activation", "")),
                "weights": decode_tensor(unit.get("weights")),
                # Bias is shipped as a plain Python float (not an envelope).
                "bias": float(unit.get("bias", 0.0)),
            }
        )
    return decoded


# ---------------------------------------------------------------------
# Cascade-correlation forward pass
# ---------------------------------------------------------------------


def cascade_forward(
    inputs: np.ndarray,
    output_weights: np.ndarray,
    output_bias: np.ndarray,
    hidden_units: List[Dict[str, Any]],
) -> Optional[np.ndarray]:
    """Pure-numpy CasCor forward pass for a single sample's network state.

    Args:
        inputs: ``[N, in_size]`` query points (numpy float32).
        output_weights: ``[in_size + num_hidden, out_size]``.
        output_bias: ``[out_size]``.
        hidden_units: ordered cascade list. Each unit dict has:
          - ``weights``: ``[in_size + cascade_index]`` (numpy)
          - ``bias``: scalar float
          - ``activation``: one of the names in ``_ACTIVATIONS``.

    Returns:
        ``[N, out_size]`` predictions, or ``None`` if any required
        tensor is missing / shape-incompatible.

    Note: this is a separate implementation from cascor's
    ``CascadeCorrelationNetwork.forward`` (PyTorch) because canopy
    must compute decision boundaries from on-the-wire payloads
    without round-tripping through the backend. The two
    implementations agree on the cascade-correlation forward
    semantics — see the conformance test in
    ``test_replay_forward.py``.
    """
    if output_weights is None or output_bias is None:
        return None
    inputs = np.asarray(inputs, dtype=np.float32)
    if inputs.ndim != 2:
        return None

    n, in_size = inputs.shape
    num_hidden = len(hidden_units)
    expected_in = in_size + num_hidden
    if output_weights.shape[0] != expected_in:
        logger.warning(
            "replay_forward: output_weights shape %s does not match in+hidden=%d (in=%d, hidden=%d)",
            output_weights.shape,
            expected_in,
            in_size,
            num_hidden,
        )
        return None

    # ``activations[:, :in_size]`` is the input. Each hidden unit appends
    # one column. We allocate the full matrix up-front so cascade
    # connectivity ("each unit sees inputs + all earlier hidden units")
    # is a simple slice.
    activations = np.zeros((n, expected_in), dtype=np.float32)
    activations[:, :in_size] = inputs.astype(np.float32, copy=False)

    for i, unit in enumerate(hidden_units):
        unit_weights = unit.get("weights")
        unit_bias = float(unit.get("bias", 0.0))
        if unit_weights is None:
            return None
        unit_weights = np.asarray(unit_weights, dtype=np.float32)
        # The unit sees ``inputs + previously computed hidden outputs``,
        # i.e. ``activations[:, : in_size + i]``. Its weight vector has
        # length ``in_size + i`` to match.
        prev = activations[:, : in_size + i]
        if unit_weights.shape[0] != prev.shape[1]:
            logger.warning(
                "replay_forward: unit %d weight length %d does not match prev-output width %d",
                i,
                unit_weights.shape[0],
                prev.shape[1],
            )
            return None
        z = prev @ unit_weights + unit_bias
        act = _activation_for(unit.get("activation"))
        activations[:, in_size + i] = act(z)

    return activations @ output_weights + output_bias


# ---------------------------------------------------------------------
# Buffer helpers (used by the panel callbacks)
# ---------------------------------------------------------------------


def latest_sample_payload(buffer: Optional[List[Dict[str, Any]]]) -> Optional[Dict[str, Any]]:
    """Return the most-recent decoded payload from a replay-weight-buffer.

    Decoding is lazy — the buffer in the Store is the raw wire form
    (base64 strings); decoding to numpy on every scrubber tick avoids
    keeping a parallel decoded mirror that would double memory.
    """
    if not buffer:
        return None
    return decode_weight_payload(buffer[-1])
