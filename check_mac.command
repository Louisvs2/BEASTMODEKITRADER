#!/bin/bash
# Double-click this to see which Python interpreters this Mac has and which
# of them can actually open a window. Handy when the app refuses to start.
cd "$(dirname "$0")" || exit 1
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

echo ""
echo "Whale Tracker - environment check"
echo "================================="
echo "macOS : $(sw_vers -productVersion 2>/dev/null || uname -sr)"
echo "Folder: $(pwd)"
echo ""
echo "Program files:"
for f in whaletracker.py theme.py widgets.py copyplan.py hyperliquid_source.py; do
    if [ -f "$f" ]; then echo "  ok      $f"; else echo "  MISSING $f"; fi
done
echo ""
echo "Python interpreters:"
for v in 3.14 3.13 3.12 3.11 3.10 3.9; do
    for p in "/Library/Frameworks/Python.framework/Versions/$v/bin/python3" \
             "/opt/homebrew/bin/python$v" "/usr/local/bin/python$v" "python$v"; do
        command -v "$p" >/dev/null 2>&1 || continue
        where="$(command -v "$p")"
        if "$p" -c 'import tkinter; tkinter.Tk().destroy()' >/dev/null 2>&1; then
            echo "  WORKS   $where"
        else
            reason="$("$p" -c 'import tkinter' 2>&1 | tail -1)"
            echo "  broken  $where"
            [ -n "$reason" ] && echo "            $reason"
        fi
    done
done
for p in /usr/bin/python3 python3; do
    command -v "$p" >/dev/null 2>&1 || continue
    where="$(command -v "$p")"
    if "$p" -c 'import tkinter; tkinter.Tk().destroy()' >/dev/null 2>&1; then
        echo "  WORKS   $where"
    else
        echo "  broken  $where"
        "$p" -c 'import tkinter' 2>&1 | tail -1 | sed 's/^/            /'
    fi
done
echo ""
PICKED="$(find_working_python)"
if [ -n "$PICKED" ]; then
    echo "=> Whale Tracker will use: $PICKED"
    printf "   HTTPS: "
    if "$PICKED" -c 'import urllib.request; urllib.request.urlopen("https://api.hyperliquid.xyz/info", data=b"{\"type\":\"allMids\"}", timeout=20)' >/dev/null 2>&1; then
        echo "ok"
    else
        echo "BROKEN - double-click fix_certificates.command"
    fi
else
    echo "=> No usable Python. Install Python 3.12 from python.org,"
    echo "   or update macOS to 15.7 or newer."
fi
echo ""
read -r -p "Press Enter to close..."
