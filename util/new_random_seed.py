#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       0.1.4 (0.7.3)
# File Name:     new_random_seed.py
# File Path:     <Project>/<Sub-Project>/<Application>/util/
#
# Date:          2024-04-01
# Last Modified: 2026-01-03
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#    This script generates a new, cryptographically secure random value for use as seed in psuedo random functions
#
#####################################################################################################################################################################################################
# Notes:
#     /Users/pcalnon/opt/anaconda3/envs/pytorch_cuda/bin/python
#     /home/pcalnon/anaconda3/envs/pytorch_cuda/bin/python
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
import os
import secrets
import sys

#####################################################################################################################################################################################################
# Define Constants for python script
#####################################################################################################################################################################################################
_BIT_SIZE = 128

_OS_LINUX = "Linux"
_OS_POSIX = "posix"
_OS_MACOS = "Darwin"
_OS_WINDOWS = "Windows"
_OS_UNKNOWN = "Unknown"

_HOME_MACOS = "/Users/pcalnon"
_HOME_LINUX = "/home/pcalnon"

_CONDA_MACOS = "opt/anaconda3"
_CONDA_LINUX = "anaconda3"

_PYTHON_LOC = "envs/pytorch_cuda/bin/python"


#####################################################################################################################################################################################################
# Define the Main function
#####################################################################################################################################################################################################
if __name__ == "__main__":

    os_name = os.name

    if os_name in [_OS_LINUX, _OS_POSIX]:
        python_cmd = f"{_HOME_LINUX}/{_CONDA_LINUX}/{_PYTHON_LOC}"
    elif os_name == _OS_MACOS:
        python_cmd = f"{_HOME_MACOS}/{_CONDA_MACOS}/{_PYTHON_LOC}"
    elif os_name == _OS_WINDOWS:
        print(f"Error: Why the hell are you running {_OS_WINDOWS}??")
        sys.exit(1)
    else:
        print(f"Error: You are running an {_OS_UNKNOWN} OS.  Shamelessly giving up,")
        sys.exit(2)

print("\nGenerating New Random Seed")
seed = secrets.randbits(_BIT_SIZE)
print(f"{seed}\n")
