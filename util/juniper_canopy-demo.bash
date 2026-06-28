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
# Resolve the live JuniperCanopy* conda environment (versioned-env convention)
#####################################################################################################################################################################################################
# The canopy conda env name is VERSIONED (see AGENTS.md): every rebuild increments
# the numeric suffix (JuniperCanopy1, JuniperCanopy2, ...) and renames the previous
# env to "*-DEPRECATED".  Hard-coding a name -- whether the unversioned "JuniperCanopy"
# (which does not exist) or a fixed "JuniperCanopy1" -- silently re-drifts on the next
# rebuild.  resolve_canopy_env discovers the single live, non-deprecated env and stores
# it in CANOPY_ENV_NAME, erroring clearly when zero or more than one candidate is found.
resolve_canopy_env() {
    local line name
    local -a candidates=()
    while IFS= read -r line; do
        # Skip the header/legend comment lines emitted by `conda env list`.
        [[ -z "${line}" || "${line}" == \#* ]] && continue
        # The env name is the first whitespace-delimited field (the active env is
        # flagged with a separate-column '*', so the first field is still the name).
        name="${line%%[[:space:]]*}"
        [[ "${name}" == JuniperCanopy* ]] || continue
        [[ "${name}" == *-DEPRECATED ]] && continue
        candidates+=("${name}")
    done < <(conda env list)

    if [[ "${#candidates[@]}" -eq 0 ]]; then
        echo -e "${RED}✗ No live (non-deprecated) JuniperCanopy* conda environment found${NC}"
        log_error "No live (non-deprecated) JuniperCanopy* conda environment found"
        echo "  The env name is versioned; discover or (re)build it, e.g.:"
        echo "      conda env list | grep JuniperCanopy"
        return 1
    fi
    if [[ "${#candidates[@]}" -gt 1 ]]; then
        echo -e "${RED}✗ Multiple live JuniperCanopy* environments: ${candidates[*]}${NC}"
        log_error "Ambiguous JuniperCanopy* environments: ${candidates[*]}"
        echo "  Exactly one non-deprecated env is expected; rename stale ones '*-DEPRECATED'."
        return 1
    fi
    CANOPY_ENV_NAME="${candidates[0]}"
    return 0
}


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
# Check if a live JuniperCanopy* environment exists
#####################################################################################################################################################################################################
log_trace "Check if a live JuniperCanopy* environment exists"
# Use a captured-output emptiness test rather than `grep -q`: when the invoking shell
# has `set -o pipefail`, `grep -q`'s early exit SIGPIPEs the upstream stage and flips
# the whole pipeline non-zero, which would spuriously trigger env (re)creation.
if [[ -z "$(conda env list | awk '{print $1}' | grep -E '^JuniperCanopy' | grep -v -- '-DEPRECATED')" ]]; then
    echo -e "${YELLOW}⚠ No live JuniperCanopy* environment found${NC}"
    log_warning "\tNo live JuniperCanopy* environment found"
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
echo -e "${GREEN}✓ JuniperCanopy* environment available${NC}"
log_trace "✓ JuniperCanopy* environment available"


#####################################################################################################################################################################################################
# Activate environment (resolve the live versioned env dynamically)
#####################################################################################################################################################################################################
resolve_canopy_env || exit 1
echo -e "${BLUE}→ Activating ${CANOPY_ENV_NAME} environment...${NC}"
log_trace "Activating ${CANOPY_ENV_NAME} environment..."
eval "$(conda shell.bash hook)"
conda activate "${CANOPY_ENV_NAME}"


#####################################################################################################################################################################################################
# Install/update dependencies if needed
#####################################################################################################################################################################################################
log_trace "Install/update dependencies if needed"
echo -e "${BLUE}→ Checking dependencies...${NC}"
log_trace "Checking dependencies..."
if [ -f "conf/requirements.txt" ]; then
    if ! pip install -q -r conf/requirements.txt; then
        echo -e "${RED}✗ Failed to install dependencies${NC}"
        log_error "pip install failed for conf/requirements.txt"
        echo "  Please check the errors above and ensure all packages are available."
        log_critical "Dependency installation failed. Cannot continue."
        exit 1
    fi
    echo -e "${GREEN}✓ Dependencies up to date${NC}"
    log_trace "✓ Dependencies up to date"
else
    echo -e "${RED}✗ conf/requirements.txt not found${NC}"
    log_error "conf/requirements.txt not found"
    exit 1
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
# Ensure JuniperData service is available
#####################################################################################################################################################################################################
export JUNIPER_DATA_URL="${JUNIPER_DATA_URL:-http://localhost:8100}"
JUNIPER_DATA_HEALTH="${JUNIPER_DATA_URL}/v1/health/ready"
log_info "Checking JuniperData service at ${JUNIPER_DATA_URL}"

JUNIPER_DATA_RUNNING=false
if curl -sf "${JUNIPER_DATA_HEALTH}" > /dev/null 2>&1; then
    JUNIPER_DATA_RUNNING=true
    echo -e "${GREEN}✓ JuniperData service is running${NC}"
    log_info "JuniperData service is already running at ${JUNIPER_DATA_URL}"
else
    echo -e "${YELLOW}⚠ JuniperData service not running, attempting to start...${NC}"
    log_info "JuniperData service not running, attempting auto-start"
    if python -m juniper_data --port 8100 > /dev/null 2>&1 &
    then
        JUNIPER_DATA_PID=$!
        log_info "JuniperData service started with PID: ${JUNIPER_DATA_PID}"
        RETRIES=0
        MAX_RETRIES=15
        while [ $RETRIES -lt $MAX_RETRIES ]; do
            if curl -sf "${JUNIPER_DATA_HEALTH}" > /dev/null 2>&1; then
                JUNIPER_DATA_RUNNING=true
                echo -e "${GREEN}✓ JuniperData service started successfully${NC}"
                log_info "JuniperData service ready after ${RETRIES} retries"
                break
            fi
            RETRIES=$((RETRIES + 1))
            sleep 1
        done
        if [ "${JUNIPER_DATA_RUNNING}" != "true" ]; then
            echo -e "${RED}✗ JuniperData service failed to start within ${MAX_RETRIES}s${NC}"
            log_error "JuniperData service failed to start"
            kill "${JUNIPER_DATA_PID}" 2>/dev/null
        fi
    else
        echo -e "${RED}✗ Failed to launch JuniperData (is juniper-data installed?)${NC}"
        log_error "Failed to launch JuniperData service"
    fi
fi

if [ "${JUNIPER_DATA_RUNNING}" != "true" ]; then
    echo -e "${RED}✗ JuniperData service is required but not available${NC}"
    echo -e "${YELLOW}  Install: pip install juniper-data${NC}"
    echo -e "${YELLOW}  Or set JUNIPER_DATA_URL to a running instance${NC}"
    log_error "JuniperData service not available, cannot continue"
    exit 1
fi


#####################################################################################################################################################################################################
# Export demo mode env var and Start the application
#####################################################################################################################################################################################################
log_trace "Export demo mode env var and Start the application"
export JUNIPER_CANOPY_DEMO_MODE="1"
export JUNIPER_DATA_URL="${JUNIPER_DATA_URL:-http://localhost:8100}"
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
if [ -n "${JUNIPER_DATA_PID:-}" ]; then
    trap 'kill "${JUNIPER_DATA_PID}" 2>/dev/null' EXIT
fi
exec "$CONDA_PREFIX/bin/uvicorn" main:app --host 0.0.0.0 --port 8050 --log-level info

exit $(( TRUE ))
