@echo off
title [kisshb] kisshub
rem Start kisshub (owns the KISS TNC) from the TinyBox folder.
rem Needs pyserial once:  py -3 -m pip install pyserial
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 -m kisshub -c kisshub.conf %*
) else (
    python -m kisshub -c kisshub.conf %*
)
pause
