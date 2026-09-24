"""
Probes behind the #678 follow-up's claims about a PADDED CANOPY_API_KEY (not blank; leading or
trailing whitespace), and about the dashboard self-call that leaked one into the logs.

Project: juniper-canopy
Sub-Project: ad-hoc tooling
Author: Paul Calnon
Created: 2026-09-24
Status: ad-hoc -- investigation
Retire when: the #678 follow-up is merged and nobody needs to re-derive its wording.
Related: juniper-canopy #678 follow-up (items 4 and 6); util/ad-hoc/2026-09-23_blank_api_key_route_sweep.py
    (its ``header-probe`` covers all-whitespace values; this one covers a real key WITH padding).

Subcommands
-----------
``header-probe``
    Starts real uvicorn twice -- ``--http h11`` and ``--http httptools`` (canopy's default parser
    when ``uvicorn[standard]`` is installed) -- on an echo app, sends raw socket bytes, and prints
    the ``X-API-Key`` value Starlette hands the app. Then prints what ``requests`` does with the
    same values as a header (``prepare()``): send it, or raise ``InvalidHeader`` -- and whether
    that exception's text carries the value.

``leak``
    Imports canopy in THIS process with a padded ``CANOPY_API_KEY`` (auth enabled), captures every
    log record at the root, and calls a dashboard handler that self-calls the API (the mount-time
    selection hydration, ``DashboardManager._hydrate_selection_handler``). Prints how many records
    carry the key's text. Run it on a tree (``--tree``) to compare before/after.

Usage::

    python util/ad-hoc/2026-09-24_padded_api_key_probes.py header-probe
    python util/ad-hoc/2026-09-24_padded_api_key_probes.py leak [--tree <checkout>]

Exit status is 0 unless a server fails to start (2) -- an instrument, not a gate.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import subprocess  # nosec B404 -- re-runs this script under another tree's src/
import sys
import threading
import time
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]

# (label, raw bytes on the wire). A "real" key with padding, in every position that matters.
WIRE_VALUES: list[tuple[str, bytes]] = [
    ("clean", b"real-key-XYZ"),
    ("leading space", b" real-key-XYZ"),
    ("leading tab", b"\treal-key-XYZ"),
    ("trailing space", b"real-key-XYZ "),
    ("trailing tab", b"real-key-XYZ\t"),
    ("both sides", b"  real-key-XYZ\t "),
    ("inner space", b"real key XYZ"),
    ("trailing VT (0B)", b"real-key-XYZ\x0b"),
    ("trailing FF (0C)", b"real-key-XYZ\x0c"),
    ("trailing FS (1C)", b"real-key-XYZ\x1c"),
    ("leading U+00A0 (A0)", b"\xa0real-key-XYZ"),
    ("trailing U+00A0 (A0)", b"real-key-XYZ\xa0"),
]

PROBE_KEY_TEXT = "leaked-key-XYZ123"


async def _echo(scope: Any, receive: Any, send: Any) -> None:
    from starlette.requests import Request

    value = Request(scope).headers.get("x-api-key")
    body = json.dumps({"value": value}).encode()
    await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
    await send({"type": "http.response.body", "body": body})


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _raw_get(port: int, raw_value: bytes) -> tuple[str, str]:
    request = b"GET / HTTP/1.1\r\nHost: probe\r\nX-API-Key: " + raw_value + b"\r\nConnection: close\r\n\r\n"
    with socket.create_connection(("127.0.0.1", port), timeout=5) as s:
        s.sendall(request)
        chunks = []
        while True:
            chunk = s.recv(65536)
            if not chunk:
                break
            chunks.append(chunk)
    response = b"".join(chunks).decode("latin-1")
    status = response.split("\r\n", 1)[0].replace("HTTP/1.1 ", "")
    body = response.split("\r\n\r\n", 1)[1] if "\r\n\r\n" in response else ""
    return status, body


def cmd_header_probe() -> int:
    import requests
    import uvicorn

    delivered: dict[str, dict[str, str]] = {label: {} for label, _ in WIRE_VALUES}
    for impl in ("h11", "httptools"):
        port = _free_port()
        server = uvicorn.Server(uvicorn.Config(_echo, host="127.0.0.1", port=port, http=impl, lifespan="off", log_level="critical"))
        thread = threading.Thread(target=lambda srv=server: asyncio.run(srv.serve()), daemon=True)
        thread.start()
        deadline = time.monotonic() + 10
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.05)
        if not server.started:
            print(f"{impl}: server did not start -- NOTHING MEASURED")
            return 2
        for label, raw in WIRE_VALUES:
            status, body = _raw_get(port, raw)
            if status.startswith("200"):
                value = json.loads(body)["value"]
                delivered[label][impl] = repr(value) + ("  (== sent)" if value == raw.decode("latin-1") else "")
            else:
                delivered[label][impl] = status
        server.should_exit = True
        thread.join(timeout=10)

    print(f"uvicorn {uvicorn.__version__}, requests {requests.__version__}")
    print(f"{'value':22} {'wire bytes':24} {'h11 delivers':28} {'httptools delivers':28} requests.prepare()")
    for label, raw in WIRE_VALUES:
        text = raw.decode("latin-1")
        try:
            requests.Request("GET", "http://127.0.0.1:1/", headers={"X-API-Key": text}).prepare()
            verdict = "sends it"
        except requests.exceptions.InvalidHeader as exc:
            verdict = f"InvalidHeader; value in text: {text in str(exc) or repr(text) in str(exc)}"
        print(f"{label:22} {raw!r:24} {delivered[label]['h11']:28} {delivered[label]['httptools']:28} {verdict}")
    return 0


def _leak_inner() -> int:
    """Runs inside a child whose sys.path puts the tree under test first."""
    import logging

    records: list[logging.LogRecord] = []

    class _All(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    root = logging.getLogger()
    root.addHandler(_All(level=logging.DEBUG))
    root.setLevel(logging.DEBUG)

    import main

    manager = next(obj for obj in vars(main).values() if type(obj).__name__ == "DashboardManager")
    outcome = manager._hydrate_selection_handler()

    def rendered(r: logging.LogRecord) -> str:
        text = r.getMessage()
        if r.exc_info:
            text += "\n" + logging.Formatter().formatException(r.exc_info)
        return text + repr(getattr(r, "context_data", ""))

    hits = [(r.name, r.levelname, rendered(r)[:220]) for r in records if PROBE_KEY_TEXT in rendered(r)]
    print(json.dumps({"main": main.__file__, "auth_enabled": main.api_key_auth.enabled, "records": len(records), "records_carrying_key": len(hits), "hits": hits, "handler_returned": repr(outcome)[:160]}, indent=2))
    return 0


def cmd_leak(tree: Path) -> int:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("CANOPY_API_KEY", "SENTRY")) and "SENTRY" not in k}
    # A free port, so the self-call cannot reach a canopy that happens to be serving on 8050 here.
    env.update({"CANOPY_API_KEY": " " + PROBE_KEY_TEXT, "JUNIPER_CANOPY_DEMO_MODE": "1", "JUNIPER_CANOPY_SERVER__PORT": str(_free_port()), "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": f"{tree / 'src'}{os.pathsep}{env.get('PYTHONPATH', '')}"})
    result = subprocess.run([sys.executable, __file__, "_leak-inner"], cwd=str(tree / "src"), env=env, capture_output=True, text=True, timeout=300)  # nosec B603
    start = result.stdout.find("{\n")
    print(result.stdout[start:] if start >= 0 else result.stdout[-3000:])
    if result.returncode != 0:
        print(result.stderr[-3000:])
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("header-probe", help="what uvicorn delivers, and what requests does, for padded key values")
    leak = sub.add_parser("leak", help="count log records carrying a padded key after one dashboard self-call")
    leak.add_argument("--tree", type=Path, default=REPO, help="checkout to import canopy from (default: this one)")
    sub.add_parser("_leak-inner", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.cmd == "header-probe":
        return cmd_header_probe()
    if args.cmd == "leak":
        return cmd_leak(args.tree.resolve())
    return _leak_inner()


if __name__ == "__main__":
    raise SystemExit(main())
