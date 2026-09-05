#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_x7_status_cache_guards.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-09-05
# Last Modified: 2026-09-05
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   X7 slice 1c -- complementary guards the T-C1/T-C2/T-C3/T-C4
#                suite cannot see: normalisation failure, the OK-but-stale
#                window, cache-side half-dead-200 error synthesis, C7 health
#                extras, and the one-hot status-class gauge.
#####################################################################
"""Complementary X7 slice 1c tests.

``test_x7_status_cache.py`` already owns T-C1 (classifier census), T-C2 (UI
renders the class), T-C3 (breaker isolation), and T-C4 (non-OK stale + dead
refresher + never-OK C6). This file covers leftover those tests cannot see:

* A raising ``normalize`` on an OK raw payload must not keep the previous
  payload *fresh* (machinery-fails-green).
* C9 on the OK path: age past ``stale_after`` but before ``unknown_after``
  stays ``status_class=ok`` and ``training_active()`` stays a bool — staleness
  is reported *beside* the boolean, which is what C7 health depends on.
* ``for_status()`` synthesises a truthy ``error`` for a half-dead 200. T-C2
  feeds the UI a pre-built body; it never asks the cache to produce one.
* Health / ``/api/status`` wiring: extras empty without a cache, cache wins
  over a live outage-negative, and a live cache means zero upstream status
  calls (C2).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.status_cache import StatusCache, StatusClass

# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------


def _cache(raw_sequence, normalize=None, **kwargs):
    """A cache whose fetch walks ``raw_sequence``, repeating its last element."""
    box = {"i": 0}

    def fetch():
        i = min(box["i"], len(raw_sequence) - 1)
        box["i"] += 1
        value = raw_sequence[i]
        if isinstance(value, Exception):
            raise value
        return value

    if normalize is None:

        def normalize(raw: dict) -> dict:  # E731: a def, not a lambda assignment
            return {"is_training": bool(raw.get("training_active"))}

    return StatusCache(fetch_raw=fetch, normalize=normalize, **kwargs)


@pytest.fixture
def restore_main_globals():
    """Save/restore ``main.status_cache`` and ``main.backend`` around a wiring test."""
    import main

    original_cache = main.status_cache
    original_backend = main.backend
    try:
        yield
    finally:
        main.status_cache = original_cache
        main.backend = original_backend


def _gauge_value(metric, **labels) -> float:
    """Read a labelled gauge sample via the public ``collect()`` API."""
    samples = list(metric.collect())[0].samples
    for sample in samples:
        if sample.name.endswith("_created"):
            continue
        if all(sample.labels.get(key) == value for key, value in labels.items()):
            return sample.value
    return 0.0


# --------------------------------------------------------------------------------------
# Normalisation failure — T-C4 always uses a working normalize
# --------------------------------------------------------------------------------------


@pytest.mark.regression
@pytest.mark.unit
class TestNormalisationFailure:
    """An OK raw payload whose normalize raises must not stay green."""

    async def test_after_ok_does_not_keep_the_previous_payload_fresh(self):
        """Do NOT keep the previous payload and call it fresh.

        The first tick normalises cleanly. The second tick is still cascor-shaped
        (so ``classify`` returns OK) but ``normalize`` raises. Leaving ``_class``
        as OK would keep ``training_active()`` True and ``for_status()`` fresh —
        the frozen-green failure this slice exists to remove.
        """
        calls = {"n": 0}

        def normalize(raw):
            calls["n"] += 1
            if calls["n"] == 1:
                return {"is_training": True}
            raise ValueError("unusable OK payload")

        cache = _cache([{"training_active": True}], normalize=normalize)
        assert await cache.refresh_once() is StatusClass.OK
        assert cache.training_active() is True

        assert await cache.refresh_once() is StatusClass.INDETERMINATE
        body = cache.for_status()
        assert body["status_class"] == "indeterminate"
        assert body["stale"] is True
        assert "normalisation" in body["error"]
        assert cache.training_active() is None

    async def test_first_tick_does_not_invent_is_training(self):
        """C6: a never-usable OK must not stamp ``is_training`` at all."""

        def boom(_raw):
            raise ValueError("unusable OK payload")

        cache = _cache([{"training_active": True}], normalize=boom)
        assert await cache.refresh_once() is StatusClass.INDETERMINATE
        body = cache.for_status()
        assert "is_training" not in body
        assert body["age_seconds"] is None
        assert body["stale"] is True
        assert cache.training_active() is None


# --------------------------------------------------------------------------------------
# C9 on the OK path — T-C4's dead-refresher test jumps past unknown_after
# --------------------------------------------------------------------------------------


@pytest.mark.regression
@pytest.mark.unit
class TestOkButStaleWindow:
    async def test_age_past_stale_after_stays_ok_and_marked_stale(self, monkeypatch):
        """Between ``stale_after`` and ``unknown_after`` the class is still OK.

        T-C4 ages the clock past ``unknown_after`` and asserts INDETERMINATE. The
        healthcheck's own budget is the *stale* threshold: a value older than a
        probe's deadline is not fresh *to that probe*, but it is still a real
        observation. ``training_active()`` must stay a bool so the health
        boolean is not smuggled into a tri-state (design §5.5).
        """
        clock = {"t": 1000.0}
        monkeypatch.setattr("backend.status_cache.time.monotonic", lambda: clock["t"])

        cache = _cache([{"training_active": True}], stale_after=5.0, unknown_after=30.0)
        assert await cache.refresh_once() is StatusClass.OK
        assert cache.for_status()["stale"] is False

        clock["t"] = 1006.0  # 6 s > stale_after, well under unknown_after
        body = cache.for_status()
        assert cache.current_class() is StatusClass.OK
        assert body["status_class"] == "ok"
        assert body["stale"] is True
        assert body["age_seconds"] == 6.0
        assert cache.training_active() is True


# --------------------------------------------------------------------------------------
# Cache-side T-C2 — the UI suite never calls for_status()
# --------------------------------------------------------------------------------------


@pytest.mark.regression
@pytest.mark.unit
class TestHalfDead200ForStatus:
    async def test_for_status_synthesises_error_and_omits_is_training(self):
        """The half-dead 200 has no ``error`` of its own; ``for_status`` must add one.

        T-C2 asserts the status bar given a *pre-built* body. If ``for_status``
        ever stopped synthesising ``error`` / ``status_class``, the UI test
        would stay green and the PR #340 defect would return.
        """
        cache = _cache([{"ok": True, "service": "something-else"}])
        assert await cache.refresh_once() is StatusClass.UNREACHABLE
        body = cache.for_status()
        assert body["status_class"] == "unreachable"
        assert body["error"], "PR #340 branch keys on a truthy error"
        assert "is_training" not in body
        assert body["stale"] is True
        assert body["age_seconds"] is None


# --------------------------------------------------------------------------------------
# training_active() on an OK payload — T-C4 only asserts None on non-OK
# --------------------------------------------------------------------------------------


@pytest.mark.regression
@pytest.mark.unit
class TestTrainingActiveOnOk:
    async def test_true_when_normalised_is_training_is_true(self):
        cache = _cache([{"training_active": True}])
        await cache.refresh_once()
        assert cache.training_active() is True

    async def test_false_when_normalised_is_training_is_false(self):
        cache = _cache([{"training_active": False, "state_machine": {"status": "Stopped"}}])
        await cache.refresh_once()
        assert cache.training_active() is False

    async def test_none_when_normalised_payload_omits_is_training(self):
        cache = StatusCache(
            fetch_raw=lambda: {"training_active": True},
            normalize=lambda raw: {"phase": "output"},
        )
        await cache.refresh_once()
        assert cache.current_class() is StatusClass.OK
        assert cache.training_active() is None


# --------------------------------------------------------------------------------------
# C7 / C2 wiring — no existing test imports these helpers
# --------------------------------------------------------------------------------------


@pytest.mark.regression
@pytest.mark.unit
class TestHealthAndStatusWiring:
    def test_c7_extras_empty_without_a_cache(self, restore_main_globals):
        import main

        main.status_cache = None
        assert main._backend_status_extras() == {}

    async def test_c7_extras_map_for_status_fields(self, restore_main_globals):
        import main

        cache = _cache([{"training_active": True}])
        await cache.refresh_once()
        main.status_cache = cache
        extras = main._backend_status_extras()
        assert extras == {
            "backend_status": "ok",
            "backend_status_stale": False,
            "backend_status_age_seconds": cache.for_status()["age_seconds"],
        }

    async def test_health_omits_c7_fields_without_a_cache(self, restore_main_globals):
        import main

        main.status_cache = None
        main.backend = MagicMock()
        main.backend.backend_type = "demo"
        main.backend.is_training_active.return_value = False
        result = await main.health_check()
        assert "backend_status" not in result
        assert "backend_status_stale" not in result
        assert "backend_status_age_seconds" not in result

    async def test_health_carries_c7_fields_from_the_cache(self, restore_main_globals):
        import main

        cache = _cache([{"training_active": True}])
        await cache.refresh_once()
        main.status_cache = cache
        main.backend = MagicMock()
        main.backend.backend_type = "service"
        result = await main.health_check()
        assert result["backend_status"] == "ok"
        assert result["backend_status_stale"] is False
        assert "backend_status_age_seconds" in result

    async def test_health_prefers_cache_over_a_live_outage_negative(self, restore_main_globals):
        """C6 on the health boolean: a live ``False`` under outage must not win.

        ``is_training_active()`` keeps its bool contract and returns False when
        the adapter cannot reach cascor. That is exactly how a cache invents
        "not training" during a live run. When the cache *knows*, health must
        use that verdict and must not call the live path.
        """
        import main

        cache = _cache([{"training_active": True}])
        await cache.refresh_once()
        main.status_cache = cache
        live = MagicMock()
        live.backend_type = "service"
        live.is_training_active.return_value = False
        main.backend = live
        result = await main.health_check()
        assert result["training_active"] is True
        live.is_training_active.assert_not_called()

    async def test_health_falls_back_to_live_when_cache_has_no_verdict(self, restore_main_globals):
        import main

        cache = _cache([{"ok": True, "service": "something-else"}])
        await cache.refresh_once()
        assert cache.training_active() is None
        main.status_cache = cache
        live = MagicMock()
        live.backend_type = "service"
        live.is_training_active.return_value = False
        main.backend = live
        result = await main.health_check()
        assert result["training_active"] is False
        live.is_training_active.assert_called_once()

    async def test_api_status_serves_the_cache_without_calling_upstream(self, restore_main_globals):
        """C2: every tab polling ``/api/status`` must cost zero upstream calls."""
        import main

        cache = _cache([{"training_active": True}])
        await cache.refresh_once()
        main.status_cache = cache
        live = MagicMock()
        live.get_status.side_effect = AssertionError("must not call upstream")
        main.backend = live
        body = await main.get_status()
        assert body["status_class"] == "ok"
        assert body["is_training"] is True
        live.get_status.assert_not_called()

    async def test_start_status_cache_skips_demo_and_adapterless_service(self, restore_main_globals):
        """Demo/recurrence answer from memory; a cache there would invent staleness."""
        import main

        main.status_cache = None
        demo = MagicMock(spec=["backend_type"])
        demo.backend_type = "demo"
        await main._start_status_cache(demo)
        assert main.status_cache is None

        service = MagicMock(spec=["backend_type"])
        service.backend_type = "service"
        await main._start_status_cache(service)
        assert main.status_cache is None


# --------------------------------------------------------------------------------------
# Gauge one-hot — registered in #578, never asserted
# --------------------------------------------------------------------------------------


@pytest.mark.regression
@pytest.mark.unit
class TestBackendStatusClassGauge:
    @pytest.fixture(autouse=True)
    def _reset_canopy_metrics(self):
        import observability as obs

        obs._canopy_metrics = None
        try:
            from prometheus_client import REGISTRY

            collector = REGISTRY._names_to_collectors.get("juniper_canopy_backend_status_class")
            if collector is not None:
                try:
                    REGISTRY.unregister(collector)
                except (KeyError, ValueError):
                    pass
        except ImportError:
            pass
        yield
        obs._canopy_metrics = None

    def test_transition_clears_the_previous_class(self):
        """A gauge left at 1 after the class moved on is the stale-green failure.

        One series per class, each 0 or 1. Moving ok → unreachable must set
        unreachable=1 *and* ok=0; otherwise an alert on
        ``{status_class="ok"} == 1`` stays true after the backend died.
        """
        import observability as obs

        obs.set_backend_status_class("ok")
        obs.set_backend_status_class("unreachable")
        gauge = obs._ensure_canopy_metrics()["backend_status_class"]
        assert _gauge_value(gauge, status_class="ok") == 0.0
        assert _gauge_value(gauge, status_class="unreachable") == 1.0
        assert _gauge_value(gauge, status_class="indeterminate") == 0.0
