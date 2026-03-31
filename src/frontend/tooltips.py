"""Tooltip text definitions for dashboard controls."""

from typing import Dict

# Maps component IDs to tooltip text.
# Used by DashboardManager._build_tooltips() to create dbc.Tooltip components.
CONTROL_TOOLTIPS: Dict[str, str] = {
    # Neural Network parameters
    "nn-max-iterations-input": "Maximum number of grow iterations (cascade additions) before training stops.",
    "nn-max-total-epochs-input": "Maximum total output training epochs across all grow iterations.",
    "nn-learning-rate-input": "Learning rate for output weight training (gradient descent step size).",
    "nn-max-hidden-units-input": "Maximum number of hidden units (cascade layers) to add to the network.",
    "nn-multi-node-layers-checkbox": "When checked, adds multiple candidate nodes per cascade layer.",
    "nn-growth-trigger-radio": "Criterion for triggering a new cascade addition: preset epoch count or convergence threshold.",
    "nn-growth-preset-epochs-input": "Number of output training epochs before adding a new cascade unit.",
    "nn-growth-convergence-threshold-input": "Loss convergence threshold — add cascade unit when improvement falls below this value.",
    "nn-spiral-rotations-input": "Number of rotations in the spiral dataset.",
    "nn-spiral-number-input": "Number of spiral arms in the dataset.",
    "nn-dataset-elements-input": "Number of data points per spiral arm.",
    "nn-dataset-noise-input": "Gaussian noise standard deviation applied to dataset points.",
    # Candidate Node parameters
    "cn-pool-size-input": "Number of candidate nodes trained in parallel per grow iteration.",
    "cn-correlation-threshold-input": "Minimum correlation with residual error required to install a candidate.",
    "cn-selected-candidates-input": "Number of top candidates selected from the pool for installation.",
    "cn-training-complete-radio": "Criterion for ending candidate training: fixed epoch count or convergence.",
    "cn-training-iterations-input": "Number of training epochs for each candidate node in the pool.",
    "cn-training-convergence-threshold-input": "Convergence threshold for candidate correlation — stop training when improvement is below this.",
    "cn-multi-candidate-checkbox": "When checked, enables multi-candidate selection mode.",
    "cn-candidate-selection-radio": "Selection strategy for choosing candidates: top-N by correlation or random subset.",
    "cn-top-candidates-input": "Number of top-performing candidates to select (by correlation).",
    "cn-random-candidates-input": "Number of candidates to select randomly from the pool.",
    # Controls
    "apply-params-button": "Apply the current parameter values to the backend (takes effect on next training cycle).",
}
