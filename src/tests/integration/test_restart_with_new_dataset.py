"""Regression — the cold-swap "Stop & Restart with new dataset" button.

Guards the *behavioral* half of the orphan-button fix (the wiring half is guarded
by the L1 control-graph lint + the ``KNOWN_ORPHANS`` trim in
``tests/unit/test_control_graph_lint.py``).

The ``restart-with-new-dataset-button`` callback issues
``POST /api/train/start?reset=true``. The real cascor backend clears its
``pending_dataset`` on ``start_training(reset=True)`` (the cold swap completes),
and ``DemoMode.start(reset=True)`` must mirror that — otherwise
``reconcile_pending_dataset_banner`` (dashboard_manager.py:3588) reads a still-set
``pending_dataset`` off ``/api/status`` on the next poll and re-opens the banner,
so the button would *look* wired but never actually dismiss the banner.

``pending_dataset`` going ``None`` on ``/api/status`` is precisely the signal the
reconcile callback uses to close the banner, so asserting it here proves the
user-visible outcome without a browser.
"""

from __future__ import annotations

import pytest


@pytest.mark.integration
def test_restart_with_new_dataset_clears_pending(client):
    """Stage a dataset, cold-swap restart, and assert pending_dataset clears."""
    # Stage a dataset change — drives pending_dataset truthy (banner opens).
    staged = client.post(
        "/api/stage_dataset",
        json={"nn_dataset_type": "xor", "nn_dataset_elements": 300},
    )
    assert staged.status_code == 200, staged.text
    assert client.get("/api/status").json().get("pending_dataset"), "precondition: pending_dataset should be set after staging a dataset change"

    # Cold-swap restart — the exact request the restart button's callback issues.
    restarted = client.post("/api/train/start?reset=true")
    assert restarted.status_code == 200, restarted.text
    assert restarted.json().get("status") == "started"

    # Demo parity: start(reset=True) consumed the staged config, so the status
    # surface (and therefore reconcile_pending_dataset_banner) sees no pending
    # change and the banner stays closed.
    assert client.get("/api/status").json().get("pending_dataset") is None, "regression: pending_dataset must clear after cold-swap restart, else the banner re-opens on the next poll"

    # Cleanup — don't leak the demo training thread into sibling modules.
    client.post("/api/train/stop")
