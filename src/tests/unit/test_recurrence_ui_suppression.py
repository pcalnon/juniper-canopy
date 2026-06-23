#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_recurrence_ui_suppression.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-06-23
# Last Modified: 2026-06-23
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   A1-iii-b1 tests: the execution flag (backend `execution`
#                property + ModelSpec.execution) and the DashboardManager
#                cascade-only tab suppression for a one-shot model.
#####################################################################
"""A1-iii-b1 unit tests (juniper-canopy #368).

Covers the model-class flag source — every backend exposes an `execution` paradigm
("live" | "one_shot") and the registry declares it per model — and the dashboard
suppression logic: `_visible_tabs` drops the 5 cascade-only tabs (and resets a now-hidden
active tab) when the active model is one-shot.
"""

import pytest

from backend.protocol import BackendProtocol
from backend.recurrence_backend import RecurrenceBackend
from backend.recurrence_service_adapter import RecurrenceTrainResult
from model_registry import get_model_spec


class _FakeAdapter:
    def __init__(self):
        self.service_url = "http://rec.test:8210"

    def train(self, **kwargs):
        return RecurrenceTrainResult(final_metrics={"r2": 0.9}, n_epochs=1, stopped_reason=None, dataset={})


@pytest.mark.unit
class TestExecutionFlag:
    """Every backend declares its execution paradigm; the registry mirrors it per model."""

    def test_recurrence_backend_is_one_shot(self):
        backend = RecurrenceBackend(_FakeAdapter())
        assert backend.execution == "one_shot"
        # execution is now part of BackendProtocol, so conformance must still hold.
        assert isinstance(backend, BackendProtocol)

    def test_demo_backend_is_live(self):
        from backend.demo_backend import DemoBackend
        from demo_mode import DemoMode

        assert DemoBackend(DemoMode(update_interval=1.0)).execution == "live"

    def test_service_backend_is_live(self):
        from unittest.mock import MagicMock

        # importorskip (not try/except + skip) so CodeQL doesn't read ServiceBackend as a
        # possibly-uninitialized local (py/uninitialized-local-variable): it skips cleanly
        # when juniper-cascor-client isn't installed.
        service_backend = pytest.importorskip("backend.service_backend")
        assert service_backend.ServiceBackend(MagicMock()).execution == "live"

    def test_model_spec_execution(self):
        assert get_model_spec("cascor").execution == "live"
        assert get_model_spec("recurrence").execution == "one_shot"


@pytest.mark.unit
class TestCascadeTabSuppression:
    """`DashboardManager._visible_tabs` hides cascade-only tabs for a one-shot model."""

    @pytest.fixture(scope="class")
    def dm(self):
        from frontend.dashboard_manager import DashboardManager

        return DashboardManager({})

    def test_cascade_only_constant(self):
        from frontend.dashboard_manager import _CASCADE_ONLY_TAB_IDS

        assert _CASCADE_ONLY_TAB_IDS == frozenset({"candidates", "topology", "evolution", "boundaries", "workers"})

    def test_all_tabs_full_set(self, dm):
        ids = [t.tab_id for t in dm._all_visualization_tabs()]
        assert len(ids) == 15
        assert {"candidates", "topology", "evolution", "boundaries", "workers"}.issubset(set(ids))
        assert {"metrics", "dataset", "parameters", "snapshots"}.issubset(set(ids))

    def test_live_keeps_all_tabs(self, dm):
        assert len(dm._visible_tabs("live")) == 15

    def test_one_shot_drops_cascade_tabs(self, dm):
        tabs = dm._visible_tabs("one_shot")
        ids = {t.tab_id for t in tabs}
        assert len(tabs) == 10
        assert ids.isdisjoint({"candidates", "topology", "evolution", "boundaries", "workers"})
        # non-cascade tabs are preserved (incl. the recurrence-relevant dataset view)
        assert {"metrics", "dataset", "parameters", "snapshots", "about"}.issubset(ids)
