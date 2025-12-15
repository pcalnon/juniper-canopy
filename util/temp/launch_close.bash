#!/usr/bin/env bash
###########################################################################################################################################
# Script Name:  launch_close.bash
# Author Name:  Paul Calnon
# Modify Date:  2025-11-21
# Description:
#     Call get_request.bash to perform a get request against api endpoint and store JSON results in close_buildwithus_rsp.json file.
#     Call the close_buildwithus.py script to read the close-buildwithus.json file, parse the JSON data, and get blake2b hashes of traits data.
#     Send POST request with traits hash array by calling get_request.bash with a POST request to the API endpoint.
#
###########################################################################################################################################
# Notes:
#     Critical Dependencies:
#         - bash
#         - Python 3.14
#
#     Warning:
#         Logging a "CRITICAL" message causes script to exit with error code
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
source "${CONF_FILE}";  SUCCESS="$?"
[[ "${SUCCESS}" != "0" ]] && printf "%b%-21s %-28s %-21s %-11s %s%b\n" "\033[1;31m" "($(date +%F_%T))" "$(basename "${SCRIPT_PATH}"):(${LINENO})" "main:" "[CRITICAL]" "Config load Failed: \"${CONF_FILE}\"" "\033[0m" | tee -a "${LOG_FILE}" 2>&1 && set -e && exit 1
log_debug "Successfully Sourced Current Script: ${SCRIPT_NAME}, Config File: ${CONF_FILE}, Success: ${SUCCESS}"


###########################################################################################################################################
# Define script functions
function valid_api_params() {
	[[ $1 != "" ]] || { log_warning "Script Param is empty."; return "${FALSE}"; }
	[[ $2 != "" ]] || { log_warning "Request Type Param is empty."; return "${FALSE}"; }
	[[ $3 != "" ]] || { log_warning "Out File Param is empty."; return "${FALSE}"; }
	return "${TRUE}"
}

function get_api_request_cmd() {
	valid_api_params "$@"; SUCCESS="$?"
    [[ ${SUCCESS} != "${TRUE}" ]] && { log_error "Invalid Input Params. Failed to initialize API_REQUEST_CMD"; return "${FALSE}"; }
	SCRIPT="$1" && REQUEST_TYPE="$2" && OUT_FILE="$3"
	API_REQUEST_CMD="${SCRIPT} ${REQUEST_TYPE} ${OUT_FILE}"
    return "${SUCCESS}"
}

function smart_run() {
    log_debug "Running command as Eval: \"${@}\""
    CMD_RET="${TRUE}"
	eval "$@"; SUCCESS="$?"
    log_debug "Eval of API Request completed. API Request Returned: \"${CMD_RET}\", Eval of Command Returned: \"${SUCCESS}\""
    [[ ${CMD_RET} != "${TRUE}" ]] && { log_warning "API Request Failed: ${CMD_RET}"; return "${CMD_RET}"; }
    [[ ${SUCCESS} != "${TRUE}" ]] && log_error "Failed to Eval the API Request Command: $1" || log_info "API Request Succeeded: ${CMD_RET}"
	return "${SUCCESS}"
}

function call_api_request() {
    log_info "Preparing API Request."
    log_debug "Calling API Request Script with Params: \"${*}\""
	get_api_request_cmd "${@}"; SUCCESS="$?"
    [[ ${SUCCESS} != "${TRUE}" ]] && { log_error "call_api_request: Invalid Input Params. Failed to initialize API_REQUEST_CMD"; return "${SUCCESS}"; }
	log_debug "Built API Request Command: API_REQUEST_CMD: \"${API_REQUEST_CMD}\""
	API_REQUEST="${API_REQUEST_CMD}; CMD_RET=$?"
	log_debug "Added additional settings to API Request Command: API_REQUEST: \"${API_REQUEST}\""
	SCRIPT="$1" && REQUEST_TYPE="$2" && log_info "Running ${SCRIPT} with ${REQUEST_TYPE} request"
	smart_run "${API_REQUEST}"; SUCCESS="$?" # Note: This is the return value from the smart_run function not the eval'd command
	log_debug "Results: API Request: CMD_RET: \"${CMD_RET}\", Smart Run Function: SUCCESS: \"${SUCCESS}\""
    log_info "Calling $(basename "${SCRIPT}") with ${REQUEST_TYPE} Request $( [[ "${SUCCESS}" == "${TRUE}" ]] && echo "Succeeded" || echo "Failed" ) [Returned ${SUCCESS}]\n"
	return "${SUCCESS}"
}


###########################################################################################################################################
# Send GET Request to API Endpoint and store JSON response data in file
log_info "Send GET Request to API Endpoint, and store JSON response data in file: ${CLOSE_JSON_FILE}"
log_debug "call_api_request \"${API_REQUEST_BASH_SCRIPT}\" \"${GET_REQUEST_TYPE}\" \"${CLOSE_JSON_FILE}\"; SUCCESS=\"$?\""
call_api_request "${API_REQUEST_BASH_SCRIPT}" "${GET_REQUEST_TYPE}" "${CLOSE_JSON_FILE}"; SUCCESS="$?"
log_debug "Results: GET Command Ret: \"${SUCCESS}\""
[[ ${SUCCESS} != "${TRUE}" ]] && log_warn "GET Request Failed. [Returned ${SUCCESS}]" || log_info "Completed GET Request Successfully. Response in ${CLOSE_JSON_FILE}."

# Parse JSON data and hash traits data into array
log_debug "Using Python version: $(${PYTHON} --version)"
PYTHON_CLOSE_CMD="${PYTHON} ${CLOSE_PYTHON_FILE} ${CLOSE_JSON_FILE} ${CLOSE_HASHED_TRAITS_FILE}"
log_info "Running Python Script: ${PYTHON_CLOSE_CMD}"
eval "${PYTHON_CLOSE_CMD}"; SUCCESS="$?"
[[ "${SUCCESS}" != "${TRUE}" ]] && log_error "Python Script Failed: ${PYTHON_CLOSE_CMD}" || log_debug "Successfully Completed Python Script: \"${PYTHON_CLOSE_CMD}\""

# Post hashed traits array results to API Endpoint
log_info "Send POST request with hashed traits array from file: \"${CLOSE_HASHED_TRAITS_FILE}\""
call_api_request "${API_REQUEST_BASH_SCRIPT}" "${POST_REQUEST_TYPE}" "${CLOSE_HASHED_TRAITS_FILE}" "${CLOSE_HASHED_RESPONSE_FILE}"; SUCCESS="$?"
log_debug "Results: POST Command Ret: \"${SUCCESS}\""
[[ "${SUCCESS}" != "${TRUE}" ]] && log_warn "POST Request Failed. [Returned ${SUCCESS}]" || log_info "Completed POST Request Successfully, Response in \"${CLOSE_HASHED_RESPONSE_FILE}\"."

exit "${SUCCESS}"
