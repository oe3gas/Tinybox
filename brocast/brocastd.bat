@echo off
rem Start brocastd from the brocast folder
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 -m brocast.daemon -c brocastd.conf
) else (
    python -m brocast.daemon -c brocastd.conf
)
pause
