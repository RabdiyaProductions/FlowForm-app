@echo off
setlocal
set "ROOT=%~dp0..\"
call "%ROOT%00_setup.bat"
set "EXIT_CODE=%ERRORLEVEL%"

set "_NEED_PAUSE="
echo %cmdcmdline% | findstr /I " /c " >nul && set "_NEED_PAUSE=1"
if defined _NEED_PAUSE (
  echo.
  echo [FlowForm] Script finished with exit code %EXIT_CODE%.
  pause
)

endlocal & exit /b %EXIT_CODE%
