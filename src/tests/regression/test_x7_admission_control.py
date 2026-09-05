#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_x7_admission_control.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-09-05
# Last Modified: 2026-09-05
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   X7 slice 1d -- T-D1: work whose caller has gone is
#                DECLINED at admission, and cascor concurrency is bounded.
#####################################################################
"""X7 slice 1d tests: admission control.

Two constraints, and they fail in opposite directions, so each needs its own guard:

* **C4** — concurrency must be *bounded*. The failure is doing too much at once: bare
  offload turned 3 upstream requests into 42 and peaked the executor at 20/20.
* **C10** — work whose caller has gone must not be *issued*. The failure is doing work
  nobody wants: 30 POSTs abandoned at 1.25 s still produced all 30 upstream calls,
  draining over 45 s.

A test for either one alone passes happily while the other is broken. A semaphore of 1
satisfies C4 and destroys throughput; a deadline with no gate satisfies C10 and leaves
the executor saturated.

**Every assertion here is about work NOT done**, which is the hard kind to test and the
easy kind to fake. A test that asserts "the call was skipped" passes trivially if the
call never had a reason to happen — so each one below is paired with a control in which
the same setup, minus the elapsed deadline, DOES issue the call.
"""

from __future__ import annotations

import asyncio

import pytest

from backend.admission import CallerGoneAway, gate, offload, set_deadline
from canopy_constants import BackendConstants
from middleware import CallerBudgetMiddleware


@pytest.fixture(autouse=True)
def _fresh_gate():
    """Each test gets its own semaphore and counters.

    The gate is process-wide by design (it bounds a process-wide resource), so without
    this the peak-in-flight high-water mark would leak between tests and the C4 assertion
    would read another test's number.
    """
    gate().reset()
    set_deadline(None)
    yield
    gate().reset()
    set_deadline(None)


# --------------------------------------------------------------------------------------
# T-D1 -- work for a departed caller is declined, not issued
# --------------------------------------------------------------------------------------


@pytest.mark.regression
@pytest.mark.unit
class TestD1DeclineAtAdmission:
    async def test_elapsed_budget_means_the_call_is_never_issued(self):
        """T-D1. The upstream function must not run at all.

        Note what is asserted: not that the *result* was discarded, but that ``fn`` was
        never entered. ``asyncio.to_thread`` is uncancellable, so discarding a result is
        all a cancellation could ever achieve — the upstream request would still have been
        made. Declining at admission is the only point where the call can be prevented.
        """
        calls = []

        def upstream():
            calls.append(1)
            return "issued"

        set_deadline(-1.0)  # already elapsed
        with pytest.raises(CallerGoneAway):
            await offload(upstream)

        assert calls == [], "the upstream call was issued for a caller that had already gone"

    async def test_live_budget_still_issues_the_call(self):
        """Control for the above: identical setup, unelapsed deadline, call happens.

        Without this, ``test_elapsed_budget...`` would pass against an ``offload`` that
        never calls anything.
        """
        calls = []

        def upstream():
            calls.append(1)
            return "issued"

        set_deadline(30.0)
        assert await offload(upstream) == "issued"
        assert calls == [1]

    async def test_no_deadline_fails_open(self):
        """An un-annotated caller is bounded but never declined.

        Deliberate direction: declining work a caller still wants breaks a feature;
        issuing work a caller abandoned wastes an upstream call. If this ever flips to
        raising, every route absent from the budget table starts failing.
        """
        set_deadline(None)
        assert await offload(lambda: "issued") == "issued"

    async def test_the_deadline_is_checked_after_the_queue_wait_not_before(self):
        """The check must happen at issue time, not at call time.

        This is the whole mechanism. A job admitted while its budget was healthy can sit
        in the gate queue long enough to outlive it, and that queue wait is exactly the
        interval during which the caller gives up. Checking the deadline before
        ``to_thread`` would test an instant nobody cares about.

        Driven by filling the gate with slow holders so a late arrival really does queue.
        """
        import threading

        issued = []
        release = threading.Event()  # set from the loop, waited on in worker threads

        def occupy():
            # Bounded: never outlives the test even if ``release`` is never set.
            release.wait(timeout=2.0)
            return "held"

        async def hold():
            await offload(occupy)

        set_deadline(30.0)
        holders = [asyncio.create_task(hold()) for _ in range(BackendConstants.CASCOR_MAX_CONCURRENT_CALLS)]
        await asyncio.sleep(0.05)  # let the holders take every slot

        # This caller's budget expires while it waits for a slot.
        set_deadline(0.05)

        def late():
            issued.append(1)
            return "issued"

        late_task = asyncio.create_task(offload(late))
        await asyncio.sleep(0.2)
        release.set()

        with pytest.raises(CallerGoneAway):
            await late_task
        await asyncio.gather(*holders)

        assert issued == [], "a job that outlived its budget in the queue was still issued"


# --------------------------------------------------------------------------------------
# C4 -- bounded concurrency
# --------------------------------------------------------------------------------------


@pytest.mark.regression
@pytest.mark.unit
class TestC4BoundedConcurrency:
    async def test_concurrent_cascor_calls_never_exceed_the_bound(self):
        """C4: the gate holds concurrency at or below its limit under a burst.

        Bare offload was measured at 20/20 executor occupancy turning 3 upstream requests
        into 42. The bound must also sit below the cascor client's ``pool_maxsize`` of 10,
        which the constant's comment records and this asserts.
        """
        limit = BackendConstants.CASCOR_MAX_CONCURRENT_CALLS
        assert limit < 10, "the bound must stay under the cascor client's pool_maxsize"

        set_deadline(None)

        def slow():
            import time as _t

            _t.sleep(0.05)
            return "done"

        results = await asyncio.gather(*[offload(slow) for _ in range(limit * 5)])

        assert results == ["done"] * (limit * 5), "every admitted job must still complete"
        assert gate().peak_in_flight <= limit, f"gate admitted {gate().peak_in_flight} concurrent calls, bound is {limit}"

    async def test_the_bound_is_actually_reached(self):
        """Vacuity guard for C4: the burst must genuinely contend for the gate.

        If the jobs finished so fast that only one ran at a time, the assertion above
        would hold over a gate that bounds nothing at all.
        """
        limit = BackendConstants.CASCOR_MAX_CONCURRENT_CALLS
        set_deadline(None)

        def slow():
            import time as _t

            _t.sleep(0.05)
            return "done"

        await asyncio.gather(*[offload(slow) for _ in range(limit * 5)])
        assert gate().peak_in_flight == limit, f"the burst never saturated the gate (peak={gate().peak_in_flight}); this proves nothing about the bound"

    async def test_a_declined_job_releases_its_slot(self):
        """A decline must not leak a permit, or the gate closes permanently.

        The raise happens inside the worker; if the semaphore were released only on the
        success path, a run of declines during an outage would strangle canopy exactly
        when it needs to keep answering.
        """
        set_deadline(-1.0)
        for _ in range(BackendConstants.CASCOR_MAX_CONCURRENT_CALLS * 3):
            with pytest.raises(CallerGoneAway):
                await offload(lambda: "issued")

        set_deadline(30.0)
        assert await offload(lambda: "issued") == "issued", "the gate leaked permits on the decline path"


# --------------------------------------------------------------------------------------
# Budget resolution
# --------------------------------------------------------------------------------------


@pytest.mark.regression
@pytest.mark.unit
class TestBudgetResolution:
    @staticmethod
    def _scope(path, headers=None):
        return {"type": "http", "path": path, "headers": headers or []}

    def test_table_routes_get_their_measured_budget(self):
        """The table is keyed on real dashboard timeouts, extracted by AST."""
        assert CallerBudgetMiddleware._resolve_budget(self._scope("/api/train/restart")) == 30.0
        assert CallerBudgetMiddleware._resolve_budget(self._scope("/api/state")) == 5.0

    def test_restart_is_not_collapsed_to_the_common_budget(self):
        """§5.5's refutation of a single global timeout, as an assertion.

        Seven real caller budgets span 1.0 s to 30 s. A single constant of 2 s would
        abandon every restart at 2 s of its 30 — so the table must keep them apart.
        """
        restart = CallerBudgetMiddleware._resolve_budget(self._scope("/api/train/restart"))
        workers = CallerBudgetMiddleware._resolve_budget(self._scope("/api/v1/workers/list"))
        assert restart > workers * 10, "the long and short budgets collapsed into one value"

    def test_unknown_route_gets_no_deadline(self):
        """Fail open: bounded, never declined."""
        assert CallerBudgetMiddleware._resolve_budget(self._scope("/api/something/new")) is None

    def test_declared_header_overrides_the_table(self):
        """A caller that knows its own budget corrects canopy's model of it."""
        scope = self._scope("/api/state", [(b"x-canopy-budget-seconds", b"12.5")])
        assert CallerBudgetMiddleware._resolve_budget(scope) == 12.5

    def test_declared_budget_is_clamped(self):
        """An absurd declared budget is a client bug, not licence to pin a slot open."""
        huge = self._scope("/api/state", [(b"x-canopy-budget-seconds", b"99999")])
        assert CallerBudgetMiddleware._resolve_budget(huge) == BackendConstants.CALLER_BUDGET_MAX_SECONDS
        tiny = self._scope("/api/state", [(b"x-canopy-budget-seconds", b"0.001")])
        assert CallerBudgetMiddleware._resolve_budget(tiny) == BackendConstants.CALLER_BUDGET_MIN_SECONDS

    def test_malformed_header_falls_back_to_the_table(self):
        """A typo must not disable the route's known budget, nor reject the request."""
        scope = self._scope("/api/state", [(b"x-canopy-budget-seconds", b"soon-ish")])
        assert CallerBudgetMiddleware._resolve_budget(scope) == 5.0

    def test_prefix_match_covers_templated_routes(self):
        """``/api/state/<anything>`` inherits ``/api/state``'s budget."""
        assert CallerBudgetMiddleware._resolve_budget(self._scope("/api/state/extra")) == 5.0


@pytest.mark.regression
@pytest.mark.unit
class TestDeadlinePropagation:
    async def test_the_deadline_reaches_the_worker_thread(self):
        """The ContextVar must survive ``asyncio.to_thread``'s context copy.

        This is the assumption the whole slice rests on: the handler sets a deadline and
        a *different thread* reads it. If context copying ever stopped applying, every
        job would look unbounded and C10 would silently do nothing — passing tests, no
        error, no decline.
        """
        seen = []

        def worker():
            from backend.admission import get_deadline

            seen.append(get_deadline())
            return "done"

        set_deadline(30.0)
        await offload(worker)

        assert seen and seen[0] is not None, "the deadline did not reach the worker thread"
