"""Wire-compat snapshot tests for the R2.1.5 juniper-observability migration.

METRICS-MON R2.1.5 / seed-06: per the R2.1 design §7, every consumer
migration ships a snapshot test that pins the externally-observable
wire format of ``/v1/health/ready`` and the Prometheus contract so the
shared-lib swap cannot silently drift the contract.

The snapshot below was captured from juniper-canopy ``main`` at
HEAD = ``4d43c0a3`` (commit immediately before the R2.1.5 migration
landed). Any future bump of the shared lib that changes these keys,
status codes, or label sets will fail this test first.

Two keys deliberately differ from the pre-migration snapshot:

- ``timestamp`` is now tz-aware UTC (closes BUG-JD-06-equivalent
  naive-tz drift). The value remains a unix epoch float; only its
  derivation changes.
- ``configure_sentry`` now installs a SEC-15 ``before_send`` hook
  (defense-in-depth header scrubbing). Canopy's previous local
  implementation did not. This is verified by ``TestSentryBeforeSendHook``.
"""

import pytest

# Snapshot captured pre-R2.1.5 (canopy main @ 4d43c0a3). The shared lib
# migration must preserve every entry below.
EXPECTED_TOP_LEVEL_KEYS = {"dependencies", "details", "service", "status", "timestamp", "version"}
EXPECTED_DEP_KEYS = {"juniper_data", "juniper_cascor"}
EXPECTED_DETAILS_KEYS = {"mode", "active_connections", "training_active"}


@pytest.mark.unit
class TestReadinessWireCompat:
    """METRICS-MON R2.1.5: /v1/health/ready JSON shape pinned across the migration."""

    def test_status_code_unchanged(self, client):
        """Canopy /v1/health/ready always returns 200 (R1.2 503-on-not-ready not yet wired)."""
        response = client.get("/v1/health/ready")
        assert response.status_code == 200

    def test_top_level_keys_unchanged(self, client):
        """No keys added or removed from the standard ReadinessResponse shape."""
        response = client.get("/v1/health/ready")
        body = response.json()
        assert set(body.keys()) == EXPECTED_TOP_LEVEL_KEYS

    def test_service_identity_unchanged(self, client):
        response = client.get("/v1/health/ready")
        assert response.json()["service"] == "juniper-canopy"

    def test_dependency_set_unchanged(self, client):
        """Canopy probes both juniper-data and juniper-cascor."""
        response = client.get("/v1/health/ready")
        assert set(response.json()["dependencies"].keys()) == EXPECTED_DEP_KEYS

    def test_details_keys_unchanged(self, client):
        """``details`` always carries canopy's mode/connection/training state."""
        response = client.get("/v1/health/ready")
        assert set(response.json()["details"].keys()) == EXPECTED_DETAILS_KEYS

    def test_timestamp_is_unix_epoch_float(self, client):
        """The shared lib reconciliation kept ``timestamp`` as a unix-epoch float."""
        import time

        response = client.get("/v1/health/ready")
        ts = response.json()["timestamp"]
        assert isinstance(ts, float)
        # R2.1.5 fix: now tz-aware UTC so this should be within seconds of
        # ``time.time()`` (also UTC unix epoch) on every host.
        assert abs(time.time() - ts) < 60.0

    def test_dependency_status_values_in_documented_set(self, client):
        """Every dep's ``status`` field stays in the documented Literal set."""
        response = client.get("/v1/health/ready")
        for dep in response.json()["dependencies"].values():
            assert dep["status"] in {"healthy", "unhealthy", "degraded", "not_configured"}


@pytest.mark.unit
class TestPrometheusContract:
    """METRICS-MON R2.1.5: HTTP metric names + label sets pinned."""

    def test_unmatched_endpoint_label_value(self):
        """The R1.1 cardinality bound must remain the same string post-migration."""
        from observability import UNMATCHED_ENDPOINT_LABEL

        assert UNMATCHED_ENDPOINT_LABEL == "_unmatched"

    def test_namespace_prefix_preserved(self):
        """``juniper_canopy_*`` prefix is the R1.1 contract for metric names."""
        from unittest.mock import MagicMock, patch

        from observability import PrometheusMiddleware

        with patch("prometheus_client.Counter") as MockCounter, patch("prometheus_client.Histogram") as MockHistogram:
            MockCounter.return_value = MagicMock()
            MockHistogram.return_value = MagicMock()

            PrometheusMiddleware(app=MagicMock(), service_name="juniper-canopy", namespace="juniper_canopy")

            counter_names = {call.args[0] for call in MockCounter.call_args_list}
            histogram_names = {call.args[0] for call in MockHistogram.call_args_list}
            assert "juniper_canopy_http_requests_total" in counter_names
            assert "juniper_canopy_http_unmatched_requests_total" in counter_names
            assert "juniper_canopy_http_request_duration_seconds" in histogram_names


@pytest.mark.unit
class TestSentryBeforeSendHook:
    """METRICS-MON R2.1.5: shared `configure_sentry` adds the SEC-15 hook.

    Canopy's previous local `configure_sentry` did not install a
    ``before_send`` hook. The migration to the shared lib adds it for
    free, scrubbing ``X-API-Key`` / ``Authorization`` / ``Cookie`` from
    outbound Sentry events. This is a security improvement for canopy.
    """

    def test_before_send_hook_installed(self):
        from unittest.mock import patch

        from juniper_observability.sentry import _strip_sensitive_headers as shared_strip

        from observability import configure_sentry

        with patch("sentry_sdk.init") as mock_init:
            configure_sentry("https://k@o0.ingest.sentry.io/0", "juniper-canopy", "0.5.0")
            kw = mock_init.call_args.kwargs
            assert kw["before_send"] is shared_strip

    def test_strip_hook_redacts_sensitive_headers(self):
        from juniper_observability.sentry import _strip_sensitive_headers

        event = {
            "request": {
                "headers": {
                    "X-API-Key": "secret-key-value",
                    "Authorization": "Bearer xyz",
                    "Cookie": "session=abc",
                    "User-Agent": "pytest/1.0",
                }
            }
        }
        cleaned = _strip_sensitive_headers(event, hint=None)
        headers = cleaned["request"]["headers"]
        assert headers["X-API-Key"] == "[Filtered]"
        assert headers["Authorization"] == "[Filtered]"
        assert headers["Cookie"] == "[Filtered]"
        assert headers["User-Agent"] == "pytest/1.0"
