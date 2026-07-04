#!/usr/bin/env python
"""SEC-F22 / D2 startup loopback bind-guard tests.

Covers ``security.is_loopback_host`` and ``security.enforce_loopback_bind_guard``
-- the fail-closed startup invariant that canopy refuses to start on a
non-loopback bind unless a fronting authenticating proxy is attested. The three
§9 cases: non-loopback + no attest -> refuse to start; non-loopback + attest ->
binds; loopback -> binds regardless.

Design-of-record: juniper-ml
notes/JUNIPER_CANOPY_CONTROL_SURFACE_AUTH_AND_NAT_DESIGN_2026-07-03.md
§4 (Option A) / §8 (D2).
"""

import logging
from unittest.mock import patch

import pytest

from security import NonLoopbackBindError, enforce_loopback_bind_guard, is_loopback_host


@pytest.mark.unit
class TestIsLoopbackHost:
    """``is_loopback_host`` classifies a bind host (SEC-F22 / D2)."""

    @pytest.mark.parametrize(
        "host",
        [
            "127.0.0.1",
            "127.0.0.5",
            "127.1.2.3",
            "::1",
            "[::1]",
            "localhost",
            "LOCALHOST",
            "  127.0.0.1  ",
        ],
    )
    def test_loopback_hosts_true(self, host):
        assert is_loopback_host(host) is True

    @pytest.mark.parametrize(
        "host",
        [
            "0.0.0.0",
            "::",
            "10.0.0.5",
            "172.23.0.1",
            "192.168.1.10",
            "8.8.8.8",
            "",
            "   ",
            "not-an-ip",
            "example.com",
        ],
    )
    def test_non_loopback_hosts_false(self, host):
        assert is_loopback_host(host) is False


@pytest.mark.unit
class TestEnforceLoopbackBindGuard:
    """``enforce_loopback_bind_guard`` fail-closed startup semantics (D2, §9)."""

    def test_non_loopback_without_attest_refuses_to_start(self):
        """Non-loopback + no attest -> refuse to start (raise)."""
        with pytest.raises(NonLoopbackBindError):
            enforce_loopback_bind_guard("0.0.0.0", attested=False)

    def test_non_loopback_with_attest_binds(self):
        """Non-loopback + attest -> binds (no raise)."""
        assert enforce_loopback_bind_guard("0.0.0.0", attested=True) is None

    @pytest.mark.parametrize("host", ["127.0.0.1", "::1", "localhost"])
    def test_loopback_binds_regardless_of_attest(self, host):
        """Loopback -> binds regardless of the attest flag."""
        assert enforce_loopback_bind_guard(host, attested=False) is None
        assert enforce_loopback_bind_guard(host, attested=True) is None

    def test_refusal_logs_critical(self):
        """The refusal path emits a fail-loud CRITICAL log."""
        logger = logging.getLogger("test.bindguard.critical")
        with patch.object(logger, "critical") as mock_crit:
            with pytest.raises(NonLoopbackBindError):
                enforce_loopback_bind_guard("10.0.0.5", attested=False, logger=logger)
        mock_crit.assert_called_once()

    def test_attested_non_loopback_logs_warning(self):
        """The attested non-loopback path is loud (WARNING) but allowed."""
        logger = logging.getLogger("test.bindguard.warn")
        with patch.object(logger, "warning") as mock_warn:
            enforce_loopback_bind_guard("0.0.0.0", attested=True, logger=logger)
        mock_warn.assert_called_once()

    def test_loopback_path_is_silent(self):
        """The loopback (allowed) path logs nothing -- no warning/critical."""
        logger = logging.getLogger("test.bindguard.quiet")
        with patch.object(logger, "warning") as mock_warn, patch.object(logger, "critical") as mock_crit:
            enforce_loopback_bind_guard("127.0.0.1", attested=False, logger=logger)
        mock_warn.assert_not_called()
        mock_crit.assert_not_called()


@pytest.mark.unit
class TestBindGuardSettingsIntegration:
    """The Settings field + default host keep canopy loopback-safe out of the box."""

    def test_settings_default_is_loopback_safe(self):
        from settings import Settings

        s = Settings()
        # Shipped defaults: no attestation, loopback bind -> canopy starts.
        assert s.fronting_auth_attested is False
        assert is_loopback_host(s.server.host) is True
        # The guard is a no-op on the shipped defaults.
        assert enforce_loopback_bind_guard(s.server.host, attested=s.fronting_auth_attested) is None
