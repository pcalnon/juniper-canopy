"""Declarative UI-control -> backend-contract manifest (harness L2).

Each :class:`ControlContract` row maps an interactive dashboard control to the
HTTP endpoint its callback drives and the observable post-condition. The driver
``tests/integration/test_control_manifest_behavioral.py`` parametrizes over this
list and exercises every row in-process against ``main.app`` (demo mode).

FUTURE-PROOFING: when a new control is added to the dashboard, add one row here
and it is automatically exercised end-to-end. Pair with the L1 control-graph
lint (``util/ui_control_graph.py``), which guarantees the control is also wired
to *some* callback.

This module is import-only (no pytest collection): plain dataclasses, no deps.
Verified against juniper-canopy @ c07dab8 (``src/main.py`` route + model lines
in each row's comment).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

# Sentinel distinguishing "do not check" from "check equals None".
_UNSET: Any = object()


@dataclass(frozen=True)
class ControlContract:
    """The backend contract a single UI control's callback must honour."""

    control_id: str  # Dash component id of the user-facing control
    kind: str  # button | dropdown | input | switch | upload
    method: str  # HTTP verb the callback issues
    endpoint: str  # canopy API path
    body: Optional[dict] = None  # request JSON (None = no body)
    expect_status: tuple[int, ...] = (200,)
    # Post-condition A: a key in the call's own JSON response.
    resp_key: Optional[str] = None
    resp_equals: Any = _UNSET
    # Post-condition B: a key read back from GET /api/state (the roundtrip).
    state_key: Optional[str] = None
    state_equals: Any = _UNSET
    notes: str = ""


# A distinctive learning-rate value used for the apply-params roundtrip.
_LR_PROBE = 0.0123


MANIFEST: tuple[ControlContract, ...] = (
    # ---- Parameter application (Apply Parameters button) ----
    ControlContract(
        control_id="apply-params-button",
        kind="button",
        method="POST",
        endpoint="/api/set_params",  # main.py:2878 (SetParamsRequest main.py:2831)
        body={"nn_learning_rate": _LR_PROBE},
        state_key="nn_learning_rate",  # get_state main.py:939
        state_equals=_LR_PROBE,
        notes="Apply Parameters -> set_params -> /api/state roundtrip (the proof the xfail browser test cannot do).",
    ),
    # ---- Dataset staging (Apply Dataset button) ----
    ControlContract(
        control_id="apply-dataset-button",
        kind="button",
        method="POST",
        endpoint="/api/stage_dataset",  # main.py:3041 (StageDatasetRequest main.py:3025)
        body={"nn_dataset_type": "xor", "nn_dataset_elements": 300},
        resp_key="status",
        resp_equals="success",
        notes="Apply Dataset stages a cold-swap dataset change.",
    ),
    # ---- Cancel pending dataset (Cancel pending change button) ----
    ControlContract(
        control_id="cancel-pending-dataset-button",
        kind="button",
        method="DELETE",
        endpoint="/api/cancel_pending_dataset",  # main.py:3064
        resp_key="status",
        resp_equals="success",
        notes="Cancel any staged dataset change.",
    ),
    # ---- Training control buttons ----
    ControlContract(
        control_id="start-button",
        kind="button",
        method="POST",
        endpoint="/api/train/start",  # main.py:2748
        resp_key="status",
        resp_equals="started",
    ),
    ControlContract(
        control_id="pause-button",
        kind="button",
        method="POST",
        endpoint="/api/train/pause",  # main.py:2765
        resp_key="status",
        resp_equals="paused",
    ),
    ControlContract(
        control_id="resume-button",
        kind="button",
        method="POST",
        endpoint="/api/train/resume",  # main.py:2779
        resp_key="status",
        resp_equals="running",
    ),
    ControlContract(
        control_id="stop-button",
        kind="button",
        method="POST",
        endpoint="/api/train/stop",  # main.py:2793
        resp_key="status",
        resp_equals="stopped",
    ),
    ControlContract(
        control_id="reset-button",
        kind="button",
        method="POST",
        endpoint="/api/train/reset",  # main.py:2807
        resp_key="status",
        resp_equals="reset",
    ),
    # ---- Controls wired by #366 (orphan-control completion); enrolled per #369 ----
    ControlContract(
        control_id="restart-with-new-dataset-button",
        kind="button",
        method="POST",
        endpoint="/api/train/start?reset=true",  # main.py:2766; callback sends reset as a query param (dashboard_manager.py:3645)
        resp_key="status",
        resp_equals="started",
        notes="Restart-with-new-dataset commits a staged cold-swap via POST /api/train/start?reset=true (demo clears pending_dataset + restarts). Side effect: starts the demo simulator.",
    ),
    ControlContract(
        control_id="nn-init-output-weights-dropdown",
        kind="dropdown",
        method="POST",
        endpoint="/api/set_params",  # main.py:2901 (SetParamsRequest field main.py:2875; nn_keys main.py:2932)
        body={"nn_init_output_weights": "random"},  # non-default; default is "zero" (canopy_constants.py:60-61)
        state_key="nn_init_output_weights",  # get_state main.py:938
        state_equals="random",
        notes="Output Weight Init dropdown -> apply-params State (dashboard_manager.py:3436) -> set_params -> /api/state roundtrip. Non-default probe so a dropped field can't pass.",
    ),
    ControlContract(
        control_id="dataset-plotter-dataset-selector",
        kind="dropdown",
        method="POST",
        endpoint="/api/dataset/generate",  # main.py:1128 (load_selected_dataset handler dashboard_manager.py:2947)
        body={"generator": "spiral"},  # spiral is demo-buildable locally; non-spiral generators need JuniperData (503)
        expect_status=(200,),
        notes="Dataset-plotter selector -> load-selected-btn -> load_selected_dataset State -> POST /api/dataset/generate {generator}. Response is the dataset dict (no 'status' key), so status-only assertion.",
    ),
)
