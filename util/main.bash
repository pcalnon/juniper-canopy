#!/usr/bin/env bash
#####################################################################################################################################################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     try.bash
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
#    This script performs initial environment setup and launches the Frontend Application
#       to monitor the current Cascade Correlation Neural Network prototype
#       including training, state, and architecture for monitoring and diagnostics.
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
#
#         LANGUAGE_NAME
#         LANGUAGE_PATH
#
#         PYTHON, JAVASCRIPT, RUST, JAVA, RUBY, NODE, GO, CPP, C, R
#
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


#####################################################################################################################################################################################################
# TODO: Move these to config file
#####################################################################################################################################################################################################
PROJECT_NAME="Juniper"

WORKING_DIR="${HOME}/Development/python/${PROJECT_NAME}"

SOURCE_DIR="${WORKING_DIR}/src"
PYTHON_FILE_NAME="main.py"

PYTHON_FILE="${SOURCE_DIR}/${PYTHON_FILE_NAME}"


#####################################################################################################################################################################################################
# Launch the Main python script for the Project
#####################################################################################################################################################################################################
python3 --version
python3 ${PYTHON_FILE}
