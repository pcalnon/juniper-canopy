#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_x7_loop_responsiveness.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-09-04
# Last Modified: 2026-09-04
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   X7 slice 1a -- T-A2/T-A3/T-A4: the loop stays answerable
#                while an upstream is slow, and the shared client session
#                survives concurrent worker threads.
#####################################################################
"""X7 behavioural tests: T-A2 (responsiveness), T-A3 (its vacuity guards), T-A4 (session).

The gate next door (``test_x7_off_loop_discipline.py``) is structural -- it proves no
``async def`` handler *contains* a blocking call. These three prove the property that
structure is supposed to buy: **while an upstream is slow, canopy still answers**.

Both matter, and neither substitutes for the other. A structural gate cannot see a new
blocking path reached some way it does not model; a behavioural test cannot enumerate
call sites. X7 is a recurrence of SEC-F20 precisely because the first fix shipped a
comment instead of either one.

**T-A3 is not decoration.** Revision 3 of the design shipped a T-A2 whose driver route
the control could outrun, so the responsiveness assertion passed while its own guard was
violated -- the measurement was well-formed and about nothing. Every guard below exists
to make one specific way of measuring nothing impossible:

* the probe sample is non-empty -- otherwise ``max()`` over zero probes proves nothing;
* every driver really waited the stub's bound -- otherwise the "slow upstream" was not slow;
* the driver route really reached the backend -- counted at the stub, not assumed;
* and the harness is **proved able to detect blocking at all**, by running the identical
  measurement against a deliberately un-offloaded control app and requiring that it FAIL
  the deadline. A responsiveness test that cannot fail is the vacuous check this arc has
  now measured five times.

**Why the stub is bounded.** ``asyncio.to_thread`` exposes no shutdown seam, and an
unbounded stub thread blocked ``asyncio.run`` finalisation past 40 s under pytest during
the design work. The stub therefore *returns*, and the discriminating quantity is
**latency**, never completion.

**Why these are not marked ``slow``** despite exceeding the 1 s threshold in that
marker's definition: the coverage gate runs ``-m "not slow"`` over ``tests/unit/`` and
``tests/regression/`` only, so marking them would remove the one behavioural check X7
has. Bound total runtime is ~5 s.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest
from fastapi import FastAPI

import main

# The upstream stall the stub simulates. 2.0 s is canopy's own "normal lane" budget
# (canopy_constants.py:373-374), so a probe that survives it survives the budget.
STUB_BLOCK_SECONDS = 2.0

# The dashboard's fast lane is 1.0 s; health must clear it with room to spare.
HEALTH_DEADLINE_SECONDS = 0.5

DRIVERS = 3
PROBES = 10

# Reaches ``backend.get_status()`` -- one of the 52 sites this slice offloaded.
DRIVER_ROUTE = "/api/status"
# Pure async, touches no backend. If this stalls, the loop itself stalled.
PROBE_ROUTE = "/v1/health/live"


class _SlowBackend:
    """A backend whose every call blocks for a bounded interval, counting itself."""

    backend_type = "service"
    execution = "live"

    def __init__(self) -> None:
        self.calls = 0
        self._lock = threading.Lock()

    def get_status(self) -> dict:
        with self._lock:
            self.calls += 1
        time.sleep(STUB_BLOCK_SECONDS)
        return {"fsm_status": "idle", "phase": "idle"}


async def _timed(client: httpx.AsyncClient, route: str, started: float) -> tuple[float, int]:
    """Latency measured from ``started`` -- the moment the request was *issued*.

    Timing from inside the coroutine would measure only its own execution and miss the
    thing under test: how long the request sat behind a blocked loop before it ever ran.
    """
    response = await client.get(route)
    return time.perf_counter() - started, response.status_code


async def _measure(app, driver_route: str, drivers: int) -> tuple[list, list]:
    """Issue ``drivers`` slow requests and ``PROBES`` health probes, all at once.

    Task creation order is load-bearing: the drivers are created first, so they reach
    their upstream call before any probe runs. When the driver blocks the loop, the
    probes cannot start -- and because every probe's clock starts at issue time, that
    wait lands in the measurement instead of vanishing from it.
    """
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://x7.test") as client:
        issued = time.perf_counter()
        driver_tasks = [asyncio.create_task(_timed(client, driver_route, issued)) for _ in range(drivers)]
        probe_tasks = [asyncio.create_task(_timed(client, PROBE_ROUTE, issued)) for _ in range(PROBES)]
        driver_results = await asyncio.gather(*driver_tasks)
        probe_results = await asyncio.gather(*probe_tasks)
    return probe_results, driver_results


def _control_app(stub: _SlowBackend) -> FastAPI:
    """A miniature canopy whose driver route is deliberately **not** offloaded.

    This is the sensitivity control. It is the pre-fix shape of every route this slice
    changed, and the measurement must fail against it -- if it does not, the measurement
    cannot detect blocking and its success against the real app means nothing.
    """
    app = FastAPI()

    @app.get("/blocking")
    async def blocking():  # noqa: ANN202 - test fixture route
        return stub.get_status()

    @app.get(PROBE_ROUTE)
    async def live():  # noqa: ANN202 - test fixture route
        return {"status": "alive"}

    return app


@pytest.mark.regression
@pytest.mark.unit
class TestLoopStaysAnswerable:
    """T-A2 and its T-A3 guards."""

    async def test_health_stays_fast_while_upstream_is_slow(self, monkeypatch):
        """T-A2: /v1/health/live answers in <500 ms under 3 concurrent slow requests.

        Pre-fix this measured 5.813 s: the first driver's synchronous ``get_status()``
        held the only worker's event loop, so the probe -- which touches nothing --
        could not be served until the upstream returned.
        """
        stub = _SlowBackend()
        monkeypatch.setattr(main, "backend", stub)

        probes, drivers = await _measure(main.app, DRIVER_ROUTE, DRIVERS)

        # --- T-A3 guard 1: the sample exists. ---
        assert len(probes) == PROBES, "no probe sample -- max() over nothing proves nothing"
        assert all(status == 200 for _latency, status in probes), "probes must succeed to be timed"

        # --- T-A3 guard 2: the upstream really was slow. ---
        assert len(drivers) == DRIVERS
        for latency, status in drivers:
            assert status == 200
            assert latency >= STUB_BLOCK_SECONDS * 0.9, f"driver returned in {latency:.3f}s -- the stub never blocked, so nothing was under test"

        # --- T-A3 guard 3: the driver route really reached the backend. ---
        assert stub.calls == DRIVERS, f"stub saw {stub.calls} calls for {DRIVERS} drivers -- {DRIVER_ROUTE} does not reach the blocking call"

        # --- T-A2 itself. ---
        worst = max(latency for latency, _status in probes)
        assert worst < HEALTH_DEADLINE_SECONDS, f"{PROBE_ROUTE} took {worst:.3f}s while an upstream was slow -- the loop is still being blocked"

    async def test_the_measurement_can_detect_blocking(self):
        """T-A3 guard 4: the same harness FAILS against an un-offloaded route.

        One driver is enough here, and that is the finding rather than a shortcut: the
        design measured that a single request to a single un-offloaded handler
        reinstates the full outage. If this test ever passes the deadline, the harness
        has stopped being able to see the defect and the test above is worthless.
        """
        stub = _SlowBackend()

        probes, drivers = await _measure(_control_app(stub), "/blocking", drivers=1)

        assert stub.calls == 1, "the control route did not reach the stub"
        assert drivers[0][0] >= STUB_BLOCK_SECONDS * 0.9

        worst = max(latency for latency, _status in probes)
        assert worst >= STUB_BLOCK_SECONDS * 0.8, f"the control's probes cleared in {worst:.3f}s -- an inline blocking call went undetected, so this harness cannot measure X7"


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
