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

find_working_python() {
    _can_run() { "$1" -c 'import tkinter; tkinter.Tk().destroy()' >/dev/null 2>&1; }
    for _c in /Library/Frameworks/Python.framework/Versions/3.1{3,2,1,0}/bin/python3 \
              /opt/homebrew/bin/python3.1{3,2,1} /usr/local/bin/python3.1{3,2,1} \
              python3.13 python3.12 python3.11 python3 /usr/bin/python3; do
        if command -v "$_c" >/dev/null 2>&1 && _can_run "$_c"; then echo "$_c"; return 0; fi
    done
    return 1
}

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
