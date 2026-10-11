@echo off
title [tinyb] TinyBox
rem Start TinyBox from its own folder.
rem RESTART in the sysop console ends TinyBox with code 3: it starts again here.
cd /d "%~dp0"
set TINYBOX_LAUNCHER=1
:start
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 -m tinybox -c tinybox.conf %*
) else (
    python -m tinybox -c tinybox.conf %*
)
if %errorlevel%==3 (
    echo [tinyb] Restart ...
    goto start
)
pause
