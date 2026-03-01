@echo off
setlocal
set "ROOT=%~dp0..\"
call "%ROOT%_run_tests.bat"
endlocal
