"""
Pytest early setup hook - runs before test collection and import rewriting

This file is loaded by pytest via conftest.py before any test collection begins.
It ensures src/ is in sys.path BEFORE pytest rewrites any test files.
"""

import sys
from pathlib import Path

# Add src directory to sys.path at the EARLIEST possible moment
project_root = Path(__file__).resolve().parent
src_dir = project_root / "src"

if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))
    print(f"[pytest_setup.py] Added src/ to sys.path: {src_dir}")
