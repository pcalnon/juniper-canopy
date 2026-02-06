"""
Mock Cascade Correlation Network for Testing

Provides a mock implementation of the CasCor network that simulates
training behavior without requiring the actual backend.
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

import numpy as np


@dataclass
class TrainingMetrics:
    """Container for training metrics."""

    epoch: int
    phase: str
    loss: float
    accuracy: float
    learning_rate: float
    correlation: float = 0.0


class MockCascorNetwork:
    """
    Mock implementation of Cascade Correlation Neural Network.

    Simulates the essential methods and attributes of the real CasCor network
    for testing purposes without requiring actual neural network computations.
    """

    def __init__(self, input_size: int = 2, output_size: int = 1, max_hidden_units: int = 10):
        """
        Initialize mock CasCor network.

        Args:
            input_size: Number of input units
            output_size: Number of output units
            max_hidden_units: Maximum number of hidden units to add during training
        """
        self.input_size = input_size
        self.output_size = output_size
        self.max_hidden_units = max_hidden_units

        # Network state
        self.hidden_units: List[Dict[str, Any]] = []
        self.output_weights: np.ndarray = np.random.randn(output_size, input_size)

        # Training history
        self.error_history: List[float] = []
        self.correlation_scores: List[float] = []
        self.epochs_completed: int = 0

        # Training configuration
        self.learning_rate: float = 0.01
        self.max_epochs: int = 100
        self.error_threshold: float = 0.01

        # Callbacks for monitoring hooks
        self.callbacks: Dict[str, List[Callable]] = {
            "on_epoch_start": [],
            "on_epoch_end": [],
            "on_phase_start": [],
            "on_phase_end": [],
            "on_hidden_unit_added": [],
            "on_training_complete": [],
        }

        # Training state
        self.is_training: bool = False
        self.current_phase: str = "idle"

    def register_callback(self, event: str, callback: Callable):
        """
        Register a callback for a training event.

        Args:
            event: Event name ('on_epoch_start', 'on_epoch_end', etc.)
            callback: Callback function to execute
        """
        if event in self.callbacks:
            self.callbacks[event].append(callback)

    def _fire_callback(self, event: str, *args, **kwargs):
        """
        Fire all callbacks for a given event.

        Args:
            event: Event name
            *args: Positional arguments for callbacks
            **kwargs: Keyword arguments for callbacks
        """
        for callback in self.callbacks.get(event, []):
            callback(*args, **kwargs)

    def train_output_weights(self, X: np.ndarray, y: np.ndarray, epochs: int = 10) -> Dict[str, Any]:
        """
        Simulate training output weights.

        Args:
            X: Input data (n_samples, n_features)
            y: Target data (n_samples, n_outputs)
            epochs: Number of training epochs

        Returns:
            Training results dictionary
        """
        self.current_phase = "output_training"
        self._fire_callback("on_phase_start", phase="output_training")

        for epoch in range(epochs):
            self._fire_callback("on_epoch_start", epoch=epoch)

            # Simulate training with decreasing error
            simulated_loss = 1.0 / (epoch + self.epochs_completed + 1) + np.random.normal(0, 0.05)
            simulated_accuracy = min(0.95, (epoch + self.epochs_completed) / self.max_epochs * 0.9)

            self.error_history.append(simulated_loss)
            self.epochs_completed += 1

            # Create metrics
            metrics = TrainingMetrics(
                epoch=self.epochs_completed,
                phase="output_training",
                loss=simulated_loss,
                accuracy=simulated_accuracy,
                learning_rate=self.learning_rate,
            )

            self._fire_callback("on_epoch_end", metrics=metrics)

        result = {
            "final_error": self.error_history[-1] if self.error_history else 0.0,
            "epochs": epochs,
            "converged": self.error_history[-1] < self.error_threshold if self.error_history else False,
        }
        self._complete_training("output_training", result)
        return result

    def train_candidate_units(self, X: np.ndarray, residual_error: np.ndarray, n_candidates: int = 8, epochs: int = 10) -> Dict[str, Any]:
        """
        Simulate training candidate hidden units.

        Args:
            X: Input data
            residual_error: Residual error from output weights
            n_candidates: Number of candidate units to train
            epochs: Number of training epochs per candidate

        Returns:
            Training results dictionary
        """
        self.current_phase = "candidate_training"
        self._fire_callback("on_phase_start", phase="candidate_training")

        candidate_correlations = []

        for candidate_idx in range(n_candidates):
            for epoch in range(epochs):
                self._fire_callback("on_epoch_start", epoch=epoch, candidate=candidate_idx)

                # Simulate correlation score
                simulated_correlation = np.random.uniform(0.5, 0.95)
                simulated_loss = 0.5 / (epoch + 1)

                metrics = TrainingMetrics(
                    epoch=self.epochs_completed,
                    phase="candidate_training",
                    loss=simulated_loss,
                    accuracy=0.0,  # Not applicable for candidate training
                    learning_rate=self.learning_rate,
                    correlation=simulated_correlation,
                )

                self.epochs_completed += 1
                self._fire_callback("on_epoch_end", metrics=metrics)

            candidate_correlations.append(simulated_correlation)

        # Select best candidate
        best_candidate_idx = np.argmax(candidate_correlations)
        best_correlation = candidate_correlations[best_candidate_idx]

        self.correlation_scores.append(best_correlation)

        result = {
            "best_candidate": best_candidate_idx,
            "best_correlation": best_correlation,
            "n_candidates": n_candidates,
        }
        self._complete_training("candidate_training", result)
        return result

    def _complete_training(self, phase: str = None, result: Dict[str, Any] = None):
        """
        Fire phase end callback and reset current phase.
        """
        self._fire_callback("on_phase_end", phase=phase, result=result)
        self.current_phase = "idle"
        return result

    def add_hidden_unit(self, unit_weights: Optional[np.ndarray] = None) -> int:
        """
        Add a hidden unit to the network.

        Args:
            unit_weights: Optional weights for the new unit

        Returns:
            Index of the added hidden unit
        """
        if unit_weights is None:
            # Generate random weights for input connections
            unit_weights = np.random.randn(self.input_size + len(self.hidden_units))

        hidden_unit = {"index": len(self.hidden_units), "weights": unit_weights, "activation": "sigmoid"}

        self.hidden_units.append(hidden_unit)

        # Update output weights to include connection from new hidden unit
        new_output_weights = np.zeros((self.output_size, self.input_size + len(self.hidden_units)))
        new_output_weights[:, :-1] = self.output_weights
        new_output_weights[:, -1] = np.random.randn(self.output_size) * 0.1
        self.output_weights = new_output_weights

        self._fire_callback("on_hidden_unit_added", unit=hidden_unit)

        return hidden_unit["index"]

    def train(self, X: np.ndarray, y: np.ndarray, max_units: Optional[int] = None, patience: int = 5) -> Dict[str, Any]:
        """
        Complete training loop with cascading architecture.

        Args:
            X: Input data (n_samples, n_features)
            y: Target data (n_samples, n_outputs)
            max_units: Maximum hidden units to add (None = use max_hidden_units)
            patience: Epochs to wait before adding new hidden unit

        Returns:
            Training results dictionary
        """
        self.is_training = True
        max_units = max_units or self.max_hidden_units

        # Initial output training
        output_result = self.train_output_weights(X, y, epochs=20)

        # Add hidden units until convergence or max units
        for _ in range(max_units):
            if output_result["converged"]:
                break

            # Train candidates
            residual_error = np.random.randn(len(X), self.output_size)  # Simulated
            candidate_result = self.train_candidate_units(X, residual_error, epochs=15)

            # Add best candidate
            self.add_hidden_unit()

            # Retrain output weights
            output_result = self.train_output_weights(X, y, epochs=10)

        self.is_training = False

        final_result = {
            "total_hidden_units": len(self.hidden_units),
            "total_epochs": self.epochs_completed,
            "final_error": self.error_history[-1] if self.error_history else 0.0,
            "converged": output_result["converged"],
            "output_result": output_result,
            "candidate_result": candidate_result,
        }

        self._fire_callback("on_training_complete", result=final_result)

        return final_result

    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Simulate prediction (returns random values for testing).

        Args:
            X: Input data

        Returns:
            Predicted outputs
        """
        n_samples = X.shape[0]
        return np.random.randn(n_samples, self.output_size)

    def compute_error(self, X: np.ndarray, y: np.ndarray) -> float:
        """
        Simulate error computation.

        Args:
            X: Input data
            y: Target data

        Returns:
            Simulated error value
        """
        return self.error_history[-1] if self.error_history else 1.0

    def get_weights(self) -> Dict[str, Any]:
        """
        Get network weights.

        Returns:
            Dictionary containing all network weights
        """
        return {
            "output_weights": self.output_weights.tolist(),
            "hidden_units": [
                {
                    "index": unit["index"],
                    "weights": unit["weights"].tolist() if isinstance(unit["weights"], np.ndarray) else unit["weights"],
                }
                for unit in self.hidden_units
            ],
        }

    def get_topology(self) -> Dict[str, int]:
        """
        Get network topology information.

        Returns:
            Dictionary with topology details
        """
        return {
            "input_units": self.input_size,
            "hidden_units": len(self.hidden_units),
            "output_units": self.output_size,
            "total_connections": self._count_connections(),
        }

    def _count_connections(self) -> int:
        """Count total number of connections in the network."""
        # Input to output
        connections = self.input_size * self.output_size

        # Input to hidden + hidden to output
        for hidden_unit in self.hidden_units:
            # Input and previous hidden to this hidden unit
            connections += self.input_size + hidden_unit["index"]
            # This hidden unit to output
            connections += self.output_size

        return connections

    def reset(self):
        """Reset network to initial state."""
        self.hidden_units = []
        self.output_weights = np.random.randn(self.output_size, self.input_size)
        self.error_history = []
        self.correlation_scores = []
        self.epochs_completed = 0
        self.is_training = False
        self.current_phase = "idle"

    def __repr__(self) -> str:
        """String representation of the network."""
        return f"MockCascorNetwork(" f"input={self.input_size}, " f"hidden={len(self.hidden_units)}, " f"output={self.output_size}, " f"epochs={self.epochs_completed}" f")"
