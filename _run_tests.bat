@echo off
setlocal
set "ROOT=%~dp0"
set "VENV_PY=%ROOT%.venv\Scripts\python.exe"
if not exist "%VENV_PY%" (
  echo [FlowForm] ERROR: venv missing. Run setup first.
  exit /b 1
)

"%VENV_PY%" "%ROOT%tools\check_structure.py"
if errorlevel 1 exit /b %errorlevel%
"%VENV_PY%" "%ROOT%tools\run_full_tests.py"
exit /b %errorlevel%
