@echo off
setlocal
set "ROOT=%~dp0..\"
if exist "%ROOT%01_run_all.bat" (
  call "%ROOT%01_run_all.bat"
) else (
  echo Missing run entrypoint: %ROOT%01_run_all.bat
  exit /b 1
)
endlocal
