# Testing Reference

**Last Updated:** September 5, 2026  
**Version:** v0.26.3

Technical reference for the active pytest configuration, markers, fixtures, and CI-equivalent commands.

---

## Table of Contents

1. [Configuration Sources](#configuration-sources)
2. [Marker Reference](#marker-reference)
3. [Fixture Reference](#fixture-reference)
4. [Environment and Gating Variables](#environment-and-gating-variables)
5. [Command Reference](#command-reference)
6. [X7 Status Cache (slice 1c)](#x7-status-cache-slice-1c)
6. [X7 Event-Loop Discipline](#x7-event-loop-discipline)
7. [Coverage Reference](#coverage-reference)
8. [CI Mapping](#ci-mapping)
9. [Troubleshooting Reference](#troubleshooting-reference)

---

## Configuration Sources

Primary sources:

- `pyproject.toml` (`[tool.pytest.ini_options]`, `[tool.coverage.*]`)
- `src/tests/conftest.py` (runtime setup, marker skip rules, fixtures)
- `.github/workflows/ci.yml` (test commands and env defaults)

Key pytest options from `pyproject.toml`:

```toml
[tool.pytest.ini_options]
minversion = "7.0"
testpaths = ["src/tests"]
pythonpath = ["src"]
timeout = 60
timeout_method = "signal"
addopts = [
  "-ra",
  "-q",
  "--strict-markers",
  "--strict-config",
  "--continue-on-collection-errors",
  "--tb=short",
]
```

Important note:

- There is no active `pytest.ini` file in this repository; configuration lives in `pyproject.toml`.

---

## Marker Reference

Registered markers include:

- `unit`
- `integration`
- `regression`
- `performance`
- `e2e`
- `slow`
- `requires_cascor`
- `requires_server`
- `requires_display`
- `requires_redis`
- `requires_cassandra`
- `api`
- `generators`

Common selector examples:

```bash
pytest -m unit -v
pytest -m integration -v
pytest -m "not requires_cascor and not requires_server and not slow" -v
pytest -m "integration and not requires_cascor and not requires_server and not slow" -v
```

---

## Fixture Reference

Defined in `src/tests/conftest.py`:

- `event_loop` (session)
- `mock_juniper_data_client` (session, autouse)
- `client` (module)
- `preserve_metrics_layouts` (session, autouse)
- `ensure_test_data_directory` (session, autouse)
- `reset_singletons` (function, autouse)
- `cleanup_test_environment` (function, autouse)
- plus sample data/config fixtures (`test_config`, `sample_training_metrics`, `sample_network_topology`, `sample_dataset`)

Runtime setup behaviors in `conftest.py`:

- Forces `JUNIPER_CANOPY_DEMO_MODE=1`
- Sets `JUNIPER_DATA_URL=http://localhost:8100`
- Sets `CANOPY_RATE_LIMIT_ENABLED=false`
- Adds `src/` to `sys.path` and `PYTHONPATH`
- Injects stubs for `juniper_data_client` and `juniper_cascor_client` when unavailable

These defaults make most unit/integration tests runnable without external services.

---

## Environment and Gating Variables

Primary gating controls:

| Variable | Enables | Default in CI unit/integration jobs |
| --- | --- | --- |
| `CASCOR_BACKEND_AVAILABLE=1` | tests marked `requires_cascor` | `0` |
| `RUN_SERVER_TESTS=1` | tests marked `requires_server` | `0` |
| `RUN_DISPLAY_TESTS=1` | tests marked `requires_display` in headless mode | unset/`0` |
| `ENABLE_SLOW_TESTS=1` | tests marked `slow` | `0` |

Automatic library-based skipping:

- `requires_cassandra` skipped if Cassandra driver import fails
- `requires_redis` skipped if Redis library import fails

---

## Command Reference

### Fast default suite (CI-aligned)

```bash
python -m pytest \
  -m "not requires_cascor and not requires_server and not slow" \
  src/tests/unit/ src/tests/regression/ \
  --verbose
```

### Integration suite (external deps off)

```bash
python -m pytest \
  -m "integration and not requires_cascor and not requires_server and not slow" \
  src/tests/integration \
  --verbose
```

### Coverage gate equivalent

```bash
python -m pytest \
  -m "not requires_cascor and not requires_server and not slow" \
  src/tests/unit/ src/tests/regression/ \
  --cov=src \
  --cov-report=term-missing \
  --cov-report=xml:reports/coverage.xml \
  --cov-report=html:reports/htmlcov \
  --cov-fail-under=80
```

### Documentation Validation Commands

```bash
# Run the documentation link checker (CI-equivalent mode)
python scripts/check_doc_links.py \
  --exclude templates --exclude history \
  --exclude pull_requests --exclude releases \
  --exclude analysis --exclude fixes --exclude development \
  --exclude CHANGELOG.md \
  --cross-repo skip

# Run link checker with cross-repo warnings (local triage)
python scripts/check_doc_links.py --cross-repo warn

# Run full cross-repo validation (requires sibling repos checked out)
python scripts/check_doc_links.py --cross-repo check

# Run focused unit tests for link-checker hardening
pytest src/tests/unit/test_check_doc_links.py -v

# F-CANOPY-047: CSP must allow plotly PNG export without over-widening
cd src
pytest tests/regression/test_csp_plotly_image_export.py \
       tests/regression/test_csp_bootstrap_cdn.py -v
```

### Hierarchy depth filter (CAN-020 / F-CANOPY-042)

The Python oracle and the clientside label suite
(`src/tests/unit/frontend/test_f042_depth_filter_label.py`, landed with canopy#570)
both live on `main`.

```bash
cd src
pytest tests/unit/test_network_visualizer.py -k "Hierarchy or hierarchy or depth" -v
```

`TestHierarchyDepthFilter` is the contract: `None` / `0` / at-total / above-total
are `"all"`; a mid-range depth copies the dict, caps `hidden_units`, and drops
edges touching `hidden_K` for `K >= depth`. `TestHierarchyDepthSliderWiring` is
source-level only and does **not** execute the JavaScript. After #570 merges,
prefer the registered-callback + `node` grid over any test that re-types the
production expression. See
[AGENTS_REFERENCE.md § Hierarchy Depth Filter](../AGENTS_REFERENCE.md#hierarchy-depth-filter-can-020).

### Topology node selection (F-CANOPY-044 / F-CANOPY-045 / F-CANOPY-046)

On `main`, drive the real registered callback (not the
`_simulate_handle_node_selection` re-implementation):

```bash
cd src
pytest tests/unit/frontend/test_f044_node_click_selection.py -v
```

`test_f044_node_click_selection.py` is the contract for click-to-select:
edge `customdata` fallback (F-044) and label-derived layer (F-045). The
canopy#573 suite (`src/tests/unit/frontend/test_f046_clear_selection.py` — not
on `main` yet) pins the Clear button, the true hints, and
`is dash.no_update` on an already-empty store. Adding an Input/Output
changes arity; three files invoke the callback by its Output key
(`-selected-nodes.data`), including
`tests/regression/test_dark_mode_info_panels.py`. See
[AGENTS_REFERENCE.md § Topology Node Selection](../AGENTS_REFERENCE.md#topology-node-selection-f-canopy-046).

### Documentation Link Checker Edge-Case Matrix

| Test File | Focus Area | Behaviors Covered |
| ----------------------------------------- | ---------------------------------------------------- | ------------------------------------------------------------------------------- |
| `src/tests/unit/test_check_doc_links.py` | Parser correctness around markdown syntax boundaries | ignores fenced-code links, ignores inline-code links, reports missing anchors |
| `src/tests/unit/test_check_doc_links.py` | Security validation of link targets | rejects absolute paths, excessive traversal depth, null bytes |
| `src/tests/unit/test_check_doc_links.py` | Cross-repo policy and fallback behavior | skip-mode counting, check-mode resolution, target-repo escape rejection, invalid mode handling, fallback-to-skip when ecosystem root missing |

Recommended targeted invocations:

```bash
pytest src/tests/unit/test_check_doc_links.py -k "code_fences or inline_code or anchor" -v
pytest src/tests/unit/test_check_doc_links.py -k "dangerous_link_inputs or rejects_escape" -v
pytest src/tests/unit/test_check_doc_links.py -k "cross_repo or invalid_cross_repo_mode or falls_back_to_skip" -v
```

## X7 Event-Loop Discipline

X7 is canopy ceasing to answer HTTP — `/v1/health/live` included — when an upstream is
unreachable. Slice 1b (`#566`) bounds the cascor client; slice 1a (`#567`) moves remaining
sync I/O off the loop. Full runbook:
[AGENTS_REFERENCE.md § Event-loop I/O discipline](../AGENTS_REFERENCE.md#event-loop-io-discipline-x7).

```bash
# Client budget (on main) — T-B1 refused-call milliseconds; T-B2 a 503 is attempted once
cd src && pytest tests/regression/test_x7_client_budget.py -v

# Structural gate + T-A2/T-A3/T-A4 (land with #567). Do not mark these slow:
# the coverage gate runs -m "not slow" and would drop the only behavioural check.
cd src && pytest tests/regression/test_x7_off_loop_discipline.py \
  tests/regression/test_x7_loop_responsiveness.py -v

# Adapter-wide census (instrument, exit 0). Needs sibling juniper-cascor-client.
python util/ad-hoc/2026-09-04_async_blocking_callgraph.py
```

The `main.py` gate cannot see adapter/self-method I/O. A green gate after editing
`cascor_service_adapter.py` or `service_backend.py` is not "1a done". `ruff --select ASYNC`
cannot see `backend.get_status()` either.

### Debugging Commands

```bash
pytest --collect-only
pytest --markers
pytest --fixtures
pytest -ra
pytest --lf
pytest --ff
```

---

## X7 Status Cache (slice 1c)

Incoming with `#578`. Pins the classifier, the PR `#340` status-bar regression, breaker
isolation, and the staleness contract. The file is
`src/tests/regression/test_x7_status_cache.py` — backtick only until it exists on `main`.

```bash
cd src && pytest tests/regression/test_x7_status_cache.py -v
```

| Id | What it pins |
| --- | --- |
| T-C1 | Every observed shape lands in exactly one class; the table exercises all three |
| T-C2 | Half-dead 200 → "Unreachable"; the same body without `status_class` still renders "Stopped" |
| T-C3 | Five failing `get_network_data()` calls open the shared breaker and leave the status breaker closed |
| T-C4 | Stale + age on non-OK; never-OK omits `is_training`; a dead refresher ages out; peak in-flight is 1 |

Do not mark these `slow`. The coverage gate runs `-m "not slow"`. Operator runbook:
[AGENTS_REFERENCE.md — Cascor status cache](../AGENTS_REFERENCE.md#cascor-status-cache-x7-slice-1c).

---

## Coverage Reference

Coverage configuration source: `pyproject.toml`.

Key settings:

- `source = ["src"]`
- `branch = true`
- `fail_under = 80`
- `show_missing = true`
- HTML output default directory: `reports/coverage`

Common commands:

```bash
pytest --cov=src --cov-report=term-missing
pytest --cov=src --cov-report=html:reports/htmlcov
pytest --cov=src --cov-report=xml:reports/coverage.xml
```

---

## CI Mapping

From `.github/workflows/ci.yml`:

- Unit job command scope: `src/tests/unit/` + `src/tests/regression/`
- Integration job command scope: `src/tests/integration`
- Unit job timeout flag: `--timeout=60`
- Integration job timeout flag: `--timeout=120`
- Coverage gate enforced in unit job via `--cov-fail-under=${COVERAGE_FAIL_UNDER}` (`80`)

Security and docs companion checks:

- security scans in `security` job (`gitleaks`, `bandit`, `pip-audit`)
- docs link validation in `docs` job (`scripts/check_doc_links.py ...`)
- lockfile freshness in `lockfile-check`

---

## Troubleshooting Reference

Unexpected skips:

```bash
pytest -ra
```

Collection issues:

- verify editable install: `pip install -e .`
- inspect discovery and markers:

```bash
cd src
pytest tests/unit/test_response_normalization.py -k "Fix1 or Fix2 or Fix3 or Fix4 or Fix13 or DashboardMetricsContract or TopologyTransformation or DatasetTargetConversion" -v
pytest tests/unit/test_service_backend.py -k "get_status or get_dataset" -v
pytest tests/unit/frontend/test_metrics_panel_handlers.py -k "validation_overlay or replay or progress_detail or training_progress or hidden_units" -v
```

### Documentation Link Validation Regression Matrix

Use this matrix when documentation tooling or markdown link policy changes.

| Test File | Contract Focus | Key Behavior |
| ------------------------------ | ---------------------------------------------------- | ------------------------------------------------------------------------ |
| `tests/unit/test_doc_link_checker.py` | Documentation link checker regression coverage | ignores fenced/inline-code links, validates same-file anchors, rejects absolute/deep traversal paths, enforces cross-repo escape protections, verifies cross-repo skip/check modes |

Recommended command subset:

```bash
cd src
pytest tests/unit/test_doc_link_checker.py -v
python ../scripts/check_doc_links.py \
  --exclude templates --exclude history \
  --exclude pull_requests --exclude releases \
  --exclude analysis --exclude fixes --exclude development \
  --exclude CHANGELOG.md \
  --cross-repo skip
```

### CSP / Plotly PNG Export (F-CANOPY-047)

The two files pin unrelated `img-src` consumers. A green result on one is not evidence the other still works.

| Test File | Contract Focus | Key Behavior |
| --- | --- | --- |
| `tests/regression/test_csp_plotly_image_export.py` | Plotly PNG rasteriser | `img-src` allows `blob:` *and* `data:`; `blob:` is absent from `script-src` / `default-src`; no `*` / `http:`; `middleware._DEFAULT_CSP` equals `SecurityConstants.DEFAULT_CSP_POLICY` |
| `tests/regression/test_csp_bootstrap_cdn.py` | Bootstrap CDN + icons | `style-src` allows `cdn.jsdelivr.net`; `img-src` allows `data:`; CDN is not on `script-src` |

```bash
cd src
pytest tests/regression/test_csp_plotly_image_export.py \
       tests/regression/test_csp_bootstrap_cdn.py -v
```

### Testing WebSocket Endpoints

```python
from fastapi.testclient import TestClient

def test_websocket():
    """Test WebSocket connection."""
    with client.websocket_connect("/ws/training") as websocket:
        websocket.send_json({"type": "subscribe"})
        data = websocket.receive_json()
        assert data["type"] == "metrics"
```

## Performance Testing

### Timing Tests

```python
import time
import pytest

def test_performance():
    """Test execution time."""
    start = time.time()

    # Operation to test
    result = expensive_operation()

    duration = time.time() - start
    assert duration < 1.0  # Must complete in under 1 second
```

### Memory Testing

```python
import tracemalloc

def test_memory_usage():
    """Test memory consumption."""
    tracemalloc.start()

    # Operation to test
    result = memory_intensive_operation()

    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert peak < 10 * 1024 * 1024  # Less than 10 MB
```

### Benchmark Plugin (pytest-benchmark)

```python
# Installation
pip install pytest-benchmark

# Usage
def test_benchmark(benchmark):
    result = benchmark(function_to_test, arg1, arg2)
    assert result == expected
```

## Advanced Topics

### Custom Markers

```python
# Register in pytest.ini
[pytest]
markers =
    smoke: Smoke tests for basic functionality
    security: Security-related tests

# Use in tests
@pytest.mark.smoke
def test_basic_functionality():
    pass
```

### Custom Fixtures

```python
# In conftest.py
@pytest.fixture
def custom_fixture():
    # Setup
    resource = create_resource()

    yield resource

    # Teardown
    cleanup_resource(resource)
```

### Fixture Factories

```python
@pytest.fixture
def make_user():
    """Factory fixture for creating users."""
    created_users = []

    def _make_user(name, email):
        user = User(name=name, email=email)
        created_users.append(user)
        return user

    yield _make_user

    # Cleanup all created users
    for user in created_users:
        user.delete()

def test_with_factory(make_user):
    user1 = make_user("Alice", "alice@example.com")
    user2 = make_user("Bob", "bob@example.com")
    # Test with multiple users
```

Coverage below threshold:

- run the coverage gate equivalent command
- inspect `reports/htmlcov/index.html` for module-level gaps

Backend/server tests not running:

- ensure required env vars are explicitly enabled (`CASCOR_BACKEND_AVAILABLE=1`, `RUN_SERVER_TESTS=1`)
- ensure dependent services/libraries are available for those tests

---

## References

- [Testing Quick Start](TESTING_QUICK_START.md)
- [Testing Environment Setup](TESTING_ENVIRONMENT_SETUP.md)
- [Testing Manual](TESTING_MANUAL.md)
- [Testing Coverage Reports](TESTING_REPORTS_COVERAGE.md)
- [Selective Test Guide](SELECTIVE_TEST_GUIDE.md)
