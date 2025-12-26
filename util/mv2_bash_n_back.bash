#!/usr/bin/env bash

CURRENT_SUFFIX="*conf.bash"

# Move files from *_conf.bash to *.conf
for ORIG in $(ls ${CURRENT_SUFFIX}); do
    echo "${ORIG}"
    TEMP="${ORIG%_*}.${ORIG##*_}"
    echo "${TEMP}"
    NEW="${TEMP%.*}"
    echo "${NEW}"
    mv "${ORIG}" "${NEW}"
done
