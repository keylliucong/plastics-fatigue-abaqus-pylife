@echo off
setlocal
cd /d "%~dp0.."
if exist ".venv\Scripts\pythonw.exe" (
  start "" ".venv\Scripts\pythonw.exe" "bridge\gui.py"
  goto :eof
)
where pythonw >nul 2>nul
if errorlevel 1 (
  echo pythonw.exe not found. Create the project venv first:
  echo   python -m venv .venv
  echo   .venv\Scripts\pip install pyLife matplotlib
  pause
  exit /b 1
)
start "" pythonw "bridge\gui.py"
endlocal
