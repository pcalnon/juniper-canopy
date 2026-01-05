#!/usr/bin/env bash
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       1.0.0
# File Name:     get_file_todo.bash
# File Path:     <Project>/<Sub-Project>/<Application>/util/
#
# Date:          2025-12-03
# Last Modified: 2026-01-02
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#     This script returns the number of TODO comments in each file.
#
#####################################################################################################################################################################################################
# Notes:
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

Count TODO comments in a specified file.

Options:
    -s, --search TERM    Search term to count (default: TODO)
    -f, --file PATH      File to search in (required)
    -h, --help           Show this help and exit

Examples:
    $(basename "$0") --search TODO --file src/main.py
    $(basename "$0") -s FIXME -f src/utils.py
EOF

    exit "${exit_code}"
}


#######################################################################################################################################################################################
# Process Script's Command Line Argument(s)
#######################################################################################################################################################################################
while [[ "${1}" != "" ]]; do
    case "${1}" in
        "${HELP_SHORT}" | "${HELP_LONG}")
            usage 0
        ;;
        "${SEARCH_SHORT}" | "${SEARCH_LONG}")
            shift
            PARAM="${1}"
            if [[ "${PARAM}" != "" ]]; then
                SEARCH_TERM="${PARAM}"
            fi
        ;;
        "${FILE_SHORT}" | "${FILE_LONG}")
            shift
            PARAM="${1}"
            if [[ ( "${PARAM}" != "" ) && ( -f "${PARAM}" ) ]]; then
                SEARCH_FILE="${PARAM}"
            else
                usage "${FALSE}" "Error: Received an invalid Search File: \"${PARAM}\"\n"
            fi
        ;;
        *)
            usage "${FALSE}" "Error: Invalid command line params: \"${*}\"\n"
        ;;
    esac
    shift
done


#######################################################################################################################################################################################
# Display instances of a specific search term in the specified source code file
#######################################################################################################################################################################################
log_trace "Display instances of a specific search term in the specified source code file"
[[ ( "${SEARCH_TERM}" == "" ) || ( "${SEARCH_FILE}" == "" ) || ! -f "${SEARCH_FILE}" ]] && usage "${FALSE}" "Error: Missing required parameters. Search Term: \"${SEARCH_TERM}\", Search File: \"${SEARCH_FILE}\"\n"
COUNT="$(grep -ic "${SEARCH_TERM}" "${SEARCH_FILE}")"
echo "${COUNT}"

exit $(( TRUE ))
