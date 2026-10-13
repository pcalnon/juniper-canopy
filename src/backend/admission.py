#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       X7 slice 1d — admission control for outbound cascor calls
#
# Author:        Paul Calnon
# Version:       0.1.0
# File Name:     admission.py
# File Path:     JuniperCanopy/juniper_canopy/src/backend/
#
# Date Created:  2026-09-05
# Last Modified: 2026-09-05
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#     Bounds concurrent outbound cascor calls (C4) and refuses to ISSUE work
#     whose caller has already given up (C10). Offloaded work cannot be
#     cancelled, so admission is the only point at which it can be declined.
#
#####################################################################################################################################################################################################
# References:
#     - juniper-ml/notes/JUNIPER_2026-09-03_JUNIPER-CANOPY_X7-EVENT-LOOP-BLOCKING-REMEDIATION-DESIGN.md §5.4, §4.2, C4, C10
#
#####################################################################################################################################################################################################

"""Admission control for outbound cascor calls (X7 slice 1d).

Slices 1a and 1c left one constraint outstanding. 1a moved every blocking call off the
event loop with a **bare** ``asyncio.to_thread``, which was safe only because 1b bounded
each call's cost — it did not bound how *many* run at once. Measured on canopy's real
cadence: inline issued **3** upstream requests where bare offload issued **42**, with the
executor peaking at **20/20**. Bare offload does not merely fail to help there; it
*deletes the back-pressure the blocked loop was accidentally providing*.

Two mechanisms, and they answer different questions:

* **The gate (C4)** bounds concurrency. It is an ``asyncio.Semaphore`` acquired on the
  **loop** side, before ``to_thread``, so a waiting caller occupies no worker thread. A
  ``threading`` semaphore inside the thread would bound cascor calls while still burning
  all 20 executor slots on threads doing nothing but waiting.
* **The deadline (C10)** bounds *usefulness*. ``asyncio.to_thread`` is **uncancellable**,
  so a caller that gives up cannot free its queued job: measured, 30 POSTs abandoned at
  1.25 s still produced **all 30** upstream calls, draining over 45 s behind a
  ``Semaphore(4)``. Since the work cannot be withdrawn, it must instead be **declined at
  admission** — the worker checks the deadline immediately before issuing, so in-flight
  work completes and queued work for a departed caller never starts.

**Why the deadline is a value and not a check.** ``Request.is_disconnected`` is a
coroutine and unreachable from inside a worker thread, so "has the caller gone?" cannot be
asked at the point it matters. The handler computes an absolute deadline up front and it
travels with the job.

**It travels in a ContextVar, not an argument.** ``asyncio.to_thread`` copies the current
context into the worker, so a deadline set per-request is visible inside the thread with
no change to any call site's signature. Threading it through ~50 call sites by hand would
be fifty chances to forget one, and a forgotten one fails *open* — it issues the work.
"""

from __future__ import annotations

import asyncio
import logging
import time
from contextvars import ContextVar
from typing import Any, Callable, Optional, TypeVar

from canopy_constants import BackendConstants

logger = logging.getLogger("juniper_canopy.backend.admission")

T = TypeVar("T")

# The absolute monotonic instant by which this request's caller stops caring. ``None``
# means "no deadline known" and is a deliberate FAIL-OPEN: an un-annotated caller gets
# bounded concurrency but its work is never declined. Skipping work a caller is still
# waiting for is a worse failure than issuing work it has abandoned -- the first breaks a
# feature, the second wastes an upstream call -- so the default has to be the safe one.
_deadline: ContextVar[Optional[float]] = ContextVar("cascor_call_deadline", default=None)


class CallerGoneAway(Exception):
    """Raised instead of issuing a cascor call whose caller's budget has elapsed.

    Not an upstream failure and not a canopy failure: the work was *declined*, and the
    distinction matters because the response almost certainly has no reader left. It is a
    dedicated type so a handler (or the app-wide handler in ``main``) can answer 503
    rather than letting it surface as a 500 that looks like a bug.
    """


class _Gate:
    """Lazily-built semaphore bounding concurrent outbound cascor calls.

    Lazy because an ``asyncio.Semaphore`` binds to the running loop on first use in some
    Python versions, and this module is imported at process start, long before uvicorn's
    loop exists. Building it at import time is the classic "attached to the wrong loop"
    bug, which shows up only under a test that creates its own loop.
    """

    def __init__(self, limit: int) -> None:
        self._limit = limit
        self._sem: Optional[asyncio.Semaphore] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        # Observability for the C4 test: the high-water mark of concurrent holders.
        self.in_flight = 0
        self.peak_in_flight = 0

    @property
    def limit(self) -> int:
        return self._limit

    def _semaphore(self) -> asyncio.Semaphore:
        loop = asyncio.get_running_loop()
        if self._sem is None or self._loop is not loop:
            self._sem = asyncio.Semaphore(self._limit)
            self._loop = loop
            self.in_flight = 0
            self.peak_in_flight = 0
        return self._sem

    def reset(self) -> None:
        """Drop the semaphore and counters. For tests that build their own loop."""
        self._sem = None
        self._loop = None
        self.in_flight = 0
        self.peak_in_flight = 0


_gate = _Gate(BackendConstants.CASCOR_MAX_CONCURRENT_CALLS)


def gate() -> _Gate:
    """The process-wide cascor gate (exposed so tests can read its high-water mark)."""
    return _gate


def set_deadline(budget_seconds: Optional[float]) -> None:
    """Record this request's caller budget as an absolute deadline.

    Called once per request. ``None`` clears it, which means work is never declined.
    """
    _deadline.set(None if budget_seconds is None else time.monotonic() + budget_seconds)


def get_deadline() -> Optional[float]:
    """The absolute deadline for the current context, or ``None`` when unbounded."""
    return _deadline.get()


def _issue(fn: Callable[..., T], deadline: Optional[float], *args: Any, **kwargs: Any) -> T:
    """Worker-thread body: decline, or issue.

    The check is here rather than at the call site on purpose. Between the handler
    computing the deadline and this line, the job may have sat in the gate's queue for
    an arbitrary time -- and that queue wait is exactly the interval during which the
    caller gives up. Checking before ``to_thread`` would test the wrong instant.
    """
    if deadline is not None and time.monotonic() >= deadline:
        raise CallerGoneAway("caller budget elapsed before the cascor call was issued")
    return fn(*args, **kwargs)


async def offload(fn: Callable[..., T], /, *args: Any, **kwargs: Any) -> T:
    """Run a blocking cascor call off-loop, bounded (C4) and deadline-guarded (C10).

    Drop-in for ``await asyncio.to_thread(fn, ...)`` at every cascor call site. The
    signature is identical on purpose: the conversion is mechanical, so it can be
    complete, and a site that is converted cannot silently opt out of the gate.

    Raises:
        CallerGoneAway: when the deadline elapsed before the call was issued. The
            upstream request is **not** made.
    """
    g = _gate
    async with g._semaphore():
        g.in_flight += 1
        g.peak_in_flight = max(g.peak_in_flight, g.in_flight)
        try:
            return await asyncio.to_thread(_issue, fn, _deadline.get(), *args, **kwargs)
        finally:
            g.in_flight -= 1
