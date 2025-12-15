#!/usr/bin/env bash
###########################################################################################################################################
# Script Name:  api_request.bash
# Author Name:  Paul Calnon
# Modify Date:  2025-11-21
# Description:  Perform the specified request against the Close api endpoint and store results
###########################################################################################################################################
# Notes:
#     Critical Dependencies:
#        - bash
#        - curl
#        - realpath
#
#     Warning:
#         Logging an error message causes script to exit with error code
#
#     API Endpoints:
#         Remote: https://api.close.com/buildwithus
#         Local http://127.0.0.1:8050/api/metrics
###########################################################################################################################################


###########################################################################################################################################
# Source Config file for Current Script.  (Assumed to be located in same directory.)
set -eE -o functrace
SCRIPT_PATH="$(realpath "${BASH_SOURCE[0]}")"
CONF_FILE="$(dirname "${SCRIPT_PATH}")/$(basename -s ".bash" "${SCRIPT_PATH}").conf"
source "${CONF_FILE}"; SUCCESS="$?" # If sourcing config file failed, bail out with error message that matches logging format
[[ "${SUCCESS}" != "0" ]] && printf "%b%-21s %-28s %-21s %-11s %s%b\n" "\033[1;31m" "($(date +%F_%T))" "$(basename "${SCRIPT_PATH}"):(${LINENO})" "main:" "[CRITICAL]" "Config load Failed: \"${CONF_FILE}\"" "\033[0m" | tee -a "${LOG_FILE}" 2>&1 && set -e && exit 1
log_debug "Successfully sourced Current Script Config File: ${CONF_FILE}"


###########################################################################################################################################
# Define script functions
function change_file_ext() {
    local file="$1"
    local new_ext="$2"
    [[ "${3}" != "" ]] && local new_suffix="_${3}" || local new_suffix=""
    local new_file_prefix="$(basename "${file}")"
    local new_filename="${new_file_prefix%.*}${new_suffix}${new_ext}"
    local dir_path="$(dirname "${file}")"
    local new_file="${dir_path}/${new_filename}"
    echo "${new_file}"
}

function set_default_files() {       # Initialize Default Values for JSON and Output files
    if [[ "${REQ_TYPE}" == "${REQ_TYPE_GET}" ]]; then
        JSON_FILE="${FILE_ROOT_DEFAULT}_${RSP_FILENAME_SUFFIX}${JSON_EXT}"
    elif [[ "${REQ_TYPE}" == "${REQ_TYPE_POST}" ]]; then
        JSON_FILE="${FILE_ROOT_DEFAULT}_${HASH_FILENAME_SUFFIX}${JSON_EXT}"
    else
        log_error "Invalid request type: ${REQ_TYPE}. This should never happen."
    fi
    OUT_FILE="$(change_file_ext "${JSON_FILE}" "${OUT_EXT}")"  # Generate output file from json filename
    log_debug "Default JSON and Output files set: JSON_FILE=${JSON_FILE}, OUT_FILE=${OUT_FILE}"
    return "${TRUE}"
}

function valid_api_params() {
	[[ $1 != "" ]] || { log_error "Request Type Param is empty."; return "${FALSE}"; }
	[[ $2 != "" ]] || { log_error "JSON File Param is empty."; return "${FALSE}"; }
	[[ $3 != "" ]] && log_debug "Response File Param is Present: ${3}" || log_warning "Response File Param is empty."
    log_debug "Validating Input Parameters: REQ_TYPE=\"${1}\", JSON_FILE=\"${2}\", RESPONSE_FILE=\"${3}\""
	return "${TRUE}"
    }


function get_input_params() {
    log_debug "Parse and validate Input Parameters: \"${*}\""
    valid_api_params "$@"; SUCCESS="$?"
    [[ ${SUCCESS} != "${TRUE}" ]] && { log_error "Invalid Input Params."; return "${SUCCESS}"; }
    REQ_TYPE="$1" && log_debug "Received Request Type Input: ${1}."  # Initializing Request Type
    JSON_FILE="$2" && log_debug "Received JSON data file: ${2}."     # Initializing .json and .out files
    if [[ "${REQ_TYPE}" == "${REQ_TYPE_POST}" ]]; then
        [[ "$3" != "" ]] && RESPONSE_FILE="$3" || RESPONSE_FILE="$(change_file_ext "${JSON_FILE}" "${RSP_EXT}" "${RSP_FILENAME_SUFFIX}")"
        log_debug "Initialized Response File: ${RESPONSE_FILE}."
        OUT_FILE="${RESPONSE_FILE}"
    else
        OUT_FILE="${JSON_FILE}"
    fi
    log_debug "Input Parameters: REQ_TYPE=\"${REQ_TYPE}\", JSON_FILE=\"${JSON_FILE}\", OUT_FILE=\"${OUT_FILE}\", RESPONSE_FILE=\"${RESPONSE_FILE}\""
    return "${TRUE}"
}

function load_hashed_traits_array() {
    [[ "$1" != "" ]] && HASH_FILE="$1" || { log_error "Hash File Param is empty."; return "${FALSE}"; }
    HASHED_TRAITS_LIST="$(cat "${HASH_FILE}")"
    log_debug "Loaded Hashed Traits List: \"${HASHED_TRAITS_LIST}\""
    [[ "${HASHED_TRAITS_LIST}" != "" ]] && return "${TRUE}" || return "${FALSE}"
}

function get_api_req_url() {
    log_debug "Building Request URL: ${REQ_TYPE}"
    REQ_URL="${REQ_PROT}${REQ_HOST}${REQ_PORT}/${REQ_PATH}"
    log_debug "Finished Building API Request URL: ${REQ_URL}"
    return "${TRUE}"
}

function get_curl_header() {
    [[ "${REQ_TYPE}" == "${REQ_TYPE_POST}" ]] && HEADER="${POST_HEADER}" || HEADER="${GET_HEADER}"
    log_debug "${REQ_TYPE} Request Header: ${HEADER}"
    return "${TRUE}"
}

function get_curl_params() {
    REQ_ENDPOINT="-X '${REQ_TYPE}' '${REQ_URL}'" && log_debug "Curl Endpoint: ${REQ_ENDPOINT}"              # Define Common Curl Params
    get_curl_header && [[ $? == "${TRUE}" ]] || { log_error "Request Header missing"; return "${FALSE}"; }  # Bail if unable to get Request Header
    log_debug "Curl API ${REQ_TYPE} Curl Header: \"${HEADER}\""
    [[ "${REQ_TYPE}" == "${REQ_TYPE_POST}" ]] && CURL_DATA="--data '${HASHED_TRAITS_LIST}'" || CURL_DATA=""
    log_debug "Curl API ${REQ_TYPE} Curl Data: ${CURL_DATA}"
    CURL_PARAMS="${VERBOSE} ${REQ_ENDPOINT} ${HEADER} ${CURL_DATA}"                                         # Define and return final curl params
    [[ "${CURL_PARAMS}" == "" ]] && { log_error "Failed to obtain Curl Params"; return "${FALSE}"; }
    log_debug "Compiled String of Curl Params: \"${CURL_PARAMS}\""
    return "${TRUE}"
}

function get_curl_command() {
    [[ "$1" != "" ]] && OUTPUT="$1" && shift || { log_error "Output File Param is empty."; return "${FALSE}"; }
    [[ "$1" != "" ]] && CURL_PARAMS="${*}" || { log_error "Curl Params Param is empty."; return "${FALSE}"; }
    CURL_CMD="curl ${CURL_PARAMS} > ${OUTPUT}"
    log_info "Built Curl Command: ${CURL_CMD}"
    return "${TRUE}"
}


###########################################################################################################################################
# Send Request to API endpoint
log_info "Setting default JSON & Out files based on Request Type"
set_default_files
log_info "Parsing and validating Input Parameters"
get_input_params "${@}"; SUCCESS="$?"
[[ "${SUCCESS}" != "${TRUE}" ]] && log_critical "Invalid Input Parameters. Exiting..."

if [[ "${REQ_TYPE}" == "${REQ_TYPE_POST}" ]]; then  # Handle POST request data
    log_info "Handling POST Request Data Preparation"
    log_debug "Loading the Hashed Traits array from the Hash JSON file: ${JSON_FILE}"
    load_hashed_traits_array "${JSON_FILE}"; SUCCESS="$?"
    [[ "${SUCCESS}" == "${TRUE}" ]] && log_debug "Hash Array loaded:\n\"${HASHED_TRAITS_LIST}\"\n" || log_critical "Failed to load Hash Array from Hash file: ${JSON_FILE}"
fi

log_info "Building API endpoint URL"
get_api_req_url; SUCCESS="$?"
[[ "${SUCCESS}" == "${TRUE}" ]] && log_debug "${REQ_TYPE} Request URL: ${REQ_URL}" || log_critical "Failed to build API endpoint URL"

log_info "Define Curl Params"
get_curl_params; SUCCESS="$?"
[[ "${SUCCESS}" == "${TRUE}" ]] && log_debug "Curl Request Params: ${CURL_PARAMS}" || log_critical "Failed to get Curl Params"

log_info "Build Curl Command"
get_curl_command "${OUT_FILE}" "${CURL_PARAMS}"; SUCCESS="$?"
[[ "${SUCCESS}" == "${TRUE}" ]] && log_debug "Curl Command: ${CURL_CMD}" || log_critical "Failed to build Curl Command: \"${CURL_CMD}\""

log_info "Curl the things" && log_debug "Curl Command: \"${CURL_CMD}\""
eval "${CURL_CMD}; CMD_RET=$?" && SUCCESS="$?"
[[ "${SUCCESS}" == "${TRUE}" ]] && { [[ "${CMD_RET}" == "${TRUE}" ]] && log_info "API Request Succeeded! [Returned ${CMD_RET}]" || log_warn "API Request Failed. \:( [Returned ${CMD_RET}]"; } || log_error "Failed to execute Curl Command: ${CURL_CMD}. [Returned ${SUCCESS}]"

exit "${SUCCESS}"
