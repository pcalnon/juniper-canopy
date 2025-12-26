#!/usr/bin/env bash
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       0.1.4 (0.7.3)
# File Name:     save_to_usb.conf
# File Path:     <Project>/<Sub-Project>/<Application>/conf/
#
# Date:          2025-10-11
# Last Modified: 2025-12-25
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#     This script saves the Juniper development directory to a USB drive
#
#####################################################################################################################################################################################################
# Notes:
#    Juniper-7.3.1_python/
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
# Define Boolean Constants
#####################################################################################################################################################################################################
export TRUE="1"
export FALSE="0"

# export DEBUG="${TRUE}"
export DEBUG="${FALSE}"


#####################################################################################################################################################################################################
# Only Source this conf file Once
#####################################################################################################################################################################################################
if [[ "${SAVE_TO_USB_SOURCED}" != "${TRUE}" ]]; then
    export SAVE_TO_USB_SOURCED="${TRUE}"
else
    log_warning "save_to_usb.conf already sourced.  Skipping re-source."
    [[ "${DEBUG}" == "${TRUE}" ]] && exit $(( TRUE )) || return $(( TRUE ))
fi


####################################################################################################
# Define Global Environment DirectoryConfiguration Constants
# TODO: add these to a config file
####################################################################################################
# shellcheck disable=SC2155
export SCRIPT_NAME="$(basename "${BASH_SOURCE[0]}")"
log_debug "SCRIPT_NAME: ${SCRIPT_NAME}"
# shellcheck disable=SC2155
export SCRIPT_PATH="$(dirname "$(get_script_path)")"
log_debug "SCRIPT_PATH: ${SCRIPT_PATH}"
# shellcheck disable=SC2155
export SCRIPT_PROJ_PATH="$(dirname "${SCRIPT_PATH}")"
log_debug "SCRIPT_PROJ_PATH: ${SCRIPT_PROJ_PATH}"
# shellcheck disable=SC2155
export ROOT_PROJ_DIR_NAME="$(basename "${SCRIPT_PROJ_PATH}")"
log_debug "ROOT_PROJ_DIR_NAME: ${ROOT_PROJ_DIR_NAME}"
# shellcheck disable=SC2155
export SCRIPT_LANG_PATH="$(dirname "${SCRIPT_PROJ_PATH}")"
log_debug "SCRIPT_LANG_PATH: ${SCRIPT_LANG_PATH}"
# shellcheck disable=SC2155
export ROOT_LANG_DIR_NAME="$(basename "${SCRIPT_LANG_PATH}")"
log_debug "ROOT_LANG_DIR_NAME: ${ROOT_LANG_DIR_NAME}"
# shellcheck disable=SC2155
export SCRIPT_DEVELOPMENT_PATH="$(dirname "${SCRIPT_LANG_PATH}")"
log_debug "SCRIPT_DEVELOPMENT_PATH: ${SCRIPT_DEVELOPMENT_PATH}"
# shellcheck disable=SC2155
export ROOT_DEV_DIR_NAME="$(basename "${SCRIPT_DEVELOPMENT_PATH}")"
log_debug "ROOT_DEV_DIR_NAME: ${ROOT_DEV_DIR_NAME}"
# shellcheck disable=SC2155
export SCRIPT_ROOT_PATH="$(dirname "${SCRIPT_DEVELOPMENT_PATH}")"
log_debug "SCRIPT_ROOT_PATH: ${SCRIPT_ROOT_PATH}"


####################################################################################################
# Define Global Environment File Configuration Constants
####################################################################################################

# `# Define directory names
# ROOT_CONF_DIR_NAME="conf"
# ROOT_DATA_DIR_NAME="data"
# ROOT_IMAGES_DIR_NAME="images"
# ROOT_JUPYTER_DIR_NAME="jupyter"# ROOT_KAGGLE_DIR_NAME="kaggle"
# ROOT_LOGS_DIR_NAME="logs"
# ROOT_NOTES_DIR_NAME="notes"
# ROOT_PAPERS_DIR_NAME="papers"
# ROOT_PROMPTS_DIR_NAME="prompts"
# ROOT_REFS_DIR_NAME="refs"
# ROOT_SCRIPTS_DIR_NAME="scripts"
# ROOT_SRC_DIR_NAME="src"
# ROOT_UTIL_DIR_NAME="util"
# ROOT_VIZ_DIR_NAME="viz"

# # Define Path names
# ROOT_CONF_PATH="${SCRIPT_PROJ_PATH}/${ROOT_CONF_DIR_NAME}"
# log_debug "ROOT_CONF_PATH: ${ROOT_CONF_PATH}"
# ROOT_DATA_PATH="${SCRIPT_PROJ_PATH}/${ROOT_DATA_DIR_NAME}"
# log_debug "ROOT_DATA_PATH: ${ROOT_DATA_PATH}"
# ROOT_IMAGES_PATH="${SCRIPT_PROJ_PATH}/${ROOT_IMAGES_DIR_NAME}"
# log_debug "ROOT_IMAGES_PATH: ${ROOT_IMAGES_PATH}"
# ROOT_JUPYTER_PATH="${SCRIPT_PROJ_PATH}/${ROOT_JUPYTER_DIR_NAME}"
# log_debug "ROOT_JUPYTER_PATH: ${ROOT_JUPYTER_PATH}"
# ROOT_KAGGLE_PATH="${SCRIPT_PROJ_PATH}/${ROOT_KAGGLE_DIR_NAME}"
# log_debug "ROOT_KAGGLE_PATH: ${ROOT_KAGGLE_PATH}"
# ROOT_LOGS_PATH="${SCRIPT_PROJ_PATH}/${ROOT_LOGS_DIR_NAME}"
# log_debug "ROOT_LOGS_PATH: ${ROOT_LOGS_PATH}"
# ROOT_NOTES_PATH="${SCRIPT_PROJ_PATH}/${ROOT_NOTES_DIR_NAME}"
# log_debug "ROOT_NOTES_PATH: ${ROOT_NOTES_PATH}"
# ROOT_PAPERS_PATH="${SCRIPT_PROJ_PATH}/${ROOT_PAPERS_DIR_NAME}"
# log_debug "ROOT_PAPERS_PATH: ${ROOT_PAPERS_PATH}"
# ROOT_PROMPTS_PATH="${SCRIPT_PROJ_PATH}/${ROOT_PROMPTS_DIR_NAME}"
# log_debug "ROOT_PROMPTS_PATH: ${ROOT_PROMPTS_PATH}"
# ROOT_REFS_PATH="${SCRIPT_PROJ_PATH}/${ROOT_REFS_DIR_NAME}"
# log_debug "ROOT_REFS_PATH: ${ROOT_REFS_PATH}"
# ROOT_SCRIPTS_PATH="${SCRIPT_PROJ_PATH}/${ROOT_SCRIPTS_DIR_NAME}"
# log_debug "ROOT_SCRIPTS_PATH: ${ROOT_SCRIPTS_PATH}"
# ROOT_SRC_PATH="${SCRIPT_PROJ_PATH}/${ROOT_SRC_DIR_NAME}"
# log_debug "ROOT_SRC_PATH: ${ROOT_SRC_PATH}"
# ROOT_UTIL_PATH="${SCRIPT_PROJ_PATH}/${ROOT_UTIL_DIR_NAME}"
# log_debug "ROOT_UTIL_PATH: ${ROOT_UTIL_PATH}"
# ROOT_VIZ_PATH="${SCRIPT_PROJ_PATH}/${ROOT_VIZ_DIR_NAME}"
# log_debug "ROOT_VIZ_PATH: ${ROOT_VIZ_PATH}"


####################################################################################################
# Define OS Specific Archive Dir Script Constants
####################################################################################################
# shellcheck disable=SC2155
export CURRENT_OS="$(${GET_OS_SCRIPT})"
log_debug "CURRENT_OS: ${CURRENT_OS}"

# EXCLUDE_SWITCH_MACOS="--exclude-dir"
export EXCLUDE_SWITCH_MACOS="--exclude"
export EXCLUDE_SWITCH_UBUNTU="--exclude"
export EXCLUDE_SWITCH_LINUX="--exclude"

case "${CURRENT_OS}" in
    "${UBUNTU}")
        export USB_ARCHIVE_MOUNT="${USB_ARCHIVE_MOUNT_UBUNTU}"
        export USB_ARCHIVE_DEVICE_NAME="${USB_ARCHIVE_DEVICE_LINUX}"
        export EXCLUDE_SWITCH="${EXCLUDE_SWITCH_UBUNTU}"
    ;;
    "${FEDORA}" | "${RHEL}" | "${CENTOS}" | "${LINUX}")
        export USB_ARCHIVE_MOUNT="${USB_ARCHIVE_MOUNT_LINUX}"
        export USB_ARCHIVE_DEVICE_NAME="${USB_ARCHIVE_DEVICE_LINUX}"
        export EXCLUDE_SWITCH="${EXCLUDE_SWITCH_LINUX}"
    ;;
    "${MACOS}")
        export USB_ARCHIVE_MOUNT="${USB_ARCHIVE_MOUNT_MACOS}"
        export USB_ARCHIVE_DEVICE_NAME="${USB_ARCHIVE_DEVICE_MACOS}"
        export EXCLUDE_SWITCH="${EXCLUDE_SWITCH_MACOS}"
    ;;
    "${UNKNOWN}") echo "Error: Current OS is Unknown: ${CURRENT_OS}"; exit 2;
esac
log_debug "USB_ARCHIVE_MOUNT: ${USB_ARCHIVE_MOUNT}"
log_debug "USB_ARCHIVE_DEVICE_NAME: ${USB_ARCHIVE_DEVICE_NAME}"
log_debug "EXCLUDE_SWITCH: ${EXCLUDE_SWITCH}"


####################################################################################################
# Define Script Archive Constants
####################################################################################################
export USB_ARCHIVE_DIR_NAME="${ROOT_PROJ_DIR_NAME}-${JUNIPER_APPLICATION_VERSION}_${ROOT_LANG_DIR_NAME}"
log_debug "USB_ARCHIVE_DIR_NAME: ${USB_ARCHIVE_DIR_NAME}"

export PROJ_APPLICATION_NAME="${ROOT_PROJ_DIR_NAME,,}"
log_debug "PROJ_APPLICATION_NAME: ${PROJ_APPLICATION_NAME}"
export PROJ_LANGUAGE_NAME="${ROOT_LANG_DIR_NAME,,}"
log_debug "PROJ_LANGUAGE_NAME: ${PROJ_LANGUAGE_NAME}"
# shellcheck disable=SC2155
export PROJ_ARCHIVE_DATESTAMP="$(date +%F)"
log_debug "PROJ_ARCHIVE_DATESTAMP: ${PROJ_ARCHIVE_DATESTAMP}"
export PROJ_ARCHIVE_EXT="tgz"
log_debug "PROJ_ARCHIVE_EXT: ${PROJ_ARCHIVE_EXT}"
export USB_ARCHIVE_FILE_NAME="${PROJ_APPLICATION_NAME}-${JUNIPER_APPLICATION_VERSION}_${PROJ_LANGUAGE_NAME}_${PROJ_ARCHIVE_DATESTAMP}.${PROJ_ARCHIVE_EXT}"
log_debug "USB_ARCHIVE_FILE_NAME: ${USB_ARCHIVE_FILE_NAME}"
export USB_ARCHIVE_DIR="${USB_ARCHIVE_MOUNT}/${USB_ARCHIVE_DIR_NAME}"
log_debug "USB_ARCHIVE_DIR: ${USB_ARCHIVE_DIR}"
export USB_ARCHIVE_FILE="${USB_ARCHIVE_DIR}/${USB_ARCHIVE_FILE_NAME}"
log_debug "USB_ARCHIVE_FILE: ${USB_ARCHIVE_FILE}"


####################################################################################################
#  Define Development Dirs Excluded from Archive file
####################################################################################################
export ROOT_BIN_PATH="${SCRIPT_PROJ_PATH}/${BIN_DIR_NAME}"
log_debug "ROOT_BIN_PATH: ${ROOT_BIN_PATH}"
export ROOT_CUDA_PATH="${SCRIPT_PROJ_PATH}/${CUDA_DIR_NAME}"
log_debug "ROOT_CUDA_PATH: ${ROOT_CUDA_PATH}"
export ROOT_DEBUG_PATH="${SCRIPT_PROJ_PATH}/${DEBUG_DIR_NAME}"
log_debug "ROOT_DEBUG_PATH: ${ROOT_DEBUG_PATH}"
export ROOT_HDF5_PATH="${SCRIPT_PROJ_PATH}/${HDF5_DIR_NAME}"
log_debug "ROOT_HDF5_PATH: ${ROOT_HDF5_PATH}"
export ROOT_LIBRARY_PATH="${SCRIPT_PROJ_PATH}/${LIBRARY_DIR_NAME}"
log_debug "ROOT_LIBRARY_PATH: ${ROOT_LIBRARY_PATH}"
export ROOT_OUTPUT_PATH="${SCRIPT_PROJ_PATH}/${OUTPUT_DIR_NAME}"
log_debug "ROOT_OUTPUT_PATH: ${ROOT_OUTPUT_PATH}"
export ROOT_PYTEST_CACHE_PATH="${SCRIPT_PROJ_PATH}/${PYTEST_CACHE_DIR_NAME}"
log_debug "ROOT_PYTEST_CACHE_PATH: ${ROOT_PYTEST_CACHE_PATH}"
export ROOT_RELEASE_PATH="${SCRIPT_PROJ_PATH}/${RELEASE_DIR_NAME}"
log_debug "ROOT_RELEASE_PATH: ${ROOT_RELEASE_PATH}"
export ROOT_RESOURCES_PATH="${SCRIPT_PROJ_PATH}/${RESOURCES_DIR_NAME}"
log_debug "ROOT_RESOURCES_PATH: ${ROOT_RESOURCES_PATH}"
export ROOT_TARGET_PATH="${SCRIPT_PROJ_PATH}/${TARGET_DIR_NAME}"
log_debug "ROOT_TARGET_PATH: ${ROOT_TARGET_PATH}"
export ROOT_TEMP_PATH="${SCRIPT_PROJ_PATH}/${TEMP_DIR_NAME}"
log_debug "ROOT_TEMP_PATH: ${ROOT_TEMP_PATH}"
export ROOT_TORCHEXPLORER_STANDALONE_PATH="${SCRIPT_PROJ_PATH}/${TORCHEXPLORER_STANDALONE_DIR_NAME}"
log_debug "ROOT_TORCHEXPLORER_STANDALONE_PATH: ${ROOT_TORCHEXPLORER_STANDALONE_PATH}"
export ROOT_TRUNK_PATH="${SCRIPT_PROJ_PATH}/${TRUNK_DIR_NAME}"
log_debug "ROOT_TRUNK_PATH: ${ROOT_TRUNK_PATH}"
export ROOT_TRUNK_NEW_PATH="${SCRIPT_PROJ_PATH}/${TRUNK_NEW_DIR_NAME}"
log_debug "ROOT_TRUNK_NEW_PATH: ${ROOT_TRUNK_NEW_PATH}"
export ROOT_VENV_PATH="${SCRIPT_PROJ_PATH}/${VENV_DIR_NAME}"
log_debug "ROOT_VENV_PATH: ${ROOT_VENV_PATH}"
export ROOT_VSCODE_PATH="${SCRIPT_PROJ_PATH}/${VSCODE_DIR_NAME}"
log_debug "ROOT_VSCODE_PATH: ${ROOT_VSCODE_PATH}"
