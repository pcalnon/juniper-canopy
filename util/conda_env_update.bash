#!/usr/bin/env bash
########################################################################################################################
########################################################################################################################

########################################################################################################################
# Define constants
CONDA_ENV_NAME="JuniperCanopy"

CONDA_PKG_FILEDIR="conf"
CONDA_PKG_FILENAME="conda_environment.yaml"
CONDA_PKG_FILE="${CONDA_PKG_FILEDIR}/${CONDA_PKG_FILENAME}"


########################################################################################################################
# conda env update --name JuniperCanopy --file  conf/conda_environment.yaml
echo "conda env update --name \"${CONDA_ENV_NAME}\" --file \"${CONDA_PKG_FILE}\""
conda env update --name "${CONDA_ENV_NAME}" --file "${CONDA_PKG_FILE}"
