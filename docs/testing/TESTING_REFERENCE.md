# Testing Reference

**Last Updated:** 2026-04-05  
**Version:** 0.26.1  
**Status:** Current

Technical reference for the active pytest configuration, markers, fixtures, and CI-equivalent commands.

---

## Table of Contents

1. [Configuration Sources](#configuration-sources)
2. [Marker Reference](#marker-reference)
3. [Fixture Reference](#fixture-reference)
4. [Environment and Gating Variables](#environment-and-gating-variables)
5. [Command Reference](#command-reference)
6. [Coverage Reference](#coverage-reference)
7. [CI Mapping](#ci-mapping)
8. [Troubleshooting Reference](#troubleshooting-reference)

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

### Useful diagnostics

```bash
pytest --collect-only
pytest --markers
pytest --fixtures
pytest -ra
pytest --lf
pytest --ff
```

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
pytest --collect-only
pytest --markers
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
