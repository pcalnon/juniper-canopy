#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       0.5.0
# File Name:     ui_control_graph.py
# File Path:     Juniper/JuniperCanopy/juniper_canopy/util/
#
# Created Date:  2026-06-15
# Last Modified: 2026-06-15
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#     L1 of the UI regression-detection harness: a static "control-graph" lint.
#     It instantiates the Dash app in demo mode, enumerates every interactive
#     control from the realized layout tree, enumerates every callback Input/State
#     binding from ``app.callback_map``, and reports "orphan" controls — actionable
#     widgets that no callback can ever observe. This deterministically catches the
#     "dead button" regression class (e.g. ``restart-with-new-dataset-button``)
#     with no browser and no new dependencies.
#
#####################################################################################################################################################################################################
# Notes:
#     * Runtime introspection (not AST/grep) is required: some ids are built
#       dynamically from a component prefix (e.g. dataset_plotter), so the id
#       string never appears literally in source.
#     * Rule (bifurcated, empirically validated against canopy@c07dab8):
#         - Button / Upload  -> must appear as a callback INPUT (a trigger read
#           only as State can never fire).
#         - value-carriers (Dropdown/Select/Input/Textarea/Switch/Checkbox/
#           Checklist/RadioItems/Slider/RangeSlider) -> must appear as an INPUT
#           OR a STATE (legitimately read on a sibling's click, e.g.
#           nn-dataset-type-dropdown which is State-only by design).
#
#####################################################################################################################################################################################################
# References:
#     * notes/CANOPY_TRAINING_CONTROL_ERROR_SURFACING_DESIGN_2026-06-14.md ("dead button" class)
#     * src/tests/ui/test_apply_blur_clientside.py (precedent for walking callback_map)
#
#####################################################################################################################################################################################################
"""Static control-graph lint for the juniper-canopy Dash dashboard (harness L1)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

# Dash component types a user can act on.
ACTIONABLE: frozenset[str] = frozenset(
    {
        "Button",
        "Dropdown",
        "Select",
        "Input",
        "Textarea",
        "Switch",
        "Checkbox",
        "Checklist",
        "RadioItems",
        "Upload",
        "Slider",
        "RangeSlider",
    }
)

# Of the actionable types, the ones whose OWN interaction is the trigger: they are
# useless unless read by a callback Input. (A button read only as State, or not at
# all, can never fire.)
TRIGGER_REQUIRES_INPUT: frozenset[str] = frozenset({"Button", "Upload"})


@dataclass(frozen=True)
class Control:
    """An ided node from the realized Dash layout tree."""

    id: Any  # str, or dict for pattern-matching ids
    kind: str  # Dash component class name


@dataclass(frozen=True)
class Violation:
    """An actionable control that no callback can observe."""

    id: Any
    kind: str
    reason: str


def id_key(control_id: Any) -> Any:
    """Normalize an id for comparison.

    Pattern-matching dict ids (``{"type": ..., "index": ...}``) are collapsed to
    their ``type`` so a concrete child matches an ``ALL``/``MATCH`` wildcard
    callback. Plain string ids pass through unchanged.
    """
    if isinstance(control_id, dict):
        return ("DICT", control_id.get("type"))
    return control_id


def enumerate_controls(app: Any) -> list[Control]:
    """Walk ``app.layout`` and collect every node that carries an ``id``."""
    out: list[Control] = []

    def walk(node: Any) -> None:
        cid = getattr(node, "id", None)
        if cid is not None:
            out.append(Control(cid, type(node).__name__))
        children = getattr(node, "children", None)
        if children is None:
            return
        if isinstance(children, (list, tuple)):
            for child in children:
                walk(child)
        elif not isinstance(children, (str, int, float, bool)):
            walk(children)

    walk(app.layout)
    return out


def enumerate_bindings(app: Any) -> tuple[set[Any], set[Any]]:
    """Collect the id-keys read as callback Inputs and as callback States."""
    inputs: set[Any] = set()
    states: set[Any] = set()
    for spec in app.callback_map.values():
        for item in spec.get("inputs", []) or []:
            inputs.add(id_key(item.get("id")))
        for item in spec.get("state", []) or []:
            states.add(id_key(item.get("id")))
    return inputs, states


def lint(app: Any) -> list[Violation]:
    """Return every actionable control unreachable by any callback."""
    inputs, states = enumerate_bindings(app)
    bound = inputs | states
    violations: list[Violation] = []
    seen: set[Any] = set()
    for control in enumerate_controls(app):
        if control.kind not in ACTIONABLE:
            continue
        key = id_key(control.id)
        if key in seen:
            continue
        seen.add(key)
        if control.kind in TRIGGER_REQUIRES_INPUT:
            if key not in inputs:
                violations.append(
                    Violation(
                        control.id,
                        control.kind,
                        "trigger control bound to no callback Input — interacting with it can never fire a callback",
                    )
                )
        elif key not in bound:
            violations.append(
                Violation(
                    control.id,
                    control.kind,
                    "value-carrying control read by no callback Input or State — its value never reaches the app",
                )
            )
    return violations


def format_violations(violations: list[Violation]) -> str:
    """Render a deterministic, human-readable report."""
    if not violations:
        return "No orphan controls — every actionable control is reachable by a callback."
    lines = ["Orphan control(s) — actionable but unreachable by any callback:"]
    for violation in sorted(violations, key=lambda v: str(v.id)):
        lines.append(f"  - id={violation.id!r} kind={violation.kind}: {violation.reason}")
    return "\n".join(lines)


def build_app() -> Any:
    """Instantiate the dashboard Dash app in demo mode for offline introspection.

    Safe to call from tests (conftest already forces demo mode + mocks the data
    client) and from the ``__main__`` CLI below.
    """
    os.environ.setdefault("JUNIPER_CANOPY_DEMO_MODE", "1")
    os.environ.setdefault("JUNIPER_DATA_URL", "http://localhost:8100")
    os.environ.setdefault("JUNIPER_CANOPY_RATE_LIMIT_ENABLED", "false")
    from frontend.dashboard_manager import DashboardManager

    return DashboardManager({}).app


if __name__ == "__main__":
    import sys

    _SRC = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
    if _SRC not in sys.path:
        sys.path.insert(0, _SRC)
    _violations = lint(build_app())
    print(format_violations(_violations))
    raise SystemExit(1 if _violations else 0)
