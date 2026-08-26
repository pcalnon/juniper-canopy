"""F-CANOPY-011 / D-0 regression: the Network Editor must read the FSM from the
key canopy's ``/api/status`` actually returns, and fetch the topology route
canopy actually serves.

Both found live in the canopy E2E arc (juniper-ml evidence note):

* F-CANOPY-011 -- the panel read ``status["state_machine"]["status"]`` (cascor's
  own ``/v1/training/status`` schema) while canopy's ``/api/status`` is a flat
  dict whose FSM field is ``fsm_status``. ``_is_investigating`` was therefore
  False unconditionally: the badge read ``FSM: Unknown`` and the whole active
  editing surface (add / remove / patch) was unreachable even with the FSM
  genuinely INVESTIGATING. The docstring asserted the wrong contract in prose.
* D-0 -- once active, the panel fetched ``/api/network/topology`` (404); the
  route canopy serves is ``/api/topology``. Fixing either alone leaves the
  panel dead, which is why the two ride together.

The contract tests below hit the REAL routes through ``main.app`` rather than a
hand-built payload, so the panel's key and route choices are pinned to what
canopy really serves.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

src_dir = Path(__file__).parents[3]
sys.path.insert(0, str(src_dir))

import pytest

from frontend.components.network_editor_panel import NetworkEditorPanel

BASE = "http://localhost:8050"
REAL_TOPOLOGY = {"input_units": 2, "output_units": 2, "hidden_units": 10, "nodes": [], "connections": []}


class _StubApp:
    def __init__(self):
        self.callbacks = []

    def callback(self, *outputs, **kwargs):
        def decorator(fn):
            self.callbacks.append((outputs, kwargs, fn))
            return fn

        return decorator


@pytest.fixture
def panel():
    return NetworkEditorPanel({"api_base_url": BASE}, component_id="ne-f011")


@pytest.fixture
def callbacks(panel):
    app = _StubApp()
    panel.register_callbacks(app)
    return {fn.__name__: fn for _, _, fn in app.callbacks}


@pytest.fixture
def client(monkeypatch):
    """Real ``main.app`` with a real (demo) backend installed.

    A bare ``TestClient(app)`` never runs the lifespan, so ``main.backend``
    is ``None`` and every backend-backed route 500s; install the demo
    backend the same way the regression contract tests do.
    """
    from fastapi.testclient import TestClient

    import main
    from backend.demo_backend import DemoBackend
    from demo_mode import DemoMode

    monkeypatch.setattr(main, "backend", DemoBackend(DemoMode(update_interval=1.0)))
    return TestClient(main.app)


def _status(payload):
    resp = MagicMock(status_code=200)
    resp.json.return_value = payload
    return resp


@pytest.mark.unit
class TestF011FsmKeyContract:
    def test_status_result_contract_declares_fsm_status_not_state_machine(self):
        """The typed contract every backend's get_status() honours."""
        from backend.protocol import StatusResult

        keys = set(StatusResult.__annotations__)
        assert "fsm_status" in keys
        assert "state_machine" not in keys

    def test_real_api_status_is_flat_and_carries_fsm_status(self, client, panel):
        """Pin the key to the REAL route: canopy never nests state_machine."""
        resp = client.get("/api/status")
        assert resp.status_code == 200
        payload = resp.json()
        assert "fsm_status" in payload
        assert "state_machine" not in payload
        # The real shape with the FSM flipped to INVESTIGATING must gate the
        # panel open -- on the parent this was False for every payload canopy
        # can produce.
        assert panel._is_investigating({**payload, "fsm_status": "INVESTIGATING"}) is True

    @pytest.mark.parametrize("value", ["INVESTIGATING", "Investigating", "investigating"])
    def test_flat_fsm_status_investigating(self, panel, value):
        assert panel._is_investigating({"fsm_status": value}) is True

    @pytest.mark.parametrize("value", ["idle", "STARTED", "Stopped", "Paused", "REPLAYING", "Completed", ""])
    def test_flat_fsm_status_other_states_rejected(self, panel, value):
        assert panel._is_investigating({"fsm_status": value}) is False

    def test_poll_flips_active_and_badge_from_the_flat_payload(self, callbacks):
        with patch("requests.get", side_effect=[_status({"fsm_status": "INVESTIGATING", "phase": "IDLE", "is_training": False}), _status(REAL_TOPOLOGY)]):
            idle, active, badge, topology = callbacks["poll_fsm_and_topology"](1)
        assert idle == {"display": "none"}
        assert active == {"display": "block"}
        assert badge == "FSM: Investigating"
        assert topology == REAL_TOPOLOGY

    def test_badge_names_the_flat_state_when_not_investigating(self, callbacks):
        with patch("requests.get", return_value=_status({"fsm_status": "STOPPED", "phase": "IDLE"})):
            idle, active, badge, topology = callbacks["poll_fsm_and_topology"](1)
        assert badge == "FSM: Stopped"
        assert idle == {"display": "block"}
        assert active == {"display": "none"}
        assert topology is None


@pytest.mark.unit
class TestD0TopologyRouteContract:
    def test_poll_fetches_the_route_canopy_serves(self, callbacks):
        with patch("requests.get", side_effect=[_status({"fsm_status": "INVESTIGATING"}), _status(REAL_TOPOLOGY)]) as get:
            callbacks["poll_fsm_and_topology"](1)
        urls = [call.args[0] for call in get.call_args_list]
        assert urls == [f"{BASE}/api/status", f"{BASE}/api/topology"]

    def test_canopy_serves_api_topology_not_api_network_topology(self, client):
        assert client.get("/api/network/topology").status_code == 404
        assert client.get("/api/topology").status_code in (200, 503)

    def test_render_topology_consumes_the_real_route_shape(self, callbacks):
        readout, options = callbacks["render_topology"](REAL_TOPOLOGY)
        assert options == [{"label": f"Unit {i}", "value": i} for i in range(10)]
        assert "Inputs: 2" in str(readout)
        assert "Hidden units: 10" in str(readout)
