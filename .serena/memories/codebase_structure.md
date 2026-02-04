# Codebase Structure

## Root Directory

```text
juniper_canopy/
├── conf/                         # Configuration & infrastructure
│   ├── app_config.yaml           # Main application config
│   ├── conda_environment.yaml    # Conda env spec
│   ├── requirements.txt          # Pip dependencies
│   ├── Dockerfile                # Container image
│   ├── docker-compose.yaml       # Local stack
│   └── logging_config.yaml       # Logging configuration
├── data/                         # Datasets for training/testing
├── docs/                         # Reference & subsystem documentation
│   ├── api/                      # API-level docs
│   ├── cascor/                   # CasCor backend integration docs
│   ├── ci_cd/                    # CI/CD pipeline documentation
│   ├── testing/                  # Testing guides
│   └── history/                  # Archived documentation
├── images/                       # Generated images/screenshots
├── logs/                         # Log files (runtime)
├── notes/                        # Development notes
├── reports/                      # Test coverage and CI reports
├── src/                          # Source code (see below)
├── util/                         # Utility scripts (bash)
├── demo                          # Root-level demo launcher
├── conftest.py                   # Root pytest config
├── pyproject.toml                # Python project config
├── AGENTS.md                     # Developer guide
└── CLAUDE.md                     # Symlink to AGENTS.md
```

## Source Code (src/)

```text
src/
├── backend/                      # CasCor backend integration & adapters
├── communication/                # WebSocket management & protocol
│   └── websocket_manager.py      # WebSocket connection management
├── frontend/                     # Dash dashboard components
│   ├── components/               # Individual UI components
│   └── dashboard_manager.py      # Main dashboard manager
├── logger/                       # Logging system
├── tests/                        # Test suite
│   ├── unit/                     # Unit tests (fast, no external deps)
│   ├── integration/              # Integration tests
│   ├── regression/               # Regression tests
│   ├── performance/              # Performance/benchmark tests
│   ├── fixtures/                 # Additional test fixtures
│   ├── mocks/                    # Mock implementations
│   └── helpers/                  # Test utility functions
├── config_manager.py             # Configuration management
├── canopy_constants.py           # Central constants
├── demo_mode.py                  # Demo mode simulation
└── main.py                       # FastAPI + Dash application entrypoint
```

## Key Files

- `src/main.py` - Application entrypoint (FastAPI + Dash)
- `src/demo_mode.py` - Demo mode simulation
- `src/config_manager.py` - Configuration management with hierarchy
- `src/canopy_constants.py` - Centralized constants
- `src/communication/websocket_manager.py` - WebSocket management
- `src/frontend/dashboard_manager.py` - Dash dashboard
- `conf/app_config.yaml` - Main configuration file
- `conftest.py` - Root pytest configuration
- `src/tests/conftest.py` - Test fixtures and configuration
