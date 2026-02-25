@echo off
setlocal

REM ------------------------------------------------------------
REM Determine repository root and venv interpreter explicitly.
REM ------------------------------------------------------------
set "ROOT=%~dp0"
set "VENV_DIR=%ROOT%.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"

if not exist "%VENV_PY%" (
  echo [FlowForm] ERROR: venv missing. Run 00_setup_all.bat first.
  exit /b 1
)

REM ------------------------------------------------------------
REM Resolve preferred/available port and record ACTIVE_PORTS.json.
REM ------------------------------------------------------------
"%VENV_PY%" "%ROOT%boot_port.py" --write-active --print-port > "%TEMP%\flowform_port.txt"
if errorlevel 1 exit /b 1
set /p PORT=<"%TEMP%\flowform_port.txt"
del "%TEMP%\flowform_port.txt" >nul 2>&1

echo [FlowForm] Starting server on port %PORT%...

REM ------------------------------------------------------------
REM Start Flask server in a separate process using venv python.
REM Use run_server.py as authoritative entrypoint.
REM ------------------------------------------------------------
start "FlowForm Server" "%VENV_PY%" "%ROOT%run_server.py" --port %PORT%

REM ------------------------------------------------------------
REM Wait until the target port is reachable before opening browser.
REM ------------------------------------------------------------
"%VENV_PY%" "%ROOT%boot_port.py" --wait --port %PORT% --timeout 40
if errorlevel 1 (
  echo [FlowForm] ERROR: server did not become ready on port %PORT%.
  exit /b 1
)

echo [FlowForm] Ready at http://127.0.0.1:%PORT%/ready
start "" "http://127.0.0.1:%PORT%/ready"

endlocal
