#!/usr/bin/env python
"""Unit tests for replay_forward (CAN-015g g-7).

Covers:
- ``decode_tensor`` round-trip for each supported dtype + handling
  of malformed envelopes.
- ``decode_weight_payload`` shape preservation.
- ``cascade_forward`` correctness:
    - identity case (no hidden units → linear output).
    - single hidden unit with each supported activation.
    - multi-unit cascade — each unit sees inputs + earlier units.
    - shape-mismatch returns None instead of raising.
- ``latest_sample_payload`` returns the buffer tail.

The cascade-correlation forward pass is a duplicated implementation
of cascor's PyTorch model — these tests pin its behaviour against
hand-computed reference values so a future drift in cascor's
forward semantics gets caught.
"""

from __future__ import annotations

import base64
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from frontend.replay_forward import (  # noqa: E402
    cascade_forward,
    decode_tensor,
    decode_weight_payload,
    latest_sample_payload,
)

pytestmark = pytest.mark.unit


def _envelope(arr, dtype="float32"):
    """Build a wire-format tensor envelope."""
    arr = np.asarray(arr, dtype=dtype)
    return {
        "dtype": dtype,
        "shape": list(arr.shape),
        "data": base64.b64encode(arr.tobytes()).decode("ascii"),
    }


# =============================================================================
# decode_tensor
# =============================================================================


class TestDecodeTensor:
    def test_round_trip_float32(self):
        original = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32)
        decoded = decode_tensor(_envelope(original))
        np.testing.assert_array_equal(decoded, original)

    def test_round_trip_1d(self):
        original = np.array([0.5, -0.25, 0.0, 1.5], dtype=np.float32)
        decoded = decode_tensor(_envelope(original))
        np.testing.assert_array_equal(decoded, original)

    def test_returns_none_on_missing_envelope(self):
        assert decode_tensor(None) is None
        assert decode_tensor({}) is None

    def test_returns_none_on_missing_data(self):
        assert decode_tensor({"dtype": "float32", "shape": [2]}) is None

    def test_returns_none_on_missing_shape(self):
        env = _envelope([1.0, 2.0])
        env.pop("shape")
        assert decode_tensor(env) is None

    def test_returns_none_on_corrupt_base64(self):
        env = {"dtype": "float32", "shape": [4], "data": "!!!not-base64!!!"}
        assert decode_tensor(env) is None

    def test_decoded_array_is_writable(self):
        # ``np.frombuffer`` returns a non-writable view; decode_tensor
        # must copy so consumers can compose without surprises.
        decoded = decode_tensor(_envelope([1.0, 2.0, 3.0]))
        decoded[0] = 99.0  # must not raise
        assert decoded[0] == 99.0


# =============================================================================
# decode_weight_payload
# =============================================================================


class TestDecodeWeightPayload:
    def test_full_payload_round_trip(self):
        ow = np.array([[0.5], [0.25], [-0.1]], dtype=np.float32)
        ob = np.array([0.0], dtype=np.float32)
        unit_w = np.array([1.0, 0.5], dtype=np.float32)
        wire = {
            "sample_index": 3,
            "epoch": 30,
            "output_weights": _envelope(ow),
            "output_bias": _envelope(ob),
            "hidden_units": [
                {
                    "first_sample_index": 1,
                    "activation": "tanh",
                    "weights": _envelope(unit_w),
                    "bias": 0.123,
                },
            ],
        }
        decoded = decode_weight_payload(wire)
        assert decoded["sample_index"] == 3
        assert decoded["epoch"] == 30
        np.testing.assert_array_equal(decoded["output_weights"], ow)
        np.testing.assert_array_equal(decoded["output_bias"], ob)
        assert len(decoded["hidden_units"]) == 1
        np.testing.assert_array_equal(decoded["hidden_units"][0]["weights"], unit_w)
        assert decoded["hidden_units"][0]["bias"] == pytest.approx(0.123)
        assert decoded["hidden_units"][0]["activation"] == "tanh"

    def test_none_input(self):
        assert decode_weight_payload(None) is None

    def test_missing_fields_default_safely(self):
        decoded = decode_weight_payload({"hidden_units": []})
        assert decoded["sample_index"] == 0
        assert decoded["epoch"] == 0
        assert decoded["output_weights"] is None
        assert decoded["output_bias"] is None
        assert decoded["hidden_units"] == []


# =============================================================================
# cascade_forward
# =============================================================================


class TestCascadeForward:
    def test_no_hidden_units_is_linear(self):
        # No hidden units → output = inputs @ output_weights + output_bias
        inputs = np.array([[1.0, 0.5], [-1.0, 2.0]], dtype=np.float32)
        ow = np.array([[2.0], [-1.0]], dtype=np.float32)
        ob = np.array([0.5], dtype=np.float32)
        result = cascade_forward(inputs, ow, ob, [])
        expected = inputs @ ow + ob
        np.testing.assert_allclose(result, expected, rtol=1e-6)

    def test_single_tanh_unit(self):
        inputs = np.array([[0.0, 0.0]], dtype=np.float32)
        # Unit 0 sees [in1, in2] = [0, 0], weights [1, -1], bias 0.5.
        # Pre-activation = 0 + 0 + 0.5 = 0.5; tanh(0.5).
        unit = {
            "weights": np.array([1.0, -1.0], dtype=np.float32),
            "bias": 0.5,
            "activation": "tanh",
        }
        # Output layer sees [in1, in2, h1] of width 3.
        ow = np.array([[0.0], [0.0], [1.0]], dtype=np.float32)
        ob = np.array([0.0], dtype=np.float32)
        result = cascade_forward(inputs, ow, ob, [unit])
        expected = np.array([[np.tanh(0.5)]], dtype=np.float32)
        np.testing.assert_allclose(result, expected, rtol=1e-6)

    def test_relu_activation(self):
        inputs = np.array([[1.0]], dtype=np.float32)
        # Unit pre-activation = -2.0; relu(-2.0) = 0.
        unit = {"weights": np.array([-2.0], dtype=np.float32), "bias": 0.0, "activation": "relu"}
        ow = np.array([[0.0], [1.0]], dtype=np.float32)
        ob = np.array([0.0], dtype=np.float32)
        result = cascade_forward(inputs, ow, ob, [unit])
        np.testing.assert_allclose(result, np.array([[0.0]]), atol=1e-7)

    def test_cascade_connectivity(self):
        # Unit 1 must see input + unit 0's output, NOT just input.
        # If connectivity were broken, the second unit would see only
        # inputs and its weight vector would have length 1 (in_size),
        # not 2 (in_size + 1).
        inputs = np.array([[1.0]], dtype=np.float32)
        unit0 = {"weights": np.array([2.0], dtype=np.float32), "bias": 0.0, "activation": "tanh"}
        # unit1 weights have length 2: [input, unit0_output].
        unit1 = {"weights": np.array([0.0, 1.0], dtype=np.float32), "bias": 0.0, "activation": "linear"}
        # Output layer sees [input, h0, h1]
        ow = np.array([[0.0], [0.0], [1.0]], dtype=np.float32)
        ob = np.array([0.0], dtype=np.float32)
        result = cascade_forward(inputs, ow, ob, [unit0, unit1])
        expected = np.array([[np.tanh(2.0)]], dtype=np.float32)
        np.testing.assert_allclose(result, expected, rtol=1e-6)

    def test_unknown_activation_falls_back_to_identity(self):
        inputs = np.array([[1.0]], dtype=np.float32)
        unit = {"weights": np.array([3.0], dtype=np.float32), "bias": 0.0, "activation": "exotic_unknown"}
        ow = np.array([[0.0], [1.0]], dtype=np.float32)
        ob = np.array([0.0], dtype=np.float32)
        result = cascade_forward(inputs, ow, ob, [unit])
        # Identity → output = pre-activation = 3.0
        np.testing.assert_allclose(result, np.array([[3.0]]), rtol=1e-6)

    def test_shape_mismatch_returns_none(self):
        inputs = np.array([[1.0, 2.0]], dtype=np.float32)
        # output_weights shape [2, 1] but expected [in_size + num_hidden, out] = [2, 1]
        # is fine; force a real mismatch by adding a hidden unit but
        # leaving output_weights undersized.
        ow = np.array([[1.0], [1.0]], dtype=np.float32)  # only 2 rows for 1 output
        ob = np.array([0.0], dtype=np.float32)
        unit = {"weights": np.array([1.0, 1.0], dtype=np.float32), "bias": 0.0, "activation": "tanh"}
        # With one hidden unit, output_weights should be [3, 1]; passing [2, 1] → None.
        assert cascade_forward(inputs, ow, ob, [unit]) is None

    def test_unit_weight_length_mismatch_returns_none(self):
        inputs = np.array([[1.0, 2.0]], dtype=np.float32)
        # Unit 0 should have weight length 2 (in_size=2). Pass length 3 → None.
        unit = {"weights": np.array([1.0, 1.0, 1.0], dtype=np.float32), "bias": 0.0, "activation": "tanh"}
        ow = np.array([[0.0], [0.0], [1.0]], dtype=np.float32)
        ob = np.array([0.0], dtype=np.float32)
        assert cascade_forward(inputs, ow, ob, [unit]) is None

    def test_missing_output_returns_none(self):
        assert cascade_forward(np.array([[1.0]]), None, np.array([0.0]), []) is None
        assert cascade_forward(np.array([[1.0]]), np.array([[1.0]]), None, []) is None

    def test_1d_inputs_returns_none(self):
        # Caller must provide 2-D ``[N, in_size]`` even for N=1.
        assert cascade_forward(np.array([1.0, 2.0]), np.array([[1.0], [1.0]]), np.array([0.0]), []) is None


# =============================================================================
# Buffer helpers
# =============================================================================


class TestBufferHelpers:
    def test_latest_sample_payload_returns_tail(self):
        buffer = [
            {
                "sample_index": 0,
                "epoch": 0,
                "output_weights": _envelope([[1.0]]),
                "output_bias": _envelope([0.0]),
                "hidden_units": [],
            },
            {
                "sample_index": 1,
                "epoch": 50,
                "output_weights": _envelope([[2.0]]),
                "output_bias": _envelope([0.0]),
                "hidden_units": [],
            },
        ]
        latest = latest_sample_payload(buffer)
        assert latest["sample_index"] == 1
        assert latest["epoch"] == 50

    def test_empty_buffer_returns_none(self):
        assert latest_sample_payload([]) is None
        assert latest_sample_payload(None) is None
