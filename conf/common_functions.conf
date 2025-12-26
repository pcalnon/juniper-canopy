#!/usr/bin/env bash
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       0.1.4 (0.7.3)
# File Name:     common_functions.conf
# File Path:     <Project>/<Sub-Project>/<Application>/conf/
#
# Date:          2025-12-22
# Last Modified: 2025-12-25
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#    This config file defines the functions needed by the common_functions.conf initialization config file for the Juniper Project's juniper_canopy prototype
#    Warning:  This Script / Config file is sourced by the common_functions.conf script
#
#####################################################################################################################################################################################################
# Notes:
#     Warning:  This Config file is sourced by the common_functions.conf script which, itself, is sourced by all Juniper Canopy util scripts including the try.bash and get_code_stats.bash scripts
#
#####################################################################################################################################################################################################
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
# Define Debug Constants
#####################################################################################################################################################################################################
export TRUE="0"
export FALSE="1"

# export DEBUG="${TRUE}"
export DEBUG="${FALSE}"


# #####################################################################################################################################################################################################
# # Check if this config file has already been sourced.  Only Source this conf file Once
# #####################################################################################################################################################################################################
if [[ "${JUNIPER_COMMON_FUNCTION_CONF_SOURCED}" != "${TRUE}" ]]; then
    export JUNIPER_COMMON_FUNCTION_CONF_SOURCED="${TRUE}"
else
    log_warning "common_functions.conf already sourced.  Skipping re-source."
    [[ "${DEBUG}" == "${TRUE}" ]] && exit $(( TRUE )) || return $(( TRUE ))
fi

#####################################################################################################################################################################################################
# Define common_functions.conf config file functions needed to validate parent script info
#####################################################################################################################################################################################################
function validate_parent_script() {
    log_debug "Inside function: validate_parent_script \"$1\" \"$2\""
    # shellcheck disable=SC2015
    [[ "$1" != "" ]] && PARENT_SCRIPT="$1" || { PARENT_SCRIPT=""; return $(( TRUE )); }
    [[ "$2" != "" ]] && INVALID_VALUE="$2" || INVALID_VALUE="${BASH_EXT}"
    log_debug "Validating Parent Script Call Info: ${PARENT_SCRIPT}, Ignoring: ${INVALID_VALUE}"
    [[ "${PARENT_SCRIPT}" == "${INVALID_VALUE}" ]] && PARENT_SCRIPT=""
    log_debug "Removed shell reference from Parent Script: \"${PARENT_SCRIPT}\""
    if [[ "${PARENT_SCRIPT}" == "" ]]; then
        log_warning "Parent Script Call Info is empty: \"${PARENT_SCRIPT}\""
        return $(( FALSE ))
    fi
    PARENT_SCRIPT="$(realpath "${PARENT_SCRIPT}")"
    log_debug "Found Parent Script Absolute Path: \"${PARENT_SCRIPT}\""
    [[ ( "${PARENT_SCRIPT}" == "" ) || ( ! -f "${PARENT_SCRIPT}" ) ]] && { log_warning "Invalid Parent Script Call Info: \"${PARENT_SCRIPT}\" does not exist"; return $(( FALSE )); }
    log_debug "Validated Parent Script File at Path: \"${PARENT_SCRIPT}\""
    return $(( TRUE ))
}

function validate_parent_path() {
    log_debug "Validating Parent Path Candidates"
    PARENT_SCRIPT_ARRAY=( "$@" )  # Create an array for easier validation
    (( ${#PARENT_SCRIPT_ARRAY[@]} < PARENT_INFO_COUNT )) && log_warning "Received fewer than expected parent script info candidates to validate: ${#PARENT_SCRIPT_ARRAY[@]} (expected ${PARENT_INFO_COUNT})"
    export PARENT_SCRIPT_PATH=""
    for CHECK in "${PARENT_SCRIPT_ARRAY[@]}"; do
        log_debug "Current Parent Script Candidate Check: \"${CHECK}\""
        validate_parent_script "${CHECK}" "${BASH_EXT}"; SUCCESS="$?"
        log_debug "Validation Result: Returned ${SUCCESS}"
        if [[ "${SUCCESS}" == "${TRUE}" ]]; then
            log_debug "Validated Parent Script Candidate: \"${CHECK}\""
            export PARENT_SCRIPT_PATH="${CHECK}"
            break
        fi
    done
    [[ "${PARENT_SCRIPT_PATH}" == "" ]] && { log_error "Error: Unable to determine Parent Script Path: \"${PARENT_SCRIPT_PATH}\""; set -e; exit $(( FALSE )); }
    log_debug "Successfully Validated the Parent Script Path: \"${PARENT_SCRIPT_PATH}\""
    return  $(( TRUE ))
}

function validate_conf_dir() {
    log_debug "Validating Config Dir using Parent and Project Config Dir Candidates"
    local CONF_DIR_1="$1"
    local CONF_DIR_2="$2"
    if [[ ( ( "${CONF_DIR_1}" == "" ) || ( ! -d "${CONF_DIR_1}" ) ) && ( ( "${CONF_DIR_2}" == "" ) || ( ! -d "${CONF_DIR_2}" ) ) ]]; then
        log_error "Error: Both Conf Dir candidates: \"${CONF_DIR_1}\" and \"${CONF_DIR_2}\" are empty or invalid directories"
        set -e && exit $(( FALSE ))
    elif [[ ( "${CONF_DIR_1}" == "" ) || ( ! -d "${CONF_DIR_1}" ) ]]; then
        export CONF_DIR="${CONF_DIR_2}"
        log_debug "Conf Dir candidate: \"${CONF_DIR_1}\", is empty or invalid, using alternate Conf Dir candidate: \"${CONF_DIR_2}\""
    else
        export CONF_DIR="${CONF_DIR_1}"
        log_debug "Parent Conf Dir: \"${CONF_DIR_1}\" is valid, using Parent Conf Dir"
    fi
    return $(( TRUE ))
}

function validate_conf_file() {
    local CONF_FILE="$1"
    log_debug "Validating Config File: \"${CONF_FILE}\""
    [[ ( "${CONF_FILE}" == "" ) || ( ! -f "${CONF_FILE}" ) ]] && { log_error "Error: Config File: \"${CONF_FILE}\" is empty or does not exist"; set -e && exit $(( FALSE )); }
    log_debug "Successfully Validated Calling Script Primary Config File: \"${CONF_FILE}\""
    return $(( TRUE ))
}


#####################################################################################################################################################################################################
# Export Function Definitions
#####################################################################################################################################################################################################
export -f validate_parent_script
export -f validate_parent_path
export -f validate_conf_dir
export -f validate_conf_file

[[ "${DEBUG}" == "${TRUE}" ]] && exit $(( TRUE )) || return $(( TRUE ))
