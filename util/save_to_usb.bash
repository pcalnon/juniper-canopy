#!/usr/bin/env bash
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       0.1.4 (0.7.3)
# File Name:     save_to_usb.bash
# File Path:     <Project>/<Sub-Project>/<Application>/util/
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
# Source script config file
#####################################################################################################################################################################################################
set -o functrace
# shellcheck disable=SC2155
export PARENT_PATH_PARAM="$(realpath "${BASH_SOURCE[0]}")" && INIT_CONF="$(realpath "../conf/init.conf")"
# shellcheck disable=SC1090
# shellcheck disable=SC2015
[[ -f "${INIT_CONF}" ]] && source "${INIT_CONF}" || { echo "Init Config File Not Found. Unable to Continue."; exit 1; }


#####################################################################################################
# Define Global Functions
####################################################################################################
# Define local Functions
get_script_path() {
    local source="${BASH_SOURCE[0]}"
    while [ -L "$source" ]; do
        # shellcheck disable=SC2155
        local dir="$(cd -P "$(dirname "$source")" && pwd)"
        source="$(readlink "$source")"
        [[ $source != /* ]] && source="$dir/$source"
    done
    echo "$(cd -P "$(dirname "$source")" && pwd)/$(basename "$source")"
}


####################################################################################################
# Define Script Archive Constants
####################################################################################################
USB_ARCHIVE_DIR_NAME="${ROOT_PROJ_DIR_NAME}-${JUNIPER_APPLICATION_VERSION}_${ROOT_LANG_DIR_NAME}"
log_debug "USB_ARCHIVE_DIR_NAME: ${USB_ARCHIVE_DIR_NAME}"
USB_ARCHIVE_DIR=""
USB_ARCHIVE_ROOT_DIR=""
for USB_ARCHIVE_DEVICE_NAME in ${USB_ARCHIVE_DEVICE_LINUX_LIST}; do
    USB_ARCHIVE_ROOT_DIR="${USB_ARCHIVE_MOUNT}/${USB_ARCHIVE_DEVICE_NAME}"
    log_debug "USB_ARCHIVE_ROOT_DIR: ${USB_ARCHIVE_ROOT_DIR}"

    # NOTE: this logic means that if multiple valid usb drives are currently mounted, the first mounted drive appearing in the USB_ARCHIVE_DEVICE_LINUX_LIST wii be used.
    if [[ -d ${USB_ARCHIVE_ROOT_DIR} ]]; then
        USB_ARCHIVE_DIR="${USB_ARCHIVE_ROOT_DIR}/${USB_ARCHIVE_DIR_NAME}"
        log_debug "USB_ARCHIVE_DIR: ${USB_ARCHIVE_DIR}"
        mkdir -p "${USB_ARCHIVE_DIR}" || exit 1
        log_debug "mkdir -p ${USB_ARCHIVE_DIR}"
        break
    else
        log_warning "Device: \"${USB_ARCHIVE_DEVICE_NAME}\",  Failed to find USB Archive Root Dir: \"${USB_ARCHIVE_ROOT_DIR}\""
    fi
done

# Verify valid usb device was found
if [[ ${USB_ARCHIVE_DIR} == "" ]]; then
    echo "ERROR: No valid USB device found.  Exiting..."
    exit 1
fi


####################################################################################################
# Define Excluded Dirs List
####################################################################################################
EXCLUDE_DIRS_LIST="${ROOT_BIN_PATH} ${ROOT_CUDA_PATH} ${ROOT_DATA_PATH} ${ROOT_DEBUG_PATH} ${ROOT_HDF5_PATH} ${ROOT_LIBRARY_PATH} ${ROOT_LOGS_PATH} ${ROOT_OUTPUT_PATH} ${ROOT_PYTEST_CACHE_PATH} ${ROOT_RELEASE_PATH} ${ROOT_RESOURCES_PATH} ${ROOT_TARGET_PATH} ${ROOT_TEMP_PATH} ${ROOT_TORCHEXPLORER_PATH} ${ROOT_TRUNK_PATH} ${ROOT_TRUNK_NEW_PATH} ${ROOT_VENV_PATH} ${ROOT_VIZ_PATH} ${ROOT_VSCODE_PATH}";
log_debug "EXCLUDE_DIRS_LIST: ${EXCLUDE_DIRS_LIST}"

USB_ARCHIVE_EXCLUDED=""
for EXCLUDE_DIR in ${EXCLUDE_DIRS_LIST}; do
    [[ -d ${EXCLUDE_DIR} ]] && USB_ARCHIVE_EXCLUDED="${USB_ARCHIVE_EXCLUDED}${EXCLUDE_SWITCH} ${EXCLUDE_DIR} "
done
log_debug "USB_ARCHIVE_EXCLUDED: ${USB_ARCHIVE_EXCLUDED}"


####################################################################################################
# Save the Jumper Rust project (excluding contents of libs & target dirs) to a USB drive
#
#    tar cvfz /media/pcalnon/DFF3-2782/Juniper_rust/juniper_rust_$(date +%F).tgz
#    --exclude libs --exclude target --exclude data ~/Development/rust/rust_mudgeon/juniper
#
####################################################################################################
echo -ne "\nSaving Archive file: ${USB_ARCHIVE_FILE}\n"
log_debug "tar -czvf ${USB_ARCHIVE_FILE} ${USB_ARCHIVE_EXCLUDED} ${SCRIPT_PROJ_PATH}"
if [[ ${DEBUG} == "${TRUE}" ]]; then
    if tar -czvf "${USB_ARCHIVE_FILE}" "${USB_ARCHIVE_EXCLUDED}" "${SCRIPT_PROJ_PATH}"; then log_debug "Successfully Saved Archive file: ${USB_ARCHIVE_FILE}"; else log_error "Failed to Save Archive file: ${USB_ARCHIVE_FILE}"; fi
else
    if tar -czf "${USB_ARCHIVE_FILE}" "${USB_ARCHIVE_EXCLUDED}" "${SCRIPT_PROJ_PATH}" >/dev/null 2>&1; then log_debug "Successfully Saved Archive file: ${USB_ARCHIVE_FILE}"; else log_error "Failed to Save Archive file: ${USB_ARCHIVE_FILE}"; fi
fi
echo -ne "\nls -Flah ${USB_ARCHIVE_DIR}\n"
ls -Flah "${USB_ARCHIVE_DIR}"

echo -ne "\nUSB Drive Space Remaining\n"
echo "Filesystem      Size  Used Avail Use% Mounted on"
df -h | grep "${USB_ARCHIVE_ROOT_DIR}"
