"""CAN-019: walk-through tutorial step configuration.

Each step is a dict with a stable schema the JS asset
(``frontend/assets/tutorial_walkthrough.js``) consumes directly. Keeping the
list in Python rather than embedding it in JS lets us:

- Reuse strings from ``CONTROL_TOOLTIPS`` for parameter-input descriptions
  (single source of truth, CAN-017 alignment).
- Add Python-side tests that the targets actually exist in the dashboard
  layout source (catches drift when an ID gets renamed).

Step schema (every key required):

- ``target``: DOM element ID to highlight. Use ``"__center__"`` to render
  the step centered on the screen with no spotlight (used for the welcome
  step that has no specific UI to point at).
- ``title``: short heading shown bolded in the tooltip card.
- ``body``: 1-2 sentence description. Rendered as plain text — HTML is
  intentionally not supported (avoids markup-injection footguns).
- ``placement``: one of ``"top"``, ``"bottom"``, ``"left"``, ``"right"``,
  ``"center"``. The JS picks a safe fallback when the requested side
  doesn't fit on screen.

To add a step: append to ``WALKTHROUGH_STEPS``. To rename a target ID:
update both this file AND the layout. The wiring test in
``test_walkthrough.py`` will fail loudly if a target no longer exists.
"""

from typing import Any, Dict, List

WALKTHROUGH_STEPS: List[Dict[str, Any]] = [
    {
        "target": "__center__",
        "title": "Welcome to Juniper Canopy",
        "body": ("This is a guided tour of the dashboard. Each step highlights " "one part of the UI and explains what it does. You can skip at " "any time and re-launch from the Tutorial tab."),
        "placement": "center",
    },
    {
        "target": "visualization-tabs",
        "title": "Visualization tabs",
        "body": ("Switch between Training Metrics, Network Topology, Decision " "Boundaries, Dataset, Snapshots, Parameters, and this Tutorial. " "Active tab persists across page reloads."),
        "placement": "bottom",
    },
    {
        "target": "dataset-plotter-generate-btn",
        "title": "Generate or import a dataset",
        "body": ("Open the dataset modal to generate a synthetic spiral, upload " "a CSV file, or fetch one from a URL. The dataset reset stops " "any running training and clears metrics history."),
        "placement": "left",
    },
    {
        "target": "apply-params-button",
        "title": "Configure parameters and apply",
        "body": ("Tune learning rate, candidate pool size, max iterations, and " "more in the sidebar. Apply commits the values to the backend " "for the next training cycle."),
        "placement": "right",
    },
    {
        "target": "start-button",
        "title": "Start training",
        "body": ("Begins a training run with the current parameters. The cascade " "grows automatically as candidates pass the correlation threshold."),
        "placement": "right",
    },
    {
        "target": "ws-connection-indicator",
        "title": "Connection status",
        "body": ("Real-time WebSocket health: green=connected, yellow=reconnecting, " "red=offline. When green, the dashboard receives metrics and " "topology pushes from cascor without polling."),
        "placement": "bottom",
    },
    {
        "target": "network-visualizer-depth-slider-container",
        "title": "Network depth filter",
        "body": ("Once training has added hidden units, this slider filters the " "network view to show only the first K cascade layers — useful " "for reading deep networks one level at a time."),
        "placement": "top",
    },
    {
        "target": "tutorial-panel",
        "title": "Read the full reference",
        "body": ("The Tutorial tab has the algorithm overview, parameter " "reference, and tips. Right-click most controls for a context " "menu that jumps directly to the relevant section."),
        "placement": "top",
    },
]


def get_walkthrough_steps() -> List[Dict[str, Any]]:
    """Return a copy of the walkthrough step list (defensive — callers
    sometimes serialize to JSON and we don't want them mutating the
    module-level constant)."""
    return [dict(step) for step in WALKTHROUGH_STEPS]
