#!/usr/bin/env python3
import yaml

try:
    print("Loading YAML file...")
    with open("conf/app_config.yaml", "r") as f:
        data = yaml.safe_load(f)
    print(f"✅ SUCCESS! Loaded {len(str(data))} characters of config data")
    print(f"Top-level keys: {list(data.keys())}")
    # sys.exit(0)
except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback

    traceback.print_exc()
    # sys.exit(1)
