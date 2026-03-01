@echo off
setlocal

set "ROOT=%~dp0"
set "VENV_PY=%ROOT%.venv\Scripts\python.exe"
if not exist "%VENV_PY%" (
  echo [FlowForm] ERROR: venv missing. Run 00_setup.bat first.
  exit /b 1
)

"%VENV_PY%" "%ROOT%boot_port.py" --write-active --print-port > "%TEMP%\flowform_port.txt"
if errorlevel 1 exit /b 1
set /p PORT=<"%TEMP%\flowform_port.txt"
del "%TEMP%\flowform_port.txt" >nul 2>&1

echo [FlowForm] Starting server on port %PORT%...
start "FlowForm Server" cmd /k ""%VENV_PY%" "%ROOT%run_server.py" --port %PORT%"

"%VENV_PY%" -c "import time,sys,urllib.request;url='http://127.0.0.1:%PORT%/health';end=time.time()+40;ok=False
while time.time()<end:

  try:
    ok=urllib.request.urlopen(url,timeout=2).status==200
  except Exception:
    ok=False
  if ok: break
  time.sleep(0.5)
sys.exit(0 if ok else 1)"
if errorlevel 1 (
  echo [FlowForm] ERROR: server did not pass /health on port %PORT%.
start "FlowForm Server" "%VENV_PY%" "%ROOT%run_server.py" --port %PORT%

"%VENV_PY%" "%ROOT%boot_port.py" --wait --port %PORT% --timeout 40
if errorlevel 1 (
  echo [FlowForm] ERROR: server did not become ready on port %PORT%.
  exit /b 1
)

echo [FlowForm] Ready at http://127.0.0.1:%PORT%/ready
start "" "http://127.0.0.1:%PORT%/ready"

endlocal
