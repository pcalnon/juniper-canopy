#!/usr/bin/env bash

COVERAGE_FAIL_UNDER=80

python -m pytest \
  -m "not requires_cascor and not requires_server and not slow" \
  src/tests/unit/ src/tests/regression/ \
  --verbose \
  --timeout=60 \
  --maxfail=5 \
  --junitxml=reports/junit/junit-unit.xml \
  --cov=src \
  --cov-report=term-missing \
  --cov-report=xml:reports/coverage.xml \
  --cov-report=html:reports/htmlcov \
  --cov-fail-under=${COVERAGE_FAIL_UNDER} \
  2>&1 | tee ./pytest-unit_$(date +%F_%H%M).log
