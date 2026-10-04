@echo off
rem Run all brocast tests from the brocast folder
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 -m unittest discover -s tests -t . -v
) else (
    python -m unittest discover -s tests -t . -v
)
pause
