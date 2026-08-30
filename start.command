#!/bin/bash
# macOS: Doppelklick auf diese Datei startet das Programm.
cd "$(dirname "$0")"
for PY in python3 python; do
  if command -v "$PY" >/dev/null 2>&1; then exec "$PY" whaletracker.py; fi
done
echo "Python 3 wurde nicht gefunden. Bitte von python.org installieren."
read -r -p "Enter zum Schliessen..."
