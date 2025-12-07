#!/bin/bash
#####################################################################################################################################################################################################
# Application: Juniper
# Script Name: __date_functions.bash
# Script Path: ${HOME}/Development/rust/rust_mudgeon/juniper/util/__date_functions.bash
#
# Description: This script contains the platform agnostic date functions and is intended to be sourced
#
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# Notes:
# 	Warning!! This script is Sourced!
#
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# Examples:
#
#####################################################################################################################################################################################################

####################################################################################################
# Define Script Functions
#
#    Non-Macos date command example:
#       CURRENT_END=$(date -d "${CURRENT_START}-1 days" +%F)
#
#    Non-Macos Date Target example:
#        START_TARGET="sunday-${PAST_WEEKS} weeks"
#        END_TARGET="next-saturday"
#
####################################################################################################
function get_timestamp() {
    CURRENT_OS="$1"
    if [[ ${CURRENT_OS} == "${MACOS}" ]]; then
        DATE_COMMAND="${MACOS_DATE_COMMAND}"
        DATE_SWITCH="${MACOS_DATE_SWITCH}"
        DATE_FORMAT="%Y-%m-%d_%H:%M:%S"
    else
        DATE_COMMAND="${LINUX_DATE_COMMAND}"
        DATE_SWITCH=""
        DATE_FORMAT="%F_%T"
    fi
    TIMESTAMP=$(${DATE_COMMAND} ${DATE_SWITCH} "+${DATE_FORMAT}")
    echo "${TIMESTAMP}"
}

function get_date_with_format() {
    CURRENT_OS="$1"
    DATE_FORMAT="$2"
    DATE_TARGET="$3"
    DATE_INPUT_SWITCH=""
    if [[ ${CURRENT_OS} == "${MACOS}" ]]; then
        DATE_COMMAND="${MACOS_DATE_COMMAND}"
        DATE_SWITCH="${MACOS_DATE_SWITCH}"
        if [[ ${DATE_TARGET} != "" ]]; then
            DATE_INPUT_SWITCH="-f ${MACOS_DATE_FORMAT}"
	fi
    else
        DATE_COMMAND="${LINUX_DATE_COMMAND}"
        DATE_SWITCH=""
	if [[ ${DATE_TARGET} != "" ]]; then
            DATE_SWITCH="${LINUX_DATE_SWITCH}"
        fi
    fi
    FORMATTED_DATE=$(${DATE_COMMAND} ${DATE_SWITCH} ${DATE_INPUT_SWITCH} "${DATE_TARGET}" "+${DATE_FORMAT}")
    echo "${FORMATTED_DATE}"
}

function get_date() {
    CURRENT_OS="$1"
    TARGET="$2"
    if [[ ${CURRENT_OS} == "${MACOS}" ]]; then
        DATE_FORMAT="${MACOS_DATE_FORMAT}"
    else
        DATE_FORMAT="${LINUX_DATE_FORMAT}"
    fi
    TARGET_DATE=$(get_date_with_format ${CURRENT_OS} "${DATE_FORMAT}" "${TARGET}")
    echo "${TARGET_DATE}"
}

function get_date_offset() {
    CURRENT_OS="$1"
    OFFSET="$2"
    if [[ ${CURRENT_OS} == "${MACOS}" ]]; then
        DATE_COMMAND="${MACOS_DATE_COMMAND}"
        DATE_SWITCH="${MACOS_DATE_SWITCH}"
        DATE_FORMAT="${MACOS_DATE_FORMAT}"
    else
        DATE_COMMAND="${LINUX_DATE_COMMAND}"
        DATE_SWITCH="${LINUX_DATE_SWITCH}"
        DATE_FORMAT="${LINUX_DATE_FORMAT}"
    fi
    DATE_OFFSET=$(${DATE_COMMAND} ${DATE_SWITCH}${OFFSET} "+${DATE_FORMAT}")
    echo "${DATE_OFFSET}"
}

function get_date_milis() {
    CURRENT_OS="$1"
    TARGET_DATE="$2"
    DATE_MILIS=$(get_date_with_format ${CURRENT_OS} "${MILIS_FORMAT}" "${TARGET_DATE}")
    echo "${DATE_MILIS}"
}

function get_start_date() {
    CURRENT_OS="$1"
    PAST_WEEKS="$2"
    if [[ ${CURRENT_OS} == "${MACOS}" ]]; then
        START_TARGET=" -v-sunday -v-${PAST_WEEKS}w"
    else
        START_TARGET="sunday-${PAST_WEEKS}weeks"
    fi
    START_DATE=$(get_date_offset "${CURRENT_OS}" "${START_TARGET}")
    echo "${START_DATE}"
}

function get_end_date() {
    CURRENT_OS="$1"
    if [[ ${CURRENT_OS} == "${MACOS}" ]]; then
	END_TARGET=" -v+saturday"
    else
        END_TARGET="next-saturday"
    fi
    END_DATE=$(get_date_offset "${CURRENT_OS}" "${END_TARGET}")
    echo "${END_DATE}"
}

function date_update() {
    CURRENT_OS="$1"
    CURRENT_DATE="$2"
    INTERVAL_NUM="$3"
    INTERVAL_TYPE="$4"
    if [[ ${CURRENT_OS} == "${MACOS}" ]]; then
        DATE_COMMAND="${MACOS_DATE_COMMAND}"
        DATE_SWITCH="${MACOS_DATE_SWITCH}"
        DATE_FORMAT="${MACOS_DATE_FORMAT}"
        DATE_INPUT_SWITCH="-f ${MACOS_DATE_FORMAT}"
        UPDATE_INTERVAL=" -v${INTERVAL_NUM}${INTERVAL_TYPE}"
	UPDATE="${UPDATE_INTERVAL} ${DATE_INPUT_SWITCH} ${CURRENT_DATE}"
    else
        DATE_COMMAND="${LINUX_DATE_COMMAND}"
        DATE_SWITCH="${LINUX_DATE_SWITCH}"
        DATE_FORMAT="${LINUX_DATE_FORMAT}"
        UPDATE_INTERVAL="${INTERVAL_NUM}${INTERVAL_TYPE}"
	UPDATE="${CURRENT_DATE}${UPDATE_INTERVAL}"
    fi
    UPDATED_DATE=$(${DATE_COMMAND} ${DATE_SWITCH}${UPDATE} "+${DATE_FORMAT}")
    echo "${UPDATED_DATE}"
}

function get_week() {
    CURRENT_OS="$1"
    FINAL_WEEK="$2"
    END_DATE="$3"
    FINAL_WEEK_MILIS=$(get_date_milis "${CURRENT_OS}" "${FINAL_WEEK}")
    END_DATE_MILIS=$(get_date_milis "${CURRENT_OS}" "${END_DATE}")
    WEEK_NUMBER=$(( (FINAL_WEEK_MILIS - END_DATE_MILIS) / (60 * 60 * 24 * 7) ))
    echo "${WEEK_NUMBER}"
}
