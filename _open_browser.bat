@echo off
setlocal

set "ROOT=%~dp0"
set "VENV_PY=%ROOT%.venv\Scripts\python.exe"
if not exist "%VENV_PY%" (
  echo [FlowForm] ERROR: venv missing. Run setup first.
  exit /b 1
)

if not exist "%ROOT%ACTIVE_PORTS.json" (
  echo [FlowForm] ERROR: ACTIVE_PORTS.json not found. Run _run.bat first.
  exit /b 1
)

"%VENV_PY%" -c "import json,sys; p=json.load(open(r'%ROOT%ACTIVE_PORTS.json','r',encoding='utf-8')).get('port'); print(p if p else ''); sys.exit(0 if p else 1)" > "%TEMP%\flowform_port.txt"
if errorlevel 1 (
  del "%TEMP%\flowform_port.txt" >nul 2>&1
  echo [FlowForm] ERROR: could not read port from ACTIVE_PORTS.json.
  exit /b 1
)
set /p PORT=<"%TEMP%\flowform_port.txt"
del "%TEMP%\flowform_port.txt" >nul 2>&1

start "" "http://127.0.0.1:%PORT%/ready"
endlocal
