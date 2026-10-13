"""
A-N5, second half: the **unknown** availability state must be reachable from the outage it
was built for, and ``⊥`` must not be reported as a conflict.

canopy#653 built the third availability state and pinned it from ``_fetch_generators``
downwards. Every one of its tests drove the failure by making ``requests.get`` raise — which
simulates *canopy's own* route being unreachable from the dashboard process. The motivating
case was **juniper-data** being down, and that case never produced ``None``:

    dashboard  --GET /api/dataset/generators-->  canopy  --GET /v1/generators-->  juniper-data
                                                   |                                   X down
                                                   +-- caught, logged at debug, and answered
                                                       HTTP 200 with four built-in demo
                                                       generators carrying no ``available`` flag

So ``resp.ok`` was true, a list came back, ``availability_is_known`` was true, no caveat
rendered, and ``is_generator_available`` fail-open reported ``equities_seq`` selectable against
a service that was not running — verbatim the complaint A-N5 was filed for.

The defect was never in ``_fetch_generators``; it was that the route made an outage and an
answer **indistinguishable**, and #653's fixture could not see the difference because it
mocked the near seam rather than the far one. These tests therefore span the whole chain:
route behaviour, consumer behaviour, and the gate notice the operator actually sees.

Second defect pinned here (canopy#652): with the dataset already ``⊥``, a gate re-fire
announced *"none is not compatible with CasCor … so it was cleared"* — a state change that
did not happen, naming a dataset that does not exist. Reachable the moment #652 made ``⊥`` a
state the gate clears into.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

REPO = Path(__file__).resolve().parents[3]
SRC = REPO / "src"
if str(SRC) not in sys.path:  # pragma: no cover - import side effect
    sys.path.insert(0, str(SRC))

import main  # noqa: E402
from dataset_schema import availability_is_known  # noqa: E402
from frontend.dashboard_manager import DashboardManager  # noqa: E402


@pytest.fixture
def dm():
    manager = DashboardManager({})
    manager._generators_cache = None  # the TTL cache would otherwise leak between cases
    return manager


def _response(payload, ok=True, status=200):
    resp = Mock()
    resp.ok = ok
    resp.status_code = status
    resp.json.return_value = payload
    return resp


class _FakeGetClient:
    def __init__(self, payload, status_code=200, raises=None):
        self._payload = payload
        self._status_code = status_code
        self._raises = raises

    async def get(self, *args, **kwargs):
        if self._raises is not None:
            raise self._raises
        resp = Mock()
        resp.status_code = self._status_code
        resp.json.return_value = self._payload
        return resp


class _FakeGetClientCM:
    def __init__(self, payload, status_code=200, raises=None):
        self._inner = _FakeGetClient(payload, status_code=status_code, raises=raises)

    async def __aenter__(self):
        return self._inner

    async def __aexit__(self, *args):
        return False


@pytest.mark.regression
@pytest.mark.unit
class TestTheRouteDistinguishesAnOutageFromAnAnswer:
    """The far seam. Without this the near seam cannot be right, whatever it does."""

    @pytest.mark.asyncio
    async def test_an_unreachable_juniper_data_is_flagged(self, monkeypatch):
        monkeypatch.setattr(main, "juniper_data_available", True)
        with patch("httpx.AsyncClient", return_value=_FakeGetClientCM(None, raises=OSError("connection refused"))):
            result = await main.list_dataset_generators()
        assert result["upstream_unavailable"] is True
        # The fallback list is still served -- this is a caveat, never a denial of service.
        assert {g["name"] for g in result["generators"]} >= {"spiral", "xor", "circles", "moon"}

    @pytest.mark.asyncio
    async def test_a_refusing_juniper_data_is_flagged(self, monkeypatch):
        """401/403 is a misconfiguration, not an answer. Y5 was this branch going quiet."""
        monkeypatch.setattr(main, "juniper_data_available", True)
        with patch("httpx.AsyncClient", return_value=_FakeGetClientCM({}, status_code=401)):
            result = await main.list_dataset_generators()
        assert result["upstream_unavailable"] is True

    @pytest.mark.asyncio
    async def test_a_live_juniper_data_is_not_flagged(self, monkeypatch):
        monkeypatch.setattr(main, "juniper_data_available", True)
        payload = {"generators": [{"name": "equities_seq", "available": False}]}
        with patch("httpx.AsyncClient", return_value=_FakeGetClientCM(payload)):
            result = await main.list_dataset_generators()
        assert result["upstream_unavailable"] is False

    @pytest.mark.asyncio
    async def test_demo_mode_is_known_not_unknown(self, monkeypatch):
        """An UNCONFIGURED deployment is not a broken one.

        Nothing was attempted, so nothing failed: the built-in four ARE the offering there.
        Flagging this would make the caveat permanent in demo mode, which trains the operator
        to ignore it -- and the caveat is the only thing that will speak during a real outage.
        """
        monkeypatch.setattr(main, "juniper_data_available", False)
        result = await main.list_dataset_generators()
        assert result["upstream_unavailable"] is False


@pytest.mark.regression
@pytest.mark.unit
class TestTheConsumerTranslatesTheFlagToUnknown:
    def test_the_flag_makes_availability_unknown(self, dm):
        payload = {"generators": [{"name": "spiral"}], "upstream_unavailable": True}
        with patch("frontend.dashboard_manager.requests.get", return_value=_response(payload)):
            assert dm._fetch_generators() is None

    def test_a_clean_answer_is_still_a_list(self, dm):
        payload = {"generators": [{"name": "spiral"}], "upstream_unavailable": False}
        with patch("frontend.dashboard_manager.requests.get", return_value=_response(payload)):
            assert dm._fetch_generators() == [{"name": "spiral"}]

    def test_a_payload_without_the_key_is_still_known(self, dm):
        """Back-compat: an older canopy answering this route must not read as an outage."""
        with patch("frontend.dashboard_manager.requests.get", return_value=_response({"generators": []})):
            assert dm._fetch_generators() == []


@pytest.mark.regression
@pytest.mark.unit
class TestTheOutageReachesTheOperator:
    """The load-bearing test: everything above is plumbing if the notice never renders."""

    def test_a_down_juniper_data_raises_the_unknown_caveat(self, dm):
        payload = {"generators": [{"name": "spiral"}], "upstream_unavailable": True}
        with patch("frontend.dashboard_manager.requests.get", return_value=_response(payload)):
            generators = dm._fetch_generators()
            assert not availability_is_known(generators)
            _options, _value, notice = dm._gate_dataset_options_handler("cascor", "spirals", generators=generators)
        assert notice is not None, "a down juniper-data must say so; this is the A-N5 defect"
        assert "spirals" not in str(notice).lower() or "cleared" not in str(notice).lower()

    def test_a_live_juniper_data_raises_no_caveat(self, dm):
        payload = {"generators": [{"name": "spirals", "available": True}], "upstream_unavailable": False}
        with patch("frontend.dashboard_manager.requests.get", return_value=_response(payload)):
            generators = dm._fetch_generators()
            _options, _value, notice = dm._gate_dataset_options_handler("cascor", "spirals", generators=generators)
        assert notice is None


@pytest.mark.regression
@pytest.mark.unit
class TestBottomIsNotAConflict:
    """canopy#652 follow-up. ``⊥`` is where the gate CLEARS TO, so it re-enters here."""

    @pytest.mark.parametrize("model_key", ["cascor", "recurrence"])
    def test_no_cleared_notice_when_nothing_was_selected(self, dm, model_key):
        _options, _value, notice = dm._gate_dataset_options_handler(model_key, None, generators=[])
        assert notice is None, "nothing was cleared, so nothing may claim it was"

    @pytest.mark.parametrize("model_key", ["cascor", "recurrence"])
    def test_the_literal_string_none_is_never_shown(self, dm, model_key):
        """``_dataset_label(None)`` renders 'none'. The operator must never read it."""
        _options, _value, notice = dm._gate_dataset_options_handler(model_key, None, generators=[])
        assert "none is not compatible" not in str(notice)

    def test_a_real_conflict_still_clears_and_says_so(self, dm):
        """The control. Fixing the false alert must not silence the true one."""
        _options, value, notice = dm._gate_dataset_options_handler("recurrence", "spirals", generators=[])
        assert value is None
        assert "Spirals" in str(notice) and "cleared" in str(notice).lower()
