#!/usr/bin/env bash

export ASCOR_BACKEND_AVAILABLE=0
export RUN_SERVER_TESTS=1
export ENABLE_DISPLAY_TESTS=1
export ENABLE_SLOW_TESTS=1

OS_NAME_LINUX="Linux"
OS_NAME_MACOS="Darwin"

USERNAME="$(whoami)"

# trunk-ignore(shellcheck/SC2015)
# trunk-ignore(shellcheck/SC2312)
[[ "$(uname)" == "${OS_NAME_LINUX}" ]]  && HOME_DIR="/home/${USERNAME}" || { [[ "$(uname)" == "${OS_NAME_MACOS}"  ]] && HOME_DIR="/Users/${USERNAME}" || { echo "Error: Invalid OS Type! Exiting..."  && set -e && exit 1; }; }

JUNIPER_CANOPY_DIR="${HOME_DIR}}/Development/python/JuniperCanopy/juniper_canopy"
cd "${JUNIPER_CANOPY_DIR}"

echo "pytest -v --cov ./src/tests"
pytest -v --cov ./src/tests
