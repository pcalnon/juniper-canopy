#!/usr/bin/env python
"""Per-file coverage-gate tests for ``frontend.components.network_evolution``.

The baseline suite covers the grid renderer but not the two callback
closures nor the ``_render_weight_norms`` sparkline builder. This drives
both callbacks through a stub app and feeds ``_render_weight_norms`` a
hand-encoded replay buffer that exercises every branch: non-dict entries,
missing epochs, ``None`` output tensors, late-appearing units (leading
``None`` pad) and dropped units (trailing ``None`` pad).
"""

import base64

import numpy as np
import plotly.graph_objects as go
import pytest

from frontend.components.network_evolution import NetworkEvolution


def _enc(values):
    """Encode a float32 array into the ``{dtype, shape, data}`` envelope
    that ``replay_forward.decode_tensor`` consumes."""
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
    return NetworkEvolution({}, component_id="ne-gate")


@pytest.fixture
def callbacks(panel):
    app = _StubApp()
    panel.register_callbacks(app)
    return {fn.__name__: fn for _, _, fn in app.callbacks}


class TestRenderGridCallback:
    def test_empty_snapshots_shows_placeholder(self, callbacks):
        grid, stats = callbacks["render_grid"](None, None)
        assert stats == "No snapshots yet"

    def test_snapshots_render_cards(self, callbacks):
        snaps = [
            {"epoch": 2, "input_units": 2, "hidden_units": 3, "output_units": 1},
            {"epoch": 1, "input_units": 2, "hidden_units": 1, "output_units": 1},
        ]
        cards, stats = callbacks["render_grid"](snaps, "dark")
        assert isinstance(cards, list)
        assert len(cards) == 2
        assert "2 of" in stats


class TestRenderWeightNormsCallback:
    def test_empty_buffer_hides_container(self, callbacks):
        style, fig = callbacks["render_weight_norms"](None, None)
        assert style == {"display": "none"}
        assert isinstance(fig, go.Figure)

    def test_full_buffer_builds_traces(self, callbacks):
        buffer = [
            "not-a-dict",  # skipped (non-dict entry)
            {"no_epoch": True},  # skipped (epoch not numeric)
            {
                "epoch": 1,
                "output_weights": _enc([0.1, 0.2, 0.3]),
                "hidden_units": [{"weights": _enc([0.5, 0.6])}],  # unit 0
            },
            {
                "epoch": 2,
                "output_weights": None,  # -> NaN norm branch
                "hidden_units": [
                    {"weights": _enc([0.5, 0.6])},  # unit 0
                    {"weights": _enc([0.1])},  # unit 1 appears late -> leading None pad
                ],
            },
            {
                "epoch": 3,
                "output_weights": _enc([0.1, 0.2]),
                "hidden_units": [{"weights": _enc([0.5, 0.6])}],  # unit 1 dropped -> trailing None pad
            },
            {
                "epoch": 4,
                "output_weights": _enc([0.9]),
                "hidden_units": [{"weights": None}, "not-a-dict"],  # both skipped
            },
        ]
        style, fig = callbacks["render_weight_norms"](buffer, "dark")
        assert style["display"] == "block"
        # One output-layer trace + one trace per hidden unit index (2 units seen).
        assert len(fig.data) == 3
        names = {t.name for t in fig.data}
        assert "output layer" in names
        assert "unit 0" in names
        assert "unit 1" in names


class TestRenderWeightNormsDirect:
    def test_empty_direct_call(self, panel):
        style, fig = panel._render_weight_norms([], "light")
        assert style == {"display": "none"}
        assert isinstance(fig, go.Figure)

    def test_light_theme_single_unit(self, panel):
        buffer = [{"epoch": 5, "output_weights": _enc([1.0, 2.0]), "hidden_units": [{"weights": _enc([0.3])}]}]
        style, fig = panel._render_weight_norms(buffer, "light")
        assert style["display"] == "block"
        assert len(fig.data) == 2
