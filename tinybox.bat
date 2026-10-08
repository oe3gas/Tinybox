@echo off
title [tinyb] TinyBox
rem Start TinyBox from its own folder
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 -m tinybox -c tinybox.conf %*
) else (
    python -m tinybox -c tinybox.conf %*
)
pause
