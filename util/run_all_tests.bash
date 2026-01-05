#!/usr/bin/env bash
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       0.1.4 (0.7.3)
# File Name:     run_all_tests.bash
# File Path:     <Project>/<Sub-Project>/<Application>/util/
#
# Date:          2025-10-11
# Last Modified: 2026-01-03
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#
#####################################################################################################################################################################################################
# Notes:
#
########################################################################################################)#############################################################################################
# References:
#
#####################################################################################################################################################################################################
# TODO :
#
#####################################################################################################################################################################################################
# COMPLETED:
#
#####################################################################################################################################################################################################


#####################################################################################################################################################################################################
# Source script config file
#####################################################################################################################################################################################################
set -o functrace
# shellcheck disable=SC2155
export PARENT_PATH_PARAM="$(realpath "${BASH_SOURCE[0]}")" && INIT_CONF="$(dirname "$(dirname "${PARENT_PATH_PARAM}")")/conf/init.conf"
# shellcheck disable=SC2015,SC1090
[[ -f "${INIT_CONF}" ]] && source "${INIT_CONF}" || { echo "Init Config File Not Found. Unable to Continue."; exit 1; }


#####################################################################################################################################################################################################
# Verify Operating System
#####################################################################################################################################################################################################
log_trace "Verify Operating System"
# trunk-ignore(shellcheck/SC2015)
# trunk-ignore(shellcheck/SC2312)
# shellcheck disable=SC2015
[[ "$(uname)" == "${OS_NAME_LINUX}" ]]  && export HOME_DIR="/home/${USERNAME}" || { [[ "$(uname)" == "${OS_NAME_MACOS}"  ]] && export HOME_DIR="/Users/${USERNAME}" || { echo "Error: Invalid OS Type! Exiting..."  && set -e && exit 1; }; }
log_verbose "HOME_DIR: ${HOME_DIR}"
cd "${PROJ_DIR}"
log_verbose "Current Directory: $(pwd)"


#####################################################################################################################################################################################################
# Run Tests with designated reports
#####################################################################################################################################################################################################
log_trace "Run Tests with designated reports"
if [[ "${COVERAGE_REPORT}" == "${FALSE}" ]]; then
    RUN_TESTS_NO_COV_RPT="pytest -v src/tests"
    log_verbose "RUN_TESTS_NO_COV_RPT: ${RUN_TESTS_NO_COV_RPT}"
    eval "${RUN_TESTS_NO_COV_RPT}"; SUCCESS="$?"
elif [[ "${COVERAGE_REPORT}" == "${TRUE}" ]]; then
    RUN_TESTS_WITH_COV_RPT="pytest -v ./src/tests \
        --cov=src \
        --cov-report=xml:src/tests/reports/coverage.xml \
        --cov-report=term-missing \
        --cov-report=html:src/tests/reports/coverage \
        --junit-xml=src/tests/reports/junit/results.xml \
        --continue-on-collection-errors \
    "
    log_verbose "RUN_TESTS_WITH_COV_RPT: ${RUN_TESTS_WITH_COV_RPT}"
    eval "${RUN_TESTS_WITH_COV_RPT}"; SUCCESS="$?"
else
    log_critical "Coverage Report flag has an Invalid Value"
fi
log_info "Running the Juniper Canopy project's Full Test Suite $( [[ "${SUCCESS}" == "${TRUE}" ]] && echo "Succeeded!" || echo "Failed." )"

exit $(( SUCCESS ))
