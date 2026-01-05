#!/usr/bin/env bash
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       0.1.4 (0.7.3)
# File Name:     test_demo_endpoints.bash
# File Path:     <Project>/<Sub-Project>/<Application>/util/
#
# Date:          2025-11-16
# Last Modified: 2026-01-02
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#    Manual test script to verify all demo mode endpoints are accessible.
#    Run this while demo mode server is running.
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
# Source script config file
#####################################################################################################################################################################################################
set -o functrace
# shellcheck disable=SC2155
export PARENT_PATH_PARAM="$(realpath "${BASH_SOURCE[0]}")" && INIT_CONF="$(dirname "$(dirname "${PARENT_PATH_PARAM}")")/conf/init.conf"
# shellcheck disable=SC2015,SC1090
[[ -f "${INIT_CONF}" ]] && source "${INIT_CONF}" || { echo "Init Config File Not Found. Unable to Continue."; exit 1; }


#####################################################################################################################################################################################################
# Display Headers
#####################################################################################################################################################################################################
echo "Testing Demo Mode Endpoints..."
echo "==============================="
echo ""


#####################################################################################################################################################################################################
# Define script functions
#####################################################################################################################################################################################################
# Test function
test_endpoint() {
	local name=$1
	local url=$2
	local expected_code=$3
	echo -n "Testing $name... "
	response=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null)
	if [[ "${response}" == "${expected_code}" ]]; then
		echo -e "${GREEN}✓ PASS${NC} (HTTP $response)"
		return 0
	else
		echo -e "${RED}✗ FAIL${NC} (HTTP $response, expected $expected_code)"
		return 1
	fi
}


#####################################################################################################################################################################################################
# Compile Pass and Fail stats
#####################################################################################################################################################################################################
# Counter for results
passed=0
failed=0

# Test health endpoint
if test_endpoint "/health" "http://localhost:8050/health" "200"; then
	((passed++))
else
	((failed++))
fi

# Test API health
if test_endpoint "/api/health" "http://localhost:8050/api/health" "200"; then
	((passed++))
else
	((failed++))
fi

# Test API state
if test_endpoint "/api/state" "http://localhost:8050/api/state" "200"; then
	((passed++))
else
	((failed++))
fi

# Test API metrics
if test_endpoint "/api/metrics" "http://localhost:8050/api/metrics" "200"; then
	((failed++))
else
	((passed++))
fi

# Test API status
if test_endpoint "/api/status" "http://localhost:8050/api/status" "200"; then
	((passed++))
else
	((failed++))
fi

# Test API topology
if test_endpoint "/api/topology" "http://localhost:8050/api/topology" "200"; then
	((passed++))
else
	((failed++))
fi

# Test API docs
if test_endpoint "/docs" "http://localhost:8050/docs" "200"; then
	((passed++))
else
	((failed++))
fi

# Test dashboard redirect
if test_endpoint "/" "http://localhost:8050/" "307"; then
	((passed++))
else
	((failed++))
fi


#####################################################################################################################################################################################################
# Display Footers
#####################################################################################################################################################################################################
echo ""
echo "==============================="
echo -e "Results: ${GREEN}${passed} passed${NC}, ${RED}${failed} failed${NC}"
echo ""

if [[ "${failed}" == "${TRUE}" ]]; then
	echo -e "${GREEN}✓ All endpoints accessible!${NC}"
	exit $(( TRUE ))
else
	echo -e "${RED}✗ Some endpoints failed${NC}"
	exit  $(( FALSE ))
fi
