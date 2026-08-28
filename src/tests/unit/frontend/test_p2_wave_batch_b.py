#!/usr/bin/env python
"""P2 fix wave, batch B — F-CANOPY-018 / -028, and the F-CANOPY-032 contract pin.

Ledger: juniper-ml notes/JUNIPER_2026-08-09_JUNIPER-CANOPY_E2E-VALIDATION-EVIDENCE.md

Both fixes here are the same class as batch A's, one level up: **a writer asserts
state it does not actually have.** The dirty-tracker compares a key the apply payload
can never carry; the pin writer reports "not pinned" for every checkbox it cannot see.

F-CANOPY-032 gets a contract pin rather than a fix — see its class docstring.
"""

import sys
from pathlib import Path

import dash
import pytest

_SRC = Path(__file__).resolve().parents[3]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from frontend.components.worker_panel import WorkerPanel  # noqa: E402
from frontend.dashboard_manager import DashboardManager  # noqa: E402


@pytest.fixture(scope="module")
def dm():
    return DashboardManager({})


# ----------------------------------------------------------------------------------
# F-CANOPY-018 — the apply toast is always overwritten ~900 ms later
# ----------------------------------------------------------------------------------


@pytest.mark.unit
class TestF018ApplyToastSurvives:
    """The toast rendered, then was replaced by "⚠️ Unsaved changes" ~900 ms later,
    and the form never returned to clean until a page reload.

    Root cause is not "two writers" — the tracker's clean path already returns
    ``no_update`` and leaves the toast alone. It is that the form never COMPARES
    clean after an apply: ``cn_training_complete`` sits in the dirty-comparison set,
    but #2b dropped it from the /api/set_params payload, so the store the apply
    writes has no such key. ``applied.get("cn_training_complete")`` is then ``None``
    against a real radio value and the dirty check latches True for the session.

    The MOUNT seed does carry the key, which is exactly why the form is clean on load
    and permanently dirty after the first apply.
    """

    # The applied-params-store shape as _apply_parameters_handler writes it: the
    # params payload, which deliberately has no cn_training_complete key.
    APPLIED = {
        "nn_max_iterations": 10,
        "nn_max_total_epochs": 1000,
        "nn_learning_rate": 0.1,
        "nn_max_hidden_units": 8,
        "nn_multi_node_layers": False,
        "nn_growth_trigger": "preset",
        "nn_growth_preset_epochs": 100,
        "nn_growth_convergence_threshold": 0.01,
        "nn_patience": 5,
        "nn_spiral_rotations": 2.0,
        "nn_spiral_number": 2,
        "cn_pool_size": 8,
        "cn_correlation_threshold": 0.4,
        "cn_selected_candidates": 1,
        "cn_training_iterations": 50,
        "cn_training_convergence_threshold": 0.01,
        "cn_patience": 5,
        "cn_multi_candidate": False,
        "cn_candidate_selection": "top",
        "cn_top_candidates": 1,
        "cn_random_candidates": 0,
        "nn_output_epochs": 100,
        "nn_optimizer_type": "adam",
        "nn_activation_function_name": "Tanh",
        "nn_init_output_weights": "zeros",
    }

    def _invoke(self, dm, *, cn_training_complete):
        """Call the tracker with a form that exactly matches APPLIED."""
        return dm._track_param_changes_handler(
            10,  # nn_max_iter
            1000,  # nn_max_epochs
            0.1,  # nn_lr
            8,  # nn_max_hu
            [],  # nn_multi_node (unchecked)
            "preset",  # nn_growth_trigger
            100,  # nn_growth_epochs
            0.01,  # nn_growth_conv_thresh
            5,  # nn_patience
            2.0,  # nn_spiral_rot
            2,  # nn_spiral_num
            200,  # nn_dataset_elem
            0.1,  # nn_dataset_noise
            8,  # cn_pool_size
            0.4,  # cn_corr_thresh
            1,  # cn_selected
            cn_training_complete,  # cn_training_complete (read-only status radio)
            50,  # cn_training_iter
            0.01,  # cn_training_conv_thresh
            5,  # cn_patience
            [],  # cn_multi_cand (unchecked)
            "top",  # cn_cand_selection
            1,  # cn_top_cands
            0,  # cn_random_cands
            100,  # nn_output_epochs
            "adam",  # nn_optimizer_type
            "Tanh",  # nn_activation_function
            self.APPLIED,  # applied-params-store (positional, ahead of the kwarg below)
            nn_init_output_weights="zeros",
        )

    def test_form_is_clean_after_an_apply(self, dm):
        """THE regression: an unchanged form against a just-applied store is clean."""
        disabled, status = self._invoke(dm, cn_training_complete="converged")
        assert disabled is True, "Apply is still enabled against a store that matches the form"
        assert status is dash.no_update, "the tracker overwrote the apply toast — F-CANOPY-018"

    def test_the_read_only_radio_never_makes_the_form_dirty(self, dm):
        """A key that can never be applied can never be unsaved.

        Whatever the status radio reads — including values the store has never seen —
        it must not dirty the form, because Apply cannot send it.
        """
        for value in ("converged", "max_iterations", "in_progress", None):
            disabled, status = self._invoke(dm, cn_training_complete=value)
            assert disabled is True, f"cn_training_complete={value!r} dirtied the form"
            assert status is dash.no_update

    def test_a_real_edit_still_dirties_the_form(self, dm):
        """Forward guard: the fix must not blunt genuine change detection."""
        result = dm._track_param_changes_handler(
            *[
                999,  # nn_max_iter -- CHANGED
                1000,
                0.1,
                8,
                [],
                "preset",
                100,
                0.01,
                5,
                2.0,
                2,
                200,
                0.1,
                8,
                0.4,
                1,
                "converged",
                50,
                0.01,
                5,
                [],
                "top",
                1,
                0,
                100,
                "adam",
                "Tanh",
                self.APPLIED,
            ],
            nn_init_output_weights="zeros",
        )
        assert result[0] is False, "a changed field no longer enables Apply"
        assert result[1] == "⚠️ Unsaved changes"

    def test_comparison_keys_are_all_keys_the_apply_can_write(self, dm):
        """Class-level pin, so the next dropped key cannot re-create this.

        Every key the dirty-tracker compares must be a key ``_apply_parameters_handler``
        actually puts in the store. A key it compares but never writes latches the form
        dirty forever, which is exactly F-CANOPY-018.
        """
        import inspect
        import re

        src = inspect.getsource(DashboardManager._track_param_changes_handler)
        compared = set(re.findall(r'^\s*\(\s*\w+\s*,\s*"([a-z0-9_]+)"\s*,\s*"(?:int|str|float|bool_checkbox)"\s*\)', src, re.M))
        assert compared, "the comparison table could not be parsed — this pin is vacuous, fix the regex"

        apply_src = inspect.getsource(DashboardManager._apply_parameters_handler)
        written = set(re.findall(r'^\s*"([a-z0-9_]+)"\s*:', apply_src, re.M))
        assert written, "the params payload could not be parsed — this pin is vacuous, fix the regex"

        orphans = sorted(compared - written)
        assert not orphans, f"dirty-tracker compares key(s) the apply payload never writes, so the form can never return to clean: {orphans}"


# ----------------------------------------------------------------------------------
# F-CANOPY-028 — pinned params silently discarded on the first pin after any reload
# ----------------------------------------------------------------------------------


@pytest.mark.unit
class TestF028PinnedParamsPreserved:
    """The pattern-matched writer rebuilt the whole list from the DOM, so it asserted
    "not pinned" for every key whose checkbox it could not see — and the next toggle
    persisted that under-report.
    """

    @staticmethod
    def _ids(*keys):
        return [{"type": "param-pin", "key": k} for k in keys]

    def test_unrendered_pins_are_preserved(self, dm):
        """THE regression: pinning a NEW key must not drop a key that is off-screen."""
        result = dm._merge_pinned_params([True], self._ids("max_iterations"), ["learning_rate"])
        assert "learning_rate" in result, "a pin whose checkbox was not rendered was silently discarded"
        assert "max_iterations" in result

    def test_no_checkboxes_rendered_is_never_a_wipe(self, dm):
        """An empty component set is not evidence that nothing is pinned."""
        assert dm._merge_pinned_params([], [], ["learning_rate", "patience"]) is dash.no_update
        assert dm._merge_pinned_params(None, None, ["learning_rate"]) is dash.no_update

    def test_unpinning_a_rendered_key_still_works(self, dm):
        """Forward guard: preserving the unseen must not make pins un-removable."""
        result = dm._merge_pinned_params([False, True], self._ids("learning_rate", "patience"), ["learning_rate", "patience"])
        assert result == ["patience"]

    def test_rendered_state_wins_over_the_stored_value(self, dm):
        """A rendered checkbox is authoritative for its own key, checked or not."""
        assert dm._merge_pinned_params([False], self._ids("a"), ["a"]) == []
        assert dm._merge_pinned_params([True], self._ids("a"), []) == ["a"]

    def test_order_is_stable(self, dm):
        """Unseen keys first, then render order — the sidebar must not reshuffle."""
        result = dm._merge_pinned_params([True, True], self._ids("b", "c"), ["a", "b"])
        assert result == ["a", "b", "c"]

    def test_empty_and_malformed_ids_do_not_crash(self, dm):
        assert dm._merge_pinned_params([True], [None], ["x"]) is dash.no_update
        assert dm._merge_pinned_params([True], [{"type": "param-pin"}], ["x"]) is dash.no_update


# ----------------------------------------------------------------------------------
# F-CANOPY-032 — contract pin only; see below
# ----------------------------------------------------------------------------------


@pytest.mark.unit
class TestF032WorkerDegradedAlertContract:
    """**No fix here — the finding's mechanism does not reproduce from source.**

    F-CANOPY-032 reports that the "Worker data degraded" alert never renders even
    though canopy's own API reports the error. Traced end to end, the path is correct:

    - ``GET /api/v1/workers/list`` returns the error dict at HTTP **200** on the
      upstream-failure branch (``main.py``), so the dashboard's ``resp.ok``
      empty-guard does NOT discard it;
    - ``_update_workers_store_handler`` threads ``"error": list_data.get("error")``
      into the store payload;
    - ``_render_from_store`` builds the ``dbc.Alert`` whenever that key is truthy.

    So this is most likely another instance of the filled-store / dead-render class
    (F-CANOPY-027, since FIXED) — which the finding itself allows for, noting the
    store fill "was not separately instrumented here". It needs a live re-drive to
    confirm or re-diagnose, not a speculative patch.

    One correction worth recording: of the finding's two test arms, the
    **control-WS-only outage** arm should not have counted as a failure. With cascor's
    HTTP up, ``list_workers()`` succeeds and the route returns no ``error`` key at all,
    so no alert is the correct behaviour there; "NO WORKERS" then just means no workers
    are registered.

    These tests pin the render contract so the path cannot silently rot before that
    re-drive happens.
    """

    def test_an_upstream_error_renders_the_alert(self):
        outputs = WorkerPanel._render_from_store({"workers": [], "count": 0, "local_reported": False, "error": "Upstream error", "stats": {}})
        error_children = outputs[2]
        assert error_children is not None, "the store carried an upstream error and the panel rendered no alert"
        assert "Worker data degraded" in str(error_children)
        assert "Upstream error" in str(error_children)

    def test_no_error_renders_no_alert(self):
        outputs = WorkerPanel._render_from_store({"workers": [], "count": 0, "local_reported": False, "error": None, "stats": {}})
        assert outputs[2] is None

    def test_the_store_handler_threads_the_error_key(self):
        """The half between the route and the render — pinned by source, since
        exercising it needs a live upstream."""
        import inspect

        src = inspect.getsource(DashboardManager._update_workers_store_handler)
        assert '"error": list_data.get("error")' in src, "the workers store no longer carries the upstream error to the panel"

    def test_the_route_reports_the_error_without_a_non_ok_status(self):
        """The guard-vs-signal interaction: the dashboard's ``resp.ok`` empty-guard
        would throw the degraded payload away if this branch ever became a 5xx."""
        import inspect

        import main

        src = inspect.getsource(main.get_worker_list)
        assert '"error": "Upstream error"' in src
        assert "raise HTTPException" not in src, "the worker-list upstream-failure branch now raises; the dashboard's resp.ok guard will discard the error payload and the degraded alert will never render"
