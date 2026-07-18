#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_main_gate_coverage_snapshots.py
# Author:        Paul Calnon
# License:       MIT License
# Description:   Per-file coverage-gate tests for src/main.py snapshot
#                routes (list/detail/create/restore), the replay/resume/
#                retrain proxy operations, and the network-mutation proxies.
#                Real HDF5 files are written to a tmp dir so the h5py read/
#                write branches execute for real; ``main._snapshots_dir`` is
#                monkeypatched so nothing touches the working tree.
#####################################################################
"""Real unit tests for main.py snapshot + network-proxy branches."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

src_dir = Path(__file__).parents[2]
sys.path.insert(0, str(src_dir))

import main  # noqa: E402


def _install_backend(mock):
    original = main.backend
    main.backend = mock
    return original


@pytest.fixture
def tmp_snapshots(tmp_path, monkeypatch):
    """Point ``main._snapshots_dir`` at an isolated tmp directory."""
    d = tmp_path / "snapshots"
    d.mkdir()
    monkeypatch.setattr(main, "_snapshots_dir", str(d))
    return d


@pytest.fixture
def preserve_demo_snapshots():
    """Snapshot and restore the module-global demo-snapshot deque."""
    saved = list(main._demo_snapshots)
    yield main._demo_snapshots
    main._demo_snapshots.clear()
    main._demo_snapshots.extend(saved)


@pytest.fixture
def restore_backend():
    """Restore ``main.backend`` after a test installs a mock."""
    original = main.backend
    yield
    main.backend = original


def _write_h5(path: Path, *, training_state=True, meta=True, attrs=True):
    import h5py

    with h5py.File(path, "w") as f:
        if attrs:
            f.attrs["created"] = "2026-01-01T00:00:00"
            f.attrs["description"] = "gate-test snapshot"
            f.attrs["mode"] = "manual"
        if training_state:
            g = f.create_group("training_state")
            g.attrs["status"] = "Stopped"
            g.attrs["current_epoch"] = 3
        if meta:
            mp = f.create_group("meta_params")
            mp.attrs["nn_learning_rate"] = 0.05
            mp.attrs["cn_pool_size"] = 8


# =============================================================================
# _list_snapshot_files — real directory walk (lines 1695-1697)
# =============================================================================
class TestListSnapshotFiles:
    def test_lists_real_h5_files(self, tmp_snapshots):
        _write_h5(tmp_snapshots / "run_a.h5")
        _write_h5(tmp_snapshots / "run_b.hdf5")
        (tmp_snapshots / "ignore.txt").write_text("noise")

        entries = main._list_snapshot_files()

        ids = {e["id"] for e in entries}
        assert ids == {"run_a", "run_b"}
        for e in entries:
            assert e["size_bytes"] > 0
            assert e["timestamp"].endswith("Z")


# =============================================================================
# GET /api/v1/snapshots — real mode with snapshots present (line 1744)
# =============================================================================
class TestGetSnapshotsRealNonEmpty:
    @pytest.mark.asyncio
    async def test_service_backend_returns_real_snapshots(self, restore_backend, monkeypatch):
        backend = MagicMock()
        backend.backend_type = "service"
        _install_backend(backend)
        monkeypatch.setattr(
            main,
            "_list_snapshot_files",
            lambda: [{"id": "s1", "name": "s1.h5", "timestamp": "t", "size_bytes": 10, "path": "/x/s1.h5"}],
        )
        result = await main.get_snapshots()
        assert result == {"snapshots": [{"id": "s1", "name": "s1.h5", "timestamp": "t", "size_bytes": 10, "path": "/x/s1.h5"}]}


# =============================================================================
# GET /api/v1/snapshots/{id} — detail branches (1816, 1858-1861)
# =============================================================================
class TestSnapshotDetail:
    @pytest.mark.asyncio
    async def test_demo_session_snapshot_with_meta_params(self, restore_backend, preserve_demo_snapshots):
        backend = MagicMock()
        backend.backend_type = "demo"
        _install_backend(backend)
        preserve_demo_snapshots.appendleft({"id": "sess_meta", "name": "sess_meta.h5", "description": "sess", "meta_params": {"nn_learning_rate": 0.1}})
        result = await main.get_snapshot_detail("sess_meta")
        assert result["meta_params"] == {"nn_learning_rate": 0.1}
        assert result["attributes"]["created_in_session"] is True

    @pytest.mark.asyncio
    async def test_real_snapshot_reads_hdf5_attributes(self, restore_backend, tmp_snapshots):
        backend = MagicMock()
        backend.backend_type = "service"
        _install_backend(backend)
        _write_h5(tmp_snapshots / "realdetail.h5")
        result = await main.get_snapshot_detail("realdetail")
        assert result["id"] == "realdetail"
        # f.attrs.items() -> attributes dict; meta_params group -> meta_params
        assert result["attributes"]["mode"] == "manual"
        assert "nn_learning_rate" in result["meta_params"]


# =============================================================================
# POST /api/v1/snapshots — create branches (1971, 1973, 2029-2032, 2056, 2058)
# =============================================================================
class TestCreateSnapshot:
    @pytest.mark.asyncio
    async def test_demo_create_includes_dataset_versioning(self, restore_backend, tmp_snapshots):
        backend = MagicMock()
        backend.backend_type = "demo"
        backend.get_status.return_value = {
            "dataset_name": "spiral-v2",
            "dataset_version": "2026.1",
            "nn_learning_rate": 0.1,
        }
        _install_backend(backend)
        result = await main.create_snapshot(name="demo_versioned")
        assert result["dataset_name"] == "spiral-v2"
        assert result["dataset_version"] == "2026.1"

    @pytest.mark.asyncio
    async def test_service_create_uses_cascor_metadata_never_local_stat(self, restore_backend, tmp_path, monkeypatch):
        """Wave-1 E2E finding (2026-07-18): in service mode the local snapshot
        path is a hint the adapter deliberately ignores — cascor names and
        stores the file server-side and canopy shares no filesystem with it.
        The route must build its response from cascor's metadata; the former
        post-save ``snapshot_path.stat()`` raised ENOENT and turned every
        successful save into a 500. The snapshots dir here holds NO file and
        the test must still get a clean result."""
        monkeypatch.setattr(main, "_snapshots_dir", str(tmp_path / "empty-snapshots"))
        backend = MagicMock()
        backend.backend_type = "service"
        backend.get_status.return_value = {"dataset_name": "mnist", "dataset_version": "1.0.1"}
        backend._adapter.save_snapshot.return_value = {
            "status": "success",
            "data": {
                "id": "snapshot_20260718T120930Z",
                "path": "/remote/cascor/snapshots/snapshot_20260718T120930Z.h5",
                "timestamp": "20260718T120930Z",
                "description": "",
            },
        }
        _install_backend(backend)
        result = await main.create_snapshot(description=None)
        # Description normalized at the seam (N4): the adapter must see "".
        assert backend._adapter.save_snapshot.call_args.kwargs["description"] == ""
        # Response carries cascor's server-side identity, not a local path.
        assert result["id"] == "snapshot_20260718T120930Z"
        assert result["path"] == "/remote/cascor/snapshots/snapshot_20260718T120930Z.h5"
        assert result["timestamp"] == "20260718T120930Z"
        assert result["dataset_name"] == "mnist"
        # No local file was ever required.
        assert not any((tmp_path / "empty-snapshots").glob("*.h5"))

    @pytest.mark.asyncio
    async def test_service_create_tolerates_bare_dict_and_empty_responses(self, restore_backend, tmp_snapshots):
        """Adapter responses without the success envelope (bare data dict) or
        empty ({}) must still produce a well-formed result — falling back to
        the locally generated id/timestamp, still with no local stat."""
        backend = MagicMock()
        backend.backend_type = "service"
        backend.get_status.return_value = {}
        backend._adapter.save_snapshot.return_value = {"id": "srv_bare", "path": "/r/srv_bare.h5"}
        _install_backend(backend)
        result = await main.create_snapshot(name="ignored_locally", description="d")
        assert result["id"] == "srv_bare"
        assert result["path"] == "/r/srv_bare.h5"

        backend._adapter.save_snapshot.return_value = {}
        result = await main.create_snapshot(name="local_fallback_id", description="d")
        assert result["id"] == "local_fallback_id"
        assert result["name"] == "local_fallback_id.h5"
        assert result["size_bytes"] == 0

    @pytest.mark.asyncio
    async def test_real_fallback_writes_meta_params_group(self, restore_backend, tmp_snapshots):
        # recurrence backend is non-demo AND non-service -> h5py fallback path.
        backend = MagicMock()
        backend.backend_type = "recurrence"
        backend.get_status.return_value = {
            "nn_learning_rate": 0.2,
            "cn_pool_size": 4,
            "dataset_name": "moon",
            "dataset_version": "v9",
        }
        _install_backend(backend)
        result = await main.create_snapshot(name="real_fallback", description="fallback test")
        assert result["dataset_name"] == "moon"
        assert result["dataset_version"] == "v9"
        # A real HDF5 file must now exist with the meta_params group.
        written = tmp_snapshots / "real_fallback.h5"
        assert written.exists()
        import h5py

        with h5py.File(written, "r") as f:
            assert "meta_params" in f
            assert "nn_learning_rate" in f["meta_params"].attrs


# =============================================================================
# POST /api/v1/snapshots/{id}/restore — restore branches
# =============================================================================
class TestRestoreSnapshot:
    @pytest.mark.asyncio
    async def test_demo_restore_session_snapshot_applies_meta_params(self, restore_backend, tmp_snapshots, preserve_demo_snapshots):
        backend = MagicMock()
        backend.backend_type = "demo"
        backend.is_training_active.return_value = False
        _install_backend(backend)
        preserve_demo_snapshots.appendleft({"id": "restore_sess", "name": "restore_sess.h5", "meta_params": {"nn_learning_rate": 0.2}})
        result = await main.restore_snapshot("restore_sess")
        assert result["status"] == "success"
        assert result["meta_params"] == {"nn_learning_rate": 0.2}
        backend.apply_params.assert_called_once_with(nn_learning_rate=0.2)

    @pytest.mark.asyncio
    async def test_demo_restore_mock_snapshot(self, restore_backend, tmp_snapshots, preserve_demo_snapshots):
        backend = MagicMock()
        backend.backend_type = "demo"
        backend.is_training_active.return_value = False
        _install_backend(backend)
        # demo_snapshot_1 is a generated mock id, not in the session deque.
        result = await main.restore_snapshot("demo_snapshot_1")
        assert result["status"] == "success"
        assert result["snapshot_id"] == "demo_snapshot_1"

    @pytest.mark.asyncio
    async def test_real_restore_fallback_reads_hdf5(self, restore_backend, tmp_snapshots):
        backend = MagicMock()
        backend.backend_type = "service"
        backend.is_training_active.return_value = False
        del backend._adapter.load_snapshot  # force h5py fallback branch
        _install_backend(backend)
        _write_h5(tmp_snapshots / "real_restore.h5")
        result = await main.restore_snapshot("real_restore")
        assert result["status"] == "success"
        assert result["mode"] == "real"
        assert result["meta_params"]["cn_pool_size"] == 8
        backend.apply_params.assert_called_once()

    @pytest.mark.asyncio
    async def test_real_restore_adapter_load_then_reread_meta(self, restore_backend, tmp_snapshots):
        backend = MagicMock()
        backend.backend_type = "service"
        backend.is_training_active.return_value = False
        # _adapter.load_snapshot present -> adapter path; meta_params re-read from file.
        _install_backend(backend)
        _write_h5(tmp_snapshots / "adapter_restore.h5", training_state=False)
        result = await main.restore_snapshot("adapter_restore")
        assert result["status"] == "success"
        backend._adapter.load_snapshot.assert_called_once()
        assert result["meta_params"]["nn_learning_rate"] == 0.05

    @pytest.mark.asyncio
    async def test_real_restore_adapter_load_corrupt_h5_meta_swallowed(self, restore_backend, tmp_snapshots):
        # Adapter path + a corrupt (non-HDF5) file: the best-effort meta_params
        # re-read raises and is swallowed (line 2253), leaving meta_params unset.
        backend = MagicMock()
        backend.backend_type = "service"
        backend.is_training_active.return_value = False
        _install_backend(backend)
        (tmp_snapshots / "corrupt_restore.h5").write_bytes(b"this is not a valid hdf5 file")
        result = await main.restore_snapshot("corrupt_restore")
        assert result["status"] == "success"
        assert "meta_params" not in result
        backend._adapter.load_snapshot.assert_called_once()


# =============================================================================
# _broadcast_snapshot_op — event-loop failure is swallowed (2341-2342)
# =============================================================================
class TestBroadcastSnapshotOp:
    def test_loop_error_is_swallowed(self):
        from unittest.mock import patch as _patch

        # No exception must escape even when the event loop cannot be obtained.
        with _patch("asyncio.get_event_loop", side_effect=RuntimeError("no running loop")):
            result = main._broadcast_snapshot_op("replay_started", "snap-x", payload={"k": "v"})
        assert result is None


# =============================================================================
# _require_service_adapter + replay/resume/retrain proxies + _broadcast_snapshot_op
# (2326-2342, 2348-2355, 2368-2463)
# =============================================================================
def _service_op_backend():
    backend = MagicMock()
    backend.backend_type = "service"
    backend.is_training_active.return_value = False
    return backend


class TestSnapshotOperationProxies:
    @pytest.mark.asyncio
    async def test_replay_success_broadcasts_and_logs(self, restore_backend, tmp_snapshots):
        backend = _service_op_backend()
        backend._adapter.replay_snapshot.return_value = {"operation": "replay", "session": {"length": 12}}
        _install_backend(backend)
        result = await main.replay_snapshot_route("snap_replay")
        assert result["operation"] == "replay"
        backend._adapter.replay_snapshot.assert_called_once_with("snap_replay")

    @pytest.mark.asyncio
    async def test_replay_training_active_409(self, restore_backend):
        from fastapi import HTTPException

        backend = _service_op_backend()
        backend.is_training_active.return_value = True
        _install_backend(backend)
        with pytest.raises(HTTPException) as exc:
            await main.replay_snapshot_route("snap_replay")
        assert exc.value.status_code == 409

    @pytest.mark.asyncio
    async def test_replay_demo_requires_service_501(self, restore_backend):
        from fastapi import HTTPException

        backend = MagicMock()
        backend.backend_type = "demo"
        backend.is_training_active.return_value = False
        _install_backend(backend)
        with pytest.raises(HTTPException) as exc:
            await main.replay_snapshot_route("snap_replay")
        assert exc.value.status_code == 501

    @pytest.mark.asyncio
    async def test_replay_adapter_exception_500(self, restore_backend):
        from fastapi import HTTPException

        backend = _service_op_backend()
        backend._adapter.replay_snapshot.side_effect = RuntimeError("cascor down")
        _install_backend(backend)
        with pytest.raises(HTTPException) as exc:
            await main.replay_snapshot_route("snap_replay")
        assert exc.value.status_code == 500

    @pytest.mark.asyncio
    async def test_replay_control_stop_logs_and_broadcasts(self, restore_backend, tmp_snapshots):
        backend = _service_op_backend()
        backend._adapter.replay_control.return_value = {"state": "stopped", "time_index": 0}
        _install_backend(backend)
        result = await main.replay_control_route("snap_ctl", main._ReplayControlBody(action="stop"))
        assert result["state"] == "stopped"
        backend._adapter.replay_control.assert_called_once()

    @pytest.mark.asyncio
    async def test_resume_success(self, restore_backend, tmp_snapshots):
        backend = _service_op_backend()
        backend._adapter.resume_snapshot.return_value = {"resume_point_epoch": 5}
        _install_backend(backend)
        result = await main.resume_snapshot_route("snap_resume")
        assert result["resume_point_epoch"] == 5

    @pytest.mark.asyncio
    async def test_resume_training_active_409(self, restore_backend):
        from fastapi import HTTPException

        backend = _service_op_backend()
        backend.is_training_active.return_value = True
        _install_backend(backend)
        with pytest.raises(HTTPException) as exc:
            await main.resume_snapshot_route("snap_resume")
        assert exc.value.status_code == 409

    @pytest.mark.asyncio
    async def test_retrain_success(self, restore_backend, tmp_snapshots):
        backend = _service_op_backend()
        backend._adapter.retrain_snapshot.return_value = {"status": "retrain_ready"}
        _install_backend(backend)
        result = await main.retrain_snapshot_route("snap_retrain")
        assert result["status"] == "retrain_ready"

    @pytest.mark.asyncio
    async def test_retrain_training_active_409(self, restore_backend):
        from fastapi import HTTPException

        backend = _service_op_backend()
        backend.is_training_active.return_value = True
        _install_backend(backend)
        with pytest.raises(HTTPException) as exc:
            await main.retrain_snapshot_route("snap_retrain")
        assert exc.value.status_code == 409


# =============================================================================
# Network mutation proxies (2493-2497, 2523-2527, 2540-2544)
# =============================================================================
class TestNetworkProxies:
    @pytest.mark.asyncio
    async def test_patch_weights_forwards_to_adapter(self, restore_backend):
        backend = _service_op_backend()
        backend._adapter.patch_weights.return_value = {"updated": True}
        _install_backend(backend)
        body = main._PatchWeightsBody(target="output_weights", field="values", values=[[1.0]])
        result = await main.patch_weights_route(body)
        assert result == {"updated": True}
        backend._adapter.patch_weights.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_hidden_unit_forwards_to_adapter(self, restore_backend):
        backend = _service_op_backend()
        backend._adapter.add_hidden_unit.return_value = {"added": True, "index": 3}
        _install_backend(backend)
        result = await main.add_hidden_unit_route(main._AddHiddenUnitBody(weights=[1.0, 2.0]))
        assert result == {"added": True, "index": 3}

    @pytest.mark.asyncio
    async def test_remove_hidden_unit_forwards_to_adapter(self, restore_backend):
        backend = _service_op_backend()
        backend._adapter.remove_hidden_unit.return_value = {"removed": True}
        _install_backend(backend)
        result = await main.remove_hidden_unit_route(2)
        assert result == {"removed": True}
        backend._adapter.remove_hidden_unit.assert_called_once_with(idx=2)
