@echo off
setlocal EnableDelayedExpansion

REM FlowForm run: activate venv, resolve PORT from .env (default 5400), start app, open browser.
set "ROOT=%~dp0"
set "VENV_ACT=%ROOT%.venv\Scripts\activate.bat"

if not exist "%VENV_ACT%" (
  echo [FlowForm] ERROR: .venv missing. Run 00_setup_all.bat first.
  exit /b 1
)

set "PORT=5400"
if exist "%ROOT%.env" (
  for /f "usebackq tokens=1,* delims==" %%A in ("%ROOT%.env") do (
    if /I "%%A"=="PORT" set "PORT=%%B"
  )
)

call "%VENV_ACT%"

echo [FlowForm] Starting on port !PORT!...
start "FlowForm Browser" cmd /c "timeout /t 2 /nobreak >nul & start "" "http://127.0.0.1:!PORT!/""
python "%ROOT%app_server.py"
