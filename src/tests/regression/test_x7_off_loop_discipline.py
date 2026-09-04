#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_x7_off_loop_discipline.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-09-04
# Last Modified: 2026-09-04
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   X7 slice 1a -- no async route handler may perform a
#                synchronous, network-bound call on the event loop.
#####################################################################
"""The X7 off-loop discipline gate.

X7 is juniper-canopy ceasing to answer HTTP -- ``/v1/health`` included -- whenever an
upstream is unreachable. The mechanism is synchronous, retrying network I/O executed
inside ``async def`` route handlers on a **single-worker** uvicorn: one such call blocks
the whole event loop, so every route stalls, including pure-async ones. Measured
end-to-end: 5.7 ms healthy, 3.0 s with cascor stopped, **123.12 s with cascor hung**.

This is a **gate, not a sample**. Its assertion is that the count is *zero*, so it cannot
be satisfied by fixing the sites someone happened to notice -- which matters because this
defect has recurred: SEC-F20 fixed the same mechanism once, shipped a comment with no
test, and X7 is that recurrence.

**Why not ruff.** The repository already runs a CI-blocking hook named "Async-route audit
(BUG-JD-10 class)" (``ruff --select ASYNC``). It reports "All checks passed!" against
these sites, because ruff's ASYNC rules match a hardcoded list of *callee names* and
``backend.get_status()`` is an opaque method call. No ruff configuration can see this.

**Why this check resolves provenance instead of matching names.** An earlier draft matched
receiver names and was wrong in both directions: the bare name ``client`` is bound in
``main.py`` to the cascor client, the redis client, the cassandra client *and* an
``httpx.AsyncClient``, so it flagged an awaited async call as blocking. A name-matching
gate would repeat exactly the flaw that makes the ruff hook useless. Receivers are
therefore resolved to the factory that bound them.

**Why closure-aware.** Canopy's *correct* idiom takes two shapes a lexical scan misreads:
a bare-attribute offload (``to_thread(backend.get_status)`` -- the backend call is an
``Attribute``, never a ``Call``) and a named closure handed to ``to_thread``. A naive scan
reports 50 unguarded / 0 guarded on this file, emitting false positives on the exemplar
code while missing every correct offload.

**SCOPE LIMIT -- read this before treating a green result as "slice 1a is done".** This gate
reads ``main.py`` only. Slice 1a is larger: §5.2 of the design also puts in scope the metrics
relay's inline ``extract_network_topology()`` (``backend/cascor_service_adapter.py:771``,
inside ``async def _relay_loop()``), measured at **123 s blocked per 183 s with no user
present**. That call is a ``self``-method whose I/O is internal, so a receiver-based scan
cannot see it, and extending this gate to cover it needs a model of which adapter methods
perform I/O. Until that exists, **the relay is tracked as a named work item, not by this
gate**. Treating a green gate as proof that 1a is complete would be exactly the
"core now, remaining paths later" split that let SEC-F20 recur as X7.

Buckets, all reported so none hides:

* ``CASCOR``     -- the module ``backend`` global or anything reached through it.
* ``OTHER``      -- another *synchronous* network client (redis, cassandra). Same
  mechanism, different upstream, so in scope: the fix is defined by mechanism, and
  excluding these would be the path-subset exclusion that let SEC-F20 recur.
* ``LOCAL``      -- verified to perform no network I/O (``DataAdapter`` is pure torch
  computation). Out of scope: X7 is an unbounded wait on an unreachable upstream.
* ``ASYNC``      -- bound from an async factory; its calls are awaited.
* ``UNRESOLVED`` -- provenance undetermined. **Fails the gate**, because an unaudited
  bucket is how a check goes quietly wrong.
"""

from __future__ import annotations

import ast
from pathlib import Path

MAIN_PY = Path(__file__).resolve().parents[2] / "main.py"

ASYNC_FACTORIES = {"AsyncClient"}
SYNC_NETWORK_FACTORIES = {"get_redis_client", "get_cassandra_client"}
CASCOR_FACTORIES = {"_require_service_adapter"}
NO_IO_FACTORIES = {"DataAdapter"}
CASCOR_ROOTS = {"backend"}
OFFLOADERS = {"to_thread", "run_in_executor"}

# Specific calls verified to be in-process accessors despite being reached through
# ``backend``. Listed by exact expression, never by receiver prefix: demo mode DOES reach
# juniper-data elsewhere (through ``JuniperDataClient``, which wraps ``requests`` internally
# and so is invisible to a grep for ``requests.``), so excluding ``backend._demo.*`` wholesale
# would hide real I/O. Each entry below was read and confirmed:
#   _demo.get_network()       -> ``return self.network``            (demo_mode.py:1752)
#   _demo.get_current_state() -> lock-guarded dict copy, no I/O      (demo_mode.py:2069)
VERIFIED_NO_IO_CALLS = {
    "backend._demo.get_network",
    "backend._demo.get_current_state",
}

# Receiver roots that plausibly perform I/O. A receiver outside this set with unknown
# provenance is a local helper, not an upstream client, and is not adjudicated.
IO_RECEIVER_ROOTS = {"backend", "adapter", "_adapter", "client", "_client"}


def _root_name(node: ast.AST) -> str | None:
    while isinstance(node, ast.Attribute):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def _offloaded_targets(tree: ast.AST) -> set[str]:
    """Names and bare attributes handed to an offloader anywhere in the module."""
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "attr", None) in OFFLOADERS:
            for arg in node.args:
                if isinstance(arg, ast.Name):
                    out.add(arg.id)
                elif isinstance(arg, ast.Attribute):
                    out.add(ast.unparse(arg))
    return out


def _provenance(fn: ast.AsyncFunctionDef) -> dict[str, str]:
    """Local name -> the factory that bound it, within one handler."""
    bound: dict[str, str] = {}
    for node in ast.walk(fn):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            callee = node.value.func
            factory = getattr(callee, "attr", None) or getattr(callee, "id", None)
            for target in node.targets:
                if isinstance(target, ast.Name) and factory:
                    bound[target.id] = factory
        for item in getattr(node, "items", []) or []:
            ctx = item.context_expr
            if isinstance(ctx, ast.Call):
                factory = getattr(ctx.func, "attr", None) or getattr(ctx.func, "id", None)
                var = item.optional_vars
                if isinstance(var, ast.Name) and factory:
                    bound[var.id] = factory
    return bound


def _classify(receiver: ast.AST, bound: dict[str, str]) -> str:
    root = _root_name(receiver)
    if root is None:
        return "SKIP"
    if root in CASCOR_ROOTS:
        return "CASCOR"
    factory = bound.get(root)
    if factory in ASYNC_FACTORIES:
        return "ASYNC"
    if factory in CASCOR_FACTORIES:
        return "CASCOR"
    if factory in SYNC_NETWORK_FACTORIES:
        return "OTHER"
    if factory in NO_IO_FACTORIES:
        return "LOCAL"
    return "UNRESOLVED" if root in IO_RECEIVER_ROOTS else "SKIP"


def census() -> dict[str, list[str]]:
    """Bucket every un-offloaded call on an I/O receiver inside an async handler."""
    tree = ast.parse(MAIN_PY.read_text())
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            child._parent = parent  # type: ignore[attr-defined]

    offloaded = _offloaded_targets(tree)
    buckets: dict[str, list[str]] = {k: [] for k in ("CASCOR", "OTHER", "LOCAL", "ASYNC", "UNRESOLVED")}

    for fn in ast.walk(tree):
        if not isinstance(fn, ast.AsyncFunctionDef):
            continue
        bound = _provenance(fn)

        exempt: set[int] = set()
        for inner in ast.walk(fn):
            if isinstance(inner, (ast.FunctionDef, ast.AsyncFunctionDef)) and inner is not fn and inner.name in offloaded:
                exempt |= {id(n) for n in ast.walk(inner)}

        for node in ast.walk(fn):
            if id(node) in exempt or not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Attribute):
                continue
            expr = ast.unparse(node.func)
            # NOTE: exemption is SITE-LOCAL only (the ``exempt`` node-id set above, which
            # covers calls inside a closure that is itself handed to an offloader). It must
            # NEVER be expression-based across sites. An earlier draft skipped any call whose
            # expression appeared offloaded ANYWHERE in the module, which made the gate
            # unsound in the worst possible way: because :3574 offloads ``backend.get_status``,
            # every OTHER ``backend.get_status()`` became invisible -- including the three
            # health endpoints X7 is defined by. Measured, that hid 15 sites (52 real vs 37
            # reported), and it degraded as work progressed: offloading one site made its
            # untouched twin vanish too, so the gate would have reached 0 with ~21 blocking
            # calls still on the loop. A gate that certifies a partial fix as complete is the
            # exact failure this slice exists to prevent.
            if isinstance(getattr(node, "_parent", None), ast.Await):
                continue
            if expr in VERIFIED_NO_IO_CALLS:
                buckets["LOCAL"].append(f"main.py:{node.lineno} {fn.name}() -> {expr}")
                continue
            kind = _classify(node.func.value, bound)
            if kind != "SKIP":
                buckets[kind].append(f"main.py:{node.lineno} {fn.name}() -> {expr}")
    return buckets


def test_census_instrument_is_not_vacuous():
    """The gate must be able to see anything at all.

    A scan that silently matches nothing would pass forever. Canopy offloads correctly in
    ~30 places, so the offloaded-target set is non-empty by construction; if this fails,
    the parser or the traversal is broken and the gate below is meaningless.
    """
    tree = ast.parse(MAIN_PY.read_text())
    assert _offloaded_targets(tree), "no offloaded targets found -- the scan is broken, not the code"

    buckets = census()
    seen = sum(len(v) for v in buckets.values())
    assert seen > 0, "the scan classified nothing at all -- it cannot discriminate"


def test_no_blocking_calls_on_the_event_loop():
    """X7 gate: zero synchronous network calls in async route handlers.

    ``LOCAL`` and ``ASYNC`` are excluded on verified grounds (no network I/O; awaited).
    ``UNRESOLVED`` fails deliberately -- a receiver whose provenance is unknown must be
    adjudicated and added to the tables above, not waved through.
    """
    buckets = census()
    blocking = buckets["CASCOR"] + buckets["OTHER"] + buckets["UNRESOLVED"]

    detail = "\n  ".join(sorted(blocking))
    assert not blocking, f"{len(blocking)} synchronous network call(s) run on the event loop in async handlers:\n  {detail}"
