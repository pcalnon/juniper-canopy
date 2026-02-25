#####################################################################################################################################################################################################
# Project:       Juniper
# Application:   juniper-canopy
# Purpose:       Real-time CasCor Neural Network Web Dashboard
#
# Author:        Paul Calnon
# Version:       <X.Y.Z  Major, Minor, Point Version for juniper-canopy>
# Config Name:   conda_environment_ci.yaml
# Config Path:   Juniper/juniper-canopy/conf/
#
# Date:          2025-12-06
# Last Modified: <YYYY-MM-dd for current date>
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-<YYYY for current year> Paul Calnon
#
# Description:
#     This config file contains an automatically generated list of environment dependencies managed by conda / mamba for the juniper-canopy application.
#
#####################################################################################################################################################################################################
# Notes:
#     created-by: conda <YYYY.MM.dd for current date>
#     platform: linux-64
#     python: <Python Version>
#
#####################################################################################################################################################################################################
# References:
#
#     This file may be used to create the Juniper Project, juniper-canopy Application environment
#         with conda and miniforge3 using:
#     create env: conda create --name [env] --file [filename]
#         e.g., $ conda create --name JuniperPython --file juniper-canopy/conf/conda_environment_ci.yaml
#     Update env: conda env update --name [env] --file [filename]
#         e.g., $ conda env update --name JuniperPython --file juniper-canopy/conf/conda_environment_ci.yaml
#     Generate deps: conda list --explicit > [filename]
#         e.g., $ conda list -e >> juniper-canopy/conf/conda_environment_ci.yaml
#
#####################################################################################################################################################################################################
# TODO :
#
#####################################################################################################################################################################################################
# COMPLETED:
#
#####################################################################################################################################################################################################
name: juniper-canopy
channels:
  - conda-forge
  - pytorch
  - nvidia
  - plotly
  - RMG
  - numba
  - jasonb857
  - ehmoussi
  - konstantin-orangeqs
dependencies:
