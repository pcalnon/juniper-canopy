#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     cascor_response_fixtures.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-03-26
# Last Modified: 2026-03-26
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   Reusable fixtures returning real cascor ResponseEnvelope-formatted responses
#####################################################################
"""
Fixture functions returning real cascor ResponseEnvelope-formatted responses.

Real cascor wraps ALL responses in::

    {"status": "success", "data": <payload>, "meta": {"timestamp": <float>, "version": "0.5.0"}}

These are plain functions (not pytest fixtures) that return dicts.
"""

import time


def _envelope(data):
    """Wrap a payload in the standard cascor ResponseEnvelope."""
    return {
        "status": "success",
        "data": data,
        "meta": {"timestamp": time.time(), "version": "0.5.0"},
    }


def real_training_status_active():
    """Envelope with active training status using real cascor nested structure."""
    return _envelope(
        {
            "state_machine": {"status": "STARTED", "phase": "OUTPUT"},
            "monitor": {
                "is_training": True,
                "current_epoch": 42,
                "current_hidden_units": 3,
                "total_metrics": 100,
            },
            "training_state": {
                "status": "Started",
                "phase": "Output",
                "learning_rate": 0.01,
                "max_hidden_units": 10,
                "max_epochs": 1000,
                "current_epoch": 42,
            },
            "network_loaded": True,
            "training_active": True,
        }
    )


def real_training_status_idle():
    """Envelope with idle training status using real cascor nested structure."""
    return _envelope(
        {
            "state_machine": {"status": "IDLE", "phase": "IDLE"},
            "monitor": {
                "is_training": False,
                "current_epoch": 0,
                "current_hidden_units": 0,
                "total_metrics": 0,
            },
            "training_state": {
                "status": "Idle",
                "phase": "Idle",
                "learning_rate": 0.01,
                "max_hidden_units": 10,
                "max_epochs": 1000,
                "current_epoch": 0,
            },
            "network_loaded": False,
            "training_active": False,
        }
    )


def real_training_status_epoch_zero():
    """Envelope with epoch=0 / hidden_units=0 edge case (training just started)."""
    return _envelope(
        {
            "state_machine": {"status": "STARTED", "phase": "OUTPUT"},
            "monitor": {
                "is_training": True,
                "current_epoch": 0,
                "current_hidden_units": 0,
                "total_metrics": 0,
            },
            "training_state": {
                "status": "Started",
                "phase": "Output",
                "learning_rate": 0.01,
                "max_hidden_units": 10,
                "max_epochs": 1000,
                "current_epoch": 0,
            },
            "network_loaded": True,
            "training_active": True,
        }
    )


def real_metrics_history():
    """Envelope with a flat list of metric dicts using real cascor field names."""
    return _envelope(
        [
            {
                "epoch": 1,
                "loss": 0.95,
                "accuracy": 0.10,
                "validation_loss": 0.97,
                "validation_accuracy": 0.08,
                "hidden_units": 0,
                "phase": "output",
                "timestamp": time.time() - 100,
            },
            {
                "epoch": 10,
                "loss": 0.45,
                "accuracy": 0.62,
                "validation_loss": 0.50,
                "validation_accuracy": 0.58,
                "hidden_units": 1,
                "phase": "candidate",
                "timestamp": time.time() - 50,
            },
            {
                "epoch": 42,
                "loss": 0.12,
                "accuracy": 0.91,
                "validation_loss": 0.15,
                "validation_accuracy": 0.89,
                "hidden_units": 3,
                "phase": "output",
                "timestamp": time.time(),
            },
        ]
    )


def real_metrics_current():
    """Envelope with a single metric dict using real cascor field names."""
    return _envelope(
        {
            "epoch": 42,
            "train_loss": 0.12,
            "train_accuracy": 0.91,
            "val_loss": 0.15,
            "val_accuracy": 0.89,
            "hidden_units": 3,
        }
    )


def real_training_params():
    """Envelope with flat training parameters dict."""
    return _envelope(
        {
            "learning_rate": 0.01,
            "max_hidden_units": 10,
            "epochs_max": 1000,
            "patience": 50,
            "candidate_pool_size": 8,
            "correlation_threshold": 0.95,
        }
    )


def real_dataset():
    """Envelope with dataset info."""
    return _envelope(
        {
            "loaded": True,
            "train_samples": 800,
            "test_samples": 200,
            "input_features": 2,
            "output_features": 1,
        }
    )


def real_topology():
    """Envelope with network topology data."""
    return _envelope(
        {
            "input_size": 2,
            "output_size": 1,
            "hidden_units": [
                {
                    "weights": [0.5, -0.3],
                    "bias": 0.1,
                    "activation": "sigmoid",
                },
                {
                    "weights": [0.2, 0.8, -0.4],
                    "bias": -0.05,
                    "activation": "sigmoid",
                },
            ],
            "output_weights": [[0.7], [-0.2], [0.4], [0.1]],
            "output_bias": [0.05],
        }
    )
