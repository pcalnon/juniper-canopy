#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_recurrence_version_display.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-10-08
# Last Modified: 2026-10-08
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   W1.7 display half: refresh_model_versions has a
#                production caller (startup and recurrence selection),
#                the version reaches /api/selection and the sidebar
#                summary, and nothing waits on the lookup.
#####################################################################
"""Regression tests for W1.7's display half (F-C8).

Plan: juniper-ml ``notes/JUNIPER_2026-10-03_JUNIPER-RECURRENCE_EQUITIES-END-TO-END-AUDIT-AND-DEVELOPMENT-PLAN.md`` --
the status-table row for W1.6 / W1.7 records "the display half of W1.7 is still open (``refresh_model_versions`` has no
production caller)". canopy#722 made the version a thing the service reports; this pins that canopy now asks, and
shows the answer:

* at startup, when a recurrence service is configured, and whenever the recurrence model is selected while its backend
  is live -- each in the background, so no page render, selection response or ``/api/selection`` read waits on it;
* in ``/api/selection`` / ``POST /api/model/select`` as an optional ``version``, and on the sidebar's Active line.

The version under test is ``0.6.3``: a value that appears nowhere in canopy's source, so it can only have come from the
fake service.
"""

import ast
import asyncio
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

import backend.recurrence_service_adapter as adapter_module
import main
from backend.recurrence_backend import RecurrenceBackend
from frontend.dashboard_manager import DashboardManager
from model_registry import MODELS, RECURRENCE_PROVIDER, SERVICE_VERSION_UNAVAILABLE, get_model_spec, refresh_model_versions
from tests.fixtures.recurrence_service_fake import BASE_URL, FakeRecurrenceService

_SERVICE_VERSION = "0.6.3"


def _wait_until(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.005)
    return predicate()


@pytest.fixture
def version_globals(monkeypatch):
    """Start every test with nothing reported and no refresh in flight; restore both afterwards."""
    monkeypatch.setattr(main, "_reported_models", None)
    monkeypatch.setattr(main, "_model_version_refresh", None)
    monkeypatch.setattr(main, "current_nn_model", None)


@pytest.fixture
def live_recurrence(monkeypatch, version_globals):
    """Install a live recurrence backend over the real adapter and ``service``; the recurrence selection targets it."""

    def install(service):
        monkeypatch.setattr(main, "backend", RecurrenceBackend(service.adapter()))
        monkeypatch.setattr(main, "_selection_targets_recurrence", lambda nn_model: nn_model == "recurrence")
        return service

    return install


class _GatedHealth(FakeRecurrenceService):
    """A fake whose ``GET /v1/health`` waits on ``gate``: the version lookup is in flight until the test releases it."""

    def __init__(self, gate, **kwargs):
        super().__init__(**kwargs)
        self._gate = gate

    def __call__(self, request):
        if request.url.path == "/v1/health":
            assert self._gate.wait(10.0), "the test never released the lookup"
        return super().__call__(request)


@pytest.mark.regression
class TestTheDisplayedVersionIsTheServices:
    """Selecting the recurrence model asks its service; the answer is what ``/api/selection`` and the sidebar show."""

    def test_the_displayed_version_comes_from_the_fake_service(self, client, live_recurrence):
        service = live_recurrence(FakeRecurrenceService(version=_SERVICE_VERSION))

        selected = client.post("/api/model/select", json={"nn_model": "recurrence"})
        assert selected.status_code == 200
        assert "version" not in selected.json(), "nothing had reported a version when this response was built"

        assert _wait_until(lambda: main._reported_models is not None), "the selection never refreshed the version"
        payload = client.get("/api/selection").json()

        assert payload["version"] == _SERVICE_VERSION
        assert DashboardManager._model_summary_text(payload) == f"Active: Recurrence (LMU) · version {_SERVICE_VERSION}"
        assert service.paths() == ["GET /v1/health", "GET /openapi.json"], "read over the wire, the way 0.5.0 answers"

    def test_the_next_selection_response_carries_it(self, client, live_recurrence):
        live_recurrence(FakeRecurrenceService(version=_SERVICE_VERSION))
        client.post("/api/model/select", json={"nn_model": "recurrence"})
        assert _wait_until(lambda: main._reported_models is not None)
        assert client.post("/api/model/select", json={"nn_model": "recurrence"}).json()["version"] == _SERVICE_VERSION

    def test_a_failed_lookup_is_labelled_not_hidden(self, client, live_recurrence):
        """A service that names no version reads as the label, on both surfaces."""

        class _NoVersion(FakeRecurrenceService):
            def __call__(self, request):
                if request.url.path == "/openapi.json":
                    self.requests.append(request)
                    return httpx.Response(200, json={"openapi": "3.1.0", "info": {}, "paths": {}})
                return super().__call__(request)

        live_recurrence(_NoVersion())
        client.post("/api/model/select", json={"nn_model": "recurrence"})
        assert _wait_until(lambda: main._reported_models is not None)
        payload = client.get("/api/selection").json()
        assert payload["version"] == SERVICE_VERSION_UNAVAILABLE
        assert DashboardManager._model_summary_text(payload) == f"Active: Recurrence (LMU) · version {SERVICE_VERSION_UNAVAILABLE}"


@pytest.mark.regression
class TestNothingWaitsOnTheLookup:
    """The lookup is two blocking HTTP calls: it runs in the background, once at a time."""

    def test_the_selection_answers_while_the_lookup_is_in_flight(self, client, live_recurrence):
        gate = threading.Event()
        service = live_recurrence(_GatedHealth(gate, version=_SERVICE_VERSION))
        try:
            response = client.post("/api/model/select", json={"nn_model": "recurrence"})
            assert response.status_code == 200, "the response must not wait for the service"
            assert main._reported_models is None, "the lookup is still blocked"
            assert client.get("/api/selection").status_code == 200, "nor may a read wait for it"
        finally:
            gate.set()
        assert _wait_until(lambda: main._reported_models is not None)
        assert get_model_spec("recurrence", models=main._reported_models).version == _SERVICE_VERSION
        assert service.paths() == ["GET /v1/health", "GET /openapi.json"]

    def test_a_burst_of_selections_asks_the_service_once(self, client, live_recurrence):
        gate = threading.Event()
        service = live_recurrence(_GatedHealth(gate, version=_SERVICE_VERSION))
        try:
            for _ in range(3):
                assert client.post("/api/model/select", json={"nn_model": "recurrence"}).status_code == 200
        finally:
            gate.set()
        assert _wait_until(lambda: main._reported_models is not None)
        assert _wait_until(lambda: main._model_version_refresh is not None and main._model_version_refresh.done())
        assert service.paths() == ["GET /v1/health", "GET /openapi.json"]

    def test_selecting_a_model_no_service_serves_asks_nothing(self, client, version_globals, monkeypatch):
        service = FakeRecurrenceService(version=_SERVICE_VERSION)
        monkeypatch.setattr(main, "_selection_targets_recurrence", lambda nn_model: False)
        assert main.backend.backend_type != "recurrence"
        assert client.post("/api/model/select", json={"nn_model": "cascor"}).status_code == 200
        assert main._model_version_refresh is None
        assert service.requests == []


@pytest.mark.regression
@pytest.mark.unit
class TestStartupAsksTheConfiguredService:
    """The startup half: the lifespan asks a configured recurrence service in the background, and nothing else."""

    def test_startup_asks_the_configured_service(self, monkeypatch, version_globals):
        service = FakeRecurrenceService(version=_SERVICE_VERSION)
        original = adapter_module.RecurrenceServiceAdapter
        built = []

        def adapter_for_the_fake(service_url, api_key=None, **kwargs):
            built.append((service_url, api_key))
            return original(service_url, api_key, transport=service.transport)

        monkeypatch.setattr(main, "settings", SimpleNamespace(recurrence_service_url=BASE_URL, recurrence_api_key="k-startup"))
        monkeypatch.setattr(adapter_module, "RecurrenceServiceAdapter", adapter_for_the_fake)

        async def boot():
            main._start_model_version_refresh()
            assert main._model_version_refresh is not None, "startup scheduled nothing"
            await asyncio.wait({main._model_version_refresh})

        asyncio.run(boot())

        assert built == [(BASE_URL, "k-startup")], "built from the settings create_backend uses"
        assert get_model_spec("recurrence", models=main._reported_models).version == _SERVICE_VERSION
        assert service.requests[0].headers["X-API-Key"] == "k-startup"

    def test_startup_without_a_service_asks_nothing(self, monkeypatch, version_globals):
        monkeypatch.setattr(main, "settings", SimpleNamespace(recurrence_service_url=None, recurrence_api_key=None))

        async def boot():
            main._start_model_version_refresh()

        asyncio.run(boot())
        assert main._model_version_refresh is None and main._reported_models is None

    def test_the_lifespan_calls_it(self):
        """The production caller F-C8's display half lacked: the lifespan itself must make the call -- and stop it."""
        tree = ast.parse(Path(main.__file__).read_text(encoding="utf-8"))
        lifespan = next(node for node in ast.walk(tree) if isinstance(node, ast.AsyncFunctionDef) and node.name == "lifespan")
        called = {node.func.id for node in ast.walk(lifespan) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
        assert {"_start_model_version_refresh", "_stop_model_version_refresh"} <= called

    def test_shutdown_abandons_an_unfinished_refresh(self, version_globals):
        """A lookup still waiting on the service is cancelled, not awaited: shutdown does not wait on a label."""
        gate = threading.Event()

        def stalled_source():
            gate.wait(10.0)
            return _SERVICE_VERSION

        async def boot_then_shut_down():
            main._schedule_model_version_refresh(stalled_source)
            task = main._model_version_refresh
            await asyncio.sleep(0.05)  # the lookup is in its worker thread now
            await main._stop_model_version_refresh()
            gate.set()  # let the worker thread end, which the loop's executor shutdown waits for
            return task

        task = asyncio.run(boot_then_shut_down())
        assert task.cancelled()
        assert main._reported_models is None, "an abandoned lookup reports nothing"

    def test_a_refresh_that_raises_is_logged_and_keeps_the_last_answer(self, monkeypatch, version_globals):
        """``refresh_model_versions`` never raises for a version; the worker hop still might (an executor shut down).

        Raised from inside the hop here, which reaches the same ``except`` without patching ``asyncio`` process-wide.
        """
        earlier = refresh_model_versions({RECURRENCE_PROVIDER: lambda: "0.5.0"}, models=MODELS)
        monkeypatch.setattr(main, "_reported_models", earlier)
        logger = SimpleNamespace(calls=[])
        monkeypatch.setattr(main, "system_logger", SimpleNamespace(warning=lambda *args: logger.calls.append(args)))

        def failing_refresh(*_args, **_kwargs):
            raise RuntimeError("cannot schedule new futures after shutdown")

        monkeypatch.setattr("model_registry.refresh_model_versions", failing_refresh)

        asyncio.run(main._refresh_model_versions(lambda: _SERVICE_VERSION))

        assert main._reported_models is earlier, "the last answer stands"
        assert logger.calls == [("Model version refresh failed: %s: %s", "RuntimeError", logger.calls[0][2])]
        assert str(logger.calls[0][2]) == "cannot schedule new futures after shutdown"


@pytest.mark.regression
@pytest.mark.unit
class TestWhereTheVersionShows:
    """The payload carries ``version`` only when a service reported one; the sidebar shows it on the Active line only."""

    def test_no_version_until_a_service_reports_one(self, monkeypatch, version_globals):
        monkeypatch.setattr(main, "backend", SimpleNamespace(backend_type="recurrence", execution="one_shot"))
        assert "version" not in main._model_state_response("recurrence", swapped=False)

    def test_only_the_model_its_service_serves_carries_it(self, monkeypatch, version_globals):
        monkeypatch.setattr(main, "backend", SimpleNamespace(backend_type="recurrence", execution="one_shot"))
        monkeypatch.setattr(main, "_reported_models", refresh_model_versions({RECURRENCE_PROVIDER: lambda: _SERVICE_VERSION}, models=MODELS))
        assert main._model_state_response("recurrence", swapped=False)["version"] == _SERVICE_VERSION
        assert "version" not in main._model_state_response("cascor", swapped=False), "cascor is in-process: it has no service to ask"
        assert "version" not in main._model_state_response("not-a-model", swapped=False)

    @pytest.mark.parametrize(
        "payload, summary",
        [
            ({"nn_model": "recurrence", "backend": "recurrence", "status": "live", "version": "0.6.3"}, "Active: Recurrence (LMU) · version 0.6.3"),
            ({"nn_model": "recurrence", "backend": "recurrence", "status": "live", "version": " 0.6.3\n"}, "Active: Recurrence (LMU) · version 0.6.3"),
            ({"nn_model": "recurrence", "backend": "recurrence", "status": "live", "version": "  "}, "Active: Recurrence (LMU)"),
            ({"nn_model": "recurrence", "backend": "recurrence", "status": "live", "version": None}, "Active: Recurrence (LMU)"),
            ({"nn_model": "recurrence", "backend": "recurrence", "status": "coming_soon", "version": "0.6.3"}, "Active: Recurrence (LMU) · version 0.6.3 · coming soon"),
            ({"nn_model": "recurrence", "backend": "demo", "status": "live", "version": "0.6.3"}, "Selected: Recurrence (LMU) · NOT ACTIVE — the demo backend is running"),
            ({"nn_model": "recurrence", "status": "live", "version": "0.6.3"}, f"Selected: Recurrence (LMU) · {DashboardManager.UNKNOWN_LIVENESS_NOTE}"),
        ],
        ids=["active", "flattened", "blank", "null", "with-status-note", "not-active", "liveness-unknown"],
    )
    def test_the_summary_names_it_on_the_active_line_only(self, payload, summary):
        """A version describes the service a LIVE backend talks to; the other two lines describe none."""
        assert DashboardManager._model_summary_text(payload) == summary
