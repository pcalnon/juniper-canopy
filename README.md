# juniper-canopy

[![PyPI](https://img.shields.io/pypi/v/juniper-canopy)](https://pypi.org/project/juniper-canopy/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](./LICENSE)

**A real-time dashboard to watch and steer Cascade-Correlation training as it happens.**

`juniper-canopy` is a Dash + FastAPI dashboard that renders Juniper training dynamics live: it pulls
metrics and network topology from [juniper-cascor](https://github.com/pcalnon/juniper-cascor) over
REST and WebSocket and visualises loss, accuracy, and unit recruitment as the network grows. It draws
dataset context from [juniper-data](https://github.com/pcalnon/juniper-data) and exposes a WebSocket
control surface to pause, resume, and step a run from the browser. A demo mode runs the whole UI
against simulated data with no backend.

> **Part of the Juniper platform.** juniper-canopy is the real-time monitoring dashboard of
> [Juniper](https://github.com/pcalnon/juniper-ml) — a multi-package ML research platform built around
> constructive (Cascade-Correlation) and recurrent neural networks. It reads from juniper-cascor and
> juniper-data over HTTP.

## Install

```bash
pip install juniper-canopy
```

## Run

Demo mode — no backend required, simulated training:

```bash
./demo                                 # then open http://localhost:8050
```

Service mode — against live juniper-cascor + juniper-data instances:

```bash
export JUNIPER_CANOPY_CASCOR_SERVICE_URL=http://<cascor-host>:8200
export JUNIPER_DATA_URL=http://<data-host>:8100
python src/main.py                     # dashboard on http://localhost:8050
```

API docs are served at `/docs` (Swagger) and `/redoc`.

## Configuration

Settings load from the `JUNIPER_CANOPY_` environment namespace (`src/settings.py`):

| Variable | Default | Purpose |
|----------|---------|---------|
| `JUNIPER_CANOPY_CASCOR_SERVICE_URL` | — | URL of the juniper-cascor service (required for service mode). |
| `JUNIPER_DATA_URL` | `http://localhost:8100` | URL of the juniper-data service. |
| `JUNIPER_CANOPY_DEMO_MODE` | `false` | Set `1` to run the UI against simulated data (no backend). |
| `JUNIPER_CANOPY_SERVER__HOST` / `JUNIPER_CANOPY_SERVER__PORT` | `127.0.0.1` / `8050` | Bind address / port. A non-loopback host requires a perimeter attestation (`JUNIPER_CANOPY_LOOPBACK_PUBLISH_ATTESTED` or `JUNIPER_CANOPY_AUTH_PROXY_ATTESTED`); otherwise startup fail-closes (SEC-F22). |
| `JUNIPER_DATA_API_KEY` | — | API key for juniper-data when its auth is enabled. |
| `JUNIPER_CANOPY_LOG_LEVEL` | `INFO` | Logging verbosity. |

## Docker

```bash
docker build -t juniper-canopy:latest .
docker run --rm -p 8050:8050 juniper-canopy:latest                # demo mode (image default)

docker run --rm -p 8050:8050 \
  -e JUNIPER_CANOPY_DEMO_MODE=0 \
  -e JUNIPER_CANOPY_CASCOR_SERVICE_URL=http://host.docker.internal:8200 \
  -e JUNIPER_DATA_URL=http://host.docker.internal:8100 \
  juniper-canopy:latest                                           # service mode
```

For the orchestrated full stack, see [`juniper-deploy`](https://github.com/pcalnon/juniper-deploy).

## Status

**Beta** on PyPI. The current version is shown by the badge above; see [`CHANGELOG.md`](CHANGELOG.md).
Supports Python 3.11–3.14.

## Documentation

- [`docs/QUICK_START.md`](docs/QUICK_START.md) — five-minute startup guide
- [`docs/USER_MANUAL.md`](docs/USER_MANUAL.md) — comprehensive usage guide
- [`docs/ENVIRONMENT_SETUP.md`](docs/ENVIRONMENT_SETUP.md) — environment configuration
- [`docs/DOCUMENTATION_OVERVIEW.md`](docs/DOCUMENTATION_OVERVIEW.md) — documentation index

## License

MIT — see [LICENSE](./LICENSE).
