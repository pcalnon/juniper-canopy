# juniper-canopy test invocation wrappers.
#
# The default pytest config (pyproject.toml [tool.pytest.ini_options])
# excludes src/tests/ui via --ignore. This Makefile encodes the
# split-invocation pattern that recovers a clean full-suite run:
#
#   make test       — unit + integration + regression (UI excluded)
#   make test-ui    — Playwright UI subsuite only
#   make test-all   — both, in two separate pytest processes
#
# Why two processes: pytest-playwright's session-level browser fixture
# leaks an event loop into the rest of the pytest session, breaking
# every async test that runs after a UI test. Running UI in its own
# pytest invocation avoids the contamination.

PYTEST ?= pytest

.PHONY: test test-ui test-all coverage check-env

test:
	$(PYTEST)

test-ui:
	$(PYTEST) src/tests/ui --override-ini=addopts=

test-all: test test-ui

coverage:  ## Reproduce the CI coverage gate locally (full suite)
	@bash util/run_coverage.bash

check-env:  ## Assert active env + requirements.lock satisfy pyproject juniper-* floors (run in JuniperCanopy1 before serving)
	juniper-env-drift-check --repo-root . --check-lock
