#!/usr/bin/env bash
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Script Name:   git_branch_ages.bash
# Script Path:   <Project>/<Sub-Project>/juniper_canopy/util/
# Conf File:     git_branch_ages.conf
# Conf Path:     <Project>/<Sub-Project>/<Application>/conf/
#
# Author:        Paul Calnon
# Version:       1.0.0
#
# Date:          2025-12-03
# Last Modified: 2025-12-18
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#     This script returns the ages of the current git branches.  Help to identify orphaned branches, etc.
#
#####################################################################################################################################################################################################
# Notes:
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
# set -eE -o functrace
# set -o functrace


#####################################################################################################################################################################################################
# Source script config file
#####################################################################################################################################################################################################
set -o functrace
export PARENT_PATH_PARAM="$(realpath "${BASH_SOURCE[0]}")" && INIT_CONF="../conf/init.conf"
[[ -f "${INIT_CONF}" ]] && source "${INIT_CONF}" || { echo "Init Config File Not Found. Unable to Continue."; exit 1; }



# export PARENT_PATH_PARAM="$(realpath "${BASH_SOURCE[0]}")"
# source "../conf/init.conf"; SUCCESS="$?"

# [[ "${SUCCESS}" != "0" ]] && { source "../conf/config_fail.conf"; log_error "${SUCCESS}" "${PARENT_PATH_PARAM}" "../conf/init.conf" "${LINENO}" "${LOG_FILE}"; }
# log_debug "Successfully Configured Current Script: $(basename "${PARENT_PATH_PARAM}"), by Sourcing the Init Config File: ${INIT_CONF}, Returned: \"${SUCCESS}\""

# export PARENT_SCRIPT_PATH_PARAM="$(realpath "${BASH_SOURCE[0]}")"
# export INIT_CONF="../conf/init.conf"
# source "${INIT_CONF}"; SUCCESS="$?"

# [[ "${SUCCESS}" != "0" ]] && printf "%b%-21s %-28s %-21s %-11s %s%b\n" "\033[1;31m" "($(date +%F_%T))" "$(basename "${PARENT_SCRIPT_PATH_PARAM}"):(${LINENO})" "main:" "[CRITICAL]" "Config load Failed: \"${INIT_CONF}\"" "\033[0m" | tee -a "${LOG_FILE}" 2>&1 && set -e && exit 1
# log_debug "Successfully Sourced Current Script: $(basename "${PARENT_SCRIPT_PATH_PARAM}"), Init Config File: ${INIT_CONF}, Success: ${SUCCESS}"


#####################################################################################################################################################################################################
# TODO: Move these "Run env info functions" to config file
#####################################################################################################################################################################################################
source "${DATE_FUNCTIONS_SCRIPT}"
log_debug "Run env info functions"
BASE_DIR=$(${GET_PROJECT_SCRIPT} "${BASH_SOURCE}")
CURRENT_OS=$(${GET_OS_SCRIPT})


#####################################################################################################################################################################################################
# Get git branches and ages.  yay.
#####################################################################################################################################################################################################
git fetch --prune

#for k in $(git branch | sed s/^..//); do echo -e $(git log --color=always -1 --pretty=format:"%Cgreen%ci %Cblue%cr%Creset" $k --)\\t"$k";done | sort
echo -ne "\nLocal Branches:\n"
git for-each-ref --sort='committerdate:iso8601' --color --format="%(color:green)%(committerdate:iso8601)|%(color:blue)%(committerdate:relative)|%(color:reset)%09%(refname)" refs/heads | awk -F "refs/heads/" '{print $1 $2;}' | column -s '|' -t

echo -ne "\nRemote Branches:\n"
git for-each-ref --sort='committerdate:iso8601' --color --format="%(color:green)%(committerdate:iso8601)|%(color:blue)%(committerdate:relative)|%(color:reset)%09%(refname)" refs/remotes | awk -F "refs/remotes/" '{print $1 $2;}' | column -s '|' -t
