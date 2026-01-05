#!/usr/bin/env bash
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       0.1.4 (0.7.3)
# File Name:     __git_log_weeks.bash
# File Path:     <Project>/<Sub-Project>/<Application>/util/
#
# Date:          2025-10-11
# Last Modified: 2026-01-03
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#     This script display the git log output over the specified range of weeks for the current repo with format designed for per-week status tracking.
#
#####################################################################################################################################################################################################
# Notes:
#     Text Color Names are as follows:
#         normal, black, red, green, yellow, blue, magenta, cyan, white
#
#     Text Attributes are as follows:
#         bold, dim, ul, blink, reverse, italic, strike, bright
#
########################################################################################################)#############################################################################################
# References:
#     %C(white)%C(dim) Author: %C(reset)%C(green) %an %C(cyan)%C(dim) <%ae> %C(reset) %n\
#     %C(white)%C(dim) Date:   %C(reset)%C(yellow)%C(dim) %ad %C(reset) %n\
#     %C(white)%C(dim) Date:   %C(reset)%C(yellow) %ad %C(reset) %n\
#     %C(green)%C(bold) %an %C(reset)%C(green) <%ae> %C(reset) %n\
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
# Parse Input Parameters
#####################################################################################################################################################################################################
if [[ ${1} != "" ]]; then
    PAST_WEEKS="${1}"
    PAST_WEEKS=$((PAST_WEEKS + 1))
fi
log_trace "Past Weeks: ${PAST_WEEKS}"


#####################################################################################################################################################################################################
# Calculate the Week Range for the Git Log command and the week numbers since tracking
#####################################################################################################################################################################################################
START_DATE=$(get_start_date "${CURRENT_OS}" "${PAST_WEEKS}")                    && log_trace "Start Date: ${START_DATE}"
END_DATE=$(get_end_date "${CURRENT_OS}")                                        && log_trace "End Date: ${END_DATE}"
WEEK_NUMBER=$(get_week "${CURRENT_OS}" "${ESTIMATED_FINAL_WEEK}" "${END_DATE}") && log_trace "Week Number: ${WEEK_NUMBER}"


#####################################################################################################################################################################################################
# Initialize Date Variables
#####################################################################################################################################################################################################
CURRENT_END="${END_DATE}"     && log_trace "Current End: ${CURRENT_END}"
CURRENT_START="${END_DATE}"   && log_trace "Current Start: ${CURRENT_START}"
CURRENT_WEEK="${WEEK_NUMBER}" && log_trace "Current Week: ${CURRENT_WEEK}"


#####################################################################################################################################################################################################
# Display Git log for the specified date range
#####################################################################################################################################################################################################
while [[ "${CURRENT_START}" > "${START_DATE}" ]]; do
    CURRENT_START=$(date_update "${CURRENT_OS}" "${CURRENT_END}" "${START_INTERVAL_NUM}" "${INTERVAL_TYPE}") && log_trace "Current Start: ${CURRENT_START}"
    if [[ "${CURRENT_WEEK}" != "${WEEK_NUMBER}" ]]; then
        echo -ne "\n"
    fi
    log_trace "Week: ${CURRENT_WEEK} (${CURRENT_START} - ${CURRENT_END})"
    echo -ne "Week: ${CURRENT_WEEK} (${CURRENT_START} - ${CURRENT_END})\n"

    git log \
        --since="${CURRENT_START} ${START_TIME}" \
        --until="${CURRENT_END} ${END_TIME}" \
        --date=format:'%Y-%m-%d %H:%M:%S' \
        --pretty=format:"\
    %C(cyan) %ad %C(reset)  %C(yellow) %h %C(reset)  %C(green)%C(dim) %s %C(reset)"

    CURRENT_END="$(date_update "${CURRENT_OS}" "${CURRENT_START}" "${END_INTERVAL_NUM}" "${INTERVAL_TYPE}")" && log_trace "Current End: ${CURRENT_END}"
    CURRENT_WEEK="$((CURRENT_WEEK + 1))"                                                                     && log_trace "Current Week: ${CURRENT_WEEK}"
done

exit $(( TRUE ))
