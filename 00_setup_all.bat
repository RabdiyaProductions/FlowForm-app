@echo off
setlocal

REM ------------------------------------------------------------
REM Determine repository root from this script location.
REM This keeps paths quote-safe even when directories contain spaces.
REM ------------------------------------------------------------
set "ROOT=%~dp0"
set "VENV_DIR=%ROOT%.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"

echo [FlowForm] Setup started in "%ROOT%"

REM ------------------------------------------------------------
REM Create virtual environment if missing.
REM Uses py launcher when available, otherwise falls back to python.
REM ------------------------------------------------------------
if not exist "%VENV_PY%" (
  echo [FlowForm] Creating virtual environment...
  where py >nul 2>&1
  if errorlevel 1 (
    python -m venv "%VENV_DIR%"
  ) else (
    py -3 -m venv "%VENV_DIR%"
  )
)

if not exist "%VENV_PY%" (
  echo [FlowForm] ERROR: virtual environment python not found.
  exit /b 1
)

REM ------------------------------------------------------------
REM Upgrade pip/setuptools/wheel and install all requirements.
REM Always use venv python explicitly (never global interpreter).
REM ------------------------------------------------------------
"%VENV_PY%" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 exit /b 1

"%VENV_PY%" -m pip install -r "%ROOT%requirements.txt"
if errorlevel 1 exit /b 1

REM ------------------------------------------------------------
REM Resolve app port and write ACTIVE_PORTS.json for run scripts/tools.
REM ------------------------------------------------------------
"%VENV_PY%" "%ROOT%boot_port.py" --write-active --print-port > "%TEMP%\flowform_port.txt"
if errorlevel 1 exit /b 1
set /p PORT=<"%TEMP%\flowform_port.txt"
del "%TEMP%\flowform_port.txt" >nul 2>&1

echo [FlowForm] ACTIVE_PORTS.json updated with port %PORT%.
echo [FlowForm] Next step: run "01_run_all.bat"

endlocal
