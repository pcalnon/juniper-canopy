#!/usr/bin/env python3
import sys

from config_manager import get_config

print("Step 1: Imported config_manager...")

sys.path.insert(0, "src")

print("Step 2: Getting config...")
config = get_config()

print("Step 3: Success!")
print(f"Config loaded: {list(config.config.keys())}")
