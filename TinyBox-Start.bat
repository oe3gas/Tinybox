@echo off
rem TinyBox Steuerkonsole (CR138): update (git pull), then start, watch, stop the
rem programs of this station in one window.
rem   TinyBox-Start.bat      programs from tbstart.conf
rem   TinyBox-Start.bat 4    profile 4 for this run (autostart): 1 client only,
rem                          2 + TinyBox, 3 + brocast, 4 all
rem Details: INSTALL.md
cd /d "%~dp0"
title TinyBox Steuerkonsole
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 -m tbstart %*
) else (
    python -m tbstart %*
)
if errorlevel 1 pause
