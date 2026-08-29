#!/usr/bin/env python
"""F-CANOPY-002: CascorWebSocket's per-type handler registry must FAN OUT.

The old ``on()`` was a single-slot registry (``this.handlers[type] = handler``)
— silent last-writer-wins. Asset load order guaranteed ``ws_latency.js``
registered its ``metrics`` sampler AFTER ``ws_dash_bridge.js`` and clobbered
the bridge's metrics intake, so the WS metrics fast path was dead in every
live run (401 metrics frames measured arriving and dispatching only into the
latency sampler) while sibling types on the same socket flowed normally.

These tests pin the structural fix in the source (the repo's established
JS-pinning idiom — see ``TestGapWs16WebSocketClientResume``): registration
appends, dispatch iterates a copy, removal splices by identity, and the
single-slot assignment is gone. Both real ``metrics`` registrants must remain
in their own files.
"""

from pathlib import Path

import pytest

ASSETS = Path(__file__).resolve().parents[2] / "frontend" / "assets"


@pytest.fixture(scope="module")
def client_js():
    return (ASSETS / "websocket_client.js").read_text(encoding="utf-8")


@pytest.mark.unit
class TestF002HandlerFanout:
    def test_on_appends_to_a_per_type_list(self, client_js):
        assert "this.handlers[type].push(handler)" in client_js, "on() must append — a single-slot registry silently drops earlier registrants (F-CANOPY-002)"

    def test_single_slot_assignment_is_gone(self, client_js):
        assert "this.handlers[type] = handler" not in client_js, "the single-slot clobber is the F-CANOPY-002 defect"

    def test_dispatch_iterates_a_copy(self, client_js):
        assert "typeHandlers.slice()" in client_js, "dispatch must iterate a COPY so off() during dispatch is safe"
        assert "for (const handler of typeHandlers.slice())" in client_js

    def test_dispatch_isolates_handler_errors(self, client_js):
        # The try/catch must sit INSIDE the loop: one throwing handler must
        # not starve its siblings (the bridge and the beacon share 'metrics').
        loop_at = client_js.index("for (const handler of typeHandlers.slice())")
        try_at = client_js.index("try {", loop_at)
        loop_close_hint = client_js.index("Handler error for type", loop_at)
        assert loop_at < try_at < loop_close_hint

    def test_off_removes_by_identity_from_the_list(self, client_js):
        assert "typeHandlers.indexOf(handler)" in client_js
        assert "typeHandlers.splice(idx, 1)" in client_js

    def test_both_metrics_registrants_still_present(self):
        bridge = (ASSETS / "ws_dash_bridge.js").read_text(encoding="utf-8")
        beacon = (ASSETS / "ws_latency.js").read_text(encoding="utf-8")
        assert 'on("metrics"' in bridge, "the bridge's metrics intake is the fast path F-CANOPY-002 killed"
        assert 'on("metrics"' in beacon, "the latency sampler stays — fan-out makes coexistence legal"
