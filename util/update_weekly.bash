#!/bin/bash
#####################################################################################################################################################################################################
# Application: Juniper
# Script Name: update_weekly.bash
# Script Path: <Project>/util/update_weekly.bash
#
# Description: This script updates the weekly record of the progress taken from git log output with the current weeks progress
#
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# Notes:
#
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# Examples:
#
#####################################################################################################################################################################################################

####################################################################################################
# Define Global Configuration File Constants
####################################################################################################
ROOT_PROJ_NAME="juniper"
ROOT_CONF_NAME="conf"
ROOT_CONF_FILE_NAME="common.conf"
ROOT_PROJ_DIR="${HOME}/Development/rust/rust_mudgeon/${ROOT_PROJ_NAME}"
ROOT_CONF_DIR="${ROOT_PROJ_DIR}/${ROOT_CONF_NAME}"
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
# source ${DATE_FUNCTIONS_SCRIPT}


####################################################################################################
# Define Script Constants
####################################################################################################
OUTPUT_FILE_NAME="week_progress.txt"
DISPLAY_LINES="45"


####################################################################################################
# Define Environment Constants
####################################################################################################
OUTPUT_DIR="${BASE_DIR}/${OUTPUT_DIR_NAME}"
OUTPUT_FILE="${OUTPUT_DIR}/${OUTPUT_FILE_NAME}"
SCRIPT_DIR="${BASE_DIR}/${SCRIPT_DIR_NAME}"
GIT_LOG_SCRIPT="${SCRIPT_DIR}/${GIT_LOG_SCRIPT_NAME}"


####################################################################################################
# Determine Dates and Calculate week values
####################################################################################################
END_DATE=$(get_end_date ${CURRENT_OS})
CURRENT_WEEK_NUMBER=$(get_week "${CURRENT_OS}" "${ESTIMATED_FINAL_WEEK}" "${END_DATE}")
BOT_WEEK_NUMBER=$(get_week "${CURRENT_OS}" "${ESTIMATED_FINAL_WEEK}" "${BEGINNING_TIME}")
PAST_WEEKS=$((BOT_WEEK_NUMBER - CURRENT_WEEK_NUMBER - 1))


####################################################################################################
# Update the Weekly Progress file from the Git Log
####################################################################################################
${GIT_LOG_SCRIPT} ${PAST_WEEKS} > ${OUTPUT_FILE}
RESULT="$?"

if [[ ${RESULT} == "0" ]]; then
    echo -ne "Successfully Updated the Weekly Progress file\n\n"
else
    echo "Error: Failed to Update the Weekly Progress file: \"${RESULT}\""
    exit 1
fi
cat ${OUTPUT_FILE} | head -${DISPLAY_LINES}

exit 0
