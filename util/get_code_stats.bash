#!/bin/bash

#  \!/usr/bin/env bash
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
# set -eE -o functrace
# TODO: revert back to this line after debugging is complete
# source "$(dirname "$(dirname "$(realpath "${BASH_SOURCE[0]}")")")/conf/$(basename -s ".bash" "$(realpath "${BASH_SOURCE[0]}")").conf"; SUCCESS="$?"

INIT_CONF="../conf/init.conf"
source "${INIT_CONF}"; SUCCESS="$?"
# ${INIT_CONF}; SUCCESS="$?"

log_debug "Completed Sourcing Init Config File: ${INIT_CONF} returned value: ${SUCCESS}"

exit 0


# export GET_CODE_STATS_CONF_SOURCED="${FALSE}"
# export CLOSE_LOGGING_CONF_SOURCED="${FALSE}"

SCRIPT_PATH="$(realpath "${BASH_SOURCE[0]}")"
echo "SCRIPT_PATH: ${SCRIPT_PATH}"

CONF_PATH="$(dirname "$(dirname "${SCRIPT_PATH}")")/conf"
echo "CONF_PATH: ${CONF_PATH}"

CONF_FILENAME="$(basename -s ".bash" "${SCRIPT_PATH}").conf"
echo "CONF_FILENAME: ${CONF_FILENAME}"

# CONF_FILE="${SCRIPT_PATH}/${SCRIPT_FILENAME}"
CONF_FILE="${CONF_PATH}/${CONF_FILENAME}"
echo "CONF_FILE: ${CONF_FILE}"

source "${CONF_FILE}"
SUCCESS="$?"
log_debug "Sourcing Config File returned: ${SUCCESS}"
log_debug "Completed sourcing Current Script: ${SCRIPT_NAME}, Config File: ${CONF_FILE}, Success: ${SUCCESS}"

[[ "${SUCCESS}" != "0" ]] && printf "%b%-21s %-28s %-21s %-11s %s%b\n" "\033[1;31m" "($(date +%F_%T))" "$(basename "${SCRIPT_PATH}"):(${LINENO})" "main:" "[CRITICAL]" "Config load Failed: \"${CONF_FILE}\"" "\033[0m" | tee -a "${LOG_FILE}" 2>&1 && set -e && exit 1

log_debug "Successfully Sourced Current Script: ${SCRIPT_NAME}, Config File: ${CONF_FILE}, Success: ${SUCCESS}"

#
# SCRIPT_PATH="$(realpath "${BASH_SOURCE[0]}")"
# CONF_PATH="$(dirname "$(dirname "${SCRIPT_PATH}")")/conf"
# CONF_FILENAME="$(basename -s ".bash" "${SCRIPT_PATH}").conf"
# CONF_FILE="${SCRIPT_PATH}/${SCRIPT_FILENAME}"
#
# CONF_PATH="$(dirname "$(dirname "$(realpath "${BASH_SOURCE[0]}")")")/conf"
# CONF_FILENAME="$(basename -s ".bash" "$(realpath "${BASH_SOURCE[0]}")").conf"
# CONF_FILE="${CONF_PATH}/${CONF_FILENAME}"
#
# CONF_FILE="$(dirname "$(dirname "$(realpath "${BASH_SOURCE[0]}")")")/conf/$(basename -s ".bash" "$(realpath "${BASH_SOURCE[0]}")").conf"
#
# source "${CONF_FILE}";  SUCCESS="$?"


####################################################################################################
# Run env info functions
####################################################################################################
# set -eE -o functrace
# set -eE
set -o functrace
BASE_DIR=$(${GET_PROJECT_SCRIPT} "${BASH_SOURCE}")

echo "Base Dir: ${BASE_DIR}"

# Determine Host OS
CURRENT_OS=$(${GET_OS_SCRIPT})
# Define Script Functions

echo "Current OS: ${CURRENT_OS}"

# TODO: This line is Borked:
#   /home/pcalnon/Development/python/JuniperCanopy/juniper_canopy/conf/get_code_stats.conf:
#   line 84
#   /home/pcalnon/Development/python/JuniperCanopy/conf/script_util.cfg: No such file or directory
# source "${SCRIPT_PATH}/conf/script_util.cfg"


####################################################################################################
# Define Script Functions
####################################################################################################
function round_size() {
    SIZEF="${1}"
    SIZE="${SIZEF%.*}"
    DEC="0.${DIG}"
    if (( $(echo "${DEC} >= 0.5" | bc -l) )); then
        SIZE=$(( SIZE + 1 ))
    fi
    echo "${SIZE}"
}

function current_size() {
    CURRENT_SIZE="${1}"
    LABEL="${CURRENT_SIZE: -1}"
    SIZEF="${CURRENT_SIZE: -1}"
    for i in "${!SIZE_LABELS[@]}"; do
        if [[ "${SIZE_LABELS[${i}]}" == "${LABEL}" ]]; then
            break
        else
            #SIZE=$(( SIZE * SIZE_LABEL_MAG ))
            #SIZEF=$(( SIZEF * SIZE_LABEL_MAG ))
            SIZEF="$(echo "${SIZEF} * ${SIZE_LABEL_MAG}" | bc -l)"
	fi
    done
    SIZE="$(round_size ${SIZEF})"
    echo "${SIZE}"
}

function readable_size() {
    CURRENT_SIZE="${1}"
    LABEL_INDEX=0
    BYTES_LABEL=""
    while (( $(echo "${CURRENT_SIZE} >= ${SIZE_LABEL_MAG}" | bc -l) )); do
        CURRENT_SIZE="$(echo "${CURRENT_SIZE} / ${SIZE_LABEL_MAG}" | bc -l)"
        LABEL_INDEX=$(( LABEL_INDEX + 1 ))
    done
    SIZE="$(round_size ${CURRENT_SIZE})"
    if (( LABEL_INDEX > 0 )); then
        BYTE_LABEL="${SIZE_LABELS[0]}"
    fi
    READABLE="${SIZE} ${SIZE_LABELS[${LABEL_INDEX}]}${BYTE_LABEL}"
    echo "${READABLE}"
}


################################################################################################################
# Print Column Labels and Header data for Project source files
################################################################################################################
# Print heading data
echo -ne "\nDisplay Stats for the ${PROJ_NAME} Project\n\n"
printf "${TABLE_FORMAT}" "Filename" "Lines" "Methods" "TODOs" "Size"
printf "${TABLE_FORMAT}" "----------------------------" "------" "--------" "------" "------"


################################################################################################################
# Search project source files and retrieve stats
################################################################################################################
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

# Evaluate each source file in project
for i in $(${GET_FILENAMES_SCRIPT} ${FILENAMES_SCRIPT_PARAMS}); do
    # Get current filename and absolute path
    FILE_PATH="$(echo "${i}" | xargs)"
    FILE_NAME="$(echo "${FILE_PATH##*/}" | xargs)"
    [[ ${DEBUG} == "${TRUE}" ]] && echo "Filename: ${FILE_NAME}"

    # Calculate stats for current file
    TOTAL_FILES=$(( TOTAL_FILES + 1 ))

    # Perform Line count calculations
    CURRENT_LINES="$(cat ${FILE_PATH} | wc -l)"
    if (( $(echo "${CURRENT_LINES} > ${MOST_LINES}" | bc -l) )); then
        MOST_LINES="$(echo "${CURRENT_LINES}" | xargs)"
	LONG_FILE="$(echo "${FILE_NAME}" | xargs)"
    elif (( $(echo "${CURRENT_LINES} == ${MOST_LINES}" | bc -l) )); then
        LONG_FILE="${LONG_FILE}, $(echo "${FILE_NAME}" | xargs)"
    fi
    TOTAL_LINES="$(echo "$(( TOTAL_LINES + CURRENT_LINES ))" | xargs)"

    # Perform Method Count calculation
    CURRENT_METHODS=$(grep ${FIND_METHOD_PARAMS} ${FIND_METHOD_REGEX} ${FILE_PATH} | wc -l)
    if (( $(echo "${CURRENT_METHODS} > ${MOST_METHODS}" | bc -l) )); then
        MOST_METHODS="$(echo "${CURRENT_METHODS}" | xargs)"
	METHOD_FILE="$(echo "${FILE_NAME}" | xargs)"
    elif (( $(echo "${CURRENT_METHODS} == ${MOST_METHODS}" | bc -l) )); then
        METHOD_FILE="${METHOD_FILE}, $(echo "${FILE_NAME}" | xargs)"
    fi
    TOTAL_METHODS="$(echo "$(( TOTAL_METHODS + CURRENT_METHODS ))" | xargs)"

    # Perform TODO count calculations
    CURRENT_TODOS="$(echo "$(${GET_FILE_TODO_SCRIPT} ${TODO_SEARCH_SCRIPT_PARAMS} ${FILE_PATH})" | xargs)"
    if (( $(echo "${CURRENT_TODOS} > ${MOST_TODOS}" | bc -l) )); then
        MOST_TODOS="$(echo "${CURRENT_TODOS}" | xargs)"
	ROUGH_FILE="$(echo "${FILE_NAME}" | xargs)"
	[[ ${DEBUG} == ${TRUE} ]] && echo "Current TODOs: ${MOST_TODOS}, for File: ${ROUGH_FILE}"
    elif (( $(echo "${CURRENT_TODOS} == ${MOST_TODOS}" | bc -l) )); then
        ROUGH_FILE="${ROUGH_FILE}, $(echo "${FILE_NAME}" | xargs)"
    fi
    TOTAL_TODOS="$(echo "$(( TOTAL_TODOS + CURRENT_TODOS ))" | xargs)"

    # Perform size calculations
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

    # Print Stats for current File
    printf "${TABLE_FORMAT}" "${FILE_NAME}" "${CURRENT_LINES}" "${CURRENT_METHODS}" "${CURRENT_TODOS}" "${OUTPUT_SIZE}"
done
READABLE_SIZE="$(readable_size $(echo "${TOTAL_SIZE}" | xargs))"
BIG_FILE_SIZE="$(readable_size $(echo "${MOST_SIZE}" | xargs))"


################################################################################################################
# Print Project Summary data
################################################################################################################
# Print summary data
echo -ne "\n\nProject ${PROJ_NAME} Summary:\n\n"
printf "${SUMMARY_FORMAT}" "Total Files:" "${TOTAL_FILES}"
printf "${SUMMARY_FORMAT}" "Total Methods:" "${TOTAL_METHODS}"
printf "${SUMMARY_FORMAT}" "Total Lines:" "${TOTAL_LINES}"
printf "${SUMMARY_FORMAT}" "Total TODOs:" "${TOTAL_TODOS}"
printf "${SUMMARY_FORMAT}" "Total Size:" "${READABLE_SIZE}"


################################################################################################################
# Print Project File Summary data
################################################################################################################
echo -ne "\n\nProject ${PROJ_NAME} File Summary:\n\n"
printf "${FILE_SUMMARY_FORMAT}" "Longest File(s):" "(${MOST_LINES} lines)" "--" "${LONG_FILE}"
printf "${FILE_SUMMARY_FORMAT}" "Methods File(s):" "(${MOST_METHODS} methods)" "--" "${METHOD_FILE}"
printf "${FILE_SUMMARY_FORMAT}" "Largest File(s):" "(${BIG_FILE_SIZE})" "--" "${BIG_FILE}"
printf "${FILE_SUMMARY_FORMAT}" "Roughest File(s):" "(${MOST_TODOS} TODOs)" "--" "${ROUGH_FILE}"


################################################################################################################
# Display Project Git log info
################################################################################################################
echo -ne "\n\nProject ${PROJ_NAME} Git Log Summary\n\n"
${GIT_LOG_WEEKS_SCRIPT} ${GIT_LOG_WEEKS}
echo -ne "\n"

exit 2
