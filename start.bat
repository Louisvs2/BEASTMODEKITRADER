@echo off
rem Windows: Doppelklick auf diese Datei startet das Programm.
cd /d "%~dp0"
python whaletracker.py
if errorlevel 1 (
  echo.
  echo Start fehlgeschlagen. Ist Python 3 von python.org installiert?
  pause
)
