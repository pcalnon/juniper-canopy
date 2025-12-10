#!/usr/bin/env bash
#####################################################################################################################################################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     run_demo.bash
# Author:        Paul Calnon
# Version:       1.0.0
#
# Date:          2025-10-22
# Last Modified: 2025-12-09
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2025 Paul Calnon
#
# Description:
#    Quick-start script to run the Juniper Canopy in demo mode.
#    Automatically activates conda environment and starts the application.
#####################################################################################################################################################################################################
# Notes:
#
# Data Adapter Module
#
# Standardizes data formats between CasCor backend and frontend visualization components.
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

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Banner
echo -e "${BLUE}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║      Juniper Canopy - Demo Mode Quick Start                ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check if conda is available
if ! command -v conda &> /dev/null; then
    echo -e "${RED}✗ Error: conda not found${NC}"
    echo "  Please install Miniconda or Anaconda"
    exit 1
fi

echo -e "${GREEN}✓ Conda found${NC}"

# Check if JuniperPython environment exists
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

# Activate environment
echo -e "${BLUE}→ Activating JuniperPython environment...${NC}"
eval "$(conda shell.bash hook)"
conda activate JuniperPython

# Install/update dependencies if needed
echo -e "${BLUE}→ Checking dependencies...${NC}"
if [ -f "conf/requirements.txt" ]; then
    pip install -q -r conf/requirements.txt
    echo -e "${GREEN}✓ Dependencies up to date${NC}"
fi

# Navigate to src directory
cd src

# Check if demo_mode.py exists
if [ ! -f "demo_mode.py" ]; then
    echo -e "${RED}✗ demo_mode.py not found in src/${NC}"
    echo "  Please ensure all files are in place"
    exit 1
fi

echo -e "${GREEN}✓ All files present${NC}"

# Export demo mode environment variable
export CASCOR_DEMO_MODE=1

# Start the application
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

# Run using uvicorn for proper ASGI server support
# Using exec for proper signal handling
exec "$CONDA_PREFIX/bin/uvicorn" main:app --host 0.0.0.0 --port 8050 --log-level info
