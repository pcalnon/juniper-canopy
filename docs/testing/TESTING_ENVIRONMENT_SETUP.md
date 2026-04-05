# Testing Environment Setup

**Last Updated:** 2026-04-05  
**Version:** 0.26.0  
**Status:** Current

Operational setup guide for running the Juniper Canopy test suite with the same assumptions used by CI and `src/tests/conftest.py`.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Install Dependencies](#install-dependencies)
3. [Default Test Runtime Behavior](#default-test-runtime-behavior)
4. [Test Selection Controls](#test-selection-controls)
5. [Run Commands](#run-commands)
6. [Verification Checklist](#verification-checklist)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

- Python `3.12+` (CI validates on `3.12`, `3.13`, `3.14`)
- `pip` available
- Repository checked out at project root

```bash
python --version
pip --version
```

---

## Install Dependencies

Use CI-aligned dependencies for local reproducibility:

```bash
python -m pip install --upgrade pip
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r conf/requirements_ci.txt
pip install -e .
```

Optional local tooling:

```bash
pip install pre-commit
pre-commit install
```

---

## Default Test Runtime Behavior

`src/tests/conftest.py` enforces and configures critical defaults before tests run:

- Forces demo mode: `JUNIPER_CANOPY_DEMO_MODE=1`
- Sets JuniperData URL for test paths: `JUNIPER_DATA_URL=http://localhost:8100`
- Disables rate limiting in tests: `CANOPY_RATE_LIMIT_ENABLED=false`
- Adds `src/` to import path at runtime
- Injects stubs for `juniper_data_client` and `juniper_cascor_client` if missing, allowing collection and most unit/integration tests to execute without external services

Implication:

- Most tests should run offline in demo mode without a live backend stack.

---

## Test Selection Controls

Environment variables used for selective enablement:

| Variable | Effect | Default in CI |
| --- | --- | --- |
| `CASCOR_BACKEND_AVAILABLE=1` | Enables tests marked `requires_cascor` | `0` |
| `RUN_SERVER_TESTS=1` | Enables tests marked `requires_server` | `0` |
| `RUN_DISPLAY_TESTS=1` | Enables tests marked `requires_display` in headless environments | `0` |
| `ENABLE_SLOW_TESTS=1` | Enables tests marked `slow` | `0` |

Library-dependent markers:

- `requires_cassandra`: skipped if Cassandra driver is not installed
- `requires_redis`: skipped if Redis library is not installed

---

## Run Commands

Fast unit/regression pass (matches CI gate intent):

```bash
python -m pytest \
  -m "not requires_cascor and not requires_server and not slow" \
  src/tests/unit/ src/tests/regression/ \
  --verbose
```

Integration pass without external dependencies:

```bash
python -m pytest \
  -m "integration and not requires_cascor and not requires_server and not slow" \
  src/tests/integration \
  --verbose
```

Coverage gate equivalent:

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

Opt-in full suite including gated tests:

```bash
export CASCOR_BACKEND_AVAILABLE=1
export RUN_SERVER_TESTS=1
export ENABLE_SLOW_TESTS=1
python -m pytest src/tests --verbose
```

---

## Verification Checklist

- `python -m pytest --collect-only` succeeds
- Fast unit/regression run completes without collection errors
- Coverage command generates:
  - `reports/coverage.xml`
  - `reports/htmlcov/index.html`
- Marker gating behaves as expected when toggling environment variables

---

## Troubleshooting

`ModuleNotFoundError` for project modules:

- Ensure `pip install -e .` has been run in the active environment.

Unexpected skips:

- Run with `-ra` to display skip reasons.
- Check whether marker-enabling env vars are set.

Backend-dependent tests not running:

- Set `CASCOR_BACKEND_AVAILABLE=1` (and ensure backend dependencies are installed/running if required by test path).

Server-dependent tests not running:

- Set `RUN_SERVER_TESTS=1` and provide the expected running server context for those tests.

Coverage below threshold:

- Re-run coverage command above and inspect `reports/htmlcov/index.html` for module-level gaps.

---

## References

- [Testing Quick Start](TESTING_QUICK_START.md)
- [Testing Manual](TESTING_MANUAL.md)
- [Testing Reference](TESTING_REFERENCE.md)
- [Selective Test Guide](SELECTIVE_TEST_GUIDE.md)
