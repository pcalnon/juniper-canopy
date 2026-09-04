#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_x7_gate_soundness.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-09-04
# Last Modified: 2026-09-04
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   X7 slice 1a -- the off-loop gate must stay able to see
#                a partial revert the clean-file test cannot.
#####################################################################
"""Soundness pins for the X7 off-loop gate in ``test_x7_off_loop_discipline``.

#567's gate already proves two things: the HELPER rule fires on a dirty synthetic
module, and the real ``main.py`` currently classifies nothing as blocking. Those
two tests stay green under four reverts that restore X7:

* Exemption becomes **expression-global** again (``d33ab0a``). One
  ``to_thread(backend.get_status)`` then hides every other ``backend.get_status()``
  -- including the three health endpoints X7 is defined by. The clean-file test
  cannot see this: a fully-offloaded ``main.py`` is green under both rules.
* ``UNRESOLVED`` or ``OTHER`` is dropped from the blocking composition. The real
  file has neither, so the clean-file test stays green while redis/cassandra and
  unaudited receivers become invisible.
* A live I/O expression (``backend.get_status``) is added to
  ``VERIFIED_NO_IO_CALLS``. That is the module-global exemption by another name;
  ``_seed_training_state`` records why it is not available.
* The **closure-local** exemption breaks, so the correct
  ``to_thread(_fetch)`` idiom is flagged and the gate becomes unshippable.

This file drives the gate's ``census`` over synthetic modules that are
deliberately dirty in one of those ways. It does not restack T-A2/T-A3/T-A4,
the real-file gate, or the four adapter sites in ``test_x7_sites_outside_main_gate``.
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import pytest

_GATE_PATH = Path(__file__).resolve().parent / "test_x7_off_loop_discipline.py"
_SPEC = importlib.util.spec_from_file_location("x7_off_loop_gate", _GATE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_GATE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_GATE)

census = _GATE.census
VERIFIED_NO_IO_CALLS = _GATE.VERIFIED_NO_IO_CALLS

# Live I/O the production comment at main.py:_seed_training_state forbids
# putting in VERIFIED_NO_IO_CALLS. Adding any of these is the module-global
# exemption that made the gate unsound in d33ab0a.
_FORBIDDEN_NO_IO = {
    "backend.get_status",
    "backend.get_metrics",
    "backend.is_training_active",
    "backend.get_network_topology",
    "backend.get_raw_topology",
}


def _blocking(buckets: dict[str, list[str]]) -> list[str]:
    """The same four buckets the gate treats as a fail."""
    return buckets["CASCOR"] + buckets["OTHER"] + buckets["HELPER"] + buckets["UNRESOLVED"]


# One offloaded ``backend.get_status`` and one inline call of the same
# expression. Expression-global exemption hides ``health_check``; site-local
# exemption does not. ``status_poll`` must stay quiet either way -- the
# offload is an Attribute, never a Call -- so a flag there is a false positive.
_TWIN_SITES = """
import asyncio


async def health_check():
    return backend.get_status()


async def status_poll():
    return await asyncio.to_thread(backend.get_status)
"""


# The correct idiom: a named closure handed to ``to_thread``. The call inside
# the closure is on the worker thread. The gate must not flag it.
_CLOSURE_OFFLOAD = """
import asyncio


async def handler():
    def _fetch():
        return backend.get_status()
    return await asyncio.to_thread(_fetch)
"""


# Redis/cassandra are the OTHER bucket. Same mechanism as cascor, different
# upstream -- excluding them is the path-subset exclusion that let SEC-F20 recur.
_OTHER_REDIS = """
async def handler():
    client = get_redis_client()
    return client.ping()
"""


# An I/O-shaped receiver whose factory was never bound. Must be UNRESOLVED,
# never waved through as SKIP.
_UNRESOLVED_CLIENT = """
async def handler():
    return client.get_status()
"""


# Verified in-process accessor -- LOCAL, not blocking.
_VERIFIED_NO_IO = """
async def handler():
    return backend.get_synced_state()
"""


# DataAdapter is pure torch. LOCAL, not blocking.
_LOCAL_ADAPTER = """
async def handler():
    adapter = DataAdapter()
    return adapter.forward(x)
"""


@pytest.mark.regression
@pytest.mark.unit
def test_exemption_is_site_local_not_expression_global():
    """A to_thread of ``backend.get_status`` must not hide an inline twin.

    This is the d33ab0a failure. The first draft skipped any call whose
    expression appeared offloaded *anywhere* in the module. Because one poll
    site offloads ``backend.get_status``, every other ``backend.get_status()``
    vanished -- including ``health_check``, ``health_check_deprecated`` and
    ``readiness_probe``. Measured: 52 real sites, 37 reported, and the count
    dropped as work progressed without the hidden twins being fixed.

    The clean-file test cannot catch a revert: ``main.py`` is fully offloaded,
    so both rules read 0.
    """
    buckets = census(ast.parse(_TWIN_SITES))
    flagged = " ".join(buckets["CASCOR"])

    assert "health_check" in flagged, (
        "inline backend.get_status() was not flagged -- exemption is expression-global "
        "again, and a single offload will hide the health endpoints"
    )
    assert "status_poll" not in flagged, "the offloaded Attribute was flagged -- false positive on the correct idiom"
    assert not buckets["UNRESOLVED"]
    assert not buckets["OTHER"]
    assert not buckets["HELPER"]


@pytest.mark.regression
@pytest.mark.unit
def test_offloaded_closure_is_not_flagged():
    """Calls inside a named closure handed to to_thread are already off the loop."""
    buckets = census(ast.parse(_CLOSURE_OFFLOAD))
    assert not _blocking(buckets), (
        f"the correct to_thread(_fetch) idiom was flagged: {_blocking(buckets)}"
    )


@pytest.mark.regression
@pytest.mark.unit
def test_redis_client_is_other_and_blocking():
    """Synchronous redis I/O on the loop is the same defect as cascor I/O."""
    buckets = census(ast.parse(_OTHER_REDIS))
    assert any("handler" in hit for hit in buckets["OTHER"]), (
        f"get_redis_client() was not classified OTHER: {buckets}"
    )
    assert any("handler" in hit for hit in _blocking(buckets))


@pytest.mark.regression
@pytest.mark.unit
def test_unbound_io_receiver_is_unresolved_and_blocking():
    """A receiver in IO_RECEIVER_ROOTS with no factory bind must fail the gate.

    An unaudited bucket is how a check goes quietly wrong. The real file has no
    UNRESOLVED hits, so dropping UNRESOLVED from the blocking list would leave
    the clean-file test green.
    """
    buckets = census(ast.parse(_UNRESOLVED_CLIENT))
    assert any("handler" in hit for hit in buckets["UNRESOLVED"]), (
        f"unbound client.get_status() was not UNRESOLVED: {buckets}"
    )
    assert any("handler" in hit for hit in _blocking(buckets))


@pytest.mark.regression
@pytest.mark.unit
def test_verified_no_io_and_data_adapter_are_not_blocking():
    """LOCAL accessors must stay out of the blocking composition."""
    no_io = census(ast.parse(_VERIFIED_NO_IO))
    adapter = census(ast.parse(_LOCAL_ADAPTER))

    assert any("handler" in hit for hit in no_io["LOCAL"])
    assert any("handler" in hit for hit in adapter["LOCAL"])
    assert not _blocking(no_io)
    assert not _blocking(adapter)


@pytest.mark.regression
@pytest.mark.unit
def test_live_io_is_not_on_the_verified_no_io_list():
    """``VERIFIED_NO_IO_CALLS`` must not become a second module-global exemption.

    ``_seed_training_state`` offloads recurrence ``get_status`` rather than
    listing it here, because the gate cannot see the ``backend_type`` guard and
    a future backend on that chain would then be invisible. Adding the live
    expressions to this set is the d33ab0a exemption by another name.
    """
    overlap = _FORBIDDEN_NO_IO & set(VERIFIED_NO_IO_CALLS)
    assert not overlap, (
        f"{sorted(overlap)} added to VERIFIED_NO_IO_CALLS -- that hides every "
        "matching call, including the health endpoints"
    )


def _gate_blocking_bucket_names() -> set[str]:
    """Bucket names concatenated into ``test_no_blocking_calls_on_the_event_loop``."""
    tree = ast.parse(_GATE_PATH.read_text())
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.FunctionDef):
            continue
        if fn.name != "test_no_blocking_calls_on_the_event_loop":
            continue
        for node in ast.walk(fn):
            if not isinstance(node, ast.Assign):
                continue
            if not any(isinstance(t, ast.Name) and t.id == "blocking" for t in node.targets):
                continue
            names: set[str] = set()
            for sub in ast.walk(node.value):
                if isinstance(sub, ast.Subscript) and isinstance(sub.slice, ast.Constant):
                    names.add(sub.slice.value)
            return names
    raise AssertionError("could not find the gate's blocking assignment")


@pytest.mark.regression
@pytest.mark.unit
def test_gate_blocking_composition_includes_other_and_unresolved():
    """The clean-file assertion must keep treating OTHER and UNRESOLVED as fails.

    ``census`` classifying those buckets is not enough: if the gate's own
    assertion dropped them, the real file (which has none) would stay green.
    """
    names = _gate_blocking_bucket_names()
    assert names == {"CASCOR", "OTHER", "HELPER", "UNRESOLVED"}, (
        f"gate blocking composition drifted: {sorted(names)}"
    )
