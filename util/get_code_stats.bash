#!/usr/bin/env bash
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Script Name:   get_code_stats.bash
# Script Path:   <Project>/<Application>/util/get_code_stats.bash
# Conf File:     get_code_stats.conf
# Conf Path:     <Project>/<Sub-Project>/<Application>/conf/  # TODO: Add parent project dir
#
# Author:        Paul Calnon
# Version:       1.0.0
#
# Date:          2025-12-15
# Last Modified: 2025-12-15
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#     This file is the sourced conf file for the get_code_stats.bash script. The conf file defines all script constants.
#
#####################################################################################################################################################################################################
# Notes:
#
#     This script sources the following primary config file: ../conf/get_code_stats.conf
#
#     This script also assumes the existence of the following additional config files:
#         - ../conf/common.conf
#         - ../conf/logging.conf
#
#     This script also expects the following file to be present if the configuration process fails:
#         - ../conf/config_fail.conf
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

# source "../conf/init.conf"
# [[ "${SUCCESS}" != "0" ]] && { source "../conf/config_fail.conf"; log_error "${SUCCESS}" "${PARENT_PATH_PARAM}" "../conf/init.conf" "${LINENO}" "${LOG_FILE}"; }
# log_debug "Successfully Configured Current Script: $(basename "${PARENT_PATH_PARAM}"), by Sourcing the Init Config File: ${INIT_CONF}, Returned: \"${SUCCESS}\""


#####################################################################################################################################################################################################
# TODO: Move these "Use env info functions" into config file
#####################################################################################################################################################################################################
source "${DATE_FUNCTIONS_SCRIPT}"
BASE_DIR=$(${GET_PROJECT_SCRIPT} "${BASH_SOURCE}")
log_debug "Base Dir: ${BASE_DIR}"
CURRENT_OS=$(${GET_OS_SCRIPT})
log_debug "Current OS: ${CURRENT_OS}"


#####################################################################################################################################################################################################
# Print Column Labels and Header data for Project source files
#####################################################################################################################################################################################################
# Print heading data
echo -ne "\nDisplay Stats for the ${PROJ_NAME} Project\n\n"
printf "${TABLE_FORMAT}" "Filename" "Lines" "Methods" "TODOs" "Size"
printf "${TABLE_FORMAT}" "----------------------------" "------" "--------" "------" "------"


#####################################################################################################################################################################################################
# Search project source files and retrieve stats
#####################################################################################################################################################################################################
# Initialize project summary counters
TOTAL_FILES=0
TOTAL_LINES=0
TOTAL_METHODS=0
TOTAL_TODOS=0
TOTAL_SIZE=0

MOST_LINES=0
MOST_METHODS=0
MOST_TODOS=0
MOST_SIZE=0

LONG_FILE=""
METHOD_FILE=""
ROUGH_FILE=""
BIG_FILE=""

#####################################################################################################################################################################################################
# Evaluate each source file in project
#####################################################################################################################################################################################################
for i in $(${GET_FILENAMES_SCRIPT} ${FILENAMES_SCRIPT_PARAMS}); do
    # Get current filename and absolute path
    FILE_PATH="$(echo "${i}" | xargs)"
    FILE_NAME="$(echo "${FILE_PATH##*/}" | xargs)"
    [[ ${DEBUG} == "${TRUE}" ]] && echo "Filename: ${FILE_NAME}"

    # Calculate stats for current file
    TOTAL_FILES=$(( TOTAL_FILES + 1 ))


    #################################################################################################################################################################################################
    # Perform Line count calculations
    #################################################################################################################################################################################################
    CURRENT_LINES="$(cat ${FILE_PATH} | wc -l)"
    if (( $(echo "${CURRENT_LINES} > ${MOST_LINES}" | bc -l) )); then
        MOST_LINES="$(echo "${CURRENT_LINES}" | xargs)"
	LONG_FILE="$(echo "${FILE_NAME}" | xargs)"
    elif (( $(echo "${CURRENT_LINES} == ${MOST_LINES}" | bc -l) )); then
        LONG_FILE="${LONG_FILE}, $(echo "${FILE_NAME}" | xargs)"
    fi
    TOTAL_LINES="$(echo "$(( TOTAL_LINES + CURRENT_LINES ))" | xargs)"


    #################################################################################################################################################################################################
    # Perform Method Count calculation
    #################################################################################################################################################################################################
    CURRENT_METHODS=$(grep ${FIND_METHOD_PARAMS} ${FIND_METHOD_REGEX} ${FILE_PATH} | wc -l)
    if (( $(echo "${CURRENT_METHODS} > ${MOST_METHODS}" | bc -l) )); then
        MOST_METHODS="$(echo "${CURRENT_METHODS}" | xargs)"
	METHOD_FILE="$(echo "${FILE_NAME}" | xargs)"
    elif (( $(echo "${CURRENT_METHODS} == ${MOST_METHODS}" | bc -l) )); then
        METHOD_FILE="${METHOD_FILE}, $(echo "${FILE_NAME}" | xargs)"
    fi
    TOTAL_METHODS="$(echo "$(( TOTAL_METHODS + CURRENT_METHODS ))" | xargs)"


    #################################################################################################################################################################################################
    # Perform TODO count calculations
    #################################################################################################################################################################################################
    CURRENT_TODOS="$(echo "$(${GET_FILE_TODO_SCRIPT} ${TODO_SEARCH_SCRIPT_PARAMS} ${FILE_PATH})" | xargs)"
    if (( $(echo "${CURRENT_TODOS} > ${MOST_TODOS}" | bc -l) )); then
        MOST_TODOS="$(echo "${CURRENT_TODOS}" | xargs)"
	ROUGH_FILE="$(echo "${FILE_NAME}" | xargs)"
	[[ ${DEBUG} == ${TRUE} ]] && echo "Current TODOs: ${MOST_TODOS}, for File: ${ROUGH_FILE}"
    elif (( $(echo "${CURRENT_TODOS} == ${MOST_TODOS}" | bc -l) )); then
        ROUGH_FILE="${ROUGH_FILE}, $(echo "${FILE_NAME}" | xargs)"
    fi
    TOTAL_TODOS="$(echo "$(( TOTAL_TODOS + CURRENT_TODOS ))" | xargs)"


    #################################################################################################################################################################################################
    # Perform size calculations
    #################################################################################################################################################################################################
    CURRENT_SIZE="$(echo "$(du -sh ${FILE_PATH} | cut -d $'\t' -f-1)" | xargs)"
    BYTE_SIZE="$(current_size ${CURRENT_SIZE})"
    if (( $(echo "${BYTE_SIZE} > ${MOST_SIZE}" | bc -l) )); then
        MOST_SIZE="$(echo "${BYTE_SIZE}" | xargs)"
	BIG_FILE="$(echo "${FILE_NAME}" | xargs)"
    elif (( $(echo "${BYTE_SIZE} == ${MOST_SIZE}" | bc -l) )); then
        BIG_FILE="$(echo "${BIG_FILE}" | xargs), $(echo "${FILE_NAME}" | xargs)"
    fi
    TOTAL_SIZE="$(echo "$(( TOTAL_SIZE + BYTE_SIZE ))" | xargs)"
    OUTPUT_SIZE="$(readable_size $(echo "${BYTE_SIZE}" | xargs))"


    #################################################################################################################################################################################################
    # Print Stats for current File
    #################################################################################################################################################################################################
    printf "${TABLE_FORMAT}" "${FILE_NAME}" "${CURRENT_LINES}" "${CURRENT_METHODS}" "${CURRENT_TODOS}" "${OUTPUT_SIZE}"

done

READABLE_SIZE="$(readable_size $(echo "${TOTAL_SIZE}" | xargs))"
BIG_FILE_SIZE="$(readable_size $(echo "${MOST_SIZE}" | xargs))"


#####################################################################################################################################################################################################
# Print Project Summary data
#####################################################################################################################################################################################################
# Print summary data
echo -ne "\n\nProject ${PROJ_NAME} Summary:\n\n"
printf "${SUMMARY_FORMAT}" "Total Files:" "${TOTAL_FILES}"
printf "${SUMMARY_FORMAT}" "Total Methods:" "${TOTAL_METHODS}"
printf "${SUMMARY_FORMAT}" "Total Lines:" "${TOTAL_LINES}"
printf "${SUMMARY_FORMAT}" "Total TODOs:" "${TOTAL_TODOS}"
printf "${SUMMARY_FORMAT}" "Total Size:" "${READABLE_SIZE}"


#####################################################################################################################################################################################################
# Print Project File Summary data
#####################################################################################################################################################################################################
echo -ne "\n\nProject ${PROJ_NAME} File Summary:\n\n"
printf "${FILE_SUMMARY_FORMAT}" "Longest File(s):" "(${MOST_LINES} lines)" "--" "${LONG_FILE}"
printf "${FILE_SUMMARY_FORMAT}" "Methods File(s):" "(${MOST_METHODS} methods)" "--" "${METHOD_FILE}"
printf "${FILE_SUMMARY_FORMAT}" "Largest File(s):" "(${BIG_FILE_SIZE})" "--" "${BIG_FILE}"
printf "${FILE_SUMMARY_FORMAT}" "Roughest File(s):" "(${MOST_TODOS} TODOs)" "--" "${ROUGH_FILE}"


#####################################################################################################################################################################################################
# Display Project Git log info
#####################################################################################################################################################################################################
echo -ne "\n\nProject ${PROJ_NAME} Git Log Summary\n\n"
${GIT_LOG_WEEKS_SCRIPT} ${GIT_LOG_WEEKS}
echo -ne "\n"

exit 2
