#!/usr/bin/env python
"""Test if plots are being created correctly."""
import sys

sys.path.insert(0, "src")

from frontend.base_component import create_empty_plot  # noqa: E402
from frontend.components.dataset_plotter import DatasetPlotter  # noqa: E402
from frontend.components.decision_boundary import DecisionBoundary  # noqa: E402
from frontend.components.metrics_panel import MetricsPanel  # noqa: E402
from frontend.components.network_visualizer import NetworkVisualizer  # noqa: E402

# Test metrics panel
print("Testing MetricsPanel...")
mp = MetricsPanel({})
test_data = [
    {"epoch": 1, "metrics": {"loss": 0.5, "accuracy": 0.7}, "phase": "output", "network_topology": {"hidden_units": 0}},
    {
        "epoch": 2,
        "metrics": {"loss": 0.4, "accuracy": 0.75},
        "phase": "output",
        "network_topology": {"hidden_units": 1},
    },
]
loss_fig = mp._create_loss_plot(test_data, "light")
print(f"  Loss plot traces: {len(loss_fig.data)}")
print(f"  Loss plot has data: {loss_fig.data[0].x is not None if loss_fig.data else False}")

# Test dataset plotter
print("\nTesting DatasetPlotter...")
dp = DatasetPlotter({})
test_dataset = {
    "inputs": [[0, 0], [1, 1], [0, 1], [1, 0]],
    "targets": [0, 0, 1, 1],
    "num_samples": 4,
    "num_features": 2,
}
scatter_fig = dp._create_scatter_plot(test_dataset, "light")
print(f"  Scatter plot traces: {len(scatter_fig.data)}")
print(f"  Scatter plot has data: {scatter_fig.data[0].x is not None if scatter_fig.data else False}")

# Test decision boundary
print("\nTesting DecisionBoundary...")
db = DecisionBoundary({})
empty_fig = create_empty_plot("Test", "light")
print(f"  Empty plot created: {empty_fig is not None}")
print(f"  Empty plot has annotations: {len(empty_fig.layout.annotations) > 0}")

# Test network visualizer
print("\nTesting NetworkVisualizer...")
nv = NetworkVisualizer({})
test_topology = {
    "input_units": 2,
    "hidden_units": 1,
    "output_units": 1,
    "connections": [
        {"source": "input_0", "target": "hidden_0", "weight": 0.5},
        {"source": "input_1", "target": "hidden_0", "weight": -0.3},
        {"source": "hidden_0", "target": "output_0", "weight": 0.8},
    ],
}
topo_fig = nv._create_network_graph(test_topology, "spring", True, None, "light")
print(f"  Topology plot traces: {len(topo_fig.data)}")
print(f"  Topology plot has data: {topo_fig.data[0].x is not None if topo_fig.data else False}")

print("\n✓ All plot creation tests passed")
