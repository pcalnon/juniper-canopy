#!/usr/bin/env python
"""SEC-F22 / D2 startup loopback bind-guard tests.

Covers ``security.is_loopback_host`` and ``security.enforce_loopback_bind_guard``
-- the fail-closed startup invariant that canopy refuses to start on a
non-loopback bind unless the operator attests the deployment perimeter. The
guard uses the owner-ratified **two-flag** bind-posture attestation (design
OQ-1): a non-loopback bind is permitted when EITHER
``JUNIPER_CANOPY_LOOPBACK_PUBLISH_ATTESTED`` (reachable only via a loopback-only
host publish -- the containerized default) OR ``JUNIPER_CANOPY_AUTH_PROXY_ATTESTED``
(a fronting authenticating proxy terminates access -- Phase 4) is set; with
NEITHER set it refuses to start (uniform hard fail, no warning-only mode).

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

    Two-flag bind-posture attestation: EITHER flag permits a non-loopback bind;
    NEITHER refuses.
    """

    def test_non_loopback_without_any_attest_refuses_to_start(self):
        """Non-loopback + NEITHER flag -> refuse to start (raise)."""
        with pytest.raises(NonLoopbackBindError):
            enforce_loopback_bind_guard("0.0.0.0", loopback_publish_attested=False, auth_proxy_attested=False)

    def test_non_loopback_with_loopback_publish_attested_binds(self):
        """Non-loopback + loopback-publish attestation -> binds (no raise)."""
        assert enforce_loopback_bind_guard("0.0.0.0", loopback_publish_attested=True, auth_proxy_attested=False) is None

    def test_non_loopback_with_auth_proxy_attested_binds(self):
        """Non-loopback + auth-proxy attestation -> binds (no raise)."""
        assert enforce_loopback_bind_guard("0.0.0.0", loopback_publish_attested=False, auth_proxy_attested=True) is None

    def test_non_loopback_with_both_attested_binds(self):
        """Non-loopback + BOTH attestations -> binds (no raise)."""
        assert enforce_loopback_bind_guard("0.0.0.0", loopback_publish_attested=True, auth_proxy_attested=True) is None

    @pytest.mark.parametrize("host", ["127.0.0.1", "::1", "localhost"])
    @pytest.mark.parametrize(
        ("loopback_publish", "auth_proxy"),
        [(False, False), (True, False), (False, True), (True, True)],
    )
    def test_loopback_binds_regardless_of_attest(self, host, loopback_publish, auth_proxy):
        """Loopback -> binds regardless of either attestation flag."""
        assert enforce_loopback_bind_guard(host, loopback_publish_attested=loopback_publish, auth_proxy_attested=auth_proxy) is None

    def test_refusal_logs_critical_naming_both_flags(self):
        """The refusal path emits a fail-loud CRITICAL log naming both env flags."""
        logger = logging.getLogger("test.bindguard.critical")
        with patch.object(logger, "critical") as mock_crit:
            with pytest.raises(NonLoopbackBindError) as excinfo:
                enforce_loopback_bind_guard("10.0.0.5", loopback_publish_attested=False, auth_proxy_attested=False, logger=logger)
        mock_crit.assert_called_once()
        (logged_message,) = mock_crit.call_args.args
        # Both env flag names appear in the CRITICAL log AND the raised error, so
        # the operator sees exactly which attestations would permit the bind.
        for text in (logged_message, str(excinfo.value)):
            assert "REFUSING TO START" in text
            assert "JUNIPER_CANOPY_LOOPBACK_PUBLISH_ATTESTED" in text
            assert "JUNIPER_CANOPY_AUTH_PROXY_ATTESTED" in text

    def test_loopback_publish_attested_warning_names_that_flag(self):
        """The loopback-publish path is loud (WARNING) and names WHICH flag permitted."""
        logger = logging.getLogger("test.bindguard.warn.looppub")
        with patch.object(logger, "warning") as mock_warn:
            enforce_loopback_bind_guard("0.0.0.0", loopback_publish_attested=True, auth_proxy_attested=False, logger=logger)
        mock_warn.assert_called_once()
        formatted = mock_warn.call_args.args[0] % mock_warn.call_args.args[1:]
        assert "JUNIPER_CANOPY_LOOPBACK_PUBLISH_ATTESTED" in formatted
        assert "JUNIPER_CANOPY_AUTH_PROXY_ATTESTED" not in formatted

    def test_auth_proxy_attested_warning_names_that_flag(self):
        """The auth-proxy path is loud (WARNING) and names WHICH flag permitted."""
        logger = logging.getLogger("test.bindguard.warn.proxy")
        with patch.object(logger, "warning") as mock_warn:
            enforce_loopback_bind_guard("0.0.0.0", loopback_publish_attested=False, auth_proxy_attested=True, logger=logger)
        mock_warn.assert_called_once()
        formatted = mock_warn.call_args.args[0] % mock_warn.call_args.args[1:]
        assert "JUNIPER_CANOPY_AUTH_PROXY_ATTESTED" in formatted
        assert "JUNIPER_CANOPY_LOOPBACK_PUBLISH_ATTESTED" not in formatted

    def test_both_attested_warning_names_both_flags(self):
        """When BOTH are set the WARNING records both permitting flags."""
        logger = logging.getLogger("test.bindguard.warn.both")
        with patch.object(logger, "warning") as mock_warn:
            enforce_loopback_bind_guard("0.0.0.0", loopback_publish_attested=True, auth_proxy_attested=True, logger=logger)
        mock_warn.assert_called_once()
        formatted = mock_warn.call_args.args[0] % mock_warn.call_args.args[1:]
        assert "JUNIPER_CANOPY_LOOPBACK_PUBLISH_ATTESTED" in formatted
        assert "JUNIPER_CANOPY_AUTH_PROXY_ATTESTED" in formatted

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

    def test_env_vars_map_to_the_two_flags(self, monkeypatch):
        """The exact env-var names (JUNIPER_CANOPY_* prefix) drive the two fields."""
        monkeypatch.setenv("JUNIPER_CANOPY_LOOPBACK_PUBLISH_ATTESTED", "true")
        monkeypatch.setenv("JUNIPER_CANOPY_AUTH_PROXY_ATTESTED", "true")
        from settings import Settings

        s = Settings()
        assert s.loopback_publish_attested is True
        assert s.auth_proxy_attested is True
