#!/usr/bin/env bash
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       1.0.0
# File Name:     get_module_filenames.conf
# File Path:     <Project>/<Sub-Project>/<Application>/conf/
#
# Date:          2025-12-03
# Last Modified: 2025-12-19
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#     This script collects and displays useful stats about the code base of the Juniper python project
#
#####################################################################################################################################################################################################
# Notes:
#
#####################################################################################################################################################################################################
# References:
#
#####################################################################################################################################################################################################
# TODO :
#
#####################################################################################################################################################################################################
# COMPLETED:
#
#####################################################################################################################################################################################################


#####################################################################################################################################################################################################
# Define Boolean Constants
#####################################################################################################################################################################################################
export TRUE="1"
export FALSE="0"

# export DEBUG="${TRUE}"
export DEBUG="${FALSE}"


#####################################################################################################################################################################################################
# Only Source this conf file Once
#####################################################################################################################################################################################################
if [[ "${GET_MODULE_FILENAME_CONF_SOURCED}" != "${TRUE}" ]]; then
    export GET_MODULE_FILENAME_CONF_SOURCED="${TRUE}"
else
    log_warning "get_module_filenames.conf already sourced.  Skipping re-source."
    [[ "${DEBUG}" == "${TRUE}" ]] && exit $(( TRUE )) || return $(( TRUE ))
fi


#####################################################################################################################################################################################################
# Define constants for script
#####################################################################################################################################################################################################
# shellcheck disable=SC2155
export SCRIPT_PATH="$(realpath "${BASH_SOURCE[0]}")"
# shellcheck disable=SC2155
export SCRIPT_NAME="$(basename "${SCRIPT_PATH}")"
# shellcheck disable=SC2155
export SCRIPT_DIR="$(dirname "${SCRIPT_PATH}")"

export BASH_EXT="bash"
export CONF_EXT="conf"

export UTIL_DIR_NAME="util"
export CONF_DIR_NAME="${CONF_EXT}"

export LOGGING_CONF_PREFIX="logging"
export COMMON_CONF_PREFIX="common"
export FUNCTION_CONF_INFIX="_fn"


#####################################################################################################################################################################################################
# Define Global Configuration File Constants
#####################################################################################################################################################################################################
export HOME_DIR="${HOME}"
export FUNCTION_NAME="${0##*/}"
export PROJ_NAME="Juniper"
export SUB_PROJECT_NAME="JuniperCanopy"
export APP_NAME="juniper_canopy"
export PROJ_LANG_DIR_NAME="python"
export DEV_DIR_NAME="Development"
export DEV_DIR="${HOME_DIR}/${DEV_DIR_NAME}"
export LANG_DIR="${DEV_DIR}/${PROJ_LANG_DIR_NAME}"
export PROJ_ROOT_DIR="${LANG_DIR}/${SUB_PROJECT_NAME}"
export PROJ_DIR_NAME="juniper_canopy"
export PROJ_DIR="${PROJ_ROOT_DIR}/${PROJ_DIR_NAME}"
export CONF_DIR="${PROJ_DIR}/${CONF_DIR_NAME}"


# #####################################################################################################################################################################################################
# # Build and Source the Function config file path
# #####################################################################################################################################################################################################
# CONF_FUNCTION_FILE_NAME="${SCRIPT_NAME%.*}${FUNCTION_CONF_INFIX}.${CONF_EXT}"
# CONF_FUNCTION_FILE="${CONF_DIR}/${CONF_FUNCTION_FILE_NAME}"

# if [[ "${DEBUG}" == "${TRUE}" ]]; then
#     log_debug "Running the function config file: ${CONF_FUNCTION_FILE}"
#     "${CONF_FUNCTION_FILE}"; SUCCESS="$?"
# else
#     log_debug "Sourcing the function config file: ${CONF_FUNCTION_FILE}"
#     # shellcheck disable=SC1090
#     source "${CONF_FUNCTION_FILE}"; SUCCESS="$?"
# fi
# [[ "${SUCCESS}" != "0" ]] && log_error "Failed to source the function config file: ${CONF_FUNCTION_FILE}, returned ${SUCCESS}"
# log_debug "Sourced the function config file: ${CONF_FUNCTION_FILE}"


# #####################################################################################################################################################################################################
# # Build and Source the Common Config file path
# #####################################################################################################################################################################################################
# CONF_COMMON_FILE_NAME="${COMMON_CONF_PREFIX}.${CONF_EXT}"
# CONF_COMMON_FILE="${CONF_DIR}/${CONF_COMMON_FILE_NAME}"

# if [[ "${DEBUG}" == "${TRUE}" ]]; then
#     log_debug "Running the common config file: ${CONF_COMMON_FILE}"
#     # shellcheck disable=SC1090
#     source "${CONF_COMMON_FILE}"; SUCCESS="$?"
# else
#     log_debug "Sourcing the common config file: ${CONF_COMMON_FILE}"
#     # shellcheck disable=SC1090
#     source "${CONF_COMMON_FILE}"; SUCCESS="$?"
# fi
# [[ "${SUCCESS}" != "0" ]] && log_error "Failed to source the common config file: ${CONF_COMMON_FILE}, returned ${SUCCESS}"
# log_debug "Sourced the common config file: ${CONF_COMMON_FILE}"


#####################################################################################################################################################################################################
# Configure Script Environment
#####################################################################################################################################################################################################
log_debug "Configure Script Environment"
export SRC_DIR_NAME="src"
export SRC_DIR="${PROJ_DIR}/${SRC_DIR_NAME}"
export UTIL_DIR_NAME="util"
export UTIL_DIR="${PROJ_DIR}/${UTIL_DIR_NAME}"
export DATA_DIR_NAME="data"
export DATA_DIR="${PROJ_DIR}/${DATA_DIR_NAME}"
export VIZ_DIR_NAME="viz"
export VIZ_DIR="${PROJ_DIR}/${VIZ_DIR_NAME}"
export LOGS_DIR_NAME="logs"
export LOGS_DIR="${PROJ_DIR}/${LOGS_DIR_NAME}"
export TEST_DIR_NAME="tests"
export TEST_DIR="${PROJ_DIR}/${TEST_DIR_NAME}"


#######################################################################################################################################################################################
# Define the Script Environment File Constants
#######################################################################################################################################################################################
log_debug "Define the Script Environment File Constants"
export CONF_FILE_NAME="logging_config.yaml"
export CONF_FILE="${CONF_DIR}/${CONF_FILE_NAME}"
export GET_FILENAMES_SCRIPT_NAME="get_module_filenames.bash"
export GET_FILENAMES_SCRIPT="${UTIL_DIR}/${GET_FILENAMES_SCRIPT_NAME}"
export GET_SOURCETREE_SCRIPT_NAME="source_tree.bash"
export GET_SOURCETREE_SCRIPT="${UTIL_DIR}/${GET_SOURCETREE_SCRIPT_NAME}"
export GET_TODO_COMMENTS_SCRIPT_NAME="get_todo_comments.bash"
export GET_TODO_COMMENTS_SCRIPT="${UTIL_DIR}/${GET_TODO_COMMENTS_SCRIPT_NAME}"
export GET_FILE_TODO_SCRIPT_NAME="get_file_todo.bash"
export GET_FILE_TODO_SCRIPT="${UTIL_DIR}/${GET_FILE_TODO_SCRIPT_NAME}"
export GIT_LOG_WEEKS_SCRIPT_NAME="__git_log_weeks.bash"
export GIT_LOG_WEEKS_SCRIPT="${UTIL_DIR}/${GIT_LOG_WEEKS_SCRIPT_NAME}"
export GET_OS_SCRIPT_NAME="__get_os_name.bash"
export GET_OS_SCRIPT="${UTIL_DIR}/${GET_OS_SCRIPT_NAME}"
export GET_PROJECT_SCRIPT_NAME="__get_project_dir.bash"
export GET_PROJECT_SCRIPT="${UTIL_DIR}/${GET_PROJECT_SCRIPT_NAME}"


#####################################################################################################################################################################################################
# Define Script Constants
#####################################################################################################################################################################################################
log_debug "Define Script Constants"
export INIT_FILE_NAME="*__init__*"
export MODULE_EXT="*.py"
export PARSE_STRING='//*\/'
export FULL_OUTPUT="${FALSE}"
export TEST_FILE_NAME="*test_*.py"


#####################################################################################################################################################################################################
# Define command line parameter switches
#####################################################################################################################################################################################################
log_debug "Define command line parameter switches"
export OUTPUT_SHORT="-f"
export OUTPUT_LONG="--full"
export HELP_SHORT="-h"
export HELP_LONG="--help"

[[ "${DEBUG}" == "${TRUE}" ]] && exit $(( TRUE )) || return $(( TRUE ))
