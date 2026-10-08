#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_recurrence_backend.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-06-22
# Last Modified: 2026-06-22
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   Unit tests for RecurrenceBackend (A1-ii) — the BackendProtocol
#                wrapper that backgrounds the recurrence one-shot fit. Uses a
#                controllable fake adapter (no network, no live service).
#####################################################################
"""Unit tests for ``backend.recurrence_backend.RecurrenceBackend`` (A1-ii).

Verifies the one-shot execution paradigm: ``start_training`` backgrounds the blocking
``adapter.train`` and the backend reports a binary idle/training/trained/failed status;
dataset ref + hyperparameters are forwarded; the cascade-only surface is stubbed; and the
unsupported controls (stop/pause/resume) fail closed.
"""

import json
import logging
import threading
import time

import httpx
import pytest

from backend.protocol import BackendProtocol
from backend.recurrence_backend import RecurrenceBackend
from backend.recurrence_service_adapter import RecurrenceServiceAdapter, RecurrenceServiceError, RecurrenceServiceUnavailableError, RecurrenceTrainResult

_BACKEND_LOGGER = "juniper_canopy.backend.recurrence_backend"
_NON_FINITE = "invalid dataset: X_train has non-finite values (NaN/Inf)"


def _make_result():
    return RecurrenceTrainResult(
        final_metrics={"r2": 0.96, "mse": 0.02, "rmse": 0.14, "mae": 0.1, "loss": 0.02},
        n_epochs=1,
        stopped_reason="fit_complete",
        dataset={"name": "equities_seq", "dataset_id": "ds-1", "n_windows": 200, "lookback": 32, "n_features": 5, "output_dim": 1},
    )


class _FakeAdapter:
    """Stand-in for RecurrenceServiceAdapter with a controllable ``train``."""

    def __init__(self, *, result=None, error=None, gate=None):
        self.service_url = "http://rec.test:8210"
        self._result = result if result is not None else _make_result()
        self._error = error
        self._gate = gate  # if set, train() blocks on this Event (simulates a long fit)
        self.calls = []

    def train(self, **kwargs):
        self.calls.append(kwargs)
        if self._gate is not None:
            self._gate.wait(timeout=5.0)
        if self._error is not None:
            raise self._error
        return self._result


def _wait_until(predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.005)
    return predicate()


# The name ``RecurrenceBackend.start_training`` gives its fit thread (``src/backend/recurrence_backend.py``).
_FIT_THREAD_NAME = "recurrence-fit"

# One bound for every join after a test, not one per thread. It matches the fake adapter's gate timeout and
# ``RecurrenceBackend.shutdown``'s join. Every gated test here releases its gate, so on a passing run each join returns
# as soon as the thread's last log call does. A gate left closed can only follow a test that already failed before
# its ``gate.set()``, and that thread is then held to this bound rather than left running into the next test.
_FIT_THREAD_JOIN_SECONDS = 5.0


@pytest.fixture(autouse=True)
def _join_recurrence_fit_threads():
    """After each test, join every live fit thread, so its log records cannot land in the NEXT test's ``caplog``.

    A failing fit flips ``_state`` to ``failed`` under the lock and logs its WARNING after releasing it, outside the
    lock (``RecurrenceBackend._run_fit``); a fit that succeeds logs its INFO line the same way. A test that waits only
    for ``is_training_active()`` to clear can therefore end while its thread is still about to log. On a slow runner
    the record then arrives during the next test's call phase, in that test's ``caplog``:
    ``TestA422DetailReachesTheOperator`` read ``TestFailureHandling``'s 503 WARNING and failed with
    ``ValueError: too many values to unpack`` or a wrong message, on canopy ``main``'s macOS leg at #702, #708 and #711.
    Joining here keeps every record in the teardown of the test that started the fit.
    """
    yield
    deadline = time.monotonic() + _FIT_THREAD_JOIN_SECONDS
    for thread in threading.enumerate():
        if thread.name == _FIT_THREAD_NAME:
            thread.join(timeout=max(0.0, deadline - time.monotonic()))


@pytest.mark.unit
class TestIdentityAndConformance:
    def test_backend_type(self):
        assert RecurrenceBackend(_FakeAdapter()).backend_type == "recurrence"

    def test_protocol_conformance(self):
        assert isinstance(RecurrenceBackend(_FakeAdapter()), BackendProtocol)


@pytest.mark.unit
class TestStartTraining:
    def test_backgrounds_and_completes(self):
        backend = RecurrenceBackend(_FakeAdapter())
        result = backend.start_training(generator="equities_seq")
        assert result["ok"] is True
        assert _wait_until(lambda: not backend.is_training_active())
        status = backend.get_status()
        assert status["completed"] is True
        assert status["fsm_status"] == "trained"
        assert backend.has_network() is True

    def test_in_progress_status_while_fitting(self):
        gate = threading.Event()
        backend = RecurrenceBackend(_FakeAdapter(gate=gate))
        try:
            backend.start_training(generator="equities_seq")
            assert _wait_until(backend.is_training_active)
            status = backend.get_status()
            assert status["is_training"] is True
            assert status["fsm_status"] == "training"
            assert status["phase"] == "fitting"
        finally:
            gate.set()  # release the fit so the daemon thread can finish
        assert _wait_until(lambda: not backend.is_training_active())

    def test_requires_dataset_ref(self):
        adapter = _FakeAdapter()
        backend = RecurrenceBackend(adapter)
        result = backend.start_training()  # no ref
        assert result["ok"] is False
        assert backend.is_training_active() is False
        assert adapter.calls == []  # never reached the adapter

    def test_forwards_dataset_ref_and_hyperparams(self):
        adapter = _FakeAdapter()
        backend = RecurrenceBackend(adapter)
        backend.start_training(name="equities_seq", params={"n": 128}, split="full", d=8, theta=1.5, ridge=0.1)
        assert _wait_until(lambda: not backend.is_training_active())
        call = adapter.calls[0]
        assert call["name"] == "equities_seq"
        assert call["params"] == {"n": 128}
        assert call["split"] == "full"
        assert call["d"] == 8 and call["theta"] == 1.5 and call["ridge"] == 0.1

    def test_double_start_rejected(self):
        gate = threading.Event()
        backend = RecurrenceBackend(_FakeAdapter(gate=gate))
        try:
            first = backend.start_training(generator="equities_seq")
            assert first["ok"] is True
            assert _wait_until(backend.is_training_active)
            second = backend.start_training(generator="equities_seq")
            assert second["ok"] is False
            assert "in progress" in second["error"]
        finally:
            gate.set()
        assert _wait_until(lambda: not backend.is_training_active())


@pytest.mark.unit
class TestFailureHandling:
    def test_failed_fit_sets_failed_state(self):
        adapter = _FakeAdapter(error=RecurrenceServiceError("boom", status_code=500))
        backend = RecurrenceBackend(adapter)
        backend.start_training(generator="equities_seq")
        assert _wait_until(lambda: not backend.is_training_active())
        status = backend.get_status()
        assert status["failed"] is True
        assert status["fsm_status"] == "failed"
        assert "boom" in status["completion_reason"]
        assert backend.has_network() is False

    # #683 validation: ``completion_reason`` is on /api/status, which an anonymous caller reads, and a failed fit wrote
    # the exception's text into it -- httpx's refusal ``Illegal header value b'<key>'`` for a padded recurrence key.

    @pytest.mark.parametrize(
        "error, reason",
        [
            (RecurrenceServiceError("recurrence service unreachable on POST /v1/train: Illegal header value b' LEAKME-rec'"), "RecurrenceServiceError"),
            (RuntimeError("Illegal header value b' LEAKME-rec'"), "unexpected error during recurrence fit: RuntimeError"),
        ],
        ids=["service-error-without-status", "unexpected"],
    )
    def test_a_failed_fits_transport_text_never_reaches_completion_reason(self, error, reason):
        backend = RecurrenceBackend(_FakeAdapter(error=error))
        backend.start_training(generator="equities_seq")
        assert _wait_until(lambda: not backend.is_training_active())
        status = backend.get_status()
        assert status["completion_reason"] == reason
        assert "LEAKME" not in repr(status)

    def test_the_services_answer_still_reaches_completion_reason(self):
        backend = RecurrenceBackend(_FakeAdapter(error=RecurrenceServiceError("recurrence service error 503 on POST /v1/train", status_code=503, body="{}")))
        backend.start_training(generator="equities_seq")
        assert _wait_until(lambda: not backend.is_training_active())
        assert backend.get_status()["completion_reason"] == "recurrence service error 503 on POST /v1/train"


def _fit_warnings(caplog):
    return [record for record in caplog.records if record.name == _BACKEND_LOGGER and record.levelno == logging.WARNING]


@pytest.mark.unit
class TestA422DetailReachesTheOperator:
    """W0.5 / F-C1: a refused fit's reason reaches ``completion_reason`` and the WARNING, not just its status code.

    The WARNING is logged after the state flips, outside the lock, so these wait for the record itself rather than for
    ``is_training_active()`` to clear.
    """

    def test_completion_reason_and_the_warning_carry_the_detail(self, caplog):
        error = RecurrenceServiceError(f"recurrence service error 422 on POST /v1/train: {_NON_FINITE}", status_code=422, body=json.dumps({"detail": _NON_FINITE}))
        backend = RecurrenceBackend(_FakeAdapter(error=error))
        with caplog.at_level(logging.WARNING, logger=_BACKEND_LOGGER):
            backend.start_training(generator="equities_seq")
            assert _wait_until(lambda: bool(_fit_warnings(caplog)))
        status = backend.get_status()
        assert status["failed"] is True
        assert "non-finite" in status["completion_reason"]
        (warning,) = _fit_warnings(caplog)
        assert warning.getMessage() == f"recurrence fit failed (status=422): recurrence service error 422 on POST /v1/train: {_NON_FINITE}"

    def test_the_real_adapters_422_reaches_completion_reason(self, caplog):
        """The whole canopy-side chain: the service's JSON body -> ``_parse`` -> ``outbound_error_text`` -> the field.

        A fake adapter would pass whatever message the test wrote; this one builds it the way production does.
        """

        def refuse(request: httpx.Request) -> httpx.Response:
            return httpx.Response(422, json={"detail": _NON_FINITE})

        backend = RecurrenceBackend(RecurrenceServiceAdapter("http://rec.test:8210", transport=httpx.MockTransport(refuse)))
        with caplog.at_level(logging.WARNING, logger=_BACKEND_LOGGER):
            backend.start_training(generator="equities_seq")
            assert _wait_until(lambda: bool(_fit_warnings(caplog)))
        assert backend.get_status()["completion_reason"] == f"recurrence service error 422 on POST /v1/train: {_NON_FINITE}"
        (warning,) = _fit_warnings(caplog)
        assert "status=422" in warning.getMessage()
        assert _NON_FINITE in warning.getMessage()

    def test_a_5xx_detail_relaying_a_refused_key_reaches_neither_the_field_nor_the_log(self, caplog):
        """The service's 502 relays its own juniper-data client's failure, and that text can quote the service's key.

        Built with the real adapter: the reply's ``detail`` is exactly what juniper-recurrence's ``map_data_error``
        sends for a juniper-data client that refused a padded key. Only a 4xx detail is appended, so neither the
        anonymous-readable field nor canopy's log carries it.
        """
        relayed = "data fetch failed: Request failed: Invalid leading whitespace, reserved character(s), or return character(s) in header value: ' LEAKME-rec-data'"

        def fail(request: httpx.Request) -> httpx.Response:
            return httpx.Response(502, json={"detail": relayed})

        backend = RecurrenceBackend(RecurrenceServiceAdapter("http://rec.test:8210", transport=httpx.MockTransport(fail)))
        with caplog.at_level(logging.WARNING, logger=_BACKEND_LOGGER):
            backend.start_training(generator="equities_seq")
            assert _wait_until(lambda: bool(_fit_warnings(caplog)))
        status = backend.get_status()
        assert status["completion_reason"] == "recurrence service error 502 on POST /v1/train"
        assert "LEAKME" not in repr(status)
        (warning,) = _fit_warnings(caplog)
        assert warning.getMessage() == "recurrence fit failed (status=502): recurrence service error 502 on POST /v1/train"

    def test_a_transport_failure_logs_no_status_and_keeps_its_text_out_of_the_field(self, caplog):
        """#683 still holds: no status code, so ``completion_reason`` is the type name; the full text stays in the log."""
        error = RecurrenceServiceUnavailableError("recurrence service unreachable on POST /v1/train: Illegal header value b' LEAKME-rec'")
        backend = RecurrenceBackend(_FakeAdapter(error=error))
        with caplog.at_level(logging.WARNING, logger=_BACKEND_LOGGER):
            backend.start_training(generator="equities_seq")
            assert _wait_until(lambda: bool(_fit_warnings(caplog)))
        assert backend.get_status()["completion_reason"] == "RecurrenceServiceUnavailableError"
        (warning,) = _fit_warnings(caplog)
        assert warning.getMessage().startswith("recurrence fit failed (status=None): recurrence service unreachable on POST /v1/train")


@pytest.mark.unit
class TestW16RemediesReachTheOperator:
    """W1.6: a 429's ``Retry-After`` (F-C7) and a 401's key variables (F-C5) reach ``completion_reason`` and the WARNING.

    Through the real adapter: ``outbound_error_text`` passes a status-bearing error as ``str(exc)``, so nothing in the
    backend changes -- these pin that the text the adapter now builds is what the operator reads.
    """

    def test_the_real_adapters_429_wait_reaches_completion_reason(self, caplog):
        def limited(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, json={"detail": "Rate limit exceeded. Try again in 30 seconds."}, headers={"Retry-After": "30"})

        backend = RecurrenceBackend(RecurrenceServiceAdapter("http://rec.test:8210", transport=httpx.MockTransport(limited)))
        with caplog.at_level(logging.WARNING, logger=_BACKEND_LOGGER):
            backend.start_training(generator="equities_seq")
            assert _wait_until(lambda: bool(_fit_warnings(caplog)))
        expected = "recurrence service error 429 on POST /v1/train — retry after 30 s: Rate limit exceeded. Try again in 30 seconds."
        status = backend.get_status()
        assert status["failed"] is True
        assert status["completion_reason"] == expected
        (warning,) = _fit_warnings(caplog)
        assert warning.getMessage() == f"recurrence fit failed (status=429): {expected}"

    def test_the_real_adapters_401_remedy_reaches_completion_reason(self, caplog):
        def refuse(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"detail": "Invalid API key."})

        backend = RecurrenceBackend(RecurrenceServiceAdapter("http://rec.test:8210", "wrong-key", transport=httpx.MockTransport(refuse)))
        with caplog.at_level(logging.WARNING, logger=_BACKEND_LOGGER):
            backend.start_training(generator="equities_seq")
            assert _wait_until(lambda: bool(_fit_warnings(caplog)))
        reason = backend.get_status()["completion_reason"]
        assert "JUNIPER_CANOPY_RECURRENCE_API_KEY or JUNIPER_CANOPY_RECURRENCE_API_KEY_FILE" in reason
        assert reason.endswith(": Invalid API key.")
        assert "wrong-key" not in reason


@pytest.mark.unit
class TestUnsupportedControls:
    def test_stop_pause_resume_fail_closed(self):
        backend = RecurrenceBackend(_FakeAdapter())
        assert backend.stop_training()["ok"] is False
        assert backend.pause_training()["ok"] is False
        assert backend.resume_training()["ok"] is False

    def test_reset_after_trained_returns_to_idle(self):
        backend = RecurrenceBackend(_FakeAdapter())
        backend.start_training(generator="equities_seq")
        assert _wait_until(lambda: not backend.is_training_active())
        assert backend.has_network() is True
        result = backend.reset_training()
        assert result["ok"] is True
        assert backend.has_network() is False
        assert backend.get_status()["fsm_status"] == "idle"

    def test_reset_during_fit_rejected(self):
        gate = threading.Event()
        backend = RecurrenceBackend(_FakeAdapter(gate=gate))
        try:
            backend.start_training(generator="equities_seq")
            assert _wait_until(backend.is_training_active)
            assert backend.reset_training()["ok"] is False
        finally:
            gate.set()
        assert _wait_until(lambda: not backend.is_training_active())


@pytest.mark.unit
class TestMetricsAndDataAccessors:
    def _trained(self):
        backend = RecurrenceBackend(_FakeAdapter())
        backend.start_training(generator="equities_seq")
        assert _wait_until(lambda: not backend.is_training_active())
        return backend

    def test_get_metrics_carries_regression_set(self):
        metrics = self._trained().get_metrics()
        assert metrics["r2"] == pytest.approx(0.96)
        assert "accuracy" not in metrics  # regression-generic
        assert metrics["loss"] == pytest.approx(0.02)
        assert metrics["epoch"] == 1

    def test_get_metrics_empty_before_fit(self):
        assert RecurrenceBackend(_FakeAdapter()).get_metrics() == {}

    def test_metrics_history_single_point(self):
        history = self._trained().get_metrics_history()
        assert len(history) == 1
        assert history[0]["r2"] == pytest.approx(0.96)

    def test_metrics_history_empty_before_fit(self):
        assert RecurrenceBackend(_FakeAdapter()).get_metrics_history() == []

    def test_cascade_surface_is_stubbed(self):
        backend = self._trained()
        assert backend.get_network_topology() is None
        assert backend.get_raw_topology() is None
        assert backend.get_decision_boundary() is None

    def test_get_dataset_maps_descriptor(self):
        dataset = self._trained().get_dataset()
        assert dataset["num_samples"] == 200
        assert dataset["num_features"] == 5
        assert dataset["dataset_name"] == "equities_seq"

    def test_get_dataset_none_before_fit(self):
        assert RecurrenceBackend(_FakeAdapter()).get_dataset() is None


@pytest.mark.unit
class TestApplyParams:
    def test_apply_params_staged_into_next_fit(self):
        adapter = _FakeAdapter()
        backend = RecurrenceBackend(adapter)
        applied = backend.apply_params(d=12, theta=2.0, ridge=0.5, junk="ignored")
        assert applied["ok"] is True
        assert applied["data"] == {"d": 12, "theta": 2.0, "ridge": 0.5}
        backend.start_training(generator="equities_seq")
        assert _wait_until(lambda: not backend.is_training_active())
        call = adapter.calls[0]
        assert call["d"] == 12 and call["theta"] == 2.0 and call["ridge"] == 0.5

    def test_start_training_kwargs_override_staged(self):
        adapter = _FakeAdapter()
        backend = RecurrenceBackend(adapter)
        backend.apply_params(d=12)
        backend.start_training(generator="equities_seq", d=8)  # explicit wins
        assert _wait_until(lambda: not backend.is_training_active())
        assert adapter.calls[0]["d"] == 8


@pytest.mark.unit
class TestLifecycle:
    @pytest.mark.asyncio
    async def test_initialize_returns_true(self):
        assert await RecurrenceBackend(_FakeAdapter()).initialize() is True

    @pytest.mark.asyncio
    async def test_shutdown_joins_inflight_fit(self):
        gate = threading.Event()
        backend = RecurrenceBackend(_FakeAdapter(gate=gate))
        backend.start_training(generator="equities_seq")
        assert _wait_until(backend.is_training_active)
        gate.set()  # let the fit finish so shutdown's join returns promptly
        await backend.shutdown()
        assert backend.is_training_active() is False
