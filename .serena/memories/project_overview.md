# Juniper Canopy - Project Overview

## Purpose

Juniper Canopy is a **real-time monitoring and diagnostic frontend** for the Cascade Correlation Neural Network (CasCor) prototype. It provides:

- Real-time network training visualization
- Interactive decision boundary plotting
- Network topology visualization with dynamic updates
- Training metrics and performance statistics
- Demo mode for development without backend connection
- Standardized WebSocket message protocol

## Tech Stack

- **Python**: 3.11+ (target 3.14)
- **Backend**: FastAPI (ASGI)
- **Frontend**: Dash (Plotly)
- **Real-time**: WebSockets
- **Testing**: pytest with coverage
- **Code Quality**: Black, isort, Flake8, MyPy, Bandit
- **CI/CD**: GitHub Actions

## Key Components

1. **FastAPI Backend** (`src/main.py`) - RESTful API endpoints, WebSocket endpoints
2. **Dash Dashboard** (`src/frontend/dashboard_manager.py`) - Interactive web UI
3. **Demo Mode** (`src/demo_mode.py`) - Simulated training for development
4. **WebSocket Manager** (`src/communication/websocket_manager.py`) - Connection management
5. **Config Manager** (`src/config_manager.py`) - Configuration hierarchy
6. **Constants** (`src/canopy_constants.py`) - Centralized constants

## Configuration Hierarchy

1. **Environment Variables** (CASCOR_*) - Highest priority
2. **YAML Configuration** (conf/app_config.yaml)
3. **Constants Module** (src/canopy_constants.py) - Defaults

## Environment

- **Conda Environment**: JuniperPython (`/opt/miniforge3/envs/JuniperPython`)
- **Python Interpreter**: `/opt/miniforge3/envs/JuniperPython/bin/python`
