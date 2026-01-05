#!/usr/bin/env bash
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       1.0.0
# File Name:     juniper_canopy-demo.bash
# File Path:     <Project>/<Sub-Project>/juniper_canopy/util/
#
# Date:          2025-10-22
# Last Modified: 2026-01-04
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#    Quick-start script to run the Juniper Canopy in demo mode.  Automatically activates conda environment and starts the application.
#
#####################################################################################################################################################################################################
# Notes:
#     Data Adapter Module
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


#####################################################################################################################################################################################################
# Initialize script by sourcing the init_conf.bash config file
#####################################################################################################################################################################################################
set -o functrace
# shellcheck disable=SC2155
export PARENT_PATH_PARAM="$(realpath "${BASH_SOURCE[0]}")" && INIT_CONF="$(dirname "$(dirname "${PARENT_PATH_PARAM}")")/conf/init.conf"
# shellcheck disable=SC2015,SC1090
[[ -f "${INIT_CONF}" ]] && source "${INIT_CONF}" || { echo "Init Config File Not Found. Unable to Continue."; exit 1; }


#####################################################################################################################################################################################################
# Display Banner
#####################################################################################################################################################################################################
log_trace "Display Banner for Juniper Canopy Demo Mode Quick Start"
echo -e "${BLUE}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║      Juniper Canopy - Demo Mode Quick Start                ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"


#####################################################################################################################################################################################################
# Check if conda is available
#####################################################################################################################################################################################################
log_trace "Check if conda is available"
if ! command -v conda &> /dev/null; then
    echo -e "${RED}✗ Error: conda not found${NC}"
    log_error "${RED}✗ Error: conda not found${NC}"
    echo "  Please install Miniconda or Anaconda"
    log_critical "\tPlease install Miniconda or Anaconda"
fi
log_info "${GREEN}✓ Conda found${NC}"
echo -e "${GREEN}✓ Conda found${NC}"


#####################################################################################################################################################################################################
# Check if JuniperPython environment exists
#####################################################################################################################################################################################################
log_trace "Check if JuniperPython environment exists"
if ! conda env list | grep -q "JuniperPython"; then
    echo -e "${YELLOW}⚠ JuniperPython environment not found${NC}"
    log_warning "\tJuniperPython environment not found"
    echo "  Creating environment from conda_environment.yaml..."
    log_debug "  Creating environment from conda_environment.yaml..."

    # Check if conda_environment.yaml exists
    log_trace "Check if conda_environment.yaml exists"
    if [ -f "conf/conda_environment.yaml" ]; then
        log_trace "Creating environment from conda_environment.yaml..."
        conda env create -f conf/conda_environment.yaml
    else
        echo -e "${RED}✗ conf/conda_environment.yaml not found${NC}"
        log_critical "✗ conf/conda_environment.yaml not found$"
    fi
fi
echo -e "${GREEN}✓ JuniperPython environment available${NC}"
log_trace "✓ JuniperPython environment available"


#####################################################################################################################################################################################################
# Activate environment
#####################################################################################################################################################################################################
echo -e "${BLUE}→ Activating JuniperPython environment...${NC}"
log_trace "Activating JuniperPython environment..."
eval "$(conda shell.bash hook)"
conda activate JuniperPython


#####################################################################################################################################################################################################
# Install/update dependencies if needed
#####################################################################################################################################################################################################
log_trace "Install/update dependencies if needed"
echo -e "${BLUE}→ Checking dependencies...${NC}"
log_trace "Checking dependencies..."
if [ -f "conf/requirements.txt" ]; then
    pip install -q -r conf/requirements.txt
    echo -e "${GREEN}✓ Dependencies up to date${NC}"
    log_trace "✓ Dependencies up to date"
fi


#####################################################################################################################################################################################################
# Check if demo_mode.py exists
#####################################################################################################################################################################################################
log_trace "move to source code directory: ./src"
cd src || log_critical "Failed to change directory to src"
log_trace "Check if demo_mode.py exists"
if [ ! -f "demo_mode.py" ]; then
    echo -e "${RED}✗ demo_mode.py not found in src/${NC}"
    log_error "The demo_mode.py file was not found in src/"
    echo "  Please ensure all files are in place"
    log_critical "\tPlease ensure all files are in place"
    exit $(( FALSE ))
fi
echo -e "${GREEN}✓ All files present${NC}"
log_trace "✓ All files present"


#####################################################################################################################################################################################################
# Export demo mode env var and Start the application
#####################################################################################################################################################################################################
log_trace "Export demo mode env var and Start the application"
export CASCOR_DEMO_MODE="${FALSE}"
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
log_debug "Run using uvicorn for proper ASGI server support & Launch using exec for proper signal handling"
exec "$CONDA_PREFIX/bin/uvicorn" main:app --host 0.0.0.0 --port 8050 --log-level info

exit $(( TRUE ))
