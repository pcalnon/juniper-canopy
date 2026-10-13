"""Regression tests for OBS-WIRE A.4 / C.1 / messages_total wire-up.

Sister PR to juniper-cascor#204 (OBS-WIRE-01). Closes the canopy half of
the post-METRICS-MON observability audit (juniper-ml#195) findings:

* **A.4 (P1)** — ``juniper_canopy_websocket_connections_active{channel}``
  Gauge wiring. The helper :func:`observability.set_websocket_connections`
  exists but had zero non-test production callers. Both the
  ``NoWebSocketConnections`` Prometheus alert in juniper-deploy and a
  panel on the canopy Grafana dashboard depend on this Gauge — without
  wiring, the alert is permanently inert and the panel shows flat zero.

* **Adjacent (P2)** — ``juniper_canopy_websocket_messages_total{channel,
  type}`` Counter wiring. Same posture as A.4: helper exists, no
  production callers, dashboard panel only.

* **C.1 (P2)** — middleware order in :mod:`main`. Starlette is LIFO
  (last-added runs OUTERMOST). ``RequestIdMiddleware`` MUST be added
  LAST so the ``request_id`` contextvar is set BEFORE
  ``PrometheusMiddleware`` records the request. Matches the canonical
  pattern in juniper-data and juniper-cascor (audit Dim C.2).

The wire-up lives in :mod:`communication.websocket_manager`:

* :meth:`WebSocketManager.connect` accepts ``channel`` and bumps the
  per-channel count + Gauge.
* :meth:`WebSocketManager.disconnect` decrements the count + Gauge,
  reading the channel from ``connection_metadata`` (no caller needs
  to plumb it back through).
* :meth:`WebSocketManager.send_personal_message` and
  :meth:`WebSocketManager.broadcast` bump
  ``juniper_canopy_websocket_messages_total{channel, type}`` once per
  successful delivery.

Closed-set discipline: only ``"training"`` and ``"control"`` channels
are emitted; the legacy ``/ws`` compat endpoint passes ``channel=None``
to skip metric emission. Message ``type`` labels are bucketed against
:data:`observability._WS_MESSAGE_TYPE_ALLOWLIST` and collapse to
``"_other"`` outside the allowlist (R1.1 cardinality discipline,
mirroring ``unrecognized_ws_frames_total``).
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

src_dir = Path(__file__).parents[2]
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

import observability as obs  # noqa: E402
from communication.websocket_manager import WebSocketManager  # noqa: E402


def _gauge_value(metric, **labels) -> float:
    """Read a Gauge labelset's current value via ``collect()``.

    Mirrors the helpers in ``test_data_client_request_hook.py`` —
    going through the public ``collect()`` API is more robust against
    fixture-reset interactions than poking ``.labels(...)._value.get()``.
    """
    samples = list(metric.collect())[0].samples
    for s in samples:
        if not s.name.endswith("_active"):
            # Gauge exposition emits one sample per labelset, name
            # matches the metric name. For our gauge the suffix is the
            # bare metric name (no ``_total``/``_count`` like Counters).
            continue
        if all(s.labels.get(k) == v for k, v in labels.items()):
            return s.value
    # Fall through: any sample matching the labels.
    for s in samples:
        if all(s.labels.get(k) == v for k, v in labels.items()):
            return s.value
    return 0.0


def _counter_value(metric, **labels) -> float:
    """Read a Counter labelset's accumulated total via ``collect()``."""
    samples = list(metric.collect())[0].samples
    for s in samples:
        if not s.name.endswith("_total"):
            continue
        if all(s.labels.get(k) == v for k, v in labels.items()):
            return s.value
    return 0.0


@pytest.fixture(autouse=True)
def _reset_canopy_metrics():
    """Null the lazy-cached metrics dict and scrub the global Prometheus
    REGISTRY of the WS collectors so each test starts with fresh,
    zero-valued counters / gauges. Same scrub pattern as the R4.3
    test fixture in ``test_data_client_request_hook.py``.
    """
    obs._canopy_metrics = None
    try:
        from prometheus_client import REGISTRY

        for metric_name in (
            "juniper_canopy_websocket_connections_active",
            "juniper_canopy_websocket_messages_total",
        ):
            collector = REGISTRY._names_to_collectors.get(metric_name)
            if collector is not None:
                try:
                    REGISTRY.unregister(collector)
                except (KeyError, ValueError):
                    pass
    except ImportError:
        pass
    yield
    obs._canopy_metrics = None


def _make_mock_ws():
    ws = MagicMock()
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()
    ws.send_text = AsyncMock()
    ws.close = AsyncMock()
    return ws


# ---------------------------------------------------------------------------
# A.4 — websocket_connections_active Gauge wire-up
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestWebsocketConnectionsActiveGauge:
    """A.4: per-channel Gauge updates on connect/disconnect."""

    @pytest.mark.asyncio
    async def test_connect_increments_training_gauge(self):
        manager = WebSocketManager()
        ws = _make_mock_ws()

        await manager.connect(ws, channel="training")

        metrics = obs._ensure_canopy_metrics()
        assert _gauge_value(metrics["websocket_connections_active"], channel="training") == 1.0

    @pytest.mark.asyncio
    async def test_connect_increments_control_gauge_independently(self):
        manager = WebSocketManager()
        ws_t = _make_mock_ws()
        ws_c = _make_mock_ws()

        await manager.connect(ws_t, channel="training")
        await manager.connect(ws_c, channel="control")

        metrics = obs._ensure_canopy_metrics()
        assert _gauge_value(metrics["websocket_connections_active"], channel="training") == 1.0
        assert _gauge_value(metrics["websocket_connections_active"], channel="control") == 1.0

    @pytest.mark.asyncio
    async def test_connect_two_clients_same_channel(self):
        manager = WebSocketManager()
        ws1 = _make_mock_ws()
        ws2 = _make_mock_ws()

        await manager.connect(ws1, channel="training")
        await manager.connect(ws2, channel="training")

        metrics = obs._ensure_canopy_metrics()
        assert _gauge_value(metrics["websocket_connections_active"], channel="training") == 2.0

    @pytest.mark.asyncio
    async def test_disconnect_decrements_gauge(self):
        manager = WebSocketManager()
        ws = _make_mock_ws()

        await manager.connect(ws, channel="training")
        manager.disconnect(ws)

        metrics = obs._ensure_canopy_metrics()
        # Gauge floors at zero — channel drained.
        assert _gauge_value(metrics["websocket_connections_active"], channel="training") == 0.0

    @pytest.mark.asyncio
    async def test_disconnect_only_decrements_owning_channel(self):
        """Disconnecting a control client must not touch the training gauge."""
        manager = WebSocketManager()
        ws_t = _make_mock_ws()
        ws_c = _make_mock_ws()

        await manager.connect(ws_t, channel="training")
        await manager.connect(ws_c, channel="control")
        manager.disconnect(ws_c)

        metrics = obs._ensure_canopy_metrics()
        assert _gauge_value(metrics["websocket_connections_active"], channel="training") == 1.0
        assert _gauge_value(metrics["websocket_connections_active"], channel="control") == 0.0

    @pytest.mark.asyncio
    async def test_double_disconnect_is_idempotent(self):
        """A second disconnect on an already-disconnected ws must not under-decrement."""
        manager = WebSocketManager()
        ws1 = _make_mock_ws()
        ws2 = _make_mock_ws()

        await manager.connect(ws1, channel="training")
        await manager.connect(ws2, channel="training")
        manager.disconnect(ws1)
        manager.disconnect(ws1)  # second disconnect — should early-return

        metrics = obs._ensure_canopy_metrics()
        assert _gauge_value(metrics["websocket_connections_active"], channel="training") == 1.0

    @pytest.mark.asyncio
    async def test_legacy_ws_endpoint_skips_gauge(self):
        """``/ws`` compat route passes channel=None — gauge stays untouched
        to preserve closed-set discipline.
        """
        manager = WebSocketManager()
        ws = _make_mock_ws()

        await manager.connect(ws)  # no channel kwarg

        # No labelset for either training or control should be present
        # with a non-zero value.
        metrics = obs._ensure_canopy_metrics()
        assert _gauge_value(metrics["websocket_connections_active"], channel="training") == 0.0
        assert _gauge_value(metrics["websocket_connections_active"], channel="control") == 0.0
        # And the connection itself is in the manager (legacy route still works).
        assert ws in manager.active_connections

    @pytest.mark.asyncio
    async def test_channel_metadata_stashed_on_connection(self):
        """Disconnect must be able to recover the channel without the
        caller plumbing it back through.
        """
        manager = WebSocketManager()
        ws = _make_mock_ws()

        await manager.connect(ws, channel="control")

        assert manager.connection_metadata[ws]["channel"] == "control"


# ---------------------------------------------------------------------------
# Adjacent — websocket_messages_total Counter wire-up
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestWebsocketMessagesTotalCounter:
    """Adjacent finding: per-(channel, type) Counter on outbound dispatch."""

    @pytest.mark.asyncio
    async def test_send_personal_message_increments_counter(self):
        manager = WebSocketManager()
        ws = _make_mock_ws()
        await manager.connect(ws, channel="training")

        # connect() itself sends a "connection_established" message —
        # snapshot the counter, then send a "metrics" frame and assert
        # the delta is exactly 1 on the (training, metrics) labelset.
        metrics = obs._ensure_canopy_metrics()
        before = _counter_value(metrics["websocket_messages_total"], channel="training", type="metrics")

        await manager.send_personal_message({"type": "metrics", "data": {"loss": 0.5}}, ws)

        after = _counter_value(metrics["websocket_messages_total"], channel="training", type="metrics")
        assert after - before == 1.0

    @pytest.mark.asyncio
    async def test_send_personal_message_buckets_unknown_type_as_other(self):
        """A misbehaving caller passing an out-of-allowlist type label
        must not blow up the cardinality — it collapses to "_other".
        """
        manager = WebSocketManager()
        ws = _make_mock_ws()
        await manager.connect(ws, channel="control")

        await manager.send_personal_message({"type": "totally_made_up", "data": {}}, ws)

        metrics = obs._ensure_canopy_metrics()
        assert _counter_value(metrics["websocket_messages_total"], channel="control", type="_other") == 1.0
        # And the made-up type itself is NOT a labelset.
        assert _counter_value(metrics["websocket_messages_total"], channel="control", type="totally_made_up") == 0.0

    @pytest.mark.asyncio
    async def test_send_personal_message_no_channel_skips_counter(self):
        """Legacy /ws endpoint connections (channel=None) bypass the counter."""
        manager = WebSocketManager()
        ws = _make_mock_ws()
        await manager.connect(ws)  # no channel

        # Snapshot whole-counter state then send.
        metrics = obs._ensure_canopy_metrics()

        await manager.send_personal_message({"type": "metrics", "data": {}}, ws)

        # No channel labelset should have been touched for "metrics".
        assert _counter_value(metrics["websocket_messages_total"], channel="training", type="metrics") == 0.0
        assert _counter_value(metrics["websocket_messages_total"], channel="control", type="metrics") == 0.0

    @pytest.mark.asyncio
    async def test_broadcast_increments_counter_per_recipient(self):
        manager = WebSocketManager()
        ws_t1 = _make_mock_ws()
        ws_t2 = _make_mock_ws()
        ws_c = _make_mock_ws()
        await manager.connect(ws_t1, channel="training")
        await manager.connect(ws_t2, channel="training")
        await manager.connect(ws_c, channel="control")

        metrics = obs._ensure_canopy_metrics()
        before_t = _counter_value(metrics["websocket_messages_total"], channel="training", type="state")
        before_c = _counter_value(metrics["websocket_messages_total"], channel="control", type="state")

        await manager.broadcast({"type": "state", "data": {"phase": "candidate"}})

        after_t = _counter_value(metrics["websocket_messages_total"], channel="training", type="state")
        after_c = _counter_value(metrics["websocket_messages_total"], channel="control", type="state")
        # Two training subscribers received → +2; one control → +1.
        assert after_t - before_t == 2.0
        assert after_c - before_c == 1.0

    @pytest.mark.asyncio
    async def test_send_failure_does_not_increment_counter(self):
        """If send_json raises, the connection is torn down (existing
        behavior) and the message counter MUST NOT increment — we
        record successful deliveries only.
        """
        manager = WebSocketManager()
        ws = _make_mock_ws()
        await manager.connect(ws, channel="training")

        ws.send_json.side_effect = Exception("connection broken")

        metrics = obs._ensure_canopy_metrics()
        before = _counter_value(metrics["websocket_messages_total"], channel="training", type="metrics")

        await manager.send_personal_message({"type": "metrics"}, ws)

        after = _counter_value(metrics["websocket_messages_total"], channel="training", type="metrics")
        assert after == before
        # And the connection got torn down (existing behavior preserved).
        assert ws not in manager.active_connections

    def test_inc_websocket_messages_allowlist_collapse(self):
        """Direct unit test of the closed-set bucketing in the helper."""
        # Known type passes through.
        obs.inc_websocket_messages("training", "metrics")
        # Unknown type collapses to "_other".
        obs.inc_websocket_messages("training", "evil_unbounded_type")

        metrics = obs._ensure_canopy_metrics()
        assert _counter_value(metrics["websocket_messages_total"], channel="training", type="metrics") == 1.0
        assert _counter_value(metrics["websocket_messages_total"], channel="training", type="_other") == 1.0
        assert _counter_value(metrics["websocket_messages_total"], channel="training", type="evil_unbounded_type") == 0.0


# ---------------------------------------------------------------------------
# C.1 — middleware order
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMiddlewareOrder:
    """C.1: ``RequestIdMiddleware`` must be added LAST so it runs OUTERMOST.

    Starlette stores middleware in :attr:`FastAPI.user_middleware` in
    add-order. At ASGI-app build time it wraps them in REVERSE order
    so the LAST added runs OUTERMOST. We assert the add-order so the
    test is robust to whether the test imports ``main`` before or after
    starlette materializes the middleware stack.
    """

    # IMPORTANT: starlette's ``FastAPI.add_middleware`` PREPENDS to
    # ``app.user_middleware`` (insert at index 0). The list reads
    # OUTERMOST-FIRST: ``user_middleware[0]`` is the last-added and runs
    # OUTERMOST at request time. Therefore "RequestIdMiddleware was added
    # LAST" ↔ "RequestIdMiddleware appears BEFORE PrometheusMiddleware
    # in user_middleware" (lower index = outer = added later).

    def test_request_id_middleware_added_after_prometheus_middleware_in_main(self, monkeypatch):
        """Structural test: walk ``app.user_middleware`` on the production
        ``main.app`` and assert ``RequestIdMiddleware`` was added AFTER
        ``PrometheusMiddleware``.

        ``add_middleware`` prepends, so the more-recently-added entry has
        the LOWER index. Therefore ``RequestIdMiddleware`` index
        < ``PrometheusMiddleware`` index ↔ RequestId was added later
        ↔ RequestId is OUTERMOST at request time. Matches the canonical
        add-order in juniper-data (``juniper_data/api/app.py``) and
        juniper-cascor (``src/api/app.py``).

        Historically this test ran with a runtime ``pytest.skip`` when
        ``PrometheusMiddleware`` was absent (the canonical test-env
        setting is ``metrics_enabled=False``). To make the test
        deterministic — and to actually exercise the production
        conditional ``add_middleware`` branch at ``main.py:314`` — we
        force ``JUNIPER_CANOPY_METRICS_ENABLED=1`` and reload ``main``
        inside the test, then restore the original module state in
        the ``finally`` block so other tests see the canonical layout.
        """
        import importlib
        import sys

        # Force metrics on so the conditional ``add_middleware`` branch
        # for ``PrometheusMiddleware`` fires.
        monkeypatch.setenv("JUNIPER_CANOPY_METRICS_ENABLED", "1")

        # ``get_settings`` is ``@lru_cache``-d; clear it so the reloaded
        # ``main`` reads the new env value.
        from settings import get_settings

        get_settings.cache_clear()

        try:
            # Reload main with metrics on. If main was already imported
            # by an earlier test, ``importlib.reload`` re-runs its top-
            # level code in place; otherwise import fresh.
            if "main" in sys.modules:
                canopy_main = importlib.reload(sys.modules["main"])
            else:
                import main as canopy_main  # noqa: WPS433 — module-level side effect is the point

            # ``m.cls`` is the middleware *class* itself (modern starlette
            # ``Middleware`` namedtuple). ``m.cls.__name__`` gives the
            # class name. (The historical ``type(m.cls).__name__`` branch
            # in the pre-fix version yielded ``'type'`` for every entry
            # because ``m.cls`` is a class object — only the synthetic
            # test below got the extraction right.)
            names = [m.cls.__name__ for m in canopy_main.app.user_middleware]
            request_id_idx = next((i for i, n in enumerate(names) if "RequestId" in n), None)
            prometheus_idx = next((i for i, n in enumerate(names) if "Prometheus" in n), None)

            assert prometheus_idx is not None, f"PrometheusMiddleware missing despite metrics_enabled=1; order seen: {names}"
            assert request_id_idx is not None, "RequestIdMiddleware missing from app.user_middleware"
            assert request_id_idx < prometheus_idx, f"RequestIdMiddleware (index {request_id_idx}) MUST appear BEFORE " f"PrometheusMiddleware (index {prometheus_idx}) in app.user_middleware " f"(add_middleware prepends — LOWER index = added LATER = OUTERMOST). " f"Order seen: {names}"
        finally:
            # Restore: monkeypatch undoes the env var, then we clear the
            # settings cache and reload main so subsequent tests see the
            # canonical metrics-disabled test-env layout.
            get_settings.cache_clear()
            if "main" in sys.modules:
                try:
                    importlib.reload(sys.modules["main"])
                except Exception:  # nosec B110 - cleanup; cannot risk masking the actual assertion failure
                    pass

    def test_request_id_added_after_prometheus_synthetic(self):
        """Synthetic FastAPI app that replays canopy main.py's exact
        observability-middleware add-order. Independent of
        ``metrics_enabled`` so the C.1 mechanic is locked in regardless
        of test-env settings.
        """
        from fastapi import FastAPI

        from observability import PrometheusMiddleware, RequestIdMiddleware

        app = FastAPI()
        # Replay the post-fix order from main.py:
        #     PrometheusMiddleware FIRST, RequestIdMiddleware LAST.
        app.add_middleware(PrometheusMiddleware, service_name="juniper-canopy", namespace="juniper_canopy")
        app.add_middleware(RequestIdMiddleware)

        names = [m.cls.__name__ for m in app.user_middleware]
        # add_middleware prepends → RequestId (added last) ends up at
        # index 0, Prometheus (added first) ends up at index 1.
        prometheus_idx = names.index("PrometheusMiddleware")
        request_id_idx = names.index("RequestIdMiddleware")
        assert request_id_idx < prometheus_idx, f"RequestIdMiddleware MUST be added LAST so it runs OUTERMOST. " f"Got order: {names}"

    def test_pre_fix_order_would_fail_assertion(self):
        """Negative control: replay the PRE-FIX add-order (RequestId
        first, Prometheus last) and assert that under that ordering
        RequestId would NOT run outermost. Pinning this prevents a
        future regression that silently re-flips the order.
        """
        from fastapi import FastAPI

        from observability import PrometheusMiddleware, RequestIdMiddleware

        app = FastAPI()
        # PRE-FIX: RequestIdMiddleware first, PrometheusMiddleware last.
        app.add_middleware(RequestIdMiddleware)
        app.add_middleware(PrometheusMiddleware, service_name="juniper-canopy", namespace="juniper_canopy")

        names = [m.cls.__name__ for m in app.user_middleware]
        # Under pre-fix order Prometheus (added last) is at index 0
        # (outermost), RequestId at index 1. Symptom of the bug.
        assert names.index("PrometheusMiddleware") < names.index("RequestIdMiddleware"), f"Negative control invariant broken — pre-fix order should put " f"Prometheus outermost. Got: {names}"
