#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_x7_client_budget.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-09-04
# Last Modified: 2026-09-04
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   X7 slice 1b -- the cascor HTTP client's per-call budget is
#                bounded explicitly instead of inherited from the library
#                defaults (timeout=30, retries=3).
#####################################################################
"""Regression tests for the X7 slice-1b client budget.

X7 is juniper-canopy ceasing to answer HTTP -- ``/v1/health`` included -- whenever
juniper-cascor is unreachable, because synchronous retrying ``requests`` I/O runs inside
``async def`` route handlers on a single-worker uvicorn and blocks the event loop.

Slice 1b bounds the cost of each such call. Two properties are pinned here, both of which
failed before the fix:

* **T-B1** -- a call against a refusing port costs milliseconds, not seconds. The library
  default ``retries=3`` spends ``0 + 1.0 + 2.0`` seconds of urllib3 backoff **sleep** on the
  calling thread; measured 3.005 s before, 0.001 s after.
* **T-B2** -- a retryable status is attempted **once**. The installed client's
  ``RETRY_ALLOWED_METHODS`` includes POST and DELETE, so a retried request was measured
  reaching the server 4 times -- a duplicate-request hazard for ``POST /v1/training/start``
  independent of the outage.

Neither test needs canopy's app, an event loop, or a live cascor. T-B2 uses a local
counting stub that answers 503 (which is in the client's retry status list), so it is
deterministic and does not wait on any timeout.
"""

from __future__ import annotations

import http.server
import threading
import time

import pytest

from backend.cascor_service_adapter import CascorServiceAdapter
from canopy_constants import BackendConstants

# A port that nothing listens on: connect() fails immediately with ECONNREFUSED, so the
# whole cost of the call is retry backoff. That makes the timing assertion below a direct
# measurement of the retry policy rather than of network latency.
_CLOSED_PORT_URL = "http://127.0.0.1:9"

# Generous relative to the post-fix measurement (0.001 s) and far below the pre-fix one
# (3.005 s), so the assertion discriminates the policy without being timing-fragile.
_REFUSED_CALL_BUDGET_SECONDS = 0.5


class _CountingHandler(http.server.BaseHTTPRequestHandler):
    """Answers 503 to everything and counts how many attempts arrived."""

    attempts = 0

    def do_GET(self):  # noqa: N802 - BaseHTTPRequestHandler's required name
        type(self).attempts += 1
        self.send_response(503)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *_args):
        """Silence the default stderr access log."""


@pytest.fixture(name="counting_stub")
def _counting_stub():
    """A local HTTP server that answers 503 and counts attempts."""
    _CountingHandler.attempts = 0
    server = http.server.HTTPServer(("127.0.0.1", 0), _CountingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, _CountingHandler
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_client_budget_is_explicit_not_inherited():
    """The adapter passes an explicit budget rather than inheriting library defaults.

    Guards the specific regression: the defaults are what X7 was measured under, so a
    future refactor that drops the keywords silently restores the 123 s worst case.
    """
    adapter = CascorServiceAdapter(service_url=_CLOSED_PORT_URL)

    assert BackendConstants.CASCOR_CLIENT_RETRIES == 0
    assert adapter._client.timeout == BackendConstants.CASCOR_CLIENT_TIMEOUT_SECONDS


def test_refused_call_costs_milliseconds_not_seconds():
    """T-B1: a refused connection must not spend seconds of retry backoff on the thread.

    Pre-fix this was 3.005 s per call, essentially all of it ``sleep`` -- which is what
    made the polled read path saturate canopy's event loop.
    """
    adapter = CascorServiceAdapter(service_url=_CLOSED_PORT_URL)

    started = time.perf_counter()
    adapter.get_training_status()
    elapsed = time.perf_counter() - started

    assert elapsed < _REFUSED_CALL_BUDGET_SECONDS, f"refused call took {elapsed:.3f}s; retry backoff appears to be back"


def test_retryable_status_is_attempted_once(counting_stub):
    """T-B2: a 503 is attempted once, not four times.

    503 is in the client's retry status list, and its ``RETRY_ALLOWED_METHODS`` includes
    non-idempotent verbs, so the pre-fix policy turned one client call into four server
    requests -- a duplicate-request hazard for training starts, separate from the outage.
    """
    server, handler = counting_stub
    host, port = server.server_address
    adapter = CascorServiceAdapter(service_url=f"http://{host}:{port}")

    adapter.get_training_status()

    assert handler.attempts == 1, f"expected a single upstream attempt, saw {handler.attempts}"
