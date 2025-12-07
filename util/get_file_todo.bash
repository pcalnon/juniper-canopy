#!/usr/bin/env bash
#####################################################################################################################################################################################################
# Application: Juniper
# Script Name: get_file_todo.bash
# Script Path: <Project>/util/get_file_todo.bash
#
# Description: This script
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
HOME_DIR="${HOME}"

FUNCTION_NAME="${0##*/}"

# PROJ_NAME="dynamic_nn"
# PROJ_NAME="juniper"
PROJ_NAME="Juniper"

# PROJ_LANG_DIR_NAME="rust/rust_mudgeon"
PROJ_LANG_DIR_NAME="python"

DEV_DIR_NAME="Development"
DEV_DIR="${HOME_DIR}/${DEV_DIR_NAME}"
PROJ_ROOT_DIR="${DEV_DIR}/${PROJ_LANG_DIR_NAME}"
PROJ_DIR="${PROJ_ROOT_DIR}/${PROJ_NAME}"

CONF_DIR_NAME="conf"
CONF_DIR="${PROJ_DIR}/${CONF_DIR_NAME}"
CONF_FILE_NAME="script_util.cfg"
CONF_FILE="${CONF_DIR}/${CONF_FILE_NAME}"

source "${CONF_FILE}"


####################################################################################################
# Configure Script Environment
####################################################################################################
SRC_DIR_NAME="src"
SRC_DIR="${PROJ_DIR}/${SRC_DIR_NAME}"
LOG_DIR_NAME="logs"
LOG_DIR="${PROJ_DIR}/${LOG_DIR_NAME}"
UTIL_DIR_NAME="util"
UTIL_DIR="${PROJ_DIR}/${UTIL_DIR_NAME}"
DATA_DIR_NAME="data"
DATA_DIR="${PROJ_DIR}/${DATA_DIR_NAME}"
VIZ_DIR_NAME="viz"
VIZ_DIR="${PROJ_DIR}/${VIZ_DIR_NAME}"
CONF_DIR_NAME="conf"
CONF_DIR="${PROJ_DIR}/${CONF_DIR_NAME}"
TEST_DIR_NAME="tests"
TEST_DIR="${PROJ_DIR}/${TEST_DIR_NAME}"


#######################################################################################################################################################################################
# Define the Script Environment File Constants
#######################################################################################################################################################################################
CONF_FILE_NAME="logging_config.yaml"
CONF_FILE="${CONF_DIR}/${CONF_FILE_NAME}"
GET_FILENAMES_SCRIPT_NAME="get_module_filenames.bash"
GET_FILENAMES_SCRIPT="${UTIL_DIR}/${GET_FILENAMES_SCRIPT_NAME}"
GET_SOURCETREE_SCRIPT_NAME="source_tree.bash"
GET_SOURCETREE_SCRIPT="${UTIL_DIR}/${GET_SOURCETREE_SCRIPT_NAME}"
GET_TODO_COMMENTS_SCRIPT_NAME="get_todo_comments.bash"
GET_TODO_COMMENTS_SCRIPT="${UTIL_DIR}/${GET_TODO_COMMENTS_SCRIPT_NAME}"
GET_FILE_TODO_SCRIPT_NAME="get_file_todo.bash"
GET_FILE_TODO_SCRIPT="${UTIL_DIR}/${GET_FILE_TODO_SCRIPT_NAME}"
GIT_LOG_WEEKS_SCRIPT_NAME="__git_log_weeks.bash"
GIT_LOG_WEEKS_SCRIPT="${UTIL_DIR}/${GIT_LOG_WEEKS_SCRIPT_NAME}"


#######################################################################################################################################################################################
# Define the Script Constants
#######################################################################################################################################################################################
# DEBUG="true"
DEBUG="false"

#SEARCH_TERM_DEFAULT="write tests"
SEARCH_TERM_DEFAULT="TODO"
SEARCH_TERM="${SEARCH_TERM_DEFAULT}"

SEARCH_FILE=""


####################################################################################################
# Define command line parameter switches
####################################################################################################
HELP_SHOR="-h"
HELP_LONG="--help"

FILE_SHORT="-f"
FILE_LONG="--file"

SEARCH_SHORT="-s"
SEARCH_LONG="--search"


####################################################################################################
# Run env info functions
####################################################################################################
BASE_DIR=$(${GET_PROJECT_SCRIPT} "${BASH_SOURCE}")
CURRENT_OS=$(${GET_OS_SCRIPT})
source "${DATE_FUNCTIONS_SCRIPT}"


####################################################################################################
# Define Script Functions
####################################################################################################
source ${DATE_FUNCTIONS_SCRIPT}

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
