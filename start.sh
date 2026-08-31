#!/bin/bash
cd "$(dirname "$0")" || exit 1
. ./find_python.sh
PY="$(find_working_python)"
if [ -z "$PY" ]; then
    echo "No Python with a working tkinter found. Try: sudo apt install python3-tk"
    exit 1
fi
exec "$PY" whaletracker.py
