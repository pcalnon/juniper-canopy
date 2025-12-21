#!/usr/bin/env bash
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       1.0.0
# File Name:     get_module_filenames.bash
# File Path:     <Project>/<Sub-Project>/<Application>/util/
#
# Date:          2025-12-03
# Last Modified: 2025-12-19
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#     This script collects and displays useful stats about the code base of the Juniper python project
#
#####################################################################################################################################################################################################
# Notes:
#
#####################################################################################################################################################################################################
# References:
#
#     SCRIPT_PATH="$(realpath "${BASH_SOURCE[0]}")"
#     CONF_PATH="$(dirname "$(dirname "${SCRIPT_PATH}")")/conf"
#     CONF_FILENAME="$(basename -s ".bash" "${SCRIPT_PATH}").conf"
#     CONF_FILE="${SCRIPT_PATH}/${SCRIPT_FILENAME}"
#
#     CONF_PATH="$(dirname "$(dirname "$(realpath "${BASH_SOURCE[0]}")")")/conf"
#     CONF_FILENAME="$(basename -s ".bash" "$(realpath "${BASH_SOURCE[0]}")").conf"
#     CONF_FILE="${CONF_PATH}/${CONF_FILENAME}"
#
#     CONF_FILE="$(dirname "$(dirname "$(realpath "${BASH_SOURCE[0]}")")")/conf/$(basename -s ".bash" "$(realpath "${BASH_SOURCE[0]}")").conf"
#
#     source "${CONF_FILE}";  SUCCESS="$?"
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
export PARENT_PATH_PARAM="$(realpath "${BASH_SOURCE[0]}")" && INIT_CONF="../conf/init.conf"
[[ -f "${INIT_CONF}" ]] && source "${INIT_CONF}" || { echo "Init Config File Not Found. Unable to Continue."; exit 1; }


#######################################################################################################################################################################################
# Process Script's Command Line Argument(s)
#######################################################################################################################################################################################
log_debug "Process Script's Command Line Argument(s)"
while [[ "$1" != "" ]]; do
    log_debug "Current Param Flag: $1"
    case $1 in
        ${HELP_SHORT} | ${HELP_LONG})
            usage 1
        ;;
        ${OUTPUT_SHORT} | ${OUTPUT_LONG})
            shift; PARAM="$1"
            log_debug "Current Param Value: ${PARAM}"
            log_debug "Lowercase: ${PARAM,,*}"
            log_debug "Uppercase: ${PARAM^^}"
            PARAM="${PARAM^^}"
            if [[ "${PARAM}" == "${TRUE}" || "${PARAM}" == "0" ]]; then
                FULL_OUTPUT="${TRUE}"
            fi
        ;;
        *)
            usage 1 "Error: Invalid command line params: \"${@}\"\n"
        ;;
    esac
done


####################################################################################################
# Get list of project modules
####################################################################################################
log_debug "Get list of project modules"
for MODULE_PATH in $(find "${SRC_DIR}" \( -name "${MODULE_EXT}" ! -name "${INIT_FILE_NAME}" ! -name "${TEST_FILE_NAME}" \) ); do
    if [[ ${FULL_OUTPUT} == "${TRUE}" ]]; then
        echo "${MODULE_PATH}"
    else
        FILENAME="${MODULE_PATH//*\/}"
        echo "${FILENAME}"
    fi
echo "get_module_filenames.bash -26"
