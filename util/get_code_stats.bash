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
# Last Modified: 2026-01-06
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
# Initialize script by sourcing the init_conf.bash config file
#####################################################################################################################################################################################################
set -o functrace
# shellcheck disable=SC2155
export PARENT_PATH_PARAM="$(realpath "${BASH_SOURCE[0]}")" && INIT_CONF="$(dirname "$(dirname "${PARENT_PATH_PARAM}")")/conf/init.conf"
# shellcheck disable=SC2015,SC1090
[[ -f "${INIT_CONF}" ]] && source "${INIT_CONF}" || { echo "Init Config File Not Found. Unable to Continue."; exit 1; }


#####################################################################################################################################################################################################
# Print Column Labels and Header data for Project source files
#####################################################################################################################################################################################################
log_debug "Print Column Labels and Header data for Project source files"
# Print heading data
log_debug "Print heading data"
echo -ne "\nDisplay Stats for the ${PROJ_NAME} Project\n\n"
# shellcheck disable=SC2059
printf "${TABLE_FORMAT}" "Filename" "Lines" "Methods" "TODOs" "Size"
# shellcheck disable=SC2059
printf "${TABLE_FORMAT}" "----------------------------" "------" "--------" "------" "------"


#####################################################################################################################################################################################################
# Evaluate each source file in project
#####################################################################################################################################################################################################
log_debug "Evaluate each source file in project"
# Inline find command for performance - avoid subprocess overhead of calling get_module_filenames.bash
while read -r i; do
    [[ -z "${i}" ]] && continue
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
    CURRENT_LINES="$(cat "${FILE_PATH}" | wc -l)"
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
    # Use tr to strip any whitespace and ensure we get a clean integer
    CURRENT_METHODS="$(grep -c -E -- "${FIND_METHOD_REGEX}" "${FILE_PATH}" 2>/dev/null | tr -d '[:space:]')"
    [[ -z "${CURRENT_METHODS}" ]] && CURRENT_METHODS="0"
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
    #     NOTE: Inline grep for performance - avoid subprocess overhead of calling get_file_todo.bash
    #     NOTE: Use tr to strip any newlines/whitespace and ensure we get a clean integer
    #################################################################################################################################################################################################
    log_debug "Perform TODO count calculations"
    CURRENT_TODOS="$(grep -ic "${SEARCH_TERM_DEFAULT}" "${FILE_PATH}" 2>/dev/null | tr -d '[:space:]')"
    [[ -z "${CURRENT_TODOS}" ]] && CURRENT_TODOS="0"
    log_verbose "Current TODOS: ${CURRENT_TODOS}"
    if (( CURRENT_TODOS > 0 && ( $(echo "${CURRENT_TODOS} > ${MOST_TODOS}" | bc -l) ) )); then
        MOST_TODOS="$(echo "${CURRENT_TODOS}" | xargs)"
        log_verbose "Most TODOS: ${MOST_TODOS}"
        ROUGH_FILE="$(echo "${FILE_NAME}" | xargs)"
        log_verbose "Rough File: ${ROUGH_FILE}"
        log_debug "Current TODOs: ${MOST_TODOS}, for File: ${ROUGH_FILE}"
    elif (( CURRENT_TODOS > 0 && ( $(echo "${CURRENT_TODOS} == ${MOST_TODOS}" | bc -l) ) )); then
        ROUGH_FILE="${ROUGH_FILE}, $(echo "${FILE_NAME}" | xargs)"
        log_verbose "Rough File: ${ROUGH_FILE}"
    else
        log_debug "No TODOs found in current file: ${FILE_NAME}"
        log_verbose "Current TODOS: ${CURRENT_TODOS}, for File: ${FILE_NAME}"
        log_verbose "Most TODOS: ${MOST_TODOS}, for File: ${ROUGH_FILE}"
        log_debug "Total Todos: ${TOTAL_TODOS}"
        log_debug "Current Todos: ${CURRENT_TODOS}"
        log_verbose "Updated Total Todos: ${TOTAL_TODOS} + ${CURRENT_TODOS} = $(( TOTAL_TODOS + CURRENT_TODOS ))"
    fi
    TOTAL_TODOS="$(echo "$(( TOTAL_TODOS + CURRENT_TODOS ))" | xargs)"
    log_debug "Total TODOS: ${TOTAL_TODOS}"


    #################################################################################################################################################################################################
    # Perform size calculations
    #################################################################################################################################################################################################
    log_debug "Perform size calculations"
    CURRENT_SIZE="$(du -sh "${FILE_PATH}" | cut -d $'\t' -f-1 | xargs)"
    log_verbose "Current Size: ${CURRENT_SIZE}"
    BYTE_SIZE="$(current_size "${CURRENT_SIZE}")"
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
    OUTPUT_SIZE="$(readable_size "$(echo "${BYTE_SIZE}" | xargs)")"
    log_debug "Output Size: ${OUTPUT_SIZE}"


    #################################################################################################################################################################################################
    # Print Stats for current File
    #################################################################################################################################################################################################
    log_debug "Print Stats for current File"
    # shellcheck disable=SC2059
    printf "${TABLE_FORMAT}" "${FILE_NAME}" "${CURRENT_LINES}" "${CURRENT_METHODS}" "${CURRENT_TODOS}" "${OUTPUT_SIZE}"

done <<< "$(find "${SRC_DIR}" \( -name "*.py" ! -name "*__init__*" ! -name "*test_*.py" \) -type f 2>/dev/null)"


#####################################################################################################################################################################################################
# Parse file sizes
#####################################################################################################################################################################################################
log_trace "Parsing file sizes"
READABLE_SIZE="$(readable_size "$(echo "${TOTAL_SIZE}" | xargs)")"
log_debug "Readable Size: ${READABLE_SIZE}"
BIG_FILE_SIZE="$(readable_size "$(echo "${MOST_SIZE}" | xargs)")"
log_debug "Big File Size: ${BIG_FILE_SIZE}"


#####################################################################################################################################################################################################
# Print Project Summary data
#####################################################################################################################################################################################################
log_debug "Print Project Summary data"
# Print summary data
echo -ne "\n\nProject ${PROJ_NAME} Summary:\n\n"
# shellcheck disable=SC2059
printf "${SUMMARY_FORMAT}" "Total Files:" "${TOTAL_FILES}"
# shellcheck disable=SC2059
printf "${SUMMARY_FORMAT}" "Total Methods:" "${TOTAL_METHODS}"
# shellcheck disable=SC2059
printf "${SUMMARY_FORMAT}" "Total Lines:" "${TOTAL_LINES}"
# shellcheck disable=SC2059
printf "${SUMMARY_FORMAT}" "Total TODOs:" "${TOTAL_TODOS}"
# shellcheck disable=SC2059
printf "${SUMMARY_FORMAT}" "Total Size:" "${READABLE_SIZE}"


#####################################################################################################################################################################################################
# Print Project File Summary data
#####################################################################################################################################################################################################
log_debug "Print Project File Summary data"
echo -ne "\n\nProject ${PROJ_NAME} File Summary:\n\n"
# shellcheck disable=SC2059
printf "${FILE_SUMMARY_FORMAT}" "Longest File(s):" "(${MOST_LINES} lines)" "--" "${LONG_FILE}"
# shellcheck disable=SC2059
printf "${FILE_SUMMARY_FORMAT}" "Methods File(s):" "(${MOST_METHODS} methods)" "--" "${METHOD_FILE}"
# shellcheck disable=SC2059
printf "${FILE_SUMMARY_FORMAT}" "Largest File(s):" "(${BIG_FILE_SIZE})" "--" "${BIG_FILE}"
# shellcheck disable=SC2059
printf "${FILE_SUMMARY_FORMAT}" "Roughest File(s):" "(${MOST_TODOS} TODOs)" "--" "${ROUGH_FILE}"


#####################################################################################################################################################################################################
# Display Project Git log info
#####################################################################################################################################################################################################
log_debug "Display Project Git log info"
echo -ne "\n\nProject ${PROJ_NAME} Git Log Summary\n\n"
${GIT_LOG_WEEKS_SCRIPT} "${GIT_LOG_WEEKS}"
echo -ne "\n"

exit $(( TRUE ))  # Exit successfully
