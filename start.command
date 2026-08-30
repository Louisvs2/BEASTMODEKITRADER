#!/bin/bash
# macOS: Doppelklick auf diese Datei startet das Programm.
cd "$(dirname "$0")"

PY=""
for CANDIDATE in python3 python3.12 python3.11 python; do
  if command -v "$CANDIDATE" >/dev/null 2>&1; then PY="$CANDIDATE"; break; fi
done

if [ -z "$PY" ]; then
  echo ""
  echo "Python 3 wurde nicht gefunden."
  echo "Bitte von https://www.python.org/downloads/ installieren und erneut starten."
  echo ""
  read -r -p "Enter zum Schliessen..."
  exit 1
fi

"$PY" whaletracker.py
CODE=$?
if [ $CODE -ne 0 ]; then
  echo ""
  echo "Das Programm wurde mit Fehler $CODE beendet (siehe Meldung oben)."
  read -r -p "Enter zum Schliessen..."
fi
exit $CODE
