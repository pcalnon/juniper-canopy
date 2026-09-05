#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_x7_sites_outside_main_gate.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-09-04
# Last Modified: 2026-09-04
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

These tests prove the property the structure is supposed to buy. A ticker
task samples the event loop while the site under test is inside a bounded
synchronous stall. An offloaded call leaves a gap of one tick; an inline
call leaves a gap of the whole stall. The last test is the sensitivity
control: the identical ticker is required to **see** an inline ``time.sleep``,
or the four tests above are measuring nothing.

Not marked ``slow``: the coverage gate runs ``-m "not slow"``. Bound total
runtime is ~2.5 s (five 0.4 s stalls).
"""

from __future__ import annotations

import asyncio
import importlib
import sys
import time
import types
from types import SimpleNamespace
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

# Long enough that a blocked loop is unambiguous against scheduling jitter;
# short enough that five sites stay well under the slow-test threshold.
BLOCK_SECONDS = 0.4
TICK_SECONDS = 0.02
# Half the stall -- well above a free loop's ~20 ms tick, well below the stub.
STALL_SECONDS = BLOCK_SECONDS * 0.5

_CTS = "backend.cascor_service_adapter.CascorTrainingStream"
_SETTINGS = "settings.get_settings"


class _Ticker:
    """Sample the event loop so a synchronous stall becomes a visible gap."""

    def __init__(self) -> None:
        self.ticks: list[float] = []
        self._stop = asyncio.Event()
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run())
        # Land one sample before the driver starts, so a stall at t=0 is a gap.
        await asyncio.sleep(0)

    async def _run(self) -> None:
        while not self._stop.is_set():
            self.ticks.append(time.perf_counter())
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=TICK_SECONDS)
                return
            except asyncio.TimeoutError:
                continue

    async def stop(self) -> None:
        # A final sample after the driver returns turns an on-loop stall
        # (ticker never got a second chance) into a measurable gap instead
        # of ``inf``.
        self.ticks.append(time.perf_counter())
        self._stop.set()
        if self._task is not None:
            await self._task

    @property
    def worst_gap(self) -> float:
        if len(self.ticks) < 2:
            return float("inf")
        return max(self.ticks[i + 1] - self.ticks[i] for i in range(len(self.ticks) - 1))


def _blocking(counter: list[int], result):
    """A synchronous stall that counts itself -- the T-A3 'did we reach it' guard."""

    def _call(*_args, **_kwargs):
        counter.append(1)
        time.sleep(BLOCK_SECONDS)
        return result

    return _call


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
        counter: list[int] = []
        adapter = CascorServiceAdapter(service_url="http://localhost:8200", client=MagicMock())
        adapter._client.is_alive = _blocking(counter, True)

        ticker = _Ticker()
        await ticker.start()
        started = time.perf_counter()
        result = await adapter.connect()
        elapsed = time.perf_counter() - started
        await ticker.stop()

        assert result is True
        assert counter == [1], "connect() never reached is_alive -- nothing was under test"
        assert elapsed >= BLOCK_SECONDS * 0.9, f"is_alive returned in {elapsed:.3f}s -- the stub never blocked"
        assert ticker.worst_gap < STALL_SECONDS, f"connect() stalled the loop for {ticker.worst_gap:.3f}s -- is_alive is back on the loop"

    async def test_initialize_attach_does_not_block_the_loop(self):
        """``initialize`` offloads ``attach_to_existing`` (request path via ``_swap_backend``)."""
        counter: list[int] = []
        adapter = MagicMock()
        adapter.connect = AsyncMock(return_value=True)
        adapter.start_metrics_relay = AsyncMock()
        adapter.service_url = "http://localhost:8200"
        adapter.attach_to_existing = _blocking(counter, False)

        backend = ServiceBackend(adapter)
        ticker = _Ticker()
        await ticker.start()
        started = time.perf_counter()
        connected = await backend.initialize()
        elapsed = time.perf_counter() - started
        await ticker.stop()

        assert connected is True
        assert counter == [1], "initialize() never reached attach_to_existing -- nothing was under test"
        assert elapsed >= BLOCK_SECONDS * 0.9, f"attach_to_existing returned in {elapsed:.3f}s -- the stub never blocked"
        assert ticker.worst_gap < STALL_SECONDS, f"initialize() stalled the loop for {ticker.worst_gap:.3f}s -- attach_to_existing is back on the loop"
        adapter.start_metrics_relay.assert_awaited_once()

    async def test_initialize_sync_does_not_block_the_loop(self):
        """``initialize`` offloads ``CascorStateSync.sync`` when an existing network is found."""
        counter: list[int] = []
        adapter = MagicMock()
        adapter.connect = AsyncMock(return_value=True)
        adapter.start_metrics_relay = AsyncMock()
        adapter.service_url = "http://localhost:8200"
        adapter.attach_to_existing = MagicMock(return_value=True)
        adapter.client = MagicMock()

        backend = ServiceBackend(adapter)
        ticker = _Ticker()
        await ticker.start()
        started = time.perf_counter()
        with patch.object(CascorStateSync, "sync", _blocking(counter, SyncedState())):
            connected = await backend.initialize()
        elapsed = time.perf_counter() - started
        await ticker.stop()

        assert connected is True
        assert counter == [1], "initialize() never reached CascorStateSync.sync -- nothing was under test"
        assert elapsed >= BLOCK_SECONDS * 0.9, f"sync() returned in {elapsed:.3f}s -- the stub never blocked"
        assert ticker.worst_gap < STALL_SECONDS, f"initialize() stalled the loop for {ticker.worst_gap:.3f}s -- sync() is back on the loop"
        assert isinstance(backend.get_synced_state(), SyncedState)

    async def test_relay_cascade_add_does_not_block_the_loop(self):
        """``_relay_loop`` offloads ``extract_network_topology`` on cascade_add.

        This is the site the design measured at 123 s blocked per 183 s with no
        user present -- a self-method whose I/O is invisible to a receiver scan
        of ``main.py``.
        """
        counter: list[int] = []
        adapter = CascorServiceAdapter(service_url="http://localhost:8200", client=MagicMock())
        adapter.extract_network_topology = _blocking(counter, {"nodes": ["n0"]})

        first = _FakeStream(messages=[{"type": "cascade_add"}])
        cancel = _FakeStream(connect_exc=asyncio.CancelledError())
        wsm = _WSM()
        settings = SimpleNamespace(use_websocket_set_params=False, ws_relay_summary_interval_seconds=0.0)

        # Inject a broadcast-only websocket_manager so this test does not
        # depend on importing the real module (fastapi, etc.). The relay
        # does ``from communication.websocket_manager import websocket_manager``.
        wsm_mod = types.ModuleType("communication.websocket_manager")
        wsm_mod.websocket_manager = wsm

        ticker = _Ticker()
        await ticker.start()
        started = time.perf_counter()
        with (
            patch(_CTS, _stream_factory(first, cancel)),
            patch.dict(sys.modules, {"communication.websocket_manager": wsm_mod}),
            patch(_SETTINGS, return_value=settings),
        ):
            await adapter.start_metrics_relay()
            await asyncio.wait_for(adapter._relay_task, timeout=5)
        elapsed = time.perf_counter() - started
        await ticker.stop()

        assert counter == [1], "cascade_add never reached extract_network_topology -- nothing was under test"
        assert elapsed >= BLOCK_SECONDS * 0.9, f"extract_network_topology returned in {elapsed:.3f}s -- the stub never blocked"
        assert ticker.worst_gap < STALL_SECONDS, f"the relay stalled the loop for {ticker.worst_gap:.3f}s -- extract_network_topology is back on the loop"
        assert any(p.get("type") == "topology" for p in wsm.payloads)

    async def test_the_ticker_detects_an_inline_block(self):
        """Sensitivity control: the same ticker MUST see a deliberate on-loop stall.

        If this ever passes the stall threshold, the four tests above have
        stopped being able to see the defect and their green result is worthless.
        """
        ticker = _Ticker()
        await ticker.start()
        started = time.perf_counter()

        async def _inline_block() -> None:
            # ruff's ASYNC251 is exactly the defect class this whole file exists to catch,
            # and blocking the loop ON PURPOSE is the only way to prove the ticker can see
            # it. Suppressed here and NOWHERE else in this file: if the rule ever fires on
            # another line, that line is the real thing, not a control.
            time.sleep(BLOCK_SECONDS)  # noqa: ASYNC251 - deliberate block; this is the harness's negative control

        await _inline_block()
        elapsed = time.perf_counter() - started
        await ticker.stop()

        assert elapsed >= BLOCK_SECONDS * 0.9
        assert ticker.worst_gap >= BLOCK_SECONDS * 0.8, f"the ticker's worst gap was {ticker.worst_gap:.3f}s against an inline " f"{BLOCK_SECONDS}s sleep -- this harness cannot measure X7"
