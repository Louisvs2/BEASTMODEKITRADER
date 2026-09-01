#!/bin/bash
# Double-click this once if BEASTMODE AI TOOL reports
#   [SSL: CERTIFICATE_VERIFY_FAILED] unable to get local issuer certificate
#
# Python installed from python.org does not register the system root
# certificates, so it cannot verify any HTTPS connection. This script runs
# the official "Install Certificates.command" that ships inside the Python
# installation, and falls back to installing the certifi bundle.
#
# It never disables certificate verification - that would make every
# connection forgeable.

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

tls_ok() {
    "$1" - <<'PYCHECK' >/dev/null 2>&1
import urllib.request
urllib.request.urlopen("https://api.hyperliquid.xyz/info", data=b'{"type":"allMids"}',
                       timeout=20)
PYCHECK
}

echo ""
echo "BEASTMODE AI TOOL - certificate repair"
echo "=================================="

PY="$(find_working_python)"
if [ -z "$PY" ]; then
    echo "No usable Python found. Run check_mac.command first."
    read -r -p "Press Enter to close..."
    exit 1
fi
echo "Python: $PY"

if tls_ok "$PY"; then
    echo ""
    echo "Certificates already work - nothing to repair."
    echo "If BEASTMODE AI TOOL still cannot connect, the problem is elsewhere."
    read -r -p "Press Enter to close..."
    exit 0
fi

echo "HTTPS currently fails. Repairing ..."
echo ""

# 1) the official installer that ships with python.org builds
RAN_OFFICIAL=0
for installer in /Applications/Python\ 3.*/Install\ Certificates.command; do
    if [ -f "$installer" ]; then
        echo "Running: $installer"
        bash "$installer" && RAN_OFFICIAL=1
        echo ""
    fi
done
[ $RAN_OFFICIAL -eq 1 ] || echo "No 'Install Certificates.command' found in /Applications."

if tls_ok "$PY"; then
    echo "Fixed. HTTPS works now - start BEASTMODE AI TOOL.app."
    read -r -p "Press Enter to close..."
    exit 0
fi

# 2) certifi as a fallback; pip carries its own certificates, so it still
#    works while the ssl module has none
echo "Installing the certifi certificate bundle ..."
# the third form is for Homebrew and other PEP 668 "externally managed"
# installs, which refuse the first two
"$PY" -m pip install --upgrade certifi 2>/dev/null || \
    "$PY" -m pip install --user --upgrade certifi 2>/dev/null || \
    "$PY" -m pip install --user --break-system-packages --upgrade certifi
echo ""

if tls_ok "$PY"; then
    echo "Fixed. HTTPS works now - start BEASTMODE AI TOOL.app."
else
    echo "Still failing."
    echo ""
    echo "Most likely a network filter or VPN is intercepting HTTPS."
    echo "Try again on a different network, or report this output."
fi
echo ""
read -r -p "Press Enter to close..."
