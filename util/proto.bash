#!/usr/bin/env bash
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       0.1.4 (0.7.3)
# File Name:     proto.bash
# File Path:     <Project>/<Sub-Project>/<Application>/util/
#
# Date:          2025-10-11
# Last Modified: 2026-01-03
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#     This script performs the following actions for the current Project:
#
#         1.  Applies the cargo linter to the source files
#         2.  Builds the current project with the debug target
#         3.  Sets the expected Environment Variables for the Application
#         4.  Adds the expected command line arguments
#         5.  Executes the project's binary
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
# Initialize script by sourcing the init_conf.bash config file
#####################################################################################################################################################################################################
set -o functrace
# shellcheck disable=SC2155
export PARENT_PATH_PARAM="$(realpath "${BASH_SOURCE[0]}")" && INIT_CONF="$(dirname "$(dirname "${PARENT_PATH_PARAM}")")/conf/init.conf"
# shellcheck disable=SC2015,SC1090
[[ -f "${INIT_CONF}" ]] && source "${INIT_CONF}" || { echo "Init Config File Not Found. Unable to Continue."; exit 1; }


#####################################################################################################
# Specify the Python script to run:
####################################################################################################
log_trace "Read Command line params to Specify the Python script to run"
PARAMS="${*}"


####################################################################################################
# Update the Python Path for the script
####################################################################################################
log_trace "Update the Python Path for the script"
PATH_DEL=":"
PATH_FOUND="$(echo "${PYTHONPATH}" | grep "${SOURCE_DIR}")"
if [[ "${PATH_FOUND}" == "" ]]; then
    [[ ( "${PYTHONPATH}" == "" ) || ( "${PYTHONPATH: -1}" == "${PATH_DEL}" ) ]] && PATH_DEL=""
fi
export PYTHONPATH="${PYTHONPATH}${PATH_DEL}${SOURCE_DIR}"


####################################################################################################
# Display Environment Values
####################################################################################################
log_debug "Display Environment Values"
log_info "Base Dir: ${BASE_DIR}"
log_info "Current OS: ${CURRENT_OS}"
log_info "Python: ${PYTHON} (ver: $(${PYTHON} --version))"
log_info "Python Path: ${PYTHONPATH}"
log_info "Python Script: ${PYTHON_SCRIPT}"
log_info " "


####################################################################################################
# Execute Python script
####################################################################################################
log_trace "Execute Python script"
log_debug "time ${PYTHON} ${PYTHON_SCRIPT} ${PARAMS}"
time ${PYTHON} "${PYTHON_SCRIPT}" "${PARAMS}"

exit $(( TRUE ))
