#!/usr/bin/env bash
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       0.1.4 (0.7.3)
# File Name:     mv2_bash_n_back.bash
# File Path:     <Project>/<Sub-Project>/<Application>/util/
#
# Date:          2025-10-11
# Last Modified: 2026-01-02
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#    This script sets up the development environment for the Juniper Canopy application.
#
#####################################################################################################################################################################################################
# Notes:
#     Juniper Canopy Environment Setup Script
#     This script sets up the development environment for the Juniper Canopy application
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
export PARENT_PATH_PARAM="$(realpath "${BASH_SOURCE[0]}")" && INIT_CONF="conf/init.conf"
# shellcheck disable=SC2015,SC1091 source=conf/init.conf
[[ -f "${INIT_CONF}" ]] && source "${INIT_CONF}" || { echo "Init Config File Not Found. Unable to Continue."; exit 1; }


#####################################################################################################################################################################################################
# Restore config filenames by removing bash extension and restoring conf extension
#####################################################################################################################################################################################################
CURRENT_SUFFIX="*conf.bash"

# Move files from *_conf.bash to *.conf
while read -r ORIG; do
    echo "${ORIG}"
    TEMP="${ORIG%_*}.${ORIG##*_}"
    echo "${TEMP}"
    NEW="${TEMP%.*}"
    echo "${NEW}"
    mv "${ORIG}" "${NEW}"
done < "$(ls "${CURRENT_SUFFIX}")"

exit $(( TRUE ))
