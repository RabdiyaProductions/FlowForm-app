@echo off
setlocal
set "ROOT=%~dp0..\"
set "URL=http://127.0.0.1:5203/diagnostics"
if exist "%ROOT%meta.json" (
  for /f "tokens=2 delims=:," %%A in ('findstr /i "\"port\"" "%ROOT%meta.json"') do set PORT_RAW=%%A
  set PORT_RAW=%PORT_RAW: =%
  set PORT_RAW=%PORT_RAW:"=%
  if not "%PORT_RAW%"=="" set "URL=http://127.0.0.1:%PORT_RAW%/diagnostics"
)
start "" "%URL%"
endlocal
