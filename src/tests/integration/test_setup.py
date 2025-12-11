#!/usr/bin/env python3
"""
Simple test script to verify Juniper Canopy setup
"""

import sys
from datetime import datetime


def test_imports():
    """Test that all required packages can be imported."""
    print("Testing package imports...")
    # Core required packages
    required_packages = ["dash", "fastapi", "plotly", "torch", "numpy", "yaml", "colorama", "psutil"]
    # Optional packages (not always installed)
    optional_packages = ["redis", "pandas"]

    for package in required_packages:  # sourcery skip: no-loop-in-tests
        try:
            __import__(package)
            print(f"  ✓ {package}")
        except ImportError as e:
            print(f"  ✗ {package}: {e}")
            raise AssertionError(f"Failed to import {package}: {e}") from e

    for package in optional_packages:  # sourcery skip: no-loop-in-tests
        try:
            __import__(package)
            print(f"  ✓ {package} (optional)")
        except ImportError:
            print(f"  ⊘ {package} (optional, not installed)")


def test_logging():
    """Test the logging framework."""
    print("\nTesting logging framework...")
    try:
        _validate_logging_framework()
    except Exception as e:
        print(f"  ✗ Logging framework error: {e}")
        raise AssertionError(f"Logging framework error: {e}") from e


def _validate_logging_framework():
    import sys
    from pathlib import Path

    # Add src to path if not already there
    src_path = Path(__file__).parent.parent.parent
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

    from logger.logger import get_system_logger, get_training_logger

    system_logger = get_system_logger()
    training_logger = get_training_logger()

    system_logger.info("System logger test message")
    training_logger.info("Training logger test message")

    print("  ✓ Logging framework functional")


def test_directories():
    """Test that required directories exist."""
    from pathlib import Path

    print("\nTesting directory structure...")
    # Get project root (3 levels up from test file)
    project_root = Path(__file__).parent.parent.parent.parent
    # required_dirs = ["conf", "notes", "src", "data", "logs", "images", "util"]
    # TODO: remove data di?r.  and logs?  fix this by eliminating most?
    # required_dirs = ["conf", "data", "docs", "images", "logs", "notes", "reports", "src", "util"]
    required_dirs = ["conf", "docs", "logs", "reports", "src", "util"]
    for dir_name in required_dirs:  # sourcery skip: no-loop-in-tests
        dir_path = project_root / dir_name
        if dir_path.exists():  # sourcery skip: no-conditionals-in-tests
            print(f"  ✓ {dir_name}/")
        else:
            print(f"  ✗ {dir_name}/ (missing)")
            raise AssertionError(f"{dir_name}/ missing")


def main():
    print("=" * 50)
    print("Juniper Canopy Setup Verification")
    print("=" * 50)
    print(f"Python version: {sys.version}")
    print(f"Test time: {datetime.now()}")
    print()

    tests = [
        ("Package imports", test_imports),
        ("Directory structure", test_directories),
        ("Logging framework", test_logging),
    ]

    passed = 0
    # for test_name, test_func in tests:
    for _, test_func in tests:
        if test_func():
            passed += 1

    print("\n" + "=" * 50)
    print(f"Tests passed: {passed}/{len(tests)}")

    if passed == len(tests):
        print("🎉 Setup verification completed successfully!")
        print("\nNext steps:")
        print("1. Activate environment: conda activate JuniperPython")
        print("2. Start development: python -m src.main")
    else:
        print("❌ Some tests failed. Please check the setup.")
        sys.exit(1)


if __name__ == "__main__":
    main()
