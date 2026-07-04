#!/usr/bin/env python
"""Per-file coverage-gate tests for ``frontend.components.decision_boundary``.

Targets the replay-boundary path the baseline suite skips: the
``update_boundary_from_replay`` callback guard chain and the
``_compute_replay_boundary`` grid computation (multi-class argmax,
single-column, None-prediction, and shape-mismatch branches).
"""

import base64

import dash
import numpy as np
import pytest

from frontend.components.decision_boundary import DecisionBoundary


def _enc(values):
    arr = np.asarray(values, dtype=np.float32)
    return {"dtype": "float32", "shape": list(arr.shape), "data": base64.b64encode(arr.tobytes()).decode("ascii")}


class _StubApp:
    def __init__(self):
        self.callbacks = []

    def callback(self, *outputs, **kwargs):
        def decorator(fn):
            self.callbacks.append((outputs, kwargs, fn))
            return fn

        return decorator


@pytest.fixture
def panel():
    # Small resolution keeps the meshgrid cheap (5x5 grid).
    return DecisionBoundary({"boundary_resolution": 5}, component_id="db-gate")


@pytest.fixture
def callbacks(panel):
    app = _StubApp()
    panel.register_callbacks(app)
    return {fn.__name__: fn for _, _, fn in app.callbacks}


_DATASET = {"inputs": [[0.0, 0.0], [1.0, 1.0], [-1.0, -1.0], [0.5, -0.5]]}


def _multiclass_payload():
    return {
        "sample_index": 0,
        "epoch": 1,
        "output_weights": np.array([[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]], dtype=np.float32),
        "output_bias": np.array([0.0, 0.0, 0.0], dtype=np.float32),
        "hidden_units": [],
    }


class TestUpdateBoundaryFromReplayCallback:
    def test_empty_buffer_no_update(self, callbacks):
        assert callbacks["update_boundary_from_replay"](None, {"snapshot_id": "s"}, _DATASET) is dash.no_update

    def test_session_without_snapshot_id_no_update(self, callbacks):
        assert callbacks["update_boundary_from_replay"]([{"x": 1}], {}, _DATASET) is dash.no_update

    def test_no_dataset_no_update(self, callbacks):
        assert callbacks["update_boundary_from_replay"]([{"x": 1}], {"snapshot_id": "s"}, None) is dash.no_update

    def test_undecodable_payload_no_update(self, callbacks):
        # buffer[-1] is falsy -> decode_weight_payload returns None.
        result = callbacks["update_boundary_from_replay"]([None], {"snapshot_id": "s"}, _DATASET)
        assert result is dash.no_update

    def test_valid_payload_computes_boundary(self, callbacks):
        raw = {
            "sample_index": 0,
            "epoch": 3,
            "output_weights": _enc([[0.1, 0.2], [0.3, 0.4]]),
            "output_bias": _enc([0.0, 0.0]),
            "hidden_units": [],
        }
        result = callbacks["update_boundary_from_replay"]([raw], {"snapshot_id": "s"}, _DATASET)
        assert isinstance(result, dict)
        assert "Z" in result
        assert "bounds" in result
        assert result["replay_sample"]["epoch"] == 3


class TestComputeReplayBoundary:
    def test_bad_inputs_dimension_returns_empty(self, panel):
        assert panel._compute_replay_boundary({"inputs": [1, 2, 3]}, _multiclass_payload()) == {}

    def test_single_feature_inputs_returns_empty(self, panel):
        assert panel._compute_replay_boundary({"inputs": [[1.0], [2.0]]}, _multiclass_payload()) == {}

    def test_multiclass_argmax_branch(self, panel):
        result = panel._compute_replay_boundary(_DATASET, _multiclass_payload())
        assert set(result) >= {"xx", "yy", "Z", "bounds", "replay_sample"}
        z = np.array(result["Z"])
        assert z.shape == (5, 5)
        # argmax over 3 columns -> class indices in {0,1,2}.
        assert set(np.unique(z)).issubset({0, 1, 2})

    def test_single_column_branch(self, panel):
        payload = {
            "sample_index": 2,
            "epoch": 9,
            "output_weights": np.array([[0.5], [0.5]], dtype=np.float32),
            "output_bias": np.array([0.0], dtype=np.float32),
            "hidden_units": [],
        }
        result = panel._compute_replay_boundary(_DATASET, payload)
        assert np.array(result["Z"]).shape == (5, 5)
        assert result["replay_sample"]["sample_index"] == 2

    def test_none_predictions_returns_empty(self, panel):
        # output_weights None -> cascade_forward returns None -> {} .
        payload = {"output_weights": None, "output_bias": None, "hidden_units": [], "sample_index": 0, "epoch": 0}
        assert panel._compute_replay_boundary(_DATASET, payload) == {}

    def test_one_d_predictions_branch(self, panel):
        # Force cascade_forward to yield a 1-D prediction array to hit the
        # ndim==1 else branch. 25 = resolution^2 grid points.
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "frontend.components.decision_boundary.cascade_forward",
                lambda *a, **k: np.zeros(25, dtype=np.float32),
            )
            result = panel._compute_replay_boundary(_DATASET, _multiclass_payload())
        assert np.array(result["Z"]).shape == (5, 5)
