#!/usr/bin/env bash
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       0.1.4 (0.7.3)
# File Name:     setup_environment.conf
# File Path:     <Project>/<Sub-Project>/<Application>/conf/
#
# Date:          2025-10-11
# Last Modified: 2025-12-25
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
# Define Script Constants
#####################################################################################################################################################################################################
export TRUE="0"
export FALSE="1"

# export DEBUG="${TRUE}"
export DEBUG="${FALSE}"


#####################################################################################################################################################################################################
# Only Source this conf file Once
#####################################################################################################################################################################################################
if [[ "${SETUP_ENVIRONMENT_SOURCED}" != "${TRUE}" ]]; then
    export SETUP_ENVIRONMENT_SOURCED="${TRUE}"
else
    log_warning "setup_environment.conf already sourced.  Skipping re-source."
    [[ "${DEBUG}" == "${TRUE}" ]] && exit $(( TRUE )) || return $(( TRUE ))
fi


#####################################################################################################################################################################################################
# Define local constants
#####################################################################################################################################################################################################
# Configuration
export PROJECT_NAME="Juniper Canopy"
export ENV_NAME="JuniperPython"
export PROJECT_DIR="${HOME}/Development/python/JuniperCanopy/juniper_canopy"

# Colors for output
export RED='\033[0;31m'
export GREEN='\033[0;32m'
export YELLOW='\033[1;33m'
export BLUE='\033[0;34m'
export NC='\033[0m' # No Color

# Define Script Constants
export BASH_CONFIG=""

export LINUX="Linux"
export MACOS="Darwin"

export COMMENT_REGEX="^[[:space:]]*#.*$"
export CONDA_CMD="conda"
export MAMBA_CMD="mamba"
export CONDA_OFFSET="2"
export MAMBA_OFFSET="3"

# USE_CONDA="${TRUE}"
export USE_CONDA="${FALSE}"
export USE_MAMBA="$(((USE_CONDA + 1) % 2))"

# shellcheck disable=SC2155
export OS_TYPE="$(uname -s)"
