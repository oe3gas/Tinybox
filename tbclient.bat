@echo off
title [tbcli] TinyBox client
rem Start the TinyBox client from its own folder
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 -m tbclient -c tbclient.conf %*
) else (
    python -m tbclient -c tbclient.conf %*
)
pause
