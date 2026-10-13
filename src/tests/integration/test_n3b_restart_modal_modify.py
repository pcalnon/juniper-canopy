"""N3b (canopy training-runtime defects plan, I-6 / Q3) — restart-modal granular MODIFY.

Integration-level contract for the in-place modify capability N3b adds to the N3
restart confirm modal:

1. **Layout wiring** — the editable dataset / param fields, the baseline store, and the
   context div are actually present in the built layout (so the callbacks that reference
   them by id are valid, not dangling).
2. **Field-set coherence** — every exposed param field maps to a real canopy→cascor
   ``set_params`` key AND is governed by N5's ``CascorPatchBounds`` (the guarantee that
   the modal's param apply delegates cleanly to the N5 machinery, no un-clampable field).
3. **Route acceptance (demo mode)** — the existing ``/api/stage_dataset`` and
   ``/api/set_params`` routes the modal calls accept the modal's payload shapes.

The confirm SEQUENCING (re-stage → apply → restart, abort-on-failure) is unit-pinned in
``tests/unit/frontend/test_restart_orchestration_handlers.py``.
"""

from __future__ import annotations

import pytest

from canopy_constants import CascorPatchBounds
from frontend.dashboard_manager import RESTART_MODAL_DATASET_FIELDS, RESTART_MODAL_PARAM_FIELDS, DashboardManager


def _collect_ids(component, out):
    cid = getattr(component, "id", None)
    if isinstance(cid, str):
        out.add(cid)
    children = getattr(component, "children", None)
    if children is None:
        return
    if isinstance(children, (list, tuple)):
        for child in children:
            _collect_ids(child, out)
    else:
        _collect_ids(children, out)


@pytest.fixture(scope="module")
def layout_ids():
    manager = DashboardManager({})
    ids: set[str] = set()
    _collect_ids(manager.app.layout, ids)
    return ids


# ---------------------------------------------------------------------------
# 1. Layout wiring
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestLayoutWiring:
    def test_editable_dataset_fields_present(self, layout_ids):
        for field_id, _key, _label in RESTART_MODAL_DATASET_FIELDS:
            assert field_id in layout_ids, f"missing restart-modal dataset field {field_id}"

    def test_editable_param_fields_present(self, layout_ids):
        for field_id, _key, _label in RESTART_MODAL_PARAM_FIELDS:
            assert field_id in layout_ids, f"missing restart-modal param field {field_id}"

    def test_baseline_store_and_context_present(self, layout_ids):
        assert "restart-modal-baseline" in layout_ids
        assert "restart-granular-context" in layout_ids

    def test_n3_surfaces_still_present(self, layout_ids):
        # N3b must not drop the N3 modal surfaces it builds on.
        for _id in ("restart-confirm-modal", "restart-confirm-summary", "restart-start-fresh-toggle", "restart-granular-collapse", "restart-outcome-alert", "restart-confirm-button"):
            assert _id in layout_ids


# ---------------------------------------------------------------------------
# 2. Field-set coherence (delegates cleanly to N5's machinery)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestFieldSetCoherence:
    def test_every_param_field_is_cascor_patch_bounds_governed(self):
        """Each editable param must be one N5's ``CascorPatchBounds`` can clamp —
        otherwise the modal would apply a value the N5 core can't guard."""
        for _id, key, _label in RESTART_MODAL_PARAM_FIELDS:
            assert key in CascorPatchBounds.BOUNDS, f"{key} is not governed by CascorPatchBounds"

    def test_param_keys_unique(self):
        keys = [key for _id, key, _label in RESTART_MODAL_PARAM_FIELDS]
        assert len(keys) == len(set(keys))

    def test_dataset_keys_match_stage_dataset_request(self):
        # The modal's dataset keys are exactly the StageDatasetRequest surface.
        assert {key for _id, key, _label in RESTART_MODAL_DATASET_FIELDS} == {"dataset_type", "n_samples", "noise", "rotations", "n_spirals"}


# ---------------------------------------------------------------------------
# 3. Route acceptance (demo mode — the routes the modal actually calls)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestRouteAcceptance:
    def test_stage_dataset_accepts_modal_payload(self, client):
        """The modal re-stages via /api/stage_dataset with the same payload shape
        the sidebar Apply-Dataset uses (nn_dataset_type always, numerics present)."""
        resp = client.post("/api/stage_dataset", json={"nn_dataset_type": "xor", "nn_dataset_elements": 300, "nn_dataset_noise": 0.1})
        assert resp.status_code == 200, resp.text

    def test_set_params_accepts_curated_param_subset(self, client):
        """/api/set_params accepts a partial PATCH of exactly the modal's curated
        param subset (a partial apply is valid — the modal need not send all 28)."""
        payload = {key: 0.5 if "threshold" in key or "learning_rate" in key else 4 for _id, key, _label in RESTART_MODAL_PARAM_FIELDS}
        resp = client.post("/api/set_params", json=payload)
        assert resp.status_code == 200, resp.text
