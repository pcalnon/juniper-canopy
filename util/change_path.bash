#!/usr/bin/env bash

SLEEPY_TIME=3

OLD_PATH="Juniper\/src\/prototypes"
NEW_PATH="JuniperCanopy"

echo "Bash Version: $(/usr/bin/env bash --version)"
echo "Current Working Dir: $(pwd)"

echo "Changing Path:  Old: \"${OLD_PATH}\", New: \"${NEW_PATH}\""

echo "${SLEEPY_TIME} second Warning"
sleep "${SLEEPY_TIME}"

echo "Filenames:"

for FILENAME in $(grep -rnI "${OLD_PATH}" ./* | awk -F ":" '{print $1;}' | sort -u); do

    # echo -ne "    grep -nI \"${OLD_PATH}\" \"${FILENAME}\"\n"
    # grep -nI "${OLD_PATH}" "${FILENAME}"

    echo -ne "    sed -i \"s/${OLD_PATH}/${NEW_PATH}/g\" ${FILENAME}\n\n"
    sed -i "s/${OLD_PATH}/${NEW_PATH}/g" ${FILENAME}

done
