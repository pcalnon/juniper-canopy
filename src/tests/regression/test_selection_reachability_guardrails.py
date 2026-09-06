#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_selection_reachability_guardrails.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-09-05
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   Guardrails G1-G11 for the selection-reachability
#                remediation. This PR lands G5 (model-state truth);
#                G1a-G1d / G3 / G6 / G7 / G8 arrive with their own
#                phases and share this module.
#####################################################################
"""Guardrails for the selection-reachability remediation design.

Design of record: ``JUNIPER_2026-09-02_JUNIPER-CANOPY_SELECTION-REACHABILITY-DESIGN.md`` (§5
names each guardrail and the status it must have before and after its phase). Evaluation of
record: ``JUNIPER_2026-09-02_JUNIPER-CANOPY_SELECTION-DEADLOCK-PROPOSALS.md``.

**G5 — the model summary reflects the backend that is actually live (X1 / N5).**

``POST /api/model/select`` returns HTTP 200 for a ``recurrence`` selection even when
``recurrence_service_url`` is unset (the code default): ``_swap_backend`` (``main.py:3891``)
sees that the selection routes to the same backend type already running, records the selection,
and no-ops. The response says so — it carries ``backend`` and ``swapped`` — but the sidebar
summary read only ``nn_model`` and the registry's lifecycle ``status``, both of which are
"recurrence" and "live", so it rendered *"Active: Recurrence (LMU)"* while cascor trained.

That is silent benchmark misattribution: the run is real, the numbers are real, and the model
they are filed under is wrong. The design ships this guardrail FIRST for that reason — unblocking
the deadlock without it would convert a blocked control into a wrong result (§7).

**The predicate under test is deliberately not ``swapped``.** ``swapped is False`` is also the
correct, healthy answer when the user re-selects the model that is already live, so a summary
gated on it would report a running CasCor as inactive. ``test_noop_reselect_of_the_live_model_still_reads_active``
is the false-positive guard that pins that distinction; it fails against the naive predicate.
"""

import pytest
from fastapi.testclient import TestClient

import main
from backend.demo_backend import DemoBackend
from demo_mode import DemoMode
from frontend.dashboard_manager import DashboardManager

# The X1 payload, shaped exactly as ``main._model_state_response`` builds it (``main.py:3860-3871``)
# for a recurrence selection over an unconfigured service. ``test_the_real_route_payload_reads_not_active``
# below re-derives this from the live route rather than trusting the literal.
X1_PAYLOAD = {
    "nn_model": "recurrence",
    "backend": "demo",
    "execution": "continuous",
    "status": "live",
    "swapped": False,
}


@pytest.mark.regression
@pytest.mark.unit
class TestG5ModelStateTruth:
    """G5 — the summary must not claim a model is active when another backend is running."""

    def test_recurrence_selected_over_a_non_recurrence_backend_is_not_live(self):
        assert DashboardManager._selection_is_live(X1_PAYLOAD) is False

    def test_recurrence_selected_over_the_recurrence_backend_is_live(self):
        data = {**X1_PAYLOAD, "backend": "recurrence", "swapped": True}
        assert DashboardManager._selection_is_live(data) is True

    @pytest.mark.parametrize("backend_type", ["cascor", "demo"])
    def test_cascor_selected_over_a_cascor_family_backend_is_live(self, backend_type):
        # Both non-recurrence backend types serve the cascor model; neither is a disagreement.
        data = {"nn_model": "cascor", "backend": backend_type, "status": "live", "swapped": False}
        assert DashboardManager._selection_is_live(data) is True

    def test_an_absent_backend_is_unknown_not_a_disagreement(self):
        # The first-paint seed has never round-tripped, so it carries no ``backend``. Reporting
        # "NOT ACTIVE" there would trade a silent lie for a loud one.
        assert DashboardManager._selection_is_live({"nn_model": "cascor", "status": "live"}) is None

    def test_summary_names_the_backend_that_is_really_running(self):
        summary = DashboardManager._model_summary_text(X1_PAYLOAD)
        assert summary.startswith("Selected: Recurrence (LMU)")
        assert "NOT ACTIVE" in summary
        assert "demo" in summary
        # The old, false rendering must be gone outright — not merely supplemented.
        assert not summary.startswith("Active:")

    def test_noop_reselect_of_the_live_model_still_reads_active(self):
        # THE FALSE-POSITIVE GUARD. ``swapped`` is False here too, because re-selecting the model
        # already running is a legitimate no-op. A summary gated on ``swapped`` alone would call a
        # perfectly healthy CasCor "NOT ACTIVE"; this test fails against that naive predicate.
        data = {"nn_model": "cascor", "backend": "cascor", "status": "live", "swapped": False}
        assert DashboardManager._model_summary_text(data) == "Active: CasCor (Cascade-Correlation)"

    def test_lifecycle_status_note_survives_the_truth_up(self):
        # The pre-existing ``· coming soon`` suffix is orthogonal to backend agreement and must
        # still render on both branches.
        live_but_soon = {"nn_model": "recurrence", "backend": "recurrence", "status": "coming_soon", "swapped": True}
        assert DashboardManager._model_summary_text(live_but_soon) == "Active: Recurrence (LMU) · coming soon"
        assert "· coming soon" in DashboardManager._model_summary_text({**X1_PAYLOAD, "status": "coming_soon"})

    def test_the_real_route_payload_reads_not_active(self, monkeypatch):
        """End-to-end: take the ACTUAL wire payload and feed it to the ACTUAL summary.

        The unit cases above assert against a hand-written dict, which pins the summary but not
        the contract between it and the route. This one closes that gap — if
        ``_model_state_response`` ever stops carrying ``backend``, the literal above keeps
        passing and this fails.
        """
        # The D-8 condition: no recurrence service URL configured, default backend live.
        monkeypatch.setattr(main.settings, "recurrence_service_url", None, raising=False)
        monkeypatch.setattr(main, "backend", DemoBackend(DemoMode(update_interval=1.0)), raising=False)

        resp = TestClient(main.app).post("/api/model/select", json={"nn_model": "recurrence"})
        assert resp.status_code == 200, resp.text
        body = resp.json()

        # Precondition: this really is the X1 state (mirrors test_d8_d11_phase4_truth_up.py).
        assert body["nn_model"] == "recurrence"
        assert body["swapped"] is False
        assert body["backend"] != "recurrence"

        summary = DashboardManager._model_summary_text(body)
        assert "NOT ACTIVE" in summary, summary
        assert body["backend"] in summary
