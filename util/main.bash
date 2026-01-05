#!/usr/bin/env bash
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       0.1.4 (0.7.3)
# File Name:     main.bash
# File Path:     <Project>/<Sub-Project>/<Application>/util/
#
# Date:          2025-10-11
# Last Modified: 2026-01-03
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#    This script performs initial environment setup and launches the Frontend Application to provide an interactive display of the
#    Cascade Correlation Neural Network prototype including training, state, and architecture for monitoring and diagnostics.
#
#####################################################################################################################################################################################################
# Notes:
#     This script is assumed to be located in a **/<Project Name>/utils/ dir for the Current Project
#     Languages are all assumed to be installed in and accessible from conda
#
#     Key Constants Defined in the juniper_canopy.conf file
#         PROJECT_NAME
#         PROTOTYPE_PROJECT == TRUE|FALSE
#         CURRENT_PROJECT
#         PROJECT_PATH
#         HOME_DIR
#         MAIN_FILE
#         LANGUAGE_NAME
#         LANGUAGE_PATH
#         PYTHON, JAVASCRIPT, RUST, JAVA, RUBY, NODE, GO, CPP, C, R
#         CASCOR_NAME
#         CASCOR_PATH
#         CASCOR
#
########################################################################################################)#############################################################################################
# References:
#
#####################################################################################################################################################################################################
# TODO:
#     Create a Bash script template from the implementation of this script using the sourced, common config file.
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
# Launch the Main python script for the Project
#####################################################################################################################################################################################################
log_trace "Launch the Main python script for the Project"
# python3 --version
log_verbose "Active Python Version: $(python3 --version)"
python3 "${PYTHON_FILE}"
log_trace "Completed launching the Main python script for the Project"

exit $(( TRUE ))
