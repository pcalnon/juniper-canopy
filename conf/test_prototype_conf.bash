#!/usr/bin/env bash
#####################################################################################################################################################################################################
# Define Script Constants
#####################################################################################################################################################################################################
TRUE="0"
FALSE="1"

DEBUG="${FALSE}"
DEBUG="${TRUE}"


#####################################################################################################################################################################################################
# Get Testing script name for prototype conf file
#####################################################################################################################################################################################################
TEST_PROTOTYPE_CONF_FILE_NAME="$(basename "$(realpath "${0}")")"


#####################################################################################################################################################################################################
# Define functions for logging
#####################################################################################################################################################################################################
function log_debug() {
    [[ "${DEBUG}" == "${TRUE}" ]] && echo -ne "${TEST_PROTOTYPE_CONF_FILE_NAME}: ($(date +%F_%T)): [DEBUG]: ${*}\n"
}

function log_info() {
    echo -ne "${TEST_PROTOTYPE_CONF_FILE_NAME}: ($(date +%F_%T)): [INFO]: ${*}\n"
}


#####################################################################################################################################################################################################
# Define Prototype config file Constants
#####################################################################################################################################################################################################
log_debug "Test Prototype Conf File NAME: ${TEST_PROTOTYPE_CONF_FILE_NAME}"

PROJECT_NAME="Juniper"         && log_debug "Project Name: ${PROJECT_NAME}"
SOURCE_DIR_NAME="src"          && log_debug "Source Dir Name: ${SOURCE_DIR_NAME}"
CONFIG_DIR_NAME="conf"         && log_debug "Config Dir Name: ${CONFIG_DIR_NAME}"
UTIL_DIR_NAME="util"           && log_debug "Util Dir Name: ${UTIL_DIR_NAME}"
CONFIG_FILE_EXT=".conf"        && log_debug "Config File Ext: ${CONFIG_FILE_EXT}"

CALLING_SCRIPT_NAME="try.bash" && log_debug "Calling Script Name: ${CALLING_SCRIPT_NAME}"


#####################################################################################################################################################################################################
# Define Prototype config constants
#####################################################################################################################################################################################################
TEST_PROTOTYPE_CONF_FILE="$(realpath "$0")"                               && log_debug "Test Prototype Conf File: ${TEST_PROTOTYPE_CONF_FILE}"
TEST_PROTOTYPE_CONF_PATH="$(dirname "${TEST_PROTOTYPE_CONF_FILE}")"       && log_debug "Test Prototype Conf Path: ${TEST_PROTOTYPE_CONF_PATH}"
PROTOTYPE_NAME="$(basename "${TEST_PROTOTYPE_CONF_PATH}")"                && log_debug "Prototype Name: ${PROTOTYPE_NAME}"
PROTOTYPE_DIR_NAME="$(basename "$(dirname "$TEST_PROTOTYPE_CONF_PATH")")" && log_debug "Prototype Dir Name: ${PROTOTYPE_DIR_NAME}"


#####################################################################################################################################################################################################
# Define juniper_canopy.conf Directory constants
#####################################################################################################################################################################################################
PROJECT_DIR_NAME="${PROJECT_NAME}" && log_debug "Project Dir Name: ${PROJECT_DIR_NAME}"
PROJECT_DIR_PATH="$(echo "${TEST_PROTOTYPE_CONF_FILE}" | awk -F "${PROJECT_DIR_NAME}" '{print $1 "'${PROJECT_DIR_NAME}'";}')" && log_debug "Project Dir Path: ${PROJECT_DIR_PATH}"

PROTOTYPE_DIR_PATH="${PROJECT_DIR_PATH}/${SOURCE_DIR_NAME}/${PROTOTYPE_DIR_NAME}/${PROTOTYPE_NAME}" && log_debug "Prototype Dir Path: ${PROTOTYPE_DIR_PATH}"

CONFIG_FILE_PATH="${PROTOTYPE_DIR_PATH}/${CONFIG_DIR_NAME}" && log_debug "Config File Path: ${CONFIG_FILE_PATH}"
SCRIPT_FILE_PATH="${PROTOTYPE_DIR_PATH}/${UTIL_DIR_NAME}" && log_debug "Script File Path: ${SCRIPT_FILE_PATH}"


#####################################################################################################################################################################################################
# Define juniper_canopy.conf file constants
#####################################################################################################################################################################################################
CONFIG_FILE_NAME="${PROTOTYPE_NAME}${CONFIG_FILE_EXT}" && log_debug "Config File Name: ${CONFIG_FILE_NAME}"
CONFIG_FILE="${CONFIG_FILE_PATH}/${CONFIG_FILE_NAME}" && log_debug "Config File: ${CONFIG_FILE}"


#####################################################################################################################################################################################################
# Define juniper_canopy.conf file Input Parameter constants
#####################################################################################################################################################################################################
CALLING_SCRIPT_NAME_PARAM="${CALLING_SCRIPT_NAME}" && log_debug "Calling Script Name Param: ${CALLING_SCRIPT_NAME_PARAM}"
CALLING_SCRIPT_PATH_PARAM="${SCRIPT_FILE_PATH}" && log_debug "Calling Script Path Param: ${CALLING_SCRIPT_PATH_PARAM}"


#####################################################################################################################################################################################################
# Test the juniper_canopy.conf config file
#####################################################################################################################################################################################################
log_info "Testing ${CONFIG_FILE} \"${CALLING_SCRIPT_NAME_PARAM}\" \"${CALLING_SCRIPT_PATH_PARAM}\""
${CONFIG_FILE} "${CALLING_SCRIPT_NAME_PARAM}" "${CALLING_SCRIPT_PATH_PARAM}"
log_info "Testing ${CONFIG_FILE_NAME} Returned: \"$?\""
