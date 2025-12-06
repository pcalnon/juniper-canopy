#!/bin/bash
#####################################################################################################################################################################################################
# Application: Juniper
# Script Name: __get_os_name.bash
# Script Path: <Project>/util/__get_os_name.bash
#
# Description: This script returns the name of the OS on the current host
#
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# Notes:
#
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# Examples:
#
#####################################################################################################################################################################################################


#####################################################################################################
# Define GLobal Debug Constants
#####################################################################################################
TRUE="true"
FALSE="false"

DEBUG="${TRUE}"
# DEBUG="${FALSE}"


#####################################################################################################
# Define Global Functions
####################################################################################################
# Define local Functions
get_script_path() {
    local source="${BASH_SOURCE[0]}"
    while [ -L "$source" ]; do
        local dir="$(cd -P "$(dirname "$source")" && pwd)"
        source="$(readlink "$source")"
        [[ $source != /* ]] && source="$dir/$source"
    done
    echo "$(cd -P "$(dirname "$source")" && pwd)/$(basename "$source")"
}


####################################################################################################
# Define Global Environment DirectoryConfiguration Constants
####################################################################################################
SCRIPT_NAME="$(basename $BASH_SOURCE)"
SCRIPT_PATH="$(dirname "$(get_script_path)")"
SCRIPT_PROJ_PATH="$(dirname "${SCRIPT_PATH}")"
ROOT_PROJ_DIR_NAME="$(basename "${SCRIPT_PROJ_PATH}")"
SCRIPT_LANG_PATH="$(dirname "${SCRIPT_PROJ_PATH}")"
ROOT_LANG_DIR_NAME="$(basename "${SCRIPT_LANG_PATH}")"
SCRIPT_DEVELOPMENT_PATH="$(dirname "${SCRIPT_LANG_PATH}")"
ROOT_DEV_DIR_NAME="$(basename "${SCRIPT_DEVELOPMENT_PATH}")"
SCRIPT_ROOT_PATH="$(dirname "${SCRIPT_DEVELOPMENT_PATH}")"

ROOT_PROJ_NAME="${ROOT_PROJ_DIR_NAME}"
ROOT_CONF_NAME="conf"
ROOT_CONF_FILE_NAME="script_util.cfg"

ROOT_PROJ_DIR="${SCRIPT_PROJ_PATH}"
ROOT_CONF_DIR="${ROOT_PROJ_DIR}/${ROOT_CONF_NAME}"
ROOT_CONF_FILE="${ROOT_CONF_DIR}/${ROOT_CONF_FILE_NAME}"
source ${ROOT_CONF_FILE}


##################################################################################
# Determine Host OS
##################################################################################
CURRENT_OS="$(cat /etc/os-release | grep -e "^NAME=" | awk -F "\"" '{print $2;}')"
echo "${CURRENT_OS}"
