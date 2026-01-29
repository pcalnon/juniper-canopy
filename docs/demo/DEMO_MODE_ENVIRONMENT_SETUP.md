# Demo Mode Environment Setup

Comprehensive guide to configuring the demo mode environment.

## Prerequisites

### Conda Environment

Demo mode requires the JuniperPython conda environment:

```bash
# Environment location
/opt/miniforge3/envs/JuniperPython

# Verify environment exists
conda env list | grep JuniperPython

# Manual activation (if needed)
conda activate JuniperPython

# Python interpreter path
/opt/miniforge3/envs/JuniperPython/bin/python
```

### Dependencies

Install required packages (normally handled by conda environment):

```bash
conda activate JuniperPython
pip install -r conf/requirements.txt
```

**Key dependencies:**

- FastAPI + Uvicorn (web server, WebSocket)
- Dash + Plotly (interactive dashboard)
- NumPy (numerical operations)
- PyYAML (configuration)
- pytest, pytest-asyncio (testing)

## Configuration Methods

Demo mode supports three configuration layers (priority order):

1. **Environment variables** (highest priority)
2. **YAML configuration file** (`conf/app_config.yaml`)
3. **Hard-coded defaults** (lowest priority)

### Method 1: Environment Variables

Set `CASCOR_<SECTION>_<KEY>` variables:

```bash
# Enable demo mode
export CASCOR_DEMO_MODE=1

# Server configuration
export CASCOR_SERVER_HOST=0.0.0.0
export CASCOR_SERVER_PORT=8050
export CASCOR_SERVER_RELOAD=0

# Demo mode settings
export CASCOR_DEMO_UPDATE_INTERVAL=0.1    # Update every 100ms
export CASCOR_DEMO_EPOCH_DURATION=0.05    # 50ms per epoch
export CASCOR_DEMO_CASCADE_INTERVAL=30    # Add unit every 30 epochs
export CASCOR_DEMO_MAX_HIDDEN_UNITS=8     # Maximum 8 cascade units

# Logging
export CASCOR_DEBUG=1                     # Enable debug logging

# Paths (with environment variable expansion)
export CASCOR_BACKEND_PATH=/path/to/cascor
export CASCOR_DATA_DIR=${HOME}/data/cascor
export CASCOR_LOG_DIR=${HOME}/logs/cascor
```

### Method 2: Configuration File

Edit `conf/app_config.yaml`:

```yaml
demo:
  enabled: true
  update_interval: 0.1
  epoch_duration: 0.05
  cascade_interval: 30
  max_hidden_units: 8

server:
  host: "0.0.0.0"
  port: 8050
  reload: false

paths:
  backend: "../cascor"
  data: "${HOME}/data/cascor"
  logs: "${HOME}/logs/cascor"

debug: true
```

**Environment variable expansion supported:**

- `${VAR}` - Full variable name
- `$VAR` - Short form

### Method 3: Launch Script

The `./demo` script sets defaults automatically:

```bash
#!/usr/bin/env bash
# util/run_demo.bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Activate conda environment
eval "$(/opt/miniforge3/bin/conda shell.bash hook)"
conda activate JuniperPython

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

Uses all defaults from `conf/app_config.yaml`.

### Scenario 2: Custom Port

```bash
export CASCOR_SERVER_PORT=8051
./demo
```

Overrides port to 8051, keeps other defaults.

### Scenario 3: Faster Training Simulation

```bash
export CASCOR_DEMO_EPOCH_DURATION=0.01    # 10ms per epoch (5x faster)
export CASCOR_DEMO_UPDATE_INTERVAL=0.05   # Update every 50ms
./demo
```

Speeds up simulation for rapid testing.

### Scenario 4: Extended Training

```bash
export CASCOR_DEMO_MAX_HIDDEN_UNITS=16    # Allow up to 16 cascade units
export CASCOR_DEMO_CASCADE_INTERVAL=50    # Add unit every 50 epochs
./demo
```

Longer training with more cascade units.

### Scenario 5: Debug Mode

```bash
export CASCOR_DEBUG=1
./demo
```

Enables verbose logging to `logs/system.log`.

### Scenario 6: Remote Access

```bash
export CASCOR_SERVER_HOST=0.0.0.0
export CASCOR_SERVER_PORT=8050
./demo
```

Allows access from other machines on the network.

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
export CASCOR_DEBUG=1
./demo
```

Check `logs/system.log` for loaded configuration:

```bash
2025-11-03 10:00:00 [INFO] Configuration loaded: demo.enabled=True
2025-11-03 10:00:00 [INFO] Configuration loaded: server.port=8050
2025-11-03 10:00:00 [INFO] Configuration loaded: demo.update_interval=0.1
```

### Test Configuration Override

```python
# From Python console (for testing)
from config_manager import ConfigManager

config = ConfigManager()
print(config.get("demo.enabled"))           # True
print(config.get("server.port"))            # 8050
print(config.get("demo.update_interval"))   # 0.1
```

## Environment Reset

To reset to defaults:

```bash
# Unset all CASCOR_* environment variables
unset $(env | grep '^CASCOR_' | cut -d= -f1)

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

# Set environment variables
ENV CASCOR_DEMO_MODE=1
ENV CASCOR_SERVER_HOST=0.0.0.0
ENV CASCOR_SERVER_PORT=8050

# Launch demo mode
CMD ["conda", "run", "-n", "JuniperPython", "python", "src/main.py"]
```

```bash
# Build and run
docker build -t cascor-demo .
docker run -p 8050:8050 cascor-demo
```

## Troubleshooting

### Issue: Environment variable not recognized

**Symptom:** `CASCOR_DEMO_MODE=1` has no effect

**Solution:** Verify variable format `CASCOR_<SECTION>_<KEY>`:

```bash
# Correct
export CASCOR_DEMO_MODE=1

# Wrong (underscore instead of section separator)
export CASCOR_DEMO_MODE=1  # Actually this is correct
export DEMO_MODE=1          # Wrong (missing CASCOR_ prefix)
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

**Last Updated:** January 29, 2026
**Version:** v0.25.0

**See Also:**

- [AGENTS.md](../../AGENTS.md) - Development guide
- [README.md](../../README.md) - Project overview
