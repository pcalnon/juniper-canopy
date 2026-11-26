#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_x7_loop_responsiveness.py
# Author:        Paul Calnon
# Version:       0.1.1
# Date:          2026-09-04
# Last Modified: 2026-11-26
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   X7 slice 1a -- T-A2/T-A3/T-A4: the loop stays answerable
#                while an upstream is slow, and the shared client session
#                survives concurrent worker threads.
#####################################################################
"""X7 behavioural tests: T-A2 (responsiveness), T-A3 (its vacuity guards), T-A4 (session).

The gate next door (``test_x7_off_loop_discipline.py``) is structural -- it proves no
``async def`` handler *contains* a blocking call. These prove the property that
structure is supposed to buy: **while an upstream is slow, canopy still answers**.

Both matter, and neither substitutes for the other. A structural gate cannot see a new
blocking path reached some way it does not model; a behavioural test cannot enumerate
call sites. X7 is a recurrence of SEC-F20 precisely because the first fix shipped a
comment instead of either one.

**How T-A2 observes it: where the slow call runs, and what the loop does while it is
held.** The stub backend's ``get_status`` records the thread it runs on, then holds -- it
does not return -- until a coroutine on the event loop releases it. That coroutine waits
until the call is in flight, sends ``PROBES`` health probes through the real app, and
releases the call only once every probe has been answered. Offloaded, the call runs on a
worker thread, the loop answers the probes while it is held, and then releases it. Inline,
the call runs on the loop thread itself: no probe can be answered and nothing can release
it, so it gives up after ``HOLD_SECONDS``. The verdict rests on WHERE the call ran and on
WHETHER the loop answered while it was held, not on how fast anything ran: a stall of the
whole process only delays the release, and fails the test only if it outlasts ``HOLD_SECONDS``.

**Why not a latency deadline.** T-A2 used to time the probes and fail when the slowest
reached 1.0 s. A latency counts every moment the loop thread did not run, whatever stopped
it, and in the unit lane a full garbage collection of the session's heap stops every thread
of the process for most of a second. Stalls of that size failed T-A2 in five CI jobs
between 2026-11-09 and 2026-11-26 (1.031-1.182 s, on Python 3.12, 3.13 and 3.14) with
``/api/status`` correctly offloaded. What the hold does not bound is how long anything else
holds the loop: a bounded on-loop stall shorter than ``HOLD_SECONDS`` beside a correctly
offloaded call (a ``time.sleep`` in a handler or a middleware, say) passes it, as it passes
any test that cannot tell it from a stalled process. The structural gate next door does not
refuse such a stall either: it refuses un-offloaded network calls in ``main.py``'s handlers,
and a ``time.sleep`` is not one.

**T-A3 is not decoration.** Revision 3 of the design shipped a T-A2 whose driver route
the control could outrun, so the responsiveness assertion passed while its own guard was
violated -- the measurement was well-formed and about nothing. Every guard below exists
to make one specific way of measuring nothing impossible:

* every driver really reached the backend -- counted at the stub, not assumed -- and
  answered with what the stub returned, so it waited for the slow call;
* the probe sample is complete, every probe succeeded, and every one was answered while
  the slow call was still held -- otherwise nothing was answered beside it;
* and the harness is **proved able to detect blocking at all**, by running the identical
  measurement against a deliberately un-offloaded control route, and against one whose
  loop waits synchronously for a worker's result, and requiring that it catch both. A
  responsiveness test that cannot fail is the vacuous check this arc has now measured
  five times.

**Why the stub is bounded.** ``asyncio.to_thread`` exposes no shutdown seam, and an
unbounded stub thread blocked ``asyncio.run`` finalisation past 40 s under pytest during
the design work. The held call therefore always returns: released by the loop, or after
``HOLD_SECONDS``.

**Why these are not marked ``slow``**: the coverage gate runs ``-m "not slow"`` over
``tests/unit/``, ``tests/regression/``, ``tests/contract/`` and ``tests/performance/``, so
marking them would take them out of ``ci.yml``'s unit lane. A passing run of the file
takes about a second; ``HOLD_SECONDS`` is only ever waited out by a test that is about to
fail.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import contextlib
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest
from fastapi import FastAPI

import main

# How long the slow upstream call holds, waiting for the loop to release it. Releasing takes
# the loop the probes' round trips and one callback, so this bounds a loop that cannot run at
# all, not a slow one: offloaded, the call is released as soon as the loop has answered the
# probes (the longest stall this test met in CI from 2026-11-01 to 2026-11-26 was 1.182 s);
# inline, it is never released.
# The calls of one stub share one deadline, counted from the first call's entry, so a run
# whose calls are all inline waits it out once. Only a test that is about to fail waits it out.
HOLD_SECONDS = 10.0
# A control's call cannot be released however long it holds -- the loop thread is inside it,
# or blocked waiting for it -- so a short hold proves the point and keeps the suite fast.
CONTROL_HOLD_SECONDS = 0.2

DRIVERS = 3
PROBES = 10

# Reaches ``backend.get_status()`` -- one of the 52 sites this slice offloaded.
DRIVER_ROUTE = "/api/status"
# Pure async, touches no backend. If this stalls, the loop itself stalled.
PROBE_ROUTE = "/v1/health/live"

# What the stub's ``get_status`` returns: a driver that answers with it waited for the call.
STUB_STATUS = {"fsm_status": "idle", "phase": "idle"}


class _SlowBackend:
    """A backend whose ``get_status`` records WHERE it runs and holds until the event loop releases it.

    Build it inside the test coroutine: it captures the running loop and that loop's thread.
    """

    backend_type = "service"
    execution = "live"

    def __init__(self, hold_seconds: float = HOLD_SECONDS) -> None:
        self.hold_seconds = hold_seconds
        self.calls = 0
        self.ran_on_loop_thread: list[bool] = []
        self.released_by_loop: list[bool] = []
        self.entered = asyncio.Event()
        self._in_flight = 0
        self._deadline: float | None = None
        self._lock = threading.Lock()
        self._loop = asyncio.get_running_loop()
        self._loop_thread = threading.get_ident()
        self._release = threading.Event()

    def get_status(self) -> dict:
        with self._lock:
            self.calls += 1
            self._in_flight += 1
            self.ran_on_loop_thread.append(threading.get_ident() == self._loop_thread)
            if self._deadline is None:
                self._deadline = time.monotonic() + self.hold_seconds
            remaining = self._deadline - time.monotonic()
        # Safe from any thread; called from the loop thread it only queues the callback.
        self._loop.call_soon_threadsafe(self.entered.set)
        released = self._release.wait(timeout=max(remaining, 0.0))
        with self._lock:
            self._in_flight -= 1
            self.released_by_loop.append(released)
        return dict(STUB_STATUS)

    def in_flight(self) -> int:
        """How many calls are being held right now."""
        with self._lock:
            return self._in_flight

    def release(self) -> None:
        self._release.set()


async def _probe_while_held(client: httpx.AsyncClient, stub: _SlowBackend) -> list[tuple[int, int]]:
    """Once a slow call is in flight, send every probe; release the call only after all are answered.

    Returns, per probe, its status code and how many slow calls were still held when its
    answer arrived.
    """

    async def probe() -> tuple[int, int]:
        response = await client.get(PROBE_ROUTE)
        return response.status_code, stub.in_flight()

    try:
        await stub.entered.wait()
        return await asyncio.gather(*(probe() for _ in range(PROBES)))
    finally:
        stub.release()


async def _measure(app, driver_route: str, stub: _SlowBackend, drivers: int) -> tuple[list, list]:
    """Issue ``drivers`` slow requests, and probe health while their upstream call is held.

    The prober waits, on the loop, until the stub reports a call in flight, so every probe
    is sent while the slow call is held -- by construction, not by task order. It releases
    the call once its probes are answered, and the drivers then return. Whatever happens,
    the call is released before this returns, so no worker thread outlives the measurement.
    """
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://x7.test") as client:
        driver_tasks = [asyncio.create_task(client.get(driver_route)) for _ in range(drivers)]
        prober = asyncio.create_task(_probe_while_held(client, stub))
        try:
            responses = await asyncio.gather(*driver_tasks)
            probes: list = []
            if stub.entered.is_set():
                probes = await prober
            else:
                # No driver reached the stub, so no probe was sent; the guards say so.
                prober.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await prober
        finally:
            stub.release()
    return probes, responses


def _control_app(stub: _SlowBackend) -> FastAPI:
    """A miniature canopy whose driver routes are deliberately **not** offloaded.

    This is the sensitivity control. Its two routes are the two shapes of a blocking call on
    the loop: the call made inline (the pre-fix shape of every route this slice changed),
    and the call made on a worker thread while the loop waits synchronously for its result.
    The measurement must catch both -- if it does not, it cannot detect blocking and its
    success against the real app means nothing.
    """
    app = FastAPI()

    @app.get("/blocking")
    async def blocking():  # noqa: ANN202 - test fixture route
        return stub.get_status()

    @app.get("/blocking-on-worker")
    async def blocking_on_worker():  # noqa: ANN202 - test fixture route
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            # Deliberately blocks the loop thread on the worker's result.
            return pool.submit(stub.get_status).result()

    @app.get(PROBE_ROUTE)
    async def live():  # noqa: ANN202 - test fixture route
        return {"status": "alive"}

    return app


@pytest.mark.regression
@pytest.mark.unit
class TestLoopStaysAnswerable:
    """T-A2 and its T-A3 guards."""

    async def test_health_stays_fast_while_upstream_is_slow(self, monkeypatch):
        """T-A2: /v1/health/live answers while 3 concurrent slow requests hold their upstream call.

        Pre-fix this measured 5.813 s: the first driver's synchronous ``get_status()`` held
        the only worker's event loop, so the probe -- which touches nothing -- could not be
        served until the upstream returned. Here that call would be seen on the loop thread,
        no probe could be answered while it was held, and nothing could release it.
        """
        stub = _SlowBackend()
        monkeypatch.setattr(main, "backend", stub)

        probes, drivers = await _measure(main.app, DRIVER_ROUTE, stub, DRIVERS)

        # --- T-A3 guard: the driver route really reached the backend. ---
        assert stub.calls == DRIVERS, f"stub saw {stub.calls} calls for {DRIVERS} drivers -- {DRIVER_ROUTE} does not reach the blocking call"

        # --- T-A2 itself: where the slow call ran, and whether the loop ran while it was held. ---
        assert not any(stub.ran_on_loop_thread), f"{DRIVER_ROUTE} ran get_status() on the event-loop thread -- the upstream call is back on the loop"
        assert all(stub.released_by_loop), f"the loop did not answer the probes and release get_status() while it was in flight (unreleased after {HOLD_SECONDS}s) -- something held the loop, or {PROBE_ROUTE} waited on the slow call"

        # --- T-A3 guard: the probes were answered, all of them, while the slow call was held. ---
        assert len(probes) == PROBES, "no probe sample -- nothing was answered beside the slow call"
        assert all(status == 200 for status, _held in probes), "probes must succeed to count"
        assert all(held >= 1 for _status, held in probes), f"a probe was answered after every slow call had returned -- {PROBE_ROUTE} was not answered while the upstream was slow"

        # --- T-A3 guard: every driver waited for the slow call and answered with its result. ---
        assert len(drivers) == DRIVERS
        for response in drivers:
            assert response.status_code == 200
            assert response.json() == STUB_STATUS, f"{DRIVER_ROUTE} answered {response.json()!r}, not the stub's status -- it did not wait for the slow call"

    async def test_the_measurement_can_detect_blocking(self):
        """T-A3 guard: the same harness MUST catch an un-offloaded route.

        One driver is enough here, and that is the finding rather than a shortcut: the
        design measured that a single request to a single un-offloaded handler
        reinstates the full outage. If this test ever sees the call off the loop thread,
        released, or a probe answered while it was held, the harness has stopped being
        able to see the defect and the test above is worthless.
        """
        stub = _SlowBackend(hold_seconds=CONTROL_HOLD_SECONDS)

        probes, drivers = await _measure(_control_app(stub), "/blocking", stub, drivers=1)

        assert stub.calls == 1, "the control route did not reach the stub"
        assert drivers[0].status_code == 200
        assert stub.ran_on_loop_thread == [True], "an inline call was not seen on the event-loop thread -- this harness cannot see X7"
        assert stub.released_by_loop == [False], "an inline call was released while the loop was inside it -- this harness cannot see X7"
        assert len(probes) == PROBES
        assert not any(held for _status, held in probes), "a probe was answered while an inline call held the loop -- this harness cannot see X7"

    async def test_the_measurement_can_detect_a_loop_blocked_on_its_result(self):
        """T-A3 guard: the same harness MUST catch a loop that waits synchronously for a worker.

        The thread check alone passes an offloaded call whose result the loop then waits
        for synchronously; only the release check catches that shape. If this test ever
        sees the call released, or a probe answered while it was held, the test above can
        no longer see it.
        """
        stub = _SlowBackend(hold_seconds=CONTROL_HOLD_SECONDS)

        probes, drivers = await _measure(_control_app(stub), "/blocking-on-worker", stub, drivers=1)

        assert stub.calls == 1, "the control route did not reach the stub"
        assert drivers[0].status_code == 200
        assert stub.ran_on_loop_thread == [False], "a call made on a worker thread was seen on the event-loop thread -- this harness cannot see X7"
        assert stub.released_by_loop == [False], "a call was released while the loop waited synchronously for its result -- this harness cannot see a loop blocked on an offloaded call"
        assert len(probes) == PROBES
        assert not any(held for _status, held in probes), "a probe was answered while the loop was blocked on the call -- this harness cannot see X7"


class _EchoHandler(BaseHTTPRequestHandler):
    """Answers every GET with the path it received, so a swapped response is visible."""

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        body = json.dumps({"path": self.path}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args) -> None:
        """Silence the default stderr access log."""


@pytest.mark.regression
@pytest.mark.unit
class TestSharedSessionUnderConcurrency:
    """T-A4: the client's shared ``requests.Session`` under real worker threads."""

    def test_shared_session_survives_concurrent_threads(self):
        """T-A4 -- and a correction to constraint C5, on evidence.

        C5 reads "the shared ``requests.Session`` must not be used concurrently from
        multiple threads", and slice 1a removes the accidental protection the blocked
        loop provided (concurrency was pinned at 1). The design's remedy was a
        ``threading.local()`` session at the client boundary.

        Reading the client, that remedy addresses a hazard this client does not have.
        ``JuniperCascorClient`` mutates session state **only in __init__** -- two
        ``mount()`` calls and one API-key header (client.py:142-183) -- and ``_request``
        passes method, url, json, params and timeout as arguments, touching nothing on
        the session (client.py:530-545). What remains shared is the ``HTTPAdapter``'s
        urllib3 connection pool, which is thread-safe by construction and is the reason
        ``pool_maxsize`` exists. A thread-local session would instead give every worker
        its own pool, discarding keep-alive across the executor's threads.

        So the safety does not rest on a lock; it rests on the client never mutating
        session state per request. That is an invariant no test pinned, which is what
        made C5's warning reasonable. This test pins it, both ways: empirically, that
        concurrent threads get their own answers, and structurally, that the session is
        unchanged afterwards. If someone adds per-request session mutation upstream,
        this fails and C5's original remedy becomes the right one.
        """
        from juniper_cascor_client import JuniperCascorClient

        server = ThreadingHTTPServer(("127.0.0.1", 0), _EchoHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_address[1]
            client = JuniperCascorClient(base_url=f"http://127.0.0.1:{port}", timeout=5.0, retries=0)

            headers_before = dict(client.session.headers)
            sessions_seen: set[int] = set()
            results: dict[str, str] = {}
            errors: list[Exception] = []
            lock = threading.Lock()

            def worker(index: int) -> None:
                try:
                    for call in range(4):
                        tag = f"/echo-{index}-{call}"
                        # ``_get`` is the only seam that takes a caller-chosen path, and a
                        # unique path per request is what makes a swapped response visible
                        # at all. A public method would send every thread to one URL, where
                        # cross-talk and correctness are indistinguishable.
                        body = client._get(tag)
                        with lock:
                            sessions_seen.add(id(client.session))
                            results[tag] = body["path"]
                except Exception as exc:  # pragma: no cover - only on a real failure
                    with lock:
                        errors.append(exc)

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=30)

            assert not errors, f"concurrent use of the shared session raised: {errors[:3]}"
            assert len(results) == 32, f"expected 32 completed calls, got {len(results)}"
            for tag, echoed in results.items():
                assert echoed.endswith(tag), f"response cross-talk: {tag} received {echoed!r}"

            # Vacuity guard: one Session for every thread, or the shared case was never tested.
            assert len(sessions_seen) == 1, "threads did not share one Session -- this proves nothing about C5"

            # The invariant the safety actually rests on.
            assert dict(client.session.headers) == headers_before, "the client mutated session headers per request -- C5's thread-local remedy is now required"
        finally:
            server.shutdown()
            server.server_close()
