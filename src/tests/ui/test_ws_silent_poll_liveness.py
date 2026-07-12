"""N1 (training-runtime defects plan §4 I-1/I-2): WS-silent poll liveness.

Pre-N1, the metrics/topology store polls were suppressed by sticky WS flags
(``metricsReceived`` / ``topologyReceived`` + ``connected``): once a tab had
seen a single WS metrics frame, its REST polls stopped forever — even when no
further frames arrived — freezing tiles and charts on long-lived tabs until a
manual refresh (the 2026-07-10 session's frozen-dashboard symptom).

These tests simulate exactly that starvation state in the browser: the bridge's
connection flags claim ``connected`` + frames-received while the WS delivers
nothing (the ring buffers stay empty). With the N1 un-gated polls the tiles must
advance anyway, and a finished run's tiles must survive the 1 Hz poll (the
empty-guard: an empty/errored fetch never wipes a populated store).
"""

import time

import pytest
import requests

_STICKY_WS_SILENT_STATE = """
() => {
    const d = window._juniperWsDrain;
    if (!d) { return false; }
    // The starvation state from plan §4 I-1 root cause 1: status says
    // connected and frames-received, but no frames are flowing (buffers
    // stay empty). The peek callback copies this into ws-connection-status
    // on the next fast tick.
    d._connectionStatus = {connected: true, reconnecting: false, mode: "live"};
    d._metricsReceived = true;
    d._topologyReceived = true;
    return true;
}
"""


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


def _epoch_tile(page) -> str:
    return (page.text_content("#metrics-panel-current-epoch") or "").strip()


@pytest.mark.ui
def test_tiles_advance_via_poll_on_long_lived_tab_with_ws_silent(dashboard_page, canopy_url):
    """The N1 regression pin: a long-lived tab whose WS claims connected +
    metricsReceived (but delivers nothing) still sees tiles advance, because
    the metrics-store poll is no longer gated on WS state. Pre-N1 this froze
    at the initial value until a manual refresh. Also covers post-completion
    persistence: after the run ends, ≥3 further poll ticks must not blank the
    tiles (the empty-guard's last-known-good posture)."""
    dashboard_page.wait_for_selector("#metrics-panel-current-epoch", timeout=15_000)
    assert dashboard_page.evaluate(_STICKY_WS_SILENT_STATE), "ws_dash_bridge drain object not present"

    initial = _epoch_tile(dashboard_page)

    dashboard_page.click("#start-button")
    _wait_status(canopy_url, lambda s: s.get("is_running") is True)

    # Liveness: the epoch tile must move off its initial value via the 1 Hz
    # poll — no refresh, no WS frames. Pre-N1 the sticky gate kept the store
    # (and therefore this tile) frozen indefinitely.
    dashboard_page.wait_for_function(
        """(init) => {
            const el = document.getElementById('metrics-panel-current-epoch');
            if (!el) { return false; }
            const v = el.textContent.trim();
            return v !== init && v !== '' && v !== '0';
        }""",
        arg=initial,
        timeout=20_000,
    )

    # Let the run finish naturally (demo runs are short); fall back to Stop so
    # the persistence probe below always runs against a non-running backend.
    try:
        _wait_status(canopy_url, lambda s: s.get("is_running") is False, timeout=60.0)
    except AssertionError:
        dashboard_page.click("#stop-button")
        _wait_status(canopy_url, lambda s: s.get("is_running") is False, timeout=10.0)

    settled = _epoch_tile(dashboard_page)
    assert settled not in ("", "0"), f"expected a populated epoch tile after the run, got {settled!r}"

    # Post-completion persistence: ≥3 further 1 Hz poll ticks must not wipe
    # the tiles back to their empty defaults (chart-wipe regression guard).
    dashboard_page.wait_for_timeout(3_500)
    persisted = _epoch_tile(dashboard_page)
    assert persisted not in ("", "0"), f"tiles wiped by the post-run poll: epoch tile went {settled!r} -> {persisted!r}"
    loss_tile = (dashboard_page.text_content("#metrics-panel-current-loss") or "").strip()
    assert loss_tile != "--", "loss tile wiped by the post-run poll"


@pytest.mark.ui
def test_topology_paints_on_tab_switch_with_ws_silent(dashboard_page, canopy_url):
    """I-2 companion: with the WS quiet (sticky topologyReceived + connected,
    no cascade_add frames), switching to the Network Topology tab must still
    paint the visualizer — the tab-activation Input plus the un-gated slow poll
    fetch REST topology. Pre-N1 the sticky gate returned no_update here."""
    dashboard_page.wait_for_selector("#visualization-tabs", timeout=15_000)
    assert dashboard_page.evaluate(_STICKY_WS_SILENT_STATE), "ws_dash_bridge drain object not present"

    dashboard_page.locator("#visualization-tabs >> a:has-text('Network Topology')").first.click()

    # The graph must render plotly traces from the REST fetch within a slow
    # tick + margin (5 s interval; tab-activation usually paints sooner).
    dashboard_page.wait_for_function(
        """() => {
            const root = document.getElementById('network-visualizer-graph');
            if (!root) { return false; }
            const gd = root.querySelector('.js-plotly-plot') || root;
            return !!(gd && gd.data && gd.data.length > 0);
        }""",
        timeout=15_000,
    )
