# Developer Cheatsheet -- juniper-canopy

**Version**: 1.0.2
**Date**: 2026-07-04
**Project**: juniper-canopy

---

## Common Commands

**The following commands launch a full set of Juniper Project services, start services in the order listed below:**

- juniper-data: cd /home/pcalnon/Development/python/Juniper/juniper-data && conda activate JuniperData && pip install -e ".[all]" && PYTHON_GIL=0 uvicorn juniper_data.api.app:app --host 0.0.0.0 --port 8100
- juniper-cascor: cd /home/pcalnon/Development/python/Juniper/juniper-cascor/src && conda activate JuniperCascor1 && JUNIPER_CASCOR_PORT=8201 python server.py
- juniper-canopy: cd /home/pcalnon/Development/python/Juniper/juniper-canopy/src && conda activate JuniperCanopy1 && JUNIPER_CANOPY_CASCOR_SERVICE_URL="<http://localhost:8201>" uvicorn main:app --host 127.0.0.1 --port 8050

> **Conda env naming:** the live envs are **versioned** — `JuniperCanopy1`, `JuniperCascor1` (the bare `JuniperCanopy` / `JuniperCascor` are now `*-DEPRECATED` with a broken toolchain; `JuniperData` is unversioned). Discover yours with `conda env list | grep Juniper<App>` and use that name; rebuilds increment the suffix.

**General list of useful Commands:**

| Task                        | Command                                                                                              |
|-----------------------------|------------------------------------------------------------------------------------------------------|
| Run in demo mode            | `./demo`                                                                                             |
| Run natively (real backend) | `conda activate JuniperCanopy1 && cd src && uvicorn main:app --port 8050`                             |
| Run via Docker              | `docker build -t juniper-canopy . && docker run --rm -p 127.0.0.1:8050:8050 juniper-canopy` |
| Run full stack (Compose)    | `cd ../juniper-deploy && docker compose up --build`                                          |
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

1. **Pydantic environment variables** (`JUNIPER_CANOPY_*`; selected legacy `CASCOR_*` fallbacks remain)
2. **YAML config** (`conf/app_config.yaml`) -- supports `${VAR:default}` substitution
3. **Constants module** (`src/canopy_constants.py`) -- dataclass-based (`TrainingConstants`, `DashboardConstants`, `ServerConstants`)

Add at the appropriate level based on how dynamic the value needs to be. If adding a constant, follow the naming convention including units (`_MS`, `_S`, `_PX`).

> See: [Constants Guide](cascor/CONSTANTS_GUIDE.md) | [AGENTS.md -- Configuration Management](../AGENTS.md#configuration-management)

### 2. Connect to CasCor Backend

```bash
# Real backend mode
unset JUNIPER_CANOPY_DEMO_MODE
export JUNIPER_CANOPY_BACKEND_PATH=/path/to/juniper-cascor
cd src && uvicorn main:app --host 127.0.0.1 --port 8050
```

Canopy refuses to start on a non-loopback bind (`0.0.0.0`, routable IP, or `::`) unless at least one
perimeter attestation is set: `JUNIPER_CANOPY_LOOPBACK_PUBLISH_ATTESTED=true` (reachable only via a
loopback-only host publish, the containerized default) or `JUNIPER_CANOPY_AUTH_PROXY_ATTESTED=true`
(a fronting authenticating reverse proxy terminates access, Phase 4). Set one only when that perimeter
is actually present in front of the browser control surface.

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
2. Run `pip install -r conf/requirements.txt` in the `JuniperCanopy1` conda env
3. Update the repo-root `Dockerfile` if needed for Docker builds

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
| `JUNIPER_CANOPY_SERVER__HOST`               | `127.0.0.1`         | Server bind address; non-loopback requires explicit fronting-auth attestation                                      |
| `JUNIPER_CANOPY_SERVER__PORT`               | `8050`              | Server port                                                                                                       |
| `JUNIPER_CANOPY_SERVER__DEBUG`              | `false`             | Enable debug mode                                                                                                 |
| `JUNIPER_CANOPY_LOOPBACK_PUBLISH_ATTESTED`  | `false`             | Allow non-loopback bind: reachable only via a loopback-only host publish (containerized default)                   |
| `JUNIPER_CANOPY_AUTH_PROXY_ATTESTED`        | `false`             | Allow non-loopback bind: a fronting authenticating reverse proxy terminates access (Phase 4)                       |
| `JUNIPER_CANOPY_BACKEND_PATH`               | `../juniper-cascor` | Path to CasCor backend                                                                                            |
| `JUNIPER_CANOPY_TRAINING__EPOCHS__DEFAULT`  | `1000000`           | Default maximum training epochs                                                                                   |
| `JUNIPER_CANOPY_TRAINING__LEARNING_RATE__DEFAULT` | `0.01`        | Default learning rate                                                                                             |
| `JUNIPER_CANOPY_TRAINING__HIDDEN_UNITS__DEFAULT` | `1000`          | Default max hidden units                                                                                          |
| `JUNIPER_CANOPY_WEBSOCKET__MAX_CONNECTIONS` | `50`                | Stack-wide cap across `/ws/training`, `/ws/control`, and `/ws`; over-cap closes with 1013                         |
| `JUNIPER_CANOPY_WEBSOCKET__MAX_CONNECTIONS_PER_IP` | `5`         | Per-IP DoS dampening; not per-client identity behind NAT                                                           |
| `JUNIPER_CANOPY_WEBSOCKET__MAX_CONNECTIONS_PER_SESSION` | `5`    | Per-session fairness cap keyed on `canopy_session`                                                               |
| `JUNIPER_CANOPY_WEBSOCKET__HEARTBEAT_INTERVAL` | `30`           | Heartbeat interval (seconds)                                                                                      |
| `JUNIPER_CANOPY_DEMO_UPDATE_INTERVAL`       | `1.0`               | Demo simulation step interval (seconds)                                                                           |
| `JUNIPER_CANOPY_DEMO_CASCADE_EVERY`         | `30`                | Demo: add hidden unit every N epochs                                                                              |
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
| `ModuleNotFoundError: No module named 'uvicorn'` | Wrong Python env           | `conda activate JuniperCanopy1`                                                                            |
| Env var not taking effect                        | Missing `JUNIPER_CANOPY_` prefix or nested delimiter | Use `JUNIPER_CANOPY_TRAINING__EPOCHS__DEFAULT=300`, not `TRAINING_EPOCHS=300`                         |
| YAML config not loading                          | Syntax error               | `python -c "import yaml; yaml.safe_load(open('conf/app_config.yaml'))"`                                         |
| Demo mode not starting                           | Demo mode env not set      | Run via `./demo` or `export JUNIPER_CANOPY_DEMO_MODE=1` first                                                   |
| Demo shows stale data                            | Singleton not reset        | Restart app; check `reset_singletons` fixture covers new singletons                                             |
| WebSocket not connecting                         | Wrong port or path         | Verify `ws://localhost:8050/ws/training`; check `JUNIPER_CANOPY_WEBSOCKET__*` vars                              |
| Startup refuses non-loopback bind                | Bind guard blocked unsafe exposure | Use `JUNIPER_CANOPY_SERVER__HOST=127.0.0.1`, or attest the perimeter: `JUNIPER_CANOPY_LOOPBACK_PUBLISH_ATTESTED=true` (loopback-only host publish) or `JUNIPER_CANOPY_AUTH_PROXY_ATTESTED=true` (fronting auth proxy) |
| WebSocket closes with `1013`                     | Global, per-IP, or per-session cap reached | Check `JUNIPER_CANOPY_WEBSOCKET__MAX_CONNECTIONS*`; remember per-IP is shared behind NAT                         |
| Tests fail with backend errors                   | Demo mode not forced       | Ensure `conftest.py` sets `JUNIPER_CANOPY_DEMO_MODE=1`; do not set `CASCOR_BACKEND_AVAILABLE` unless backend is running |
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

**Last Updated:** 2026-07-04
**Version:** 1.0.2
**Maintainer:** Paul Calnon
