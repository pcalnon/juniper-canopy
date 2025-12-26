#!/usr/bin/env bash
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       1.0.0
# File Name:     common.conf
# File Path:     <Project>/<Sub-Project>/<Application>/conf/
#
# Date:          2025-09-16
# Last Modified: 2025-12-25
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#     This config file is sourced to define global constants used in project util scripts
#
#####################################################################################################################################################################################################
# Notes:
#     This script functions as a Common config file for all scripts in the current Project/Sub-Project/Application_Name dir
#
#     Warning:
#         This config file is sourced by the config files for the api_request.bash and launch_close.bash scripts.
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
export TRUE="0"
export FALSE="1"

# export DEBUG="${TRUE}"
export DEBUG="${FALSE}"


#####################################################################################################################################################################################################
# Only Source this conf file Once
#####################################################################################################################################################################################################
if [[ "${COMMON_CONF_SOURCED}" != "${TRUE}" ]]; then
    export COMMON_CONF_SOURCED="${TRUE}"
else
    log_warning "common.conf already sourced.  Skipping re-source."
    [[ "${DEBUG}" == "${TRUE}" ]] && exit $(( TRUE )) || return $(( TRUE ))
fi


#####################################################################################################################################################################################################
# Define Current Active Language for this Project
#####################################################################################################################################################################################################
export PYTHON_LANGUAGE_NAME="python"
export CPP_LANGUAGE_NAME="c++"
export RUST_LANGUAGE_NAME="rust"

# export LANG_NAME="${RUST_LANGUAGE_NAME}"
export LANG_NAME="${PYTHON_LANGUAGE_NAME}"
# export LANG_NAME="${CPP_LANGUAGE_NAME}"


#####################################################################################################################################################################################################
# Define Calling Script Constants
#####################################################################################################################################################################################################
export SCRIPT_NAME_ID="2"
export LINE_NO_ID="1"
export FUNC_NAME_ID="2"


#####################################################################################################################################################################################################
# Define Constants for the Current Script Environment
#####################################################################################################################################################################################################
export SCRIPTS_EXT="bash"
export UTIL_DIR_NAME="util"
export LOGGING_NAME="logging"
export FUNCTIONS_FILE_ROOT="functions"


#####################################################################################################################################################################################################
# Define Parent's Calling Script Info Constants
#####################################################################################################################################################################################################
# shellcheck disable=SC2155
export CALLING_SCRIPT_PATH="$(realpath "${BASH_SOURCE[${SCRIPT_NAME_ID}]}")"
# shellcheck disable=SC2155
export CALLING_SCRIPT="$(basename "${CALLING_SCRIPT_PATH}")"
export CALLING_LINE="${BASH_LINENO[${LINE_NO_ID}]}"
export CALLING_FUNC="${FUNCNAME[FUNC_NAME_ID]}"


#####################################################################################################################################################################################################
# Define constants for the common config file's functions config file
#####################################################################################################################################################################################################
# shellcheck disable=SC2155
export CURRENT_NAME="$(basename "${CURRENT_PATH}")"
# shellcheck disable=SC2155
export CURRENT_DIR="$(dirname "${CURRENT_PATH}")"

export COMMON_FUNCTIONS_FILENAME="${LOGGING_NAME}_${FUNCTIONS_FILE_ROOT}.${CONF_EXT}"
export COMMON_FUNCTIONS_FILE="${CONF_DIR}/${COMMON_FUNCTIONS_FILENAME}"


#####################################################################################################################################################################################################
# Parse and Validate the Parent Path Param
#####################################################################################################################################################################################################
# shellcheck disable=SC2155
export PARENT_PATH_PARAM="$(realpath "${PARENT_PATH_PARAM}")"
[[ ("${PARENT_PATH_PARAM}" == "") || ( ! -f "${PARENT_PATH_PARAM}" ) ]] && log_critical "Parent Path Param: ${PARENT_PATH_PARAM} is not a valid file. Unable to Continue."


#####################################################################################################################################################################################################
# Define Constants for sourcing the logging conf file
#####################################################################################################################################################################################################
export LOGGING_CONF_FILENAME="${LOGGING_NAME}.${CONF_EXT}"
export LOGGING_CONF_FILE="${CONF_DIR}/${LOGGING_CONF_FILENAME}"


#####################################################################################################################################################################################################
# Validate and Source the logging conf file
#####################################################################################################################################################################################################
[[ ( "${LOGGING_CONF_FILE}" == "" ) || ( ! -f "${LOGGING_CONF_FILE}" ) ]] && log_fatal "Logging Config File: ${LOGGING_CONF_FILE} is not a valid file. Unable to Continue."
if [[ "${DEBUG}" == "${TRUE}" ]]; then
    bash "${LOGGING_CONF_FILE}"
    SUCCESS="$?"
else
    # shellcheck disable=SC1090
    source "${LOGGING_CONF_FILE}"
    SUCCESS="$?"
fi
[[ "${SUCCESS}" != "${TRUE}" ]] && log_fatal "Failed to source the logging config file: ${LOGGING_CONF_FILE}"
log_info "Completed Calling the logging config file: ${LOGGING_CONF_FILE}"  # Standard Logging is enabled from this point



#####################################################################################################################################################################################################
# Define Project-Global, Absolute-Path-Based Environment Constants
#####################################################################################################################################################################################################

#####################################################################################################################################################################################################
# Define Top Level, Environment Constants
#####################################################################################################################################################################################################
export PROJECT_NAME="Juniper"
export SUB_PROJECT_NAME="JuniperCanopy"
export APP_NAME="juniper_canopy"
export JUNIPER_APPLICATION_VERSION="0.7.3-1"

export HOME_DIR="${HOME}"
export DEV_DIR_NAME="Development"
export DEV_DIR="${HOME_DIR}/${DEV_DIR_NAME}"


#####################################################################################################################################################################################################
# Define Global Language Constants
#####################################################################################################################################################################################################
export PYTHON_LANGUAGE_DIR_NAME="${PYTHON_LANGUAGE_NAME}"
export CPP_LANGUAGE_DIR_NAME="${CPP_LANGUAGE_NAME}"
export RUST_LANGUAGE_PARENT_ROOT_DIR_NAME="${RUST_LANGUAGE_NAME}"
export RUST_LANGUAGE_PROJECT_ROOT_DIR_NAME="rust_mudgeon"
export RUST_LANGUAGE_DIR_NAME="${RUST_LANGUAGE_PARENT_ROOT_DIR_NAME}/${RUST_LANGUAGE_PROJECT_ROOT_DIR_NAME}"

export PYTHON_DEV_DIR="${DEV_DIR}/${PYTHON_LANGUAGE_DIR_NAME}"
export CPP_DEV_DIR="${DEV_DIR}/${CPP_LANGUAGE_DIR_NAME}"
export RUST_DEV_DIR="${DEV_DIR}/${RUST_LANGUAGE_DIR_NAME}"


#####################################################################################################################################################################################################
# Define environment constants for the current selected language
#####################################################################################################################################################################################################
if [[ ${LANG_NAME} == "${PYTHON_LANGUAGE_NAME}" ]]; then
    export LANG_DIR="${PYTHON_DEV_DIR}"
    export SRC_FILE_SUFFIX="py"
    export CONF_FILE_SUFFIX="conf"
elif [[ ${LANG_NAME} == "${CPP_LANGUAGE_NAME}" ]]; then
    export LANG_DIR="${CPP_DEV_DIR}"
    export SRC_FILE_SUFFIX="cpp"
    export CONF_FILE_SUFFIX="cnf"
elif [[ ${LANG_NAME} == "${RUST_LANGUAGE_NAME}" ]]; then
    export LANG_DIR="${RUST_DEV_DIR}"
    export SRC_FILE_SUFFIX="rs"
    export CONF_FILE_SUFFIX="cfg"
else
    log_critical "Error: Unknown Language: ${LANG_NAME}"
fi


#####################################################################################################################################################################################################
# Define Global OS Name Constants
#####################################################################################################################################################################################################
export UBUNTU="Ubuntu"
export FEDORA="Fedora"
export RHEL="Red Hat"
export CENTOS="Centos"
export MACOS="Darwin"
export LINUX="Linux"
export UNKNOWN="Unknown"


#####################################################################################################################################################################################################
# Define Global Date Related Constants
#####################################################################################################################################################################################################
export BEGINNING_TIME="2023-11-27"
export ESTIMATED_FINAL_WEEK="2042-06-10"


#####################################################################################################################################################################################################
# Define Global Directory Name Constants
#####################################################################################################################################################################################################
export BIN_DIR_NAME="bin"
export CONF_DIR_NAME="conf"
export CUDA_DIR_NAME="cuda"
export DATA_DIR_NAME="data"
export DEBUG_DIR_NAME="debug"
export DOCUMENT_DIR_NAME="docs"
export GIT_DIR_NAME=".git"
export GIT_HUB_DIR_NAME=".github"
export HDF5_DIR_NAME="hdf5"
export IMAGES_DIR_NAME="images"
export INTEGRATION_TESTS_DIR_NAME="integration"
export JUPYTER_DIR_NAME="jupyter"
export KAGGLE_DIR_NAME="kaggle"
export LIBRARY_DIR_NAME="libs"
export LOGGING_DIR_NAME="logs"
export MYPY_CACHE_DIR_NAME=".mypy_cache"
export NOTES_DIR_NAME="notes"
export PAPERS_DIR_NAME="papers"
export PERF_TESTS_DIR_NAME="performance"
export PROMPTS_DIR_NAME="prompts"
export PYTEST_CACHE_DIR_NAME=".pytest_cache"
export REFS_DIR_NAME="refs"
export REGRESSION_TESTS_DIR_NAME="regression"
export RELEASE_DIR_NAME="release"
export REPORTS_DIR_NAME="reports"
export RESOURCES_DIR_NAME="resources"
export SNAPSHOTS_DIR_NAME="snapshots"
export SOURCE_DIR_NAME="src"
export TARGET_DIR_NAME="target"
export TEMP_DIR_NAME="temp"
export TESTS_DIR_NAME="tests"
export TESTS_REPORTS_DIR_NAME="reports"
export TESTS_UTIL_DIR_NAME="util"
export TORCHEXPLORER_STANDALONE_DIR_NAME="torchexplorer_standalone"
export TRUNK_DIR_NAME=".trunk"
export TRUNK_NEW_DIR_NAME=".trunk_new"
export UNIT_TESTS_DIR_NAME="unit"
export UTILITY_DIR_NAME="util"
export VENV_DIR_NAME=".venV"
export VIZ_DIR_NAME="viz"
export VSCODE_DIR_NAME=".vscode"


#####################################################################################################################################################################################################
# Define Global Directory Name Alias Constants
#####################################################################################################################################################################################################
export BINARY_DIR_NAME="${TARGET_DIR_NAME}"
export SCRIPTS_DIR_NAME="${UTILITY_DIR_NAME}"
export OUTPUT_DIR_NAME="${DOCUMENT_DIR_NAME}"


#####################################################################################################################################################################################################
# Define Comprehensive List of GLobal Project Directories
#####################################################################################################################################################################################################
# Top Level Directories
export BIN_DIR="${PROJ_DIR}/${BIN_DIR_NAME}"
export CONF_DIR="${PROJ_DIR}/${CONF_DIR_NAME}"
export CUDA_DIR="${PROJ_DIR}/${CUDA_DIR_NAME}"
export DATA_DIR="${PROJ_DIR}/${DATA_DIR_NAME}"
export DOCUMENT_DIR="${PROJ_DIR}/${DOCUMENT_DIR_NAME}"
export GIT_DIR="${PROJ_DIR}/${GIT_DIR_NAME}"
export GIT_HUB_DIR="${PROJ_DIR}/${GIT_HUB_DIR_NAME}"
export HDF5_DIR="${PROJ_DIR}/${HDF5_DIR_NAME}"
export IMAGES_DIR="${PROJ_DIR}/${IMAGES_DIR_NAME}"
export JUPYTER_DIR="${PROJ_DIR}/${JUPYTER_DIR_NAME}"
export KAGGLE_DIR="${PROJ_DIR}/${KAGGLE_DIR_NAME}"
export LIBRARY_DIR="${PROJ_DIR}/${LIBRARY_DIR_NAME}"
export LOGGING_DIR="${PROJ_DIR}/${LOGGING_DIR_NAME}"
export MYPY_CACHE_DIR="${PROJ_DIR}/${MYPY_CACHE_DIR_NAME}"
export NOTES_DIR="${PROJ_DIR}/${NOTES_DIR_NAME}"
export OUTPUT_DIR="${PROJ_DIR}/${OUTPUT_DIR_NAME}"
export PAPERS_DIR="${PROJ_DIR}/${PAPERS_DIR_NAME}"
export PROMPTS_DIR="${PROJ_DIR}/${PROMPTS_DIR_NAME}"
export REFS_DIR="${PROJ_DIR}/${REFS_DIR_NAME}"
export REPORTS_DIR="${PROJ_DIR}/${REPORTS_DIR_NAME}"
export RESOURCES_DIR="${PROJ_DIR}/${RESOURCES_DIR_NAME}"
export SCRIPTS_DIR="${PROJ_DIR}/${SCRIPTS_DIR_NAME}"
export SOURCE_DIR="${PROJ_DIR}/${SOURCE_DIR_NAME}"
export TEMP_DIR="${PROJ_DIR}/${TEMP_DIR_NAME}"
export TORCHEXPLORER_STANDALONE_DIR="${PROJ_DIR}/${TORCHEXPLORER_STANDALONE_DIR_NAME}"
export TRUNK_DIR="${PROJ_DIR}/${TRUNK_DIR_NAME}"
export TRUNK_NEW_DIR="${PROJ_DIR}/${TRUNK_NEW_DIR_NAME}"
export UTILITY_DIR="${PROJ_DIR}/${UTILITY_DIR_NAME}"
export VENV_DIR="${PROJ_DIR}/${VENV_DIR_NAME}"
export VIZ_DIR="${PROJ_DIR}/${VIZ_DIR_NAME}"
export VSCODE_DIR="${PROJ_DIR}/${VSCODE_DIR_NAME}"

# Source Dir Children, 2nd Level Dirs
export BINARY_DIR="${SOURCE_DIR}/${BINARY_DIR_NAME}"
export DEBUG_DIR="${SOURCE_DIR}/${DEBUG_DIR_NAME}"
export PYTEST_CACHE_DIR="${SOURCE_DIR}/${PYTEST_CACHE_DIR_NAME}"
export RELEASE_DIR="${SOURCE_DIR}/${RELEASE_DIR_NAME}"
export SNAPSHOTS_DIR="${SOURCE_DIR}/${SNAPSHOTS_DIR_NAME}"
export TARGET_DIR="${SOURCE_DIR}/${TARGET_DIR_NAME}"
export TESTS_DIR="${SOURCE_DIR}/${TESTS_DIR_NAME}"

# Target Dir Children, 3rd Level Dirs
export DEBUG_EXECUTABLE_DIR="${TARGET_DIR}/${DEBUG_DIR_NAME}"
export RELEASE_EXECUTABLE_DIR="${TARGET_DIR}/${RELEASE_DIR_NAME}"

# Tests Dir Children, 3rd Level Dirs
export INTEGRATION_TESTS_DIR="${TESTS_DIR}/${INTEGRATION_TESTS_DIR_NAME}"
export PERF_TESTS_DIR="${TESTS_DIR}/${PERF_TESTS_DIR_NAME}"
export REGRESSION_TESTS_DIR="${TESTS_DIR}/${REGRESSION_TESTS_DIR_NAME}"
export TESTS_REPORTS_DIR="${TESTS_DIR}/${TESTS_REPORTS_DIR_NAME}"
export TESTS_UTIL_DIR="${TESTS_DIR}/${TESTS_UTIL_DIR_NAME}"
export UNIT_TESTS_DIR="${TESTS_DIR}/${UNIT_TESTS_DIR_NAME}"


#####################################################################################################################################################################################################
# Define Global Script Name Constants
#####################################################################################################################################################################################################
export GET_OS_SCRIPT_NAME="__get_os_name.bash"
export GET_PROJECT_SCRIPT_NAME="__get_project_dir.bash"
export DATE_FUNCTIONS_NAME="__date_functions.bash"
export ADD_CRATES_SCRIPT_NAME="add_crates.bash"
export GIT_LOG_SCRIPT_NAME="git_log_weeks.bash"


#####################################################################################################################################################################################################
# Define Global File Name Constants
#####################################################################################################################################################################################################
export SCRIPT_FILE_SUFFIX="bash"

export DATA_FILE_SUFFIX="dat"
export LOG_FILE_SUFFIX="log"
export YAML_FILE_SUFFIX="yaml"


#####################################################################################################################################################################################################
# Define Global File Name Constants
#####################################################################################################################################################################################################
export LOG_FILE_MODULE_NAME="juniper.${LOG_FILE_SUFFIX}"
export LOG_FILE_STARTUP_NAME="startup.${LOG_FILE_SUFFIX}"
export LOG_CONFIG_FILE_NAME="log4rs.${YAML_FILE_SUFFIX}"
export JUNIPER_CONF_FILE_NAME="juniper.${YAML_FILE_SUFFIX}"


#####################################################################################################################################################################################################
# Define Global Script Path Constants
#####################################################################################################################################################################################################
export GET_OS_SCRIPT="${ROOT_UTIL_DIR}/${GET_OS_SCRIPT_NAME}"
export GET_PROJECT_SCRIPT="${ROOT_UTIL_DIR}/${GET_PROJECT_SCRIPT_NAME}"
export ADD_CRATES_SCRIPT="${ROOT_UTIL_DIR}/${ADD_CRATES_SCRIPT_NAME}"
export GIT_LOG_SCRIPT="${ROOT_UTIL_DIR}/${GIT_LOG_SCRIPT_NAME}"
export DATE_FUNCTIONS_SCRIPT="${ROOT_UTIL_DIR}/${DATE_FUNCTIONS_NAME}"


#####################################################################################################################################################################################################
# Define Tensor Type Constants
#####################################################################################################################################################################################################
export TENSOR_DOUBLE_CPU="DOUBLE_CPU"
export TENSOR_DOUBLE_CUDA="DOUBLE_CUDA"
export TENSOR_FLOAT_CPU="FLOAT_CPU"
export TENSOR_FLOAT_CUDA="FLOAT_CUDA"


#####################################################################################################################################################################################################
# Define USB archive Constants
#####################################################################################################################################################################################################
export USB_ARCHIVE_MOUNT_UBUNTU="/media/pcalnon"
export USB_ARCHIVE_MOUNT_MACOS="/Volumes"

export USB_ARCHIVE_DEVICE_MACOS="Untitled"
export USB_ARCHIVE_DEVICE_LINUX_SAMSUNG_BRONZE="DFF3-2782"  # Archive USB Drive on keychain, bronze
export USB_ARCHIVE_DEVICE_LINUX_SAMSUNG_SILVER="EBC5-F0A3"  # Archive USB Drive on keychain, silver
export USB_ARCHIVE_DEVICE_LINUX_OLD_ARCHIVE="USB30FD"  # Archive USB Drive in Safe
export USB_ARCHIVE_DEVICE_LINUX_LIST="${USB_ARCHIVE_DEVICE_LINUX_SAMSUNG_BRONZE} ${USB_ARCHIVE_DEVICE_LINUX_SAMSUNG_SILVER} ${USB_ARCHIVE_DEVICE_LINUX_OLD_ARCHIVE} ${USB_ARCHIVE_DEVICE_MACOS}"

export JUNIPER_PROJECT_NAME="${PROJECT_NAME}"
# export JUNIPER_PROJECT_NAME="${SUB_PROJECT_NAME}"

export USB_ARCHIVE_DIR_NAME_RUST="${JUNIPER_PROJECT_NAME}-${JUNIPER_APPLICATION_VERSION}_${RUST_LANGUAGE_DIR_NAME}"
export USB_ARCHIVE_DIR_NAME_CPP="${JUNIPER_PROJECT_NAME}-${JUNIPER_APPLICATION_VERSION}_${PYTHON_LANGUAGE_DIR_NAME}"
export USB_ARCHIVE_DIR_NAME_PYTHON="${JUNIPER_PROJECT_NAME}-${JUNIPER_APPLICATION_VERSION}_${CPP_LANGUAGE_DIR_NAME}"


#####################################################################################################################################################################################################
# Define Global OS Specific Command Constants
#####################################################################################################################################################################################################
export MILIS_FORMAT="%s"

# MacOS Constants
export MACOS_DATE_COMMAND="/bin/date"
export MACOS_DATE_SWITCH="-j "
export MACOS_DATE_FORMAT="%Y-%m-%d"

export MACOS_DATE_MONTHS="m"
export MACOS_DATE_WEEKS="w"
export MACOS_DATE_DAYS="d"

# Linux Constants
export LINUX_DATE_COMMAND="/usr/bin/date"
export LINUX_DATE_SWITCH="-d"
export LINUX_DATE_FORMAT="%F"

export LINUX_DATE_MONTHS="months"
export LINUX_DATE_WEEKS="weeks"
export LINUX_DATE_DAYS="days"


#####################################################################################################################################################################################################
# Define Constants for sourcing the common functions conf file
#####################################################################################################################################################################################################
export COMMON_FUNCTIONS_NAME_ROOT="${COMMON_FILE_ROOT}_${FUNCTIONS_FILE_ROOT}"
export COMMON_FUNCTIONS_CONF_FILENAME="${COMMON_FUNCTIONS_NAME_ROOT}.${CONF_EXT}"
export COMMON_FUNCTIONS_CONF_FILE="${CONF_DIR}/${COMMON_FUNCTIONS_CONF_FILENAME}"


#####################################################################################################################################################################################################
# Validate and Source the common.conf file's common_functions.conf file
#####################################################################################################################################################################################################
[[ ( "${COMMON_FUNCTIONS_CONF_FILE}" == "" ) || ( ! -f "${COMMON_FUNCTIONS_CONF_FILE}" ) ]] && log_fatal "Common Functions Config File: ${COMMON_FUNCTIONS_CONF_FILE} is not a valid file. Unable to Continue."
# shellcheck disable=SC1091,SC1090,SC2015
[[ "${DEBUG}" == "${TRUE}" ]] && { bash "${COMMON_FUNCTIONS_CONF_FILE}"; SUCCESS="$?"; } || { source "${COMMON_FUNCTIONS_CONF_FILE}"; SUCCESS="$?"; }
[[ "${SUCCESS}" != "${TRUE}" ]] && log_fatal "Failed to source the common functions config file: ${COMMON_FUNCTIONS_CONF_FILE}"
log_info "Completed Calling the common functions config file: ${COMMON_FUNCTIONS_CONF_FILE}"


#####################################################################################################################################################################################################
# Retrieve and Validate parent script info and constants
#####################################################################################################################################################################################################
# shellcheck disable=SC2155,SC2153
export PARENT_CMD="$( tr -d '\0' < /proc/"${PARENT_PID}"/cmdline )"
log_trace "PARENT_CMD: ${PARENT_CMD}"
# shellcheck disable=SC2155
export PARENT_CALL="$(ps -o args="${PARENT_PID}")"
log_trace "PARENT_CALL: ${PARENT_CALL}"
export PARENT_PARAM="${PARENT_PATH_PARAM}"
log_trace "PARENT_PARAM: ${PARENT_PARAM}"
validate_parent_path "${PARENT_CMD}" "${PARENT_CALL}" "${PARENT_PARAM}"
log_debug "Parent Script Path: \"${PARENT_SCRIPT_PATH}\""


#####################################################################################################################################################################################################
# Build Parent Script Config File Path
#####################################################################################################################################################################################################
PARENT_CONF="${PARENT_SCRIPT_PATH%.*}.${CONF_EXT}"
log_debug "Parent Script Config File: \"${PARENT_CONF}\""
PARENT_CONF_FILENAME="$(basename "${PARENT_CONF}")"
log_debug "Parent Script Config File Name: \"${PARENT_CONF_FILENAME}\""
PARENT_DIR="$(dirname "${PARENT_CONF}")"
log_debug "Parent Script Config File Dir: \"${PARENT_DIR}\""
PARENT_ROOT_DIR="$(dirname "${PARENT_DIR}")"
log_debug "Parent Script Config File Root Dir: \"${PARENT_ROOT_DIR}\""
PARENT_CONF_DIR="${PARENT_ROOT_DIR}/${CONF_EXT}"
log_debug "Parent Script Config Dir: \"${PARENT_CONF_DIR}\""


#####################################################################################################################################################################################################
# Validate config directory and Primary Config File for calling script
#####################################################################################################################################################################################################
validate_conf_dir "${PARENT_CONF_DIR}" "${PROJ_CONF_DIR}"
log_info "Successfully Validated conf dir for Calling Script primary config file: \"${PARENT_CONF_DIR}\""
PRIMARY_CONF_FILE="${PARENT_CONF_DIR}/${PARENT_CONF_FILENAME}"
log_debug "Calling Script Primary Conf File: \"${PRIMARY_CONF_FILE}\""
validate_conf_file "${PRIMARY_CONF_FILE}"; SUCCESS="$?"
[[ "${SUCCESS}" != "${TRUE}" ]] && log_critical "Failed to validate Primary config file: \"${PRIMARY_CONF_FILE}\""
log_info "Successfully Validated the Parent Script's primary config file: ${PRIMARY_CONF_FILE}"
export PRIMARY_CONF_FILE


#####################################################################################################################################################################################################
# Source the Calling Script's Primary config file and check result
#####################################################################################################################################################################################################
if [[ "${DEBUG}" == "${TRUE}" ]]; then
    log_debug "Running Calling Script's Primary config file: \"${PRIMARY_CONF_FILE}\""
    bash "${PRIMARY_CONF_FILE}"; SUCCESS="$?"
else
    log_debug "Sourcing Calling Script's Primary config file: \"${PRIMARY_CONF_FILE}\""
    # shellcheck source=/dev/null
    source "${PRIMARY_CONF_FILE}"; SUCCESS="$?"
fi
[[ "${SUCCESS}" != "${TRUE}" ]] && log_critical "Failed to source Primary config file: \"${PRIMARY_CONF_FILE}\""
log_info "Completed sourcing Primary config file. Returned \"${SUCCESS}\""


[[ "${DEBUG}" == "${TRUE}" ]] && exit $(( TRUE )) || return $(( TRUE ))
