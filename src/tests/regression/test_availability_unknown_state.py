"""
Pin the third availability state: **unknown**, as distinct from available and unavailable.

`_fetch_generators` returned `[]` for three different outcomes — an exception, a non-ok
response, and a 200 with an empty payload — and the availability helpers read every generator
as available in all of them (the flag-absent fallback). So the panel looked identical whether
juniper-data had answered "everything is fine" or had not answered at all, and nothing in
canopy could tell the two apart.

**The gating is deliberately unchanged.** Fail-open is the ratified two-tier posture (D5): the
UI is a best-effort affordance, the backend is the correctness guarantee and still refuses with
a 501 install hint. Failing closed on a transient blip would strand the operator, which is the
outcome fail-open exists to prevent. What this adds is the ability to SAY which state we are
in, so a confident-looking panel is not built on nothing.

Note what was untested before: every existing stub of `_fetch_generators` returns a successful
list, so the failure path had no coverage at all. That is part of why the collapse survived.
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

from dataset_schema import availability_is_known, availability_map, is_generator_available  # noqa: E402
from frontend.dashboard_manager import DashboardManager  # noqa: E402


@pytest.fixture
def dm():
    manager = DashboardManager({})
    manager._generators_cache = None  # the TTL cache would otherwise leak between cases
    return manager


@pytest.mark.regression
@pytest.mark.unit
class TestTheThreeStatesAreDistinct:
    def test_none_is_unknown_and_empty_is_known(self):
        """The whole point: these were the same value, and they mean opposite things."""
        assert availability_is_known(None) is False
        assert availability_is_known([]) is True
        assert availability_is_known([{"name": "spiral", "available": True}]) is True

    def test_unknown_does_not_become_unavailable(self):
        """Fail-open is preserved — unknown must not grey anything out."""
        assert is_generator_available("spirals", None) is True
        assert availability_map(None) == {}

    def test_a_known_unavailable_generator_is_still_unavailable(self):
        """The new state must not have softened the real one."""
        generators = [{"name": "mnist", "available": False}]
        assert availability_is_known(generators) is True
        assert is_generator_available("mnist", generators) is False


@pytest.mark.regression
@pytest.mark.unit
class TestFetchGeneratorsReportsWhetherItSucceeded:
    """The failure path of this function had no test at all before today."""

    def _response(self, *, ok=True, payload=None, status=200):
        resp = Mock()
        resp.ok = ok
        resp.status_code = status
        resp.json.return_value = payload if payload is not None else {}
        return resp

    def test_a_good_response_returns_the_list(self, dm):
        entries = [{"name": "spiral", "available": True}]
        with patch("frontend.dashboard_manager.requests.get", return_value=self._response(payload={"generators": entries})):
            assert dm._fetch_generators() == entries

    def test_an_exception_returns_unknown_not_empty(self, dm):
        with patch("frontend.dashboard_manager.requests.get", side_effect=OSError("connection refused")):
            assert dm._fetch_generators() is None

    def test_a_non_ok_response_returns_unknown_not_empty(self, dm):
        """Y5 (canopy#609) was this exact shape: a 401 read as an empty schema.

        The route ignored the status and every dataset's params panel said "No adjustable
        parameters" — an authoritative-sounding statement derived from a rejected request.
        """
        with patch("frontend.dashboard_manager.requests.get", return_value=self._response(ok=False, status=401)):
            assert dm._fetch_generators() is None

    def test_a_good_but_empty_response_is_known(self, dm):
        """A service that answers with no generators HAS answered. Known, not unknown."""
        with patch("frontend.dashboard_manager.requests.get", return_value=self._response(payload={"generators": []})):
            result = dm._fetch_generators()
        assert result == []
        assert availability_is_known(result) is True

    def test_the_unknown_result_is_cached_like_a_success(self, dm):
        """One request per TTL while the service is down, not one per gate callback.

        A failing service is exactly when canopy can least afford a request per callback, and
        the gate runs on every model change.
        """
        with patch("frontend.dashboard_manager.requests.get", side_effect=OSError("down")) as get:
            assert dm._fetch_generators() is None
            assert dm._fetch_generators() is None
        assert get.call_count == 1


@pytest.mark.regression
@pytest.mark.unit
class TestTheGateSaysSoWithoutChangingWhatItGates:
    def test_nothing_is_disabled_merely_because_availability_is_unknown(self, dm):
        options, _value, _notice = dm._gate_dataset_options_handler("cascor", "spirals", generators=None)
        cascor_compatible = [o for o in options if not o.get("disabled")]
        assert cascor_compatible, "unknown availability disabled every option — that is fail-CLOSED, and it is not the ratified posture"

    def test_the_caveat_is_raised_when_availability_is_unknown(self, dm):
        _options, _value, notice = dm._gate_dataset_options_handler("cascor", "spirals", generators=None)
        assert notice is not None, "availability was unknown and the operator was told nothing"
        assert notice.id == "dataset-gate-availability-unknown-alert"

    def test_no_caveat_when_availability_is_known(self, dm):
        _options, _value, notice = dm._gate_dataset_options_handler("cascor", "spirals", generators=[])
        assert notice is None, "a known-good fetch must not raise the unknown caveat"

    def test_the_caveat_persists_rather_than_auto_dismissing(self, dm):
        """The condition lasts while the service is down; an auto-dismiss would hide a live caveat."""
        _options, _value, notice = dm._gate_dataset_options_handler("cascor", "spirals", generators=None)
        assert getattr(notice, "duration", None) is None

    def test_the_caveat_does_not_claim_anything_is_unavailable(self, dm):
        """Everything is still selectable. Saying otherwise would be a different lie."""
        _options, _value, notice = dm._gate_dataset_options_handler("cascor", "spirals", generators=None)
        text = " ".join(str(child.children) for child in notice.children if hasattr(child, "children"))
        assert "unknown" in text.lower()
        assert "unavailable in this deployment" not in text.lower()

    def test_a_state_change_notice_still_wins_over_the_caveat(self, dm):
        """The cleared/empty-set notices describe something the operator just did.

        The caveat is a standing condition and must not displace them — one notice slot, and
        the event is more urgent than the background.
        """
        _options, value, notice = dm._gate_dataset_options_handler("recurrence", "spirals", generators=None)
        assert value is None  # OQ-6: the stranded dataset is cleared
        assert notice.id == "dataset-gate-cleared-alert"
