#!/usr/bin/env bash
#####################################################################################################################################################################################################
# Application: Juniper
# Script Name: get_code_stats.bash
# Script Path: <Project>/util/get_code_stats.bash
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

#######################################################################################################################################################################################
# Define Debug Constants
#######################################################################################################################################################################################
TRUE="TRUE"
FALSE="FALSE"

# DEBUG="${TRUE}"
DEBUG="${FALSE}"


#######################################################################################################################################################################################
# Define Global Project Constants
#######################################################################################################################################################################################
HOME_DIR="${HOME}"

FUNCTION_NAME="${0##*/}"

# PROJ_NAME="dynamic_nn"
# PROJ_NAME="juniper"
PROJ_NAME="Juniper"

#PROJ_LANG_DIR_NAME="rust/rust_mudgeon"
PROJ_LANG_DIR_NAME="python"

DEV_DIR_NAME="Development"
DEV_DIR="${HOME_DIR}/${DEV_DIR_NAME}"
PROJ_ROOT_DIR="${DEV_DIR}/${PROJ_LANG_DIR_NAME}"
PROJ_DIR="${PROJ_ROOT_DIR}/${PROJ_NAME}"

UTIL_DIR_NAME="util"
UTIL_DIR="${PROJ_DIR}/${UTIL_DIR_NAME}"

CONF_DIR_NAME="conf"
CONF_DIR="${PROJ_DIR}/${CONF_DIR_NAME}"
CONF_FILE_NAME="script_util.cfg"
CONF_FILE="${CONF_DIR}/${CONF_FILE_NAME}"

source "${CONF_FILE}"


#######################################################################################################################################################################################
# Configure Script Environment
#######################################################################################################################################################################################
SRC_DIR_NAME="src"
SRC_DIR="${PROJ_DIR}/${SRC_DIR_NAME}"
LOG_DIR_NAME="logs"
LOG_DIR="${PROJ_DIR}/${LOG_DIR_NAME}"
UTIL_DIR_NAME="util"
UTIL_DIR="${PROJ_DIR}/${UTIL_DIR_NAME}"
DATA_DIR_NAME="data"
DATA_DIR="${PROJ_DIR}/${DATA_DIR_NAME}"
VIZ_DIR_NAME="viz"
VIZ_DIR="${PROJ_DIR}/${VIZ_DIR_NAME}"
CONF_DIR_NAME="conf"
CONF_DIR="${PROJ_DIR}/${CONF_DIR_NAME}"
TEST_DIR_NAME="tests"
TEST_DIR="${PROJ_DIR}/${TEST_DIR_NAME}"


#######################################################################################################################################################################################
# Define the Script Environment File Constants
#######################################################################################################################################################################################
CONF_FILE_NAME="logging_config.yaml"
CONF_FILE="${CONF_DIR}/${CONF_FILE_NAME}"
GET_FILENAMES_SCRIPT_NAME="get_module_filenames.bash"
GET_FILENAMES_SCRIPT="${UTIL_DIR}/${GET_FILENAMES_SCRIPT_NAME}"
GET_SOURCETREE_SCRIPT_NAME="source_tree.bash"
GET_SOURCETREE_SCRIPT="${UTIL_DIR}/${GET_SOURCETREE_SCRIPT_NAME}"
GET_TODO_COMMENTS_SCRIPT_NAME="get_todo_comments.bash"
GET_TODO_COMMENTS_SCRIPT="${UTIL_DIR}/${GET_TODO_COMMENTS_SCRIPT_NAME}"
GET_FILE_TODO_SCRIPT_NAME="get_file_todo.bash"
GET_FILE_TODO_SCRIPT="${UTIL_DIR}/${GET_FILE_TODO_SCRIPT_NAME}"
GIT_LOG_WEEKS_SCRIPT_NAME="__git_log_weeks.bash"
GIT_LOG_WEEKS_SCRIPT="${UTIL_DIR}/${GIT_LOG_WEEKS_SCRIPT_NAME}"


#######################################################################################################################################################################################
# Define the Script Constants
#######################################################################################################################################################################################
#DEBUG="true"
DEBUG="false"

FULL_OUTPUT="true"
#FULL_OUTPUT="false"

FILENAMES_SCRIPT_PARAMS="--full ${FULL_OUTPUT}"

SEARCH_TERM_DEFAULT="TODO"
TODO_SEARCH_SCRIPT_PARAMS="--search ${SEARCH_TERM_DEFAULT} --file"

FIND_METHOD_REGEX='^[[:space:]]+(def)[[:space:]]+'
FIND_METHOD_PARAMS="-E --"

EXIT_COND_DEFAULT="1"

INIT_PYTHON_FILE="__init__"

GIT_LOG_WEEKS="0"

SIZE_LABEL_MAG="1024"
SIZE_LABELS=("B" "K" "M" "G" "T" "P" "E" "Z" "Y")

TABLE_FORMAT="%-28s %8s %9s %7s %9s\n"
SUMMARY_FORMAT="%-14s %-10s\n"
FILE_SUMMARY_FORMAT="%-17s %-12s %-3s %-40s\n"

# Longest File(s):  (    1999 lines) --  NeuralNetwork.py
# Methods File(s):  (      76 methods) --  EvolveState.py
# Largest File(s):  (108 KB)     --  NeuralNetwork.py
# Roughest File(s): (      24 TODOs) --  DNA.py


####################################################################################################
# Define command line parameter switches
####################################################################################################
HELP_SHOR="-h"
HELP_LONG="--help"

SEARCH_SHORT="-s"
SEARCH_LONG="--search"

OUTPUT_SHORT="-f"
OUTPUT_LONG="--full"


####################################################################################################
# Run env info functions
####################################################################################################
BASE_DIR=$(${GET_PROJECT_SCRIPT} "${BASH_SOURCE}")
# Determine Host OS
CURRENT_OS=$(${GET_OS_SCRIPT})
# Define Script Functions
source "${DATE_FUNCTIONS_SCRIPT}"


####################################################################################################
# Define Script Functions
####################################################################################################
function round_size() {
    SIZEF="${1}"
    SIZE="${SIZEF%.*}"
    DEC="0.${DIG}"
    if (( $(echo "${DEC} >= 0.5" | bc -l) )); then
        SIZE=$(( SIZE + 1 ))
    fi
    echo "${SIZE}"
}

function current_size() {
    CURRENT_SIZE="${1}"
    LABEL="${CURRENT_SIZE: -1}"
    SIZEF="${CURRENT_SIZE::-1}"
    for i in "${!SIZE_LABELS[@]}"; do
        if [[ "${SIZE_LABELS[${i}]}" == "${LABEL}" ]]; then
            break
        else
            #SIZE=$(( SIZE * SIZE_LABEL_MAG ))
            #SIZEF=$(( SIZEF * SIZE_LABEL_MAG ))
            SIZEF="$(echo "${SIZEF} * ${SIZE_LABEL_MAG}" | bc -l)"
	fi
    done
    SIZE="$(round_size ${SIZEF})"
    echo "${SIZE}"
}

function readable_size() {
    CURRENT_SIZE="${1}"
    LABEL_INDEX=0
    BYTES_LABEL=""
    while (( $(echo "${CURRENT_SIZE} >= ${SIZE_LABEL_MAG}" | bc -l) )); do
        CURRENT_SIZE="$(echo "${CURRENT_SIZE} / ${SIZE_LABEL_MAG}" | bc -l)"
        LABEL_INDEX=$(( LABEL_INDEX + 1 ))
    done
    SIZE="$(round_size ${CURRENT_SIZE})"
    if (( LABEL_INDEX > 0 )); then
        BYTE_LABEL="${SIZE_LABELS[0]}"
    fi
    READABLE="${SIZE} ${SIZE_LABELS[${LABEL_INDEX}]}${BYTE_LABEL}"
    echo "${READABLE}"
}


################################################################################################################
# Print Column Labels and Header data for Project source files
################################################################################################################
# Print heading data
echo -ne "\nDisplay Stats for the ${PROJ_NAME} Project\n\n"
printf "${TABLE_FORMAT}" "Filename" "Lines" "Methods" "TODOs" "Size"
printf "${TABLE_FORMAT}" "----------------------------" "------" "--------" "------" "------"


################################################################################################################
# Search project source files and retrieve stats
################################################################################################################
# Initialize project summary counters
TOTAL_FILES=0
TOTAL_LINES=0
TOTAL_METHODS=0
TOTAL_TODOS=0
TOTAL_SIZE=0

MOST_LINES=0
MOST_METHODS=0
MOST_TODOS=0
MOST_SIZE=0

LONG_FILE=""
METHOD_FILE=""
ROUGH_FILE=""
BIG_FILE=""

# Evaluate each source file in project
for i in $(${GET_FILENAMES_SCRIPT} ${FILENAMES_SCRIPT_PARAMS}); do
    # Get current filename and absolute path
    FILE_PATH="$(echo "${i}" | xargs)"
    FILE_NAME="$(echo "${FILE_PATH##*/}" | xargs)"
    [[ ${DEBUG} == "${TRUE}" ]] && echo "Filename: ${FILE_NAME}"

    # Calculate stats for current file
    TOTAL_FILES=$(( TOTAL_FILES + 1 ))

    # Perform Line count calculations
    CURRENT_LINES="$(cat ${FILE_PATH} | wc -l)"
    if (( $(echo "${CURRENT_LINES} > ${MOST_LINES}" | bc -l) )); then
        MOST_LINES="$(echo "${CURRENT_LINES}" | xargs)"
	LONG_FILE="$(echo "${FILE_NAME}" | xargs)"
    elif (( $(echo "${CURRENT_LINES} == ${MOST_LINES}" | bc -l) )); then
        LONG_FILE="${LONG_FILE}, $(echo "${FILE_NAME}" | xargs)"
    fi
    TOTAL_LINES="$(echo "$(( TOTAL_LINES + CURRENT_LINES ))" | xargs)"

    # Perform Method Count calculation
    CURRENT_METHODS=$(grep ${FIND_METHOD_PARAMS} ${FIND_METHOD_REGEX} ${FILE_PATH} | wc -l)
    if (( $(echo "${CURRENT_METHODS} > ${MOST_METHODS}" | bc -l) )); then
        MOST_METHODS="$(echo "${CURRENT_METHODS}" | xargs)"
	METHOD_FILE="$(echo "${FILE_NAME}" | xargs)"
    elif (( $(echo "${CURRENT_METHODS} == ${MOST_METHODS}" | bc -l) )); then
        METHOD_FILE="${METHOD_FILE}, $(echo "${FILE_NAME}" | xargs)"
    fi
    TOTAL_METHODS="$(echo "$(( TOTAL_METHODS + CURRENT_METHODS ))" | xargs)"

    # Perform TODO count calculations
    CURRENT_TODOS="$(echo "$(${GET_FILE_TODO_SCRIPT} ${TODO_SEARCH_SCRIPT_PARAMS} ${FILE_PATH})" | xargs)"
    if (( $(echo "${CURRENT_TODOS} > ${MOST_TODOS}" | bc -l) )); then
        MOST_TODOS="$(echo "${CURRENT_TODOS}" | xargs)"
	ROUGH_FILE="$(echo "${FILE_NAME}" | xargs)"
	[[ ${DEBUG} == ${TRUE} ]] && echo "Current TODOs: ${MOST_TODOS}, for File: ${ROUGH_FILE}"
    elif (( $(echo "${CURRENT_TODOS} == ${MOST_TODOS}" | bc -l) )); then
        ROUGH_FILE="${ROUGH_FILE}, $(echo "${FILE_NAME}" | xargs)"
    fi
    TOTAL_TODOS="$(echo "$(( TOTAL_TODOS + CURRENT_TODOS ))" | xargs)"

    # Perform size calculations
    CURRENT_SIZE="$(echo "$(du -sh ${FILE_PATH} | cut -d $'\t' -f-1)" | xargs)"
    BYTE_SIZE="$(current_size ${CURRENT_SIZE})"
    if (( $(echo "${BYTE_SIZE} > ${MOST_SIZE}" | bc -l) )); then
        MOST_SIZE="$(echo "${BYTE_SIZE}" | xargs)"
	BIG_FILE="$(echo "${FILE_NAME}" | xargs)"
    elif (( $(echo "${BYTE_SIZE} == ${MOST_SIZE}" | bc -l) )); then
        BIG_FILE="$(echo "${BIG_FILE}" | xargs), $(echo "${FILE_NAME}" | xargs)"
    fi
    TOTAL_SIZE="$(echo "$(( TOTAL_SIZE + BYTE_SIZE ))" | xargs)"
    OUTPUT_SIZE="$(readable_size $(echo "${BYTE_SIZE}" | xargs))"

    # Print Stats for current File
    printf "${TABLE_FORMAT}" "${FILE_NAME}" "${CURRENT_LINES}" "${CURRENT_METHODS}" "${CURRENT_TODOS}" "${OUTPUT_SIZE}"
done
READABLE_SIZE="$(readable_size $(echo "${TOTAL_SIZE}" | xargs))"
BIG_FILE_SIZE="$(readable_size $(echo "${MOST_SIZE}" | xargs))"


################################################################################################################
# Print Project Summary data
################################################################################################################
# Print summary data
echo -ne "\n\nProject ${PROJ_NAME} Summary:\n\n"
printf "${SUMMARY_FORMAT}" "Total Files:" "${TOTAL_FILES}"
printf "${SUMMARY_FORMAT}" "Total Methods:" "${TOTAL_METHODS}"
printf "${SUMMARY_FORMAT}" "Total Lines:" "${TOTAL_LINES}"
printf "${SUMMARY_FORMAT}" "Total TODOs:" "${TOTAL_TODOS}"
printf "${SUMMARY_FORMAT}" "Total Size:" "${READABLE_SIZE}"


################################################################################################################
# Print Project File Summary data
################################################################################################################
echo -ne "\n\nProject ${PROJ_NAME} File Summary:\n\n"
printf "${FILE_SUMMARY_FORMAT}" "Longest File(s):" "(${MOST_LINES} lines)" "--" "${LONG_FILE}"
printf "${FILE_SUMMARY_FORMAT}" "Methods File(s):" "(${MOST_METHODS} methods)" "--" "${METHOD_FILE}"
printf "${FILE_SUMMARY_FORMAT}" "Largest File(s):" "(${BIG_FILE_SIZE})" "--" "${BIG_FILE}"
printf "${FILE_SUMMARY_FORMAT}" "Roughest File(s):" "(${MOST_TODOS} TODOs)" "--" "${ROUGH_FILE}"


################################################################################################################
# Display Project Git log info
################################################################################################################
echo -ne "\n\nProject ${PROJ_NAME} Git Log Summary\n\n"
${GIT_LOG_WEEKS_SCRIPT} ${GIT_LOG_WEEKS}
echo -ne "\n"

exit 2
