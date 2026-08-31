#!/bin/bash
# macOS: double-click to run Whale Tracker from the Terminal.
# For the nicer route, double-click WhaleTracker.app instead.
cd "$(dirname "$0")" || exit 1
. ./find_python.sh

PY="$(find_working_python)"
if [ -z "$PY" ]; then
    cat <<'MSG'

No usable Python found on this Mac.

Every Python here either has no tkinter, or ships a Tk that demands a newer
macOS - that is the "macOS 15 (1507) or later required" abort.

Two ways to fix it:

  1. Update macOS      System Settings > General > Software Update
  2. Install Python 3.12 from python.org - its Tk runs on older macOS:
     https://www.python.org/downloads/release/python-3128/

MSG
    read -r -p "Press Enter to close..."
    exit 1
fi

echo "Using $PY"
"$PY" whaletracker.py
CODE=$?
if [ $CODE -ne 0 ]; then
    echo ""
    echo "Whale Tracker exited with error $CODE (see the message above)."
    read -r -p "Press Enter to close..."
fi
exit $CODE
