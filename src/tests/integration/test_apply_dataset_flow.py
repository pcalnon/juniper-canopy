"""§3.5.1 + §3.5.2 P1 (Issue #3 Phase 1) — canopy adapter + route + demo
backend round-trips for the dataset stage / cancel / get-pending surface
landed in cascor #242.

Three layers:

  1. CascorServiceAdapter.stage_dataset / cancel_pending_dataset /
     get_pending_dataset thread the cascor REST envelope through to the
     ``{ok, data}`` shape main.py expects.
  2. DemoMode.stage_dataset etc. mirror that shape so the route handler
     doesn't have to special-case demo (Resolution log Q1).
  3. POST /api/stage_dataset and DELETE /api/cancel_pending_dataset return
     ``{status: "success", data: …}`` on success and 502 on backend
     rejection.

The dashboard callback wiring is a UX concern verified by the existing
PR-3 Playwright harness skeleton; this file pins the API contract.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.cascor_service_adapter import CascorServiceAdapter

pytest.importorskip("juniper_cascor_client.testing", reason="juniper-cascor-client[testing] not installed")


@pytest.fixture
def adapter():
    """Adapter with a bare MagicMock as the cascor client.

    The dataset stage/cancel/get_pending methods route through the client's
    ``_request`` escape hatch (FakeCascorClient doesn't expose dedicated
    methods); a MagicMock lets us pin the exact wire calls without needing
    any of the fake's other behavior.
    """
    fake_client = MagicMock()
    return CascorServiceAdapter(client=fake_client)


# ---------------------------------------------------------------------------
# Layer 1 — adapter
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestAdapterStageCancelGetPending:
    def test_stage_dataset_maps_canopy_keys_and_posts(self, adapter):
        adapter._client._request.return_value = {"status": "success", "data": {"status": "staged", "config": {"dataset_type": "spirals"}}}
        result = adapter.stage_dataset(
            nn_dataset_type="spirals",
            nn_dataset_elements=200,
            nn_dataset_noise=0.05,
            nn_spiral_rotations=2.5,
            nn_spiral_number=2,
            nn_unrelated_field="ignored",  # not in _DATASET_PARAM_MAP
        )
        assert result["ok"] is True
        # Verify the POST body was the cascor-namespace mapping (not canopy keys).
        call = adapter._client._request.call_args
        assert call.args[:2] == ("POST", "/training/dataset")
        body = call.kwargs["json"]
        assert body == {
            "dataset_type": "spirals",
            "n_samples": 200,
            "noise": 0.05,
            "rotations": 2.5,
            "n_spirals": 2,
        }
        # Unrelated field dropped, not forwarded.
        assert "nn_unrelated_field" not in body
        assert "unrelated" not in str(body)

    def test_stage_dataset_drops_none_values(self, adapter):
        adapter._client._request.return_value = {"data": {"status": "staged"}}
        adapter.stage_dataset(nn_dataset_type="xor", nn_dataset_elements=None)
        body = adapter._client._request.call_args.kwargs["json"]
        assert body == {"dataset_type": "xor"}, body  # n_samples=None dropped

    def test_stage_dataset_maps_generic_params_channel(self, adapter):
        # N7 (I-7): a non-spiral generator's schema-driven params ride the generic
        # ``nn_dataset_params`` canopy key -> cascor's StageDatasetRequest.params, alongside the
        # typed convenience fields, so the staging dialect is preserved.
        adapter._client._request.return_value = {"data": {"status": "staged"}}
        adapter.stage_dataset(nn_dataset_type="mnist", nn_dataset_params={"dataset": "fashion_mnist", "n_samples": 512})
        body = adapter._client._request.call_args.kwargs["json"]
        assert body == {"dataset_type": "mnist", "params": {"dataset": "fashion_mnist", "n_samples": 512}}, body

    def test_stage_dataset_surfaces_client_error(self, adapter):
        from juniper_cascor_client import JuniperCascorClientError

        adapter._client._request.side_effect = JuniperCascorClientError("422 Unknown dataset")
        result = adapter.stage_dataset(nn_dataset_type="lottery")
        assert result["ok"] is False
        assert "422" in result["error"]

    def test_cancel_pending_dataset_calls_delete(self, adapter):
        adapter._client._request.return_value = {"data": {"status": "cleared", "discarded": {"dataset_type": "spirals"}}}
        result = adapter.cancel_pending_dataset()
        assert result["ok"] is True
        assert adapter._client._request.call_args.args[:2] == ("DELETE", "/training/dataset")
        assert result["data"]["status"] == "cleared"

    def test_get_pending_dataset_returns_pending_field(self, adapter):
        adapter._client._request.return_value = {"data": {"pending": {"dataset_type": "spirals", "n_samples": 200}}}
        result = adapter.get_pending_dataset()
        assert result["ok"] is True
        assert result["pending"] == {"dataset_type": "spirals", "n_samples": 200}

    def test_get_pending_dataset_handles_null(self, adapter):
        adapter._client._request.return_value = {"data": {"pending": None}}
        result = adapter.get_pending_dataset()
        assert result["ok"] is True
        assert result["pending"] is None


# ---------------------------------------------------------------------------
# Layer 2 — demo backend
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestDemoBackendStageCancelGetPending:
    def _bare_demo(self):
        """Minimal DemoMode skipping the heavy network/dataset init — just
        enough to exercise stage / cancel / get_pending without firing up
        torch."""
        from demo_mode import DemoMode

        demo = DemoMode.__new__(DemoMode)
        import threading

        demo._lock = threading.Lock()
        demo._pending_dataset_config = None
        demo.logger = MagicMock()
        return demo

    def test_demo_stage_then_cancel_round_trip(self):
        demo = self._bare_demo()
        result = demo.stage_dataset(nn_dataset_type="xor", nn_dataset_elements=100)
        assert result["ok"] is True
        assert result["data"]["status"] == "staged"
        assert result["data"]["config"] == {"nn_dataset_type": "xor", "nn_dataset_elements": 100}

        peek = demo.get_pending_dataset()
        assert peek["pending"] == {"nn_dataset_type": "xor", "nn_dataset_elements": 100}

        cancel = demo.cancel_pending_dataset()
        assert cancel["ok"] is True
        assert cancel["data"]["status"] == "cleared"
        assert cancel["data"]["discarded"] == {"nn_dataset_type": "xor", "nn_dataset_elements": 100}

        assert demo.get_pending_dataset()["pending"] is None

    def test_demo_empty_stage_clears(self):
        demo = self._bare_demo()
        demo.stage_dataset(nn_dataset_type="xor")
        assert demo.get_pending_dataset()["pending"] == {"nn_dataset_type": "xor"}
        result = demo.stage_dataset()
        assert result["data"]["status"] == "cleared"
        assert demo.get_pending_dataset()["pending"] is None


# ---------------------------------------------------------------------------
# Layer 3 — route (N7 generic-params staging channel through the real request model)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestStageDatasetRouteGenericParams:
    """N7 (I-7): POST /api/stage_dataset accepts the generic ``nn_dataset_params`` dict.

    Exercises the real ``StageDatasetRequest`` (the field addition) + route through canopy's demo
    backend (which mirrors the cascor stage shape), proving a non-spiral generator's schema-driven
    params survive validation and reach the backend unflattened.
    """

    def test_route_accepts_and_forwards_generic_params(self, client):
        body = {"nn_dataset_type": "mnist", "nn_dataset_params": {"dataset": "fashion_mnist", "n_samples": 512, "flatten": True}}
        resp = client.post("/api/stage_dataset", json=body)
        assert resp.status_code == 200, resp.text
        config = resp.json()["data"]["config"]
        assert config["nn_dataset_type"] == "mnist"
        assert config["nn_dataset_params"] == {"dataset": "fashion_mnist", "n_samples": 512, "flatten": True}

    def test_route_still_accepts_legacy_spiral_body(self, client):
        # Back-compat: the legacy typed-only body is unchanged (no params key required).
        resp = client.post("/api/stage_dataset", json={"nn_dataset_type": "spirals", "nn_dataset_elements": 200})
        assert resp.status_code == 200, resp.text
        config = resp.json()["data"]["config"]
        assert config == {"nn_dataset_type": "spirals", "nn_dataset_elements": 200}
