#!/bin/bash
#
# Builds the sellable version of BEASTMODE AI TOOL.
#
#   ./build_release.sh
#
# Produces in dist/ :
#   BEASTMODE AI TOOL.app   - carries its own Python and Tk, so a buyer needs
#                             nothing installed
#   BEASTMODE AI TOOL.dmg   - the disk image to put on your website
#
# MUST BE RUN ON A MAC. A macOS app bundle can only be produced on macOS.
#
# Signing (optional but strongly recommended for a website download):
#   export CODESIGN_ID="Developer ID Application: Your Name (TEAMID)"
#   export NOTARY_PROFILE="beastmode"     # created once with:
#       xcrun notarytool store-credentials beastmode \
#            --apple-id you@example.com --team-id TEAMID --password APP-PASSWORD
# With those set the app is signed, notarised and stapled, and buyers can just
# double-click. Without them the build still works, but macOS will warn buyers
# that the app is from an unidentified developer - see the tutorial PDF.

set -e
cd "$(dirname "$0")"

APP="BEASTMODE AI TOOL"
DMG="dist/$APP.dmg"

if [ "$(uname)" != "Darwin" ]; then
    echo "This script builds a macOS app and must run on a Mac."
    exit 1
fi

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
    echo "Install Python 3.12 from python.org, then run this again."
    exit 1
fi
echo "==> Building with $PY"

"$PY" -m pip install --quiet --upgrade pyinstaller 2>/dev/null || \
    "$PY" -m pip install --quiet --user --upgrade pyinstaller

echo "==> Cleaning previous build"
rm -rf build dist "$APP.spec"

echo "==> Bundling"
"$PY" -m PyInstaller \
    --name "$APP" \
    --windowed \
    --noconfirm \
    --clean \
    --osx-bundle-identifier com.beastmode.aitool \
    --icon "BEASTMODE AI TOOL.app/Contents/Resources/AppIcon.icns" \
    --add-data "theme.py:." \
    --add-data "widgets.py:." \
    --add-data "copyplan.py:." \
    --add-data "hyperliquid_source.py:." \
    beastmode.py

[ -d "dist/$APP.app" ] || { echo "Build produced no app bundle."; exit 1; }

if [ -n "$CODESIGN_ID" ]; then
    echo "==> Signing as: $CODESIGN_ID"
    codesign --force --deep --options runtime --timestamp \
             --sign "$CODESIGN_ID" "dist/$APP.app"
    codesign --verify --deep --strict --verbose=2 "dist/$APP.app"
else
    echo "==> CODESIGN_ID not set - shipping UNSIGNED."
    echo "    Buyers will have to allow the app in System Settings on first run."
fi

echo "==> Building the disk image"
rm -f "$DMG"
STAGE="$(mktemp -d)"
cp -R "dist/$APP.app" "$STAGE/"
ln -s /Applications "$STAGE/Applications"     # drag-to-install
hdiutil create -volname "$APP" -srcfolder "$STAGE" -ov -format UDZO "$DMG" >/dev/null
rm -rf "$STAGE"

if [ -n "$CODESIGN_ID" ] && [ -n "$NOTARY_PROFILE" ]; then
    echo "==> Notarising (this takes a few minutes)"
    xcrun notarytool submit "$DMG" --keychain-profile "$NOTARY_PROFILE" --wait
    xcrun stapler staple "$DMG"
    xcrun stapler staple "dist/$APP.app"
    echo "==> Gatekeeper assessment:"
    spctl --assess --type execute --verbose=2 "dist/$APP.app" || true
fi

echo ""
echo "Done."
echo "  App: dist/$APP.app"
echo "  DMG: $DMG    <- upload this to your website"
echo ""
echo "Test it before selling: open the DMG, drag the app to Applications,"
echo "then launch it from Applications on a Mac WITHOUT Python installed."
