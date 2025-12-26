#!/usr/bin/env bash
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       0.1.4 (0.7.3)
# File Name:     test_common.conf
# File Path:     <Project>/<Sub-Project>/<Application>/conf/
#
# Date:          2025-10-11
# Last Modified: 2025-12-25
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
# Define Script Constants
#####################################################################################################################################################################################################
export TRUE="0"
export FALSE="1"

# export DEBUG="${FALSE}"
export DEBUG="${TRUE}"


#####################################################################################################################################################################################################
# Only Source this conf file Once
#####################################################################################################################################################################################################
if [[ "${TEST_COMMON_SOURCED}" != "${TRUE}" ]]; then
    export TEST_COMMON_SOURCED="${TRUE}"
else
    log_warning "test_common_conf.bash already sourced.  Skipping re-source."
    [[ "${DEBUG}" == "${TRUE}" ]] && exit $(( TRUE )) || return $(( TRUE ))
fi


# #####################################################################################################################################################################################################
# # Source script config file
# #####################################################################################################################################################################################################
# set -o functrace

# # shellcheck disable=SC2155
# export PARENT_PATH_PARAM="$(realpath "${BASH_SOURCE[0]}")"
# # shellcheck disable=SC1091
# source "conf/init.conf"; SUCCESS="$?"

# # Verify configuration succeeded
# # shellcheck disable=SC1091
# [[ "${SUCCESS}" != "0" ]] && { source "conf/config_fail.conf"; log_error "${SUCCESS}" "${PARENT_PATH_PARAM}" "../conf/init.conf" "${LINENO}" "${LOG_FILE}"; set -e && exit 1; }
# log_debug "Successfully Configured Current Script: $(basename "${PARENT_PATH_PARAM}"), by Sourcing the Init Config File: ${INIT_CONF}, Returned: \"${SUCCESS}\""


# #####################################################################################################################################################################################################
# # Define Testing script for common.conf file
# #####################################################################################################################################################################################################
# TEST_COMMON_CONF_FILE_NAME="$(basename "$(realpath "$0")")"


# #####################################################################################################################################################################################################
# # Define Logging Functions
# #####################################################################################################################################################################################################
# function log_debug() {
#     [[ "${DEBUG}" == "${TRUE}" ]] && echo -ne "${TEST_COMMON_CONF_FILE_NAME}: ($(date +%F_%T)): [DEBUG] ${*}\n"
# }

# function log_info() {
#     echo -ne "${TEST_COMMON_CONF_FILE_NAME}: ($(date +%F_%T)): [INFO] ${*}\n"
# }


#####################################################################################################################################################################################################
# Define Test Common Conf file script constants
#####################################################################################################################################################################################################
log_debug "Test Common Conf File Name: ${TEST_COMMON_CONF_FILE_NAME}"

TEST_COMMON_CONF_FILE="$(realpath "$0")"                       && log_debug "Test Common Conf File: ${TEST_COMMON_CONF_FILE}"

CONFIG_FILE_SUFFIX="conf"                                      && log_debug "Config File Suffix: ${CONFIG_FILE_SUFFIX}"
COMMON_CONF_FILE_NAME="common.${CONFIG_FILE_SUFFIX}"           && log_debug "Common Conf File Name: ${COMMON_CONF_FILE_NAME}"

COMMON_CONF_DIR="$(dirname "${TEST_COMMON_CONF_FILE}")"        && log_debug "Common Conf Dir: ${COMMON_CONF_DIR}"
COMMON_CONF_FILE="${COMMON_CONF_DIR}/${COMMON_CONF_FILE_NAME}" && log_debug "Common Conf File: ${COMMON_CONF_FILE}"


#####################################################################################################################################################################################################
# Define Config file constants
#####################################################################################################################################################################################################
CALLING_SCRIPT_NAME_DEFAULT="try.bash"                                     && log_debug "Calling Script Name Default: ${CALLING_SCRIPT_NAME_DEFAULT}"
PROTOTYPE_NAME_DEFAULT="juniper_canopy"                                    && log_debug "Prototype Name Default: ${PROTOTYPE_NAME_DEFAULT}"
PROJECT_NAME_DEFAULT="Juniper"                                             && log_debug "Project Name Default: ${PROJECT_NAME_DEFAULT}"
CONFIG_FILE_NAME_DEFAULT="${PROTOTYPE_NAME_DEFAULT}.${CONFIG_FILE_SUFFIX}" && log_debug "Config File Name Default: ${CONFIG_FILE_NAME_DEFAULT}"


#####################################################################################################################################################################################################
# Get and Validate Input Parameters
#####################################################################################################################################################################################################
CALLING_SCRIPT_NAME="$( [[ "${1}" == "" ]] && echo "${CALLING_SCRIPT_NAME_DEFAULT}" || echo "${1}" )" && shift && log_debug "Calling Script Name: ${CALLING_SCRIPT_NAME}"
PROTOTYPE_NAME="$( [[ "${1}" == "" ]]      && echo "${PROTOTYPE_NAME_DEFAULT}"      || echo "${1}" )" && shift && log_debug "Prototype Name: ${PROTOTYPE_NAME}"
PROJECT_NAME="$( [[ "${1}" == "" ]]        && echo "${PROJECT_NAME_DEFAULT}"        || echo "${1}" )" && shift && log_debug "Project Name: ${PROJECT_NAME}"
CONFIG_FILE_NAME="$( [[ "${1}" == "" ]]    && echo "${CONFIG_FILE_NAME_DEFAULT}"    || echo "${1}" )" && shift && log_debug "Config File Name: ${CONFIG_FILE_NAME}"


#####################################################################################################################################################################################################
# Define common.conf file Input Parameter constants
#####################################################################################################################################################################################################
CALLING_SCRIPT_NAME_PARAM="${CALLING_SCRIPT_NAME}" && log_debug "Calling Script Name Param: ${CALLING_SCRIPT_NAME_PARAM}"
PROTOTYPE_NAME_PARAM="${PROTOTYPE_NAME}"           && log_debug "Prototype Name Param: ${PROTOTYPE_NAME_PARAM}"
PROJECT_NAME_PARAM="${PROJECT_NAME}"               && log_debug "Project Name Param: ${PROJECT_NAME_PARAM}"
PROTOTYPE_CONF_FILE="${CONFIG_FILE_NAME}"          && log_debug "Prototype Conf File: ${PROTOTYPE_CONF_FILE}"


#####################################################################################################################################################################################################
# Test the Common.conf config file
#####################################################################################################################################################################################################
log_info "Testing ${COMMON_CONF_FILE}\n\t${CALLING_SCRIPT_NAME_PARAM}\n\t${PROTOTYPE_NAME_PARAM}\n\t${PROJECT_NAME_PARAM}\n\t${PROTOTYPE_CONF_FILE}"
${COMMON_CONF_FILE} "${CALLING_SCRIPT_NAME_PARAM}" "${PROTOTYPE_NAME_PARAM}" "${PROJECT_NAME_PARAM}" "${PROTOTYPE_CONF_FILE}"
log_info "Testing ${COMMON_CONF_FILE} Returned: \"$?\" for inputs:\n\t${CALLING_SCRIPT_NAME_PARAM}\n\t${PROTOTYPE_NAME_PARAM}\n\t${PROJECT_NAME_PARAM}\n\t${PROTOTYPE_CONF_FILE}"
