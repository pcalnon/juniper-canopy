#!/usr/bin/env python
"""Quick test to see if dashboard initializes without errors."""
import sys

sys.path.insert(0, "src")

try:
    from frontend.dashboard_manager import DashboardManager

    config = {
        "metrics_panel": {},
        "network_visualizer": {},
        "dataset_plotter": {},
        "decision_boundary": {},
    }
    dashboard = DashboardManager(config)
    print("✓ Dashboard initialized successfully")
    print(f"✓ Number of components: {len(dashboard.components)}")
    print(f"✓ Component IDs: {[c.get_component_id() for c in dashboard.components]}")
except Exception as e:
    print(f"✗ Dashboard initialization failed: {e}")
    import traceback

    traceback.print_exc()
