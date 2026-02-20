#!/usr/bin/env bash

for f in /home/pcalnon/Development/python/Juniper/JuniperCascor/juniper_cascor/src/tests/unit/test_*.py; do
    name=$(basename "$f")
    start=$(date +%s%N)
    timeout 12 /opt/miniforge3/envs/JuniperPython/bin/python -m pytest "$f" --no-cov -q --timeout=10 2>&1 > /tmp/test_out.txt
    exit_code=$?
    end=$(date +%s%N)
    elapsed=$(( (end - start) / 1000000 ))
    last_line=$(tail -1 /tmp/test_out.txt)
    if [ $exit_code -eq 124 ]; then
        echo "STALL  ${elapsed}ms $name (killed by timeout)"
    else
        echo "OK     ${elapsed}ms $name: $last_line"
    fi
done
