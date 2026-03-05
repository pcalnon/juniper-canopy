"""Observability module for structured logging, Prometheus metrics, and Sentry integration."""

import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

request_id_var: ContextVar[str] = ContextVar("request_id", default="")

_SERVICE_NAME_DEFAULT: str = "juniper-canopy"
_NAMESPACE_DEFAULT: str = "juniper_canopy"


class JuniperJsonFormatter(logging.Formatter):
    """JSON log formatter with request_id propagation."""

    def __init__(self, service: str = _SERVICE_NAME_DEFAULT) -> None:
        super().__init__()
        self._service = service

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": self._service,
            "request_id": request_id_var.get(""),
        }
        if record.exc_info and record.exc_info[1] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Injects X-Request-ID into ContextVar and response header."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        rid = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        token = request_id_var.set(rid)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = rid
            return response
        finally:
            request_id_var.reset(token)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Tracks http_requests_total and http_request_duration_seconds with namespace prefix."""

    def __init__(self, app: object, service_name: str = _SERVICE_NAME_DEFAULT, namespace: str = _NAMESPACE_DEFAULT) -> None:
        super().__init__(app)
        from prometheus_client import Counter, Histogram

        prefix = f"{namespace}_" if namespace else ""
        self._request_count = Counter(
            f"{prefix}http_requests_total",
            "Total HTTP requests",
            ["method", "endpoint", "status"],
        )
        self._request_duration = Histogram(
            f"{prefix}http_request_duration_seconds",
            "HTTP request duration in seconds",
            ["method", "endpoint"],
        )

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start

        endpoint = request.url.path
        method = request.method
        status = str(response.status_code)

        self._request_count.labels(method=method, endpoint=endpoint, status=status).inc()
        self._request_duration.labels(method=method, endpoint=endpoint).observe(duration)

        return response


def configure_logging(log_level: str, log_format: str, service_name: str = _SERVICE_NAME_DEFAULT) -> None:
    """Configure logging — JSON when log_format='json', plain text otherwise.

    Args:
        log_level: Logging level string (e.g. "INFO", "DEBUG").
        log_format: Format mode — "json" for structured JSON, anything else for plain text.
        service_name: Service name included in JSON log entries.
    """
    level = getattr(logging, log_level.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)

    # Remove existing handlers to avoid duplicate output
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    handler = logging.StreamHandler()
    handler.setLevel(level)

    if log_format == "json":
        handler.setFormatter(JuniperJsonFormatter(service=service_name))
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

    root.addHandler(handler)


def configure_sentry(dsn: str | None, service_name: str, version: str) -> None:
    """Initialize Sentry with FastAPI integration. No-op when dsn is None or empty.

    Args:
        dsn: Sentry DSN URL. Pass None or empty string to skip initialization.
        service_name: Service name for Sentry environment tag.
        version: Application version string.
    """
    if not dsn:
        return

    import sentry_sdk

    sentry_sdk.init(
        dsn=dsn,
        send_default_pii=True,
        enable_logs=True,
        traces_sample_rate=1.0,
        release=f"{service_name}@{version}",
    )


def get_prometheus_app():
    """Return ASGI app for /metrics endpoint via prometheus_client.make_asgi_app().

    Returns:
        ASGI application serving Prometheus metrics.
    """
    from prometheus_client import make_asgi_app

    return make_asgi_app()


def set_build_info(namespace: str, version: str) -> None:
    """Set build information as a Prometheus Info metric.

    Args:
        namespace: Metric namespace prefix (e.g. "juniper_canopy").
        version: Application version string.
    """
    from prometheus_client import Info

    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    info = Info(f"{namespace}_build", f"Build information for {namespace.replace('_', '-')} service")
    info.info({"version": version, "python_version": python_version})


# ---------------------------------------------------------------------------
# Custom application metrics — lazily initialized to avoid requiring
# prometheus_client at import time (it is an optional dependency).
# ---------------------------------------------------------------------------

_canopy_metrics: dict | None = None


def _ensure_canopy_metrics() -> dict:
    """Create canopy-related Prometheus metrics on first access."""
    global _canopy_metrics
    if _canopy_metrics is None:
        from prometheus_client import Counter, Gauge

        _canopy_metrics = {
            "websocket_connections_active": Gauge(
                "juniper_canopy_websocket_connections_active",
                "Number of active WebSocket connections",
                ["channel"],
            ),
            "websocket_messages_total": Counter(
                "juniper_canopy_websocket_messages_total",
                "Total WebSocket messages sent",
                ["channel", "type"],
            ),
            "demo_mode_active": Gauge(
                "juniper_canopy_demo_mode_active",
                "Whether demo mode is currently active (0 or 1)",
            ),
        }
    return _canopy_metrics


def set_websocket_connections(channel: str, count: int) -> None:
    """Update the active WebSocket connections gauge.

    Args:
        channel: WebSocket channel — "training" or "control".
        count: Current number of active connections.
    """
    _ensure_canopy_metrics()["websocket_connections_active"].labels(channel=channel).set(count)


def inc_websocket_messages(channel: str, msg_type: str) -> None:
    """Increment the WebSocket messages counter.

    Args:
        channel: WebSocket channel — "training" or "control".
        msg_type: Message type — "metrics", "state", "topology", "event", "control_ack", etc.
    """
    _ensure_canopy_metrics()["websocket_messages_total"].labels(channel=channel, type=msg_type).inc()


def set_demo_mode_active(active: bool) -> None:
    """Update the demo mode active gauge.

    Args:
        active: Whether demo mode is currently active.
    """
    _ensure_canopy_metrics()["demo_mode_active"].set(1 if active else 0)
