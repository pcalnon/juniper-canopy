"""Extended coverage tests for the observability module.

Covers PrometheusMiddleware fallback to raw path, configure_sentry
parameter forwarding, invalid log levels, request ID context isolation,
and _ensure_canopy_metrics lazy initialization.
"""

import json
import logging
from unittest.mock import MagicMock, patch

import pytest

from observability import (
    JuniperJsonFormatter,
    PrometheusMiddleware,
    RequestIdMiddleware,
    _ensure_canopy_metrics,
    configure_logging,
    configure_sentry,
    request_id_var,
    set_build_info,
)


@pytest.mark.unit
class TestPrometheusMiddlewareCoverage:
    """Additional PrometheusMiddleware edge cases."""

    @pytest.mark.asyncio
    async def test_falls_back_to_raw_path_when_no_route(self):
        """When scope has no 'route', endpoint label uses request.url.path."""
        with patch("prometheus_client.Counter") as MockCounter, patch("prometheus_client.Histogram") as MockHistogram:
            mock_counter = MagicMock()
            mock_histogram = MagicMock()
            MockCounter.return_value = mock_counter
            MockHistogram.return_value = mock_histogram

            middleware = PrometheusMiddleware(app=MagicMock(), namespace="test")

            response = MagicMock()
            response.status_code = 200

            async def mock_call_next(request):
                return response

            request = MagicMock()
            request.url.path = "/some/unmatched/path"
            request.method = "GET"
            request.scope = {}  # No "route" key

            await middleware.dispatch(request, mock_call_next)

            mock_counter.labels.assert_called_once_with(method="GET", endpoint="/some/unmatched/path", status="200")

    @pytest.mark.asyncio
    async def test_route_is_none_falls_back_to_raw_path(self):
        """When scope['route'] is None, endpoint label uses request.url.path."""
        with patch("prometheus_client.Counter") as MockCounter, patch("prometheus_client.Histogram") as MockHistogram:
            mock_counter = MagicMock()
            mock_histogram = MagicMock()
            MockCounter.return_value = mock_counter
            MockHistogram.return_value = mock_histogram

            middleware = PrometheusMiddleware(app=MagicMock(), namespace="test")

            response = MagicMock()
            response.status_code = 200

            async def mock_call_next(request):
                return response

            request = MagicMock()
            request.url.path = "/raw/path"
            request.method = "POST"
            request.scope = {"route": None}

            await middleware.dispatch(request, mock_call_next)

            mock_counter.labels.assert_called_once_with(method="POST", endpoint="/raw/path", status="200")

    @pytest.mark.asyncio
    async def test_records_duration_as_positive_float(self):
        """Verify histogram observation receives a positive duration."""
        with patch("prometheus_client.Counter") as MockCounter, patch("prometheus_client.Histogram") as MockHistogram:
            mock_counter = MagicMock()
            mock_histogram = MagicMock()
            MockCounter.return_value = mock_counter
            MockHistogram.return_value = mock_histogram

            middleware = PrometheusMiddleware(app=MagicMock(), namespace="test")

            response = MagicMock()
            response.status_code = 200

            async def mock_call_next(request):
                return response

            route = MagicMock()
            route.path = "/test"
            request = MagicMock()
            request.url.path = "/test"
            request.method = "GET"
            request.scope = {"route": route}

            await middleware.dispatch(request, mock_call_next)

            observed_value = mock_histogram.labels().observe.call_args[0][0]
            assert isinstance(observed_value, float)
            assert observed_value >= 0

    @pytest.mark.asyncio
    async def test_records_non_200_status_codes(self):
        """Verify non-200 status codes are recorded correctly."""
        with patch("prometheus_client.Counter") as MockCounter, patch("prometheus_client.Histogram") as MockHistogram:
            mock_counter = MagicMock()
            mock_histogram = MagicMock()
            MockCounter.return_value = mock_counter
            MockHistogram.return_value = mock_histogram

            middleware = PrometheusMiddleware(app=MagicMock(), namespace="test")

            response = MagicMock()
            response.status_code = 404

            async def mock_call_next(request):
                return response

            route = MagicMock()
            route.path = "/missing"
            request = MagicMock()
            request.url.path = "/missing"
            request.method = "GET"
            request.scope = {"route": route}

            await middleware.dispatch(request, mock_call_next)

            mock_counter.labels.assert_called_once_with(method="GET", endpoint="/missing", status="404")

    def test_default_service_name_and_namespace(self):
        """Verify PrometheusMiddleware uses defaults when not specified."""
        with patch("prometheus_client.Counter") as MockCounter, patch("prometheus_client.Histogram") as MockHistogram:
            MockCounter.return_value = MagicMock()
            MockHistogram.return_value = MagicMock()

            PrometheusMiddleware(app=MagicMock())

            MockCounter.assert_called_once_with(
                "juniper_canopy_http_requests_total",
                "Total HTTP requests",
                ["method", "endpoint", "status"],
            )


@pytest.mark.unit
class TestConfigureSentryCoverage:
    """Additional coverage for configure_sentry."""

    def test_send_default_pii_is_false(self):
        """Verify PII sending is explicitly disabled."""
        with patch("sentry_sdk.init") as mock_init:
            configure_sentry("https://key@sentry.io/0", "svc", "1.0")
            assert mock_init.call_args[1]["send_default_pii"] is False

    def test_enable_logs_is_true(self):
        """Verify Sentry log integration is enabled."""
        with patch("sentry_sdk.init") as mock_init:
            configure_sentry("https://key@sentry.io/0", "svc", "1.0")
            assert mock_init.call_args[1]["enable_logs"] is True

    def test_release_format(self):
        """Verify release string follows 'service@version' format."""
        with patch("sentry_sdk.init") as mock_init:
            configure_sentry("https://key@sentry.io/0", "juniper-canopy", "0.4.0")
            assert mock_init.call_args[1]["release"] == "juniper-canopy@0.4.0"

    def test_default_sample_rate_is_0_1(self):
        """Verify default traces_sample_rate is 0.1 (not 1.0)."""
        with patch("sentry_sdk.init") as mock_init:
            configure_sentry("https://key@sentry.io/0", "svc", "1.0")
            assert mock_init.call_args[1]["traces_sample_rate"] == 0.1

    def test_zero_sample_rate(self):
        """Verify traces_sample_rate=0 disables tracing."""
        with patch("sentry_sdk.init") as mock_init:
            configure_sentry("https://key@sentry.io/0", "svc", "1.0", traces_sample_rate=0.0)
            assert mock_init.call_args[1]["traces_sample_rate"] == 0.0


@pytest.mark.unit
class TestConfigureLoggingCoverage:
    """Additional coverage for configure_logging."""

    def setup_method(self):
        root = logging.getLogger()
        for handler in root.handlers[:]:
            root.removeHandler(handler)

    def test_invalid_log_level_defaults_to_info(self):
        """Invalid level string should fall back to logging.INFO."""
        configure_logging("NONEXISTENT_LEVEL", "text")
        root = logging.getLogger()
        assert root.level == logging.INFO

    def test_case_insensitive_log_level(self):
        """Log level should be case-insensitive."""
        configure_logging("debug", "text")
        root = logging.getLogger()
        assert root.level == logging.DEBUG

    def test_json_formatter_includes_service_name(self):
        """JSON formatter should use the provided service name."""
        configure_logging("INFO", "json", "my-custom-service")
        root = logging.getLogger()
        formatter = root.handlers[0].formatter
        assert isinstance(formatter, JuniperJsonFormatter)
        assert formatter._service == "my-custom-service"

    def test_handler_level_matches_root_level(self):
        """Handler level should match the root logger level."""
        configure_logging("WARNING", "text")
        root = logging.getLogger()
        assert root.handlers[0].level == logging.WARNING


@pytest.mark.unit
class TestRequestIdMiddlewareCoverage:
    """Additional RequestIdMiddleware coverage."""

    @pytest.mark.asyncio
    async def test_context_var_reset_after_dispatch(self):
        """Verify request_id contextvar is reset after the dispatch completes."""
        middleware = RequestIdMiddleware(app=MagicMock())

        async def mock_call_next(request):
            response = MagicMock()
            response.headers = {}
            return response

        request = MagicMock()
        request.headers = {"X-Request-ID": "temp-id"}

        # Set a known value before dispatch
        token = request_id_var.set("before-test")
        try:
            await middleware.dispatch(request, mock_call_next)
            # After dispatch completes, the middleware should have reset the contextvar
            # The value should be back to "before-test" (the token we set)
            assert request_id_var.get("") == "before-test"
        finally:
            request_id_var.reset(token)

    @pytest.mark.asyncio
    async def test_generated_id_is_uuid_format(self):
        """Verify auto-generated request IDs look like UUIDs."""
        import uuid

        middleware = RequestIdMiddleware(app=MagicMock())
        captured_rid = None

        async def mock_call_next(request):
            nonlocal captured_rid
            captured_rid = request_id_var.get("")
            response = MagicMock()
            response.headers = {}
            return response

        request = MagicMock()
        request.headers = {}

        await middleware.dispatch(request, mock_call_next)
        # Should be a valid UUID
        uuid.UUID(captured_rid)  # Raises ValueError if not valid UUID

    @pytest.mark.asyncio
    async def test_response_header_set_even_on_provided_id(self):
        """Verify X-Request-ID header is always set in response."""
        middleware = RequestIdMiddleware(app=MagicMock())

        async def mock_call_next(request):
            response = MagicMock()
            response.headers = {}
            return response

        request = MagicMock()
        request.headers = {"X-Request-ID": "my-custom-id"}

        response = await middleware.dispatch(request, mock_call_next)
        assert response.headers["X-Request-ID"] == "my-custom-id"


@pytest.mark.unit
class TestJuniperJsonFormatterCoverage:
    """Additional JuniperJsonFormatter coverage."""

    def test_no_exception_key_when_exc_info_is_none(self):
        """Verify 'exception' key is absent when no exception info."""
        formatter = JuniperJsonFormatter()
        record = logging.LogRecord(name="test", level=logging.INFO, pathname="", lineno=0, msg="msg", args=None, exc_info=None)
        output = json.loads(formatter.format(record))
        assert "exception" not in output

    def test_no_exception_key_when_exc_info_tuple_is_none_values(self):
        """Verify 'exception' key is absent when exc_info is (None, None, None)."""
        formatter = JuniperJsonFormatter()
        record = logging.LogRecord(name="test", level=logging.INFO, pathname="", lineno=0, msg="msg", args=None, exc_info=(None, None, None))
        output = json.loads(formatter.format(record))
        assert "exception" not in output

    def test_message_with_format_args(self):
        """Verify getMessage() resolves format arguments."""
        formatter = JuniperJsonFormatter()
        record = logging.LogRecord(name="test", level=logging.INFO, pathname="", lineno=0, msg="count=%d", args=(42,), exc_info=None)
        output = json.loads(formatter.format(record))
        assert output["message"] == "count=42"

    def test_empty_request_id_when_not_set(self):
        """Verify request_id is empty string when contextvar not set."""
        formatter = JuniperJsonFormatter()
        record = logging.LogRecord(name="test", level=logging.INFO, pathname="", lineno=0, msg="msg", args=None, exc_info=None)
        output = json.loads(formatter.format(record))
        assert output["request_id"] == ""


@pytest.mark.unit
class TestSetBuildInfoCoverage:
    """Additional set_build_info coverage."""

    def test_python_version_format(self):
        """Verify python_version is in X.Y.Z format."""
        import sys

        with patch("prometheus_client.Info") as MockInfo:
            mock_info = MagicMock()
            MockInfo.return_value = mock_info
            set_build_info("test", "1.0.0")
            call_args = mock_info.info.call_args[0][0]
            expected = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
            assert call_args["python_version"] == expected

    def test_namespace_used_in_metric_name(self):
        """Verify namespace prefixes the Info metric name."""
        with patch("prometheus_client.Info") as MockInfo:
            MockInfo.return_value = MagicMock()
            set_build_info("my_ns", "2.0")
            MockInfo.assert_called_once_with("my_ns_build", "Build information for my-ns service")


@pytest.mark.unit
class TestEnsureCanopyMetrics:
    """Tests for _ensure_canopy_metrics lazy initialization."""

    def test_creates_metrics_on_first_call(self):
        import observability as obs

        obs._canopy_metrics = None
        try:
            with patch("prometheus_client.Counter") as MockCounter, patch("prometheus_client.Gauge") as MockGauge:
                MockCounter.return_value = MagicMock()
                MockGauge.return_value = MagicMock()

                result = _ensure_canopy_metrics()
                assert result is not None
                assert "websocket_connections_active" in result
                assert "websocket_messages_total" in result
                assert "demo_mode_active" in result
        finally:
            obs._canopy_metrics = None

    def test_returns_same_dict_on_second_call(self):
        import observability as obs

        obs._canopy_metrics = None
        try:
            with patch("prometheus_client.Counter") as MockCounter, patch("prometheus_client.Gauge") as MockGauge:
                MockCounter.return_value = MagicMock()
                MockGauge.return_value = MagicMock()

                first = _ensure_canopy_metrics()
                second = _ensure_canopy_metrics()
                assert first is second
        finally:
            obs._canopy_metrics = None
