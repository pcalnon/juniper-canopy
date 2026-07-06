#!/usr/bin/env python
"""SEC-F22 / D2 startup loopback bind-guard tests.

Covers ``security.is_loopback_host`` and ``security.enforce_loopback_bind_guard``
-- the fail-closed startup invariant that canopy refuses to start on a
non-loopback bind unless a perimeter is attested by AT LEAST ONE of two flags
(``loopback_publish_attested`` / ``auth_proxy_attested``). The §9 cases:
non-loopback + neither attest -> refuse to start; non-loopback + either attest
-> binds; loopback -> binds regardless.

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
    """``enforce_loopback_bind_guard`` fail-closed startup semantics (D2, §9).

    Two independent attestations (``loopback_publish_attested`` /
    ``auth_proxy_attested``); a non-loopback bind is allowed iff at least one is
    True, and hard-fails otherwise (no warning-only mode).
    """

    def test_non_loopback_without_any_attest_refuses_to_start(self):
        """Non-loopback + NEITHER attest -> refuse to start (raise)."""
        with pytest.raises(NonLoopbackBindError):
            enforce_loopback_bind_guard("0.0.0.0", loopback_publish_attested=False, auth_proxy_attested=False)

    def test_non_loopback_with_loopback_publish_attest_binds(self):
        """Non-loopback + loopback-publish attest -> binds (no raise)."""
        assert enforce_loopback_bind_guard("0.0.0.0", loopback_publish_attested=True, auth_proxy_attested=False) is None

    def test_non_loopback_with_auth_proxy_attest_binds(self):
        """Non-loopback + auth-proxy attest -> binds (no raise)."""
        assert enforce_loopback_bind_guard("0.0.0.0", loopback_publish_attested=False, auth_proxy_attested=True) is None

    def test_non_loopback_with_both_attests_binds(self):
        """Non-loopback + both attestations -> binds (no raise)."""
        assert enforce_loopback_bind_guard("0.0.0.0", loopback_publish_attested=True, auth_proxy_attested=True) is None

    @pytest.mark.parametrize("host", ["127.0.0.1", "::1", "localhost"])
    def test_loopback_binds_regardless_of_attest(self, host):
        """Loopback -> binds regardless of either attest flag (all 4 combos)."""
        for lp in (False, True):
            for ap in (False, True):
                assert enforce_loopback_bind_guard(host, loopback_publish_attested=lp, auth_proxy_attested=ap) is None

    def test_refusal_logs_critical(self):
        """The refusal path emits a fail-loud CRITICAL log."""
        logger = logging.getLogger("test.bindguard.critical")
        with patch.object(logger, "critical") as mock_crit:
            with pytest.raises(NonLoopbackBindError):
                enforce_loopback_bind_guard("10.0.0.5", loopback_publish_attested=False, auth_proxy_attested=False, logger=logger)
        mock_crit.assert_called_once()

    def test_loopback_publish_attest_logs_warning_naming_it(self):
        """The loopback-publish attested path is loud (WARNING) and names the flag."""
        logger = logging.getLogger("test.bindguard.warn.publish")
        with patch.object(logger, "warning") as mock_warn:
            enforce_loopback_bind_guard("0.0.0.0", loopback_publish_attested=True, auth_proxy_attested=False, logger=logger)
        mock_warn.assert_called_once()
        rendered = " ".join(str(a) for a in mock_warn.call_args.args)
        assert "JUNIPER_CANOPY_LOOPBACK_PUBLISH_ATTESTED" in rendered
        assert "JUNIPER_CANOPY_AUTH_PROXY_ATTESTED" not in rendered

    def test_auth_proxy_attest_logs_warning_naming_it(self):
        """The auth-proxy attested path is loud (WARNING) and names the flag."""
        logger = logging.getLogger("test.bindguard.warn.proxy")
        with patch.object(logger, "warning") as mock_warn:
            enforce_loopback_bind_guard("0.0.0.0", loopback_publish_attested=False, auth_proxy_attested=True, logger=logger)
        mock_warn.assert_called_once()
        rendered = " ".join(str(a) for a in mock_warn.call_args.args)
        assert "JUNIPER_CANOPY_AUTH_PROXY_ATTESTED" in rendered
        assert "JUNIPER_CANOPY_LOOPBACK_PUBLISH_ATTESTED" not in rendered

    def test_both_attests_warning_names_both(self):
        """Both attestations -> the WARNING names both permitting flags."""
        logger = logging.getLogger("test.bindguard.warn.both")
        with patch.object(logger, "warning") as mock_warn:
            enforce_loopback_bind_guard("0.0.0.0", loopback_publish_attested=True, auth_proxy_attested=True, logger=logger)
        mock_warn.assert_called_once()
        rendered = " ".join(str(a) for a in mock_warn.call_args.args)
        assert "JUNIPER_CANOPY_LOOPBACK_PUBLISH_ATTESTED" in rendered
        assert "JUNIPER_CANOPY_AUTH_PROXY_ATTESTED" in rendered

    def test_loopback_path_is_silent(self):
        """The loopback (allowed) path logs nothing -- no warning/critical."""
        logger = logging.getLogger("test.bindguard.quiet")
        with patch.object(logger, "warning") as mock_warn, patch.object(logger, "critical") as mock_crit:
            enforce_loopback_bind_guard("127.0.0.1", loopback_publish_attested=False, auth_proxy_attested=False, logger=logger)
        mock_warn.assert_not_called()
        mock_crit.assert_not_called()


@pytest.mark.unit
class TestBindGuardSettingsIntegration:
    """The Settings fields + default host keep canopy loopback-safe out of the box."""

    def test_settings_default_is_loopback_safe(self):
        from settings import Settings

        s = Settings()
        # Shipped defaults: neither attestation, loopback bind -> canopy starts.
        assert s.loopback_publish_attested is False
        assert s.auth_proxy_attested is False
        assert is_loopback_host(s.server.host) is True
        # The guard is a no-op on the shipped defaults.
        assert (
            enforce_loopback_bind_guard(
                s.server.host,
                loopback_publish_attested=s.loopback_publish_attested,
                auth_proxy_attested=s.auth_proxy_attested,
            )
            is None
        )
