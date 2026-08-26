# Demo Mode Environment Setup

## Comprehensive Guide to Configuring the Demo Mode Environment

**Version:** 0.25.0
**Status:** Active
**Last Updated:** March 3, 2026
**Project:** Juniper - Cascade Correlation Neural Network Monitoring

---

## Prerequisites

### Conda Environment

Demo mode runs in the live `JuniperCanopy*` conda environment (the name is versioned — `JuniperCanopy1` today; `./demo` resolves it automatically):

```bash
# Environment location
/opt/miniforge3/envs/JuniperCanopy1

# Verify environment exists
conda env list | grep JuniperCanopy

# Manual activation (if needed)
conda activate JuniperCanopy1

# Python interpreter path
/opt/miniforge3/envs/JuniperCanopy1/bin/python
```

### Dependencies

Install required packages (normally handled by conda environment):

```bash
conda activate JuniperCanopy1
pip install -r conf/requirements.txt
```

**Key dependencies:**

- FastAPI + Uvicorn (web server, WebSocket)
- Dash + Plotly (interactive dashboard)
- NumPy (numerical operations)
- PyYAML (configuration)
- pytest, pytest-asyncio (testing)

## Configuration Methods

Demo mode reads the same typed settings as every other mode (`src/settings.py`, `pydantic-settings`).
Precedence, highest first:

1. **Environment variables** (`JUNIPER_CANOPY_*`)
2. **A `.env` file** in the process's working directory — `src/`, since both `./demo` and the manual
   launch `cd src` first (`.env.example` at the repo root lists every key)
3. **The defaults in `src/settings.py`**

`conf/app_config.yaml` is legacy: nothing in demo mode reads it any more (only the optional Redis
client still does, through `config_manager.py`).

### Method 1: Environment Variables

Set `JUNIPER_CANOPY_`-prefixed variables; nested sections use a double underscore:

```bash
# Enable demo mode
export JUNIPER_CANOPY_DEMO_MODE=1

# Server configuration (a non-loopback host needs a SEC-F22 attestation — see Scenario 6)
export JUNIPER_CANOPY_SERVER__HOST=0.0.0.0
export JUNIPER_CANOPY_SERVER__PORT=8050

# Demo pacing
export JUNIPER_CANOPY_DEMO_CASCADE_EVERY=30      # add a cascade unit every N epochs (default 30)
# JUNIPER_CANOPY_DEMO_UPDATE_INTERVAL is declared in settings but not applied: the backend
# factory creates the demo backend with a fixed 1.0 s epoch interval (a tracked divergence).

# Sidebar default for the hidden-unit cap
export JUNIPER_CANOPY_TRAINING__HIDDEN_UNITS__DEFAULT=8

# Logging
export JUNIPER_CANOPY_LOG_LEVEL=DEBUG

# In-process cascor checkout (legacy path; the service is selected with JUNIPER_CANOPY_CASCOR_SERVICE_URL)
export JUNIPER_CANOPY_BACKEND_PATH=/path/to/juniper-cascor
```

### Method 2: Configuration File

The only configuration file the application reads is a `.env` file:

```bash
# Copy the template next to main.py (the directory canopy runs from) and edit the keys above
cp .env.example src/.env
```

The file is read at startup, below any exported variable.

**Legacy names.** `CASCOR_DEMO_MODE`, `CASCOR_DEMO_UPDATE_INTERVAL`, `CASCOR_DEMO_CASCADE_EVERY`,
`CASCOR_BACKEND_PATH` and `CASCOR_LOG_LEVEL` still work, with a deprecation warning.
`CASCOR_SERVER_*`, `CASCOR_DEBUG`, `CASCOR_DEMO_EPOCH_DURATION`, `CASCOR_DEMO_CASCADE_INTERVAL`,
`CASCOR_DEMO_MAX_HIDDEN_UNITS`, `CASCOR_DATA_DIR` and `CASCOR_LOG_DIR` are read by nothing.

### Method 3: Launch Script

The `./demo` script sets defaults automatically:

```bash
#!/usr/bin/env bash
# util/run_demo.bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Activate conda environment
eval "$(/opt/miniforge3/bin/conda shell.bash hook)"
conda activate JuniperCanopy1

# Set demo mode
export CASCOR_DEMO_MODE=1

# Launch application
cd "$PROJECT_ROOT/src"
exec "$CONDA_PREFIX/bin/python" -u main.py
```

## Configuration Scenarios

### Scenario 1: Basic Demo (Default)

```bash
./demo
```

Uses all defaults from `src/settings.py`.

### Scenario 2: Custom Port

```bash
export JUNIPER_CANOPY_SERVER__PORT=8051
./demo
```

Overrides port to 8051, keeps other defaults.

### Scenario 3: Faster Cascade Growth

```bash
export JUNIPER_CANOPY_DEMO_CASCADE_EVERY=10   # add a cascade unit every 10 epochs
./demo
```

The simulated epoch interval itself is fixed at 1.0 s by the application (the
`JUNIPER_CANOPY_DEMO_UPDATE_INTERVAL` setting exists but is not applied — a tracked divergence), so
growth is made visible sooner by shortening the cascade schedule.

### Scenario 4: Extended Training

```bash
export JUNIPER_CANOPY_TRAINING__HIDDEN_UNITS__DEFAULT=16   # sidebar default: up to 16 cascade units
export JUNIPER_CANOPY_DEMO_CASCADE_EVERY=50                # add a unit every 50 epochs
./demo
```

Longer training with more cascade units.

### Scenario 5: Debug Mode

```bash
export JUNIPER_CANOPY_LOG_LEVEL=DEBUG
./demo
```

Enables verbose logging to `logs/system.log`.

### Scenario 6: Remote Access

```bash
export JUNIPER_CANOPY_SERVER__HOST=0.0.0.0
export JUNIPER_CANOPY_SERVER__PORT=8050
export JUNIPER_CANOPY_AUTH_PROXY_ATTESTED=true   # or JUNIPER_CANOPY_LOOPBACK_PUBLISH_ATTESTED=true
./demo
```

Allows access from other machines on the network. A non-loopback bind **refuses to start** unless one
of the two SEC-F22 perimeter attestations is set — they are operator statements that an
authenticating proxy (or a loopback-only publish) fronts the port, not a runtime check.

## Path Configuration

Demo mode uses `pathlib` for cross-platform path resolution:

```python
from pathlib import Path

# Automatically resolved from project structure
ROOT = Path(__file__).resolve().parents[1]
data_dir = (ROOT / "data").resolve()
logs_dir = (ROOT / "logs").resolve()
```

**No hardcoded paths allowed.** Use environment variables or config file.

## Verification

### Check Active Configuration

```bash
# Launch with debug logging
export JUNIPER_CANOPY_LOG_LEVEL=DEBUG
./demo
```

Check `logs/system.log` for the startup lines — a legacy `CASCOR_*` name in use is reported there as
a deprecation warning — and `GET /v1/health` for `demo_mode`.

### Test Configuration Override

```python
# From a Python console started in src/ (for testing)
from settings import get_settings

s = get_settings()
print(s.demo_mode)      # True
print(s.server.port)    # 8050
```

## Environment Reset

To reset to defaults:

```bash
# Unset all canopy environment variables (current and legacy names)
unset $(env | grep -E '^(JUNIPER_CANOPY_|CASCOR_)' | cut -d= -f1)

# Or start fresh shell
exec $SHELL

# Launch with clean defaults
./demo
```

## Docker Environment (Future)

Placeholder for future Docker deployment:

```dockerfile
# Dockerfile
FROM continuumio/miniconda3

# Copy environment file
COPY conf/conda_environment.yaml /tmp/environment.yaml

# Create conda environment
RUN conda env create -f /tmp/environment.yaml

# Set environment variables (a non-loopback bind needs a SEC-F22 attestation)
ENV JUNIPER_CANOPY_DEMO_MODE=1
ENV JUNIPER_CANOPY_SERVER__HOST=0.0.0.0
ENV JUNIPER_CANOPY_SERVER__PORT=8050
ENV JUNIPER_CANOPY_LOOPBACK_PUBLISH_ATTESTED=true

# Launch demo mode
CMD ["conda", "run", "-n", "JuniperCanopy1", "python", "src/main.py"]
```

```bash
# Build and run
docker build -t cascor-demo .
docker run -p 8050:8050 cascor-demo
```

## Troubleshooting

### Issue: Environment variable not recognized

**Symptom:** `DEMO_MODE=1` (or another unprefixed name) has no effect

**Solution:** the prefix is `JUNIPER_CANOPY_`, with `__` between a section and its key:

```bash
# Correct
export JUNIPER_CANOPY_DEMO_MODE=1
export JUNIPER_CANOPY_SERVER__PORT=8051

# Legacy alias — still works, logs a deprecation warning
export CASCOR_DEMO_MODE=1

# Wrong — no prefix, or a single underscore between section and key (silently ignored)
export DEMO_MODE=1
export JUNIPER_CANOPY_SERVER_PORT=8051
```

### Issue: Path expansion fails

**Symptom:** `${HOME}` appears literally in paths

**Solution:** Use proper expansion syntax:

```yaml
# Correct
paths:
  data: "${HOME}/data"
  logs: "$HOME/logs"

# Wrong
paths:
  data: $HOME/data     # Missing quotes, may not expand
```

### Issue: Configuration not loading

**Symptom:** Changes to `conf/app_config.yaml` ignored

**Solution:** Force reload or check file syntax:

```bash
# Verify YAML syntax
python -c "import yaml; yaml.safe_load(open('conf/app_config.yaml'))"

# Check file is being read
ls -la conf/app_config.yaml
```

## Next Steps

- **[Demo Mode Manual](DEMO_MODE_MANUAL.md)** - Using demo mode
- **[Technical Reference](DEMO_MODE_REFERENCE.md)** - Implementation details
- **[Quick Start](DEMO_MODE_QUICK_START.md)** - Launch in 60 seconds

---

**Last Updated:** March 3, 2026
**Version:** 0.25.0
**Maintainer:** Paul Calnon
