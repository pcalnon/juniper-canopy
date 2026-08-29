"""F-CANOPY-007 regression: canopy must list and resolve snapshots through the
backend that CREATED them, not off its own local filesystem.

Found live in the canopy E2E arc (juniper-ml evidence note, W5 step 3): a create
succeeded end-to-end (cascor wrote the file under its own ``src/snapshots``) while
canopy's ``GET /api/v1/snapshots`` answered ``{"snapshots": [], "message": "No
snapshots available"}`` -- the list was read off ``_snapshots_dir`` (env, else
``./snapshots`` relative to canopy's CWD). The shipped compose topology co-mounts
one volume into both services, which is why it was never seen; two host processes
with different CWDs, or any split-host deployment, silently disagree. The failure
was silent: no error, no warning, and the whole FA-4 surface (list / detail /
restore / replay / resume / retrain) had no row to act on.

Fix: in service mode the inventory comes from cascor's ``GET /v1/snapshots`` (and
the detail from ``GET /v1/snapshots/{id}``); the local directory is the fallback
when the backend cannot answer, and a local copy -- when also visible -- only
enriches the record with its HDF5 attributes.
"""

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from juniper_cascor_client.exceptions import JuniperCascorConnectionError, JuniperCascorNotFoundError

import main
from backend.cascor_service_adapter import CascorServiceAdapter

CASCOR_INVENTORY = [
    # cascor sorts by filename, not by time -- the panel wants newest first.
    {"id": "snap_old", "path": "/cascor/src/snapshots/snap_old.h5", "size_bytes": 100, "modified": "2026-08-10T01:00:00+00:00"},
    {"id": "snap_new", "path": "/cascor/src/snapshots/snap_new.h5", "size_bytes": 296701, "modified": "2026-08-11T01:08:49+00:00"},
]
LOCAL_ONLY = [{"id": "local_1", "name": "local_1.h5", "timestamp": "2026-08-01T00:00:00Z", "size_bytes": 1, "path": "/local/local_1.h5"}]


@pytest.fixture
def service_backend(monkeypatch):
    """A service-mode backend whose cascor holds two snapshots -- and a canopy
    whose local directory holds NONE (the split-filesystem condition)."""
    backend = MagicMock()
    backend.backend_type = "service"
    backend._adapter.list_snapshots.return_value = {"ok": True, "snapshots": list(CASCOR_INVENTORY)}
    backend._adapter.get_snapshot.side_effect = lambda sid: {"ok": True, "snapshot": next((dict(s) for s in CASCOR_INVENTORY if s["id"] == sid), None)}
    monkeypatch.setattr(main, "backend", backend)
    monkeypatch.setattr(main, "_list_snapshot_files", lambda: [])
    monkeypatch.setattr(main, "_find_snapshot_file", lambda _dir, _sid: (None, None, False))
    return backend


@pytest.mark.unit
class TestF007ListResolvesThroughBackend:
    async def test_split_filesystem_lists_cascors_inventory_newest_first(self, service_backend):
        # The live signature on the parent: {"snapshots": [], "total": 0, "message": "No snapshots available"}.
        resp = await main.get_snapshots(limit=None, offset=0)
        assert [s["id"] for s in resp["snapshots"]] == ["snap_new", "snap_old"]
        assert resp["total"] == 2
        assert resp["snapshots"][0] == {
            "id": "snap_new",
            "name": "snap_new.h5",
            "timestamp": "2026-08-11T01:08:49+00:00",
            "size_bytes": 296701,
            "path": "/cascor/src/snapshots/snap_new.h5",
            "source": "cascor",
        }

    async def test_f031_limit_offset_total_contract_holds_on_the_backend_list(self, service_backend):
        resp = await main.get_snapshots(limit=1, offset=1)
        assert [s["id"] for s in resp["snapshots"]] == ["snap_old"]
        assert resp["total"] == 2

    async def test_backend_failure_falls_back_to_the_local_listing(self, service_backend, monkeypatch):
        service_backend._adapter.list_snapshots.return_value = {"ok": False, "error": "connection refused", "snapshots": []}
        monkeypatch.setattr(main, "_list_snapshot_files", lambda: list(LOCAL_ONLY))
        resp = await main.get_snapshots(limit=None, offset=0)
        assert [s["id"] for s in resp["snapshots"]] == ["local_1"]

    async def test_adapter_without_inventory_support_keeps_the_local_listing(self, monkeypatch):
        # A bare MagicMock adapter answers with a MagicMock, not an envelope -- the
        # route must treat that as "backend cannot answer" (this is also what
        # keeps the F-031 route tests, which mock the backend, on the local path).
        backend = MagicMock()
        backend.backend_type = "service"
        monkeypatch.setattr(main, "backend", backend)
        monkeypatch.setattr(main, "_list_snapshot_files", lambda: list(LOCAL_ONLY))
        resp = await main.get_snapshots(limit=None, offset=0)
        assert [s["id"] for s in resp["snapshots"]] == ["local_1"]

    async def test_non_service_backends_never_ask_the_adapter(self, monkeypatch):
        backend = MagicMock()
        backend.backend_type = "recurrence"
        monkeypatch.setattr(main, "backend", backend)
        monkeypatch.setattr(main, "_list_snapshot_files", lambda: list(LOCAL_ONLY))
        resp = await main.get_snapshots(limit=None, offset=0)
        assert [s["id"] for s in resp["snapshots"]] == ["local_1"]
        backend._adapter.list_snapshots.assert_not_called()


@pytest.mark.unit
class TestF007DetailResolvesThroughBackend:
    async def test_detail_comes_from_cascor_when_not_visible_locally(self, service_backend):
        detail = await main.get_snapshot_detail("snap_new")
        assert detail["id"] == "snap_new"
        assert detail["source"] == "cascor"
        assert detail["size_bytes"] == 296701
        assert detail["attributes"] is None

    async def test_unknown_id_is_404_when_cascor_says_so(self, service_backend):
        with pytest.raises(HTTPException) as exc:
            await main.get_snapshot_detail("snap_nope")
        assert exc.value.status_code == 404

    async def test_backend_failure_falls_back_to_the_local_lookup(self, service_backend):
        service_backend._adapter.get_snapshot.side_effect = None
        service_backend._adapter.get_snapshot.return_value = {"ok": False, "error": "connection refused", "snapshot": None}
        # Local lookup finds nothing either -> the local 404, not a crash.
        with pytest.raises(HTTPException) as exc:
            await main.get_snapshot_detail("snap_new")
        assert exc.value.status_code == 404

    async def test_local_copy_enriches_the_cascor_record_with_hdf5_attributes(self, service_backend, monkeypatch, tmp_path):
        h5py = pytest.importorskip("h5py")
        local = tmp_path / "snap_new.h5"
        with h5py.File(local, "w") as f:
            f.attrs["format_version"] = "2"
        monkeypatch.setattr(main, "_find_snapshot_file", lambda _dir, _sid: (local, local.stat(), False))
        detail = await main.get_snapshot_detail("snap_new")
        assert detail["source"] == "cascor"
        assert detail["attributes"] == {"format_version": "2"}


class _FakeClient:
    def __init__(self, responses):
        self._responses = responses
        self.calls = []

    def _request(self, method, path, json=None, params=None):
        self.calls.append((method, path))
        outcome = self._responses[path]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.mark.unit
class TestF007AdapterProxies:
    def test_list_snapshots_unwraps_cascors_envelope(self):
        fake = _FakeClient({"/snapshots": {"status": "success", "data": list(CASCOR_INVENTORY)}})
        result = CascorServiceAdapter(client=fake).list_snapshots()
        assert result == {"ok": True, "snapshots": list(CASCOR_INVENTORY)}
        assert fake.calls == [("GET", "/snapshots")]

    def test_list_snapshots_reports_client_failure(self):
        fake = _FakeClient({"/snapshots": JuniperCascorConnectionError("refused")})
        result = CascorServiceAdapter(client=fake).list_snapshots()
        assert result["ok"] is False
        assert result["snapshots"] == []
        assert "refused" in result["error"]

    def test_get_snapshot_unwraps_cascors_envelope(self):
        fake = _FakeClient({"/snapshots/snap_new": {"status": "success", "data": dict(CASCOR_INVENTORY[1])}})
        assert CascorServiceAdapter(client=fake).get_snapshot("snap_new") == {"ok": True, "snapshot": dict(CASCOR_INVENTORY[1])}

    def test_get_snapshot_404_is_a_definite_absence(self):
        fake = _FakeClient({"/snapshots/snap_nope": JuniperCascorNotFoundError("not found")})
        assert CascorServiceAdapter(client=fake).get_snapshot("snap_nope") == {"ok": True, "snapshot": None}

    def test_get_snapshot_reports_other_client_failures(self):
        fake = _FakeClient({"/snapshots/snap_new": JuniperCascorConnectionError("refused")})
        result = CascorServiceAdapter(client=fake).get_snapshot("snap_new")
        assert result["ok"] is False
        assert result["snapshot"] is None
