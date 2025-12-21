#!/usr/bin/env bash
#####################################################################################################################################################################################################
# Application: Juniper
# Script Name: get_duplicate_methods.bash
# Script Path: <Project>/util/get_duplicate_methods.bash
#
# Description: This script finds duplicate method definitions in the specified group of files
#
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# Notes:
#
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# Examples:
#
#####################################################################################################################################################################################################

#####################################################################################################
# Define Global Project Constants
####################################################################################################
HOME_DIR="${HOME}"

FUNCTION_NAME="${0##*/}"

# PROJ_NAME="dynamic_nn"
# PROJ_NAME="juniper"
PROJ_NAME="Juniper"

#PROJ_LANG_DIR_NAME="rust/rust_mudgeon"
PROJ_LANG_DIR_NAME="python"

DEV_DIR_NAME="Development"
DEV_DIR="${HOME_DIR}/${DEV_DIR_NAME}"
PROJ_ROOT_DIR="${DEV_DIR}/${PROJ_LANG_DIR_NAME}"
PROJ_DIR="${PROJ_ROOT_DIR}/${PROJ_NAME}"

CONF_DIR_NAME="conf"
CONF_DIR="${PROJ_DIR}/${CONF_DIR_NAME}"
CONF_FILE_NAME="common.conf"
CONF_FILE="${CONF_DIR}/${CONF_FILE_NAME}"

source "${CONF_FILE}"


#######################################################################################################################################################################################
# Configure Script Environment
#######################################################################################################################################################################################
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
#DEBUG="true"
DEBUG="false"


####################################################################################################
# Run env info functions
####################################################################################################
BASE_DIR=$(${GET_PROJECT_SCRIPT} "${BASH_SOURCE}")
# Determine Host OS
CURRENT_OS=$(${GET_OS_SCRIPT})
# Define Script Functions
# source "${DATE_FUNCTIONS_SCRIPT}"


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
    SIZEF="${CURRENT_SIZE::-1}"
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


####################################################################################################
#
####################################################################################################
