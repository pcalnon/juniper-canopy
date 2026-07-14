"""N1 (training-runtime defects plan §4 I-1/I-2): WS-silent poll liveness.

Pre-N1, the metrics/topology store polls were suppressed by sticky WS flags
(``metricsReceived`` / ``topologyReceived`` + ``connected``): once a tab had
seen a single WS metrics frame, its REST polls stopped forever — even when no
further frames arrived — freezing tiles and charts on long-lived tabs until a
manual refresh (the 2026-07-10 session's frozen-dashboard symptom).

These tests simulate exactly that starvation state in the browser: the bridge's
connection flags claim ``connected`` + frames-received while the WS delivers
nothing (the ring buffers stay empty). The assertions observe the Dash
callback wire (``_dash-update-component`` responses for the store outputs):

- pre-N1, the sticky gate makes the store callbacks return ``no_update``
  (HTTP 204 / empty responses) under this state — the store starves;
- post-N1, data-bearing 200s keep flowing every poll tick, and a stopped
  run's populated store is never wiped by the continuing 1 Hz poll.

The store wire is the deliberate observable: the store is the single source
for tiles and charts, and asserting on it keeps these tests independent of a
separate pre-existing harness issue where ``update_metrics_display`` renders
lazily in headless runs (present on main before N1 — see the N1 PR notes).
"""

import json
import time

import pytest
import requests

_STICKY_WS_SILENT_STATE = """
() => {
    const d = window._juniperWsDrain;
    if (!d) { return false; }
    // The starvation state from plan §4 I-1 root cause 1: the WS layer
    // reports connected + frames-received while no frames are flowing (the
    // ring buffers stay empty). peekConnectionStatus is overridden (not just
    // the fields) because websocket_client.js replaces _connectionStatus
    // wholesale on every status change — the harness's failing socket would
    // otherwise flip `connected` back to false within a tick. The peek
    // clientside callback copies this into the ws-connection-status store on
    // the next fast tick, which is exactly the State the pre-N1 sticky gates
    // consumed.
    d._metricsReceived = true;
    d._topologyReceived = true;
    d.peekConnectionStatus = function() {
        return {connected: true, reconnecting: false, mode: "live", metricsReceived: true, topologyReceived: true};
    };
    return true;
}
"""

_METRICS_STORE_OUTPUT = "metrics-panel-metrics-store.data"
_TOPOLOGY_STORE_OUTPUT = "network-visualizer-topology-store.data"


def _status(canopy_url: str) -> dict:
    r = requests.get(f"{canopy_url}/api/status", timeout=2)
    r.raise_for_status()
    return r.json()


def _wait_status(canopy_url: str, predicate, *, timeout: float = 10.0) -> dict:
    deadline = time.time() + timeout
    last: dict = {}
    while time.time() < deadline:
        last = _status(canopy_url)
        if predicate(last):
            return last
        time.sleep(0.2)
    raise AssertionError(f"status predicate not satisfied within {timeout}s; last={last}")


def _attach_store_collector(page, output_name):
    """Collect ``_dash-update-component`` responses whose callback output is
    ``output_name``. Body reads are deferred (sync-API handlers must not
    block); call the returned ``drain()`` after waiting to get
    ``[(status, payload-or-None), ...]``."""
    collected = []

    def on_response(resp):
        if "_dash-update-component" in resp.url:
            collected.append(resp)  # body read deferred

    page.on("response", on_response)

    def drain():
        results = []
        for resp in collected:
            try:
                out = json.loads(resp.request.post_data or "{}").get("output", "")
            except Exception:
                continue
            if out != output_name:
                continue
            payload = None
            if resp.status == 200:
                try:
                    body = json.loads(resp.text())
                    payload = body.get("response", {}).get(output_name.rsplit(".", 1)[0], {}).get("data")
                except Exception:
                    payload = None
            results.append((resp.status, payload))
        return results

    return drain


def _wait_for(predicate, *, timeout: float, interval: float = 0.5, page=None):
    """Bounded wait helper: poll ``predicate`` until truthy or timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = predicate()
        if result:
            return result
        if page is not None:
            page.wait_for_timeout(int(interval * 1000))
        else:
            time.sleep(interval)
    return None


def _ensure_running_run(dashboard_page, canopy_url):
    """Lifecycle-robust precondition: return with a training run RUNNING.

    On CI runners the demo's boot-time auto-run (or the fresh run a preceding
    test left behind) converges after ~31 epochs — CI has no juniper-data
    service, so the demo falls back to local dataset generation, every
    first-cascade candidate misses the correlation threshold, and the run ends
    in fsm ``COMPLETED`` (hidden_units=0) roughly 31 s after any start. The
    Start button posts ``/api/train/start`` with the route-default
    ``reset=False``, and ``training_state_machine._handle_start`` has no
    COMPLETED branch — START from COMPLETED is refused (409) and
    ``is_running`` never flips, which is exactly how this suite went red on
    main 2026-07-12..13. RESET is legal from every state (→ STOPPED), and
    START from STOPPED is legal, so go Reset → Start whenever the run is not
    live. The restart-orchestration UX itself (surfacing the refusal, N3) is
    product work tracked in the training-runtime defects plan — these tests
    only need the precondition."""
    if _status(canopy_url).get("is_running"):
        return
    dashboard_page.click("#reset-button")
    _wait_status(canopy_url, lambda s: s.get("is_running") is False and s.get("fsm_status") != "COMPLETED")
    dashboard_page.click("#start-button")
    _wait_status(canopy_url, lambda s: s.get("is_running") is True)


@pytest.mark.ui
def test_metrics_store_polls_on_long_lived_tab_with_ws_silent(dashboard_page, canopy_url):
    """The N1 regression pin: a long-lived tab whose WS claims connected +
    metricsReceived (but delivers nothing) still hydrates the metrics store
    via the 1 Hz REST poll. Pre-N1 the sticky gate returned ``no_update`` for
    every tick in this state, starving the store (and everything it feeds)
    until a manual refresh."""
    dashboard_page.wait_for_selector("#start-button", timeout=15_000)
    assert dashboard_page.evaluate(_STICKY_WS_SILENT_STATE), "ws_dash_bridge drain object not present"

    # Demo mode auto-starts a training run at boot, but it may already have
    # converged — establish a live run the FSM-legal way (see the helper).
    _ensure_running_run(dashboard_page, canopy_url)

    drain = _attach_store_collector(dashboard_page, _METRICS_STORE_OUTPUT)

    # Liveness: within a handful of fast ticks the poll must deliver at least
    # two data-bearing store writes (epochs advancing), despite the sticky
    # connected+metricsReceived state.
    def data_writes():
        writes = [p for s, p in drain() if s == 200 and isinstance(p, list) and p]
        return writes if len(writes) >= 2 else None

    writes = _wait_for(data_writes, timeout=12.0, page=dashboard_page)
    assert writes, f"metrics-store poll starved under WS-silent sticky state; captured={[(s, type(p).__name__) for s, p in drain()]}"
    epochs = [w[-1].get("epoch") for w in writes if isinstance(w[-1], dict)]
    assert any(isinstance(e, int) and e > 0 for e in epochs), f"store writes carried no advancing epochs: {epochs}"


@pytest.mark.ui
def test_populated_store_survives_poll_after_stop(dashboard_page, canopy_url):
    """Post-run persistence (the empty-guard's last-known-good posture): with
    the store demonstrably populated by the un-gated poll (the pre-stop
    discriminator — starved on pre-N1 code), stop the run and keep observing
    further poll dispatches. The store must never be wiped by an empty write:
    a post-stop dispatch may carry rows (backend retained history) or answer
    ``no_update``/204 (backend cleared history and the empty-guard preserved
    the store) — but an empty-list 200 write is the chart-wipe regression."""
    dashboard_page.wait_for_selector("#stop-button", timeout=15_000)
    assert dashboard_page.evaluate(_STICKY_WS_SILENT_STATE), "ws_dash_bridge drain object not present"

    _ensure_running_run(dashboard_page, canopy_url)

    drain = _attach_store_collector(dashboard_page, _METRICS_STORE_OUTPUT)

    # Pre-stop: the un-gated poll must populate the store under the sticky
    # WS-silent state (pre-N1 this starves and the test fails here).
    def populated_write():
        return [p for s, p in drain() if s == 200 and isinstance(p, list) and p] or None

    assert _wait_for(populated_write, timeout=12.0, page=dashboard_page), f"store never populated under WS-silent sticky state; captured={[(s, type(p).__name__) for s, p in drain()]}"
    pre_stop_count = len(drain())

    dashboard_page.click("#stop-button")
    _wait_status(canopy_url, lambda s: s.get("is_running") is False)
    dashboard_page.wait_for_timeout(6_000)  # ≥3 poll ticks post-stop

    all_writes = drain()
    post_stop = all_writes[pre_stop_count:]
    assert post_stop, "poll went silent after stop — expected continuing dispatches"
    empty_writes = [p for s, p in post_stop if s == 200 and isinstance(p, list) and not p]
    assert not empty_writes, f"post-stop poll wiped the metrics store ({len(empty_writes)} empty writes of {len(post_stop)} dispatches)"


@pytest.mark.ui
def test_topology_store_fetches_on_tab_switch_with_ws_silent(dashboard_page, canopy_url):
    """I-2 companion: with the WS quiet (sticky topologyReceived + connected,
    no cascade_add frames), switching to the Network Topology tab must fetch
    REST topology into the store — pre-N1 the sticky gate returned
    ``no_update`` here, leaving the visualizer starved."""
    dashboard_page.wait_for_selector("#visualization-tabs", timeout=15_000)
    assert dashboard_page.evaluate(_STICKY_WS_SILENT_STATE), "ws_dash_bridge drain object not present"

    # A live run guarantees a real network behind /api/topology; the
    # converged post-run state is where this test went red in CI (its store
    # dispatches carried null payloads there — unreachable with a live run).
    _ensure_running_run(dashboard_page, canopy_url)

    drain = _attach_store_collector(dashboard_page, _TOPOLOGY_STORE_OUTPUT)
    dashboard_page.locator("#visualization-tabs >> a:has-text('Network Topology')").first.click()

    # Tab activation triggers the callback immediately; the slow interval
    # (5 s) re-fires it while the tab stays active. Wait ≤ slow tick + margin.
    def topo_write():
        writes = [p for s, p in drain() if s == 200 and isinstance(p, dict) and p.get("nodes")]
        return writes or None

    writes = _wait_for(topo_write, timeout=12.0, page=dashboard_page)
    assert writes, f"topology store never received a REST fetch under WS-silent sticky state; captured={[(s, type(p).__name__) for s, p in drain()]}"
    assert writes[-1].get("connections") is not None, "transformed topology payload missing connections"
