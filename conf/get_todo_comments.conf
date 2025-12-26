#!/usr/bin/env bash
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       1.0.0
# File Name:     get_todo_comments.conf
# File Path:     <Project>/<Sub-Project>/<Application>/conf/
#
# Date:          2025-12-03
# Last Modified: 2025-12-25
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#     This script files in the source directory of the current project for a specific search term and then displays the number of files that do and do not contain the search term.
#
#####################################################################################################################################################################################################
# Notes:
#
#####################################################################################################################################################################################################
# References:
#
#####################################################################################################################################################################################################
# TODO :
#     1. Add parent project dir
#
#####################################################################################################################################################################################################
# COMPLETED:
#
#####################################################################################################################################################################################################


#####################################################################################################################################################################################################
# Define Boolean Constants
#####################################################################################################################################################################################################
export TRUE="0"
export FALSE="1"

# export DEBUG="${TRUE}"
export DEBUG="${FALSE}"


#####################################################################################################################################################################################################
# Only Source this conf file Once
#####################################################################################################################################################################################################
if [[ "${GET_TODO_COMMENTS_CONF_SOURCED}" != "${TRUE}" ]]; then
    export GET_TODO_COMMENTS_CONF_SOURCED="${TRUE}"
else
    log_warning "get_todo_comments.conf already sourced.  Skipping re-source."
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
export CONF_DIR_NAME="conf"

export LOGGING_CONF_PREFIX="logging"
export COMMON_CONF_PREFIX="common"
export FUNCTION_CONF_INFIX="_fn"


#####################################################################################################################################################################################################
# Define Global Configuration File Constants  # TODO: These should already be defined in the common.conf file
#####################################################################################################################################################################################################
export ROOT_PROJ_NAME="Juniper"
export SUB_PROJ_NAME="JuniperCanopy"
export APP_NAME="juniper_canopy"
export HOME_DIR="${HOME}"
export DEV_DIR_NAME="Development"
export DEV_DIR="${HOME_DIR}/${DEV_DIR_NAME}"
export LANG_DIR_NAME="python"
export LANG_DIR="${DEV_DIR}/${LANG_DIR_NAME}"
export ROOT_PROJ_DIR="${LANG_DIR}/${SUB_PROJ_NAME}"
export PROJ_DIR="${ROOT_PROJ_DIR}/${APP_NAME}"
export CONF_DIR_NAME="conf"
export CONF_FILE_NAME="script_util.cfg"
export CONF_DIR="${PROJ_DIR}/${CONF_DIR_NAME}"
export CONF_FILE="${CONF_DIR}/${CONF_FILE_NAME}"
export INIT_PYTHON_FILE="__init__"



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
#     "${CONF_COMMON_FILE}"; SUCCESS="$?"
# else
#     log_debug "Sourcing the common config file: ${CONF_COMMON_FILE}"
#     # shellcheck disable=SC1090
#     source "${CONF_COMMON_FILE}"; SUCCESS="$?"
# fi
# [[ "${SUCCESS}" != "0" ]] && log_error "Failed to source the common config file: ${CONF_COMMON_FILE}, returned ${SUCCESS}"
# log_debug "Sourced the common config file: ${CONF_COMMON_FILE}"


#####################################################################################################################################################################################################
# Determine Project environment info
#####################################################################################################################################################################################################
export BASE_DIR=${PROJ_DIR}
log_debug "Base Dir: ${BASE_DIR}"

# shellcheck disable=SC2155
export CURRENT_OS=$(${GET_OS_SCRIPT})
log_debug "Current OS: ${CURRENT_OS}"


#####################################################################################################################################################################################################
# Define the Script Environment Constants
#####################################################################################################################################################################################################
export SRC_DIR="${BASE_DIR}/${SOURCE_DIR_NAME}"
log_debug "Source Dir: ${SRC_DIR}"
export LOG_DIR="${BASE_DIR}/${LOGGING_DIR_NAME}"
log_debug "Log Dir: ${LOG_DIR}"
export CONF_DIR="${BASE_DIR}/${CONF_DIR_NAME}"
log_debug "Conf Dir: ${CONF_DIR}"
export CONF_FILE="${CONF_DIR}/${ROOT_CONF_FILE_NAME}"
log_debug "Conf File: ${CONF_FILE}"


#####################################################################################################################################################################################################
# Define the Script Constants
#####################################################################################################################################################################################################
export FULL_OUTPUT="${TRUE}"
# export FULL_OUTPUT="${FALSE}"

export HELP_SHORT="-h"
export HELP_LONG="--help"
export EXIT_COND_DEFAULT="1"
export SEARCH_TERM_DEFAULT="TODO"

[[ "${DEBUG}" == "${TRUE}" ]] && exit $(( TRUE )) || return $(( TRUE ))
