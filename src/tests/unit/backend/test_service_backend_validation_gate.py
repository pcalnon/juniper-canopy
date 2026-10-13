"""``start_training`` must refuse a dataset with no validation split, and say why.

Project:       Juniper
Sub-Project:   JuniperCanopy
Application:   juniper_canopy
File Name:     test_service_backend_validation_gate.py
Author:        Paul Calnon
License:       MIT License

cascor refuses the artifact at ingress (§6.1 rule 1), and that refusal is what
ultimately protects the metric. But by then the user has clicked Start and receives a
service error instead of a choice. §6.4 requires canopy to explain and offer options
BEFORE the request, which is what these pin.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from unittest.mock import MagicMock

import pytest

import validation_gate
from backend.service_backend import ServiceBackend

pytestmark = pytest.mark.unit


def _backend(dataset_info: Optional[Dict[str, Any]]) -> ServiceBackend:
    """A ServiceBackend whose adapter reports ``dataset_info`` and nothing else."""
    adapter = MagicMock()
    adapter.is_training_in_progress.return_value = False
    adapter.get_dataset_info.return_value = dataset_info
    adapter.network = object()  # non-None: skip the first-start staging path
    adapter.start_training_background.return_value = (True, None)
    backend = ServiceBackend.__new__(ServiceBackend)
    backend._adapter = adapter
    return backend


class TestStartTrainingGate:
    def test_refuses_when_the_producer_reports_no_validation_split(self):
        backend = _backend({"loaded": True, "train_samples": 100, "val_samples": 0, "test_samples": 25})
        result = backend.start_training()
        assert result["ok"] is False
        assert "SELECTED-ON" in result["error"], "the refusal must say what the number would mean, not merely that it is refused"
        backend._adapter.start_training_background.assert_not_called()

    def test_the_refusal_carries_the_options(self):
        """A refusal with no options is a dead end; §6.4 requires a choice."""
        backend = _backend({"val_samples": 0})
        result = backend.start_training()
        options = result["data"]["options"]
        assert [o["id"] for o in options] == [
            validation_gate.OPTION_FILL_SYNTHETICALLY,
            validation_gate.OPTION_CONTINUE_WITH_WARNING,
            validation_gate.OPTION_BACK_TO_DATASET,
            validation_gate.OPTION_CANCEL,
        ]
        assert [o["id"] for o in options if o["enabled"]], "at least one option must be pickable"

    def test_proceeds_when_the_split_exists(self):
        backend = _backend({"loaded": True, "train_samples": 100, "val_samples": 20, "test_samples": 25})
        result = backend.start_training()
        assert result["ok"] is True
        backend._adapter.start_training_background.assert_called_once()

    def test_proceeds_when_the_user_accepted_the_absence(self):
        """§6.4 option 1 arriving back. The run starts; the caller records the warning."""
        backend = _backend({"val_samples": 0})
        result = backend.start_training(accept_missing_validation_split=True)
        assert result["ok"] is True
        backend._adapter.start_training_background.assert_called_once()

    def test_acceptance_is_not_forwarded_to_cascor_as_a_training_kwarg(self):
        """It is canopy's gate, not a cascor training parameter.

        Leaking it into ``**kwargs`` would send an unknown field to the service, and on a
        stricter cascor that is a 422 on every accepted run.
        """
        backend = _backend({"val_samples": 0})
        backend.start_training(accept_missing_validation_split=True)
        _args, kwargs = backend._adapter.start_training_background.call_args
        assert "accept_missing_validation_split" not in kwargs

    def test_proceeds_but_does_not_refuse_when_cascor_cannot_say(self):
        """An older cascor omits ``val_samples`` entirely.

        Refusing here would block every run against it and teach the user to click past
        the gate -- worse than the thing being guarded. The uncertainty is surfaced as a
        warning by ``validation_gate.decide``, not as a refusal.
        """
        backend = _backend({"loaded": True, "train_samples": 100, "test_samples": 25})
        result = backend.start_training()
        assert result["ok"] is True
        backend._adapter.start_training_background.assert_called_once()

    def test_training_already_in_progress_still_wins(self):
        """The pre-existing guard must not be displaced by the new one."""
        backend = _backend({"val_samples": 0})
        backend._adapter.is_training_in_progress.return_value = True
        result = backend.start_training()
        assert result["ok"] is False
        assert result["error"] == "Training already in progress"


class TestDatasetCounts:
    def test_num_samples_spans_three_partitions(self):
        """It summed train + test, which under-counts by the validation rows."""
        backend = _backend(None)
        backend._adapter.get_dataset_info.return_value = {
            "loaded": True,
            "train_samples": 100,
            "val_samples": 20,
            "test_samples": 25,
            "input_features": 2,
            "output_features": 2,
            "inputs": [],
            "targets": [],
        }
        result = backend.get_dataset()
        assert result["num_samples"] == 145
        assert result["val_samples"] == 20
        assert result["test_samples"] == 25

    def test_missing_val_samples_reads_as_zero_without_inventing_rows(self):
        """An older cascor's payload must not make ``num_samples`` wrong in the other direction."""
        backend = _backend(None)
        backend._adapter.get_dataset_info.return_value = {
            "loaded": True,
            "train_samples": 100,
            "test_samples": 25,
            "input_features": 2,
            "output_features": 2,
            "inputs": [],
            "targets": [],
        }
        result = backend.get_dataset()
        assert result["val_samples"] == 0
        assert result["num_samples"] == 125
