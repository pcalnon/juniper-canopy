#!/usr/bin/env python
"""F-CANOPY-055, F-CANOPY-058 and F-CANOPY-068: paced polls, by request/ack.

Findings: juniper-ml ``notes/JUNIPER_2026-08-09_JUNIPER-CANOPY_E2E-VALIDATION-EVIDENCE.md``.

* **F-CANOPY-055 (P1).** The top status bar's feeder rode ``fast-update-interval`` (1 s)
  with a round trip of ~1.2 s and more. dash-renderer evicts a ``watched`` request when the
  same callback is requested again and discards its response, so every response was
  evicted: 0 of 36 applied on the census, and the bar held its layout defaults for the
  life of the page.
* **F-CANOPY-058 (P1).** canopy#613 kept the metrics store's feeder from re-requesting over
  itself with a ``running=`` guard on its Interval's ``disabled``. The renderer releases
  that guard from ``completeJob()`` for an evicted request's late completion too, so any
  mid-fetch re-enable could start a chain of evictions: observed live on canopy ``main`` in
  runs of up to 11 evictions and 34.8 s (Phase 11).
* **F-CANOPY-068.** The guard's strand watchdog sampled ``disabled`` every 5 s against a
  ~4.9 s feeder cycle and fired falsely, mid-fetch, 13 and 15 times in two 25-minute runs.

The fix: each paced poll's feeder has ONE Input, a request store written only by a
clientside pacer, and a second Output, an ack store echoing the request's ``seq``. The
pacer writes the next request only when the ack has caught up, or when the outstanding
request is older than ``POLL_PACER_STALE_MS``.

What these tests prove:
  * WIRING (everywhere): each feeder's only Input is its request store; nothing else writes
    the request or the ack; the ack is never an Input (no cycle); no ``running=`` guard;
    the display mode reaches the metrics feeder as State and its pacer as an Input; the
    registered pacers are the function the node tests run.
  * FEEDERS (everywhere): each ack echoes the request's ``seq`` on every return path,
    including a raised handler; the request's ``reason`` maps onto the handler's
    full-history modulus gate exactly as the old triggers did.
  * PACER RULE (under node, on the registered JavaScript): ask only when acknowledged or
    stale; a late ack of an older request does not count; a display-mode change is read
    from its value; the seq-0 mount request ages from first sight.
  * TEN IDLE MINUTES (under node, simulated clock): on a healthy lane whose cycle is near
    5 s, with round trips drawn from Phase 11's measured range, no request is ever made
    while another is in flight and the stale path never fires. The same simulation run
    against canopy#613's guard-plus-watchdog semantics fires falsely, so it can fail.

What they cannot prove: that the live renderer agrees. juniper-ml's real-renderer check and
the census on a leg serving this branch do that.

Falsified against the parent (``3029d07d``): the wiring and feeder tests fail at import
(``poll_pacer_js`` and the request/ack ids do not exist), and so do the node tests.
"""

import json
import random
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import dash
import pytest

_SRC = Path(__file__).resolve().parents[3]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from canopy_constants import DashboardConstants  # noqa: E402
from frontend import dashboard_manager as dm  # noqa: E402
from frontend.dashboard_manager import DashboardManager, poll_pacer_js  # noqa: E402

NODE = shutil.which("node") or shutil.which("nodejs")
NU = "__NO_UPDATE__"

METRICS_REQ = "metrics-store-request.data"
METRICS_ACK = "metrics-store-ack.data"
STATUS_REQ = "status-bar-request.data"
STATUS_ACK = "status-bar-ack.data"
MODE = "metrics-panel-display-mode-store.data"
METRICS_LANE = "metrics-store-interval"
FAST_LANE = "fast-update-interval"


@pytest.fixture(scope="module")
def dashboard():
    return DashboardManager({"title": "Test Dashboard", "update_interval": 1000, "server": {"host": "localhost", "port": 8050}})


def _outputs(entry):
    raw = str(entry["output"])
    parts = raw[2:-2].split("...") if raw.startswith("..") and raw.endswith("..") else [raw]
    return {part.split("@", 1)[0] for part in parts}


def _deps(entry, key):
    return {f"{d['id']}.{d['property']}" for d in entry.get(key) or [] if isinstance(d.get("id"), str)}


def _writers(dashboard, prop):
    return [e for e in dashboard.app._callback_list if prop in _outputs(e)]


def _one_writer(dashboard, prop):
    writers = _writers(dashboard, prop)
    assert len(writers) == 1, f"{prop}: {len(writers)} writers"
    return writers[0]


def _layout_ids(dashboard):
    found = {}

    def walk(node):
        if isinstance(node, (list, tuple)):
            for child in node:
                walk(child)
            return
        if node is None or not hasattr(node, "to_plotly_json"):
            return
        cid = getattr(node, "id", None)
        if isinstance(cid, str):
            found[cid] = node
        walk(getattr(node, "children", None))

    walk(dashboard.app.layout)
    return found


# ---------------------------------------------------------------------------------------------
# WIRING
# ---------------------------------------------------------------------------------------------
@pytest.mark.unit
class TestWiring:
    @pytest.mark.parametrize(
        "feeder_output, req_prop, ack",
        [
            ("metrics-panel-metrics-store.data", METRICS_REQ, METRICS_ACK),
            ("top-status-display.children", STATUS_REQ, STATUS_ACK),
        ],
    )
    def test_the_feeder_has_one_input_the_request(self, dashboard, feeder_output, req_prop, ack):
        """Any other Input could re-request the feeder mid-flight, which evicts it."""
        feeders = [e for e in _writers(dashboard, feeder_output) if req_prop in _deps(e, "inputs")]
        assert len(feeders) == 1, feeders
        feeder = feeders[0]
        assert _deps(feeder, "inputs") == {req_prop}
        assert ack in _outputs(feeder)
        assert not feeder.get("running"), "a running= guard is released by an evicted request's completion (F-CANOPY-058)"

    @pytest.mark.parametrize("req_prop", [METRICS_REQ, STATUS_REQ])
    def test_only_the_clientside_pacer_writes_the_request(self, dashboard, req_prop):
        pacer = _one_writer(dashboard, req_prop)
        assert pacer.get("clientside_function"), "the pacer must be clientside: a server pacer is itself a round trip"
        assert pacer["prevent_initial_call"] is True, "the layout's seq-0 request is the mount fetch"

    @pytest.mark.parametrize("ack", [METRICS_ACK, STATUS_ACK])
    def test_only_the_feeder_writes_the_ack(self, dashboard, ack):
        feeder = _one_writer(dashboard, ack)
        assert not feeder.get("clientside_function")

    @pytest.mark.parametrize("ack", [METRICS_ACK, STATUS_ACK])
    def test_the_ack_is_never_an_input(self, dashboard, ack):
        """As an Input it would close pacer -> feeder -> pacer, a dependency cycle."""
        readers = [sorted(_outputs(e)) for e in dashboard.app._callback_list if ack in _deps(e, "inputs")]
        assert not readers, readers

    def test_the_metrics_pacer_reads_its_lane_and_the_display_mode(self, dashboard):
        pacer = _one_writer(dashboard, METRICS_REQ)
        assert _deps(pacer, "inputs") == {f"{METRICS_LANE}.n_intervals", MODE}
        assert _deps(pacer, "state") == {METRICS_REQ, METRICS_ACK}

    def test_the_status_pacer_rides_the_fast_lane(self, dashboard):
        pacer = _one_writer(dashboard, STATUS_REQ)
        assert _deps(pacer, "inputs") == {f"{FAST_LANE}.n_intervals"}
        assert _deps(pacer, "state") == {STATUS_REQ, STATUS_ACK}

    def test_the_display_mode_is_state_of_the_metrics_feeder(self, dashboard):
        feeder = _one_writer(dashboard, METRICS_ACK)
        assert MODE in _deps(feeder, "state")
        assert MODE not in _deps(feeder, "inputs")

    def test_both_pacer_lanes_are_still_apply_clamped(self):
        """The pacers ride gated lanes, so the CAN-000 clamp still stops them asking."""
        gated = {iid for iid, _tab in dm._GATED_POLL_INTERVALS}
        assert {METRICS_LANE, FAST_LANE} <= gated

    def test_the_request_stores_start_at_seq_zero(self, dashboard):
        ids = _layout_ids(dashboard)
        for store in ("metrics-store-request", "status-bar-request"):
            assert ids[store].data == {"seq": 0}, store
        for store in ("metrics-store-ack", "status-bar-ack"):
            assert ids[store].data is None, store

    @pytest.mark.parametrize("lane, extra", [(METRICS_LANE, True), (FAST_LANE, False)])
    def test_the_registered_pacer_is_the_function_under_test(self, dashboard, lane, extra):
        js = poll_pacer_js(lane, DashboardConstants.POLL_PACER_STALE_MS, extra_input=extra).strip()
        scripts = getattr(dashboard.app, "_inline_scripts", []) or []
        assert any(js in s for s in scripts), "the node tests would run a function canopy does not register"

    def test_the_stale_bound_is_interpolated(self):
        js = poll_pacer_js(METRICS_LANE, DashboardConstants.POLL_PACER_STALE_MS, extra_input=True)
        assert str(DashboardConstants.POLL_PACER_STALE_MS) in js
        assert "POLL_PACER_STALE_MS" not in js

    def test_the_stale_bound_is_far_above_any_measured_round_trip(self):
        """Re-issuing evicts the request in flight. The longest measured was 5.4 s (Phase 11)."""
        assert DashboardConstants.POLL_PACER_STALE_MS >= 20000
        assert DashboardConstants.POLL_PACER_STALE_MS >= 10 * DashboardConstants.API_TIMEOUT_SECONDS * 1000


# ---------------------------------------------------------------------------------------------
# FEEDERS
# ---------------------------------------------------------------------------------------------
def _feeder_fn(dashboard, ack):
    entry = _one_writer(dashboard, ack)
    key = str(entry["output"])
    return dashboard.app.callback_map[key]["callback"].__wrapped__


@pytest.mark.unit
class TestFeeders:
    def test_metrics_ack_echoes_the_seq(self, dashboard, monkeypatch):
        monkeypatch.setattr(dashboard, "_update_metrics_store_handler", lambda **kw: [{"epoch": 1}])
        fn = _feeder_fn(dashboard, METRICS_ACK)
        data, ack = fn({"seq": 7, "reason": "tick"}, {"mode": "window"}, None, None)
        assert data == [{"epoch": 1}] and ack == {"seq": 7}

    @pytest.mark.parametrize("exc", [RuntimeError("boom"), dash.exceptions.PreventUpdate()])
    def test_metrics_ack_lands_when_the_handler_raises(self, dashboard, monkeypatch, exc):
        def _raise(**_kw):
            raise exc

        monkeypatch.setattr(dashboard, "_update_metrics_store_handler", _raise)
        data, ack = _feeder_fn(dashboard, METRICS_ACK)({"seq": 3, "reason": "tick"}, None, None, None)
        assert data is dash.no_update and ack == {"seq": 3}

    def test_status_ack_echoes_the_seq(self, dashboard, monkeypatch):
        monkeypatch.setattr(dashboard, "_update_unified_status_bar_handler", lambda **kw: tuple(range(11)))
        out = _feeder_fn(dashboard, STATUS_ACK)({"seq": 12, "reason": "tick"}, None, None, True)
        assert len(out) == 12 and out[:11] == tuple(range(11)) and out[11] == {"seq": 12}

    def test_status_ack_lands_when_the_handler_raises(self, dashboard, monkeypatch):
        def _raise(**_kw):
            raise RuntimeError("boom")

        monkeypatch.setattr(dashboard, "_update_unified_status_bar_handler", _raise)
        out = _feeder_fn(dashboard, STATUS_ACK)({"seq": 4}, None, None, True)
        assert all(v is dash.no_update for v in out[:11]) and out[11] == {"seq": 4}

    @pytest.mark.parametrize(
        "req, trigger",
        [
            ({"seq": 0}, ""),
            ({"seq": 5, "reason": "tick"}, "metrics-store-interval.n_intervals"),
            ({"seq": 5, "reason": "stale"}, "metrics-store-interval.n_intervals"),
            ({"seq": 5, "reason": "extra"}, "metrics-panel-display-mode-store.data"),
            (None, ""),
        ],
    )
    def test_reason_maps_onto_the_handlers_trigger(self, req, trigger):
        assert DashboardManager._metrics_store_trigger(req) == trigger

    def test_full_mode_ticks_still_skip_off_the_modulus(self, dashboard, monkeypatch):
        """A tick request whose seq is off the modulus must not fetch the full history."""
        calls = []
        monkeypatch.setattr(dm.requests, "get", lambda *a, **k: calls.append(a) or (_ for _ in ()).throw(AssertionError("fetched")))
        mod = DashboardConstants.FULL_HISTORY_POLL_TICK_MODULUS
        data, ack = _feeder_fn(dashboard, METRICS_ACK)({"seq": mod + 1, "reason": "tick"}, {"mode": "full"}, None, [{"epoch": 1}])
        assert data is dash.no_update and ack == {"seq": mod + 1} and not calls

    def test_a_mode_change_fetches_at_once(self, dashboard, monkeypatch):
        seen = []
        resp = MagicMock(ok=True)
        resp.json.return_value = [{"epoch": 1}]
        monkeypatch.setattr(dm.requests, "get", lambda url, **k: seen.append(url) or resp)
        mod = DashboardConstants.FULL_HISTORY_POLL_TICK_MODULUS
        _feeder_fn(dashboard, METRICS_ACK)({"seq": mod + 1, "reason": "extra"}, {"mode": "full"}, None, None)
        assert seen and "limit=0" in seen[0]


# ---------------------------------------------------------------------------------------------
# PACER RULE and TEN IDLE MINUTES, under node, on the registered JavaScript
# ---------------------------------------------------------------------------------------------
_HARNESS = r"""
let NOW = 0;
Date.now = function () { return NOW; };
global.window = { dash_clientside: { no_update: "__NO_UPDATE__" } };
const pacerMetrics = (__METRICS__);
const pacerStatus = (__STATUS__);
const STALE = __STALE__;
const input = JSON.parse(process.argv[2]);

function runCases(cases) {
    return cases.map(function (c) {
        NOW = c.now;
        if (c.reset) { delete window.__junPollPacerFirstSeen; }
        return c.extra === undefined ? pacerStatus(c.n, c.req, c.ack) : pacerMetrics(c.n, c.extra, c.req, c.ack);
    });
}

// A healthy lane for `minutes`: the Interval ticks every 1000 ms; the feeder answers each
// request after a round trip drawn from `rtts` (ms, cycled). `mode` "pacer" runs the
// registered pacer; "guard" models canopy#613's running= guard + 5 s strand watchdog.
function simulate(mode, minutes, rtts, watchdogPhase) {
    const end = minutes * 60000;
    let req = { seq: 0 }, ack = null, inFlight = null, rttIdx = 0;
    let issuedWhileInFlight = 0, stale = 0, requests = 0, falseFires = 0;
    let disabled = true, disabledSince = null, nextTick = 1000, nextSample = watchdogPhase;
    // mount: the feeder's seq-0 call is in flight from t=0
    inFlight = { seq: 0, landsAt: rtts[rttIdx++ % rtts.length] };
    delete window.__junPollPacerFirstSeen;
    for (NOW = 0; NOW <= end; NOW += 10) {
        if (inFlight && NOW >= inFlight.landsAt) {
            ack = { seq: inFlight.seq };
            inFlight = null;
            if (mode === "guard") { disabled = false; nextTick = NOW + 1000; }
        }
        if (mode === "guard" && NOW >= nextSample) {
            nextSample += 5000;
            if (!disabled) { disabledSince = null; }
            else if (disabledSince === null) { disabledSince = NOW; }
            else if (NOW - disabledSince >= STALE) {
                disabledSince = null;
                if (inFlight) { falseFires++; }
                disabled = false; nextTick = NOW + 1000;
            }
        }
        if (NOW >= nextTick && (mode === "pacer" || !disabled)) {
            nextTick += 1000;
            if (mode === "pacer") {
                const out = pacerStatus(Math.floor(NOW / 1000), req, ack);
                if (out !== "__NO_UPDATE__") {
                    if (inFlight) { issuedWhileInFlight++; }
                    if (out.reason === "stale") { stale++; }
                    req = out; requests++;
                    inFlight = { seq: out.seq, landsAt: NOW + rtts[rttIdx++ % rtts.length] };
                }
            } else {
                if (inFlight) { issuedWhileInFlight++; }
                requests++; disabled = true;
                inFlight = { seq: requests, landsAt: NOW + rtts[rttIdx++ % rtts.length] };
            }
        }
    }
    return { issuedWhileInFlight: issuedWhileInFlight, stale: stale, requests: requests, falseFires: falseFires };
}

if (input.cases) { console.log(JSON.stringify(runCases(input.cases))); }
else { console.log(JSON.stringify(simulate(input.mode, input.minutes, input.rtts, input.watchdogPhase || 0))); }
"""


def _run_node(tmp_path, payload):
    stale = DashboardConstants.POLL_PACER_STALE_MS
    src = _HARNESS.replace("__METRICS__", poll_pacer_js(METRICS_LANE, stale, extra_input=True)).replace("__STATUS__", poll_pacer_js(FAST_LANE, stale, extra_input=False)).replace("__STALE__", str(stale))
    driver = tmp_path / "pacer.js"
    driver.write_text(src, encoding="utf-8")
    proc = subprocess.run([NODE, str(driver), json.dumps(payload)], capture_output=True, text=True, timeout=120, check=False)  # nosec B603 - fixed interpreter, test-authored script
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


@pytest.mark.unit
@pytest.mark.skipif(NODE is None, reason="node is not installed; the wiring and feeder tests above still run")
class TestPacerRule:
    STALE = DashboardConstants.POLL_PACER_STALE_MS
    WIN = {"mode": "window", "window_size": 100}
    FULL = {"mode": "full"}
    WIN_KEY = json.dumps(WIN, separators=(",", ":"))

    def _one(self, tmp_path, **case):
        return _run_node(tmp_path, {"cases": [case]})[0]

    def test_asks_when_acknowledged(self, tmp_path):
        out = self._one(tmp_path, now=50000, n=9, req={"seq": 4, "issued_at": 49000}, ack={"seq": 4})
        assert out == {"seq": 5, "issued_at": 50000, "reason": "tick", "extra_key": None}

    def test_waits_while_unacknowledged_and_young(self, tmp_path):
        assert self._one(tmp_path, now=50000, n=9, req={"seq": 4, "issued_at": 50000 - self.STALE + 1}, ack={"seq": 3}) == NU

    def test_reissues_once_the_request_is_stale(self, tmp_path):
        out = self._one(tmp_path, now=50000, n=9, req={"seq": 4, "issued_at": 50000 - self.STALE}, ack={"seq": 3})
        assert out["seq"] == 5 and out["reason"] == "stale"

    def test_a_late_ack_of_an_older_request_does_not_count(self, tmp_path):
        """An evicted request's late response must not release the pacer (F-058's chain)."""
        assert self._one(tmp_path, now=50000, n=9, req={"seq": 6, "issued_at": 49500}, ack={"seq": 5}) == NU

    def test_no_ack_at_all_waits(self, tmp_path):
        assert self._one(tmp_path, now=50000, n=9, req={"seq": 1, "issued_at": 49500}, ack=None) == NU

    def test_a_display_mode_change_is_read_from_its_value(self, tmp_path):
        out = self._one(tmp_path, now=50000, n=9, extra=self.FULL, req={"seq": 4, "issued_at": 49000, "extra_key": self.WIN_KEY}, ack={"seq": 4})
        assert out["reason"] == "extra" and out["extra_key"] == json.dumps(self.FULL, separators=(",", ":"))

    def test_an_unchanged_display_mode_is_a_tick(self, tmp_path):
        out = self._one(tmp_path, now=50000, n=9, extra=self.WIN, req={"seq": 4, "issued_at": 49000, "extra_key": self.WIN_KEY}, ack={"seq": 4})
        assert out["reason"] == "tick" and out["extra_key"] == self.WIN_KEY

    def test_a_display_mode_change_mid_flight_waits_for_the_ack(self, tmp_path):
        """F-CANOPY-058's second-Input trigger: it used to evict the fetch in flight."""
        assert self._one(tmp_path, now=50000, n=9, extra=self.FULL, req={"seq": 4, "issued_at": 49500, "extra_key": self.WIN_KEY}, ack={"seq": 3}) == NU

    def test_the_mount_request_ages_from_first_sight(self, tmp_path):
        req = {"seq": 0}
        got = _run_node(
            tmp_path,
            {
                "cases": [
                    {"now": 1000, "n": 1, "req": req, "ack": None, "reset": True},
                    {"now": 1000 + self.STALE - 1, "n": 2, "req": req, "ack": None},
                    {"now": 1000 + self.STALE, "n": 3, "req": req, "ack": None},
                ]
            },
        )
        assert got[0] == NU and got[1] == NU and got[2]["reason"] == "stale" and got[2]["seq"] == 1

    def test_the_mount_ack_releases_the_first_tick(self, tmp_path):
        out = self._one(tmp_path, now=1000, n=1, req={"seq": 0}, ack={"seq": 0}, reset=True)
        assert out["seq"] == 1 and out["reason"] == "tick"


@pytest.mark.unit
@pytest.mark.skipif(NODE is None, reason="node is not installed; the wiring and feeder tests above still run")
class TestTenIdleMinutes:
    """A healthy lane whose cycle is near the old watchdog's 5 s sampling period.

    Round trips are drawn from Phase 11's measured in-flight range (888 ms to 5,345 ms,
    median ~2.8 s), seeded, so the cycle (round trip plus up to one 1 s tick) sits near 5 s
    as it did on canopy ``main``.
    """

    @staticmethod
    def _rtts(seed, centre):
        rng = random.Random(seed)
        return [int(min(5345, max(888, rng.gauss(centre, 450)))) for _ in range(400)]

    @pytest.mark.parametrize("seed", [1, 2, 3])
    def test_no_request_is_made_in_flight_and_nothing_goes_stale(self, tmp_path, seed):
        got = _run_node(tmp_path, {"mode": "pacer", "minutes": 10, "rtts": self._rtts(seed, 3600)})
        assert got["issuedWhileInFlight"] == 0, got
        assert got["stale"] == 0, got
        assert got["requests"] > 100, got  # the lane kept polling: ~10 min / ~4.6 s

    def test_the_simulation_can_fail(self, tmp_path):
        """Non-vacuity: canopy#613's guard and watchdog, simulated on the same lane, fire
        falsely and request in flight, as Phase 11 measured on canopy ``main``."""
        worst = max(
            (_run_node(tmp_path, {"mode": "guard", "minutes": 10, "rtts": self._rtts(seed, 3600), "watchdogPhase": phase}) for seed in (1, 2, 3) for phase in (0, 1700, 3400)),
            key=lambda r: r["falseFires"],
        )
        assert worst["falseFires"] > 0 and worst["issuedWhileInFlight"] > 0, worst
