#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     2026-09-24_683_validation_leak_probes.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-09-24
# Last Modified: 2026-09-24
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   The #683 validation's leak probes, kept: does any
#                secret reach a log, Sentry, the wire or an API body?
#####################################################################
"""Leak probes for the juniper-canopy#683 validation findings (items 1-4), runnable against any canopy tree.

Project: juniper-canopy
Sub-Project: ad-hoc tooling
Author: Paul Calnon
Created: 2026-09-24
Status: ad-hoc -- investigation
Retire when: the #683 validation PR is merged and its CHANGELOG entry is released
Related: juniper-canopy#683 (head 8917fdac) and its independent validation, whose probes these are, ported from the
    validator's session scratchpad (``lib_probe.py``, ``e2e_other_secrets.py``, ``e2e_anon_extract.py``,
    ``sentry_probe.py``, ``file_linebreak_probe.py``, ``docs_switch_probe.py``) so the before/after evidence outlives it.

Each subcommand runs canopy -- or, for ``lib``, the client libraries alone -- in a FRESH interpreter, in a temporary
working directory with the repo's logging config, against local stand-ins for every upstream. ``TREE`` is a canopy
checkout (default: this one); run the same probe against the pre-fix tree and this one to see before and after.

Subcommands::

    lib                          do requests / cascor REST / data-client / httpx / cascor WS quote a padded key?
    outbound [TREE] [SCENARIO..] padded cascor/data/recurrence keys: log records, logs/*.log, console, API bodies, wire
    anon [TREE]                  auth ON: can a KEYLESS caller read a padded cascor key out of /api/train/start?
    sentry [TREE] [h11|httptools] [validate|internal-anon|internal|csrf]
                                 real uvicorn, DSN -> a local sink: which secrets reach a Sentry envelope when one
                                 request puts a non-ASCII byte into a secret compare (``probe_sentry`` names each case)?
    file-linebreak [TREE]        which variable does the padded-key WARNING name for a two-line key FILE?
    docs [TREE]                  the docs switch under a file-only real key and an NBSP-only env key

Usage (in the canopy conda env, with ``LIBTORCH= LD_LIBRARY_PATH=``)::

    python util/ad-hoc/2026-09-24_683_validation_leak_probes.py outbound
    python util/ad-hoc/2026-09-24_683_validation_leak_probes.py sentry /path/to/pre-fix/canopy httptools

Exit status is 0 (an instrument, not a gate).
"""

from __future__ import annotations

import base64
import gzip
import hashlib
import http.server
import json
import os
import shutil
import socket
import subprocess  # nosec B404 -- runs a local canopy tree in a fresh interpreter
import sys
import tempfile
import threading
import time
import urllib.request
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PY = sys.executable
MARK = "LEAKME"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class _RawUpstream:
    """Raw-socket stand-in: HTTP 200 JSON for a request, a 101 for a WebSocket upgrade; records every request's bytes."""

    def __init__(self, upgrade: bool = True) -> None:
        self.received: list[bytes] = []
        self._upgrade = upgrade
        self._sock = socket.socket()
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(64)
        self.port = self._sock.getsockname()[1]
        self.url = f"http://127.0.0.1:{self.port}"
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self) -> None:
        while True:
            try:
                conn, _ = self._sock.accept()
            except OSError:
                return
            conn.settimeout(2)
            data = b""
            try:
                while b"\r\n\r\n" not in data:
                    chunk = conn.recv(65536)
                    if not chunk:
                        break
                    data += chunk
            except OSError:
                pass
            self.received.append(data)
            try:
                if self._upgrade and b"upgrade: websocket" in data.lower():
                    key = b""
                    for line in data.split(b"\r\n"):
                        if line.lower().startswith(b"sec-websocket-key:"):
                            key = line.split(b":", 1)[1].strip()
                    accept = base64.b64encode(hashlib.sha1(key + b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11").digest())  # nosec B324 -- the RFC 6455 handshake
                    conn.sendall(b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: " + accept + b"\r\n\r\n")
                else:
                    body = b'{"status":"ok","dataset_id":"x"}'
                    conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: " + str(len(body)).encode() + b"\r\nConnection: close\r\n\r\n" + body)
            except OSError:
                pass
            finally:
                try:
                    conn.close()
                except OSError:
                    pass


def _workdir(tree: Path, name: str) -> Path:
    work = Path(tempfile.mkdtemp(prefix=f"683v-{name}-"))
    (work / "conf").mkdir()
    shutil.copy(tree / "conf" / "logging_config.yaml", work / "conf" / "logging_config.yaml")
    return work


_SCRUB = ("CANOPY_API_KEY", "JUNIPER_CANOPY_REQUIRE_AUTH", "JUNIPER_SKIP_AUTH_POSTURE_CHECK", "JUNIPER_CANOPY_SERVER__", "JUNIPER_DATA_API_KEY", "JUNIPER_CASCOR_API_KEY", "JUNIPER_RECURRENCE_API_KEY", "JUNIPER_CANOPY_JUNIPER_DATA_API_KEY", "JUNIPER_CANOPY_RECURRENCE", "JUNIPER_CANOPY_CASCOR", "CASCOR_SERVICE_URL", "RECURRENCE_SERVICE_URL", "JUNIPER_DATA_URL", "JUNIPER_CANOPY_DEMO_MODE")


def _child_env(tree: Path, extra: dict[str, str]) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith(_SCRUB) and "SENTRY" not in k.upper()}
    env.update({"PYTHONPATH": str(tree / "src"), "PYTHONDONTWRITEBYTECODE": "1", "JUNIPER_CANOPY_LOG_LEVEL": "DEBUG", "JUNIPER_CANOPY_SERVER__PORT": str(_free_port()), "JUNIPER_DATA_URL": f"http://127.0.0.1:{_free_port()}", "LIBTORCH": "", "LD_LIBRARY_PATH": ""})
    env.update(extra)
    return env


# ── lib ─────────────────────────────────────────────────────────────────────────────────────────────────────────────

LIB_VALUES = {
    "lead-space": " LEAKME-lead-space",
    "trail-space": "LEAKME-trail-space ",
    "trail-LF": "LEAKME-trail-LF\n",
    "lead-tab": "\tLEAKME-lead-tab",
    "trail-CRLF": "LEAKME-trail-CRLF\r\n",
    "inner-LF": "LEAKME-in\nner-LF",
    "inner-VT": "LEAKME-in\x0bner-VT",
    "trail-NBSP": "LEAKME-trail-NBSP\xa0",
    "latin1": "LEAKME-cl\xe9",
    "non-latin1": "LEAKME-euro€",
}


def probe_lib() -> None:
    import asyncio
    import importlib.metadata as md

    import httpx
    import requests
    from juniper_cascor_client import CascorTrainingStream, JuniperCascorClient
    from juniper_data_client import JuniperDataClient

    upstream = _RawUpstream()
    print("versions:", {d: md.version(d) for d in ["requests", "urllib3", "httpx", "h11", "websockets", "juniper-cascor-client", "juniper-data-client"]})

    def check(label, fn, value):
        before = len(upstream.received)
        body = value.strip()
        try:
            fn(value)
            outcome, text = "OK", ""
        except BaseException as exc:  # noqa: BLE001 -- every outcome is reported
            outcome, text = type(exc).__name__, str(exc)
            cause = exc.__cause__ or exc.__context__
            while cause is not None:
                text += " || " + type(cause).__name__ + ": " + str(cause)
                cause = cause.__cause__ or cause.__context__
        wire = b"".join(upstream.received[before:])
        on_wire = body.encode("utf-8", "replace") in wire or body.encode("latin-1", "replace") in wire
        leak = MARK in text
        print(f"  {label:<14} {outcome:<32} key-in-exc-text={str(leak):<5} key-on-wire={on_wire}" + (f"  | {text[:150]!r}" if leak else ""))

    def f_requests(v):
        requests.get(upstream.url + "/x", headers={"X-API-Key": v}, timeout=3)

    def f_cascor_rest(v):
        JuniperCascorClient(base_url=upstream.url, api_key=v, retries=0).get_training_status()

    def f_data(v):
        JuniperDataClient(base_url=upstream.url, api_key=v).create_dataset(generator="spiral", params={}, persist=True)

    def f_httpx(v):
        with httpx.Client(base_url=upstream.url, headers={"X-API-Key": v}, timeout=3) as client:
            client.request("GET", "/v1/training/status")

    def f_ws(v):
        async def go():
            stream = CascorTrainingStream(base_url=f"ws://127.0.0.1:{upstream.port}", api_key=v)
            await stream.connect()
            await stream.disconnect()

        asyncio.run(go())

    for name, fn in [("requests", f_requests), ("cascor REST", f_cascor_rest), ("data-client", f_data), ("httpx", f_httpx), ("cascor WS", f_ws)]:
        print(f"== {name}")
        for label, value in LIB_VALUES.items():
            check(label, fn, value)


# ── outbound ────────────────────────────────────────────────────────────────────────────────────────────────────────

_OUTBOUND_CHILD = r'''
import json, logging, os, time
records = []
_real = logging.Logger.callHandlers
def _every(self, record):
    records.append(record)
    return _real(self, record)
logging.Logger.callHandlers = _every
import main
from fastapi.testclient import TestClient
bodies = []
with TestClient(main.app) as c:
    for method, path, body in json.loads(os.environ["PROBE_STEPS"]):
        if method == "SLEEP":
            time.sleep(body)
            continue
        r = c.request(method, path, json=body)
        bodies.append((f"{method} {path}", r.status_code, r.text))
def render(r):
    s = r.getMessage()
    if r.exc_info:
        s += "\n" + logging.Formatter().formatException(r.exc_info)
    return s
hits = [{"logger": r.name, "level": r.levelname, "msg": render(r)[:260]} for r in records if "LEAKME" in render(r)]
body_hits = [(k, s, t[:260]) for k, s, t in bodies if "LEAKME" in t]
warnings = [r.getMessage()[:140] for r in records if r.levelno >= logging.WARNING and "holds a key canopy does not send" in r.getMessage()]
print("__REPORT__" + json.dumps({"main_file": main.__file__, "hits": hits, "body_hits": body_hits, "n_records": len(records), "statuses": [(k, s) for k, s, _ in bodies], "refused_key_warnings": warnings}))
'''


def probe_outbound(tree: Path, names: list[str]) -> None:
    upstream = _RawUpstream()
    status_steps = [["GET", "/api/status", None], ["GET", "/api/metrics", None], ["GET", "/api/network/topology", None]]
    cascor_steps = status_steps + [["POST", "/api/train/start", None], ["SLEEP", "", 6], ["GET", "/api/status", None], ["GET", "/api/stream_health", None]]
    recurrence_steps = [["POST", "/api/train/stop", None], ["SLEEP", "", 2], ["POST", "/api/model/select", {"nn_model": "recurrence"}], ["POST", "/api/train/start", {"dataset": {"generator": "spiral"}}], ["SLEEP", "", 3], ["GET", "/api/status", None]]
    scenarios = {
        "data-lead-space": ({"JUNIPER_CANOPY_DEMO_MODE": "1", "JUNIPER_DATA_API_KEY": " LEAKME-data-key-1"}, status_steps),
        "data-trail-LF": ({"JUNIPER_CANOPY_DEMO_MODE": "1", "JUNIPER_DATA_API_KEY": "LEAKME-data-key-1b\n"}, status_steps),
        "cascor-lead-space": ({"JUNIPER_CANOPY_DEMO_MODE": "0", "JUNIPER_CANOPY_CASCOR_SERVICE_URL": upstream.url, "JUNIPER_CASCOR_API_KEY": " LEAKME-cascor-key-2"}, cascor_steps),
        "cascor-trail-LF": ({"JUNIPER_CANOPY_DEMO_MODE": "0", "JUNIPER_CANOPY_CASCOR_SERVICE_URL": upstream.url, "JUNIPER_CASCOR_API_KEY": "LEAKME-cascor-key-3\n"}, cascor_steps),
        "recurrence-lead-space": ({"JUNIPER_CANOPY_DEMO_MODE": "1", "JUNIPER_CANOPY_RECURRENCE_SERVICE_URL": upstream.url, "JUNIPER_RECURRENCE_API_KEY": " LEAKME-rec-key-4"}, recurrence_steps),
        "recurrence-trail-space": ({"JUNIPER_CANOPY_DEMO_MODE": "1", "JUNIPER_CANOPY_RECURRENCE_SERVICE_URL": upstream.url, "JUNIPER_RECURRENCE_API_KEY": "LEAKME-rec-key-5 "}, recurrence_steps),
    }
    for name in names or list(scenarios):
        extra, steps = scenarios[name]
        work = _workdir(tree, name)
        before = len(upstream.received)
        # Every upstream is the recording stand-in, as in the validator's run: juniper-data for every scenario.
        env = _child_env(tree, {"JUNIPER_DATA_URL": upstream.url, **extra, "PROBE_STEPS": json.dumps(steps)})
        result = subprocess.run([PY, "-c", _OUTBOUND_CHILD], cwd=str(work), env=env, capture_output=True, text=True, timeout=300)  # nosec B603
        lines = [line for line in result.stdout.splitlines() if line.startswith("__REPORT__")]
        print(f"===== {name}  (exit {result.returncode})")
        if not lines:
            print(result.stderr[-3000:])
            continue
        report = json.loads(lines[0][len("__REPORT__") :])
        if Path(report["main_file"]).resolve() != (tree / "src" / "main.py").resolve():
            print(f"  NOTHING MEASURED: main was imported from {report['main_file']}, not {tree / 'src'}")
            continue
        print(f"  records={report['n_records']}  statuses={report['statuses']}")
        print(f"  refused-key WARNINGs: {report['refused_key_warnings']}")
        print(f"  log records carrying the key: {len(report['hits'])}")
        seen = set()
        for hit in report["hits"]:
            key = (hit["logger"], hit["level"], hit["msg"][:70])
            if key not in seen:
                seen.add(key)
                print(f"    [{hit['level']}] {hit['logger']}: {hit['msg'][:230]!r}")
        print(f"  API bodies carrying the key: {len(report['body_hits'])}")
        for step, status, text in report["body_hits"]:
            print(f"    {step} -> {status}: {text[:200]!r}")
        for log_file in sorted((work / "logs").glob("*.log")):
            count = sum(1 for line in log_file.read_text(errors="replace").splitlines() if MARK in line)
            if count:
                print(f"  logs/{log_file.name}: {count} lines carry the key")
        console = sum(1 for line in (result.stdout + result.stderr).splitlines() if MARK in line and not line.startswith("__REPORT__"))
        print(f"  console lines carrying the key: {console}")
        wire = b"".join(upstream.received[before:])
        print(f"  key bytes reached the fake upstream: {MARK.encode() in wire}  ({len(upstream.received) - before} requests, {wire.lower().count(b'x-api-key:')} with an X-API-Key header)")


# ── anon ────────────────────────────────────────────────────────────────────────────────────────────────────────────

_ANON_CHILD = r'''
import json
import main
from fastapi.testclient import TestClient
out = {"auth_enabled": main.api_key_auth.enabled}
with TestClient(main.app) as c:
    out["status_keyless"] = c.get("/api/status").status_code
    tok = c.get("/api/csrf")
    out["csrf_status"] = tok.status_code
    token = tok.json().get("csrf_token") or tok.json().get("token")
    r = c.post("/api/train/start", headers={"Origin": "http://localhost:8050", "X-CSRF-Token": token or ""})
    out["start_status"] = r.status_code
    out["start_body"] = r.text[:400]
    out["key_in_start_body"] = "LEAKME" in r.text
print("__REPORT__" + json.dumps(out))
'''


def probe_anon(tree: Path) -> None:
    upstream = _RawUpstream(upgrade=False)
    env = _child_env(tree, {"JUNIPER_CANOPY_DEMO_MODE": "0", "JUNIPER_CANOPY_CASCOR_SERVICE_URL": upstream.url, "JUNIPER_DATA_URL": upstream.url, "CANOPY_API_KEY": "real-canopy-key-no-padding", "JUNIPER_CASCOR_API_KEY": "LEAKME-cascor-key-6\n"})
    result = subprocess.run([PY, "-c", _ANON_CHILD], cwd=str(_workdir(tree, "anon")), env=env, capture_output=True, text=True, timeout=300)  # nosec B603
    lines = [line for line in result.stdout.splitlines() if line.startswith("__REPORT__")]
    print(json.dumps(json.loads(lines[0][10:]), indent=1) if lines else result.stderr[-3000:])


# ── sentry ──────────────────────────────────────────────────────────────────────────────────────────────────────────


def _raw_request(port: int, request: bytes) -> bytes:
    with socket.create_connection(("127.0.0.1", port)) as sock:
        sock.sendall(request)
        response = b""
        sock.settimeout(10)
        try:
            while chunk := sock.recv(65536):
                response += chunk
        except OSError as e:
            print(e)
    return response


# Each case is ONE request with a non-ASCII byte (0xA0, which both uvicorn parsers pass) where a secret compare reads it.
SENTRY_CASES = ("validate", "internal-anon", "internal", "csrf")


def probe_sentry(tree: Path, loop: str, case: str = "validate") -> None:
    """``validate``: anonymous ``X-API-Key: \\xa0`` (the validator's scenario, unchanged). ``internal-anon``: ANONYMOUS
    ``GET /api/csrf`` -- key-exempt, still rate-limited -- with ``X-Canopy-Internal: \\xa0``, the rate limiter on (its
    exemption compare). ``internal``: the same header beside the REAL key. ``csrf``: keyless, a CSRF token minted, then
    Start from an allowlisted Origin with ``X-CSRF-Token: \\xa0`` (the CSRF store's compare)."""
    real_key = "real-canopy-key-REALKEYMARK-7f3a"
    captured: list[bytes] = []

    class Sink(http.server.BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            body = self.rfile.read(int(self.headers.get("Content-Length", "0") or 0))
            encoding = (self.headers.get("Content-Encoding") or "").lower()
            try:
                if encoding == "gzip":
                    body = gzip.decompress(body)
                elif encoding == "deflate":
                    body = zlib.decompress(body)
                elif encoding == "br":
                    import brotli  # type: ignore

                    body = brotli.decompress(body)
            except Exception as exc:  # noqa: BLE001
                body = f"<undecodable {encoding}: {exc}>".encode()
            captured.append(body)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, *args):
            pass

    sink_port = _free_port()
    sink = http.server.ThreadingHTTPServer(("127.0.0.1", sink_port), Sink)
    threading.Thread(target=sink.serve_forever, daemon=True).start()
    work = _workdir(tree, "sentry")
    port = _free_port()
    extra = {"CANOPY_API_KEY": real_key, "JUNIPER_DATA_API_KEY": " LEAKME-data-key-S1", "JUNIPER_CANOPY_SENTRY_DSN": f"http://publickey@127.0.0.1:{sink_port}/42", "JUNIPER_CANOPY_DEMO_MODE": "1", "JUNIPER_CANOPY_SERVER__PORT": str(port), "JUNIPER_SKIP_DEP_FLOOR_CHECK": "1"}
    if case in ("internal", "internal-anon"):
        extra["JUNIPER_CANOPY_RATE_LIMIT_ENABLED"] = "true"
    env = _child_env(tree, extra)
    csrf_token = ""
    with open(work / "uvicorn.log", "wb") as log:
        proc = subprocess.Popen([PY, "-m", "uvicorn", "main:app", "--app-dir", str(tree / "src"), "--host", "127.0.0.1", "--port", str(port), "--http", loop], cwd=str(work), env=env, stdout=log, stderr=subprocess.STDOUT)  # nosec B603
        up = False
        for _ in range(120):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/v1/health/live", timeout=1)  # nosec B310 -- a local fixed URL
                up = True
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.5)
        print("server up:", up, "parser:", loop, "case:", case)
        if case == "validate":
            response = _raw_request(port, b"GET /api/status HTTP/1.1\r\nHost: 127.0.0.1\r\nX-API-Key: \xa0\r\nConnection: close\r\n\r\n")
            print("anonymous non-ASCII-key request ->", response.split(b"\r\n", 1)[0])
        elif case == "internal-anon":
            response = _raw_request(port, b"GET /api/csrf HTTP/1.1\r\nHost: 127.0.0.1\r\nX-Canopy-Internal: \xa0\r\nConnection: close\r\n\r\n")
            print("anonymous /api/csrf with a non-ASCII X-Canopy-Internal ->", response.split(b"\r\n", 1)[0])
        elif case == "internal":
            response = _raw_request(port, b"GET /api/status HTTP/1.1\r\nHost: 127.0.0.1\r\nX-API-Key: " + real_key.encode() + b"\r\nX-Canopy-Internal: \xa0\r\nConnection: close\r\n\r\n")
            print("keyed request with a non-ASCII X-Canopy-Internal ->", response.split(b"\r\n", 1)[0])
        else:
            minted = _raw_request(port, b"GET /api/csrf HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n")
            body = minted.split(b"\r\n\r\n", 1)[-1]
            try:
                payload = json.loads(body)
                csrf_token = payload.get("csrf_token") or payload.get("token") or ""
            except ValueError:
                csrf_token = ""
            print("keyless CSRF mint ->", minted.split(b"\r\n", 1)[0], "| token minted:", bool(csrf_token))
            response = _raw_request(port, b"POST /api/train/start HTTP/1.1\r\nHost: 127.0.0.1\r\nOrigin: http://localhost:8050\r\nX-CSRF-Token: \xa0\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
            print("keyless Start with a non-ASCII X-CSRF-Token ->", response.split(b"\r\n", 1)[0])
        time.sleep(12)  # the logs batcher's flush interval
        proc.terminate()
        proc.wait(20)
    time.sleep(1)
    sink.shutdown()
    print(f"envelopes captured: {len(captured)}")
    marks = [("real CANOPY_API_KEY", b"REALKEYMARK"), ("padded JUNIPER_DATA_API_KEY", b"LEAKME-data-key-S1")]
    if csrf_token:
        marks.append(("live CSRF token", csrf_token.encode()))
    for label, mark in marks:
        print(f"  envelopes carrying the {label}: {sum(1 for body in captured if mark in body)}")
        for body in captured:
            at = body.find(mark)
            if at >= 0:
                print("    ...", body[max(0, at - 220) : at + 60].decode("utf-8", "replace").replace("\n", " "), "...")
                break
    print("uvicorn console lines carrying the real key:", sum(1 for line in (work / "uvicorn.log").read_bytes().splitlines() if b"REALKEYMARK" in line))


# ── file-linebreak ──────────────────────────────────────────────────────────────────────────────────────────────────

_FILE_LINEBREAK_CHILD = r'''
import security
from frontend import internal_api


class L:
    def __init__(self):
        self.m = []

    def warning(self, m):
        self.m.append(m)


auth = security.get_api_key_auth()
log = L()
n = security.report_api_key_configuration(log)
print("auth enabled:", auth.enabled, "| recorded padded source:", security._padded_key_source, "| warnings:", n)
print("warning begins:", log.m[0][:70] if log.m else None)
print("self-call sends a key:", "X-API-Key" in internal_api.internal_api_headers())
'''


def probe_file_linebreak(tree: Path) -> None:
    work = _workdir(tree, "file-linebreak")
    key_file = work / "two_line_key"
    key_file.write_text("first-line-key\nsecond-line\n", encoding="utf-8")
    result = subprocess.run([PY, "-c", _FILE_LINEBREAK_CHILD], cwd=str(work), env=_child_env(tree, {"CANOPY_API_KEY_FILE": str(key_file)}), capture_output=True, text=True, timeout=120)  # nosec B603
    print(result.stdout.strip() or result.stderr[-2000:])


# ── docs ────────────────────────────────────────────────────────────────────────────────────────────────────────────

_DOCS_CHILD = r'''
import os
import main
from fastapi.testclient import TestClient

key = os.environ.get("PROBE_KEY", "")
with TestClient(main.app) as c:
    anon = c.get("/openapi.json").status_code
    keyed = c.get("/openapi.json", headers={"X-API-Key": key}).status_code if key else None
    status_anon = c.get("/api/status").status_code
print(f"docs_enabled={main._docs_enabled} auth_enabled={main.api_key_auth.enabled} /openapi.json keyless={anon} keyed={keyed} /api/status keyless={status_anon}")
'''


def probe_docs(tree: Path) -> None:
    work = _workdir(tree, "docs")
    key_file = work / "real_key_file"
    key_file.write_text("real-file-key-123\n", encoding="utf-8")
    for label, extra in (("file-only real key", {"CANOPY_API_KEY_FILE": str(key_file), "PROBE_KEY": "real-file-key-123"}), ("NBSP-only env key", {"CANOPY_API_KEY": "\xa0"})):
        result = subprocess.run([PY, "-c", _DOCS_CHILD], cwd=str(work), env=_child_env(tree, {"JUNIPER_CANOPY_DEMO_MODE": "1", **extra}), capture_output=True, text=True, timeout=300)  # nosec B603
        print(f"## {label}: " + (result.stdout.strip().splitlines() or [result.stderr[-500:]])[-1])


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in ("lib", "outbound", "anon", "sentry", "file-linebreak", "docs"):
        print(__doc__)
        return 0
    command, rest = sys.argv[1], sys.argv[2:]
    tree = Path(rest[0]).resolve() if rest and not rest[0].startswith(("data-", "cascor-", "recurrence-", "h11", "httptools", *SENTRY_CASES)) else REPO
    args = [arg for arg in rest if Path(arg).resolve() != tree]
    if command == "lib":
        probe_lib()
    elif command == "outbound":
        probe_outbound(tree, args)
    elif command == "anon":
        probe_anon(tree)
    elif command == "sentry":
        loop = next((arg for arg in args if arg in ("h11", "httptools")), "httptools")
        probe_sentry(tree, loop, next((arg for arg in args if arg in SENTRY_CASES), "validate"))
    elif command == "file-linebreak":
        probe_file_linebreak(tree)
    else:
        probe_docs(tree)
    return 0


if __name__ == "__main__":
    sys.exit(main())
