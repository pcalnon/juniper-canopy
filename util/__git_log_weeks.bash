#!/bin/bash
#####################################################################################################################################################################################################
# Application: Juniper
# Script Name: git_log_weeks.bash
# Script Path: <Project>/util/git_log_weeks.bash
#
# Description: This script display the git log output over the specified range of weeks for the current repo with format designed for per-week status tracking.
#
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# Notes:
#   Text Color Names are as follows:
#     normal, black, red, green, yellow, blue, magenta, cyan, white
#
#   Text Attributes are as follows:
#     bold, dim, ul, blink, reverse, italic, strike, bright
#
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# Examples:
#    %C(white)%C(dim) Author: %C(reset)%C(green) %an %C(cyan)%C(dim) <%ae> %C(reset) %n\
#    %C(white)%C(dim) Date:   %C(reset)%C(yellow)%C(dim) %ad %C(reset) %n\
#    %C(white)%C(dim) Date:   %C(reset)%C(yellow) %ad %C(reset) %n\
#    %C(green)%C(bold) %an %C(reset)%C(green) <%ae> %C(reset) %n\
#
#####################################################################################################################################################################################################

####################################################################################################
# Define Global Configuration File Constants
####################################################################################################
HOME_DIR="${HOME}"

PROJ_NAME="Juniper"
#PROJ_NAME="dynamic_nn"

#PROJ_LANG_DIR_NAME="rust/rust_mudgeon"
PROJ_LANG_DIR_NAME="python"

DEV_DIR_NAME="Development"
DEV_DIR="${HOME_DIR}/${DEV_DIR_NAME}"

PROJ_ROOT_DIR="${DEV_DIR}/${PROJ_LANG_DIR_NAME}"
PROJ_DIR="${PROJ_ROOT_DIR}/${PROJ_NAME}"

ROOT_CONF_DIR_NAME="conf"
ROOT_CONF_DIR="${PROJ_DIR}/${ROOT_CONF_DIR_NAME}"
ROOT_CONF_FILE_NAME="script_util.cfg"
ROOT_CONF_FILE="${ROOT_CONF_DIR}/${ROOT_CONF_FILE_NAME}"
source ${ROOT_CONF_FILE}


##################################################################################
# Determine Project Dir
##################################################################################
BASE_DIR=$(${GET_PROJECT_SCRIPT} "${BASH_SOURCE}")


##################################################################################
# Determine Host OS
##################################################################################
CURRENT_OS=$(${GET_OS_SCRIPT})


####################################################################################################
# Define Script Functions
####################################################################################################
source ${DATE_FUNCTIONS_SCRIPT}


####################################################################################################
# Define Constants
####################################################################################################
PAST_WEEKS="1"
START_INTERVAL_NUM="-6"
END_INTERVAL_NUM="-1"
START_TIME="00:00:00"
END_TIME="23:59:59"
if [[ ${CURRENT_OS} == "${MACOS}" ]]; then
    INTERVAL_TYPE="${MACOS_DATE_DAYS}"
else
    INTERVAL_TYPE="${LINUX_DATE_DAYS}"
fi


####################################################################################################
# Parse Input Parameters
####################################################################################################
if [[ ${1} != "" ]]; then
    PAST_WEEKS="${1}"
    PAST_WEEKS=$((PAST_WEEKS + 1))
fi
#echo "Past Weeks: ${PAST_WEEKS}"


####################################################################################################
# Calculate the Week Range for the Git Log command and the week numbers since tracking
####################################################################################################
START_DATE=$(get_start_date "${CURRENT_OS}" "${PAST_WEEKS}")
#echo "Start Date: ${START_DATE}"
END_DATE=$(get_end_date "${CURRENT_OS}")
#echo "End Date: ${END_DATE}"
WEEK_NUMBER=$(get_week "${CURRENT_OS}" "${ESTIMATED_FINAL_WEEK}" "${END_DATE}")
#echo "Week Number: ${WEEK_NUMBER}"


####################################################################################################
# Display Git log for the specified date range
####################################################################################################
CURRENT_END="${END_DATE}"
#echo "Current End: ${CURRENT_END}"
CURRENT_START="${END_DATE}"
#echo "Current Start: ${CURRENT_START}"
CURRENT_WEEK="${WEEK_NUMBER}"
#echo "Current Week: ${CURRENT_WEEK}"
while [[ ${CURRENT_START} > ${START_DATE} ]]; do
    CURRENT_START=$(date_update "${CURRENT_OS}" "${CURRENT_END}" "${START_INTERVAL_NUM}" "${INTERVAL_TYPE}")
    #echo "Current Start: ${CURRENT_START}"
    if [[ ${CURRENT_WEEK} != ${WEEK_NUMBER} ]]; then
        echo -ne "\n"
    fi
    echo -ne "Week: ${CURRENT_WEEK} (${CURRENT_START} - ${CURRENT_END})\n"

    git log \
        --since="${CURRENT_START} ${START_TIME}" \
        --until="${CURRENT_END} ${END_TIME}" \
        --date=format:'%Y-%m-%d %H:%M:%S' \
        --pretty=format:"\
    %C(cyan) %ad %C(reset)  %C(yellow) %h %C(reset)  %C(green)%C(dim) %s %C(reset)"

    CURRENT_END=$(date_update "${CURRENT_OS}" "${CURRENT_START}" "${END_INTERVAL_NUM}" "${INTERVAL_TYPE}")
    #echo "Current End: ${CURRENT_END}"
    CURRENT_WEEK="$((CURRENT_WEEK + 1))"
    #echo "Current Week: ${CURRENT_WEEK}"
done

exit 0
