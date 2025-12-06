#!/usr/bin/env bash
############################################################################################################################################################
# Project: Juniper
# Application: dynamic_nn
# Version: 6.3.2
#
# File: random_seed.bash
# Author: Paul Calnon
# Created: 2024-04-01
# Modified: 2024-04-01
#
############################################################################################################################################################
# Description:
#   Call a python script to generate a new, cryptographically secure random value for use as seed in psuedo random functions
#
#
############################################################################################################################################################
# Notes:
#   /Users/pcalnon/opt/anaconda3/envs/pytorch_cuda/bin/python
#   /home/pcalnon/anaconda3/envs/pytorch_cuda/bin/python
#
#
############################################################################################################################################################

#####################################################################################################
# Define Global Configuration File Constants
####################################################################################################
ROOT_DIR="${HOME}"

DEV_DIR_NAME="Development"
ROOT_DEV_DIR="${ROOT_DIR}/${DEV_DIR_NAME}"

PYTHON_DIR_NAME="python/testing"
PYTHON_DIR="${ROOT_DEV_DIR}/${PYTHON_DIR_NAME}"

# ROOT_PROJ_NAME="dynamic_nn"
# ROOT_PROJ_NAME="juniper"
ROOT_PROJ_NAME="Juniper"
PROJ_DIR="${PYTHON_DIR}/${ROOT_PROJ_NAME}"

ROOT_CONF_NAME="conf"
CONF_DIR="${PROJ_DIR}/${ROOT_CONF_NAME}"

ROOT_CONF_FILE_NAME="script_util.cfg"
CONF_FILE="${CONF_DIR}/${ROOT_CONF_FILE_NAME}"

ROOT_UTIL_NAME="util"
UTIL_DIR="${PROJ_DIR}/${ROOT_UTIL_NAME}"

NEW_RANDOM_SEED_FILE_NAME="new_random_seed.py"
RANDOM_SEED="${UTIL_DIR}/${NEW_RANDOM_SEED_FILE_NAME}"

OS_NAME_SCRIPT_FILE="__get_os_name.bash"
OS_NAME_SCRIPT="${UTIL_DIR}/${OS_NAME_SCRIPT_FILE}"


####################################################################################################
# Source script config file
####################################################################################################
#echo "source ${CONF_FILE}"
source ${CONF_FILE}


####################################################################################################
# Define Environment constants for determining active python binary
####################################################################################################
OS_LINUX="Linux"
OS_MACOS="Darwin"
OS_WINDOWS="Windows"
OS_UNKNOWN="Unknown"

CONDA_MACOS="opt/anaconda3"
CONDA_LINUX="anaconda3"

PYTHON_LOC="envs/pytorch_cuda/bin/python"


####################################################################################################
# Get the OS name and find active python binary
####################################################################################################

#echo "Getting Current OS Name"
#OS_NAME=$(__get_os_name.bash)
#echo "OS_NAME=\$(${OS_NAME_SCRIPT})"
OS_NAME=$(${OS_NAME_SCRIPT})
#echo "Detected Running OS: ${OS_NAME}"

# Validate Local OS
#echo "Validating Local OS"
if [[ ${OS_NAME} == ${OS_LINUX} ]]; then
    #echo "Found Valid OS: ${OS_NAME}"
    PYTHON_CMD="${HOME}/${CONDA_LINUX}/${PYTHON_LOC}"
elif [[ ${OS_NAME} == ${OS_MACOS} ]]; then
    #echo "Found Valid OS: ${OS_NAME}"
    PYTHON_CMD="${HOME}/${CONDA_MACOS}/${PYTHON_LOC}"
elif [[ ${OS_NAME} == ${OS_WINDOWS} ]]; then
    echo "Error: Why the hell are you running ${OS_WINDOWS}??"
    exit 1
else
    echo "Error: You are running an ${OS_UNKNOWN} OS. Cowardly not wading into this crazy."
    exit 2
fi
#echo "OS Name: ${OS_NAME},  Python Command: ${PYTHON_CMD}"

PYTHON_VER="$(${PYTHON_CMD} --version)"
#echo "Current Python Version: ${PYTHON_VER}"
#echo "Local OS: ${OS_NAME}, Python: ${PYTHON_CMD}, Version: ${PYTHON_VERSION}"
#echo "Launching python script: ${RANDOM_SEED}"
#echo "${PYTHON_CMD} ${RANDOM_SEED}"
${PYTHON_CMD} ${RANDOM_SEED}

RESULT="$?"
if [[ ${RESULT} == "0" ]]; then
    echo -ne "\nSuccess!!  "
else
    echo -ne "\nFailure :(  "
fi
echo "Python Script: ${NEW_RANDOM_SEED_FILE_NAME}, returned: ${RESULT}"
