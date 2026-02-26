@echo off
setlocal

REM FlowForm setup: create virtual environment and install dependencies.
set "ROOT=%~dp0"
set "VENV_DIR=%ROOT%.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"

if not exist "%VENV_PY%" (
  echo [FlowForm] Creating virtual environment...
  python -m venv "%VENV_DIR%"
)

if not exist "%VENV_PY%" (
  echo [FlowForm] ERROR: could not create .venv
  pause
  exit /b 1
)

echo [FlowForm] Installing requirements...
"%VENV_PY%" -m pip install --upgrade pip
if errorlevel 1 (
  echo [FlowForm] ERROR: pip upgrade failed
  pause
  exit /b 1
)

"%VENV_PY%" -m pip install -r "%ROOT%requirements.txt"
if errorlevel 1 (
  echo [FlowForm] ERROR: requirements install failed
  pause
  exit /b 1
)

echo [FlowForm] Setup complete.
pause
endlocal
