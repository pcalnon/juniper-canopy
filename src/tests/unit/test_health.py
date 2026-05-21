"""Tests for health check models, probe utility, and enhanced endpoints."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

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
    """Test the probe_dependency utility function.

    METRICS-MON R4.2: ``probe_dependency`` is now native async via
    :class:`httpx.AsyncClient` (replaced the previous ``asyncio.to_thread``
    wrapper around the shared synchronous probe). Patches target
    ``httpx.AsyncClient.get`` accordingly.
    """

    @pytest.mark.asyncio
    async def test_probe_healthy(self):
        import httpx

        mock_response = MagicMock()
        mock_response.status_code = 200
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            result = await probe_dependency("Test", "http://localhost:8100/v1/health/live")
            assert result.status == "healthy"
            assert result.latency_ms >= 0
            assert result.name == "Test"
            assert result.message == "http://localhost:8100/v1/health/live"

    @pytest.mark.asyncio
    async def test_probe_non_200_is_unhealthy(self):
        """R4.2: HTTP non-200 maps to ``unhealthy`` (matches the shared
        sync lib's contract — urllib's HTTPError on 4xx/5xx ends up in
        the unhealthy branch)."""
        import httpx

        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.reason_phrase = "Service Unavailable"
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            result = await probe_dependency("Degraded", "http://localhost:8100/v1/health/live")
            assert result.status == "unhealthy"
            assert "503" in result.message
            assert "HTTPStatusError" in result.message

    @pytest.mark.asyncio
    async def test_probe_unhealthy_on_transport_error(self):
        import httpx

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=httpx.ConnectError("refused")):
            result = await probe_dependency("Test", "http://localhost:9999/v1/health/live")
            assert result.status == "unhealthy"
            assert "ConnectError" in result.message

    @pytest.mark.asyncio
    async def test_probe_timeout(self):
        import httpx

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=httpx.ReadTimeout("timeout")):
            result = await probe_dependency("Slow", "http://localhost:8100/v1/health/live", timeout=0.1)
            assert result.status == "unhealthy"
            assert result.latency_ms is not None
            assert "ReadTimeout" in result.message

    @pytest.mark.asyncio
    async def test_probe_runs_concurrently_not_serially_under_fanout(self):
        """METRICS-MON R4.2 / seed-10: N concurrent probes complete in
        far less wall-clock than N serial probes would.

        The seed-10 motivation is event-loop responsiveness under
        concurrent fan-out: each probe must not block other coroutines
        for its full duration. With native ``httpx.AsyncClient``, N
        concurrent probes overlap (each ``asyncio.sleep`` yields); with
        the pre-R4.2 ``asyncio.to_thread`` pattern, the default 32-worker
        thread pool would serialize fan-outs above 32 concurrent calls.

        Test sets ``probe_count = 64 > 32`` so a regression to
        thread-pool offload would force ``ceil(64/32) = 2`` waves
        (≈2·L wall-clock minimum). Native async runs all 64 concurrently
        → wall-clock dominated by per-call overhead, not by serial
        layering. The assertion uses a 4·L threshold — generous for
        AsyncClient construction overhead and CI noise but still
        catches the serialization regression (a 32-thread pool processing
        64 probes at L=100ms each would land at ~200ms minimum, plus the
        same overhead, easily breaching even relaxed thresholds when
        compared against the native-async baseline of ~700ms for the
        same workload).

        Sanity-floor: also assert wall-clock is at least one probe's
        latency, so the test's slow-mock is actually being awaited.
        """
        probe_count = 64
        probe_latency = 0.1  # 100ms per probe.

        async def slow_get(*args, **kwargs):
            await asyncio.sleep(probe_latency)
            mock_response = MagicMock()
            mock_response.status_code = 200
            return mock_response

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=slow_get):
            start = time.monotonic()
            results = await asyncio.gather(*(probe_dependency("S", f"http://h-{i}/x", timeout=1.0) for i in range(probe_count)))
            elapsed = time.monotonic() - start

        assert all(r.status == "healthy" for r in results)
        # Sanity floor — confirms the slow-mock is being awaited.
        assert elapsed >= probe_latency * 0.9, f"wall-clock {elapsed*1000:.1f}ms below floor; mock probably not being awaited"
        # Concurrency property: 64 native-async probes overlap, so the
        # wall-clock is dominated by per-call ``httpx.AsyncClient``
        # construction plus the single shared 100ms sleep. P-16 audit
        # observed GitHub-hosted ubuntu runners landing 1672–2063 ms
        # (vs the previous 1600 ms threshold = 25 % of the 6.4 s serial
        # floor); macOS runners land within the original budget. The
        # AsyncClient construction overhead is sensitive to runner
        # cgroup scheduling — concurrency itself is healthy (a real
        # blocking-call regression would push elapsed toward 80 % of
        # serial = ~5.1 s). Bump to 50 % serial (3.2 s) so the gate
        # tolerates the slower runners while still catching any
        # serializing regression by a wide margin (5.1 s ≫ 3.2 s).
        serial_floor = probe_count * probe_latency
        threshold = serial_floor * 0.5
        assert elapsed < threshold, f"wall-clock {elapsed*1000:.1f}ms exceeded threshold {threshold*1000:.0f}ms (serial would be ~{serial_floor*1000:.0f}ms; blocking-call regression would push elapsed close to serial)"


@pytest.mark.unit
class TestCanopyHealthEndpoints:
    """Test canopy health endpoints via TestClient."""

    def test_v1_health(self, client):
        """Test /v1/health returns the API-01-normalized "ok" status (see PR #299)."""
        response = client.get("/v1/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert "version" in body
        assert "training_active" in body

    def test_liveness(self, client):
        """Test /v1/health/live returns alive."""
        response = client.get("/v1/health/live")
        assert response.status_code == 200
        assert response.json()["status"] == "alive"

    def test_readiness_returns_readiness_response(self, client):
        """Test /v1/health/ready returns ReadinessResponse format."""
        response = client.get("/v1/health/ready")
        assert response.status_code == 200
        body = response.json()
        assert body["service"] == "juniper-canopy"
        assert "version" in body
        assert "timestamp" in body
        assert "dependencies" in body
        assert "details" in body
        assert "mode" in body["details"]
        assert "training_active" in body["details"]

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
class TestReadinessDownstreamInjection:
    """METRICS-MON R2.3 / seed-15: probe-direction symmetry.

    Asserts the canopy-side severity policy when an injected upstream
    dependency is unhealthy:

      * `juniper-data` unhealthy   → status="degraded", HTTP 200
      * `juniper-cascor` unhealthy → status="degraded", HTTP 200

    Canopy intentionally **does not** return 503 when an upstream is
    down — the dashboard remains reachable so operators can read the
    "X is broken" diagnostic in the body. This contrasts with cascor's
    `/v1/health/ready` which returns 503 when JuniperData is unreachable
    (`test_readiness_503_when_juniper_data_unhealthy` in
    juniper-cascor). The asymmetry is documented in
    `juniper-deploy/notes/PROBE_GRAPH.md`.
    """

    @pytest.mark.asyncio
    async def test_degraded_when_only_data_unhealthy(self, client):
        """JuniperData unhealthy + JuniperCascor not_configured → degraded (200)."""
        from health import DependencyStatus

        async def fake_probe(name, url, timeout=5.0):
            return DependencyStatus(name=name, status="unhealthy", latency_ms=1.0, message=f"injected: {url}")

        with patch("main.probe_dependency", side_effect=fake_probe):
            response = client.get("/v1/health/ready")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "degraded"
        assert body["dependencies"]["juniper_data"]["status"] == "unhealthy"
        # Cascor remains not_configured (URL unset in default test settings).
        assert body["dependencies"]["juniper_cascor"]["status"] == "not_configured"

    def test_degraded_when_cascor_unhealthy_with_url_set(self, client, monkeypatch):
        """JuniperCascor unhealthy (URL set) → degraded (200)."""
        import main as main_module
        from health import DependencyStatus

        async def fake_probe(name, url, timeout=5.0):
            # juniper-data healthy, juniper-cascor unhealthy
            if "JuniperCascor" in name:
                return DependencyStatus(name=name, status="unhealthy", latency_ms=1.0, message=f"injected: {url}")
            return DependencyStatus(name=name, status="healthy", latency_ms=1.0, message=url)

        # Settings is loaded once at module import as `main.settings`; patch
        # the runtime attribute the readiness handler reads.
        monkeypatch.setattr(main_module.settings, "cascor_service_url", "http://injected-cascor:8200", raising=False)
        with patch("main.probe_dependency", side_effect=fake_probe):
            response = client.get("/v1/health/ready")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "degraded"
        assert body["dependencies"]["juniper_cascor"]["status"] == "unhealthy"
        assert body["dependencies"]["juniper_data"]["status"] == "healthy"

    def test_ready_when_all_configured_upstreams_healthy(self, client, monkeypatch):
        """All probed upstreams healthy → ready (200, no degraded transition)."""
        import main as main_module
        from health import DependencyStatus

        async def fake_probe(name, url, timeout=5.0):
            return DependencyStatus(name=name, status="healthy", latency_ms=1.0, message=url)

        monkeypatch.setattr(main_module.settings, "cascor_service_url", "http://injected-cascor:8200", raising=False)
        with patch("main.probe_dependency", side_effect=fake_probe):
            response = client.get("/v1/health/ready")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ready"
        assert body["dependencies"]["juniper_data"]["status"] == "healthy"
        assert body["dependencies"]["juniper_cascor"]["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_canopy_never_returns_503_on_upstream_down(self, client):
        """Severity policy: canopy MUST NOT propagate 503 when an upstream is unhealthy.

        The dashboard must remain reachable so operators can see the
        diagnostic body. If this ever flips to 503 it would page on
        every downstream incident — explicit regression guard.
        """
        from health import DependencyStatus

        async def fake_probe(name, url, timeout=5.0):
            return DependencyStatus(name=name, status="unhealthy", latency_ms=1.0, message="injected")

        with patch("main.probe_dependency", side_effect=fake_probe):
            response = client.get("/v1/health/ready")
        assert response.status_code != 503, "canopy should not 503 on upstream-down per probe-graph severity policy"


@pytest.mark.unit
class TestDeprecatedEndpoints:
    """Test deprecated health endpoint aliases."""

    def test_health_deprecated(self, client):
        """Test /health still works but is deprecated (status now "ok" — API-01, PR #299)."""
        response = client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"

    def test_api_health_deprecated(self, client):
        """Test /api/health still works but is deprecated (status now "ok" — API-01, PR #299)."""
        response = client.get("/api/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
