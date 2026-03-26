"""Fixtures containing real cascor ResponseEnvelope-formatted responses.

These fixtures mirror the actual juniper-cascor server's response format,
including envelope wrapping, nested structure, and uppercase enum values.
Used by characterization tests to validate normalization logic.
"""

import time


def real_training_status_active():
    """Training status response from a real cascor server that is actively training."""
    return {
        "status": "success",
        "data": {
            "training_active": True,
            "network_loaded": True,
            "state_machine": {
                "status": "STARTED",
                "phase": "OUTPUT",
                "current_state": "STARTED",
            },
            "monitor": {
                "current_epoch": 42,
                "current_hidden_units": 3,
                "best_loss": 0.15,
            },
            "training_state": {
                "learning_rate": 0.01,
                "max_epochs": 500,
                "max_hidden_units": 10,
                "input_size": 2,
                "output_size": 3,
                "phase": "OUTPUT",
            },
        },
        "meta": {"timestamp": time.time(), "version": "0.4.0"},
    }


def real_training_status_idle():
    """Training status response from a real cascor server that is idle."""
    return {
        "status": "success",
        "data": {
            "training_active": False,
            "network_loaded": True,
            "state_machine": {
                "status": "STOPPED",
                "phase": "IDLE",
                "current_state": "STOPPED",
            },
            "monitor": {
                "current_epoch": 0,
                "current_hidden_units": 0,
            },
            "training_state": {
                "learning_rate": 0.01,
                "max_epochs": 500,
                "max_hidden_units": 10,
            },
        },
        "meta": {"timestamp": time.time(), "version": "0.4.0"},
    }


def real_training_status_epoch_zero():
    """Training status where epoch is legitimately 0 (just started)."""
    return {
        "status": "success",
        "data": {
            "training_active": True,
            "network_loaded": True,
            "state_machine": {
                "status": "STARTED",
                "phase": "OUTPUT",
            },
            "monitor": {
                "current_epoch": 0,
                "current_hidden_units": 0,
            },
            "training_state": {
                "max_epochs": 500,
            },
        },
        "meta": {"timestamp": time.time(), "version": "0.4.0"},
    }


def real_metrics_history():
    """Metrics history response from a real cascor server.

    Note: real server returns data as a flat list (not nested in dict.history),
    and uses field names loss/accuracy/validation_loss/validation_accuracy
    (not train_loss/train_accuracy/val_loss/val_accuracy).
    """
    return {
        "status": "success",
        "data": [
            {"epoch": 1, "loss": 0.95, "accuracy": 0.35, "validation_loss": 0.92, "validation_accuracy": 0.38, "hidden_units": 0, "phase": "output", "timestamp": 1711400001.0},
            {"epoch": 2, "loss": 0.82, "accuracy": 0.51, "validation_loss": 0.84, "validation_accuracy": 0.49, "hidden_units": 0, "phase": "output", "timestamp": 1711400002.0},
            {"epoch": 3, "loss": 0.0, "accuracy": 0.65, "validation_loss": 0.71, "validation_accuracy": 0.62, "hidden_units": 1, "phase": "candidate", "timestamp": 1711400003.0},
        ],
        "meta": {"timestamp": time.time(), "version": "0.4.0"},
    }


def real_metrics_current():
    """Current metrics snapshot from a real cascor server."""
    return {
        "status": "success",
        "data": {
            "train_loss": 0.45,
            "train_accuracy": 0.72,
            "timestamp": 1711400010.0,
        },
        "meta": {"timestamp": time.time(), "version": "0.4.0"},
    }


def real_training_params():
    """Training params from a real cascor server (flat data, no nested params dict)."""
    return {
        "status": "success",
        "data": {
            "learning_rate": 0.01,
            "max_hidden_units": 10,
            "epochs_max": 500,
            "patience": 50,
            "candidate_pool_size": 8,
            "correlation_threshold": 0.4,
            "candidate_epochs": 200,
        },
        "meta": {"timestamp": time.time(), "version": "0.4.0"},
    }


def real_topology():
    """Network topology from a real cascor server."""
    return {
        "status": "success",
        "data": {
            "input_size": 2,
            "output_size": 3,
            "hidden_units": [
                {"id": 0, "activation": "sigmoid", "connections": [0, 1]},
                {"id": 1, "activation": "sigmoid", "connections": [0, 1, 2]},
            ],
            "output_weights": [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]],
            "output_bias": [0.01, 0.02, 0.03],
        },
        "meta": {"timestamp": time.time(), "version": "0.4.0"},
    }


def real_dataset():
    """Dataset metadata from a real cascor server."""
    return {
        "status": "success",
        "data": {
            "loaded": True,
            "train_samples": 800,
            "test_samples": 200,
            "input_features": 2,
            "output_features": 3,
            "dataset_name": "spiral",
        },
        "meta": {"timestamp": time.time(), "version": "0.4.0"},
    }


# --- Fake client format fixtures (for backward-compat testing) ---


def fake_training_status_active():
    """Training status as returned by FakeCascorClient."""
    return {
        "status": "ok",
        "is_training": True,
        "data": {
            "state": "training",
            "phase": "output",
            "epoch": 42,
            "max_epochs": 500,
        },
    }


def fake_training_status_idle():
    """Idle training status as returned by FakeCascorClient."""
    return {
        "status": "ok",
        "is_training": False,
        "data": {
            "state": "idle",
            "epoch": 0,
            "max_epochs": 0,
        },
    }


def fake_metrics_history():
    """Metrics history as returned by FakeCascorClient."""
    return {
        "status": "ok",
        "data": {
            "history": [
                {"epoch": 1, "train_loss": 0.95, "train_accuracy": 0.35, "val_loss": 0.92, "val_accuracy": 0.38, "hidden_units": 0},
                {"epoch": 2, "train_loss": 0.82, "train_accuracy": 0.51, "val_loss": 0.84, "val_accuracy": 0.49, "hidden_units": 0},
            ],
            "total": 2,
        },
    }


def fake_training_params():
    """Training params as returned by FakeCascorClient."""
    return {
        "status": "ok",
        "data": {
            "params": {
                "learning_rate": 0.01,
                "max_hidden_units": 10,
                "epochs_max": 500,
                "patience": 50,
                "candidate_pool_size": 8,
                "correlation_threshold": 0.4,
                "candidate_epochs": 200,
            },
            "epochs": 500,
        },
    }
