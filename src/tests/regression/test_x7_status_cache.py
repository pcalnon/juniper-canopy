#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_x7_status_cache.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-09-04
# Last Modified: 2026-09-04
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   X7 slice 1c -- T-C1/T-C2/T-C3/T-C4: the status cache
#                classifier, the PR #340 regression, breaker isolation,
#                and the staleness contract.
#####################################################################
"""X7 slice 1c tests.

The four the design names, plus guards for the two failure modes the design implies but
does not enumerate: a refresher that dies, and a cache that fabricates a fresh negative.

**T-C1 is table-driven on purpose.** The coverage gate reads ``tests/unit/`` and
``tests/regression/`` with ``-m "not slow"`` and holds each new module to ≥90%; a census
over one table covers the classifier's branches without twenty near-identical tests.

**Every case in the T-C1 table is a shape that was actually observed or is actually
reachable**, not a fuzz corpus. The half-dead 200 and ``error: None`` rows are the two
that a plausible-looking classifier gets wrong in opposite directions, which is why an
earlier draft keyed on ``is_training`` and misclassified 7 of 20 healthy shapes.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from juniper_cascor_client import JuniperCascorClientError

from backend.circuit_breaker import CircuitState
from backend.status_cache import (
    StatusCache,
    StatusClass,
    classify,
)
from frontend.dashboard_manager import DashboardManager

# --------------------------------------------------------------------------------------
# T-C1 -- the classifier census
# --------------------------------------------------------------------------------------

# (label, raw, expected class). The design's §5.3 table, made executable.
CLASSIFIER_CASES = [
    # --- OK: a cascor-shaped payload with no error ---
    ("nested state_machine", {"state_machine": {"status": "Started"}}, StatusClass.OK),
    ("nested training_active", {"training_active": True}, StatusClass.OK),
    ("idle but healthy", {"state_machine": {"status": "Stopped"}, "training_active": False}, StatusClass.OK),
    # ``error: None`` is present-but-falsy. A truthiness check gets this right and an
    # ``"error" in raw`` check gets it wrong -- the backend really is healthy.
    ("error present but None", {"training_active": True, "error": None}, StatusClass.OK),
    # --- UNREACHABLE: reached the point of having an answer, and the answer is bad ---
    ("adapter client error", {"is_training": False, "error": "Failed to get training status: timeout"}, StatusClass.UNREACHABLE),
    ("empty error string is falsy but shape is wrong", {"error": ""}, StatusClass.UNREACHABLE),
    # THE case this slice exists for: a 200 with a dict body that is not a cascor status.
    # No error to trip the PR #340 branch, and not nested, so a payload-reading UI shows
    # "Stopped" -- a healthy-looking lie.
    ("half-dead 200", {"ok": True, "service": "something-else"}, StatusClass.UNREACHABLE),
    ("empty dict", {}, StatusClass.UNREACHABLE),
    # Non-dicts. ``"error" in None`` raises TypeError; an exception here kills the
    # refresher and freezes the cache green, so these are load-bearing, not padding.
    ("None", None, StatusClass.UNREACHABLE),
    ("list", [], StatusClass.UNREACHABLE),
    ("bare string", "down", StatusClass.UNREACHABLE),
    # --- INDETERMINATE: the call was SKIPPED, so nothing was observed ---
    ("circuit open", {"is_training": False, "error": "circuit open"}, StatusClass.INDETERMINATE),
    ("circuit open, different casing", {"error": "Circuit Open"}, StatusClass.INDETERMINATE),
]


@pytest.mark.regression
@pytest.mark.unit
@pytest.mark.parametrize("label,raw,expected", CLASSIFIER_CASES, ids=[c[0] for c in CLASSIFIER_CASES])
def test_c1_classifier_census(label, raw, expected):
    """T-C1: every shape in the §5.3 table lands in its stated class."""
    assert classify(raw) is expected, f"{label}: {raw!r}"


@pytest.mark.regression
@pytest.mark.unit
def test_c1_census_covers_every_class():
    """Vacuity guard for T-C1: the table must exercise all three classes.

    A table that happened to contain only UNREACHABLE rows would pass every case above
    while proving nothing about the discrimination the slice depends on.
    """
    covered = {expected for _label, _raw, expected in CLASSIFIER_CASES}
    assert covered == set(StatusClass), f"table does not exercise every class: {covered}"


# --------------------------------------------------------------------------------------
# T-C2 -- the PR #340 regression guard
# --------------------------------------------------------------------------------------


@pytest.mark.regression
@pytest.mark.unit
class TestC2StatusBarRendersTheClass:
    """A half-dead 200 must render "Unreachable", never "Stopped"."""

    @pytest.fixture
    def dm(self):
        return DashboardManager({})

    @staticmethod
    def _resp(body):
        resp = MagicMock()
        resp.status_code = 200
        resp.ok = True
        resp.json.return_value = body
        return resp

    def _label(self, dm, body):
        with patch("frontend.dashboard_manager.requests.get", return_value=self._resp(body)):
            return dm._update_unified_status_bar_handler(n_intervals=1)[3]

    def test_half_dead_200_renders_unreachable(self, dm):
        """T-C2. The body carries no ``error``; only the cache's class saves it.

        Before 1c, ``/api/status`` handed this payload straight through: the PR #340
        branch keys on ``error``, finds none, and the elif chain below it renders
        "Stopped" from the default-False fields. An operator cannot tell that from a
        backend that is genuinely idle.
        """
        body = {"ok": True, "status_class": "unreachable", "stale": True, "age_seconds": None}
        assert self._label(dm, body) == "Unreachable"

    def test_the_guard_is_the_class_not_the_error(self, dm):
        """Vacuity guard for T-C2: the same body WITHOUT the class must render "Stopped".

        This is what makes the test above meaningful. If the payload alone were enough to
        get "Unreachable", T-C2 would pass whether or not the class was routed, and the
        defect it guards would be undetectable. Asserting the pre-fix behaviour pins that
        the class is doing the work.
        """
        body = {"ok": True}
        assert self._label(dm, body) == "Stopped"

    def test_indeterminate_is_not_reported_as_unreachable(self, dm):
        """An open breaker SKIPPED the call, so "Unreachable" would assert unseen evidence."""
        body = {"status_class": "indeterminate", "error": "circuit open", "stale": True}
        assert self._label(dm, body) == "Unknown"

    def test_ok_class_still_renders_the_payload(self, dm):
        """The class must not swallow the happy path."""
        body = {"status_class": "ok", "stale": False, "age_seconds": 0.2, "is_running": True, "phase": "output", "current_epoch": 3, "hidden_units": 1}
        assert self._label(dm, body) == "Running"

    def test_legacy_error_marker_still_renders_unreachable(self, dm):
        """Back-compat: demo/recurrence serve the raw result and carry no class."""
        body = {"is_training": False, "error": "circuit open"}
        assert self._label(dm, body) == "Unreachable"


# --------------------------------------------------------------------------------------
# T-C3 -- breaker isolation
# --------------------------------------------------------------------------------------


@pytest.mark.regression
@pytest.mark.unit
class TestC3DedicatedBreaker:
    """The refresher's breaker must not be tripped by unrelated adapter traffic."""

    @staticmethod
    def _adapter():
        from backend.cascor_service_adapter import CascorServiceAdapter

        # ``__new__`` skips __init__ and its client construction; both breakers are lazy
        # properties precisely so this works.
        adapter = CascorServiceAdapter.__new__(CascorServiceAdapter)
        adapter._client = MagicMock()
        return adapter

    def test_network_data_failures_do_not_open_the_status_breaker(self):
        """T-C3. Five failing ``get_network_data()`` calls open the SHARED breaker.

        Before the dedicated breaker, that also short-circuited ``get_training_status``,
        so the cache published INDETERMINATE for the full 60 s recovery timeout while
        cascor was answering status requests perfectly well. The status poll must be
        unaffected.
        """
        adapter = self._adapter()
        adapter._client.get_statistics.side_effect = JuniperCascorClientError("statistics down")
        adapter._client.get_training_status.return_value = {"state_machine": {"status": "Started"}}

        for _ in range(5):
            adapter.get_network_data()

        assert adapter._cb.state is CircuitState.OPEN, "precondition: the shared breaker must actually open"
        assert adapter._status_cb.state is CircuitState.CLOSED, "the status refresher's breaker was tripped by unrelated traffic"

        # And the refresher still gets a real answer, not the circuit-open fallback.
        raw = adapter.get_training_status_for_refresh()
        assert classify(raw) is StatusClass.OK

    def test_shared_path_would_have_been_short_circuited(self):
        """Vacuity guard for T-C3: prove the shared breaker really does gate the old path.

        Without this, the test above could pass because the shared breaker never opened,
        or because ``get_training_status`` does not consult it — neither of which would
        say anything about isolation.
        """
        adapter = self._adapter()
        adapter._client.get_statistics.side_effect = JuniperCascorClientError("statistics down")
        adapter._client.get_training_status.return_value = {"state_machine": {"status": "Started"}}

        for _ in range(5):
            adapter.get_network_data()

        assert classify(adapter.get_training_status()) is StatusClass.INDETERMINATE

    def test_status_failures_do_open_the_status_breaker(self):
        """The dedicated breaker must still be a breaker."""
        adapter = self._adapter()
        adapter._client.get_training_status.side_effect = JuniperCascorClientError("status down")
        for _ in range(5):
            adapter.get_training_status_for_refresh()
        assert adapter._status_cb.state is CircuitState.OPEN


# --------------------------------------------------------------------------------------
# T-C4 -- the staleness contract, and the two guards the design implies
# --------------------------------------------------------------------------------------


def _cache(raw_sequence, **kwargs):
    """A cache whose fetch walks ``raw_sequence``, repeating its last element."""
    box = {"i": 0}

    def fetch():
        i = min(box["i"], len(raw_sequence) - 1)
        box["i"] += 1
        value = raw_sequence[i]
        if isinstance(value, Exception):
            raise value
        return value

    return StatusCache(fetch_raw=fetch, normalize=lambda raw: {"is_training": bool(raw.get("training_active"))}, **kwargs)


@pytest.mark.regression
@pytest.mark.unit
class TestC4StalenessContract:
    async def test_non_ok_read_carries_stale_and_age(self):
        """T-C4: after an OK then a failure, the body is marked stale and dated."""
        cache = _cache([{"training_active": True}, {"error": "boom"}])

        assert await cache.refresh_once() is StatusClass.OK
        fresh = cache.for_status()
        assert fresh["stale"] is False
        assert fresh["status_class"] == "ok"
        assert fresh["age_seconds"] is not None and fresh["age_seconds"] >= 0

        assert await cache.refresh_once() is StatusClass.UNREACHABLE
        stale = cache.for_status()
        assert stale["stale"] is True, "a non-OK read must be marked stale (C9)"
        assert stale["age_seconds"] is not None, "a stale read must carry its age (C9)"
        assert stale["status_class"] == "unreachable"
        assert stale["error"], "every non-OK body carries a truthy error for the PR #340 branch"
        # The last-OK payload is still served -- that is the point of a cache -- but it is
        # labelled, so a reader cannot mistake it for current.
        assert stale["is_training"] is True

    async def test_never_ok_does_not_fabricate_a_fresh_negative(self):
        """C6: with no OK ever seen, the body must not claim ``is_training: False``.

        The adapter returns ``{"is_training": False, "error": …}`` rather than raising, so
        passing that through is how a cache invents "not training" during a live run whose
        status call merely failed. The class and the error are reported; the claim is not.
        """
        cache = _cache([{"is_training": False, "error": "connection refused"}])
        assert await cache.refresh_once() is StatusClass.UNREACHABLE

        body = cache.for_status()
        assert "is_training" not in body, "an unreachable backend does not license a training claim"
        assert body["status_class"] == "unreachable"
        assert body["stale"] is True
        assert body["age_seconds"] is None
        assert cache.training_active() is None

    async def test_a_dead_refresher_stops_reporting_ok(self):
        """A frozen cache must admit it, not keep serving its last green verdict.

        The whole machinery-fails-green class: if the task dies after one OK poll, every
        reader would go on being told the backend is healthy forever. ``current_class``
        therefore ages out on the last ATTEMPT, not the last success.
        """
        cache = _cache([{"training_active": True}], unknown_after=0.05)
        assert await cache.refresh_once() is StatusClass.OK
        assert cache.current_class() is StatusClass.OK

        await asyncio.sleep(0.1)  # nothing polls -- the task is "dead"

        assert cache.current_class() is StatusClass.INDETERMINATE
        assert cache.for_status()["stale"] is True
        assert cache.training_active() is None

    async def test_a_raising_fetch_does_not_kill_the_refresher(self):
        """A fetch that raises is an unreachable upstream, not a reason to stop polling."""
        cache = _cache([RuntimeError("kaboom"), {"training_active": True}])
        assert await cache.refresh_once() is StatusClass.UNREACHABLE
        assert await cache.refresh_once() is StatusClass.OK, "the cache must recover once the upstream does"

    async def test_ticks_do_not_overlap(self):
        """Single-flight is structural: the loop sleeps AFTER its fetch.

        Asserted by construction rather than by racing -- a slow fetch records its peak
        concurrency, and the loop must never show two in flight.
        """
        inflight = {"now": 0, "peak": 0}

        def slow_fetch():
            inflight["now"] += 1
            inflight["peak"] = max(inflight["peak"], inflight["now"])
            import time as _time

            _time.sleep(0.05)
            inflight["now"] -= 1
            return {"training_active": False}

        cache = StatusCache(fetch_raw=slow_fetch, normalize=lambda raw: {"is_training": False}, interval=0.001)
        await cache.start()
        await asyncio.sleep(0.3)
        await cache.stop()

        assert cache.ticks >= 2, f"the refresher must have ticked more than once (got {cache.ticks})"
        assert inflight["peak"] == 1, f"ticks overlapped (peak={inflight['peak']}) -- single-flight is broken"

    async def test_stop_is_prompt_and_idempotent(self):
        """SIGTERM must not wait on the poll loop, and a double stop must not raise."""
        cache = _cache([{"training_active": True}], interval=60.0)
        await cache.start()
        await asyncio.sleep(0.05)
        await cache.stop()
        await cache.stop()
        assert cache.ticks >= 1

    async def test_a_raising_verdict_sink_cannot_kill_the_refresher(self):
        """Observability must never be able to break the thing it observes."""

        def boom(_verdict):
            raise RuntimeError("prometheus is unhappy")

        cache = _cache([{"training_active": True}], on_verdict=boom)
        assert await cache.refresh_once() is StatusClass.OK
        assert cache.for_status()["status_class"] == "ok"
