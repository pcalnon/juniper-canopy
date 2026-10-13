"""Regression — the nn-init-output-weights-dropdown wiring (the "double break").

The "Output Weight Init" dropdown (`dashboard_manager.py:880`, options zero|random)
was an orphan with TWO independent breaks:

1. Frontend: its value was never read by the apply-params callback, so it never
   reached `POST /api/set_params`.
2. Backend model: `nn_init_output_weights` was absent from `SetParamsRequest`
   (`main.py`), so even a hand-crafted POST was silently dropped at request parsing
   (Pydantic `extra="ignore"`) before the handler — whose `nn_keys` list and
   `/api/state` round-trip were already ready for it — ever saw it.

This proves the end-to-end backend contract now holds: a POSTed value survives
parse, flows through `apply_params`, is stored on the demo simulator, and is read
back from `/api/state`. The frontend-wiring half (the dropdown is now a callback
State) is guarded by the L1 control-graph lint + the `KNOWN_ORPHANS` trim.
"""

from __future__ import annotations

import pytest


@pytest.mark.integration
def test_init_output_weights_round_trips_through_set_params(client):
    """nn_init_output_weights survives SetParamsRequest and reaches /api/state, both ways."""
    # Set the NON-default option first ("random"; the default is "zero") so a pass
    # cannot be the default value leaking through a dropped field.
    resp = client.post("/api/set_params", json={"nn_init_output_weights": "random"})
    assert resp.status_code == 200, resp.text
    assert client.get("/api/state").json().get("nn_init_output_weights") == "random", "nn_init_output_weights='random' must survive parse + reach /api/state (was dropped pre-fix)"

    # And back to the default — proves /api/state actually tracks the request,
    # not a constant.
    resp = client.post("/api/set_params", json={"nn_init_output_weights": "zero"})
    assert resp.status_code == 200, resp.text
    assert client.get("/api/state").json().get("nn_init_output_weights") == "zero"
