#!/usr/bin/env python
"""F-CANOPY-031: the snapshots panel must scale to the no-deletion corpus.

The shared corpus holds 27,903+ snapshots (10.4 MB / ~4.9 s as one payload)
and the S-2 retention ruling is no-deletion — the old unbounded fetch lost the
race to the panel's 2 s timeout AND, when it did land, asked the client to
build one ``html.Tr`` (with two buttons and a four-item dropdown) per
snapshot. The panel sat at its layout-default "Loading snapshots…" with the
empty-state hidden — neither data nor an honest empty state.

Fix under test: the route slices server-side (``limit``/``offset``, always
reporting the pre-slice ``total``), and the panel fetches only the newest
``SNAPSHOT_TABLE_PAGE_SIZE`` with an elevated timeout and an honest
"Showing newest N of TOTAL" status line.
"""

from unittest.mock import MagicMock, patch

import pytest

import main
from frontend.components.hdf5_snapshots_panel import SNAPSHOT_TABLE_PAGE_SIZE, HDF5SnapshotsPanel


def _fake_files(n):
    return [{"id": f"s{i}", "name": f"s{i}.h5", "timestamp": f"t{i}", "size_bytes": i, "path": f"/x/s{i}.h5"} for i in range(n)]


@pytest.fixture
def service_backend(monkeypatch):
    backend = MagicMock()
    backend.backend_type = "service"
    monkeypatch.setattr(main, "backend", backend)
    return backend


class TestF031RouteSlicing:
    @pytest.mark.asyncio
    async def test_limit_returns_newest_head_and_total(self, service_backend, monkeypatch):
        # _list_snapshot_files is already newest-first; the slice must keep its head.
        monkeypatch.setattr(main, "_list_snapshot_files", lambda: _fake_files(7))
        result = await main.get_snapshots(limit=3)
        assert [s["id"] for s in result["snapshots"]] == ["s0", "s1", "s2"]
        assert result["total"] == 7

    @pytest.mark.asyncio
    async def test_offset_skips_after_the_sort(self, service_backend, monkeypatch):
        monkeypatch.setattr(main, "_list_snapshot_files", lambda: _fake_files(7))
        result = await main.get_snapshots(limit=2, offset=3)
        assert [s["id"] for s in result["snapshots"]] == ["s3", "s4"]
        assert result["total"] == 7

    @pytest.mark.asyncio
    async def test_no_params_keeps_the_legacy_full_list(self, service_backend, monkeypatch):
        monkeypatch.setattr(main, "_list_snapshot_files", lambda: _fake_files(5))
        result = await main.get_snapshots()
        assert len(result["snapshots"]) == 5
        assert result["total"] == 5

    @pytest.mark.asyncio
    async def test_demo_branch_reports_total_too(self, monkeypatch):
        backend = MagicMock()
        backend.backend_type = "demo"
        monkeypatch.setattr(main, "backend", backend)
        monkeypatch.setattr(main, "_list_snapshot_files", lambda: [])
        monkeypatch.setattr(main, "_demo_snapshots", [])
        monkeypatch.setattr(main, "_generate_mock_snapshots", lambda: _fake_files(4))
        result = await main.get_snapshots(limit=2)
        assert len(result["snapshots"]) == 2
        assert result["total"] == 4


class TestF031PanelPageFetch:
    @pytest.fixture
    def panel(self):
        return HDF5SnapshotsPanel({"api_timeout": 2})

    @patch("frontend.components.hdf5_snapshots_panel.requests.get")
    def test_fetch_requests_one_page_with_headroom_timeout(self, mock_get, panel):
        mock_get.return_value = MagicMock(status_code=200, json=lambda: {"snapshots": [], "total": 0})
        panel._parse_snapshots_response()
        _, kwargs = mock_get.call_args
        assert kwargs["params"] == {"limit": SNAPSHOT_TABLE_PAGE_SIZE}
        # The 2 s bare timeout lost the race to the corpus scan (measured 4.9 s
        # for the unbounded listing); the list fetch gets the create-path's +3.
        assert kwargs["timeout"] == panel.api_timeout + 3

    @patch("frontend.components.hdf5_snapshots_panel.requests.get")
    def test_fetch_carries_total_through(self, mock_get, panel):
        mock_get.return_value = MagicMock(status_code=200, json=lambda: {"snapshots": _fake_files(2), "total": 27903})
        result = panel._fetch_snapshots_handler()
        assert result["total"] == 27903
        assert len(result["snapshots"]) == 2

    def test_status_line_reports_truncation(self, panel):
        app = MagicMock()
        captured = {}

        def callback(*_args, **_kwargs):
            def register(fn):
                captured[getattr(fn, "__name__", "fn")] = fn
                return fn

            return register

        app.callback.side_effect = callback
        panel.register_callbacks(app)
        fn = captured["update_snapshots_table"]
        with patch.object(panel, "_fetch_snapshots_handler", return_value={"snapshots": _fake_files(3), "total": 27903, "message": None}):
            rows, status_text, empty_style, store = fn(0, 0, None, None)
        assert status_text == "Showing newest 3 of 27903 snapshot(s)"
        assert len(rows) == 3
        assert empty_style == {"display": "none"}
        # The ledger's secondary observation ("data-snapshot-id on zero
        # elements") was zero ROWS — the attrs are on every rendered row.
        actions_div = rows[0].children[3].children
        assert getattr(actions_div, "data-snapshot-id", None) or "data-snapshot-id" in str(actions_div)

    def test_status_line_plain_when_not_truncated(self, panel):
        app = MagicMock()
        captured = {}

        def callback(*_args, **_kwargs):
            def register(fn):
                captured[getattr(fn, "__name__", "fn")] = fn
                return fn

            return register

        app.callback.side_effect = callback
        panel.register_callbacks(app)
        fn = captured["update_snapshots_table"]
        with patch.object(panel, "_fetch_snapshots_handler", return_value={"snapshots": _fake_files(2), "total": 2, "message": None}):
            _rows, status_text, _empty, _store = fn(0, 0, None, None)
        assert status_text == "2 snapshot(s) found"
