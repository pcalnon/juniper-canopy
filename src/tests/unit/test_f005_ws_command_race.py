#!/usr/bin/env python
"""F-CANOPY-005: the WS command send-promise raced its own timeout and the
REST fallback double-fired state-changing commands.

Observed live: a resume was acked on the wire **+18 ms** after send, yet the
send-promise rejected "Command timeout" at its 3 s ceiling — under main-thread
congestion the expired-timer task beat the queued ``message`` task carrying
the ack — and the Phase-D fallback then POSTed ``/api/train/resume`` into a
409. Separately (segment 10), a legitimate BUSINESS rejection ("Training
cannot be paused in the current state") also triggered the REST re-issue: the
fallback could not tell "socket failed" from "the server said no".

Fix under test (JS-source pins, the repo's established idiom):
1. the timeout re-arms ONCE for a short grace window so an already-queued ack
   task wins the race;
2. every rejection is CLASSED — transport failures (timeout, socket closed,
   send threw, not connected) carry ``transport = true``; a server-adjudicated
   ``command_response`` error carries ``transport = false``;
3. the Phase-D fallback fires only for transport-class rejections and surfaces
   business rejections to the operator instead (pinned in
   ``test_phase_d_button_clientside.py``).
"""

from pathlib import Path

import pytest

ASSETS = Path(__file__).resolve().parents[2] / "frontend" / "assets"


@pytest.fixture(scope="module")
def client_js():
    return (ASSETS / "websocket_client.js").read_text(encoding="utf-8")


@pytest.mark.unit
class TestF005TimeoutGrace:
    def test_timeout_rearms_once_before_rejecting(self, client_js):
        assert "pending.graceUsed" in client_js, "first expiry must re-arm, not reject — the queued ack task has to get its turn"
        assert "GRACE_MS" in client_js
        assert "setTimeout(onTimeout, GRACE_MS)" in client_js

    def test_timeout_checks_pending_still_exists(self, client_js):
        # If the ack landed while the timer task was queued, the pending entry
        # is gone and the timer must be a no-op.
        idx = client_js.index("var onTimeout = function()")
        window = client_js[idx : idx + 400]
        assert "_pendingCommands.get(commandId)" in window
        assert "if (!pending)" in window


@pytest.mark.unit
class TestF005RejectionClassing:
    def test_timeout_rejection_is_transport(self, client_js):
        idx = client_js.index("Command timeout (no command_response for")
        window = client_js[max(0, idx - 300) : idx + 300]
        assert "transport = true" in window

    def test_not_connected_rejection_is_transport(self, client_js):
        idx = client_js.index("WebSocket not connected")
        window = client_js[max(0, idx - 200) : idx + 300]
        assert "transport = true" in window

    def test_socket_close_rejections_are_transport(self, client_js):
        idx = client_js.index("_rejectAllPending(reason)")
        window = client_js[idx : idx + 600]
        assert "transport = true" in window

    def test_business_rejection_is_not_transport(self, client_js):
        idx = client_js.index("_resolvePendingCommand(data) {")
        window = client_js[idx : idx + 900]
        assert "transport = false" in window, "a server-adjudicated command_response error is NOT a transport failure — re-POSTing it re-issues an adjudicated state change"
