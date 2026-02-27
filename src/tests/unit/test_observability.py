"""Unit tests for the observability module."""

import json
import logging
from unittest.mock import MagicMock, patch

import pytest

from observability import (
    JuniperJsonFormatter,
    PrometheusMiddleware,
    RequestIdMiddleware,
    configure_logging,
    configure_sentry,
    get_prometheus_app,
    request_id_var,
)


@pytest.mark.unit
class TestJuniperJsonFormatter:
    """Tests for JuniperJsonFormatter."""

    def test_format_produces_valid_json(self):
        formatter = JuniperJsonFormatter(service="test-service")
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=None,
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test.logger"
        assert parsed["message"] == "Test message"
        assert parsed["service"] == "test-service"
        assert "timestamp" in parsed
        assert "request_id" in parsed

    def test_format_includes_request_id_from_contextvar(self):
        formatter = JuniperJsonFormatter(service="test-service")
        token = request_id_var.set("abc-123")
        try:
            record = logging.LogRecord(name="test", level=logging.INFO, pathname="", lineno=0, msg="hi", args=None, exc_info=None)
            output = formatter.format(record)
            parsed = json.loads(output)
            assert parsed["request_id"] == "abc-123"
        finally:
            request_id_var.reset(token)

    def test_format_includes_exception_info(self):
        formatter = JuniperJsonFormatter(service="test-service")
        try:
            raise ValueError("test error")
        except ValueError:
            import sys

            exc_info = sys.exc_info()
            record = logging.LogRecord(name="test", level=logging.ERROR, pathname="", lineno=0, msg="error", args=None, exc_info=exc_info)
            output = formatter.format(record)
            parsed = json.loads(output)
            assert "exception" in parsed
            assert "ValueError" in parsed["exception"]

    def test_format_default_service_name(self):
        formatter = JuniperJsonFormatter()
        record = logging.LogRecord(name="test", level=logging.INFO, pathname="", lineno=0, msg="hi", args=None, exc_info=None)
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["service"] == "juniper-canopy"


@pytest.mark.unit
class TestConfigureLogging:
    """Tests for configure_logging function."""

    def setup_method(self):
        root = logging.getLogger()
        for handler in root.handlers[:]:
            root.removeHandler(handler)

    def test_text_mode_uses_standard_formatter(self):
        configure_logging("INFO", "text", "test-service")
        root = logging.getLogger()
        assert len(root.handlers) == 1
        assert not isinstance(root.handlers[0].formatter, JuniperJsonFormatter)

    def test_json_mode_uses_json_formatter(self):
        configure_logging("INFO", "json", "test-service")
        root = logging.getLogger()
        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0].formatter, JuniperJsonFormatter)

    def test_sets_log_level(self):
        configure_logging("DEBUG", "text", "test-service")
        root = logging.getLogger()
        assert root.level == logging.DEBUG

    def test_removes_existing_handlers(self):
        root = logging.getLogger()
        root.addHandler(logging.StreamHandler())
        root.addHandler(logging.StreamHandler())
        stream_handlers_before = [h for h in root.handlers if isinstance(h, logging.StreamHandler) and type(h) is logging.StreamHandler]
        assert len(stream_handlers_before) == 2
        configure_logging("INFO", "text", "test-service")
        # configure_logging removes all handlers and adds exactly one
        assert len(root.handlers) == 1


@pytest.mark.unit
class TestConfigureSentry:
    """Tests for configure_sentry function."""

    def test_noop_when_dsn_is_none(self):
        configure_sentry(None, "test-service", "1.0.0")

    def test_noop_when_dsn_is_empty(self):
        configure_sentry("", "test-service", "1.0.0")

    def test_initializes_when_dsn_provided(self):
        with patch("sentry_sdk.init") as mock_init:
            configure_sentry("https://examplePublicKey@o0.ingest.sentry.io/0", "test-service", "1.0.0")
            mock_init.assert_called_once()
            call_kwargs = mock_init.call_args[1]
            assert call_kwargs["dsn"] == "https://examplePublicKey@o0.ingest.sentry.io/0"
            assert call_kwargs["release"] == "test-service@1.0.0"


@pytest.mark.unit
class TestRequestIdMiddleware:
    """Tests for RequestIdMiddleware."""

    @pytest.mark.asyncio
    async def test_generates_request_id_when_not_provided(self):
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

        response = await middleware.dispatch(request, mock_call_next)
        assert captured_rid != ""
        assert "X-Request-ID" in response.headers

    @pytest.mark.asyncio
    async def test_uses_provided_request_id(self):
        middleware = RequestIdMiddleware(app=MagicMock())
        captured_rid = None

        async def mock_call_next(request):
            nonlocal captured_rid
            captured_rid = request_id_var.get("")
            response = MagicMock()
            response.headers = {}
            return response

        request = MagicMock()
        request.headers = {"X-Request-ID": "custom-id-123"}

        response = await middleware.dispatch(request, mock_call_next)
        assert captured_rid == "custom-id-123"
        assert response.headers["X-Request-ID"] == "custom-id-123"


@pytest.mark.unit
class TestPrometheusMiddleware:
    """Tests for PrometheusMiddleware."""

    @pytest.mark.asyncio
    async def test_increments_counter_and_records_histogram(self):
        with patch("prometheus_client.Counter") as MockCounter, patch("prometheus_client.Histogram") as MockHistogram:
            mock_counter = MagicMock()
            mock_histogram = MagicMock()
            MockCounter.return_value = mock_counter
            MockHistogram.return_value = mock_histogram

            middleware = PrometheusMiddleware(app=MagicMock(), service_name="test")

            response = MagicMock()
            response.status_code = 200

            async def mock_call_next(request):
                return response

            request = MagicMock()
            request.url.path = "/v1/test"
            request.method = "GET"

            result = await middleware.dispatch(request, mock_call_next)

            mock_counter.labels.assert_called_once_with(method="GET", endpoint="/v1/test", status="200")
            mock_counter.labels().inc.assert_called_once()
            mock_histogram.labels.assert_called_once_with(method="GET", endpoint="/v1/test")
            mock_histogram.labels().observe.assert_called_once()
            assert result == response


@pytest.mark.unit
class TestGetPrometheusApp:
    """Tests for get_prometheus_app function."""

    def test_returns_asgi_app(self):
        app = get_prometheus_app()
        assert callable(app)
