#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       1.1.0
# File Name:     test_blank_api_key_warning_boot.py
# File Path:     src/tests/regression/
#
# Created Date:  2026-09-23
# Last Modified: 2026-09-24
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#     APD-ECO-008 follow-up. A SET-but-blank CANOPY_API_KEY disables API-key auth, and the boot posture check words that
#     exactly like an unset key ("running OPEN"), so the blank case carries its own WARNING. The first version logged it
#     where the key is read: ``get_api_key_auth()``, which first runs at import (``api_key_auth = get_api_key_auth()`` in
#     main.py), before the lifespan's ``configure_logging``. There it reached only Python's last-resort handler -- no
#     level, no JSON, no Sentry, never logs/system.log -- and the test that covered it used ``caplog``, which hides that.
#     These tests run canopy's REAL lifespan and capture on the system logger that ``configure_logging`` has configured
#     by then, and they record whether configuration had already happened when the record arrived.
#
#     #678 follow-up. The in-process tests rebuild the auth singleton themselves, so they could not see whether main.py
#     builds its handler through ``get_api_key_auth()`` -- the one step the WARNING depends on; the fresh-interpreter
#     tests at the end of this file can. They also pin the WARNING under JUNIPER_CANOPY_REQUIRE_AUTH=true, the two other
#     readers of the key (the docs switch and the dashboard's self-calls), the padded-key and missing-key-file WARNINGs,
#     and that a padded key never reaches a log record.
#
#####################################################################################################################################################################################################
"""Regression tests: the set-but-blank CANOPY_API_KEY WARNING is emitted by the lifespan, once, after logging is configured."""

import ast
import json
import logging
import os
import shutil
import socket
import subprocess  # nosec B404 -- runs this tree's canopy in a fresh interpreter
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Written out rather than imported from security.py: an expectation imported from the
# module under test moves with any mutant that rewrites the advice there, and passes.
# src/tests/unit/test_security.py pins the same two texts at the unit level.
ENV_WARNING = "CANOPY_API_KEY is set but blank (empty or whitespace-only), so API-key authentication is DISABLED: every route, including the state-changing /api/* routes and the /api/train/* control surface, serves without a key, exactly as with no key configured. Set a real key, or unset CANOPY_API_KEY for an intentional open profile."
FILE_WARNING = "The file named by CANOPY_API_KEY_FILE is blank (empty or whitespace-only), so API-key authentication is DISABLED: every route, including the state-changing /api/* routes and the /api/train/* control surface, serves without a key, exactly as with no key configured. While CANOPY_API_KEY_FILE names an existing file it takes precedence and CANOPY_API_KEY is not read. Write a real key into that file, or unset CANOPY_API_KEY_FILE to use CANOPY_API_KEY instead."

# The same two sources when JUNIPER_CANOPY_REQUIRE_AUTH=true makes the posture check refuse
# to start (#678 follow-up): nothing serves, so the texts above would be false there.
ENV_REFUSED_WARNING = "CANOPY_API_KEY is set but blank (empty or whitespace-only), so it counts as no key: it is the key the auth-posture check reports as not configured, and because JUNIPER_CANOPY_REQUIRE_AUTH is true, canopy refuses to start. Set a real key."
FILE_REFUSED_WARNING = "The file named by CANOPY_API_KEY_FILE is blank (empty or whitespace-only), so it counts as no key: it is the key the auth-posture check reports as not configured, and because JUNIPER_CANOPY_REQUIRE_AUTH is true, canopy refuses to start. While CANOPY_API_KEY_FILE names an existing file it takes precedence and CANOPY_API_KEY is not read. Write a real key into that file, or unset CANOPY_API_KEY_FILE to use CANOPY_API_KEY instead."

# The other two findings of the key's one read (#678 follow-up).
PADDED_KEY_WARNING = (
    "CANOPY_API_KEY has leading or trailing whitespace, or a line break, and API-key authentication is enabled with the key exactly as set. HTTP does not carry such a key reliably: uvicorn's parsers drop a header value's leading spaces and tabs, h11 drops its trailing ones as well, and a header cannot hold a line break."
    + " So callers presenting the key can fail to authenticate, and the dashboard's own requests to this API send no key at all when it starts with whitespace or holds a line break, because their HTTP client refuses to send it. Remove the whitespace and any line break from the key."
)
MISSING_KEY_FILE_WARNING = "CANOPY_API_KEY_FILE is set but does not name an existing file, so it is ignored: the key is read from CANOPY_API_KEY instead, exactly as if CANOPY_API_KEY_FILE were unset. Point CANOPY_API_KEY_FILE at the key file, or unset it."

# Common to every blank-key text and to nothing the posture check logs, so a mutant that
# rewords or repeats the WARNING is still COUNTED here, and fails on the count or the text.
BLANK_MARKER = "blank (empty or whitespace-only)"

# src/tests/regression/<this> -> parents[2] == src/
_SRC = Path(__file__).resolve().parents[2]


class _Capture(logging.Handler):
    """Records every record with whether ``configure_logging`` had run when it arrived."""

    def __init__(self, state: dict) -> None:
        super().__init__(level=logging.DEBUG)
        self._state = state
        self.seen: list[tuple[logging.LogRecord, bool]] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.seen.append((record, self._state["configured"]))


@pytest.fixture
def boot(monkeypatch):
    """Run canopy's real lifespan N times; return the blank-key records the system logger received."""
    import main
    from frontend import internal_api

    state = {"configured": False, "configure_calls": 0}
    real_configure_logging = main.configure_logging

    def configure_logging_spy(*args, **kwargs):
        real_configure_logging(*args, **kwargs)
        state["configured"] = True
        state["configure_calls"] += 1

    monkeypatch.setattr(main, "configure_logging", configure_logging_spy)
    # The stdlib logger behind ``main.system_logger``: its handlers write logs/system.log,
    # and it propagates to the root handler ``configure_logging`` installs.
    system = main.system_logger.logger
    capture = _Capture(state)
    # Every record, not only the blank-key ones: the refused-boot test orders the WARNING
    # against the posture check's CRITICAL.
    state["capture"] = capture
    system.addHandler(capture)

    def run(startups: int) -> list[tuple[logging.LogRecord, bool]]:
        for _ in range(startups):
            with TestClient(main.app):
                pass
        return [(record, configured) for record, configured in capture.seen if BLANK_MARKER in record.getMessage()]

    try:
        yield run, state
    finally:
        system.removeHandler(capture)
        # internal_api caches the key per process; never let a blank one outlive this test.
        internal_api._canopy_api_key.cache_clear()


def _read_key_as_main_does_at_import(monkeypatch, tmp_path, source: str) -> None:
    """Configure the key's source, then rebuild the auth singleton the way main.py's import does."""
    import security

    monkeypatch.delenv("CANOPY_API_KEY_FILE", raising=False)
    monkeypatch.delenv("CANOPY_API_KEY", raising=False)
    if source == "env-blank":
        monkeypatch.setenv("CANOPY_API_KEY", " \t ")
    elif source == "file-blank":
        secret_file = tmp_path / "canopy_api_key"
        secret_file.write_text("  \n", encoding="utf-8")
        monkeypatch.setenv("CANOPY_API_KEY_FILE", str(secret_file))
        # The case the first WARNING got wrong: the env var holds a real key the file overrides.
        monkeypatch.setenv("CANOPY_API_KEY", "real-key-the-file-overrides")
    elif source == "env-real":
        monkeypatch.setenv("CANOPY_API_KEY", "real-key")
    security.reset_security_state()
    security.get_api_key_auth()


@pytest.mark.parametrize("source, expected", [("env-blank", ENV_WARNING), ("file-blank", FILE_WARNING)], ids=["env", "file"])
def test_blank_key_warns_once_through_the_configured_logger(boot, monkeypatch, tmp_path, source, expected):
    run, state = boot
    _read_key_as_main_does_at_import(monkeypatch, tmp_path, source)

    blank = run(startups=2)

    assert state["configure_calls"] == 2, "both startups must have run the real lifespan"
    assert len(blank) == 1, f"exactly one blank-key record across two startups, got {[r.getMessage() for r, _ in blank]}"
    record, configured = blank[0]
    assert configured is True, "the WARNING must be emitted after configure_logging, not where the key is read"
    assert record.levelno == logging.WARNING
    assert record.getMessage() == expected


@pytest.mark.parametrize("source", ["unset", "env-real"])
def test_unset_or_real_key_emits_no_blank_key_warning(boot, monkeypatch, tmp_path, source):
    run, state = boot
    _read_key_as_main_does_at_import(monkeypatch, tmp_path, source)

    assert run(startups=1) == []
    assert state["configure_calls"] == 1


@pytest.mark.parametrize("source, expected", [("env-blank", ENV_REFUSED_WARNING), ("file-blank", FILE_REFUSED_WARNING)], ids=["env", "file"])
def test_blank_key_warns_when_require_auth_refuses_the_boot(boot, monkeypatch, tmp_path, source, expected):
    """#678 follow-up: under JUNIPER_CANOPY_REQUIRE_AUTH=true the posture check refuses first.

    Its CRITICAL says NO API key is configured, which misleads an operator whose key is
    SET but blank -- the confusion the WARNING exists to clear up -- and #678 never got
    that far: the WARNING came after the posture call, which raised. It now follows the
    CRITICAL, once, worded for a boot that is failing (the open-boot text would claim
    routes serve without a key, and nothing serves), and the refusal still propagates.
    """
    from juniper_service_core import AuthPostureError

    import main

    run, state = boot
    monkeypatch.delenv("JUNIPER_SKIP_AUTH_POSTURE_CHECK", raising=False)
    monkeypatch.setattr(main.settings, "require_auth", True)
    _read_key_as_main_does_at_import(monkeypatch, tmp_path, source)

    for _ in range(2):
        with pytest.raises(AuthPostureError):
            run(startups=1)

    seen = state["capture"].seen
    critical = [index for index, (record, _) in enumerate(seen) if record.levelno == logging.CRITICAL]
    blank = [(index, record, configured) for index, (record, configured) in enumerate(seen) if BLANK_MARKER in record.getMessage()]
    assert state["configure_calls"] == 2, "both startups must have run the real lifespan"
    assert len(critical) == 2, "both startups must have been refused by the posture check"
    assert len(blank) == 1, f"exactly one blank-key record across two refused startups, got {[r.getMessage() for _, r, _ in blank]}"
    index, record, configured = blank[0]
    assert configured is True
    assert record.levelno == logging.WARNING
    assert record.getMessage() == expected
    assert critical[0] < index < critical[1], "the WARNING must follow the first refusal's CRITICAL, before the second startup"


def test_lifespan_reports_right_after_the_posture_check():
    """Source-order pin, the companion of test_auth_posture_boot_check.py's: the report
    follows ``enforce_auth_posture`` on both of its outcomes -- inside the handler that
    re-raises a refused boot, and right after a check that returns -- and both precede
    the bind guard and backend creation."""
    src = (_SRC / "main.py").read_text(encoding="utf-8")
    lifespan = next(node for node in ast.walk(ast.parse(src)) if isinstance(node, ast.AsyncFunctionDef) and node.name == "lifespan")

    def calls(stmt: ast.AST, name: str) -> bool:
        return any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == name for node in ast.walk(stmt))

    body = lifespan.body
    [posture] = [index for index, stmt in enumerate(body) if calls(stmt, "enforce_auth_posture")]
    guarded = body[posture]
    assert isinstance(guarded, ast.Try), "the posture check must run inside a try that reports a refused boot"
    assert len(guarded.body) == 1 and calls(guarded.body[0], "enforce_auth_posture")
    assert not guarded.orelse and not guarded.finalbody
    [handler] = guarded.handlers
    assert handler.type is not None and ast.unparse(handler.type) == "AuthPostureError"
    assert [ast.unparse(stmt) for stmt in handler.body] == ["report_api_key_configuration(system_logger, boot_refused=True)", "raise"]
    assert ast.unparse(body[posture + 1]) == "report_api_key_configuration(system_logger)"
    bind_guard = next(index for index, stmt in enumerate(body) if calls(stmt, "enforce_loopback_bind_guard"))
    backend = next(index for index, stmt in enumerate(body) if calls(stmt, "create_backend"))
    assert posture + 1 < bind_guard < backend


# ---------------------------------------------------------------------------------------------------------------------
# #678 follow-up: FRESH interpreters.
#
# Everything above rebuilds the auth singleton itself (``_read_key_as_main_does_at_import``), so it cannot see whether
# main.py builds its handler through ``get_api_key_auth()`` -- the step the WARNING depends on. The validation of #678
# rewrote that line as ``api_key_auth = APIKeyAuth([_k] if (_k := get_secret("CANOPY_API_KEY")) else None)`` (mutant
# V8): the whole CI lane passed, 6866 tests, and real uvicorn logged no blank-key line anywhere. These tests run canopy
# in a fresh interpreter instead: a real ``import main`` with the key set, the real lifespan, and canopy's own log
# files. The loggers write under the WORKING directory (``logger.logger.LoggerFactory`` reads
# ``conf/logging_config.yaml`` and ``log_directory: logs/`` relative to it), so each process runs in a temporary one,
# and ``logs/system.log`` there holds that boot's lines and nothing else.
# ---------------------------------------------------------------------------------------------------------------------

_REPORT_PREFIX = "__CANOPY_FRESH_BOOT_REPORT__"
# Scrubbed from the child's environment: the key under test is set explicitly, the posture is the code default, the
# port is chosen here, and a developer's Sentry DSN must never receive a test boot.
_SCRUBBED_PREFIXES = ("CANOPY_API_KEY", "JUNIPER_CANOPY_REQUIRE_AUTH", "JUNIPER_SKIP_AUTH_POSTURE_CHECK", "JUNIPER_CANOPY_SERVER__")
DOCS_PATHS = ("/docs", "/docs/oauth2-redirect", "/openapi.json", "/redoc")


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _fresh_canopy(workdir: Path, script: str, env: dict[str, str]) -> dict:
    """Run ``script`` in a fresh interpreter, in ``workdir``, with this tree's ``src/`` first on the path.

    Returns the JSON report the script prints, plus its stdout (report line removed), its stderr and the text of every
    ``logs/*.log`` it wrote.
    """
    (workdir / "conf").mkdir(parents=True, exist_ok=True)
    # The repo's logging config, so the loggers are set up exactly as for a boot from the repo root.
    shutil.copy(_SRC.parent / "conf" / "logging_config.yaml", workdir / "conf" / "logging_config.yaml")
    child_env = {name: value for name, value in os.environ.items() if not name.startswith(_SCRUBBED_PREFIXES) and "SENTRY" not in name.upper()}
    child_env.update(
        {
            "PYTHONPATH": os.pathsep.join([str(_SRC), child_env.get("PYTHONPATH", "")]),
            "PYTHONDONTWRITEBYTECODE": "1",
            "JUNIPER_CANOPY_DEMO_MODE": "1",
            "JUNIPER_CANOPY_LOG_LEVEL": "DEBUG",
            # Nothing listens on either port, so each refuses at once: juniper-data is probed at startup, and the
            # dashboard's self-calls target the server port.
            "JUNIPER_DATA_URL": f"http://127.0.0.1:{_free_port()}",
            "JUNIPER_CANOPY_SERVER__PORT": str(_free_port()),
        }
    )
    child_env.update(env)
    result = subprocess.run([sys.executable, "-c", script], cwd=str(workdir), env=child_env, capture_output=True, text=True, timeout=240)  # nosec B603
    report_lines = [line for line in result.stdout.splitlines() if line.startswith(_REPORT_PREFIX)]
    assert result.returncode == 0 and len(report_lines) == 1, f"the fresh canopy process failed (exit {result.returncode}):\n{result.stderr[-4000:]}"
    report = json.loads(report_lines[0][len(_REPORT_PREFIX) :])
    # juniper-canopy is often installed editable against ANOTHER checkout; an import that resolved there would
    # measure the wrong code while looking fine.
    assert Path(report["main_file"]).resolve() == (_SRC / "main.py").resolve(), f"the child imported {report['main_file']}, not this tree's main.py"
    report["stdout"] = "\n".join(line for line in result.stdout.splitlines() if not line.startswith(_REPORT_PREFIX))
    report["stderr"] = result.stderr
    report["log_files"] = {path.name: path.read_text(encoding="utf-8", errors="replace") for path in sorted((workdir / "logs").glob("*.log"))}
    return report


# A real ``import main`` with a blank key, then two real startups; the second also requests the docs routes.
_BLANK_KEY_BOOT = """
import json

import main
import security
from fastapi.testclient import TestClient
from frontend.internal_api import internal_api_headers

report = {
    "main_file": main.__file__,
    "handler_is_the_singleton": main.api_key_auth is security._api_key_auth,
    "auth_enabled": main.api_key_auth.enabled,
    "docs_enabled": main._docs_enabled,
    "self_call_sends_a_key": "X-API-Key" in internal_api_headers(),
}
with TestClient(main.app):
    pass
with TestClient(main.app) as client:
    report["docs_status"] = {path: client.get(path).status_code for path in ("/docs", "/docs/oauth2-redirect", "/openapi.json", "/redoc")}
print("__CANOPY_FRESH_BOOT_REPORT__" + json.dumps(report))
"""


@pytest.fixture(scope="module")
def blank_key_fresh_boot(tmp_path_factory):
    """One fresh canopy process whose CANOPY_API_KEY env var is whitespace-only."""
    return _fresh_canopy(tmp_path_factory.mktemp("blank-key-boot"), _BLANK_KEY_BOOT, {"CANOPY_API_KEY": " \t "})


@pytest.mark.timeout(300)
def test_a_fresh_process_builds_its_auth_handler_through_get_api_key_auth(blank_key_fresh_boot):
    """The blank-key WARNING exists only because main.py's import reads the key through ``get_api_key_auth()``,
    which records what it found. A handler built any other way records nothing, so the WARNING vanishes."""
    assert blank_key_fresh_boot["handler_is_the_singleton"] is True, "main.api_key_auth is not security's singleton: main.py built its handler another way, and the blank key was never recorded"
    assert blank_key_fresh_boot["auth_enabled"] is False


@pytest.mark.timeout(300)
def test_a_fresh_boot_writes_the_blank_key_warning_to_system_log_once(blank_key_fresh_boot):
    """The end-to-end form of the in-process tests: one line in canopy's own logs/system.log, across two startups."""
    system_log = blank_key_fresh_boot["log_files"].get("system.log", "")
    lines = [line for line in system_log.splitlines() if BLANK_MARKER in line]
    assert len(lines) == 1, f"exactly one blank-key line in logs/system.log across two startups, got {lines}"
    assert " | WARNING | " in lines[0]
    assert lines[0].endswith(ENV_WARNING)


@pytest.mark.timeout(300)
def test_a_whitespace_only_env_key_serves_the_docs_exactly_as_no_key_does(blank_key_fresh_boot):
    """#678 follow-up: ``_docs_enabled`` read the raw value, so these four routes answered 404 for a whitespace-only
    key while every other route served without one. With no key configured they serve, and now so they do here."""
    assert blank_key_fresh_boot["docs_enabled"] is True
    assert blank_key_fresh_boot["docs_status"] == dict.fromkeys(DOCS_PATHS, 200)


@pytest.mark.timeout(300)
def test_a_whitespace_only_env_key_puts_no_key_on_a_self_call(blank_key_fresh_boot):
    """#678 follow-up: the dashboard's self-calls sent the raw whitespace key, which ``requests`` refuses (InvalidHeader)
    -- so every self-call failed, although auth was off. With no key configured they send none, and now so they do here."""
    assert blank_key_fresh_boot["self_call_sends_a_key"] is False


# The padded keys the self-calls are driven with. The first is the one main.py reads at import (auth is enabled on it,
# with the key exactly as set); each later one replaces it for the self-calls alone. Every one is a key ``requests``
# refuses to send, and whose refusal quoted it into the logs: leading whitespace, or a line break anywhere.
PADDED_KEYS = (" leaked-key-A1", "leaked-key-B2\n", "\tleaked-key-C3", "leaked-key-D4\r\nsecond-line-D4", "\u00a0leaked-key-E5")
MISSING_KEY_FILE_NAME = "no-such-key-file-F6"
# Text that must never reach a log record, a log file, the console or a dashboard alert. The missing file's NAME is
# here too: an operator who confuses the two variables puts the key itself in CANOPY_API_KEY_FILE.
LEAK_MARKERS = ("leaked-key-A1", "leaked-key-B2", "leaked-key-C3", "leaked-key-D4", "second-line-D4", "leaked-key-E5", MISSING_KEY_FILE_NAME)

# Records EVERY log record any logger handles -- whatever its level, handlers or propagation -- by wrapping
# ``Logger.callHandlers``, the hook Sentry's logging integration also wraps, so what Sentry could receive is what this
# sees. It is installed before ``import main``. Then, with the lifespan running, it drives real dashboard handlers whose
# self-calls fail -- each logs or returns the exception's text, at WARNING or DEBUG, through ``%s`` or an f-string --
# once per key, and counts the self-calls each one made.
_PADDED_KEY_BOOT = """
import json
import logging
import os

records = []
_real_call_handlers = logging.Logger.callHandlers


def _every_record(self, record):
    records.append(record)
    return _real_call_handlers(self, record)


logging.Logger.callHandlers = _every_record

import requests

self_calls = []
_real_request = requests.sessions.Session.request


def _record_self_call(self, method, url, *args, **kwargs):
    self_calls.append({"url": str(url), "sends_a_key": "X-API-Key" in (kwargs.get("headers") or {})})
    return _real_request(self, method, url, *args, **kwargs)


requests.sessions.Session.request = _record_self_call

import main
from fastapi.testclient import TestClient
from frontend import internal_api

manager = main.dashboard_manager
HANDLERS = (
    ("_hydrate_selection_handler", {}),
    ("_update_network_info_handler", {"n": 1}),
    ("_update_dataset_store_handler", {"n": 1, "active_tab": "dataset"}),
    ("_update_workers_store_handler", {"n": 1, "active_tab": "workers"}),
    ("_update_stream_health_handler", {"n": 1}),
    ("_fetch_generators", {}),
    ("_resolve_model_class", {}),
    ("_fetch_pending_dataset_config", {}),
)


def drive():
    calls = []
    for name, kwargs in HANDLERS:
        manager._generators_cache = None  # it caches a failure too, and every round must self-call
        before = len(self_calls)
        outcome = getattr(manager, name)(**kwargs)
        made = [call for call in self_calls[before:] if call["url"].startswith(manager._api_base_url)]
        calls.append({"handler": name, "self_calls": len(made), "outcome": repr(outcome)})
    return calls


def render(record):
    parts = [record.getMessage(), repr(record.__dict__)]
    if record.exc_info:
        parts.append(logging.Formatter().formatException(record.exc_info))
    if record.stack_info:
        parts.append(record.stack_info)
    return "\\n".join(parts)


keys = json.loads(os.environ["PADDED_KEY_PROBE_KEYS"])
markers = json.loads(os.environ["PADDED_KEY_PROBE_MARKERS"])
report = {"main_file": main.__file__, "auth_enabled": main.api_key_auth.enabled, "rounds": []}
with TestClient(main.app):
    for index, key in enumerate(keys):
        if index:
            os.environ["CANOPY_API_KEY"] = key
            internal_api._canopy_api_key.cache_clear()
        report["rounds"].append({"sends_a_key": "X-API-Key" in internal_api.internal_api_headers(), "calls": drive()})
report["records"] = len(records)
report["record_hits"] = [{"logger": r.name, "level": r.levelname, "text": render(r)[:400]} for r in records if any(m in render(r) for m in markers)]
report["warnings"] = [{"logger": r.name, "level": r.levelname, "message": r.getMessage()} for r in records if r.levelno >= logging.WARNING]
report["self_calls_sending_a_key"] = sum(1 for call in self_calls if call["sends_a_key"] and call["url"].startswith(manager._api_base_url))
print("__CANOPY_FRESH_BOOT_REPORT__" + json.dumps(report))
"""


@pytest.fixture(scope="module")
def padded_key_fresh_boot(tmp_path_factory):
    """One fresh canopy process with a padded CANOPY_API_KEY and a CANOPY_API_KEY_FILE that names no file."""
    workdir = tmp_path_factory.mktemp("padded-key-boot")
    env = {
        "CANOPY_API_KEY": PADDED_KEYS[0],
        "CANOPY_API_KEY_FILE": str(workdir / MISSING_KEY_FILE_NAME),
        "PADDED_KEY_PROBE_KEYS": json.dumps(PADDED_KEYS),
        "PADDED_KEY_PROBE_MARKERS": json.dumps(LEAK_MARKERS),
    }
    return _fresh_canopy(workdir, _PADDED_KEY_BOOT, env)


@pytest.mark.timeout(300)
def test_a_padded_key_never_reaches_a_log_record(padded_key_fresh_boot):
    """#678 follow-up: a padded key ENABLES auth, and the dashboard's self-calls handed it to ``requests``, whose
    ``InvalidHeader`` quotes the whole value. The handlers log that text -- at WARNING, and so to Sentry -- and show it
    in their alerts: CANOPY_API_KEY=" leaked-key-XYZ123" logged ``Selection hydration read failed (Invalid leading
    whitespace ... ' leaked-key-XYZ123')``. Now no record, log file, console line or handler result carries it."""
    report = padded_key_fresh_boot
    assert report["auth_enabled"] is True, "a padded key is not blank: auth stays enabled with the key as set"
    assert len(report["rounds"]) == len(PADDED_KEYS)
    for index, round_ in enumerate(report["rounds"]):
        # Vacuity guard: every handler really self-called, so a refusal quoting the key had its chance to happen.
        assert all(call["self_calls"] >= 1 for call in round_["calls"]), f"round {index}: a handler made no self-call: {round_['calls']}"
        assert round_["sends_a_key"] is False, f"round {index}: the self-calls must send no key that requests refuses to send"
        for call in round_["calls"]:
            assert not [marker for marker in LEAK_MARKERS if marker in call["outcome"]], f"round {index}: {call['handler']} returned the key text: {call['outcome'][:300]}"
    assert report["self_calls_sending_a_key"] == 0
    assert report["records"] > 0
    assert report["record_hits"] == [], f"log records carrying the key: {report['record_hits']}"
    for marker in LEAK_MARKERS:
        assert marker not in report["stdout"] and marker not in report["stderr"], f"{marker!r} reached the console"
        for name, text in report["log_files"].items():
            assert marker not in text, f"{marker!r} reached logs/{name}"


@pytest.mark.timeout(300)
def test_a_padded_key_warns_once_at_boot(padded_key_fresh_boot):
    """#678 follow-up: auth is enabled on a padded key exactly as set (not stripped: that would need an owner ruling),
    so boot WARNs, once, through the system logger, and logs/system.log gets the line."""
    report = padded_key_fresh_boot
    padded = [warning for warning in report["warnings"] if warning["message"] == PADDED_KEY_WARNING]
    assert padded == [{"logger": "system", "level": "WARNING", "message": PADDED_KEY_WARNING}]
    assert report["log_files"]["system.log"].count(PADDED_KEY_WARNING) == 1


@pytest.mark.timeout(300)
def test_a_missing_key_file_warns_once_at_boot(padded_key_fresh_boot):
    """#678 follow-up: a CANOPY_API_KEY_FILE naming no file was ignored silently, exactly as if unset. It now WARNs,
    once, naming the variable and never the path it holds (the leak test above checks the path's text)."""
    report = padded_key_fresh_boot
    missing = [warning for warning in report["warnings"] if warning["message"] == MISSING_KEY_FILE_WARNING]
    assert missing == [{"logger": "system", "level": "WARNING", "message": MISSING_KEY_FILE_WARNING}]
    assert report["log_files"]["system.log"].count(MISSING_KEY_FILE_WARNING) == 1
