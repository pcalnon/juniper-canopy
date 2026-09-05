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
reads ``main.py`` only, and it guards two shapes there: a direct call on a receiver that
resolves to an I/O client, and a bare call to a module-level helper whose body reaches one
(``_blocking_helpers``). The second was added after the first shipped: ``_extract_meta_params``
held a ``backend.get_status()`` and ``create_snapshot`` called it twice, so the gate read a
clean **0** over two live blocking calls -- the same "green over a partial fix" failure as the
module-global exemption fixed in ``d33ab0a``, reached by a different route.

**Four sites outside ``main.py`` are NOT guarded by this file.** They were found by
``util/ad-hoc/2026-09-04_async_blocking_callgraph.py`` -- a transitive taint scan over
canopy plus both client libraries -- and fixed in the same change:
``cascor_service_adapter.py`` ``connect()`` (``self._client.is_alive()``) and ``_relay_loop()``
(``self.extract_network_topology()``, measured at **123 s blocked per 183 s with no user
present**), and ``service_backend.py`` ``initialize()`` (``attach_to_existing()`` and
``CascorStateSync(...).sync()``, both on the runtime model-swap path via ``_swap_backend``).
Guarding them here needs a model of which adapter methods perform I/O; that model exists in
the ad-hoc script but is not a committed gate. **Run the script when touching the adapter.**
Treating a green gate as proof that 1a is complete would be exactly the "core now, remaining
paths later" split that let SEC-F20 recur as X7.

Buckets, all reported so none hides:

* ``CASCOR``     -- the module ``backend`` global or anything reached through it.
* ``HELPER``     -- a bare call to a module-level sync function that reaches the network
  through its own body. Same mechanism, invisible to receiver resolution.
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
# ``offload`` is slice 1d's admission-controlled wrapper around ``to_thread`` (bounded
# concurrency + the caller's deadline). It is an offloader for this gate's purposes: the
# work leaves the loop exactly as before, it merely does so through a gate. Omitting it
# would make the gate report every 1d-converted site as blocking — the gate would fail
# BECAUSE the code got safer, which is the fastest way to teach someone to delete a gate.
OFFLOADERS = {"to_thread", "run_in_executor", "offload"}

# Specific calls verified to be in-process accessors despite being reached through
# ``backend``. Listed by exact expression, never by receiver prefix: demo mode DOES reach
# juniper-data elsewhere (through ``JuniperDataClient``, which wraps ``requests`` internally
# and so is invisible to a grep for ``requests.``), so excluding ``backend._demo.*`` wholesale
# would hide real I/O. Each entry below was read and confirmed:
#   _demo.get_network()       -> ``return self.network``            (demo_mode.py:1752)
#   _demo.get_current_state() -> lock-guarded dict copy, no I/O      (demo_mode.py:2069)
#   get_synced_state()        -> ``return self._synced_state``      (service_backend.py:372)
#   set_state_update_callback -> stores the callback, and forwards to the adapter's own
#                                store (service_backend.py:72, cascor_service_adapter.py:566);
#                                both implementations are assignments, nothing else
VERIFIED_NO_IO_CALLS = {
    "backend._demo.get_network",
    "backend._demo.get_current_state",
    "backend.get_synced_state",
    "backend.set_state_update_callback",
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
        if not isinstance(node, ast.Call):
            continue
        # ``asyncio.to_thread(...)`` is an Attribute call; the bare ``offload(...)`` is a
        # Name call. Match either, or the 1d idiom is invisible here.
        callee = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
        if callee in OFFLOADERS:
            for arg in node.args:
                if isinstance(arg, ast.Name):
                    out.add(arg.id)
                elif isinstance(arg, ast.Attribute):
                    out.add(ast.unparse(arg))
    return out


def _provenance(fn: ast.AST) -> dict[str, str]:
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


def _blocking_helpers(tree: ast.Module) -> set[str]:
    """Module-level **sync** functions that transitively perform a blocking call.

    Everything above answers one question -- "is this call's receiver an I/O client?" --
    and that is the wrong question at ``_extract_meta_params()``: a bare module function
    whose *body* holds ``backend.get_status()``. At its call sites the receiver is not a
    client at all, it is nothing, so a receiver-resolving scan sees nothing while the
    call blocks the loop exactly as the direct one does.

    This was not hypothetical. ``create_snapshot`` called it twice, and both sites were
    invisible to this gate while it reported a clean **0** for the file. That is the same
    failure shape as the module-global exemption fixed in ``d33ab0a`` -- a gate reading
    zero over live blocking calls -- reached by a different route, which is the argument
    for closing it here rather than noting it.

    Transitive on purpose: a helper that calls a helper that blocks, blocks.
    """
    funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    direct: set[str] = set()
    calls: dict[str, set[str]] = {}

    for name, fn in funcs.items():
        bound = _provenance(fn)
        callees: set[str] = set()
        for node in ast.walk(fn):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name):
                callees.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                if ast.unparse(node.func) in VERIFIED_NO_IO_CALLS:
                    continue
                if _classify(node.func.value, bound) in ("CASCOR", "OTHER"):
                    direct.add(name)
        calls[name] = callees

    blocking = set(direct)
    changed = True
    while changed:
        changed = False
        for name, callees in calls.items():
            if name not in blocking and callees & blocking:
                blocking.add(name)
                changed = True
    return blocking


def census(tree: ast.Module | None = None) -> dict[str, list[str]]:
    """Bucket every un-offloaded call on an I/O receiver inside an async handler.

    ``tree`` defaults to ``main.py``; passing one lets the tests below drive the whole
    classifier over a synthetic module, so the rules can be proved to *fire* rather than
    only proved to be quiet against a file that currently happens to be clean.
    """
    if tree is None:
        tree = ast.parse(MAIN_PY.read_text())
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            child._parent = parent  # type: ignore[attr-defined]

    offloaded = _offloaded_targets(tree)
    helpers = _blocking_helpers(tree)
    buckets: dict[str, list[str]] = {k: [] for k in ("CASCOR", "OTHER", "HELPER", "LOCAL", "ASYNC", "UNRESOLVED")}

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
            if isinstance(node.func, ast.Name):
                # A bare call to a module-level sync helper that reaches the network.
                if node.func.id in helpers and not isinstance(getattr(node, "_parent", None), ast.Await):
                    buckets["HELPER"].append(f"main.py:{node.lineno} {fn.name}() -> {node.func.id}()")
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


# A miniature ``main.py``: one direct blocking call, one that blocks only through a
# module-level helper, one that blocks two helpers deep, and three that must stay quiet.
_SYNTHETIC = """
import asyncio


def _reaches_network():
    return backend.get_status()


def _one_more_hop():
    return _reaches_network()


def _pure_helper():
    return {"a": 1}


async def direct_handler():
    return backend.get_metrics()


async def helper_handler():
    return _reaches_network()


async def transitive_handler():
    return _one_more_hop()


async def clean_handler():
    return await asyncio.to_thread(backend.get_status)


async def helper_awaited_handler():
    return await _reaches_network()


async def pure_handler():
    return _pure_helper()
"""


def test_helper_rule_fires_on_a_call_that_blocks_through_a_helper():
    """The HELPER rule must catch what receiver resolution structurally cannot.

    This is the check that would have failed before ``_extract_meta_params`` was made
    async: the gate read a clean 0 over ``main.py`` while two of ``create_snapshot``'s
    calls blocked the loop through it. Asserting only "the real file is clean" cannot
    distinguish a working rule from a rule that never fires, so the rule is exercised
    here against a module that is deliberately dirty.
    """
    tree = ast.parse(_SYNTHETIC)

    helpers = _blocking_helpers(tree)
    assert "_reaches_network" in helpers, "a helper holding backend.get_status() must be blocking"
    assert "_one_more_hop" in helpers, "blocking must propagate transitively through helpers"
    assert "_pure_helper" not in helpers, "a helper with no network call must stay clean"

    buckets = census(tree)
    flagged = " ".join(buckets["HELPER"])
    assert "helper_handler" in flagged, "a bare call to a blocking helper must be flagged"
    assert "transitive_handler" in flagged, "a two-hop blocking helper must be flagged"
    assert "pure_handler" not in flagged, "a pure helper must not be flagged"
    assert "helper_awaited_handler" not in flagged, "an awaited helper is already off the loop"

    # And the direct rule still works alongside it, in its own bucket.
    assert any("direct_handler" in hit for hit in buckets["CASCOR"])
    assert not any("clean_handler" in hit for hit in buckets["CASCOR"])


def test_no_blocking_calls_on_the_event_loop():
    """X7 gate: zero synchronous network calls in async route handlers.

    ``LOCAL`` and ``ASYNC`` are excluded on verified grounds (no network I/O; awaited).
    ``UNRESOLVED`` fails deliberately -- a receiver whose provenance is unknown must be
    adjudicated and added to the tables above, not waved through.
    """
    buckets = census()
    blocking = buckets["CASCOR"] + buckets["OTHER"] + buckets["HELPER"] + buckets["UNRESOLVED"]

    detail = "\n  ".join(sorted(blocking))
    assert not blocking, f"{len(blocking)} synchronous network call(s) run on the event loop in async handlers:\n  {detail}"
