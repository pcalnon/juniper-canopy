#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     2026-09-04_async_blocking_callgraph.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-09-04
# Last Modified: 2026-09-04
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   X7 slice 1a -- find async functions that call, without
#                awaiting, a function that transitively performs blocking
#                network I/O. Answers the question the committed gate
#                cannot: which calls block through a helper.
#####################################################################
"""Transitive blocking-I/O census for X7 slice 1a.

**Why this exists.** ``src/tests/regression/test_x7_off_loop_discipline.py`` is the
committed gate, and it is deliberately narrow: it reads ``main.py`` only, and it decides
"is this receiver an I/O client?" by resolving the *receiver* to its factory. That
answers the question exactly once, at the call site. It cannot answer the other shape of
the same defect -- ``self.some_method()`` inside an ``async def``, where ``some_method``
is an ordinary local method whose *body* reaches the network. Its own docstring names
this limit and defers it to "a model of which adapter methods perform I/O".

This script is that model. It builds a name-keyed call graph over canopy's own sources
plus the two client libraries, seeds it with the primitives that actually touch a socket,
propagates the taint to a fixed point, and then reports every **non-awaited** call to a
tainted function that appears inside an ``async def``.

**Resolution is by bare method name, and that is deliberate.** Python's dynamic dispatch
makes exact receiver typing undecidable here, so ``a.foo()`` taints if *any* ``def foo``
anywhere in the corpus is tainted. That over-reports -- two unrelated ``close()`` methods
collapse into one node -- and over-reporting is the correct bias for a safety scan whose
output a human adjudicates. It does **not** under-report through a helper, which is the
failure this script exists to catch. Read every hit before acting on it; the ADJUDICATED
table below records the ones already read, and why each verdict was reached.

Usage (from the repo root)::

    python util/ad-hoc/2026-09-04_async_blocking_callgraph.py
    python util/ad-hoc/2026-09-04_async_blocking_callgraph.py --all   # include adjudicated

Exit status is always 0: this is an instrument, not a gate. The gate is the pytest file.
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "src"


def _juniper_root() -> Path:
    """The directory holding the sibling repos.

    Not ``REPO.parent``: this repo is normally checked out as a worktree under
    ``Juniper/worktrees/``, so ``REPO.parent`` is the worktree pen, not the ecosystem
    root, and the client corpus silently resolves to nothing. A missing corpus is the
    worst failure this script has -- every adapter method looks pure and the census
    prints a confident zero -- so walk up and *prove* the sibling is there.
    """
    for candidate in [REPO, *REPO.parents]:
        if (candidate / "juniper-cascor-client").is_dir():
            return candidate
    raise SystemExit("cannot locate the Juniper root (no sibling juniper-cascor-client)")


JUNIPER = _juniper_root()

# The client libraries canopy calls through. Their bodies are where the actual
# ``requests`` calls live, so the corpus must include them or every adapter method
# looks pure.
EXTERNAL_CORPUS = [
    JUNIPER / "juniper-cascor-client" / "juniper_cascor_client",
    JUNIPER / "juniper-data-client" / "juniper_data_client",
]

# Socket-touching primitives. A function whose body contains a call matching one of
# these is tainted at seed time, before any propagation.
IO_PRIMITIVES = {
    # requests / httpx sync surface
    "get", "post", "put", "delete", "patch", "head", "request", "send",
    # the client libraries' own private verbs
    "_get", "_post", "_put", "_delete", "_patch", "_request",
    # stdlib + drivers
    "urlopen", "connect", "execute", "execute_async", "ping",
}

# Receivers that make an ``IO_PRIMITIVES`` name mean "network", rather than
# "dict.get" or "list.get". Without this every ``.get(...)`` on a dict seeds the taint
# and the whole corpus goes red.
IO_RECEIVER_HINTS = {
    "requests", "httpx", "session", "_session", "client", "_client", "http",
    "_http", "urllib", "cluster", "_cluster", "redis", "_redis", "conn", "_conn",
    "pool", "_pool", "s",
}

# Calls that are named like I/O but are verified in-process. Keyed by the unparsed
# receiver expression so a prefix can never widen silently -- the same discipline the
# committed gate uses for ``backend._demo.*``.
NOT_IO_EXPRESSIONS = {
    "self._lock.acquire",
    "self.health.snapshot",
    "self.relay_health.snapshot",
}

# Callees ruled on ONCE, for every site that reaches them. Keyed by the callee
# expression -> verdict text.
#
# **Why keying by expression is sound here, when it was catastrophic in the gate.**
# The committed gate once exempted by expression and was unsound: it asked "is this call
# offloaded?", which is a property of the *call site*, so one offloaded
# ``backend.get_status`` made every other one invisible and hid 15 live sites. This table
# asks a different question -- "does this callee reach the network?" -- and that is a
# property of the *callee*, identical at every site that names it. Ruling once is
# therefore correct. Keep the distinction: never move a site-dependent judgement in here.
ADJUDICATED_CALLEES = {
    "training_state.get_state": "in-memory TrainingState dict copy; name collides with tainted get_state",
    "demo.training_state.get_state": "same TrainingState object, demo branch",
    "backend._demo.get_network": "``return self.network`` (demo_mode.py:1752); also gate-adjudicated",
    "websocket_manager.broadcast": "async coroutine object built here, awaited or scheduled elsewhere",
    "websocket_manager.disconnect": "in-memory connection bookkeeping",
    "websocket_manager.get_statistics": "in-memory counters",
    "self.disconnect": "websocket_manager's own bookkeeping method",
    "schedule_broadcast": "hands a coroutine to the loop via call_soon_threadsafe; never blocks",
    "_broadcast_snapshot_op": "builds a payload from training_state and schedules it",
    "_seed_training_state": "reads cached get_synced_state() (service) or the recurrence "
    "backend's lock-guarded in-memory get_status(); no branch does I/O",
    "get_redis_client": "singleton factory; the eager ping is commented out at redis_client.py:236 "
    "and redis ConnectionPool is lazy, so construction touches no socket",
    "_stream_is_alive": "consults the cascor-client stream's in-memory frame-recency surface",
    "is_alive": "on the WS stream object in _probe_liveness -- frame recency, not an HTTP probe",
    "thread.is_alive": "threading.Thread.is_alive; collides with the cascor client's HTTP is_alive",
    "self._connect_loop": "coroutine handed to create_task",
    "_relay_loop": "coroutine handed to create_task",
    "_websocket_keepalive_loop": "coroutine handed to create_task",
}

# Hits already read and ruled on at ONE site. ``(file, function, callee)`` -> verdict.
# Anything in neither table is unadjudicated and prints by default.
ADJUDICATED = {
    ("backend/service_backend.py", "shutdown", "self._adapter.shutdown"): (
        "OUT -- Session.close() releases pooled sockets locally; no round trip, so no "
        "unbounded wait on an unreachable upstream."
    ),
    ("backend/demo_backend.py", "initialize", "self._demo.start"): (
        "OUT of 1a -- demo simulator start; reaches JuniperDataClient, which the design "
        "books as residual (demo_mode.py:918/:1829), not slice 1a."
    ),
    ("backend/demo_backend.py", "shutdown", "self._demo.stop"): (
        "OUT -- stops the simulator thread; no upstream call."
    ),
}


def _iter_py(root: Path):
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root) if root in path.parents or root == path.parent else path
        if "tests" in path.parts or path.name.startswith("test_"):
            continue
        yield path, rel


def _receiver_name(node: ast.AST) -> str | None:
    """The *immediate* receiver of a call, not the root of its attribute chain.

    ``self.session.request(...)`` must read as a request on ``session``. Rooting the
    chain instead yields ``self``, which is true of nearly every method call in the
    corpus and so discriminates nothing -- an earlier draft did exactly that, seeded
    zero functions, and printed "0 hits" over a file with 52 known ones.
    """
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return None


def _calls_in(fn: ast.AST) -> list[tuple[str, str | None, ast.Call]]:
    """(callee_name, receiver_root, node) for every attribute/name call in ``fn``.

    Nested function definitions are included on purpose: a closure handed to
    ``to_thread`` runs off-loop, but one merely *defined* inside a handler and called
    inline does not, and only the caller's ``await`` distinguishes them.
    """
    out = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute):
            out.append((node.func.attr, _receiver_name(node.func.value), node))
        elif isinstance(node.func, ast.Name):
            out.append((node.func.id, None, node))
    return out


def build_corpus():
    """name -> {callee names}, plus the seed set of directly-tainted names."""
    graph: dict[str, set[str]] = {}
    tainted: set[str] = set()
    roots = [SRC] + [p for p in EXTERNAL_CORPUS if p.exists()]

    for root in roots:
        for path, _rel in _iter_py(root):
            try:
                tree = ast.parse(path.read_text())
            except (SyntaxError, UnicodeDecodeError):
                continue
            for fn in ast.walk(tree):
                if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                callees = graph.setdefault(fn.name, set())
                for name, recv, node in _calls_in(fn):
                    callees.add(name)
                    if name in IO_PRIMITIVES and recv in IO_RECEIVER_HINTS:
                        if isinstance(node.func, ast.Attribute) and ast.unparse(node.func) in NOT_IO_EXPRESSIONS:
                            continue
                        tainted.add(fn.name)
    return graph, tainted


def propagate(graph: dict[str, set[str]], tainted: set[str]) -> set[str]:
    """Fixed point: a function is tainted if it calls a tainted function."""
    changed = True
    while changed:
        changed = False
        for name, callees in graph.items():
            if name in tainted:
                continue
            if callees & tainted:
                tainted.add(name)
                changed = True
    return tainted


def census(tainted: set[str]):
    """Every non-awaited call to a tainted function inside an ``async def``."""
    hits = []
    for path, _rel in _iter_py(SRC):
        try:
            tree = ast.parse(path.read_text())
        except (SyntaxError, UnicodeDecodeError):
            continue
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                child._parent = parent  # type: ignore[attr-defined]

        # A closure handed to an offloader runs off the loop; its body is exempt.
        offloaded_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "attr", None) in {"to_thread", "run_in_executor"}:
                for arg in node.args:
                    if isinstance(arg, ast.Name):
                        offloaded_names.add(arg.id)
                    elif isinstance(arg, ast.Attribute):
                        offloaded_names.add(arg.attr)

        for fn in ast.walk(tree):
            if not isinstance(fn, ast.AsyncFunctionDef):
                continue
            exempt: set[int] = set()
            for inner in ast.walk(fn):
                if isinstance(inner, (ast.FunctionDef, ast.AsyncFunctionDef)) and inner is not fn:
                    if inner.name in offloaded_names:
                        exempt |= {id(n) for n in ast.walk(inner)}
            for name, _recv, node in _calls_in(fn):
                if id(node) in exempt or name not in tainted:
                    continue
                if isinstance(getattr(node, "_parent", None), ast.Await):
                    continue
                if isinstance(node.func, ast.Attribute) and node.func.attr in offloaded_names:
                    # ``to_thread(obj.method)`` -- a bare attribute, never a Call node.
                    pass
                expr = ast.unparse(node.func)
                rel = str(path.relative_to(SRC))
                hits.append((rel, node.lineno, fn.name, expr))
    return sorted(set(hits))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--all", action="store_true", help="include already-adjudicated hits")
    args = ap.parse_args()

    graph, seeds = build_corpus()
    tainted = propagate(graph, set(seeds))

    print(f"corpus: {len(graph)} functions, {len(seeds)} seeded, {len(tainted)} tainted after propagation")
    if not seeds:
        print("FAIL: nothing seeded -- the scan is broken, not the code", file=sys.stderr)
        return 0

    hits = census(tainted)
    shown = 0
    for rel, lineno, fnname, expr in hits:
        key = (rel, fnname, expr)
        verdict = ADJUDICATED.get(key) or ADJUDICATED_CALLEES.get(expr)
        if verdict and not args.all:
            continue
        shown += 1
        flag = f"  [{verdict}]" if verdict else ""
        print(f"{rel}:{lineno}  async {fnname}() -> {expr}{flag}")

    print(f"\n{shown} unadjudicated hit(s); {len(hits)} total.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
