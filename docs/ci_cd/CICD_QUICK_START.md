# CI/CD Quick Start

**Last Updated:** 2026-04-05  
**Time to Complete:** ~5 minutes  
**Version:** 0.26.0  
**Status:** Current

## Prerequisites

- Repository cloned locally
- Python 3.12+ available (`3.14` recommended to mirror default non-matrix jobs)
- `uv` and `pre-commit` installed

```bash
python --version
uv --version
pre-commit --version
```

## 1. Install Local Quality Hooks

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

## 2. Run the Fast CI-Equivalent Test Gates

Run the same marker filters used by `.github/workflows/ci.yml`:

```bash
cd src

# Unit + regression gate (coverage enforced in CI)
python -m pytest \
  -m "not requires_cascor and not requires_server and not slow" \
  tests/unit/ tests/regression/ \
  --verbose \
  --cov=. \
  --cov-report=term-missing

# Integration gate (fast-only subset)
python -m pytest \
  -m "integration and not requires_cascor and not requires_server and not slow" \
  tests/integration \
  --verbose
```

## 3. Validate Documentation Links

```bash
python scripts/check_doc_links.py \
  --exclude templates --exclude history \
  --exclude pull_requests --exclude releases \
  --exclude analysis --exclude fixes --exclude development \
  --exclude CHANGELOG.md \
  --cross-repo skip
```

## 4. If You Changed Dependencies, Refresh the Lockfile

The lockfile freshness gate recompiles with three extras:

```bash
uv pip compile pyproject.toml \
  --extra juniper-data \
  --extra juniper-cascor \
  --extra observability \
  -o requirements.lock
```

## 5. Push and Watch CI

```bash
git push origin <your-branch>
```

Open the PR checks and confirm these gates complete:

- `Pre-commit (Python 3.12/3.13/3.14)`
- `Unit Tests + Coverage (Python 3.12/3.13/3.14)`
- `Integration Tests`
- `Security Scans`
- `Build Distribution`
- `Dependency Documentation`
- `Lockfile Freshness`
- `Documentation Links`
- `Docker Build & Smoke Test`
- `Quality Gate`

## Common Pitfalls

- Dependency update PR passes lockfile-update automation but fails `Lockfile Freshness`:
  Run the lockfile compile command above with `--extra observability`, then commit the result.
- Docs-only change fails CI:
  Run `scripts/check_doc_links.py` locally with the same excludes used in CI.
- Local tests pass but CI fails:
  Re-run on Python `3.14` and use the same marker filters as the workflow.

## Next Steps

- [CI/CD Manual](CICD_MANUAL.md) for end-to-end operator workflows
- [CI/CD Environment Setup](CICD_ENVIRONMENT_SETUP.md) for runner/secrets configuration
- [CI/CD Reference](CICD_REFERENCE.md) for job-level technical details
