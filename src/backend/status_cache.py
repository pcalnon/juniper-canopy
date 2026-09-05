#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       X7 slice 1c — the cascor status cache and its classifier
#
# Author:        Paul Calnon
# Version:       0.1.0
# File Name:     status_cache.py
# File Path:     JuniperCanopy/juniper_canopy/src/backend/
#
# Date Created:  2026-09-04
# Last Modified: 2026-09-04
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#     A single background task polls cascor's training status on a timer; read
#     handlers serve from its cache instead of each paying an upstream call.
#     Publishes a CLASS (ok / unreachable / indeterminate) alongside the payload,
#     so a consumer can tell "cascor says idle" from "we cannot reach cascor".
#
#####################################################################################################################################################################################################
# References:
#     - juniper-ml/notes/JUNIPER_2026-09-03_JUNIPER-CANOPY_X7-EVENT-LOOP-BLOCKING-REMEDIATION-DESIGN.md §5.3, §5.6
#
#####################################################################################################################################################################################################

"""The cascor status cache (X7 slice 1c).

**What this buys, given 1a already closed X7.** Slice 1a moved every blocking call
off the event loop, so canopy answers HTTP under a dead upstream. It did not reduce the
*number* of upstream calls, and it did not make an unreachable backend legible. This
module does both:

* **C2 — call rate independent of tabs and pollers.** One task polls on a timer; every
  read handler serves from its result. Adding a browser tab adds zero upstream calls.
* **C6 / C9 — an unknown backend is never presented as a fresh negative.** The adapter
  returns ``{"is_training": False, "error": …}`` rather than raising, so a naive cache
  would stamp "not training" ``FRESH`` during a live run whose status call merely failed.
  Every read carries ``stale`` and ``age_seconds``, and non-OK reads carry a class.

**Single-flight is structural, not enforced.** The loop awaits its fetch, then sleeps, so
a second tick cannot begin while one is in flight — there is no lock to get wrong and no
overlap to detect. It is also **self-limiting**: because the sleep follows the fetch, a
slow upstream lowers the poll rate on its own (a 30 s timeout yields a 1/31 Hz poll, not a
pile of 1 Hz calls), which is why no backoff is implemented. See OQ-X2 in the design;
backoff would trade a load problem this shape does not have for slower recovery detection,
and recovery detection is the thing the status bar exists to show.

**Why a class and not just a payload.** ``dashboard_manager`` renders "Unreachable" only
when it finds a truthy ``error`` key (the PR #340 branch, and the only working outage
indicator in the product). On a *half-dead 200* — a response that is a dict, carries no
error, and is not cascor-shaped — that branch does not fire and the status bar renders
**"Stopped"**, which is indistinguishable from a healthy idle backend. That is the exact
defect PR #340 was opened to fix, re-created by handing the UI a raw payload. So the cache
publishes what it *concluded*, and the UI renders the conclusion.
"""

from __future__ import annotations

import asyncio
import logging
import time
from enum import Enum
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger("juniper_canopy.backend.status_cache")


def _is_cascor_nested(raw: dict) -> bool:
    """Canopy's own nested-structure predicate, imported **lazily and deliberately**.

    ``cascor_service_adapter`` imports ``juniper_cascor_client`` unconditionally at module
    level, while ``backend/__init__`` imports the *adapter* only inside the service branch
    of ``create_backend``. That structure is load-bearing: demo mode runs without the
    cascor client installed at all, and CI relies on it -- ``conf/requirements_ci.txt``
    does not ship the client, so the UI sub-suite boots canopy in demo mode against an
    environment where importing it raises.

    A module-level import here would therefore make the client a hard **startup**
    dependency of demo mode. Measured: canopy exits 1 before serving a request, and the
    only symptom is the UI harness reporting "canopy exited early with code 1" -- every
    unit test still passes, because they run in an environment that has the client.

    Deferring it to call time costs a cached ``sys.modules`` lookup at 1 Hz and keeps the
    predicate shared rather than copied, which is what the design asks for: an earlier
    draft invented its own rule and misclassified 7 of 20 healthy shapes.
    """
    from backend.cascor_service_adapter import CascorServiceAdapter

    return bool(CascorServiceAdapter.is_cascor_nested(raw))


# Poll cadence. Derived, not chosen (design OQ-X1): the tightest consumer is the container
# healthcheck at a 15 s interval with a 5 s budget, and the dashboard's own fast lane is
# 1.0 s (canopy_constants.py). At 1 Hz the worst-case age a probe can observe is ~1 s — 6.7%
# of the tightest probe interval, and never older than the fast lane's own budget, so no
# consumer can be handed a value staler than the deadline it is working to.
REFRESH_INTERVAL_SECONDS = 1.0

# Beyond this, a served value stops being "current" for the fastest consumer. Set to the
# healthcheck's own budget: a value older than the probe's deadline cannot honestly be
# called fresh *to that probe*.
STALE_AFTER_SECONDS = 5.0

# Beyond this, the cache does not merely hold a stale value — it has no recent knowledge at
# all, and the most likely cause is that the refresher stopped ticking rather than that the
# upstream is slow (a failing poll still updates the clock, every second). Serving the last
# OK verdict past this point would be the frozen-green failure this codebase keeps meeting:
# the machinery dies, and the report still reads healthy. Chosen as the LONGEST probe
# interval (the image healthcheck's 30 s), so a cache that has missed a whole probe cycle
# admits it.
UNKNOWN_AFTER_SECONDS = 30.0

# The adapter's short-circuit marker. ``get_training_status`` returns this when the breaker
# is open, i.e. when the call was **skipped**.
CIRCUIT_OPEN_MARKER = "circuit open"


class StatusClass(str, Enum):
    """What the cache concluded about the backend on its last look.

    ``str`` mixin so the value serialises directly into a JSON response without a
    converter at every call site.
    """

    OK = "ok"
    UNREACHABLE = "unreachable"
    INDETERMINATE = "indeterminate"


def classify(raw: Any) -> StatusClass:
    """Classify one raw ``get_training_status()`` result.

    Pure and total — every input lands in exactly one class, including the ones that are
    not dicts. That matters more than it looks: ``"error" in None`` raises ``TypeError``,
    and an exception here would kill the refresher task and freeze the cache at whatever
    it last held, which fails silently and green.

    The predicate is canopy's own ``CascorServiceAdapter.is_cascor_nested`` rather than a
    new one. An earlier draft invented a rule keyed on ``is_training``, which appears
    **only on the failure path** — it misclassified 7 of 20 measured shapes, every one of
    them healthy, as UNREACHABLE. ``is_cascor_nested`` does *positive* detection of
    cascor's nested structure for exactly this reason and is already the production
    discriminator at ``service_backend.py:168``.

    ``INDETERMINATE`` for a circuit-open result is not a hedge. An open breaker means the
    call was **skipped**, so this tick made no observation of cascor at all — reporting
    UNREACHABLE would claim evidence that was never gathered, and reporting OK would be
    worse. The dedicated breaker (see :meth:`StatusCache`) is what keeps this class honest:
    without it, five failing ``get_network_data()`` calls would open the shared breaker and
    freeze this cache for 60 s *against a healthy upstream*.
    """
    if not isinstance(raw, dict):
        # Covers None, [], a bare string — anything the adapter or a fake might hand back.
        return StatusClass.UNREACHABLE

    error = raw.get("error")
    if error:
        if isinstance(error, str) and CIRCUIT_OPEN_MARKER in error.lower():
            return StatusClass.INDETERMINATE
        return StatusClass.UNREACHABLE

    # A truthy-error check alone is not enough. A half-dead 200 carries no error and is
    # still not a cascor status; without this it would classify OK and render "Stopped".
    if not _is_cascor_nested(raw):
        return StatusClass.UNREACHABLE

    return StatusClass.OK


class StatusCache:
    """Polls cascor's status on a timer; serves the last verdict to every reader.

    Args:
        fetch_raw: Returns cascor's raw training-status dict. **Synchronous** — it is run
            with :func:`asyncio.to_thread`, so it must not be a coroutine function.
        normalize: Maps a raw OK payload to canopy's ``StatusResult`` shape. Kept separate
            from ``fetch_raw`` because classification needs the *raw* response (the nested
            check) while readers need the *normalized* one.
        interval: Seconds between polls.
        on_verdict: Called with the class after every tick. Used to drive the Prometheus
            gauge. Failures here are logged and swallowed -- an observability sink must
            never be able to kill the refresher it observes.
    """

    def __init__(
        self,
        fetch_raw: Callable[[], Any],
        normalize: Callable[[Dict[str, Any]], Dict[str, Any]],
        interval: float = REFRESH_INTERVAL_SECONDS,
        stale_after: float = STALE_AFTER_SECONDS,
        unknown_after: float = UNKNOWN_AFTER_SECONDS,
        on_verdict: Optional[Callable[["StatusClass"], None]] = None,
    ) -> None:
        self._fetch_raw = fetch_raw
        self._normalize = normalize
        self._on_verdict = on_verdict
        self._interval = interval
        self._stale_after = stale_after
        self._unknown_after = unknown_after

        self._task: Optional[asyncio.Task] = None
        self._class: StatusClass = StatusClass.INDETERMINATE
        self._last_ok_payload: Optional[Dict[str, Any]] = None
        self._last_ok_at: Optional[float] = None
        self._last_attempt_at: Optional[float] = None
        self._last_error: Optional[str] = None
        self._ticks = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Begin polling. Idempotent — a second call while running is a no-op."""
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(self._run(), name="x7-status-refresher")
        logger.info("Status cache refresher started (interval=%.2fs)", self._interval)

    async def stop(self) -> None:
        """Cancel the refresher and wait for it to unwind."""
        task = self._task
        self._task = None
        if task is None or task.done():
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception:  # pragma: no cover — defensive; a dying task must not block shutdown
            logger.exception("Status cache refresher raised during shutdown")
        logger.info("Status cache refresher stopped")

    async def refresh_once(self) -> StatusClass:
        """Run exactly one poll. The loop body, exposed so tests need no timing."""
        raw: Any
        try:
            raw = await asyncio.to_thread(self._fetch_raw)
        except Exception as exc:
            # A raising fetch is an unreachable upstream, not a reason to stop polling.
            logger.warning("Status refresh raised: %s: %s", type(exc).__name__, exc)
            raw = {"is_training": False, "error": f"{type(exc).__name__}: {exc}"}

        verdict = classify(raw)
        now = time.monotonic()
        self._last_attempt_at = now
        self._ticks += 1
        self._class = verdict

        if verdict is StatusClass.OK:
            self._last_error = None
            try:
                self._last_ok_payload = dict(self._normalize(raw))
            except Exception:
                # Normalisation is canopy's own code; if it fails the response was OK but
                # unusable. Do NOT keep the previous payload and call it fresh.
                logger.exception("Status normalisation failed on an OK payload")
                self._class = StatusClass.INDETERMINATE
                self._last_error = "normalisation failed"
                self._publish(self._class)
                return self._class
            self._last_ok_at = now
        else:
            self._last_error = str(raw.get("error")) if isinstance(raw, dict) and raw.get("error") else f"{verdict.value} (no error field)"

        self._publish(self._class)
        return self._class

    def _publish(self, verdict: "StatusClass") -> None:
        """Hand the verdict to the observability sink, if one was supplied."""
        if self._on_verdict is None:
            return
        try:
            self._on_verdict(verdict)
        except Exception:
            logger.exception("Status cache verdict sink raised; continuing to poll")

    async def _run(self) -> None:
        """Poll, then sleep. Order matters — see the module docstring on self-limiting."""
        while True:
            try:
                await self.refresh_once()
            except asyncio.CancelledError:
                raise
            except Exception:  # pragma: no cover — refresh_once already swallows fetch errors
                logger.exception("Status refresher tick failed")
            await asyncio.sleep(self._interval)

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    @property
    def ticks(self) -> int:
        """Completed polls. A reader asserting freshness can check this moved."""
        return self._ticks

    def current_class(self) -> StatusClass:
        """The class a reader should act on, accounting for a refresher that stopped.

        Distinct from the stored ``_class``: a task that dies leaves the last verdict
        frozen, so a cache that had just seen OK would keep answering OK forever while
        nothing polled. Past ``unknown_after`` with no attempt, the honest answer is that
        we do not know.
        """
        if self._last_attempt_at is None:
            return StatusClass.INDETERMINATE
        if (time.monotonic() - self._last_attempt_at) > self._unknown_after:
            return StatusClass.INDETERMINATE
        return self._class

    def age_seconds(self) -> Optional[float]:
        """Seconds since the last **OK** payload, or ``None`` if there has never been one."""
        if self._last_ok_at is None:
            return None
        return time.monotonic() - self._last_ok_at

    def for_status(self) -> Dict[str, Any]:
        """The ``/api/status`` body: last-OK payload, its class, and its age.

        Three properties this must hold, each a constraint the design names:

        * **C6** — when there has never been an OK payload, nothing training-related is
          invented. The body carries the class and an error, not ``is_training: False``.
        * **C9** — a payload that is not fresh carries ``stale`` and ``age_seconds``.
        * **PR #340 compatibility** — every non-OK body carries a truthy ``error``, so the
          existing status-bar branch keeps rendering "Unreachable" even against a UI that
          has not been taught about ``status_class`` yet. The half-dead 200, which has no
          error of its own, gets one synthesised here; that is the T-C2 fix.
        """
        verdict = self.current_class()
        age = self.age_seconds()
        fresh = verdict is StatusClass.OK and age is not None and age <= self._stale_after

        body: Dict[str, Any] = dict(self._last_ok_payload) if self._last_ok_payload else {}
        body["status_class"] = verdict.value
        body["stale"] = not fresh
        body["age_seconds"] = round(age, 3) if age is not None else None

        if verdict is not StatusClass.OK:
            body["error"] = self._last_error or f"backend {verdict.value}"
        return body

    def training_active(self) -> Optional[bool]:
        """``is_training`` from the last OK payload, or ``None`` when unknown.

        ``None`` rather than ``False`` on purpose: ``False`` is a claim that training is
        not running, and the whole point of C6 is that an unreachable backend does not
        license that claim. Callers that need a ``bool`` decide their own default —
        ``is_training_active()`` keeps its ``bool`` contract and is deliberately untouched
        (design §5.5); widening it was measured to open all five 409 gates.
        """
        if self.current_class() is not StatusClass.OK or not self._last_ok_payload:
            return None
        value = self._last_ok_payload.get("is_training")
        return bool(value) if value is not None else None
