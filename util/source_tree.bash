#!/usr/bin/env bash
#####################################################################################################################################################################################################
# Application: Juniper
# Script Name: source_tree.bash
# Script Path: <Project>/util/source_tree.bash
#
# Description: This script display the contents of the source, config, and log directories for a project in Tree format
#
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# Notes:
#
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# Examples:
#
#####################################################################################################################################################################################################

#####################################################################################################
# Define Global Configuration File Constants
####################################################################################################
# ROOT_PROJ_NAME="dynamic_nn"
# ROOT_PROJ_NAME="juniper"
ROOT_PROJ_NAME="Juniper"
ROOT_CONF_NAME="conf"
ROOT_CONF_FILE_NAME="script_util.cfg"
# ROOT_PROJ_DIR="${HOME}/Development/rust/rust_mudgeon/${ROOT_PROJ_NAME}"
ROOT_PROJ_DIR="${HOME}/Development/python/${ROOT_PROJ_NAME}"
ROOT_CONF_DIR="${ROOT_PROJ_DIR}/${ROOT_CONF_NAME}"
ROOT_CONF_FILE="${ROOT_CONF_DIR}/${ROOT_CONF_FILE_NAME}"

source ${ROOT_CONF_FILE}


#######################################################################################################################################################################################
# Define the Script Constants
#######################################################################################################################################################################################
DEBUG="true"
# DEBUG="false"

FULL_OUTPUT="true"
#FULL_OUTPUT="false"

HELP_SHORT="-h"
HELP_LONG="--help"

EXIT_COND_DEFAULT="1"

SEARCH_TERM_DEFAULT="write tests"
SEARCH_TERM_DEFAULT="TODO"

INIT_PYTHON_FILE="__init__"


##################################################################################
# Determine Project Dir
##################################################################################
BASE_DIR=$(${GET_PROJECT_SCRIPT} "${BASH_SOURCE}")


##################################################################################
# Determine Host OS
##################################################################################
CURRENT_OS=$(${GET_OS_SCRIPT})


####################################################################################################
# Define Script Functions
####################################################################################################
source ${DATE_FUNCTIONS_SCRIPT}


##################################################################################
# Define Script Constants
##################################################################################
if [[ $@ == "" ]]; then
  echo "Warning: No Input Parameters Provided"
  #DIR_LIST="./conf ./data ./src ./util"
  DIR_LIST="${CONFIG_DIR_NAME} ${DATA_DIR_NAME} ${DOCUMENT_DIR_NAME} ${SOURCE_DIR_NAME} ${UTILITY_DIR_NAME}"
else
  DIR_LIST="$@"
fi
echo "Dir list: ${DIR_LIST}"


##################################################################################
# Validate subdirectory list
##################################################################################
cd ${BASE_DIR}
WORKING_LIST=""
for DIR in ${DIR_LIST}; do
    if [[ -d ${DIR} ]]; then
        WORKING_LIST="${WORKING_LIST}${DIR} "
    fi
done


##################################################################################
# Print directory listing as Tree structure
##################################################################################
tree ${WORKING_LIST}
