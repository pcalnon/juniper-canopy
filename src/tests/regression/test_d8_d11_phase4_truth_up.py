#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_d8_d11_phase4_truth_up.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-08-26
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   Canopy E2E arc, Phase-4 code truth-up (plan §7.5, §11).
#                D-8: pin the REAL recurrence-selection behaviour the
#                corrected src/backend/__init__ docstring now describes;
#                D-11: pin the package __version__ single-source so the
#                stale "0.5.0" literals cannot silently return.
#####################################################################
"""Phase-4 code truth-up regression tests (D-8 and D-11).

**D-8** — the ``_try_create_recurrence_backend`` docstring used to claim "the A1 selection UI
gates an unconfigured recurrence model out of the picker". It does not: ``model_is_trainable``
gates on the registry ``status`` only, the recurrence spec is hardcoded ``status="live"``, and
``POST /api/model/select`` accepts the recurrence model with HTTP 200 whether or not
``recurrence_service_url`` is configured — while the live backend stays the default. These tests
pin that reality so the docstring and the behaviour cannot drift apart again. (Reproduced live
during the 2026-08-26 re-drive via ``util/ad-hoc/e2e_fcandidate_model_select_probe.py`` in
juniper-ml.)

**D-11** — ``juniper_canopy/__init__.py`` and ``src/__init__.py`` carried a hardcoded
``__version__ = "0.5.0"`` while ``pyproject.toml`` was ``0.6.0``. Both now resolve from
``importlib.metadata`` (the same source as ``/v1/health`` and the About panel), so the literal
can never rot again; the fallback tracks ``pyproject.toml``.
"""

import importlib
import importlib.metadata
import tomllib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import main
from backend.demo_backend import DemoBackend
from demo_mode import DemoMode
from model_registry import get_model_spec, model_is_trainable

_REPO_ROOT = Path(__file__).resolve().parents[3]
PYPROJECT_VERSION = tomllib.loads((_REPO_ROOT / "pyproject.toml").read_text())["project"]["version"]


@pytest.mark.regression
@pytest.mark.unit
class TestD8RecurrenceSelectionIsNotGatedOnConfig:
    """The unset-``recurrence_service_url`` path is a reachable normal flow, not a UI-gated one."""

    def test_recurrence_spec_is_live_so_the_picker_shows_it_trainable(self):
        spec = get_model_spec("recurrence")
        assert spec is not None
        assert spec.status == "live"
        # The Train-gate reads status only; a "live" model is trainable regardless of whether a
        # recurrence service URL is configured — so the picker never gates it out on config.
        assert model_is_trainable("recurrence") is True

    def test_select_recurrence_without_service_url_is_accepted_and_backend_unchanged(self, monkeypatch):
        # No recurrence (or cascor) service URL configured — the D-8 condition.
        monkeypatch.setattr(main.settings, "recurrence_service_url", None, raising=False)
        # A bare TestClient never runs the lifespan, so install a demo backend directly.
        monkeypatch.setattr(main, "backend", DemoBackend(DemoMode(update_interval=1.0)), raising=False)

        # The routing predicate must agree the target is NOT the recurrence backend when unconfigured.
        assert main._selection_targets_recurrence("recurrence") is False

        client = TestClient(main.app)
        resp = client.post("/api/model/select", json={"nn_model": "recurrence"})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        # Selection recorded, status reported live, but the live backend stayed the default —
        # the "successful selection of a model that is not actually active" the docstring now warns of.
        assert body["nn_model"] == "recurrence"
        assert body["status"] == "live"
        assert body["swapped"] is False
        assert body["backend"] != "recurrence"

    def test_docstring_no_longer_claims_a_ui_config_gate(self):
        import backend as backend_pkg

        doc = backend_pkg._try_create_recurrence_backend.__doc__ or ""
        assert "gates an unconfigured recurrence model out of the picker" not in doc
        assert "REACHABLE normal path" in doc


@pytest.mark.regression
@pytest.mark.unit
class TestD11VersionSingleSource:
    """The package ``__version__`` resolves from installed metadata, not a stale literal."""

    def _expected(self) -> str:
        try:
            return importlib.metadata.version("juniper-canopy")
        except importlib.metadata.PackageNotFoundError:
            return PYPROJECT_VERSION

    def test_juniper_canopy_version_resolves_from_metadata(self):
        import juniper_canopy

        importlib.reload(juniper_canopy)
        assert juniper_canopy.__version__ == self._expected()
        assert juniper_canopy.__version__ != "0.5.0" or self._expected() == "0.5.0"

    def test_src_shim_version_matches_and_is_not_a_stale_literal(self):
        import src as src_pkg

        importlib.reload(src_pkg)
        assert src_pkg.__version__ == self._expected()

    def test_no_hardcoded_version_literal_remains_in_either_init(self):
        for rel in ("juniper_canopy/__init__.py", "src/__init__.py"):
            text = (_REPO_ROOT / rel).read_text(encoding="utf-8")
            assert '__version__ = "0.5.0"' not in text, f"{rel} still carries the stale 0.5.0 literal"
            assert "importlib.metadata.version" in text, f"{rel} must single-source the version from installed metadata"
