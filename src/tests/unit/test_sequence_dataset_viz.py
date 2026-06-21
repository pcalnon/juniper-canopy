"""CANOPY-3D-1 — 3-D (sequence) dataset load + display (Phase 1).

Fixture-tested per the agreed plan: a mocked ``JuniperDataClient`` returns synthetic 3-D
NPZ artifacts (the real juniper-data path is the same dispatch, verified end-to-end
separately). Covers the ndim-aware load dispatch, the display-only sequence install, the
plotter's sequence render branch, and a 2-D regression guard.
"""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

import numpy as np


def _dt(n_windows: int, length: int) -> np.ndarray:
    rng = np.random.default_rng(0)
    a = rng.random((n_windows, length)).astype(np.float32)
    a[:, 0] = 0.0  # contract: first per-step Δt is 0
    return a


def _sequence_npz(n_windows: int = 5, length: int = 4, n_features: int = 2) -> dict:
    """Synthetic 3-D sequence NPZ (mirrors ``window_*_series``: dt-only, regression y)."""
    rng = np.random.default_rng(1)
    w_tr, w_te = 3, n_windows - 3

    def x(w):
        return rng.random((w, length, n_features)).astype(np.float32)

    def y(w):
        return rng.random((w, n_features)).astype(np.float32)

    return {
        "X_train": x(w_tr),
        "X_test": x(w_te),
        "X_full": x(n_windows),
        "y_train": y(w_tr),
        "y_test": y(w_te),
        "y_full": y(n_windows),
        "dt_train": _dt(w_tr, length),
        "dt_test": _dt(w_te, length),
        "dt_full": _dt(n_windows, length),
        "target_dt_train": np.ones(w_tr, np.float32),
        "target_dt_test": np.ones(w_te, np.float32),
        "target_dt_full": np.ones(n_windows, np.float32),
        "observed_mask_train": np.ones((w_tr, length), np.uint8),
        "observed_mask_test": np.ones((w_te, length), np.uint8),
        "observed_mask_full": np.ones((n_windows, length), np.uint8),
    }


def _tabular_npz(n: int = 10, n_features: int = 2, n_classes: int = 2) -> dict:
    rng = np.random.default_rng(2)
    onehot = np.eye(n_classes, dtype=np.float32)[rng.integers(0, n_classes, size=n)]
    return {"X_full": rng.random((n, n_features)).astype(np.float32), "y_full": onehot}


# ----------------------------------------------------------- DemoMode load (mocked deps)
def _bare_demo():
    from demo_mode import DemoMode

    demo = DemoMode.__new__(DemoMode)
    demo.logger = MagicMock()
    demo.is_running = False  # `running` is a read-only property over this
    demo._lock = threading.Lock()
    demo.dataset = {"inputs": [[0.0]], "targets": [0], "source": "old-tabular"}
    demo.current_epoch = 7
    demo.current_loss = 0.3
    demo.current_accuracy = 0.9
    demo.metrics_history = [{"epoch": 1}]
    demo.network = MagicMock()
    demo.network.train_x = "UNCHANGED-X"
    demo.network.train_y = "UNCHANGED-Y"
    return demo


def test_install_sequence_dataset_is_display_only():
    demo = _bare_demo()
    out = demo._install_sequence_dataset(_sequence_npz(5, 4, 2), source_label="generator:irregular_sine")

    assert out["dataset_kind"] == "sequence"
    assert (out["n_windows"], out["lookback"], out["n_features"]) == (5, 4, 2)
    # JSON-serializable window 0: nested lists (L, F), not ndarrays
    assert isinstance(out["sequence"]["X"], list) and isinstance(out["sequence"]["X"][0], list)
    assert len(out["sequence"]["X"]) == 4 and len(out["sequence"]["X"][0]) == 2
    assert isinstance(out["sequence"]["dt"], list) and len(out["sequence"]["dt"]) == 4
    assert out["sequence"]["feature_labels"] == ["Feature 0", "Feature 1"]
    # installed as the visible dataset, and NOT wired into the trainer (display-only / OQ-4)
    assert demo.dataset is out
    assert demo.network.train_x == "UNCHANGED-X"
    assert demo.network.train_y == "UNCHANGED-Y"


def _run_regenerate(npz: dict, generator: str):
    demo = _bare_demo()
    demo._install_sequence_dataset = MagicMock(return_value={"dataset_kind": "sequence"})
    demo.import_dataset = MagicMock(return_value={"dataset_kind": "tabular"})
    demo._validate_npz_arrays = MagicMock(return_value=None)
    client = MagicMock()
    client.create_dataset.return_value = {"dataset_id": "ds-test"}
    client.download_artifact_npz.return_value = npz
    settings = MagicMock(juniper_data_url="http://test", juniper_data_api_key=None)
    with patch("juniper_data_client.JuniperDataClient", return_value=client), patch("demo_mode.get_settings", return_value=settings), patch("observability.build_data_client_request_hook", return_value=None):
        result = demo.regenerate_dataset_from_generator(generator)
    return demo, result


def test_regenerate_dispatches_sequence_to_display_only():
    demo, result = _run_regenerate(_sequence_npz(), "irregular_sine")
    demo._install_sequence_dataset.assert_called_once()
    demo.import_dataset.assert_not_called()
    assert result["dataset_kind"] == "sequence"


def test_regenerate_dispatches_tabular_to_import():
    demo, result = _run_regenerate(_tabular_npz(), "xor")
    demo.import_dataset.assert_called_once()
    demo._install_sequence_dataset.assert_not_called()
    assert result["dataset_kind"] == "tabular"


# ----------------------------------------------------------------- plotter sequence branch
def _bare_plotter():
    from frontend.components.dataset_plotter import DatasetPlotter

    plotter = DatasetPlotter.__new__(DatasetPlotter)
    plotter.default_colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]
    return plotter


def test_plotter_renders_sequence_branch():
    import plotly.graph_objects as go

    plotter = _bare_plotter()
    dataset = {
        "dataset_kind": "sequence",
        "n_windows": 5,
        "n_features": 2,
        "sequence": {
            "X": [[0.1, 0.2], [0.3, 0.5], [0.2, 0.4], [0.6, 0.1]],  # (L=4, F=2)
            "dt": [0.0, 1.0, 0.5, 2.0],
            "feature_labels": ["Feature 0", "Feature 1"],
        },
    }
    scatter_fig, dist_fig, n_samples, n_features, n_classes, balance = plotter._process_dataset_update(dataset, "all", "light")

    assert isinstance(scatter_fig, go.Figure) and len(scatter_fig.data) == 2  # one trace per feature
    assert isinstance(dist_fig, go.Figure) and len(dist_fig.data) == 1  # the Δt strip
    assert (n_samples, n_features, n_classes, balance) == ("5", "2", "0", "N/A")


def test_plotter_sequence_empty_is_graceful():
    plotter = _bare_plotter()
    scatter_fig, dist_fig, *_ = plotter._process_dataset_update({"dataset_kind": "sequence", "n_windows": 0, "n_features": 0, "sequence": {}}, "all", "light")
    # no data -> empty plots, no crash
    assert scatter_fig is not None and dist_fig is not None


# ----------------------------------------------------- Phase 2a: compare-signals controls
def _seq_dataset_3feat() -> dict:
    """A window-0 sequence view with 3 mixed-scale signals (OHLCV-flavoured)."""
    return {
        "dataset_kind": "sequence",
        "n_windows": 4,
        "n_features": 3,
        "sequence": {
            "X": [[0.1, 0.2, 0.9], [0.3, 0.5, 0.7], [0.2, 0.4, 0.8], [0.6, 0.1, 0.5]],  # (L=4, F=3)
            "dt": [0.0, 1.0, 0.5, 2.0],
            "feature_labels": ["Open", "Close", "Volume"],
        },
    }


def test_plotter_sequence_signal_filter_selects_subset():
    plotter = _bare_plotter()
    fig, *_ = plotter._process_dataset_update(_seq_dataset_3feat(), "all", "light", [1], "overlay")
    assert len(fig.data) == 1
    assert fig.data[0].name == "Close"


def test_plotter_sequence_signal_filter_out_of_range_falls_back_to_all():
    plotter = _bare_plotter()
    # Stale selection (indices from a larger prior dataset) -> guard falls back to all 3.
    fig, *_ = plotter._process_dataset_update(_seq_dataset_3feat(), "all", "light", [7, 9], "small_multiples")
    assert len(fig.data) == 3


def test_plotter_sequence_overlay_vs_small_multiple_offset():
    plotter = _bare_plotter()
    ds = _seq_dataset_3feat()
    sm, *_ = plotter._process_dataset_update(ds, "all", "light", None, "small_multiples")
    ov, *_ = plotter._process_dataset_update(ds, "all", "light", None, "overlay")
    sm_max = max(float(max(tr.y)) for tr in sm.data)
    ov_max = max(float(max(tr.y)) for tr in ov.data)
    # small-multiples vertically offsets each signal (3 signals -> top offset 2*1.15);
    # overlay shares one normalized [0, 1] axis (no offset).
    assert sm_max > 1.5
    assert ov_max <= 1.2
    assert len(sm.data) == 3 and len(ov.data) == 3


def test_sequence_signal_options_population():
    plotter = _bare_plotter()
    opts, val = plotter._sequence_signal_options(_seq_dataset_3feat())
    assert [o["value"] for o in opts] == [0, 1, 2]
    assert [o["label"] for o in opts] == ["Open", "Close", "Volume"]
    assert val == [0, 1, 2]  # default: all signals selected


def test_sequence_signal_options_empty_for_tabular_and_none():
    plotter = _bare_plotter()
    opts, val = plotter._sequence_signal_options({"dataset_kind": "tabular"})
    assert opts == [] and val is None
    opts2, val2 = plotter._sequence_signal_options(None)
    assert opts2 == [] and val2 is None
