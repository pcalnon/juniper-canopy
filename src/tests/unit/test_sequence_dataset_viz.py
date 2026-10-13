"""CANOPY-3D-1/2 — 3-D (sequence) dataset load + display (Phases 1, 2a, 2b, 2c, 3).

Fixture-tested per the agreed plan: a mocked ``JuniperDataClient`` returns synthetic 3-D
NPZ artifacts (the real juniper-data path is the same dispatch, verified end-to-end
separately). Covers the ndim-aware load dispatch, the display-only sequence install
(window-0 view + the capped multi-window store + per-window target + characterization
histograms), the plotter's two comparison modes (compare-signals / compare-windows,
small-multiples ⇄ overlay), the selector-options helpers, the target / characterization
companions, the advanced full-cross grid, and a 2-D regression guard.

The final section covers the post-decision-11 whole-dataset assembly (S-6): a sequence
artifact minted after juniper-data#369 carries no ``*_full`` family, and the install used
to fall back to the ``_train`` partition alone while reporting whole-dataset counts.
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


# --------------------------------------------- Phase 2b: compare-windows + multi-window
def _seq_dataset_multiwindow(n_windows: int = 4, length: int = 4, n_features: int = 2) -> dict:
    """A sequence view with multiple stored windows (``windows_X`` / ``windows_dt``)."""
    rng = np.random.default_rng(7)
    windows_X = [rng.random((length, n_features)).round(3).tolist() for _ in range(n_windows)]
    windows_dt = []
    for _ in range(n_windows):
        d = rng.random(length).round(3)
        d[0] = 0.0  # contract: first per-step Δt is 0
        windows_dt.append(d.tolist())
    return {
        "dataset_kind": "sequence",
        "n_windows": n_windows,
        "n_windows_stored": n_windows,
        "n_features": n_features,
        "sequence": {
            "X": windows_X[0],
            "dt": windows_dt[0],
            "feature_labels": [f"Feature {i}" for i in range(n_features)],
            "windows_X": windows_X,
            "windows_dt": windows_dt,
        },
    }


def test_install_caps_and_stores_multiple_windows():
    demo = _bare_demo()
    out = demo._install_sequence_dataset(_sequence_npz(5, 4, 2), source_label="generator:irregular_sine")
    seq = out["sequence"]
    assert out["n_windows_stored"] == 5  # all 5 fit under the cap
    assert len(seq["windows_X"]) == 5 and len(seq["windows_dt"]) == 5
    assert len(seq["windows_X"][0]) == 4 and len(seq["windows_X"][0][0]) == 2  # (L=4, F=2)
    # the default single view mirrors window 0
    assert seq["X"] == seq["windows_X"][0] and seq["dt"] == seq["windows_dt"][0]


def test_install_caps_window_payload_at_50():
    demo = _bare_demo()
    out = demo._install_sequence_dataset(_sequence_npz(60, 3, 1), source_label="big")
    assert out["n_windows"] == 60  # true window count preserved
    assert out["n_windows_stored"] == 50  # payload capped
    assert len(out["sequence"]["windows_X"]) == 50


def test_plotter_windows_mode_compares_selected_windows():
    plotter = _bare_plotter()
    ds = _seq_dataset_multiwindow(n_windows=4, length=4, n_features=2)
    # windows mode: one signal (0), three selected windows -> one trace per window.
    fig, *_ = plotter._process_dataset_update(ds, "all", "light", None, "small_multiples", "windows", None, 0, [0, 1, 2])
    assert len(fig.data) == 3
    assert [tr.name for tr in fig.data] == ["Window 0", "Window 1", "Window 2"]


def test_plotter_windows_mode_default_selection_first_few():
    plotter = _bare_plotter()
    ds = _seq_dataset_multiwindow(n_windows=5, length=4, n_features=2)
    # no windows selected -> the first few (<= 3).
    fig, *_ = plotter._process_dataset_update(ds, "all", "light", None, "overlay", "windows", None, 1, None)
    assert [tr.name for tr in fig.data] == ["Window 0", "Window 1", "Window 2"]


def test_plotter_signals_mode_respects_window_selection():
    plotter = _bare_plotter()
    ds = _seq_dataset_multiwindow(n_windows=3, length=4, n_features=2)
    # signals mode, window 2 -> plot uses window 2's data; both signals -> 2 traces.
    fig, *_ = plotter._process_dataset_update(ds, "all", "light", None, "small_multiples", "signals", 2, None, None)
    assert len(fig.data) == 2
    assert "window 2" in fig.layout.title.text


def test_window_arrays_falls_back_to_window0_view():
    plotter = _bare_plotter()
    # legacy dict: only X/dt, no windows_X -> _window_arrays returns the window-0 view.
    seq = {"X": [[1.0, 2.0], [3.0, 4.0]], "dt": [0.0, 1.0]}
    X, dt = plotter._window_arrays(seq, 5)  # out-of-range index -> fallback
    assert X.shape == (2, 2) and list(dt) == [0.0, 1.0]


def test_sequence_control_options_population():
    plotter = _bare_plotter()
    ds = _seq_dataset_multiwindow(n_windows=4, length=4, n_features=2)
    sig_opts, sig_multi, win_opts, win_single, sig_opts2, sig_single, win_opts2, win_multi = plotter._sequence_control_options(ds)
    assert [o["value"] for o in sig_opts] == [0, 1]
    assert sig_multi == [0, 1]  # all signals
    assert [o["value"] for o in win_opts] == [0, 1, 2, 3]
    assert win_single == 0  # first window
    assert sig_single == 0  # first signal
    assert win_multi == [0, 1, 2]  # the first few windows (<= 3)
    assert win_opts == win_opts2 and sig_opts == sig_opts2  # shared option lists


def test_sequence_control_options_empty_for_tabular_and_none():
    plotter = _bare_plotter()
    empty = ([], None, [], None, [], None, [], None)
    assert plotter._sequence_control_options({"dataset_kind": "tabular"}) == empty
    assert plotter._sequence_control_options(None) == empty


# --------------------------------------------------- Phase 2c: target + characterization
def test_install_stores_target_and_histograms():
    demo = _bare_demo()
    out = demo._install_sequence_dataset(_sequence_npz(5, 4, 2), source_label="g")
    seq = out["sequence"]
    assert len(seq["windows_y"]) == 5  # one target per stored window
    assert len(seq["windows_y"][0]) == 2  # y_full is (W, F=2) -> per-window (F,) flattened
    for h in (seq["dt_hist"], seq["target_hist"]):
        assert h is not None and len(h["counts"]) == 30 and len(h["edges"]) == 31


def _seq_dataset_with_companions() -> dict:
    ds = _seq_dataset_multiwindow(n_windows=3, length=4, n_features=2)
    ds["sequence"]["windows_y"] = [[0.5, 0.6], [0.7, 0.8], [0.1, 0.2]]
    ds["sequence"]["dt_hist"] = {"edges": [0.0, 0.5, 1.0], "counts": [3, 5]}
    ds["sequence"]["target_hist"] = {"edges": [0.0, 1.0, 2.0], "counts": [2, 4]}
    return ds


def test_target_companion_hidden_when_toggle_off():
    plotter = _bare_plotter()
    _, style = plotter._process_target_update(_seq_dataset_with_companions(), [], "signals", 0, None, "light")
    assert style["display"] == "none"


def test_target_companion_shows_selected_window_when_on():
    plotter = _bare_plotter()
    # signals mode, window 2 -> the target of window 2
    fig, style = plotter._process_target_update(_seq_dataset_with_companions(), ["on"], "signals", 2, None, "light")
    assert style["display"] == "block"
    assert list(fig.data[0].y) == [0.1, 0.2]
    assert "window 2" in fig.layout.title.text


def test_target_companion_windows_mode_uses_first_selected():
    plotter = _bare_plotter()
    fig, _ = plotter._process_target_update(_seq_dataset_with_companions(), ["on"], "windows", None, [1, 2], "light")
    assert list(fig.data[0].y) == [0.7, 0.8]  # window 1 (first selected)


def test_characterization_renders_for_sequence():
    import plotly.graph_objects as go

    plotter = _bare_plotter()
    dt_fig, tgt_fig, stats, style = plotter._process_characterization_update(_seq_dataset_with_companions(), "light")
    assert isinstance(dt_fig, go.Figure) and len(dt_fig.data) == 1
    assert isinstance(tgt_fig, go.Figure) and len(tgt_fig.data) == 1
    assert style["display"] == "block"
    assert stats  # non-empty W/L/F stats children


def test_characterization_hidden_for_tabular():
    plotter = _bare_plotter()
    dt_fig, tgt_fig, stats, style = plotter._process_characterization_update({"dataset_kind": "tabular"}, "light")
    assert style == {"display": "none"}
    assert stats == ""


# ----------------------------------------------------- Phase 3: advanced full-cross grid (M4)
def test_grid_hidden_when_toggle_off():
    plotter = _bare_plotter()
    _, style = plotter._process_grid_update(_seq_dataset_multiwindow(3, 4, 2), [], "light")
    assert style["display"] == "none"


def test_grid_hidden_for_tabular_even_when_on():
    plotter = _bare_plotter()
    _, style = plotter._process_grid_update({"dataset_kind": "tabular"}, ["on"], "light")
    assert style["display"] == "none"


def test_grid_renders_full_cross_when_on():
    import plotly.graph_objects as go

    plotter = _bare_plotter()
    ds = _seq_dataset_multiwindow(n_windows=3, length=4, n_features=2)
    fig, style = plotter._process_grid_update(ds, ["on"], "light")
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 6  # 3 windows × 2 signals
    assert style["display"] == "block" and style["overflowY"] == "auto"


def test_grid_caps_cells_at_100():
    plotter = _bare_plotter()
    # 5 signals × 30 windows -> capped to 5 × 20 = 100 cells (rows trimmed)
    ds = _seq_dataset_multiwindow(n_windows=30, length=4, n_features=5)
    fig = plotter._create_grid_plot(ds["sequence"], "light")
    assert len(fig.data) == 100  # 20 windows × 5 signals
    assert "first 20 of 30 windows" in fig.layout.title.text


# ═══════════════════════════════════════════════════════════════════════════════════════
# S-6: the install must assemble the WHOLE dataset from the partitions
#
# Decision 11 (juniper-ml notes/JUNIPER_2026-08-29_JUNIPER-ECOSYSTEM_TRAIN-EVAL-TEST-
# PARTITION-DESIGN.md §9.5) retired the ``*_full`` family and juniper-data#369 stopped
# emitting it, so NO artifact minted since 2026-09-06 carries ``X_full``. #589 migrated
# the 2-D path to ``DemoMode._whole_dataset``; the 3-D path kept reading ``X_full`` with
# an ``X_train`` fallback, so every sequence install was silently TRAIN-ONLY while
# ``n_windows`` / ``lookback`` / ``n_features``, the stored windows and the Δt / target
# histograms all claimed the whole dataset. Nothing errored.
#
# Each test below names, in its docstring, the assertion that fails against that old code.
# ═══════════════════════════════════════════════════════════════════════════════════════
def _tagged_windows(tags: list[float], length: int, n_features: int) -> np.ndarray:
    """(W, L, F) whose every cell equals its window's tag — so row ORDER is readable."""
    return np.stack([np.full((length, n_features), t, dtype=np.float32) for t in tags])


def _tagged_dt(tags: list[float], length: int) -> np.ndarray:
    """(W, L) Δt tagged the same way, with the contract's leading per-window 0."""
    a = np.stack([np.full(length, t, dtype=np.float32) for t in tags])
    a[:, 0] = 0.0
    return a


def _partitioned_sequence_npz(w_train: int = 3, w_val: int = 2, w_test: int = 1, length: int = 4, n_features: int = 2) -> dict:
    """A post-#369 3-D artifact: partitions only, NO ``*_full`` family anywhere.

    Windows are tagged 0.. within train, 100.. within val, 200.. within test, so the
    assembled row order is directly readable off the stored windows.
    """
    npz: dict = {}
    for split, base, count in (("train", 0.0, w_train), ("val", 100.0, w_val), ("test", 200.0, w_test)):
        if count <= 0:
            continue
        tags = [base + i for i in range(count)]
        npz[f"X_{split}"] = _tagged_windows(tags, length, n_features)
        npz[f"dt_{split}"] = _tagged_dt(tags, length)
        npz[f"y_{split}"] = np.array([[t] for t in tags], dtype=np.float32)
    return npz


def test_sequence_install_assembles_all_partitions_without_full():
    """(1) train+val+test, no ``*_full`` → the WHOLE dataset is installed.

    Fails on the old code at ``n_windows == 6`` (it returned 3, the train partition
    alone) and at the Δt-histogram total (9 of the 18 inter-step gaps).
    """
    demo = _bare_demo()
    npz = _partitioned_sequence_npz(w_train=3, w_val=2, w_test=1, length=4, n_features=2)

    out = demo._install_sequence_dataset(npz, source_label="generator:window_irregular_series")

    assert out["n_windows"] == 6  # 3 + 2 + 1, not 3
    assert (out["lookback"], out["n_features"]) == (4, 2)
    seq = out["sequence"]
    assert len(seq["windows_X"]) == 6
    # Contract order: every train window, then every val, then every test.
    assert [w[0][0] for w in seq["windows_X"]] == [0.0, 1.0, 2.0, 100.0, 101.0, 200.0]
    # "computed over ALL windows": 6 windows × (L-1 = 3) inter-step gaps.
    assert sum(seq["dt_hist"]["counts"]) == 18
    assert sum(seq["target_hist"]["counts"]) == 6
    # Δt and y were reordered with X, not independently.
    assert [w[1] for w in seq["windows_dt"]] == [0.0, 1.0, 2.0, 100.0, 101.0, 200.0]
    assert [w[0] for w in seq["windows_y"]] == [0.0, 1.0, 2.0, 100.0, 101.0, 200.0]


def test_sequence_install_prefers_legacy_full_family():
    """(2) a legacy artifact's ``*_full`` still wins — tolerance, never a requirement.

    This one passes against the old code too, deliberately: it is the guard on the
    tolerance, and the mutation it catches is the tempting over-correction (deleting the
    legacy branch so everything is re-derived). Every artifact minted before 2026-09-06
    still ships the family, and re-deriving it could change the row order the producer
    actually wrote.
    """
    demo = _bare_demo()
    npz = _partitioned_sequence_npz(w_train=3, w_val=2, w_test=1, length=4, n_features=2)
    legacy_tags = [900.0 + i for i in range(4)]
    npz["X_full"] = _tagged_windows(legacy_tags, 4, 2)
    npz["dt_full"] = _tagged_dt(legacy_tags, 4)
    npz["y_full"] = np.array([[t] for t in legacy_tags], dtype=np.float32)

    out = demo._install_sequence_dataset(npz, source_label="legacy")

    assert out["n_windows"] == 4  # the producer's own array, not the 6-row concatenation
    assert [w[0][0] for w in out["sequence"]["windows_X"]] == legacy_tags
    assert [w[0] for w in out["sequence"]["windows_y"]] == legacy_tags


def test_whole_dataset_concatenates_1d_targets_flat():
    """(3) a 1-D ``(W,)`` target per partition concatenates to ``(W_total,)``.

    Fails on the old code at the shape assertion: ``np.vstack`` promoted the three
    ``(W,)`` partitions to a ``(3, W)`` matrix — three rows of "the whole dataset"
    instead of one — and the install's target histogram then counted one partition.
    """
    from demo_mode import DemoMode

    npz = {
        "X_train": _tagged_windows([0.0, 1.0], 4, 2),
        "X_val": _tagged_windows([100.0, 101.0], 4, 2),
        "X_test": _tagged_windows([200.0, 201.0], 4, 2),
        "y_train": np.array([0.0, 1.0], dtype=np.float32),
        "y_val": np.array([100.0, 101.0], dtype=np.float32),
        "y_test": np.array([200.0, 201.0], dtype=np.float32),
    }

    whole_y = DemoMode._whole_dataset(npz, "y")
    assert whole_y.shape == (6,)  # not (3, 2)
    assert whole_y.tolist() == [0.0, 1.0, 100.0, 101.0, 200.0, 201.0]

    out = _bare_demo()._install_sequence_dataset(npz, source_label="flat-target")
    assert out["n_windows"] == 6
    assert list(out["sequence"]["windows_y"]) == [[0.0], [1.0], [100.0], [101.0], [200.0], [201.0]]
    assert sum(out["sequence"]["target_hist"]["counts"]) == 6  # all six targets, not two


def test_whole_dataset_restores_entity_major_order_for_two_tickers():
    """(4) split-major partitions + ``ticker_code_*`` reproduce the ENTITY-major order.

    juniper-data built ``*_full`` entity-major (each ticker's train, val, test in turn)
    while the partitions are split-major, so a plain concatenation renders a different
    order for the same logical dataset. ``equities`` and ``equities_seq`` both emit
    ``ticker_code_<split>`` for every partition, which makes the legacy order exactly
    reconstructible — concatenate, then ONE stable argsort on the codes.

    Fails on the old code twice: ``_whole_dataset`` returned the split-major
    concatenation (no reordering at all), and the install never got past ``X_train``.
    """
    from demo_mode import DemoMode

    # Ticker 0 tags 10..13, ticker 1 tags 20..23; each partition is SPLIT-major.
    split_major_tags = {"train": [10.0, 11.0, 20.0, 21.0], "val": [12.0, 22.0], "test": [13.0, 23.0]}
    codes = {"train": [0, 0, 1, 1], "val": [0, 1], "test": [0, 1]}
    npz: dict = {}
    for split, tags in split_major_tags.items():
        npz[f"X_{split}"] = _tagged_windows(tags, 4, 2)
        npz[f"dt_{split}"] = _tagged_dt(tags, 4)
        npz[f"y_{split}"] = np.array([[t] for t in tags], dtype=np.float32)
        npz[f"ticker_code_{split}"] = np.array(codes[split], dtype=np.int32)

    # Built by hand: ticker 0's train, val, test, then ticker 1's train, val, test.
    expected = [10.0, 11.0, 12.0, 13.0, 20.0, 21.0, 22.0, 23.0]
    # ... and that is NOT what a plain concatenation gives.
    assert expected != [10.0, 11.0, 20.0, 21.0, 12.0, 22.0, 13.0, 23.0]

    assert DemoMode._whole_dataset(npz, "X")[:, 0, 0].tolist() == expected

    out = _bare_demo()._install_sequence_dataset(npz, source_label="generator:equities_seq")
    assert out["n_windows"] == 8
    seq = out["sequence"]
    assert [w[0][0] for w in seq["windows_X"]] == expected
    # One permutation for the artifact: Δt and y land on the same windows as X.
    assert [w[1] for w in seq["windows_dt"]] == expected
    assert [w[0] for w in seq["windows_y"]] == expected


def test_entity_major_order_is_none_without_ticker_code_or_for_one_ticker():
    """(4b) no ``ticker_code`` (every non-equities generator) or one ticker → no reorder.

    ``None`` is the "nothing to permute" answer, and it spares a full copy of every array.
    """
    from demo_mode import DemoMode

    plain = _partitioned_sequence_npz(w_train=2, w_val=1, w_test=1, length=3, n_features=1)
    assert DemoMode._entity_major_order(plain) is None

    single = dict(plain)
    for split, count in (("train", 2), ("val", 1), ("test", 1)):
        single[f"ticker_code_{split}"] = np.zeros(count, dtype=np.int32)
    assert DemoMode._entity_major_order(single) is None  # identity permutation


def test_sequence_install_handles_val_less_artifact():
    """(5) a two-partition (train + test) artifact still installs, whole.

    The HF / Kaggle store artifacts carry no ``val``. Fails on the old code at
    ``n_windows == 5``, which returned 3.
    """
    demo = _bare_demo()
    npz = _partitioned_sequence_npz(w_train=3, w_val=0, w_test=2, length=4, n_features=2)
    assert "X_val" not in npz and "X_full" not in npz

    out = demo._install_sequence_dataset(npz, source_label="store:kaggle")

    assert out["n_windows"] == 5  # 3 + 2, not 3
    assert [w[0][0] for w in out["sequence"]["windows_X"]] == [0.0, 1.0, 2.0, 200.0, 201.0]
    assert sum(out["sequence"]["dt_hist"]["counts"]) == 15  # 5 windows × 3 gaps
