#!/usr/bin/env bash

# Per-file pytest output goes to this repo's gitignored tmp/, never the system temp
# directory (Juniper rule, 2026-10-26). The path derives from this script's location.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
OUT_FILE="${REPO_ROOT}/tmp/find_stalling_tests.out"
mkdir -p "${REPO_ROOT}/tmp"

for f in /home/pcalnon/Development/python/Juniper/JuniperCascor/juniper_cascor/src/tests/unit/test_*.py; do
    name=$(basename "$f")
    start=$(date +%s%N)
    timeout 12 /opt/miniforge3/envs/JuniperCanopyCascor/bin/python -m pytest "$f" --no-cov -q --timeout=10 > "${OUT_FILE}" 2>&1
    exit_code=$?
    end=$(date +%s%N)
    elapsed=$(( (end - start) / 1000000 ))
    last_line=$(tail -1 "${OUT_FILE}")
    if [ $exit_code -eq 124 ]; then
        echo "STALL  ${elapsed}ms $name (killed by timeout)"
    else
        echo "OK     ${elapsed}ms $name: $last_line"
    fi
done
