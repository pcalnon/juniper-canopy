#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       1.0.0
# File Name:     test_outbound_secret_leaks_boot.py
# File Path:     src/tests/regression/
#
# Created Date:  2026-09-24
# Last Modified: 2026-09-24
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#     #683 validation, in FRESH canopy processes: a real ``import main`` with the environment under test, the real
#     lifespan, canopy's own logs/system.log in a temporary working directory, and a local fake upstream that records
#     every request canopy sends it.
#
#     Item 1: a padded outbound key (juniper-cascor, juniper-data, recurrence) is refused where it is read, WARNed once by
#     NAME through the configured system logger, and never sent: no request, log record, log file, console line or API
#     body carries it -- including the /api/train/start body an ANONYMOUS caller reads with auth enabled.
#     Item 2: with auth enabled, a keyless request presenting a non-ASCII X-API-Key is a 401 and a WebSocket presenting
#     one is closed 4001 -- never an exception, whose error report recorded the real key.
#     Item 3: the four docs routes follow the auth handler itself: 404 for a real key in CANOPY_API_KEY or in the file
#     CANOPY_API_KEY_FILE names, 200 for every blank key, NBSP-only included.
#
#####################################################################################################################################################################################################
"""Regression tests, fresh interpreters: no outbound key a client would refuse is ever sent, logged or returned."""

import http.server
import json
import os
import shutil
import socket
import subprocess  # nosec B404 -- runs this tree's canopy in a fresh interpreter
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

# src/tests/regression/<this> -> parents[2] == src/
_SRC = Path(__file__).resolve().parents[2]
_REPORT_PREFIX = "__CANOPY_683V_BOOT_REPORT__"
# Every variable a scenario sets is scrubbed from the inherited environment first, and a developer's Sentry DSN must
# never receive a test boot.
_SCRUBBED_PREFIXES = (
    "CANOPY_API_KEY",
    "JUNIPER_CANOPY_REQUIRE_AUTH",
    "JUNIPER_SKIP_AUTH_POSTURE_CHECK",
    "JUNIPER_CANOPY_SERVER__",
    "JUNIPER_CANOPY_DEMO_MODE",
    "JUNIPER_CANOPY_CASCOR",
    "JUNIPER_CANOPY_RECURRENCE",
    "JUNIPER_CANOPY_JUNIPER_DATA",
    "JUNIPER_CASCOR_API_KEY",
    "JUNIPER_DATA_API_KEY",
    "JUNIPER_DATA_URL",
    "JUNIPER_RECURRENCE_API_KEY",
    "CASCOR_SERVICE_URL",
    "CASCOR_DEMO_MODE",
    "RECURRENCE_SERVICE_URL",
)
MARK = "LEAKME"
DOCS_PATHS = ("/docs", "/docs/oauth2-redirect", "/openapi.json", "/redoc")

# Written out, not imported: an expectation imported from the module under test moves with any mutant that rewrites it.
REFUSED_ENV_WARNING = (
    "{var} holds a key canopy does not send: it has leading or trailing whitespace, or a character outside printable ASCII (0x21-0x7E) such as a line break, a space or a non-ASCII character. " + "HTTP clients refuse such a header value, and the error they raise quotes it. " + "Canopy treats {var} as empty instead, so no client is handed the key: a request it would have authenticated carries the next key canopy falls back to, or none. Remove the whitespace, line break or non-ASCII character from {var}."
)
STARTUP_LINE = "Starting Juniper Canopy application"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class _Upstream:
    """A local stand-in for juniper-cascor / juniper-data / recurrence: answers every request 200 JSON, records it.

    A WebSocket upgrade also gets a plain 200, so canopy's stream clients fail their handshake -- after sending it,
    which is the part recorded.
    """

    def __init__(self) -> None:
        self.requests: list[dict] = []
        upstream = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def _answer(self) -> None:
                length = int(self.headers.get("Content-Length") or 0)
                if length:
                    self.rfile.read(length)
                upstream.requests.append({"line": self.requestline, "headers": dict(self.headers.items())})
                body = b'{"status": "ok"}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(body)

            do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = _answer

            def log_message(self, *args) -> None:  # the test's own console stays quiet
                pass

        self._server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self._server.server_address[1]}"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()


def _run_fresh(workdir: Path, script: str, env: dict[str, str]) -> dict:
    """Run ``script`` in a fresh interpreter in ``workdir``, with this tree's ``src/`` first on the path."""
    (workdir / "conf").mkdir(parents=True, exist_ok=True)
    shutil.copy(_SRC.parent / "conf" / "logging_config.yaml", workdir / "conf" / "logging_config.yaml")
    child_env = {name: value for name, value in os.environ.items() if not name.startswith(_SCRUBBED_PREFIXES) and "SENTRY" not in name.upper()}
    child_env.update(
        {
            "PYTHONPATH": os.pathsep.join([str(_SRC), child_env.get("PYTHONPATH", "")]),
            "PYTHONDONTWRITEBYTECODE": "1",
            "JUNIPER_CANOPY_LOG_LEVEL": "DEBUG",
            "JUNIPER_CANOPY_SERVER__PORT": str(_free_port()),
            # Nothing listens here unless a scenario points it at the fake upstream.
            "JUNIPER_DATA_URL": f"http://127.0.0.1:{_free_port()}",
        }
    )
    child_env.update(env)
    result = subprocess.run([sys.executable, "-c", script], cwd=str(workdir), env=child_env, capture_output=True, text=True, timeout=240)  # nosec B603
    report_lines = [line for line in result.stdout.splitlines() if line.startswith(_REPORT_PREFIX)]
    assert result.returncode == 0 and len(report_lines) == 1, f"the fresh canopy process failed (exit {result.returncode}):\n{result.stderr[-4000:]}"
    report = json.loads(report_lines[0][len(_REPORT_PREFIX) :])
    # juniper-canopy is often installed editable against ANOTHER checkout; a child that imported that would measure the
    # wrong code while looking fine.
    assert Path(report["main_file"]).resolve() == (_SRC / "main.py").resolve(), f"the child imported {report['main_file']}, not this tree's main.py"
    report["console"] = "\n".join(line for line in (result.stdout + "\n" + result.stderr).splitlines() if not line.startswith(_REPORT_PREFIX))
    report["log_files"] = {path.name: path.read_text(encoding="utf-8", errors="replace") for path in sorted((workdir / "logs").glob("*.log"))}
    return report


def _run_all(tmp_path_factory, scenarios: dict[str, tuple[str, dict[str, str]]]) -> dict[str, dict]:
    """Run each ``name: (script, env)`` scenario in its own process, three at a time (each imports the whole app).

    The working directories are made here, in this thread. ``tmp_path_factory`` creates its base directory on first use
    and is not thread-safe: when this fixture is the session's first user, three first calls racing from the pool each
    created one, and pytest refused the path ("data is not a normalized and relative path").
    """
    workdirs = {name: tmp_path_factory.mktemp(name) for name in scenarios}

    def one(item):
        name, (script, env) = item
        return name, _run_fresh(workdirs[name], script, env)

    with ThreadPoolExecutor(max_workers=3) as pool:
        return dict(pool.map(one, scenarios.items()))


# ---------------------------------------------------------------------------------------------------------------------
# Items 1 and 2: the outbound keys, and a non-ASCII presented key.
# ---------------------------------------------------------------------------------------------------------------------

# Records EVERY log record any logger handles -- whatever its level, handlers or propagation -- by wrapping
# ``Logger.callHandlers``, the hook Sentry's logging integration wraps too. Installed before ``import main``. Then runs
# the scenario's steps against the real app with its lifespan running.
_LEAK_BOOT = """
import json
import logging
import os
import time

records = []
_real_call_handlers = logging.Logger.callHandlers


def _every_record(self, record):
    records.append(record)
    return _real_call_handlers(self, record)


logging.Logger.callHandlers = _every_record

import main
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

steps = json.loads(os.environ["LEAK_PROBE_STEPS"])
bodies = []
with TestClient(main.app) as client:
    for step in steps:
        kind = step[0]
        if kind == "sleep":
            time.sleep(step[1])
            continue
        if kind == "anonymous-start":
            # The key-exempt browser control surface: a keyless CSRF mint, then Start from an allowlisted Origin.
            token = client.get("/api/csrf").json().get("csrf_token") or ""
            response = client.post("/api/train/start", headers={"Origin": "http://localhost:8050", "X-CSRF-Token": token})
        elif kind == "non-ascii-key":
            # Raw latin-1 byte 0xA0, as both uvicorn parsers pass it.
            response = client.get("/api/status", headers={"X-API-Key": b"\\xa0"})
        elif kind == "non-ascii-ws-key":
            try:
                with client.websocket_connect("/ws/training?api_key=%C2%A0") as ws:
                    ws.receive_text()
                bodies.append({"step": kind, "status": None, "text": "connected"})
            except WebSocketDisconnect as exc:
                bodies.append({"step": kind, "status": exc.code, "text": ""})
            continue
        else:
            _, method, path, body = step
            response = client.request(method, path, json=body)
        bodies.append({"step": " ".join(str(part) for part in step[:3]), "status": response.status_code, "text": response.text})


def render(record):
    parts = [record.getMessage(), repr(record.__dict__)]
    if record.exc_info:
        parts.append(logging.Formatter().formatException(record.exc_info))
    return "\\n".join(parts)


report = {
    "main_file": main.__file__,
    "auth_enabled": main.api_key_auth.enabled,
    "bodies": bodies,
    "records": len(records),
    "record_hits": [{"logger": r.name, "level": r.levelname, "text": render(r)[:400]} for r in records if "LEAKME" in render(r)],
    "warnings": [{"logger": r.name, "level": r.levelname, "message": r.getMessage()} for r in records if r.levelno >= logging.WARNING],
}
print("__CANOPY_683V_BOOT_REPORT__" + json.dumps(report))
"""


@pytest.fixture(scope="module")
def leak_boots(tmp_path_factory):
    upstream = _Upstream()
    try:
        scenarios = {
            # Service mode, auth ON with a real canopy key, a padded cascor key (and no data key to fall back to).
            "cascor": (
                _LEAK_BOOT,
                {
                    "JUNIPER_CANOPY_DEMO_MODE": "0",
                    "JUNIPER_CANOPY_CASCOR_SERVICE_URL": upstream.url,
                    "CANOPY_API_KEY": "real-canopy-key-683v",
                    "JUNIPER_CASCOR_API_KEY": f"{MARK}-cascor-key\n",
                    "LEAK_PROBE_STEPS": json.dumps([["anonymous-start"], ["sleep", 2], ["non-ascii-key"], ["non-ascii-ws-key"]]),
                },
            ),
            # Demo mode, a padded shared juniper-data key; the startup probe finds the fake juniper-data healthy, so the
            # generators proxy calls it too.
            "data": (
                _LEAK_BOOT,
                {
                    "JUNIPER_CANOPY_DEMO_MODE": "1",
                    "JUNIPER_DATA_URL": upstream.url,
                    "JUNIPER_DATA_API_KEY": f" {MARK}-data-key",
                    "LEAK_PROBE_STEPS": json.dumps([["http", "GET", "/api/dataset/generators", None], ["http", "GET", "/api/status", None]]),
                },
            ),
            # The recurrence model: select it, start a fit, read the status a failed fit's reason would reach.
            "recurrence": (
                _LEAK_BOOT,
                {
                    "JUNIPER_CANOPY_DEMO_MODE": "1",
                    "JUNIPER_CANOPY_RECURRENCE_SERVICE_URL": upstream.url,
                    "JUNIPER_RECURRENCE_API_KEY": f"{MARK}-rec-key ",
                    "LEAK_PROBE_STEPS": json.dumps(
                        [
                            ["http", "POST", "/api/train/stop", None],
                            ["sleep", 1],
                            ["http", "POST", "/api/model/select", {"nn_model": "recurrence"}],
                            ["http", "POST", "/api/train/start", {"dataset": {"generator": "spiral"}}],
                            ["sleep", 2],
                            ["http", "GET", "/api/status", None],
                        ]
                    ),
                },
            ),
        }
        reports = _run_all(tmp_path_factory, scenarios)
        yield reports, list(upstream.requests)
    finally:
        upstream.close()


def _assert_no_leak(report: dict) -> None:
    assert report["records"] > 0
    assert report["record_hits"] == [], f"log records carrying the key: {report['record_hits']}"
    assert MARK not in report["console"], "the key reached the console"
    for name, text in report["log_files"].items():
        assert MARK not in text, f"the key reached logs/{name}"
    for body in report["bodies"]:
        assert MARK not in body["text"], f"{body['step']} returned the key: {body['text'][:300]}"


def _refused_warnings(report: dict, var: str) -> list[dict]:
    return [warning for warning in report["warnings"] if warning["message"] == REFUSED_ENV_WARNING.format(var=var)]


@pytest.mark.timeout(600)
@pytest.mark.parametrize("scenario", ["cascor", "data", "recurrence"])
def test_a_padded_outbound_key_never_reaches_a_record_a_log_or_a_body(leak_boots, scenario):
    reports, _ = leak_boots
    _assert_no_leak(reports[scenario])


@pytest.mark.timeout(600)
def test_no_request_canopy_sends_carries_a_refused_key(leak_boots):
    """The wire itself: every request the fake upstreams received. The cascor streams' WebSocket upgrades included --
    websockets 16.0 SENT a key with a line break raw, and 17.1 refused it quoting the key."""
    _, requests_seen = leak_boots
    assert requests_seen, "canopy sent the fake upstream nothing, so nothing was measured"
    assert [request["line"] for request in requests_seen if MARK in json.dumps(request)] == []
    # No key reached it at all: each refused key had nothing to fall back to.
    assert [request["line"] for request in requests_seen if any(name.lower() == "x-api-key" for name in request["headers"])] == []


@pytest.mark.timeout(600)
@pytest.mark.parametrize("scenario, var", [("cascor", "JUNIPER_CASCOR_API_KEY"), ("data", "JUNIPER_DATA_API_KEY"), ("recurrence", "JUNIPER_RECURRENCE_API_KEY")])
def test_a_refused_outbound_key_warns_once_by_name_through_the_system_logger(leak_boots, scenario, var):
    reports, _ = leak_boots
    report = reports[scenario]
    assert _refused_warnings(report, var) == [{"logger": "system", "level": "WARNING", "message": REFUSED_ENV_WARNING.format(var=var)}]
    assert report["log_files"]["system.log"].count(REFUSED_ENV_WARNING.format(var=var)) == 1


@pytest.mark.timeout(600)
def test_a_key_read_at_import_is_reported_before_startup_goes_on(leak_boots):
    """``settings`` reads the juniper-data key at import; its WARNING follows the posture check, ahead of the rest of
    startup, not only after ``create_backend`` (which reads the cascor key and reports again)."""
    reports, _ = leak_boots
    lines = reports["data"]["log_files"]["system.log"].splitlines()
    warning = next(index for index, line in enumerate(lines) if line.endswith(REFUSED_ENV_WARNING.format(var="JUNIPER_DATA_API_KEY")))
    startup = next(index for index, line in enumerate(lines) if line.endswith(STARTUP_LINE))
    assert warning < startup


@pytest.mark.timeout(600)
def test_an_anonymous_start_answers_without_the_key(leak_boots):
    """The validator's extraction: auth ON, no key, a CSRF token minted keyless, Start from an allowlisted Origin."""
    reports, _ = leak_boots
    report = reports["cascor"]
    assert report["auth_enabled"] is True
    start = next(body for body in report["bodies"] if body["step"] == "anonymous-start")
    assert start["status"] in (200, 409), start
    assert MARK not in start["text"]


@pytest.mark.timeout(600)
def test_a_non_ascii_presented_key_is_a_401_not_an_exception(leak_boots):
    """Item 2: ``compare_digest`` on ``str`` raised ``TypeError`` for it -- a 500 whose Sentry event recorded the real key."""
    reports, _ = leak_boots
    bodies = {body["step"]: body for body in reports["cascor"]["bodies"]}
    assert bodies["non-ascii-key"]["status"] == 401
    # A TypeError here escaped the WebSocket handler and failed the whole child process instead.
    assert bodies["non-ascii-ws-key"]["status"] == 4001


# ---------------------------------------------------------------------------------------------------------------------
# Item 3: the docs switch is the auth switch.
# ---------------------------------------------------------------------------------------------------------------------

_DOCS_BOOT = """
import json
import os

import main
from fastapi.testclient import TestClient

key = os.environ.get("DOCS_PROBE_KEY") or ""
paths = ("/docs", "/docs/oauth2-redirect", "/openapi.json", "/redoc")
report = {"main_file": main.__file__, "auth_enabled": main.api_key_auth.enabled, "docs_enabled": main._docs_enabled}
with TestClient(main.app) as client:
    report["keyless"] = {path: client.get(path).status_code for path in paths}
    if key:
        report["keyed"] = {path: client.get(path, headers={"X-API-Key": key}).status_code for path in paths}
print("__CANOPY_683V_BOOT_REPORT__" + json.dumps(report))
"""


@pytest.fixture(scope="module")
def docs_boots(tmp_path_factory):
    files = tmp_path_factory.mktemp("docs-key-files")
    real_file = files / "real"
    real_file.write_text("real-file-key-683v\n", encoding="utf-8")
    blank_file = files / "blank"
    blank_file.write_text("  \n", encoding="utf-8")
    scenarios = {
        "env-real": {"CANOPY_API_KEY": "real-env-key-683v", "DOCS_PROBE_KEY": "real-env-key-683v"},
        # The file wins: CANOPY_API_KEY is not read at all while the file exists.
        "file-real": {"CANOPY_API_KEY_FILE": str(real_file), "DOCS_PROBE_KEY": "real-file-key-683v"},
        "env-empty": {"CANOPY_API_KEY": ""},
        "env-nbsp": {"CANOPY_API_KEY": "\u00a0"},
        # A blank file shadows a real env key: auth is off, so the docs are served.
        "file-blank": {"CANOPY_API_KEY_FILE": str(blank_file), "CANOPY_API_KEY": "real-env-key-the-file-shadows"},
    }
    return _run_all(tmp_path_factory, {name: (_DOCS_BOOT, {"JUNIPER_CANOPY_DEMO_MODE": "1", **env}) for name, env in scenarios.items()})


@pytest.mark.timeout(600)
@pytest.mark.parametrize("scenario", ["env-real", "file-real"])
def test_a_real_key_turns_the_docs_off(docs_boots, scenario):
    """404 for a caller that PRESENTS the key: the routes are not mounted, not merely refused."""
    report = docs_boots[scenario]
    assert report["auth_enabled"] is True
    assert report["docs_enabled"] is False
    assert report["keyed"] == dict.fromkeys(DOCS_PATHS, 404)


@pytest.mark.timeout(600)
@pytest.mark.parametrize("scenario", ["env-empty", "env-nbsp", "file-blank"])
def test_a_blank_key_serves_the_docs_exactly_as_no_key_does(docs_boots, scenario):
    report = docs_boots[scenario]
    assert report["auth_enabled"] is False
    assert report["docs_enabled"] is True
    assert report["keyless"] == dict.fromkeys(DOCS_PATHS, 200)
