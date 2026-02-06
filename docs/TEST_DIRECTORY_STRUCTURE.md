# Test Directory Structure

**Last Updated:** 2026-02-04
**Version:** 1.0.0

This document describes the test directory organization for JuniperCanopy.

## Directory Layout

```text
src/tests/
├── conftest.py              # Root fixtures and pytest configuration
├── data/                    # Test data files
│   └── sample_metrics.json  # Sample metrics for testing
├── fixtures/                # Shared test fixtures (deprecated - use conftest.py)
├── helpers/                 # Test utility functions
├── integration/             # Integration tests
│   ├── backend/             # Backend integration tests
│   ├── test_*.py            # API, WebSocket, config integration tests
├── mocks/                   # Mock implementations
├── performance/             # Performance and benchmark tests
├── regression/              # Regression tests for fixed bugs
├── reports/                 # Generated test reports
│   ├── coverage.xml         # Coverage report (XML)
│   └── junit/               # JUnit test results
└── unit/                    # Unit tests
    ├── backend/             # Backend unit tests
    ├── frontend/            # Frontend component unit tests
    └── test_*.py            # Other unit tests
```

## Test Categories

### Unit Tests (`tests/unit/`)

Fast tests with no external dependencies. Test individual components in isolation.

**Markers:** `@pytest.mark.unit`

**Examples:**

- `test_config_manager.py` - ConfigManager class tests
- `test_demo_mode_advanced.py` - DemoMode thread safety tests
- `frontend/test_metrics_panel.py` - MetricsPanel component tests

### Integration Tests (`tests/integration/`)

Tests that verify component interactions, file I/O, database access, or API behavior.

**Markers:** `@pytest.mark.integration`

**Examples:**

- `test_demo_endpoints.py` - API endpoints in demo mode
- `test_websocket_state.py` - WebSocket message handling
- `test_config_integration.py` - Configuration loading and validation

### Regression Tests (`tests/regression/`)

Tests that guard against previously-fixed bugs.

**Markers:** `@pytest.mark.regression`

**Examples:**

- `test_candidate_visibility.py` - Candidate phase visibility fixes

### Performance Tests (`tests/performance/`)

Benchmark and performance tests.

**Markers:** `@pytest.mark.performance`

**Examples:**

- `test_button_responsiveness.py` - UI callback latency tests

## Conditional Test Markers

Some tests require specific environments or resources:

| Marker                          | Environment Variable         | Description                  |
| ------------------------------- | ---------------------------- | ---------------------------- |
| `@pytest.mark.requires_cascor`  | `CASCOR_BACKEND_AVAILABLE=1` | Tests needing CasCor backend |
| `@pytest.mark.requires_server`  | `RUN_SERVER_TESTS=1`         | Tests needing live server    |
| `@pytest.mark.requires_redis`   | -                            | Tests needing Redis          |
| `@pytest.mark.requires_display` | `RUN_DISPLAY_TESTS=1`        | Tests needing display        |
| `@pytest.mark.slow`             | `ENABLE_SLOW_TESTS=1`        | Tests taking >1 second       |
| `@pytest.mark.e2e`              | `RUN_SERVER_TESTS=1`         | End-to-end tests             |

## Key Fixtures

Defined in `conftest.py`:

- **`client`** - FastAPI TestClient for API testing
- **`reset_singletons`** - Auto-use fixture that resets singletons between tests
- **`sample_training_metrics`** - Sample metrics data for testing
- **`sample_network_topology`** - Sample topology data for testing
- **`sample_dataset`** - Sample dataset for testing

## Running Tests

```bash
# All tests
cd src && pytest tests/ -v

# Unit tests only
pytest tests/unit/ -v

# Integration tests only
pytest tests/integration/ -v

# Specific marker
pytest -m "unit and not slow" -v

# With coverage
pytest tests/ --cov=. --cov-report=html
```

## Related Documentation

- [ADR-001: Valid Test Skips](ADR_001_VALID_TEST_SKIPS.md)
- [CLAUDE.md - Testing Section](../../CLAUDE.md#testing)
