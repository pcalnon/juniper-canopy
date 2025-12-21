#!/usr/bin/env bash
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       1.0.0
# File Name:     get_code_stats.bash
# File Path:     <Project>/<Sub-Project>/<Application>/util/
#
# Date:          2025-02-05
# Last Modified: 2025-12-19
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
# TRUE="0"
# FALSE="1"

# # DEBUG="${TRUE}"
# DEBUG="${FALSE}"


#####################################################################################################################################################################################################
# Source script config file
#####################################################################################################################################################################################################
set -o functrace
export PARENT_PATH_PARAM="$(realpath "${BASH_SOURCE[0]}")" && INIT_CONF="../conf/init.conf"

if [[ "${DEBUG}" == "${TRUE}" ]]; then
    if [ -f "${INIT_CONF}" ]; then
        echo "Init Config File Found. Sourcing: \"${INIT_CONF}\""
        source "${INIT_CONF}"
    else
        echo "Init Config File Not Found. Unable to Continue."
        return 0
    fi
else
    [[ -f "${INIT_CONF}" ]] && source "${INIT_CONF}" || { echo "Init Config File Not Found. Unable to Continue."; exit 1; }
fi


#####################################################################################################################################################################################################
# Print Column Labels and Header data for Project source files
#####################################################################################################################################################################################################
log_debug "Print Column Labels and Header data for Project source files"

# Print heading data
log_debug "Print heading data"
echo -ne "\nDisplay Stats for the ${PROJ_NAME} Project\n\n"
printf "${TABLE_FORMAT}" "Filename" "Lines" "Methods" "TODOs" "Size"
printf "${TABLE_FORMAT}" "----------------------------" "------" "--------" "------" "------"


#####################################################################################################################################################################################################
# Search project source files and retrieve stats
#####################################################################################################################################################################################################
log_debug "Search project source files and retrieve stats"

# Initialize project summary counters
log_debug "Initialize project summary counters"
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
log_debug "Evaluate each source file in project"
for i in $(${GET_FILENAMES_SCRIPT} ${FILENAMES_SCRIPT_PARAMS}); do
    # Get current filename and absolute path
    log_debug "Get current filename and absolute path"
    FILE_PATH="$(echo "${i}" | xargs)"
    log_verbose "File Path: ${FILE_PATH}"
    FILE_NAME="$(echo "${FILE_PATH##*/}" | xargs)"
    log_debug "File Name: ${FILE_NAME}"
    # Calculate stats for current file
    log_debug "Calculate stats for current file"
    TOTAL_FILES=$(( TOTAL_FILES + 1 ))
    log_verbose "Total Files: ${TOTAL_FILES}"


    #################################################################################################################################################################################################
    # Perform Line count calculations
    #################################################################################################################################################################################################
    log_debug "Perform Line count calculations"
    CURRENT_LINES="$(cat ${FILE_PATH} | wc -l)"
    log_verbose "Current Lines: ${CURRENT_LINES}"
    # TODO: consider switching to [[ ]] since output of bc is a bool?
    if (( $(echo "${CURRENT_LINES} > ${MOST_LINES}" | bc -l) )); then
        log_verbose "Most Lines before update: ${MOST_LINES}"
        MOST_LINES="$(echo "${CURRENT_LINES}" | xargs)"
        log_verbose "Most Lines after update: ${MOST_LINES}"
        LONG_FILE="$(echo "${FILE_NAME}" | xargs)"
        log_verbose "Long File: ${LONG_FILE}"
    elif (( $(echo "${CURRENT_LINES} == ${MOST_LINES}" | bc -l) )); then
        log_verbose "Most Lines: ${MOST_LINES}"
        log_verbose "Long File before update: ${LONG_FILE}"
        LONG_FILE="${LONG_FILE}, $(echo "${FILE_NAME}" | xargs)"
        log_verbose "Long File after update: ${LONG_FILE}"
    fi
    TOTAL_LINES="$(echo "$(( TOTAL_LINES + CURRENT_LINES ))" | xargs)"
    log_debug "Total Lines: ${TOTAL_LINES}"


    #################################################################################################################################################################################################
    # Perform Method Count calculation
    #################################################################################################################################################################################################
    log_debug "Perform Method Count calculation"
    CURRENT_METHODS=$(grep ${FIND_METHOD_PARAMS} ${FIND_METHOD_REGEX} ${FILE_PATH} | wc -l)
    log_verbose "Current Methods: ${CURRENT_METHODS}"
    if (( $(echo "${CURRENT_METHODS} > ${MOST_METHODS}" | bc -l) )); then
        MOST_METHODS="$(echo "${CURRENT_METHODS}" | xargs)"
        log_verbose "Most Methods: ${MOST_METHODS}"
        METHOD_FILE="$(echo "${FILE_NAME}" | xargs)"
        log_verbose "Method File: ${METHOD_FILE}"
    elif (( $(echo "${CURRENT_METHODS} == ${MOST_METHODS}" | bc -l) )); then
        METHOD_FILE="${METHOD_FILE}, $(echo "${FILE_NAME}" | xargs)"
        log_verbose "Method File: ${METHOD_FILE}"
    fi
    TOTAL_METHODS="$(echo "$(( TOTAL_METHODS + CURRENT_METHODS ))" | xargs)"
    log_debug "Total Methods: ${TOTAL_METHODS}"


    #################################################################################################################################################################################################
    # Perform TODO count calculations
    #################################################################################################################################################################################################
    log_debug "Perform TODO count calculations"
    CURRENT_TODOS="$(echo "$(${GET_FILE_TODO_SCRIPT} ${TODO_SEARCH_SCRIPT_PARAMS} ${FILE_PATH})" | xargs)"
    log_verbose "Current TODOS: ${CURRENT_TODOS}"
    if (( $(echo "${CURRENT_TODOS} > ${MOST_TODOS}" | bc -l) )); then
        MOST_TODOS="$(echo "${CURRENT_TODOS}" | xargs)"
        log_verbose "Most TODOS: ${MOST_TODOS}"
        ROUGH_FILE="$(echo "${FILE_NAME}" | xargs)"
        log_verbose "Rough File: ${ROUGH_FILE}"
        log_debug "Current TODOs: ${MOST_TODOS}, for File: ${ROUGH_FILE}"
    elif (( $(echo "${CURRENT_TODOS} == ${MOST_TODOS}" | bc -l) )); then
        ROUGH_FILE="${ROUGH_FILE}, $(echo "${FILE_NAME}" | xargs)"
        log_verbose "Rough File: ${ROUGH_FILE}"
    fi
    TOTAL_TODOS="$(echo "$(( TOTAL_TODOS + CURRENT_TODOS ))" | xargs)"
    log_debug "Total TODOS: ${TOTAL_TODOS}"


    #################################################################################################################################################################################################
    # Perform size calculations
    #################################################################################################################################################################################################
    log_debug "Perform size calculations"
    CURRENT_SIZE="$(echo "$(du -sh ${FILE_PATH} | cut -d $'\t' -f-1)" | xargs)"
    log_verbose "Current Size: ${CURRENT_SIZE}"
    BYTE_SIZE="$(current_size ${CURRENT_SIZE})"
    log_verbose "Byte Size: ${BYTE_SIZE}"
    if (( $(echo "${BYTE_SIZE} > ${MOST_SIZE}" | bc -l) )); then
        MOST_SIZE="$(echo "${BYTE_SIZE}" | xargs)"
        log_verbose "Most Size: ${MOST_SIZE}"
        BIG_FILE="$(echo "${FILE_NAME}" | xargs)"
        log_verbose "Big File: ${BIG_FILE}"
    elif (( $(echo "${BYTE_SIZE} == ${MOST_SIZE}" | bc -l) )); then
        BIG_FILE="${BIG_FILE}, $(echo "${FILE_NAME}" | xargs)"
        log_verbose "Big File: ${BIG_FILE}"
    fi
    TOTAL_SIZE="$(echo "$(( TOTAL_SIZE + BYTE_SIZE ))" | xargs)"
    log_debug "Total Size: ${TOTAL_SIZE}"
    OUTPUT_SIZE="$(readable_size $(echo "${BYTE_SIZE}" | xargs))"
    log_debug "Output Size: ${OUTPUT_SIZE}"


    #################################################################################################################################################################################################
    # Print Stats for current File
    #################################################################################################################################################################################################
    log_debug "Print Stats for current File"
    printf "${TABLE_FORMAT}" "${FILE_NAME}" "${CURRENT_LINES}" "${CURRENT_METHODS}" "${CURRENT_TODOS}" "${OUTPUT_SIZE}"

done

READABLE_SIZE="$(readable_size $(echo "${TOTAL_SIZE}" | xargs))"
log_debug "Readable Size: ${READABLE_SIZE}"
BIG_FILE_SIZE="$(readable_size $(echo "${MOST_SIZE}" | xargs))"
log_debug "Big File Size: ${BIG_FILE_SIZE}"


#####################################################################################################################################################################################################
# Print Project Summary data
#####################################################################################################################################################################################################
log_debug "Print Project Summary data"

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
log_debug "Print Project File Summary data"
echo -ne "\n\nProject ${PROJ_NAME} File Summary:\n\n"
printf "${FILE_SUMMARY_FORMAT}" "Longest File(s):" "(${MOST_LINES} lines)" "--" "${LONG_FILE}"
printf "${FILE_SUMMARY_FORMAT}" "Methods File(s):" "(${MOST_METHODS} methods)" "--" "${METHOD_FILE}"
printf "${FILE_SUMMARY_FORMAT}" "Largest File(s):" "(${BIG_FILE_SIZE})" "--" "${BIG_FILE}"
printf "${FILE_SUMMARY_FORMAT}" "Roughest File(s):" "(${MOST_TODOS} TODOs)" "--" "${ROUGH_FILE}"


#####################################################################################################################################################################################################
# Display Project Git log info
#####################################################################################################################################################################################################
log_debug "Display Project Git log info"
echo -ne "\n\nProject ${PROJ_NAME} Git Log Summary\n\n"
${GIT_LOG_WEEKS_SCRIPT} ${GIT_LOG_WEEKS}
echo -ne "\n"

exit 2  # TODO: Why is this returning a non-zero value?
