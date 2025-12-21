#!/usr/bin/env bash
#####################################################################################################################################################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     save_to_usb.bash
# Author:        Paul Calnon
# Version:       0.1.4 (0.7.3)
#
# Date:          2025-10-11
# Last Modified: 2025-12-03
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2025 Paul Calnon
#
# Description:
#    This script saves the Juniper development directory to a USB drive
#
#####################################################################################################################################################################################################
# Notes:
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# Notes:
#    Juniper-7.3.1_python/
#
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# Examples:
#
#####################################################################################################################################################################################################

#####################################################################################################
# Define GLobal Debug Constants
#####################################################################################################
TRUE="true"
FALSE="false"

DEBUG="${TRUE}"
# DEBUG="${FALSE}"


#####################################################################################################
# Define Global Functions
####################################################################################################
# Define local Functions
get_script_path() {
    local source="${BASH_SOURCE[0]}"
    while [ -L "$source" ]; do
        local dir="$(cd -P "$(dirname "$source")" && pwd)"
        source="$(readlink "$source")"
        [[ $source != /* ]] && source="$dir/$source"
    done
    echo "$(cd -P "$(dirname "$source")" && pwd)/$(basename "$source")"
}


####################################################################################################
# Define Global Environment DirectoryConfiguration Constants
# TODO: add these to a config file
####################################################################################################
SCRIPT_NAME="$(basename $BASH_SOURCE)";                        [[ ${DEBUG} == "${TRUE}" ]] && echo "SCRIPT_NAME: ${SCRIPT_NAME}"
SCRIPT_PATH="$(dirname "$(get_script_path)")";                 [[ ${DEBUG} == "${TRUE}" ]] && echo "SCRIPT_PATH: ${SCRIPT_PATH}"
SCRIPT_PROJ_PATH="$(dirname "${SCRIPT_PATH}")";                [[ ${DEBUG} == "${TRUE}" ]] && echo "SCRIPT_PROJ_PATH: ${SCRIPT_PROJ_PATH}"
ROOT_PROJ_DIR_NAME="$(basename "${SCRIPT_PROJ_PATH}")";        [[ ${DEBUG} == "${TRUE}" ]] && echo "ROOT_PROJ_DIR_NAME: ${ROOT_PROJ_DIR_NAME}"
SCRIPT_LANG_PATH="$(dirname "${SCRIPT_PROJ_PATH}")";           [[ ${DEBUG} == "${TRUE}" ]] && echo "SCRIPT_LANG_PATH: ${SCRIPT_LANG_PATH}"
ROOT_LANG_DIR_NAME="$(basename "${SCRIPT_LANG_PATH}")";        [[ ${DEBUG} == "${TRUE}" ]] && echo "ROOT_LANG_DIR_NAME: ${ROOT_LANG_DIR_NAME}"
SCRIPT_DEVELOPMENT_PATH="$(dirname "${SCRIPT_LANG_PATH}")";    [[ ${DEBUG} == "${TRUE}" ]] && echo "SCRIPT_DEVELOPMENT_PATH: ${SCRIPT_DEVELOPMENT_PATH}"
ROOT_DEV_DIR_NAME="$(basename "${SCRIPT_DEVELOPMENT_PATH}")";  [[ ${DEBUG} == "${TRUE}" ]] && echo "ROOT_DEV_DIR_NAME: ${ROOT_DEV_DIR_NAME}"
SCRIPT_ROOT_PATH="$(dirname "${SCRIPT_DEVELOPMENT_PATH}")";    [[ ${DEBUG} == "${TRUE}" ]] && echo "SCRIPT_ROOT_PATH: ${SCRIPT_ROOT_PATH}"


####################################################################################################
# Define Global Environment File Configuration Constants
####################################################################################################

# Define directory names
ROOT_CONF_DIR_NAME="conf"
ROOT_DATA_DIR_NAME="data"
ROOT_IMAGES_DIR_NAME="images"
ROOT_JUPYTER_DIR_NAME="jupyter"
ROOT_KAGGLE_DIR_NAME="kaggle"
ROOT_LOGS_DIR_NAME="logs"
ROOT_NOTES_DIR_NAME="notes"
ROOT_PAPERS_DIR_NAME="papers"
ROOT_PROMPTS_DIR_NAME="prompts"
ROOT_REFS_DIR_NAME="refs"
ROOT_SCRIPTS_DIR_NAME="scripts"
ROOT_SRC_DIR_NAME="src"
ROOT_UTIL_DIR_NAME="util"
ROOT_VIZ_DIR_NAME="viz"

# Define Path names
ROOT_CONF_PATH="${SCRIPT_PROJ_PATH}/${ROOT_CONF_DIR_NAME}";         [[ ${DEBUG} == "${TRUE}" ]] && echo "ROOT_CONF_PATH: ${ROOT_CONF_PATH}"
ROOT_DATA_PATH="${SCRIPT_PROJ_PATH}/${ROOT_DATA_DIR_NAME}";         [[ ${DEBUG} == "${TRUE}" ]] && echo "ROOT_DATA_PATH: ${ROOT_DATA_PATH}"
ROOT_IMAGES_PATH="${SCRIPT_PROJ_PATH}/${ROOT_IMAGES_DIR_NAME}";     [[ ${DEBUG} == "${TRUE}" ]] && echo "ROOT_IMAGES_PATH: ${ROOT_IMAGES_PATH}"
ROOT_JUPYTER_PATH="${SCRIPT_PROJ_PATH}/${ROOT_JUPYTER_DIR_NAME}";   [[ ${DEBUG} == "${TRUE}" ]] && echo "ROOT_JUPYTER_PATH: ${ROOT_JUPYTER_PATH}"
ROOT_KAGGLE_PATH="${SCRIPT_PROJ_PATH}/${ROOT_KAGGLE_DIR_NAME}";     [[ ${DEBUG} == "${TRUE}" ]] && echo "ROOT_KAGGLE_PATH: ${ROOT_KAGGLE_PATH}"
ROOT_LOGS_PATH="${SCRIPT_PROJ_PATH}/${ROOT_LOGS_DIR_NAME}";         [[ ${DEBUG} == "${TRUE}" ]] && echo "ROOT_LOGS_PATH: ${ROOT_LOGS_PATH}"
ROOT_NOTES_PATH="${SCRIPT_PROJ_PATH}/${ROOT_NOTES_DIR_NAME}";       [[ ${DEBUG} == "${TRUE}" ]] && echo "ROOT_NOTES_PATH: ${ROOT_NOTES_PATH}"
ROOT_PAPERS_PATH="${SCRIPT_PROJ_PATH}/${ROOT_PAPERS_DIR_NAME}";     [[ ${DEBUG} == "${TRUE}" ]] && echo "ROOT_PAPERS_PATH: ${ROOT_PAPERS_PATH}"
ROOT_PROMPTS_PATH="${SCRIPT_PROJ_PATH}/${ROOT_PROMPTS_DIR_NAME}";   [[ ${DEBUG} == "${TRUE}" ]] && echo "ROOT_PROMPTS_PATH: ${ROOT_PROMPTS_PATH}"
ROOT_REFS_PATH="${SCRIPT_PROJ_PATH}/${ROOT_REFS_DIR_NAME}";         [[ ${DEBUG} == "${TRUE}" ]] && echo "ROOT_REFS_PATH: ${ROOT_REFS_PATH}"
ROOT_SCRIPTS_PATH="${SCRIPT_PROJ_PATH}/${ROOT_SCRIPTS_DIR_NAME}";   [[ ${DEBUG} == "${TRUE}" ]] && echo "ROOT_SCRIPTS_PATH: ${ROOT_SCRIPTS_PATH}"
ROOT_SRC_PATH="${SCRIPT_PROJ_PATH}/${ROOT_SRC_DIR_NAME}";           [[ ${DEBUG} == "${TRUE}" ]] && echo "ROOT_SRC_PATH: ${ROOT_SRC_PATH}"
ROOT_UTIL_PATH="${SCRIPT_PROJ_PATH}/${ROOT_UTIL_DIR_NAME}";         [[ ${DEBUG} == "${TRUE}" ]] && echo "ROOT_UTIL_PATH: ${ROOT_UTIL_PATH}"
ROOT_VIZ_PATH="${SCRIPT_PROJ_PATH}/${ROOT_VIZ_DIR_NAME}";           [[ ${DEBUG} == "${TRUE}" ]] && echo "ROOT_VIZ_PATH: ${ROOT_VIZ_PATH}"


####################################################################################################
# Define Sourced Config File Constants
####################################################################################################
ROOT_CONF_FILE_NAME="common.conf"
ROOT_CONF_FILE="${ROOT_CONF_PATH}/${ROOT_CONF_FILE_NAME}";          [[ ${DEBUG} == "${TRUE}" ]] && echo "Root Conf file: ${ROOT_CONF_FILE}"
source ${ROOT_CONF_FILE}


####################################################################################################
# Define OS Specific Archive Dir Script Constants
####################################################################################################
CURRENT_OS="$(${GET_OS_SCRIPT})";                                   [[ ${DEBUG} == "${TRUE}" ]] && echo "CURRENT_OS: ${CURRENT_OS}"

# EXCLUDE_SWITCH_MACOS="--exclude-dir"
EXCLUDE_SWITCH_MACOS="--exclude"
EXCLUDE_SWITCH_UBUNTU="--exclude"
EXCLUDE_SWITCH_LINUX="--exclude"

case "${CURRENT_OS}" in
  ${UBUNTU})
    USB_ARCHIVE_MOUNT="${USB_ARCHIVE_MOUNT_UBUNTU}"
    USB_ARCHIVE_DEVICE_NAME="${USB_ARCHIVE_DEVICE_LINUX}"
    EXCLUDE_SWITCH="${EXCLUDE_SWITCH_UBUNTU}"
  ;;
  ${FEDORA} | ${RHEL} | ${CENTOS} | ${LINUX})
    USB_ARCHIVE_MOUNT="${USB_ARCHIVE_MOUNT_LINUX}"
    USB_ARCHIVE_DEVICE_NAME="${USB_ARCHIVE_DEVICE_LINUX}"
    EXCLUDE_SWITCH="${EXCLUDE_SWITCH_LINUX}"
  ;;
  ${MACOS})
    USB_ARCHIVE_MOUNT="${USB_ARCHIVE_MOUNT_MACOS}"
    USB_ARCHIVE_DEVICE_NAME="${USB_ARCHIVE_DEVICE_MACOS}"
    EXCLUDE_SWITCH="${EXCLUDE_SWITCH_MACOS}"
  ;;
  ${UNKNOWN}) echo "Error: Current OS is Unknown: ${CURRENT_OS}"; exit 2;;
esac
[[ ${DEBUG} == "${TRUE}" ]] && echo "USB_ARCHIVE_MOUNT: ${USB_ARCHIVE_MOUNT}"
[[ ${DEBUG} == "${TRUE}" ]] && echo "USB_ARCHIVE_DEVICE_NAME: ${USB_ARCHIVE_DEVICE_NAME}"
[[ ${DEBUG} == "${TRUE}" ]] && echo "EXCLUDE_SWITCH: ${EXCLUDE_SWITCH}"


####################################################################################################
# Define Script Archive Constants
####################################################################################################
USB_ARCHIVE_DIR_NAME="${ROOT_PROJ_DIR_NAME}-${JUNIPER_APPLICATION_VERSION}_${ROOT_LANG_DIR_NAME}"; [[ ${DEBUG} == "${TRUE}" ]] && echo "USB_ARCHIVE_DIR_NAME: ${USB_ARCHIVE_DIR_NAME}"
USB_ARCHIVE_DIR=""
USB_ARCHIVE_ROOT_DIR=""
for USB_ARCHIVE_DEVICE_NAME in ${USB_ARCHIVE_DEVICE_LINUX_LIST}; do
    USB_ARCHIVE_ROOT_DIR="${USB_ARCHIVE_MOUNT}/${USB_ARCHIVE_DEVICE_NAME}";                        [[ ${DEBUG} == "${TRUE}" ]] && echo "USB_ARCHIVE_ROOT_DIR: ${USB_ARCHIVE_ROOT_DIR}"

    # NOTE: this logic means that if multiple valid usb drives are currently mounted, the first mounted drive appearing in the USB_ARCHIVE_DEVICE_LINUX_LIST wii be used.
    if [[ -d ${USB_ARCHIVE_ROOT_DIR} ]]; then
        USB_ARCHIVE_DIR="${USB_ARCHIVE_ROOT_DIR}/${USB_ARCHIVE_DIR_NAME}";                         [[ ${DEBUG} == "${TRUE}" ]] && echo "USB_ARCHIVE_DIR: ${USB_ARCHIVE_DIR}"
        mkdir -p ${USB_ARCHIVE_DIR}                                                                [[ ${DEBUG} == "${TRUE}" ]] && echo "mkdir -p ${USB_ARCHIVE_DIR}"
	break
    fi;                                                                                            [[ ${DEBUG} == "${TRUE}" ]] && echo "WARNING: Device: \"${USB_ARCHIVE_DEVICE_NAME}\",  Failed to find USB Archive Root Dir: \"${USB_ARCHIVE_ROOT_DIR}\""

done

# Verify valid usb device was found
if [[ ${USB_ARCHIVE_DIR} == "" ]]; then
    echo "ERROR: No valid USB device found.  Exiting..."
    exit 1
fi

PROJ_APPLICATION_NAME="${ROOT_PROJ_DIR_NAME,,}";                                                   [[ ${DEBUG} == "${TRUE}" ]] && echo "PROJ_APPLICATION_NAME: ${PROJ_APPLICATION_NAME}"
PROJ_LANGUAGE_NAME="${ROOT_LANG_DIR_NAME,,}";                                                      [[ ${DEBUG} == "${TRUE}" ]] && echo "PROJ_LANGUAGE_NAME: ${PROJ_LANGUAGE_NAME}"
PROJ_ARCHIVE_DATESTAMP="$(date +%F)";                                                              [[ ${DEBUG} == "${TRUE}" ]] && echo "PROJ_ARCHIVE_DATESTAMP: ${PROJ_ARCHIVE_DATESTAMP}"
PROJ_ARCHIVE_EXT="tgz";                                                                            [[ ${DEBUG} == "${TRUE}" ]] && echo "PROJ_ARCHIVE_EXT: ${PROJ_ARCHIVE_EXT}"
USB_ARCHIVE_FILE_NAME="${PROJ_APPLICATION_NAME}-${JUNIPER_APPLICATION_VERSION}_${PROJ_LANGUAGE_NAME}_${PROJ_ARCHIVE_DATESTAMP}.${PROJ_ARCHIVE_EXT}";
                                                                                                   [[ ${DEBUG} == "${TRUE}" ]] && echo "USB_ARCHIVE_FILE_NAME: ${USB_ARCHIVE_FILE_NAME}"
USB_ARCHIVE_FILE="${USB_ARCHIVE_DIR}/${USB_ARCHIVE_FILE_NAME}";                                    [[ ${DEBUG} == "${TRUE}" ]] && echo "USB_ARCHIVE_FILE: ${USB_ARCHIVE_FILE}"


####################################################################################################
# Define Script Functions
####################################################################################################
# source ${DATE_FUNCTIONS_SCRIPT}


####################################################################################################
#  Define Development Dirs Excluded from Archive file
####################################################################################################
ROOT_BIN_PATH="${SCRIPT_PROJ_PATH}/${BIN_DIR_NAME}";                                               [[ ${DEBUG} == "${TRUE}" ]] && echo "ROOT_BIN_PATH: ${ROOT_BIN_PATH}"
ROOT_CUDA_PATH="${SCRIPT_PROJ_PATH}/${CUDA_DIR_NAME}";                                             [[ ${DEBUG} == "${TRUE}" ]] && echo "ROOT_CUDA_PATH: ${ROOT_CUDA_PATH}"
ROOT_DEBUG_PATH="${SCRIPT_PROJ_PATH}/${DEBUG_DIR_NAME}";                                           [[ ${DEBUG} == "${TRUE}" ]] && echo "ROOT_DEBUG_PATH: ${ROOT_DEBUG_PATH}"
ROOT_HDF5_PATH="${SCRIPT_PROJ_PATH}/${HDF5_DIR_NAME}";                                             [[ ${DEBUG} == "${TRUE}" ]] && echo "ROOT_HDF5_PATH: ${ROOT_HDF5_PATH}"
ROOT_LIBRARY_PATH="${SCRIPT_PROJ_PATH}/${LIBRARY_DIR_NAME}";                                       [[ ${DEBUG} == "${TRUE}" ]] && echo "ROOT_LIBRARY_PATH: ${ROOT_LIBRARY_PATH}"
ROOT_OUTPUT_PATH="${SCRIPT_PROJ_PATH}/${OUTPUT_DIR_NAME}";                                         [[ ${DEBUG} == "${TRUE}" ]] && echo "ROOT_OUTPUT_PATH: ${ROOT_OUTPUT_PATH}"
ROOT_PYTEST_CACHE_PATH="${SCRIPT_PROJ_PATH}/${PYTEST_CACHE_DIR_NAME}";                             [[ ${DEBUG} == "${TRUE}" ]] && echo "ROOT_PYTEST_CACHE_PATH: ${ROOT_PYTEST_CACHE_PATH}"
ROOT_RELEASE_PATH="${SCRIPT_PROJ_PATH}/${RELEASE_DIR_NAME}";                                       [[ ${DEBUG} == "${TRUE}" ]] && echo "ROOT_RELEASE_PATH: ${ROOT_RELEASE_PATH}"
ROOT_RESOURCES_PATH="${SCRIPT_PROJ_PATH}/${RESOURCES_DIR_NAME}";                                   [[ ${DEBUG} == "${TRUE}" ]] && echo "ROOT_RESOURCES_PATH: ${ROOT_RESOURCES_PATH}"
ROOT_TARGET_PATH="${SCRIPT_PROJ_PATH}/${TARGET_DIR_NAME}";                                         [[ ${DEBUG} == "${TRUE}" ]] && echo "ROOT_TARGET_PATH: ${ROOT_TARGET_PATH}"
ROOT_TEMP_PATH="${SCRIPT_PROJ_PATH}/${TEMP_DIR_NAME}";                                             [[ ${DEBUG} == "${TRUE}" ]] && echo "ROOT_TEMP_PATH: ${ROOT_TEMP_PATH}"
ROOT_TORCHEXPLORER_STANDALONE_PATH="${SCRIPT_PROJ_PATH}/${TORCHEXPLORER_STANDALONE_DIR_NAME}";     [[ ${DEBUG} == "${TRUE}" ]] && echo "ROOT_TORCHEXPLORER_STANDALONE_PATH: ${ROOT_TORCHEXPLORER_STANDALONE_PATH}"
ROOT_TRUNK_PATH="${SCRIPT_PROJ_PATH}/${TRUNK_DIR_NAME}";                                           [[ ${DEBUG} == "${TRUE}" ]] && echo "ROOT_TRUNK_PATH: ${ROOT_TRUNK_PATH}"
ROOT_TRUNK_NEW_PATH="${SCRIPT_PROJ_PATH}/${TRUNK_NEW_DIR_NAME}";                                   [[ ${DEBUG} == "${TRUE}" ]] && echo "ROOT_TRUNK_NEW_PATH: ${ROOT_TRUNK_NEW_PATH}"
ROOT_VENV_PATH="${SCRIPT_PROJ_PATH}/${VENV_DIR_NAME}";                                             [[ ${DEBUG} == "${TRUE}" ]] && echo "ROOT_VENV_PATH: ${ROOT_VENV_PATH}"
ROOT_VSCODE_PATH="${SCRIPT_PROJ_PATH}/${VSCODE_DIR_NAME}";                                         [[ ${DEBUG} == "${TRUE}" ]] && echo "ROOT_VSCODE_PATH: ${ROOT_VSCODE_PATH}"


####################################################################################################
# Define Excluded Dirs List
####################################################################################################
EXCLUDE_DIRS_LIST="${ROOT_BIN_PATH} ${ROOT_CUDA_PATH} ${ROOT_DATA_PATH} ${ROOT_DEBUG_PATH} ${ROOT_HDF5_PATH} ${ROOT_LIBRARY_PATH} ${ROOT_LOGS_PATH} ${ROOT_OUTPUT_PATH} ${ROOT_PYTEST_CACHE_PATH} ${ROOT_RELEASE_PATH} ${ROOT_RESOURCES_PATH} ${ROOT_TARGET_PATH} ${ROOT_TEMP_PATH} ${ROOT_TORCHEXPLORER_STANDALONE_PATH} ${ROOT_TRUNK_PATH} ${ROOT_TRUNK_NEW_PATH} ${ROOT_VENV_PATH} ${ROOT_VIZ_PATH} ${ROOT_VSCODE_PATH}";
                                                                                                   [[ ${DEBUG} == "${TRUE}" ]] && echo "EXCLUDE_DIRS_LIST: ${EXCLUDE_DIRS_LIST}"

USB_ARCHIVE_EXCLUDED=""

for EXCLUDE_DIR in ${EXCLUDE_DIRS_LIST}; do
    [[ -d ${EXCLUDE_DIR} ]] && USB_ARCHIVE_EXCLUDED="${USB_ARCHIVE_EXCLUDED}${EXCLUDE_SWITCH} ${EXCLUDE_DIR} "
done
[[ ${DEBUG} == "${TRUE}" ]] && echo "USB_ARCHIVE_EXCLUDED: ${USB_ARCHIVE_EXCLUDED}"


####################################################################################################
# Save the Jumper Rust project (excluding contents of libs & target dirs) to a USB drive
#
#    tar cvfz /media/pcalnon/DFF3-2782/Juniper_rust/juniper_rust_$(date +%F).tgz
#    --exclude libs --exclude target --exclude data ~/Development/rust/rust_mudgeon/juniper
#
####################################################################################################
echo -ne "\nSaving Archive file: ${USB_ARCHIVE_FILE}\n";  [[ ${DEBUG} == "${TRUE}" ]] && echo "tar -czvf ${USB_ARCHIVE_FILE} ${USB_ARCHIVE_EXCLUDED} ${SCRIPT_PROJ_PATH}"
if [[ ${DEBUG} == "${TRUE}" ]]; then
    tar -czvf ${USB_ARCHIVE_FILE} ${USB_ARCHIVE_EXCLUDED} ${SCRIPT_PROJ_PATH}
else
    tar -czf ${USB_ARCHIVE_FILE} ${USB_ARCHIVE_EXCLUDED} ${SCRIPT_PROJ_PATH}  >/dev/null 2>&1
fi
[[ $? == 0 ]] && echo "Successfully Saved Archive file: ${USB_ARCHIVE_FILE}" || echo "Failed to Save Archive file: ${USB_ARCHIVE_FILE}"

echo -ne "\nls -Flah ${USB_ARCHIVE_DIR}\n"
ls -Flah ${USB_ARCHIVE_DIR}

echo -ne "\nUSB Drive Space Remaining\n"
echo "Filesystem      Size  Used Avail Use% Mounted on"
df -h | grep "${USB_ARCHIVE_ROOT_DIR}"
