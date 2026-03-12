"""Root conftest for juniper_canopy pytest configuration."""

import os
import sys
from pathlib import Path

# Add src/ to Python path for absolute imports
src_path = Path(__file__).parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Set demo mode for all tests
os.environ["JUNIPER_CANOPY_DEMO_MODE"] = "1"
