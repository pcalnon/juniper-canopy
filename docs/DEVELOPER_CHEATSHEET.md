# Developer Cheatsheet -- juniper-canopy

**Version**: 1.0.0
**Date**: 2026-03-15
**Project**: juniper-canopy

---

## Common Commands

**The following commands launch a full set of Juniper Project services, start services in the order listed below:**

- juniper-data: cd /home/pcalnon/Development/python/Juniper/juniper-data && conda activate JuniperData && pip install -e ".[all]" && PYTHON_GIL=0 uvicorn juniper_data.api.app:app --host 0.0.0.0 --port 8100
- juniper-cascor: cd /home/pcalnon/Development/python/Juniper/juniper-cascor/src && conda activate JuniperCascor && JUNIPER_CASCOR_PORT=8201 python server.py
- juniper-canopy: cd /home/pcalnon/Development/python/Juniper/juniper-canopy/src && conda activate JuniperCanopy && CASCOR_SERVICE_URL="<http://localhost:8201>" uvicorn main:app --host 0.0.0.0 --port 8050

**General list of useful Commands:**

| Task                        | Command                                                                                              |
|-----------------------------|------------------------------------------------------------------------------------------------------|
| Run in demo mode            | `./demo`                                                                                             |
| Run natively (real backend) | `conda activate JuniperCanopy && cd src && uvicorn main:app --port 8050`                             |
| Run via Docker              | `docker build -f conf/Dockerfile -t juniper_canopy . && docker run --rm -p 8050:8050 juniper_canopy` |
| Run via Docker Compose      | `docker compose -f conf/docker-compose.yaml up --build`                                              |
| Health check                | `curl -s http://localhost:8050/v1/health \| python -m json.tool`                                     |
| Liveness / readiness        | `curl -s http://localhost:8050/v1/health/live` / `.../v1/health/ready`                               |
| Run all tests               | `cd src && pytest tests/ -v`                                                                         |
| Run unit tests only         | `cd src && pytest -m "unit and not slow" -v`                                                         |
| Run integration tests       | `cd src && pytest tests/integration/ -v`                                                             |
| Run with coverage           | `cd src && pytest tests/ --cov=. --cov-report=html --cov-report=term-missing`                        |
| Coverage threshold check    | `cd src && pytest tests/ --cov=. --cov-fail-under=80`                                                |
| Validate documentation links (CI mode) | `python scripts/check_doc_links.py --exclude templates --exclude history --exclude pull_requests --exclude releases --exclude analysis --exclude fixes --exclude development --exclude CHANGELOG.md --cross-repo skip` |
| Validate documentation links (cross-repo local) | `python scripts/check_doc_links.py --cross-repo check` |
| Pre-commit (all hooks)      | `pre-commit run --all-files`                                                                         |
| Validate documentation links (CI mode) | `python scripts/check_doc_links.py --exclude templates --exclude history --exclude pull_requests --exclude releases --exclude analysis --exclude fixes --exclude development --exclude CHANGELOG.md --cross-repo skip` |
| Format code                 | `black src/ && isort src/`                                                                           |
| Lint                        | `flake8 src/ --max-line-length=512 --statistics`                                                     |
| Type check                  | `mypy src/ --ignore-missing-imports`                                                                 |
| Security scan               | `bandit -r src/`                                                                                     |
| Check doc links (CI parity) | `python scripts/check_doc_links.py --exclude templates --exclude history --exclude pull_requests --exclude releases --exclude analysis --exclude fixes --exclude development --exclude CHANGELOG.md --cross-repo skip` |
| Check doc links (strict)    | `python scripts/check_doc_links.py --cross-repo check`                                               |
| Install pre-commit hooks    | `pip install pre-commit && pre-commit install`                                                       |

> See: [AGENTS.md](../AGENTS.md) for full command reference

---

## Project-Specific Procedures

### 1. Add a Config Entry

juniper-canopy uses a 3-level hierarchy (highest priority first):

1. **Environment variables** (`CASCOR_*`, `JUNIPER_CANOPY_*`)
2. **YAML config** (`conf/app_config.yaml`) -- supports `${VAR:default}` substitution
3. **Constants module** (`src/canopy_constants.py`) -- dataclass-based (`TrainingConstants`, `DashboardConstants`, `ServerConstants`)

Add at the appropriate level based on how dynamic the value needs to be. If adding a constant, follow the naming convention including units (`_MS`, `_S`, `_PX`).

> See: [Constants Guide](cascor/CONSTANTS_GUIDE.md) | [AGENTS.md -- Configuration Management](../AGENTS.md#configuration-management)

### 2. Connect to CasCor Backend

```bash
# Real backend mode
unset CASCOR_DEMO_MODE
export CASCOR_BACKEND_PATH=/path/to/cascor
cd src && uvicorn main:app --host 0.0.0.0 --port 8050
```

WebSocket channels for real-time training updates:

| Channel  | Path           | Direction        | Purpose                           |
|----------|----------------|------------------|-----------------------------------|
| Training | `/ws/training` | Server -> Client | Metrics, state, topology updates  |
| Control  | `/ws/control`  | Bidirectional    | Start, stop, pause, resume, reset |

> See: [CasCor Backend Reference](cascor/CASCOR_BACKEND_REFERENCE.md) | [API Reference](api/API_REFERENCE.md)

### 3. Add a Dashboard Component

Component hierarchy: `dashboard_manager.py` -> `frontend/components/*.py` -> `frontend/base_component.py`

1. Create `src/frontend/components/my_component.py` extending `BaseComponent`
2. Register in `src/frontend/dashboard_manager.py`
3. Add Dash callbacks in the component or `src/frontend/callback_context.py`
4. If the component uses singletons, extend the `reset_singletons` fixture in `src/tests/conftest.py`

Existing components: `training_metrics`, `metrics_panel`, `network_visualizer`, `decision_boundary`, `dataset_plotter`, `about_panel`, `hdf5_snapshots_panel`, `redis_panel`, `cassandra_panel`

> See: [AGENTS.md -- Architecture](../AGENTS.md#architecture)

### 4. Add a Dependency

1. Add to `conf/requirements.txt` (and `conf/conda_environment.yaml` if conda-installable)
2. Run `pip install -r conf/requirements.txt` in the `JuniperCanopy` conda env
3. Update `conf/Dockerfile` if needed for Docker builds

> See: [ENVIRONMENT_SETUP.md](ENVIRONMENT_SETUP.md)

### 5. Validate Documentation Links

Use the same command as CI when validating markdown links locally:

```bash
python scripts/check_doc_links.py \
  --exclude templates --exclude history \
  --exclude pull_requests --exclude releases \
  --exclude analysis --exclude fixes --exclude development \
  --exclude CHANGELOG.md \
  --cross-repo skip
```

Cross-repo policy modes:

- `--cross-repo skip`: ignore Juniper sibling-repo links (default CI mode)
- `--cross-repo warn`: print warnings for sibling-repo links but do not fail
- `--cross-repo check`: validate sibling-repo links against a local ecosystem checkout

Common failure causes:

- Absolute path links (for example, `/tmp/file.md`) are rejected
- Overly deep traversal links (`../../../../../../file.md`) are rejected
- Null-byte targets are rejected
- Same-file anchors fail if no matching heading exists
- Links inside fenced code blocks and inline code are intentionally ignored

---

## Environment Variables

| Variable                                    | Default             | Description                                                                                                       |
|---------------------------------------------|---------------------|-------------------------------------------------------------------------------------------------------------------|
| `JUNIPER_CANOPY_DEMO_MODE`                  | unset               | Set `1` to enable demo mode (simulated training). `CASCOR_DEMO_MODE` is accepted as a deprecated legacy fallback. |
| `CASCOR_SERVER_HOST`                        | `127.0.0.1`         | Server bind address                                                                                               |
| `CASCOR_SERVER_PORT`                        | `8050`              | Server port                                                                                                       |
| `CASCOR_SERVER_DEBUG`                       | `0`                 | Enable debug mode                                                                                                 |
| `CASCOR_BACKEND_PATH`                       | `../juniper-cascor` | Path to CasCor backend                                                                                            |
| `CASCOR_TRAINING_EPOCHS`                    | `500`               | Maximum training epochs                                                                                           |
| `CASCOR_TRAINING_LEARNING_RATE`             | `0.01`              | Learning rate                                                                                                     |
| `CASCOR_TRAINING_HIDDEN_UNITS`              | `40`                | Max hidden units                                                                                                  |
| `CASCOR_WEBSOCKET_MAX_CONNECTIONS`          | `50`                | Max concurrent WebSocket connections                                                                              |
| `CASCOR_WEBSOCKET_HEARTBEAT_INTERVAL`       | `30`                | Heartbeat interval (seconds)                                                                                      |
| `CASCOR_DEMO_UPDATE_INTERVAL`               | `1.0`               | Demo simulation step interval (seconds)                                                                           |
| `CASCOR_DEMO_CASCADE_EVERY`                 | `30`                | Demo: add hidden unit every N epochs                                                                              |
| `JUNIPER_CANOPY_METRICS_UPDATE_INTERVAL_MS` | `1000`              | Dashboard metrics refresh (ms)                                                                                    |
| `JUNIPER_CANOPY_METRICS_BUFFER_SIZE`        | `10000`             | Metrics data buffer size                                                                                          |
| `JUNIPER_CANOPY_LOG_FORMAT`                 | text                | Set `json` for structured JSON logging                                                                            |
| `JUNIPER_CANOPY_SENTRY_DSN`                 | unset               | Sentry error tracking DSN                                                                                         |
| `JUNIPER_CANOPY_METRICS_ENABLED`            | `false`             | Enable Prometheus metrics (`juniper_canopy_*`)                                                                    |

> See: [ENVIRONMENT_SETUP.md](ENVIRONMENT_SETUP.md) | [REFERENCE.md -- Configuration Reference](REFERENCE.md#configuration-reference)

---

## Logging and Metrics

Extended log levels: `TRACE (5)`, `VERBOSE (7)`, `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`, `FATAL (60)`. Config: `conf/logging_config.yaml`. Prometheus metrics use the `juniper_canopy_*` namespace (e.g., `juniper_canopy_websocket_connections_active`).

> See: [REFERENCE.md](REFERENCE.md#constants-reference)

---

## Testing

### Pytest Markers

| Marker             | Meaning                       |
|--------------------|-------------------------------|
| `unit`             | Fast, no external deps        |
| `integration`      | Backend, DB, filesystem       |
| `regression`       | Guards against fixed bugs     |
| `performance`      | Benchmarks                    |
| `e2e`              | Full stack with real services |
| `slow`             | Tests > 1s                    |
| `requires_cascor`  | Needs real CasCor backend     |
| `requires_server`  | Needs running server          |
| `requires_redis`   | Needs Redis                   |
| `requires_display` | Needs GUI/display             |
| `api`              | API endpoint tests            |
| `generators`       | Data generator tests          |

### Test Opt-In Variables

| Variable                     | Effect                          |
|------------------------------|---------------------------------|
| `CASCOR_BACKEND_AVAILABLE=1` | Enable `requires_cascor` tests  |
| `RUN_SERVER_TESTS=1`         | Enable `requires_server` tests  |
| `RUN_DISPLAY_TESTS=1`        | Enable `requires_display` tests |
| `ENABLE_SLOW_TESTS=1`        | Enable `slow` tests             |

> Note: `conftest.py` forces `JUNIPER_CANOPY_DEMO_MODE=1` by default so tests do not require a real backend.
> See: [Testing Reference](testing/TESTING_REFERENCE.md) | [Test Enablement Quick Reference](testing/TEST_ENABLEMENT_QUICK_REFERENCE.md)

### Documentation Link Checker Test Coverage

Run focused tests for documentation link validation hardening:

```bash
pytest src/tests/unit/test_check_doc_links.py -v
```

Coverage includes:

- Link parsing boundaries (ignores fenced-code and inline-code link literals).
- Anchor integrity checks for same-file heading targets.
- Security validation for path inputs (absolute paths, null bytes, excessive traversal).
- Cross-repo policy behavior (`skip`, `warn`, `check`) and fallback when ecosystem root discovery fails.

---

## Troubleshooting

| Symptom                                          | Cause                      | Fix                                                                                                             |
|--------------------------------------------------|----------------------------|-----------------------------------------------------------------------------------------------------------------|
| `ModuleNotFoundError: No module named 'uvicorn'` | Wrong Python env           | `conda activate JuniperCanopy`                                                                            |
| Env var not taking effect                        | Missing `CASCOR_` prefix   | Use `CASCOR_TRAINING_EPOCHS=300`, not `TRAINING_EPOCHS=300`                                                     |
| YAML config not loading                          | Syntax error               | `python -c "import yaml; yaml.safe_load(open('conf/app_config.yaml'))"`                                         |
| Demo mode not starting                           | `CASCOR_DEMO_MODE` not set | Run via `./demo` or `export CASCOR_DEMO_MODE=1` first                                                           |
| Demo shows stale data                            | Singleton not reset        | Restart app; check `reset_singletons` fixture covers new singletons                                             |
| WebSocket not connecting                         | Wrong port or path         | Verify `ws://localhost:8050/ws/training`; check `CASCOR_WEBSOCKET_*` vars                                       |
| Tests fail with backend errors                   | Demo mode not forced       | Ensure `conftest.py` sets `CASCOR_DEMO_MODE=1`; do not set `CASCOR_BACKEND_AVAILABLE` unless backend is running |
| Docs job fails in CI (`Documentation Links`)     | Broken links/anchors or unsafe doc path | Re-run `python scripts/check_doc_links.py --cross-repo skip --exclude templates --exclude history --exclude pull_requests --exclude releases --exclude analysis --exclude fixes --exclude development --exclude CHANGELOG.md` and fix reported markdown targets |
| Prometheus metrics missing                       | Feature not enabled        | Set `JUNIPER_CANOPY_METRICS_ENABLED=true`; verify `/metrics` endpoint returns data                              |

---

## Integration Setup (Planned -- NOT YET IMPLEMENTED)

| Integration   | Purpose                                | Config Status                  | Component Stub                               |
|---------------|----------------------------------------|--------------------------------|----------------------------------------------|
| **Cassandra** | Time-series metrics storage            | Not in `app_config.yaml`       | `src/frontend/components/cassandra_panel.py` |
| **Redis**     | Metrics caching, session mgmt, pub/sub | In `app_config.yaml` (pending) | `src/frontend/components/redis_panel.py`     |

> See: [Cassandra Reference](cassandra/CASSANDRA_INTEGRATION_REFERENCE.md) | [Redis Reference](redis/REDIS_INTEGRATION_REFERENCE.md)

---

## Cross-References

| Resource                              | Location                                                                 |
|---------------------------------------|--------------------------------------------------------------------------|
| Ecosystem cheatsheet                  | `../../juniper-ml/docs/DEVELOPER_CHEATSHEET.md`                          |
| Parent ecosystem guide                | [../CLAUDE.md](../CLAUDE.md)                                             |
| juniper-cascor-client (WebSocket)     | `../../juniper-cascor-client/docs/DEVELOPER_CHEATSHEET.md`               |
| juniper-deploy (Docker orchestration) | `../../juniper-deploy/docs/DEVELOPER_CHEATSHEET.md`                      |
| API Reference                         | [api/API_REFERENCE.md](api/API_REFERENCE.md)                             |
| Demo Mode Reference                   | [demo/DEMO_MODE_REFERENCE.md](demo/DEMO_MODE_REFERENCE.md)               |
| CasCor Backend Reference              | [cascor/CASCOR_BACKEND_REFERENCE.md](cascor/CASCOR_BACKEND_REFERENCE.md) |

---

**Last Updated:** 2026-04-05
**Version:** 1.0.1
**Maintainer:** Paul Calnon
