#!/usr/bin/env bash
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       0.1.4 (0.7.3)
# File Name:     todo_search.bash
# File Path:     <Project>/<Sub-Project>/<Application>/conf/
#
# Date:          2025-10-11
# Last Modified: 2026-01-02
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#     This script files in the source directory of the current project for a specific search term and then displays the number of files that do and do not contain the search term.
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
# Process Script's Command Line Argument(s)
#####################################################################################################################################################################################################
log_trace "Process Script's Command Line Argument(s)"
if [[ "$1" != "" ]]; then
    if [[ "$1" == "${HELP_SHORT}" || "$1" == "${HELP_LONG}" ]]; then
        usage 0
    else
        SEARCH_TERM="$1"
    fi
else
    if [[ "${DEBUG}" == "${TRUE}" ]]; then
        SEARCH_TERM="${SEARCH_TERM_DEFAULT}"
    else
        usage
    fi
fi


#####################################################################################################################################################################################################
# Sanitize Inputs
#####################################################################################################################################################################################################
log_trace "Sanitizing Input Params for TODO search script"
DASHES="$(echo "${SEARCH_TERM}" | grep -e '^-.*')"
if [[ "${DASHES}" != "" ]]; then
    SEARCH_TERM="\\${SEARCH_TERM}"
    log_debug "Sanitized SEARCH_TERM Input: ${SEARCH_TERM}"
fi


#####################################################################################################################################################################################################
# Search for a specific TODO reference in source code
#####################################################################################################################################################################################################
log_trace "Search for a specific TODO reference in source code"
DONE_COUNT=0
FOUND_COUNT=0
while read -r i; do
    SOURCE_FILE="$(echo "${i}" | grep "\.${SRC_FILE_SUFFIX}\$")"
    if [[ ${SOURCE_FILE} != "" ]]; then
        SOURCE_FILE="$(echo "${SOURCE_FILE}" | grep -v "${INIT_PYTHON_FILE}")"
        if [[ ( ${SOURCE_FILE} != "" ) && ( -f ${SOURCE_FILE} ) ]]; then
            FOUND="$(cat "${SOURCE_FILE}" | grep "${SEARCH_TERM}")"
            if [[ ${FOUND} != "" ]]; then
                FOUND_COUNT="$((FOUND_COUNT + 1))"
                if [[ ( "${DEBUG}" == "${TRUE}" ) || ( "${FULL_OUTPUT}" == "${TRUE}" ) ]]; then
                    echo -ne "${SOURCE_FILE}\n${FOUND}\n\n"
                fi
            else
                DONE_COUNT="$((DONE_COUNT + 1))"
                if [[ ( "${FULL_OUTPUT}" == "${TRUE}" ) && ( "${DEBUG}" == "${TRUE}" ) ]]; then
                    echo -ne "${SOURCE_FILE}\n\tNot Found: **********************\n\n"
                fi
            fi
        fi
    fi
done < "$(find "${SRC_DIR}" -type f)"


#####################################################################################################################################################################################################
# Display Results
#####################################################################################################################################################################################################
log_trace "Display Results of TODO search"
echo "Search Term: \"${SEARCH_TERM}\""
echo "Found in Files: ${FOUND_COUNT}"
echo "Files Complete: ${DONE_COUNT}"

exit $(( TRUE ))
