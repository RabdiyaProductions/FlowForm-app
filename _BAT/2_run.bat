@echo off
setlocal
set "ROOT=%~dp0..\"
set "PORT=5203"

if exist "%ROOT%meta.json" (
  for /f "tokens=2 delims=:," %%A in ('findstr /i "\"port\"" "%ROOT%meta.json"') do set PORT_RAW=%%A
  set PORT_RAW=%PORT_RAW: =%
  set PORT_RAW=%PORT_RAW:"=%
  if not "%PORT_RAW%"=="" set "PORT=%PORT_RAW%"
)

set "PY=%ROOT%.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

echo [FlowForm] Deterministic run port: %PORT%
start "FlowForm App" "%PY%" "%ROOT%run_server.py" --port %PORT%
endlocal
