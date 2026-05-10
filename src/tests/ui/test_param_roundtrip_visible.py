"""§5.6 (Issue #1, PR-10) — apply round-trip is visible to the user.

The apply chain we ship: dashboard form → ``POST /api/set_params`` →
demo or service backend ``apply_params`` → ``/api/state`` reflects the
new value → dashboard re-reads on next ``init_params_from_backend``
tick → input values in the DOM update.

This test exercises the round-trip the **user** experiences without
relying on Playwright to drive a Dash-React input (see
``test_apply_button_flow.py``'s xfail for that harness gap). We POST
directly to ``/api/set_params``, then assert:

  1. ``/api/state`` reflects the new value within a few seconds.
  2. The dashboard's input element value updates to match (after the
     init/reload tick).

If either assertion fails, the user-visible round-trip is broken and
the PR-2 toast surfacing + PR-5 adapter map + PR-7 demo backend +
PR-8 demo nn_*-alias mirror would all need to be revisited.
"""

from __future__ import annotations

import time

import pytest
import requests


@pytest.mark.ui
def test_set_params_reflects_in_api_state_and_dashboard_input(dashboard_page, canopy_url):
    new_lr = 0.0789

    # Build a payload that satisfies SetParamsRequest's required-field
    # contract — the dashboard sends all 28 fields on Apply, so we
    # mirror that shape rather than rely on an "all-optional" surface.
    base_payload = {
        "nn_learning_rate": new_lr,
        "nn_max_hidden_units": 50,
        "nn_max_total_epochs": 1000,
        "nn_max_iterations": 10,
        "nn_growth_convergence_threshold": 0.001,
        "nn_patience": 5,
        "nn_spiral_rotations": 3.0,
        "nn_spiral_number": 2,
        "nn_dataset_elements": 200,
        "nn_dataset_noise": 0.0,
        "nn_multi_node_layers": False,
        "nn_growth_trigger": "convergence",
        "nn_growth_preset_epochs": 100,
        "cn_pool_size": 8,
        "cn_correlation_threshold": 0.5,
        "cn_selected_candidates": 1,
        "cn_training_complete": "convergence",
        "cn_training_iterations": 100,
        "cn_training_convergence_threshold": 0.001,
        "cn_patience": 5,
        "cn_multi_candidate": False,
        "cn_candidate_selection": "top",
        "cn_top_candidates": 1,
        "cn_random_candidates": 0,
        "nn_output_epochs": 100,
        "nn_optimizer_type": "Adam",
        "nn_activation_function_name": "tanh",
    }
    resp = requests.post(f"{canopy_url}/api/set_params", json=base_payload, timeout=10)
    assert resp.status_code == 200, resp.text

    # Assertion 1: /api/state reflects the new value.
    deadline = time.time() + 5
    last = None
    while time.time() < deadline:
        last = requests.get(f"{canopy_url}/api/state", timeout=2).json().get("nn_learning_rate")
        if last == pytest.approx(new_lr):
            break
        time.sleep(0.2)
    assert last == pytest.approx(new_lr), f"/api/state nn_learning_rate did not update; last={last}"

    # Assertion 2: dashboard input reflects after init reload tick. The
    # dashboard polls /api/state via params-init-interval; reload to
    # trigger a fresh init.
    dashboard_page.reload()
    # Wait for params-init-interval to fire and write backend values
    # back to inputs (the init-stable-poll the conftest uses runs here too).
    dashboard_page.wait_for_function(
        f"""() => {{
            const el = document.getElementById('nn-learning-rate-input');
            if (!el) return false;
            return Math.abs(parseFloat(el.value) - {new_lr}) < 1e-6;
        }}""",
        timeout=8_000,
    )
