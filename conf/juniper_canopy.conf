#!/usr/bin/env bash
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       0.1.4 (0.7.3)
# File Name:     juniper_canopy.conf
# File Path:     <Project>/<Sub-Project>/<Application>/conf/
#
# Date:          2025-11-04
# Last Modified: 2025-12-25
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#    This Script serves as the config file for the Juniper Project's juniper_canopy prototype
#    Warning:  This Script / Config file is sourced by the try.bash script
#
#####################################################################################################################################################################################################
# Notes:
#     Warning:  This Config file is sourced by the try.bash script
#
#     The primary use case for this Script is to be sourced by the try.bash script.
#     However, this script can also be run directly from the command line for testing purposes.
#     When run directly from the command line, this script will output debug information based on the DEBUG constant defined within the script.
#     A convenience script, ~/Development/python/JuniperCanopy/juniper_canopy/conf/test_prototype_conf.bash, is provided for testing this config file.
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
# Define Top Level Constants for Script
#####################################################################################################################################################################################################
export TRUE="0"
export FALSE="1"

export DEBUG="${FALSE}"
# export DEBUG="${TRUE}"


#####################################################################################################################################################################################################
# Define Juniper Canopy config script Name
#####################################################################################################################################################################################################
# shellcheck disable=SC2155
export SCRIPT_NAME="$(basename "$(realpath "$0")")"


#####################################################################################################################################################################################################
# Define config file demo mode and language constants
#####################################################################################################################################################################################################
log_debug "Script Name: \"${SCRIPT_NAME}\""

export RUN_DEMO_MODE_SCRIPT="run_demo.bash" && log_debug "Run Demo Mode Script: \"${RUN_DEMO_MODE_SCRIPT}\""
export DEMO_MODE="${DEBUG}"                 && log_debug "Demo Mode: \"${DEMO_MODE}\""

# export PIN_LANGUAGE_VERSIONS="${FALSE}"   && log_debug "Pin Language Versions: \"${PIN_LANGUAGE_VERSIONS}\""
export PIN_LANGUAGE_VERSIONS="${TRUE}"      && log_debug "Pin Language Versions: \"${PIN_LANGUAGE_VERSIONS}\""

NOT_FOUND="-1"

LANGUAGE_NAME=""
LANGUAGE_VERS=""
LANGUAGE_PATH=""


#####################################################################################################################################################################################################
# Define Script functions
#####################################################################################################################################################################################################
function set_language_path() {
    LANGUAGE="$1"
    LANG_PATH="$2"
    MAJ_VER="$3"
    MIN_VER="$4"
    LANG_NAME="$5"
    if [[ "${LANG_NAME}" == "${LANGUAGE}" ]]; then
        LANGUAGE="${LANG_NAME}${MAJ_VER}${MIN_VER}"
    fi
    LANGUAGE_ABS_PATH="${LANG_PATH}${PATH_DELIMITER}${LANGUAGE}"
    log_debug "Initial Language Name: ${LANGUAGE_NAME}"
    [[ "${LANGUAGE_NAME}" == "" ]] && LANGUAGE_NAME="${LANG_NAME}"
    log_debug "Final Language Name: ${LANGUAGE_NAME}"
    log_debug "Initial Language Path: ${LANGUAGE_PATH}"
    [[ "${LANGUAGE_PATH}" == "" ]] && LANGUAGE_PATH="${LANGUAGE_ABS_PATH}"
    log_debug "Final Language Path: ${LANGUAGE_PATH}"
    log_debug "Initial Language Vers: ${LANGUAGE_VERS}"
    [[ "${LANGUAGE_VERS}" == "" ]] && LANGUAGE_VERS="${MAJ_VER}${MIN_VER}"
    log_debug "Final Language Vers: ${LANGUAGE_VERS}"
    eval "export ${LANG_NAME^^}=\"${LANGUAGE_ABS_PATH}\""
}

function contains() {
    local ITEM="$1" && shift
    for ELEMENT in "${@}"; do
        if [[ "${ELEMENT}" == "${ITEM}" ]]; then
            return 0
        fi
    done
    return 1
}

function get_index() {
    local ITEM="$1" && shift
    local INDEX=0
    for ELEMENT in "${@}"; do
        if [[ "${ELEMENT}" == "${ITEM}" ]]; then
            echo "${INDEX}"
            return 0
        fi
        INDEX="$(( INDEX+1 ))"
    done
    echo "${NOT_FOUND}"
    return 1
}


#####################################################################################################################################################################################################
# Define Juniper Canopy config script Environment Constants
#####################################################################################################################################################################################################
export DEV_DIR_NAME="Development"      && log_debug "Dev Dir Name: \"${DEV_DIR_NAME}\""
export PROJECT_NAME="Juniper"          && log_debug "Project Name: \"${PROJECT_NAME}\""
export PROTOTYPE_DIR_NAME="prototypes" && log_debug "Prototype Dir Name: \"${PROTOTYPE_DIR_NAME}\""
export SOURCE_DIR_NAME="src"           && log_debug "Source Dir Name: \"${SOURCE_DIR_NAME}\""
export UTIL_DIR_NAME="util"            && log_debug "Util Dir Name: \"${UTIL_DIR_NAME}\""
export CONFIG_DIR_NAME="conf"          && log_debug "Config Dir Name: \"${CONFIG_DIR_NAME}\""
export CONFIG_FILE_EXT=".conf"         && log_debug "Config File Ext: \"${CONFIG_FILE_EXT}\""


#####################################################################################################################################################################################################
# Parse and Validate Input Parameters
#####################################################################################################################################################################################################
# shellcheck disable=SC2155
export CALLING_SCRIPT_NAME="$( [[ "$1" == "" ]] && echo "${SCRIPT_NAME}" || echo "$1" )" && shift && log_info "Input Param, Calling script name: ${CALLING_SCRIPT_NAME}"

if [[ "$1" == "" ]]; then
    log_info "Input Param, Empty Calling script path: \"${1}\""
    # shellcheck disable=SC2155
    # shellcheck disable=SC2155
    export CALLING_SCRIPT_DIR="$(dirname "$(realpath "$0")")"
    # shellcheck disable=SC2155
    export CALLING_SCRIPT_FILE_NAME="$(basename "$(realpath "$0")")"
    # shellcheck disable=SC2155
    export CALLING_SCRIPT_PROJECT_NAME="$(basename -s "${CONFIG_FILE_EXT}" "$(realpath "$0")")"
    # shellcheck disable=SC2155
    export PROJECT_ROOT_DIR="$( echo "${CALLING_SCRIPT_DIR}" | awk -F "${PROJECT_NAME}" '{print $1 "'${PROJECT_NAME}'";}')"
    # shellcheck disable=SC2155
    export CALLING_SCRIPT_PATH="$( [[ "${PROJECT_NAME,,}" != "${CALLING_SCRIPT_PROJECT_NAME}" ]] && echo "${PROJECT_ROOT_DIR}/${SOURCE_DIR_NAME}/${PROTOTYPE_DIR_NAME}/${CALLING_SCRIPT_PROJECT_NAME}/${UTIL_DIR_NAME}" || echo "${PROJECT_ROOT_DIR}/${UTIL_DIR_NAME}" )"
else
    export CALLING_SCRIPT_PATH="$1" && log_info "Input Param, Calling script path: \"${1}\""
fi
log_info "Calling script path: \"${CALLING_SCRIPT_PATH}\""


#####################################################################################################################################################################################################
# Define File Name Constants
#####################################################################################################################################################################################################
export CASCOR_NAME="juniper_cascor"               && log_debug "Cascor Name: \"${CASCOR_NAME}\""
export MAIN_FILE_NAME="main.py"                   && log_debug "Main File Name: \"${MAIN_FILE_NAME}\""
export COLOR_CONF_FILE="color_display_codes.conf" && log_debug "Color Conf File Name: \"${COLOR_CONF_FILE}\""


#####################################################################################################################################################################################################
# Define Operating System and ENvironment related Constants
#####################################################################################################################################################################################################
export CONDA_ENV_NAME="JuniperPython" && log_debug "Conda Env Name: \"${CONDA_ENV_NAME}\""

CONDA_ACTIVE_ENV_LABEL="active environment" && log_debug "Conda Active Env Label: \"${CONDA_ACTIVE_ENV_LABEL}\""
CONDA_ACTIVE_ENV_LINE=$(conda info | grep "${CONDA_ACTIVE_ENV_LABEL}") && log_debug "Conda Active Env Line: \"${CONDA_ACTIVE_ENV_LINE}\""
export CONDA_ACTIVE_ENV_RAW="${CONDA_ACTIVE_ENV_LINE#*:}" && log_debug "Conda Active Environment Raw: ${CONDA_ACTIVE_ENV_RAW}"
# export CONDA_ACTIVE_ENV="$(echo "${CONDA_ACTIVE_ENV_RAW}" | sed 's/^[[:space:]]*//g')" && log_debug "Conda Active Environment: ${CONDA_ACTIVE_ENV}"
# shellcheck disable=SC2155
export CONDA_ACTIVE_ENV="${CONDA_ACTIVE_ENV_RAW//^[[:space:]]*//}" && log_debug "Conda Active Environment: ${CONDA_ACTIVE_ENV}"

export MACOS="Darwin"                 && log_debug "MacOS: \"${MACOS}\""
export LINUX="Linux"                  && log_debug "Linux: \"${LINUX}\""

export PATH_DELIMITER="/"             && log_debug "Path Delimiter: \"${PATH_DELIMITER}\""
export PROTOTYPE_PROJECT="${FALSE}"   && log_debug "Prototype Project: \"${PROTOTYPE_PROJECT}\""


#####################################################################################################################################################################################################
# Define Programming Language related Constants
#####################################################################################################################################################################################################
declare -a PROJECT_SUPPORTED_LANGUAGE_NAMES=()

export PYTHON_LANGUAGE_NAME="python"         && PROJECT_SUPPORTED_LANGUAGE_NAMES+=("${PYTHON_LANGUAGE_NAME}")     && log_debug "Python Language Name: \"${PYTHON_LANGUAGE_NAME}\""
export JAVASCRIPT_LANGUAGE_NAME="javascript" && PROJECT_SUPPORTED_LANGUAGE_NAMES+=("${JAVASCRIPT_LANGUAGE_NAME}") && log_debug "JavaScript Language Name: \"${JAVASCRIPT_LANGUAGE_NAME}\""
export RUST_LANGUAGE_NAME="rust"             && PROJECT_SUPPORTED_LANGUAGE_NAMES+=("${RUST_LANGUAGE_NAME}")       && log_debug "Rust Language Name: \"${RUST_LANGUAGE_NAME}\""
export JAVA_LANGUAGE_NAME="java"             && PROJECT_SUPPORTED_LANGUAGE_NAMES+=("${JAVA_LANGUAGE_NAME}")       && log_debug "Java Language Name: \"${JAVA_LANGUAGE_NAME}\""
export GO_LANGUAGE_NAME="go"                 && PROJECT_SUPPORTED_LANGUAGE_NAMES+=("${GO_LANGUAGE_NAME}")         && log_debug "Go Language Name: \"${GO_LANGUAGE_NAME}\""
export RUBY_LANGUAGE_NAME="ruby"             && PROJECT_SUPPORTED_LANGUAGE_NAMES+=("${RUBY_LANGUAGE_NAME}")       && log_debug "Ruby Language Name: \"${RUBY_LANGUAGE_NAME}\""
export NODE_LANGUAGE_NAME="node"             && PROJECT_SUPPORTED_LANGUAGE_NAMES+=("${NODE_LANGUAGE_NAME}")       && log_debug "Node Language Name: \"${NODE_LANGUAGE_NAME}\""
export CPP_LANGUAGE_NAME="c++"               && PROJECT_SUPPORTED_LANGUAGE_NAMES+=("${CPP_LANGUAGE_NAME}")        && log_debug "C++ Language Name: \"${CPP_LANGUAGE_NAME}\""
export C_LANGUAGE_NAME="c"                   && PROJECT_SUPPORTED_LANGUAGE_NAMES+=("${C_LANGUAGE_NAME}")          && log_debug "C Language Name: \"${C_LANGUAGE_NAME}\""
export R_LANGUAGE_NAME="R"                   && PROJECT_SUPPORTED_LANGUAGE_NAMES+=("${R_LANGUAGE_NAME}")          && log_debug "R Language Name: \"${R_LANGUAGE_NAME}\""
log_debug "All Project Languages: \"${PROJECT_SUPPORTED_LANGUAGE_NAMES[*]}\""

export LANGUAGE_LOCAL_PATH="miniforge3/envs/${CONDA_ENV_NAME}/bin" && log_debug "Language Local Path: \"${LANGUAGE_LOCAL_PATH}\""

# # NOTE: The Languages list is ordered by Primacy:  The first language listed should be the primary language for this prototype
export PROJECT_LANGUAGE_NAMES=("${PYTHON_LANGUAGE_NAME}" "${JAVASCRIPT_LANGUAGE_NAME}" "${RUST_LANGUAGE_NAME}") && log_debug "Project Language Names: \"${PROJECT_LANGUAGE_NAMES[*]}\""


#####################################################################################################################################################################################################
# Define Programming Language Specific Major and Minor Version Constants
#####################################################################################################################################################################################################
declare -a LANGUAGE_MAJOR_VERSIONS=()
declare -a LANGUAGE_MINOR_VERSIONS=()

export PYTHON_VERSION_MAJOR="3"       && LANGUAGE_MAJOR_VERSIONS+=("${PYTHON_VERSION_MAJOR}")     && log_debug "Python Version Major: ${PYTHON_VERSION_MAJOR}"
export PYTHON_VERSION_MINOR=".13"     && LANGUAGE_MINOR_VERSIONS+=("${PYTHON_VERSION_MINOR}")     && log_debug "Python Version Minor: ${PYTHON_VERSION_MINOR}"
export JAVASCRIPT_VERSION_MAJOR="1"   && LANGUAGE_MAJOR_VERSIONS+=("${JAVASCRIPT_VERSION_MAJOR}") && log_debug "Javascript Version Major: ${JAVASCRIPT_VERSION_MAJOR}"
export JAVASCRIPT_VERSION_MINOR=".17" && LANGUAGE_MINOR_VERSIONS+=("${JAVASCRIPT_VERSION_MINOR}") && log_debug "Javascript Version Minor: ${JAVASCRIPT_VERSION_MINOR}"
export RUST_VERSION_MAJOR="1"         && LANGUAGE_MAJOR_VERSIONS+=("${RUST_VERSION_MAJOR}")       && log_debug "Rust Version Major: ${RUST_VERSION_MAJOR}"
export RUST_VERSION_MINOR=".66"       && LANGUAGE_MINOR_VERSIONS+=("${RUST_VERSION_MINOR}")       && log_debug "Rust Version Minor: ${RUST_VERSION_MINOR}"
export JAVA_VERSION_MAJOR="1"         && LANGUAGE_MAJOR_VERSIONS+=("${JAVA_VERSION_MAJOR}")       && log_debug "Java Version Major: ${JAVA_VERSION_MAJOR}"
export JAVA_VERSION_MINOR=".17"       && LANGUAGE_MINOR_VERSIONS+=("${JAVA_VERSION_MINOR}")       && log_debug "Java Version Minor: ${JAVA_VERSION_MINOR}"
export GO_VERSION_MAJOR="1"           && LANGUAGE_MAJOR_VERSIONS+=("${GO_VERSION_MAJOR}")         && log_debug "Go Version Major: ${GO_VERSION_MAJOR}"
export GO_VERSION_MINOR=".19"         && LANGUAGE_MINOR_VERSIONS+=("${GO_VERSION_MINOR}")         && log_debug "Go Version Minor: ${GO_VERSION_MINOR}"
export RUBY_VERSION_MAJOR="3"         && LANGUAGE_MAJOR_VERSIONS+=("${RUBY_VERSION_MAJOR}")       && log_debug "Ruby Version Major: ${RUBY_VERSION_MAJOR}"
export RUBY_VERSION_MINOR=".1"        && LANGUAGE_MINOR_VERSIONS+=("${RUBY_VERSION_MINOR}")       && log_debug "Ruby Version Minor: ${RUBY_VERSION_MINOR}"
export NODE_VERSION_MAJOR="1"         && LANGUAGE_MAJOR_VERSIONS+=("${NODE_VERSION_MAJOR}")       && log_debug "Node Version Major: ${NODE_VERSION_MAJOR}"
export NODE_VERSION_MINOR=".18"       && LANGUAGE_MINOR_VERSIONS+=("${NODE_VERSION_MINOR}")       && log_debug "Node Version Minor: ${NODE_VERSION_MINOR}"
export CPP_VERSION_MAJOR="23"         && LANGUAGE_MAJOR_VERSIONS+=("${CPP_VERSION_MAJOR}")        && log_debug "C++ Version Major: ${CPP_VERSION_MAJOR}"
export CPP_VERSION_MINOR=".17"        && LANGUAGE_MINOR_VERSIONS+=("${CPP_VERSION_MINOR}")        && log_debug "C++ Version Minor: ${CPP_VERSION_MINOR}"
export C_VERSION_MAJOR="1"            && LANGUAGE_MAJOR_VERSIONS+=("${C_VERSION_MAJOR}")          && log_debug "C Version Major: ${C_VERSION_MAJOR}"
export C_VERSION_MINOR="17"           && LANGUAGE_MINOR_VERSIONS+=("${C_VERSION_MINOR}")          && log_debug "C Version Minor: ${C_VERSION_MINOR}"
export R_VERSION_MAJOR="4"            && LANGUAGE_MAJOR_VERSIONS+=("${R_VERSION_MAJOR}")          && log_debug "R Version Major: ${R_VERSION_MAJOR}"
export R_VERSION_MINOR="1"            && LANGUAGE_MINOR_VERSIONS+=("${R_VERSION_MINOR}")          && log_debug "R Version Minor: ${R_VERSION_MINOR}"
log_debug "Language Major Versions: ${LANGUAGE_MAJOR_VERSIONS[*]}"
log_debug "Language Minor Versions: ${LANGUAGE_MINOR_VERSIONS[*]}"


#####################################################################################################################################################################################################
# Define Programming Language Specific Version Constants
#####################################################################################################################################################################################################
declare -a LANGUAGE_VERSIONS=()

export PYTHON_VERSION="${PYTHON_VERSION_MAJOR}${PYTHON_VERSION_MINOR}"             && LANGUAGE_VERSIONS+=("${PYTHON_VERSION}")     && log_debug "Python Version: ${PYTHON_VERSION}"
export JAVASCRIPT_VERSION="${JAVASCRIPT_VERSION_MAJOR}${JAVASCRIPT_VERSION_MINOR}" && LANGUAGE_VERSIONS+=("${JAVASCRIPT_VERSION}") && log_debug "Javascript Version: ${JAVASCRIPT_VERSION}"
export RUST_VERSION="${RUST_VERSION_MAJOR}${RUST_VERSION_MINOR}"                   && LANGUAGE_VERSIONS+=("${RUST_VERSION}")       && log_debug "Rust Version: ${RUST_VERSION}"
export JAVA_VERSION="${JAVA_VERSION_MAJOR}${JAVA_VERSION_MINOR}"                   && LANGUAGE_VERSIONS+=("${JAVA_VERSION}")       && log_debug "Java Version: ${JAVA_VERSION}"
export GO_VERSION="${GO_VERSION_MAJOR}${GO_VERSION_MINOR}"                         && LANGUAGE_VERSIONS+=("${GO_VERSION}")         && log_debug "Go Version: ${GO_VERSION}"
export RUBY_VERSION="${RUBY_VERSION_MAJOR}${RUBY_VERSION_MINOR}"                   && LANGUAGE_VERSIONS+=("${RUBY_VERSION}")       && log_debug "Ruby Version: ${RUBY_VERSION}"
export NODE_VERSION="${NODE_VERSION_MAJOR}${NODE_VERSION_MINOR}"                   && LANGUAGE_VERSIONS+=("${NODE_VERSION}")       && log_debug "Node Version: ${NODE_VERSION}"
export CPP_VERSION="${CPP_VERSION_MAJOR}${CPP_VERSION_MINOR}"                      && LANGUAGE_VERSIONS+=("${CPP_VERSION}")        && log_debug "C++ Version: ${CPP_VERSION}"
export C_VERSION="${C_VERSION_MAJOR}${C_VERSION_MINOR}"                            && LANGUAGE_VERSIONS+=("${C_VERSION}")          && log_debug "C Version: ${C_VERSION}"
export R_VERSION="${R_VERSION_MAJOR}${R_VERSION_MINOR}"                            && LANGUAGE_VERSIONS+=("${R_VERSION}")          && log_debug "R Version: ${R_VERSION}"
log_debug "Language Versions: ${LANGUAGE_VERSIONS[*]}"


#####################################################################################################################################################################################################
# Define Versioned, Programming Language Versioned Executables
#####################################################################################################################################################################################################
declare -a PROJECT_SUPPORTED_LANGUAGES=()

export PYTHON_LANGUAGE="${PYTHON_LANGUAGE_NAME}${PYTHON_VERSION}"             && PROJECT_SUPPORTED_LANGUAGES+=("${PYTHON_LANGUAGE}")     && log_debug "Python Language: \"${PYTHON_LANGUAGE}\""
export JAVASCRIPT_LANGUAGE="${JAVASCRIPT_LANGUAGE_NAME}${JAVASCRIPT_VERSION}" && PROJECT_SUPPORTED_LANGUAGES+=("${JAVASCRIPT_LANGUAGE}") && log_debug "Javascript Language: \"${JAVASCRIPT_LANGUAGE}\""
export RUST_LANGUAGE="${RUST_LANGUAGE_NAME}${RUST_VERSION}"                   && PROJECT_SUPPORTED_LANGUAGES+=("${RUST_LANGUAGE}")       && log_debug "Rust Language: \"${RUST_LANGUAGE}\""
export JAVA_LANGUAGE="${JAVA_LANGUAGE_NAME}${JAVA_VERSION}"                   && PROJECT_SUPPORTED_LANGUAGES+=("${JAVA_LANGUAGE}")       && log_debug "Java Language: \"${JAVA_LANGUAGE}\""
export GO_LANGUAGE="${GO_LANGUAGE_NAME}${GO_VERSION}"                         && PROJECT_SUPPORTED_LANGUAGES+=("${GO_LANGUAGE}")         && log_debug "Go Language: \"${GO_LANGUAGE}\""
export RUBY_LANGUAGE="${RUBY_LANGUAGE_NAME}${RUBY_VERSION}"                   && PROJECT_SUPPORTED_LANGUAGES+=("${RUBY_LANGUAGE}")       && log_debug "Ruby Language: \"${RUBY_LANGUAGE}\""
export NODE_LANGUAGE="${NODE_LANGUAGE_NAME}${NODE_VERSION}"                   && PROJECT_SUPPORTED_LANGUAGES+=("${NODE_LANGUAGE}")       && log_debug "Node Language: \"${NODE_LANGUAGE}\""
export CPP_LANGUAGE="${CPP_LANGUAGE_NAME}${CPP_VERSION}"                      && PROJECT_SUPPORTED_LANGUAGES+=("${CPP_LANGUAGE}")        && log_debug "C++ Language: \"${CPP_LANGUAGE}\""
export C_LANGUAGE="${C_LANGUAGE_NAME}${C_VERSION}"                            && PROJECT_SUPPORTED_LANGUAGES+=("${C_LANGUAGE}")          && log_debug "C Language: \"${C_LANGUAGE}\""
export R_LANGUAGE="${R_LANGUAGE_NAME}${R_VERSION}"                            && PROJECT_SUPPORTED_LANGUAGES+=("${R_LANGUAGE}")          && log_debug "R Language: \"${R_LANGUAGE}\""
log_debug "Project Supported Languages: ${PROJECT_SUPPORTED_LANGUAGES[*]}"

export PROJECT_LANGUAGES=("${PYTHON_LANGUAGE} ${JAVASCRIPT_LANGUAGE} ${RUST_LANGUAGE} ${NODE_LANGUAGE}")                                 && log_debug "Project Languages: ${PROJECT_LANGUAGES[*]}"


#####################################################################################################################################################################################################
# Identify Current Environment
#####################################################################################################################################################################################################
if [[ "$(uname -s | grep -i "${MACOS}" 2>/dev/null)" == "${MACOS}" ]]; then
    log_debug "Check for MacOS Returned: ${TRUE}, Current OS: $(uname -s)"
    LANGUAGE_PATH_ROOT="/usr/local"
elif [[ "$(uname -s | grep -i "${LINUX}" 2>/dev/null)" == "${LINUX}" ]]; then
    log_debug "Check for Linux Returned: ${TRUE}, Current OS: $(uname -s)"
    LANGUAGE_PATH_ROOT="/opt"
else
    log_error "Error: Unknown OS Type: $(uname -s), Exiting..."
fi


#####################################################################################################################################################################################################
# Define Top Level Constants for Script Environment Directories
#####################################################################################################################################################################################################
# shellcheck disable=SC2155
export SCRIPT_ABS_PATH="${CALLING_SCRIPT_PATH}/${CALLING_SCRIPT_NAME}" && log_debug "Script Abs Path: ${SCRIPT_ABS_PATH}"
# shellcheck disable=SC2155
export SCRIPT_DIR_PATH="${CALLING_SCRIPT_PATH}"                        && log_debug "Script Dir Path: ${SCRIPT_DIR_PATH}"
# shellcheck disable=SC2155
export SCRIPT_DIR_PARENT="$(dirname "${SCRIPT_DIR_PATH}")"             && log_debug "Script Dir Parent: ${SCRIPT_DIR_PARENT}"
# shellcheck disable=SC2155
export SCRIPT_DIR_ROOT="$(dirname "${SCRIPT_DIR_PARENT}")"             && log_info "Script Dir Root: ${SCRIPT_DIR_ROOT}"

# shellcheck disable=SC2155
export PROTOTYPE_DIR_NAME="$(basename "${SCRIPT_DIR_ROOT}")"           && log_info "Prototype Dir Name: ${PROTOTYPE_DIR_NAME}"

# shellcheck disable=SC2155
export PROJECT_DIR_ROOT="$(PROJECT_DIR_ROOT_LOCAL="$(echo "${SCRIPT_DIR_PARENT}" | awk -F "${PROJECT_NAME}" '{print $1;}')" && echo "${PROJECT_DIR_ROOT_LOCAL:0:-1}")" && log_debug "Project Dir Root: ${PROJECT_DIR_ROOT}"
# shellcheck disable=SC2155
export HOME_DIR="$( LOCAL_HOME_DIR="$(echo "${PROJECT_DIR_ROOT}" | awk -F "${DEV_DIR_NAME}" '{print $1;}')" && echo "${LOCAL_HOME_DIR:0:-1}" )"                        && log_debug "Home Dir: ${HOME_DIR}"
# shellcheck disable=SC2155
export SCRIPT_REL_PATH="$( PATH_LOCAL="$(echo "${SCRIPT_DIR_PARENT}" | awk -F "${PROJECT_NAME}" '{print $2;}')" && { [[ "${PATH_LOCAL:0:1}" == "${PATH_DELIMITER}" ]] && echo "${PATH_LOCAL:1}" || echo "${PATH_LOCAL}"; } )" && log_debug "Script Rel Path: ${SCRIPT_REL_PATH}"


#####################################################################################################################################################################################################
# Define Top Level Constants for Script Environment Files
#####################################################################################################################################################################################################
# shellcheck disable=SC2155
export PROJECT_LANGUAGE="$(basename "${PROJECT_DIR_ROOT}")" && log_debug "Project Language: ${PROJECT_LANGUAGE}"
log_debug "CURRENT_DIR_PREFIX=\"\$( echo \"${SCRIPT_REL_PATH}\" | awk -F \"${PATH_DELIMITER}\" '{print \$2 '\"${PATH_DELIMITER}\"' \$3 '\"${PATH_DELIMITER}\"'}' )\""
# shellcheck disable=SC2155
export CURRENT_DIR_PREFIX="$( PATH_LOCAL="$( echo "${SCRIPT_REL_PATH}" | awk -F "${PROTOTYPE_DIR_NAME}" '{print $2;}')" && { [[ "${PATH_LOCAL:0:1}" == "${PATH_DELIMITER}" ]] && echo "${PATH_LOCAL:1}" || echo "${PATH_LOCAL}"; } )" && log_debug "Current Dir Prefix: \"${CURRENT_DIR_PREFIX}\""


#####################################################################################################################################################################################################
# Handle Case where Current Project is the Main Juniper Project, and handle Case where Current Project is a Juniper sub-project in the Prototype Directory
#####################################################################################################################################################################################################
if [[ ! "${CURRENT_DIR_PREFIX}" == "" ]]; then
    log_debug "Current Project is a Juniper sub-project in the Prototype Directory"
    export PROTOTYPE_PROJECT="${TRUE}"                            && log_debug "Prototype Project: ${PROTOTYPE_PROJECT}"
    export PROTOTYPE_NAME="${PROTOTYPE_DIR_NAME}"                 && log_debug "Prototype Name: ${PROTOTYPE_NAME}"
    export PROTOTYPE_ABS_PATH="${SCRIPT_DIR_ROOT}"                && log_debug "Prototype Abs Path: ${PROTOTYPE_ABS_PATH}"
    export CURRENT_PROJECT="${PROTOTYPE_NAME}"                    && log_info "Current Project: ${CURRENT_PROJECT}"
    export PROJECT_PATH="${PROTOTYPE_ABS_PATH}"                   && log_info "Project Path: ${PROJECT_PATH}"
else
    log_debug "Current Project is the Main Project: ${PROJECT_NAME}"
    export PROTOTYPE_ABS_PATH=""                                  && log_debug "Prototype Abs Path: ${PROTOTYPE_ABS_PATH}"
    export PROJECT_ABS_PATH="${PROJECT_DIR_ROOT}/${PROJECT_NAME}" && log_debug "Project Abs Path: ${PROJECT_ABS_PATH}"
    export CURRENT_PROJECT="${PROJECT_NAME}"                      && log_debug "Current Project: ${CURRENT_PROJECT}"
    export PROJECT_PATH="${PROJECT_ABS_PATH}"                     && log_debug "Project Path: ${PROJECT_PATH}"
fi


#####################################################################################################################################################################################################
# Define Constants for the Current Project's Internal Directory paths
#####################################################################################################################################################################################################
# shellcheck disable=SC2155
export PROTOTYPE_PARENT_PATH="$(dirname "${SCRIPT_DIR_PARENT}")"            && log_debug "Prototype Parent Path: ${PROTOTYPE_PARENT_PATH}"
# shellcheck disable=SC2155
export UTIL_DIR="${PROJECT_PATH}${PATH_DELIMITER}${UTIL_DIR_NAME}"     && log_debug "Util Dir: ${UTIL_DIR}"
# shellcheck disable=SC2155
export SOURCE_DIR="${PROJECT_PATH}${PATH_DELIMITER}${SOURCE_DIR_NAME}" && log_debug "Source Dir: ${SOURCE_DIR}"
# shellcheck disable=SC2155
export CONFIG_DIR="${PROJECT_PATH}${PATH_DELIMITER}${CONFIG_DIR_NAME}" && log_debug "Config Dir: ${CONFIG_DIR}"


#####################################################################################################################################################################################################
# Define Constants for the Current Project's Internal File paths
#####################################################################################################################################################################################################
export LAUNCH_DEMO_MODE="${UTIL_DIR}${PATH_DELIMITER}${RUN_DEMO_MODE_SCRIPT}" && log_debug "Launch Demo Mode: ${LAUNCH_DEMO_MODE}"
export COLOR_CONFIG="${CONFIG_DIR}${PATH_DELIMITER}${COLOR_CONF_FILE}"        && log_debug "Color Config: ${COLOR_CONFIG}"
export MAIN_FILE="${SOURCE_DIR}${PATH_DELIMITER}${MAIN_FILE_NAME}"            && log_debug "Main File: ${MAIN_FILE}"


#####################################################################################################################################################################################################
# Source Script Specific and Secondary Config files
#####################################################################################################################################################################################################
log_debug "Sourcing Output Color Config: ${COLOR_CONFIG}"
# shellcheck disable=SC1090
# shellcheck disable=SC2015
[[ "${DEBUG}" == "${FALSE}" ]] && source "${COLOR_CONFIG}" || bash "${COLOR_CONFIG}"


#####################################################################################################################################################################################################
# Define Constants for the Cascor Project's Internal paths
#####################################################################################################################################################################################################
export CASCOR_PARENT_PATH="${PROTOTYPE_PARENT_PATH}"              && log_debug "Cascor Parent Path: ${CASCOR_PARENT_PATH}"
export CASCOR_PATH="${CASCOR_PARENT_PATH}/${CASCOR_NAME}"         && log_debug "Cascor Path: ${CASCOR_PATH}"
export CASCOR_SOURCE_PATH="${CASCOR_PATH}/${SOURCE_DIR_NAME}"     && log_debug "Cascor Source Path: ${CASCOR_SOURCE_PATH}"
export CASCOR_MAIN_FILE="${CASCOR_SOURCE_PATH}/${MAIN_FILE_NAME}" && log_debug "Cascor Main File: ${CASCOR_MAIN_FILE}"


#####################################################################################################################################################################################################
# Define Current Language specific Constants for all Project Languages
# NOTE: The Project Languages list is in order of Primacy
#####################################################################################################################################################################################################
export LANGUAGE_DIR_PATH="${LANGUAGE_PATH_ROOT}/${LANGUAGE_LOCAL_PATH}" && log_debug "Language Dir Path: ${LANGUAGE_DIR_PATH}"

# shellcheck disable=SC2155
# shellcheck disable=SC2155
export CURRENT_LANGUAGES="$( [[ "${PIN_LANGUAGE_VERSIONS}" == "${TRUE}" ]] && echo "${PROJECT_LANGUAGES[@]}" || echo "${PROJECT_LANGUAGE_NAMES[@]}" )" && log_debug "Current Languages: ${CURRENT_LANGUAGES[*]}"
# shellcheck disable=SC2155
export CURRENT_SUPPORTED_LANGUAGES="$( [[ "${PIN_LANGUAGE_VERSIONS}" == "${TRUE}" ]] && echo "${PROJECT_SUPPORTED_LANGUAGES[@]}" || echo "${PROJECT_SUPPORTED_LANGUAGE_NAMES[@]}" )" && log_debug "Current Supported Languages: ${CURRENT_SUPPORTED_LANGUAGES[*]}"

for LANGUAGE in "${CURRENT_LANGUAGES[@]}"; do
    log_debug "Current Language: ${LANGUAGE}"
    CURRENT_INDEX="$(get_index "${LANGUAGE}" "${CURRENT_SUPPORTED_LANGUAGES[@]}")" && log_debug "Current Index: ${CURRENT_INDEX}"
    # Note:  Unlike standard shell scripts, the double paren returns 1 for true and 0 for false
    if [[ "$(( CURRENT_INDEX >= 0 ))" == "1" ]]; then
        log_debug "Language is supported: ${LANGUAGE}"
        log_debug "Language Dir Path: ${LANGUAGE_DIR_PATH}"
        log_debug "Language Major Version: ${LANGUAGE_MAJOR_VERSIONS[${CURRENT_INDEX}]}"
        log_debug "Language Minor Version: ${LANGUAGE_MINOR_VERSIONS[${CURRENT_INDEX}]}"
        log_debug "Language Name: ${PROJECT_SUPPORTED_LANGUAGE_NAMES[${CURRENT_INDEX}]}"
        set_language_path "${LANGUAGE}" "${LANGUAGE_DIR_PATH}" "${LANGUAGE_MAJOR_VERSIONS[${CURRENT_INDEX}]}" "${LANGUAGE_MINOR_VERSIONS[${CURRENT_INDEX}]}" "${PROJECT_SUPPORTED_LANGUAGE_NAMES[${CURRENT_INDEX}]}"
    else
        log_error "Unsupported Project Language: ${LANGUAGE}, Exiting..."
    fi
done
log_info "Language Name: ${LANGUAGE_NAME}"
log_info "Language Vers: ${LANGUAGE_VERS}"
log_info "Language Path: ${LANGUAGE_PATH}"
