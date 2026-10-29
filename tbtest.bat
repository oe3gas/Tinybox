@echo off
rem tbtest - Testbed fuer TinyBox (PLANUNG 27, tbtest\README.md)
rem   tbtest init                 Testbed-Verzeichnis anlegen (Standard: ..\tinybox-testbed)
rem   tbtest run                  4 User, alle Funktionen, 5 Minuten
rem   tbtest run -u 10 -t 10m     10 User, 10 Minuten
rem   tbtest report / box / reset / funcs
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 -m tbtest %*
) else (
    python -m tbtest %*
)
