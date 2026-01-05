#!/usr/bin/env bash
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       0.1.4 (0.7.3)
# File Name:     proto.bash
# File Path:     <Project>/<Sub-Project>/<Application>/util/
#
# Date:          2025-10-11
# Last Modified: 2026-01-02
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#     This script finds duplicate method definitions in the specified group of files
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
#####################################################################################################################################################################################################
# COMPLETED:
#
#####################################################################################################################################################################################################


#####################################################################################################################################################################################################
# Initialize script by sourcing the init_conf.bash config file
#####################################################################################################################################################################################################
set -o functrace
# shellcheck disable=SC2155
export PARENT_PATH_PARAM="$(realpath "${BASH_SOURCE[0]}")" && INIT_CONF="$(dirname "$(dirname "${PARENT_PATH_PARAM}")")/conf/init.conf"
# shellcheck disable=SC2015,SC1090
[[ -f "${INIT_CONF}" ]] && source "${INIT_CONF}" || { echo "Init Config File Not Found. Unable to Continue."; exit 1; }


#####################################################################################################################################################################################################
# Define Global Project Constants
#####################################################################################################################################################################################################
HOME_DIR="${HOME}"

export FUNCTION_NAME="${0##*/}"

# PROJ_NAME="dynamic_nn"
# PROJ_NAME="juniper"
export PROJ_NAME="Juniper"
export SUB_PROJ_NAME="JuniperCanopy"
export APP_NAME="juniper_canopy"


#PROJ_LANG_DIR_NAME="rust/rust_mudgeon"
PROJ_LANG_DIR_NAME="python"

DEV_DIR_NAME="Development"
export DEV_DIR="${HOME_DIR}/${DEV_DIR_NAME}"
PROJ_ROOT_DIR="${DEV_DIR}/${PROJ_LANG_DIR_NAME}"
# export PROJ_DIR="${PROJ_ROOT_DIR}/${PROJ_NAME}/${SUB_PROJ_NAME}/${APP_NAME}"
export PROJ_DIR="${PROJ_ROOT_DIR}/${SUB_PROJ_NAME}/${APP_NAME}"

CONF_DIR_NAME="conf"
export CONF_DIR="${PROJ_DIR}/${CONF_DIR_NAME}"
CONF_FILE_NAME="common.conf"
export CONF_FILE="${CONF_DIR}/${CONF_FILE_NAME}"


# shellcheck disable=SC1090
source "${CONF_FILE}"


#######################################################################################################################################################################################
# Configure Script Environment
#######################################################################################################################################################################################
SRC_DIR_NAME="src"
export SRC_DIR="${PROJ_DIR}/${SRC_DIR_NAME}"
LOG_DIR_NAME="logs"
export LOG_DIR="${PROJ_DIR}/${LOG_DIR_NAME}"
UTIL_DIR_NAME="util"
export UTIL_DIR="${PROJ_DIR}/${UTIL_DIR_NAME}"
DATA_DIR_NAME="data"
export DATA_DIR="${PROJ_DIR}/${DATA_DIR_NAME}"
VIZ_DIR_NAME="viz"
export VIZ_DIR="${PROJ_DIR}/${VIZ_DIR_NAME}"
TEST_DIR_NAME="tests"
export TEST_DIR="${PROJ_DIR}/${TEST_DIR_NAME}"


#######################################################################################################################################################################################
# Define the Script Environment File Constants
#######################################################################################################################################################################################
# CONF_FILE_NAME="logging_config.yaml"
# CONF_FILE="${CONF_DIR}/${CONF_FILE_NAME}"
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


####################################################################################################
# Run env info functions
####################################################################################################
# shellcheck disable=SC2155
export BASE_DIR=$(${GET_PROJECT_SCRIPT} "${BASH_SOURCE[0]}")
# Determine Host OS
# shellcheck disable=SC2155
export CURRENT_OS="$(bash "${GET_OS_SCRIPT}")"
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
    SIZE="$(round_size "${SIZEF}")"
    echo "${SIZE}"
}

function readable_size() {
    CURRENT_SIZE="${1}"
    LABEL_INDEX=0
    export BYTES_LABEL=""
    while (( $(echo "${CURRENT_SIZE} >= ${SIZE_LABEL_MAG}" | bc -l) )); do
        CURRENT_SIZE="$(echo "${CURRENT_SIZE} / ${SIZE_LABEL_MAG}" | bc -l)"
        LABEL_INDEX=$(( LABEL_INDEX + 1 ))
    done
    SIZE="$(round_size "${CURRENT_SIZE}")"
    if (( LABEL_INDEX > 0 )); then
        BYTE_LABEL="${SIZE_LABELS[0]}"
    fi
    READABLE="${SIZE} ${SIZE_LABELS[${LABEL_INDEX}]}${BYTE_LABEL}"
    echo "${READABLE}"
}


####################################################################################################
#
####################################################################################################
