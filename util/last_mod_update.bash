#!/usr/bin/env bash
FILENAME="$1"
if [[ "${FILENAME}" == "" ]]; then
    echo "Error, Input file name not specified. Exiting..."
    exit 1
fi

TRUE="0"
FALSE="1"

# DEBUG="${TRUE}"
DEBUG="${FALSE}"

TARGET_FILE="${FILENAME}"
BASENAME="$(basename ${TARGET_FILE})"
DIRNAME="$(dirname ${TARGET_FILE})"
if [[ "${DIRNAME}" == "" ]]; then
    DIRNAME="."
fi

if [[ ${DEBUG} == "${TRUE}" ]]; then
    BACKUP_FILE="${DIRNAME}/.${BASENAME}-BAK"

    if [[ ! -f "${TARGET_FILE}" && ! -f "${BACKUP_FILE}" ]]; then
        echo "Error: Neither Input File or Backup File are valid, non-empty files.  Exiting"
        exit 2
    elif [[ ! -f "${TARGET_FILE}" && -f "${BACKUP_FILE}" ]]; then
        echo "Warning: Restoring Target File: ${TARGET_FILE} from Backup File: ${BACKUP_FILE}"
        cp -a ${BACKUP_FILE} ${TARGET_FILE}
    else
        echo "Updating Backup File: ${BACKUP_FILE} from Target File: ${TARGET_FILE}"
        cp -a ${TARGET_FILE} ${BACKUP_FILE}
    fi
fi

sed -i "" -e "s/^[[:space:]]*#[[:space:]]*Last[[:space:]]*Modified:[[:space:]]*[0-9.:_-]*[[:space:]]*[A-Z]*[[:space:]]*[#]*$/# Last Modified: $(date "+%F %T %Z")/g" ${TARGET_FILE}
