#!/usr/bin/env bash
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       1.0.0
# File Name:     git_branch_ages.bash
# File Path:     <Project>/<Sub-Project>/<Application>/util/
#
# Date:          2025-12-03
# Last Modified: 2026-01-03
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


#####################################################################################################################################################################################################
# Initialize script by sourcing the init_conf.bash config file
#####################################################################################################################################################################################################
set -o functrace
# shellcheck disable=SC2155
export PARENT_PATH_PARAM="$(realpath "${BASH_SOURCE[0]}")" && INIT_CONF="$(dirname "$(dirname "${PARENT_PATH_PARAM}")")/conf/init.conf"
# shellcheck disable=SC2015,SC1090
[[ -f "${INIT_CONF}" ]] && source "${INIT_CONF}" || { echo "Init Config File Not Found. Unable to Continue."; exit 1; }


#####################################################################################################################################################################################################
# Get git branches and ages.  yay.
#####################################################################################################################################################################################################
log_trace "Get git branches and ages. yay."
git fetch --prune
log_trace "Git fetch --prune completed."

log_trace "Get ages for local git branches."
echo -ne "\nLocal Branches:\n"
git for-each-ref --sort='committerdate:iso8601' --color --format="%(color:green)%(committerdate:iso8601)|%(color:blue)%(committerdate:relative)|%(color:reset)%09%(refname)" refs/heads | awk -F "refs/heads/" '{print $1 $2;}' | column -s '|' -t

log_trace "Get ages for remote git branches."
echo -ne "\nRemote Branches:\n"
git for-each-ref --sort='committerdate:iso8601' --color --format="%(color:green)%(committerdate:iso8601)|%(color:blue)%(committerdate:relative)|%(color:reset)%09%(refname)" refs/remotes | awk -F "refs/remotes/" '{print $1 $2;}' | column -s '|' -t

return $(( TRUE ))
