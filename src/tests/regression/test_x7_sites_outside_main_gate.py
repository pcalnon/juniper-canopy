#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_x7_sites_outside_main_gate.py
# Author:        Paul Calnon
# Version:       0.1.1
# Date:          2026-09-04
# Last Modified: 2026-11-25
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   X7 slice 1a -- the four off-loop sites the main.py
#                structural gate cannot see must not stall the loop.
#####################################################################
"""X7 complementary tests: the four sites ``test_x7_off_loop_discipline`` cannot see.

The committed gate reads ``main.py`` only. Slice 1a also offloaded four call
sites outside that file -- ``CascorServiceAdapter.connect``, the cascade_add
arm of ``_relay_loop`` (measured **123 s blocked per 183 s with no user
present**), and the two ``ServiceBackend.initialize`` hops that sit on the
runtime model-swap path via ``_swap_backend``. Existing unit tests still pass
if any of those four are reverted to an inline call: they mock the callee, not
the offload.

These tests prove the property the structure is supposed to buy by observing
WHERE the blocking call runs, not by timing the loop. Each site's call is
replaced by a ``_HeldCall``: it records the thread it runs on, then holds until
a coroutine on the event loop releases it. Offloaded, it runs on a worker
thread while the loop stays free, and the loop releases it as soon as it has
entered. Inline, it runs on the loop thread itself: the loop is inside the
call, nothing can release it, and it gives up after ``HOLD_SECONDS``. Neither
outcome depends on how fast the loop runs, only on whether it can run at all
within ``HOLD_SECONDS``. What they do not bound is how long anything else holds
the loop: a bounded on-loop stall beside a correctly offloaded call (a
``time.sleep`` in the same arm) passes them, as it passes any test that cannot
tell it from a stalled process.
The last two tests are the sensitivity controls. The same held call made inline
on purpose MUST be seen on the loop thread and unreleased; made on a worker
thread while the loop waits synchronously for its result, it MUST be seen off
the loop thread and still unreleased. Otherwise the four tests above are
measuring nothing.

Why not a wall-clock gap. These tests used to sample the loop with a ticker and
fail when its worst gap between samples reached 0.2 s. A gap counts every moment
the loop thread did not run, whatever stopped it, and in the unit lane a full
garbage collection of the session's heap stops every thread of the process for
about a second (0.68-0.95 s per pass in the regression directory in two local
runs of the lane on Python 3.13, 0.77-1.52 s in two on Python 3.12). Stalls of
that size (whole-process stops in the four jobs whose logs settle it) failed
these tests in ten CI jobs between 2026-11-02 and 2026-11-25 (the relay test six
times, the ``initialize`` sync test four), with every call correctly offloaded.

Not marked ``slow``: the coverage gate runs ``-m "not slow"``. A passing run
of the six tests takes about a second; ``HOLD_SECONDS`` is only ever waited out
by a test that is about to fail.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import contextlib
import importlib
import sys
import threading
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# The conftest client stub does not ship ``juniper_cascor_client.constants``.
# The adapter imports ``ENDPOINT_TRAINING_START`` at module level, so the stub
# path used in CI (and in this file, which never calls that endpoint) needs
# the name present. A real install is left untouched.
if "juniper_cascor_client.constants" not in sys.modules:
    try:
        # `importlib.import_module` rather than a bare `import` statement: the import
        # is for its SIDE EFFECT (populate sys.modules, or raise so the stub below
        # runs), and a bare import whose name is never referenced reads as dead to
        # CodeQL -- an unresolved alert of that shape blocks the merge while every
        # check stays green.
        importlib.import_module("juniper_cascor_client.constants")
    except ImportError:
        _constants = types.ModuleType("juniper_cascor_client.constants")
        _constants.ENDPOINT_TRAINING_START = "/v1/training/start"
        sys.modules["juniper_cascor_client.constants"] = _constants

from backend.cascor_service_adapter import CascorServiceAdapter
from backend.service_backend import ServiceBackend
from backend.state_sync import CascorStateSync, SyncedState

# The relay imports these lazily, inside its loop. A module first imported inside the
# relay test's patch.dict(sys.modules, ...) is dropped again when the patch exits, so
# every isolated run would re-execute them inside that test's HOLD_SECONDS + 5 bound.
# Imported here, they stay cached, as the unit lane's earlier tests leave them.
for _lazily_imported in ("juniper_cascor_protocol.envelope", "observability"):
    importlib.import_module(_lazily_imported)

# How long a held call waits for the loop to release it. Releasing takes the loop
# one callback and one task step, so this bounds a loop that cannot run at all,
# not a slow one: offloaded, the call is released as soon as the loop runs again
# (the longest stall these tests met in CI was 1.06 s); inline, it
# is never released. Only a test that is about to fail waits it out.
HOLD_SECONDS = 10.0
# The control's inline call cannot be released however long it holds -- the loop
# thread is inside it -- so a short hold proves the point and keeps the suite fast.
CONTROL_HOLD_SECONDS = 0.2

_CTS = "backend.cascor_service_adapter.CascorTrainingStream"
_SETTINGS = "settings.get_settings"


class _HeldCall:
    """A stand-in for a blocking call: it records WHERE it runs and holds until the loop releases it.

    Build it inside the test coroutine -- it captures the running loop and that
    loop's thread there -- and drive the code under test inside
    ``released_by_the_loop()``, which keeps the releasing coroutine on the loop.
    """

    def __init__(self, result, hold_seconds: float = HOLD_SECONDS) -> None:
        self.result = result
        self.hold_seconds = hold_seconds
        self.calls = 0
        self.ran_on_loop_thread: bool | None = None
        self.released_by_loop: bool | None = None
        self._loop = asyncio.get_running_loop()
        self._loop_thread = threading.get_ident()
        self._entered = asyncio.Event()
        self._release = threading.Event()

    def __call__(self, *_args, **_kwargs):
        self.calls += 1
        self.ran_on_loop_thread = threading.get_ident() == self._loop_thread
        # Safe from any thread; called from the loop thread it only queues the callback.
        self._loop.call_soon_threadsafe(self._entered.set)
        self.released_by_loop = self._release.wait(timeout=self.hold_seconds)
        return self.result

    async def _release_when_entered(self) -> None:
        await self._entered.wait()
        self._release.set()

    @contextlib.asynccontextmanager
    async def released_by_the_loop(self):
        releaser = asyncio.create_task(self._release_when_entered())
        try:
            yield self
        finally:
            releaser.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await releaser


class _FakeStream:
    """Minimal CascorTrainingStream: yields controlled messages then stops."""

    def __init__(self, messages=None, connect_exc=None):
        self.messages = messages or []
        self.connect_exc = connect_exc
        self.disconnected = False

    async def connect(self):
        if self.connect_exc is not None:
            raise self.connect_exc

    async def disconnect(self):
        self.disconnected = True

    async def stream(self):
        for message in self.messages:
            yield message


class _WSM:
    def __init__(self):
        self.payloads = []

    async def broadcast(self, payload):
        self.payloads.append(payload)


def _stream_factory(*streams):
    queue = list(streams)

    def _make(*_args, **_kwargs):
        return queue.pop(0)

    return _make


@pytest.mark.regression
@pytest.mark.unit
class TestSitesOutsideMainGateStayOffLoop:
    """The four 1a sites the main.py gate does not model."""

    async def test_connect_does_not_block_the_loop(self):
        """``connect`` offloads ``is_alive`` -- the 123 s hang if this returns to inline."""
        adapter = CascorServiceAdapter(service_url="http://localhost:8200", client=MagicMock())
        held = _HeldCall(True)
        adapter._client.is_alive = held

        async with held.released_by_the_loop():
            result = await adapter.connect()

        assert result is True
        assert held.calls == 1, "connect() never reached is_alive -- nothing was under test"
        assert held.ran_on_loop_thread is False, "connect() ran is_alive on the event-loop thread -- is_alive is back on the loop"
        assert held.released_by_loop is True, f"the loop did not run while is_alive was in flight (unreleased after {HOLD_SECONDS}s) -- connect() is blocking the loop"

    async def test_initialize_attach_does_not_block_the_loop(self):
        """``initialize`` offloads ``attach_to_existing`` (request path via ``_swap_backend``)."""
        adapter = MagicMock()
        adapter.connect = AsyncMock(return_value=True)
        adapter.start_metrics_relay = AsyncMock()
        adapter.service_url = "http://localhost:8200"
        held = _HeldCall(False)
        adapter.attach_to_existing = held

        backend = ServiceBackend(adapter)
        async with held.released_by_the_loop():
            connected = await backend.initialize()

        assert connected is True
        assert held.calls == 1, "initialize() never reached attach_to_existing -- nothing was under test"
        assert held.ran_on_loop_thread is False, "initialize() ran attach_to_existing on the event-loop thread -- attach_to_existing is back on the loop"
        assert held.released_by_loop is True, f"the loop did not run while attach_to_existing was in flight (unreleased after {HOLD_SECONDS}s) -- initialize() is blocking the loop"
        adapter.start_metrics_relay.assert_awaited_once()

    async def test_initialize_sync_does_not_block_the_loop(self):
        """``initialize`` offloads ``CascorStateSync.sync`` when an existing network is found."""
        adapter = MagicMock()
        adapter.connect = AsyncMock(return_value=True)
        adapter.start_metrics_relay = AsyncMock()
        adapter.service_url = "http://localhost:8200"
        adapter.attach_to_existing = MagicMock(return_value=True)
        adapter.client = MagicMock()

        backend = ServiceBackend(adapter)
        held = _HeldCall(SyncedState())
        async with held.released_by_the_loop():
            with patch.object(CascorStateSync, "sync", held):
                connected = await backend.initialize()

        assert connected is True
        assert held.calls == 1, "initialize() never reached CascorStateSync.sync -- nothing was under test"
        assert held.ran_on_loop_thread is False, "initialize() ran sync() on the event-loop thread -- sync() is back on the loop"
        assert held.released_by_loop is True, f"the loop did not run while sync() was in flight (unreleased after {HOLD_SECONDS}s) -- initialize() is blocking the loop"
        assert isinstance(backend.get_synced_state(), SyncedState)

    async def test_relay_cascade_add_does_not_block_the_loop(self):
        """``_relay_loop`` offloads ``extract_network_topology`` on cascade_add.

        This is the site the design measured at 123 s blocked per 183 s with no
        user present -- a self-method whose I/O is invisible to a receiver scan
        of ``main.py``.
        """
        adapter = CascorServiceAdapter(service_url="http://localhost:8200", client=MagicMock())
        held = _HeldCall({"nodes": ["n0"]})
        adapter.extract_network_topology = held

        first = _FakeStream(messages=[{"type": "cascade_add"}])
        cancel = _FakeStream(connect_exc=asyncio.CancelledError())
        wsm = _WSM()
        settings = types.SimpleNamespace(use_websocket_set_params=False, ws_relay_summary_interval_seconds=0.0)

        # Inject a broadcast-only websocket_manager so this test does not
        # depend on importing the real module (fastapi, etc.). The relay
        # does ``from communication.websocket_manager import websocket_manager``.
        wsm_mod = types.ModuleType("communication.websocket_manager")
        wsm_mod.websocket_manager = wsm

        async with held.released_by_the_loop():
            with (
                patch(_CTS, _stream_factory(first, cancel)),
                patch.dict(sys.modules, {"communication.websocket_manager": wsm_mod}),
                patch(_SETTINGS, return_value=settings),
            ):
                await adapter.start_metrics_relay()
                # Longer than the hold, so a relay stuck inside an inline call fails on the
                # assertions below rather than on this timeout. asyncio.wait, not wait_for: the
                # relay swallows CancelledError, so a wait_for that runs out cancels it and then
                # returns normally, and the assertions below would blame the loop for a slow run.
                done, _pending = await asyncio.wait({adapter._relay_task}, timeout=HOLD_SECONDS + 5)
                if adapter._relay_task not in done:
                    adapter._relay_task.cancel()
                    pytest.fail(f"the relay did not finish within {HOLD_SECONDS + 5}s -- too slow a run to judge where extract_network_topology ran; nothing here says the loop was blocked")

        assert held.calls == 1, "cascade_add never reached extract_network_topology -- nothing was under test"
        assert held.ran_on_loop_thread is False, "the relay ran extract_network_topology on the event-loop thread -- extract_network_topology is back on the loop"
        assert held.released_by_loop is True, f"the loop did not run while extract_network_topology was in flight (unreleased after {HOLD_SECONDS}s) -- the relay is blocking the loop"
        assert any(p.get("type") == "topology" for p in wsm.payloads)

    async def test_the_held_call_detects_an_inline_call(self):
        """Sensitivity control: the same held call MUST catch a deliberate on-loop call.

        If this ever reports the call off the loop, or released, the four tests
        above have stopped being able to see the defect and their green result
        is worthless.
        """
        held = _HeldCall(True, hold_seconds=CONTROL_HOLD_SECONDS)

        async with held.released_by_the_loop():
            # Deliberately inline: the loop thread runs the call, so the coroutine
            # that would release it cannot run until the call has returned.
            result = held()

        assert result is True
        assert held.calls == 1
        assert held.ran_on_loop_thread is True, "an inline call was not seen on the event-loop thread -- this harness cannot see X7"
        assert held.released_by_loop is False, "an inline call was released while the loop was inside it -- this harness cannot see X7"

    async def test_the_held_call_detects_a_loop_blocked_on_its_result(self):
        """Sensitivity control for the release check: a loop that waits on the worker MUST leave the call unreleased.

        The thread check alone passes an offloaded call whose result the loop then
        waits for synchronously; only the release check catches that shape. If this
        ever reports the call released, the four tests above can no longer see it.
        """
        held = _HeldCall(True, hold_seconds=CONTROL_HOLD_SECONDS)

        async with held.released_by_the_loop():
            # Let the releasing coroutine start first, as it does in the four tests above
            # (their code under test awaits before the call is made).
            await asyncio.sleep(0)
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                # Deliberately blocks the loop thread on the worker's result, so the
                # coroutine that would release the call cannot run until it returns.
                result = pool.submit(held).result()

        assert result is True
        assert held.calls == 1
        assert held.ran_on_loop_thread is False, "a call made on a worker thread was seen on the event-loop thread -- this harness cannot see X7"
        assert held.released_by_loop is False, "a call was released while the loop waited synchronously for its result -- this harness cannot see a loop blocked on an offloaded call"
