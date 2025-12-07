#!/usr/bin/env bash
#####################################################################################################################################################################################################
# Application: Juniper
# Script Name: todo_search.bash
# Script Path: <Project>/util/todo_search.bash
#
# Description: This script files in the source directory of the current project for a specific search term and then displays the number of files that do and do not contain the search term.
#
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# Notes:
#
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# Examples:
#
#####################################################################################################################################################################################################

#####################################################################################################
# Define Global Configuration File Constants
####################################################################################################
# ROOT_PROJ_NAME="dynamic_nn"
## ROOT_PROJ_NAME="juniper"
ROOT_PROJ_NAME="Juniper"
ROOT_CONF_NAME="conf"
ROOT_CONF_FILE_NAME="script_util.cfg"
# ROOT_PROJ_DIR="${HOME}/Development/rust/rust_mudgeon/${ROOT_PROJ_NAME}"
ROOT_PROJ_DIR="${HOME}/Development/python/${ROOT_PROJ_NAME}"
ROOT_CONF_DIR="${ROOT_PROJ_DIR}/${ROOT_CONF_NAME}"
ROOT_CONF_FILE="${ROOT_CONF_DIR}/${ROOT_CONF_FILE_NAME}"
INIT_PYTHON_FILE="__init__"
source ${ROOT_CONF_FILE}
# echo "Root Conf File: ${ROOT_CONF_FILE}"
# echo "Source Dir Name: ${SOURCE_DIR_NAME}"


##################################################################################
# Determine Project Dir
##################################################################################
# BASE_DIR=$(${GET_PROJECT_SCRIPT} "${BASH_SOURCE}")
BASE_DIR=${ROOT_PROJ_DIR}
# echo "Base Dir: ${BASE_DIR}"


##################################################################################
# Determine Host OS
##################################################################################
CURRENT_OS=$(${GET_OS_SCRIPT})
# echo "Current OS: ${CURRENT_OS}"


####################################################################################################
# Define Script Functions
####################################################################################################
source ${DATE_FUNCTIONS_SCRIPT}

function usage() {
    EXIT_COND="${EXIT_COND_DEFAULT}"
    if [[ "$1" != "" ]]; then
        EXIT_COND="$1"
    fi
    MESSAGE="usage: ${SCRIPT_NAME} <SEARCH TERM> | [--help|-h]"
    echo -ne "\n\t${MESSAGE}\n\n"
    exit ${EXIT_COND}
}


#######################################################################################################################################################################################
# Define the Script Environment Constants
#######################################################################################################################################################################################
SRC_DIR="${BASE_DIR}/${SOURCE_DIR_NAME}"
# echo "Source Dir: ${SRC_DIR}"
LOG_DIR="${BASE_DIR}/${LOGGING_DIR_NAME}"
# echo "Log Dir: ${LOG_DIR}"
CONF_DIR="${BASE_DIR}/${CONFIG_DIR_NAME}"
# echo "Conf Dir: ${CONF_DIR}"

# LOG_FILE_MODULE="${LOG_DIR}/${LOG_FILE_MODULE_NAME}"
# echo "Log File Module: ${LOG_FILE_MODULE}"
# LOG_FILE_STARTUP="${LOG_DIR}/${LOG_FILE_STARTUP_NAME}"
# echo "Log File Startup: ${LOG_FILE_STARTUP}"
CONF_FILE="${CONF_DIR}/${ROOT_CONF_FILE_NAME}"
# echo "Conf File: ${CONF_FILE}"


#######################################################################################################################################################################################
# Define the Script Constants
#######################################################################################################################################################################################
# DEBUG="true"
DEBUG="false"

FULL_OUTPUT="true"
# FULL_OUTPUT="false"

HELP_SHORT="-h"
HELP_LONG="--help"

EXIT_COND_DEFAULT="1"

# SEARCH_TERM_DEFAULT="write tests"
SEARCH_TERM_DEFAULT="TODO"


#######################################################################################################################################################################################
# Process Script's Command Line Argument(s)
#######################################################################################################################################################################################
if [[ "$1" != "" ]]; then
    if [[ "$1" == "${HELP_SHORT}" || "$1" == "${HELP_LONG}" ]]; then
        usage 0
    else
        SEARCH_TERM="$1"
    fi
else
    # SEARCH_TERM="${SEARCH_TERM_DEFAULT}"
    if [[ ${DEBUG} == "true" ]]; then
        SEARCH_TERM="${SEARCH_TERM_DEFAULT}"
    else
        usage
    fi
fi


#######################################################################################################################################################################################
# Sanitize Inputs
#######################################################################################################################################################################################
DASHES=$(echo "${SEARCH_TERM}" | grep -e '^-.*')
if [[ ${DASHES} != "" ]]; then
    SEARCH_TERM="\\${SEARCH_TERM}"
    if [[ ${DEBUG} == "true" ]]; then
        echo "Sanitized SEARCH_TERM Input: ${SEARCH_TERM}"
    fi
fi


#######################################################################################################################################################################################
# Search for a specific TODO reference in source code
#######################################################################################################################################################################################
DONE_COUNT=0
FOUND_COUNT=0
for i in $(find ${SRC_DIR}); do
    SOURCE_FILE=$(echo "${i}" | grep "\.${SRC_FILE_SUFFIX}\$")
    # echo "Source File: \"${SOURCE_FILE}\""
    if [[ ${SOURCE_FILE} != "" ]]; then
        SOURCE_FILE=$(echo "${SOURCE_FILE}" | grep -v "${INIT_PYTHON_FILE}")
	if [[ ${SOURCE_FILE} != "" ]]; then
            if [[ -f ${SOURCE_FILE} ]]; then
                FOUND=$(cat ${SOURCE_FILE} | grep "${SEARCH_TERM}")
                if [[ ${FOUND} != "" ]]; then
                    FOUND_COUNT=$((FOUND_COUNT + 1))
                    if [[ ${DEBUG} == "true" || ${FULL_OUTPUT} == "true" ]]; then
                        # echo -ne "${SOURCE_FILE}\n\tFound: ${FOUND}\n\n"
                        echo -ne "${SOURCE_FILE}\n${FOUND}\n\n"
                    fi
                else
                    DONE_COUNT=$((DONE_COUNT + 1))
                    if [[ ${FULL_OUTPUT} == "true" && ${DEBUG} == "true" ]]; then
                        echo -ne "${SOURCE_FILE}\n\tNot Found: **********************\n\n"
                    fi
                fi
            fi
        fi
    fi
done


#######################################################################################################################################################################################
# Display Results
#######################################################################################################################################################################################
echo "Search Term: \"${SEARCH_TERM}\""
echo "Found in Files: ${FOUND_COUNT}"
echo "Files Complete: ${DONE_COUNT}"
