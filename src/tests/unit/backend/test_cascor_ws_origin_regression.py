#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Application:   juniper-canopy
# File Name:     test_cascor_ws_origin_regression.py
# Author:        Paul Calnon
#
# Date Created:  2026-05-29
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
#
# Description:
#    E.2 PR-2-C regression coverage: ``CascorServiceAdapter`` threads the
#    configured ``ws_origin`` through to the underlying
#    ``CascorControlStream`` (via ``ControlStreamSupervisor``) so cascor's
#    fail-closed ``/ws/control`` Origin allowlist (juniper-cascor#129)
#    accepts the docker-compose canopy upgrade.
#
#    Sits next to the existing v1-prefix regression test (E.1) under
#    ``src/tests/unit/backend/``.  See juniper-ml
#    ``notes/STACK_REGRESSION_CORRECTIONS_2026-05-27.md`` §E.2 for the
#    cross-repo context.
#
#####################################################################################################################################################################################################

from unittest.mock import MagicMock, patch

import pytest

from backend.cascor_service_adapter import CascorServiceAdapter, ControlStreamSupervisor


@pytest.mark.unit
class TestSupervisorOriginForwarding:
    """``ControlStreamSupervisor`` constructs ``CascorControlStream``
    inside its background ``_connect_loop`` and must forward the
    configured Origin.  This guards the cascor-client>=0.5.0 contract
    that ``origin=None`` preserves the pre-0.5.0 behaviour (no Origin
    header sent) and that an explicit Origin is propagated unchanged.
    """

    def test_supervisor_stores_origin(self):
        supervisor = ControlStreamSupervisor(ws_url="ws://juniper-cascor:8200", api_key="key1", ws_origin="http://juniper-canopy:8050")
        assert supervisor._ws_origin == "http://juniper-canopy:8050"

    def test_supervisor_origin_defaults_to_none(self):
        supervisor = ControlStreamSupervisor(ws_url="ws://localhost:8200")
        assert supervisor._ws_origin is None


@pytest.mark.unit
class TestAdapterOriginForwarding:
    """``CascorServiceAdapter`` is canopy's only ``CascorServiceAdapter``
    construction site (``src/backend/__init__.py:81``).  The adapter must
    construct its ``ControlStreamSupervisor`` with the same ``ws_origin``
    so the env-var → settings → adapter → supervisor → stream chain
    forwards correctly end-to-end.
    """

    def test_adapter_forwards_ws_origin_to_supervisor(self):
        with patch("backend.cascor_service_adapter.JuniperCascorClient", new=MagicMock()):
            adapter = CascorServiceAdapter(
                service_url="http://juniper-cascor:8200",
                api_key="key1",
                ws_origin="http://juniper-canopy:8050",
            )
            assert adapter._ws_origin == "http://juniper-canopy:8050"
            assert adapter._control_supervisor._ws_origin == "http://juniper-canopy:8050"

    def test_adapter_origin_defaults_to_none(self):
        """Backwards-compat: callers that don't pass ``ws_origin`` keep
        the pre-PR-2-C behaviour of sending no Origin header on the
        ``/ws/control`` upgrade.
        """
        with patch("backend.cascor_service_adapter.JuniperCascorClient", new=MagicMock()):
            adapter = CascorServiceAdapter(service_url="http://juniper-cascor:8200")
            assert adapter._ws_origin is None
            assert adapter._control_supervisor._ws_origin is None


@pytest.mark.unit
class TestSettingsCascorWsOrigin:
    """The canopy ``Settings.cascor_ws_origin`` field controls the
    Origin string the adapter receives.  Default is derived from
    ``socket.gethostname()`` so it tracks the actual runtime topology
    (compose service name in docker, pod name in k8s, dev box name
    under host-mode dev). Env var ``JUNIPER_CANOPY_CASCOR_WS_ORIGIN``
    overrides; empty-string opt-out is handled at the
    ``create_backend`` layer (``src/backend/__init__.py``) where the
    empty string is mapped to ``None`` before being passed to the
    adapter.
    """

    def test_default_is_runtime_hostname_derived(self, monkeypatch):
        """Default value is derived from ``socket.gethostname()`` so a
        fresh ``docker compose up`` works without any operator action
        on env vars — regardless of which compose service name canopy
        runs under (``juniper-canopy``, ``juniper-canopy-demo``, etc.).
        """
        import socket

        monkeypatch.delenv("JUNIPER_CANOPY_CASCOR_WS_ORIGIN", raising=False)
        from settings import Settings

        settings = Settings()
        expected = f"http://{socket.gethostname()}:8050"
        assert settings.cascor_ws_origin == expected

    def test_default_uses_factory_not_module_load_value(self, monkeypatch):
        """The default is wired as a ``Field(default_factory=…)`` so it
        evaluates per-``Settings()``-instantiation, not once at module
        load. This lets tests / runtime code monkey-patch
        ``socket.gethostname`` if they really need to.
        """
        import socket

        monkeypatch.delenv("JUNIPER_CANOPY_CASCOR_WS_ORIGIN", raising=False)
        from settings import Settings, _default_cascor_ws_origin

        # Patch gethostname so a fresh Settings() instance picks up the new value.
        monkeypatch.setattr(socket, "gethostname", lambda: "test-host-name")
        # The factory itself reads at call time, so calling it here reflects
        # the patched value.
        assert _default_cascor_ws_origin() == "http://test-host-name:8050"
        # And a freshly-constructed Settings consumes the same factory.
        settings = Settings()
        assert settings.cascor_ws_origin == "http://test-host-name:8050"

    def test_env_var_override(self, monkeypatch):
        monkeypatch.setenv("JUNIPER_CANOPY_CASCOR_WS_ORIGIN", "http://override:8050")
        from settings import Settings

        settings = Settings()
        assert settings.cascor_ws_origin == "http://override:8050"
