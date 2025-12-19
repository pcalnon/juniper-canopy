#!/usr/bin/env bash
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Script Name:   get_file_todo.bash
# Script Path:   <Project>/<Sub-Project>/juniper_canopy/util/get_file_todo.bash
# Conf File:     get_file_todo.conf
# Conf Path:     <Project>/<Sub-Project>/<Application>/conf/  # TODO: Add parent project dir
#
# Author:        Paul Calnon
# Version:       1.0.0
#
# Date:          2025-12-03
# Last Modified: 2025-12-15
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
#     Determine if failed configuration via sourced config files will consistently generate signals
#         If so, evaluate trapping signals to simplify error handling
#         trap 'log_error $? "${PARENT_PATH_PARAM}" "${BASH_SOURCE[0]}" "${LINENO}" "${LOG_FILE}"' ERR
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
# set -eE -o functrace
# set -o functrace


#####################################################################################################################################################################################################
# Source script config file
#####################################################################################################################################################################################################
set -o functrace
export PARENT_PATH_PARAM="$(realpath "${BASH_SOURCE[0]}")" && INIT_CONF="../conf/init.conf"
[[ -f "${INIT_CONF}" ]] && source "${INIT_CONF}" || { echo "Init Config File Not Found. Unable to Continue."; exit 1; }


# export PARENT_PATH_PARAM="$(realpath "${BASH_SOURCE[0]}")"
# source "../conf/init.conf"; SUCCESS="$?"

# [[ "${SUCCESS}" != "0" ]] && { source "../conf/config_fail.conf"; log_error "${SUCCESS}" "${PARENT_PATH_PARAM}" "../conf/init.conf" "${LINENO}" "${LOG_FILE}"; }
# log_debug "Successfully Configured Current Script: $(basename "${PARENT_PATH_PARAM}"), by Sourcing the Init Config File: ${INIT_CONF}, Returned: \"${SUCCESS}\""


# # set -eE -o functrace

# # source "$(dirname "$(dirname "$(realpath "${BASH_SOURCE[0]}")")")/conf/$(basename -s ".bash" "$(realpath "${BASH_SOURCE[0]}")").conf"; SUCCESS="$?"
# # [[ "${SUCCESS}" != "0" ]] && printf "%b%-21s %-28s %-21s %-11s %s%b\n" "\033[1;31m" "($(date +%F_%T))" "$(basename "${SCRIPT_PATH}"):(${LINENO})" "main:" "[CRITICAL]" "Config load Failed: \"${CONF_FILE}\"" "\033[0m" | tee -a "${LOG_FILE}" 2>&1 && set -e && exit 1
# # log_debug "Successfully Sourced Current Script: ${SCRIPT_NAME}, Config File: ${CONF_FILE}, Success: ${SUCCESS}"

# export PARENT_SCRIPT_PATH_PARAM="$(realpath "${BASH_SOURCE[0]}")"
# export INIT_CONF="../conf/init.conf"
# source "${INIT_CONF}"; SUCCESS="$?"

# [[ "${SUCCESS}" != "0" ]] && printf "%b%-21s %-28s %-21s %-11s %s%b\n" "\033[1;31m" "($(date +%F_%T))" "$(basename "${PARENT_SCRIPT_PATH_PARAM}"):(${LINENO})" "main:" "[CRITICAL]" "Config load Failed: \"${INIT_CONF}\"" "\033[0m" | tee -a "${LOG_FILE}" 2>&1 && set -e && exit 1
# log_debug "Successfully Sourced Current Script: $(basename "${PARENT_SCRIPT_PATH_PARAM}"), Init Config File: ${INIT_CONF}, Success: ${SUCCESS}"


####################################################################################################
# TODO: Move this "Run env info functions" into config file
####################################################################################################
source ${DATE_FUNCTIONS_SCRIPT}


####################################################################################################
# Define Script Functions
####################################################################################################
function usage() {
    RET_VAL="$1"
    shift
    MESSAGE="$@"
    USAGE="\n\tusage: ${FUNCTION_NAME} [${HELP_SHORT}|${HELP_LONG}] [${FILE_SHORT}|${FILE_LONG} <Path to File>] [${SEARCH_SHORT}|${SEARCH_LONG} <Search Term>]\n\n"
    if [[ ${MESSAGE} != "" ]]; then
        echo -ne "${MESSAGE}"
    fi
    echo -ne "${USAGE}"
    exit $(( RET_VAL ))
}


#######################################################################################################################################################################################
# Process Script's Command Line Argument(s)
#######################################################################################################################################################################################
while [[ "${1}" != "" ]]; do
    case ${1} in
        ${HELP_SHORT} | ${HELP_LONG})
            usage 0
        ;;
        ${SEARCH_SHORT} | ${SEARCH_LONG})
            shift
            PARAM="${1}"
            shift
        if [[ ${PARAM} != "" ]]; then
                SEARCH_TERM="${PARAM}"
            fi
        ;;
        ${FILE_SHORT} | ${FILE_LONG})
            shift
            PARAM="${1}"
            shift
        if [[ ( ${PARAM} != "" ) && ( -f ${PARAM} ) ]]; then
                SEARCH_FILE="${PARAM}"
            else
                usage 1 "Error: Received an invalid Search File: \"${PARAM}\"\n"
            fi
        ;;
        *)
            #echo "Invalid Param: \"${1}\""
            usage 1 "Error: Invalid command line params: \"${@}\"\n"
        ;;
    esac
done


#######################################################################################################################################################################################
# Search for instances of a specific search term in the specified source code file
#######################################################################################################################################################################################
RAW_OUTPUT="$(grep "${SEARCH_TERM}" ${SEARCH_FILE})"
COUNT="$(grep "${SEARCH_TERM}" ${SEARCH_FILE} | wc -l)"


#######################################################################################################################################################################################
# Display Results
#######################################################################################################################################################################################
echo "${COUNT}"
