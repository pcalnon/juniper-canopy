"""Tests for cascor auto-discovery logic."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from discovery import discover_cascor, probe_cascor_url


class TestProbeCascorUrl:
    def test_probe_returns_true_on_healthy_response(self):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"status": "alive"}'
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = asyncio.get_event_loop().run_until_complete(
                probe_cascor_url("http://localhost:8200")
            )
        assert result is True

    def test_probe_returns_false_on_connection_error(self):
        import urllib.error
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
            result = asyncio.get_event_loop().run_until_complete(
                probe_cascor_url("http://localhost:8200")
            )
        assert result is False

    def test_probe_returns_false_on_wrong_status(self):
        mock_response = MagicMock()
        mock_response.status = 503
        mock_response.read.return_value = b'{"status": "down"}'
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=mock_response):
            result = asyncio.get_event_loop().run_until_complete(
                probe_cascor_url("http://localhost:8200")
            )
        assert result is False

    def test_probe_returns_false_on_wrong_body(self):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"status": "not-cascor"}'
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=mock_response):
            result = asyncio.get_event_loop().run_until_complete(
                probe_cascor_url("http://localhost:8200")
            )
        assert result is False


class TestDiscoverCascor:
    def test_returns_url_when_cascor_found(self):
        with patch("discovery.probe_cascor_url", new_callable=AsyncMock, return_value=True):
            result = asyncio.get_event_loop().run_until_complete(
                discover_cascor(host="localhost", ports=[8200])
            )
        assert result == "http://localhost:8200"

    def test_returns_none_when_no_cascor(self):
        with patch("discovery.probe_cascor_url", new_callable=AsyncMock, return_value=False):
            result = asyncio.get_event_loop().run_until_complete(
                discover_cascor(host="localhost", ports=[8200, 8201])
            )
        assert result is None

    def test_returns_first_responding_port(self):
        async def mock_probe(url, timeout=2.0):
            return "8201" in url  # Only respond on 8201

        with patch("discovery.probe_cascor_url", side_effect=mock_probe):
            result = asyncio.get_event_loop().run_until_complete(
                discover_cascor(host="localhost", ports=[8200, 8201, 8202])
            )
        assert result == "http://localhost:8201"

    def test_empty_ports_returns_none(self):
        result = asyncio.get_event_loop().run_until_complete(
            discover_cascor(host="localhost", ports=[])
        )
        assert result is None
