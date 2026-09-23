"""canopy#559 -- ``validate_npz_contract`` runs as an ADVISORY second check on generator loads.

``DemoMode.regenerate_dataset_from_generator`` gates on its own rank probe, because the shared
helper fails closed (a legacy ``X_full``-only artifact raises ``KeyError``; any sequence-rule
violation raises) while the ecosystem contract obliges canopy to keep loading such artifacts.
The owner ruled on 2026-09-22 that the helper should nonetheless run, warn-only. These tests
pin both halves: a violation is REPORTED, and it never stops the install.
"""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

import numpy as np


def _sequence_npz(dt_first_column: float = 0.0) -> dict:
    """A post-decision-11 3-D sequence artifact: three partitions, no ``*_full``."""
    rng = np.random.default_rng(3)
    arrays: dict = {}
    for split, windows in (("train", 4), ("val", 2), ("test", 2)):
        dt = rng.random((windows, 5)).astype(np.float32)
        dt[:, 0] = dt_first_column  # the contract requires 0 here
        arrays[f"X_{split}"] = rng.random((windows, 5, 2)).astype(np.float32)
        arrays[f"y_{split}"] = rng.random((windows, 2)).astype(np.float32)
        arrays[f"dt_{split}"] = dt
    return arrays


def _tabular_npz() -> dict:
    """A post-decision-11 tabular artifact."""
    rng = np.random.default_rng(4)
    arrays: dict = {}
    for split, rows in (("train", 8), ("val", 2), ("test", 2)):
        arrays[f"X_{split}"] = rng.random((rows, 2)).astype(np.float32)
        arrays[f"y_{split}"] = np.eye(2, dtype=np.float32)[rng.integers(0, 2, size=rows)]
    return arrays


def _legacy_full_only_npz() -> dict:
    """A pre-decision-11 artifact canopy must still load: only the ``*_full`` pair."""
    rng = np.random.default_rng(5)
    return {"X_full": rng.random((10, 2)).astype(np.float32), "y_full": np.eye(2, dtype=np.float32)[rng.integers(0, 2, size=10)]}


def _bare_demo():
    from demo_mode import DemoMode

    demo = DemoMode.__new__(DemoMode)
    demo.logger = MagicMock()
    demo.is_running = False
    demo._lock = threading.Lock()
    return demo


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


def _advisory_warnings(demo) -> list[str]:
    """The advisory check's WARNING lines, rendered, ignoring anything else logged."""
    rendered = [call.args[0] % call.args[1:] for call in demo.logger.warning.call_args_list]
    return [line for line in rendered if "Advisory NPZ contract check" in line]


# ------------------------------------------------------------------ the helper on its own
def test_helper_classifies_a_valid_artifact_and_stays_quiet():
    demo = _bare_demo()
    assert demo._advise_npz_contract(_sequence_npz(), "generator:irregular_sine") == "sequence"
    assert demo._advise_npz_contract(_tabular_npz(), "generator:xor") == "tabular"
    assert _advisory_warnings(demo) == []


def test_helper_returns_none_and_warns_on_a_violation():
    demo = _bare_demo()
    assert demo._advise_npz_contract(_sequence_npz(dt_first_column=1.0), "generator:irregular_sine") is None
    (line,) = _advisory_warnings(demo)
    assert "FAILED" in line and "generator:irregular_sine" in line and "dt_train[:, 0] must be 0" in line


# ------------------------------------------------------------- inside the real load path
def test_a_valid_sequence_artifact_installs_with_no_advisory_warning():
    demo, result = _run_regenerate(_sequence_npz(), "irregular_sine")
    demo._install_sequence_dataset.assert_called_once()
    assert result["dataset_kind"] == "sequence"
    assert _advisory_warnings(demo) == []


def test_a_contract_violation_is_reported_but_still_installs():
    """The point of 'advisory': the warning names the violation and the install happens."""
    demo, result = _run_regenerate(_sequence_npz(dt_first_column=1.0), "irregular_sine")
    demo._install_sequence_dataset.assert_called_once()
    assert result["dataset_kind"] == "sequence"
    (line,) = _advisory_warnings(demo)
    assert "FAILED" in line and "dt_train[:, 0] must be 0" in line and "installing anyway" in line


def test_a_legacy_full_only_artifact_is_reported_but_still_installs():
    """The helper cannot read an ``X_full``-only artifact; canopy is obliged to load it."""
    demo, result = _run_regenerate(_legacy_full_only_npz(), "xor")
    demo.import_dataset.assert_called_once()
    assert result["dataset_kind"] == "tabular"
    (line,) = _advisory_warnings(demo)
    assert "could not run" in line and "X_train" in line


def test_an_unexpected_error_from_the_helper_never_blocks_the_install():
    with patch("juniper_data_client.validate_npz_contract", side_effect=RuntimeError("boom")):
        demo, result = _run_regenerate(_tabular_npz(), "xor")
    demo.import_dataset.assert_called_once()
    assert result["dataset_kind"] == "tabular"
    (line,) = _advisory_warnings(demo)
    assert "RuntimeError" in line and "boom" in line


def test_the_advisory_check_sees_the_artifact_the_probe_dispatches():
    """It is handed the downloaded artifact itself, and its answer does not change the route."""
    seen: list = []

    def record(arrays):
        seen.append(sorted(arrays))
        return "sequence"

    with patch("juniper_data_client.validate_npz_contract", side_effect=record):
        demo, _ = _run_regenerate(_sequence_npz(), "irregular_sine")
    assert seen == [sorted(_sequence_npz())]
    demo._install_sequence_dataset.assert_called_once()
