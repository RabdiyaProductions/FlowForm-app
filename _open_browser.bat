@echo off
setlocal

set "ROOT=%~dp0"
set "VENV_PY=%ROOT%.venv\Scripts\python.exe"
if not exist "%VENV_PY%" set "VENV_PY=python"

"%VENV_PY%" "%ROOT%boot_port.py" --write-active --print-port > "%TEMP%\flowform_port.txt"
if errorlevel 1 exit /b 1
set /p PORT=<"%TEMP%\flowform_port.txt"
del "%TEMP%\flowform_port.txt" >nul 2>&1

start "" "http://127.0.0.1:%PORT%/ready"
endlocal
