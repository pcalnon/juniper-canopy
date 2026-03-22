"""
Regression tests for demo mode priority and create_backend() behavior.

Guards against:
  R1: CASCOR_DEMO_MODE=1 must take absolute priority over CASCOR_SERVICE_URL
      and over any auto-discovery logic.
  R2: create_backend() must be synchronous and must never perform network I/O.
      Auto-discovery runs only in the FastAPI lifespan (main.py), not here.
  R3: When CASCOR_SERVICE_URL is absent and demo mode is not forced, create_backend()
      returns DemoBackend (fallback), unchanged from pre-discovery behaviour.
"""
from unittest.mock import patch, MagicMock

import pytest

from backend.demo_backend import DemoBackend


def _make_backend(monkeypatch, env_vars: dict):
    """Set env vars and call create_backend() from a fresh import."""
    for key, value in env_vars.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    from backend import create_backend
    return create_backend()


# ── R1: Demo mode priority ────────────────────────────────────────────────────

class TestDemoModePriority:
    """CASCOR_DEMO_MODE=1 always wins, regardless of other env vars."""

    def test_demo_beats_service_url(self, monkeypatch):
        """R1 — demo mode set + service URL set → DemoBackend."""
        backend = _make_backend(monkeypatch, {
            "CASCOR_DEMO_MODE": "1",
            "CASCOR_SERVICE_URL": "http://localhost:8200",
        })
        assert isinstance(backend, DemoBackend)
        assert backend.backend_type == "demo"

    def test_demo_beats_service_url_true(self, monkeypatch):
        """R1 — CASCOR_DEMO_MODE=true + service URL set → DemoBackend."""
        backend = _make_backend(monkeypatch, {
            "CASCOR_DEMO_MODE": "true",
            "CASCOR_SERVICE_URL": "http://cascor.internal:8200",
        })
        assert backend.backend_type == "demo"

    def test_demo_beats_service_url_yes(self, monkeypatch):
        """R1 — CASCOR_DEMO_MODE=yes + service URL set → DemoBackend."""
        backend = _make_backend(monkeypatch, {
            "CASCOR_DEMO_MODE": "yes",
            "CASCOR_SERVICE_URL": "http://cascor.internal:8200",
        })
        assert backend.backend_type == "demo"

    def test_demo_no_network_io_when_service_url_also_set(self, monkeypatch):
        """R1+R2 — demo mode must not probe CASCOR_SERVICE_URL even when it is set."""
        with patch("socket.create_connection") as mock_sock, \
             patch("urllib.request.urlopen") as mock_urlopen:
            backend = _make_backend(monkeypatch, {
                "CASCOR_DEMO_MODE": "1",
                "CASCOR_SERVICE_URL": "http://localhost:8200",
            })
            mock_sock.assert_not_called()
            mock_urlopen.assert_not_called()
        assert backend.backend_type == "demo"


# ── R2: No network I/O in create_backend() ────────────────────────────────────

class TestCreateBackendNoNetworkIO:
    """create_backend() must be synchronous and perform no network I/O."""

    def test_no_network_io_in_demo_fallback(self, monkeypatch):
        """R2 — no service URL, no demo mode → DemoBackend with zero network calls."""
        with patch("socket.create_connection") as mock_sock, \
             patch("urllib.request.urlopen") as mock_urlopen:
            backend = _make_backend(monkeypatch, {
                "CASCOR_DEMO_MODE": "0",
                "CASCOR_SERVICE_URL": None,
            })
            mock_sock.assert_not_called()
            mock_urlopen.assert_not_called()
        assert backend.backend_type == "demo"

    def test_create_backend_is_synchronous(self, monkeypatch):
        """R2 — create_backend() returns a concrete object, not a coroutine."""
        import inspect
        backend = _make_backend(monkeypatch, {
            "CASCOR_DEMO_MODE": "1",
            "CASCOR_SERVICE_URL": None,
        })
        assert not inspect.iscoroutine(backend), "create_backend() must not return a coroutine"


# ── R3: Fallback to DemoBackend when CASCOR_SERVICE_URL is absent ─────────────

class TestFallbackBehaviour:
    """When no env vars are configured, create_backend() falls back to demo mode."""

    def test_no_env_vars_returns_demo_backend(self, monkeypatch):
        """R3 — empty env → DemoBackend (fallback)."""
        backend = _make_backend(monkeypatch, {
            "CASCOR_DEMO_MODE": "0",
            "CASCOR_SERVICE_URL": None,
        })
        assert isinstance(backend, DemoBackend)
        assert backend.backend_type == "demo"

    def test_demo_mode_false_no_url_returns_demo_backend(self, monkeypatch):
        """R3 — CASCOR_DEMO_MODE=false, no URL → DemoBackend fallback."""
        backend = _make_backend(monkeypatch, {
            "CASCOR_DEMO_MODE": "false",
            "CASCOR_SERVICE_URL": None,
        })
        assert backend.backend_type == "demo"

    def test_discovery_env_var_absent_means_demo_backend(self, monkeypatch):
        """R3 — CASCOR_SERVICE_URL absent means discovery never ran; factory falls back."""
        monkeypatch.delenv("CASCOR_SERVICE_URL", raising=False)
        monkeypatch.setenv("CASCOR_DEMO_MODE", "0")
        from backend import create_backend
        backend = create_backend()
        assert isinstance(backend, DemoBackend)
