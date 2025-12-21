#!/usr/bin/env bash
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Script Name:   juniper_canopy-demo.bash
# Script Path:   <Project>/<Sub-Project>/juniper_canopy/util/
# Conf File:     juniper_canopy-demo.conf
# Conf Path:     <Project>/<Sub-Project>/<Application>/conf/
#
# Author:        Paul Calnon
# Version:       1.0.0
#
# Date:          2025-10-22
# Last Modified: 2025-12-18
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#    Quick-start script to run the Juniper Canopy in demo mode.  Automatically activates conda environment and starts the application.
#
#####################################################################################################################################################################################################
# Notes:
#
#     Data Adapter Module
#
#     Standardizes data formats between CasCor backend and frontend visualization components.
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
set -eE -o functrace


#####################################################################################################################################################################################################
# Source script config file
#####################################################################################################################################################################################################
export PARENT_PATH_PARAM="$(realpath "${BASH_SOURCE[0]}")"
source "../conf/init.conf"; SUCCESS="$?"

# Verify configuration succeeded
[[ "${SUCCESS}" != "0" ]] && { source "../conf/config_fail.conf"; log_error "${SUCCESS}" "${PARENT_PATH_PARAM}" "../conf/init.conf" "${LINENO}" "${LOG_FILE}"; set -e && exit 1; }
log_debug "Successfully Configured Current Script: $(basename "${PARENT_PATH_PARAM}"), by Sourcing the Init Config File: ${INIT_CONF}, Returned: \"${SUCCESS}\""

# export PARENT_SCRIPT_PATH_PARAM="$(realpath "${BASH_SOURCE[0]}")"
# export INIT_CONF="../conf/init.conf"
# source "${INIT_CONF}"; SUCCESS="$?"

# [[ "${SUCCESS}" != "0" ]] && printf "%b%-21s %-28s %-21s %-11s %s%b\n" "\033[1;31m" "($(date +%F_%T))" "$(basename "${PARENT_SCRIPT_PATH_PARAM}"):(${LINENO})" "main:" "[CRITICAL]" "Config load Failed: \"${INIT_CONF}\"" "\033[0m" | tee -a "${LOG_FILE}" 2>&1 && set -e && exit 1
# log_debug "Successfully Sourced Current Script: $(basename "${PARENT_SCRIPT_PATH_PARAM}"), Init Config File: ${INIT_CONF}, Success: ${SUCCESS}"


#####################################################################################################################################################################################################
# Run env info functions
#####################################################################################################################################################################################################
# source "${DATE_FUNCTIONS_SCRIPT}"
log_debug "Run env info functions"
BASE_DIR=$(${GET_PROJECT_SCRIPT} "${BASH_SOURCE}")
CURRENT_OS=$(${GET_OS_SCRIPT})


#####################################################################################################################################################################################################
# Colors for output
#####################################################################################################################################################################################################
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color


#####################################################################################################################################################################################################
# Banner
#####################################################################################################################################################################################################
echo -e "${BLUE}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║      Juniper Canopy - Demo Mode Quick Start                ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"


#####################################################################################################################################################################################################
# Check if conda is available
#####################################################################################################################################################################################################
if ! command -v conda &> /dev/null; then
    echo -e "${RED}✗ Error: conda not found${NC}"
    echo "  Please install Miniconda or Anaconda"
    exit 1
fi

echo -e "${GREEN}✓ Conda found${NC}"


#####################################################################################################################################################################################################
# Check if JuniperPython environment exists
#####################################################################################################################################################################################################
if ! conda env list | grep -q "JuniperPython"; then
    echo -e "${YELLOW}⚠ JuniperPython environment not found${NC}"
    echo "  Creating environment from conda_environment.yaml..."

    # Check if conda_environment.yaml exists
    if [ -f "conf/conda_environment.yaml" ]; then
        conda env create -f conf/conda_environment.yaml
    else
        echo -e "${RED}✗ conf/conda_environment.yaml not found${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}✓ JuniperPython environment available${NC}"


#####################################################################################################################################################################################################
# Activate environment
#####################################################################################################################################################################################################
echo -e "${BLUE}→ Activating JuniperPython environment...${NC}"
eval "$(conda shell.bash hook)"
conda activate JuniperPython


#####################################################################################################################################################################################################
# Install/update dependencies if needed
#####################################################################################################################################################################################################
echo -e "${BLUE}→ Checking dependencies...${NC}"
if [ -f "conf/requirements.txt" ]; then
    pip install -q -r conf/requirements.txt
    echo -e "${GREEN}✓ Dependencies up to date${NC}"
fi


#####################################################################################################################################################################################################
# Check if demo_mode.py exists
#####################################################################################################################################################################################################
cd src

if [ ! -f "demo_mode.py" ]; then
    echo -e "${RED}✗ demo_mode.py not found in src/${NC}"
    echo "  Please ensure all files are in place"
    exit 1
fi

echo -e "${GREEN}✓ All files present${NC}"


#####################################################################################################################################################################################################
# Export demo mode env var and Start the application
#####################################################################################################################################################################################################
export CASCOR_DEMO_MODE=1

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Starting Juniper Canopy in Demo Mode...                   ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}Dashboard URL: ${GREEN}http://localhost:8050/dashboard/${NC}"
echo -e "${YELLOW}API Docs:      ${GREEN}http://localhost:8050/docs${NC}"
echo -e "${YELLOW}Health Check:  ${GREEN}http://localhost:8050/health${NC}"
echo -e "${YELLOW}WebSocket:     ${GREEN}ws://localhost:8050/ws/training${NC}"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop the server${NC}"
echo ""


#####################################################################################################################################################################################################
# Run using uvicorn for proper ASGI server support & Launch using exec for proper signal handling
#####################################################################################################################################################################################################
exec "$CONDA_PREFIX/bin/uvicorn" main:app --host 0.0.0.0 --port 8050 --log-level info
