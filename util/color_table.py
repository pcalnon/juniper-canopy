#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       0.1.4 (0.7.3)
# File Name:     color_table.py
# File Path:     <Project>/<Sub-Project>/<Application>/conf/
#
# Date:          2025-10-31
# Last Modified: 2026-01-03
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#
#####################################################################################################################################################################################################
# Notes:
#
#####################################################################################################################################################################################################
# References:
#
#         terse = "-t" in sys.argv[1:] or "--terse" in sys.argv[1:]
#         # for i in range(2 if terse else 10):
#         for i in range(10):             # text attributes
#             for j in range(30, 38):     # foreground colors
#                 for k in range(40, 48): # background colors
#                     # if terse:
#                     #     write("\33[%d;%d;%dm%d;%d;%d\33[m " % (i, j, k, i, j, k))
#                     # else:
#                     write("%d;%d;%d: \33[%d;%d;%dm Hello, World! \33[m \n" % (i, j, k, i, j, k,))
#                 write("\n")
#
#####################################################################################################################################################################################################
# TODO :
#
#####################################################################################################################################################################################################
# COMPLETED:
#
#####################################################################################################################################################################################################
import itertools
import sys

write = sys.stdout.write

write("\n")
for i, j in itertools.product(range(10), range(30, 38)):  # Text attributes and foreground colors
    for k in range(40, 48):  # background colors
        write(
            "%d;%d;%d: \33[%d;%d;%dm Hello, World! \33[m \n"
            % (
                i,
                j,
                k,
                i,
                j,
                k,
            )
        )
    write("\n")
