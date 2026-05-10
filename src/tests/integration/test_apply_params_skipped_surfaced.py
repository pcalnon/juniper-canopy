"""§1.5 C1a (Issue #1) — adapter surfaces ``skipped`` keys end-to-end.

Three layers covered:

1. ``CascorServiceAdapter.apply_params`` returns ``skipped`` in every code
   path (early-return-no-mapped, success, REST failure).
2. ``DemoMode.apply_params`` returns the same shape so the response handler
   in ``main.py`` can extract ``skipped`` uniformly.
3. ``POST /api/set_params`` threads ``skipped`` into the response JSON so
   the dashboard handler can surface it in the toast (the handler-side
   string-formatting is covered by a unit-style call against the handler
   below).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.cascor_service_adapter import CascorServiceAdapter

pytest.importorskip("juniper_cascor_client.testing", reason="juniper-cascor-client[testing] not installed")

from juniper_cascor_client.testing import FakeCascorClient  # noqa: E402


@pytest.fixture
def adapter():
    client = FakeCascorClient(scenario="two_spiral_training")
    yield CascorServiceAdapter(client=client)
    client.close()


# ---------------------------------------------------------------------------
# Layer 1 — adapter
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestAdapterSurfacesSkipped:
    def test_skipped_returned_when_no_mapped_keys(self, adapter):
        """All-canopy-only params take the no-mapped early-return path; skipped is the full input list."""
        result = adapter.apply_params(nn_spiral_rotations=3.0, nn_dataset_noise=0.05)
        assert result["ok"] is True
        assert result["skipped"] == ["nn_dataset_noise", "nn_spiral_rotations"], result
        assert result["data"] == {}

    def test_skipped_returned_alongside_mapped_keys(self, adapter):
        """Mixed call: some keys map (success path), some don't (skipped)."""
        result = adapter.apply_params(
            nn_learning_rate=0.05,
            nn_spiral_rotations=3.0,  # canopy-only, not in adapter map
        )
        assert result["ok"] is True
        # nn_spiral_rotations is canopy-only; nn_learning_rate is mapped.
        assert result["skipped"] == ["nn_spiral_rotations"], result

    def test_empty_skipped_when_all_keys_map(self, adapter):
        result = adapter.apply_params(nn_learning_rate=0.05, nn_max_hidden_units=64)
        assert result["ok"] is True
        assert result["skipped"] == [], result

    def test_skipped_returned_on_rest_failure(self, adapter):
        """Failure path also surfaces skipped — distinguishes 'rejected' from 'never sent'."""
        from juniper_cascor_client import JuniperCascorClientError

        # Force the underlying client.update_params to raise.
        with patch.object(adapter._client, "update_params", side_effect=JuniperCascorClientError("boom")):
            result = adapter.apply_params(nn_learning_rate=0.05, nn_spiral_rotations=3.0)
        assert result["ok"] is False
        assert result["error"] == "boom"
        assert result["skipped"] == ["nn_spiral_rotations"], result


# ---------------------------------------------------------------------------
# Layer 2 — demo backend
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestDemoModeReturnsSkipped:
    def test_demo_returns_skipped_shape_for_unknown_keys(self):
        """DemoMode.apply_params must match the adapter contract so main.py can
        thread ``skipped`` through uniformly regardless of which backend
        served the call."""
        from demo_mode import DemoMode

        # Skip the heavy network init — only need the apply_params method,
        # the lock, the per-attribute storage, and _update_training_state.
        demo = DemoMode.__new__(DemoMode)
        import threading

        demo._lock = threading.RLock()
        demo.training_state = None
        demo.network = MagicMock()
        demo.network.output_optimizer.param_groups = [{"lr": 0.01}]
        demo.logger = MagicMock()
        demo.max_hidden_units = 0
        demo.max_epochs = 0
        demo.convergence_enabled = True
        demo.convergence_threshold = 0.001
        demo.spiral_rotations = 3.0
        demo._update_training_state = lambda: None  # type: ignore[assignment]

        result = demo.apply_params(
            nn_learning_rate=0.05,  # known
            totally_made_up_key=42,  # genuinely unmapped
        )
        assert isinstance(result, dict)
        assert result["ok"] is True
        assert "totally_made_up_key" in result["skipped"]
        assert "nn_learning_rate" not in result["skipped"]


# ---------------------------------------------------------------------------
# Layer 3 — /api/set_params response handler (string formatting)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestDashboardToastSurfacesSkipped:
    """Pin the toast format the user sees when the adapter drops keys."""

    def _invoke_handler(self, response_json):
        """Drive ``DashboardManager._apply_parameters_handler`` with a stubbed
        ``requests.post`` so we exercise the toast-format branch without a
        live server."""
        from frontend.dashboard_manager import DashboardManager

        mgr = DashboardManager.__new__(DashboardManager)
        mgr.logger = MagicMock()
        mgr._api_url = lambda path: f"http://mock{path}"  # type: ignore[assignment]

        post_resp = MagicMock(status_code=200)
        post_resp.json.return_value = response_json
        get_resp = MagicMock(status_code=200, json=MagicMock(return_value={}))

        with patch("frontend.dashboard_manager.requests.post", return_value=post_resp), patch("frontend.dashboard_manager.requests.get", return_value=get_resp):
            return mgr._apply_parameters_handler(
                n_clicks=1,
                nn_max_iter=1,
                nn_max_epochs=1,
                nn_lr=0.05,
                nn_max_hu=1,
                nn_multi_node=[],
                nn_growth_trigger="convergence",
                nn_growth_epochs=1,
                nn_growth_conv_thresh=0.001,
                nn_patience=1,
                nn_spiral_rot=1.0,
                nn_spiral_num=2,
                nn_dataset_elem=10,
                nn_dataset_noise=0.0,
                cn_pool_size=8,
                cn_corr_thresh=0.5,
                cn_selected=1,
                cn_training_complete="patience",
                cn_training_iter=10,
                cn_training_conv_thresh=0.001,
                cn_patience=10,
                cn_multi_cand=[],
                cn_cand_selection="top",
                cn_top_cands=1,
                cn_random_cands=0,
            )

    def test_toast_blanket_message_when_no_skipped(self):
        _, msg = self._invoke_handler({"status": "success", "state": {}})
        assert msg == "Parameters applied", msg

    def test_toast_lists_skipped_keys(self):
        skipped = ["nn_dataset_noise", "nn_spiral_rotations"]
        _, msg = self._invoke_handler({"status": "success", "state": {}, "skipped": skipped})
        assert "Applied" in msg
        assert "of" in msg
        assert "not yet supported" in msg
        for k in skipped:
            assert k in msg, f"toast {msg!r} missing {k!r}"

    def test_toast_truncates_long_skipped_with_ellipsis(self):
        skipped = [f"key_{i}" for i in range(8)]
        _, msg = self._invoke_handler({"status": "success", "state": {}, "skipped": skipped})
        assert msg.endswith("…"), msg
        # First 5 listed; rest summarised by the ellipsis.
        for k in skipped[:5]:
            assert k in msg
        assert "key_5" not in msg
