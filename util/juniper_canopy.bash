#!/usr/bin/env bash
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       0.1.4 (0.7.3)
# File Name:     juniper_canopy.bash
# File Path:     <Project>/<Sub-Project>/<Application>/util/
#
# Date:          2025-10-11
# Last Modified: 2026-01-19
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#    This script performs initial environment setup and launches the Frontend Application to monitor the current Cascade Correlation Neural Network prototype
#    including training, state, and architecture for monitoring and diagnostics.
#
#####################################################################################################################################################################################################
# Notes:
#     This script is assumed to be located in a **/<Project Name>/utils/ dir for the Current Project
#     Languages are all assumed to be installed in and accessible from conda
#
#     Key Constants Defined in the juniper_canopy.conf file
#         PROJECT_NAME
#         PROTOTYPE_PROJECT == TRUE|FALSE
#         CURRENT_PROJECT
#         PROJECT_PATH
#         HOME_DIR
#         MAIN_FILE
#         LANGUAGE_NAME
#         LANGUAGE_PATH
#         PYTHON, JAVASCRIPT, RUST, JAVA, RUBY, NODE, GO, CPP, C, R
#         CASCOR_NAME
#         CASCOR_PATH
#         CASCOR
#
########################################################################################################)#############################################################################################
# References:
#
#####################################################################################################################################################################################################
# TODO:
#
#     Create a Bash script template from the implementation of this script using the sourced, common config file.
#
#     libgomp: Invalid value for environment variable OMP_NUM_THREADS
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
# Validate Environment
#####################################################################################################################################################################################################
log_info "Validating Environment: Conda Active Env: \"${CONDA_ACTIVE_ENV}\", Expected Conda Env: \"${CONDA_ENV_NAME}\""
log_info "Validating Environment: Python Version: ${PYTHON_VERSION}, Expected Python Version: ${LANGUAGE_VERS}"
if [[ "${CONDA_ACTIVE_ENV}" != "${CONDA_ENV_NAME}" ]]; then
    log_error "Active Conda Environment is Wrong: Found: \"${CONDA_ACTIVE_ENV}\", Expected: \"${CONDA_ENV_NAME}\""
elif [[ "${PYTHON_VERSION}" != "${LANGUAGE_VERS}" ]]; then
    log_error "Python Version is Wrong: Found: ${PYTHON_VERSION}, Expected: ${LANGUAGE_VERS}"
else
    log_info "Successfully Validated Env: Python Version: ${PYTHON_VERSION}, Conda Environment: ${CONDA_ACTIVE_ENV}"
fi


#####################################################################################################################################################################################################
# Ensure JuniperData service URL is set
#####################################################################################################################################################################################################
export JUNIPER_DATA_URL="${JUNIPER_DATA_URL:-http://localhost:8100}"
log_info "JuniperData URL: ${JUNIPER_DATA_URL}"


#####################################################################################################################################################################################################
# Launch the Main function of the Juniper Canopy Application
#####################################################################################################################################################################################################
if [[ "${DEMO_MODE}" == "${TRUE}" ]]; then
    log_info "Launching ${CURRENT_PROJECT} in Demo Mode with simulated CasCor backend"
    log_debug "Launch Demo Mode: ${LAUNCH_DEMO_MODE}"
    ${LAUNCH_DEMO_MODE}
else
    log_trace "Launching ${CURRENT_PROJECT} in Main Mode with real CasCor backend"
    # Ensure JuniperData service is available
    JUNIPER_DATA_HEALTH="${JUNIPER_DATA_URL}/v1/health/ready"
    log_info "Checking JuniperData service at ${JUNIPER_DATA_URL}"
    JUNIPER_DATA_PID=""
    if ! curl -sf "${JUNIPER_DATA_HEALTH}" > /dev/null 2>&1; then
        log_info "JuniperData not running, attempting auto-start"
        nohup python -m juniper_data --port 8100 > /dev/null 2>&1 &
        JUNIPER_DATA_PID="$!"
        log_info "JuniperData launched with PID: ${JUNIPER_DATA_PID}"
        RETRIES=0
        while [ $RETRIES -lt 15 ]; do
            if curl -sf "${JUNIPER_DATA_HEALTH}" > /dev/null 2>&1; then
                log_info "JuniperData ready"
                break
            fi
            RETRIES=$((RETRIES + 1))
            sleep 1
        done
    fi

    log_trace "pgrep -f \"${CASCOR_PROCESS_NAME}\" 2>/dev/null"
    CASCOR_PIDS=$(pgrep -f "${CASCOR_PROCESS_NAME}" 2>/dev/null)
    log_verbose "Cascor Process Pid: \"${CASCOR_PIDS}\""

    if [[ "${CASCOR_PIDS}" != "" ]]; then
        PID="$(pgrep -f "${CASCOR_PROCESS_NAME}" 2>/dev/null | head -1)"
        log_info "CasCor Backend is already running with pid: ${PID}"
    else
        log_info "CasCor Backend is not running, launching ${CASCOR_NAME} in Main Mode with real CasCor backend: ${CASCOR_MAIN_FILE}"
        log_debug "nohup ${LANGUAGE_PATH} \"${CASCOR_MAIN_FILE}\" > /dev/null 2>&1 &"
        nohup "${LANGUAGE_PATH}" "${CASCOR_MAIN_FILE}" > /dev/null 2>&1 &
        PID="$!"
        log_info "CasCor Backend was launched with pid: ${PID}"
    fi

    # Launch juniper_canopy main function
    log_info "Launching ${CURRENT_PROJECT} in Main Mode with real CasCor backend"
    log_debug "${LANGUAGE_PATH} \"${MAIN_FILE}\""
    ${LANGUAGE_PATH} "${MAIN_FILE}"

    # Kill the CasCor Backend
    log_info "Killing CasCor Backend with pid: ${PID}"
    log_debug "kill -KILL ${PID} && rm -f nohup.out"
    kill -KILL "${PID}" && rm -f nohup.out
    if [ -n "${JUNIPER_DATA_PID}" ]; then
        log_info "Killing JuniperData with pid: ${JUNIPER_DATA_PID}"
        kill "${JUNIPER_DATA_PID}" 2>/dev/null
    fi
fi


log_info "Completed Launch of the Juniper Canopy Application Main function"
exit $(( TRUE ))
