#!/usr/bin/env bash
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       0.1.4 (0.7.3)
# File Name:     change_path.bash
# File Path:     <Project>/<Sub-Project>/<Application>/util/
#
# Date:          2025-10-11
# Last Modified: 2026-01-03
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#     This script is used to change the path of the JuniperCanopy application.
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
# Source script config file
#####################################################################################################################################################################################################
set -o functrace
# shellcheck disable=SC2155
export PARENT_PATH_PARAM="$(realpath "${BASH_SOURCE[0]}")" && INIT_CONF="$(dirname "$(dirname "${PARENT_PATH_PARAM}")")/conf/init.conf"
# shellcheck disable=SC2015,SC1090
[[ -f "${INIT_CONF}" ]] && source "${INIT_CONF}" || { echo "Init Config File Not Found. Unable to Continue."; exit 1; }


#####################################################################################################################################################################################################
# Move sub-project into new location
#####################################################################################################################################################################################################
log_info "Bash Version: $(/usr/bin/env bash --version)"
log_info "Current Working Dir: $(pwd)"

log_debug "Changing Path:  Old: \"${OLD_PATH}\", New: \"${NEW_PATH}\""
echo "Changing Path:  Old: \"${OLD_PATH}\", New: \"${NEW_PATH}\""
log_warning "Second Warning: Pausing for ${SLEEPY_TIME} seconds before proceeding..."
echo "Second Warning: Pausing for ${SLEEPY_TIME} seconds before proceeding..."
sleep "${SLEEPY_TIME}"
log_debug "Filenames:"

while read -r FILENAME; do
    log_debug "    sed -i \"s/${OLD_PATH}/${NEW_PATH}/g\" ${FILENAME}\n"
    sed -i "s/${OLD_PATH}/${NEW_PATH}/g" "${FILENAME}"
done <<< "$(grep -rnI "${OLD_PATH}" ./* | awk -F ":" '{print $1;}' | sort -u)"
log_debug "Finished implementing path change."

exit $(( TRUE ))
