#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       1.0.0
# File Name:     test_outbound_errors.py
# File Path:     src/tests/unit/
#
# Created Date:  2026-09-24
# Last Modified: 2026-09-24
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#     #683 validation, item 1b. The cascor adapter returned ``{"error": str(e)}`` from every failed call, and that text
#     reached the /api/train/start 409 body, the /api/status envelope, /api/stream_health and every other route that
#     relays a backend error -- with a padded JUNIPER_CASCOR_API_KEY it held the key, for an anonymous caller.
#     ``outbound_errors.outbound_error_text`` is now the one thing that turns such a failure into text a caller reads:
#     the upstream's answer when it replied with an HTTP status, the exception's type name for anything else. These
#     tests pin the rule, every adapter site behaviourally, and -- statically -- that no site builds that text another way.
#
#####################################################################################################################################################################################################
"""Unit tests: a failed outbound call reaches a caller as the upstream's answer or the exception's type -- never its transport text."""

import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
import requests

from outbound_errors import outbound_error_text

_jcc = pytest.importorskip("juniper_cascor_client", reason="juniper-cascor-client not installed")
if getattr(_jcc, "_is_stub", False):
    pytest.skip("juniper-cascor-client is a test stub, not the real package", allow_module_level=True)

from juniper_cascor_client import JuniperCascorClientError  # noqa: E402
from juniper_cascor_client.exceptions import JuniperCascorConflictError, JuniperCascorConnectionError, JuniperCascorTimeoutError, JuniperCascorValidationError  # noqa: E402

# The message-only constructor, which canopy's conftest stub (CI installs no juniper-data-client) also accepts.
from juniper_data_client.exceptions import JuniperDataClientError  # noqa: E402

from backend.cascor_service_adapter import CascorServiceAdapter  # noqa: E402
from backend.recurrence_service_adapter import RecurrenceServiceError, RecurrenceServiceUnavailableError  # noqa: E402

SRC = Path(__file__).resolve().parents[2]
MARK = "LEAKME-7f3a"
# What each client said when it refused a padded key: the real message shapes, with the key in them.
TRANSPORT_TEXT = f"Request to http://cascor:8200/v1/training/status failed: Invalid leading whitespace, reserved character(s), or return character(s) in header value: ' {MARK}'"


def _answered(text: str, status_code: int) -> RuntimeError:
    """Any exception an upstream's HTTP answer produced: it carries the status code."""
    exc = RuntimeError(text)
    exc.status_code = status_code  # type: ignore[attr-defined]
    return exc


@pytest.mark.unit
class TestOutboundErrorText:
    @pytest.mark.parametrize(
        "exc, expected",
        [
            (JuniperCascorClientError(TRANSPORT_TEXT), "JuniperCascorClientError"),
            (JuniperCascorConnectionError(f"Failed to connect to ws://cascor:8200/ws/training: invalid X-API-Key header: {MARK}\n"), "JuniperCascorConnectionError"),
            (JuniperCascorTimeoutError(f"Request to http://cascor:8200/v1/x?k={MARK} timed out after 5s"), "JuniperCascorTimeoutError"),
            (requests.exceptions.InvalidHeader(f"Invalid leading whitespace ... in header value: ' {MARK}'"), "InvalidHeader"),
            (httpx.LocalProtocolError(f"Illegal header value b' {MARK}'"), "LocalProtocolError"),
            (JuniperDataClientError(f"Request failed: ... ' {MARK}'"), "JuniperDataClientError"),
            (RecurrenceServiceUnavailableError(f"recurrence service unreachable on POST /v1/train: Illegal header value b' {MARK}'"), "RecurrenceServiceUnavailableError"),
            (RuntimeError(MARK), "RuntimeError"),
        ],
        ids=["cascor-client", "cascor-ws", "cascor-timeout", "requests", "httpx", "data-client", "recurrence", "other"],
    )
    def test_a_failure_with_no_http_status_is_named_by_type_only(self, exc, expected):
        assert outbound_error_text(exc) == expected

    @pytest.mark.parametrize(
        "exc, expected",
        [
            (JuniperCascorConflictError("Training cannot be started: Training data not provided", status_code=409), "Training cannot be started: Training data not provided"),
            (JuniperCascorValidationError("body.values: shape mismatch", status_code=422), "body.values: shape mismatch"),
            (JuniperCascorClientError("HTTP 500: internal error", status_code=500), "HTTP 500: internal error"),
            (_answered("Validation error (422): seed: Field required", status_code=422), "Validation error (422): seed: Field required"),
            (RecurrenceServiceError("recurrence service error 500 on POST /v1/train", status_code=500, body="{}"), "recurrence service error 500 on POST /v1/train"),
        ],
        ids=["cascor-409", "cascor-422", "cascor-500", "any-answer", "recurrence-500"],
    )
    def test_the_upstreams_answer_passes(self, exc, expected):
        """PR-B2 / N4 / CAN-015h surface cascor's own detail on purpose; an answered request had every header sendable."""
        assert outbound_error_text(exc) == expected

    def test_an_answer_with_no_text_is_named_by_type(self):
        assert outbound_error_text(JuniperCascorConflictError("", status_code=409)) == "JuniperCascorConflictError"

    def test_a_boolean_status_is_no_status(self):
        exc = RuntimeError(MARK)
        exc.status_code = True  # type: ignore[attr-defined]
        assert outbound_error_text(exc) == "RuntimeError"

    def test_a_status_that_cannot_be_read_counts_as_none(self):
        class Odd(Exception):
            @property
            def status_code(self):
                raise KeyError("boom")

        assert outbound_error_text(Odd(MARK)) == "Odd"


# ---------------------------------------------------------------------------------------------------------------------
# Every adapter site that turns a failed cascor call into a value, driven with a client whose call raises. Transport
# text must not survive into the value; an answer must. ``(method, args, kwargs, client attribute that raises, reader)``.
# ---------------------------------------------------------------------------------------------------------------------

_ERROR = lambda result: result["error"]  # noqa: E731
_TUPLE = lambda result: result[1]  # noqa: E731
ADAPTER_SITES = [
    ("create_network", (), {}, "create_network", _ERROR),
    ("start_training_background", (), {}, "start_training", _TUPLE),
    ("start_training_background", (), {"start_fresh": True}, "_post", _TUPLE),
    ("pause_training", (), {}, "pause_training", _ERROR),
    ("resume_training", (), {}, "resume_training", _ERROR),
    ("reset_training", (), {}, "reset_training", _ERROR),
    ("apply_params", (), {"nn_learning_rate": 0.1}, "update_params", _ERROR),
    ("stage_dataset", (), {"nn_dataset_type": "spirals"}, "_request", _ERROR),
    ("cancel_pending_dataset", (), {}, "_request", _ERROR),
    ("get_pending_dataset", (), {}, "_request", _ERROR),
    ("get_experimental_functions", (), {}, "_request", _ERROR),
    ("set_experimental_functions", (True,), {}, "_request", _ERROR),
    ("swap_dataset_live", (), {"nn_dataset_type": "spirals"}, "_request", _ERROR),
    ("cancel_swap_dataset_live", (), {}, "_request", _ERROR),
    ("get_dataset_swap_events", (), {}, "_request", _ERROR),
    ("list_snapshots", (), {}, "_request", _ERROR),
    ("get_snapshot", ("snap-1",), {}, "_request", _ERROR),
    ("get_snapshot_dataset_swaps", ("snap-1",), {}, "_request", _ERROR),
    ("get_training_status", (), {}, "get_training_status", _ERROR),
    ("get_training_status_for_refresh", (), {}, "get_training_status", _ERROR),
]
_SITE_IDS = [f"{method}{'-fresh' if kwargs.get('start_fresh') else ''}" for method, _, kwargs, _, _ in ADAPTER_SITES]


def _adapter_raising(attribute: str, exc: Exception) -> CascorServiceAdapter:
    client = MagicMock()
    getattr(client, attribute).side_effect = exc
    return CascorServiceAdapter(service_url="http://cascor:8200", client=client)


@pytest.mark.unit
class TestEveryAdapterSite:
    @pytest.mark.parametrize("method, args, kwargs, attribute, read", ADAPTER_SITES, ids=_SITE_IDS)
    def test_transport_text_never_reaches_the_returned_error(self, monkeypatch, method, args, kwargs, attribute, read):
        monkeypatch.setattr("settings.get_settings", lambda: SimpleNamespace(use_websocket_set_params=False))
        result = getattr(_adapter_raising(attribute, JuniperCascorClientError(TRANSPORT_TEXT)), method)(*args, **kwargs)
        assert read(result) == "JuniperCascorClientError"
        assert MARK not in repr(result)

    @pytest.mark.parametrize("method, args, kwargs, attribute, read", ADAPTER_SITES, ids=_SITE_IDS)
    def test_the_upstreams_answer_still_reaches_it(self, monkeypatch, method, args, kwargs, attribute, read):
        monkeypatch.setattr("settings.get_settings", lambda: SimpleNamespace(use_websocket_set_params=False))
        answer = JuniperCascorConflictError("Training cannot be started: Training data not provided", status_code=409)
        result = getattr(_adapter_raising(attribute, answer), method)(*args, **kwargs)
        assert read(result) == "Training cannot be started: Training data not provided"


# ---------------------------------------------------------------------------------------------------------------------
# Static census. A behavioural list only covers the sites it names; the next method added to the adapter would copy the
# ``{"error": str(e)}`` pattern this PR removed. So: in the adapter, no ``return`` inside an ``except ... as <name>``
# handler, and no ``mark_disconnected(...)`` there, may use ``<name>`` except through ``outbound_error_text``.
# ---------------------------------------------------------------------------------------------------------------------


def _uses_outside_the_describer(node: ast.AST, name: str) -> list[str]:
    """Every use of ``name`` under ``node`` that is not inside an ``outbound_error_text(...)`` call."""
    uses: list[str] = []

    def walk(current: ast.AST, shielded: bool) -> None:
        if isinstance(current, ast.Call) and isinstance(current.func, ast.Name) and current.func.id == "outbound_error_text":
            shielded = True
        if isinstance(current, ast.Name) and current.id == name and not shielded:
            uses.append(ast.unparse(current))
        for child in ast.iter_child_nodes(current):
            walk(child, shielded)

    walk(node, False)
    return uses


def _escapes(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list[str] = []
    for handler in ast.walk(tree):
        if not isinstance(handler, ast.ExceptHandler) or handler.name is None:
            continue
        for node in ast.walk(handler):
            carried: ast.AST | None = None
            if isinstance(node, ast.Return) and node.value is not None:
                carried = node.value
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "mark_disconnected":
                carried = node
            if carried is not None and _uses_outside_the_describer(carried, handler.name):
                found.append(f"{path.name}:{node.lineno}: {ast.unparse(node)[:160]}")
    return found


@pytest.mark.unit
class TestNoSiteBuildsTheTextAnotherWay:
    def test_the_cascor_adapter(self):
        assert _escapes(SRC / "backend" / "cascor_service_adapter.py") == []

    def test_the_census_sees_the_pattern_it_forbids(self, tmp_path):
        """Vacuity guard: the scan flags the removed shapes, so a clean result above means something."""
        sample = tmp_path / "sample.py"
        sample.write_text(
            "def f(client, health):\n"
            "    try:\n"
            "        client.go()\n"
            "    except Exception as e:\n"
            '        return {"ok": False, "error": str(e)}\n'
            "def g(client):\n"
            "    try:\n"
            "        client.go()\n"
            "    except Exception as e:\n"
            "        return False, f'failed: {e}'\n"
            "def h(client, health):\n"
            "    try:\n"
            "        client.go()\n"
            "    except Exception as exc:\n"
            "        health.mark_disconnected(str(exc))\n"
            "def ok(client, health):\n"
            "    try:\n"
            "        client.go()\n"
            "    except Exception as e:\n"
            "        health.mark_disconnected(outbound_error_text(e))\n"
            '        return {"error": outbound_error_text(e)}\n',
            encoding="utf-8",
        )
        assert [line.split(":")[1] for line in _escapes(sample)] == ["5", "10", "15"]


# ---------------------------------------------------------------------------------------------------------------------
# The routes that proxy a cascor operation and put the failure in the HTTP detail. The adapter re-raises for these, so
# the route is where the text is built.
# ---------------------------------------------------------------------------------------------------------------------

# (adapter method, HTTP method, path, JSON body, detail prefix)
PROXY_ROUTES = [
    ("replay_snapshot", "POST", "/api/v1/snapshots/snap-1/replay", None, "Failed to start replay"),
    ("replay_control", "POST", "/api/v1/snapshots/snap-1/replay/control", {"action": "play"}, "Replay control failed"),
    ("resume_snapshot", "POST", "/api/v1/snapshots/snap-1/resume", None, "Failed to resume"),
    ("retrain_snapshot", "POST", "/api/v1/snapshots/snap-1/retrain", None, "Failed to retrain"),
    ("patch_weights", "PATCH", "/api/v1/network/weights", {"target": "output", "field": "weights", "values": [0.1]}, "patch_weights failed"),
    ("add_hidden_unit", "POST", "/api/v1/network/hidden-units", {"weights": [0.1]}, "add_hidden_unit failed"),
    ("remove_hidden_unit", "DELETE", "/api/v1/network/hidden-units/2", None, "remove_hidden_unit failed"),
    ("save_snapshot", "POST", "/api/v1/snapshots?name=snap_683", None, "Failed to create snapshot"),
]


@pytest.fixture
def service_routes(monkeypatch, tmp_path):
    """The real app, its backend swapped for a service backend whose adapter the test drives."""
    from unittest.mock import AsyncMock

    from fastapi.testclient import TestClient

    import main

    adapter = MagicMock()
    backend = MagicMock()
    backend.backend_type = "service"
    backend._adapter = adapter
    backend.is_training_active.return_value = False
    backend.shutdown = AsyncMock()
    with TestClient(main.app) as client:
        monkeypatch.setattr(main, "backend", backend)
        monkeypatch.setattr(main, "_snapshots_dir", str(tmp_path))
        yield client, adapter


@pytest.mark.unit
class TestTheProxyRoutes:
    @pytest.mark.parametrize("attribute, method, path, body, prefix", PROXY_ROUTES, ids=[route[0] for route in PROXY_ROUTES])
    def test_transport_text_never_reaches_the_detail(self, service_routes, attribute, method, path, body, prefix):
        client, adapter = service_routes
        getattr(adapter, attribute).side_effect = JuniperCascorClientError(TRANSPORT_TEXT)
        response = client.request(method, path, json=body)
        assert response.status_code == 500
        assert response.json()["detail"] == f"{prefix}: JuniperCascorClientError"

    @pytest.mark.parametrize("attribute, method, path, body, prefix", PROXY_ROUTES, ids=[route[0] for route in PROXY_ROUTES])
    def test_cascors_answer_still_reaches_it(self, service_routes, attribute, method, path, body, prefix):
        """CAN-015h h-5 surfaces cascor's detail verbatim (FSM 409, shape 422): that is an answer, and it passes."""
        client, adapter = service_routes
        getattr(adapter, attribute).side_effect = JuniperCascorConflictError("Network is not in Investigating", status_code=409)
        response = client.request(method, path, json=body)
        assert response.status_code == 500
        assert response.json()["detail"] == f"{prefix}: Network is not in Investigating"
