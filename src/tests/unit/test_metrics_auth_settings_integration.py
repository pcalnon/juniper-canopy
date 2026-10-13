#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Pin Settings.metrics_trusted_ips resolution + fail-loud validator
#
# Author:        Paul Calnon
# Version:       0.5.0
# File Name:     test_metrics_auth_settings_integration.py
# File Path:     ${HOME}/Development/python/Juniper/juniper-canopy/src/tests/unit/
#
# Date Created:  2026-05-29
# Last Modified: 2026-05-29
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
#
# Description:
#    Regression tests for canopy's ``Settings.metrics_trusted_ips`` field
#    and its ``_validate_metrics_trusted_ips`` field validator. The
#    middleware itself is exhaustively tested in juniper-observability
#    0.3.0's ``tests/test_metrics_auth_middleware.py``; this suite pins
#    the canopy-side wiring: the field exists, the default is loopback,
#    the validator delegates to ``parse_trusted_networks`` (fail-loud
#    behaviour), and the canopy ``EXEMPT_PATH_PREFIXES`` already covers
#    ``/metrics`` so ``SecurityMiddleware`` is out of the picture.
#
#####################################################################################################################################################################################################
"""Unit tests for canopy's metrics_trusted_ips wiring."""

from __future__ import annotations

import pytest

from canopy_constants import SecurityConstants
from settings import Settings

_ENV_VARS_TO_SCRUB = (
    "JUNIPER_CANOPY_METRICS_ENABLED",
    "JUNIPER_CANOPY_METRICS_TRUSTED_IPS",
)


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch):
    """Strip env vars this module touches so tests start from a known state."""
    for name in _ENV_VARS_TO_SCRUB:
        monkeypatch.delenv(name, raising=False)
    yield monkeypatch


class TestMetricsTrustedIpsField:
    """``Settings.metrics_trusted_ips`` — default value, env override,
    JSON-list shape."""

    def test_default_is_loopback_only(self, clean_env: pytest.MonkeyPatch) -> None:
        assert Settings().metrics_trusted_ips == ["127.0.0.1", "::1"]

    def test_env_var_widens_to_cidr_list(self, clean_env: pytest.MonkeyPatch) -> None:
        """Pydantic-settings auto-deserialises JSON lists for ``list[str]``
        fields. Operators set ``JUNIPER_CANOPY_METRICS_TRUSTED_IPS`` as
        a JSON list so docker compose substitution works the same way
        it does for juniper-data and juniper-cascor."""
        clean_env.setenv(
            "JUNIPER_CANOPY_METRICS_TRUSTED_IPS",
            '["172.18.0.0/16", "127.0.0.1", "::1"]',
        )
        assert Settings().metrics_trusted_ips == [
            "172.18.0.0/16",
            "127.0.0.1",
            "::1",
        ]

    def test_env_var_accepts_bare_ipv6_cidr(self, clean_env: pytest.MonkeyPatch) -> None:
        clean_env.setenv(
            "JUNIPER_CANOPY_METRICS_TRUSTED_IPS",
            '["fd00::/8"]',
        )
        assert Settings().metrics_trusted_ips == ["fd00::/8"]


class TestMetricsTrustedIpsValidator:
    """``_validate_metrics_trusted_ips`` fails loud on unparseable
    entries — delegates to the same ``parse_trusted_networks`` the
    middleware uses, so the failure surfaces at ``Settings()`` not at
    the first scrape."""

    def test_invalid_cidr_raises_at_settings_construction(self) -> None:
        """A typo like ``172.18.0.0/164`` must surface at startup."""
        import pydantic_core

        with pytest.raises((ValueError, pydantic_core.ValidationError)):
            Settings(
                metrics_enabled=True,
                metrics_trusted_ips=["172.18.0.0/164"],
            )

    def test_invalid_string_raises_at_settings_construction(self) -> None:
        """``"not-an-ip"`` is not a valid IP or CIDR; must raise."""
        import pydantic_core

        with pytest.raises((ValueError, pydantic_core.ValidationError)):
            Settings(
                metrics_enabled=True,
                metrics_trusted_ips=["not-an-ip"],
            )

    def test_valid_cidr_and_bare_ip_mix_accepted(self) -> None:
        s = Settings(
            metrics_enabled=True,
            metrics_trusted_ips=["172.18.0.0/16", "fd00::/8", "127.0.0.1"],
        )
        assert s.metrics_trusted_ips == ["172.18.0.0/16", "fd00::/8", "127.0.0.1"]

    def test_validator_uses_shared_parse_trusted_networks(self) -> None:
        """Canonical contract: the canopy validator must delegate to
        ``juniper_observability.parse_trusted_networks`` so the failure
        message is consistent across the three Juniper services."""
        from juniper_observability import parse_trusted_networks

        with pytest.raises(ValueError):
            parse_trusted_networks(["172.18.0.0/164"])


class TestMetricsExemptPathInvariant:
    """``/metrics`` is exempt-by-prefix in canopy's ``SecurityMiddleware``
    so ``MetricsAuthMiddleware`` is the only gate. Pin the invariant —
    if a future refactor drops the prefix exempt, ``MetricsAuthMiddleware``
    becomes dead code on any deployment that has ``api_keys`` set."""

    def test_metrics_prefix_in_exempt_prefixes(self) -> None:
        assert "/metrics" in SecurityConstants.EXEMPT_PATH_PREFIXES
