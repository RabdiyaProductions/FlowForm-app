@echo off
setlocal
set "ROOT=%~dp0..\"
if exist "%ROOT%00_setup_all.bat" (
  call "%ROOT%00_setup_all.bat"
) else (
  echo Missing setup entrypoint: %ROOT%00_setup_all.bat
  exit /b 1
)
endlocal
