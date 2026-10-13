"""N5 (I-4 / T1 / T3) — Apply-params UX end-to-end.

Covers the four behaviors of the apply-params UX unit:

1. Backend-seeded / submitted values are clamped to cascor's PATCH bounds at
   init and before apply (``CascorPatchBounds``) so an out-of-range value can't
   wholesale-422 the form; the clamp is flagged in the toast.
2. The failure toast carries the upstream rejection detail verbatim (truncated)
   instead of the bare status code.
3. cascor's C2a ``applied`` / ``skipped(reason)`` partition reaches the user:
   the adapter surfaces it, ``/api/set_params`` threads it, the toast renders it.
4. The WS ``set_params`` leg is skipped (no burned ack window) when the control
   stream is not connected — consuming N2/CL2's honest liveness surface.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from frontend.dashboard_manager import DashboardManager

# ---------------------------------------------------------------------------
# Handler-drive helper (mirrors test_apply_params_skipped_surfaced.py)
# ---------------------------------------------------------------------------


def _make_manager():
    mgr = DashboardManager.__new__(DashboardManager)
    mgr.logger = MagicMock()
    mgr._api_url = lambda path: f"http://mock{path}"  # type: ignore[assignment]
    return mgr


def _drive_apply(mgr, *, post_status=200, post_json=None, post_text="", **overrides):
    """Invoke ``_apply_parameters_handler`` with a stubbed post/get.

    ``overrides`` replaces individual form values (defaults are all in-range).
    Returns ``(store_value, toast_msg, posted_json)``.
    """
    values = {
        "n_clicks": 1,
        "nn_max_iter": 1,
        "nn_max_epochs": 1000,
        "nn_lr": 0.05,
        "nn_max_hu": 64,
        "nn_multi_node": [],
        "nn_growth_trigger": "convergence",
        "nn_growth_epochs": 1,
        "nn_growth_conv_thresh": 0.001,
        "nn_patience": 50,
        "nn_spiral_rot": 1.0,
        "nn_spiral_num": 2,
        "nn_dataset_elem": 200,
        "nn_dataset_noise": 0.0,
        "cn_pool_size": 8,
        "cn_corr_thresh": 0.5,
        "cn_selected": 1,
        "cn_training_complete": "patience",
        "cn_training_iter": 10,
        "cn_training_conv_thresh": 0.001,
        "cn_patience": 10,
        "cn_multi_cand": [],
        "cn_cand_selection": "top",
        "cn_top_cands": 1,
        "cn_random_cands": 0,
    }
    values.update(overrides)

    post_resp = MagicMock(status_code=post_status)
    post_resp.text = post_text
    if post_json is None:
        post_resp.json.side_effect = ValueError("no json")
    else:
        post_resp.json.return_value = post_json
    get_resp = MagicMock(status_code=200, json=MagicMock(return_value={}))

    with patch("frontend.dashboard_manager.requests.post", return_value=post_resp) as mp, patch("frontend.dashboard_manager.requests.get", return_value=get_resp):
        store_value, msg = mgr._apply_parameters_handler(**values)
    posted_json = mp.call_args.kwargs.get("json") if mp.call_args else None
    return store_value, msg, posted_json


# ---------------------------------------------------------------------------
# Behavior 1 — clamp at apply + init
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestClampAtApplyAndInit:
    def test_apply_clamps_out_of_range_submission_before_post(self):
        """An out-of-range learning rate is clamped to cascor's ``le=10.0``
        BEFORE the POST, so the request carries the admissible value (not the
        doomed one), and the toast flags the clamp."""
        mgr = _make_manager()
        store, msg, posted = _drive_apply(mgr, post_json={"status": "success", "state": {}}, nn_lr=50.0, nn_max_hu=999999)
        assert posted["nn_learning_rate"] == 10.0
        assert posted["nn_max_hidden_units"] == 10000
        assert store["nn_learning_rate"] == 10.0  # store reflects what was applied
        assert "clamped to bounds" in msg
        assert "nn_learning_rate→10.0" in msg

    def test_apply_in_range_submission_has_no_clamp_note(self):
        mgr = _make_manager()
        _, msg, posted = _drive_apply(mgr, post_json={"status": "success", "state": {}})
        assert posted["nn_learning_rate"] == 0.05
        assert msg == "Parameters applied"

    def test_init_clamps_out_of_range_seeded_value(self):
        """A backend that echoes an out-of-range default seeds the form with the
        clamped (admissible) value — both the visible input and the store."""
        mgr = _make_manager()
        state = {"nn_learning_rate": 50.0, "nn_max_hidden_units": 999999}
        get_resp = MagicMock(status_code=200, json=MagicMock(return_value=state))
        with patch("frontend.dashboard_manager.requests.get", return_value=get_resp):
            result = mgr._init_params_from_backend_handler(1, {})
        assert result[2] == 10.0  # nn_lr output position
        assert result[3] == 10000  # nn_max_hu output position
        applied = result[-1]
        assert applied["nn_learning_rate"] == 10.0
        assert applied["nn_max_hidden_units"] == 10000

    def test_init_in_range_seed_is_unchanged(self):
        mgr = _make_manager()
        state = {"nn_learning_rate": 0.02}
        get_resp = MagicMock(status_code=200, json=MagicMock(return_value=state))
        with patch("frontend.dashboard_manager.requests.get", return_value=get_resp):
            result = mgr._init_params_from_backend_handler(1, {})
        assert result[2] == 0.02
        assert result[-1]["nn_learning_rate"] == 0.02


# ---------------------------------------------------------------------------
# Behavior 2 — verbatim rejection detail in the toast
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestVerbatimRejectionDetail:
    def test_toast_carries_502_backend_reason_verbatim(self):
        """The canopy 502 payload (``{"error": "Backend rejected parameters:
        <cascor detail>"}``) surfaces verbatim, not a bare ``Failed to apply
        (502)``."""
        mgr = _make_manager()
        payload = {"error": "Backend rejected parameters: [epochs_max le=1000000]"}
        _, msg, _ = _drive_apply(mgr, post_status=502, post_json=payload)
        assert "Backend rejected parameters" in msg
        assert "epochs_max le=1000000" in msg
        assert "502" in msg

    def test_toast_carries_422_structured_message(self):
        mgr = _make_manager()
        payload = {"error": {"message": "candidate pool triple invalid"}}
        _, msg, _ = _drive_apply(mgr, post_status=422, post_json=payload)
        assert "candidate pool triple invalid" in msg
        assert "422" in msg

    def test_toast_falls_back_to_raw_text_when_body_not_json(self):
        mgr = _make_manager()
        _, msg, _ = _drive_apply(mgr, post_status=500, post_json=None, post_text="upstream boom detail")
        assert "upstream boom detail" in msg

    def test_extract_detail_truncates_and_never_raises(self):
        resp = MagicMock(status_code=500)
        resp.json.side_effect = ValueError
        resp.text = "x" * 5000
        msg = DashboardManager._extract_apply_error_detail(resp)
        assert msg.startswith("Failed to apply (HTTP 500):")
        assert len(msg) < 400  # truncated


# ---------------------------------------------------------------------------
# Behavior 3 — render cascor's C2a applied / skipped(reason) partition
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestRenderAppliedSkipped:
    def test_toast_renders_skipped_detail_with_reasons(self):
        mgr = _make_manager()
        body = {
            "status": "success",
            "state": {},
            "applied": ["nn_learning_rate"],
            "skipped_detail": [{"key": "nn_max_total_epochs", "reason": "not-updatable"}],
        }
        _, msg, _ = _drive_apply(mgr, post_json=body)
        assert "skipped" in msg
        assert "nn_max_total_epochs (not-updatable)" in msg

    def test_adapter_skipped_list_takes_precedence_and_keeps_legacy_format(self):
        """The pre-existing ``skipped`` (list[str]) format is unchanged when
        present — the C1a contract other tests pin stays intact."""
        mgr = _make_manager()
        body = {"status": "success", "state": {}, "skipped": ["nn_bogus"]}
        _, msg, _ = _drive_apply(mgr, post_json=body)
        assert "not yet supported by the backend" in msg
        assert "nn_bogus" in msg

    def test_adapter_surfaces_cascor_partition_from_rest_envelope(self):
        pytest.importorskip("juniper_cascor_client.testing", reason="cascor-client[testing] not installed")
        from juniper_cascor_client.testing import FakeCascorClient

        from backend.cascor_service_adapter import CascorServiceAdapter

        client = FakeCascorClient(scenario="two_spiral_training")
        try:
            adapter = CascorServiceAdapter(client=client)
            c2a_envelope = {
                "data": {
                    "learning_rate": 0.05,
                    "patience": 40,
                    "applied": ["learning_rate", "patience"],
                    "skipped": [{"key": "epochs_max", "reason": "not-updatable"}],
                }
            }
            # Isolate the C2a partition extraction from the roundtrip verify: the
            # Fake's GET echoes its own stored config (not our injected envelope),
            # which would flag a benign mismatch unrelated to this behavior.
            with patch.object(adapter._client, "update_params", return_value=c2a_envelope), patch.object(adapter, "_verify_apply_roundtrip", return_value=None):
                result = adapter.apply_params(nn_learning_rate=0.05, nn_patience=40, nn_max_total_epochs=5000)
            assert result["ok"] is True
            assert set(result["applied"]) == {"nn_learning_rate", "nn_patience"}
            assert result["skipped_detail"] == [{"key": "nn_max_total_epochs", "reason": "not-updatable"}]
        finally:
            client.close()

    def test_adapter_partition_empty_on_pre_c2a_backend(self):
        pytest.importorskip("juniper_cascor_client.testing", reason="cascor-client[testing] not installed")
        from juniper_cascor_client.testing import FakeCascorClient

        from backend.cascor_service_adapter import CascorServiceAdapter

        client = FakeCascorClient(scenario="two_spiral_training")
        try:
            adapter = CascorServiceAdapter(client=client)
            result = adapter.apply_params(nn_learning_rate=0.05)  # Fake returns pre-C2a envelope
            assert result["ok"] is True
            assert result["applied"] == []
            assert result["skipped_detail"] == []
        finally:
            client.close()

    def test_set_params_route_threads_partition_into_response(self, client):
        """``POST /api/set_params`` surfaces the adapter's C2a partition so the
        dashboard can render it."""
        import main

        mock_backend = MagicMock()
        mock_backend.apply_params.return_value = {
            "ok": True,
            "skipped": [],
            "applied": ["nn_learning_rate"],
            "skipped_detail": [{"key": "nn_max_total_epochs", "reason": "not-updatable"}],
        }
        with patch.object(main, "backend", mock_backend):
            resp = client.post("/api/set_params", json={"nn_learning_rate": 0.05, "nn_max_total_epochs": 5000})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["applied"] == ["nn_learning_rate"]
        assert body["skipped_detail"] == [{"key": "nn_max_total_epochs", "reason": "not-updatable"}]


# ---------------------------------------------------------------------------
# Behavior 4 — skip the WS leg when the control stream is dead
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestLivenessGatedWsLeg:
    def _adapter(self):
        pytest.importorskip("juniper_cascor_client.testing", reason="cascor-client[testing] not installed")
        from juniper_cascor_client.testing import FakeCascorClient

        from backend.cascor_service_adapter import CascorServiceAdapter

        client = FakeCascorClient(scenario="two_spiral_training")
        return CascorServiceAdapter(client=client), client

    def test_hot_apply_skips_ws_when_disconnected_no_burned_window(self):
        adapter, client = self._adapter()
        try:
            supervisor = MagicMock()
            supervisor.is_connected = False
            adapter._control_supervisor = supervisor
            result = adapter._apply_params_hot({"learning_rate": 0.05})
            assert result is None  # caller falls straight through to REST
            supervisor.set_params.assert_not_called()  # the ack window is never opened
        finally:
            client.close()

    def test_hot_apply_skips_ws_when_supervisor_absent(self):
        adapter, client = self._adapter()
        try:
            adapter._control_supervisor = None
            assert adapter._apply_params_hot({"learning_rate": 0.05}) is None
        finally:
            client.close()

    def test_hot_apply_attempts_ws_when_connected(self, monkeypatch):
        adapter, client = self._adapter()
        try:
            supervisor = MagicMock()
            supervisor.is_connected = True
            supervisor.loop = MagicMock()
            adapter._control_supervisor = supervisor
            fake_future = MagicMock()
            fake_future.result.return_value = {"applied": ["learning_rate"]}
            monkeypatch.setattr(
                "backend.cascor_service_adapter.asyncio.run_coroutine_threadsafe",
                lambda coro, loop: fake_future,
            )
            result = adapter._apply_params_hot({"learning_rate": 0.05})
            assert result == {"applied": ["learning_rate"]}
        finally:
            client.close()
