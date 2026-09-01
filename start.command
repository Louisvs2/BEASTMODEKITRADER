#!/bin/bash
# macOS: double-click to run Whale Tracker from a Terminal window.
# For the nicer route, double-click WhaleTracker.app instead.
cd "$(dirname "$0")" || exit 1

# A Tk built for a newer macOS aborts the process on import, so each candidate
# has to be probed from outside rather than caught with try/except.
find_working_python() {
    _can_run() { "$1" -c 'import tkinter; tkinter.Tk().destroy()' >/dev/null 2>&1; }
    _candidates=""
    for _v in 3.13 3.12 3.11 3.10 3.9; do
        _candidates="$_candidates /Library/Frameworks/Python.framework/Versions/$_v/bin/python3"
        _candidates="$_candidates /opt/homebrew/bin/python$_v /usr/local/bin/python$_v python$_v"
    done
    _candidates="$_candidates /opt/homebrew/bin/python3 /usr/local/bin/python3 python3 /usr/bin/python3"
    for _c in $_candidates; do
        if command -v "$_c" >/dev/null 2>&1 && _can_run "$_c"; then echo "$_c"; return 0; fi
    done
    return 1
}

PY="$(find_working_python)"
if [ -z "$PY" ]; then
    cat <<'MSG'

No usable Python found on this Mac.

Every Python here either has no tkinter, or ships a Tk that demands a newer
macOS - the "macOS 15 (1507) or later required" abort.

  1. Install Python 3.12 from python.org (its Tk runs on older macOS):
     https://www.python.org/downloads/release/python-3128/
  2. Or update macOS: System Settings > General > Software Update

Run ./check_mac.command to see exactly which interpreters were tried.

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
