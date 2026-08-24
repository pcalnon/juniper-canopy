# CI/CD Quick Start

**Last Updated:** 2026-08-24  
**Time to Complete:** ~5 minutes  
**Version:** 0.27.0  
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

---

## 3. Trigger CI

```bash
uv pip compile pyproject.toml \
  --extra juniper-data \
  --extra juniper-cascor \
  --extra observability \
  -o /tmp/requirements.lock.check
tail -n +3 requirements.lock > /tmp/lock_body
tail -n +3 /tmp/requirements.lock.check > /tmp/check_body
diff -u /tmp/lock_body /tmp/check_body
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
- `Analyze (python)` (CodeQL; standalone workflow, required)
- `Sequence Safety` and `Guard PR base branch` (standalone required checks)

`Quality Gate` does **not** include CodeQL. A green Quality Gate with a red `Analyze (python)` is not merge-safe.

## Common Pitfalls

- Dependency update PR passes lockfile-update automation but fails `Lockfile Freshness`:
  Run the lockfile compile command above with `--extra observability`, then commit the result.
- Docs-only change fails CI:
  Run `scripts/check_doc_links.py` locally with the same excludes used in CI.
- Local tests pass but CI fails:
  Re-run on Python `3.14` and use the same marker filters as the workflow.
- Dependabot `ci: bump the codeql-action group` PR looks like a CodeQL-only change but also edits `ci.yml`:
  The group pattern `github/codeql-action*` covers `init` / `autobuild` / `analyze` **and** `upload-sarif` (Bandit SARIF). Review both files; keep the SHA comments in lockstep.
- Waiting only on `Security Scans` (Bandit / pip-audit / Gitleaks) for a SAST signal:
  Semantic CodeQL is `Analyze (python)` from `.github/workflows/codeql.yml`.

## Next Steps

- [CI/CD Manual](CICD_MANUAL.md) for end-to-end operator workflows
- [CI/CD Environment Setup](CICD_ENVIRONMENT_SETUP.md) for runner/secrets configuration
- [CI/CD Reference](CICD_REFERENCE.md) for job-level technical details
