@echo off
rem Windows: double-click to run BEASTMODE AI TOOL.
cd /d "%~dp0"
for %%P in (python3.12 python3.11 python3 python) do (
  %%P -c "import tkinter" >nul 2>&1 && (
    %%P beastmode.py
    goto :done
  )
)
echo.
echo No Python with tkinter found.
echo Install Python from python.org and keep "tcl/tk and IDLE" ticked.
pause
:done
