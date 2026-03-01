@echo off
setlocal
set "ROOT=%~dp0..\"
python "%ROOT%tools\check_structure.py"
if errorlevel 1 exit /b %errorlevel%
python "%ROOT%tools\run_full_tests.py"
exit /b %errorlevel%
