#!/usr/bin/env python
"""SEC-F19 / D4 WebSocket connection-cap tests: global + per-session caps.

Covers the D4 hardening in ``communication.websocket_manager`` added alongside
the existing per-IP cap:

- the stack-absolute GLOBAL cap (``max_connections``) rejects the N+1th
  connection stack-wide (through ``connect()`` -- the single admission choke
  point shared by every WS endpoint) with close code 1013;
- the PER-SESSION cap keyed on the anonymous ``canopy_session`` cookie restores
  per-client fairness under a shared NAT IP (two sessions from one peer IP each
  keep their allocation);
- a legit single user is unaffected; a cookieless first connection is allowed
  and left to the global cap as the backstop (§9 R2); the per-IP cap still binds
  when IT is the constraint (off-NAT DoS-dampening preserved).

Design-of-record: juniper-ml
notes/JUNIPER_CANOPY_CONTROL_SURFACE_AUTH_AND_NAT_DESIGN_2026-07-03.md
§5 (Option B) / §9 (R2, testing).
"""

from unittest.mock import AsyncMock

import pytest

from communication.websocket_manager import WebSocketManager


def _make_ws(ip="127.0.0.1", session=None):
    """Fake WebSocket with a peer-IP tuple + a cookies dict.

    ``session=None`` -> no ``canopy_session`` cookie (cookieless); a string ->
    that session cookie value. ``accept`` / ``send_json`` / ``close`` are async
    mocks so the same object can also be driven through ``connect()``.
    """
    ws = AsyncMock()
    ws.client = (ip, 12345)
    ws.cookies = {} if session is None else {"canopy_session": session}
    return ws


@pytest.mark.unit
class TestPerSessionLimit:
    """Per-session cap keyed on the canopy_session cookie (SEC-F19 / D4)."""

    def test_allows_under_limit_and_tracks(self):
        mgr = WebSocketManager()
        ws = _make_ws(session="sess-A")
        assert mgr.check_per_session_limit(ws, max_per_session=5) is True
        assert mgr._per_session_counts["sess-A"] == 1

    def test_cap_enforced(self):
        mgr = WebSocketManager()
        for _ in range(5):
            assert mgr.check_per_session_limit(_make_ws(session="sess-A"), max_per_session=5) is True
        assert mgr.check_per_session_limit(_make_ws(session="sess-A"), max_per_session=5) is False

    def test_cookieless_allowed_and_untracked(self):
        """A cookieless first connection is allowed and left to the global cap."""
        mgr = WebSocketManager()
        # Even a max_per_session of 1 does not block cookieless connections.
        assert mgr.check_per_session_limit(_make_ws(session=None), max_per_session=1) is True
        assert mgr.check_per_session_limit(_make_ws(session=None), max_per_session=1) is True
        assert mgr._per_session_counts == {}

    def test_counter_decrements_on_disconnect(self):
        mgr = WebSocketManager()
        ws = _make_ws(session="sess-A")
        mgr.check_per_session_limit(ws, max_per_session=5)
        mgr.active_connections.add(ws)
        mgr.connection_metadata[ws] = {"client_id": "test"}
        mgr.disconnect(ws)
        assert mgr._per_session_counts.get("sess-A", 0) == 0

    def test_counter_partial_decrement(self):
        """Decrementing one of two same-session connections leaves the other."""
        mgr = WebSocketManager()
        ws1 = _make_ws(session="sess-A")
        ws2 = _make_ws(session="sess-A")
        mgr.check_per_session_limit(ws1, max_per_session=5)
        mgr.check_per_session_limit(ws2, max_per_session=5)
        assert mgr._per_session_counts["sess-A"] == 2
        mgr._decrement_session_count(ws1)
        assert mgr._per_session_counts["sess-A"] == 1

    def test_decrement_cookieless_is_noop(self):
        mgr = WebSocketManager()
        mgr._decrement_session_count(_make_ws(session=None))
        assert mgr._per_session_counts == {}


@pytest.mark.unit
class TestConnectionLimitsComposition:
    """``check_connection_limits`` composes per-IP + per-session caps (SEC-F19/D4)."""

    def test_two_sessions_one_ip_each_keep_allocation(self):
        """Two sessions behind one NAT gateway IP each keep their allocation."""
        mgr = WebSocketManager()
        ip = "172.23.0.1"  # the Docker bridge gateway every client NATs to (HO-3)
        # High per-IP cap so the (inert-behind-NAT) per-IP cap is NOT the binding
        # constraint -- this isolates the per-session fairness behavior.
        per_ip = 100
        per_session = 2

        # Session A saturates its own per-session allocation...
        for _ in range(per_session):
            assert mgr.check_connection_limits(_make_ws(ip=ip, session="sess-A"), max_per_ip=per_ip, max_per_session=per_session) is True
        # ...and A's next connection is rejected by the per-session cap.
        assert mgr.check_connection_limits(_make_ws(ip=ip, session="sess-A"), max_per_ip=per_ip, max_per_session=per_session) is False

        # Session B -- SAME peer IP -- still gets its full, independent allocation.
        for _ in range(per_session):
            assert mgr.check_connection_limits(_make_ws(ip=ip, session="sess-B"), max_per_ip=per_ip, max_per_session=per_session) is True

        assert mgr._per_session_counts["sess-A"] == per_session
        assert mgr._per_session_counts["sess-B"] == per_session

    def test_per_session_rejection_rolls_back_per_ip(self):
        """A per-session rejection must not leak the per-IP counter."""
        mgr = WebSocketManager()
        ip = "172.23.0.1"
        for _ in range(2):
            mgr.check_connection_limits(_make_ws(ip=ip, session="sess-A"), max_per_ip=100, max_per_session=2)
        ip_before = mgr._per_ip_counts[ip]
        # 3rd from the capped session -> per-session rejects; per-IP rolled back.
        assert mgr.check_connection_limits(_make_ws(ip=ip, session="sess-A"), max_per_ip=100, max_per_session=2) is False
        assert mgr._per_ip_counts[ip] == ip_before

    def test_single_user_unaffected(self):
        """A legit single user is admitted (regression: caps don't over-block)."""
        mgr = WebSocketManager()
        ws = _make_ws(ip="10.0.0.9", session="only-user")
        assert mgr.check_connection_limits(ws, max_per_ip=5, max_per_session=5) is True
        assert mgr._per_ip_counts["10.0.0.9"] == 1
        assert mgr._per_session_counts["only-user"] == 1

    def test_per_ip_still_binds_when_it_is_the_constraint(self):
        """The per-IP cap still rejects when IT is the binding constraint
        (off-NAT DoS-dampening preserved); per-session is not the gate here."""
        mgr = WebSocketManager()
        ip = "203.0.113.7"
        for i in range(3):
            assert mgr.check_connection_limits(_make_ws(ip=ip, session=f"s{i}"), max_per_ip=3, max_per_session=100) is True
        # 4th from the same IP (distinct session) -> per-IP cap rejects.
        assert mgr.check_connection_limits(_make_ws(ip=ip, session="s3"), max_per_ip=3, max_per_session=100) is False
        # The rejected attempt did not create a per-session entry for "s3".
        assert "s3" not in mgr._per_session_counts


@pytest.mark.unit
class TestGlobalConnectionCap:
    """Stack-absolute global cap (max_connections) via the connect() choke point."""

    async def test_global_cap_rejects_n_plus_1_stackwide(self):
        mgr = WebSocketManager()
        mgr.max_connections = 3  # small cap for the test
        # Distinct cookieless peers so neither per-IP nor per-session is the
        # constraint -- only the global cap can reject here.
        for i in range(3):
            await mgr.connect(_make_ws(ip=f"10.0.0.{i}", session=None))
        assert mgr.get_connection_count() == 3

        # The N+1th connection is rejected stack-wide with close code 1013 and
        # is NOT added to the active set.
        ws4 = _make_ws(ip="10.0.0.99", session=None)
        await mgr.connect(ws4)
        ws4.close.assert_awaited_once_with(code=1013, reason="Max connections reached")
        assert mgr.get_connection_count() == 3
        assert ws4 not in mgr.active_connections

    async def test_global_reject_after_reserved_limits_releases_counters(self):
        """A global-cap rejection must not leak per-IP or per-session slots.

        FastAPI endpoints reserve per-IP/per-session capacity via
        ``check_connection_limits`` before calling ``connect()``, where the
        global stack-wide cap is enforced. If that later global check rejects,
        the already-reserved slots must be released or future legitimate
        connections can be blocked by stale counters.
        """
        mgr = WebSocketManager()
        mgr.max_connections = 1

        admitted = _make_ws(ip="10.0.0.1", session="sess-A")
        assert mgr.check_connection_limits(admitted, max_per_ip=5, max_per_session=5) is True
        assert await mgr.connect(admitted, limits_reserved=True) is True

        rejected = _make_ws(ip="10.0.0.2", session="sess-B")
        assert mgr.check_connection_limits(rejected, max_per_ip=5, max_per_session=5) is True
        assert await mgr.connect(rejected, limits_reserved=True) is False

        rejected.close.assert_awaited_once_with(code=1013, reason="Max connections reached")
        assert rejected not in mgr.active_connections
        assert mgr._per_ip_counts == {"10.0.0.1": 1}
        assert mgr._per_session_counts == {"sess-A": 1}
        
    async def test_global_cap_rejection_releases_reserved_session_slots(self):
        """A connect-time global-cap reject must not strand per-IP/session slots."""
        mgr = WebSocketManager()
        mgr.max_connections = 1
        ip = "172.23.0.1"
        session = "sess-A"

        ws1 = _make_ws(ip=ip, session=session)
        assert mgr.check_connection_limits(ws1, max_per_ip=10, max_per_session=5) is True
        assert await mgr.connect(ws1) is True

        ws2 = _make_ws(ip=ip, session=session)
        assert mgr.check_connection_limits(ws2, max_per_ip=10, max_per_session=5) is True
        assert mgr._per_ip_counts[ip] == 2
        assert mgr._per_session_counts[session] == 2

        assert await mgr.connect(ws2) is False
        mgr.release_connection_limits(ws2)

        ws2.close.assert_awaited_once_with(code=1013, reason="Max connections reached")
        assert ws2 not in mgr.active_connections
        assert mgr._per_ip_counts[ip] == 1
        assert mgr._per_session_counts[session] == 1

        mgr.disconnect(ws1)
        assert ip not in mgr._per_ip_counts
        assert session not in mgr._per_session_counts
