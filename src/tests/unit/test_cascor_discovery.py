"""Tests for cascor auto-discovery logic.

METRICS-MON R4.2: ``probe_cascor_url`` is now native async via
``httpx.AsyncClient`` (replaced the previous
``asyncio.get_running_loop().run_in_executor(...)`` offload of
``urllib.request.urlopen``). Tests patch ``httpx.AsyncClient.get``
accordingly.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from discovery import discover_cascor, probe_cascor_url


class TestProbeCascorUrl:
    """Tests for probe_cascor_url() HTTP probe function."""

    async def test_probe_returns_true_on_healthy_response(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "alive"}

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            result = await probe_cascor_url("http://localhost:8200")
        assert result is True

    async def test_probe_returns_false_on_connection_error(self):
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=httpx.ConnectError("refused")):
            result = await probe_cascor_url("http://localhost:8200")
        assert result is False

    async def test_probe_returns_false_on_wrong_status(self):
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.json.return_value = {"status": "down"}
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            result = await probe_cascor_url("http://localhost:8200")
        assert result is False

    async def test_probe_returns_false_on_wrong_body(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "not-cascor"}
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            result = await probe_cascor_url("http://localhost:8200")
        assert result is False

    async def test_probe_returns_false_on_timeout(self):
        """R4.2: ``httpx.ReadTimeout`` (and its parent ``TimeoutException``)
        falls through to the broad-except path; result is False."""
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=httpx.ReadTimeout("timeout")):
            result = await probe_cascor_url("http://localhost:8200", timeout=0.05)
        assert result is False


class TestDiscoverCascor:
    """Tests for discover_cascor() async discovery function."""

    async def test_returns_url_when_cascor_found(self):
        with patch("discovery.probe_cascor_url", new_callable=AsyncMock, return_value=True):
            result = await discover_cascor(host="localhost", ports=[8200])
        assert result == "http://localhost:8200"

    async def test_returns_none_when_no_cascor(self):
        with patch("discovery.probe_cascor_url", new_callable=AsyncMock, return_value=False):
            result = await discover_cascor(host="localhost", ports=[8200, 8201])
        assert result is None

    async def test_returns_first_responding_port(self):
        async def mock_probe(url, timeout=2.0):
            return "8201" in url  # Only respond on 8201

        with patch("discovery.probe_cascor_url", side_effect=mock_probe):
            result = await discover_cascor(host="localhost", ports=[8200, 8201, 8202])
        assert result == "http://localhost:8201"

    async def test_empty_ports_returns_none(self):
        result = await discover_cascor(host="localhost", ports=[])
        assert result is None
