#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_main_gate_coverage_routes.py
# Author:        Paul Calnon
# License:       MIT License
# Description:   Per-file coverage-gate tests for src/main.py REST route
#                service/recurrence/error branches. Exercises the async
#                route handlers directly (and via TestClient where a real
#                Request object is required) with the process-global
#                ``main.backend`` swapped for a configured mock, the pattern
#                already used by test_main_api_coverage.py.
#####################################################################
"""Real unit tests raising statement coverage of main.py route branches.

Every test asserts a concrete response value / status code / mock call —
never a bare truthiness smoke check. The handlers reference the module-global
``main.backend``; each test saves and restores it so isolation is preserved.
"""

import contextlib
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

src_dir = Path(__file__).parents[2]
sys.path.insert(0, str(src_dir))

from fastapi.responses import JSONResponse  # noqa: E402

import main  # noqa: E402


@contextlib.contextmanager
def use_backend(mock):
    """Temporarily install ``mock`` as the process-global backend."""
    original = main.backend
    main.backend = mock
    try:
        yield mock
    finally:
        main.backend = original


def service_backend(**adapter_attrs):
    """Build a service-mode mock backend with a configured ``_adapter``."""
    mock = MagicMock()
    mock.backend_type = "service"
    mock.is_training_active.return_value = False
    for key, value in adapter_attrs.items():
        setattr(mock._adapter, key, value)
    return mock


# =============================================================================
# _seed_training_state — service branch (lines 180, 189)
# =============================================================================
class TestSeedTrainingStateService:
    def test_service_backend_syncs_state_and_registers_callback(self):
        synced = SimpleNamespace(
            status="Started",
            phase="Output",
            current_epoch=7,
            max_epochs=200,
            params={"learning_rate": 0.05, "max_hidden_units": 12},
            progress_fields={"current_step": 3},
        )
        backend = MagicMock()
        backend.backend_type = "service"
        backend.get_synced_state.return_value = synced

        main._seed_training_state(backend)

        # The global training_state must now reflect the synced values.
        state = main.training_state.get_state()
        assert state["status"] == "Started"
        assert state["current_epoch"] == 7
        # Relay callback must be registered so live updates keep flowing.
        backend.set_state_update_callback.assert_called_once_with(main.training_state.update_state)


# =============================================================================
# get_state — demo(no training_state) fallback + non-demo/non-service (1050, 1124)
# =============================================================================
class TestGetStateBranches:
    @pytest.mark.asyncio
    async def test_demo_without_training_state_uses_global(self):
        backend = MagicMock()
        backend.backend_type = "demo"
        backend._demo.training_state = None  # falsy -> global training_state path (1050)
        with use_backend(backend):
            state = await main.get_state()
        # Demo-only convergence keys are always merged in the demo branch.
        assert "convergence_enabled" in state
        assert "cn_pool_size" in state

    @pytest.mark.asyncio
    async def test_recurrence_backend_returns_global_state(self):
        backend = MagicMock()
        backend.backend_type = "recurrence"  # neither demo nor service -> 1124
        with use_backend(backend):
            state = await main.get_state()
        assert state == main.training_state.get_state()


# =============================================================================
# get_network_stats — demo branch with non-empty hidden units (1180, 1182)
# =============================================================================
class TestNetworkStatsDemoHiddenUnits:
    @pytest.mark.asyncio
    async def test_demo_concatenates_all_hidden_unit_weights(self):
        import torch

        network = SimpleNamespace(
            hidden_units=[{"weights": torch.zeros(1, 2)}, {"weights": torch.ones(1, 2)}],
            input_weights=torch.zeros(2, 2),
            output_weights=torch.zeros(2, 1),
            output_bias=torch.zeros(1),
        )
        backend = MagicMock()
        backend.backend_type = "demo"
        backend._demo.get_network.return_value = network
        backend._demo.get_current_state.return_value = {"activation_fn": "tanh", "optimizer": "adam"}

        sentinel = {"nodes": 3, "edges": 4}
        with (
            use_backend(backend),
            patch("backend.data_adapter.DataAdapter") as adapter_cls,
        ):
            adapter_cls.return_value.get_network_statistics.return_value = sentinel
            result = await main.get_network_stats()

        assert result == sentinel
        # The concatenated hidden-weights tensor (2 units x 2) must reach the adapter.
        _, kwargs = adapter_cls.return_value.get_network_statistics.call_args
        assert kwargs["hidden_weights"].shape[0] == 2
        assert kwargs["threshold_function"] == "tanh"


# =============================================================================
# get_raw_topology — both branches (lines 1230-1233)
# =============================================================================
class TestRawTopology:
    @pytest.mark.asyncio
    async def test_returns_raw_when_present(self):
        backend = MagicMock()
        backend.get_raw_topology.return_value = {"layers": [1, 2]}
        with use_backend(backend):
            result = await main.get_raw_topology()
        assert result == {"layers": [1, 2]}

    @pytest.mark.asyncio
    async def test_returns_503_when_none(self):
        backend = MagicMock()
        backend.get_raw_topology.return_value = None
        with use_backend(backend):
            result = await main.get_raw_topology()
        assert isinstance(result, JSONResponse)
        assert result.status_code == 503


# =============================================================================
# POST /api/dataset/generate — needs a real Request, so drive via TestClient
# (lines 1253, 1256, 1260-1261, 1278-1288, 1292)
# =============================================================================
class TestGenerateDataset:
    def test_service_backend_rejected_400(self, client):
        backend = MagicMock()
        backend.backend_type = "service"
        with use_backend(backend):
            resp = client.post("/api/dataset/generate", json={"n_samples": 100})
        assert resp.status_code == 400

    def test_demo_without_regenerate_returns_501(self, client):
        backend = MagicMock()
        backend.backend_type = "demo"
        del backend.regenerate_dataset  # hasattr(...) -> False (line 1256)
        with use_backend(backend):
            resp = client.post("/api/dataset/generate", json={})
        assert resp.status_code == 501

    def test_invalid_json_body_falls_back_to_defaults(self, client):
        backend = MagicMock()
        backend.backend_type = "demo"
        backend.regenerate_dataset.return_value = {}  # falsy -> {"status": "generated"} (1292)
        with use_backend(backend):
            resp = client.post(
                "/api/dataset/generate",
                content=b"not-json",
                headers={"content-type": "application/json"},
            )
        assert resp.status_code == 200
        assert resp.json() == {"status": "generated"}

    def test_nonspiral_generator_requires_data_service_503(self, client):
        backend = MagicMock()
        backend.backend_type = "demo"
        original = main.juniper_data_available
        try:
            main.juniper_data_available = False
            with use_backend(backend):
                resp = client.post("/api/dataset/generate", json={"generator": "xor"})
        finally:
            main.juniper_data_available = original
        assert resp.status_code == 503

    def test_nonspiral_generator_without_backend_support_501(self, client):
        backend = MagicMock()
        backend.backend_type = "demo"
        del backend.regenerate_dataset_from_generator
        original = main.juniper_data_available
        try:
            main.juniper_data_available = True
            with use_backend(backend):
                resp = client.post("/api/dataset/generate", json={"generator": "moon"})
        finally:
            main.juniper_data_available = original
        assert resp.status_code == 501

    def test_nonspiral_generator_success(self, client):
        backend = MagicMock()
        backend.backend_type = "demo"
        backend.regenerate_dataset_from_generator.return_value = {"status": "generated_xor"}
        original = main.juniper_data_available
        try:
            main.juniper_data_available = True
            with use_backend(backend):
                resp = client.post("/api/dataset/generate", json={"generator": "xor", "n_samples": 80})
        finally:
            main.juniper_data_available = original
        assert resp.status_code == 200
        assert resp.json()["status"] == "generated_xor"

    def test_nonspiral_generator_failure_returns_500_error_id(self, client):
        backend = MagicMock()
        backend.backend_type = "demo"
        backend.regenerate_dataset_from_generator.side_effect = RuntimeError("boom")
        original = main.juniper_data_available
        try:
            main.juniper_data_available = True
            with use_backend(backend):
                resp = client.post("/api/dataset/generate", json={"generator": "circles"})
        finally:
            main.juniper_data_available = original
        assert resp.status_code == 500
        assert "error_id" in resp.json()


# =============================================================================
# POST /api/set_params — ts_updates + skipped branches (3307,3309,3311,3317,3333,3352)
# =============================================================================
class TestSetParams:
    @pytest.mark.asyncio
    async def test_success_maps_ts_updates_and_surfaces_skipped(self):
        backend = MagicMock()
        backend.backend_type = "service"
        backend.apply_params.return_value = {"ok": True, "skipped": ["cn_unsupported"]}
        body = main.SetParamsRequest(
            nn_max_iterations=9,
            nn_init_output_weights="zeros",
            cn_pool_size=8,
            cn_correlation_threshold=0.4,
            nn_learning_rate=0.05,
            nn_max_hidden_units=6,
            nn_max_total_epochs=40,
            nn_growth_convergence_threshold=0.02,
            nn_patience=4,
            cn_candidate_learning_rate=0.03,
        )
        with use_backend(backend):
            result = await main.api_set_params(body)
        assert result["status"] == "success"
        assert result["skipped"] == ["cn_unsupported"]

    @pytest.mark.asyncio
    async def test_backend_rejection_returns_502_with_skipped(self):
        backend = MagicMock()
        backend.backend_type = "service"
        backend.apply_params.return_value = {"ok": False, "error": "bad param", "skipped": ["cn_x"]}
        body = main.SetParamsRequest(nn_learning_rate=0.1)
        with use_backend(backend):
            result = await main.api_set_params(body)
        assert isinstance(result, JSONResponse)
        assert result.status_code == 502


# =============================================================================
# stage_dataset / cancel_pending_dataset (3394-3406, 3412-3422)
# =============================================================================
class TestStageAndCancelDataset:
    @pytest.mark.asyncio
    async def test_stage_dataset_success(self):
        backend = MagicMock()
        backend.stage_dataset.return_value = {"ok": True, "data": {"staged": "spiral"}}
        with use_backend(backend):
            result = await main.api_stage_dataset(main.StageDatasetRequest(nn_dataset_type="spiral"))
        assert result == {"status": "success", "data": {"staged": "spiral"}}

    @pytest.mark.asyncio
    async def test_stage_dataset_backend_rejection_502(self):
        backend = MagicMock()
        backend.stage_dataset.return_value = {"ok": False, "error": "unknown type"}
        with use_backend(backend):
            result = await main.api_stage_dataset(main.StageDatasetRequest(nn_dataset_type="???"))
        assert isinstance(result, JSONResponse)
        assert result.status_code == 502

    @pytest.mark.asyncio
    async def test_stage_dataset_exception_500(self):
        backend = MagicMock()
        backend.stage_dataset.side_effect = RuntimeError("boom")
        with use_backend(backend):
            result = await main.api_stage_dataset(main.StageDatasetRequest(nn_dataset_elements=50))
        assert isinstance(result, JSONResponse)
        assert result.status_code == 500

    @pytest.mark.asyncio
    async def test_cancel_pending_success(self):
        backend = MagicMock()
        backend.cancel_pending_dataset.return_value = {"ok": True, "data": {"cancelled": True}}
        with use_backend(backend):
            result = await main.api_cancel_pending_dataset()
        assert result == {"status": "success", "data": {"cancelled": True}}

    @pytest.mark.asyncio
    async def test_cancel_pending_backend_rejection_502(self):
        backend = MagicMock()
        backend.cancel_pending_dataset.return_value = {"ok": False, "error": "nothing staged"}
        with use_backend(backend):
            result = await main.api_cancel_pending_dataset()
        assert isinstance(result, JSONResponse)
        assert result.status_code == 502

    @pytest.mark.asyncio
    async def test_cancel_pending_exception_500(self):
        backend = MagicMock()
        backend.cancel_pending_dataset.side_effect = RuntimeError("boom")
        with use_backend(backend):
            result = await main.api_cancel_pending_dataset()
        assert isinstance(result, JSONResponse)
        assert result.status_code == 500


# =============================================================================
# experimental_functions get/set (3451-3461, 3473-3483)
# =============================================================================
class TestExperimentalFunctions:
    @pytest.mark.asyncio
    async def test_get_success(self):
        backend = MagicMock()
        backend.get_experimental_functions.return_value = {"enabled": True}
        with use_backend(backend):
            result = await main.api_get_experimental_functions()
        assert result == {"status": "success", "data": {"enabled": True}}

    @pytest.mark.asyncio
    async def test_get_backend_rejection_502(self):
        backend = MagicMock()
        backend.get_experimental_functions.return_value = {"ok": False, "error": "locked"}
        with use_backend(backend):
            result = await main.api_get_experimental_functions()
        assert isinstance(result, JSONResponse)
        assert result.status_code == 502

    @pytest.mark.asyncio
    async def test_get_exception_500(self):
        backend = MagicMock()
        backend.get_experimental_functions.side_effect = RuntimeError("boom")
        with use_backend(backend):
            result = await main.api_get_experimental_functions()
        assert isinstance(result, JSONResponse)
        assert result.status_code == 500

    @pytest.mark.asyncio
    async def test_set_success(self):
        backend = MagicMock()
        backend.set_experimental_functions.return_value = {"enabled": True}
        with use_backend(backend):
            result = await main.api_set_experimental_functions(main.ExperimentalFunctionsRequest(enabled=True))
        assert result == {"status": "success", "data": {"enabled": True}}

    @pytest.mark.asyncio
    async def test_set_backend_rejection_502(self):
        backend = MagicMock()
        backend.set_experimental_functions.return_value = {"ok": False, "error": "policy"}
        with use_backend(backend):
            result = await main.api_set_experimental_functions(main.ExperimentalFunctionsRequest(enabled=False))
        assert isinstance(result, JSONResponse)
        assert result.status_code == 502

    @pytest.mark.asyncio
    async def test_set_exception_500(self):
        backend = MagicMock()
        backend.set_experimental_functions.side_effect = RuntimeError("boom")
        with use_backend(backend):
            result = await main.api_set_experimental_functions(main.ExperimentalFunctionsRequest(enabled=True))
        assert isinstance(result, JSONResponse)
        assert result.status_code == 500


# =============================================================================
# live_dataset_swap POST/DELETE (3516-3527, 3543-3553)
# =============================================================================
class TestLiveDatasetSwap:
    @pytest.mark.asyncio
    async def test_swap_success(self):
        backend = MagicMock()
        backend.swap_dataset_live.return_value = {"ok": True, "data": {"status": "swapped"}}
        with use_backend(backend):
            result = await main.api_live_dataset_swap(main.StageDatasetRequest(nn_dataset_type="xor"))
        assert result == {"status": "success", "data": {"status": "swapped"}}

    @pytest.mark.asyncio
    async def test_swap_backend_rejection_502(self):
        backend = MagicMock()
        backend.swap_dataset_live.return_value = {"ok": False, "error": "in flight"}
        with use_backend(backend):
            result = await main.api_live_dataset_swap(main.StageDatasetRequest(nn_dataset_type="xor"))
        assert isinstance(result, JSONResponse)
        assert result.status_code == 502

    @pytest.mark.asyncio
    async def test_swap_exception_500(self):
        backend = MagicMock()
        backend.swap_dataset_live.side_effect = RuntimeError("boom")
        with use_backend(backend):
            result = await main.api_live_dataset_swap(main.StageDatasetRequest())
        assert isinstance(result, JSONResponse)
        assert result.status_code == 500

    @pytest.mark.asyncio
    async def test_cancel_swap_success(self):
        backend = MagicMock()
        backend.cancel_swap_dataset_live.return_value = {"ok": True, "data": {"cancelled": True}}
        with use_backend(backend):
            result = await main.api_cancel_live_dataset_swap()
        assert result == {"status": "success", "data": {"cancelled": True}}

    @pytest.mark.asyncio
    async def test_cancel_swap_backend_rejection_502(self):
        backend = MagicMock()
        backend.cancel_swap_dataset_live.return_value = {"ok": False, "error": "no swap"}
        with use_backend(backend):
            result = await main.api_cancel_live_dataset_swap()
        assert isinstance(result, JSONResponse)
        assert result.status_code == 502

    @pytest.mark.asyncio
    async def test_cancel_swap_exception_500(self):
        backend = MagicMock()
        backend.cancel_swap_dataset_live.side_effect = RuntimeError("boom")
        with use_backend(backend):
            result = await main.api_cancel_live_dataset_swap()
        assert isinstance(result, JSONResponse)
        assert result.status_code == 500


# =============================================================================
# dataset_swap event feeds (3580-3591, 3609-3620)
# =============================================================================
class TestDatasetSwapEvents:
    @pytest.mark.asyncio
    async def test_events_success(self):
        backend = MagicMock()
        backend.get_dataset_swap_events.return_value = {"events": [{"timestamp": "t"}]}
        with use_backend(backend):
            result = await main.api_get_dataset_swap_events(since="2020-01-01")
        assert result == {"status": "success", "data": {"events": [{"timestamp": "t"}]}}

    @pytest.mark.asyncio
    async def test_events_backend_rejection_502(self):
        backend = MagicMock()
        backend.get_dataset_swap_events.return_value = {"ok": False, "error": "cascor down"}
        with use_backend(backend):
            result = await main.api_get_dataset_swap_events()
        assert isinstance(result, JSONResponse)
        assert result.status_code == 502

    @pytest.mark.asyncio
    async def test_events_exception_500(self):
        backend = MagicMock()
        backend.get_dataset_swap_events.side_effect = RuntimeError("boom")
        with use_backend(backend):
            result = await main.api_get_dataset_swap_events()
        assert isinstance(result, JSONResponse)
        assert result.status_code == 500

    @pytest.mark.asyncio
    async def test_snapshot_events_success(self):
        backend = MagicMock()
        backend.get_snapshot_dataset_swaps.return_value = {"events": []}
        with use_backend(backend):
            result = await main.api_get_snapshot_dataset_swaps("snap-1")
        assert result == {"status": "success", "data": {"events": []}}

    @pytest.mark.asyncio
    async def test_snapshot_events_backend_rejection_502(self):
        backend = MagicMock()
        backend.get_snapshot_dataset_swaps.return_value = {"ok": False, "error": "404"}
        with use_backend(backend):
            result = await main.api_get_snapshot_dataset_swaps("snap-1")
        assert isinstance(result, JSONResponse)
        assert result.status_code == 502

    @pytest.mark.asyncio
    async def test_snapshot_events_exception_500(self):
        backend = MagicMock()
        backend.get_snapshot_dataset_swaps.side_effect = RuntimeError("boom")
        with use_backend(backend):
            result = await main.api_get_snapshot_dataset_swaps("snap-1")
        assert isinstance(result, JSONResponse)
        assert result.status_code == 500


# =============================================================================
# Remote worker management (3636, 3668-3670, 3695-3698, 3733-3736)
# =============================================================================
class TestRemoteWorkers:
    @pytest.mark.asyncio
    async def test_remote_status_service(self):
        backend = service_backend()
        backend._adapter.get_remote_worker_status.return_value = {"available": True, "connected": True}
        with use_backend(backend):
            result = await main.api_remote_status()
        assert result == {"available": True, "connected": True}

    @pytest.mark.asyncio
    async def test_remote_connect_success(self):
        backend = service_backend()
        backend._adapter.connect_remote_workers.return_value = True
        body = main.RemoteConnectRequest(host="10.0.0.1", port=5555, authkey="s3cr3t")
        with use_backend(backend):
            result = await main.api_remote_connect(body)
        assert result == {"status": "connected", "address": "10.0.0.1:5555"}
        # SecretStr must be unwrapped before reaching the adapter.
        args, _ = backend._adapter.connect_remote_workers.call_args
        assert args[0] == ("10.0.0.1", 5555)
        assert args[1] == "s3cr3t"

    @pytest.mark.asyncio
    async def test_remote_connect_failure_500(self):
        backend = service_backend()
        backend._adapter.connect_remote_workers.return_value = False
        body = main.RemoteConnectRequest(host="h", port=1, authkey="k")
        with use_backend(backend):
            result = await main.api_remote_connect(body)
        assert isinstance(result, JSONResponse)
        assert result.status_code == 500

    @pytest.mark.asyncio
    async def test_remote_start_workers_success(self):
        backend = service_backend()
        backend._adapter.start_remote_workers.return_value = True
        with use_backend(backend):
            result = await main.api_remote_start_workers(num_workers=3)
        assert result == {"status": "started", "num_workers": 3}

    @pytest.mark.asyncio
    async def test_remote_start_workers_failure_500(self):
        backend = service_backend()
        backend._adapter.start_remote_workers.return_value = False
        with use_backend(backend):
            result = await main.api_remote_start_workers()
        assert isinstance(result, JSONResponse)
        assert result.status_code == 500

    @pytest.mark.asyncio
    async def test_remote_disconnect_success(self):
        backend = service_backend()
        backend._adapter.disconnect_remote_workers.return_value = True
        with use_backend(backend):
            result = await main.api_remote_disconnect()
        assert result == {"status": "disconnected"}

    @pytest.mark.asyncio
    async def test_remote_disconnect_failure_500(self):
        backend = service_backend()
        backend._adapter.disconnect_remote_workers.return_value = False
        with use_backend(backend):
            result = await main.api_remote_disconnect()
        assert isinstance(result, JSONResponse)
        assert result.status_code == 500


# =============================================================================
# Worker stats / list (2836-2843, 2874-2881)
# =============================================================================
class TestWorkerStatsAndList:
    @pytest.mark.asyncio
    async def test_worker_stats_service_success_unwraps_data(self):
        backend = service_backend()
        backend._adapter._client.get_worker_stats.return_value = {"data": {"total": 5, "idle": 2}}
        with use_backend(backend):
            result = await main.get_worker_stats()
        assert result == {"total": 5, "idle": 2}

    @pytest.mark.asyncio
    async def test_worker_stats_service_failure_returns_error_id(self):
        backend = service_backend()
        backend._adapter._client.get_worker_stats.side_effect = RuntimeError("upstream")
        with use_backend(backend):
            result = await main.get_worker_stats()
        assert result["error"] == "Upstream error"
        assert "error_id" in result
        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_worker_list_service_success_unwraps_data(self):
        backend = service_backend()
        backend._adapter._client.list_workers.return_value = {"data": {"workers": [], "count": 0}}
        with use_backend(backend):
            result = await main.get_worker_list()
        # N10: the route now annotates the response with local_reported
        # (False until cascor exposes the local pool) and defaults each
        # worker's kind — with no workers, only the flag is added.
        assert result == {"workers": [], "count": 0, "local_reported": False}

    @pytest.mark.asyncio
    async def test_worker_list_service_failure_returns_error_id(self):
        backend = service_backend()
        backend._adapter._client.list_workers.side_effect = RuntimeError("upstream")
        with use_backend(backend):
            result = await main.get_worker_list()
        assert result["error"] == "Upstream error"
        assert "error_id" in result
        assert result["workers"] == []
