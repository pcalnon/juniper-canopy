# Suggested Commands for Juniper Canopy

## Running the Application

```bash
# Run in demo mode (recommended for development)
./demo
# or
./util/juniper_canopy-demo.bash

# Run with uvicorn directly (from src/)
cd src
uvicorn main:app --host 0.0.0.0 --port 8050 --log-level info
```

## Testing

```bash
# Run all tests
cd src
pytest tests/ -v

# Run all tests with coverage
cd src
pytest tests/ --cov=. --cov-report=html --cov-report=term-missing

# Run unit tests only
cd src
pytest tests/unit/ -v

# Run integration tests only
cd src
pytest tests/integration/ -v

# Run by marker
cd src
pytest -m unit -v
pytest -m "not slow and not requires_cascor" -v

# View coverage report
xdg-open reports/coverage/index.html
```

## Code Quality

```bash
# Install pre-commit hooks (one-time setup)
pip install pre-commit
pre-commit install

# Run all pre-commit hooks
pre-commit run --all-files

# Individual tools
black src/
isort src/
flake8 src/ --max-line-length=512
mypy src/ --ignore-missing-imports
```

## Git Operations

```bash
# Standard git commands
git status
git diff
git log --oneline -10
git add <files>
git commit -m "message"
```

## System Utilities

```bash
# Linux standard commands
ls -la
find . -name "*.py"
grep -r "pattern" src/
```

## URLs (when running)

- Dashboard: <http://localhost:8050/dashboard/>
- API Docs: <http://localhost:8050/docs>
- Health Check: <http://localhost:8050/health>
- WebSocket: ws://localhost:8050/ws/training
