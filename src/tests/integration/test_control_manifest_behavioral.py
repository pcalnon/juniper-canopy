"""Harness L2 — control-manifest behavioral driver.

Exercises every :class:`ControlContract` row (``tests/ui_contract/control_manifest.py``)
in-process against ``main.app`` (demo mode, forced by conftest) and asserts the
declared backend post-condition. Complements L1 (``util/ui_control_graph.py``):
L1 proves each control is wired to *some* callback; L2 proves the endpoint that
callback drives actually behaves.

Adding a control = add one row to the manifest; it is then exercised here
automatically.
"""

from __future__ import annotations

import os
import sys

import pytest

_UICONTRACT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ui_contract"))
if _UICONTRACT not in sys.path:
    sys.path.insert(0, _UICONTRACT)

from control_manifest import MANIFEST, ControlContract  # noqa: E402


@pytest.mark.integration
@pytest.mark.parametrize("contract", MANIFEST, ids=lambda c: c.control_id)
def test_control_backend_contract(client, contract: ControlContract):
    """Each manifested control's endpoint honours its declared contract."""
    resp = client.request(contract.method, contract.endpoint, json=contract.body)
    assert resp.status_code in contract.expect_status, f"{contract.control_id}: {contract.method} {contract.endpoint} -> " f"{resp.status_code} (expected {contract.expect_status})\n{resp.text[:300]}"
    if contract.resp_key is not None:
        body = resp.json()
        assert body.get(contract.resp_key) == contract.resp_equals, f"{contract.control_id}: response[{contract.resp_key!r}]=" f"{body.get(contract.resp_key)!r} != {contract.resp_equals!r}"
    if contract.state_key is not None:
        state = client.get("/api/state").json()
        assert state.get(contract.state_key) == contract.state_equals, f"{contract.control_id}: /api/state[{contract.state_key!r}]=" f"{state.get(contract.state_key)!r} != {contract.state_equals!r}"
