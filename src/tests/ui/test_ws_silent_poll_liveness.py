"""N1 → N8 (training-runtime defects plan §4 I-1/I-2): WS liveness of the store polls.

Pre-N1, the metrics/topology store polls were suppressed by sticky WS flags
(``metricsReceived`` / ``topologyReceived`` + ``connected``): once a tab had
seen a single WS metrics frame, its REST polls stopped forever — even when no
further frames arrived — freezing tiles and charts on long-lived tabs until a
manual refresh (the 2026-07-10 session's frozen-dashboard symptom).

N1 un-gated the polls; N8 made the metrics/state stores WS-PRIMARY with the poll
demoted to a **liveness-gated** fallback (posture O3+O1). The gate is a LIVE
freshness signal — the age of the last WS frame (``ws_dash_bridge.js``'s
``_lastMetricsFrameMs`` / ``_lastStateFrameMs`` via ``peekLiveness``) vs
``WS_LIVENESS_WINDOW_MS`` — and deliberately NOT the sticky ``metricsReceived``
flag N1 retired. So the starvation contract these tests encode still holds, now
expressed against the N8 gate:

- **WS-silent** (``_WS_SILENT_STATE``): the demo backend keeps broadcasting, so
  faithfully simulating "no fresh WS data reaching the gate" means neutralizing the
  WS *data path* itself — the drains yield nothing and ``peekLiveness`` reports a
  stale age (NOT merely toggling the sticky flag, which the gate ignores). Under
  this state the metrics store MUST stay live via the REST poll, and a stopped
  run's populated store is never wiped (empty-guard). This is the preserved
  anti-starvation protection.
- **WS-fresh** (``_ws_fresh_state``): fresh frames + a fresh ``peekLiveness`` age
  drive the WS-primary path; a sentinel-epoch injected frame proves the store is
  fed from the WS buffer (a value REST could never produce), and the liveness store
  flips ``metrics_live`` false again within a tick the moment the age goes stale —
  the anti-sticky reset, end-to-end.

The store wire is the deliberate observable: the store is the single source
for tiles and charts, and asserting on it keeps these tests independent of a
separate pre-existing harness issue where ``update_metrics_display`` renders
lazily in headless runs (present on main before N1 — see the N1 PR notes).
"""

import json
import time

import pytest
import requests

# N8: neutralize the WS *data path* so the liveness gate reads stale and the
# buffers yield nothing — the faithful WS-silent starvation state. The demo
# backend keeps emitting frames, so overriding only the sticky flags (which the
# N8 gate ignores) would leave the real frames feeding _lastMetricsFrameMs and the
# store WS-primary; we therefore also stub the drains (empty) and peekLiveness
# (stale age). The sticky flags + peekConnectionStatus stay overridden to prove the
# gate does NOT consult them.
_WS_SILENT_STATE = """
() => {
    const d = window._juniperWsDrain;
    if (!d) { return false; }
    d._metricsReceived = true;
    d._topologyReceived = true;
    d.peekConnectionStatus = function() {
        return {connected: true, reconnecting: false, mode: "live", metricsReceived: true, topologyReceived: true};
    };
    // The load-bearing N8 change: stale the LIVE freshness signal + drain nothing,
    // so ws_live is false and no WS events reach the store — the poll must carry it.
    d.drainMetrics = function() { return []; };
    d.drainState = function() { return null; };
    d.peekLiveness = function() { return {metrics_age_ms: 999999, state_age_ms: 999999}; };
    return true;
}
"""

# Back-compat alias for the historical name used elsewhere / in muscle memory.
_STICKY_WS_SILENT_STATE = _WS_SILENT_STATE


def _ws_fresh_state(sentinel_epoch: int) -> str:
    """JS injector: drive the WS-primary path deterministically (bridge-state
    independent). ``peekLiveness`` reports a fresh age (gate → live) and
    ``drainMetrics`` yields one nested sentinel-epoch metric frame per drain, so the
    metrics store accumulates a value REST could never mint — proving WS-primary."""
    return """
    () => {
        const d = window._juniperWsDrain;
        if (!d) { return false; }
        d.peekLiveness = function() { return {metrics_age_ms: 50, state_age_ms: 50}; };
        d.drainMetrics = function() {
            return [{epoch: %d, metrics: {loss: 0.0123, accuracy: 0.987}, network_topology: {hidden_units: 3}, phase: "output"}];
        };
        return true;
    }
    """ % sentinel_epoch


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
    ``output_name``. Body reads happen inside ``drain()`` (sync-API response
    handlers must not block) and are MEMOIZED on first success: Chromium
    evicts response bodies under renderer pressure (headless CI runners,
    especially after heavy re-renders like the network-visualizer tab), so a
    late re-read of an old response raises and, pre-memoization, every
    payload silently degraded to ``None`` at assert time — the
    ``(200, NoneType)`` captures of the 2026-07-12..14 CI failures. Call
    ``drain()`` periodically (the ``_wait_for`` loops do) so first reads
    happen close to arrival; a body that is never readable is surfaced as a
    ``"<body-unavailable:ExcName>"`` sentinel payload instead of ``None``.
    Returns ``[(status, payload), ...]`` for responses matching
    ``output_name``."""
    collected = []
    memo = {}  # index into collected -> ("nonmatch",) | ("match", status, payload)
    inputs = {}  # index into collected -> {input_id: value} of matching dispatches (failure triage)

    def on_response(resp):
        if "_dash-update-component" in resp.url:
            collected.append(resp)  # body read deferred to drain()

    page.on("response", on_response)

    def drain():
        results = []
        for i, resp in enumerate(collected):
            entry = memo.get(i)
            if entry is None:
                try:
                    req = json.loads(resp.request.post_data or "{}")
                    out = req.get("output", "")
                except Exception:
                    memo[i] = ("nonmatch",)
                    continue
                # N8: a Dash ``allow_duplicate`` output is encoded as
                # ``<id.prop>@<hash>`` on the wire. The N8 metrics/state store is now
                # co-owned by the liveness-gated poll (plain output) AND the WS-primary
                # append callback (``@hash`` output); accept both so this collector sees
                # the store's data regardless of which callback wrote it.
                if out != output_name and not out.startswith(output_name + "@"):
                    memo[i] = ("nonmatch",)
                    continue
                inputs[i] = {inp.get("id"): inp.get("value") for inp in req.get("inputs", []) if isinstance(inp, dict)}
                if resp.status != 200:
                    entry = memo[i] = ("match", resp.status, None)
                else:
                    try:
                        body = json.loads(resp.text())
                        resp_map = body.get("response") or {}
                        component = output_name.rsplit(".", 1)[0]
                        if component in resp_map:
                            payload = resp_map[component].get("data")
                        else:
                            # dash 4.x serializes PreventUpdate/no_update as
                            # HTTP 200 {"multi":true,"response":{}} (not 204):
                            # the output key is simply absent. Mark it so a
                            # gated/no-op dispatch is distinguishable from a
                            # genuine null write in failure messages.
                            payload = "<no_update>"
                        entry = memo[i] = ("match", 200, payload)
                    except Exception as exc:
                        # Body not readable (yet or anymore) — do NOT memoize,
                        # so the next drain() retries; report a sentinel that
                        # no assertion can mistake for real data.
                        entry = ("match", 200, f"<body-unavailable:{type(exc).__name__}>")
            if entry[0] == "nonmatch":
                continue
            results.append((entry[1], entry[2]))
        return results

    def detail():
        """(status, payload, inputs) triples of matching dispatches — for failure messages."""
        drained = drain()
        matched = [inputs.get(i, {}) for i in sorted(inputs)]
        return [(s, p, matched[j] if j < len(matched) else {}) for j, (s, p) in enumerate(drained)]

    drain.detail = detail
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
    """The starvation-protection pin, expressed against the N8 gate: a long-lived
    tab whose WS claims connected + metricsReceived but delivers NO fresh data (the
    drains yield nothing and ``peekLiveness`` reads stale) still hydrates the metrics
    store via the REST poll. Pre-N1 the sticky gate starved it forever; under N8 the
    liveness gate reads stale (never the sticky flag), so the poll re-engages — REST
    is the ONLY possible source here (the WS drains are stubbed empty), so
    data-bearing writes prove REST liveness."""
    dashboard_page.wait_for_selector("#start-button", timeout=15_000)
    assert dashboard_page.evaluate(_WS_SILENT_STATE), "ws_dash_bridge drain object not present"

    # Demo mode auto-starts a training run at boot, but it may already have
    # converged — establish a live run the FSM-legal way (see the helper).
    _ensure_running_run(dashboard_page, canopy_url)

    drain = _attach_store_collector(dashboard_page, _METRICS_STORE_OUTPUT)

    # Liveness: within a handful of fast ticks the poll must deliver at least
    # two data-bearing store writes (epochs advancing), despite the sticky
    # connected+metricsReceived state and with the WS data path silenced.
    def data_writes():
        writes = [p for s, p in drain() if s == 200 and isinstance(p, list) and p]
        return writes if len(writes) >= 2 else None

    writes = _wait_for(data_writes, timeout=12.0, page=dashboard_page)
    assert writes, f"metrics-store poll starved under WS-silent state; captured={[(s, type(p).__name__) for s, p in drain()]}"
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
    assert dashboard_page.evaluate(_WS_SILENT_STATE), "ws_dash_bridge drain object not present"

    _ensure_running_run(dashboard_page, canopy_url)

    drain = _attach_store_collector(dashboard_page, _METRICS_STORE_OUTPUT)

    # Pre-stop: the liveness-gated REST poll must populate the store under the
    # WS-silent state (WS drains stubbed empty + stale age → REST is the source).
    def populated_write():
        return [p for s, p in drain() if s == 200 and isinstance(p, list) and p] or None

    assert _wait_for(populated_write, timeout=12.0, page=dashboard_page), f"store never populated under WS-silent state; captured={[(s, type(p).__name__) for s, p in drain()]}"
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
    """I-2 companion (topology stays N1 — N8 does not change the tab-gated slow poll):
    with the WS quiet (topologyReceived + connected, no cascade_add frames),
    switching to the Network Topology tab must fetch REST topology into the store —
    pre-N1 the sticky gate returned ``no_update`` here, leaving the visualizer
    starved."""
    dashboard_page.wait_for_selector("#visualization-tabs", timeout=15_000)
    assert dashboard_page.evaluate(_WS_SILENT_STATE), "ws_dash_bridge drain object not present"

    # A live run guarantees a real network behind /api/topology; the
    # converged post-run state is where this test went red in CI (its store
    # dispatches carried null payloads there — unreachable with a live run).
    _ensure_running_run(dashboard_page, canopy_url)

    drain = _attach_store_collector(dashboard_page, _TOPOLOGY_STORE_OUTPUT)
    dashboard_page.locator("#visualization-tabs >> a:has-text('Network Topology')").first.click()
    # Confirm the tab actually activated (the callback's REST fallback is
    # tab-gated) before holding the store to the fetch contract.
    dashboard_page.wait_for_selector("#visualization-tabs a.active:has-text('Network Topology')", timeout=10_000)

    # Tab activation triggers the callback immediately; the slow interval
    # (5 s) re-fires it while the tab stays active. Wait ≤ slow tick + margin.
    def topo_write():
        writes = [p for s, p in drain() if s == 200 and isinstance(p, dict) and p.get("nodes")]
        return writes or None

    writes = _wait_for(topo_write, timeout=15.0, page=dashboard_page)
    if not writes:
        # Failure triage, in causality order:
        # 1. per-dispatch active_tab values — a non-"topology" value on every
        #    dispatch means the gate (not the fetch) starved the store;
        # 2. direct GET /api/topology — route-broken vs wire-broken;
        # 3. a forced callback-wire POST with active_tab="topology" — if THIS
        #    returns data while the browser dispatches no_update'd, the
        #    handler works and the dispatches carried the wrong inputs; if it
        #    also comes back empty/no_update, the server side is the problem.
        dispatches = [(s, p if isinstance(p, str) else type(p).__name__, (inp or {}).get("visualization-tabs")) for s, p, inp in drain.detail()]
        try:
            route = requests.get(f"{canopy_url}/api/topology", timeout=2)
            route_info = (route.status_code, sorted(route.json().keys()) if route.ok else route.text[:120])
        except Exception as exc:
            route_info = f"route probe failed: {exc}"
        component = _TOPOLOGY_STORE_OUTPUT.rsplit(".", 1)[0]
        probe_body = {
            "output": _TOPOLOGY_STORE_OUTPUT,
            "outputs": {"id": component, "property": "data"},
            "inputs": [
                {"id": "slow-update-interval", "property": "n_intervals", "value": 99},
                {"id": "ws-topology-buffer", "property": "data", "value": None},
                {"id": "visualization-tabs", "property": "active_tab", "value": "topology"},
            ],
            "changedPropIds": ["visualization-tabs.active_tab"],
        }
        try:
            wire = requests.post(f"{canopy_url}/dashboard/_dash-update-component", json=probe_body, headers={"Origin": canopy_url}, timeout=8)
            if not wire.ok:
                wire_info = (wire.status_code, wire.text[:120])
            else:
                comp = (wire.json().get("response") or {}).get(component)
                wire_info = (wire.status_code, "no_update" if comp is None else f"nodes={len((comp.get('data') or {}).get('nodes') or [])}")
        except Exception as exc:
            wire_info = f"wire probe failed: {exc}"
        raise AssertionError(f"topology store never received a REST fetch under WS-silent state; dispatches (status, payload, active_tab)={dispatches}; direct GET /api/topology={route_info}; forced wire dispatch={wire_info}")
    assert writes[-1].get("connections") is not None, "transformed topology payload missing connections"


@pytest.mark.ui
def test_metrics_store_ws_primary_feeds_store_when_fresh(dashboard_page, canopy_url):
    """N8 WS-primary pin: when the WS metrics stream is fresh, the store is fed from
    the WS buffer via the ``allow_duplicate`` append callback (not the REST poll). A
    sentinel-epoch frame injected through the drain lands in the metrics store — a
    value the REST /api/metrics/history poll could never mint — so its presence proves
    the WS-primary path drove the tiles."""
    dashboard_page.wait_for_selector("#start-button", timeout=15_000)
    sentinel = 987654
    assert dashboard_page.evaluate(_ws_fresh_state(sentinel)), "ws_dash_bridge drain object not present"
    _ensure_running_run(dashboard_page, canopy_url)

    # The collector accepts both the poll (plain) and append (``@hash``) outputs, so a
    # WS-primary write is visible here.
    drain = _attach_store_collector(dashboard_page, _METRICS_STORE_OUTPUT)

    def sentinel_write():
        for _s, payload in drain():
            if isinstance(payload, list) and any(isinstance(row, dict) and row.get("epoch") == sentinel for row in payload):
                return payload
        return None

    hit = _wait_for(sentinel_write, timeout=12.0, page=dashboard_page)
    assert hit, f"WS-primary sentinel epoch {sentinel} never reached the metrics store; captured={[(s, type(p).__name__) for s, p in drain()]}"


@pytest.mark.ui
def test_poll_resumes_rest_when_ws_goes_stale(dashboard_page, canopy_url):
    """N8 anti-sticky pin (end-to-end): WS-primary sentinels fill the store while fresh,
    then the moment the frame age goes stale the liveness-gated REST poll re-engages and
    OVERWRITES the store with real /api/metrics/history rows (no sentinel). The revert
    from WS-injected values to REST values is the categorical break from the N1-era
    sticky gate that latched off forever."""
    dashboard_page.wait_for_selector("#start-button", timeout=15_000)
    sentinel = 987654
    assert dashboard_page.evaluate(_ws_fresh_state(sentinel)), "ws_dash_bridge drain object not present"
    _ensure_running_run(dashboard_page, canopy_url)

    drain = _attach_store_collector(dashboard_page, _METRICS_STORE_OUTPUT)

    # Phase 1 — fresh: the WS-primary append must land the sentinel.
    def sentinel_write():
        return next((p for _s, p in drain() if isinstance(p, list) and any(isinstance(r, dict) and r.get("epoch") == sentinel for r in p)), None)

    assert _wait_for(sentinel_write, timeout=12.0, page=dashboard_page), "WS-primary never fed the sentinel before the stale transition"
    boundary = len(drain())

    # Phase 2 — stale: no WS events + stale age → append stops, poll re-engages REST.
    dashboard_page.evaluate(_WS_SILENT_STATE)
    _ensure_running_run(dashboard_page, canopy_url)  # keep a live run so REST has rows

    def rest_write_after():
        after = drain()[boundary:]
        rest = [p for _s, p in after if isinstance(p, list) and p and not any(isinstance(r, dict) and r.get("epoch") == sentinel for r in p)]
        return rest or None

    assert _wait_for(rest_write_after, timeout=15.0, page=dashboard_page), "the REST poll never re-engaged after the WS went stale (the store kept only WS " f"sentinels — sticky regression); post-stale writes={[(s, type(p).__name__) for s, p in drain()[boundary:]]}"
