"""P2-4 (Issue #3) — ``CascadeServiceAdapter`` experimental_functions methods.

Covers ``get_experimental_functions`` + ``set_experimental_functions`` on
the cascor REST adapter. These proxy ``GET/POST /v1/admin/experimental_functions``
(cascor #245 P2-1a) and feed the canopy backend's
``/api/admin/experimental_functions`` route (which the Dash callback layer
calls). F2.10 server-authoritative: the adapter trusts cascor's response body.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

_jcc = pytest.importorskip("juniper_cascor_client", reason="juniper-cascor-client not installed")
if getattr(_jcc, "_is_stub", False):
    pytest.skip("juniper-cascor-client is a test stub", allow_module_level=True)

from juniper_cascor_client.exceptions import JuniperCascorClientError

from backend.cascor_service_adapter import CascorServiceAdapter


@pytest.fixture
def adapter():
    a = CascorServiceAdapter(service_url="http://localhost:8200")
    a._client = MagicMock()
    return a


class TestGetExperimentalFunctions:
    def test_returns_enabled_true_when_cascor_says_true(self, adapter):
        adapter._client._request.return_value = {"data": {"enabled": True}}
        result = adapter.get_experimental_functions()
        assert result == {"ok": True, "enabled": True}
        adapter._client._request.assert_called_once_with("GET", "/admin/experimental_functions")

    def test_returns_enabled_false_when_cascor_says_false(self, adapter):
        adapter._client._request.return_value = {"data": {"enabled": False}}
        result = adapter.get_experimental_functions()
        assert result == {"ok": True, "enabled": False}

    def test_returns_safe_default_on_missing_field(self, adapter):
        """If cascor's response is structurally valid but lacks the
        ``enabled`` key, treat as ``False`` (F2.10 safe default)."""
        adapter._client._request.return_value = {"data": {}}
        result = adapter.get_experimental_functions()
        assert result == {"ok": True, "enabled": False}

    def test_returns_error_on_cascor_failure(self, adapter):
        adapter._client._request.side_effect = JuniperCascorClientError("connection refused")
        result = adapter.get_experimental_functions()
        assert result["ok"] is False
        assert "connection refused" in result["error"]
        # Safe default — gate treated as closed when we can't confirm.
        assert result["enabled"] is False


class TestSetExperimentalFunctions:
    def test_writes_true_and_returns_authoritative_value(self, adapter):
        """Cascor's response body uses ``experimental_functions_enabled``
        as the field name (per cascor's lifecycle.set_experimental_functions).
        Adapter unwraps it and returns ``enabled`` for canopy uniformity."""
        adapter._client._request.return_value = {"data": {"experimental_functions_enabled": True}}
        result = adapter.set_experimental_functions(True)
        assert result == {"ok": True, "enabled": True}
        adapter._client._request.assert_called_once_with("POST", "/admin/experimental_functions", json={"enabled": True})

    def test_writes_false_and_returns_authoritative_value(self, adapter):
        adapter._client._request.return_value = {"data": {"experimental_functions_enabled": False}}
        result = adapter.set_experimental_functions(False)
        assert result == {"ok": True, "enabled": False}

    def test_handles_legacy_response_field_name(self, adapter):
        """If cascor returns ``enabled`` (legacy / future-rename) instead of
        ``experimental_functions_enabled``, the adapter still works."""
        adapter._client._request.return_value = {"data": {"enabled": True}}
        result = adapter.set_experimental_functions(True)
        assert result == {"ok": True, "enabled": True}

    def test_server_authoritative_override(self, adapter):
        """F2.10: cascor may override the request (e.g., env-var lockdown).
        The adapter returns the server's value, NOT the requested value."""
        # User requests True, server says no.
        adapter._client._request.return_value = {"data": {"experimental_functions_enabled": False}}
        result = adapter.set_experimental_functions(True)
        assert result == {"ok": True, "enabled": False}, "server-authoritative override must trump the request"

    def test_returns_error_on_cascor_failure(self, adapter):
        adapter._client._request.side_effect = JuniperCascorClientError("HTTP 503")
        result = adapter.set_experimental_functions(True)
        assert result["ok"] is False
        assert "HTTP 503" in result["error"]
        assert result["enabled"] is False
