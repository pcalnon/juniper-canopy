#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_x7_demo_mode_honesty.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-09-05
# Last Modified: 2026-09-05
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   X7 PR 2 -- demo mode must not present simulated data
#                as real: the badge must be reachable, and no snapshot
#                may carry an invented size.
#####################################################################
"""X7 PR 2: demo-mode honesty.

Canopy falls back to demo mode when a **cold start** cannot reach cascor. That fallback
is legitimate; presenting its output as real is not, and three things did:

1. the ``"WS: Demo"`` badge was **unreachable dead code** — both JS producers hardcode
   ``mode: "live"``, so the UI rendered a green ``"WS: Connected"`` over simulated data;
2. ``POST /api/v1/snapshots`` invented a *plausible* ``size_bytes`` (~1–1.5 MB) for a file
   it never wrote, beside a ``path`` inside the real archive;
3. the mock listing did the same for three entries.

**This is the sequencing gate for PR 3.** Tightening liveness probes before demo mode is
honest converts a loud, self-recovering hang into a fast, silent restart *into the
simulator* — the failure stops being visible at exactly the moment it starts being
frequent. These tests are what "honest" has to mean before that lever is pulled.

**A plausible number is worse than no number.** It survives every sanity check a consumer
might apply, so the assertions below are about the *absence* of a fabricated value, not
about its range.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import main

_SRC = Path(__file__).resolve().parents[2]


# --------------------------------------------------------------------------------------
# The badge must be reachable
# --------------------------------------------------------------------------------------


@pytest.mark.regression
@pytest.mark.unit
class TestDemoBadgeIsReachable:
    def test_stream_health_reports_mode_on_both_branches(self, client):
        """The mode signal must exist regardless of which branch answers.

        Before PR 2 only the non-service branch carried ``mode``, so a consumer had to
        already know which branch it was reading in order to read the field that tells it
        which branch it is reading.
        """
        body = client.get("/api/stream_health").json()
        assert "mode" in body, "/api/stream_health must report the backend mode"
        assert body["mode"] == main.backend.backend_type

    def test_badge_does_not_depend_solely_on_the_hardcoded_client_mode(self):
        """The ``WS: Demo`` branch must not be keyed only on ``wsStatus.mode``.

        Both producers hardcode it: ``websocket_client.js`` and ``ws_dash_bridge.js``. A
        branch keyed only on that value can never fire, which is precisely how canopy
        showed green over simulated data. Asserted against the callback source because
        the defect is *unreachability* — no runtime test can observe a branch that cannot
        be entered, so the only place to catch it is the code path itself.
        """
        from frontend.components.connection_indicator import CONNECTION_INDICATOR_JS

        assert '"WS: Demo"' in CONNECTION_INDICATOR_JS, "the demo badge state disappeared"
        assert "streamHealth" in CONNECTION_INDICATOR_JS.split('"WS: Demo"')[0], "the demo branch must consult server-provided stream health, not only the hardcoded client mode"

    def test_the_client_producers_really_do_hardcode_live(self):
        """Vacuity guard: the premise above must still hold.

        If a future client learns its own mode, the assertion above stops being about a
        real defect — and this test says so loudly rather than letting the guard quietly
        become decoration.
        """
        producers = [
            _SRC / "frontend" / "assets" / "websocket_client.js",
            _SRC / "frontend" / "assets" / "ws_dash_bridge.js",
        ]
        hardcoded = [p.name for p in producers if p.exists() and re.search(r'mode:\s*"live"', p.read_text())]
        assert hardcoded, "no client hardcodes mode:'live' any more — re-derive whether the badge still needs the server signal"


# --------------------------------------------------------------------------------------
# No invented sizes
# --------------------------------------------------------------------------------------


@pytest.mark.regression
@pytest.mark.unit
class TestNoFabricatedSnapshotBytes:
    def test_mock_listing_reports_no_invented_size(self):
        """``_generate_mock_snapshots`` names no file on disk, so it may claim no bytes."""
        rows = main._generate_mock_snapshots()
        assert rows, "the mock listing must still produce rows"
        for row in rows:
            assert row["size_bytes"] == 0, f"{row['id']} carries a fabricated size {row['size_bytes']}"
            assert row.get("simulated") is True, f"{row['id']} is not marked simulated"

    async def test_demo_snapshot_creation_reports_no_invented_size(self, monkeypatch):
        """A demo snapshot writes nothing, so it must not report a size.

        The old value was ``1 MB + timestamp % 512 KB`` — stable-looking, in a believable
        range, and different every time, which is exactly what makes it indistinguishable
        from a real snapshot in a listing or an archive-size total.
        """

        class _DemoBackend:
            backend_type = "demo"

            def get_status(self):
                return {"fsm_status": "idle"}

        monkeypatch.setattr(main, "backend", _DemoBackend())
        result = await main.create_snapshot(name="honesty_probe", description=None)

        assert result["size_bytes"] == 0, f"demo snapshot invented a size: {result['size_bytes']}"
        assert result["simulated"] is True, "a demo snapshot must be machine-readably marked"

    async def test_the_marker_survives_a_caller_supplied_description(self, monkeypatch):
        """The marker must not live only in prose the caller can overwrite.

        Before PR 2 the sole marker was a *default* description — so a caller that passed
        its own description produced a demo snapshot with no marker at all, which is the
        case most likely to be scripted.
        """

        class _DemoBackend:
            backend_type = "demo"

            def get_status(self):
                return {"fsm_status": "idle"}

        monkeypatch.setattr(main, "backend", _DemoBackend())
        result = await main.create_snapshot(name="described_probe", description="my own description")

        assert result["description"] == "my own description"
        assert result["simulated"] is True, "the demo marker was lost when the caller supplied a description"
        assert result["size_bytes"] == 0
