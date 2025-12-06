#!/bin/bash
#####################################################################################################################################################################################################
# Application: Juniper
# Script Name: __get_project_dir.bash
# Script Path: ${HOME}/Development/rust/rust_mudgeon/juniper/util/__get_project_dir.bash
#
# Description: This script returns the absolute path of the directory for the current project
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
ROOT_CONF_FILE_NAME="script_util.cfg"
ROOT_PROJ_DIR="${HOME}/Development/rust/rust_mudgeon/${ROOT_PROJ_NAME}"
ROOT_CONF_DIR="${ROOT_PROJ_DIR}/${ROOT_CONF_NAME}"
ROOT_CONF_FILE="${ROOT_CONF_DIR}/${ROOT_CONF_FILE_NAME}"
source ${ROOT_CONF_FILE}


##################################################################################
# Determine Project Dir
##################################################################################
SCRIPT_PATH="${1}"
if [[ ${SCRIPT_PATH} == "" ]]; then
    echo "Error: Script path not provided."
    exit 1
fi

while [[ -L "${SCRIPT_PATH}" ]]; do
    SCRIPT_DIR="$(cd -P "$(dirname "${SCRIPT_PATH}")" > /dev/null 2>&1 && pwd)"
    SCRIPT_PATH="$(readlink "${SCRIPT_PATH}")"
    if [[ ${SCRIPT_PATH} != /* ]]; then
        SCRIPT_PATH="${SCRIPT_DIR}/${SCRIPT_PATH}"
    fi
done

SCRIPT_PATH="$(readlink -f "${SCRIPT_PATH}")"
SCRIPT_DIR="$(cd -P "$(dirname -- "${SCRIPT_PATH}")" > /dev/null 2>&1 && pwd)"
PROJECT_DIR="$(dirname -- ${SCRIPT_DIR})"
BASE_DIR="${PROJECT_DIR}"
echo "${BASE_DIR}"
