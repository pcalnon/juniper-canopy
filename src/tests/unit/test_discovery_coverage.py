"""Extended coverage tests for cascor auto-discovery logic.

Covers _probe_url_sync directly, timeout behavior, malformed responses,
default parameter handling, and edge cases not in test_cascor_discovery.py.
"""

import json
import urllib.error
import urllib.request
from unittest.mock import MagicMock, patch

import pytest

from discovery import (
    _DEFAULT_HOST,
    _DEFAULT_PORTS,
    _DEFAULT_TIMEOUT,
    _probe_url_sync,
    discover_cascor,
    probe_cascor_url,
)


@pytest.mark.unit
class TestProbeUrlSync:
    """Direct tests for _probe_url_sync (synchronous probe)."""

    def test_returns_true_on_valid_health_response(self):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b'{"status": "alive"}'
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            assert _probe_url_sync("http://localhost:8200", timeout=2.0) is True

    def test_returns_false_on_non_200_status(self):
        mock_resp = MagicMock()
        mock_resp.status = 503
        mock_resp.read.return_value = b'{"status": "alive"}'
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            assert _probe_url_sync("http://localhost:8200", timeout=2.0) is False

    def test_returns_false_on_non_json_body(self):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b"<html>Not JSON</html>"
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            assert _probe_url_sync("http://localhost:8200", timeout=2.0) is False

    def test_returns_false_on_empty_body(self):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b""
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            assert _probe_url_sync("http://localhost:8200", timeout=2.0) is False

    def test_returns_false_on_missing_status_key(self):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b'{"healthy": true}'
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            assert _probe_url_sync("http://localhost:8200", timeout=2.0) is False

    def test_returns_false_on_connection_refused(self):
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused")):
            assert _probe_url_sync("http://localhost:9999", timeout=1.0) is False

    def test_returns_false_on_timeout(self):
        with patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")):
            assert _probe_url_sync("http://localhost:8200", timeout=0.001) is False

    def test_returns_false_on_http_error(self):
        with patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError("http://localhost:8200/v1/health/live", 404, "Not Found", {}, None)):
            assert _probe_url_sync("http://localhost:8200", timeout=2.0) is False

    def test_probes_correct_url_path(self):
        """Verify the probe hits /v1/health/live endpoint."""
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b'{"status": "alive"}'
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
            _probe_url_sync("http://myhost:8200", timeout=2.0)
            req_arg = mock_open.call_args[0][0]
            assert req_arg.full_url == "http://myhost:8200/v1/health/live"

    def test_passes_timeout_to_urlopen(self):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b'{"status": "alive"}'
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
            _probe_url_sync("http://localhost:8200", timeout=5.0)
            assert mock_open.call_args[1]["timeout"] == 5.0


@pytest.mark.unit
class TestProbeCascorUrlCoverage:
    """Additional coverage for probe_cascor_url async wrapper."""

    async def test_uses_executor_for_sync_call(self):
        """Verify the async wrapper delegates to executor (not blocking event loop)."""
        with patch("discovery._probe_url_sync", return_value=True) as mock_sync:
            result = await probe_cascor_url("http://localhost:8200", timeout=3.0)
            assert result is True
            mock_sync.assert_called_once_with("http://localhost:8200", 3.0)

    async def test_default_timeout_value(self):
        """Verify default timeout matches _DEFAULT_TIMEOUT."""
        with patch("discovery._probe_url_sync", return_value=False) as mock_sync:
            await probe_cascor_url("http://localhost:8200")
            mock_sync.assert_called_once_with("http://localhost:8200", _DEFAULT_TIMEOUT)


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
