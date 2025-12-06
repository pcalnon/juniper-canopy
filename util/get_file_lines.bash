#!/usr/bin/env bash
#####################################################################################################################################################################################################
# Application: Juniper
# Script Name: todo_search.bash
# Script Path: <Project>/util/todo_search.bash
#
# Description: This script files in the source directory of the current project for a specific search term and then displays the number of files that do and do not contain the search term.
#
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# Notes:
#
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# Examples:
#
#####################################################################################################################################################################################################

#####################################################################################################
# Define Global Project Constants
####################################################################################################
# PROJ_NAME="dynamic_nn"
# PROJ_NAME="juniper"
PROJ_NAME="Juniper"

HOME_DIR="${HOME}"

DEVELOPMENT_DIR_NAME="Development"
DEVELOPMENT_DIR="${HOME_DIR}/${DEVELOPMENT_DIR_NAME}"

#LANGUAGE_DIR_NAME="rust/rust_mudgeon"
LANGUAGE_DIR_NAME="python"
LANGUAGE_DIR="${DEVELOPMENT_DIR}/${LANGUAGE_DIR_NAME}"

PROJECT_DIR_NAME="${PROJ_NAME}"
PROJECT_DIR="${LANGUAGE_DIR}/${PROJECT_DIR_NAME}"

BASE_DIR=${PROJECT_DIR}
#echo "Base Dir: ${BASE_DIR}"


#####################################################################################################
# Define Global Configuration File Constants
####################################################################################################
ROOT_CONF_DIR_NAME="conf"
ROOT_CONF_DIR="${PROJECT_DIR}/${ROOT_CONF_DIR_NAME}"
ROOT_CONF_FILE_NAME="script_util.cfg"
ROOT_CONF_FILE="${ROOT_CONF_DIR}/${ROOT_CONF_FILE_NAME}"
#echo "Root Conf File: ${ROOT_CONF_FILE}"
source ${ROOT_CONF_FILE}


#######################################################################################################################################################################################
# Define the Script Constants
#######################################################################################################################################################################################
#DEBUG="true"
DEBUG="false"

FULL_OUTPUT="true"
#FULL_OUTPUT="false"

HELP_SHORT="-h"
HELP_LONG="--help"

EXIT_COND_DEFAULT="1"

#SEARCH_TERM_DEFAULT="write tests"
SEARCH_TERM_DEFAULT="TODO"

INIT_PYTHON_FILE="__init__"


#######################################################################################################################################################################################
# Define the Script Environment Dir Constants
#######################################################################################################################################################################################
SRC_DIR_NAME="src"
SRC_DIR="${BASE_DIR}/${SOURCE_DIR_NAME}"
#echo "Source Dir: ${SRC_DIR}"

LOG_DIR_NAME="logs"
LOG_DIR="${BASE_DIR}/${LOG_DIR_NAME}"
#echo "Log Dir: ${LOG_DIR}"

CONF_DIR_NAME="conf"
CONF_DIR="${BASE_DIR}/${CONFIG_DIR_NAME}"
#echo "Conf Dir: ${CONF_DIR}"

DATA_DIR_NAME="data"
DATA_DIR="${BASE_DIR}/${DATA_DIR_NAME}"
#echo "Data Dir: ${DATA_DIR}"

UTIL_DIR_NAME="util"
UTIL_DIR="${BASE_DIR}/${UTIL_DIR_NAME}"
#echo "Util Dir: ${UTIL_DIR}"

TEST_DIR_NAME="tests"
TEST_DIR="${BASE_DIR}/${TEST_DIR_NAME}"
#echo "Test Dir: ${TEST_DIR}"

VIZ_DIR_NAME="viz"
VIZ_DIR="${BASE_DIR}/${VIZ_DIR_NAME}"
#echo "Viz Dir: ${VIZ_DIR}"


#######################################################################################################################################################################################
# Define the Script Environment File Constants
#######################################################################################################################################################################################
CONF_FILE_NAME="logging_config.yaml"
CONF_FILE="${CONF_DIR}/${CONF_FILE_NAME}"
#echo "Conf File: ${CONF_FILE}"

GET_FILENAMES_SCRIPT_NAME="get_module_filenames.bash"
GET_FILENAMES_SCRIPT="${UTIL_DIR}/${GET_FILENAMES_SCRIPT_NAME}"
#echo "Get FIlenames Script: ${GET_FILENAMES_SCRIPT}"

GET_SOURCETREE_SCRIPT_NAME="source_tree.bash"
GET_SOURCETREE_SCRIPT="${UTIL_DIR}/${GET_SOURCETREE_SCRIPT_NAME}"
#echo "Get Sourcetree Script: ${GET_SOURCETREE_SCRIPT}"

GET_TODO_COMMENTS_SCRIPT_NAME="get_todo_comments.bash"
GET_TODO_COMMENTS_SCRIPT="${UTIL_DIR}/${GET_TODO_COMMENTS_SCRIPT_NAME}"
#echo "TODO Search Script: ${GET_TODO_COMMENTS_SCRIPT}"



##################################################################################
# Determine Host OS
##################################################################################
CURRENT_OS=$(${GET_OS_SCRIPT})
#echo "Current OS: ${CURRENT_OS}"


####################################################################################################
# Define Script Functions
####################################################################################################
source ${DATE_FUNCTIONS_SCRIPT}

#function usage() {
#    EXIT_COND="${EXIT_COND_DEFAULT}"
#    if [[ "$1" != "" ]]; then
#        EXIT_COND="$1"
#    fi
#    MESSAGE="usage: ${SCRIPT_NAME} <SEARCH TERM> | [--help|-h]"
#    echo -ne "\n\t${MESSAGE}\n\n"
#    exit ${EXIT_COND}
#}


#######################################################################################################################################################################################
# Process Script's Command Line Argument(s)
#######################################################################################################################################################################################
#if [[ "$1" != "" ]]; then
#    if [[ "$1" == "${HELP_SHORT}" || "$1" == "${HELP_LONG}" ]]; then
#        usage 0
#    else
#        SEARCH_TERM="$1"
#    fi
#else
#    #SEARCH_TERM="${SEARCH_TERM_DEFAULT}"
#    if [[ ${DEBUG} == "true" ]]; then
#        SEARCH_TERM="${SEARCH_TERM_DEFAULT}"
#    else
#        usage
#    fi
#fi


#######################################################################################################################################################################################
# Sanitize Inputs
#######################################################################################################################################################################################
#DASHES=$(echo "${SEARCH_TERM}" | grep -e '^-.*')
#if [[ ${DASHES} != "" ]]; then
#    SEARCH_TERM="\\${SEARCH_TERM}"
#    if [[ ${DEBUG} == "true" ]]; then
#        echo "Sanitized SEARCH_TERM Input: ${SEARCH_TERM}"
#    fi
#fi


################################################################################################################
# TODO: Use this to get names & then get lines
################################################################################################################
TOTAL_FILES=0
TOTAL_LINES=0
TOTAL_TODOS=0

for i in $(${GET_FILENAMES_SCRIPT_NAME}); do

  TOTAL_FILES=$(( TOTAL_FILES + 1 ))
  CURRENT_LINES="$(cat ${i} | wc -l)"
  TOTAL_LINES=$(( TOTAL_LINES + CURRENT_LINES ))
  CURRENT_TODOS="$(${TODO_SEARCH_SCRIPT} ${i})"
  TOTAL_TODOS=$(( TOTAL_TODOS + CURRENT_TODOS ))

  CURRENT_SIZE="$(du -sh ${i})"

  echo "File: ${i}\tLines: ${CURRENT_LINES}\tTODOs: ${CURRENT_TODOS}"

done


#######################################################################################################################################################################################
# Search for a specific TODO reference in source code
#######################################################################################################################################################################################
#DONE_COUNT=0
#FOUND_COUNT=0
#for i in $(find ${SRC_DIR}); do
#    SOURCE_FILE=$(echo "${i}" | grep "\.${SRC_FILE_SUFFIX}\$")
#    #echo "Source File: \"${SOURCE_FILE}\""
#    if [[ ${SOURCE_FILE} != "" ]]; then
#        SOURCE_FILE=$(echo "${SOURCE_FILE}" | grep -v "${INIT_PYTHON_FILE}")
#	if [[ ${SOURCE_FILE} != "" ]]; then
#            if [[ -f ${SOURCE_FILE} ]]; then
#                FOUND=$(cat ${SOURCE_FILE} | grep "${SEARCH_TERM}")
#                if [[ ${FOUND} != "" ]]; then
#                    FOUND_COUNT=$((FOUND_COUNT + 1))
#                    if [[ ${DEBUG} == "true" || ${FULL_OUTPUT} == "true" ]]; then
#                        #echo -ne "${SOURCE_FILE}\n\tFound: ${FOUND}\n\n"
#                        echo -ne "${SOURCE_FILE}\n${FOUND}\n\n"
#                    fi
#                else
#                    DONE_COUNT=$((DONE_COUNT + 1))
#                    if [[ ${FULL_OUTPUT} == "true" && ${DEBUG} == "true" ]]; then
#                        echo -ne "${SOURCE_FILE}\n\tNot Found: **********************\n\n"
#                    fi
#                fi
#            fi
#        fi
#    fi
#done


#######################################################################################################################################################################################
# Display Results Summary
#######################################################################################################################################################################################
echo "Search Term: \"${SEARCH_TERM}\""
echo "Found in Files: ${FOUND_COUNT}"
echo "Files Complete: ${DONE_COUNT}"
