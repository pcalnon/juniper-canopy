#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_demo_mode_local_fallback.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-09-06
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   Guardrail G9 — demo mode announces the local
#                dataset fallback instead of degrading silently.
#####################################################################
"""G9 — demo mode degrades LOUDLY when it runs on a locally generated dataset.

Design of record: ``JUNIPER_2026-09-02_JUNIPER-CANOPY_SELECTION-REACHABILITY-DESIGN.md`` §4.12 /
N13. Demo mode exists to **dogfood the platform** — it calls juniper-data first and only falls back
to its own generator when the service is unreachable (Docker standalone, CI smoke test). That
fallback is deliberately kept, because deleting it would make demo mode hard-depend on juniper-data
being up; what it must not do is happen *quietly*, because then demo mode silently stops
demonstrating the platform and starts demonstrating code that runs nowhere else.

**Two corrections to §4.12 are pinned here.**

1. The design names **one** fallback site. There are **three** (``__init__``, ``restart_dataset``,
   and the spiral-rotations regeneration). A banner wired at one caller would leave demo mode able
   to *become* degraded mid-session unannounced, so the flag is set **inside** the degraded
   function — covering every call site by construction, including any added later.
   ``test_the_flag_is_set_inside_the_degraded_path_not_at_its_callers`` is what keeps that true.

2. The design says the fallback "degrades silently". It does not — it logs a ``warning`` and raises
   a ``DeprecationWarning``. Both are log-channel only. It degrades silently **in the UI**, which
   is the channel a researcher actually reads, and that is what this guardrail closes.
"""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import main
from backend.demo_backend import DemoBackend
from demo_mode import DemoMode

DEMO_MODE_SOURCE = Path(main.__file__).parent / "demo_mode.py"
INDICATOR_SOURCE = Path(main.__file__).parent / "frontend" / "components" / "connection_indicator.py"


@pytest.fixture
def demo():
    """A DemoMode instance. Whether its dataset came from juniper-data depends on the environment,
    so every test below sets ``local_dataset_fallback`` explicitly rather than assuming."""
    return DemoMode(update_interval=1.0)


@pytest.mark.regression
@pytest.mark.unit
class TestG9TheFlag:
    def test_the_local_generator_marks_the_instance_degraded(self, demo):
        demo.local_dataset_fallback = False
        demo._generate_spiral_dataset_local(n_samples=20)
        assert demo.local_dataset_fallback is True

    def test_the_attribute_exists_from_construction(self, demo):
        # It is read by ``/api/stream_health`` on every poll; an AttributeError there would take
        # out the badge for the live case too.
        assert isinstance(demo.local_dataset_fallback, bool)

    def test_the_flag_is_set_inside_the_degraded_path_not_at_its_callers(self):
        """THE structural guard, and the reason this survives a fourth call site.

        The design's one-site premise is false. Rather than wire a banner at each caller, the flag
        is set inside ``_generate_spiral_dataset_local`` itself. This test fails if someone moves
        the assignment out to the callers — which would look equivalent and would silently
        reintroduce the gap the moment a new call site is added.
        """
        source = DEMO_MODE_SOURCE.read_text()
        call_sites = re.findall(r"self\._generate_spiral_dataset_local\(", source)
        assert len(call_sites) >= 3, f"expected the three known call sites, found {len(call_sites)}"
        assignments = re.findall(r"self\.local_dataset_fallback = True", source)
        assert len(assignments) == 1, "the degraded flag must be set in exactly one place — inside the degraded function"

        # ...and that one place must be inside the function, not beside a caller.
        func_start = source.index("def _generate_spiral_dataset_local(")
        func_end = source.index("\n    def ", func_start + 1)
        assert "self.local_dataset_fallback = True" in source[func_start:func_end]


@pytest.mark.regression
@pytest.mark.unit
class TestG9TheWireField:
    def test_a_local_fallback_reports_local(self, monkeypatch, demo):
        demo.local_dataset_fallback = True
        monkeypatch.setattr(main, "backend", DemoBackend(demo), raising=False)
        assert main._demo_dataset_source() == "local"

    def test_the_dogfooding_path_reports_juniper_data(self, monkeypatch, demo):
        demo.local_dataset_fallback = False
        monkeypatch.setattr(main, "backend", DemoBackend(demo), raising=False)
        assert main._demo_dataset_source() == "juniper-data"

    def test_a_non_demo_backend_reports_nothing(self, monkeypatch):
        # ``None`` rather than "juniper-data": a service backend's dataset provenance is not this
        # field's business, and claiming otherwise would be its own small lie.
        monkeypatch.setattr(main, "backend", object(), raising=False)
        assert main._demo_dataset_source() is None

    def test_stream_health_carries_it_on_the_branch_demo_mode_takes(self, monkeypatch, demo):
        demo.local_dataset_fallback = True
        monkeypatch.setattr(main, "backend", DemoBackend(demo), raising=False)
        body = TestClient(main.app).get("/api/stream_health").json()
        assert body["mode"] == "demo"
        assert body["dataset_source"] == "local"


@pytest.mark.regression
@pytest.mark.unit
class TestG9TheBadge:
    """The indicator is clientside JS, so it is pinned by source — the Python suite never runs it.

    Same reasoning as the F-CANOPY-042 bounds-sync suite: a clientside callback that no test
    executes is a contract with nothing holding it.
    """

    def test_the_badge_distinguishes_local_data_from_platform_data(self):
        js = INDICATOR_SOURCE.read_text()
        assert 'dataset_source === "local"' in js, "the badge must read the field stream_health publishes"
        assert "LOCAL data" in js

    def test_the_local_branch_precedes_the_generic_demo_return(self):
        # Order is load-bearing: the generic ``return ["WS: Demo", ...]`` would otherwise shadow it
        # and the degraded case would render as an ordinary demo.
        js = INDICATOR_SOURCE.read_text()
        assert js.index('dataset_source === "local"') < js.index('return ["WS: Demo", baseStyle]')
