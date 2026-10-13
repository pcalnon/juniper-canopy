#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_demo_backend_gate_coverage.py
# Author:        Paul Calnon
# License:       MIT License
# Description:   Per-file coverage-gate tests for backend.demo_backend
#####################################################################
"""Statement-coverage tests for ``DemoBackend``.

``DemoBackend`` is a thin adapter over ``DemoMode``. The existing
``test_demo_backend.py`` drives it against a real ``DemoMode`` and covers
the happy paths, but leaves the ``None``-network early returns, the
metrics-history truncation, the non-dict ``apply_params`` fallback, and
the Issue-#3 pass-through methods uncovered. These tests use a mocked
``DemoMode`` so each delegating branch is exercised directly with a
meaningful assertion.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest

from backend.demo_backend import DemoBackend


class _Scalar:
    """Minimal tensor-like scalar exposing ``.item()`` (matches DemoMode weights)."""

    def __init__(self, value):
        self._value = value

    def item(self):
        return self._value


def _fake_network():
    """A hand-built network with one hidden unit for get_raw_topology()."""
    output_weight = np.array([[0.11, 0.22, 0.33]], dtype=float)  # (output=1, inputs+hidden=3)
    return SimpleNamespace(
        input_size=2,
        output_size=1,
        hidden_units=[{"weights": [_Scalar(0.1), _Scalar(0.2), _Scalar(0.3)], "bias": 0.5, "activation": "sigmoid"}],
        output_layer=SimpleNamespace(
            weight=SimpleNamespace(data=output_weight),
            bias=SimpleNamespace(data=[_Scalar(0.0)]),
        ),
    )


@pytest.fixture
def demo():
    return MagicMock()


@pytest.fixture
def backend(demo):
    return DemoBackend(demo)


@pytest.mark.unit
class TestMetricsHistoryTruncation:
    def test_history_truncated_to_count(self, backend, demo):
        demo.get_metrics_history.return_value = [{"epoch": i} for i in range(5)]
        result = backend.get_metrics_history(count=2)
        assert result == [{"epoch": 3}, {"epoch": 4}]

    def test_history_untruncated_when_short(self, backend, demo):
        demo.get_metrics_history.return_value = [{"epoch": 0}]
        assert backend.get_metrics_history(count=100) == [{"epoch": 0}]


@pytest.mark.unit
class TestNoneNetworkEarlyReturns:
    def test_network_topology_none_when_no_network(self, backend, demo):
        demo.get_network.return_value = None
        assert backend.get_network_topology() is None

    def test_raw_topology_none_when_no_network(self, backend, demo):
        demo.get_network.return_value = None
        assert backend.get_raw_topology() is None

    def test_decision_boundary_none_when_no_network(self, backend, demo):
        demo.get_network.return_value = None
        assert backend.get_decision_boundary() is None

    def test_decision_boundary_none_when_dataset_missing_inputs(self, backend, demo):
        demo.get_network.return_value = MagicMock()
        demo.get_dataset.return_value = {"num_samples": 5}  # no "inputs" key
        assert backend.get_decision_boundary() is None

    def test_get_dataset_none_when_demo_returns_none(self, backend, demo):
        demo.get_dataset.return_value = None
        assert backend.get_dataset() is None


@pytest.mark.unit
class TestRawTopologyWithHiddenUnit:
    def test_raw_topology_serializes_hidden_units(self, backend, demo):
        demo.get_network.return_value = _fake_network()

        result = backend.get_raw_topology()

        assert result["input_size"] == 2
        assert result["output_size"] == 1
        assert len(result["hidden_units"]) == 1
        unit = result["hidden_units"][0]
        assert unit["weights"] == [0.1, 0.2, 0.3]
        assert unit["bias"] == 0.5
        assert unit["activation"] == "sigmoid"
        # output_weights is column-major: 3 columns (2 inputs + 1 hidden), 1 row each.
        assert result["output_weights"] == [[0.11], [0.22], [0.33]]
        assert result["output_bias"] == [0.0]


@pytest.mark.unit
class TestRegeneration:
    def test_regenerate_dataset_delegates_and_refetches(self, backend, demo):
        demo.get_dataset.return_value = {"num_samples": 10, "num_features": 2, "num_classes": 2}
        result = backend.regenerate_dataset(n_samples=10, n_spirals=3, noise=0.2, n_rotations=2.0)

        demo.regenerate_dataset.assert_called_once_with(n_samples=10, n_spirals=3, noise=0.2, n_rotations=2.0)
        assert result["num_samples"] == 10

    def test_regenerate_from_generator_delegates_and_refetches(self, backend, demo):
        demo.get_dataset.return_value = {"num_samples": 20, "num_features": 2, "num_classes": 2}
        result = backend.regenerate_dataset_from_generator(generator="xor", n_samples=20)

        demo.regenerate_dataset_from_generator.assert_called_once_with(generator="xor", n_samples=20)
        assert result["num_samples"] == 20


@pytest.mark.unit
class TestApplyParamsFallback:
    def test_non_dict_result_returns_ok_envelope(self, backend, demo):
        demo.apply_params.return_value = "not-a-dict"
        result = backend.apply_params(nn_learning_rate=0.5)
        assert result == {"ok": True, "data": {"nn_learning_rate": 0.5}}

    def test_dict_result_passed_through(self, backend, demo):
        demo.apply_params.return_value = {"ok": True, "applied": {"lr": 0.1}}
        result = backend.apply_params(nn_learning_rate=0.1)
        assert result == {"ok": True, "applied": {"lr": 0.1}}


@pytest.mark.unit
class TestPassThroughs:
    """Each Issue-#3 method delegates 1:1 to the wrapped DemoMode."""

    def test_stage_dataset(self, backend, demo):
        demo.stage_dataset.return_value = {"ok": True, "config": {"n_samples": 5}}
        result = backend.stage_dataset(nn_dataset_elements=5)
        demo.stage_dataset.assert_called_once_with(nn_dataset_elements=5)
        assert result == {"ok": True, "config": {"n_samples": 5}}

    def test_cancel_pending_dataset(self, backend, demo):
        demo.cancel_pending_dataset.return_value = {"ok": True}
        assert backend.cancel_pending_dataset() == {"ok": True}
        demo.cancel_pending_dataset.assert_called_once_with()

    def test_get_pending_dataset(self, backend, demo):
        demo.get_pending_dataset.return_value = {"ok": True, "pending": None}
        assert backend.get_pending_dataset() == {"ok": True, "pending": None}
        demo.get_pending_dataset.assert_called_once_with()

    def test_get_experimental_functions(self, backend, demo):
        demo.get_experimental_functions.return_value = {"enabled": False}
        assert backend.get_experimental_functions() == {"enabled": False}
        demo.get_experimental_functions.assert_called_once_with()

    def test_set_experimental_functions(self, backend, demo):
        demo.set_experimental_functions.return_value = {"enabled": True}
        assert backend.set_experimental_functions(True) == {"enabled": True}
        demo.set_experimental_functions.assert_called_once_with(True)

    def test_swap_dataset_live(self, backend, demo):
        demo.swap_dataset_live.return_value = {"ok": True, "swapped": True}
        result = backend.swap_dataset_live(nn_dataset_type="xor")
        demo.swap_dataset_live.assert_called_once_with(nn_dataset_type="xor")
        assert result == {"ok": True, "swapped": True}

    def test_cancel_swap_dataset_live(self, backend, demo):
        demo.cancel_swap_dataset_live.return_value = {"ok": True}
        assert backend.cancel_swap_dataset_live() == {"ok": True}
        demo.cancel_swap_dataset_live.assert_called_once_with()

    def test_get_dataset_swap_events(self, backend, demo):
        demo.get_dataset_swap_events.return_value = {"events": []}
        assert backend.get_dataset_swap_events(since="2026-01-01") == {"events": []}
        demo.get_dataset_swap_events.assert_called_once_with(since="2026-01-01")

    def test_get_snapshot_dataset_swaps(self, backend, demo):
        demo.get_snapshot_dataset_swaps.return_value = {"snapshot_id": "s1", "swaps": []}
        assert backend.get_snapshot_dataset_swaps("s1") == {"snapshot_id": "s1", "swaps": []}
        demo.get_snapshot_dataset_swaps.assert_called_once_with(snapshot_id="s1")
