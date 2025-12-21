#!/usr/bin/env python

import itertools
import sys

write = sys.stdout.write


# terse = "-t" in sys.argv[1:] or "--terse" in sys.argv[1:]
# # for i in range(2 if terse else 10):
# for i in range(10):             # text attributes
#     for j in range(30, 38):     # foreground colors
#         for k in range(40, 48): # background colors
#             # if terse:
#             #     write("\33[%d;%d;%dm%d;%d;%d\33[m " % (i, j, k, i, j, k))
#             # else:
#             write("%d;%d;%d: \33[%d;%d;%dm Hello, World! \33[m \n" % (i, j, k, i, j, k,))
#         write("\n")

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
