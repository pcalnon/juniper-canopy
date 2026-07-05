#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_service_backend_gate_coverage.py
# Author:        Paul Calnon
# License:       MIT License
# Description:   Per-file coverage-gate tests for backend.service_backend
#####################################################################
"""Statement-coverage tests for ``ServiceBackend``.

Covers the delegating branches the existing ``test_service_backend.py``
leaves uncovered: ``set_state_update_callback``, the synced-topology
fallback in ``get_network_topology``, ``get_synced_state``, the
``initialize`` no-existing-network branch, and the Issue-#3 / Phase-2
pass-through methods. A mocked ``CascorServiceAdapter`` is used so each
branch is exercised without network dependencies.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

try:
    from backend.service_backend import ServiceBackend

    _HAS_SERVICE_BACKEND = True
except ImportError:
    _HAS_SERVICE_BACKEND = False

pytestmark = pytest.mark.skipif(not _HAS_SERVICE_BACKEND, reason="juniper-cascor-client not installed")


@pytest.fixture
def adapter():
    a = MagicMock()
    type(a).network = PropertyMock(return_value=MagicMock(__bool__=lambda s: True))
    a._service_url = "http://localhost:8200"
    return a


@pytest.fixture
def backend(adapter):
    return ServiceBackend(adapter)


@pytest.mark.unit
class TestStateCallbackRegistration:
    def test_set_state_update_callback_stores_and_forwards(self, backend, adapter):
        cb = MagicMock()
        backend.set_state_update_callback(cb)
        assert backend._state_update_callback is cb
        adapter.set_state_update_callback.assert_called_once_with(cb)


@pytest.mark.unit
class TestTopologyFallback:
    def test_uses_synced_topology_when_live_fetch_fails(self, backend, adapter):
        adapter.extract_network_topology.return_value = None
        backend._synced_state = SimpleNamespace(topology={"nodes": [{"id": "input_0"}]})

        result = backend.get_network_topology()

        assert result == {"nodes": [{"id": "input_0"}]}

    def test_returns_live_topology_when_available(self, backend, adapter):
        adapter.extract_network_topology.return_value = {"nodes": []}
        backend._synced_state = SimpleNamespace(topology={"nodes": ["stale"]})
        assert backend.get_network_topology() == {"nodes": []}

    def test_returns_none_when_no_live_and_no_synced(self, backend, adapter):
        adapter.extract_network_topology.return_value = None
        backend._synced_state = None
        assert backend.get_network_topology() is None


@pytest.mark.unit
class TestSyncedState:
    def test_get_synced_state_returns_snapshot(self, backend):
        sentinel = SimpleNamespace(status="Started")
        backend._synced_state = sentinel
        assert backend.get_synced_state() is sentinel

    def test_get_synced_state_none_by_default(self, backend):
        assert backend.get_synced_state() is None


@pytest.mark.unit
class TestInitializeNoExistingNetwork:
    async def test_initialize_connects_without_existing_network(self, backend, adapter):
        adapter.connect = AsyncMock(return_value=True)
        adapter.attach_to_existing = MagicMock(return_value=False)
        adapter.start_metrics_relay = AsyncMock()

        connected = await backend.initialize()

        assert connected is True
        adapter.attach_to_existing.assert_called_once_with()
        adapter.start_metrics_relay.assert_awaited_once()
        # No sync happened because there was no existing network.
        assert backend.get_synced_state() is None

    async def test_initialize_returns_false_when_connect_fails(self, backend, adapter):
        adapter.connect = AsyncMock(return_value=False)
        adapter.start_metrics_relay = AsyncMock()

        connected = await backend.initialize()

        assert connected is False
        adapter.start_metrics_relay.assert_not_awaited()


@pytest.mark.unit
class TestPassThroughs:
    def test_stage_dataset(self, backend, adapter):
        adapter.stage_dataset.return_value = {"ok": True, "config": {"n_samples": 5}}
        result = backend.stage_dataset(nn_dataset_elements=5)
        adapter.stage_dataset.assert_called_once_with(nn_dataset_elements=5)
        assert result == {"ok": True, "config": {"n_samples": 5}}

    def test_cancel_pending_dataset(self, backend, adapter):
        adapter.cancel_pending_dataset.return_value = {"ok": True}
        assert backend.cancel_pending_dataset() == {"ok": True}
        adapter.cancel_pending_dataset.assert_called_once_with()

    def test_get_pending_dataset(self, backend, adapter):
        adapter.get_pending_dataset.return_value = {"ok": True, "pending": None}
        assert backend.get_pending_dataset() == {"ok": True, "pending": None}
        adapter.get_pending_dataset.assert_called_once_with()

    def test_get_experimental_functions(self, backend, adapter):
        adapter.get_experimental_functions.return_value = {"enabled": True}
        assert backend.get_experimental_functions() == {"enabled": True}
        adapter.get_experimental_functions.assert_called_once_with()

    def test_set_experimental_functions(self, backend, adapter):
        adapter.set_experimental_functions.return_value = {"enabled": False}
        assert backend.set_experimental_functions(False) == {"enabled": False}
        adapter.set_experimental_functions.assert_called_once_with(False)

    def test_swap_dataset_live(self, backend, adapter):
        adapter.swap_dataset_live.return_value = {"ok": True, "swapped": True}
        result = backend.swap_dataset_live(nn_dataset_type="spiral")
        adapter.swap_dataset_live.assert_called_once_with(nn_dataset_type="spiral")
        assert result == {"ok": True, "swapped": True}

    def test_cancel_swap_dataset_live(self, backend, adapter):
        adapter.cancel_swap_dataset_live.return_value = {"ok": True}
        assert backend.cancel_swap_dataset_live() == {"ok": True}
        adapter.cancel_swap_dataset_live.assert_called_once_with()

    def test_get_dataset_swap_events(self, backend, adapter):
        adapter.get_dataset_swap_events.return_value = {"events": [], "latest": None}
        assert backend.get_dataset_swap_events(since="2026-06-01") == {"events": [], "latest": None}
        adapter.get_dataset_swap_events.assert_called_once_with(since="2026-06-01")

    def test_get_snapshot_dataset_swaps(self, backend, adapter):
        adapter.get_snapshot_dataset_swaps.return_value = {"snapshot_id": "snap-1", "swaps": []}
        assert backend.get_snapshot_dataset_swaps("snap-1") == {"snapshot_id": "snap-1", "swaps": []}
        adapter.get_snapshot_dataset_swaps.assert_called_once_with(snapshot_id="snap-1")
