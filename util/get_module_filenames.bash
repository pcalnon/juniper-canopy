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
# Last Modified: 2026-01-02
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
# shellcheck disable=SC2155
export PARENT_PATH_PARAM="$(realpath "${BASH_SOURCE[0]}")" && INIT_CONF="$(dirname "$(dirname "${PARENT_PATH_PARAM}")")/conf/init.conf"
# shellcheck disable=SC2015,SC1090
[[ -f "${INIT_CONF}" ]] && source "${INIT_CONF}" || { echo "Init Config File Not Found. Unable to Continue."; exit 1; }


#######################################################################################################################################################################################
# Define usage function for help and error messages
#######################################################################################################################################################################################
function usage() {
    local exit_code="${1:-0}"
    local msg="${2:-}"

    [[ -n "${msg}" ]] && printf '%s\n' "${msg}" >&2

    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Get module filenames from the source directory.

Options:
    -f, --full [true|false]   Print full paths instead of just filenames
    -h, --help                Show this help and exit

Examples:
    $(basename "$0")              # List module filenames only
    $(basename "$0") --full 0     # List full paths
EOF

    exit "${exit_code}"
}


#######################################################################################################################################################################################
# Process Script's Command Line Argument(s)
#######################################################################################################################################################################################
log_debug "Process Script's Command Line Argument(s)"
while [[ "$1" != "" ]]; do
    log_debug "Current Param Flag: $1"
    case $1 in
        "${HELP_SHORT}" | "${HELP_LONG}")
            usage "${TRUE}"
        ;;
        "${OUTPUT_SHORT}" | "${OUTPUT_LONG}")
            shift
            PARAM="$1"
            log_debug "Current Param Value: ${PARAM}"
            log_debug "Lowercase: ${PARAM,,*}"
            log_debug "Uppercase: ${PARAM^^}"
            PARAM="${PARAM^^}"
            if [[ "${PARAM}" == "${TRUE}" || "${PARAM}" == "0" ]]; then
                FULL_OUTPUT="${TRUE}"
            fi
        ;;
        *)
            usage "${FALSE}" "Error: Invalid command line params: \"${*}\"\n"
        ;;
    esac
    shift
done


####################################################################################################
# Get list of project modules
####################################################################################################
log_debug "Get list of project modules"
while read -r MODULE_PATH; do
    if [[ "${FULL_OUTPUT}" == "${TRUE}" ]]; then
        echo "${MODULE_PATH}"
    else
        FILENAME="${MODULE_PATH//*\/}"
        echo "${FILENAME}"
    fi
done<<< "$(find "${SRC_DIR}" \( -name "${MODULE_EXT}" ! -name "${INIT_FILE_NAME}" ! -name "${TEST_FILE_NAME}" \) )"

exit $(( TRUE ))
