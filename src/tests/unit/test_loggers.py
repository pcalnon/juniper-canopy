#!/usr/bin/env python3
"""Smoke test script for logger initialization — system, training, and UI loggers."""

import sys

from config_manager import get_config
from logger.logger import get_system_logger, get_training_logger, get_ui_logger

sys.path.insert(0, "src")

print("Step 1: Importing config...")
config = get_config()
print("✅ Config loaded")

print("\nStep 2: Importing loggers...")
print("✅ Logger module imported")

print("\nStep 3: Getting system logger...")
system_logger = get_system_logger()
print(f"✅ System logger: {system_logger}")

print("\nStep 4: Getting training logger...")
training_logger = get_training_logger()
print(f"✅ Training logger: {training_logger}")

print("\nStep 5: Getting UI logger...")
ui_logger = get_ui_logger()
print(f"✅ UI logger: {ui_logger}")

print("\n🎉 All loggers initialized successfully!")
