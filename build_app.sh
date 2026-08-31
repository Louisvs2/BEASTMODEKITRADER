#!/bin/bash
# Builds a fully self-contained WhaleTracker.app - one that carries its own
# Python and Tk, so it runs on a Mac with no Python installed at all.
#
# Run this ON THE MAC:   ./build_app.sh
# Result:                dist/WhaleTracker.app
#
# The plain WhaleTracker.app in this folder already works if a usable Python
# is present; this build is for handing the app to someone else.

set -e
cd "$(dirname "$0")"
. ./find_python.sh

PY="$(find_working_python)"
if [ -z "$PY" ]; then
    echo "No Python with a working tkinter found - cannot build."
    echo "Install Python 3.12 from python.org and try again."
    exit 1
fi
echo "Building with $PY"

"$PY" -m pip install --quiet --upgrade pyinstaller

rm -rf build dist WhaleTracker.spec
"$PY" -m PyInstaller \
    --name WhaleTracker \
    --windowed \
    --noconfirm \
    --clean \
    --osx-bundle-identifier com.whaletracker.app \
    --icon WhaleTracker.app/Contents/Resources/AppIcon.icns \
    --add-data "theme.py:." \
    --add-data "widgets.py:." \
    --add-data "copyplan.py:." \
    --add-data "hyperliquid_source.py:." \
    whaletracker.py

echo ""
echo "Done:  dist/WhaleTracker.app"
echo "Drag it into /Applications and it runs on its own."
