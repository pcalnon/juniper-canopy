#!/usr/bin/env bash
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       0.1.4 (0.7.3)
# File Name:     random_seed.bash
# File Path:     <Project>/<Sub-Project>/<Application>/util/
#
# Date:          2024-04-01
# Last Modified: 2026-01-03
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#   Call a python script to generate a new, cryptographically secure random value for use as seed in psuedo random functions
#
#####################################################################################################################################################################################################
# Notes:
#   /Users/pcalnon/opt/anaconda3/envs/pytorch_cuda/bin/python
#   /home/pcalnon/anaconda3/envs/pytorch_cuda/bin/python
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


####################################################################################################
# Get the OS name and find active python binary
####################################################################################################
log_trace "Get the OS name and find active python binary"
OS_NAME=$(${OS_NAME_SCRIPT})
log_verbose "OS_NAME: ${OS_NAME}"


#####################################################################################################################################################################################################
# Validate the Local OS
#####################################################################################################################################################################################################
log_trace "Validate the Local OS"
if [[ "${OS_NAME}" == "${OS_LINUX}" ]]; then
    PYTHON_CMD="${HOME}/${CONDA_LINUX}/${PYTHON_LOC}"
    log_verbose "PYTHON_CMD: ${PYTHON_CMD}"
elif [[ "${OS_NAME}" == "${OS_MACOS}" ]]; then
    PYTHON_CMD="${HOME}/${CONDA_MACOS}/${PYTHON_LOC}"
    log_verbose "PYTHON_CMD: ${PYTHON_CMD}"
elif [[ "${OS_NAME}" == "${OS_WINDOWS}" ]]; then
    log_critical "Why the hell are you running ${OS_WINDOWS}???"
else
    log_fatal "Error: You are running an ${OS_UNKNOWN} OS. Cowardly not wading into this crazy."
fi


#####################################################################################################################################################################################################
# Run the Python script to initialize application randomness with a new seed
#####################################################################################################################################################################################################
log_debug "Run the Python script to initialize application randomness with a new seed"
log_trace "Get Python Version"
# shellcheck disable=SC2155
export PYTHON_VER="$(${PYTHON_CMD} --version)"
log_verbose "PYTHON_VER: ${PYTHON_VER}"
log_trace "Call Python Script"
"${PYTHON_CMD}" "${RANDOM_SEED}"; SUCCESS="$?"
log_trace "Check Python Script Result"
[[ "${SUCCESS}" == "${TRUE}" ]] && echo -ne "\nSuccess!!  " || echo -ne "\nFailure :(  "
log_info "Python Script: ${NEW_RANDOM_SEED_FILE_NAME}, returned: ${SUCCESS}"

exit $(( SUCCESS ))
