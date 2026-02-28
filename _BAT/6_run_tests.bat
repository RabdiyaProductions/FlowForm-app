@echo off
setlocal
set "ROOT=%~dp0..\"
python "%ROOT%tools\run_full_tests.py"
exit /b %errorlevel%
