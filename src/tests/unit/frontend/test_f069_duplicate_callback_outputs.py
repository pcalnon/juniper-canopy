"""F-CANOPY-069 -- no two callbacks may claim one output id.

Dash suffixes an ``allow_duplicate`` Output with ``@sha256(inputs)`` (``create_callback_id``), so two callbacks
that share an Output AND the same Inputs get the SAME id. The server registers both. dash 3's renderer validates
the served dependency list unconditionally and, on that ``Duplicate callback outputs`` error, drops the whole
callback graph: the page renders and nothing on it works. dash 4 validates only with dev tools on, runs both
members, and lets their response order decide what the shared prop ends up as. Measured 2026-10-20 on canopy
571743db: inert under dash 3.0.4, 3.2.0, 3.3.0 and 3.4.0, alive under 4.4.1 (juniper-ml
``reports/e2e-canopy-2026-09-02/item30-turing/dash_version_matrix.json``; both members POST under 4.4.1,
``reports/e2e-canopy-2026-09-02/item32-turing/pair_members.json``).

The two pairs were ``accept_live_switch`` + ``open_progress_alert_on_accept`` (Input
``live-switch-accept-button.n_clicks``) and ``execute_restart`` + ``open_restart_progress`` (Input
``restart-confirm-button.n_clicks``). Each opener existed to show a progress spinner before the slow POST
returned, which is what a callback's ``running=`` spec is for, so the openers are gone and the specs are pinned
here.

Ids are parsed EXACTLY (``..a.prop@hash...b.prop..`` for a multi-output), never by substring: several of this
arc's ids are substrings of others, and ``live-switch-outcome-alert.children`` has a second, hashed writer.
"""

from __future__ import annotations

import collections

import pytest

from frontend.dashboard_manager import DashboardManager


@pytest.fixture(scope="module")
def dashboard():
    return DashboardManager({"title": "Test Dashboard", "update_interval": 1000, "server": {"host": "localhost", "port": 8050}})


def _output_ids(raw) -> list:
    """The individual output ids of one served callback, exactly as the renderer sees them."""
    raw = str(raw)
    if raw.startswith("..") and raw.endswith(".."):
        return raw[2:-2].split("...")
    return [raw]


def _bare(output_id: str) -> str:
    """``id.prop`` without the ``@hash`` suffix."""
    return output_id.split("@", 1)[0]


def _inputs(entry) -> list:
    return [f"{i['id']}.{i['property']}" for i in entry.get("inputs", [])]


def _collisions(callback_list) -> dict:
    """``{output id: [inputs of each claimant]}`` for every id more than one callback claims."""
    owners = collections.defaultdict(list)
    for entry in callback_list:
        for out in _output_ids(entry["output"]):
            owners[out].append(_inputs(entry))
    return {out: claimants for out, claimants in owners.items() if len(claimants) > 1}


def _served(dashboard):
    """The dependency list as ``GET /dashboard/_dash-dependencies`` serves it."""
    return dashboard.app._callback_list


def _only_entry_with_exact_output(dashboard, exact_id):
    matches = [e for e in _served(dashboard) if exact_id in _output_ids(e["output"])]
    assert len(matches) == 1, f"{exact_id}: expected exactly one callback with that exact output id, found {len(matches)}"
    return matches[0]


class TestNoOutputIdIsClaimedTwice:
    def test_no_output_id_is_claimed_by_two_callbacks(self, dashboard):
        collisions = _collisions(_served(dashboard))
        assert not collisions, f"output ids claimed by more than one callback (dash 3 drops the whole graph on any): {collisions}"

    def test_callback_map_and_served_list_agree(self, dashboard):
        """The registry is keyed by the served ``output`` string; a collision in one is a collision in the other."""
        served = sorted(str(e["output"]) for e in _served(dashboard))
        assert served == sorted(dashboard.app.callback_map.keys())

    def test_the_scan_sees_a_collision_where_one_exists(self):
        """Non-vacuity: a scratch app with the shape that bit canopy -- two callbacks, one Input, one
        ``allow_duplicate`` Output each -- yields exactly one colliding id, and it carries the hash."""
        from dash import Dash, Input, Output, dcc, html

        app = Dash(__name__)
        app.layout = html.Div([html.Button(id="go"), dcc.Store(id="out"), dcc.Store(id="other")])

        @app.callback([Output("other", "data"), Output("out", "data", allow_duplicate=True)], Input("go", "n_clicks"), prevent_initial_call=True)
        def slow(n):
            return n, False

        @app.callback(Output("out", "data", allow_duplicate=True), Input("go", "n_clicks"), prevent_initial_call=True)
        def fast(n):
            return True

        collisions = _collisions(app._callback_list)
        assert len(collisions) == 1
        (collided,) = collisions
        assert _bare(collided) == "out.data" and "@" in collided
        assert collisions[collided] == [["go.n_clicks"], ["go.n_clicks"]]


class TestTheProgressAlertsAreRunningSpecs:
    """The spinner idiom: the one callback that does the work opens its alert through ``running=`` the
    moment the request leaves, and the renderer closes it when the response lands."""

    def test_live_switch_accept_opens_its_alert_and_store_through_running(self, dashboard):
        entry = _only_entry_with_exact_output(dashboard, "live-switch-outcome-alert.children")
        assert _inputs(entry) == ["live-switch-accept-button.n_clicks"]
        assert entry.get("running") == {
            "running": {"live-switch-progress-alert.is_open": True, "live-swap-in-flight-store.data": {"in_flight": True}},
            "runningOff": {"live-switch-progress-alert.is_open": False, "live-swap-in-flight-store.data": {"in_flight": False}},
        }

    def test_restart_confirm_opens_its_alert_through_running(self, dashboard):
        entry = _only_entry_with_exact_output(dashboard, "restart-outcome-alert.children")
        assert _inputs(entry) == ["restart-confirm-button.n_clicks"]
        assert entry.get("running") == {"running": {"restart-progress-alert.is_open": True}, "runningOff": {"restart-progress-alert.is_open": False}}

    @pytest.mark.parametrize("alert", ["live-switch-progress-alert.is_open", "restart-progress-alert.is_open"])
    def test_each_progress_alert_has_exactly_one_writer(self, dashboard, alert):
        writers = [e for e in _served(dashboard) if alert in {_bare(o) for o in _output_ids(e["output"])}]
        assert len(writers) == 1, f"{alert}: {len(writers)} callbacks write it; their inputs: {[_inputs(w) for w in writers]}"

    @pytest.mark.parametrize("fired", ["live-switch-accept-button.n_clicks", "restart-confirm-button.n_clicks"])
    def test_each_fired_input_runs_exactly_one_callback(self, dashboard, fired):
        listeners = [e for e in _served(dashboard) if fired in _inputs(e)]
        assert len(listeners) == 1, f"{fired}: {len(listeners)} callbacks listen; their outputs: {[_output_ids(e['output']) for e in listeners]}"
