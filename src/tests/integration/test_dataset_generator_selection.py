"""Regression — the dataset-plotter "Dataset:" selector + Load button.

The selector (`dataset_plotter.py`) offered spiral/xor/circles/moon, but its value
reached no callback and canopy's backend could only generate spirals. Completion
(Paul's call, "Wire + proxy juniper-data"): a Load button reads the selector value
(State) and POSTs `/api/dataset/generate` with the chosen generator; spiral uses the
demo's local path, every other generator is proxied to the JuniperData service.

Coverage:
- the demo proxy method calls JuniperData with the selected generator and installs
  the decoded NPZ via import_dataset (unit, JuniperDataClient mocked);
- the route refuses a non-spiral generator with a clean 503 when JuniperData is
  unavailable (instead of silently falling back to a spiral).

The frontend wiring (selector value now reaches a callback as State, Load button as
an Input) is guarded by the L1 control-graph lint + the KNOWN_ORPHANS trim.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from demo_mode import DemoMode


@pytest.mark.integration
def test_regenerate_from_generator_proxies_juniper_data_and_installs():
    """demo.regenerate_dataset_from_generator -> JuniperData create_dataset(generator) -> import_dataset."""
    demo = DemoMode.__new__(DemoMode)  # bare instance: exercise just the proxy method
    demo.logger = MagicMock()
    demo.import_dataset = MagicMock(return_value={"n_samples": 20, "source": "generator:circles"})

    npz_data = {
        "X_full": np.zeros((20, 2), dtype=np.float32),
        "y_full": np.eye(2, dtype=np.float32)[np.arange(20) % 2],
        "X_train": np.zeros((16, 2), dtype=np.float32),
        "y_train": np.eye(2, dtype=np.float32)[np.arange(16) % 2],
        "X_test": np.zeros((4, 2), dtype=np.float32),
        "y_test": np.eye(2, dtype=np.float32)[np.arange(4) % 2],
    }
    mock_client = MagicMock()
    mock_client.create_dataset.return_value = {"dataset_id": "ds-circles-1"}
    mock_client.download_artifact_npz.return_value = npz_data

    with patch("juniper_data_client.JuniperDataClient", return_value=mock_client):
        result = demo.regenerate_dataset_from_generator("circles", n_samples=20)

    # The selected generator is what we asked JuniperData for (not a hardcoded spiral).
    assert mock_client.create_dataset.call_args.kwargs["generator"] == "circles"
    # The decoded NPZ was installed via import_dataset with a generator-tagged source.
    install = demo.import_dataset.call_args
    assert install.kwargs.get("source_label") == "generator:circles"
    passed_targets = install.args[1]
    assert np.asarray(passed_targets).ndim == 1  # one-hot decoded to 1-D labels
    assert result["source"] == "generator:circles"


@pytest.mark.integration
def test_generate_route_rejects_non_spiral_when_juniper_data_unavailable(client):
    """A non-spiral generator returns a clean 503 (not a silent spiral) when JuniperData is down."""
    resp = client.post("/api/dataset/generate", json={"generator": "circles"})
    assert resp.status_code == 503, resp.text
    assert "JuniperData" in resp.json().get("error", "")


@pytest.mark.integration
def test_generate_route_still_serves_spiral_without_juniper_data(client):
    """Spiral stays demo-local: the default/spiral path is unaffected by the generator branch."""
    resp = client.post("/api/dataset/generate", json={"generator": "spiral", "n_samples": 60})
    assert resp.status_code == 200, resp.text
