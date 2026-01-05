#!/usr/bin/env bash
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       0.1.4 (0.7.3)
# File Name:     color_display_codes.bash
# File Path:     <Project>/<Sub-Project>/<Application>/util/

# Date:          2025-10-31
# Last Modified: 2026-01-03
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#    This config file defines all constants related to Color and Formatting of printing.
#
#####################################################################################################################################################################################################
# Notes:
#
#    Warning: This Config File is Sourced.
#
#    This script is sourced by a similarly named wrapper script: run_all_tests.bash
#    This script uses a .bash extension so vim doesn't complain about Conditionals in a Config File.
#    When Debug Mode is set to True, This config file can run a full display of all colors and formatting options.
#
#####################################################################################################################################################################################################
# References:
#     Color Number: 90, Format: 1   => Grey   [DEBUG]
#     Color Number: 31, Format: 1   => Red    [ERROR]
#     Color Number: 32, Format: 1   => Green  [SUCCESS]
#     Color Number: 93, Format: 1   => Yellow [WARNING]
#     Color Number: 94, Format: 0   => Blue   [INFO]
#     Color Number: 35, Format: 1   => Purple [STATUS]
#     Color Number: 36, Format: 1   => Cyan   []
#     Color Number: 37, Format: 0   => White  []
#
#     DebugMsgColor:   Color Number: 90, (Color: 30, Intensity: 60, Layer: 0), Format: 1  => Grey   [DEBUG]
#     ErrorMsgColor:   Color Number: 31, (Color: 31, Intensity: 0,  Layer: 0), Format: 1  => Red    [ERROR]
#     SuccessMsgColor: Color Number: 32, (Color: 32, Intensity: 0,  Layer: 0), Format: 1  => Green  [SUCCESS]
#     WarningMsgColor: Color Number: 93, (Color: 33, Intensity: 60, Layer: 0), Format: 1  => Yellow [WARNING]
#     InfoMsgColor:    Color Number: 94, (Color: 34, Intensity: 60, Layer: 0), Format: 0  => Blue   [INFO]
#     StatusMsgColor:  Color Number: 35, (Color: 35, Intensity: 0,  Layer: 0), Format: 1  => Purple [STATUS]
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
export PARENT_PATH_PARAM="$(realpath "${BASH_SOURCE[0]}")" && INIT_CONF="../conf/init.conf"
# shellcheck disable=SC2015,SC1090
[[ -f "${INIT_CONF}" ]] && source "${INIT_CONF}" || { echo "Init Config File Not Found. Unable to Continue."; exit 1; }


##############################################################################################################################################################################
# Define Color Component Element Lists
##############################################################################################################################################################################
# shellcheck disable=SC2154
ColorList="${Black} ${Red} ${Green} ${Yellow} ${Blue} ${Purple} ${Cyan} ${White}"
# shellcheck disable=SC2154
IntensityList="${Normal} ${Bright}"
# shellcheck disable=SC2154
LayerList="${Foreground} ${Background}"
# shellcheck disable=SC2154
FormatList="${Light} ${Normal} ${Bold}"


##############################################################################################################################################################################
# In Debug Mode, Test Color and format combinations
##############################################################################################################################################################################
if [[ "${DEBUG}" == "${TRUE}" ]]; then
    for Color in ${ColorList}; do
        for Intensity in ${IntensityList}; do
            for Layer in ${LayerList}; do
                for Format in ${FormatList}; do
                    ColorNumber="$(( Color+Intensity+Layer ))"
                    # shellcheck disable=SC2154
                    DisplayCode="${Prefix}${Format}${Delimiter}${ColorNumber}${Suffix}"
                    log_debug "${Prefix}_${Format}_${Delimiter}_${ColorNumber}_${Suffix}"
                    echo "${Prefix}_${Format}_${Delimiter}_${ColorNumber}_${Suffix}"
                    # shellcheck disable=SC2154
                    log_debug "\n${DisplayCode}[TESTING]${ColorReset} for Color Number: ${ColorNumber} (Color: ${Color}, Intensity: ${Intensity}, Layer: ${Layer}), Format: ${Format}"
                    echo -ne "\n${DisplayCode}[TESTING]${ColorReset} for Color Number: ${ColorNumber} (Color: ${Color}, Intensity: ${Intensity}, Layer: ${Layer}), Format: ${Format}\n"
                done
            done
        done
    done
    echo -ne "\n"
fi

exit $(( TRUE ))
