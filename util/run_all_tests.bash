#!/usr/bin/env bash

TRUE=0
FALSE=1

COVERAGE_REPORT="${TRUE}"
# COVERAGE_REPORT="${FALSE}"

export ASCOR_BACKEND_AVAILABLE=0
export RUN_SERVER_TESTS=1
export ENABLE_DISPLAY_TESTS=1
export ENABLE_SLOW_TESTS=1

OS_NAME_LINUX="Linux"
OS_NAME_MACOS="Darwin"

USERNAME="$(whoami)"

# trunk-ignore(shellcheck/SC2015)
# trunk-ignore(shellcheck/SC2312)
[[ "$(uname)" == "${OS_NAME_LINUX}" ]]  && HOME_DIR="/home/${USERNAME}" || { [[ "$(uname)" == "${OS_NAME_MACOS}"  ]] && HOME_DIR="/Users/${USERNAME}" || { echo "Error: Invalid OS Type! Exiting..."  && set -e && exit 1; }; }

JUNIPER_CANOPY_DIR="${HOME_DIR}/Development/python/JuniperCanopy/juniper_canopy"
cd "${JUNIPER_CANOPY_DIR}"

if [[ "${COVERAGE_REPORT}" == "${FALSE}" ]]; then
    echo "pytest -v src/tests"
    pytest -v src/tests
elif [[ "${COVERAGE_REPORT}" == "${TRUE}" ]]; then
    # echo "pytest -v ./src/tests --cov=. --cov-report=term-missing"
    # pytest -v ./src/tests --cov=. --cov-report=term-missing
    #     --html=src/tests/reports/test_report.html \n \
    #     --self-contained-html \n \

    echo -ne " \
    pytest -v ./src/tests \n \
        --cov=src \n \
        --cov-report=xml:src/tests/reports/coverage.xml \n \
        --cov-report=term-missing \n \
        --cov-report=html:src/tests/reports/coverage \n \
        --junit-xml=src/tests/reports/junit/results.xml \n \
        --continue-on-collection-errors \n \
        \n"

    pytest -v ./src/tests \
        --cov=src \
        --cov-report=xml:src/tests/reports/coverage.xml \
        --cov-report=term-missing \
        --cov-report=html:src/tests/reports/coverage \
        --junit-xml=src/tests/reports/junit/results.xml \
        --continue-on-collection-errors \

        # --html=src/tests/reports/test_report.html \
        # --self-contained-html \

else
    echo "Coverate Report flag has an Invalid Value"
    exit 1
fi

echo "Running the Juniper Canopy project's Full Test Suite $( [[ "$?" == "${TRUE}" ]] && echo "Succeeded!" || echo "Failed." )"
exit 0
