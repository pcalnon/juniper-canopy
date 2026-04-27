"""Tests for health check models, probe utility, and enhanced endpoints."""

from unittest.mock import patch

import pytest

from health import DependencyStatus, ReadinessResponse, probe_dependency


@pytest.mark.unit
class TestDependencyStatusModel:
    """Test DependencyStatus Pydantic model."""

    def test_healthy_status(self):
        dep = DependencyStatus(name="Test", status="healthy", latency_ms=1.5, message="ok")
        assert dep.name == "Test"
        assert dep.status == "healthy"
        assert dep.latency_ms == 1.5

    def test_unhealthy_status(self):
        dep = DependencyStatus(name="Test", status="unhealthy", message="refused")
        assert dep.status == "unhealthy"
        assert dep.latency_ms is None

    def test_not_configured_status(self):
        dep = DependencyStatus(name="CasCor", status="not_configured", message="demo mode")
        assert dep.status == "not_configured"


@pytest.mark.unit
class TestReadinessResponseModel:
    """Test ReadinessResponse Pydantic model."""

    def test_ready_response(self):
        resp = ReadinessResponse(status="ready", version="1.0.0", service="juniper-canopy")
        assert resp.status == "ready"
        assert resp.timestamp > 0
        assert resp.dependencies == {}

    def test_degraded_with_deps(self):
        dep = DependencyStatus(name="CasCor", status="unhealthy")
        resp = ReadinessResponse(
            status="degraded",
            version="1.0.0",
            service="juniper-canopy",
            dependencies={"juniper_cascor": dep},
            details={"mode": "service"},
        )
        assert resp.status == "degraded"
        assert resp.details["mode"] == "service"


@pytest.mark.unit
class TestProbeDependency:
    """Test the probe_dependency utility function."""

    @pytest.mark.asyncio
    async def test_probe_healthy(self):
        with patch("health.urllib.request.urlopen") as mock:
            mock.return_value.__enter__ = lambda s: s
            mock.return_value.__exit__ = lambda s, *a: None
            result = await probe_dependency("Test", "http://localhost:8100/v1/health/live")
            assert result.status == "healthy"
            assert result.latency_ms >= 0
            assert result.name == "Test"

    @pytest.mark.asyncio
    async def test_probe_unhealthy(self):
        with patch("health.urllib.request.urlopen", side_effect=ConnectionRefusedError("refused")):
            result = await probe_dependency("Test", "http://localhost:9999/v1/health/live")
            assert result.status == "unhealthy"
            assert "ConnectionRefusedError" in result.message

    @pytest.mark.asyncio
    async def test_probe_timeout(self):
        from urllib.error import URLError

        with patch("health.urllib.request.urlopen", side_effect=URLError("timeout")):
            result = await probe_dependency("Slow", "http://localhost:8100/v1/health/live", timeout=0.1)
            assert result.status == "unhealthy"
            assert result.latency_ms is not None


@pytest.mark.unit
class TestCanopyHealthEndpoints:
    """Test canopy health endpoints via TestClient."""

    def test_v1_health(self, client):
        """Test /v1/health returns healthy status."""
        response = client.get("/v1/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"
        assert "version" in body
        assert "training_active" in body

    def test_liveness(self, client):
        """R1.2 / seed-03: /v1/health/live returns alive + tick metadata."""
        response = client.get("/v1/health/live")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "alive"
        assert body["tick"] == "juniper-canopy"
        assert isinstance(body["duration_ms"], int)

    def test_liveness_503_when_websocket_manager_missing(self, client):
        """R1.2 / seed-03: tick raises when websocket_manager singleton is None → 503."""
        import main as main_module

        original = main_module.websocket_manager
        main_module.websocket_manager = None
        try:
            response = client.get("/v1/health/live")
            assert response.status_code == 503
            body = response.json()
            assert body["status"] == "unresponsive"
            assert body["tick"] == "juniper-canopy"
            assert "websocket_manager" in body["error"]
        finally:
            main_module.websocket_manager = original

    def test_readiness_returns_readiness_response(self, client):
        """Test /v1/health/ready returns ReadinessResponse format with header."""
        response = client.get("/v1/health/ready")
        assert response.status_code in (200, 503)  # depends on upstream availability
        # Header always set per R1.2 contract
        assert response.headers.get("X-Juniper-Readiness") in ("ready", "degraded", "not_ready")
        body = response.json()
        assert body["service"] == "juniper-canopy"
        assert "version" in body
        assert "timestamp" in body
        assert "dependencies" in body
        assert "details" in body
        assert "mode" in body["details"]
        assert "training_active" in body["details"]
        assert "websocket_manager" in body["dependencies"]

    def test_readiness_503_when_websocket_manager_missing(self, client):
        """R1.2 / seed-02: ws_manager unbound → required dep unhealthy → 503/not_ready."""
        import main as main_module

        original = main_module.websocket_manager
        main_module.websocket_manager = None
        try:
            response = client.get("/v1/health/ready")
            assert response.status_code == 503
            assert response.headers.get("X-Juniper-Readiness") == "not_ready"
            body = response.json()
            assert body["status"] == "not_ready"
            assert body["dependencies"]["websocket_manager"]["status"] == "unhealthy"
        finally:
            main_module.websocket_manager = original

    def test_readiness_degraded_keeps_200_for_optional_deps(self, client):
        """R1.2 / seed-02: optional dep unhealthy → 200/degraded (LB keeps traffic)."""
        # JuniperData is unreachable in tests, JuniperCascor is not_configured
        # → ws_manager healthy (required) + data unhealthy (optional) → degraded
        response = client.get("/v1/health/ready")
        body = response.json()
        if body["dependencies"]["juniper_data"]["status"] == "unhealthy":
            assert response.status_code == 200
            assert body["status"] == "degraded"
            assert response.headers.get("X-Juniper-Readiness") == "degraded"

    def test_readiness_includes_data_dependency(self, client):
        """Test readiness probes JuniperData."""
        response = client.get("/v1/health/ready")
        body = response.json()
        assert "juniper_data" in body["dependencies"]
        data_dep = body["dependencies"]["juniper_data"]
        assert data_dep["name"] == "JuniperData Service"
        # Will be unhealthy in test (no real service running)
        assert data_dep["status"] in ("healthy", "unhealthy")

    def test_readiness_cascor_not_configured(self, client):
        """Test readiness shows not_configured for CasCor when URL not set."""
        response = client.get("/v1/health/ready")
        body = response.json()
        cascor_dep = body["dependencies"]["juniper_cascor"]
        assert cascor_dep["status"] == "not_configured"
        assert "demo mode" in cascor_dep["message"]


@pytest.mark.unit
class TestDeprecatedEndpoints:
    """Test deprecated health endpoint aliases."""

    def test_health_deprecated(self, client):
        """Test /health still works but is deprecated."""
        response = client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"

    def test_api_health_deprecated(self, client):
        """Test /api/health still works but is deprecated."""
        response = client.get("/api/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"
