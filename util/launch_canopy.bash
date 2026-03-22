#!/usr/bin/env bash

APPLICATION_DIR="${HOME}/Development/python/Juniper/juniper-canopy"
SOURCE_DIR="${APPLICATION_DIR}/src"

# export CASCOR_SERVICE_URL="http://127.0.0.1:8200"
# export CASCOR_SERVICE_URL="0.0.0.0:8200"
# export CASCOR_SERVICE_URL="http://0.0.0.0:8200"
#
export CASCOR_SERVICE_URL="http://localhost:8201"
cd "${SOURCE_DIR}"
uvicorn main:app --port 8050
