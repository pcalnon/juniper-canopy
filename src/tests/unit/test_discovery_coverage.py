"""Extended coverage tests for cascor auto-discovery logic.

Covers ``probe_cascor_url`` directly, timeout behavior, malformed
responses, default parameter handling, and edge cases not in
test_cascor_discovery.py.

METRICS-MON R4.2 / seed-10: ``_probe_url_sync`` was removed when the
discovery probe migrated from ``urllib.request.urlopen`` (offloaded via
``run_in_executor``) to native async ``httpx.AsyncClient``. The
TestProbeUrlSync class below tested the now-deleted helper; it has been
replaced by ``TestProbeCascorUrlEdgeCases`` which targets the live
async path with the same coverage intent (URL-path correctness, timeout
pass-through, JSON edge cases, error mapping).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from discovery import (
    _DEFAULT_HOST,
    _DEFAULT_PORTS,
    _DEFAULT_TIMEOUT,
    discover_cascor,
    probe_cascor_url,
)


@pytest.mark.unit
class TestProbeCascorUrlEdgeCases:
    """Edge-case coverage for the native-async probe.

    Mirrors the coverage intent of the pre-R4.2 ``TestProbeUrlSync``
    class against the new ``httpx.AsyncClient``-based implementation.
    """

    async def test_returns_true_on_valid_health_response(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "alive"}
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            assert await probe_cascor_url("http://localhost:8200", timeout=2.0) is True

    async def test_returns_false_on_non_200_status(self):
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.json.return_value = {"status": "alive"}
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            assert await probe_cascor_url("http://localhost:8200", timeout=2.0) is False

    async def test_returns_false_on_non_json_body(self):
        """``response.json()`` raises on invalid JSON; broad-except → False."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Expecting value")
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            assert await probe_cascor_url("http://localhost:8200", timeout=2.0) is False

    async def test_returns_false_on_empty_body(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("empty body")
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            assert await probe_cascor_url("http://localhost:8200", timeout=2.0) is False

    async def test_returns_false_on_missing_status_key(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"healthy": True}  # wrong key
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            assert await probe_cascor_url("http://localhost:8200", timeout=2.0) is False

    async def test_returns_false_on_connection_refused(self):
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=httpx.ConnectError("Connection refused")):
            assert await probe_cascor_url("http://localhost:9999", timeout=1.0) is False

    async def test_returns_false_on_timeout(self):
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=httpx.ReadTimeout("timed out")):
            assert await probe_cascor_url("http://localhost:8200", timeout=0.001) is False

    async def test_returns_false_on_http_status_error(self):
        """HTTP 4xx/5xx with intact JSON body still maps to False (non-200 path)."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.json.return_value = {"status": "alive"}
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            assert await probe_cascor_url("http://localhost:8200", timeout=2.0) is False

    async def test_probes_correct_url_path(self):
        """Verify the probe hits ``/v1/health/live``."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "alive"}
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response) as mock_get:
            await probe_cascor_url("http://myhost:8200", timeout=2.0)
            # First positional arg is the URL passed to AsyncClient.get
            assert mock_get.call_args[0][0] == "http://myhost:8200/v1/health/live"

    async def test_default_timeout_used(self):
        """Default timeout matches _DEFAULT_TIMEOUT (no kwarg passed)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "alive"}
        # Patch AsyncClient.__init__ to capture the timeout it was constructed with.
        captured = {}
        original_init = httpx.AsyncClient.__init__

        def capture_init(self, *args, timeout=None, **kwargs):
            captured["timeout"] = timeout
            original_init(self, *args, timeout=timeout, **kwargs)

        with patch("httpx.AsyncClient.__init__", capture_init):
            with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
                await probe_cascor_url("http://localhost:8200")
        assert captured["timeout"] == _DEFAULT_TIMEOUT


@pytest.mark.unit
class TestDiscoverCascorCoverage:
    """Additional coverage for discover_cascor."""

    async def test_uses_default_ports_when_none(self):
        """Verify default ports are _DEFAULT_PORTS when not provided."""
        calls = []

        async def mock_probe(url, timeout=2.0):
            calls.append(url)
            return False

        with patch("discovery.probe_cascor_url", side_effect=mock_probe):
            result = await discover_cascor()
            assert result is None
            assert len(calls) == len(_DEFAULT_PORTS)
            for port in _DEFAULT_PORTS:
                assert f"http://{_DEFAULT_HOST}:{port}" in calls

    async def test_uses_default_host(self):
        """Verify default host is 'localhost'."""
        calls = []

        async def mock_probe(url, timeout=2.0):
            calls.append(url)
            return False

        with patch("discovery.probe_cascor_url", side_effect=mock_probe):
            await discover_cascor(ports=[8200])
            assert calls[0] == "http://localhost:8200"

    async def test_custom_host(self):
        """Verify custom host is used in probe URLs."""
        calls = []

        async def mock_probe(url, timeout=2.0):
            calls.append(url)
            return False

        with patch("discovery.probe_cascor_url", side_effect=mock_probe):
            await discover_cascor(host="cascor.internal", ports=[8200])
            assert calls[0] == "http://cascor.internal:8200"

    async def test_passes_timeout_to_probe(self):
        """Verify timeout parameter is forwarded to probe."""
        calls = []

        async def mock_probe(url, timeout=2.0):
            calls.append(timeout)
            return False

        with patch("discovery.probe_cascor_url", side_effect=mock_probe):
            await discover_cascor(ports=[8200], timeout=10.0)
            assert calls[0] == 10.0

    async def test_stops_after_first_hit(self):
        """Verify discovery stops probing after first successful response."""
        calls = []

        async def mock_probe(url, timeout=2.0):
            calls.append(url)
            return True  # All respond

        with patch("discovery.probe_cascor_url", side_effect=mock_probe):
            result = await discover_cascor(ports=[8200, 8201, 8202])
            assert result == "http://localhost:8200"
            assert len(calls) == 1  # Only probed first port

    async def test_multiple_ports_all_fail(self):
        """Verify None when all ports fail."""
        with patch("discovery.probe_cascor_url", return_value=False):
            result = await discover_cascor(ports=[8200, 8201, 8202, 8203])
            assert result is None


@pytest.mark.unit
class TestDiscoveryModuleConstants:
    """Tests for module-level constants."""

    def test_default_ports_contains_8200(self):
        assert 8200 in _DEFAULT_PORTS

    def test_default_host_is_localhost(self):
        assert _DEFAULT_HOST == "localhost"

    def test_default_timeout_is_positive(self):
        assert _DEFAULT_TIMEOUT > 0
