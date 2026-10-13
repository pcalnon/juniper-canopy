#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     2026-09-23_blank_api_key_route_sweep.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-09-23
# Last Modified: 2026-09-23
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   APD-ECO-008 follow-up -- measure what a whitespace-only
#                CANOPY_API_KEY gated before juniper-canopy#660 and what
#                it serves after, by sweeping app.routes on two trees.
#####################################################################
"""Route sweep for a whitespace-only ``CANOPY_API_KEY``, before and after APD-ECO-008.

Project: juniper-canopy
Sub-Project: ad-hoc tooling
Author: Paul Calnon
Created: 2026-09-23
Status: ad-hoc -- investigation
Retire when: the APD-ECO-008 follow-up (the CHANGELOG disclosure of what #660 opened) is merged
Related: juniper-canopy#660 (squash 3a6dea95); APD-ECO-008 (juniper-ml defect register)

**What it measures.** #660 made a whitespace-only ``CANOPY_API_KEY`` env var count as
no key. Before it, that value ENABLED ``APIKeyAuth`` on a key no caller could present,
so ``SecurityMiddleware`` refused every request to every route outside its exempt sets.
After it, auth is off and those routes serve anyone. This script counts that surface
from the route table rather than from a reading of ``main.py``:

* ``classify`` -- every (method, path) pair in ``app.routes``, classified with the tree's
  OWN ``SecurityMiddleware._is_exempt`` / ``_is_key_exempt`` (so a change to the exempt
  sets between trees is measured, not assumed). A pair is **key-gated** when neither
  applies. **State-changing** means POST, PUT, PATCH or DELETE.
* ``gate`` -- sends one KEYLESS request per pair through the tree's real middleware
  stack, with the router swapped for a stub that records arrival and answers 299. No
  handler runs, so the state-changing routes are measured without being executed. A
  401 means the middleware refused; 299 means the request got past every middleware.
* ``handlers`` -- the key-gated GETs with no path parameter, sent keyless to the REAL
  handlers with the lifespan running (demo mode). This is the "401 before, 200 after"
  column.
* ``presentable`` -- the exception to "no header can carry it": keys made only of
  characters ``str.strip()`` removes but a header does carry (``PRESENTABLE_KEYS``).
* ``header-probe`` -- what real uvicorn (h11 and httptools) delivers to Starlette for a
  whitespace-only ``X-API-Key``, sent as raw bytes so no client library normalises it.

Each tree is imported in its own subprocess with its ``src/`` first on ``sys.path``, and
every run asserts the modules it measured were imported from that tree: juniper-canopy
is often editable-installed against another checkout, and an import that resolves
there would measure the wrong code while looking fine.

Usage (from the repo root, in the canopy conda env)::

    python util/ad-hoc/2026-09-23_blank_api_key_route_sweep.py materialize --rev 48074653 --dest <scratch>/pre
    python util/ad-hoc/2026-09-23_blank_api_key_route_sweep.py materialize --rev 3a6dea95 --dest <scratch>/post
    python util/ad-hoc/2026-09-23_blank_api_key_route_sweep.py compare --pre <scratch>/pre --post <scratch>/post
    python util/ad-hoc/2026-09-23_blank_api_key_route_sweep.py presentable --pre <scratch>/pre --post <scratch>/post
    python util/ad-hoc/2026-09-23_blank_api_key_route_sweep.py header-probe

``materialize`` extracts a commit with ``git archive``; it never touches the working tree.
Exit status: 0 = measured; 2 = nothing measured (a binding check or a subprocess failed).
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import os
import re
import socket
import subprocess  # nosec B404 -- runs git archive / this script on local trees
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
WHITESPACE_KEY = "   "  # three ASCII spaces: the value #660 changed the meaning of
# Keys made only of characters ``str.strip()`` removes but a header CAN carry (measured by
# ``header-probe``): U+00A0 and U+0085 pass both uvicorn parsers as latin-1 bytes, U+001C
# passes h11 only. Written as \x escapes on purpose: a literal U+00A0 is invisible.
PRESENTABLE_KEYS = {"U+00A0 x2": "\xa0\xa0", "U+0085 x2": "\x85\x85", "U+001C x2": "\x1c\x1c"}
STATE_CHANGING = frozenset({"POST", "PUT", "PATCH", "DELETE"})
REACHED_ROUTER = 299  # the stub router's answer: the request passed every middleware
BOUND_MODULES = ("main", "security", "middleware", "secrets_util", "canopy_constants", "logger.logger", "backend", "frontend.dashboard_manager")


# ── subprocess side: runs INSIDE one tree ────────────────────────────────────


def _bind(tree: Path) -> Any:
    src = (tree / "src").resolve()
    sys.path.insert(0, str(src))
    os.chdir(src)
    import main  # noqa: E402 -- imported from the tree just placed on sys.path

    for name in BOUND_MODULES:
        mod = importlib.import_module(name)
        where = Path(str(mod.__file__)).resolve()
        if src not in where.parents:
            raise SystemExit(f"BINDING FAILED: {name} imported from {where}, not from {src}")
    return main


def _pairs(main: Any) -> list[dict[str, Any]]:
    from starlette.routing import Mount, Route, WebSocketRoute

    import middleware

    rows = []
    for route in main.app.routes:
        if isinstance(route, Mount):
            rows.append({"kind": "mount", "path": route.path, "method": None})
            continue
        if isinstance(route, WebSocketRoute) or not isinstance(route, Route):
            rows.append({"kind": "websocket", "path": getattr(route, "path", repr(route)), "method": None})
            continue
        methods = sorted(route.methods or [])
        concrete = re.sub(r"\{[^}]+\}", "probe", route.path)
        exempt = middleware.SecurityMiddleware._is_exempt(None, concrete)
        key_exempt = middleware.SecurityMiddleware._is_key_exempt(None, concrete)
        for method in methods:
            rows.append(
                {
                    "kind": "http",
                    "method": method,
                    "path": route.path,
                    "concrete": concrete,
                    # Starlette adds HEAD beside GET on a plain Route; FastAPI's APIRoute does not.
                    "implicit_head": method == "HEAD" and "GET" in methods,
                    "has_path_params": concrete != route.path,
                    "gate": "exempt" if exempt else ("key-exempt" if key_exempt else "key-gated"),
                    "state_changing": method in STATE_CHANGING,
                }
            )
    return rows


def _inner(tree: Path, mode: str) -> dict[str, Any]:
    main = _bind(tree)
    import security

    out: dict[str, Any] = {
        "tree": str(tree),
        "auth_enabled": security.get_api_key_auth().enabled,
        "middleware_auth_enabled": main.api_key_auth.enabled,
        "docs_enabled": bool(getattr(main, "_docs_enabled", None)),
    }
    rows = _pairs(main)
    out["rows"] = rows
    if mode == "classify":
        return out

    from fastapi.testclient import TestClient

    http = [r for r in rows if r["kind"] == "http" and not r["implicit_head"]]
    if mode == "gate":
        real_router = main.app.router

        class _StubRouter:
            """Answers every HTTP request that got past the middleware stack; runs no handler."""

            async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
                if scope["type"] != "http":
                    await real_router(scope, receive, send)
                    return
                await send({"type": "http.response.start", "status": REACHED_ROUTER, "headers": [(b"content-length", b"0")]})
                await send({"type": "http.response.body", "body": b""})

        main.app.router = _StubRouter()
        main.app.middleware_stack = None  # rebuilt on the first request, around the stub
        client = TestClient(main.app, raise_server_exceptions=False)
        for row in http:
            row["keyless_status"] = client.request(row["method"], row["concrete"]).status_code
        return out

    if mode == "handlers":
        gets = [r for r in http if r["method"] == "GET" and r["gate"] == "key-gated" and not r["has_path_params"]]
        with TestClient(main.app, raise_server_exceptions=False) as client:
            for row in gets:
                row["keyless_status"] = client.get(row["path"]).status_code
        return out

    if mode == "presentable":
        # One key-gated GET, three callers: keyless, the configured key sent as the raw
        # latin-1 bytes a uvicorn parser delivers (see header-probe), and a wrong ASCII key.
        key = os.environ["CANOPY_API_KEY"]
        try:
            validated = repr(security.get_api_key_auth().validate(key))
        except Exception as exc:  # noqa: BLE001 -- the exception IS the measurement
            validated = f"{type(exc).__name__}: {exc}"
        with TestClient(main.app, raise_server_exceptions=False) as client:
            out["presentable"] = {
                "path": "/api/status",
                "validate(configured key)": validated,
                "keyless": client.get("/api/status").status_code,
                "configured_key_as_latin1_bytes": client.get("/api/status", headers={"X-API-Key": key.encode("latin-1")}).status_code,
                "wrong_ascii_key": client.get("/api/status", headers={"X-API-Key": "wrong"}).status_code,
            }
        return out

    raise SystemExit(f"unknown mode {mode!r}")


# ── parent side ──────────────────────────────────────────────────────────────


def _env(key: str) -> dict[str, str]:
    env = dict(os.environ)
    for var in ("CANOPY_API_KEY_FILE", "JUNIPER_CANOPY_REQUIRE_AUTH", "JUNIPER_SKIP_AUTH_POSTURE_CHECK", "CASCOR_BACKEND_AVAILABLE", "JUNIPER_CANOPY_CASCOR_SERVICE_URL"):
        env.pop(var, None)
    env.update(
        {
            "CANOPY_API_KEY": key,
            "JUNIPER_CANOPY_DEMO_MODE": "1",
            # The floor check reads the INSTALLED distribution's metadata, not the tree's,
            # so it says nothing about the tree under test; it is orthogonal to this sweep.
            "JUNIPER_SKIP_DEP_FLOOR_CHECK": "1",
            "LIBTORCH": "",
            "LD_LIBRARY_PATH": "",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    return env


def run_tree(tree: Path, mode: str, key: str = WHITESPACE_KEY) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="blank-key-sweep-") as tmp:
        result = Path(tmp) / "result.json"
        cmd = [sys.executable, "-B", str(Path(__file__).resolve()), "_inner", "--tree", str(tree.resolve()), "--mode", mode, "--out", str(result)]
        proc = subprocess.run(cmd, env=_env(key), capture_output=True, text=True, timeout=900)  # nosec B603 -- fixed argv, local tree
        if proc.returncode != 0 or not result.exists():
            sys.stderr.write(proc.stdout[-4000:] + "\n" + proc.stderr[-4000:] + "\n")
            raise SystemExit(f"NOTHING MEASURED -- {mode} on {tree} exited {proc.returncode}")
        return json.loads(result.read_text(encoding="utf-8"))


def _summary(rows: list[dict[str, Any]]) -> dict[str, int]:
    http = [r for r in rows if r["kind"] == "http" and not r["implicit_head"]]
    gated = [r for r in http if r["gate"] == "key-gated"]
    return {
        "http_pairs": len(http),
        "exempt": sum(r["gate"] == "exempt" for r in http),
        "key_exempt": sum(r["gate"] == "key-exempt" for r in http),
        "key_gated": len(gated),
        "key_gated_state_changing": sum(r["state_changing"] for r in gated),
        "key_gated_get": sum(r["method"] == "GET" for r in gated),
        "key_gated_get_parameterless": sum(r["method"] == "GET" and not r["has_path_params"] for r in gated),
        "implicit_head_skipped": sum(r["kind"] == "http" and r["implicit_head"] for r in rows),
        "websocket_routes": sum(r["kind"] == "websocket" for r in rows),
        "mounts": sum(r["kind"] == "mount" for r in rows),
    }


def cmd_compare(pre: Path, post: Path) -> int:
    report: dict[str, Any] = {}
    for label, tree in (("pre", pre), ("post", post)):
        gate = run_tree(tree, "gate")
        handlers = run_tree(tree, "handlers")
        by_handler = {(r["method"], r["path"]): r.get("keyless_status") for r in handlers["rows"] if "keyless_status" in r}
        rows = gate["rows"]
        for row in rows:
            if (row.get("method"), row.get("path")) in by_handler:
                row["handler_status"] = by_handler[(row["method"], row["path"])]
        report[label] = {"auth_enabled": gate["auth_enabled"], "middleware_auth_enabled": gate["middleware_auth_enabled"], "docs_enabled": gate["docs_enabled"], "summary": _summary(rows), "rows": rows}

    pre_rows = {(r["method"], r["path"]): r for r in report["pre"]["rows"] if r["kind"] == "http" and not r["implicit_head"]}
    post_rows = {(r["method"], r["path"]): r for r in report["post"]["rows"] if r["kind"] == "http" and not r["implicit_head"]}
    print(f"CANOPY_API_KEY={WHITESPACE_KEY!r} (env), CANOPY_API_KEY_FILE unset, demo mode")
    for label in ("pre", "post"):
        r = report[label]
        print(f"{label:4}: auth enabled={r['auth_enabled']} (middleware's instance: {r['middleware_auth_enabled']}), docs routes={r['docs_enabled']}  {json.dumps(r['summary'])}")
    only = sorted(set(pre_rows) ^ set(post_rows))
    print(f"pairs present in only one tree: {only or 'none'}")

    print("\nkey-gated pairs (pre gate / post gate / pre handler / post handler):")
    opened = refused_pre = 0
    for key in sorted(pre_rows, key=lambda k: (k[1], k[0])):
        a = pre_rows[key]
        b = post_rows.get(key)
        if a["gate"] != "key-gated":
            continue
        refused_pre += a["keyless_status"] == 401
        opened += bool(b) and a["keyless_status"] == 401 and b["keyless_status"] == REACHED_ROUTER
        flag = "state-changing" if a["state_changing"] else ""
        print(f"  {key[0]:6} {key[1]:58} {a['keyless_status']} -> {b['keyless_status'] if b else '-'}   {a.get('handler_status', '')} -> {b.get('handler_status', '') if b else ''}  {flag}")
    gets = [k for k, v in pre_rows.items() if "handler_status" in v]
    get_flips = sum(pre_rows[k]["handler_status"] == 401 and post_rows.get(k, {}).get("handler_status") == 200 for k in gets)
    print(f"\nkeyless and refused by the middleware before: {refused_pre}; of those, past every middleware after: {opened}")
    print(f"parameterless key-gated GETs sent to the real handlers: {len(gets)}; 401 before and 200 after: {get_flips}")
    non_200 = {f"{k[0]} {k[1]}": post_rows[k].get("handler_status") for k in gets if post_rows.get(k, {}).get("handler_status") != 200}
    print(f"post-fix handler statuses other than 200: {non_200 or 'none'}")
    others = {f"{k[0]} {k[1]}": (v["gate"], v["keyless_status"]) for k, v in pre_rows.items() if v["gate"] != "key-gated" and v["keyless_status"] == 401}
    print(f"non-key-gated pairs the middleware refused before (should be none): {others or 'none'}")
    return 0


def cmd_presentable(pre: Path, post: Path) -> int:
    for name, key in PRESENTABLE_KEYS.items():
        for label, tree in (("pre", pre), ("post", post)):
            out = run_tree(tree, "presentable", key=key)
            print(f"{name:10} {label:4}: auth enabled={out['auth_enabled']}; {json.dumps(out['presentable'])}")
    return 0


# ── header probe: what real uvicorn hands Starlette ──────────────────────────


async def _echo(scope: Any, receive: Any, send: Any) -> None:
    from starlette.requests import Request

    value = Request(scope).headers.get("x-api-key")
    body = json.dumps({"value": value, "codepoints": [f"U+{ord(c):04X}" for c in value] if value is not None else None, "str_strip_empties_it": value is not None and value != "" and not value.strip()}).encode()
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
    status = response.split("\r\n", 1)[0]
    body = response.split("\r\n\r\n", 1)[1] if "\r\n\r\n" in response else ""
    return status, body


def cmd_header_probe() -> int:
    import uvicorn

    values = {
        "3 spaces": b"   ",
        "2 tabs": b"\t\t",
        "space tab space": b" \t ",
        "padded ascii key": b"  abc\t",
        "U+00A0 x2 (latin-1 byte A0)": b"\xa0\xa0",
        "U+0085 x2 (latin-1 byte 85)": b"\x85\x85",
        "U+00A0 as UTF-8 (C2 A0)": b"\xc2\xa0",
        "VT (0B)": b"\x0b",
        "FF (0C)": b"\x0c",
        "FS (1C)": b"\x1c",
        "GS (1D)": b"\x1d",
        "RS (1E)": b"\x1e",
        "US (1F)": b"\x1f",
    }
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
        print(f"uvicorn {uvicorn.__version__} --http {impl}:")
        for label, raw in values.items():
            status, body = _raw_get(port, raw)
            print(f"  {label:30} {raw!r:16} -> {status:24} {body}")
        server.should_exit = True
        thread.join(timeout=10)
    return 0


def cmd_materialize(rev: str, dest: Path) -> int:
    dest.mkdir(parents=True, exist_ok=True)
    if any(dest.iterdir()):
        raise SystemExit(f"{dest} is not empty")
    with tempfile.TemporaryDirectory(prefix="blank-key-archive-") as tmp:
        archive = Path(tmp) / "tree.tar"
        subprocess.run(["git", "-C", str(REPO), "archive", "--format=tar", "-o", str(archive), rev], check=True)  # nosec B603 B607 -- fixed argv
        # The tar CLI rather than tarfile: notes/ carries relative symlinks into the sibling
        # juniper-ml checkout, which tarfile's "data" filter refuses as links outside the
        # destination. The archive is this repo's own commit.
        subprocess.run(["tar", "-x", "-f", str(archive), "-C", str(dest)], check=True)  # nosec B603 B607 -- fixed argv
    sha = subprocess.run(["git", "-C", str(REPO), "rev-parse", rev], check=True, capture_output=True, text=True).stdout.strip()  # nosec B603 B607
    (dest / ".materialized-from").write_text(sha + "\n", encoding="utf-8")
    print(f"{rev} ({sha}) -> {dest}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("materialize", help="extract a commit into an empty directory with git archive")
    m.add_argument("--rev", required=True)
    m.add_argument("--dest", required=True, type=Path)
    c = sub.add_parser("compare", help="classify + gate + handlers on two trees")
    c.add_argument("--pre", required=True, type=Path)
    c.add_argument("--post", required=True, type=Path)
    n = sub.add_parser("presentable", help="keys of header-carriable strip-empty characters, on two trees")
    n.add_argument("--pre", required=True, type=Path)
    n.add_argument("--post", required=True, type=Path)
    sub.add_parser("header-probe", help="what real uvicorn delivers for whitespace-only X-API-Key values")
    i = sub.add_parser("_inner", help=argparse.SUPPRESS)
    i.add_argument("--tree", required=True, type=Path)
    i.add_argument("--mode", required=True)
    i.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    if args.cmd == "materialize":
        return cmd_materialize(args.rev, args.dest)
    if args.cmd == "compare":
        return cmd_compare(args.pre, args.post)
    if args.cmd == "presentable":
        return cmd_presentable(args.pre, args.post)
    if args.cmd == "header-probe":
        return cmd_header_probe()
    out = _inner(args.tree, args.mode)
    args.out.write_text(json.dumps(out), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
