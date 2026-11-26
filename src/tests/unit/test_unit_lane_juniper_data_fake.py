"""
Pin the unit lane's juniper-data fake (``src/tests/conftest.py``, UNIT-LANE JUNIPER-DATA FAKE).

The app reaches juniper-data (:8100) through httpx: its startup probe, ``/v1/health/ready`` and the
generators proxy. In a guarded test those requests are answered in-process at httpx's async
transport, and the network guard refuses, and fails, any connect to :8100 that reaches a socket.
These tests pin the fake's contract (what it answers, for which requests, and when it stands aside)
and that the code above the seam runs for real against it: the lifespan's ``juniper_data_available``
decision and the generators proxy with its fallback. ``test_health.py`` pins probe_dependency's
mapping of each answer and the readiness verdict the same way.

No case here reaches a Juniper service: the fake answers before any socket opens, the guard refuses
:8100 if one did, and the two cases that make a real connect aim it at port 9, where nothing
listens, which the kernel refuses.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

import main as main_module

pytestmark = pytest.mark.unit

PROBE = "GET http://localhost:8100/v1/health/live"
GENERATORS = [{"name": "spiral", "display_name": "Spiral (juniper-data)"}]


@pytest.fixture
def unanswered_port():
    """Port 9 on 127.0.0.1, where nothing listens: a connect there is refused at once, as on an empty host.

    It is the closed port ``src/tests/regression/test_x7_client_budget.py`` relies on. A port this test binds
    and never listens on is not used: Linux refuses a connect to it, but CI's macOS runner let it time out
    (``httpx.ConnectTimeout``).
    """
    return 9


async def _get(url: str) -> httpx.Response:
    async with httpx.AsyncClient(timeout=5.0) as http:
        return await http.get(url)


def test_the_fake_is_armed_with_the_guard(service_port_guard, juniper_data_fake, request):
    assert service_port_guard.armed_for == request.node.nodeid
    assert juniper_data_fake.intercepts(httpx.Request("GET", "http://localhost:8100/v1/health/live"))
    assert juniper_data_fake.intercepts(httpx.Request("GET", "http://juniper-data:8100/v1/generators"))
    assert not juniper_data_fake.intercepts(httpx.Request("GET", "http://localhost:8101/v1/health/live"))
    assert not juniper_data_fake.intercepts(httpx.Request("GET", "http://localhost:8050/v1/health/live"))


@pytest.mark.allow_service_ports
def test_the_fake_stands_aside_where_the_guard_is_disarmed(service_port_guard, juniper_data_fake):
    """A test the guard does not arm reaches whatever listens on :8100, so the fake answers nothing there (no request is sent)."""
    assert service_port_guard.armed_for is None
    assert not juniper_data_fake.intercepts(httpx.Request("GET", "http://localhost:8100/v1/health/live"))


async def test_a_request_to_juniper_data_is_refused_in_process(service_port_guard, juniper_data_fake):
    with pytest.raises(httpx.ConnectError, match="^All connection attempts failed$"):
        await _get("http://localhost:8100/v1/health/live")
    assert juniper_data_fake.answered == [PROBE]
    assert service_port_guard.take() == []  # no socket was opened: the guard saw nothing


async def test_the_refusal_is_what_an_empty_host_gives(juniper_data_fake, unanswered_port):
    """The default answer equals httpx's own error for a connect the kernel refused, so the probe's message is CI's."""
    with pytest.raises(httpx.ConnectError) as faked:
        await _get("http://127.0.0.1:8100/v1/health/live")
    with pytest.raises(httpx.ConnectError) as real:
        await _get(f"http://127.0.0.1:{unanswered_port}/v1/health/live")
    assert str(faked.value) == str(real.value) == juniper_data_fake.refusal
    assert juniper_data_fake.answered == ["GET http://127.0.0.1:8100/v1/health/live"]


async def test_an_answer_is_served_to_every_request_until_refuse(juniper_data_fake):
    juniper_data_fake.answer(200, {"status": "alive"})
    first = await _get("http://localhost:8100/v1/health/live")
    second = await _get("http://127.0.0.1:8100/v1/generators")
    assert (first.status_code, first.json(), second.status_code, second.json()) == (200, {"status": "alive"}, 200, {"status": "alive"})
    juniper_data_fake.refuse()
    with pytest.raises(httpx.ConnectError):
        await _get("http://localhost:8100/v1/health/live")
    assert juniper_data_fake.answered == [PROBE, "GET http://127.0.0.1:8100/v1/generators", PROBE]


async def test_another_port_is_not_answered(juniper_data_fake, unanswered_port):
    with pytest.raises(httpx.ConnectError):
        await _get(f"http://127.0.0.1:{unanswered_port}/v1/health/live")
    assert juniper_data_fake.answered == []


def test_a_leaves_an_answer_behind(_juniper_data_fake_transport):
    """With the next test, pins the reset before every test: this one changes the fake without the resetting fixture."""
    _juniper_data_fake_transport.answer(200, {"status": "alive"})
    _juniper_data_fake_transport.answered.append(PROBE)


def test_b_starts_from_the_default(_juniper_data_fake_transport):
    assert _juniper_data_fake_transport.response is None
    assert _juniper_data_fake_transport.answered == []


class TestTheStartupProbeAgainstTheFake:
    """main.py's lifespan probe, run for real against the fake: what it sends and what it concludes.

    Each test starts its own app (no module-scoped ``client``), so the fake's answer is set before the
    lifespan runs, and restores ``main.juniper_data_available``, which a healthy probe sets for the rest
    of the process.
    """

    def test_a_refused_probe_leaves_juniper_data_unavailable(self, juniper_data_fake, monkeypatch):
        monkeypatch.setattr(main_module, "juniper_data_available", False)
        with TestClient(main_module.app) as app_client:
            body = app_client.get("/v1/health").json()
        assert juniper_data_fake.answered == [PROBE]
        assert body["juniper_data_available"] is False

    def test_a_healthy_probe_makes_juniper_data_available(self, juniper_data_fake, monkeypatch):
        monkeypatch.setattr(main_module, "juniper_data_available", False)
        juniper_data_fake.answer(200, {"status": "alive"})
        with TestClient(main_module.app) as app_client:
            body = app_client.get("/v1/health").json()
        assert juniper_data_fake.answered == [PROBE]
        assert body["juniper_data_available"] is True

    def test_juniper_data_generators_are_served_once_it_is_up(self, juniper_data_fake, monkeypatch):
        """The generators proxy, which only a healthy startup probe opens, relays juniper-data's list."""
        monkeypatch.setattr(main_module, "juniper_data_available", False)
        juniper_data_fake.answer(200, GENERATORS)
        with TestClient(main_module.app) as app_client:
            body = app_client.get("/api/dataset/generators").json()
        assert juniper_data_fake.answered == [PROBE, "GET http://localhost:8100/v1/generators"]
        assert body == {"generators": GENERATORS, "upstream_unavailable": False}

    def test_a_juniper_data_that_stops_answering_is_reported_unknown(self, juniper_data_fake, monkeypatch):
        """canopy#653's ``unknown`` state: up at startup, refused later, so the built-in list is served and flagged."""
        monkeypatch.setattr(main_module, "juniper_data_available", False)
        juniper_data_fake.answer(200, {"status": "alive"})
        with TestClient(main_module.app) as app_client:
            juniper_data_fake.refuse()
            body = app_client.get("/api/dataset/generators").json()
        assert juniper_data_fake.answered == [PROBE, "GET http://localhost:8100/v1/generators"]
        assert body["upstream_unavailable"] is True
        assert [generator["name"] for generator in body["generators"]] == ["spiral", "xor", "circles", "moon"]

    def test_the_configured_juniper_data_url_is_the_one_asked(self, juniper_data_fake, monkeypatch):
        """The fake answers port 8100 whatever the host, so only the recorded URLs show that the startup probe, the
        generators proxy and /v1/health/ready use the configured juniper-data URL, not the default one."""
        monkeypatch.setattr(main_module, "juniper_data_available", False)
        monkeypatch.setattr(main_module.settings, "juniper_data_url", "http://juniper-data.invalid:8100")
        juniper_data_fake.answer(200, GENERATORS)
        with TestClient(main_module.app) as app_client:
            app_client.get("/api/dataset/generators")
            app_client.get("/v1/health/ready")
        configured = "http://juniper-data.invalid:8100"
        assert juniper_data_fake.answered == [f"GET {configured}/v1/health/live", f"GET {configured}/v1/generators", f"GET {configured}/v1/health/live"]

    def test_every_request_to_juniper_data_carries_a_5_second_timeout(self, juniper_data_fake, monkeypatch):
        """A hung juniper-data must cost canopy's startup, /v1/health/ready and the generators proxy 5 s each, not forever."""
        monkeypatch.setattr(main_module, "juniper_data_available", False)
        seen = []
        respond = juniper_data_fake.respond

        def recording_respond(request):
            seen.append((request.url.path, request.extensions.get("timeout")))
            return respond(request)

        monkeypatch.setattr(juniper_data_fake, "respond", recording_respond)
        juniper_data_fake.answer(200, GENERATORS)
        with TestClient(main_module.app) as app_client:
            app_client.get("/api/dataset/generators")
            app_client.get("/v1/health/ready")
        five = {"connect": 5.0, "read": 5.0, "write": 5.0, "pool": 5.0}
        assert seen == [("/v1/health/live", five), ("/v1/generators", five), ("/v1/health/live", five)]
