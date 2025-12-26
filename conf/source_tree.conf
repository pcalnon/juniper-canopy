#!/usr/bin/env bash
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       0.1.4 (0.7.3)
# File Name:     source_tree.conf
# File Path:     <Project>/<Sub-Project>/<Application>/conf/
#
# Date:          2025-10-11
# Last Modified: 2025-12-25
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#     This script display the contents of the source, config, and log directories for a project in Tree format
#
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
# Define Script Constants
#####################################################################################################################################################################################################
export TRUE="0"
export FALSE="1"

# export DEBUG="${TRUE}"
export DEBUG="${FALSE}"


#####################################################################################################################################################################################################
# Only Source this conf file Once
#####################################################################################################################################################################################################
if [[ "${SOURCE_TREE_SOURCED}" != "${TRUE}" ]]; then
    export SOURCE_TREE_SOURCED="${TRUE}"
else
    log_warning "source_tree.conf already sourced.  Skipping re-source."
    [[ "${DEBUG}" == "${TRUE}" ]] && exit $(( TRUE )) || return $(( TRUE ))
fi


#####################################################################################################
# Define Global Configuration File Constants
####################################################################################################
# ROOT_PROJ_NAME="dynamic_nn"
# ROOT_PROJ_NAME="juniper"
export ROOT_PROJ_NAME="Juniper"
export ROOT_SUB_PROJECT_NAME="JuniperCanopy"
export ROOT_APP_NAME="juniper_canopy"
export ROOT_CONF_NAME="conf"
export ROOT_CONF_FILE_NAME="common.conf"
# ROOT_PROJ_DIR="${HOME}/Development/rust/rust_mudgeon/${ROOT_PROJ_NAME}"
# export ROOT_PROJ_DIR="${HOME}/Development/python/${ROOT_PROJ_NAME}"
export ROOT_PROJ_DIR="${HOME}/Development/python/${ROOT_SUB_PROJ_NAME}/${ROOT_APP_NAME}"
export ROOT_CONF_DIR="${ROOT_PROJ_DIR}/${ROOT_CONF_NAME}"
export ROOT_CONF_FILE="${ROOT_CONF_DIR}/${ROOT_CONF_FILE_NAME}"

# source ${ROOT_CONF_FILE}


#######################################################################################################################################################################################
# Define the Script Constants
#######################################################################################################################################################################################
export TRUE="0"
export FALSE="1"

export DEBUG="${TRUE}"
# export DEBUG="${FALSE}"

export FULL_OUTPUT="${TRUE}"
# export FULL_OUTPUT="${FALSE}"

export HELP_SHORT="-h"
export HELP_LONG="--help"

export EXIT_COND_DEFAULT="1"

export SEARCH_TERM_DEFAULT="write tests"
export SEARCH_TERM_DEFAULT="TODO"

export INIT_PYTHON_FILE="__init__"


##################################################################################
# Determine Project Dir
##################################################################################
# shellcheck disable=SC2155
export BASE_DIR=$("${GET_PROJECT_SCRIPT}" "${BASH_SOURCE[0]}")


##################################################################################
# Determine Host OS
##################################################################################
# shellcheck disable=SC2155
export CURRENT_OS=$(${GET_OS_SCRIPT})


####################################################################################################
# Define Script Functions
####################################################################################################
# source ${DATE_FUNCTIONS_SCRIPT}
