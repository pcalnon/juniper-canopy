"""
Dataset generator functions for test scenarios.

Produces realistic test data matching the canopy dataset format expected by
DatasetPlotter and other dashboard components.

Dataset dict keys:
    inputs       – list of [f1, f2, ...] per sample
    targets      – list of class labels (int)
    num_samples  – int
    num_features – int
    num_classes  – int
"""

from typing import Any, Dict

import numpy as np


def generate_dataset_inputs(num_samples: int = 100, num_features: int = 2, *, seed: int = 42) -> np.ndarray:
    """Return a float32 array of shape (num_samples, num_features) with random inputs."""
    rng = np.random.RandomState(seed)
    return rng.randn(num_samples, num_features).astype(np.float32)


def generate_dataset_targets(num_samples: int = 100, num_classes: int = 2, *, seed: int = 42) -> np.ndarray:
    """Return an int array of class labels in [0, num_classes)."""
    rng = np.random.RandomState(seed)
    return rng.randint(0, num_classes, size=num_samples)


def generate_two_spiral_dataset(num_samples: int = 100, noise: float = 0.1, *, seed: int = 42) -> Dict[str, Any]:
    """Generate a two-spiral dataset matching the canopy dashboard format.

    Args:
        num_samples: Total number of samples (split evenly between two classes).
        noise: Standard deviation of Gaussian noise added to the spirals.
        seed: Random seed for reproducibility.

    Returns:
        Dataset dict with keys: inputs, targets, num_samples, num_features, num_classes.
    """
    rng = np.random.RandomState(seed)
    n_per_class = num_samples // 2

    theta = np.linspace(0, 4 * np.pi, n_per_class)
    r = theta / (4 * np.pi)

    x0 = r * np.cos(theta) + rng.randn(n_per_class) * noise
    y0 = r * np.sin(theta) + rng.randn(n_per_class) * noise

    x1 = -r * np.cos(theta) + rng.randn(n_per_class) * noise
    y1 = -r * np.sin(theta) + rng.randn(n_per_class) * noise

    inputs = np.vstack([np.column_stack([x0, y0]), np.column_stack([x1, y1])]).astype(np.float32)
    targets = np.concatenate([np.zeros(n_per_class), np.ones(n_per_class)]).astype(int)

    indices = rng.permutation(len(inputs))
    inputs = inputs[indices]
    targets = targets[indices]

    return {
        "inputs": inputs.tolist(),
        "targets": targets.tolist(),
        "num_samples": len(inputs),
        "num_features": 2,
        "num_classes": 2,
    }
