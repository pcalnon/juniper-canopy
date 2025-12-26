#!/usr/bin/env bash
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       0.1.4 (0.7.3)
# File Name:     create_performance_profile.conf
# File Path:     <Project>/<Sub-Project>/<Application>/conf/
#
# Date:          2025-10-11
# Last Modified: 2025-12-25
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#     This script Profiles the Python class for optimization
#
#####################################################################################################################################################################################################
# Notes:
#
########################################################################################################)#############################################################################################
# References:
#
#####################################################################################################################################################################################################
# TODO :
#
#     Moved defs to config file
#
#
#####################################################################################################################################################################################################
# COMPLETED:
#
#####################################################################################################################################################################################################


#####################################################################################################################################################################################################
# Define Script Constants
#####################################################################################################################################################################################################
export TRUE="0"
export FALSE="1"

# export DEBUG="${TRUE}"
export DEBUG="${FALSE}"


#####################################################################################################################################################################################################
# Only Source this conf file Once
#####################################################################################################################################################################################################
if [[ "${CREATE_PERFORMANCE_PROFILE_SOURCED}" != "${TRUE}" ]]; then
    export CREATE_PERFORMANCE_PROFILE_SOURCED="${TRUE}"
else
    log_warning "create_performance_profile.conf already sourced.  Skipping re-source."
    [[ "${DEBUG}" == "${TRUE}" ]] && exit $(( TRUE )) || return $(( TRUE ))
fi


#######################################################################################################################################################################################
# Define the Script Environment File Constants
#######################################################################################################################################################################################
GET_FILENAMES_SCRIPT_NAME="get_module_filenames.bash"
export GET_FILENAMES_SCRIPT="${UTIL_DIR}/${GET_FILENAMES_SCRIPT_NAME}"
GET_SOURCETREE_SCRIPT_NAME="source_tree.bash"
export GET_SOURCETREE_SCRIPT="${UTIL_DIR}/${GET_SOURCETREE_SCRIPT_NAME}"
GET_TODO_COMMENTS_SCRIPT_NAME="get_todo_comments.bash"
export GET_TODO_COMMENTS_SCRIPT="${UTIL_DIR}/${GET_TODO_COMMENTS_SCRIPT_NAME}"
GET_FILE_TODO_SCRIPT_NAME="get_file_todo.bash"
export GET_FILE_TODO_SCRIPT="${UTIL_DIR}/${GET_FILE_TODO_SCRIPT_NAME}"
GIT_LOG_WEEKS_SCRIPT_NAME="__git_log_weeks.bash"
export GIT_LOG_WEEKS_SCRIPT="${UTIL_DIR}/${GIT_LOG_WEEKS_SCRIPT_NAME}"

PYTHON_FILE_NAME="main.py"
export PYTHON_FILE="${SRC_DIR}/${PYTHON_FILE_NAME}"

# OUTPUT_FILE_NAME_ROOT="dynamic_nn"
# OUTPUT_FILE_NAME_ROOT="juniper"
export OUTPUT_FILE_NAME_ROOT="Juniper"
export OUTPUT_FILE_NAME_EXT="prof"
# shellcheck disable=SC2155
export DATE_STAMP="$(date +%F_%T)"
export OUTPUT_FILE_NAME="${OUTPUT_FILE_NAME_ROOT}_${DATE_STAMP}.${OUTPUT_FILE_NAME_EXT}"
export OUTPUT_FILE="${CONF_DIR}/${OUTPUT_FILE_NAME}"


#######################################################################################################################################################################################
# Define the Script Constants
#    /Users/pcalnon/opt/anaconda3/envs/pytorch_cuda/bin/python
#######################################################################################################################################################################################
export PYTHON_NAME="python"
export PYTHON_ENV_ROOT="/opt/miniforge3/envs/JuniperCanopy/bin"
export PYTHON_ENV="${PYTHON_ENV_ROOT}/${PYTHON_NAME}"

export OS_TYPE="ubuntu"
export OS_TYPE_PREFIX="macOS"
export ENV_PREFIX="opt"

if [[ -f "$(which sw_vers)" ]]; then
    # shellcheck disable=SC2155
    export OS_TYPE="$(sw_vers -ProductName)"
fi

if [[ "${OS_TYPE}" == "${OS_TYPE_PREFIX}" ]]; then
    export PYTHON_ENV="${ENV_PREFIX}/${PYTHON_ENV}"
fi

export PYTHON="${HOME}/${PYTHON_ENV}"
export PROFILER="cProfile"


#######################################################################################################################################################################################
# Run env info functions
#######################################################################################################################################################################################
# shellcheck disable=SC2155
export BASE_DIR=$(${GET_PROJECT_SCRIPT} "${BASH_SOURCE[0]}")
# Determine Host OS
# shellcheck disable=SC2155
export CURRENT_OS=$(${GET_OS_SCRIPT})
# Define Script Functions
# source "${DATE_FUNCTIONS_SCRIPT}"


#######################################################################################################################################################################################
# Define Parameter Constants
#######################################################################################################################################################################################
export MODULE_FLAG="-m"
export OUTPUT_FLAG="-o"

export MODULE_PARAM="${MODULE_FLAG} ${PROFILER}"
export OUTPUT_PARAM="${OUTPUT_FLAG} ${OUTPUT_FILE}"

# shellcheck disable=SC2034
export PARAM_LIST="${MODULE_PARAM} ${OUTPUT_PARAM}"
