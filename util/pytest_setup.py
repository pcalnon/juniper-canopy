#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       0.1.4 (0.7.3)
# File Name:     pytest_setup.py
# File Path:     <Project>/<Sub-Project>/<Application>/util/
#
# Date:          2024-04-01
# Last Modified: 2025-01-04
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#    Pytest early setup hook - runs before test collection and import rewriting
#
#####################################################################################################################################################################################################
# Notes:
#     This file is loaded by pytest via conftest.py before any test collection begins.
#     It ensures src/ is in sys.path BEFORE pytest rewrites any test files.
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
"""
Pytest early setup hook - runs before test collection and import rewriting

This file is loaded by pytest via conftest.py before any test collection begins.
It ensures src/ is in sys.path BEFORE pytest rewrites any test files.
"""
import sys
from pathlib import Path

#####################################################################################################################################################################################################
# Add src directory to sys.path at the EARLIEST possible moment
#####################################################################################################################################################################################################
project_root = Path(__file__).resolve().parent
src_dir = project_root / "src"

if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))
    print(f"[pytest_setup.py] Added src/ to sys.path: {src_dir}")
