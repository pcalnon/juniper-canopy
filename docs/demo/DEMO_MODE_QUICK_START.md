# Demo Mode Quick Start

Get the Juniper Canopy demo running in 60 seconds.

## Launch Demo Mode

```bash
# From project root
./demo

# Or using full script path
./util/run_demo.bash
```

The demo script automatically:

- Activates the JuniperPython conda environment
- Sets `CASCOR_DEMO_MODE=1`
- Launches the application with simulated training

## Access the Dashboard

Once started, open your browser to:

```bash
http://localhost:8050
```

You'll see real-time visualization of:

- **Training Metrics** - Loss and accuracy curves with realistic exponential decay
- **Network Topology** - Dynamic graph showing cascade unit additions (every ~30 epochs)
- **Decision Boundary** - 2D visualization of network learning on spiral dataset
- **Dataset View** - 200-point spiral dataset (2 features, 2 classes)

## Control Training

The dashboard provides real-time controls:

- **Pause/Resume** - Control training flow
- **Reset** - Restart training from epoch 0
- **Stop** - End demo session

## What's Being Simulated

Demo mode simulates a realistic CasCor training run:

- Spiral dataset (200 samples, 2 features, 2 classes)
- Exponential decay loss curve
- Auto-cascade: New hidden unit every 30 epochs (max 8 units)
- Training and validation metrics updated every 100ms
- WebSocket-based real-time updates (<100ms latency)

## Demo vs Production

| Aspect       | Demo Mode                  | Production Mode              |
| ------------ | -------------------------- | ---------------------------- |
| **Backend**  | Simulated in Python        | Real CasCor C++ prototype    |
| **Dataset**  | Fixed spiral (200 samples) | Configurable datasets        |
| **Training** | Deterministic curves       | Real network training        |
| **Launch**   | `./demo`                   | `cd src && python main.py`   |
| **Purpose**  | UI development, testing    | Real neural network training |

## Stop Demo Mode

Press `Ctrl+C` in the terminal to stop cleanly. The demo mode uses thread-safe Events for graceful shutdown.

## Next Steps

- **[Demo Mode Manual](DEMO_MODE_MANUAL.md)** - Complete user guide
- **[Environment Setup](DEMO_MODE_ENVIRONMENT_SETUP.md)** - Configuration details
- **[Technical Reference](DEMO_MODE_REFERENCE.md)** - Implementation details

## Troubleshooting

**Problem:** `ModuleNotFoundError: No module named 'uvicorn'`

**Solution:** Ensure `./demo` script is used (not `python src/main.py` directly). The demo script activates the conda environment.

**Problem:** Dashboard shows "No data available"

**Solution:** Wait 2-3 seconds after launch for demo mode initialization. Check browser console for WebSocket connection status.

**Problem:** Port 8050 already in use

**Solution:** Set custom port:

```bash
export CASCOR_SERVER_PORT=8051
./demo
```

---

**Last Updated:** January 29, 2026
**Version:** v0.25.0

**See Also:**

- [Main README](../../README.md) - Project overview
- [AGENTS.md](../../AGENTS.md) - Development guide
- [CHANGELOG.md](../../CHANGELOG.md) - Recent changes
