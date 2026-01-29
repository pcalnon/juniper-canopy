# Test Enablement Quick Reference Card

**Last Updated:** January 29, 2026  
**Version:** v0.25.0

## Environment Variables

```bash
export CASCOR_BACKEND_AVAILABLE=1  # Enable CasCor backend tests
export RUN_SERVER_TESTS=1          # Enable live server tests
export RUN_DISPLAY_TESTS=1         # Enable display tests (headless)
export ENABLE_SLOW_TESTS=1         # Enable slow tests (>1s)
```

## Common Commands

```bash
# Run all default tests (fast, no external deps)
cd src && pytest tests/

# Run only unit tests
cd src && pytest tests/ -m unit

# Run integration tests (no external deps)
cd src && pytest tests/ -m "integration and not requires_cascor and not requires_server"

# Run tests excluding slow tests
cd src && pytest tests/ -m "not slow"

# Run CasCor backend tests (requires backend)
export CASCOR_BACKEND_AVAILABLE=1
cd src && pytest tests/ -m requires_cascor

# Run server tests (requires running server)
./demo  # Terminal 1
export RUN_SERVER_TESTS=1 && cd src && pytest tests/ -m requires_server  # Terminal 2

# Run all tests including optional
export CASCOR_BACKEND_AVAILABLE=1 RUN_SERVER_TESTS=1 ENABLE_SLOW_TESTS=1
cd src && pytest tests/
```

## Test Markers

| Marker             | Description                               |
| ------------------ | ----------------------------------------- |
| `unit`             | Fast unit tests, no external dependencies |
| `integration`      | Integration tests (may use files, DB)     |
| `e2e`              | End-to-end tests (full system)            |
| `slow`             | Tests taking >1 second                    |
| `requires_cascor`  | Requires CasCor backend                   |
| `requires_server`  | Requires live server                      |
| `requires_display` | Requires display                          |
| `requires_redis`   | Requires Redis                            |

## Check Test Configuration

```bash
cd src
pytest --collect-only -q | head -20

# Shows:
# === Test Environment Configuration ===
# CasCor Backend Tests: ENABLED/DISABLED
# Live Server Tests: ENABLED/DISABLED
# Display Tests: ENABLED/DISABLED
# Slow Tests: ENABLED/DISABLED
# ========================================
```

## See Full Guide

[SELECTIVE_TEST_GUIDE.md](SELECTIVE_TEST_GUIDE.md)
